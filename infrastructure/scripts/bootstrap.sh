#!/bin/bash
# ============================================================
# IntelliDoc — Bootstrap Script (Run Once)
# ============================================================
# Creates the S3 bucket and DynamoDB table for Terraform
# remote state. Run this BEFORE terraform init.
#
# Usage:
#   chmod +x infrastructure/scripts/bootstrap.sh
#   ./infrastructure/scripts/bootstrap.sh
# ============================================================

set -euo pipefail

REGION="${AWS_REGION:-ap-south-1}"
BUCKET_NAME="intellidoc-terraform-state"
TABLE_NAME="intellidoc-terraform-locks"

echo "=== IntelliDoc Bootstrap ==="
echo "Region: $REGION"
echo ""

# 1. Create S3 bucket for Terraform state
echo "Creating S3 bucket: $BUCKET_NAME ..."
if aws s3api head-bucket --bucket "$BUCKET_NAME" 2>/dev/null; then
  echo "  Bucket already exists, skipping."
else
  aws s3api create-bucket \
    --bucket "$BUCKET_NAME" \
    --region "$REGION" \
    --create-bucket-configuration LocationConstraint="$REGION"

  aws s3api put-bucket-versioning \
    --bucket "$BUCKET_NAME" \
    --versioning-configuration Status=Enabled

  aws s3api put-bucket-encryption \
    --bucket "$BUCKET_NAME" \
    --server-side-encryption-configuration '{
      "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
    }'

  aws s3api put-public-access-block \
    --bucket "$BUCKET_NAME" \
    --public-access-block-configuration \
      BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

  echo "  Bucket created."
fi

# 2. Create DynamoDB table for state locking
echo "Creating DynamoDB table: $TABLE_NAME ..."
if aws dynamodb describe-table --table-name "$TABLE_NAME" --region "$REGION" 2>/dev/null; then
  echo "  Table already exists, skipping."
else
  aws dynamodb create-table \
    --table-name "$TABLE_NAME" \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region "$REGION"

  echo "  Table created."
fi

echo ""
echo "=== Bootstrap Complete ==="
echo ""
echo "Next steps:"
echo "  cd infrastructure/terraform"
echo "  cp terraform.tfvars.example terraform.tfvars"
echo "  # Edit terraform.tfvars with your values"
echo "  terraform init"
echo "  terraform plan"
echo "  terraform apply"
