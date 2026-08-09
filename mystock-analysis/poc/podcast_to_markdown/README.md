# Podcast Pipeline — Apple Podcast 自動下載 → 逐字稿 → 摘要

從一條 Apple Podcast 網址出發，全自動完成三個步驟：

| 步驟 | 工具 | 輸出 |
|------|------|------|
| 1. 下載 MP3 | iTunes API + RSS + `requests` | `mp3/<檔名>.mp3` |
| 2. 轉錄逐字稿 | OpenAI Whisper（本機推論） | `md/<檔名>.md` |
| 3. 生成摘要 | OpenAI Chat API（`gpt-4o-mini`） | `md/<檔名>-摘要.md` |

> 若 MP3 已存在，步驟 1 自動跳過；步驟 3 需設定 `OPENAI_API_KEY`，未設定時跳過。

---

## 檔案說明

```
podcast_to_markdown/
├── podcast_pipeline.py   # ★ 主程式（三步驟一鍵執行）
├── download_podcast.py   # 獨立：僅下載 MP3
├── mp3_to_markdown.py    # 獨立：MP3 → 逐字稿
├── requirements.txt      # Python 相依套件
├── mp3/                  # 下載的 MP3（自動建立）
└── md/                   # 產出的 Markdown（自動建立）
```

---

## 環境需求

- Python 3.10+
- FFmpeg（Whisper 解碼音訊需要）
- CUDA（選用，有 GPU 時自動加速 Whisper）

---

## 安裝

```bash
# 安裝 Python 套件
pip install feedparser requests openai-whisper openai tqdm

# 安裝 FFmpeg（Windows，使用 winget）
winget install Gyan.FFmpeg
```

---

## 使用方式

### 1. 設定執行參數

開啟 `podcast_pipeline.py`，修改最上方「使用者設定」區的兩個變數：

```python
# Apple Podcast 單集網址（從瀏覽器或 App 複製）
APPLE_PODCAST_URL = "https://podcasts.apple.com/tw/podcast/.../id..."

# 自訂輸出檔名（不含副檔名）；留空則自動沿用集數標題
CUSTOM_OUTPUT_FILENAME = "Gooaye-EP655_20260425"
```

### 2. 設定 OpenAI API Key（選用，用於生成摘要）

```bash
# Windows PowerShell
$env:OPENAI_API_KEY = "sk-..."

# macOS / Linux
export OPENAI_API_KEY="sk-..."
```

### 3. 執行 Pipeline

```bash
cd poc/podcast_to_markdown
python podcast_pipeline.py
```

執行過程中會依序顯示：

```
==============================================================
  🎙️  Podcast Pipeline 開始執行
==============================================================

▶ [1/3] 下載 MP3
  ⏭️  MP3 已存在，跳過下載

▶ [2/3] 轉錄逐字稿
  🤖 正在載入 Whisper 模型（base）…
     ✔ 模型載入完成（3.2s）
  🎧 開始轉錄：Gooaye-EP655_20260425.mp3（可能需要幾分鐘）…
     ✔ 轉錄完成（182.4s，共 312 段）

▶ [3/3] 生成摘要
  💡 正在使用 gpt-4o-mini 生成摘要…
     ✔ 摘要生成完成（8.1s）

==============================================================
  ✅  Pipeline 執行完成！
==============================================================
  [1] 下載 MP3       ✅     0.1s
  [2] 轉錄逐字稿     ✅   185.8s
  [3] 生成摘要       ✅     8.1s
  ──────────────────────────────────────────────────────────
  總耗時：194.0s
==============================================================
```

---

## Whisper 模型大小對照

| 模型 | 速度 | 準確度 | 建議使用情境 |
|------|------|--------|-------------|
| `tiny` | 最快 | 普通 | 快速預覽 |
| `base` | 快 | 良好 | 日常使用（預設） |
| `small` | 中 | 較佳 | 需要更高準確度 |
| `medium` | 慢 | 好 | 有 GPU 時使用 |
| `large` | 最慢 | 最佳 | 高品質轉錄 |

在 `podcast_pipeline.py` 的「系統設定」區修改 `WHISPER_MODEL` 即可切換。