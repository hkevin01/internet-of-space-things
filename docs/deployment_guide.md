# 🚀 Internet of Space Things (IoST) - Deployment Guide

**Version:** 1.0  
**Last Updated:** July 30, 2025  
**Target Environments:** Development, Staging, Production

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Local Development Deployment](#local-development-deployment)
4. [Docker Deployment](#docker-deployment)
5. [Kubernetes Deployment](#kubernetes-deployment)
6. [Cloud Platform Deployment](#cloud-platform-deployment)
7. [Database Setup](#database-setup)
8. [Security Configuration](#security-configuration)
9. [Monitoring and Logging](#monitoring-and-logging)
10. [Troubleshooting](#troubleshooting)

---

## 📋 Prerequisites

### System Requirements

**Minimum Requirements:**
- **CPU**: 4 cores, 2.4 GHz
- **RAM**: 8 GB
- **Storage**: 50 GB available space
- **Network**: Stable internet connection

**Recommended Requirements:**
- **CPU**: 8 cores, 3.0 GHz+
- **RAM**: 16 GB+
- **Storage**: 100 GB SSD
- **Network**: High-speed connection (100 Mbps+)

### Software Dependencies

#### Core Dependencies
```bash
# Python 3.9 or higher
python --version  # Should be 3.9+

# Docker and Docker Compose
docker --version  # Should be 20.10+
docker-compose --version  # Should be 1.29+

# Kubernetes (for production)
kubectl version --client  # Should be 1.21+

# Git
git --version  # Any recent version
```

#### Optional Dependencies
```bash
# Node.js (for web dashboard development)
node --version  # Should be 16+
npm --version   # Should be 8+

# Helm (for Kubernetes deployments)
helm version    # Should be 3.7+
```

---

## 🔧 Environment Setup

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/internet-of-space-things.git
cd internet-of-space-things
```

### 2. Environment Variables

Create environment file:
```bash
cp .env.example .env
```

Edit `.env` file:
```bash
# Database Configuration
DATABASE_URL=postgresql://iost:password@localhost:5432/iost_db
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=your_influxdb_token
REDIS_URL=redis://localhost:6379

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=true
SECRET_KEY=your_secret_key_here

# Authentication
OAUTH_CLIENT_ID=your_oauth_client_id
OAUTH_CLIENT_SECRET=your_oauth_client_secret

# External Services
NASA_API_KEY=your_nasa_api_key
NORAD_API_KEY=your_norad_api_key

# Monitoring
PROMETHEUS_ENABLED=true
GRAFANA_ADMIN_PASSWORD=admin_password

# Security
SSL_ENABLED=false
ENCRYPTION_KEY=your_encryption_key
```

### 3. Python Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Linux/Mac:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

## 💻 Local Development Deployment

### Quick Start (Development Mode)

```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up database (if needed)
python scripts/setup_database.py

# 4. Run the application
python main.py
```

### Development with Hot Reload

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run with hot reload
uvicorn src.interfaces.web_dashboard.app:app --reload --host 0.0.0.0 --port 8000
```

### Access Points

- **Main Application**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Mission Control Dashboard**: http://localhost:8000/dashboard
- **Health Check**: http://localhost:8000/health

---

## 🐳 Docker Deployment

### Single Container Deployment

#### Build Docker Image
```bash
# Build the image
docker build -t iost:latest .

# Run the container
docker run -d \
  --name iost-app \
  -p 8000:8000 \
  -e DATABASE_URL=postgresql://user:pass@host:5432/iost \
  iost:latest
```

### Docker Compose Deployment (Recommended)

#### Production-like Environment
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

#### Custom Configuration
Create `docker-compose.override.yml`:
```yaml
version: '3.8'

services:
  iost-app:
    environment:
      - DEBUG=true
      - API_PORT=8001
    ports:
      - "8001:8000"
    volumes:
      - ./data:/app/data
      
  postgres:
    environment:
      - POSTGRES_PASSWORD=custom_password
    volumes:
      - postgres_data_dev:/var/lib/postgresql/data

volumes:
  postgres_data_dev:
```

#### Complete Docker Compose Stack

```yaml
# docker-compose.yml
version: '3.8'

services:
  # Main Application
  iost-app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://iost:iost_password@postgres:5432/iost_db
      - REDIS_URL=redis://redis:6379
      - INFLUXDB_URL=http://influxdb:8086
    depends_on:
      - postgres
      - redis
      - influxdb
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs

  # PostgreSQL Database
  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=iost_db
      - POSTGRES_USER=iost
      - POSTGRES_PASSWORD=iost_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  # Redis Cache
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  # InfluxDB (Time-series Database)
  influxdb:
    image: influxdb:2.7
    environment:
      - INFLUXDB_DB=iost_telemetry
      - INFLUXDB_ADMIN_USER=admin
      - INFLUXDB_ADMIN_PASSWORD=admin_password
    volumes:
      - influxdb_data:/var/lib/influxdb2
    ports:
      - "8086:8086"

  # Prometheus Monitoring
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./config/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus

  # Grafana Dashboard
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
      - ./config/grafana:/etc/grafana/provisioning

volumes:
  postgres_data:
  redis_data:
  influxdb_data:
  prometheus_data:
  grafana_data:
```

### Docker Management Commands

```bash
# Build and start all services
docker-compose up --build -d

# View service status
docker-compose ps

# View logs for specific service
docker-compose logs -f iost-app

# Scale services
docker-compose up -d --scale iost-app=3

# Update specific service
docker-compose up -d --no-deps iost-app

# Clean up
docker-compose down -v  # Remove volumes too
docker system prune -a  # Clean up unused images
```

---

## ☸️ Kubernetes Deployment

### Prerequisites

```bash
# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/

# Install Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Verify cluster access
kubectl cluster-info
```

### Namespace Setup

```bash
# Create namespace
kubectl create namespace iost

# Set default namespace
kubectl config set-context --current --namespace=iost
```

### ConfigMap and Secrets

#### ConfigMap
```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: iost-config
  namespace: iost
data:
  API_HOST: "0.0.0.0"
  API_PORT: "8000"
  DEBUG: "false"
  PROMETHEUS_ENABLED: "true"
  DATABASE_URL: "postgresql://iost:$(POSTGRES_PASSWORD)@postgres:5432/iost_db"
```

#### Secrets
```yaml
# k8s/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: iost-secrets
  namespace: iost
type: Opaque
data:
  postgres-password: <base64-encoded-password>
  secret-key: <base64-encoded-secret-key>
  oauth-client-secret: <base64-encoded-oauth-secret>
```

```bash
# Create secrets
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/configmap.yaml
```

### Database Deployment

```yaml
# k8s/postgres.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
  namespace: iost
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15
        env:
        - name: POSTGRES_DB
          value: iost_db
        - name: POSTGRES_USER
          value: iost
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: iost-secrets
              key: postgres-password
        ports:
        - containerPort: 5432
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
      volumes:
      - name: postgres-storage
        persistentVolumeClaim:
          claimName: postgres-pvc

---
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: iost
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-pvc
  namespace: iost
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

### Application Deployment

```yaml
# k8s/iost-app.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: iost-app
  namespace: iost
spec:
  replicas: 3
  selector:
    matchLabels:
      app: iost-app
  template:
    metadata:
      labels:
        app: iost-app
    spec:
      containers:
      - name: iost-app
        image: iost:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            configMapKeyRef:
              name: iost-config
              key: DATABASE_URL
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: iost-secrets
              key: secret-key
        envFrom:
        - configMapRef:
            name: iost-config
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"

---
apiVersion: v1
kind: Service
metadata:
  name: iost-app-service
  namespace: iost
spec:
  selector:
    app: iost-app
  ports:
  - port: 80
    targetPort: 8000
  type: ClusterIP

---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: iost-ingress
  namespace: iost
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - api.iost.space
    secretName: iost-tls
  rules:
  - host: api.iost.space
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: iost-app-service
            port:
              number: 80
```

### Horizontal Pod Autoscaler

```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: iost-app-hpa
  namespace: iost
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: iost-app
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Deployment Commands

```bash
# Deploy database
kubectl apply -f k8s/postgres.yaml

# Wait for database to be ready
kubectl wait --for=condition=ready pod -l app=postgres --timeout=300s

# Deploy application
kubectl apply -f k8s/iost-app.yaml

# Deploy autoscaler
kubectl apply -f k8s/hpa.yaml

# Check deployment status
kubectl get pods
kubectl get services
kubectl get ingress

# View logs
kubectl logs -l app=iost-app -f
```

---

## ☁️ Cloud Platform Deployment

### AWS EKS Deployment

#### Prerequisites
```bash
# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Install eksctl
curl --silent --location "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz" | tar xz -C /tmp
sudo mv /tmp/eksctl /usr/local/bin

# Configure AWS credentials
aws configure
```

#### Create EKS Cluster
```bash
# Create cluster
eksctl create cluster \
  --name iost-cluster \
  --version 1.21 \
  --region us-west-2 \
  --nodegroup-name iost-nodes \
  --node-type t3.medium \
  --nodes 3 \
  --nodes-min 2 \
  --nodes-max 5 \
  --managed

# Update kubeconfig
aws eks update-kubeconfig --region us-west-2 --name iost-cluster
```

#### AWS-specific Configuration
```yaml
# k8s/aws-storage-class.yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: gp2-retain
provisioner: kubernetes.io/aws-ebs
parameters:
  type: gp2
reclaimPolicy: Retain
allowVolumeExpansion: true

---
# k8s/aws-load-balancer.yaml
apiVersion: v1
kind: Service
metadata:
  name: iost-lb
  namespace: iost
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-type: nlb
spec:
  type: LoadBalancer
  selector:
    app: iost-app
  ports:
  - port: 80
    targetPort: 8000
```

### Google Cloud GKE Deployment

#### Prerequisites
```bash
# Install Google Cloud SDK
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud init

# Install GKE auth plugin
gcloud components install gke-gcloud-auth-plugin
```

#### Create GKE Cluster
```bash
# Create cluster
gcloud container clusters create iost-cluster \
  --num-nodes=3 \
  --machine-type=e2-standard-2 \
  --zone=us-central1-a \
  --enable-autoscaling \
  --min-nodes=2 \
  --max-nodes=5

# Get credentials
gcloud container clusters get-credentials iost-cluster --zone=us-central1-a
```

### Azure AKS Deployment

#### Prerequisites
```bash
# Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Login to Azure
az login
```

#### Create AKS Cluster
```bash
# Create resource group
az group create --name iost-rg --location eastus

# Create AKS cluster
az aks create \
  --resource-group iost-rg \
  --name iost-cluster \
  --node-count 3 \
  --node-vm-size Standard_B2s \
  --enable-addons monitoring \
  --generate-ssh-keys

# Get credentials
az aks get-credentials --resource-group iost-rg --name iost-cluster
```

---

## 🗄️ Database Setup

### PostgreSQL Setup

#### Local Installation
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install postgresql postgresql-contrib

# CentOS/RHEL
sudo yum install postgresql-server postgresql-contrib
sudo postgresql-setup initdb
sudo systemctl enable postgresql
sudo systemctl start postgresql

# macOS
brew install postgresql
brew services start postgresql
```

#### Database Configuration
```sql
-- Connect as postgres user
sudo -u postgres psql

-- Create database and user
CREATE DATABASE iost_db;
CREATE USER iost WITH ENCRYPTED PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE iost_db TO iost;

-- Create extensions
\c iost_db;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";
```

#### Run Migrations
```bash
# Using Alembic (if configured)
alembic upgrade head

# Or run setup script
python scripts/setup_database.py
```

### InfluxDB Setup

#### Installation
```bash
# Ubuntu/Debian
wget -qO- https://repos.influxdata.com/influxdb.key | sudo apt-key add -
echo "deb https://repos.influxdata.com/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/influxdb.list
sudo apt update
sudo apt install influxdb2

# Start service
sudo systemctl enable influxdb
sudo systemctl start influxdb
```

#### Initial Setup
```bash
# Setup InfluxDB
influx setup \
  --username admin \
  --password admin_password \
  --org iost \
  --bucket telemetry \
  --retention 365d \
  --force

# Create API token
influx auth create --org iost --all-access
```

### Redis Setup

#### Installation
```bash
# Ubuntu/Debian
sudo apt install redis-server

# CentOS/RHEL
sudo yum install redis
sudo systemctl enable redis
sudo systemctl start redis

# macOS
brew install redis
brew services start redis
```

#### Configuration
```bash
# Edit Redis configuration
sudo nano /etc/redis/redis.conf

# Key settings:
# maxmemory 256mb
# maxmemory-policy allkeys-lru
# appendonly yes
```

---

## 🔒 Security Configuration

### SSL/TLS Setup

#### Certificate Generation (Let's Encrypt)
```bash
# Install Certbot
sudo apt install certbot

# Generate certificate
sudo certbot certonly --standalone -d api.iost.space

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

#### SSL Configuration for NGINX
```nginx
# /etc/nginx/sites-available/iost
server {
    listen 80;
    server_name api.iost.space;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.iost.space;

    ssl_certificate /etc/letsencrypt/live/api.iost.space/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.iost.space/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Firewall Configuration

#### UFW (Ubuntu)
```bash
# Enable UFW
sudo ufw enable

# Allow SSH
sudo ufw allow ssh

# Allow HTTP/HTTPS
sudo ufw allow 80
sudo ufw allow 443

# Allow application port
sudo ufw allow 8000

# Check status
sudo ufw status
```

#### Firewall Rules for Kubernetes
```bash
# Allow Kubernetes API server
sudo ufw allow 6443

# Allow kubelet API
sudo ufw allow 10250

# Allow NodePort services
sudo ufw allow 30000:32767/tcp
```

### Environment Security

#### Secrets Management
```bash
# Generate secure secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Encrypt sensitive files
gpg --symmetric --cipher-algo AES256 sensitive_file.txt

# Use environment-specific secrets
export SECRET_KEY=$(cat /etc/iost/secret_key)
```

#### Container Security
```dockerfile
# Use non-root user
FROM python:3.9-slim
RUN adduser --disabled-password --gecos '' iost
USER iost

# Scan for vulnerabilities
# docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
#   aquasec/trivy image iost:latest
```

---

## 📊 Monitoring and Logging

### Prometheus Configuration

```yaml
# config/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "iost_rules.yml"

scrape_configs:
  - job_name: 'iost-app'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
    scrape_interval: 5s

  - job_name: 'postgres'
    static_configs:
      - targets: ['localhost:9187']

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093
```

### Grafana Dashboard

#### Import Dashboard
```bash
# Import IoST dashboard
curl -X POST \
  http://admin:admin@localhost:3000/api/dashboards/db \
  -H 'Content-Type: application/json' \
  -d @config/grafana/iost-dashboard.json
```

### Logging Configuration

#### Structured Logging
```python
# config/logging.py
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
```

#### Log Rotation
```bash
# /etc/logrotate.d/iost
/var/log/iost/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 644 iost iost
    postrotate
        systemctl reload iost
    endscript
}
```

---

## 🔧 Troubleshooting

### Common Issues

#### 1. Database Connection Issues

**Problem**: Application cannot connect to database
```
ERROR: could not connect to server: Connection refused
```

**Solution**:
```bash
# Check database status
sudo systemctl status postgresql

# Check connection parameters
psql -h localhost -U iost -d iost_db

# Verify firewall rules
sudo ufw status | grep 5432
```

#### 2. Port Already in Use

**Problem**: Port 8000 is already in use
```
ERROR: [Errno 98] Address already in use
```

**Solution**:
```bash
# Find process using port
sudo lsof -i :8000

# Kill process
sudo kill -9 <PID>

# Or use different port
export API_PORT=8001
```

#### 3. Docker Build Issues

**Problem**: Docker build fails with permission errors

**Solution**:
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Logout and login again
# Or restart docker service
sudo systemctl restart docker
```

#### 4. Kubernetes Pod CrashLoopBackOff

**Problem**: Pods are crashing repeatedly

**Diagnosis**:
```bash
# Check pod status
kubectl get pods

# View pod logs
kubectl logs <pod-name>

# Describe pod for events
kubectl describe pod <pod-name>

# Check resource limits
kubectl top pods
```

#### 5. SSL Certificate Issues

**Problem**: SSL certificate validation fails

**Solution**:
```bash
# Check certificate validity
openssl x509 -in cert.pem -text -noout

# Verify certificate chain
openssl verify -CAfile ca-bundle.crt cert.pem

# Test SSL connection
openssl s_client -connect api.iost.space:443
```

### Health Checks

#### Application Health Check
```bash
# Basic health check
curl -f http://localhost:8000/health || exit 1

# Detailed status
curl http://localhost:8000/status | jq .
```

#### Database Health Check
```bash
# PostgreSQL
pg_isready -h localhost -p 5432

# InfluxDB
curl -f http://localhost:8086/health

# Redis
redis-cli ping
```

### Performance Tuning

#### Application Optimization
```python
# config/performance.py
import uvicorn

# Production settings
uvicorn.run(
    "app:app",
    host="0.0.0.0",
    port=8000,
    workers=4,
    worker_class="uvicorn.workers.UvicornWorker",
    access_log=False,
    use_colors=False
)
```

#### Database Optimization
```sql
-- PostgreSQL tuning
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
SELECT pg_reload_conf();
```

### Backup and Recovery

#### Database Backup
```bash
# PostgreSQL backup
pg_dump -h localhost -U iost iost_db > backup_$(date +%Y%m%d).sql

# InfluxDB backup
influx backup /path/to/backup/dir

# Automated backup script
#!/bin/bash
BACKUP_DIR="/backup/$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR
pg_dump -h localhost -U iost iost_db > $BACKUP_DIR/postgres.sql
influx backup $BACKUP_DIR/influxdb
```

#### Recovery
```bash
# PostgreSQL restore
psql -h localhost -U iost iost_db < backup_20250730.sql

# InfluxDB restore
influx restore /path/to/backup/dir
```

---

## 📚 Additional Resources

### Documentation Links
- [Docker Documentation](https://docs.docker.com/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Helm Documentation](https://helm.sh/docs/)
- [Prometheus Documentation](https://prometheus.io/docs/)

### Monitoring Dashboards
- **Application Metrics**: http://localhost:3000/d/iost-app
- **Infrastructure Metrics**: http://localhost:3000/d/iost-infra
- **Alert Manager**: http://localhost:9093

### Support
- **GitHub Issues**: [https://github.com/iost/issues](https://github.com/iost/issues)
- **Community Forum**: [https://community.iost.space](https://community.iost.space)
- **Deployment Support**: [deploy-support@iost.space](mailto:deploy-support@iost.space)

---

*This deployment guide is regularly updated. For the latest version and deployment automation scripts, visit our [deployment repository](https://github.com/iost/deployment).*

**Document Control**:
- **Version**: 1.0
- **Last Updated**: July 30, 2025
- **Next Review**: August 30, 2025
