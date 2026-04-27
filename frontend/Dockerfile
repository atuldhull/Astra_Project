# ASTRA frontend — Vite build → nginx static.

FROM node:22-alpine AS build
WORKDIR /app

# Build args so VITE_* env can be baked at build time
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY package.json package-lock.json /app/
RUN npm ci

COPY . /app
RUN npm run build

# ── Runtime ──────────────────────────────────────────────────────────
FROM nginx:1.27-alpine

# Reverse-proxy /api → backend:8000 so the frontend hits the same origin.
RUN cat > /etc/nginx/conf.d/default.conf <<'EOF'
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    location /ws/ {
        proxy_pass http://backend:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    location /health {
        proxy_pass http://backend:8000/health;
    }

    # SPA fallback
    location / {
        try_files $uri /index.html;
    }
}
EOF

COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
