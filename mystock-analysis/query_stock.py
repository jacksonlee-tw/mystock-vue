#!/usr/bin/env python
# -*- coding: utf-8 -*-
import yfinance as yf
from datetime import datetime

# 台積電股票代碼
tickers = ["2330.TW", "^TWII"]  # 台灣上市 + 台灣指數
target_date = "2026-05-04"

print("=" * 60)
print(f"查詢日期: {target_date}")
print("=" * 60)

for ticker in tickers:
    print(f"\n嘗試取得 {ticker} 資料...")
    stock = yf.Ticker(ticker)
    
    # 先查詢特定日期
    hist = stock.history(start=target_date, end=target_date)
    
    if not hist.empty:
        print(f"\n✅ {ticker} 於 {target_date} 的資料:")
        print(f"  開盤價: {hist['Open'].iloc[0]:.2f}")
        print(f"  最高價: {hist['High'].iloc[0]:.2f}")
        print(f"  最低價: {hist['Low'].iloc[0]:.2f}")
        print(f"  收盤價: {hist['Close'].iloc[0]:.2f}")
        print(f"  成交量: {int(hist['Volume'].iloc[0])}")
        break
    else:
        # 查詢最近資料
        hist_recent = stock.history(period="6mo")
        if not hist_recent.empty:
            latest_date = hist_recent.index[-1].strftime("%Y-%m-%d")
            latest_close = hist_recent['Close'].iloc[-1]
            print(f"  ⓘ 查詢日期無資料")
            print(f"  最近交易日: {latest_date}")
            print(f"  收盤價: {latest_close:.2f} TWD")
            
            # 顯示過去 5 天資料
            print(f"\n  過去 5 天資料:")
            for idx, row in hist_recent.tail(5).iterrows():
                print(f"    {idx.strftime('%Y-%m-%d')}: {row['Close']:.2f}")
            break
        else:
            print(f"  ❌ 無法取得 {ticker} 的資料")

print("\n" + "=" * 60)
