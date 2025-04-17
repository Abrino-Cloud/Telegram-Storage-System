# Build stage
FROM node:18-alpine AS build-stage

# Set working directory
WORKDIR /app

# Copy package.json
COPY package*.json ./

# Install dependencies with specific optimizations
RUN npm install --no-fund --no-audit --progress=false --loglevel=error

# Copy all files
COPY . .

# Create a simple dist for development
RUN mkdir -p dist && \
    echo '<!DOCTYPE html><html><head><meta charset="utf-8"><title>Telegram Storage</title><style>body{font-family:sans-serif;margin:0;padding:0}header{background:#3498db;color:white;padding:20px;text-align:center}main{padding:20px}footer{background:#2c3e50;color:white;padding:10px;text-align:center;position:fixed;bottom:0;width:100%}</style></head><body><header><h1>Telegram Storage System</h1></header><main><h2>Welcome to AbrinoStorage</h2><p>The system is under development. Please check back later.</p></main><footer>AbrinoStorage - Telegram-based file storage</footer></body></html>' > dist/index.html

# Production stage
FROM nginx:stable-alpine AS production-stage

# Copy built files from build stage
COPY --from=build-stage /app/dist /usr/share/nginx/html

# Create a default nginx config
RUN echo "server { listen 80; location / { root /usr/share/nginx/html; index index.html; try_files \$uri \$uri/ /index.html; } }" > /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:80/ || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]


