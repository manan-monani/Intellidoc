# ============================================================
# IntelliDoc — Terraform Configuration (AWS)
# ============================================================
# Provider config and data sources. All resources are in
# separate files (networking.tf, compute.tf, etc.)
#
# Usage:
#   1. Run infrastructure/scripts/bootstrap.sh first (one-time)
#   2. cp terraform.tfvars.example terraform.tfvars (fill in values)
#   3. terraform init
#   4. terraform plan
#   5. terraform apply
# ============================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state — created by bootstrap.sh
  backend "s3" {
    bucket         = "intellidoc-terraform-state"
    key            = "prod/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "intellidoc-terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# CloudFront requires ACM certificates in us-east-1
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
