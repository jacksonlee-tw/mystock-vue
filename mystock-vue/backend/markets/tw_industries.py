"""台股官方產業分類代碼表（見 docs/10.加權指數/大盤指數功能規劃書.md §8）。

單一事實來源，同時供兩處使用：
- P5 類股指數（services/index_fetcher.py 的 fetch_and_store_sector_snapshot()）：
  `index_name` 對應 TWSE `MI_INDEX?type=IND` 回應裡的指數名稱字串，用來從當日快照比對出
  該產業的收盤指數。
- P6 個股產業標籤（services/industry_fetcher.py）：`name` 對應 TWSE OpenAPI
  `t187ap03_L`／TPEx `mopsfin_t187ap03_O` 回應裡「產業別」欄位的代碼（"01"、"02"…）。

代碼與名稱依 TWSE 上市公司產業分類標準（2026-08-15 以 openapi.twse.com.tw/v1/opendata/t187ap03_L
與 rwd/zh/afterTrading/MI_INDEX?type=IND 實測比對）；91（存託憑證）沒有對應的類股指數，
`index_name` 留 None。代碼清單若未來新增類別，只需在此補一筆，不需要改動抓取邏輯。
"""

TWSE_INDUSTRY_MAP: dict[str, dict] = {
    "01": {"name": "水泥工業", "index_name": "水泥類指數"},
    "02": {"name": "食品工業", "index_name": "食品類指數"},
    "03": {"name": "塑膠工業", "index_name": "塑膠類指數"},
    "04": {"name": "紡織纖維", "index_name": "紡織纖維類指數"},
    "05": {"name": "電機機械", "index_name": "電機機械類指數"},
    "06": {"name": "電器電纜", "index_name": "電器電纜類指數"},
    "08": {"name": "玻璃陶瓷", "index_name": "玻璃陶瓷類指數"},
    "09": {"name": "造紙工業", "index_name": "造紙類指數"},
    "10": {"name": "鋼鐵工業", "index_name": "鋼鐵類指數"},
    "11": {"name": "橡膠工業", "index_name": "橡膠類指數"},
    "12": {"name": "汽車工業", "index_name": "汽車類指數"},
    "13": {"name": "電子工業", "index_name": "電子工業類指數"},
    "14": {"name": "建材營造業", "index_name": "建材營造類指數"},
    "15": {"name": "航運業", "index_name": "航運類指數"},
    "16": {"name": "觀光餐旅業", "index_name": "觀光餐旅類指數"},
    "17": {"name": "金融保險業", "index_name": "金融保險類指數"},
    "18": {"name": "貿易百貨業", "index_name": "貿易百貨類指數"},
    "20": {"name": "其他業", "index_name": "其他類指數"},
    "21": {"name": "化學工業", "index_name": "化學類指數"},
    "22": {"name": "生技醫療業", "index_name": "生技醫療類指數"},
    "23": {"name": "油電燃氣業", "index_name": "油電燃氣類指數"},
    "24": {"name": "半導體業", "index_name": "半導體類指數"},
    "25": {"name": "電腦及週邊設備業", "index_name": "電腦及週邊設備類指數"},
    "26": {"name": "光電業", "index_name": "光電類指數"},
    "27": {"name": "通信網路業", "index_name": "通信網路類指數"},
    "28": {"name": "電子零組件業", "index_name": "電子零組件類指數"},
    "29": {"name": "電子通路業", "index_name": "電子通路類指數"},
    "30": {"name": "資訊服務業", "index_name": "資訊服務類指數"},
    "31": {"name": "其他電子業", "index_name": "其他電子類指數"},
    "35": {"name": "綠能環保業", "index_name": "綠能環保類指數"},
    "36": {"name": "數位雲端業", "index_name": "數位雲端類指數"},
    "37": {"name": "運動休閒業", "index_name": "運動休閒類指數"},
    "38": {"name": "居家生活業", "index_name": "居家生活類指數"},
    "91": {"name": "存託憑證", "index_name": None},
}


def get_industry_name(code: str) -> str:
    entry = TWSE_INDUSTRY_MAP.get(code)
    return entry["name"] if entry else f"未分類（代碼 {code}）"


# 類股指數 JSON/symbol 代號前綴，見 services/index_fetcher.py 的 fetch_and_store_sector_snapshot()。
SECTOR_CODE_PREFIX = "TWSE_S"


def sector_code(industry_code: str) -> str:
    return f"{SECTOR_CODE_PREFIX}{industry_code}"
