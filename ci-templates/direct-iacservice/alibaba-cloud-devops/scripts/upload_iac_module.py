import argparse
import logging
import os
import sys
from io import BytesIO

from alibabacloud_iacservice20210806 import models as ia_cservice_20210806_models
from alibabacloud_iacservice20210806.client import Client as IaCService20210806Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models

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
    description="upload code to iac module")
parser.add_argument('--region', help='The region in which the module is located.',
                    default=os.environ.get('IAC_REGION'))
parser.add_argument('--code_module_id', help='The id of the module.',
                    default=os.environ.get('CODE_MODULE_ID'))
parser.add_argument(
    '--file_path', help='The path of Upload file.', required=True)

def validate_arguments(args):
    """Validate command line arguments"""
    errors = []
    if not args.region:
        errors.append(
            "Region must be provided either as argument or via IAC_REGION environment variable")
    if not args.code_module_id:
        errors.append(
            "code_module_id must be provided either as argument or via CODE_MODULE_ID environment variable")
    if errors:
        for error in errors:
            logger.error(f"Validation error: {error}")
        return False
    return True


def validate_configuration(region, code_module_id):
    """Validate configuration"""
    try:
        # Validate region format
        if not region or len(region) < 3:
            logger.error("Invalid region format")
            return False

        # Validate code_module_id format
        if not code_module_id or len(code_module_id) < 3:
            logger.error("Invalid code_module_id format")
            return False

        # Check environment variables
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

def upload_file_to_iac_module(client, code_module_id, file_path):
    """Upload file to iac module"""
    try:
        logger.info(
            f"Uploading file: {file_path} to iac module: {code_module_id}")

        request = ia_cservice_20210806_models.UploadModuleAdvanceRequest()
        request.module_id = code_module_id

        with open(file_path, 'rb') as f:
            content = f.read()
            request.url_object = BytesIO(content)
        headers = {}
        result = client.upload_module_advance("ModuleVersion", request, headers, util_models.RuntimeOptions())

        logger.info(f'File uploaded to iac module successfully\n'
                    f'Status Code: {result.status_code}\n'
                    f'Request ID: {result.body.request_id}\n'
                    f'Version ID: {result.body.version}')
        return True
    except Exception as e:
        logger.error(f'Failed to upload file to iac module: {e}')
        return False

def main():
    """Main function"""
    try:
        args = parser.parse_args()

        # Validate arguments
        if not validate_arguments(args):
            return 1

        # Validate configuration
        if not validate_configuration(args.region, args.code_module_id):
            return 1

        # Create IaCService client
        client = create_iac_client(args.region)
        if not client:
            return 1

        # Upload file to module
        if upload_file_to_iac_module(client, args.code_module_id, args.file_path):
            logger.info("Upload process completed successfully")
            return 0
        else:
            logger.error("Upload process failed")
            return 1

    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error occurred: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
