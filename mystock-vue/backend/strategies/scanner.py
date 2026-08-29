"""策略掃描主邏輯（選股功能與爬蟲 規格書 §4、§7、§13、§14）。

流程：
1. 讀取 YAML 策略定義（區分 watchlist 與 universe 選股池）
2. 若有 universe 策略，透過 MarketRepository.preload_market_data() 批次預載行情、估值與營收
3. 逐標的透過 ChipDataProvider 組成 ScanContext
4. 逐策略逐條件執行評估
5. 通過濾網計算訊號強度
6. 選股日榜上限截斷（max_picks_per_day）與排序（sort_by），僅對入選標的記錄冷卻
7. 寫入警示／選股記錄
"""
import asyncio
from datetime import date, datetime, timedelta
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import repositories.alert_repository as alert_repository
from config import get_alert_cooldown_days, get_target_stocks
from repositories.market_repository import MarketRepository
from services.chip_provider import ChipDataProvider, MarketPreload, PositionContext
from strategies import cooldown as cooldown_mod
from strategies.config_loader import StrategyDef, load_strategy_config
from strategies.direction import classify_direction, to_signal_type
from strategies.filters import evaluate_filters
from strategies.registry import CONDITION_REGISTRY

logger = logging.getLogger("mystock-backend")

_SUGGESTED_ACTION_TEMPLATES = {
    # 均線技術面
    ("price_cross_ma", "bullish"): "可納入多頭觀察清單，停損參考 MA{ma_period} 下 3%（{stop_loss}）",
    ("price_cross_ma", "bearish"): "跌破 MA{ma_period}，建議減碼或設定停損觀察",
    ("ma_golden_death_cross", "bullish"): "均線黃金交叉，趨勢轉強訊號，可留意進場時機",
    ("ma_golden_death_cross", "bearish"): "均線死亡交叉，趨勢轉弱，建議降低持股比重",
    ("ma_alignment", "bullish"): "均線多頭排列成形，動能轉強，可列入強勢股觀察",
    ("ma_alignment", "bearish"): "均線空頭排列成形，趨勢偏弱，不宜逢低攤平",
    ("ma_squeeze_breakout", "bullish"): "均線糾結後帶量突破，留意起漲點",
    ("extreme_bias", "bearish"): "正乖離過大，短線過熱，留意獲利了結賣壓",
    ("extreme_bias", "bullish"): "負乖離過大，超跌可能醞釀反彈，留意止跌訊號",
    ("ma_pullback_support", "bullish"): "回踩均線支撐未破，為趨勢股拉回找買點的參考時機",
    # 籌碼面
    ("chip_bottom_turnover", "bullish"): "融資去化、法人同步進場，籌碼面止穩，留意底部反轉契機",
    ("chip_short_squeeze", "bullish"): "券資比與融券同步走高，留意軋空行情，但反噬急殺風險亦高，不宜追高",
    ("chip_distribution_top", "bearish"): "法人連續賣超、融資餘額創新高，留意高檔出貨風險，建議降低持股",
    ("fundamental_revenue_decline", "bearish"): "營收年增率連續轉負，原始成長邏輯可能失效，建議重新評估持股並留意後續季報",
    # KD 隨機指標
    ("kd_oversold_golden_cross", "bullish"): "KD 於超賣區黃金交叉，短線動能可能轉強；建議確認是否站上 MA{ma_period} 再行進場",
    ("kd_overbought_death_cross", "bearish"): "KD 於超買區死亡交叉，短線動能轉弱，留意獲利了結賣壓",
    # MACD／RSI（Phase1-基礎量化與技術面 設計文件 §9 Q-1／Q-3：RSI 門檻採業界慣用 70/30）
    ("macd_golden_cross", "bullish"): "MACD 出現黃金交叉（DIF 上穿訊號線），中期動能轉強，可留意進場時機",
    ("macd_death_cross", "bearish"): "MACD 出現死亡交叉（DIF 下穿訊號線），中期動能轉弱，建議降低持股比重",
    ("rsi_oversold_recovery", "bullish"): "RSI 由超賣區（30 以下）回升，短線止跌訊號浮現，可留意反彈機會",
    ("rsi_overbought_reversal", "bearish"): "RSI 由超買區（70 以上）回落，短線動能轉弱，留意獲利了結賣壓",
    # ── 選股策略範本（選股功能與爬蟲 規格書 §13）────────────────────────
    ("pick_valuation_low_pe", "bullish"): "低本益比/高殖利率價值選股標的，基本面估值偏低，具安全邊際",
    ("pick_revenue_growth_momentum", "bullish"): "營收連續高成長，營運動能充沛，可搭配技術面均線支撐逢低買進",
    ("pick_chip_institutional_resonance", "bullish"): "外資與投信法人同步連續買超，籌碼集中度高，留意波段起漲機會",
    ("pick_multi_factor_resonance", "bullish"): "估值、營收與籌碼多因子共振精選標的，多頭排列成形，優先關注",
    # ── 相對低點承接（股價相對低點 需求規格書 §10.1）────────────────────
    ("pick_relative_low_zone", "bullish"): "已帶量站回 {ma_period}MA，可分批建立第一筆部位（建議 1/3），跌破 {stop_loss} 停損。",
    # ── 出場風控策略範本（選股功能與爬蟲 規格書 §6、§13）────────────────────
    ("exit_trailing_stop", "bearish"): "自持股最高點回檔超過停利門檻，建議執行移動停利、分批出場鎖定獲利",
    ("exit_fixed_stop_loss", "bearish"): "跌破平均持股成本達停損門檻，建議嚴格執行停損控制下檔風險",
    ("exit_time_stop", "bearish"): "持股時間已達上限但股價未有表現，資金效率偏低，建議轉移資金至強勢標的",
}

_CHIP_EXCLUDED_SYMBOL_PATTERN = re.compile(r"^00\d{2,4}[A-Za-z]?$")
_CHIP_EXCLUDED_SECURITY_KEYWORDS = ("ETF", "ETN", "TDR", "特別股", "受益證券")


def _is_chip_excluded(symbol: str, security_type: Optional[str] = None) -> bool:
    """排除 ETF/ETN/TDR/特別股/受益證券等籌碼語意不同的證券類別（ADR-SP-13）。
    優先依代碼主檔的 security_type 判斷（全市場掃描下能正確識別 TDR、特別股等代號規則抱不到的類別）；
    查無主檔資料時（例如尚未同步、或非 universe 掃描）退回既有代號正則。"""
    if security_type:
        return any(kw in security_type for kw in _CHIP_EXCLUDED_SECURITY_KEYWORDS)
    return bool(_CHIP_EXCLUDED_SYMBOL_PATTERN.match(symbol))


def _strength(passed_filter_count: int) -> str:
    if passed_filter_count >= 2:
        return "strong"
    if passed_filter_count == 1:
        return "moderate"
    return "weak"


def _suggested_action(strategy_id: str, direction: str, details: dict) -> str:
    template = _SUGGESTED_ACTION_TEMPLATES.get((strategy_id, classify_direction(direction)))
    if not template:
        template = _SUGGESTED_ACTION_TEMPLATES.get((strategy_id, "bullish")) or _SUGGESTED_ACTION_TEMPLATES.get((strategy_id, "bearish"))
    if not template:
        return ""
    ma_period = details.get("ma_period")
    ma_value = details.get("ma_value")
    ma_period_display = ma_period if ma_period is not None else "—"
    stop_loss = round(ma_value * 0.97, 2) if ma_value else "—"
    try:
        return template.format(ma_period=ma_period_display, stop_loss=stop_loss)
    except Exception:
        return template


def _extract_sort_metric(alert: dict, sort_by: Optional[str]) -> float:
    """從 alert details 中提取排序鍵值。"""
    if not sort_by:
        return 0.0
    details = alert.get("details", {})
    # 支援常用排序欄位
    if "pe" in sort_by:
        return float(details.get("pe_ratio") or 999.0)  # PE 越小越好
    if "yield" in sort_by:
        return -float(details.get("dividend_yield") or 0.0)  # 殖利率越大越好
    if "yoy" in sort_by:
        return -float(details.get("yoy_percent") or details.get("revenue_yoy") or -999.0)  # YoY 越大越好
    if "chip" in sort_by or "ratio" in sort_by:
        return -float(details.get("foreign_net_ratio") or details.get("trust_net_ratio") or details.get("institutional_sum") or 0.0)
    return 0.0


async def scan_market(
    market: str,
    lookback_days: Optional[int] = None,
    symbols: Optional[List[str]] = None,
    universe_tier: Optional[str] = None,
) -> Dict[str, Any]:
    started = time.perf_counter()
    cfg = load_strategy_config()
    lookback = lookback_days or cfg.defaults.get("lookback_days", 1)
    ma_periods = cfg.defaults.get("ma_periods", [5, 10, 20, 60, 120, 240])
    volume_ma_period = cfg.defaults.get("volume_ma_period", 5)
    cooldown_days = get_alert_cooldown_days()
    kd_params = [tuple(p) for p in cfg.defaults.get("kd_params", [])]
    kd_warmup_bars = cfg.defaults.get("kd_warmup_bars", 25)
    kd_smoothing = cfg.defaults.get("kd_smoothing", "wilder_1_3")
    # MACD／RSI（Phase1-基礎量化與技術面 設計文件 §9 Q-1）：defaults 只有單一組 MACD 參數
    # （非 kd_params 那種允許多組的 list of list），包成單元素 list 比照 ChipDataProvider.get_bars()
    # 對 macd_params 的介面（Dict[Tuple, MACDSeries] 鍵集合）。
    macd_params = [tuple(cfg.defaults.get("macd_params", [12, 26, 9]))]
    rsi_periods = cfg.defaults.get("rsi_periods", [6, 14])

    strategies = cfg.enabled_for_market(market)
    provider = ChipDataProvider()
    market_repo = MarketRepository()

    # 1. 區分選股池範圍：watchlist 策略 vs universe 策略
    has_universe_strategy = any(s.scope == "universe" for s in strategies)
    # 選股/籌碼策略需要的估值/營收序列只在有 universe 策略時才組裝，既有純技術面/籌碼面
    # 掃描（scope="watchlist"）維持零額外成本（見 ScanContext.get_bars() 的 with_valuation 說明）。
    needs_valuation = has_universe_strategy
    watchlist_symbols = symbols or get_target_stocks(market=market)

    # 2. 若有 universe 策略且為台股，準備全市場預載快取
    universe_preload: Optional[MarketPreload] = None
    all_scan_symbols = list(watchlist_symbols)
    security_type_map: Dict[str, Optional[str]] = {}

    if has_universe_strategy and market == "tw":
        try:
            # 取得全市場股票代號清單（排除 ETF 若策略需要）
            from repositories.stock_repository import StockRepository
            stock_repo = StockRepository()
            all_sym_rows = await stock_repo.list_symbols(market_type=market)
            universe_symbols = [r["symbol"] for r in all_sym_rows if r.get("status") == "active"]
            security_type_map = {r["symbol"]: r.get("security_type") for r in all_sym_rows}
            if not universe_symbols:
                universe_symbols = list(watchlist_symbols)

            # 批次預載近 90 天數據（避免 N+1 查詢）
            end_date = date.today()
            start_date = end_date - timedelta(days=120)
            logger.info(f"[選股掃描] 啟動全市場批次預載 ({len(universe_symbols)} 檔)...")
            raw_preloaded = await market_repo.preload_market_data(universe_symbols, start_date, end_date, market=market)
            universe_preload = MarketPreload(
                quotes=raw_preloaded.get("quotes", {}),
                valuation=raw_preloaded.get("valuation", {}),
                revenue=raw_preloaded.get("revenue", {}),
            )
            logger.info(f"[選股掃描] 全市場批次預載完成（{len(universe_preload.quotes)} 檔有行情記錄）")

            # 合併掃描標的
            all_scan_symbols = sorted(list(set(watchlist_symbols).union(set(universe_preload.quotes.keys()))))
        except Exception as e:
            logger.warning(f"[選股掃描] 全市場預載失敗，回退至追蹤清單: {e}")
            universe_preload = None

    existing_keys = alert_repository.load_existing_signal_keys()
    cooldown_state = alert_repository.load_cooldown_state()
    raw_candidates: List[Dict[str, Any]] = []

    # 3. 逐標的掃描
    for symbol in all_scan_symbols:
        is_watchlist = symbol in watchlist_symbols
        # 決定預載來源
        preload_src = universe_preload if (universe_preload and symbol in universe_preload.quotes) else None

        try:
            ctx = await provider.get_bars(
                symbol, market, ma_periods, volume_ma_period,
                kd_params=kd_params, kd_warmup_bars=kd_warmup_bars, kd_smoothing=kd_smoothing,
                macd_params=macd_params, rsi_periods=rsi_periods,
                with_valuation=needs_valuation, preloaded=preload_src,
            )
        except Exception as e:
            logger.warning(f"[策略引擎] 取得 {symbol} 資料失敗，已略過: {e}")
            continue
        if ctx is None:
            continue

        start_idx = max(0, ctx.length - lookback)

        for strategy in strategies:
            # 作用範圍過濾：watchlist 策略不跑非追蹤清單標的
            if strategy.scope == "watchlist" and not is_watchlist:
                continue

            # 籌碼與選股類策略排除 ETF/ETN/TDR/特別股/受益證券
            if strategy.category in {"chip", "stock_picking"} and _is_chip_excluded(symbol, security_type_map.get(symbol)):
                continue

            effective_cooldown = strategy.cooldown_days if strategy.cooldown_days is not None else cooldown_days

            for condition_cfg in strategy.conditions:
                # 防呆（股價相對低點 需求規格書 §2.3-1／AC-10）：conditions 若被誤寫成 dict
                # （例如三個面向各自一個 key），迭代出的會是字串 key，下面 .get("type") 會
                # 拋 AttributeError 且中斷整個 scan_market()。改為記警告後略過該筆設定，
                # 不讓單一策略的設定錯誤拖垮當日所有策略的掃描。
                if not isinstance(condition_cfg, dict):
                    logger.warning(f"[策略引擎] 策略 {strategy.id} 的 condition 設定格式錯誤（非物件，型別={type(condition_cfg).__name__}），已略過: {condition_cfg!r}")
                    continue

                spec = CONDITION_REGISTRY.get(condition_cfg.get("type"))
                if not spec:
                    continue

                if ctx.length < spec.min_bars:
                    continue
                if any(not getattr(ctx, field_name, None) for field_name in spec.requires):
                    continue

                for idx in range(start_idx, ctx.length):
                    try:
                        signals = spec.func(ctx, idx, condition_cfg)
                    except Exception as e:
                        logger.warning(f"[策略引擎] 條件 {spec.type} 評估失敗 ({symbol}): {e}")
                        continue
                    if not signals:
                        continue

                    trade_date = ctx.dates[idx]
                    for signal in signals:
                        direction = signal["direction"]
                        dedup_key = (symbol, strategy.id, direction, trade_date)
                        if dedup_key in existing_keys:
                            continue

                        cd_key = cooldown_mod.cooldown_key(symbol, strategy.id, direction)
                        if cooldown_mod.is_active(cooldown_state, cd_key, trade_date, effective_cooldown):
                            continue

                        passed_filters = evaluate_filters(strategy.filters, ctx, idx)
                        details = signal.get("details", {})

                        raw_candidates.append({
                            "stock_id": symbol,
                            "stock_name": ctx.name,
                            "market": market,
                            "strategy_id": strategy.id,
                            "strategy_name": strategy.name,
                            "category": strategy.category,
                            "direction": direction,
                            "signal_type": to_signal_type(direction),
                            "signal_strength": _strength(len(passed_filters)),
                            "trade_date": trade_date,
                            "details": details,
                            "filters_passed": passed_filters,
                            "suggested_action": _suggested_action(strategy.id, direction, details),
                            "dedup_key": dedup_key,
                            "cd_key": cd_key,
                            "max_picks": strategy.max_picks_per_day,
                            "sort_by": strategy.sort_by,
                        })

    # 4. 選股日榜上限截斷（max_picks_per_day）與排序（§7.3）
    # 依 (strategy_id, trade_date) 分組處理
    groups: Dict[Tuple[str, str], List[dict]] = {}
    for item in raw_candidates:
        groups.setdefault((item["strategy_id"], item["trade_date"]), []).append(item)

    final_alerts: List[Dict[str, Any]] = []

    for (strat_id, t_date), items in groups.items():
        max_picks = items[0].get("max_picks")
        sort_by = items[0].get("sort_by")

        # 排序
        if sort_by:
            items.sort(key=lambda x: _extract_sort_metric(x, sort_by))

        # 截斷
        kept = items[:max_picks] if max_picks else items

        for rank_idx, alert_item in enumerate(kept, start=1):
            alert_item["rank_value"] = rank_idx
            # 寫入冷卻狀態（只有真正入選並輸出的才進冷卻，§7.3）
            existing_keys.add(alert_item["dedup_key"])
            cooldown_mod.mark(cooldown_state, alert_item["cd_key"], alert_item["trade_date"])

            # 移除暫存鍵
            alert_to_save = dict(alert_item)
            alert_to_save.pop("dedup_key", None)
            alert_to_save.pop("cd_key", None)
            alert_to_save.pop("max_picks", None)
            alert_to_save.pop("sort_by", None)
            final_alerts.append(alert_to_save)

    finalized = alert_repository.append_alerts(final_alerts)
    if final_alerts:
        alert_repository.save_cooldown_state(cooldown_state)

    return {
        "scanned_stocks": len(all_scan_symbols),
        "alerts_generated": len(finalized),
        "scan_duration_ms": int((time.perf_counter() - started) * 1000),
        "alerts": finalized,
    }


async def scan_positions(market: str = "tw") -> Dict[str, Any]:
    """持倉出場風控策略掃描（選股功能與爬蟲 規格書 §6、§13、§14 P2）。
    讀取記帳模組中的真實持倉，注入 PositionContext 執行移動停利、固定停損與時間停損。
    """
    started = time.perf_counter()
    from db.session import get_async_session
    from repositories.portfolio_repository import PortfolioRepository
    from services.portfolio_ledger import build_ledger, Settings

    # 1. 取得持倉
    async with get_async_session() as session:
        p_repo = PortfolioRepository(session)
        txs = await p_repo.list_transactions(market=market)
        divs = await p_repo.list_dividends(market=market)
        settings_dict = await p_repo.get_settings()
        settings = Settings(**{k: v for k, v in settings_dict.items() if hasattr(Settings, k)})

    ledger = build_ledger(txs, divs, settings)
    active_positions = [p for p in ledger.positions if p.get("market") == market and float(p.get("shares", 0)) > 0]

    if not active_positions:
        return {"scanned_positions": 0, "alerts_generated": 0, "alerts": []}

    cfg = load_strategy_config()
    risk_strategies = [s for s in cfg.enabled_for_market(market) if s.category in {"risk", "fundamental"}]
    provider = ChipDataProvider()
    cooldown_state = alert_repository.load_cooldown_state()
    existing_keys = alert_repository.load_existing_signal_keys()

    new_alerts: List[Dict[str, Any]] = []

    for pos in active_positions:
        symbol = pos["symbol"]
        shares = float(pos["shares"])
        avg_cost = float(pos.get("avg_cost", 0.0))

        # 取出該持股完整的日 K 棒
        ctx = await provider.get_bars(symbol, market, [5, 10, 20, 60], volume_ma_period=5, with_valuation=True)
        if not ctx or ctx.length == 0:
            continue

        # 計算進場後交易日數與最高收盤價
        # 若無明確 entry_date 則推算
        first_buy_date = str(pos.get("first_buy_date") or ctx.dates[0])
        entry_idx = 0
        for i, d in enumerate(ctx.dates):
            if d >= first_buy_date:
                entry_idx = i
                break

        holding_days = max(1, ctx.length - entry_idx)
        since_closes = [c for c in ctx.closes[entry_idx:] if c is not None]
        peak_close = max(since_closes) if since_closes else (ctx.closes[-1] or avg_cost)
        curr_close = ctx.closes[-1] or 0.0
        unrealized_pct = ((curr_close - avg_cost) / avg_cost * 100.0) if avg_cost > 0 else 0.0

        pos_ctx = PositionContext(
            symbol=symbol,
            market=market,
            shares=shares,
            avg_cost=avg_cost,
            entry_date=first_buy_date,
            holding_trading_days=holding_days,
            peak_close_since_entry=peak_close,
            unrealized_return_pct=unrealized_pct,
        )

        ctx.position = pos_ctx
        idx = ctx.length - 1
        trade_date = ctx.dates[idx]

        for strategy in risk_strategies:
            effective_cooldown = strategy.cooldown_days or 5
            for condition_cfg in strategy.conditions:
                if not isinstance(condition_cfg, dict):
                    logger.warning(f"[風控掃描] 策略 {strategy.id} 的 condition 設定格式錯誤（非物件，型別={type(condition_cfg).__name__}），已略過: {condition_cfg!r}")
                    continue

                spec = CONDITION_REGISTRY.get(condition_cfg.get("type"))
                if not spec or ctx.length < spec.min_bars:
                    continue

                try:
                    signals = spec.func(ctx, idx, condition_cfg)
                except Exception as e:
                    logger.warning(f"[風控掃描] 條件 {spec.type} 評估失敗 ({symbol}): {e}")
                    continue

                for signal in signals:
                    direction = signal["direction"]
                    dedup_key = (symbol, strategy.id, direction, trade_date)
                    if dedup_key in existing_keys:
                        continue

                    cd_key = cooldown_mod.cooldown_key(symbol, strategy.id, direction)
                    if cooldown_mod.is_active(cooldown_state, cd_key, trade_date, effective_cooldown):
                        continue

                    details = signal.get("details", {})
                    new_alerts.append({
                        "stock_id": symbol,
                        "stock_name": ctx.name,
                        "market": market,
                        "strategy_id": strategy.id,
                        "strategy_name": strategy.name,
                        "category": strategy.category,
                        "direction": direction,
                        "signal_type": "SELL",
                        "signal_strength": "strong",
                        "trade_date": trade_date,
                        "details": details,
                        "filters_passed": [],
                        "suggested_action": _suggested_action(strategy.id, direction, details),
                    })
                    existing_keys.add(dedup_key)
                    cooldown_mod.mark(cooldown_state, cd_key, trade_date)

    finalized = alert_repository.append_alerts(new_alerts)
    if new_alerts:
        alert_repository.save_cooldown_state(cooldown_state)

    return {
        "scanned_positions": len(active_positions),
        "alerts_generated": len(finalized),
        "scan_duration_ms": int((time.perf_counter() - started) * 1000),
        "alerts": finalized,
    }


def scan_market_sync(
    market: str,
    lookback_days: Optional[int] = None,
    symbols: Optional[List[str]] = None,
    universe_tier: Optional[str] = None,
) -> Dict[str, Any]:
    return asyncio.run(scan_market(market, lookback_days=lookback_days, symbols=symbols, universe_tier=universe_tier))


def scan_positions_sync(market: str = "tw") -> Dict[str, Any]:
    return asyncio.run(scan_positions(market))

