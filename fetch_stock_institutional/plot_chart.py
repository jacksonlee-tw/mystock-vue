"""
掃描 data/ 目錄下所有個股 JSON 檔（由 institutional_fetcher.py 產生，一檔股票一個檔案，
例如 data/2330.json），繪製「三大法人買賣超（張）」「K 線圖含成交量副圖與MA」「估算買賣超金額（萬元）」
「融資餘額（張）」「融券餘額（張）」「券資比（%）」圖表，輸出成單一可離線開啟的
HTML 檔案（無外部 CDN 依賴，SPA 儀表板架構：包含 Tier 1 全市場股票熱力圖總覽、股票快捷膠囊條、Tier 2 單股 6 Widget 儀表板與 Tier 3 點擊放大明細頁與 CSV 匯出）。

用法：
    python plot_chart.py
"""
import glob
import json
import os
import re
import sys
from datetime import datetime

# Windows terminal 編碼防護
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 沿用 institutional_fetcher 的資料設定，避免重複定義
from institutional_fetcher import DATA_DIR, MONTHS_RANGE, months_ago

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chart")
OUTPUT_HTML = os.path.join(OUTPUT_DIR, "institutional_chart.html")

# 個股 JSON 檔內容應為 { "YYYY-MM-DD": {...}, ... }，用來過濾掉非此格式的檔案
_DATE_KEY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def discover_stock_files(data_dir: str) -> list:
    """掃描 data_dir 下所有 *.json 檔，回傳 [(股票代號, 內容dict), ...]（依檔名排序）。"""
    results = []
    for path in sorted(glob.glob(os.path.join(data_dir, "*.json"))):
        stock_id = os.path.splitext(os.path.basename(path))[0]
        if stock_id.startswith("_"):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"⚠️ 略過無法讀取的檔案 ({path}): {e}")
            continue
        if not isinstance(raw, dict) or not all(_DATE_KEY_RE.match(k) for k in raw.keys()):
            print(f"⚠️ 略過非個股資料格式的檔案：{path}")
            continue
        results.append((stock_id, raw))
    return results


def load_all_stocks_data(data_dir: str, months: int = MONTHS_RANGE) -> dict:
    """掃描 data_dir 下所有個股 JSON 檔，整理成前端繪圖用的結構：
    { 股票代號: { name, dates[], open[], high[], low[], close[], volume[], foreign[], trust[],
    dealer[], total[], amount[], marginBalance[], shortBalance[] } }
    """
    cutoff = months_ago(months).strftime("%Y-%m-%d")

    chart_data = {}
    for stock_id, by_date in discover_stock_files(data_dir):
        dates = sorted(d for d in by_date.keys() if d >= cutoff)
        latest = by_date[dates[-1]] if dates else {}
        chart_data[stock_id] = {
            "name": latest.get("股票名稱", ""),
            "dates": dates,
            "open": [by_date[d].get("開盤價", 0) for d in dates],
            "high": [by_date[d].get("最高價", 0) for d in dates],
            "low": [by_date[d].get("最低價", 0) for d in dates],
            "close": [by_date[d].get("收盤價", 0) for d in dates],
            "volume": [round(by_date[d].get("成交股數(股)", 0) / 1000) for d in dates],  # 轉成「張」
            "foreign": [by_date[d].get("外資買賣超(張)", 0) for d in dates],
            "trust": [by_date[d].get("投信買賣超(張)", 0) for d in dates],
            "dealer": [by_date[d].get("自營商買賣超(張)", 0) for d in dates],
            "total": [by_date[d].get("合計買賣超(張)", 0) for d in dates],
            "amount": [by_date[d].get("估算買賣超金額(萬元)", 0) for d in dates],
            "marginBalance": [by_date[d].get("融資餘額(張)", 0) for d in dates],
            "shortBalance": [by_date[d].get("融券餘額(張)", 0) for d in dates],
        }
    return chart_data


def build_html(chart_data: dict) -> str:
    payload = {"order": list(chart_data.keys()), "stocks": chart_data}
    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    range_start = months_ago(MONTHS_RANGE).strftime("%Y-%m-%d")
    range_end = datetime.now().strftime("%Y-%m-%d")

    return f"""<!doctype html>
<html lang="zh-Hant" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>三大法人與籌碼全市場熱力儀表板</title>
<style>
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; min-height: 100vh; }}
  html {{ scroll-behavior: smooth; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "PingFang TC", "Microsoft JhengHei", sans-serif; }}

  /* Design Tokens - Financial Terminal Palette */
  :root[data-theme="dark"] {{
    --bg-page: #0b0e14;
    --bg-header: rgba(15, 21, 32, 0.90);
    --bg-surface: #131a27;
    --bg-card: #182232;
    --bg-card-hover: #1e2a3e;
    --bg-input: #101622;
    --text-primary: #f3f4f6;
    --text-secondary: #9ca3af;
    --text-muted: #6b7280;
    --border-color: rgba(255, 255, 255, 0.08);
    --border-glow: rgba(59, 130, 246, 0.35);
    --gridline: rgba(255, 255, 255, 0.05);
    --baseline: rgba(255, 255, 255, 0.18);
    --series-1: #3b82f6; /* 外資 */
    --series-2: #f97316; /* 投信 */
    --series-3: #10b981; /* 自營商 */
    --series-4: #eab308; /* 合計 */
    --ma5-color: #38bdf8;
    --ma20-color: #c084fc;
    --candle-up: #ef4444;   /* 台股紅漲 */
    --candle-down: #10b981; /* 台股綠跌 */
    --up-bg: rgba(239, 68, 68, 0.14);
    --down-bg: rgba(16, 185, 129, 0.14);
    --shadow-card: 0 4px 20px rgba(0, 0, 0, 0.35);
    --tooltip-bg: rgba(19, 26, 39, 0.95);
  }}

  :root[data-theme="light"] {{
    --bg-page: #f4f6fa;
    --bg-header: rgba(255, 255, 255, 0.92);
    --bg-surface: #ffffff;
    --bg-card: #ffffff;
    --bg-card-hover: #f8fafc;
    --bg-input: #f1f5f9;
    --text-primary: #0f172a;
    --text-secondary: #475569;
    --text-muted: #94a3b8;
    --border-color: rgba(0, 0, 0, 0.08);
    --border-glow: rgba(59, 130, 246, 0.25);
    --gridline: rgba(0, 0, 0, 0.05);
    --baseline: rgba(0, 0, 0, 0.25);
    --series-1: #2563eb;
    --series-2: #ea580c;
    --series-3: #059669;
    --series-4: #ca8a04;
    --ma5-color: #0284c7;
    --ma20-color: #9333ea;
    --candle-up: #dc2626;
    --candle-down: #059669;
    --up-bg: rgba(220, 38, 38, 0.08);
    --down-bg: rgba(5, 150, 105, 0.08);
    --shadow-card: 0 4px 16px rgba(0, 0, 0, 0.06);
    --tooltip-bg: rgba(255, 255, 255, 0.96);
  }}

  body {{
    background-color: var(--bg-page);
    color: var(--text-primary);
    transition: background-color 0.25s ease, color 0.25s ease;
    touch-action: manipulation;
  }}

  .dashboard-container {{
    max-width: 1360px;
    margin: 0 auto;
    padding: 0 16px 40px;
  }}

  /* Sticky Top Navigation Bar */
  .top-navbar {{
    position: sticky;
    top: 0;
    z-index: 100;
    background: var(--bg-header);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border-bottom: 1px solid var(--border-color);
    padding: 10px 16px;
    margin-bottom: 16px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.1);
  }}

  .top-navbar-inner {{
    max-width: 1360px;
    margin: 0 auto;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }}

  .brand-title {{
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 17px;
    font-weight: 700;
    color: var(--text-primary);
    margin: 0;
    white-space: nowrap;
    cursor: pointer;
  }}

  .brand-badge {{
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 12px;
    background: rgba(59, 130, 246, 0.15);
    color: var(--series-1);
    border: 1px solid var(--border-glow);
    font-weight: 600;
  }}

  /* Stock Chips Bar (Quick Switcher) */
  .stock-chips-container {{
    display: flex;
    align-items: center;
    gap: 6px;
    overflow-x: auto;
    padding: 2px 0;
    max-width: 600px;
    scrollbar-width: thin;
  }}

  .stock-chip {{
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
    background: var(--bg-input);
    border: 1px solid var(--border-color);
    border-radius: 20px;
    padding: 5px 12px;
    cursor: pointer;
    white-space: nowrap;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s ease;
    flex: none;
  }}
  .stock-chip:hover {{
    color: var(--text-primary);
    border-color: var(--border-glow);
    transform: translateY(-1px);
  }}
  .stock-chip.active {{
    background: var(--series-1);
    color: #ffffff;
    border-color: var(--series-1);
    box-shadow: 0 2px 8px rgba(59, 130, 246, 0.35);
  }}

  .chip-tag {{
    font-size: 10px;
    padding: 1px 4px;
    border-radius: 4px;
    font-weight: 700;
  }}
  .chip-tag-up {{ color: var(--candle-up); background: var(--up-bg); }}
  .chip-tag-down {{ color: var(--candle-down); background: var(--down-bg); }}

  .controls-group {{
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }}

  .pill-group {{
    display: inline-flex;
    background: var(--bg-input);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 2px;
  }}

  .pill-btn {{
    font: inherit;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-secondary);
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 5px 12px;
    cursor: pointer;
    min-height: 34px;
    transition: all 0.2s ease;
    white-space: nowrap;
  }}
  .pill-btn:hover {{ color: var(--text-primary); }}
  .pill-btn[aria-pressed="true"], .pill-btn.active {{
    background: var(--bg-card);
    color: var(--series-1);
    box-shadow: 0 1px 4px rgba(0,0,0,0.15);
  }}

  .theme-btn {{
    background: var(--bg-input);
    border: 1px solid var(--border-color);
    color: var(--text-primary);
    border-radius: 8px;
    width: 36px;
    height: 36px;
    font-size: 16px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
  }}

  /* Metadata Banner */
  .meta-banner {{
    font-size: 12px;
    color: var(--text-muted);
    margin-bottom: 16px;
    padding: 8px 14px;
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: 10px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
  }}

  /* Tier 1: Heatmap Grid Styles */
  .heatmap-section-title {{
    font-size: 18px;
    font-weight: 700;
    color: var(--text-primary);
    margin: 0 0 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}

  .heatmap-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
  }}

  .heatmap-card {{
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 14px;
    padding: 16px;
    box-shadow: var(--shadow-card);
    cursor: pointer;
    transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    position: relative;
    overflow: hidden;
  }}
  .heatmap-card:hover {{
    transform: translateY(-4px);
    border-color: var(--border-glow);
    box-shadow: 0 10px 28px rgba(0,0,0,0.3);
  }}

  .heatmap-card-header {{
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 8px;
  }}

  .heatmap-stock-name {{ font-size: 16px; font-weight: 700; color: var(--text-primary); }}
  .heatmap-stock-code {{ font-size: 12px; color: var(--text-muted); font-weight: 500; }}

  .heatmap-price-wrap {{
    text-align: right;
  }}

  .heatmap-price {{ font-size: 20px; font-weight: 800; font-variant-numeric: tabular-nums; }}
  .heatmap-change {{ font-size: 12px; font-weight: 700; margin-top: 2px; }}

  .heatmap-sparkline-wrap {{
    width: 100%;
    height: 60px;
    margin: 10px 0;
  }}

  .heatmap-card-footer {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 12px;
    color: var(--text-secondary);
    border-top: 1px solid var(--border-color);
    padding-top: 8px;
  }}

  /* Tier 2: Single Stock KPI & Widget Grid Styles */
  .kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 12px;
    margin-bottom: 18px;
  }}

  .kpi-card {{
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 12px 14px;
    box-shadow: var(--shadow-card);
  }}
  .kpi-title {{ font-size: 12px; font-weight: 500; color: var(--text-muted); margin-bottom: 3px; }}
  .kpi-value {{ font-size: 17px; font-weight: 700; color: var(--text-primary); font-variant-numeric: tabular-nums; }}
  .kpi-sub {{ font-size: 11px; margin-top: 3px; font-weight: 600; display: flex; align-items: center; gap: 4px; }}
  .badge-up {{ color: var(--candle-up); background: var(--up-bg); padding: 2px 6px; border-radius: 4px; }}
  .badge-down {{ color: var(--candle-down); background: var(--down-bg); padding: 2px 6px; border-radius: 4px; }}

  .widget-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
  }}

  .widget-card {{
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 14px;
    padding: 14px 16px 12px;
    box-shadow: var(--shadow-card);
    cursor: pointer;
    transition: transform 0.2s ease, border-color 0.2s ease;
    display: flex;
    flex-direction: column;
    position: relative;
    overflow: hidden;
  }}
  .widget-card:hover {{
    transform: translateY(-3px);
    border-color: var(--border-glow);
    box-shadow: 0 8px 24px rgba(59, 130, 246, 0.15);
  }}

  .widget-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
  }}

  .widget-title {{ font-size: 14px; font-weight: 700; color: var(--text-primary); margin: 0; }}
  .widget-action-btn {{
    font-size: 12px; font-weight: 600; color: var(--series-1);
    background: rgba(59, 130, 246, 0.1); border: 1px solid var(--border-glow);
    border-radius: 6px; padding: 3px 8px; display: flex; align-items: center; gap: 4px;
  }}

  .widget-svg-wrap {{ width: 100%; height: 150px; position: relative; }}

  /* Tier 3: Detail View Layout */
  .detail-nav-bar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 16px;
    flex-wrap: wrap;
  }}

  .back-btn {{
    font: inherit; font-size: 13px; font-weight: 700;
    color: var(--text-primary); background: var(--bg-card);
    border: 1px solid var(--border-glow); border-radius: 8px;
    padding: 7px 14px; cursor: pointer; display: inline-flex; align-items: center; gap: 6px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15); transition: all 0.2s ease;
  }}
  .back-btn:hover {{ background: var(--series-1); color: #ffffff; }}

  .chart-card {{
    background: var(--bg-card); border: 1px solid var(--border-color);
    border-radius: 14px; padding: 20px 22px 16px; box-shadow: var(--shadow-card); position: relative;
  }}

  .chart-card-header {{ display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px 16px; margin-bottom: 14px; }}
  .chart-title {{ font-size: 16px; font-weight: 700; color: var(--text-primary); margin: 0; }}
  .legend {{ display: flex; gap: 12px; flex-wrap: wrap; font-size: 12px; color: var(--text-secondary); }}
  .legend-item {{ display: flex; align-items: center; gap: 6px; }}
  .legend-swatch {{ width: 12px; height: 3px; border-radius: 2px; display: inline-block; }}

  /* SVG & Tooltip */
  .chart-svg-wrap {{ position: relative; width: 100%; }}
  svg.chart-svg {{ width: 100%; height: auto; display: block; overflow: visible; }}

  .axis-label {{ fill: var(--text-muted); font-size: 11px; font-weight: 500; }}
  .gridline {{ stroke: var(--gridline); stroke-width: 1; }}
  .baseline {{ stroke: var(--baseline); stroke-width: 1.5; stroke-dasharray: 4 4; }}
  .crosshair {{ stroke: var(--text-muted); stroke-width: 1; stroke-dasharray: 3 3; opacity: 0; pointer-events: none; }}
  .hit-rect {{ fill: transparent; cursor: crosshair; touch-action: pan-y; }}

  .tooltip {{
    position: absolute; pointer-events: none; background: var(--tooltip-bg);
    backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
    border: 1px solid var(--border-glow); border-radius: 10px; padding: 10px 14px;
    font-size: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.3); opacity: 0;
    transform: translate(-50%, -115%); transition: opacity 0.1s ease, transform 0.1s ease;
    white-space: nowrap; z-index: 50; left: 0; top: 0;
  }}
  .tooltip-date {{ color: var(--text-primary); font-weight: 700; font-size: 13px; margin-bottom: 2px; }}
  .tooltip-sub {{ color: var(--text-muted); font-size: 11px; margin-bottom: 6px; }}
  .tooltip-row {{ display: flex; align-items: center; gap: 8px; margin-top: 3px; }}
  .tooltip-key {{ width: 10px; height: 3px; display: inline-block; border-radius: 2px; flex: none; }}
  .tooltip-name {{ color: var(--text-secondary); }}
  .tooltip-value {{ color: var(--text-primary); font-weight: 700; font-variant-numeric: tabular-nums; margin-left: auto; padding-left: 14px; }}

  .table-actions {{ display: flex; align-items: center; justify-content: space-between; margin-top: 16px; gap: 8px; }}
  .btn-sm {{
    font: inherit; font-size: 12px; font-weight: 600; color: var(--text-secondary);
    background: var(--bg-input); border: 1px solid var(--border-color);
    border-radius: 6px; padding: 6px 14px; cursor: pointer; transition: all 0.2s ease;
  }}
  .btn-sm:hover {{ color: var(--text-primary); border-color: var(--border-glow); }}

  .table-responsive-wrap {{ overflow-x: auto; margin-top: 10px; border-radius: 8px; border: 1px solid var(--border-color); max-height: 400px; }}
  .data-table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  .data-table th, .data-table td {{ padding: 8px 12px; border-bottom: 1px solid var(--gridline); text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }}
  .data-table th:first-child, .data-table td:first-child {{ text-align: left; }}
  .data-table thead th {{ position: sticky; top: 0; background: var(--bg-surface); color: var(--text-muted); font-weight: 700; border-bottom: 1px solid var(--border-color); z-index: 2; }}
  .data-table tbody tr:hover {{ background: var(--bg-card-hover); }}
  .num-positive {{ color: var(--candle-up); font-weight: 600; }}
  .num-negative {{ color: var(--candle-down); font-weight: 600; }}

  /* RWD Media Queries */
  @media (max-width: 1024px) {{
    .widget-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .stock-chips-container {{ max-width: 400px; }}
  }}

  @media (max-width: 640px) {{
    .top-navbar-inner {{ flex-direction: column; align-items: stretch; gap: 10px; }}
    .controls-group {{ justify-content: space-between; width: 100%; }}
    .stock-chips-container {{ max-width: 100%; }}
    .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .widget-grid {{ grid-template-columns: 1fr; }}
    .detail-nav-bar {{ flex-direction: column; align-items: stretch; }}
    .chart-card {{ padding: 14px 12px 10px; }}
  }}
</style>
</head>
<body>

<header class="top-navbar">
  <div class="top-navbar-inner">
    <h1 class="brand-title" id="brand-home-btn" title="返回全市場熱力圖總覽">
      三大法人與籌碼儀表板
      <span class="brand-badge">PRO</span>
    </h1>

    <!-- Stock Chips Quick Switcher Bar -->
    <div id="stock-chips-bar" class="stock-chips-container"></div>

    <div class="controls-group">
      <div class="pill-group" role="group" aria-label="週期切換">
        <button class="pill-btn" type="button" data-tf="day" aria-pressed="true">日線</button>
        <button class="pill-btn" type="button" data-tf="week" aria-pressed="false">週線</button>
        <button class="pill-btn" type="button" data-tf="month" aria-pressed="false">月線</button>
      </div>

      <button id="theme-toggle" class="theme-btn" type="button" aria-label="切換主題" title="切換深色/淺色主題">🌙</button>
    </div>
  </div>
</header>

<div class="dashboard-container">
  <div class="meta-banner">
    <div>
      <strong>資料範圍：</strong>近 {MONTHS_RANGE} 個月（{range_start} ~ {range_end}） ・ <strong>產生時間：</strong>{generated_at}
    </div>
    <div id="meta-hint">
      點擊股票卡片可進入個股分析儀表板
    </div>
  </div>

  <!-- TIER 1: 全市場股票熱力圖總覽 (#heatmap) -->
  <div id="heatmap-view">
    <div class="heatmap-section-title">
      <span>🔥 全市場個股動態熱力圖</span>
      <span style="font-size: 13px; font-weight: 500; color: var(--text-muted)">點擊卡片深入檢視個股</span>
    </div>
    <main id="heatmap-grid" class="heatmap-grid"></main>
  </div>

  <!-- TIER 2: 單股 6 WIDGET 儀表板 (#stock/:id) -->
  <div id="stock-overview-view" hidden>
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px;">
      <button id="back-to-heatmap-btn" class="back-btn" type="button">
        🏠 全市場熱力圖
      </button>
      <span id="stock-overview-title" style="font-size: 16px; font-weight: 700; color: var(--text-primary);"></span>
    </div>

    <!-- KPI Summary Cards -->
    <section id="kpi-summary-container" class="kpi-grid"></section>

    <!-- 6 Widget Grid -->
    <main id="widget-grid" class="widget-grid"></main>
  </div>

  <!-- TIER 3: 圖表明細放大頁 (#stock/:id/detail/:chartId) -->
  <div id="detail-view" hidden>
    <div class="detail-nav-bar">
      <div style="display: flex; gap: 8px;">
        <button id="back-to-heatmap-from-detail" class="back-btn" type="button" title="回到市場熱力圖">
          🏠 熱力圖
        </button>
        <button id="back-to-stock-btn" class="back-btn" type="button">
          ← 返回個股儀表板
        </button>
      </div>

      <div class="pill-group detail-tabs" role="tablist" aria-label="圖表明細切換">
        <button class="pill-btn detail-tab-btn" type="button" data-chart="flow">三大法人</button>
        <button class="pill-btn detail-tab-btn" type="button" data-chart="kline">K 線成交量</button>
        <button class="pill-btn detail-tab-btn" type="button" data-chart="amount">估算金額</button>
        <button class="pill-btn detail-tab-btn" type="button" data-chart="margin">融資餘額</button>
        <button class="pill-btn detail-tab-btn" type="button" data-chart="short">融券餘額</button>
        <button class="pill-btn detail-tab-btn" type="button" data-chart="ratio">券資比</button>
      </div>
    </div>

    <main id="detail-chart-container"></main>
  </div>
</div>

<script id="chart-data" type="application/json">{data_json}</script>
<script>
(function () {{
  "use strict";
  var PAYLOAD = JSON.parse(document.getElementById("chart-data").textContent);
  var DATA = PAYLOAD.stocks;
  var STOCK_ORDER = PAYLOAD.order;
  var svgNS = "http://www.w3.org/2000/svg";

  // Theme Manager
  var themeBtn = document.getElementById("theme-toggle");
  function setTheme(t) {{
    document.documentElement.setAttribute("data-theme", t);
    themeBtn.textContent = t === "dark" ? "🌙" : "☀️";
    try {{ localStorage.setItem("dashboard_theme", t); }} catch (e) {{}}
  }}
  var savedTheme = null;
  try {{ savedTheme = localStorage.getItem("dashboard_theme"); }} catch (e) {{}}
  if (!savedTheme) {{
    savedTheme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }}
  setTheme(savedTheme);
  themeBtn.addEventListener("click", function () {{
    var current = document.documentElement.getAttribute("data-theme");
    setTheme(current === "dark" ? "light" : "dark");
  }});

  // Number Formatters
  function formatSigned(v) {{
    if (!isValidNum(v)) return "—";
    var n = Math.round(v);
    return (n > 0 ? "+" : "") + n.toLocaleString("en-US");
  }}
  function formatPlain(v) {{
    if (!isValidNum(v)) return "—";
    return Math.round(v).toLocaleString("en-US");
  }}
  function formatPrice(v) {{
    if (!isValidNum(v)) return "—";
    return Number(v).toLocaleString("en-US", {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }});
  }}
  function formatPercent(v) {{
    if (!isValidNum(v)) return "—";
    return v.toLocaleString("en-US", {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }}) + "%";
  }}

  var TIMEFRAMES = {{
    day:   {{ unit: "日", dateHeader: "日期",  maxXLabels: 8 }},
    week:  {{ unit: "週", dateHeader: "週別",  maxXLabels: 10 }},
    month: {{ unit: "月", dateHeader: "月份",  maxXLabels: 12 }}
  }};
  var SUM_FIELDS = ["foreign", "trust", "dealer", "total", "amount", "volume"];
  var END_FIELDS = ["close", "marginBalance", "shortBalance"];
  var START_FIELDS = ["open"];
  var MAX_FIELDS = ["high"];
  var MIN_FIELDS = ["low"];

  function num(v) {{ return typeof v === "number" && isFinite(v) ? v : 0; }}
  function isValidNum(v) {{ return typeof v === "number" && isFinite(v); }}

  function periodKey(dateStr, tf) {{
    if (tf === "month") return dateStr.slice(0, 7);
    if (tf !== "week") return dateStr;
    var p = dateStr.split("-");
    var d = new Date(Date.UTC(+p[0], +p[1] - 1, +p[2]));
    var dow = d.getUTCDay();
    d.setUTCDate(d.getUTCDate() - (dow === 0 ? 6 : dow - 1));
    return d.toISOString().slice(0, 10);
  }}

  function mmdd(dateStr) {{ return dateStr.slice(5).replace("-", "/"); }}

  function aggregateStock(stock, tf) {{
    var dates = stock.dates;
    var agg = {{ keys: [], axisLabels: [], pointLabels: [], subLabels: [], days: [], first: [], last: [] }};
    SUM_FIELDS.forEach(function (f) {{ agg[f] = []; }});
    END_FIELDS.forEach(function (f) {{ agg[f] = []; }});
    START_FIELDS.forEach(function (f) {{ agg[f] = []; }});
    MAX_FIELDS.forEach(function (f) {{ agg[f] = []; }});
    MIN_FIELDS.forEach(function (f) {{ agg[f] = []; }});

    var lastKey = null;
    for (var i = 0; i < dates.length; i++) {{
      var key = periodKey(dates[i], tf);
      if (key !== lastKey) {{
        lastKey = key;
        agg.keys.push(key);
        agg.days.push(0);
        agg.first.push(dates[i]);
        agg.last.push(dates[i]);
        SUM_FIELDS.forEach(function (f) {{ agg[f].push(0); }});
        END_FIELDS.forEach(function (f) {{ agg[f].push(num(stock[f][i])); }});
        START_FIELDS.forEach(function (f) {{ agg[f].push(num(stock[f][i])); }});
        MAX_FIELDS.forEach(function (f) {{ agg[f].push(num(stock[f][i])); }});
        MIN_FIELDS.forEach(function (f) {{ var v = num(stock[f][i]); agg[f].push(v > 0 ? v : Infinity); }});
      }}
      var j = agg.keys.length - 1;
      SUM_FIELDS.forEach(function (f) {{ agg[f][j] += num(stock[f][i]); }});
      END_FIELDS.forEach(function (f) {{ if (num(stock[f][i])) agg[f][j] = num(stock[f][i]); }});
      START_FIELDS.forEach(function (f) {{ if (!agg[f][j] && num(stock[f][i])) agg[f][j] = num(stock[f][i]); }});
      MAX_FIELDS.forEach(function (f) {{ agg[f][j] = Math.max(agg[f][j], num(stock[f][i])); }});
      MIN_FIELDS.forEach(function (f) {{ var v = num(stock[f][i]); if (v > 0) agg[f][j] = Math.min(agg[f][j], v); }});
      agg.last[j] = dates[i];
      agg.days[j] += 1;
    }}

    MIN_FIELDS.forEach(function (f) {{
      for (var k = 0; k < agg[f].length; k++) {{ if (!isFinite(agg[f][k])) agg[f][k] = 0; }}
    }});

    agg.shortToMarginRatio = agg.marginBalance.map(function (m, idx) {{
      return m > 0 ? (agg.shortBalance[idx] / m * 100) : null;
    }});

    // MA5 / MA20
    agg.ma5 = [];
    agg.ma20 = [];
    for (var m = 0; m < agg.close.length; m++) {{
      if (m >= 4) {{
        var sum5 = 0; for (var a = m - 4; a <= m; a++) sum5 += agg.close[a];
        agg.ma5.push(sum5 / 5);
      }} else {{ agg.ma5.push(null); }}
      if (m >= 19) {{
        var sum20 = 0; for (var b = m - 19; b <= m; b++) sum20 += agg.close[b];
        agg.ma20.push(sum20 / 20);
      }} else {{ agg.ma20.push(null); }}
    }}

    for (var k = 0; k < agg.keys.length; k++) {{
      if (tf === "day") {{
        agg.axisLabels.push(mmdd(agg.keys[k]));
        agg.pointLabels.push(agg.keys[k]);
        agg.subLabels.push(null);
      }} else if (tf === "week") {{
        agg.axisLabels.push(mmdd(agg.first[k]));
        agg.pointLabels.push(mmdd(agg.first[k]) + " ~ " + mmdd(agg.last[k]));
        agg.subLabels.push(agg.first[k].slice(0, 4) + " 年・" + agg.days[k] + " 個交易日");
      }} else {{
        agg.axisLabels.push(agg.keys[k]);
        agg.pointLabels.push(agg.keys[k]);
        agg.subLabels.push(mmdd(agg.first[k]) + " ~ " + mmdd(agg.last[k]) + "・" + agg.days[k] + " 個交易日");
      }}
    }}
    return agg;
  }}

  // Nice scale generator
  function niceNum(range, round) {{
    if (range === 0) return 1;
    var exponent = Math.floor(Math.log10(range));
    var fraction = range / Math.pow(10, exponent);
    var niceFraction;
    if (round) {{
      if (fraction < 1.5) niceFraction = 1;
      else if (fraction < 3) niceFraction = 2;
      else if (fraction < 7) niceFraction = 5;
      else niceFraction = 10;
    }} else {{
      if (fraction <= 1) niceFraction = 1;
      else if (fraction <= 2) niceFraction = 2;
      else if (fraction <= 5) niceFraction = 5;
      else niceFraction = 10;
    }}
    return niceFraction * Math.pow(10, exponent);
  }}
  function niceScale(dataMin, dataMax, maxTicks) {{
    var min = dataMin, max = dataMax;
    if (min === max) {{ min -= 1; max += 1; }}
    var range = niceNum(max - min, false);
    var step = niceNum(range / (maxTicks - 1), true);
    var niceMin = Math.floor(min / step) * step;
    var niceMax = Math.ceil(max / step) * step;
    var ticks = [];
    for (var v = niceMin; v <= niceMax + step / 1000; v += step) ticks.push(Math.round(v * 1000) / 1000);
    return {{ min: niceMin, max: niceMax, step: step, ticks: ticks }};
  }}

  function el(tag, attrs) {{
    var e = document.createElementNS(svgNS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }}

  // ---------- KPI Summary Header Stats ----------
  function renderKPIStats(stockId, stock, agg) {{
    var kpiWrap = document.getElementById("kpi-summary-container");
    while (kpiWrap.firstChild) kpiWrap.removeChild(kpiWrap.firstChild);
    if (!agg || agg.keys.length === 0) return;

    var idx = agg.keys.length - 1;
    var prevIdx = idx > 0 ? idx - 1 : idx;

    var latestClose = agg.close[idx];
    var prevClose = agg.close[prevIdx];
    var diff = latestClose - prevClose;
    var pct = prevClose ? (diff / prevClose * 100) : 0;

    var cards = [
      {{
        title: stockId + " " + stock.name,
        val: formatPrice(latestClose),
        sub: idx > 0 ? (
          '<span class="' + (diff >= 0 ? "badge-up" : "badge-down") + '">' +
          (diff >= 0 ? "▲ +" : "▼ ") + diff.toFixed(2) + " (" + (diff >= 0 ? "+" : "") + pct.toFixed(2) + "%)</span>"
        ) : '<span style="color:var(--text-muted)">最新收盤價</span>'
      }},
      {{
        title: "外資買賣超",
        val: formatSigned(agg.foreign[idx]) + " 張",
        sub: '<span style="color:var(--text-muted)">期末累積/流量</span>'
      }},
      {{
        title: "投信買賣超",
        val: formatSigned(agg.trust[idx]) + " 張",
        sub: '<span style="color:var(--text-muted)">期末累積/流量</span>'
      }},
      {{
        title: "自營商買賣超",
        val: formatSigned(agg.dealer[idx]) + " 張",
        sub: '<span style="color:var(--text-muted)">期末累積/流量</span>'
      }},
      {{
        title: "三大法人合計",
        val: formatSigned(agg.total[idx]) + " 張",
        sub: '<span style="color:var(--text-muted)">合計買賣超</span>'
      }},
      {{
        title: "融資餘額 / 券資比",
        val: formatPlain(agg.marginBalance[idx]) + " 張",
        sub: '<span style="color:var(--text-muted)">券資比 ' + formatPercent(agg.shortToMarginRatio[idx]) + '</span>'
      }}
    ];

    cards.forEach(function (c) {{
      var card = document.createElement("div");
      card.className = "kpi-card";
      card.innerHTML = '<div class="kpi-title">' + c.title + '</div>' +
                       '<div class="kpi-value">' + c.val + '</div>' +
                       '<div class="kpi-sub">' + c.sub + '</div>';
      kpiWrap.appendChild(card);
    }});
  }}

  // ---------- Mini Sparkline Renderers ----------
  function renderMiniSparkline(container, chartType, agg, customHeight) {{
    var width = 360, height = customHeight || 150;
    var margin = {{ top: 8, right: 8, bottom: 16, left: 32 }};
    var plotW = width - margin.left - margin.right;
    var plotH = height - margin.top - margin.bottom;
    var n = agg.axisLabels.length;
    if (n === 0) return;

    function xAt(i) {{ return n <= 1 ? margin.left + plotW / 2 : margin.left + (i / (n - 1)) * plotW; }}

    var svg = el("svg", {{ "class": "chart-svg", viewBox: "0 0 " + width + " " + height }});

    if (chartType === "flow") {{
      var allVals = [0];
      for (var v = 0; v < n; v++) allVals.push(agg.foreign[v], agg.trust[v], agg.dealer[v], agg.total[v]);
      var scale = niceScale(Math.min.apply(null, allVals), Math.max.apply(null, allVals), 4);
      function yAt(val) {{ return margin.top + plotH - ((val - scale.min) / (scale.max - scale.min)) * plotH; }}

      scale.ticks.forEach(function (t) {{
        var y = yAt(t);
        svg.appendChild(el("line", {{ "class": t === 0 ? "baseline" : "gridline", x1: margin.left, x2: width - margin.right, y1: y, y2: y }}));
      }});

      var slot = n > 1 ? plotW / (n - 1) : plotW;
      var barW = Math.max(1, Math.min(slot * 0.25, 4));
      var yZero = yAt(0);

      for (var bi = 0; bi < n; bi++) {{
        var cx = xAt(bi);
        if (agg.foreign[bi] !== 0) {{
          var fY = yAt(Math.max(0, agg.foreign[bi]));
          var fH = Math.max(1, Math.abs(yAt(agg.foreign[bi]) - yZero));
          svg.appendChild(el("rect", {{ x: cx - barW * 1.5, y: fY, width: barW, height: fH, fill: "var(--series-1)" }}));
        }}
        if (agg.trust[bi] !== 0) {{
          var tY = yAt(Math.max(0, agg.trust[bi]));
          var tH = Math.max(1, Math.abs(yAt(agg.trust[bi]) - yZero));
          svg.appendChild(el("rect", {{ x: cx - barW * 0.5, y: tY, width: barW, height: tH, fill: "var(--series-2)" }}));
        }}
        if (agg.dealer[bi] !== 0) {{
          var dY = yAt(Math.max(0, agg.dealer[bi]));
          var dH = Math.max(1, Math.abs(yAt(agg.dealer[bi]) - yZero));
          svg.appendChild(el("rect", {{ x: cx + barW * 0.5, y: dY, width: barW, height: dH, fill: "var(--series-3)" }}));
        }}
      }}
      var dPath = "";
      agg.total.forEach(function (tv, idx) {{ dPath += (idx === 0 ? "M" : "L") + xAt(idx).toFixed(2) + " " + yAt(tv).toFixed(2) + " "; }});
      svg.appendChild(el("path", {{ d: dPath, fill: "none", stroke: "var(--series-4)", "stroke-width": 2 }}));

    }} else if (chartType === "kline" || chartType === "price_line") {{
      var pVals = [];
      for (var ki = 0; ki < n; ki++) {{ if (agg.high[ki] > 0) pVals.push(agg.high[ki], agg.low[ki]); }}
      if (pVals.length === 0) pVals.push(0, 1);
      var scaleK = niceScale(Math.min.apply(null, pVals), Math.max.apply(null, pVals), 4);
      function yK(val) {{ return margin.top + plotH - ((val - scaleK.min) / (scaleK.max - scaleK.min)) * plotH; }}

      if (chartType === "price_line") {{
        var dP = "";
        agg.close.forEach(function (cv, idx) {{
          if (isValidNum(cv) && cv > 0) dP += (dP === "" ? "M" : "L") + xAt(idx).toFixed(2) + " " + yK(cv).toFixed(2) + " ";
        }});
        svg.appendChild(el("path", {{ d: dP, fill: "none", stroke: "var(--series-1)", "stroke-width": 2.2 }}));
      }} else {{
        scaleK.ticks.forEach(function (t) {{
          var y = yK(t);
          svg.appendChild(el("line", {{ "class": "gridline", x1: margin.left, x2: width - margin.right, y1: y, y2: y }}));
        }});

        var candleW = Math.max(1, Math.min((plotW / (n > 1 ? n - 1 : 1)) * 0.6, 6));
        for (var ci = 0; ci < n; ci++) {{
          if (!(agg.high[ci] > 0)) continue;
          var cxK = xAt(ci);
          var isUp = agg.close[ci] >= agg.open[ci];
          var cColor = isUp ? "--candle-up" : "--candle-down";
          svg.appendChild(el("line", {{ x1: cxK, x2: cxK, y1: yK(agg.high[ci]), y2: yK(agg.low[ci]), stroke: "var(" + cColor + ")" }}));
          var bodyTop = yK(Math.max(agg.open[ci], agg.close[ci]));
          var bodyH = Math.max(1, yK(Math.min(agg.open[ci], agg.close[ci])) - bodyTop);
          svg.appendChild(el("rect", {{ x: cxK - candleW / 2, y: bodyTop, width: candleW, height: bodyH, fill: "var(" + cColor + ")" }}));
        }}
      }}

    }} else {{
      var seriesData = [];
      if (chartType === "amount") seriesData = agg.amount;
      else if (chartType === "margin") seriesData = agg.marginBalance;
      else if (chartType === "short") seriesData = agg.shortBalance;
      else if (chartType === "ratio") seriesData = agg.shortToMarginRatio;

      var validVals = [];
      seriesData.forEach(function (v) {{ if (isValidNum(v)) validVals.push(v); }});
      if (chartType === "amount" || chartType === "ratio") validVals.push(0);
      if (validVals.length === 0) validVals.push(0, 1);

      var scaleL = niceScale(Math.min.apply(null, validVals), Math.max.apply(null, validVals), 4);
      function yL(val) {{ return margin.top + plotH - ((val - scaleL.min) / (scaleL.max - scaleL.min)) * plotH; }}

      scaleL.ticks.forEach(function (t) {{
        var y = yL(t);
        svg.appendChild(el("line", {{ "class": (t === 0 && (chartType === "amount" || chartType === "ratio")) ? "baseline" : "gridline", x1: margin.left, x2: width - margin.right, y1: y, y2: y }}));
      }});

      var lineD = "", areaD = "";
      var drawing = false, lastX = 0;
      var zeroY = yL(chartType === "amount" || chartType === "ratio" ? 0 : scaleL.min);

      seriesData.forEach(function (v, idx) {{
        if (!isValidNum(v)) {{ drawing = false; return; }}
        var x = xAt(idx), y = yL(v);
        if (!drawing) {{
          lineD += "M" + x.toFixed(2) + " " + y.toFixed(2) + " ";
          areaD += "M" + x.toFixed(2) + " " + zeroY.toFixed(2) + " L" + x.toFixed(2) + " " + y.toFixed(2) + " ";
          drawing = true;
        }} else {{
          lineD += "L" + x.toFixed(2) + " " + y.toFixed(2) + " ";
          areaD += "L" + x.toFixed(2) + " " + y.toFixed(2) + " ";
        }}
        lastX = x;
      }});

      if (drawing) {{
        areaD += "L" + lastX.toFixed(2) + " " + zeroY.toFixed(2) + " Z";
        svg.appendChild(el("path", {{ d: areaD, fill: "rgba(59, 130, 246, 0.15)" }}));
        svg.appendChild(el("path", {{ d: lineD, fill: "none", stroke: "var(--series-1)", "stroke-width": 2 }}));
      }}
    }}

    container.appendChild(svg);
  }}

  // ---------- Full Detail Chart Renderers ----------
  function renderInstitutionalChart(container, opts) {{
    var width = 880, height = opts.height || 340;
    var margin = {{ top: 20, right: 24, bottom: 30, left: 68 }};
    var plotW = width - margin.left - margin.right;
    var plotH = height - margin.top - margin.bottom;

    var axisLabels = opts.axisLabels;
    var n = axisLabels.length;
    if (n === 0) return;

    var foreign = opts.foreign, trust = opts.trust, dealer = opts.dealer, total = opts.total;
    var allVals = [0];
    for (var v = 0; v < n; v++) allVals.push(foreign[v], trust[v], dealer[v], total[v]);
    var scale = niceScale(Math.min.apply(null, allVals), Math.max.apply(null, allVals), 5);

    function xAt(i) {{ return n <= 1 ? margin.left + plotW / 2 : margin.left + (i / (n - 1)) * plotW; }}
    function yAt(v) {{ return margin.top + plotH - ((v - scale.min) / (scale.max - scale.min)) * plotH; }}

    var svg = el("svg", {{ "class": "chart-svg", viewBox: "0 0 " + width + " " + height }});

    scale.ticks.forEach(function (t) {{
      var y = yAt(t);
      svg.appendChild(el("line", {{ "class": t === 0 ? "baseline" : "gridline", x1: margin.left, x2: width - margin.right, y1: y, y2: y }}));
      var label = el("text", {{ "class": "axis-label", x: margin.left - 8, y: y + 4, "text-anchor": "end" }});
      label.textContent = formatSigned(t);
      svg.appendChild(label);
    }});

    var maxXLabels = opts.maxXLabels || 8;
    var xStep = Math.max(1, Math.ceil(n / maxXLabels));
    for (var i = 0; i < n; i += xStep) {{
      var lbl = el("text", {{ "class": "axis-label", x: xAt(i), y: height - margin.bottom + 18, "text-anchor": "middle" }});
      lbl.textContent = axisLabels[i];
      svg.appendChild(lbl);
    }}

    var slot = n > 1 ? plotW / (n - 1) : plotW;
    var barW = Math.max(1, Math.min(slot * 0.22, 8));
    var yZero = yAt(0);

    for (var bi = 0; bi < n; bi++) {{
      var cx = xAt(bi);
      if (foreign[bi] !== 0) {{
        var fY = yAt(Math.max(0, foreign[bi]));
        var fH = Math.max(1, Math.abs(yAt(foreign[bi]) - yZero));
        svg.appendChild(el("rect", {{ x: cx - barW * 1.5, y: fY, width: barW, height: fH, fill: "var(--series-1)", rx: 1 }}));
      }}
      if (trust[bi] !== 0) {{
        var tY = yAt(Math.max(0, trust[bi]));
        var tH = Math.max(1, Math.abs(yAt(trust[bi]) - yZero));
        svg.appendChild(el("rect", {{ x: cx - barW * 0.5, y: tY, width: barW, height: tH, fill: "var(--series-2)", rx: 1 }}));
      }}
      if (dealer[bi] !== 0) {{
        var dY = yAt(Math.max(0, dealer[bi]));
        var dH = Math.max(1, Math.abs(yAt(dealer[bi]) - yZero));
        svg.appendChild(el("rect", {{ x: cx + barW * 0.5, y: dY, width: barW, height: dH, fill: "var(--series-3)", rx: 1 }}));
      }}
    }}

    var dPath = "";
    total.forEach(function (tv, idx) {{
      var x = xAt(idx), y = yAt(tv);
      dPath += (idx === 0 ? "M" : "L") + x.toFixed(2) + " " + y.toFixed(2) + " ";
    }});
    svg.appendChild(el("path", {{ d: dPath, fill: "none", stroke: "var(--series-4)", "stroke-width": 2.5, "stroke-linejoin": "round" }}));

    var crosshair = el("line", {{ "class": "crosshair", x1: margin.left, x2: margin.left, y1: margin.top, y2: height - margin.bottom }});
    svg.appendChild(crosshair);
    var hit = el("rect", {{ "class": "hit-rect", x: margin.left, y: margin.top, width: plotW, height: plotH, tabindex: "0" }});
    svg.appendChild(hit);
    container.appendChild(svg);

    var tooltip = document.createElement("div");
    tooltip.className = "tooltip";
    container.appendChild(tooltip);

    function showTooltip(idx) {{
      crosshair.setAttribute("x1", xAt(idx)); crosshair.setAttribute("x2", xAt(idx)); crosshair.style.opacity = 1;
      while (tooltip.firstChild) tooltip.removeChild(tooltip.firstChild);

      var d = document.createElement("div"); d.className = "tooltip-date"; d.textContent = opts.pointLabels[idx]; tooltip.appendChild(d);
      if (opts.subLabels && opts.subLabels[idx]) {{
        var sub = document.createElement("div"); sub.className = "tooltip-sub"; sub.textContent = opts.subLabels[idx]; tooltip.appendChild(sub);
      }}

      var seriesInfo = [
        {{ label: "外資", color: "--series-1", val: foreign[idx] }},
        {{ label: "投信", color: "--series-2", val: trust[idx] }},
        {{ label: "自營商", color: "--series-3", val: dealer[idx] }},
        {{ label: "合計", color: "--series-4", val: total[idx] }}
      ];
      seriesInfo.forEach(function (s) {{
        var r = document.createElement("div"); r.className = "tooltip-row";
        r.innerHTML = '<span class="tooltip-key" style="background:var(' + s.color + ')"></span>' +
                      '<span class="tooltip-name">' + s.label + '</span>' +
                      '<span class="tooltip-value">' + formatSigned(s.val) + ' 張</span>';
        tooltip.appendChild(r);
      }});

      var svgRect = svg.getBoundingClientRect();
      var wrapRect = container.getBoundingClientRect();
      var scaleX = svgRect.width / width;
      var posX = (svgRect.left - wrapRect.left) + xAt(idx) * scaleX;
      var posY = (svgRect.top - wrapRect.top) + margin.top * scaleX;

      tooltip.style.left = posX + "px"; tooltip.style.top = posY + "px"; tooltip.style.opacity = 1;
    }}

    function hideTooltip() {{ tooltip.style.opacity = 0; crosshair.style.opacity = 0; }}
    function ptToIdx(evt) {{
      var rect = svg.getBoundingClientRect();
      var rx = ((evt.clientX - rect.left) / rect.width) * width;
      var i = Math.round(((rx - margin.left) / plotW) * (n - 1));
      return Math.min(n - 1, Math.max(0, i));
    }}

    hit.addEventListener("pointermove", function (e) {{ showTooltip(ptToIdx(e)); }});
    hit.addEventListener("pointerleave", hideTooltip);
  }}

  function renderCandlestickChart(container, opts) {{
    var width = 880, height = opts.height || 380;
    var margin = {{ top: 20, right: 24, bottom: 30, left: 68 }};
    var plotW = width - margin.left - margin.right;
    var priceH = 220; var volH = 80; var volTop = margin.top + priceH + 20;

    var axisLabels = opts.axisLabels;
    var n = axisLabels.length;
    if (n === 0) return;

    var open = opts.open, high = opts.high, low = opts.low, close = opts.close, volume = opts.volume;
    var ma5 = opts.ma5, ma20 = opts.ma20;

    var priceVals = [], volVals = [0];
    var maxHiIdx = 0, minLoIdx = 0, maxHi = -Infinity, minLo = Infinity;

    for (var i = 0; i < n; i++) {{
      if (high[i] > 0 && low[i] > 0) {{
        priceVals.push(high[i], low[i]);
        if (high[i] > maxHi) {{ maxHi = high[i]; maxHiIdx = i; }}
        if (low[i] < minLo) {{ minLo = low[i]; minLoIdx = i; }}
      }}
      if (volume && volume[i] > 0) volVals.push(volume[i]);
    }}
    if (priceVals.length === 0) priceVals.push(0, 1);

    var priceScale = niceScale(Math.min.apply(null, priceVals), Math.max.apply(null, priceVals), 5);
    var volMax = Math.max.apply(null, volVals) || 1;

    function xAt(i) {{ return n <= 1 ? margin.left + plotW / 2 : margin.left + (i / (n - 1)) * plotW; }}
    function yPriceAt(v) {{ return margin.top + priceH - ((v - priceScale.min) / (priceScale.max - priceScale.min)) * priceH; }}
    function yVolAt(v) {{ return volTop + volH - (v / volMax) * volH; }}

    var svg = el("svg", {{ "class": "chart-svg", viewBox: "0 0 " + width + " " + height }});

    priceScale.ticks.forEach(function (t) {{
      var y = yPriceAt(t);
      svg.appendChild(el("line", {{ "class": "gridline", x1: margin.left, x2: width - margin.right, y1: y, y2: y }}));
      var label = el("text", {{ "class": "axis-label", x: margin.left - 8, y: y + 4, "text-anchor": "end" }});
      label.textContent = formatPrice(t);
      svg.appendChild(label);
    }});

    svg.appendChild(el("line", {{ "class": "gridline", x1: margin.left, x2: width - margin.right, y1: volTop, y2: volTop }}));
    var volLbl = el("text", {{ "class": "axis-label", x: margin.left - 8, y: volTop + 12, "text-anchor": "end" }});
    volLbl.textContent = "成交(張)"; svg.appendChild(volLbl);

    var maxXLabels = opts.maxXLabels || 8;
    var xStep = Math.max(1, Math.ceil(n / maxXLabels));
    for (var xi = 0; xi < n; xi += xStep) {{
      var lbl = el("text", {{ "class": "axis-label", x: xAt(xi), y: height - margin.bottom + 18, "text-anchor": "middle" }});
      lbl.textContent = axisLabels[xi]; svg.appendChild(lbl);
    }}

    var slot = n > 1 ? plotW / (n - 1) : plotW;
    var candleW = Math.max(1.5, Math.min(slot * 0.6, 12));

    for (var ci = 0; ci < n; ci++) {{
      var o = open[ci], h = high[ci], l = low[ci], c = close[ci], v = volume ? volume[ci] : 0;
      if (!(h > 0 && l > 0)) continue;
      var cx = xAt(ci); var isUp = c >= o; var colorVar = isUp ? "--candle-up" : "--candle-down";

      svg.appendChild(el("line", {{ x1: cx, x2: cx, y1: yPriceAt(h), y2: yPriceAt(l), "stroke-width": 1, stroke: "var(" + colorVar + ")" }}));
      var bodyTop = yPriceAt(Math.max(o, c));
      var bodyH = Math.max(1, yPriceAt(Math.min(o, c)) - bodyTop);
      svg.appendChild(el("rect", {{ x: cx - candleW / 2, y: bodyTop, width: candleW, height: bodyH, fill: "var(" + colorVar + ")" }}));

      if (v > 0) {{
        var vY = yVolAt(v); var vH = Math.max(1, volTop + volH - vY);
        svg.appendChild(el("rect", {{ x: cx - candleW / 2, y: vY, width: candleW, height: vH, fill: "var(" + colorVar + ")", opacity: 0.65 }}));
      }}
    }}

    function drawMA(maArr, colorVar) {{
      var p = "";
      maArr.forEach(function (mv, idx) {{
        if (isValidNum(mv)) p += (p === "" ? "M" : "L") + xAt(idx).toFixed(2) + " " + yPriceAt(mv).toFixed(2) + " ";
      }});
      if (p !== "") svg.appendChild(el("path", {{ d: p, fill: "none", stroke: "var(" + colorVar + ")", "stroke-width": 1.5 }}));
    }}
    if (ma5) drawMA(ma5, "--ma5-color");
    if (ma20) drawMA(ma20, "--ma20-color");

    if (isFinite(maxHi)) {{
      var hX = xAt(maxHiIdx), hY = yPriceAt(maxHi);
      var hTxt = el("text", {{ x: hX, y: hY - 6, "class": "axis-label", "text-anchor": "middle", fill: "var(--candle-up)", "font-weight": "700" }});
      hTxt.textContent = "高 " + formatPrice(maxHi); svg.appendChild(hTxt);
    }}
    if (isFinite(minLo)) {{
      var lX = xAt(minLoIdx), lY = yPriceAt(minLo);
      var lTxt = el("text", {{ x: lX, y: lY + 14, "class": "axis-label", "text-anchor": "middle", fill: "var(--candle-down)", "font-weight": "700" }});
      lTxt.textContent = "低 " + formatPrice(minLo); svg.appendChild(lTxt);
    }}

    var crosshair = el("line", {{ "class": "crosshair", x1: margin.left, x2: margin.left, y1: margin.top, y2: height - margin.bottom }});
    svg.appendChild(crosshair);
    var hit = el("rect", {{ "class": "hit-rect", x: margin.left, y: margin.top, width: plotW, height: height - margin.top - margin.bottom, tabindex: "0" }});
    svg.appendChild(hit);
    container.appendChild(svg);

    var tooltip = document.createElement("div");
    tooltip.className = "tooltip";
    container.appendChild(tooltip);

    function showTooltip(idx) {{
      crosshair.setAttribute("x1", xAt(idx)); crosshair.setAttribute("x2", xAt(idx)); crosshair.style.opacity = 1;
      while (tooltip.firstChild) tooltip.removeChild(tooltip.firstChild);

      var d = document.createElement("div"); d.className = "tooltip-date"; d.textContent = opts.pointLabels[idx]; tooltip.appendChild(d);
      if (opts.subLabels && opts.subLabels[idx]) {{
        var sub = document.createElement("div"); sub.className = "tooltip-sub"; sub.textContent = opts.subLabels[idx]; tooltip.appendChild(sub);
      }}

      var isUp = close[idx] >= open[idx];
      var cColor = isUp ? "--candle-up" : "--candle-down";

      var rows = [
        ["開盤", formatPrice(open[idx])],
        ["最高", formatPrice(high[idx])],
        ["最低", formatPrice(low[idx])],
        ["收盤", formatPrice(close[idx])],
        ["成交張數", formatPlain(volume ? volume[idx] : 0) + " 張"]
      ];
      if (isValidNum(ma5[idx])) rows.push(["MA5", formatPrice(ma5[idx])]);
      if (isValidNum(ma20[idx])) rows.push(["MA20", formatPrice(ma20[idx])]);

      rows.forEach(function (r) {{
        var tr = document.createElement("div"); tr.className = "tooltip-row";
        tr.innerHTML = '<span class="tooltip-key" style="background:var(' + cColor + ')"></span>' +
                       '<span class="tooltip-name">' + r[0] + '</span>' +
                       '<span class="tooltip-value">' + r[1] + '</span>';
        tooltip.appendChild(tr);
      }});

      var svgRect = svg.getBoundingClientRect();
      var wrapRect = container.getBoundingClientRect();
      var scaleX = svgRect.width / width;
      var posX = (svgRect.left - wrapRect.left) + xAt(idx) * scaleX;
      var posY = (svgRect.top - wrapRect.top) + margin.top * scaleX;

      tooltip.style.left = posX + "px"; tooltip.style.top = posY + "px"; tooltip.style.opacity = 1;
    }}

    function hideTooltip() {{ tooltip.style.opacity = 0; crosshair.style.opacity = 0; }}
    function ptToIdx(evt) {{
      var rect = svg.getBoundingClientRect();
      var rx = ((evt.clientX - rect.left) / rect.width) * width;
      var i = Math.round(((rx - margin.left) / plotW) * (n - 1));
      return Math.min(n - 1, Math.max(0, i));
    }}

    hit.addEventListener("pointermove", function (e) {{ showTooltip(ptToIdx(e)); }});
    hit.addEventListener("pointerleave", hideTooltip);
  }}

  function renderLineChart(container, opts) {{
    var width = 880, height = opts.height || 300;
    var margin = {{ top: 20, right: 24, bottom: 30, left: 68 }};
    var plotW = width - margin.left - margin.right;
    var plotH = height - margin.top - margin.bottom;

    var axisLabels = opts.axisLabels;
    var n = axisLabels.length;
    if (n === 0) return;

    var allVals = [];
    opts.series.forEach(function (s) {{ s.values.forEach(function (v) {{ if (isValidNum(v)) allVals.push(v); }}); }});
    if (opts.zeroBaseline) allVals.push(0);
    if (allVals.length === 0) allVals.push(0, 1);

    var scale = niceScale(Math.min.apply(null, allVals), Math.max.apply(null, allVals), 5);

    function xAt(i) {{ return n <= 1 ? margin.left + plotW / 2 : margin.left + (i / (n - 1)) * plotW; }}
    function yAt(v) {{ return margin.top + plotH - ((v - scale.min) / (scale.max - scale.min)) * plotH; }}

    var svg = el("svg", {{ "class": "chart-svg", viewBox: "0 0 " + width + " " + height }});

    var defs = el("defs");
    opts.series.forEach(function (s, sIdx) {{
      var gradId = "grad-" + (opts.cardId || "line") + "-" + sIdx;
      var grad = el("linearGradient", {{ id: gradId, x1: "0%", y1: "0%", x2: "0%", y2: "100%" }});
      grad.appendChild(el("stop", {{ offset: "0%", "stop-color": "var(" + s.colorVar + ")", "stop-opacity": "0.3" }}));
      grad.appendChild(el("stop", {{ offset: "100%", "stop-color": "var(" + s.colorVar + ")", "stop-opacity": "0.0" }}));
      defs.appendChild(grad);
    }});
    svg.appendChild(defs);

    scale.ticks.forEach(function (t) {{
      var y = yAt(t);
      svg.appendChild(el("line", {{ "class": (t === 0 && opts.zeroBaseline) ? "baseline" : "gridline", x1: margin.left, x2: width - margin.right, y1: y, y2: y }}));
      var label = el("text", {{ "class": "axis-label", x: margin.left - 8, y: y + 4, "text-anchor": "end" }});
      label.textContent = opts.formatTick(t);
      svg.appendChild(label);
    }});

    var maxXLabels = opts.maxXLabels || 8;
    var xStep = Math.max(1, Math.ceil(n / maxXLabels));
    for (var i = 0; i < n; i += xStep) {{
      var lbl = el("text", {{ "class": "axis-label", x: xAt(i), y: height - margin.bottom + 18, "text-anchor": "middle" }});
      lbl.textContent = axisLabels[i];
      svg.appendChild(lbl);
    }}

    opts.series.forEach(function (s, sIdx) {{
      var gradId = "grad-" + (opts.cardId || "line") + "-" + sIdx;
      var dLine = "", dArea = "";
      var drawing = false, lastX = 0;
      var zeroY = yAt(opts.zeroBaseline ? 0 : scale.min);

      s.values.forEach(function (v, idx) {{
        if (!isValidNum(v)) {{ drawing = false; return; }}
        var x = xAt(idx), y = yAt(v);
        if (!drawing) {{
          dLine += "M" + x.toFixed(2) + " " + y.toFixed(2) + " ";
          dArea += "M" + x.toFixed(2) + " " + zeroY.toFixed(2) + " L" + x.toFixed(2) + " " + y.toFixed(2) + " ";
          drawing = true;
        }} else {{
          dLine += "L" + x.toFixed(2) + " " + y.toFixed(2) + " ";
          dArea += "L" + x.toFixed(2) + " " + y.toFixed(2) + " ";
        }}
        lastX = x;
      }});

      if (drawing) {{
        dArea += "L" + lastX.toFixed(2) + " " + zeroY.toFixed(2) + " Z";
        svg.appendChild(el("path", {{ d: dArea, fill: "url(#" + gradId + ")" }}));
        svg.appendChild(el("path", {{ d: dLine, fill: "none", stroke: "var(" + s.colorVar + ")", "stroke-width": 2.2, "stroke-linejoin": "round" }}));
      }}
    }});

    var crosshair = el("line", {{ "class": "crosshair", x1: margin.left, x2: margin.left, y1: margin.top, y2: height - margin.bottom }});
    svg.appendChild(crosshair);
    var hit = el("rect", {{ "class": "hit-rect", x: margin.left, y: margin.top, width: plotW, height: plotH, tabindex: "0" }});
    svg.appendChild(hit);
    container.appendChild(svg);

    var tooltip = document.createElement("div");
    tooltip.className = "tooltip";
    container.appendChild(tooltip);

    function showTooltip(idx) {{
      crosshair.setAttribute("x1", xAt(idx)); crosshair.setAttribute("x2", xAt(idx)); crosshair.style.opacity = 1;
      while (tooltip.firstChild) tooltip.removeChild(tooltip.firstChild);

      var d = document.createElement("div"); d.className = "tooltip-date"; d.textContent = opts.pointLabels[idx]; tooltip.appendChild(d);
      if (opts.subLabels && opts.subLabels[idx]) {{
        var sub = document.createElement("div"); sub.className = "tooltip-sub"; sub.textContent = opts.subLabels[idx]; tooltip.appendChild(sub);
      }}

      opts.series.forEach(function (s) {{
        var tr = document.createElement("div"); tr.className = "tooltip-row";
        tr.innerHTML = '<span class="tooltip-key" style="background:var(' + s.colorVar + ')"></span>' +
                       '<span class="tooltip-name">' + s.label + '</span>' +
                       '<span class="tooltip-value">' + opts.formatTick(s.values[idx]) + '</span>';
        tooltip.appendChild(tr);
      }});

      var svgRect = svg.getBoundingClientRect();
      var wrapRect = container.getBoundingClientRect();
      var scaleX = svgRect.width / width;
      var posX = (svgRect.left - wrapRect.left) + xAt(idx) * scaleX;
      var posY = (svgRect.top - wrapRect.top) + margin.top * scaleX;

      tooltip.style.left = posX + "px"; tooltip.style.top = posY + "px"; tooltip.style.opacity = 1;
    }}

    function hideTooltip() {{ tooltip.style.opacity = 0; crosshair.style.opacity = 0; }}
    function ptToIdx(evt) {{
      var rect = svg.getBoundingClientRect();
      var rx = ((evt.clientX - rect.left) / rect.width) * width;
      var i = Math.round(((rx - margin.left) / plotW) * (n - 1));
      return Math.min(n - 1, Math.max(0, i));
    }}

    hit.addEventListener("pointermove", function (e) {{ showTooltip(ptToIdx(e)); }});
    hit.addEventListener("pointerleave", hideTooltip);
  }}

  // ---------- 資料表與 CSV 匯出 ----------
  function renderTable(container, stockId, rowLabels, series, formatVal, title, rowHeader) {{
    var actions = document.createElement("div");
    actions.className = "table-actions";

    var toggleBtn = document.createElement("button");
    toggleBtn.type = "button"; toggleBtn.className = "btn-sm"; toggleBtn.textContent = "顯示數據資料表";

    var exportBtn = document.createElement("button");
    exportBtn.type = "button"; exportBtn.className = "btn-sm"; exportBtn.textContent = "匯出 CSV";

    actions.appendChild(toggleBtn);
    actions.appendChild(exportBtn);

    var tableWrap = document.createElement("div");
    tableWrap.className = "table-responsive-wrap";
    tableWrap.hidden = true;

    var table = document.createElement("table");
    table.className = "data-table";

    var thead = document.createElement("thead");
    var trH = document.createElement("tr");
    trH.innerHTML = '<th>' + (rowHeader || "日期") + '</th>' +
                    series.map(function (s) {{ return '<th>' + s.label + '</th>'; }}).join("");
    thead.appendChild(trH); table.appendChild(thead);

    var tbody = document.createElement("tbody");
    for (var i = rowLabels.length - 1; i >= 0; i--) {{
      var tr = document.createElement("tr");
      var html = '<td>' + rowLabels[i] + '</td>';
      series.forEach(function (s) {{
        var val = s.values[i];
        var cls = "";
        if (typeof val === "number") {{
          if (val > 0) cls = "num-positive";
          else if (val < 0) cls = "num-negative";
        }}
        html += '<td class="' + cls + '">' + formatVal(val) + '</td>';
      }});
      tr.innerHTML = html;
      tbody.appendChild(tr);
    }}
    table.appendChild(tbody);
    tableWrap.appendChild(table);

    toggleBtn.addEventListener("click", function () {{
      tableWrap.hidden = !tableWrap.hidden;
      toggleBtn.textContent = tableWrap.hidden ? "顯示數據資料表" : "隱藏數據資料表";
    }});

    exportBtn.addEventListener("click", function () {{
      var csv = [(rowHeader || "日期")].concat(series.map(function(s){{return s.label;}})).join(",") + "\\n";
      for (var k = rowLabels.length - 1; k >= 0; k--) {{
        var row = [rowLabels[k]];
        series.forEach(function (s) {{ row.push(s.values[k] != null ? s.values[k] : ""); }});
        csv += row.join(",") + "\\n";
      }}
      var blob = new Blob(["\\uFEFF" + csv], {{ type: "text/csv;charset=utf-8;" }});
      var url = URL.createObjectURL(blob);
      var a = document.createElement("a");
      a.href = url;
      a.download = stockId + "_" + title + ".csv";
      a.click();
      URL.revokeObjectURL(url);
    }});

    container.appendChild(actions);
    container.appendChild(tableWrap);
  }}

  // ---------- 3-TIER SPA ENGINE ----------
  var stockChipsBar = document.getElementById("stock-chips-bar");
  var tfButtons = document.querySelectorAll('.pill-btn[data-tf]');
  var brandHomeBtn = document.getElementById("brand-home-btn");

  var heatmapView = document.getElementById("heatmap-view");
  var stockOverviewView = document.getElementById("stock-overview-view");
  var detailView = document.getElementById("detail-view");

  var heatmapGrid = document.getElementById("heatmap-grid");
  var widgetGrid = document.getElementById("widget-grid");
  var detailContainer = document.getElementById("detail-chart-container");
  var metaHint = document.getElementById("meta-hint");

  var backToHeatmapBtn = document.getElementById("back-to-heatmap-btn");
  var backToHeatmapFromDetail = document.getElementById("back-to-heatmap-from-detail");
  var backToStockBtn = document.getElementById("back-to-stock-btn");
  var stockOverviewTitle = document.getElementById("stock-overview-title");
  var detailTabBtns = document.querySelectorAll(".detail-tab-btn");

  var stockIds = STOCK_ORDER;
  var currentStockId = stockIds[0] || "";
  var currentTf = "day";
  var currentView = "heatmap"; // "heatmap" | "stock" | "detail"
  var currentDetailChart = "flow";

  var CHART_CONFIGS = {{
    flow:   {{ title: "三大法人買賣超 (張)" }},
    kline:  {{ title: "K 線圖與成交量" }},
    amount: {{ title: "估算買賣超金額 (萬元)" }},
    margin: {{ title: "融資餘額 (張)" }},
    short:  {{ title: "融券餘額 (張)" }},
    ratio:  {{ title: "券資比 (%)" }}
  }};

  // 渲染 Stock Quick Switcher Chips
  function renderStockChipsBar() {{
    while (stockChipsBar.firstChild) stockChipsBar.removeChild(stockChipsBar.firstChild);

    stockIds.forEach(function (sId) {{
      var stock = DATA[sId];
      var agg = aggregateStock(stock, currentTf);
      var idx = agg.close.length - 1;
      var prevIdx = idx > 0 ? idx - 1 : idx;
      var diff = agg.close[idx] - agg.close[prevIdx];
      var pct = agg.close[prevIdx] ? (diff / agg.close[prevIdx] * 100) : 0;

      var chip = document.createElement("button");
      chip.type = "button";
      chip.className = "stock-chip" + (currentView !== "heatmap" && sId === currentStockId ? " active" : "");
      chip.innerHTML = sId + ' ' + (stock.name || '') +
                       ' <span class="chip-tag ' + (diff >= 0 ? "chip-tag-up" : "chip-tag-down") + '">' +
                       (diff >= 0 ? "▲+" : "▼") + pct.toFixed(2) + '%</span>';

      chip.addEventListener("click", function () {{
        currentStockId = sId;
        location.hash = "#stock/" + sId;
      }});
      stockChipsBar.appendChild(chip);
    }});
  }}

  // TIER 1: 全市場股票熱力圖 (Heatmap Overview)
  function renderHeatmapView() {{
    while (heatmapGrid.firstChild) heatmapGrid.removeChild(heatmapGrid.firstChild);

    stockIds.forEach(function (sId) {{
      var stock = DATA[sId];
      var agg = aggregateStock(stock, currentTf);
      var idx = agg.close.length - 1;
      var prevIdx = idx > 0 ? idx - 1 : idx;

      var latestClose = agg.close[idx];
      var prevClose = agg.close[prevIdx];
      var diff = latestClose - prevClose;
      var pct = prevClose ? (diff / prevClose * 100) : 0;
      var totalNet = agg.total[idx];

      var isUp = diff >= 0;
      var intensity = Math.min(0.5, 0.12 + Math.abs(pct) * 0.12);
      var bgStyle = isUp ? ("rgba(239, 68, 68, " + intensity + ")") : ("rgba(16, 185, 129, " + intensity + ")");

      var card = document.createElement("div");
      card.className = "heatmap-card";
      card.style.background = bgStyle;

      card.innerHTML = '<div class="heatmap-card-header">' +
                         '<div>' +
                           '<div class="heatmap-stock-name">' + sId + ' ' + stock.name + '</div>' +
                           '<div class="heatmap-stock-code">TWSE / OTC</div>' +
                         '</div>' +
                         '<div class="heatmap-price-wrap">' +
                           '<div class="heatmap-price">' + formatPrice(latestClose) + '</div>' +
                           '<div class="heatmap-change ' + (isUp ? "num-positive" : "num-negative") + '">' +
                             (isUp ? "▲ +" : "▼ ") + diff.toFixed(2) + ' (' + (isUp ? "+" : "") + pct.toFixed(2) + '%)' +
                           '</div>' +
                         '</div>' +
                       '</div>' +
                       '<div class="heatmap-sparkline-wrap"></div>' +
                       '<div class="heatmap-card-footer">' +
                         '<span>三大法人合計：<strong>' + formatSigned(totalNet) + ' 張</strong></span>' +
                         '<span style="color:var(--series-1); font-weight:700">點擊查看 ➔</span>' +
                       '</div>';

      var sparkWrap = card.querySelector(".heatmap-sparkline-wrap");
      renderMiniSparkline(sparkWrap, "price_line", agg, 60);

      card.addEventListener("click", function () {{
        currentStockId = sId;
        location.hash = "#stock/" + sId;
      }});

      heatmapGrid.appendChild(card);
    }});
  }}

  // TIER 2: 單股 6 Widget 儀表板
  function renderStockOverviewGrid() {{
    while (widgetGrid.firstChild) widgetGrid.removeChild(widgetGrid.firstChild);
    var stock = DATA[currentStockId];
    if (!stock || stock.dates.length === 0) return;

    stockOverviewTitle.textContent = currentStockId + " " + stock.name + " 籌碼分析儀表板";

    var tf = TIMEFRAMES[currentTf];
    var agg = aggregateStock(stock, currentTf);
    renderKPIStats(currentStockId, stock, agg);

    var widgetTypes = ["flow", "kline", "amount", "margin", "short", "ratio"];
    widgetTypes.forEach(function (cType) {{
      var card = document.createElement("div");
      card.className = "widget-card";

      var header = document.createElement("div");
      header.className = "widget-header";
      header.innerHTML = '<h3 class="widget-title">' + CHART_CONFIGS[cType].title + '</h3>' +
                         '<span class="widget-action-btn">檢視明細 🔍</span>';
      card.appendChild(header);

      var svgWrap = document.createElement("div");
      svgWrap.className = "widget-svg-wrap";
      renderMiniSparkline(svgWrap, cType, agg, 150);
      card.appendChild(svgWrap);

      card.addEventListener("click", function () {{
        location.hash = "#stock/" + currentStockId + "/detail/" + cType;
      }});
      widgetGrid.appendChild(card);
    }});
  }}

  // TIER 3: 圖表明細大圖頁
  function renderDetailView() {{
    while (detailContainer.firstChild) detailContainer.removeChild(detailContainer.firstChild);
    var stock = DATA[currentStockId];
    if (!stock || stock.dates.length === 0) return;

    var tf = TIMEFRAMES[currentTf];
    var agg = aggregateStock(stock, currentTf);
    renderKPIStats(currentStockId, stock, agg);

    detailTabBtns.forEach(function (btn) {{
      var active = btn.getAttribute("data-chart") === currentDetailChart;
      btn.setAttribute("aria-pressed", active ? "true" : "false");
      btn.classList.toggle("active", active);
    }});

    var card = document.createElement("div");
    card.className = "chart-card";

    if (currentDetailChart === "flow") {{
      card.innerHTML = '<div class="chart-card-header"><h3 class="chart-title">' + currentStockId + ' ' + stock.name + ' 三大法人買賣超 (張)' + (currentTf === "day" ? "" : "・" + tf.unit + "合計") + '</h3>' +
                       '<div class="legend"><span class="legend-item"><span class="legend-swatch" style="background:var(--series-1)"></span>外資</span>' +
                       '<span class="legend-item"><span class="legend-swatch" style="background:var(--series-2)"></span>投信</span>' +
                       '<span class="legend-item"><span class="legend-swatch" style="background:var(--series-3)"></span>自營商</span>' +
                       '<span class="legend-item"><span class="legend-swatch" style="background:var(--series-4)"></span>合計</span></div></div>';
      var cWrap = document.createElement("div"); cWrap.className = "chart-svg-wrap"; card.appendChild(cWrap);
      renderInstitutionalChart(cWrap, {{
        axisLabels: agg.axisLabels, pointLabels: agg.pointLabels, subLabels: agg.subLabels,
        foreign: agg.foreign, trust: agg.trust, dealer: agg.dealer, total: agg.total, maxXLabels: tf.maxXLabels
      }});
      renderTable(card, currentStockId, agg.pointLabels, [
        {{ label: "外資(張)", values: agg.foreign }}, {{ label: "投信(張)", values: agg.trust }},
        {{ label: "自營商(張)", values: agg.dealer }}, {{ label: "合計(張)", values: agg.total }}
      ], formatSigned, "三大法人買賣超", tf.dateHeader);

    }} else if (currentDetailChart === "kline") {{
      card.innerHTML = '<div class="chart-card-header"><h3 class="chart-title">' + currentStockId + ' ' + stock.name + ' K 線圖與成交量 (' + tf.unit + '線)</h3>' +
                       '<div class="legend"><span class="legend-item"><span class="legend-swatch" style="background:var(--ma5-color)"></span>MA5</span>' +
                       '<span class="legend-item"><span class="legend-swatch" style="background:var(--ma20-color)"></span>MA20</span></div></div>';
      var cWrap2 = document.createElement("div"); cWrap2.className = "chart-svg-wrap"; card.appendChild(cWrap2);
      renderCandlestickChart(cWrap2, {{
        axisLabels: agg.axisLabels, pointLabels: agg.pointLabels, subLabels: agg.subLabels,
        open: agg.open, high: agg.high, low: agg.low, close: agg.close, volume: agg.volume,
        ma5: agg.ma5, ma20: agg.ma20, maxXLabels: tf.maxXLabels
      }});
      renderTable(card, currentStockId, agg.pointLabels, [
        {{ label: "開盤", values: agg.open }}, {{ label: "最高", values: agg.high }},
        {{ label: "最低", values: agg.low }}, {{ label: "收盤", values: agg.close }},
        {{ label: "成交張數", values: agg.volume }}
      ], formatPrice, "K線行情數據", tf.dateHeader);

    }} else if (currentDetailChart === "amount") {{
      card.innerHTML = '<div class="chart-card-header"><h3 class="chart-title">' + currentStockId + ' ' + stock.name + ' 估算買賣超金額 (萬元)' + (currentTf === "day" ? "" : "・" + tf.unit + "合計") + '</h3>' +
                       '<div class="legend"><span class="legend-item"><span class="legend-swatch" style="background:var(--series-1)"></span>估算金額</span></div></div>';
      var cWrap3 = document.createElement("div"); cWrap3.className = "chart-svg-wrap"; card.appendChild(cWrap3);
      renderLineChart(cWrap3, {{
        cardId: "amount", axisLabels: agg.axisLabels, pointLabels: agg.pointLabels, subLabels: agg.subLabels,
        series: [{{ label: "估算金額(萬元)", colorVar: "--series-1", values: agg.amount }}], formatTick: formatSigned, zeroBaseline: true, maxXLabels: tf.maxXLabels
      }});
      renderTable(card, currentStockId, agg.pointLabels, [{{ label: "估算金額(萬元)", values: agg.amount }}], formatSigned, "估算金額", tf.dateHeader);

    }} else if (currentDetailChart === "margin") {{
      card.innerHTML = '<div class="chart-card-header"><h3 class="chart-title">' + currentStockId + ' ' + stock.name + ' 融資餘額 (張)' + (currentTf === "day" ? "" : "・" + tf.unit + "底") + '</h3>' +
                       '<div class="legend"><span class="legend-item"><span class="legend-swatch" style="background:var(--series-1)"></span>融資餘額</span></div></div>';
      var cWrap4 = document.createElement("div"); cWrap4.className = "chart-svg-wrap"; card.appendChild(cWrap4);
      renderLineChart(cWrap4, {{
        cardId: "margin", axisLabels: agg.axisLabels, pointLabels: agg.pointLabels, subLabels: agg.subLabels,
        series: [{{ label: "融資餘額(張)", colorVar: "--series-1", values: agg.marginBalance }}], formatTick: formatPlain, zeroBaseline: false, maxXLabels: tf.maxXLabels
      }});
      renderTable(card, currentStockId, agg.pointLabels, [{{ label: "融資餘額(張)", values: agg.marginBalance }}], formatPlain, "融資餘額", tf.dateHeader);

    }} else if (currentDetailChart === "short") {{
      card.innerHTML = '<div class="chart-card-header"><h3 class="chart-title">' + currentStockId + ' ' + stock.name + ' 融券餘額 (張)' + (currentTf === "day" ? "" : "・" + tf.unit + "底") + '</h3>' +
                       '<div class="legend"><span class="legend-item"><span class="legend-swatch" style="background:var(--series-1)"></span>融券餘額</span></div></div>';
      var cWrap5 = document.createElement("div"); cWrap5.className = "chart-svg-wrap"; card.appendChild(cWrap5);
      renderLineChart(cWrap5, {{
        cardId: "short", axisLabels: agg.axisLabels, pointLabels: agg.pointLabels, subLabels: agg.subLabels,
        series: [{{ label: "融券餘額(張)", colorVar: "--series-1", values: agg.shortBalance }}], formatTick: formatPlain, zeroBaseline: false, maxXLabels: tf.maxXLabels
      }});
      renderTable(card, currentStockId, agg.pointLabels, [{{ label: "融券餘額(張)", values: agg.shortBalance }}], formatPlain, "融券餘額", tf.dateHeader);

    }} else if (currentDetailChart === "ratio") {{
      card.innerHTML = '<div class="chart-card-header"><h3 class="chart-title">' + currentStockId + ' ' + stock.name + ' 券資比 (%)' + (currentTf === "day" ? "" : "・" + tf.unit + "底") + '</h3>' +
                       '<div class="legend"><span class="legend-item"><span class="legend-swatch" style="background:var(--series-1)"></span>券資比</span></div></div>';
      var cWrap6 = document.createElement("div"); cWrap6.className = "chart-svg-wrap"; card.appendChild(cWrap6);
      renderLineChart(cWrap6, {{
        cardId: "ratio", axisLabels: agg.axisLabels, pointLabels: agg.pointLabels, subLabels: agg.subLabels,
        series: [{{ label: "券資比(%)", colorVar: "--series-1", values: agg.shortToMarginRatio }}], formatTick: formatPercent, zeroBaseline: true, maxXLabels: tf.maxXLabels
      }});
      renderTable(card, currentStockId, agg.pointLabels, [{{ label: "券資比(%)", values: agg.shortToMarginRatio }}], formatPercent, "券資比", tf.dateHeader);
    }}

    detailContainer.appendChild(card);
  }}

  // SPA Route Resolver (#heatmap | #stock/:id | #stock/:id/detail/:type)
  function handleRoute() {{
    var hash = location.hash || "#heatmap";
    renderStockChipsBar();

    if (hash.indexOf("#stock/") === 0) {{
      var parts = hash.replace("#stock/", "").split("/detail/");
      currentStockId = parts[0] || stockIds[0];

      if (parts.length > 1) {{
        // TIER 3: 明細頁
        currentView = "detail";
        currentDetailChart = parts[1] || "flow";
        heatmapView.hidden = true;
        stockOverviewView.hidden = true;
        detailView.hidden = false;
        metaHint.textContent = "檢視 " + currentStockId + " 圖表明細數據";
        renderDetailView();
      }} else {{
        // TIER 2: 單股 6 Widget 儀表板
        currentView = "stock";
        heatmapView.hidden = true;
        stockOverviewView.hidden = false;
        detailView.hidden = true;
        metaHint.textContent = "點擊 Widget 可放大檢視單一圖表明細";
        renderStockOverviewGrid();
      }}
    }} else {{
      // TIER 1: 全市場股票熱力圖
      currentView = "heatmap";
      heatmapView.hidden = false;
      stockOverviewView.hidden = true;
      detailView.hidden = true;
      metaHint.textContent = "點擊個股卡片進入該股票的分析儀表板";
      renderHeatmapView();
    }}

    window.scrollTo(0, 0);
  }}

  // Controls & Event Listeners
  tfButtons.forEach(function (btn) {{
    btn.addEventListener("click", function () {{
      var tf = btn.getAttribute("data-tf");
      if (tf === currentTf) return;
      currentTf = tf;
      tfButtons.forEach(function (b) {{ b.setAttribute("aria-pressed", b.getAttribute("data-tf") === tf ? "true" : "false"); }});
      handleRoute();
    }});
  }});

  brandHomeBtn.addEventListener("click", function () {{ location.hash = "#heatmap"; }});
  backToHeatmapBtn.addEventListener("click", function () {{ location.hash = "#heatmap"; }});
  backToHeatmapFromDetail.addEventListener("click", function () {{ location.hash = "#heatmap"; }});

  backToStockBtn.addEventListener("click", function () {{
    location.hash = "#stock/" + currentStockId;
  }});

  detailTabBtns.forEach(function (btn) {{
    btn.addEventListener("click", function () {{
      var cType = btn.getAttribute("data-chart");
      location.hash = "#stock/" + currentStockId + "/detail/" + cType;
    }});
  }});

  window.addEventListener("hashchange", handleRoute);
  handleRoute();
}})();
</script>
</body>
</html>
"""


def main():
    print(f"📅 繪圖範圍：近 {MONTHS_RANGE} 個月（{months_ago(MONTHS_RANGE).strftime('%Y-%m-%d')} ~ {datetime.now().strftime('%Y-%m-%d')}）")

    chart_data = load_all_stocks_data(DATA_DIR)
    if not chart_data:
        print(f"❌ 在 {DATA_DIR} 找不到任何個股資料檔（data/{{股票代號}}.json）。")
        print("   請先執行 main.py 抓取資料。")
        return

    print(f"📈 找到 {len(chart_data)} 檔股票：{', '.join(chart_data.keys())}")

    html = build_html(chart_data)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ 圖表已成功產生：{OUTPUT_HTML}")
    print("   全市場熱力儀表板：包含 Tier 1 熱力圖總覽、快捷股票膠囊列、Tier 2 單股儀表板與 Tier 3 明細頁。")


if __name__ == "__main__":
    main()
