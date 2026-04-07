import argparse
import logging
import os
import sys
import uuid

from alibabacloud_iacservice20210806 import models as ia_cservice_20210806_models
from alibabacloud_iacservice20210806.client import Client as IaCService20210806Client
from alibabacloud_tea_openapi import models as open_api_models

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Constants
IAC_ENDPOINT = "iac.{}.aliyuncs.com"

parser = argparse.ArgumentParser(
    description="trigger stack")
parser.add_argument('--region', help='The region in which the stack is located.',
                    default=os.environ.get('IAC_REGION'))
parser.add_argument('--code_module_id', help='The id of the module.',
                    default=os.environ.get('CODE_MODULE_ID'))
parser.add_argument('--action', help='The action of operation.',
                    default=os.environ.get('ACTION'))
parser.add_argument('--code_module_version', help='The version of the module.',
                    default=os.environ.get('CODE_MODULE_VERSION'))
parser.add_argument('--change_folders', help='The change folders of the code.',
                    default=os.environ.get('CHANGE_FOLDERS'))

def validate_arguments(args):
    """Validate command line arguments"""
    errors = []
    if not args.region:
        errors.append(
            "region must be provided either as argument or via IAC_REGION environment variable")
    if not args.code_module_id:
        errors.append(
            "code_module_id must be provided either as argument or via CODE_MODULE_ID environment variable")
    if not args.action:
        errors.append(
            "action must be provided either as argument or via ACTION environment variable")
    if not args.code_module_version:
        errors.append(
            "code_module_version must be provided either as argument or via CODE_MODULE_VERSION environment variable")
    if not args.change_folders:
        errors.append(
            "change_folders must be provided either as argument or via CHANGE_FOLDERS environment variable")
    if errors:
        for error in errors:
            logger.error(f"Validation error: {error}")
        return False
    return True


def validate_configuration(region, code_module_id):
    """Validate configuration"""
    try:
        if not region or len(region) < 3:
            logger.error("Invalid region format")
            return False

        if not code_module_id or len(code_module_id) < 3:
            logger.error("Invalid code_module_id format")
            return False

        access_key = os.environ.get('IAC_ACCESS_KEY_ID')
        secret_key = os.environ.get('IAC_ACCESS_KEY_SECRET')

        if not access_key or not secret_key:
            logger.error(
                "Missing required environment variables: IAC_ACCESS_KEY_ID or IAC_ACCESS_KEY_SECRET")
            return False

        logger.info("Configuration validation passed")
        logger.info(f"access_key: {access_key}")
        return True

    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        return False


def create_iac_client(region):
    """Create IaCService client"""
    try:
        logger.info(f"Creating IaCService client for region: {region}")

        config = open_api_models.Config()
        config.access_key_secret = os.environ.get('IAC_ACCESS_KEY_SECRET')
        config.access_key_id = os.environ.get('IAC_ACCESS_KEY_ID')
        config.region_id = region
        config.endpoint = IAC_ENDPOINT.format(region)
        logger.info("IaCService client created successfully")
        return IaCService20210806Client(config)
    except Exception as e:
        logger.error(f"Failed to create IaCService client: {e}")
        return None

def trigger_stack(client, code_module_id, action, code_module_version, change_folders):
    """trigger stack"""
    try:
        logger.info(
            f"trigger stack action: {action}, code_module_id: {code_module_id}, code_module_version: {code_module_version}, change_folders: {change_folders}")

        change_folders_list = [folder.strip() for folder in change_folders.split(',')]
        logger.info(f"Parsed change_folders list: {change_folders_list}")

        request = ia_cservice_20210806_models.TriggerStackExecutionRequest()
        request.module_id = code_module_id
        request.action = action
        request.module_version = code_module_version
        request.code_package_path = "iacservice::" + code_module_id
        request.changed_folders = change_folders_list
        request.client_token = str(uuid.uuid4())

        result = client.trigger_stack_execution(request);

        logger.info(f'trigger stack successfully\n'
                    f'Status Code: {result.status_code}\n'
                    f'Request ID: {result.body.request_id}\n'
                    f'Trigger ID: {result.body.trigger_id}')
        return True
    except Exception as e:
        logger.error(f'Failed to trigger stack: {e}')
        return False

def main():
    """Main function"""
    try:
        args = parser.parse_args()

        if not validate_arguments(args):
            return 1

        if not validate_configuration(args.region, args.code_module_id):
            return 1

        client = create_iac_client(args.region)
        if not client:
            return 1

        if trigger_stack(client, args.code_module_id, args.action, args.code_module_version, args.change_folders):
            logger.info("trigger stack completed successfully")
            return 0
        else:
            logger.error("trigger stack failed")
            return 1

    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error occurred: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
