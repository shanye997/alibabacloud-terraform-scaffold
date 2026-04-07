#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Result Parser and Formatter

This module provides functionality to poll and format execution results from API.
"""

import argparse
import logging
import os
import threading
import time
from typing import Dict, Any, Optional, Tuple, List

import yaml
from alibabacloud_iacservice20210806.client import Client as IaCService20210806Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_openapi.exceptions import ClientException

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

IAC_ENDPOINT = "iac.{}.aliyuncs.com"


def load_credentials(profile_name: str, code_path: str = "") -> Optional[Tuple[str, str]]:
    """Load credentials for a specific profile.

    First looks for profile credentials in deployments/{profile_name}/profile.yaml
    to get the access key names, then looks in the root profile.yaml to get the actual values.

    Args:
        profile_name: The name of the profile to load credentials for
        code_path: Optional code path to use for credential file location

    Returns:
        Tuple of (access_key_id, access_key_secret) or None if not found
    """
    try:
        base_path = code_path if code_path else "."
        logger.info(f"Base path: {base_path}")

        profile_credentials_path = f"{base_path}/deployments/{profile_name}/profile.yaml"

        if not os.path.exists(profile_credentials_path):
            logger.warning(f"Profile credentials file not found: {profile_credentials_path}")
            return None

        with open(profile_credentials_path, 'r') as f:
            profile_credentials = yaml.safe_load(f)

        if not isinstance(profile_credentials, dict):
            logger.error(f"Profile credentials is not a dictionary: {profile_credentials}")
            return None

        access_key_id_name = profile_credentials.get('access_key_id')
        access_key_secret_name = profile_credentials.get('access_key_secret')
        logger.info(f"Access key names: {access_key_id_name}, {access_key_secret_name}")

        if not access_key_id_name or not access_key_secret_name:
            logger.warning(f"Access key names not found in profile credentials for {profile_name}")
            return None

        access_key_id = os.getenv(access_key_id_name)
        access_key_secret = os.getenv(access_key_secret_name)

        if not access_key_id or not access_key_secret:
            logger.warning(f"Access key values not found for {profile_name}")
            return None

        logger.info(f"Loaded credentials for profile {profile_name}")
        return access_key_id, access_key_secret

    except Exception as e:
        logger.error(f"Error loading credentials for profile {profile_name}: {str(e)}")
        return None

def create_iac_client(region: str, profile_name: str, code_path: str = "") -> Optional[IaCService20210806Client]:
    """Create IaCService client with profile credentials."""
    try:
        logger.info(f"Creating IaCService client for region: {region}")

        credentials = load_credentials(profile_name, code_path)
        if not credentials:
            logger.error(f"Failed to load credentials for profile {profile_name}")
            return None

        access_key_id, access_key_secret = credentials

        config = open_api_models.Config()
        config.access_key_id = access_key_id
        config.access_key_secret = access_key_secret
        config.region_id = region
        config.endpoint = IAC_ENDPOINT.format(region)

        client = IaCService20210806Client(config)
        logger.info("IaCService client created successfully")
        return client

    except Exception as e:
        logger.error(f"Failed to create IaCService client: {e}")
        return None


def get_trigger_result(client: IaCService20210806Client, trigger_id: str) -> Optional[Dict]:
    """Get trigger result from API.

    Returns:
        Dict: 当状态为终态(Success/Errored)时返回数据
        None: 当状态为非终态或发生可重试异常时返回None
    """
    try:
        logger.info(f"Getting trigger result for trigger_id: {trigger_id}")
        result = client.get_stack_execution_result(trigger_id)

        logger.info(f'get trigger result successfully\n'
                    f'Status Code: {result.status_code}\n'
                    f'Request ID: {result.body.request_id}')

        body = result.body
        if hasattr(body, 'to_map') and callable(getattr(body, 'to_map')):
            data = body.to_map()
        elif isinstance(body, dict):
            data = body
        else:
            data = vars(body) if hasattr(body, '__dict__') else {'data': body}

        status = data.get('triggeredStatus', '')
        if status not in ['Success', 'Errored']:
            logger.info(
                f"Trigger {trigger_id} status is '{status}', "
                f"not a terminal state, continuing to poll..."
            )
            return None

        logger.info(f"Trigger {trigger_id} reached terminal state: '{status}'")
        return data

    except ClientException as e:
        error_message = str(e)
        error_str = repr(e)
        logger.error(f'Client exception, Failed to get  trigger result: {e}, error_str: {error_str}, error_message: {error_message}')
        return {
            'trigger_id': trigger_id,
            'triggeredStatus': 'Errored',
            'message': error_message
        }
    except Exception as e:
        error_message = str(e)
        error_str = repr(e)
        logger.error(f'Failed to get trigger result: {e}, error_str: {error_str}, error_message: {error_message}')
        return None


def format_execution_result(data: Dict[str, Any]) -> str:
    """Format execution result data for display in Markdown format."""
    try:
        output = []

        status = data.get('triggeredStatus')
        trigger_id = data.get('triggerId')

        if not status and not trigger_id:
            trigger_id = 'Unknown'
            status = 'Unknown'
        elif not status and trigger_id:
            status = 'Success'
        elif status and not trigger_id:
            trigger_id = 'Unknown'

        message = data.get('message', '')

        status_emoji = "✅" if status == "Success" else "❌" if status == "Errored" else "⚪"

        output.append("## 📋 Execution Information")
        output.append("")
        output.append(f"| Field | Value |")
        output.append(f"|-------|-------|")
        output.append(f"| **Trigger ID** | `{trigger_id}` |")
        output.append(f"| **Trigger Status** | {status_emoji} {status} |")

        if message:
            output.append(f"| **Message** | {message} |")

        output.append("")

        stacks = data.get('stackResults', [])
        if stacks:
            output.append(f"## 📦 Stacks ({len(stacks)} total)")
            output.append("")

            for i, stack in enumerate(stacks, 1):
                stack_name = stack.get('stackName', 'Unknown')
                stack_status = stack.get('stackStatus', 'Unknown')
                stack_message = stack.get('message', '')

                stack_emoji = "✅" if stack_status == "Deployed" or stack_status == "DetectTriggered" else "❌" if stack_status == "Errored" else "⚪"

                output.append(f"### {i}. Stack: {stack_name}")
                output.append("")
                output.append(f"**Status:** {stack_emoji} {stack_status}")
                output.append("")
                if stack_message:
                    output.append(f"**Message:** {stack_message}")
                    output.append("")

                deployments = stack.get('deployments', [])
                if deployments:
                    output.append(f"#### 🚀 Deployments ({len(deployments)} total)")
                    output.append("")
                    output.append("| Deployment | Status | Job Result | Details |")
                    output.append("|------------|--------|------------|---------|")

                    for deployment in deployments:
                        deploy_name = deployment.get('deploymentName') or deployment.get('deployment_name', 'Unknown')
                        deploy_status = deployment.get('status', 'Unknown')
                        job_result = deployment.get('jobResult', '')
                        deploy_url = deployment.get('url', '')

                        deploy_emoji = {
                            "Applied": "✅",
                            "Planned": "✅",
                            "PlannedAndFinished": "✅",
                            "DetectInProgress": "✅",
                            "Errored": "❌"
                        }.get(deploy_status, "⚪")

                        job_result_display = f"`{job_result}`" if job_result else "-"
                        details_link = f'<a href="{deploy_url}" target="_blank">View Details</a>' if deploy_url else "-"

                        output.append(
                            f"| {deploy_name} | {deploy_emoji} {deploy_status} | {job_result_display} | {details_link} |")

                    output.append("")
                else:
                    output.append("#### 🚀 Deployments")
                    output.append("")
                    output.append("*No deployments found*")
                    output.append("")

                if i < len(stacks):
                    output.append("---")
                    output.append("")
        else:
            output.append("## 📦 Stacks")
            output.append("")
            output.append("*No stacks found*")
            output.append("")

        return "\n".join(output)

    except Exception as e:
        return f"## ❌ Error\n\nError formatting result: `{str(e)}`"


def parse_result_path(result_path: str) -> List[tuple]:
    """Parse result path string into list of profile and trigger ID pairs."""
    results = []
    if not result_path:
        return results

    entries = result_path.split(';')
    for entry in entries:
        if '@' in entry:
            profile, trigger_id = entry.split('@')
            results.append((profile.strip(), trigger_id.strip()))

    return results


def poll_trigger_result(profile: str, trigger_id: str, region: str, code_path: str,
                        max_wait_time: int, results: List, lock: threading.Lock) -> None:
    """Poll API for trigger result in a separate thread."""
    poll_interval = 10

    logger.info(f"Processing profile: {profile}")

    client = create_iac_client(region, profile, code_path)
    if not client:
        logger.error(f"Failed to create IAC client for profile {profile}")
        return

    start_time = time.time()
    attempt = 0

    while True:
        attempt += 1
        elapsed_time = time.time() - start_time

        logger.info(f"Attempt #{attempt} for {profile} (Elapsed: {elapsed_time:.1f}s)")

        if elapsed_time > max_wait_time:
            logger.warning(f"Maximum wait time ({max_wait_time}s) exceeded for profile {profile}")
            break

        result = get_trigger_result(client, trigger_id)
        if result:
            logger.info(
                f"Terminal state reached for {profile}, "
                f"status: {result.get('triggeredStatus')}"
            )
            with lock:
                results.append({'profile': profile, 'result': result})
            break

        logger.info(
            f"Trigger still in progress for {profile}, "
            f"waiting {poll_interval}s before next attempt..."
        )
        time.sleep(poll_interval)


def main():
    """Main function for command line usage."""
    parser = argparse.ArgumentParser(
        description="Poll and format execution results from API"
    )
    parser.add_argument(
        '--code-path',
        type=str,
        required=True,
        help='Code path for credential file location'
    )
    parser.add_argument(
        '--result-path',
        type=str,
        required=True,
        help='Result path in format: profile1@triggerId1;profile2@triggerId2'
    )
    parser.add_argument(
        '--output-file',
        type=str,
        required=True,
        help='Output file path to write the formatted result'
    )
    parser.add_argument(
        '--max-wait-time',
        type=int,
        default=600,
        help='Maximum wait time in seconds (default: 600)'
    )

    args = parser.parse_args()

    try:
        entries = parse_result_path(args.result_path)
        if not entries:
            logger.error("No valid entries found in result path")
            exit(1)

        threads = []
        all_results = []
        lock = threading.Lock()

        for profile, trigger_id in entries:
            thread = threading.Thread(
                target=poll_trigger_result,
                args=(profile, trigger_id, 'cn-zhangjiakou', args.code_path,
                      args.max_wait_time, all_results, lock)
            )
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        if not all_results:
            logger.error("Failed to retrieve results")
            exit(1)

        formatted_outputs = []
        for result in all_results:
            profile = result['profile']
            formatted_result = format_execution_result(result['result'])
            formatted_outputs.append(f"## Profile: {profile}\n\n{formatted_result}")

        final_output = "\n\n---\n\n".join(formatted_outputs)

        if args.output_file:
            with open(args.output_file, 'w', encoding='utf-8') as f:
                f.write(final_output)
            logger.info(f"Result written to file: {args.output_file}")

        print(final_output)

    except KeyboardInterrupt:
        logger.warning("Operation cancelled by user")
        exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        exit(1)


if __name__ == "__main__":
    main()
