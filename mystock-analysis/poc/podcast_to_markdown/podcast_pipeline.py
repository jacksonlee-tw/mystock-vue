"""
Podcast Pipeline — 三步驟自動化流程
  Step 1: 從 Apple Podcast URL 解析 RSS，下載 MP3（若已存在則跳過）
  Step 2: 用 OpenAI Whisper 將 MP3 轉為帶時間戳記的逐字稿 Markdown
  Step 3: 呼叫 OpenAI Chat API 生成結構化摘要 Markdown（需設定 API Key）
"""

import feedparser
import requests
import os
import re
import time
import whisper
from openai import OpenAI
from tqdm import tqdm

# =============================================================
# ★  使用者設定 — 每集執行前請修改此區
# =============================================================

# Apple Podcast 單集網址（從瀏覽器或 App 複製）
APPLE_PODCAST_URL = "https://podcasts.apple.com/tw/podcast/ep655/id1500839292?i=1000763028792"

# 自訂輸出檔名（不含副檔名）；留空則自動沿用集數標題
CUSTOM_OUTPUT_FILENAME = "Gooaye-EP655_20260425"

# =============================================================
# ⚙  系統設定 — 通常不需修改
# =============================================================

# 輸出目錄
MP3_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mp3")
MD_OUTPUT_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "md")

# Whisper 轉錄模型大小：tiny / base / small / medium / large（愈大愈準但愈慢）
WHISPER_MODEL = "base"

# OpenAI：優先讀環境變數 OPENAI_API_KEY；未設定時跳過摘要步驟
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL   = "gpt-4o-mini"

# 下載分塊大小（1 MB）
CHUNK_SIZE = 1024 * 1024

# 內部常數
FILE_EXTENSION = ".mp3"
ENCLOSURE_REL  = "enclosure"   # RSS enclosure 連結 rel 值

# =============================================================
# FFmpeg 路徑自動偵測（Whisper 解碼音訊需要）
# =============================================================
_FFMPEG_CANDIDATES = [
    r"C:\Users\jackson.lee\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin",
    r"C:\ffmpeg\bin",
    r"C:\Program Files\ffmpeg\bin",
]
for _p in _FFMPEG_CANDIDATES:
    if os.path.exists(_p) and _p not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _p + ";" + os.environ["PATH"]
        break


# =============================================================
# Step 1  下載 MP3
# =============================================================

def _get_rss_from_apple_url(apple_url: str) -> str | None:
    """透過 iTunes Lookup API，將 Apple Podcast 網址轉換為 RSS Feed URL。"""
    print(f"\n📡 正在解析 Apple Podcast ID: {apple_url}")
    match = re.search(r'id(\d+)', apple_url)
    if not match:
        print("❌ 無法從網址中找到 Podcast ID")
        return None

    podcast_id = match.group(1)
    lookup_url = f"https://itunes.apple.com/lookup?id={podcast_id}&entity=podcast"
    resp = requests.get(lookup_url, timeout=15)

    if resp.status_code != 200:
        print(f"❌ iTunes API 查詢失敗，狀態碼：{resp.status_code}")
        return None

    data = resp.json()
    if data.get("resultCount", 0) == 0:
        print("❌ iTunes API 找不到此節目")
        return None

    feed_url = data["results"][0].get("feedUrl")
    print(f"✅ RSS Feed：{feed_url}")
    return feed_url


def download_mp3(apple_url: str, output_dir: str = MP3_OUTPUT_DIR,
                 custom_filename: str = "") -> str | None:
    """解析 RSS 並下載最新一集 MP3；若目標檔案已存在則跳過，直接回傳路徑。"""
    os.makedirs(output_dir, exist_ok=True)

    # 有自訂檔名時可提前確認，省去不必要的 RSS 網路請求
    if custom_filename.strip():
        early_path = os.path.join(output_dir, f"{custom_filename.strip()}{FILE_EXTENSION}")
        if os.path.exists(early_path):
            print(f"⏭️  MP3 已存在，跳過下載：{early_path}")
            return early_path

    rss_url = _get_rss_from_apple_url(apple_url)
    if not rss_url:
        return None

    print(f"\n📰 正在解析 RSS Feed …")
    feed = feedparser.parse(rss_url)
    if not feed.entries:
        print("❌ RSS Feed 中找不到任何集數")
        return None

    episode   = feed.entries[0]
    safe_title = "".join(c for c in episode.title if c.isalnum() or c in " -_").rstrip()

    # 從 RSS entry 的 links 中找出 enclosure（實際音檔 URL）
    audio_url = next(
        (lk.href for lk in episode.links if lk.rel == ENCLOSURE_REL), None
    )
    if not audio_url:
        print("❌ 找不到音檔下載連結")
        return None

    filename  = custom_filename.strip() if custom_filename.strip() else safe_title
    file_path = os.path.join(output_dir, f"{filename}{FILE_EXTENSION}")

    print(f"🎙️ 集數：{safe_title}")

    # 使用集數標題命名時，在取得標題後才能確認路徑，再次檢查
    if os.path.exists(file_path):
        print(f"⏭️  MP3 已存在，跳過下載：{file_path}")
        return file_path

    print(f"⬇️  開始下載 → {file_path}")

    resp = requests.get(audio_url, stream=True, timeout=60)
    if resp.status_code != 200:
        print(f"❌ 下載失敗，狀態碼：{resp.status_code}")
        return None

    total_size = int(resp.headers.get("content-length", 0))
    with open(file_path, "wb") as f, tqdm(
        desc="   進度",
        total=total_size,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        ncols=80,
    ) as bar:
        for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                f.write(chunk)
                bar.update(len(chunk))

    print(f"✅ MP3 已儲存：{file_path}")
    return file_path


# =============================================================
# Step 2  MP3 → 逐字稿 Markdown
# =============================================================

def _format_time(seconds: float) -> str:
    """將秒數轉為 MM:SS 格式，用於逐字稿時間戳記。"""
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def transcribe_to_markdown(mp3_path: str, output_dir: str = MD_OUTPUT_DIR) -> tuple[str, str]:
    """用 Whisper 轉錄 MP3，產生帶時間戳記的逐字稿 Markdown，回傳 (md_path, full_text)。"""
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n🤖 正在載入 Whisper 模型（{WHISPER_MODEL}）…")
    t0 = time.time()
    model = whisper.load_model(WHISPER_MODEL)
    print(f"   ✔ 模型載入完成（{time.time() - t0:.1f}s）")

    print(f"🎧 開始轉錄：{os.path.basename(mp3_path)}（可能需要幾分鐘）…")
    t0 = time.time()
    result = model.transcribe(mp3_path)
    print(f"   ✔ 轉錄完成（{time.time() - t0:.1f}s，共 {len(result['segments'])} 段）")

    segments  = result["segments"]
    full_text = result["text"]

    # 組合逐字稿 Markdown：標頭 + 各段落時間戳記
    basename = os.path.basename(mp3_path)
    md_lines = [
        "# Podcast 逐字稿\n",
        f"**音檔來源:** `{basename}`\n",
        "---\n",
        "## 內容段落\n",
    ]
    for seg in segments:
        ts   = _format_time(seg["start"])
        text = seg["text"].strip()
        md_lines.append(f"**[{ts}]** {text}\n")

    md_path = os.path.join(output_dir, f"{os.path.splitext(basename)[0]}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"✅ 逐字稿已儲存：{md_path}")
    return md_path, full_text


# =============================================================
# Step 3  逐字稿 → 摘要 Markdown（需要 OpenAI API Key）
# =============================================================

_SUMMARY_PROMPT = """\
請根據以下 Podcast 逐字稿，以繁體中文產生一份結構化摘要 Markdown，格式要求：
1. H1 標題（包含節目名稱、集數、日期）
2. 目錄（各主題段落連結）
3. 各主題段落：H2 標題 + 重點條列（使用 emoji 增加可讀性）
4. 最後一節「本集重點一覽」：以 Markdown 表格呈現
只輸出 Markdown 內容，不需要任何前置說明。

逐字稿：
{transcript}
"""


def summarize_to_markdown(transcript: str, mp3_basename: str,
                          output_dir: str = MD_OUTPUT_DIR,
                          api_key: str = OPENAI_API_KEY) -> str | None:
    """將逐字稿送交 OpenAI Chat API 生成結構化摘要；未設定 API Key 時自動跳過，回傳 None。"""
    if not api_key:
        print("\n⚠️  未設定 OPENAI_API_KEY，跳過摘要生成")
        print("   請設定環境變數 OPENAI_API_KEY 或在常數設定區填入 API Key")
        return None

    os.makedirs(output_dir, exist_ok=True)

    print(f"\n💡 正在使用 {OPENAI_MODEL} 生成摘要…")
    t0 = time.time()
    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "你是一位專業的 Podcast 內容整理助手，擅長將逐字稿整理成結構清晰的繁體中文摘要。"},
            {"role": "user",   "content": _SUMMARY_PROMPT.format(transcript=transcript)},
        ],
        temperature=0.3,
    )
    print(f"   ✔ 摘要生成完成（{time.time() - t0:.1f}s）")

    summary_text = response.choices[0].message.content

    stem        = os.path.splitext(mp3_basename)[0]
    summary_path = os.path.join(output_dir, f"{stem}-摘要.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary_text)

    print(f"✅ 摘要已儲存：{summary_path}")
    return summary_path


# =============================================================
# 主程式
# =============================================================

if __name__ == "__main__":
    pipeline_start = time.time()
    step_times: dict[str, float] = {}

    print("=" * 62)
    print("  🎙️  Podcast Pipeline 開始執行")
    print("=" * 62)

    # ── Step 1：下載 MP3 ──────────────────────────────────────
    print("\n▶ [1/3] 下載 MP3")
    t0 = time.time()
    mp3_path = download_mp3(
        apple_url=APPLE_PODCAST_URL,
        custom_filename=CUSTOM_OUTPUT_FILENAME,
    )
    step_times["download"] = time.time() - t0
    if not mp3_path:
        print("\n❌ MP3 下載失敗，程式結束")
        raise SystemExit(1)

    # ── Step 2：MP3 → 逐字稿 MD ───────────────────────────────
    print("\n▶ [2/3] 轉錄逐字稿")
    t0 = time.time()
    transcript_md_path, full_text = transcribe_to_markdown(mp3_path)
    step_times["transcribe"] = time.time() - t0

    # ── Step 3：逐字稿 → 摘要 MD ──────────────────────────────
    print("\n▶ [3/3] 生成摘要")
    t0 = time.time()
    summary_md_path = summarize_to_markdown(
        transcript=full_text,
        mp3_basename=os.path.basename(mp3_path),
    )
    step_times["summarize"] = time.time() - t0

    total_elapsed = time.time() - pipeline_start

    # ── 執行結果 ──────────────────────────────────────────────
    print("\n" + "=" * 62)
    print("  ✅  Pipeline 執行完成！")
    print("=" * 62)
    print(f"  [1] 下載 MP3       ✅  {step_times['download']:>6.1f}s")
    print(f"      → {mp3_path}")
    print(f"  [2] 轉錄逐字稿     ✅  {step_times['transcribe']:>6.1f}s")
    print(f"      → {transcript_md_path}")
    if summary_md_path:
        print(f"  [3] 生成摘要       ✅  {step_times['summarize']:>6.1f}s")
        print(f"      → {summary_md_path}")
    else:
        print(f"  [3] 生成摘要       ⏭️  跳過（未設定 OPENAI_API_KEY）")
    print(f"  {'─' * 58}")
    print(f"  總耗時：{total_elapsed:.1f}s")
    print("=" * 62)
