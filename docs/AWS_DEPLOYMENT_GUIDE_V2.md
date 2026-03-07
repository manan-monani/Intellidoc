# IntelliDoc — AWS Production Deployment Guide (v2)

## Architecture Overview

```
                    ┌─────────────────────────────────────────┐
                    │              CloudFront CDN              │
                    │  (HTTPS, SPA routing, API proxy)        │
                    └────────┬──────────────────┬─────────────┘
                             │                  │
                    /assets, /*           /api/*, /health
                             │                  │
                    ┌────────▼─────┐   ┌───────▼──────────┐
                    │  S3 Bucket   │   │  Application     │
                    │  (Frontend)  │   │  Load Balancer   │
                    │  React SPA   │   │  (ALB)           │
                    └──────────────┘   └───────┬──────────┘
                                               │
                                    ┌──────────▼──────────┐
                                    │   ECS Fargate       │
                                    │   (Auto-scaling     │
                                    │    1-4 tasks)       │
                                    │   FastAPI Backend   │
                                    └──┬───┬───┬───┬──────┘
                                       │   │   │   │
                    ┌──────────────┐   │   │   │   │  ┌────────────┐
                    │ RDS Postgres │◄──┘   │   │   └─►│ AWS Bedrock│
                    │ (Multi-AZ)   │       │   │      │ Claude /   │
                    └──────────────┘       │   │      │ Titan      │
                    ┌──────────────┐       │   │      └────────────┘
                    │ ElastiCache  │◄──────┘   │
                    │ Redis        │           │
                    └──────────────┘           │
                    ┌──────────────┐           │
                    │ S3 Documents │◄──────────┘
                    │ (Encrypted)  │
                    └──────────────┘
                    ┌──────────────┐
                    │ EFS (FAISS   │ ◄── Shared across ECS tasks
                    │  Vector Index)│
                    └──────────────┘
```

### AWS Services Used

| Service | Purpose | Resource |
|---------|---------|----------|
| Frontend | React SPA | S3 + CloudFront |
| Backend API | FastAPI containers | ECS Fargate + ALB |
| Database | PostgreSQL 16 | RDS (Multi-AZ) |
| Cache | Redis 7.1 | ElastiCache |
| Document Storage | File uploads | S3 (encrypted, versioned) |
| Vector Index | FAISS persistence | EFS (Elastic File System) |
| ML: Classification | Zero-shot document classification | AWS Bedrock (Claude 3 Haiku) |
| ML: Summarization | Abstractive text summarization | AWS Bedrock (Claude 3 Haiku) |
| ML: Q&A | RAG-powered question answering | AWS Bedrock (Claude 3 Haiku) |
| ML: Embeddings | Document chunk embeddings | AWS Bedrock (Titan Embeddings v2) |
| ML: OCR | Text extraction from images/PDFs | Tesseract (in container) |
| ML: NER | Named entity recognition | BERT model (in container) |
| CI/CD | Automated deployments | GitHub Actions + OIDC |
| Monitoring | Logs, alarms, metrics | CloudWatch |
| Secrets | Credentials management | Secrets Manager |
| IaC | Infrastructure automation | Terraform |

---

## Prerequisites

1. **AWS Account** with admin access (or IAM user with sufficient permissions)
2. **AWS CLI v2** installed and configured (`aws configure`)
3. **Terraform** >= 1.5.0 installed
4. **Docker** installed locally (for building images)
5. **Node.js** >= 20 (for frontend build)
6. **GitHub repository** with the IntelliDoc code pushed

### Enable AWS Bedrock Models

Before deploying, request access to the required Bedrock models:

1. Go to **AWS Console → Amazon Bedrock → Model access**
2. Click **Manage model access**
3. Enable:
   - **Anthropic → Claude 3 Haiku** (classification, summarization, Q&A)
   - **Amazon → Titan Text Embeddings V2** (document embeddings)
4. Wait for access to be granted (Titan is instant; Claude may take a few minutes)

---

## Step 1: Bootstrap Terraform State (One-Time)

This creates an S3 bucket and DynamoDB table for Terraform remote state management.

```bash
# Set your AWS region
export AWS_REGION=ap-south-1

# Run the bootstrap script
chmod +x infrastructure/scripts/bootstrap.sh
./infrastructure/scripts/bootstrap.sh
```

This creates:
- `intellidoc-terraform-state` S3 bucket (versioned, encrypted)
- `intellidoc-terraform-locks` DynamoDB table (state locking)

---

## Step 2: Configure Terraform Variables

```bash
cd infrastructure/terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:

```hcl
aws_region     = "ap-south-1"
environment    = "prod"

# Strong database password
db_password       = "YourStr0ngP@ssw0rd!"
db_instance_class = "db.t3.small"

# ECS (1 vCPU, 3GB for running NER + OCR in-container)
ecs_cpu           = 1024
ecs_memory        = 3072
ecs_desired_count = 1
ecs_min_count     = 1
ecs_max_count     = 4

# Generate strong random secrets:
#   openssl rand -hex 32
jwt_secret_key = "your-generated-jwt-secret"
app_secret_key = "your-generated-app-secret"

# Your GitHub username/org name
github_org  = "manan-monani"
github_repo = "Intellidoc"

# Bedrock model IDs
bedrock_model_id       = "anthropic.claude-3-haiku-20240307-v1:0"
bedrock_embed_model_id = "amazon.titan-embed-text-v2:0"

# Redis
redis_node_type = "cache.t3.micro"
```

---

## Step 3: Deploy Infrastructure

```bash
cd infrastructure/terraform

# Download providers and connect to remote state
terraform init

# Preview changes
terraform plan

# Deploy everything (~10-15 minutes)
terraform apply
```

Save the outputs — you'll need them for CI/CD and first deployment:

```bash
# View all outputs
terraform output

# Key outputs:
terraform output cloudfront_url              # Your app URL
terraform output ecr_repository_url          # Docker registry
terraform output github_actions_role_arn     # For CI/CD
terraform output s3_frontend_bucket          # Frontend bucket
terraform output cloudfront_distribution_id  # For cache invalidation
```

---

## Step 4: First Backend Deployment

```bash
# Login to ECR
aws ecr get-login-password --region ap-south-1 | \
  docker login --username AWS --password-stdin \
  $(terraform output -raw ecr_repository_url | cut -d'/' -f1)

# Build and push backend Docker image
cd ../../backend
ECR_URL=$(cd ../infrastructure/terraform && terraform output -raw ecr_repository_url)
docker build -t $ECR_URL:latest .
docker push $ECR_URL:latest

# Trigger ECS deployment
aws ecs update-service \
  --cluster intellidoc-cluster \
  --service intellidoc-backend \
  --force-new-deployment

# Wait for it to stabilize
aws ecs wait services-stable \
  --cluster intellidoc-cluster \
  --services intellidoc-backend
```

---

## Step 5: First Frontend Deployment

```bash
cd frontend
npm ci
VITE_API_URL="" npm run build

# Deploy to S3
BUCKET=$(cd ../infrastructure/terraform && terraform output -raw s3_frontend_bucket)
aws s3 sync dist/ s3://$BUCKET --delete

# Invalidate CDN cache
DIST_ID=$(cd ../infrastructure/terraform && terraform output -raw cloudfront_distribution_id)
aws cloudfront create-invalidation --distribution-id $DIST_ID --paths "/*"
```

Your app should now be live at the CloudFront URL from Step 3!

---

## Step 6: Set Up CI/CD (GitHub Actions)

### Add GitHub Repository Secrets

Go to **GitHub repo → Settings → Secrets and variables → Actions** → **New repository secret**:

| Secret Name | Value | Source |
|-------------|-------|--------|
| `AWS_ROLE_ARN` | The GitHub Actions role ARN | `terraform output github_actions_role_arn` |
| `FRONTEND_BUCKET` | Frontend S3 bucket name | `terraform output s3_frontend_bucket` |
| `CLOUDFRONT_DISTRIBUTION_ID` | CloudFront distribution ID | `terraform output cloudfront_distribution_id` |

### CI/CD Flow

**On Pull Request** (`.github/workflows/ci.yml`):
- Backend lint + import check
- Frontend lint + build check
- Docker build verification
- Terraform format + validate

**On Push to `main`** (`.github/workflows/deploy.yml`):
1. Builds backend Docker image → pushes to ECR (tagged with commit SHA)
2. Registers new ECS task definition with the new image
3. Updates ECS service (rolling deployment, zero downtime)
4. Builds React frontend → syncs to S3 → invalidates CloudFront

After this setup, **every push to main automatically deploys to production**.

---

## Auto-Scaling Configuration

ECS auto-scales based on:

| Metric | Target | Scale Out | Scale In |
|--------|--------|-----------|----------|
| CPU Utilization | 70% | 60s cooldown | 300s cooldown |
| Memory Utilization | 80% | 60s cooldown | 300s cooldown |

- Minimum: 1 task (cost efficiency when idle)
- Maximum: 4 tasks (handles traffic spikes)
- All tasks share the FAISS vector index via EFS
- New tasks register automatically with the ALB

---

## ML Models in Production

| Task | Local Mode | AWS Production Mode |
|------|-----------|-------------------|
| **OCR** | Tesseract (in container) | Tesseract (in container) |
| **Classification** | facebook/bart-large-mnli (~1.6GB) | Bedrock Claude 3 Haiku (API) |
| **NER** | dslim/bert-base-NER (~420MB) | dslim/bert-base-NER (in container) |
| **Summarization** | facebook/bart-large-cnn (~1.6GB) | Bedrock Claude 3 Haiku (API) |
| **Embeddings** | all-MiniLM-L6-v2 (384-dim) | Titan Embeddings v2 (1024-dim) |
| **RAG LLM** | Ollama / Mistral | Bedrock Claude 3 Haiku (API) |

**Environment variables that control the mode:**
- `ML_INFERENCE_MODE=bedrock` → Classification & Summarization
- `LLM_PROVIDER=bedrock` → RAG Q&A
- `EMBEDDING_PROVIDER=bedrock` → Embeddings

> **Important**: Changing the embedding provider requires reindexing all documents (different vector dimensions).

---

## Monitoring & Troubleshooting

### View Application Logs

```bash
# Stream live logs
aws logs tail /ecs/intellidoc-backend --follow

# Last hour of logs
aws logs tail /ecs/intellidoc-backend --since 1h
```

### Check ECS Service Status

```bash
aws ecs describe-services \
  --cluster intellidoc-cluster \
  --services intellidoc-backend \
  --query 'services[0].{status:status,running:runningCount,desired:desiredCount}'
```

### CloudWatch Alarms

Pre-configured alarms:
- **ECS CPU** > 85% for 10 minutes
- **ECS Memory** > 85% for 10 minutes
- **RDS CPU** > 80% for 10 minutes
- **ALB 5XX errors** > 10 per 5 minutes
- **ALB latency** > 5 seconds average

### Common Issues

| Issue | Solution |
|-------|----------|
| ECS task keeps restarting | Check CloudWatch logs for startup errors |
| 502 Bad Gateway | ECS task health check failing; check `/health` endpoint |
| Bedrock errors | Verify model access is enabled in Bedrock console |
| Database connection refused | Verify RDS security group allows ECS security group |
| Frontend not updating | Invalidate CloudFront: `aws cloudfront create-invalidation ...` |

---

## Cost Estimation (Monthly, ap-south-1)

| Service | Spec | Est. Cost |
|---------|------|-----------|
| ECS Fargate | 1 vCPU, 3GB, 1 task (24/7) | ~$35 |
| RDS PostgreSQL | db.t3.small, Multi-AZ | ~$50 |
| ElastiCache Redis | cache.t3.micro | ~$15 |
| ALB | Always on | ~$20 |
| NAT Gateway | Always on + data transfer | ~$35 |
| S3 | Documents + frontend | ~$5 |
| CloudFront | CDN distribution | ~$5 |
| EFS | FAISS index storage | ~$5 |
| Bedrock | Pay per token (usage-dependent) | ~$5–50 |
| CloudWatch | Logs + alarms | ~$5 |
| **Total** | | **~$180–225/mo** |

> Auto-scaling can increase costs during high traffic (up to 4x compute).
> Bedrock costs scale with usage (tokens processed).

---

## Cleanup

To destroy all AWS resources:

```bash
cd infrastructure/terraform

# Destroy everything
terraform destroy
```

Then remove the bootstrap resources:

```bash
# Empty and delete the state bucket
aws s3 rb s3://intellidoc-terraform-state --force

# Delete the lock table
aws dynamodb delete-table --table-name intellidoc-terraform-locks --region ap-south-1
```
