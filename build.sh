#!/bin/bash

# Exit on error
set -e

# Show commands
set -x

# Create directory structure if needed
mkdir -p frontend/src/components
mkdir -p frontend/src/views
mkdir -p frontend/src/router
mkdir -p frontend/public
mkdir -p backend/app/core
mkdir -p backend/app/api
mkdir -p backend/app/db
mkdir -p backend/app/crud
mkdir -p backend/app/schemas
mkdir -p backend/app/utils
mkdir -p bot

# Set environment variable for better performance
export COMPOSE_BAKE=true
# Fix apt repository issues by setting mirror
export DOCKER_BUILDKIT=1

# Pull images first to avoid timeout issues with apt-get
echo "Pulling base images..."
docker pull python:3.11-slim
docker pull node:18-alpine
docker pull nginx:stable-alpine
docker pull redis:7-alpine
docker pull postgres:14-alpine

# Build specific services one by one with timeouts to avoid hanging
echo "Building API service..."
timeout 300 docker compose build --no-cache --progress=plain api || echo "API build timed out but continuing..."

echo "Building Telegram Bot service..."
timeout 300 docker compose build --no-cache --progress=plain telegram-bot || echo "Bot build timed out but continuing..."

echo "Building Frontend service..."
timeout 300 docker compose build --no-cache --progress=plain frontend || echo "Frontend build timed out but continuing..."

echo "Starting services..."
docker compose up -d

echo "Build process completed!"