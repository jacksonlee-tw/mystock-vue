<template>
  <div class="space-y-3">
    <!-- 日期區間只在此顯示一次 -->
    <div v-if="dateRangeText" class="flex justify-end">
      <span class="num text-xs font-semibold text-surface-600 dark:text-surface-300 bg-surface-100 dark:bg-surface-800 px-2.5 py-1 rounded-lg border border-surface-200 dark:border-surface-700">
        <i class="pi pi-calendar text-[10px] mr-1 text-primary"></i>{{ dateRangeText }}
      </span>
    </div>

    <!-- 單一圖表舞台：一次只顯示一張圖，用上方頁籤切換或點選 KPI 卡（見 StockDashboard.vue）。
         所有圖表共用同一個固定高度容器，大小格式統一，不再逐張堆疊成長頁。 -->
    <div ref="chartCardRef" class="card shadow-sm border border-surface-200 dark:border-surface-700 rounded-xl bg-surface-0 dark:bg-surface-900 overflow-hidden">
      <div class="flex flex-wrap items-center gap-0.5 px-3 pt-2.5 pb-2 border-b border-surface-100 dark:border-surface-800 bg-surface-50/60 dark:bg-surface-800/30">
        <button
          v-for="w in availableWidgets"
          :key="w.id"
          :id="'widget-' + w.id"
          type="button"
          @click="activeId = w.id"
          :class="[
            'px-3 py-1.5 text-xs font-bold rounded-md flex items-center gap-1.5 transition-all duration-150',
            activeId === w.id
              ? 'bg-primary text-primary-contrast shadow-sm'
              : 'text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-0'
          ]"
        >
          <i :class="['pi', w.icon]"></i> {{ w.title }}
        </button>

        <!-- KD 副圖開關（KD指標 設計規格書 §7.2）：只在 K 線頁籤顯示；資料筆數不足暖身期時停用並提示原因 -->
        <button
          v-if="activeId === 'kline'"
          type="button"
          @click="toggleKd"
          :disabled="!kdAvailable"
          :aria-pressed="kdVisible"
          :title="kdAvailable ? 'KD 隨機指標副圖' : '資料筆數不足，無法計算 KD'"
          :class="[
            'ml-auto px-2.5 py-1 text-xs font-bold rounded-md flex items-center gap-1 transition-colors',
            !kdAvailable
              ? 'text-surface-300 dark:text-surface-600 cursor-not-allowed'
              : kdVisible
                ? 'bg-primary/10 text-primary'
                : 'text-surface-500 hover:text-primary hover:bg-surface-100 dark:hover:bg-surface-800'
          ]"
        >
          <i class="pi pi-chart-line text-xs"></i> KD
        </button>

        <!-- 放大：導去獨立的圖表明細頁（仍保留大圖檢視能力，只是不再是預設呈現方式） -->
        <button
          v-if="activeWidget?.route"
          type="button"
          @click="goToDetail(activeWidget.route)"
          :class="['p-1.5 text-surface-400 hover:text-primary hover:bg-surface-100 dark:hover:bg-surface-800 rounded-md transition-colors', activeId === 'kline' ? '' : 'ml-auto']"
          title="放大檢視此圖表"
        >
          <i class="pi pi-window-maximize text-xs"></i>
        </button>
      </div>

      <div class="p-4">
        <div v-if="activeId === 'kline'" class="flex items-center justify-end gap-3 text-[11px] font-semibold text-surface-500 mb-2">
          <span class="flex items-center gap-1"><i class="inline-block w-2 h-2 rounded-sm" :style="{ background: upDown.up }"></i>上漲</span>
          <span class="flex items-center gap-1"><i class="inline-block w-2 h-2 rounded-sm" :style="{ background: upDown.down }"></i>下跌</span>
        </div>

        <v-chart
          v-if="activeWidget && !activeWidget.emptyPlaceholder"
          ref="chartRef"
          :class="['chart-container-stage', { 'chart-container-stage--kd': kdSubchartActive }]"
          :option="getOption(activeId)"
          :update-options="{ notMerge: true }"
          autoresize
        />
        <div v-else-if="activeWidget?.emptyPlaceholder" class="chart-container-stage flex items-center justify-center text-center text-surface-500 px-6">
          {{ activeWidget.emptyPlaceholder }}
        </div>

        <ChartExplanationBlock v-if="activeWidget && chartExplanations[activeId]" :explanation="chartExplanations[activeId]" />
        <ChartExplanationBlock v-if="kdSubchartActive && chartExplanations.kd" :explanation="chartExplanations.kd" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart, LineChart, CandlestickChart } from 'echarts/charts';
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  MarkPointComponent,
  MarkLineComponent,
  MarkAreaComponent
} from 'echarts/components';
import VChart from 'vue-echarts';

import { useRoute, useRouter } from 'vue-router';
import { getUpDownColor } from '@/utils/marketColors';
import { buildMovingAverageSeries } from '@/utils/movingAverage';
import { chartExplanations } from '@/utils/chartExplanations';
import { directionVisual, formatDirectionLabel } from '@/utils/alertDirection';
import { alertApi } from '@/service/alertApi';
import ChartExplanationBlock from '@/components/ChartExplanationBlock.vue';

use([
  CanvasRenderer,
  BarChart,
  LineChart,
  CandlestickChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  MarkPointComponent,
  MarkLineComponent,
  MarkAreaComponent
]);

const router = useRouter();
const route = useRoute();

const props = defineProps({
  chartData: {
    type: Object,
    required: true
  },
  stockId: String,
  period: String,
  months: Number,
  market: String, // 'tw' | 'us'；未提供時 getUpDownColor 退回台股慣例
  modelValue: { type: String, default: null }, // 目前顯示中的圖表 id（v-model，供父層 KPI 卡點選切換）
  kind: { type: String, default: 'stock' } // 'stock' | 'index'：決定「放大檢視」導去 /stock/... 還是 /index/...（大盤指數功能規劃書 ADR-I1，同一元件重用）
});

const emit = defineEmits(['update:modelValue']);

const upDown = computed(() => getUpDownColor(props.market));

// id 對應到 chartExplanations.js 的 key，兩邊要一致。panel 對應後端 meta.panels，
// 用來依市場（台股／美股）決定要顯示哪些頁籤——'always' 一律顯示。
const widgetDefinitions = [
  { id: 'kline', title: 'K 線圖 (蠟燭圖)', icon: 'pi-chart-bar', route: 'kline', panel: 'always' },
  { id: 'institutional', title: '三大法人買賣超', icon: 'pi-users', route: 'institutional', panel: 'institutional' },
  { id: 'amount', title: '估算買賣超金額', icon: 'pi-dollar', route: 'amount', panel: 'institutional' },
  { id: 'margin-long', title: '融資餘額', icon: 'pi-chart-line', route: 'margin-long', panel: 'margin' },
  { id: 'margin-short', title: '融券餘額', icon: 'pi-sort-alt', route: 'margin-short', panel: 'margin' },
  { id: 'short-ratio', title: '券資比', icon: 'pi-percentage', route: 'short-ratio', panel: 'margin' },
  { id: 'short', title: '空頭持倉', icon: 'pi-sort-alt', panel: 'short', emptyPlaceholder: '歷史空頭趨勢圖表即將支援' },
  { id: 'holders', title: '機構持股', icon: 'pi-users', panel: 'holders', emptyPlaceholder: '歷史機構持股趨勢圖表即將支援' },
  // 指數專用（大盤指數功能規劃書 FR-IDX-04）：panel='index' 只在後端 meta.panels 含 'index' 時出現，
  // 目前只有指數的 chart-data 會回傳這個 panel（見 services/index_service.py 的 get_index_chart_data）。
  { id: 'index-turnover', title: '成交金額', icon: 'pi-dollar', route: 'index-turnover', panel: 'index' }
];

const availableWidgets = computed(() => {
  const activePanels = props.chartData?.meta?.panels || ['institutional', 'margin'];
  return widgetDefinitions.filter((w) => w.panel === 'always' || activePanels.includes(w.panel));
});

// 目前顯示中的圖表：優先吃 v-model，若父層沒傳或傳了目前市場沒有的 id，退回第一個可用頁籤。
const activeId = computed({
  get() {
    if (props.modelValue && availableWidgets.value.some((w) => w.id === props.modelValue)) {
      return props.modelValue;
    }
    return availableWidgets.value[0]?.id || 'kline';
  },
  set(id) {
    emit('update:modelValue', id);
  }
});

const activeWidget = computed(() => availableWidgets.value.find((w) => w.id === activeId.value) || null);

// AI 診股報告擷圖（AI 技術分析報告 系統開發規格書 §4.1）：<v-chart> 是同一個元素隨 activeId
// 切換 option 重畫，不是每個頁籤各自一個實例，所以只要目前有任一非 emptyPlaceholder 的圖表
// 顯示中，chartRef 就是有效的 ECharts 實例。vue-echarts v8 會把 getDataURL 等方法代理到這個
// template ref 上，不需要另外引入截圖套件。
const chartRef = ref(null);
const chartCardRef = ref(null);

async function captureKlineImage() {
  if (activeId.value !== 'kline') {
    activeId.value = 'kline'; // 沿用既有的頁籤切換路徑，不卸載內容區塊（CLAUDE.md 鐵則 1 的同一條原則）
  }
  // 等兩次 tick：第一次讓 Vue 把 activeId 的變動流過 v-model 反映回 props，
  // 第二次讓 vue-echarts 對新 option 完成 setOption／重繪，避免擷到切換前的畫面。
  await nextTick();
  await nextTick();
  if (!chartRef.value) return null;

  // 背景色不可透明：ECharts 預設透明底轉 PNG 後，深色主題下的文字會落在透明底上幾乎讀不到。
  // 直接讀卡片元素目前解析出的實際背景色，不寫死色碼，明暗主題與未來換色都會自動跟著對。
  let backgroundColor = '#ffffff';
  if (chartCardRef.value) {
    const resolved = getComputedStyle(chartCardRef.value).backgroundColor;
    if (resolved && resolved !== 'rgba(0, 0, 0, 0)' && resolved !== 'transparent') {
      backgroundColor = resolved;
    }
  }

  const dataUrl = chartRef.value.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor });
  return dataUrl.replace(/^data:image\/png;base64,/, '');
}

defineExpose({ captureKlineImage });

// KD 副圖開關（KD指標 設計規格書 §7.2）：預設關閉、狀態存 localStorage；網址帶
// ?indicator=kd 時強制開啟（不寫回 localStorage），供警示看板跳轉使用（§7.5）。
const KD_VISIBLE_STORAGE_KEY = 'mystock:chart:kd-visible';
const kdVisible = ref(localStorage.getItem(KD_VISIBLE_STORAGE_KEY) === '1');

const kdData = computed(() => props.chartData?.kd || null);
// chartData.kd 一律會有 k/d 陣列（見 stock_service.get_stock_chart_payload()），但資料筆數
// 不足暖身期時會整組是 null——此時誠實停用開關，而不是畫一張空的 KD 副圖。
const kdAvailable = computed(() => !!kdData.value?.k?.some((v) => v != null));

// 警示看板 → 圖表跳轉（KD指標 設計規格書 §7.5）：?indicator=kd 強制開啟 KD 並切到 K 線頁籤；
// ?highlight=YYYY-MM-DD 在該日期畫一條貫穿主圖與 KD 副圖的垂直線。
watch(
  () => route.query.indicator,
  (indicator) => {
    if (indicator === 'kd') {
      kdVisible.value = true;
      activeId.value = 'kline';
    }
  },
  { immediate: true }
);
const highlightDate = computed(() => route.query.highlight || null);

function toggleKd() {
  if (!kdAvailable.value) return;
  kdVisible.value = !kdVisible.value;
  localStorage.setItem(KD_VISIBLE_STORAGE_KEY, kdVisible.value ? '1' : '0');
}

const kdSubchartActive = computed(() => activeId.value === 'kline' && kdVisible.value && kdAvailable.value);

function getOption(id) {
  switch (id) {
    case 'kline': return klineOption.value;
    case 'institutional': return institutionalOption.value;
    case 'amount': return estimatedAmountOption.value;
    case 'margin-long': return marginLongOption.value;
    case 'margin-short': return marginShortOption.value;
    case 'short-ratio': return shortRatioOption.value;
    case 'index-turnover': return indexTurnoverOption.value;
    default: return null;
  }
}

function goToDetail(chartType) {
  if (props.stockId && props.market) {
    const base = props.kind === 'index' ? '/index' : '/stock';
    router.push({
      path: `${base}/${props.market}/${props.stockId}/chart/${chartType}`,
      query: { period: props.period, months: props.months }
    });
  }
}

const dates = computed(() => props.chartData?.dates || []);

// K 線圖策略觸發標記（均線策略警示系統 設計文件第 9.2 節）。抓該檔近期警示，
// 疊在 candlestick series 上；抓不到（尚未掃描過、API 失敗等）不影響原本圖表渲染。
const stockAlerts = ref([]);

async function loadStockAlerts() {
  if (!props.stockId || !props.market) {
    stockAlerts.value = [];
    return;
  }
  try {
    const res = await alertApi.getAlerts({ symbol: props.stockId, market: props.market, days: 400 });
    stockAlerts.value = res.success ? res.data : [];
  } catch {
    stockAlerts.value = [];
  }
}

watch([() => props.stockId, () => props.market], loadStockAlerts, { immediate: true });

const alertMarkPoints = computed(() => {
  const dateIndex = new Map(dates.value.map((d, i) => [d, i]));
  return stockAlerts.value
    .filter((a) => dateIndex.has(a.trade_date))
    .map((a) => {
      const idx = dateIndex.get(a.trade_date);
      const candle = props.chartData?.kline?.[idx];
      const visual = directionVisual(a.direction);
      const bullish = visual.icon === 'pi-arrow-up';
      // markPoint 座標值只是用來把圖標定位在 K 棒之上/之下，不影響數值座標軸範圍
      const yValue = candle ? (bullish ? candle[3] : candle[2]) : null;
      return {
        name: `${a.strategy_name}：${formatDirectionLabel(a.direction)}`,
        coord: [idx, yValue],
        symbol: 'triangle',
        symbolRotate: bullish ? 0 : 180,
        symbolSize: 10,
        symbolOffset: [0, bullish ? -10 : 10],
        itemStyle: { color: bullish ? upDown.value.up : upDown.value.down }
      };
    })
    .filter((p) => p.coord[1] != null);
});

const dateRangeText = computed(() => {
  if (props.chartData?.start_date && props.chartData?.end_date) {
    return `${props.chartData.start_date} ~ ${props.chartData.end_date}`;
  }
  if (dates.value && dates.value.length > 0) {
    return `${dates.value[0]} ~ ${dates.value[dates.value.length - 1]}`;
  }
  return '';
});

// 三大法人買賣超 Option
const institutionalOption = computed(() => {
  const inst = props.chartData?.institutional || {};
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['外資', '投信', '自營商', '合計'], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '15%', top: '5%', containLabel: true },
    xAxis: { type: 'category', data: dates.value },
    yAxis: { type: 'value', name: '張' },
    series: [
      { name: '外資', type: 'bar', data: inst.foreign || [], itemStyle: { color: '#ef4444' } },
      { name: '投信', type: 'bar', data: inst.trust || [], itemStyle: { color: '#3b82f6' } },
      { name: '自營商', type: 'bar', data: inst.dealer || [], itemStyle: { color: '#f59e0b' } },
      { name: '合計', type: 'line', data: inst.total || [], itemStyle: { color: '#8b5cf6' }, lineStyle: { width: 3 } }
    ]
  };
});

// KD 副圖顏色（KD指標 設計規格書 §7.1）：K 線 indigo、D 線 pink，與 K 棒漲跌色
// （getUpDownColor）及三條均線色（#f59e0b/#0ea5e9/#8b5cf6）皆不重複。
const KD_K_COLOR = '#6366f1';
const KD_D_COLOR = '#ec4899';
const KD_BAND_COLOR = 'rgba(148, 163, 184, 0.12)'; // 超買/超賣區背景，低透明度中性灰，明暗主題皆可讀
const HIGHLIGHT_LINE_COLOR = '#7c3aed';

// 貫穿主圖與 KD 副圖的策略觸發垂直線（KD指標 設計規格書 §7.5）：同一個 markLine 定義各自掛在
// 兩個 grid 的其中一個 series 上；highlightDate 不在目前顯示區間內時，ECharts 對 category
// x 軸找不到對應值會直接不畫，不會報錯或畫錯位置。
function buildHighlightMarkLine() {
  if (!highlightDate.value) return undefined;
  return {
    silent: true,
    symbol: ['none', 'none'],
    lineStyle: { type: 'solid', color: HIGHLIGHT_LINE_COLOR, width: 1.5 },
    label: { show: false },
    data: [{ xAxis: highlightDate.value }]
  };
}

// K 線圖 (Candlestick) Option ── 疊加 5/20/60 期均線，標籤依目前聚合週期顯示「日/週/月均線」；
// KD 開啟時在下方加一個副圖 grid（同一個 ECharts 實例，非另開頁籤，見 §7.1）。
const klineOption = computed(() => {
  const kline = props.chartData?.kline || [];
  const ma = buildMovingAverageSeries(kline, props.period);
  const showKd = kdSubchartActive.value;
  const kd = kdData.value;

  const grid = showKd
    ? [
        { left: '3%', right: '4%', top: '10%', height: '50%', containLabel: true },
        { left: '3%', right: '4%', top: '68%', height: '16%', containLabel: true }
      ]
    : [{ left: '3%', right: '4%', top: '12%', bottom: '14%', containLabel: true }];

  const xAxis = [{ type: 'category', data: dates.value, gridIndex: 0 }];
  const yAxis = [{ type: 'value', scale: true, gridIndex: 0 }];
  if (showKd) {
    xAxis.push({ type: 'category', data: dates.value, gridIndex: 1, axisLabel: { show: false } });
    yAxis.push({ type: 'value', gridIndex: 1, min: 0, max: 100, interval: 50 });
  }

  const series = [
    {
      type: 'candlestick',
      xAxisIndex: 0,
      yAxisIndex: 0,
      data: kline,
      itemStyle: {
        color: upDown.value.up, // 陽線 (漲)
        color0: upDown.value.down, // 陰線 (跌)
        borderColor: upDown.value.up,
        borderColor0: upDown.value.down
      },
      // 策略觸發標記（均線策略警示系統 設計文件第 9.2 節）：▲ 綠色=偏多方向，▼ 紅色=偏空方向
      markPoint: {
        symbolSize: 10,
        data: alertMarkPoints.value,
        tooltip: { trigger: 'item', formatter: (p) => p.name }
      },
      markLine: buildHighlightMarkLine()
    },
    ...ma.series
  ];

  if (showKd) {
    series.push(
      {
        name: 'K',
        type: 'line',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: kd.k,
        smooth: false,
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1.5, color: KD_K_COLOR },
        itemStyle: { color: KD_K_COLOR },
        z: 3,
        markArea: {
          silent: true,
          itemStyle: { color: KD_BAND_COLOR },
          data: [
            [{ yAxis: kd.overbought }, { yAxis: 100 }],
            [{ yAxis: 0 }, { yAxis: kd.oversold }]
          ]
        },
        markLine: {
          silent: true,
          symbol: 'none',
          label: { show: false },
          lineStyle: { type: 'dashed', color: '#94a3b8', width: 1 },
          data: [{ yAxis: kd.overbought }, { yAxis: kd.oversold }]
        }
      },
      {
        name: 'D',
        type: 'line',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: kd.d,
        smooth: false,
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1.5, color: KD_D_COLOR },
        itemStyle: { color: KD_D_COLOR },
        z: 3,
        markLine: buildHighlightMarkLine()
      }
    );
  }

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: (params) => {
        const candle = params.find((p) => p.seriesType === 'candlestick') || params[0];
        if (!candle || !candle.data) return '';
        const date = candle.name;
        // candle.data 是 ECharts candlestick 內部的 raw value，格式為
        // [類別索引, open, close, low, high]（開頭多一個座標軸索引維度，不是我們傳入的 [open,close,low,high]），
        // 需去掉第 0 個索引維度，否則開盤價會顯示成 K 棒的索引序號。
        const [openRaw, closeRaw, lowRaw, highRaw] = candle.data.slice(1);
        const change = closeRaw - openRaw;
        const color = change >= 0 ? upDown.value.up : upDown.value.down;
        // 美股價格是原始浮點數（可能十幾位小數），統一只顯示到小數 2 位，避免撐爆 tooltip。
        const open = Number(openRaw).toFixed(2);
        const close = Number(closeRaw).toFixed(2);
        const low = Number(lowRaw).toFixed(2);
        const high = Number(highRaw).toFixed(2);
        let html = `
          <div class="font-bold">${date}</div>
          <div>開盤價: <span style="color:${color}">${open}</span></div>
          <div>最高價: <span style="color:${color}">${high}</span></div>
          <div>最低價: <span style="color:${color}">${low}</span></div>
          <div>收盤價: <span style="color:${color}">${close}</span> (${change >= 0 ? '+' : ''}${change.toFixed(2)})</div>
        `;

        // 均線與 KD 分開分組顯示，避免混在一起難以區分（KD指標 設計規格書 §7.1 tooltip 規格）。
        const maLines = params.filter((p) => p.seriesType === 'line' && p.data != null && p.seriesName !== 'K' && p.seriesName !== 'D');
        const kdLines = params.filter((p) => (p.seriesName === 'K' || p.seriesName === 'D') && p.data != null);

        if (maLines.length) {
          html += '<div class="mt-1 pt-1" style="border-top:1px dashed rgba(148,163,184,0.4)">';
          maLines.forEach((p) => { html += `${p.marker}${p.seriesName}: ${p.data}&nbsp;&nbsp;`; });
          html += '</div>';
        }
        if (kdLines.length) {
          html += '<div class="mt-1 pt-1" style="border-top:1px dashed rgba(148,163,184,0.4)">';
          kdLines.forEach((p) => { html += `${p.marker}${p.seriesName} ${Number(p.data).toFixed(2)}&nbsp;&nbsp;`; });
          const kVal = kdLines.find((p) => p.seriesName === 'K')?.data;
          if (kVal != null && kd) {
            if (kVal >= kd.overbought) html += '<span class="opacity-70">（超買）</span>';
            else if (kVal <= kd.oversold) html += '<span class="opacity-70">（超賣）</span>';
          }
          html += '</div>';
        }
        return html;
      }
    },
    legend: { data: ma.names, top: 0, right: 0, itemWidth: 14, itemHeight: 8, textStyle: { fontSize: 11 } },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    dataZoom: [
      { type: 'inside', start: 0, end: 100, xAxisIndex: showKd ? [0, 1] : [0] },
      { type: 'slider', start: 0, end: 100, height: 18, bottom: 4, xAxisIndex: showKd ? [0, 1] : [0] }
    ],
    grid,
    xAxis,
    yAxis,
    series
  };
});

// 估算買賣超金額 Option
const estimatedAmountOption = computed(() => {
  const amounts = props.chartData?.institutional?.estimated_amount || [];
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '10%', top: '5%', containLabel: true },
    xAxis: { type: 'category', data: dates.value },
    yAxis: { type: 'value', name: '萬元' },
    series: [
      {
        name: '估算買賣超金額',
        type: 'line',
        data: amounts,
        smooth: true,
        itemStyle: { color: '#06b6d4' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(6, 182, 212, 0.4)' },
              { offset: 1, color: 'rgba(6, 182, 212, 0.0)' }
            ]
          }
        }
      }
    ]
  };
});

// 指數成交金額 Option（大盤指數功能規劃書 FR-IDX-04）：資料來源是 chartData.records 裡
// 每日原始的 amount 欄位（K 線聚合時就已經帶著，不需要後端另外組一份陣列，見
// services/index_service.py 對 meta.panels 的註解）。
const indexTurnoverOption = computed(() => {
  const records = props.chartData?.records || [];
  const amounts = records.map((r) => r.amount || 0);
  const unit = props.market === 'us' ? '美元' : '元';
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '10%', top: '5%', containLabel: true },
    xAxis: { type: 'category', data: dates.value },
    yAxis: { type: 'value', name: unit },
    series: [
      {
        name: '成交金額',
        type: 'bar',
        data: amounts,
        itemStyle: { color: '#0ea5e9' }
      }
    ]
  };
});

// 融資餘額 Option
const marginLongOption = computed(() => {
  const longs = props.chartData?.margin?.long_balance || [];
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '10%', top: '5%', containLabel: true },
    xAxis: { type: 'category', data: dates.value },
    yAxis: { type: 'value', name: '張', scale: true },
    series: [
      {
        name: '融資餘額',
        type: 'line',
        data: longs,
        smooth: true,
        itemStyle: { color: '#ec4899' },
        lineStyle: { width: 3 }
      }
    ]
  };
});

// 融券餘額 Option
const marginShortOption = computed(() => {
  const shorts = props.chartData?.margin?.short_balance || [];
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '10%', top: '5%', containLabel: true },
    xAxis: { type: 'category', data: dates.value },
    yAxis: { type: 'value', name: '張', scale: true },
    series: [
      {
        name: '融券餘額',
        type: 'line',
        data: shorts,
        smooth: true,
        itemStyle: { color: '#10b981' },
        lineStyle: { width: 3 }
      }
    ]
  };
});

// 券資比 Option
const shortRatioOption = computed(() => {
  const ratios = props.chartData?.margin?.short_ratio || [];
  return {
    tooltip: { trigger: 'axis', formatter: '{b}<br/>券資比: {c}%' },
    grid: { left: '3%', right: '4%', bottom: '10%', top: '5%', containLabel: true },
    xAxis: { type: 'category', data: dates.value },
    yAxis: { type: 'value', name: '%', scale: true },
    series: [
      {
        name: '券資比',
        type: 'line',
        data: ratios,
        smooth: true,
        itemStyle: { color: '#f97316' },
        lineStyle: { width: 3 }
      }
    ]
  };
});
</script>

<style scoped>
.chart-container-stage {
  width: 100%;
  height: 440px;
}

/* KD 副圖開啟時加高舞台，避免主圖被壓扁（KD指標 設計規格書 §7.1） */
.chart-container-stage--kd {
  height: 560px;
}
</style>
