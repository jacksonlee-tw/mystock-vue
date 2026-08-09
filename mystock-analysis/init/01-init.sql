-- 初始化資料庫指令碼
-- 此檔案在 MySQL 容器啟動時自動執行

USE mystock_db;

-- 建立範例表（根據需要修改）
CREATE TABLE IF NOT EXISTS stocks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL UNIQUE COMMENT '股票代碼',
    name VARCHAR(100) NOT NULL COMMENT '股票名稱',
    current_price DECIMAL(10, 2) COMMENT '現價',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_symbol (symbol),
    CHARSET=utf8mb4,
    COLLATE=utf8mb4_unicode_ci
) ENGINE=InnoDB CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 插入範例資料
INSERT INTO stocks (symbol, name, current_price) VALUES 
('2330', '台積電', 600.00),
('2454', '聯發科', 950.00),
('2317', '鴻海', 155.00)
ON DUPLICATE KEY UPDATE updated_at = NOW();

-- 建立其他所需表格（按需添加）
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHARSET=utf8mb4,
    COLLATE=utf8mb4_unicode_ci
) ENGINE=InnoDB CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
