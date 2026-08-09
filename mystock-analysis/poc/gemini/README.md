# Gemini POC

使用 Google Gemini API 進行簡單問答的 Python 範例程式。

---

## 環境需求

- Python 3.9+
- 已申請 Gemini API Key（取得方式見下方說明）

---

## 取得 Gemini API Key

1. 前往 [Google AI Studio](https://aistudio.google.com/prompts/new_chat) 並登入 Google 帳號
2. 點選左側選單「Get API key」或直接前往 [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
3. 點擊「Create API key」產生新的金鑰
4. 複製金鑰後設定至環境變數 `GEMINI_API_KEY`（詳見下方說明）

> **注意**：API Key 僅顯示一次，請妥善保存，切勿公開或提交至版本控制。

---

## 安裝相依套件

```bash
pip install google-genai
```

---

## 設定 API Key

程式透過環境變數 `GEMINI_API_KEY` 取得 API Key，執行前請先設定：

**PowerShell（Windows）**
```powershell
$env:GEMINI_API_KEY = "your_api_key_here"
```

**CMD（Windows）**
```cmd
set GEMINI_API_KEY=your_api_key_here
```

**Bash / Zsh（macOS / Linux）**
```bash
export GEMINI_API_KEY="your_api_key_here"
```

---

## 執行方式

```bash
python main.py
```

執行後會提示輸入問題：

```
請輸入你想問 Gemini 的問題：台灣的首都是哪裡？
Gemini 回覆：
台灣的首都是台北市。
```

---

## 程式說明

| 項目 | 說明 |
|------|------|
| 使用模型 | `gemini-2.0-flash` |
| API Key 來源 | 環境變數 `GEMINI_API_KEY` |
| 互動方式 | 終端機輸入問題，回覆顯示於終端機 |

---

## 注意事項

- 請勿將 API Key 直接寫入程式碼或提交至版本控制。
- 若未設定環境變數，程式將因 API Key 為 `None` 而拋出驗證錯誤。
