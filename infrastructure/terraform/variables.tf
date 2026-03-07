# ============================================================
# IntelliDoc — Terraform Variables
# ============================================================

# ── General ──────────────────────────────────────────────────

variable "aws_region" {
  description = "AWS region to deploy to"
  default     = "ap-south-1"
}

variable "project_name" {
  description = "Project name for resource naming"
  default     = "intellidoc"
}

variable "environment" {
  description = "Environment (dev/staging/prod)"
  default     = "prod"
}

# ── Database ─────────────────────────────────────────────────

variable "db_password" {
  description = "RDS PostgreSQL password"
  type        = string
  sensitive   = true
}

variable "db_instance_class" {
  description = "RDS instance class"
  default     = "db.t3.small"
}

# ── ECS (Container Compute) ─────────────────────────────────

variable "ecs_cpu" {
  description = "ECS task CPU units (1024 = 1 vCPU)"
  default     = 1024
}

variable "ecs_memory" {
  description = "ECS task memory in MiB"
  default     = 3072
}

variable "ecs_desired_count" {
  description = "Desired number of ECS tasks"
  default     = 1
}

variable "ecs_min_count" {
  description = "Minimum ECS tasks for auto-scaling"
  default     = 1
}

variable "ecs_max_count" {
  description = "Maximum ECS tasks for auto-scaling"
  default     = 4
}

# ── Secrets ──────────────────────────────────────────────────

variable "jwt_secret_key" {
  description = "JWT secret key for auth tokens"
  type        = string
  sensitive   = true
}

variable "app_secret_key" {
  description = "Application secret key"
  type        = string
  sensitive   = true
}

# ── GitHub (CI/CD OIDC) ─────────────────────────────────────

variable "github_org" {
  description = "GitHub organization or username"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
  default     = "Intellidoc"
}

# ── AWS Bedrock (ML Models) ─────────────────────────────────

variable "bedrock_model_id" {
  description = "Bedrock model ID for text generation (classification, summarization, Q&A)"
  default     = "anthropic.claude-3-haiku-20240307-v1:0"
}

variable "bedrock_embed_model_id" {
  description = "Bedrock model ID for text embeddings"
  default     = "amazon.titan-embed-text-v2:0"
}

# ── ElastiCache ──────────────────────────────────────────────

variable "redis_node_type" {
  description = "ElastiCache Redis node type"
  default     = "cache.t3.micro"
}
