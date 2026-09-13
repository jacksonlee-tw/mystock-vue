<template>
  <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
    <!-- 大盤位階燈號：紅漲綠跌是本專案全站統一規定，站上月線視同「偏多」比照個股漲用紅、
         跌破月線視同「偏空」比照個股跌用綠（不是財經界常見的紅跌綠漲，見 marketColors.js 說明）。
         同列卡片高度需一致（CLAUDE.md 硬性規則 #2）：grid 卡片一律補 !m-0 中和 _utils.scss
         legacy margin-bottom，比照 StockDashboard.vue KPI 卡片的既有作法。 -->
    <div class="card !m-0 rounded-2xl border border-surface-200 dark:border-surface-700/80 bg-surface-0 dark:bg-surface-900 shadow-sm p-4 flex flex-col justify-between">
      <div class="flex items-center justify-between">
        <span class="text-xs font-bold text-surface-500">大盤位階（台股月線）</span>
        <i class="pi pi-compass text-primary"></i>
      </div>
      <div v-if="loadingRegime" class="text-sm text-surface-400 mt-2 flex items-center gap-1.5">
        <i class="pi pi-spin pi-spinner"></i>載入中...
      </div>
      <div v-else-if="!regime || !regime.has_data" class="text-sm text-surface-400 mt-2">尚無資料</div>
      <div v-else class="mt-1">
        <span
          class="inline-flex items-center gap-1 px-2 py-1 rounded-full text-sm font-bold"
          :class="regime.above_ma20 ? 'bg-up-soft text-up' : 'bg-down-soft text-down'"
        >
          <i class="pi" :class="regime.above_ma20 ? 'pi-arrow-up' : 'pi-arrow-down'"></i>
          {{ regime.above_ma20 ? '站上月線' : '跌破月線' }}
        </span>
        <div class="text-xs text-surface-400 mt-1">
          {{ regime.index_code }} {{ formatNumber(regime.close) }}（MA20 {{ formatNumber(regime.ma20) }}）
        </div>
      </div>
    </div>

    <!-- 美債殖利率／美元指數：Sparkline 比照 HeatmapDashboard.vue 既有 getSparklineOption()
         的漸層線圖畫法，改用中性單色（不套用漲跌色，因為指標本身漲跌不直接代表個股多空）。 -->
    <div
      v-for="ind in [{ code: 'US10Y', label: '美債10年殖利率', unit: '%' }, { code: 'DXY', label: '美元指數', unit: '' }]"
      :key="ind.code"
      class="card !m-0 rounded-2xl border border-surface-200 dark:border-surface-700/80 bg-surface-0 dark:bg-surface-900 shadow-sm p-4 flex flex-col justify-between"
    >
      <div class="flex items-center justify-between">
        <span class="text-xs font-bold text-surface-500">{{ ind.label }}</span>
        <i class="pi pi-chart-line text-primary"></i>
      </div>
      <div v-if="loadingIndicators" class="text-sm text-surface-400 mt-2 flex items-center gap-1.5">
        <i class="pi pi-spin pi-spinner"></i>載入中...
      </div>
      <div v-else-if="!indicatorValue(ind.code)" class="text-sm text-surface-400 mt-2">尚無資料</div>
      <template v-else>
        <div class="flex items-end justify-between gap-2 mt-1">
          <div>
            <div class="text-lg font-black text-surface-900 dark:text-surface-0 tabular-nums">
              {{ formatNumber(indicatorValue(ind.code).value) }}<span class="text-xs font-normal text-surface-400">{{ ind.unit }}</span>
            </div>
            <!-- 較前一筆的變化：用已抓回來的序列最後兩點自己算，不需要後端另外提供。
                 刻意維持中性灰、只用箭頭表示方向，不套紅漲綠跌——殖利率或美元指數上漲
                 對個股是偏多還偏空要看情境，直接上漲跌色會強加一個不成立的語意。 -->
            <div v-if="changeInfo(ind.code)" class="text-[11px] text-surface-500 tabular-nums mt-0.5">
              <i class="pi text-[9px]" :class="changeInfo(ind.code).diff >= 0 ? 'pi-arrow-up' : 'pi-arrow-down'"></i>
              {{ changeInfo(ind.code).diff >= 0 ? '+' : '' }}{{ formatNumber(changeInfo(ind.code).diff) }}
              （{{ changeInfo(ind.code).pct >= 0 ? '+' : '' }}{{ formatNumber(changeInfo(ind.code).pct) }}%）
            </div>
          </div>
          <div class="w-20 h-8">
            <v-chart :option="getSparklineOption(sparklines[ind.code])" :update-options="{ notMerge: true }" autoresize />
          </div>
        </div>
        <div class="text-[11px] text-surface-400 mt-1">公布日 {{ indicatorValue(ind.code).release_date }}</div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { LineChart } from 'echarts/charts';
import { GridComponent } from 'echarts/components';
import VChart from 'vue-echarts';
import { macroApi } from '@/service/macroApi';
import { hexToRgba } from '@/utils/marketColors';

// 比照專案既有慣例（HeatmapDashboard.vue／StockCharts.vue 等每個用到 <v-chart> 的檔案
// 都各自 use() 一次自己需要的 echarts 元件，不依賴其他檔案先執行過的全域註冊）。
use([CanvasRenderer, LineChart, GridComponent]);

// 中性單色：不套用紅漲綠跌，總經指標本身漲跌不直接對應個股多空方向（見上方模板註解）。
const NEUTRAL_COLOR = '#64748b';

const regime = ref(null);
const indicators = ref({});
const sparklines = ref({ US10Y: [], DXY: [] });
const loadingRegime = ref(true);
const loadingIndicators = ref(true);

function indicatorValue(code) {
  return indicators.value[code] || null;
}

function formatNumber(v) {
  if (v === null || v === undefined) return '—';
  return Number(v).toLocaleString('zh-TW', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// 較前一筆的變化：直接取 Sparkline 序列（本來就抓回來畫圖用）的最後兩點相減，
// 不需要後端額外提供欄位。資料不足兩點、前一筆為 0 或非數字時回傳 null（該區塊不顯示），
// 不硬算出一個會誤導人的百分比。
function changeInfo(code) {
  const series = sparklines.value[code] || [];
  if (series.length < 2) return null;
  const prev = Number(series[series.length - 2]);
  const curr = Number(series[series.length - 1]);
  if (!Number.isFinite(prev) || !Number.isFinite(curr) || prev === 0) return null;
  const diff = curr - prev;
  return { diff, pct: (diff / Math.abs(prev)) * 100 };
}

function getSparklineOption(data) {
  const color04 = hexToRgba(NEUTRAL_COLOR, 0.4);
  const color00 = hexToRgba(NEUTRAL_COLOR, 0.0);
  return {
    grid: { left: 0, right: 0, top: 4, bottom: 4 },
    xAxis: { type: 'category', show: false, boundaryGap: false },
    yAxis: { type: 'value', show: false, min: 'dataMin', max: 'dataMax' },
    series: [
      {
        type: 'line',
        data: data || [],
        showSymbol: false,
        smooth: true,
        lineStyle: { width: 1.5, color: NEUTRAL_COLOR },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: color04 },
              { offset: 1, color: color00 }
            ]
          }
        }
      }
    ]
  };
}

async function loadRegime() {
  loadingRegime.value = true;
  try {
    const res = await macroApi.getMarketRegime('tw');
    if (res.success) regime.value = res.data;
  } catch {
    regime.value = null;
  } finally {
    loadingRegime.value = false;
  }
}

async function loadIndicators() {
  loadingIndicators.value = true;
  try {
    const res = await macroApi.getIndicators();
    if (res.success) indicators.value = res.data;
    for (const code of ['US10Y', 'DXY']) {
      try {
        const seriesRes = await macroApi.getIndicatorSeries(code, 30);
        if (seriesRes.success) sparklines.value[code] = seriesRes.data.series.map((p) => p.value);
      } catch {
        sparklines.value[code] = [];
      }
    }
  } catch {
    indicators.value = {};
  } finally {
    loadingIndicators.value = false;
  }
}

onMounted(() => {
  loadRegime();
  loadIndicators();
});
</script>
