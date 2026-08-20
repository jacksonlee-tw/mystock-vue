<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6">
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 card p-6 shadow-sm border border-surface-200 dark:border-surface-700 rounded-2xl bg-surface-0 dark:bg-surface-900">
      <div>
        <h1 class="text-2xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
          <i class="pi pi-money-bill text-primary text-2xl"></i>已實現損益
        </h1>
        <p class="text-sm text-surface-500 mt-1">平倉明細、勝率／盈虧比與月度／年度績效彙整</p>
      </div>
      <div class="flex items-center gap-2">
        <Select v-model="market" :options="marketOptions" optionLabel="label" optionValue="value" placeholder="全部市場" showClear class="w-32" />
        <div class="flex items-center gap-1 bg-surface-100 dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded-lg p-1">
          <button v-for="opt in costMethodOptions" :key="opt.value" @click="costMethod = opt.value"
            class="px-3 py-1.5 text-xs font-bold rounded-md transition-colors"
            :class="costMethod === opt.value ? 'bg-primary text-primary-contrast shadow-sm' : 'text-surface-500'">{{ opt.label }}</button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="flex items-center gap-2 text-surface-500 text-sm py-10 justify-center"><i class="pi pi-spin pi-spinner"></i> 載入中...</div>

    <template v-else>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div class="p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm">
          <div class="text-xs font-bold text-surface-400 uppercase tracking-wide mb-1">累計已實現損益</div>
          <div class="text-2xl font-black num" :class="stats.total >= 0 ? 'text-emerald-600' : 'text-red-600'">{{ signed(stats.total) }}</div>
          <div class="text-xs text-surface-400 mt-1">交易 {{ signed(stats.trade_total) }} ＋股利 {{ fmtNum(stats.dividend_income) }}</div>
        </div>
        <div class="p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm">
          <div class="text-xs font-bold text-surface-400 uppercase tracking-wide mb-1">總獲利 / 總虧損</div>
          <div class="text-lg font-black num"><span class="text-emerald-600">+{{ fmtNum(stats.gross_win) }}</span> / <span class="text-red-600">-{{ fmtNum(stats.gross_loss) }}</span></div>
          <div class="text-xs text-surface-400 mt-1">獲利因子 {{ stats.gross_loss ? (stats.gross_win / stats.gross_loss).toFixed(2) : '—' }}</div>
        </div>
        <div class="p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm">
          <div class="text-xs font-bold text-surface-400 uppercase tracking-wide mb-1">勝率</div>
          <div class="text-2xl font-black text-primary-700 dark:text-primary-300 num">{{ stats.lots ? stats.win_rate.toFixed(1) + '%' : '—' }}</div>
          <div class="text-xs text-surface-400 mt-1">{{ stats.wins }} 勝 / {{ stats.losses }} 敗（共 {{ stats.lots }} 次平倉）</div>
        </div>
        <div class="p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm">
          <div class="text-xs font-bold text-surface-400 uppercase tracking-wide mb-1">平均盈虧比</div>
          <div class="text-2xl font-black text-surface-800 dark:text-surface-100 num">{{ stats.avg_win_loss_ratio == null ? '—' : stats.avg_win_loss_ratio.toFixed(2) }}</div>
          <div class="text-xs text-surface-400 mt-1">平均獲利 {{ fmtNum(stats.avg_win) }} / 平均虧損 {{ fmtNum(stats.avg_loss) }}</div>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div class="p-5 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm">
          <h2 class="text-sm font-bold text-surface-700 dark:text-surface-200 mb-1 pb-2 border-b border-surface-100 dark:border-surface-800">月度已實現損益</h2>
          <p class="text-xs text-surface-400 mb-2">跨市場彙總為 TWD；損益一律綠賺紅賠（非個股漲跌色）</p>
          <v-chart v-if="monthlySeries.length" class="h-56" :option="monthlyOption" :update-options="{ notMerge: true }" autoresize />
          <div v-else class="h-56 flex items-center justify-center text-sm text-surface-400">尚無平倉紀錄</div>
        </div>
        <div class="p-5 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm">
          <h2 class="text-sm font-bold text-surface-700 dark:text-surface-200 mb-1 pb-2 border-b border-surface-100 dark:border-surface-800">資產權益曲線</h2>
          <p class="text-xs text-surface-400 mb-2">累計已實現損益（含股利），最後一點加計目前未實現損益</p>
          <v-chart v-if="equitySeries.length" class="h-56" :option="equityOption" :update-options="{ notMerge: true }" autoresize />
          <div v-else class="h-56 flex items-center justify-center text-sm text-surface-400">尚無平倉紀錄</div>
        </div>
      </div>

      <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm overflow-hidden">
        <div class="p-4 border-b border-surface-100 dark:border-surface-800 flex items-center justify-between gap-2">
          <h2 class="text-sm font-bold text-surface-700 dark:text-surface-200">年度 / 月度損益彙整</h2>
          <div class="flex items-center gap-1 bg-surface-100 dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded-md p-0.5">
            <button v-for="o in periodOptions" :key="o.value" @click="periodMode = o.value"
              class="px-2.5 py-1 text-[11px] font-bold rounded transition-colors"
              :class="periodMode === o.value ? 'bg-primary text-primary-contrast' : 'text-surface-500'">{{ o.label }}</button>
          </div>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse text-sm">
            <thead>
              <tr class="bg-surface-50 dark:bg-surface-800 text-surface-400 text-xs uppercase tracking-wide">
                <th class="p-3">{{ periodMode === 'year' ? '年度' : '月份' }}</th>
                <th class="p-3 text-right">平倉次數</th>
                <th class="p-3 text-right">勝 / 敗</th>
                <th class="p-3 text-right">勝率</th>
                <th class="p-3 text-right">股利收入</th>
                <th class="p-3 text-right">已實現損益</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in periodSummary" :key="row.label" class="border-t border-surface-100 dark:border-surface-800">
                <td class="p-3 font-bold text-surface-700 dark:text-surface-200 num">{{ row.label }}</td>
                <td class="p-3 text-right num">{{ row.lots }}</td>
                <td class="p-3 text-right num text-surface-500">{{ row.wins }} / {{ row.losses }}</td>
                <td class="p-3 text-right num">{{ row.lots ? row.win_rate.toFixed(0) + '%' : '—' }}</td>
                <td class="p-3 text-right num text-surface-500">{{ row.dividend ? fmtNum(row.dividend) : '—' }}</td>
                <td class="p-3 text-right num font-bold" :class="row.total >= 0 ? 'text-emerald-600' : 'text-red-600'">{{ signed(row.total) }}</td>
              </tr>
              <tr v-if="!periodSummary.length"><td colspan="6" class="p-8 text-center text-surface-400 text-sm">尚無平倉紀錄</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm overflow-hidden">
        <div class="p-4 border-b border-surface-100 dark:border-surface-800">
          <h2 class="text-sm font-bold text-surface-700 dark:text-surface-200">平倉明細清單</h2>
          <p class="text-xs text-surface-400 mt-0.5">
            依「{{ costMethod === 'fifo' ? '先進先出 FIFO' : '加權平均法' }}」對沖買賣紀錄，已扣除買賣雙邊手續費與證交稅。
          </p>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse text-sm">
            <thead>
              <tr class="bg-surface-50 dark:bg-surface-800 text-surface-400 text-xs uppercase tracking-wide">
                <th class="p-3">平倉日期</th>
                <th class="p-3">市場</th>
                <th class="p-3">股票</th>
                <th class="p-3 text-right">股數</th>
                <th class="p-3 text-right">賣出均價</th>
                <th class="p-3 text-right">成本均價</th>
                <th class="p-3 text-right">交易成本</th>
                <th class="p-3 text-right">已實現損益</th>
                <th class="p-3 text-center">配對明細</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="lot in lots" :key="lot.id">
                <tr class="border-t border-surface-100 dark:border-surface-800">
                  <td class="p-3 text-surface-500 num">{{ lot.close_date }}</td>
                  <td class="p-3"><span class="px-2 py-0.5 text-xs font-bold rounded bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-300">{{ marketMeta[lot.market].label }}</span></td>
                  <td class="p-3 font-medium text-surface-800 dark:text-surface-100">{{ lot.symbol }} <span class="text-surface-400 font-normal">{{ lot.name }}</span></td>
                  <td class="p-3 text-right num">{{ fmtNum(lot.shares) }}</td>
                  <td class="p-3 text-right num">{{ marketMeta[lot.market].symbol }} {{ lot.sell_avg.toFixed(2) }}</td>
                  <td class="p-3 text-right num">{{ marketMeta[lot.market].symbol }} {{ lot.cost_avg.toFixed(2) }}</td>
                  <td class="p-3 text-right num text-surface-400">{{ marketMeta[lot.market].symbol }} {{ fmtAmt(lot.cost, lot.market) }}</td>
                  <td class="p-3 text-right num font-bold" :class="lot.pnl >= 0 ? 'text-emerald-600' : 'text-red-600'">{{ marketMeta[lot.market].symbol }} {{ signed(lot.pnl, lot.market) }} ({{ fmtPct(lot.pnl_pct) }})</td>
                  <td class="p-3 text-center">
                    <button v-if="lot.matches.length" @click="expandedId = expandedId === lot.id ? null : lot.id" class="text-surface-400 hover:text-primary transition-colors">
                      <i :class="expandedId === lot.id ? 'pi pi-chevron-up' : 'pi pi-chevron-down'"></i>
                    </button>
                    <span v-else class="text-surface-300 text-xs">不適用</span>
                  </td>
                </tr>
                <tr v-if="expandedId === lot.id && lot.matches.length" class="bg-surface-50/70 dark:bg-surface-800/50">
                  <td colspan="9" class="p-3">
                    <div class="text-xs font-bold text-surface-500 mb-1.5">該筆賣出對應到以下歷史買進（FIFO）：</div>
                    <table class="w-full text-xs border-collapse max-w-2xl">
                      <thead><tr class="text-surface-400"><th class="py-1 pr-3 text-left">買進日期</th><th class="py-1 px-3 text-right">配對股數</th><th class="py-1 px-3 text-right">買進價</th><th class="py-1 pl-3 text-right">該段損益</th></tr></thead>
                      <tbody>
                        <tr v-for="(m, i) in lot.matches" :key="i" class="border-t border-surface-100 dark:border-surface-800">
                          <td class="py-1 pr-3 num">{{ m.buy_date }}</td>
                          <td class="py-1 px-3 text-right num">{{ fmtNum(m.shares) }}</td>
                          <td class="py-1 px-3 text-right num">{{ marketMeta[lot.market].symbol }} {{ m.buy_price.toFixed(2) }}</td>
                          <td class="py-1 pl-3 text-right num font-bold" :class="m.pnl >= 0 ? 'text-emerald-600' : 'text-red-600'">{{ marketMeta[lot.market].symbol }} {{ signed(m.pnl, lot.market) }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </td>
                </tr>
              </template>
              <tr v-if="!lots.length"><td colspan="9" class="p-8 text-center text-surface-400 text-sm">尚無平倉紀錄</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useToast } from 'primevue/usetoast';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart, LineChart } from 'echarts/charts';
import { GridComponent, TooltipComponent } from 'echarts/components';
import VChart from 'vue-echarts';
import { portfolioApi } from '@/service/portfolioApi';
import { marketMeta, fmtNum, fmtAmt, fmtPct, signed } from '@/composables/usePortfolioFormat';

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent]);

const toast = useToast();
const marketOptions = [{ label: '台股', value: 'tw' }, { label: '美股', value: 'us' }];
const costMethodOptions = [{ value: 'fifo', label: '先進先出 FIFO' }, { value: 'average', label: '加權平均法' }];
const periodOptions = [{ value: 'year', label: '年度' }, { value: 'month', label: '月度' }];

const market = ref(null);
const costMethod = ref('fifo');
const periodMode = ref('year');
const loading = ref(true);
const expandedId = ref(null);

const lots = ref([]);
const stats = ref({ lots: 0, wins: 0, losses: 0, win_rate: 0, gross_win: 0, gross_loss: 0, avg_win: 0, avg_loss: 0, avg_win_loss_ratio: null, trade_total: 0, dividend_income: 0, total: 0 });
const periodSummary = ref([]);
const monthlyRows = ref([]); // 恆為月度，供權益曲線月月累計，不受 periodMode 影響
const unrealizedTotal = ref(0);

async function loadRealized() {
  const res = await portfolioApi.getRealized({ market: market.value, costMethod: costMethod.value });
  lots.value = res.data.lots;
  stats.value = res.data.stats;
}
async function loadPeriodSummary() {
  const res = await portfolioApi.getHistory({ groupBy: periodMode.value, market: market.value, costMethod: costMethod.value });
  periodSummary.value = res.data;
}
async function loadMonthlyForEquity() {
  const res = await portfolioApi.getHistory({ groupBy: 'month', market: market.value, costMethod: costMethod.value });
  monthlyRows.value = [...res.data].sort((a, b) => (a.label < b.label ? -1 : 1));
}
async function loadUnrealized() {
  const res = await portfolioApi.getSummary();
  unrealizedTotal.value = res.data.unrealized_total_twd;
}

async function loadAll() {
  loading.value = true;
  try {
    await Promise.all([loadRealized(), loadPeriodSummary(), loadMonthlyForEquity(), loadUnrealized()]);
  } catch (err) {
    toast.add({ severity: 'error', summary: '載入失敗', detail: err?.response?.data?.detail || err.message, life: 4000 });
  } finally {
    loading.value = false;
  }
}
watch([market, costMethod], loadAll);
watch(periodMode, loadPeriodSummary);
onMounted(loadAll);

const monthlySeries = computed(() => monthlyRows.value.map((r) => ({ label: r.label, value: r.total })));
const equitySeries = computed(() => {
  if (!monthlyRows.value.length) return [];
  let acc = 0;
  const points = monthlyRows.value.map((r) => { acc += r.total; return { label: r.label, value: acc }; });
  points.push({ label: '目前', value: acc + unrealizedTotal.value });
  return points;
});

const monthlyOption = computed(() => ({
  grid: { left: 8, right: 12, top: 16, bottom: 4, containLabel: true },
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (v) => fmtNum(v) },
  xAxis: { type: 'category', data: monthlySeries.value.map((r) => r.label), axisLabel: { fontSize: 10, rotate: monthlySeries.value.length > 8 ? 45 : 0 } },
  yAxis: { type: 'value', axisLabel: { fontSize: 10, formatter: (v) => fmtNum(v) } },
  series: [{
    type: 'bar', barMaxWidth: 28,
    data: monthlySeries.value.map((r) => ({ value: r.value, itemStyle: { color: r.value >= 0 ? '#16a34a' : '#dc2626' } }))
  }]
}));

const equityOption = computed(() => ({
  grid: { left: 8, right: 12, top: 16, bottom: 4, containLabel: true },
  tooltip: { trigger: 'axis', valueFormatter: (v) => fmtNum(v) },
  xAxis: { type: 'category', boundaryGap: false, data: equitySeries.value.map((r) => r.label), axisLabel: { fontSize: 10, rotate: equitySeries.value.length > 8 ? 45 : 0 } },
  yAxis: { type: 'value', axisLabel: { fontSize: 10, formatter: (v) => fmtNum(v) } },
  series: [{
    type: 'line', smooth: true, symbolSize: 5,
    data: equitySeries.value.map((r) => r.value),
    lineStyle: { color: '#8f6413', width: 2 }, itemStyle: { color: '#8f6413' },
    areaStyle: { color: 'rgba(143,100,19,0.12)' }
  }]
}));
</script>

<style scoped>
.num {
  font-family: ui-monospace, 'Cascadia Mono', 'SF Mono', Menlo, Consolas, monospace;
  font-variant-numeric: tabular-nums;
}
</style>
