#!/bin/bash

# Azure App Service Deployment Script
# Usage: ./deploy.sh <app-name> <resource-group> <location>

set -e

APP_NAME=${1:-"maf-demo-app-$(date +%s)"}
RESOURCE_GROUP=${2:-"maf-demo-rg"}
LOCATION=${3:-"westeurope"}
ACR_NAME="${APP_NAME//-/}acr"
PLAN_NAME="${APP_NAME}-plan"

echo "🚀 Deploying $APP_NAME to Azure..."

# Login check
echo "📋 Checking Azure login..."
az account show > /dev/null 2>&1 || { echo "❌ Please run 'az login' first"; exit 1; }

# Create Resource Group
echo "📦 Creating Resource Group: $RESOURCE_GROUP..."
az group create --name $RESOURCE_GROUP --location $LOCATION --output none

# Create ACR
echo "🐳 Creating Container Registry: $ACR_NAME..."
az acr create --resource-group $RESOURCE_GROUP --name $ACR_NAME --sku Basic --output none
az acr update --name $ACR_NAME --admin-enabled true --output none

# Login to ACR
echo "🔐 Logging into ACR..."
az acr login --name $ACR_NAME

# Build and push image
echo "🔨 Building Docker image..."
docker build -t $ACR_NAME.azurecr.io/$APP_NAME:latest .

echo "📤 Pushing image to ACR..."
docker push $ACR_NAME.azurecr.io/$APP_NAME:latest

# Create App Service Plan
echo "📋 Creating App Service Plan: $PLAN_NAME..."
az appservice plan create \
  --name $PLAN_NAME \
  --resource-group $RESOURCE_GROUP \
  --sku F1 \
  --is-linux \
  --output none

# Get ACR credentials
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv)

# Create Web App
echo "🌐 Creating Web App: $APP_NAME..."
az webapp create \
  --resource-group $RESOURCE_GROUP \
  --plan $PLAN_NAME \
  --name $APP_NAME \
  --deployment-container-image-name $ACR_NAME.azurecr.io/$APP_NAME:latest \
  --output none

# Configure container settings
echo "⚙️ Configuring container settings..."
az webapp config container set \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --docker-custom-image-name $ACR_NAME.azurecr.io/$APP_NAME:latest \
  --docker-registry-server-url https://$ACR_NAME.azurecr.io \
  --docker-registry-server-user $ACR_USERNAME \
  --docker-registry-server-password $ACR_PASSWORD \
  --output none

# Set port
az webapp config appsettings set \
  --resource-group $RESOURCE_GROUP \
  --name $APP_NAME \
  --settings WEBSITES_PORT=8000 \
  --output none

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📝 Next steps:"
echo "1. Set your Azure OpenAI credentials:"
echo "   az webapp config appsettings set \\"
echo "     --resource-group $RESOURCE_GROUP \\"
echo "     --name $APP_NAME \\"
echo "     --settings \\"
echo "       AZURE_OPENAI_ENDPOINT='https://your-endpoint.openai.azure.com/' \\"
echo "       AZURE_OPENAI_KEY='your-api-key' \\"
echo "       AZURE_OPENAI_DEPLOYMENT='gpt-5.1-chat' \\"
echo "       AZURE_OPENAI_API_VERSION='2024-02-15-preview'"
echo ""
echo "2. Open your app:"
echo "   https://$APP_NAME.azurewebsites.net"
echo ""
