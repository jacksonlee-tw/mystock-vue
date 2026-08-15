# 爬蟲開發.md 第七節「Docker 執行與排程」的容器化實作。
#
# 排程器（services/scheduler.py 的 AsyncIOScheduler）是內嵌在 FastAPI 的 lifespan 裡跟著
# uvicorn 一起啟動，因此這裡不需要另外拆一個 crawler_worker 容器／entrypoint——
# 這個 image 同時扮演「API 服務」與「排程器」兩種角色，用單一容器跑起來即可。
#
# 多階段建置：
#   development → 熱重載開發（docker-compose.dev.yml 使用，原始碼由 volume 掛載，不 COPY）
#   production  → 原始碼烘進 image（backend/docker-compose.yml、根目錄 docker-compose.yml 使用）
# 沒有指定 --target 時，docker build 預設使用最後一個 stage（production），
# 與這裡修改前的單一 stage 行為完全相同，backend/docker-compose.yml 不需要跟著修改。

FROM python:3.11-slim AS base

WORKDIR /app

# tzdata 讓容器內時區顯示與 log 時間跟排程設定的 Asia/Taipei 一致；
# curl 供 docker-compose healthcheck 使用。
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Taipei \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 先只複製 requirements.txt 再安裝，讓「改程式碼」和「改依賴」分屬不同 layer，
# 一般開發只改 .py 檔時可以重用 pip install 的快取層。
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

# ---- development：原始碼由 docker-compose.dev.yml 的 volume 掛載進來，故不 COPY ----
FROM base AS development
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ---- production ----
FROM base AS production

COPY . .

# data/（爬蟲落地 JSON）、postgres_data/、backups/ 一律由 docker-compose 的 volume 掛載提供，
# 不烘進 image；.env 也不烘進 image（見 .dockerignore），啟動所需設定改用 docker-compose 的
# environment 區塊注入，避免把資料庫密碼之類的敏感資訊留在 image layer 裡。

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
