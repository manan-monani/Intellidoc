# ============================================================
# IntelliDoc — Database & Cache (RDS, ElastiCache, Secrets)
# ============================================================

# ── RDS: PostgreSQL ──────────────────────────────────────────

resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnet"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_b.id]

  tags = { Name = "${var.project_name}-db-subnet" }
}

resource "aws_db_instance" "postgres" {
  identifier            = "${var.project_name}-db"
  engine                = "postgres"
  engine_version        = "16"
  instance_class        = var.db_instance_class
  allocated_storage     = 20
  max_allocated_storage = 100
  storage_encrypted     = true

  db_name  = "intellidoc"
  username = "intellidoc_user"
  password = var.db_password

  skip_final_snapshot       = true
  backup_retention_period   = 1
  backup_window             = "03:00-04:00"
  maintenance_window        = "Mon:04:00-Mon:05:00"

  publicly_accessible    = false
  multi_az               = false
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name

  tags = { Name = "${var.project_name}-postgres" }
}

# ── ElastiCache: Redis ───────────────────────────────────────

resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.project_name}-redis-subnet"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_b.id]
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "${var.project_name}-redis"
  engine               = "redis"
  engine_version       = "7.1"
  node_type            = var.redis_node_type
  num_cache_nodes      = 1
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.redis.id]

  tags = { Name = "${var.project_name}-redis" }
}

# ── Secrets Manager ──────────────────────────────────────────

resource "aws_secretsmanager_secret" "app_secrets" {
  name = "${var.project_name}/${var.environment}/app-secrets"

  tags = { Name = "${var.project_name}-secrets" }
}

resource "aws_secretsmanager_secret_version" "app_secrets" {
  secret_id = aws_secretsmanager_secret.app_secrets.id

  secret_string = jsonencode({
    DB_PASSWORD    = var.db_password
    JWT_SECRET_KEY = var.jwt_secret_key
    APP_SECRET_KEY = var.app_secret_key
    GROQ_API_KEY   = var.groq_api_key
  })
}
