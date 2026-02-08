# Azure App Service Deployment Guide

Bu uygulama Azure App Service'e Docker container olarak deploy edilebilir.

## Ön Gereksinimler

1. Azure CLI yüklü olmalı
2. Docker yüklü olmalı
3. Azure Container Registry (ACR) oluşturulmuş olmalı

## Adım 1: Azure'a Giriş

```bash
az login
```

## Adım 2: Resource Group Oluşturma

```bash
az group create --name maf-demo-rg --location westeurope
```

## Adım 3: Azure Container Registry Oluşturma

```bash
az acr create --resource-group maf-demo-rg --name mafdemoregistry --sku Basic
az acr login --name mafdemoregistry
```

## Adım 4: Docker Image Build ve Push

```bash
# Image build
docker build -t mafdemoregistry.azurecr.io/maf-demo-app:latest .

# Image push
docker push mafdemoregistry.azurecr.io/maf-demo-app:latest
```

## Adım 5: App Service Plan Oluşturma

```bash
az appservice plan create \
  --name maf-demo-plan \
  --resource-group maf-demo-rg \
  --sku F1 \
  --is-linux
```

## Adım 6: Web App Oluşturma

```bash
az webapp create \
  --resource-group maf-demo-rg \
  --plan maf-demo-plan \
  --name maf-demo-app \
  --deployment-container-image-name mafdemoregistry.azurecr.io/maf-demo-app:latest
```

## Adım 7: ACR Credentials Ayarlama

```bash
# ACR admin credentials'ı etkinleştir
az acr update --name mafdemoregistry --admin-enabled true

# Credentials'ı al
ACR_USERNAME=$(az acr credential show --name mafdemoregistry --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name mafdemoregistry --query passwords[0].value -o tsv)

# Web App'e ACR credentials ekle
az webapp config container set \
  --name maf-demo-app \
  --resource-group maf-demo-rg \
  --docker-custom-image-name mafdemoregistry.azurecr.io/maf-demo-app:latest \
  --docker-registry-server-url https://mafdemoregistry.azurecr.io \
  --docker-registry-server-user $ACR_USERNAME \
  --docker-registry-server-password $ACR_PASSWORD
```

## Adım 8: Environment Variables Ayarlama

```bash
az webapp config appsettings set \
  --resource-group maf-demo-rg \
  --name maf-demo-app \
  --settings \
    AZURE_OPENAI_ENDPOINT="https://your-endpoint.openai.azure.com/" \
    AZURE_OPENAI_KEY="your-api-key" \
    AZURE_OPENAI_DEPLOYMENT="gpt-5.1-chat" \
    AZURE_OPENAI_API_VERSION="2024-02-15-preview" \
    WEBSITES_PORT=8000
```

## Adım 9: Uygulamayı Aç

```bash
az webapp browse --resource-group maf-demo-rg --name maf-demo-app
```

## Tek Komutla Deploy (deploy.sh)

Tüm adımları otomatik çalıştırmak için `deploy.sh` script'ini kullanabilirsiniz.

## Notlar

- `maf-demo-app` ismi unique olmalıdır, gerekirse değiştirin
- Azure OpenAI credentials'larını kendi değerlerinizle güncelleyin
- Container başlangıcı birkaç dakika sürebilir
