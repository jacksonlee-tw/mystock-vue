<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6">
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 card p-6 shadow-sm border border-surface-200 dark:border-surface-700 rounded-2xl bg-surface-0 dark:bg-surface-900">
      <div>
        <h1 class="text-2xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
          <i class="pi pi-wallet text-primary text-2xl"></i>
          個人投資記帳與績效追蹤
        </h1>
        <p class="text-sm text-surface-500 mt-1">帳戶總覽：市值、未實現／已實現損益、資產配置與到價提醒一次看</p>
      </div>
      <div class="flex items-center gap-1 bg-surface-100 dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded-lg p-1">
        <button v-for="m in marketFilterOptions" :key="m.value" @click="marketFilter = m.value"
          class="px-3 py-1.5 text-xs font-bold rounded-md transition-colors"
          :class="marketFilter === m.value ? 'bg-primary text-primary-contrast shadow-sm' : 'text-surface-500 hover:text-surface-800 dark:hover:text-surface-200'">
          {{ m.label }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="flex items-center gap-2 text-surface-500 text-sm py-10 justify-center">
      <i class="pi pi-spin pi-spinner"></i> 載入中...
    </div>
    <div v-else-if="error" class="p-4 rounded-xl bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 text-sm flex items-center justify-between gap-3">
      <span><i class="pi pi-exclamation-triangle"></i> {{ error }}</span>
      <button @click="loadAll" class="px-3 py-1.5 rounded-lg bg-red-100 dark:bg-red-900/40 font-bold text-xs">重試</button>
    </div>

    <template v-else>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div class="p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm flex items-center gap-3">
          <div class="w-12 h-12 rounded-xl bg-primary-50 dark:bg-primary-500/10 text-primary flex items-center justify-center text-xl shrink-0"><i class="pi pi-wallet"></i></div>
          <div class="min-w-0">
            <div class="text-xs font-bold text-surface-400 uppercase tracking-wide">帳戶總值</div>
            <div class="text-2xl font-black text-surface-900 dark:text-surface-0 num">NT$ {{ fmtNum(summary.account_value_twd) }}</div>
            <div class="text-xs text-surface-400">持股 {{ fmtNum(summary.portfolio_value_twd) }} + 現金 {{ fmtNum(summary.cash_balance_twd) }}</div>
          </div>
        </div>
        <div class="p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm flex items-center gap-3">
          <div class="w-12 h-12 rounded-xl flex items-center justify-center text-xl shrink-0" :class="summary.unrealized_total_twd >= 0 ? 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600' : 'bg-red-50 dark:bg-red-500/10 text-red-600'">
            <i :class="summary.unrealized_total_twd >= 0 ? 'pi pi-arrow-up' : 'pi pi-arrow-down'"></i>
          </div>
          <div class="min-w-0">
            <div class="text-xs font-bold text-surface-400 uppercase tracking-wide">未實現總損益</div>
            <div class="text-2xl font-black num" :class="summary.unrealized_total_twd >= 0 ? 'text-emerald-600' : 'text-red-600'">
              {{ signed(summary.unrealized_total_twd) }}
            </div>
            <div class="text-xs text-surface-400">報酬率 {{ fmtPct(summary.unrealized_total_pct) }}</div>
          </div>
        </div>
        <div class="p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm flex items-center gap-3">
          <div class="w-12 h-12 rounded-xl flex items-center justify-center text-xl shrink-0" :class="summary.realized_total_twd >= 0 ? 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600' : 'bg-red-50 dark:bg-red-500/10 text-red-600'">
            <i class="pi pi-money-bill"></i>
          </div>
          <div class="min-w-0">
            <div class="text-xs font-bold text-surface-400 uppercase tracking-wide">累計已實現損益</div>
            <div class="text-2xl font-black num" :class="summary.realized_total_twd >= 0 ? 'text-emerald-600' : 'text-red-600'">
              {{ signed(summary.realized_total_twd) }}
            </div>
            <div class="text-xs text-surface-400">共 {{ summary.realized_lots }} 筆平倉紀錄</div>
          </div>
        </div>
        <div class="p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm flex items-center gap-3">
          <div class="w-12 h-12 rounded-xl bg-primary-50 dark:bg-primary-500/10 text-primary flex items-center justify-center text-xl shrink-0"><i class="pi pi-percentage"></i></div>
          <div class="min-w-0">
            <div class="text-xs font-bold text-surface-400 uppercase tracking-wide">勝率（獲利次數/總平倉）</div>
            <div class="text-2xl font-black text-primary-700 dark:text-primary-300 num">{{ summary.realized_lots ? summary.win_rate.toFixed(1) + '%' : '—' }}</div>
            <div class="text-xs text-surface-400">{{ summary.wins }} 勝 / {{ summary.losses }} 敗</div>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div class="lg:col-span-1 p-5 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm">
          <h2 class="text-sm font-bold text-surface-700 dark:text-surface-200 mb-3 pb-2 border-b border-surface-100 dark:border-surface-800">資產配置比重</h2>
          <div v-if="!holdings.length" class="h-56 flex items-center justify-center text-sm text-surface-400">目前沒有庫存部位</div>
          <v-chart v-else class="h-56" :option="allocationOption" :update-options="{ notMerge: true }" autoresize />
        </div>

        <div class="lg:col-span-2 p-5 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm overflow-hidden">
          <h2 class="text-sm font-bold text-surface-700 dark:text-surface-200 mb-3 pb-2 border-b border-surface-100 dark:border-surface-800">當前持股明細</h2>
          <div class="overflow-x-auto">
            <table class="w-full text-left border-collapse text-sm">
              <thead>
                <tr class="text-surface-400 text-xs uppercase tracking-wide">
                  <th class="py-2 pr-3">股票</th>
                  <th class="py-2 px-3 text-right">庫存</th>
                  <th class="py-2 px-3 text-right">均價</th>
                  <th class="py-2 px-3 text-right">現價</th>
                  <th class="py-2 px-3 text-right">未實現損益</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="h in holdings" :key="h.market + h.symbol" class="border-t border-surface-100 dark:border-surface-800">
                  <td class="py-2.5 pr-3">
                    <div class="font-bold text-surface-800 dark:text-surface-100">{{ h.symbol }}</div>
                    <div class="text-xs text-surface-400">{{ h.name }}</div>
                  </td>
                  <td class="py-2.5 px-3 text-right num">{{ fmtNum(h.shares) }}</td>
                  <td class="py-2.5 px-3 text-right num">{{ h.avg_cost.toFixed(2) }}</td>
                  <td class="py-2.5 px-3 text-right num font-medium">
                    <span v-if="!h.quote_missing">{{ h.price.toFixed(2) }}</span>
                    <span v-else class="text-surface-300 text-xs">待報價</span>
                  </td>
                  <td class="py-2.5 px-3 text-right num font-bold" :data-market="h.market" :class="h.pnl >= 0 ? 'text-up' : 'text-down'">
                    {{ signed(h.pnl, h.market) }}
                    <div class="text-xs font-normal">({{ fmtPct(h.pnl_pct) }})</div>
                  </td>
                </tr>
                <tr v-if="!holdings.length">
                  <td colspan="5" class="py-8 text-center text-surface-400 text-sm">目前沒有庫存部位</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div class="p-5 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm">
          <h2 class="text-sm font-bold text-surface-700 dark:text-surface-200 mb-3 pb-2 border-b border-surface-100 dark:border-surface-800 flex items-center gap-2">
            <i class="pi pi-list text-primary"></i>近期交易
          </h2>
          <p v-if="!recentTransactions.length" class="text-sm text-surface-400 py-4 text-center">尚無交易紀錄</p>
          <ul class="divide-y divide-surface-100 dark:divide-surface-800">
            <li v-for="tx in recentTransactions" :key="tx.id" class="py-2.5 flex items-center gap-3 text-sm">
              <span class="px-2 py-0.5 text-xs font-bold rounded shrink-0" :class="tx.side === 'buy' ? 'bg-red-50 dark:bg-red-500/10 text-red-600' : 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600'">
                {{ tx.side === 'buy' ? '買進' : '賣出' }}
              </span>
              <span class="font-bold text-surface-700 dark:text-surface-200">{{ tx.symbol }}</span>
              <span class="text-surface-400 text-xs truncate">{{ tx.name }}</span>
              <span class="ml-auto num text-surface-500 text-xs shrink-0">{{ tx.trade_date }}</span>
            </li>
          </ul>
        </div>

        <div class="p-5 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm">
          <h2 class="text-sm font-bold text-surface-700 dark:text-surface-200 mb-3 pb-2 border-b border-surface-100 dark:border-surface-800 flex items-center gap-2">
            <i class="pi pi-bell text-primary"></i>觀察名單到價提醒
          </h2>
          <p v-if="!nearTargetWatchlist.length" class="text-sm text-surface-400 py-4 text-center">目前沒有股票接近目標買進價</p>
          <ul class="divide-y divide-surface-100 dark:divide-surface-800">
            <li v-for="w in nearTargetWatchlist" :key="w.id" class="py-2.5 flex items-center gap-3 text-sm">
              <span class="px-2 py-0.5 text-xs font-bold rounded shrink-0" :class="w.is_reached ? 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600' : 'bg-amber-50 dark:bg-amber-500/10 text-amber-600'">
                {{ w.is_reached ? '已達價' : '接近目標' }}
              </span>
              <span class="font-bold text-surface-700 dark:text-surface-200">{{ w.symbol }}</span>
              <span class="text-surface-400 text-xs truncate">{{ w.name }}</span>
              <span class="ml-auto num text-xs shrink-0" :class="w.gap_pct <= 0 ? 'text-emerald-600 font-bold' : 'text-surface-500'">
                距目標 {{ fmtPct(w.gap_pct) }}
              </span>
            </li>
          </ul>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { PieChart } from 'echarts/charts';
import { TooltipComponent, LegendComponent } from 'echarts/components';
import VChart from 'vue-echarts';
import { portfolioApi } from '@/service/portfolioApi';
import { fmtNum, fmtPct, signed } from '@/composables/usePortfolioFormat';

use([CanvasRenderer, PieChart, TooltipComponent, LegendComponent]);

const marketFilterOptions = [
  { value: '', label: '全部' }, { value: 'tw', label: '台股' }, { value: 'us', label: '美股' }
];
const marketFilter = ref('');

const loading = ref(true);
const error = ref(null);
const summary = ref({
  account_value_twd: 0, portfolio_value_twd: 0, cash_balance_twd: 0,
  unrealized_total_twd: 0, unrealized_total_pct: 0, realized_total_twd: 0,
  realized_lots: 0, wins: 0, losses: 0, win_rate: 0
});
const allHoldings = ref([]);
const allTransactions = ref([]);
const allWatchlist = ref([]);

const holdings = computed(() => marketFilter.value ? allHoldings.value.filter((h) => h.market === marketFilter.value) : allHoldings.value);
const recentTransactions = computed(() => {
  const list = marketFilter.value ? allTransactions.value.filter((t) => t.market === marketFilter.value) : allTransactions.value;
  return list.slice(0, 5);
});
const nearTargetWatchlist = computed(() => {
  const list = marketFilter.value ? allWatchlist.value.filter((w) => w.market === marketFilter.value) : allWatchlist.value;
  return list.filter((w) => w.is_near_target);
});

const PIE_COLORS = ['#8f6413', '#d9a441', '#e4c27c', '#5c400c', '#daab55', '#64748b', '#94a3b8', '#cbd5e1'];
const allocationOption = computed(() => {
  const data = holdings.value
    .map((h) => ({ name: `${h.symbol} ${h.name}`, value: h.market_value * (h.market === 'us' ? 1 : 1) }))
    .sort((a, b) => b.value - a.value);
  return {
    color: PIE_COLORS,
    tooltip: { trigger: 'item', valueFormatter: (v) => fmtNum(v) },
    legend: { bottom: 0, type: 'scroll', itemWidth: 10, itemHeight: 10, textStyle: { fontSize: 11 } },
    series: [{
      type: 'pie', radius: ['45%', '70%'], center: ['50%', '44%'],
      itemStyle: { borderWidth: 2, borderColor: 'transparent' },
      label: { show: false }, labelLine: { show: false },
      data
    }]
  };
});

async function loadAll() {
  loading.value = true;
  error.value = null;
  try {
    const [summaryRes, holdingsRes, txRes, watchRes] = await Promise.all([
      portfolioApi.getSummary(),
      portfolioApi.getHoldings(),
      portfolioApi.getTransactions(),
      portfolioApi.getWatchlist()
    ]);
    summary.value = summaryRes.data;
    allHoldings.value = holdingsRes.data;
    allTransactions.value = [...txRes.data].sort((a, b) => (a.trade_date < b.trade_date ? 1 : -1));
    allWatchlist.value = watchRes.data;
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message || '載入失敗';
  } finally {
    loading.value = false;
  }
}

onMounted(loadAll);
</script>

<style scoped>
.num {
  font-family: ui-monospace, 'Cascadia Mono', 'SF Mono', Menlo, Consolas, monospace;
  font-variant-numeric: tabular-nums;
}
</style>
