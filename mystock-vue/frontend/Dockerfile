# 多階段建置：
#   development → 熱重載開發（docker-compose.dev.yml 使用，原始碼由 volume 掛載）
#   build       → 產出正式靜態檔（dist/），僅供 production 階段內部使用
#   production  → 以 nginx 提供 build 階段產出的靜態檔，並反向代理 /api 給 backend
#                （docker-compose.yml 使用；見 nginx.conf）
#
# VITE_API_BASE 於建置期烘進 JS，預設為相對路徑 /api/v1，交由 nginx.conf 轉發至
# backend:8000，因此同一份建置產物換環境／換主機都不需要重新建置。

# ---- development ----
FROM node:20-alpine AS development
WORKDIR /app
COPY package*.json ./
RUN npm install
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# ---- build（僅供 production 階段取用產物，不單獨執行） ----
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE=/api/v1
ENV VITE_API_BASE=${VITE_API_BASE}
RUN npm run build

# ---- production ----
# 使用 alpine 版本是因為內建 busybox wget，healthcheck 不需要額外安裝套件；
# 若日後部署主機的 Linux kernel 過舊（例如 CentOS 7 / kernel < 4.6）導致 nginx
# 啟動時出現 pwrite() 相關錯誤，改用非 alpine 的 nginx:1.27 即可排除。
FROM nginx:1.27-alpine AS production
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=10s --timeout=5s --retries=3 --start-period=10s \
    CMD wget -qO- http://127.0.0.1:80/ || exit 1
CMD ["nginx", "-g", "daemon off;"]
