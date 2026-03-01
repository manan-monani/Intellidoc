"""
S3 Service
==========
AWS S3 operations for document storage.

This service handles all interactions with Amazon S3:
- Uploading documents when users submit files
- Downloading documents for ML processing
- Generating presigned URLs for secure browser downloads
- Listing and deleting objects

How S3 Works:
- S3 is object storage — think of it as a massive key-value store
- "Bucket" = top-level container (like a drive)
- "Key" = path to the object (like a file path)
- Objects are immutable — you replace, never edit in-place
"""

import boto3
from botocore.exceptions import ClientError
from app.config import get_settings
from typing import Optional, List, BinaryIO
import logging
import uuid

logger = logging.getLogger(__name__)
settings = get_settings()


class S3Service:
    """
    Manages all S3 operations for IntelliDoc.

    Usage:
        s3 = S3Service()
        key = await s3.upload_file(file, "document.pdf", "application/pdf")
        url = s3.generate_presigned_url(key)
    """

    def __init__(self):
        """Initialize the S3 client with credentials from config."""
        self.client = boto3.client(
            "s3",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )
        self.bucket = settings.s3_bucket_name

    def upload_file(
        self,
        file_obj: BinaryIO,
        filename: str,
        content_type: str,
        folder: str = "uploads",
    ) -> str:
        """
        Upload a file to S3.

        Args:
            file_obj: File-like object (from FastAPI UploadFile)
            filename: Original filename
            content_type: MIME type (e.g., "application/pdf")
            folder: S3 folder prefix

        Returns:
            S3 key (path) where the file was stored

        How it works:
            1. Generates a unique key: uploads/<uuid>/<filename>
            2. Uploads the file bytes to S3
            3. Returns the key for database storage
        """
        # Create unique key to avoid collisions
        unique_id = str(uuid.uuid4())
        s3_key = f"{folder}/{unique_id}/{filename}"

        try:
            self.client.upload_fileobj(
                file_obj,
                self.bucket,
                s3_key,
                ExtraArgs={
                    "ContentType": content_type,
                    "ServerSideEncryption": "AES256",  # Encrypt at rest
                },
            )
            logger.info(f"Uploaded file to s3://{self.bucket}/{s3_key}")
            return s3_key

        except ClientError as e:
            logger.error(f"S3 upload failed: {e}")
            raise Exception(f"Failed to upload file to S3: {e}")

    def download_file(self, s3_key: str) -> bytes:
        """
        Download a file from S3.

        Args:
            s3_key: The S3 object key

        Returns:
            File content as bytes
        """
        try:
            response = self.client.get_object(
                Bucket=self.bucket,
                Key=s3_key,
            )
            return response["Body"].read()

        except ClientError as e:
            logger.error(f"S3 download failed for {s3_key}: {e}")
            raise Exception(f"Failed to download file from S3: {e}")

    def generate_presigned_url(
        self,
        s3_key: str,
        expiration: int = 3600,
    ) -> str:
        """
        Generate a temporary URL for direct browser download.

        Args:
            s3_key: The S3 object key
            expiration: URL validity in seconds (default 1 hour)

        Returns:
            Presigned URL string

        How it works:
            - Creates a URL with embedded AWS credentials
            - URL expires after the specified time
            - No authentication needed to access the URL
            - Useful for letting the frontend download files directly
        """
        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": s3_key},
                ExpiresIn=expiration,
            )
            return url

        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise Exception(f"Failed to generate download URL: {e}")

    def delete_file(self, s3_key: str) -> bool:
        """
        Delete a file from S3.

        Args:
            s3_key: The S3 object key

        Returns:
            True if deleted successfully
        """
        try:
            self.client.delete_object(
                Bucket=self.bucket,
                Key=s3_key,
            )
            logger.info(f"Deleted s3://{self.bucket}/{s3_key}")
            return True

        except ClientError as e:
            logger.error(f"S3 delete failed: {e}")
            return False

    def list_objects(
        self,
        prefix: str = "uploads/",
        max_keys: int = 100,
    ) -> List[dict]:
        """
        List objects in the bucket with a given prefix.

        Returns:
            List of {key, size, last_modified} dicts
        """
        try:
            response = self.client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix,
                MaxKeys=max_keys,
            )
            objects = []
            for obj in response.get("Contents", []):
                objects.append({
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                })
            return objects

        except ClientError as e:
            logger.error(f"S3 list failed: {e}")
            return []

    def ensure_bucket_exists(self):
        """
        Create the S3 bucket if it doesn't exist.
        Call this on app startup.
        """
        try:
            self.client.head_bucket(Bucket=self.bucket)
            logger.info(f"S3 bucket '{self.bucket}' exists")
        except ClientError:
            try:
                if settings.aws_region == "us-east-1":
                    self.client.create_bucket(Bucket=self.bucket)
                else:
                    self.client.create_bucket(
                        Bucket=self.bucket,
                        CreateBucketConfiguration={
                            "LocationConstraint": settings.aws_region,
                        },
                    )
                logger.info(f"Created S3 bucket '{self.bucket}'")
            except ClientError as e:
                logger.error(f"Failed to create bucket: {e}")
                raise


# ── Singleton ────────────────────────────────────────────────
_s3_service: Optional[S3Service] = None


def get_s3_service() -> S3Service:
    """Get or create S3 service singleton."""
    global _s3_service
    if _s3_service is None:
        _s3_service = S3Service()
    return _s3_service
