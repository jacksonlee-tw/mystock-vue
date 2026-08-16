<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6">
    <Toast />

    <!-- 標題列與市場切換 -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h1 class="text-3xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
          <i class="pi pi-filter text-primary text-3xl"></i>
          策略選股與風控中心
        </h1>
        <p class="text-base text-surface-500 mt-1">
          全市場多因子選股模型（估值安全邊際、月營收動能、法人籌碼共振）與持倉出場風控掃描
        </p>
      </div>

      <div class="flex items-center gap-2">
        <div class="flex items-center gap-1 bg-surface-100 dark:bg-surface-800 p-1 rounded-lg border border-surface-200 dark:border-surface-700">
          <button
            v-for="m in marketOptions"
            :key="m.value"
            @click="setMarket(m.value)"
            :class="[
              'px-3 py-1.5 text-sm font-bold rounded-md transition-colors',
              currentMarket === m.value ? 'bg-primary text-primary-contrast shadow-sm' : 'text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-0'
            ]"
          >
            {{ m.label }}
          </button>
        </div>
        <Button
          label="全市場選股掃描"
          icon="pi pi-search"
          size="small"
          :loading="scanning"
          @click="runScan"
        />
        <Button
          label="持倉風控掃描"
          icon="pi pi-shield"
          size="small"
          severity="warning"
          outlined
          :loading="scanningRisk"
          @click="runRiskScan"
        />
      </div>
    </div>

    <!-- 策略選擇 Tabs / 晶片選單 -->
    <div class="flex flex-wrap items-center gap-2 p-1.5 bg-surface-100 dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700">
      <button
        v-for="strat in pickingStrategies"
        :key="strat.id"
        @click="selectStrategy(strat.id)"
        :class="[
          'px-4 py-2 text-sm font-bold rounded-lg transition-all flex items-center gap-2',
          activeStrategyId === strat.id
            ? 'bg-surface-0 dark:bg-surface-900 text-primary shadow-sm ring-1 ring-surface-200 dark:ring-surface-700'
            : 'text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-0'
        ]"
      >
        <i :class="strat.icon"></i>
        <span>{{ strat.name }}</span>
        <Tag v-if="countsByStrategy[strat.id]" :value="countsByStrategy[strat.id]" severity="primary" class="text-xs scale-90" />
      </button>
    </div>

    <!-- 頂部策略說明與 KPI 卡片（同列加 !m-0 滿足 CLAUDE.md 硬規則 2） -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
      <div class="md:col-span-2 rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 p-4 shadow-sm !m-0 flex flex-col justify-between">
        <div>
          <div class="flex items-center justify-between gap-2">
            <span class="text-xs font-bold text-primary uppercase tracking-wide">策略邏輯說明</span>
            <Tag :value="currentStrategyDef?.scope === 'universe' ? '全市場選股池' : '追蹤清單'" severity="info" />
          </div>
          <h3 class="text-lg font-black text-surface-900 dark:text-surface-0 mt-1">
            {{ currentStrategyDef?.name || '多因子選股策略' }}
          </h3>
          <p class="text-xs text-surface-500 mt-1 leading-relaxed">
            {{ currentStrategyDef?.description || '結合價值面、成長面與籌碼面多重條件，自動從全市場標的中篩選最具優勢之投資標的。' }}
          </p>
        </div>
        <div class="flex items-center gap-4 mt-3 pt-3 border-t border-surface-100 dark:border-surface-800 text-xs text-surface-400">
          <span>每日上限: <b class="text-surface-700 dark:text-surface-300">{{ currentStrategyDef?.max_picks_per_day || 10 }} 檔</b></span>
          <span>冷卻天數: <b class="text-surface-700 dark:text-surface-300">{{ currentStrategyDef?.cooldown_days || 10 }} 天</b></span>
        </div>
      </div>

      <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 p-4 shadow-sm !m-0 flex items-center gap-3">
        <div class="w-10 h-10 rounded-lg bg-emerald-50 dark:bg-emerald-900/30 text-emerald-500 flex items-center justify-center text-lg shrink-0">
          <i class="pi pi-check-circle"></i>
        </div>
        <div class="min-w-0">
          <div class="text-xs font-bold text-surface-400 uppercase tracking-wide">最新入選標的數</div>
          <div class="text-2xl font-black text-surface-900 dark:text-surface-0 num">
            {{ currentPicks.length }} 檔
          </div>
          <div class="text-xs text-surface-400">交易日: {{ latestScanDate || '—' }}</div>
        </div>
      </div>

      <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 p-4 shadow-sm !m-0 flex items-center gap-3">
        <div class="w-10 h-10 rounded-lg bg-blue-50 dark:bg-blue-900/30 text-blue-500 flex items-center justify-center text-lg shrink-0">
          <i class="pi pi-chart-pie"></i>
        </div>
        <div class="min-w-0">
          <div class="text-xs font-bold text-surface-400 uppercase tracking-wide">選股平均殖利率</div>
          <div class="text-2xl font-black text-surface-900 dark:text-surface-0 num">
            {{ avgYield != null ? `${avgYield.toFixed(2)}%` : '—' }}
          </div>
          <div class="text-xs text-surface-400">平均本益比: {{ avgPe != null ? `${avgPe.toFixed(1)}x` : '—' }}</div>
        </div>
      </div>
    </div>

    <!-- 選股精選結果 DataTable -->
    <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm overflow-hidden relative">
      <div v-if="loading" class="absolute inset-0 bg-surface-0/60 dark:bg-surface-900/60 backdrop-blur-xs z-10 flex items-center justify-center">
        <ProgressSpinner style="width: 50px; height: 50px" strokeWidth="4" />
      </div>

      <DataTable
        :value="currentPicks"
        responsiveLayout="scroll"
        class="p-datatable-sm"
      >
        <Column field="rank_value" header="排名" style="width: 4.5rem; text-align: center">
          <template #body="{ data, index }">
            <span
              class="w-7 h-7 rounded-full inline-flex items-center justify-center font-mono font-black text-xs"
              :class="index === 0 ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300' :
                      index === 1 ? 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200' :
                      index === 2 ? 'bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300' :
                      'bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-400'"
            >
              {{ data.rank_value || index + 1 }}
            </span>
          </template>
        </Column>

        <Column field="stock_id" header="股票代號" style="min-width: 6rem">
          <template #body="{ data }">
            <router-link
              :to="`/stock/${currentMarket}/${data.stock_id}`"
              class="font-mono font-bold text-primary hover:underline"
            >
              {{ data.stock_id }}
            </router-link>
          </template>
        </Column>

        <Column field="stock_name" header="名稱" style="min-width: 7rem">
          <template #body="{ data }">
            <span class="font-bold text-surface-900 dark:text-surface-0">{{ data.stock_name }}</span>
          </template>
        </Column>

        <Column field="signal_strength" header="強度" style="min-width: 5rem; text-align: center">
          <template #body="{ data }">
            <Tag
              :value="data.signal_strength === 'strong' ? '強烈' : data.signal_strength === 'moderate' ? '中等' : '一般'"
              :severity="data.signal_strength === 'strong' ? 'danger' : data.signal_strength === 'moderate' ? 'warning' : 'secondary'"
            />
          </template>
        </Column>

        <Column header="關鍵指標與條件細節" style="min-width: 14rem">
          <template #body="{ data }">
            <div class="flex flex-wrap gap-2 text-xs">
              <span v-if="data.details?.pe_ratio" class="px-2 py-0.5 rounded bg-surface-100 dark:bg-surface-800 font-mono">
                PE: <b>{{ data.details.pe_ratio.toFixed(1) }}</b>x
              </span>
              <span v-if="data.details?.dividend_yield" class="px-2 py-0.5 rounded bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600 font-mono">
                殖利率: <b>{{ data.details.dividend_yield.toFixed(2) }}%</b>
              </span>
              <span v-if="data.details?.yoy_percent != null || data.details?.revenue_yoy != null" class="px-2 py-0.5 rounded bg-blue-50 dark:bg-blue-900/30 text-blue-600 font-mono">
                YoY: <b>{{ (data.details.yoy_percent ?? data.details.revenue_yoy).toFixed(1) }}%</b>
              </span>
              <span v-if="data.details?.foreign_consec_days" class="px-2 py-0.5 rounded bg-purple-50 dark:bg-purple-900/30 text-purple-600 font-mono">
                外資連買 <b>{{ data.details.foreign_consec_days }}</b> 天
              </span>
              <span v-if="data.details?.trust_consec_days" class="px-2 py-0.5 rounded bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 font-mono">
                投信連買 <b>{{ data.details.trust_consec_days }}</b> 天
              </span>
            </div>
          </template>
        </Column>

        <Column field="suggested_action" header="建議操作" style="min-width: 16rem">
          <template #body="{ data }">
            <span class="text-xs text-surface-600 dark:text-surface-300 leading-relaxed">
              {{ data.suggested_action || '納入觀察名單分批佈局' }}
            </span>
          </template>
        </Column>

        <Column field="trade_date" header="觸發日期" style="min-width: 6rem; text-align: right">
          <template #body="{ data }">
            <span class="font-mono text-xs text-surface-400">{{ data.trade_date }}</span>
          </template>
        </Column>

        <Column header="操作" style="min-width: 6rem; text-align: center">
          <template #body="{ data }">
            <div class="flex items-center justify-center gap-1">
              <Button
                icon="pi pi-plus"
                size="small"
                text
                rounded
                v-tooltip.top="'加入追蹤清單'"
                @click="addToWatchlist(data.stock_id)"
              />
              <Button
                icon="pi pi-sliders-h"
                size="small"
                text
                rounded
                severity="info"
                v-tooltip.top="'加入比較報表'"
                @click="goToCompareSingle(data.stock_id)"
              />
            </div>
          </template>
        </Column>

        <template #empty>
          <div class="text-center p-8 text-surface-400">
            <i class="pi pi-inbox text-3xl mb-2 block"></i>
            目前無符合該策略條件之選股標的，請點擊上方「全市場選股掃描」按鈕更新
          </div>
        </template>
      </DataTable>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useToast } from 'primevue/usetoast';
import { alertApi } from '@/service/alertApi';
import { stockApi } from '@/service/stockApi';

const router = useRouter();
const toast = useToast();

const currentMarket = ref('tw');
const marketOptions = [
  { label: '台股 (TW)', value: 'tw' },
  { label: '美股 (US)', value: 'us' }
];

const pickingStrategies = [
  { id: 'pick_valuation_low_pe', name: '低本益比高殖利率精選', icon: 'pi pi-percentage', description: '篩選本益比低於 15 倍、殖利率高於 4% 之價值型投資標的，具備高度安全邊際。' },
  { id: 'pick_revenue_growth_momentum', name: '營收高成長動能精選', icon: 'pi pi-bolt', description: '篩選月營收年增率 (YoY) 超過 20% 且連續 2 個月維持高度成長之營運動能強勢股。' },
  { id: 'pick_chip_institutional_resonance', name: '法人籌碼共振精選', icon: 'pi pi-users', description: '外資與投信兩大主力法人連續買超且買超佔成交量達 5% 以上，籌碼面高度集中。' },
  { id: 'pick_multi_factor_resonance', name: '多因子共振旗艦精選', icon: 'pi pi-star-fill', description: '同時兼具低估值、營收成長超過 15% 與主力買超，多因子全方位共振之旗艦精選。' }
];

const activeStrategyId = ref('pick_valuation_low_pe');
const allAlerts = ref([]);
const loading = ref(false);
const scanning = ref(false);
const scanningRisk = ref(false);

const currentStrategyDef = computed(() => {
  return pickingStrategies.find(s => s.id === activeStrategyId.value);
});

const countsByStrategy = computed(() => {
  const map = {};
  for (const a of allAlerts.value) {
    map[a.strategy_id] = (map[a.strategy_id] || 0) + 1;
  }
  return map;
});

const currentPicks = computed(() => {
  return allAlerts.value.filter(a => a.strategy_id === activeStrategyId.value);
});

const latestScanDate = computed(() => {
  if (currentPicks.value.length > 0) {
    return currentPicks.value[0].trade_date;
  }
  return '';
});

const avgYield = computed(() => {
  const yields = currentPicks.value.map(p => p.details?.dividend_yield).filter(y => y != null);
  if (!yields.length) return null;
  return yields.reduce((a, b) => a + b, 0) / yields.length;
});

const avgPe = computed(() => {
  const pes = currentPicks.value.map(p => p.details?.pe_ratio).filter(p => p != null && p > 0);
  if (!pes.length) return null;
  return pes.reduce((a, b) => a + b, 0) / pes.length;
});

function setMarket(m) {
  currentMarket.value = m;
  loadAlerts();
}

function selectStrategy(stratId) {
  activeStrategyId.value = stratId;
}

async function loadAlerts() {
  loading.value = true;
  try {
    const res = await alertApi.getAlerts({
      market: currentMarket.value,
      days: 30,
      category: 'stock_picking'
    });
    if (res.success && res.data) {
      allAlerts.value = res.data;
    }
  } catch (err) {
    toast.add({ severity: 'error', summary: '載入失敗', detail: err.message || '無法取得選股記錄', life: 3000 });
  } finally {
    loading.value = false;
  }
}

async function runScan() {
  scanning.value = true;
  try {
    const res = await alertApi.triggerScan(currentMarket.value);
    if (res.success) {
      toast.add({
        severity: 'success',
        summary: '選股掃描完成',
        detail: `掃描 ${res.data?.scanned_stocks || 0} 檔，產生 ${res.data?.alerts_generated || 0} 筆精選標的`,
        life: 4000
      });
      await loadAlerts();
    }
  } catch (err) {
    toast.add({ severity: 'error', summary: '掃描失敗', detail: err.message || '選股掃描失敗', life: 3000 });
  } finally {
    scanning.value = false;
  }
}

async function runRiskScan() {
  scanningRisk.value = true;
  try {
    const response = await fetch(`${import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1'}/alerts/scan/positions?market=${currentMarket.value}`, {
      method: 'POST'
    });
    const res = await response.json();
    if (res.success) {
      toast.add({
        severity: 'info',
        summary: '風控掃描完成',
        detail: `檢查 ${res.data?.scanned_positions || 0} 檔持倉，觸發 ${res.data?.alerts_generated || 0} 筆出場警示`,
        life: 4000
      });
    }
  } catch (err) {
    toast.add({ severity: 'error', summary: '風控掃描失敗', detail: String(err), life: 3000 });
  } finally {
    scanningRisk.value = false;
  }
}

async function addToWatchlist(symbol) {
  try {
    await stockApi.addStock(symbol, currentMarket.value);
    toast.add({ severity: 'success', summary: '已加入追蹤', detail: `股票 ${symbol} 已加入追蹤清單`, life: 3000 });
  } catch (err) {
    toast.add({ severity: 'warn', summary: '提醒', detail: err.message || '加入追蹤失敗', life: 3000 });
  }
}

function goToCompareSingle(symbol) {
  router.push({ path: '/compare', query: { symbols: symbol } });
}

onMounted(() => {
  loadAlerts();
});
</script>
