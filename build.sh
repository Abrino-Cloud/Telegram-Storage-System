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

# Build specific services one by one
echo "Building API service..."
docker compose build --progress=plain api

echo "Building Telegram Bot service..."
docker compose build --progress=plain telegram-bot

echo "Building Frontend service..."
docker compose build --progress=plain frontend

echo "All services built successfully!"