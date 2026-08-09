"""
三大法人買賣超／融資融券／每日行情資料抓取模組。

負責向 TWSE 公開資訊抓取指定股票近 N 個月的三大法人買賣超、融資融券餘額、
每日行情（開高低收與成交量值）資料，並將結果存成 CSV 快照與依股票代號分檔的
JSON（data/{股票代號}.json，供 plot_chart.py 繪圖用）。

使用三個 TWSE 端點：
    - T86（三大法人買賣超）：逐日、全市場快照，已抓過的日期會自動跳過。
    - MI_MARGN（融資融券彙總）：與 T86 同一形狀（逐日、全市場快照），併入同一個
      日迴圈一起抓取，不另外跑一輪獨立迴圈（見 docs/README.md「資料來源」一節）。
    - STOCK_DAY（每日行情）：改用單股單月，而非逐日全市場的 STOCK_DAY_ALL，
      大幅降低請求量（股票數 × 月份數，而非天數），避免長時間高頻率請求時
      被 TWSE 節流導致逾時（見 docs/README.md「已知限制」）。除收盤價外，也一併
      解析開盤價、最高價、最低價、成交股數、成交金額、成交筆數。

供 main.py 呼叫；也可單獨執行 `python institutional_fetcher.py` 只做抓取、不畫圖。
"""
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import json
import os
import calendar
from dotenv import load_dotenv

# 資料收集目錄：存放歷次抓取的三大法人 JSON 資料，供後續分析/製圖使用
# 每檔股票各自存成一個檔案：data/{股票代號}.json
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# 讀取同目錄下的 .env（不存在也不會報錯），用來設定要追蹤的股票代號（STOCK_CODES）
load_dotenv(os.path.join(BASE_DIR, ".env"))

# .env 未設定/找不到檔案時的預設股票清單
DEFAULT_STOCKS = ["0050", "2330", "006208"]


def get_target_stocks() -> list:
    """
    從 .env 的 STOCK_CODES 讀取要追蹤的股票代號清單（逗號分隔，例如
    STOCK_CODES=0050,2330,006208），可隨時編輯 .env 增減股票，不需修改程式碼。
    未設定或為空時，回退使用 DEFAULT_STOCKS。
    """
    raw = os.getenv("STOCK_CODES", "")
    stocks = [s.strip() for s in raw.split(",") if s.strip()]
    return stocks or DEFAULT_STOCKS


def stock_json_path(stock_id: str) -> str:
    """回傳指定股票代號對應的資料檔路徑，例如 2330 -> data/2330.json"""
    return os.path.join(DATA_DIR, f"{stock_id}.json")


def load_stock_json(stock_id: str) -> dict:
    """讀取單一股票既有的 JSON 資料；檔案不存在或損毀則回傳空字典。"""
    path = stock_json_path(stock_id)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"⚠️ 讀取既有 JSON 失敗，將視為無資料 ({path}): {e}")
        return {}


def find_stocks_without_data(target_stocks: list | None = None) -> list:
    """
    回傳 target_stocks 中「完全沒有資料」的股票代號（維持原本的順序）。

    判定條件是 data/{股票代號}.json 不存在或內容為空——也就是這檔股票從未抓過。
    典型情境：使用者在 .env 的 STOCK_CODES 新增了一檔股票，但還沒抓過它的資料。
    未指定 target_stocks 時，以 .env 的設定為準（get_target_stocks()）。
    """
    stocks = target_stocks or get_target_stocks()
    return [stock_id for stock_id in stocks if not load_stock_json(stock_id)]


# 記錄「TWSE 確認無交易資料」的日期（國定假日等），避免每次執行都重新查詢同一批
# 已確認的非交易日。刻意獨立於各股票的 JSON 之外，因為 T86 是全市場快照，
# 一旦某天確認無資料，對所有股票都成立。
NO_TRADING_DAYS_FILE = os.path.join(DATA_DIR, "_no_trading_days.json")


def load_no_trading_days() -> set:
    """讀取已確認無交易資料的日期集合；檔案不存在或損毀則回傳空集合。"""
    if not os.path.exists(NO_TRADING_DAYS_FILE):
        return set()
    try:
        with open(NO_TRADING_DAYS_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (json.JSONDecodeError, OSError) as e:
        print(f"⚠️ 讀取無交易日快取失敗，將視為空 ({NO_TRADING_DAYS_FILE}): {e}")
        return set()


def save_no_trading_days(days: set) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(NO_TRADING_DAYS_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(days), f, ensure_ascii=False, indent=2)


# 預設資料日期範圍：近 3 個月（抓取範圍、plot_chart.py 繪圖範圍皆以此為準）
MONTHS_RANGE = 3


def months_ago(months: int, from_date: datetime | None = None) -> datetime:
    """
    回推「N 個月前」的日期（依日曆月計算，而非固定 30 天）。
    若原始日超出目標月份天數（如 5/31 回推 3 個月至 2 月），則取該月最後一天。
    """
    base = from_date or datetime.now()
    month_index = base.month - 1 - months
    year = base.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base.day, calendar.monthrange(year, month)[1])
    return base.replace(year=year, month=month, day=day)

def _months_in_range(days: int) -> list:
    """回傳近 `days` 天範圍內涵蓋到的所有 (year, month)（升冪、不重複）。"""
    today = datetime.now()
    start = today - timedelta(days=days - 1)
    months = []
    cursor = start.replace(day=1)
    while cursor <= today:
        months.append((cursor.year, cursor.month))
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)  # 跳到下個月 1 號
    return months


def _roc_date_to_iso(roc_date: str):
    """將 STOCK_DAY 回傳的民國年日期（如 "115/08/03"）轉為西元 ISO 格式（"2026-08-03"）。"""
    try:
        roc_year, month, day = roc_date.split("/")
        return f"{int(roc_year) + 1911}-{int(month):02d}-{int(day):02d}"
    except (ValueError, AttributeError):
        return None


# STOCK_DAY 原始欄位索引（0 起算）："日期","成交股數","成交金額","開盤價","最高價",
# "最低價","收盤價","漲跌價差","成交筆數","註記"——只取用分析需要的 7 個欄位，
# 「漲跌價差」不存（可由前後兩日收盤價相減即得，屬展示層計算，且該欄位在停牌／
# 除權息日格式不穩定）。
_STOCK_DAY_FIELD_MAP = {
    "開盤價": (3, float),
    "最高價": (4, float),
    "最低價": (5, float),
    "收盤價": (6, float),
    "成交股數(股)": (1, int),
    "成交金額(元)": (2, int),
    "成交筆數(筆)": (8, int),
}


def _parse_quote_field(row: list, index: int, cast):
    """解析 STOCK_DAY row 中索引 index 的數值欄位；停牌等異常格式（如 "--"）
    解析失敗時回傳 None，不中斷整列（或整個月份）的解析。"""
    try:
        return cast(str(row[index]).replace(",", ""))
    except (ValueError, IndexError, TypeError):
        return None


def fetch_daily_quotes(target_stocks: list, days: int) -> dict:
    """
    改用 TWSE 的 STOCK_DAY 端點（單股單月）預先抓取 target_stocks 在近 `days`
    天範圍內、涵蓋到的每個月份每日行情，回傳
    { 股票代號: { "YYYY-MM-DD": {開盤價,最高價,最低價,收盤價,成交股數(股),
    成交金額(元),成交筆數(筆)} } }。

    相較於逐日呼叫全市場的 STOCK_DAY_ALL（近 3 個月約 90 次請求），這裡改成
    「股票數 × 月份數」（3 檔股票 × 3 個月 = 9 次請求），大幅降低觸發 TWSE
    節流機制的機會——STOCK_DAY_ALL 在長時間、高頻率請求下容易開始逾時
    （見 docs/README.md「已知限制」），單股單月的請求量小很多，也更不容易踩到門檻。

    同一次請求裡的欄位不只收盤價，還有開高低與成交量值（見 _STOCK_DAY_FIELD_MAP），
    這裡一併解析儲存——零額外請求成本，資料早就在回應裡，只是原本沒有解析。
    """
    months = _months_in_range(days)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    quote_lookup = {stock_id: {} for stock_id in target_stocks}
    total = len(target_stocks) * len(months)
    n = 0

    for stock_id in target_stocks:
        for year, month in months:
            n += 1
            # 逐筆印出進度，避免這段（唯一有感等待時間的地方）畫面長時間無任何輸出
            print(f"   [{n}/{total}] {stock_id} {year}-{month:02d} ...", end=" ", flush=True)
            date_param = f"{year}{month:02d}01"
            url = f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?date={date_param}&stockNo={stock_id}&response=json"
            try:
                res = requests.get(url, headers=headers, timeout=10).json()
                if res.get("stat") == "OK":
                    rows = res.get("data", [])
                    for row in rows:
                        date_key = _roc_date_to_iso(row[0])
                        if date_key is None:
                            continue
                        close = _parse_quote_field(row, 6, float)
                        if close is None:
                            continue  # 沒有收盤價視為當天無有效資料，與舊版行為一致
                        quote = {"收盤價": close}
                        for field, (index, cast) in _STOCK_DAY_FIELD_MAP.items():
                            if field == "收盤價":
                                continue
                            # 個別欄位解析失敗（如 "--"）不影響其餘欄位，預設 0 而非
                            # None——沿用既有「收盤價=0 佔位、之後由回補補上」的慣例
                            value = _parse_quote_field(row, index, cast)
                            quote[field] = value if value is not None else cast(0)
                        quote_lookup[stock_id][date_key] = quote
                    print(f"✅ {len(rows)} 個交易日")
                else:
                    print("⏸️ 無收盤價資料")
            except Exception as e:
                print(f"⚠️ 失敗: {e}")

            # ⚠️ 請保留延遲，避免 API 被鎖
            time.sleep(3)

    return quote_lookup


def backfill_daily_quotes(target_stocks: list, quote_lookup: dict) -> int:
    """
    用 quote_lookup（見 fetch_daily_quotes()）修補 data/{股票代號}.json 中既有的
    0 元收盤價佔位值，或欠缺開高低量欄位的舊格式記錄（連帶重算估算金額），
    不需要重新抓取 T86。

    回傳實際修補的筆數。
    """
    patched = 0
    for stock_id in target_stocks:
        stock_data = load_stock_json(stock_id)
        if not stock_data:
            continue

        changed = False
        for date_key, record in stock_data.items():
            # 「收盤價=0」代表先前抓取失敗留下的佔位值；「缺開盤價」代表這筆是
            # 本次擴充欄位前留下的舊格式紀錄——兩種情況都需要用新抓到的行情補上
            if record.get("收盤價", 0) != 0 and "開盤價" in record:
                continue
            quote = quote_lookup.get(stock_id, {}).get(date_key)
            if not quote:
                continue
            record.update(quote)
            total_lots = record.get("合計買賣超(張)", 0)
            record["估算買賣超金額(萬元)"] = round(total_lots * quote["收盤價"] / 10, 2)
            changed = True
            patched += 1

        if changed:
            with open(stock_json_path(stock_id), "w", encoding="utf-8") as f:
                json.dump(stock_data, f, ensure_ascii=False, indent=2)

    return patched


# MI_MARGN table[1]（個股融資融券彙總）原始欄位索引（0 起算）："代號","名稱",
# "買進","賣出","現金償還","前日餘額","今日餘額","次一營業日限額"（融資，2~7），
# "買進","賣出","現券償還","前日餘額","今日餘額","次一營業日限額"（融券，8~13），
# "資券互抵"（14），"註記"（15）。「次一營業日限額」與「註記」不存——前者是
# 主管機關給的額度上限而非交易結果，後者是文字備註，兩者都對走勢分析沒有意義。
_MI_MARGN_FIELD_MAP = {
    "融資買進(張)": 2, "融資賣出(張)": 3, "融資現金償還(張)": 4,
    "融資前日餘額(張)": 5, "融資餘額(張)": 6,
    "融券買進(張)": 8, "融券賣出(張)": 9, "融券現券償還(張)": 10,
    "融券前日餘額(張)": 11, "融券餘額(張)": 12,
    "資券互抵(張)": 14,
}


def _parse_margin_row(row: list):
    """解析 MI_MARGN table[1] 的單一個股 row，回傳融資融券欄位 dict；
    任一欄位解析失敗（欄位順序異常等）時整列視為不可信，回傳 None。"""
    try:
        return {field: int(row[index].replace(",", "").strip()) for field, index in _MI_MARGN_FIELD_MAP.items()}
    except (ValueError, IndexError, AttributeError):
        return None


def fetch_stock_institutional_data(target_stocks=["0050", "2330"], days=92, quote_lookup=None):
    """
    抓取指定個股近 N 天的三大法人買賣超張數、融資融券餘額與估算金額。

    每日行情（收盤價等）來自 quote_lookup（見 fetch_daily_quotes()，改用 STOCK_DAY
    單股單月端點，不再逐日呼叫全市場的 STOCK_DAY_ALL）；未提供時會現場呼叫
    fetch_daily_quotes() 補上。

    融資融券資料來自 MI_MARGN 端點，與 T86 併在同一個日迴圈裡一起抓（逐日、
    全市場快照，形狀與 T86 完全一致），不另外跑一輪獨立迴圈（見
    docs/README.md「資料來源」一節）。

    效率優化：若某天所有 target_stocks 都已有「T86 + 融資融券」的完整資料，
    則直接跳過、不重新發送任何請求——收盤價等行情的新鮮度改由 quote_lookup 與
    backfill_daily_quotes() 另外處理，不再綁在這裡的重抓邏輯裡，避免為了修補
    行情而白白重抓一次 T86 / MI_MARGN。
    """
    if quote_lookup is None:
        quote_lookup = fetch_daily_quotes(target_stocks, days)

    today = datetime.now()
    all_records = []

    # 預先讀取每檔股票既有的資料，用來判斷哪些日期已經抓過、可以跳過
    existing_data = {stock_id: load_stock_json(stock_id) for stock_id in target_stocks}

    # 已確認無交易資料的日期（國定假日等）——T86 是全市場快照，一旦某天確認
    # 無資料，對所有股票都成立，不需要每次執行都重新查詢同一批日期。
    # 注意：絕不快取「今天」，因為當天資料可能只是還沒公布，而非真的沒交易。
    no_trading_days = load_no_trading_days()
    newly_confirmed_no_trading = set()

    # 融資融券於本功能上線前抓過的舊記錄不會有「融資餘額(張)」欄位，藉此判斷
    # 「這天資料完不完整」——舊記錄會被視為不完整而重新抓取一次（連帶補齊融資
    # 融券欄位），行情欄位屆時也會被 quote_lookup 覆蓋為最新值，不會遺失資料。
    def is_date_complete(stock_id: str, date_key: str) -> bool:
        record = existing_data[stock_id].get(date_key)
        return record is not None and "融資餘額(張)" in record

    # 查無融資融券資料的股票（很可能是上櫃股票——MI_MARGN 只涵蓋上市，見
    # docs/README.md「已知限制」一節），彙整到最後統一提示一次，
    # 避免在近 60 個交易日的迴圈裡對同一檔股票重複印出同樣的警告。
    stocks_missing_margin = set()

    print(f"開始抓取個股 {target_stocks} 近 {days} 天的三大法人／融資融券數據...")
    print("-" * 60)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    skipped_count = 0
    for i in range(days):
        target_date = today - timedelta(days=i)

        # 排除週末 (5:週六, 6:週日)
        if target_date.weekday() >= 5:
            continue

        date_key = target_date.strftime("%Y-%m-%d")

        # 所有目標股票這天都已有完整資料，或已確認是無交易資料的日子 -> 直接跳過
        if date_key in no_trading_days or all(is_date_complete(stock_id, date_key) for stock_id in target_stocks):
            skipped_count += 1
            continue

        date_str = target_date.strftime("%Y%m%d")

        # 先抓當天所有個股的融資融券彙總 (MI_MARGN 端點)，供稍後與 T86 合併成同一筆記錄
        margn_url = f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={date_str}&selectType=ALL&response=json"
        margin_by_stock = {}
        try:
            res_margn = requests.get(margn_url, headers=headers, timeout=10).json()
            if res_margn.get("stat") == "OK":
                tables = res_margn.get("tables", [])
                stock_rows = tables[1].get("data", []) if len(tables) > 1 else []
                for row in stock_rows:
                    row_stock_id = row[0].strip()
                    if row_stock_id not in target_stocks:
                        continue
                    parsed = _parse_margin_row(row)
                    if parsed is not None:
                        margin_by_stock[row_stock_id] = parsed
                for stock_id in target_stocks:
                    if stock_id not in margin_by_stock:
                        stocks_missing_margin.add(stock_id)
            # stat != "OK" 通常代表當天非交易日，交由下方 T86 的判斷統一處理、
            # 這裡不重複印出「無交易資料」訊息
        except Exception as e:
            print(f"⚠️ 抓取 {date_str} 融資融券資料失敗: {e}", flush=True)

        # ⚠️ 請保留延遲，避免 API 被鎖（MI_MARGN 與 T86 是各自獨立的端點）
        time.sleep(3)

        # 抓取當天所有個股的三大法人買賣超 (T86 端點)
        t86_url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={date_str}&selectType=ALL&response=json"

        try:
            res_t86 = requests.get(t86_url, headers=headers, timeout=10).json()

            if res_t86.get("stat") == "OK":
                # 解析三大法人數據
                for row in res_t86["data"]:
                    stock_id = row[0].strip()
                    stock_name = row[1].strip()

                    # 篩選我們指定的股票
                    if stock_id in target_stocks:
                        # 取得當日行情（來自預先抓好的 quote_lookup；查無資料則各欄位預設 0）
                        quote = quote_lookup.get(stock_id, {}).get(date_key, {})
                        close_price = quote.get("收盤價", 0.0)

                        # 解析股數 (T86 欄位：4=外資, 7=投信, 10=自營商, 11=三大法人合計)
                        foreign_shares = int(row[4].replace(",", ""))
                        trust_shares = int(row[7].replace(",", ""))
                        dealer_shares = int(row[10].replace(",", ""))
                        total_shares = int(row[11].replace(",", ""))

                        # 轉換為張數 (股數 / 1000)
                        foreign_lots = foreign_shares // 1000
                        trust_lots = trust_shares // 1000
                        dealer_lots = dealer_shares // 1000
                        total_lots = total_shares // 1000

                        # 估算金額 (單位：萬元) = 張數 * 1000 * 收盤價 / 10000 = 張數 * 收盤價 / 10
                        total_amount_wan = round(total_lots * close_price / 10, 2)

                        record = {
                            "日期": target_date.strftime("%Y-%m-%d"),
                            "股票代號": stock_id,
                            "股票名稱": stock_name,
                            "開盤價": quote.get("開盤價", 0.0),
                            "最高價": quote.get("最高價", 0.0),
                            "最低價": quote.get("最低價", 0.0),
                            "收盤價": close_price,
                            "成交股數(股)": quote.get("成交股數(股)", 0),
                            "成交金額(元)": quote.get("成交金額(元)", 0),
                            "成交筆數(筆)": quote.get("成交筆數(筆)", 0),
                            "外資買賣超(張)": foreign_lots,
                            "投信買賣超(張)": trust_lots,
                            "自營商買賣超(張)": dealer_lots,
                            "合計買賣超(張)": total_lots,
                            "估算買賣超金額(萬元)": total_amount_wan,
                        }
                        # 只有實際抓到融資融券資料時才寫入這幾個欄位——刻意不補 0
                        # 佔位值，讓 is_date_complete() 能正確判斷「這天還缺融資
                        # 融券資料」，下次執行時才會自動重抓（而不是被當成已完成）。
                        if stock_id in margin_by_stock:
                            record.update(margin_by_stock[stock_id])

                        all_records.append(record)

                print(f"✅ 成功抓取: {target_date.strftime('%Y-%m-%d')}", flush=True)
            else:
                print(f"⏸️ 無交易資料: {date_str}", flush=True)
                # 只快取「今天以前」確認無資料的日期——今天的資料可能只是還沒公布，
                # 之後再查仍可能有結果，不能當成永久的非交易日。
                if target_date.date() < today.date():
                    newly_confirmed_no_trading.add(date_key)

        except Exception as e:
            print(f"❌ 抓取 {date_str} 失敗: {e}", flush=True)

        # ⚠️ 請保留延遲，避免 API 被鎖
        time.sleep(3)

    if skipped_count:
        print(f"⏭️ 略過 {skipped_count} 天（目標股票皆已有完整資料，未發送任何請求）")

    if newly_confirmed_no_trading:
        save_no_trading_days(no_trading_days | newly_confirmed_no_trading)
        print(f"🗓️ 已記錄 {len(newly_confirmed_no_trading)} 個新確認的無交易日，之後執行會自動跳過")

    if stocks_missing_margin:
        print(f"⚠️ 以下股票在抓取範圍內查無融資融券資料，可能為上櫃股票"
              f"（MI_MARGN 信用交易報表僅涵蓋上市）：{sorted(stocks_missing_margin)}")

    return pd.DataFrame(all_records)


def save_data_to_json(df: pd.DataFrame) -> list:
    """
    將抓取結果依股票代號分別存成獨立 JSON 檔：data/{股票代號}.json，結構為：
        { 日期: { 股票名稱, 開盤價/最高價/最低價/收盤價, 成交股數(股)/成交金額(元)/
        成交筆數(筆), 外資/投信/自營商/合計買賣超(張), 估算買賣超金額(萬元),
        融資/融券買進/賣出/償還/前日餘額/今日餘額(張), 資券互抵(張) } }
        （融資融券欄位只在當天實際抓到 MI_MARGN 資料時才會出現，見
        fetch_stock_institutional_data() 的 is_date_complete() 判斷邏輯）

    每個檔案都會先讀取既有內容再合併（相同日期以最新資料覆蓋），
    讓每次執行都能累積歷史資料，方便後續分析與製作圖表。

    回傳本次寫入的檔案路徑清單。
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    written_files = []

    # 融資融券欄位並非每筆記錄都有（見 fetch_stock_institutional_data() 的說明：
    # 當天查無 MI_MARGN 資料時刻意不補值）。但 all_records 一旦混合「有／無這些
    # 欄位」的字典，pd.DataFrame() 會依全體欄位聯集補 NaN、並把整欄位 upcast 成
    # float——這裡要把補進來的 NaN 濾掉、int 欄位轉回整數，才能還原「這天沒有
    # 融資融券資料」的原意，讓 is_date_complete() 在下次執行時能正確判斷。
    margin_fields = set(_MI_MARGN_FIELD_MAP.keys())

    for stock_id, group in df.groupby("股票代號"):
        stock_id = str(stock_id)
        path = stock_json_path(stock_id)
        stock_data = load_stock_json(stock_id)

        # 合併本次抓取結果（key: 日期）
        for record in group.to_dict(orient="records"):
            date_key = record["日期"]
            detail = {}
            for k, v in record.items():
                if k in ("股票代號", "日期") or pd.isna(v):
                    continue
                detail[k] = int(v) if k in margin_fields else v
            # 用 update() 併入既有記錄，而非整筆覆蓋：這次重抓若因故缺少某些
            # 欄位（例如 MI_MARGN 剛好逾時失敗，detail 就不會有融資融券欄位），
            # 既有記錄裡先前已抓到的欄位仍會保留，不會被這次的空缺蓋掉——確保
            # 「新增欄位只補新增的值」，不會意外遺失舊資料。
            stock_data.setdefault(date_key, {}).update(detail)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(stock_data, f, ensure_ascii=False, indent=2)

        written_files.append(path)

    return written_files


def fetch_and_save(target_stocks: list | None = None, months: int = MONTHS_RANGE):
    """
    完整抓取流程（供 main.py 呼叫）：
        1. 決定股票清單（未指定時取自 .env）與日期範圍（近 `months` 個月）
        2. 預先抓取每日行情（STOCK_DAY，單股單月，含開高低收與成交量值）
        3. 抓取三大法人與融資融券資料（T86 + MI_MARGN，逐日併在同一迴圈，
           已抓過的完整日期會自動跳過）
        4. 存成當次 CSV 快照 + 依股票代號分檔、可累積歷史的 JSON
        5. 用剛抓到的行情，修補既有資料中先前失敗留下的 0 元佔位值／舊格式缺欄位

    回傳 (df, json_paths)；未抓到任何新 T86 資料時 json_paths 為空list
    （但仍可能因步驟 5 而修補既有檔案）。
    """
    stocks = target_stocks or get_target_stocks()
    print(f"🎯 追蹤股票（來自 .env STOCK_CODES）：{stocks}")

    # 依日曆月精確計算「近 months 個月」對應的天數（而非固定天數），
    # 確保不論當月天數多寡，抓取範圍都是實際的近三個月。
    start_date = months_ago(months)
    days = (datetime.now() - start_date).days + 1  # +1 涵蓋起始日當天
    print(f"📅 資料範圍：近 {months} 個月（{start_date.strftime('%Y-%m-%d')} ~ {datetime.now().strftime('%Y-%m-%d')}）")

    print("\n💰 預先抓取每日行情（STOCK_DAY，單股單月）...")
    quote_lookup = fetch_daily_quotes(stocks, days)

    df = fetch_stock_institutional_data(target_stocks=stocks, days=days, quote_lookup=quote_lookup)

    json_paths = []
    if not df.empty:
        # 印出前 10 筆預覽
        print("\n📊 個股三大法人買賣超與融資融券數據表（前 10 筆）：")
        print(df.head(10).to_string(index=False))

        # 匯出 CSV 檔（存於本模組所在目錄，與呼叫時的工作目錄無關）
        filename = os.path.join(BASE_DIR, f"個股三大法人買賣超_{datetime.now().strftime('%Y%m%d')}.csv")
        df.to_csv(filename, index=False, encoding="utf-8-sig")
        print(f"\n📁 完整資料已存至：{filename}")

        # 依股票代號分別匯出/合併至 JSON 資料收集目錄，供後續分析與製圖使用
        json_paths = save_data_to_json(df)
        for path in json_paths:
            print(f"🗂️ 歷史資料已合併儲存至：{path}")
    else:
        print("未抓取到任何新的三大法人資料（T86 皆已存在）。")

    # 用這次抓到的行情，修補既有資料中先前失敗留下的 0 元佔位值／舊格式缺欄位
    # （即使上面沒有抓到任何新資料，仍可能有舊紀錄可以修補）
    patched = backfill_daily_quotes(stocks, quote_lookup)
    if patched:
        print(f"🩹 已用最新行情修補 {patched} 筆先前失敗（收盤價=0）或缺欄位的既有紀錄")

    return df, json_paths


if __name__ == "__main__":
    fetch_and_save()
