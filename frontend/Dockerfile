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

# Build app (only if needed)
RUN if [ -f "src/main.js" ] || [ -f "src/App.vue" ]; then npm run build; else mkdir -p dist && echo "<html><body><h1>Telegram Storage</h1><p>Frontend under development</p></body></html>" > dist/index.html; fi

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