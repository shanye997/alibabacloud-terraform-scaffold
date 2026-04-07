#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OSS Result Parser and Formatter

This module provides functionality to poll, download, and format execution results from OSS.
"""

from calendar import c
import os
import json
import time
import argparse
import yaml
import threading
from typing import Dict, Any, Optional, Tuple, List
from urllib.parse import urlparse
import alibabacloud_oss_v2 as oss


def parse_oss_url(oss_url: str) -> Tuple[Optional[str], Optional[str], Optional[str], list[str]]:
    """Parse OSS URL to extract bucket, key, and region information.

    Supports format:
    - oss::https://bucket-name.oss-region.aliyuncs.com/path/to/object
    """
    errors = []

    if not oss_url:
        errors.append('OSS URL cannot be empty')
        return None, None, None, errors

    try:
        # Handle oss::https:// format
        if oss_url.startswith('oss::https://'):
            # Remove oss::https:// prefix
            url_without_prefix = oss_url[13:]
        else:
            errors.append('OSS URL must start with oss::https://')
            return None, None, None, errors

        # Parse the URL using urllib
        parsed_url = urlparse(f"https://{url_without_prefix}")

        if not parsed_url.hostname:
            errors.append('Invalid OSS URL format: missing hostname')
            return None, None, None, errors

        if not parsed_url.path or parsed_url.path == '/':
            errors.append('Invalid OSS URL format: missing object key')
            return None, None, None, errors

        # Extract object key (remove leading slash)
        object_key = parsed_url.path[1:] if parsed_url.path.startswith(
            '/') else parsed_url.path

        if not object_key:
            errors.append('Object key cannot be empty')
            return None, None, None, errors

        # Parse hostname: bucket-name.oss-region.aliyuncs.com
        hostname = parsed_url.hostname

        if not hostname.endswith('.aliyuncs.com'):
            errors.append('OSS URL must use aliyuncs.com domain')
            return None, None, None, errors

        # Remove .aliyuncs.com suffix and split by dots
        host_without_suffix = hostname[:-13]  # Remove '.aliyuncs.com'
        host_parts = host_without_suffix.split('.')

        if len(host_parts) < 2:
            errors.append(
                'Invalid OSS URL format: missing bucket or region information')
            return None, None, None, errors

        # First part is bucket name
        bucket_name = host_parts[0]

        if not bucket_name:
            errors.append('Bucket name cannot be empty')
            return None, None, None, errors

        # Find the oss-region part (should start with 'oss-')
        region = None
        for part in host_parts[1:]:
            if part.startswith('oss-'):
                region = part[4:]  # Remove 'oss-' prefix
                break

        if not region:
            errors.append('Region information not found in URL')
            return None, None, None, errors

        return bucket_name, object_key, region, errors

    except Exception as e:
        errors.append(f'Failed to parse OSS URL: {str(e)}')
        return None, None, None, errors


def parse_multi_oss_urls(oss_urls: str) -> List[Tuple[str, str, str, str]]:
    """Parse multiple OSS URLs separated by semicolon, each with optional profile name.
    
    Format: profile1@oss::https://bucket1.oss-region1.aliyuncs.com/path/to/object;oss::https://bucket2.oss-region2.aliyuncs.com/path/to/object
    
    Returns:
        List of tuples: (profile_name, bucket_name, object_key, region)
    """
    results = []

    # Split by semicolon to get individual URL entries
    entries = oss_urls.split(';')

    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue

        # Check if entry has profile name prefix (profile@url)
        if '@' in entry and not entry.startswith('oss::https://'):
            profile_name, url = entry.split('@', 1)
            profile_name = profile_name.strip()
            url = url.strip()
        else:
            profile_name = "default"
            url = entry

        # Parse the URL
        bucket, key, region, errors = parse_oss_url(url)
        if not errors and bucket and key and region:
            results.append((profile_name, bucket, key, region))
        else:
            print(
                f"⚠️  Warning: Failed to parse URL for profile '{profile_name}': {errors}")

    return results


def load_credentials(profile_name: str, code_path: str = "") -> Optional[Tuple[str, str]]:
    """Load credentials for a specific profile.
    
    First looks for profile credentials in deployments/{profile_name}/credentials.yaml
    to get the access key names, then looks in the root credentials.yaml to get the actual values.
    
    Args:
        profile_name: The name of the profile to load credentials for
        code_path: Optional code path to use for credential file location
        
    Returns:
        Tuple of (access_key_id, access_key_secret) or None if not found
    """
    try:
        # Determine the base path for credentials
        if code_path:
            base_path = code_path
        else:
            base_path = "."

        print(f"Base path: {base_path}")

        # Path to profile credentials file
        profile_credentials_path = f"{base_path}/deployments/{profile_name}/credentials.yaml"

        # Check if profile credentials file exists
        if not os.path.exists(profile_credentials_path):
            print(
                f"⚠️  Warning: Profile credentials file not found: {profile_credentials_path}")
            return None

        # Load profile credentials to get key names
        with open(profile_credentials_path, 'r') as f:
            profile_credentials = yaml.safe_load(f)

        # Check if profile_credentials is a dictionary
        if not isinstance(profile_credentials, dict):
            print(
                f"❌ Error: Profile credentials is not a dictionary: {profile_credentials}")
            return None

        # Get access key names from profile credentials
        access_key_id_name = profile_credentials.get('access_key_id')
        access_key_secret_name = profile_credentials.get('access_key_secret')
        print(
            f"Access key names: {access_key_id_name}, {access_key_secret_name}")

        if not access_key_id_name or not access_key_secret_name:
            print(
                f"⚠️  Warning: Access key names not found in profile credentials for {profile_name}")
            return None

        # Load root credentials file to get actual values
        root_credentials_path = "oss_credentials.yaml"
        if not os.path.exists(root_credentials_path):
            print(
                f"⚠️  Warning: Root credentials file not found: {root_credentials_path}")
            return None

        # Load root credentials file using YAML parser
        with open(root_credentials_path, 'r') as f:
            root_credentials = yaml.safe_load(f)

        # Check if root_credentials is a dictionary
        if not isinstance(root_credentials, dict):
            print(
                f"❌ Error: Root credentials is not a dictionary: {root_credentials}")
            return None

        # Get actual access key values
        access_key_id = root_credentials.get(access_key_id_name)
        access_key_secret = root_credentials.get(access_key_secret_name)

        if not access_key_id or not access_key_secret:
            print(
                f"⚠️  Warning: Access key values not found for {profile_name}")
            return None

        print(
            f"Loaded credentials for profile {profile_name}: {access_key_id[:5]}***")
        return access_key_id, access_key_secret

    except Exception as e:
        print(
            f"❌ Error loading credentials for profile {profile_name}: {str(e)}")
        return None


def create_oss_client(region: str, profile_name: str = "default", code_path: str = "") -> Optional[oss.Client]:
    """Create OSS client with proper credentials and configuration."""
    try:
        # Load credentials for the profile
        credentials = load_credentials(profile_name, code_path)

        if credentials:
            access_key_id, access_key_secret = credentials

            # Create credentials provider with specific credentialss
            credentials_provider = oss.credentials.StaticCredentialsProvider(
                access_key_id=access_key_id,
                access_key_secret=access_key_secret
            )
        else:
            # Fallback to environment variable credentials provider
            print(
                f"⚠️  Warning: Using environment variable credentials for profile {profile_name}")
            credentials_provider = oss.credentials.EnvironmentVariableCredentialsProvider()

        cfg = oss.config.load_default()
        cfg.credentials_provider = credentials_provider
        cfg.region = region

        return oss.Client(cfg)

    except Exception as e:
        print(f"Failed to create OSS client: {str(e)}")
        return None


def get_oss_object_content(client: oss.Client, bucket: str, key: str) -> Optional[str]:
    """Get object content from OSS if it exists."""
    try:
        if not client.is_object_exist(bucket=bucket, key=key):
            return None

        result = client.get_object(
            oss.GetObjectRequest(bucket=bucket, key=key))

        if result and result.body:
            content = result.body.read()
            return content.decode('utf-8') if isinstance(content, bytes) else str(content)

        return None

    except Exception as e:
        print(f"Error getting object content: {str(e)}")
        return None


def format_execution_result(data: Dict[str, Any]) -> str:
    """Format execution result data for display in Markdown format."""
    try:
        output = []

        # Main execution info
        execution_id = data.get('id', 'Unknown')
        status = data.get('triggeredStatus', 'Unknown')
        message = data.get('message', '')

        # Status with emoji
        status_emoji = "✅" if status == "Success" else "❌" if status == "Errored" else "⚪"

        output.append("## 📋 Execution Information")
        output.append("")
        output.append(f"| Field | Value |")
        output.append(f"|-------|-------|")
        output.append(f"| **Execution ID** | `{execution_id}` |")
        output.append(f"| **Trigger Status** | {status_emoji} {status} |")

        if message:
            output.append(f"| **Message** | {message} |")

        output.append("")

        # Stack details
        stacks = data.get('stacks', [])
        if stacks:
            output.append(f"## 📦 Stacks ({len(stacks)} total)")
            output.append("")

            for i, stack in enumerate(stacks, 1):
                stack_name = stack.get('stackName', 'Unknown')
                stack_status = stack.get('stackStatus', 'Unknown')
                stack_message = stack.get('message', '')

                # Stack status with emoji
                stack_emoji = "✅" if stack_status == "Deployed" else "❌" if stack_status == "Errored" else "⚪"

                output.append(f"### {i}. Stack: {stack_name}")
                output.append("")
                output.append(f"**Status:** {stack_emoji} {stack_status}")
                output.append("")
                if stack_message:
                    output.append(f"**Message:** {stack_message}")
                    output.append("")

                # Deployment details
                deployments = stack.get('deployments', [])
                if deployments:
                    output.append(
                        f"#### 🚀 Deployments ({len(deployments)} total)")
                    output.append("")

                    # Create deployment table
                    output.append(
                        "| Deployment | Status | Job Result | Details |")
                    output.append(
                        "|------------|--------|------------|---------|")

                    for deployment in deployments:
                        deploy_name = deployment.get('deploymentName') or deployment.get(
                            'deployment_name', 'Unknown')
                        deploy_status = deployment.get('status', 'Unknown')
                        job_result = deployment.get('jobResult', '')
                        deploy_url = deployment.get('url', '')

                        # Deployment status with emoji
                        deploy_emoji = {
                            "Applied": "✅",
                            "Planned": "✅",
                            "PlannedAndFinished": "✅",
                            "Errored": "❌"
                        }.get(deploy_status, "⚪")

                        # Format job result
                        job_result_display = f"`{job_result}`" if job_result else "-"

                        # Format details link
                        details_link = f'<a href="{deploy_url}" target="_blank">View Details</a>' if deploy_url else "-"

                        output.append(
                            f"| {deploy_name} | {deploy_emoji} {deploy_status} | {job_result_display} | {details_link} |")

                    output.append("")
                else:
                    output.append("#### 🚀 Deployments")
                    output.append("")
                    output.append("*No deployments found*")
                    output.append("")

                # Add separator between stacks
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


def poll_oss_result(code_path: str, profile_name: str, bucket: str, key: str, region: str, max_wait_time: int, results: List, lock: threading.Lock) -> None:
    """Poll OSS URL for result file in a separate thread."""
    poll_interval = 10  # Fixed polling interval: 10 seconds

    print(f"🔄 Processing profile: {profile_name}")

    # Create OSS client with profile-specific credentials
    client = create_oss_client(region, profile_name, code_path)
    if not client:
        print(f"❌ Failed to create OSS client for profile {profile_name}")
        return

    print(f"✅ OSS client created successfully for profile {profile_name}")

    # Start polling for this profile
    start_time = time.time()
    attempt = 0

    while True:
        attempt += 1
        elapsed_time = time.time() - start_time

        print(
            f"🔄 Attempt #{attempt} for {profile_name} (Elapsed: {elapsed_time:.1f}s)")

        # Check if max wait time exceeded
        if elapsed_time > max_wait_time:
            print(
                f"⏰ Maximum wait time ({max_wait_time}s) exceeded for profile {profile_name}")
            break

        # Check if object exists and get content
        content = get_oss_object_content(client, bucket, key)
        if content:
            print(
                f"✅ Object found for {profile_name}! Downloaded {len(content)} characters")

            # Parse JSON
            try:
                data = json.loads(content)
                print(
                    f"✅ JSON content validated successfully for {profile_name}")

                # Add profile information to the data
                data['profile'] = profile_name

                # Add result to shared results list
                with lock:
                    results.append(data)
                break
            except json.JSONDecodeError as e:
                print(f"❌ Invalid JSON format for {profile_name}: {str(e)}")
                break
            except Exception as e:
                print(
                    f"❌ Failed to parse content for {profile_name}: {str(e)}")
                break
        else:
            print(
                f"⏳ Object not found for {profile_name}, waiting {poll_interval}s...")
            time.sleep(poll_interval)


def poll_and_process_oss_result(oss_url: str, max_wait_time: int = 600, output_file: Optional[str] = None, code_path: str = "") -> Optional[str]:
    """Poll OSS URL for result file, download and format when available."""
    poll_interval = 10  # Fixed polling interval: 10 seconds

    print(f"\n🔍 Starting to poll OSS URL(s): {oss_url}")
    print(
        f"⏱️  Poll interval: {poll_interval}s, Max wait time: {max_wait_time}s")
    if output_file:
        print(f"📄 Output will be written to: {output_file}")
    print("")

    # Parse multiple OSS URLs
    oss_entries = parse_multi_oss_urls(oss_url)
    if not oss_entries:
        print("❌ No valid OSS URLs found")
        return None

    print(f"📋 Found {len(oss_entries)} OSS entry(s) to process:")
    for profile_name, bucket, key, region in oss_entries:
        print(
            f"   - Profile: {profile_name}, Bucket: {bucket}, Key: {key}, Region: {region}")
    print("")

    # Process each OSS entry in parallel using threads
    threads = []
    all_results = []
    lock = threading.Lock()

    # Create and start threads for each profile
    for profile_name, bucket, key, region in oss_entries:
        thread = threading.Thread(
            target=poll_oss_result,
            args=(code_path, profile_name, bucket, key, region,
                  max_wait_time, all_results, lock)
        )
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    if not all_results:
        print("❌ Failed to retrieve results from any OSS location")
        return None

    # Format all results
    formatted_outputs = []
    for data in all_results:
        profile_name = data.get('profile', 'Unknown')
        formatted_result = format_execution_result(data)
        formatted_outputs.append(
            f"## Profile: {profile_name}\n\n{formatted_result}")

    final_output = "\n\n---\n\n".join(formatted_outputs)

    # Write to file if output_file is specified
    if output_file:
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(final_output)
            print(f"📄 Result written to file: {output_file}")
        except Exception as e:
            print(
                f"⚠️  Warning: Failed to write to file {output_file}: {str(e)}")

    return final_output


def main():
    """Main function for command line usage."""
    parser = argparse.ArgumentParser(
        description="Poll, download and format execution results from OSS"
    )
    parser.add_argument(
        '--oss-url',
        help='OSS URL(s) to poll in format: [profile1@]oss::https://bucket1.oss-region1.aliyuncs.com/path/to/file;[profile2@]oss::https://bucket2.oss-region2.aliyuncs.com/path/to/file'
    )
    parser.add_argument(
        '--max-wait-time',
        type=int,
        default=600,
        help='Maximum wait time in seconds (default: 3600)'
    )
    parser.add_argument(
        '--output-file',
        type=str,
        help='Output file path to write the formatted result (optional)'
    )
    parser.add_argument(
        '--code-path',
        type=str,
        help='Code path for credential file location (optional)'
    )

    args = parser.parse_args()

    try:
        result = poll_and_process_oss_result(
            oss_url=args.oss_url,
            max_wait_time=args.max_wait_time,
            output_file=args.output_file,
            code_path=args.code_path
        )

        if result:
            print(result)
        else:
            print("❌ Failed to process OSS result")
            exit(1)

    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
        exit(0)
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        exit(1)


if __name__ == "__main__":
    main()
