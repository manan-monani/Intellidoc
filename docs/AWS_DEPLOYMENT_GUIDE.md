# 🚀 IntelliDoc — AWS Deployment Guide (Fresh Account)

> Step-by-step guide to deploy IntelliDoc on AWS from a brand-new account.

---

## 📋 Prerequisites (Install on Your Windows PC)

Before touching AWS, install these on your local machine:

| Tool | Install Command | Why Needed |
|------|----------------|-----------|
| **AWS CLI** | `winget install Amazon.AWSCLI` | Talk to AWS from terminal |
| **Docker Desktop** | Download from [docker.com](https://www.docker.com/products/docker-desktop/) | Build container images |
| **Git** | `winget install Git.Git` | Push code to GitHub |
| **Terraform** | `winget install Hashicorp.Terraform` | Create AWS infrastructure |

After installing, restart your terminal and verify:
```powershell
aws --version
docker --version
terraform --version
git --version
```

---

## 🏗️ STEP 1: Configure Your AWS Account (15 min)

### 1.1 Create IAM Admin User

> ⚠️ Never use the root account for day-to-day work. Create an admin IAM user.

1. Go to **AWS Console** → [console.aws.amazon.com](https://console.aws.amazon.com)
2. Search **IAM** → Click **Users** → **Create User**
3. Username: `intellidoc-admin`
4. Check ✅ **Provide user access to the AWS Management Console**
5. Select **I want to create an IAM user**
6. Set a password
7. Click **Next** → **Attach policies directly**
8. Search and select ✅ `AdministratorAccess`
9. Click **Create User**

### 1.2 Create Access Keys (for CLI)

1. Go to **IAM** → **Users** → `intellidoc-admin`
2. Click **Security credentials** tab
3. Scroll to **Access keys** → **Create access key**
4. Select **Command Line Interface (CLI)**
5. Check the acknowledgment → **Create**
6. **⚠️ SAVE BOTH KEYS** (you'll never see the secret again!):
   - Access Key ID: `AKIAXXXXXXXXXXXXXXXX`
   - Secret Access Key: `wJaXXXXXXXXXXXXXXXXXXXXXXXXXX`

### 1.3 Configure AWS CLI

```powershell
aws configure
```
Enter when prompted:
```
AWS Access Key ID:     AKIAXXXXXXXXXXXXXXXX
Secret Access Key:     wJaXXXXXXXXXXXXXXXXXXXXXXXXXX
Default region:        ap-south-1
Default output format: json
```

Verify it works:
```powershell
aws sts get-caller-identity
```
You should see your account ID, user ARN, etc.

---

## 🏗️ STEP 2: Create AWS Infrastructure with Terraform (10 min)

### 2.1 Initialize Terraform

```powershell
cd "d:\Projects\placement project antigravity\intellidoc\infrastructure\terraform"
terraform init
```
This downloads the AWS provider plugin.

### 2.2 Create a Secrets File

Create `terraform.tfvars` (this file stays local, never push to git):
```powershell
# In the terraform folder, create this file:
```
File content:
```hcl
db_password    = "YourStrongDBPassword123!"
instance_type  = "t3.medium"
aws_region     = "ap-south-1"
```

### 2.3 Preview What Will Be Created

```powershell
terraform plan
```
You'll see a list of ~15 resources that will be created:
- VPC + Subnets + Internet Gateway
- Security Groups (firewall)
- EC2 instance (t3.medium)
- RDS PostgreSQL (db.t3.micro)
- S3 Bucket (document storage)
- ECR Repository (Docker registry)
- IAM Roles

### 2.4 Create Everything

```powershell
terraform apply
```
Type `yes` when prompted. This takes **5-10 minutes**.

After completion, Terraform prints the outputs:
```
ec2_public_ip    = "13.235.XX.XX"
rds_endpoint     = "intellidoc-db.xxxxx.ap-south-1.rds.amazonaws.com:5432"
s3_bucket_name   = "intellidoc-documents-ap-south-1"
ecr_repository_url = "123456789.dkr.ecr.ap-south-1.amazonaws.com/intellidoc-backend"
```

**⚠️ SAVE THESE VALUES — you'll need them in the next steps!**

---

## 🏗️ STEP 3: Create an SSH Key Pair (2 min)

You need this to SSH into your EC2 instance.

### On AWS Console:
1. Go to **EC2** → **Key Pairs** (left sidebar)
2. Click **Create Key Pair**
3. Name: `intellidoc-key`
4. Type: **RSA**
5. Format: **.pem**
6. Click **Create** — the `.pem` file downloads automatically
7. Move it to a safe location:
```powershell
mkdir ~\.ssh -Force
move ~/Downloads/intellidoc-key.pem ~/.ssh/intellidoc-key.pem
```

### Associate Key with EC2

Since Terraform already created the EC2 without a key pair, the easiest approach:
1. Go to **EC2 Console** → **Instances** → Select `intellidoc-backend`
2. **Stop** the instance
3. **Actions** → **Instance settings** → **Edit user data** → Confirm
4. Go to **Actions** → **Modify** → Add key pair `intellidoc-key`
5. **Start** the instance

Alternative (simpler): terminate the EC2 and add `key_name = "intellidoc-key"` to the Terraform file, then `terraform apply` again.

---

## 🏗️ STEP 4: Build & Push Docker Image (10 min)

### 4.1 Login to ECR

```powershell
# Replace 123456789 with your actual AWS account ID
aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin 123456789.dkr.ecr.ap-south-1.amazonaws.com
```

### 4.2 Build the Backend Docker Image

```powershell
cd "d:\Projects\placement project antigravity\intellidoc\backend"
docker build -t intellidoc-backend .
```
This takes 5-10 minutes (downloads Python packages + ML deps).

### 4.3 Tag & Push to ECR

```powershell
# Tag the image (use YOUR ecr_repository_url from Terraform output)
docker tag intellidoc-backend:latest 123456789.dkr.ecr.ap-south-1.amazonaws.com/intellidoc-backend:latest

# Push to ECR
docker push 123456789.dkr.ecr.ap-south-1.amazonaws.com/intellidoc-backend:latest
```

---

## 🏗️ STEP 5: Build & Upload Frontend (5 min)

### 5.1 Build the React Production Bundle

```powershell
cd "d:\Projects\placement project antigravity\intellidoc\frontend"

# Set the API URL to your EC2 public IP
$env:VITE_API_URL="http://YOUR_EC2_IP:8000"
npm run build
```

### 5.2 Create an S3 Bucket for the Frontend (Optional)

You can serve the frontend from the EC2 via Nginx, or from S3 + CloudFront:

**Option A — Serve from EC2 via Nginx (simpler, we'll use this):**
We'll upload `frontend/dist/` to EC2 later.

---

## 🏗️ STEP 6: Deploy to EC2 (15 min)

### 6.1 SSH into EC2

```powershell
ssh -i ~/.ssh/intellidoc-key.pem ubuntu@YOUR_EC2_IP
```

> If you get a "permission denied" error on Windows, run:
> ```powershell
> icacls ~/.ssh/intellidoc-key.pem /inheritance:r /grant:r "$($env:USERNAME):R"
> ```

### 6.2 Wait for Setup to Complete

The EC2 user data script runs automatically. Wait for it:
```bash
# On EC2:
tail -f /var/log/cloud-init-output.log
# Wait until you see "Setup complete!"

# Verify Docker is working
docker --version
docker-compose --version
```

### 6.3 Create the Project Directory

```bash
# On EC2:
mkdir ~/intellidoc && cd ~/intellidoc
```

### 6.4 Create the .env File

```bash
cat > .env << 'EOF'
# ---- Application ----
APP_NAME=IntelliDoc
APP_ENV=production
DEBUG=false
SECRET_KEY=GENERATE_A_RANDOM_64_CHAR_STRING_HERE

# ---- Database (use RDS endpoint from Terraform) ----
DB_HOST=intellidoc-db.xxxxx.ap-south-1.rds.amazonaws.com
DB_PORT=5432
DB_NAME=intellidoc
DB_USER=intellidoc_user
DB_PASSWORD=YourStrongDBPassword123!

# ---- Redis ----
REDIS_HOST=localhost
REDIS_PORT=6379

# ---- AWS ----
AWS_REGION=ap-south-1
S3_BUCKET_NAME=intellidoc-documents-ap-south-1

# ---- ML ----
ML_INFERENCE_MODE=local
HUGGINGFACE_CACHE_DIR=/app/ml/models_cache

# ---- RAG ----
FAISS_INDEX_PATH=/app/rag/faiss_index
EMBEDDING_MODEL=all-MiniLM-L6-v2
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=mistral

# ---- Auth ----
JWT_SECRET_KEY=ANOTHER_RANDOM_64_CHAR_STRING

# ---- CORS ----
CORS_ORIGINS=http://YOUR_EC2_IP,http://YOUR_EC2_IP:80

# ---- Upload ----
MAX_UPLOAD_SIZE_MB=50
ALLOWED_EXTENSIONS=pdf,png,jpg,jpeg,tiff,docx
EOF
```

> **Replace** the placeholder values with your actual Terraform outputs!
> Generate random secrets: `openssl rand -hex 32`

### 6.5 Create docker-compose.yml on EC2

```bash
cat > docker-compose.yml << 'EOF'
version: "3.9"
services:
  backend:
    image: YOUR_ECR_URL/intellidoc-backend:latest
    container_name: intellidoc-backend
    restart: always
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      redis:
        condition: service_healthy
    volumes:
      - faiss_index:/app/rag/faiss_index
      - ml_models:/app/ml/models_cache

  redis:
    image: redis:7-alpine
    container_name: intellidoc-redis
    restart: always
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  redis_data:
  faiss_index:
  ml_models:
EOF
```

> **Replace** `YOUR_ECR_URL` with your actual ECR repository URL from Terraform.

### 6.6 Login to ECR from EC2

```bash
aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin YOUR_ECR_URL
```

### 6.7 Start Everything

```bash
docker-compose pull
docker-compose up -d
```

### 6.8 Check It's Running

```bash
# Check containers
docker-compose ps

# Check backend health
curl http://localhost:8000/health
# Should return: {"status":"healthy",...}

# Check logs if something fails
docker-compose logs backend
```

---

## 🏗️ STEP 7: Setup Nginx + Frontend (10 min)

### 7.1 Upload Frontend Build to EC2

**From your local Windows machine:**
```powershell
# Build frontend with production API URL
cd "d:\Projects\placement project antigravity\intellidoc\frontend"
$env:VITE_API_URL="http://YOUR_EC2_IP"
npm run build

# Upload to EC2
scp -i ~/.ssh/intellidoc-key.pem -r dist/* ubuntu@YOUR_EC2_IP:~/frontend_build/
```

### 7.2 Configure Nginx (on EC2)

```bash
# On EC2:
# Move frontend files
sudo mkdir -p /var/www/intellidoc
sudo cp -r ~/frontend_build/* /var/www/intellidoc/

# Create Nginx config
sudo tee /etc/nginx/sites-available/intellidoc << 'EOF'
server {
    listen 80;
    server_name _;

    # API proxy
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300s;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /health { proxy_pass http://localhost:8000; }
    location /docs { proxy_pass http://localhost:8000; }
    location /redoc { proxy_pass http://localhost:8000; }
    location /openapi.json { proxy_pass http://localhost:8000; }

    # Frontend
    location / {
        root /var/www/intellidoc;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    client_max_body_size 50M;
    gzip on;
    gzip_types text/plain text/css application/json application/javascript;
}
EOF

# Enable the site
sudo ln -sf /etc/nginx/sites-available/intellidoc /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test & restart
sudo nginx -t
sudo systemctl restart nginx
```

---

## 🏗️ STEP 8: Install Ollama for LLM (5 min)

```bash
# On EC2:
curl -fsSL https://ollama.com/install.sh | sh

# Pull the Mistral model (~4GB)
ollama pull mistral

# Start Ollama as a systemd service (it does this automatically)
sudo systemctl enable ollama
sudo systemctl start ollama

# Verify
curl http://localhost:11434/api/tags
```

---

## ✅ STEP 9: Test Everything!

### Open in Browser

1. **Frontend Dashboard**: `http://YOUR_EC2_IP`
2. **API Docs (Swagger)**: `http://YOUR_EC2_IP/docs`
3. **Health Check**: `http://YOUR_EC2_IP/health`

### Quick Test via API Docs

1. Open `http://YOUR_EC2_IP/docs`
2. **Register**: `POST /api/auth/register` → Create an account
3. **Upload**: `POST /api/documents/upload` → Upload a PDF
4. **OCR**: `POST /api/ml/{id}/ocr` → Extract text
5. **Classify**: `POST /api/ml/{id}/classify` → See the document type
6. **Index**: `POST /api/rag/{id}/index` → Prepare for Q&A
7. **Ask**: `POST /api/rag/ask` → Ask a question!

---

## 💰 Cost Estimate (Per Month)

| Service | Type | Est. Cost |
|---------|------|-----------|
| EC2 | t3.medium (2 vCPU, 4GB RAM) | ~$30 |
| RDS | db.t3.micro (1 vCPU, 1GB) | ~$15 |
| S3 | < 5GB storage | ~$0.12 |
| ECR | < 1GB images | ~$0.10 |
| Data Transfer | < 10GB | ~$1 |
| **Total** | | **~$46/month** |

> 💡 **Free Tier**: New AWS accounts get 12 months of free tier which covers:
> - 750 hrs/month of t2.micro EC2 (use `t2.micro` instead to save)
> - 750 hrs/month of db.t3.micro RDS
> - 5GB S3 storage
> With free tier: **~$0-5/month**

---

## 🔒 STEP 10: Security Checklist

- [ ] Change all default passwords in `.env`
- [ ] Restrict SSH security group to your IP only (not `0.0.0.0/0`)
- [ ] Set `DEBUG=false` in production `.env`
- [ ] Generate strong random `SECRET_KEY` and `JWT_SECRET_KEY`
- [ ] Consider adding SSL with `certbot --nginx` for HTTPS
- [ ] Enable CloudWatch monitoring for EC2 and RDS

---

## 🛑 Stopping to Save Costs

```bash
# Stop EC2 (no compute charges, storage charges continue)
aws ec2 stop-instances --instance-ids YOUR_INSTANCE_ID

# To resume
aws ec2 start-instances --instance-ids YOUR_INSTANCE_ID

# Nuclear option — destroy everything
cd infrastructure/terraform
terraform destroy
```

---

## 🔧 Troubleshooting

| Problem | Solution |
|---------|----------|
| Can't SSH to EC2 | Check security group allows port 22 from your IP |
| Backend won't start | `docker-compose logs backend` — check for errors |
| Database connection refused | Verify RDS endpoint in `.env`, check DB security group |
| 502 Bad Gateway | Backend container not running: `docker-compose up -d` |
| ML models slow to load | First run downloads ~3GB of models; subsequent starts are cached |
| Out of disk space | EC2 has 30GB; ML models use ~5GB; extend volume if needed |
| Ollama not responding | `sudo systemctl status ollama` and check port 11434 |
