# Frontend Angular → archivos estáticos servidos por nginx (que también hace de proxy hacia la API en /api).
FROM node:22-alpine AS build
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci --legacy-peer-deps --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY docker-entrypoint.sh /docker-entrypoint.d/40-config.sh
COPY --from=build /web/dist/cosco-web/browser /usr/share/nginx/html
RUN chmod +x /docker-entrypoint.d/40-config.sh
EXPOSE 80
HEALTHCHECK --interval=15s --timeout=3s --retries=5 CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
