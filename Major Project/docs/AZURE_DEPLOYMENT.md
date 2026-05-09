# Azure Deployment Quick Reference

## Prerequisites
- Azure account (free tier has $200 credit for 30 days)
- Azure CLI installed: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli
- Git installed and repo pushed to GitHub

---

## Option 1: Deploy to Azure App Service (5 minutes)

### Step 1: Create Resource Group
```bash
az group create --name ventilator-demo --location eastus
```

### Step 2: Create App Service Plan
```bash
az appservice plan create --name ventilator-plan --resource-group ventilator-demo --sku B2 --is-linux
```

### Step 3: Create Web App
```bash
az webapp create --resource-group ventilator-demo --plan ventilator-plan --name ventilator-ai-demo --runtime "PYTHON:3.11"
```

### Step 4: Configure Startup Command
```bash
az webapp config set --resource-group ventilator-demo --name ventilator-ai-demo --startup-file "gunicorn -w 4 -b 0.0.0.0 --timeout 120 api.main:app"
```

### Step 5: Deploy from Git
```bash
az webapp deployment source config-zip --resource-group ventilator-demo --name ventilator-ai-demo --src <path-to-zip>
```

Or use GitHub Actions:
```bash
az webapp deployment github-action add --repo-url https://github.com/<username>/<repo> --branch main --resource-group ventilator-demo --name ventilator-ai-demo --runtime "python|3.11"
```

### Step 6: Check Status
```bash
az webapp show --resource-group ventilator-demo --name ventilator-ai-demo --query "hostNames" -o table
```

**Result:** Your app will be available at:
```
https://ventilator-ai-demo.azurewebsites.net
```

---

## Option 2: Deploy Docker to Azure Container Instances (10 minutes)

### Step 1: Create Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Step 2: Create Azure Container Registry
```bash
az acr create --resource-group ventilator-demo --name ventilatorregistry --sku Basic
```

### Step 3: Build and Push Image
```bash
az acr build --registry ventilatorregistry --image ventilator-api:latest .
```

### Step 4: Create Container Instance
```bash
az container create \
  --resource-group ventilator-demo \
  --name ventilator-api-instance \
  --image ventilatorregistry.azurecr.io/ventilator-api:latest \
  --registry-login-server ventilatorregistry.azurecr.io \
  --registry-username <username> \
  --registry-password <password> \
  --cpu 2 \
  --memory 4 \
  --ports 8000 \
  --environment-variables DATASET_PATH=/data/clean_full_data_v2.csv
```

### Step 5: Get Public IP
```bash
az container show --resource-group ventilator-demo --name ventilator-api-instance --query ipAddress.ip -o table
```

**Result:** Your API will be available at:
```
http://<public-ip>:8000
```

---

## Option 3: Deploy to Azure VM with SSH (15 minutes)

### Step 1: Create VM
```bash
az vm create \
  --resource-group ventilator-demo \
  --name ventilator-vm \
  --image UbuntuLTS \
  --size Standard_B2s \
  --admin-username azureuser \
  --generate-ssh-keys
```

### Step 2: SSH into VM
```bash
ssh azureuser@<public-ip>
```

### Step 3: Install Dependencies
```bash
sudo apt-get update
sudo apt-get install -y python3.11 python3-pip python3-venv nginx
sudo apt-get install -y git
```

### Step 4: Clone and Setup Project
```bash
git clone https://github.com/<username>/<repo>.git
cd Major\ Project
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 5: Create Systemd Service
```bash
sudo nano /etc/systemd/system/ventilator-api.service
```

Paste:
```ini
[Unit]
Description=Ventilator AI API
After=network.target

[Service]
Type=notify
User=azureuser
WorkingDirectory=/home/azureuser/Major\ Project
ExecStart=/home/azureuser/Major\ Project/venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Step 6: Start Service
```bash
sudo systemctl daemon-reload
sudo systemctl start ventilator-api
sudo systemctl enable ventilator-api
sudo systemctl status ventilator-api
```

### Step 7: Configure Nginx (Reverse Proxy)
```bash
sudo nano /etc/nginx/sites-available/default
```

Replace with:
```nginx
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    
    server_name _;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Step 8: Restart Nginx
```bash
sudo systemctl restart nginx
```

**Result:** Your app will be available at:
```
http://<public-ip>
```

---

## Estimated Monthly Costs

| Option | SKU | CPU | RAM | Cost/Month |
|--------|-----|-----|-----|-----------|
| **App Service** | B2 | 2 | 3.5 GB | ~$50 |
| **Container Instances** | 2 CPU, 4 GB | 2 | 4 GB | ~$50 |
| **VM** | Standard_B2s | 2 | 4 GB | ~$50 |
| **VM + GPU** | Standard_NV6 | 6 | 56 GB | ~$400 |

---

## Monitoring & Logging

### Application Insights (Auto-Instrumentation)
```bash
az monitor app-insights component create \
  --resource-group ventilator-demo \
  --location eastus \
  --app ventilator-insights
```

### View Logs
```bash
az webapp log tail --resource-group ventilator-demo --name ventilator-ai-demo
```

---

## Cleanup (Delete Resources)
```bash
# Delete everything in the resource group
az group delete --resource-group ventilator-demo --yes
```

---

## Troubleshooting

### App Service won't start
```bash
# Check deployment logs
az webapp deployment log show --name ventilator-ai-demo --resource-group ventilator-demo --slot-name staging
```

### Container won't pull image
```bash
# Check image exists
az acr repository list --name ventilatorregistry

# Verify credentials
az acr login --name ventilatorregistry
```

### Can't connect to API
```bash
# Check if service is running
curl http://<ip>:8000/health

# Check firewall rules
az network nsg rule list --resource-group ventilator-demo --nsg-name <nsg-name>
```

---

## Quick Commands for Viva Day

If faculty asks to deploy live:

```bash
# 1. Show Docker image
docker build -t ventilator-api:latest .

# 2. Test locally
docker run -p 8000:8000 ventilator-api:latest

# 3. Push to registry
az acr build --registry ventilatorregistry --image ventilator-api:latest .

# 4. Deploy
az container create --resource-group ventilator-demo --name ventilator-api --image ventilatorregistry.azurecr.io/ventilator-api:latest --cpu 2 --memory 4 --ports 8000
```

---

## Dashboard URL (Once Deployed)

Frontend also needs to be deployed. Options:
1. **Static Hosting on Azure Blob Storage + CDN**
2. **Deploy to App Service alongside API**
3. **Use separate GitHub Pages**

Recommended: Deploy both API and frontend to same App Service.

---

**For your viva, you can say:**
> "The system is currently running locally. We can scale it to Azure in ~10 minutes using App Service or Container Instances. The architecture is cloud-native and doesn't require GPU for inference—only for model training, which we'd schedule on-demand via Azure Batch or Databricks to keep costs down."
