# Docker & MySQL 設定指南

## 快速開始

### 1. 建立環境變數檔案
```bash
cp .env.example .env
```

### 2. 啟動容器
```bash
docker-compose up -d
```

### 3. 檢查容器狀態
```bash
docker-compose ps
```

### 4. 查看日誌
```bash
# 查看所有容器日誌
docker-compose logs -f

# 只查看 MySQL 日誌
docker-compose logs -f mysql

# 只查看 Backend 日誌
docker-compose logs -f backend
```

## 常用命令

### MySQL 連線
```bash
# 進入 MySQL 容器
docker-compose exec mysql mysql -u mystock_user -pmystock_password mystock_db

# 或直接使用本地 MySQL 用戶端
mysql -h 127.0.0.1 -u mystock_user -pmystock_password -D mystock_db
```

### 停止容器
```bash
docker-compose down
```

### 停止並刪除所有資料
```bash
docker-compose down -v
```

### 重啟單個服務
```bash
docker-compose restart mysql
docker-compose restart backend
```

## 環境變數設定

編輯 `.env` 檔案修改：
- `MYSQL_ROOT_PASSWORD` - MySQL root 密碼
- `MYSQL_DATABASE` - 資料庫名稱
- `MYSQL_USER` - MySQL 使用者名稱
- `MYSQL_PASSWORD` - MySQL 使用者密碼

## 目錄結構

```
mystock-analysis/
├── docker-compose.yml      # Docker Compose 配置
├── Dockerfile              # FastAPI 後端鏡像
├── .env.example            # 環境變數範本
├── init/
│   └── 01-init.sql         # MySQL 初始化指令碼
└── README-DOCKER.md        # 本文件
```

## 服務訊息

| 服務 | 端口 | 連接字符串 |
|-----|------|----------|
| MySQL | 3306 | m ysql://mystock_user:mystock_password@localhost:3306/mystock_db |
| FastAPI | 8000 | http://localhost:8000 |

## 常見問題

### 1. MySQL 容器無法啟動
```bash
# 檢查日誌
docker-compose logs mysql

# 確保端口 3306 未被佔用
netstat -an | grep 3306
```

### 2. Database connection refused
- 確保 MySQL 容器已完全啟動（約 10-20 秒）
- 檢查 `.env` 中的認證資訊是否正確
- 確保 `depends_on` 中的健康檢查成功

### 3. 重新初始化資料庫
```bash
# 停止並刪除所有資料
docker-compose down -v

# 重新啟動
docker-compose up -d
```

## 生產環境注意事項

- 修改所有預設密碼，特別是 `MYSQL_ROOT_PASSWORD` 和 `MYSQL_PASSWORD`
- 使用強密碼（至少 16 個字元）
- 設定 `rebuild` 為 `never` 避免自動重啟
- 配置備份策略
- 使用 `volumes` 持久化資料

## 進階設定

### 增加 MySQL 記憶體限制
編輯 `docker-compose.yml`：
```yaml
mysql:
  deploy:
    resources:
      limits:
        memory: 2G
      reservations:
        memory: 512M
```

### 修改 MySQL 配置
建立 `mysql.cnf` 並掛載到容器：
```yaml
mysql:
  volumes:
    - ./mysql.cnf:/etc/mysql/conf.d/mysql.cnf
```
