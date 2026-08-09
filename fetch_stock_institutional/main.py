"""
主程式進入點：
    1.（選用）呼叫 institutional_fetcher 抓取三大法人資料並存檔
       （CSV 快照 + 依股票代號分檔、可累積歷史的 JSON）
    2. 呼叫 plot_chart 依 data/ 目錄現有資料重新產生互動式曲線圖 HTML

預設「不抓資料」，只用既有資料重畫圖表——重畫圖表不會動到 data/，
而抓取會連線證交所、耗時且有次數限制，因此改為明確加參數才執行。

唯一的例外是「.env 的 STOCK_CODES 有股票從未抓過資料」（例如剛新增一檔 2317）：
這種情況圖表上根本畫不出那檔股票，所以啟動時會主動詢問要不要現在抓。

用法：
    python main.py            # 只重新產生圖表（不連線抓資料）
    python main.py --fetch    # 先抓取最新資料，再產生圖表
    python main.py -f         # 同上（縮寫）
"""
import argparse
import sys

import institutional_fetcher
import plot_chart


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="抓取三大法人買賣超資料並產生互動式圖表（預設不抓資料，只重畫圖表）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="範例：\n"
               "  python main.py            只用 data/ 現有資料重新產生圖表\n"
               "  python main.py --fetch    先向證交所抓取最新資料，再產生圖表\n"
               "\n"
               "若 .env 的 STOCK_CODES 中有從未抓過資料的股票，未加 --fetch 時會先詢問。",
    )
    parser.add_argument(
        "-f", "--fetch",
        action="store_true",
        help="抓取最新的三大法人資料後再產生圖表（預設：不抓取）",
    )
    return parser.parse_args(argv)


def confirm_fetch_for_new_stocks() -> bool:
    """
    檢查 .env 的 STOCK_CODES 裡有沒有「還沒抓過資料」的股票；有的話詢問使用者
    要不要現在抓，回傳使用者的決定（沒有新股票則直接回傳 False，不打擾使用者）。

    非互動環境（stdin 不是終端機，例如排程或管線執行）不會卡住等輸入，
    改為印出提示後視同「否」，避免自動化流程無限等待。
    """
    missing = institutional_fetcher.find_stocks_without_data()
    if not missing:
        return False

    print(f"🆕 偵測到 {len(missing)} 檔股票尚未抓過資料：{', '.join(missing)}")
    print("   （.env 的 STOCK_CODES 有設定，但 data/ 下沒有對應的資料檔，圖表上會缺這幾檔）")

    if not sys.stdin.isatty():
        print("⚠️ 非互動模式，略過詢問。如需抓取請執行：python main.py --fetch")
        return False

    try:
        answer = input("❓ 是否要現在抓取資料？(y/N) ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n已取消，不抓取。")
        return False

    if answer in ("y", "yes"):
        return True
    print("   好，這次不抓。之後要抓可以執行：python main.py --fetch")
    return False


def main(argv=None):
    args = parse_args(argv)

    # 抓取範圍一律是 .env 的完整清單，不會只抓新股票：T86 是全市場的單日快照，
    # 只抓新股票的請求次數完全一樣，卻會錯過順便補齊其他股票缺漏日期的機會。
    should_fetch = args.fetch or confirm_fetch_for_new_stocks()

    if should_fetch:
        institutional_fetcher.fetch_and_save()
    else:
        print("⏭️ 略過資料抓取，直接以 data/ 現有資料產生圖表。")
        print("   若要抓取最新資料，請執行：python main.py --fetch\n")

    plot_chart.main()


if __name__ == "__main__":
    main()
