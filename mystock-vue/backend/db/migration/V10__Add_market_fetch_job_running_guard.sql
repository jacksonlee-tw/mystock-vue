-- V10__Add_market_fetch_job_running_guard.sql
-- 防止併發觸發全市場抓取／回補作業：同時間只允許存在一筆 status='running' 的紀錄。
-- run_async() 每次呼叫都會建立並丟棄整個連線池（見 repositories/market_repository.py 說明），
-- session 級的 pg_advisory_lock 無法跨越多次 run_async() 呼叫存活，改用部分唯一索引在 DB 層原子擋下併發 INSERT。

CREATE UNIQUE INDEX IF NOT EXISTS uq_mfj_single_running
    ON market_fetch_job (status)
    WHERE status = 'running';
