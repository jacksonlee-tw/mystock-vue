<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6">
    <div class="flex items-center flex-col md:flex-row md:items-center justify-between gap-4 card p-6 shadow-sm border border-surface-200 dark:border-surface-700 rounded-2xl bg-surface-0 dark:bg-surface-900">
      <div>
        <h1 class="text-2xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
          <i class="pi pi-briefcase text-primary text-2xl"></i>持股總覽
        </h1>
        <p class="text-sm text-surface-500 mt-1">庫存股數、均價成本、市值與未實現損益，成本法可即時切換比較</p>
      </div>
      <Select v-model="market" :options="marketOptions" optionLabel="label" optionValue="value" placeholder="全部市場" showClear class="w-36" />
    </div>

    <div class="p-4 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm flex flex-wrap items-center gap-4">
      <span class="text-sm font-bold text-surface-600 dark:text-surface-300 flex items-center gap-1.5"><i class="pi pi-sliders-h text-primary"></i>成本計算法</span>
      <div class="flex items-center gap-1 bg-surface-100 dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded-lg p-1">
        <button v-for="opt in costMethodOptions" :key="opt.value" @click="costMethod = opt.value"
          class="px-3 py-1.5 text-xs font-bold rounded-md transition-colors"
          :class="costMethod === opt.value ? 'bg-primary text-primary-contrast shadow-sm' : 'text-surface-500 hover:text-surface-800 dark:hover:text-surface-200'">
          {{ opt.label }}
        </button>
      </div>
      <span class="text-xs text-surface-400">{{ costMethod === 'fifo' ? '賣出時由最早買進的部位開始對沖' : '每次買進後重算移動平均成本' }}</span>
    </div>

    <div v-if="loading" class="flex items-center gap-2 text-surface-500 text-sm py-10 justify-center"><i class="pi pi-spin pi-spinner"></i> 載入中...</div>

    <div v-else class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-left border-collapse text-sm">
          <thead>
            <tr class="bg-surface-50 dark:bg-surface-800 text-surface-400 text-xs uppercase tracking-wide">
              <th class="p-3">股票</th>
              <th class="p-3">市場</th>
              <th class="p-3 text-right">庫存股數</th>
              <th class="p-3 text-right">均價成本</th>
              <th class="p-3 text-right">現價</th>
              <th class="p-3 text-right">市值</th>
              <th class="p-3">佔比</th>
              <th class="p-3 text-right">未實現損益</th>
              <th class="p-3 text-right">報酬率</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="h in holdings" :key="h.market + h.symbol" class="border-t border-surface-100 dark:border-surface-800 hover:bg-surface-50 dark:hover:bg-surface-800/60">
              <td class="p-3">
                <div class="font-bold text-surface-800 dark:text-surface-100">{{ h.symbol }}</div>
                <div class="text-xs text-surface-400">{{ h.name }}</div>
              </td>
              <td class="p-3"><span class="px-2 py-0.5 text-xs font-bold rounded bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-300">{{ marketMeta[h.market].label }}</span></td>
              <td class="p-3 text-right num">
                {{ fmtNum(h.shares) }}
                <div v-if="lotLabel(h.shares, h.market)" class="text-[11px] text-surface-400">{{ lotLabel(h.shares, h.market) }}</div>
              </td>
              <td class="p-3 text-right num">
                {{ marketMeta[h.market].symbol }} {{ h.avg_cost.toFixed(2) }}
                <div v-if="h.dividend_offset > 0" class="text-[11px] text-emerald-600">含息還原 -{{ (h.dividend_offset / h.shares).toFixed(2) }}</div>
              </td>
              <td class="p-3 text-right num font-medium">
                <span v-if="!h.quote_missing">{{ marketMeta[h.market].symbol }} {{ h.price.toFixed(2) }}</span>
                <span v-else class="text-surface-300 text-xs">待報價</span>
              </td>
              <td class="p-3 text-right num">{{ marketMeta[h.market].symbol }} {{ fmtAmt(h.market_value, h.market) }}</td>
              <td class="p-3 w-32">
                <div class="h-1.5 rounded-full bg-surface-200 dark:bg-surface-700 overflow-hidden"><div class="h-full bg-primary rounded-full" :style="{ width: Math.min(100, h.weight_pct).toFixed(1) + '%' }"></div></div>
                <div class="text-xs text-surface-400 num mt-0.5">{{ h.weight_pct.toFixed(1) }}%</div>
              </td>
              <td class="p-3 text-right num font-bold" :data-market="h.market" :class="h.pnl >= 0 ? 'text-up' : 'text-down'">{{ marketMeta[h.market].symbol }} {{ signed(h.pnl, h.market) }}</td>
              <td class="p-3 text-right num font-bold" :data-market="h.market" :class="h.pnl >= 0 ? 'text-up' : 'text-down'">{{ fmtPct(h.pnl_pct) }}</td>
            </tr>
            <tr v-if="!holdings.length">
              <td colspan="9" class="p-8 text-center text-surface-400 text-sm">此市場目前沒有庫存部位</td>
            </tr>
          </tbody>
          <tfoot v-if="holdings.length">
            <tr class="border-t-2 border-surface-200 dark:border-surface-700 font-bold text-surface-700 dark:text-surface-200 bg-surface-50 dark:bg-surface-800">
              <td class="p-3" colspan="5">合計（美股折算 TWD）</td>
              <td class="p-3 text-right num">NT$ {{ fmtNum(totalValueTwd) }}</td>
              <td class="p-3">100%</td>
              <td class="p-3 text-right num" :class="totalPnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'">{{ signed(totalPnl) }}</td>
              <td class="p-3 text-right num" :class="totalPnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'">{{ fmtPct(totalPnlPct) }}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useToast } from 'primevue/usetoast';
import { portfolioApi } from '@/service/portfolioApi';
import { marketMeta, fmtNum, fmtAmt, fmtPct, signed, lotLabel } from '@/composables/usePortfolioFormat';

const toast = useToast();
const marketOptions = [{ label: '台股', value: 'tw' }, { label: '美股', value: 'us' }];
const costMethodOptions = [{ value: 'fifo', label: '先進先出 FIFO' }, { value: 'average', label: '加權平均法' }];

const market = ref(null);
const costMethod = ref('fifo');
const loading = ref(true);
const holdings = ref([]);
const fxRate = ref(32.5);

const toTwd = (v, m) => (m === 'us' ? v * fxRate.value : v);
const totalValueTwd = computed(() => holdings.value.reduce((s, h) => s + toTwd(h.market_value, h.market), 0));
const totalPnl = computed(() => holdings.value.reduce((s, h) => s + toTwd(h.pnl, h.market), 0));
const totalCost = computed(() => holdings.value.reduce((s, h) => s + toTwd(h.cost, h.market), 0));
const totalPnlPct = computed(() => (totalCost.value ? (totalPnl.value / totalCost.value) * 100 : 0));

async function load() {
  loading.value = true;
  try {
    const [holdingsRes, settingsRes] = await Promise.all([
      portfolioApi.getHoldings({ market: market.value, costMethod: costMethod.value }),
      portfolioApi.getSettings()
    ]);
    holdings.value = holdingsRes.data;
    fxRate.value = settingsRes.data.fx_rate;
  } catch (err) {
    toast.add({ severity: 'error', summary: '載入失敗', detail: err?.response?.data?.detail || err.message, life: 4000 });
  } finally {
    loading.value = false;
  }
}

watch([market, costMethod], load);
onMounted(load);
</script>

<style scoped>
.num {
  font-family: ui-monospace, 'Cascadia Mono', 'SF Mono', Menlo, Consolas, monospace;
  font-variant-numeric: tabular-nums;
}
</style>
