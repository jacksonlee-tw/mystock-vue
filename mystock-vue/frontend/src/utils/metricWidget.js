// 指標 key → StockCharts.vue 圖表舞台的 widget id（對應其 widgetDefinitions 的 id）。
// 個股頁「點盤面摘要某一列就切換圖表」與「標示目前圖表對應哪幾列指標」共用這一份對照，
// 避免 StockDashboard.vue 與 MetricSummaryStrip.vue 各寫一套、日後新增指標時只改到其中一邊。
export function widgetIdForMetric(metricKey) {
  if (['foreign_buy_sell', 'trust_buy_sell', 'dealer_buy_sell', 'institutional_total'].includes(metricKey)) return 'institutional';
  if (metricKey === 'institutional_amount_est') return 'amount';
  if (metricKey === 'margin_balance') return 'margin-long';
  if (metricKey === 'short_balance') return 'margin-short';
  if (metricKey === 'short_ratio') return 'short-ratio';
  if (metricKey === 'short_interest') return 'short';
  if (metricKey === 'institutional_holders') return 'holders';
  // 估值／市值排名（FR-1／FR-5）與月營收（FR-2）：導去對應趨勢圖分頁，不落回預設的 K 線圖（G-2）。
  // market_cap／mcap_rank 目前沒有專屬趨勢線，導去估值分頁至少維持在同一主題頁籤。
  if (['pe_ratio', 'pb_ratio', 'dividend_yield', 'market_cap', 'mcap_rank'].includes(metricKey)) return 'valuation';
  if (['revenue_yoy', 'revenue_mom'].includes(metricKey)) return 'revenue';
  return 'kline';
}
