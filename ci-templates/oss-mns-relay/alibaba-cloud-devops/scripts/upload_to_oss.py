from alibabacloud_oss_v2.models.bucket_basic import ListObjectVersionsResult
import os
import argparse
import alibabacloud_oss_v2 as oss
import logging
import sys

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
MAX_VERSIONS_TO_CHECK = 10
OSS_ENDPOINT_TEMPLATE = "oss-{}.aliyuncs.com"

parser = argparse.ArgumentParser(
    description="Create an OSS bucket for code storage")
parser.add_argument('--region', help='The region in which the bucket is located.',
                    default=os.environ.get('OSS_REGION'))
parser.add_argument('--bucket', help='The name of the bucket.',
                    default=os.environ.get('OSS_BUCKET'))
parser.add_argument('--key', help='The name of the object.', required=True)
parser.add_argument(
    '--file_path', help='The path of Upload file.', required=True)
parser.add_argument(
    '--unique_key', help='The commit id of the code package.')


def validate_arguments(args):
    """Validate command line arguments"""
    errors = []
    if not args.region:
        errors.append(
            "Region must be provided either as argument or via OSS_REGION environment variable")
    if not args.bucket:
        errors.append(
            "Bucket name must be provided either as argument or via OSS_BUCKET environment variable")

    if errors:
        for error in errors:
            logger.error(f"Validation error: {error}")
        return False
    return True


def validate_configuration(region, bucket):
    """Validate OSS configuration"""
    try:
        # Validate region format
        if not region or len(region) < 3:
            logger.error("Invalid region format")
            return False

        # Validate bucket name format
        if not bucket or len(bucket) < 3:
            logger.error("Invalid bucket name format")
            return False

        # Check environment variables
        access_key = os.environ.get('OSS_ACCESS_KEY_ID')
        secret_key = os.environ.get('OSS_ACCESS_KEY_SECRET')

        if not access_key or not secret_key:
            logger.error(
                "Missing required environment variables: OSS_ACCESS_KEY_ID or OSS_ACCESS_KEY_SECRET")
            return False

        logger.info("Configuration validation passed")
        logger.info(f"access_key: {access_key}")
        return True

    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        return False


def create_oss_client(region):
    """Create OSS client"""
    try:
        logger.info(f"Creating OSS client for region: {region}")
        credentials_provider = oss.credentials.EnvironmentVariableCredentialsProvider()
        cfg = oss.config.load_default()
        cfg.credentials_provider = credentials_provider
        cfg.region = region
        client = oss.Client(cfg)
        logger.info("OSS client created successfully")
        return client
    except Exception as e:
        logger.error(f"Failed to create OSS client: {e}")
        return None


def check_object_exists(client, bucket, key):
    """Check if object exists"""
    try:
        logger.info(f"Checking if object exists: {key} in bucket: {bucket}")
        exists = client.is_object_exist(bucket=bucket, key=key)
        logger.info(f"Object existence check result: {exists}")
        return exists
    except Exception as e:
        logger.error(f"Failed to check object existence: {e}")
        return False


def check_version_metadata(client, bucket, key, unique_key):
    """Check version metadata"""
    try:
        logger.info(f"Checking version metadata for object: {key}")
        list_result: ListObjectVersionsResult = client.list_object_versions(
            oss.ListObjectVersionsRequest(
                bucket=bucket,
                prefix=key,
                max_keys=MAX_VERSIONS_TO_CHECK
            )
        )

        if list_result.version:
            logger.info(f"Found {len(list_result.version)} versions to check")
            for version in list_result.version:
                if version.key == key:
                    try:
                        head_result = client.head_object(oss.HeadObjectRequest(
                            bucket=bucket,
                            key=key,
                            version_id=version.version_id
                        ))

                        if (head_result.metadata and
                                head_result.metadata.get('unique-key') == unique_key):
                            logger.info(f'Object {key} with unique-key {unique_key} already exists\n'
                                        f'Version ID: {head_result.version_id}')
                            return True
                    except Exception as e:
                        logger.warning(
                            f'Failed to get head object for version {version.version_id}: {e}')
                        continue
        return False
    except Exception as e:
        logger.warning(f'Failed to list object versions: {e}')
        return check_current_object_metadata(client, bucket, key, unique_key)


def check_current_object_metadata(client, bucket, key, unique_key):
    """Check current object metadata"""
    try:
        logger.info(f"Checking current object metadata for: {key}")
        result = client.head_object(oss.HeadObjectRequest(
            bucket=bucket,
            key=key
        ))
        if (result.metadata and
                result.metadata.get('unique-key') == unique_key):
            logger.info(f'Object {key} with unique-key {unique_key} already exists\n'
                        f'Version ID: {result.version_id}')
            return True
        return False
    except Exception as e:
        logger.warning(f'Failed to get current object metadata: {e}')
        return False


def upload_file_to_oss(client, bucket, key, file_path, unique_key=None):
    """Upload file to OSS"""
    try:
        logger.info(
            f"Uploading file: {file_path} to OSS bucket: {bucket}, key: {key}")

        meta_data = {}
        if unique_key:
            meta_data = {"unique-key": str(unique_key)}
            logger.info(f"Using unique key: {unique_key}")

        result = client.put_object_from_file(oss.PutObjectRequest(
            bucket=bucket,
            key=key,
            metadata=meta_data,
        ), file_path)

        logger.info(f'File uploaded to OSS successfully\n'
                    f'Status Code: {result.status_code}\n'
                    f'Request ID: {result.request_id}\n'
                    f'Version ID: {result.version_id}')
        return True
    except Exception as e:
        logger.error(f'Failed to upload file to OSS: {e}')
        return False


def main():
    """Main function"""
    try:
        args = parser.parse_args()

        # Validate arguments
        if not validate_arguments(args):
            return 1

        # Validate configuration
        if not validate_configuration(args.region, args.bucket):
            return 1

        # Create OSS client
        client = create_oss_client(args.region)
        if not client:
            return 1

        # Check if object exists
        object_exists = check_object_exists(client, args.bucket, args.key)

        # If object exists and has unique key, check if same version already uploaded
        if object_exists and args.unique_key:
            if check_version_metadata(client, args.bucket, args.key, args.unique_key):
                logger.info(
                    "Object with same unique key already exists, skipping upload")
                return 0

        # Upload file
        if upload_file_to_oss(client, args.bucket, args.key, args.file_path, args.unique_key):
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
