import feedparser
import requests
import os
import re

# ==================== 常數設定 ====================
DEFAULT_OUTPUT_DIR = "./mp3"
CHUNK_SIZE = 1024 * 1024  # 1MB
FILE_EXTENSION = ".mp3"
# 這裡貼上您想下載的 Apple Podcasts 網址
APPLE_PODCAST_URL = "https://podcasts.apple.com/tw/podcast/ep655/id1500839292?i=1000763028792"
ENCLOSURE_REL = "enclosure"
CUSTOM_OUTPUT_FILENAME = "Gooaye-EP655_20260422"  # 若要指定檔名設定此變數 (不含副檔名)，留空則自動使用節目集數名稱
# ================================================

def get_rss_from_apple_podcast(apple_url):
    """方法二：自動從 Apple Podcasts 網址解析出原始 RSS 連結"""
    print(f"正在從 Apple Podcasts 網址提取 ID: {apple_url}")
    
    # 使用正則表達式抓取 'id' 後面的數字
    match = re.search(r'id(\d+)', apple_url)
    if not match:
        print("❌ 無法從網址中找到 Apple Podcast ID！")
        return None
    
    podcast_id = match.group(1)
    print(f"✅ 成功取得 ID: {podcast_id}，正在向 Apple API 查詢 RSS...")
    
    # 呼叫 Apple iTunes API
    lookup_url = f"https://itunes.apple.com/lookup?id={podcast_id}&entity=podcast"
    response = requests.get(lookup_url)
    
    if response.status_code == 200:
        data = response.json()
        if data['resultCount'] > 0:
            feed_url = data['results'][0].get('feedUrl')
            print(f"✅ 成功取得原始 RSS 連結: {feed_url}")
            return feed_url
        else:
            print("❌ Apple API 找不到此節目資訊！")
            return None
    else:
        print(f"❌ 查詢失敗，HTTP 狀態碼: {response.status_code}")
        return None

def download_latest_podcast(rss_url, output_dir=DEFAULT_OUTPUT_DIR, custom_filename=None):
    """從 RSS 連結下載最新一集的音檔"""
    # 確保輸出資料夾存在，若沒有則自動建立
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"正在解析 RSS Feed: {rss_url}")
    feed = feedparser.parse(rss_url)
    
    if not feed.entries:
        print("❌ 找不到任何 Podcast 集數！")
        return None

    # 取得最新的一集 (索引 0 通常是最新的)
    latest_episode = feed.entries[0]
    
    # 處理檔名，移除可能導致存檔錯誤的特殊字元 (只保留英數字、空白、減號、底線)
    safe_title = "".join([c for c in latest_episode.title if c.isalnum() or c in ' -_']).rstrip()
    
    # 尋找音檔的直接下載連結 (通常在 enclosure 屬性裡)
    audio_url = None
    for link in latest_episode.links:
        if link.rel == ENCLOSURE_REL:
            audio_url = link.href
            break
            
    if not audio_url:
        print("❌ 在這集中找不到音檔連結！")
        return None

    print(f"🎙️ 找到最新集數: {safe_title}")
    print(f"準備下載音檔...")

    # 設定存檔路徑
    # 優先使用自定義檔名，若未指定則使用處理過的安全集數標題
    filename = custom_filename if custom_filename else safe_title
    file_path = os.path.join(output_dir, f"{filename}{FILE_EXTENSION}")

    # 執行下載檔案，使用 stream 模式避免佔用過多記憶體
    response = requests.get(audio_url, stream=True)
    if response.status_code == 200:
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    f.write(chunk)
        print(f"✅ 下載完成！已儲存至: {file_path}")
        return file_path
    else:
        print(f"❌ 下載失敗，HTTP 狀態碼: {response.status_code}")
        return None

# ==================== 執行區塊 ====================
if __name__ == "__main__":
    # 步驟 1：先從 Apple Podcasts 網址自動解析出原始 RSS Feed
    rss_feed_url = get_rss_from_apple_podcast(APPLE_PODCAST_URL)
    
    # 步驟 2：如果成功取得 RSS 連結，就丟給下載函式去抓最新一集
    if rss_feed_url:
        print("-" * 40)
        downloaded_file = download_latest_podcast(rss_feed_url, custom_filename=CUSTOM_OUTPUT_FILENAME)