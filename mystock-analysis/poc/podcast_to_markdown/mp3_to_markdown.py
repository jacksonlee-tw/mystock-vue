import whisper
import os
import sys

# ==================== FFmpeg 路徑設置 ====================
# 自動尋找並添加 FFmpeg 到 PATH
ffmpeg_paths = [
    r"C:\Users\jackson.lee\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin",
    r"C:\ffmpeg\bin",
    r"C:\Program Files\ffmpeg\bin",
]
for ffmpeg_path in ffmpeg_paths:
    if os.path.exists(ffmpeg_path):
        if ffmpeg_path not in os.environ.get("PATH", ""):
            os.environ["PATH"] = ffmpeg_path + ";" + os.environ.get("PATH", "")
        break
# ================================================

# ==================== 常數設定 ====================
INPUT_AUDIO_FILENAME = "Gooaye-EP655_20260425.mp3"  # 只需檔案名稱
INPUT_AUDIO_DIR = r"mp3"  # 音檔所在子目錄
OUTPUT_DIR = r"C:\github_repos\#ai-agent\mystock-analysis\poc\podcast_to_markdown\md"
WHISPER_MODEL = "base"  # 可選：tiny, base, small, medium, large
# ================================================

def podcast_to_markdown(audio_path, output_md_path):
    print(f"正在載入 Whisper 模型...")
    # Whisper 提供不同大小的模型：tiny, base, small, medium, large
    # 模型越大越精準，但需要越多的記憶體與運算時間。這裡先用 'base' 示範。
    model = whisper.load_model(WHISPER_MODEL)

    print(f"正在處理音檔：{audio_path}，這可能需要幾分鐘...")
    # transcribe 會自動偵測語言並進行轉錄
    result = model.transcribe(audio_path)
    
    # 取得轉錄文字
    transcribed_text = result["text"]
    
    # 取得各段落的時間軸 (可選，讓 Markdown 更有結構)
    segments = result["segments"]

    print(f"轉錄完成，正在生成 Markdown 檔案...")
    
    # 建立 Markdown 內容
    md_content = f"# Podcast 逐字稿\n\n"
    md_content += f"**音檔來源:** `{os.path.basename(audio_path)}`\n\n"
    md_content += "---\n\n"
    md_content += "## 內容段落\n\n"

    # 將帶有時間軸的段落寫入 Markdown
    for segment in segments:
        start_time = format_time(segment['start'])
        text = segment['text'].strip()
        md_content += f"**[{start_time}]** {text}\n\n"

    # 儲存為 .md 檔案
    with open(output_md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
        
    print(f"成功儲存至：{output_md_path}")

def format_time(seconds):
    """將秒數轉換為 MM:SS 的格式"""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"

# 執行範例
if __name__ == "__main__":
    # 確保輸出目錄存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 完整輸入路徑（相對於此指令檔）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_audio = os.path.join(script_dir, INPUT_AUDIO_DIR, INPUT_AUDIO_FILENAME)
    
    # 輸出檔案完整路徑
    output_filename = f"{os.path.splitext(INPUT_AUDIO_FILENAME)[0]}.md"
    output_file = os.path.join(OUTPUT_DIR, output_filename)
    
    if os.path.exists(input_audio):
        print(f"輸入檔案：{input_audio}")
        print(f"輸出檔案：{output_file}")
        podcast_to_markdown(input_audio, output_file)
    else:
        print(f"找不到音檔：{input_audio}，請確認路徑是否正確。")