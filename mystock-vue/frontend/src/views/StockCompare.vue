<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6">
    <Toast />

    <!-- 標題列 -->
    <div class="flex items-center flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h1 class="text-3xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
          <i class="pi pi-sliders-h text-primary text-3xl"></i>
          多股綜合比較報表
        </h1>
        <p class="text-base text-surface-500 mt-1">
          橫向對比多檔個股之估值水準、營收動能、法人籌碼與技術面指標（最多 10 檔）
        </p>
      </div>

      <div class="flex items-center gap-2">
        <Button
          label="匯出比較表"
          icon="pi pi-download"
          size="small"
          severity="secondary"
          @click="exportCompareCsv"
        />
      </div>
    </div>

    <!-- 標的選擇與快捷群組工具列 -->
    <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 p-4 shadow-sm space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center gap-2">
          <span class="text-xs font-bold text-surface-500">新增比較標的:</span>
          <div class="p-inputgroup w-48">
            <InputText
              v-model="inputSymbol"
              placeholder="輸入代號 (如 2330)"
              class="text-sm"
              @keydown.enter="addSymbol"
            />
            <Button icon="pi pi-plus" size="small" @click="addSymbol" />
          </div>
        </div>

        <!-- 快捷比較群組 -->
        <div class="flex flex-wrap items-center gap-2 text-xs">
          <span class="text-surface-400">快捷預設:</span>
          <button
            v-for="preset in presets"
            :key="preset.label"
            class="px-2.5 py-1 rounded-md bg-surface-100 dark:bg-surface-800 hover:bg-primary-50 dark:hover:bg-primary-900/30 text-surface-600 dark:text-surface-300 transition-colors font-medium cursor-pointer"
            @click="applyPreset(preset.symbols)"
          >
            {{ preset.label }}
          </button>
          <Button
            v-if="selectedSymbols.length > 0"
            label="清空"
            icon="pi pi-trash"
            size="small"
            severity="danger"
            text
            @click="clearAll"
          />
        </div>
      </div>

      <!-- 目前已選取的標的 Chips -->
      <div class="flex flex-wrap items-center gap-2 pt-2 border-t border-surface-100 dark:border-surface-800">
        <span class="text-xs text-surface-400">目前比較 ({{ selectedSymbols.length }}/10):</span>
        <Tag
          v-for="sym in selectedSymbols"
          :key="sym"
          :value="sym"
          severity="primary"
          class="cursor-pointer font-mono"
        >
          <template #default>
            <span class="flex items-center gap-1.5 px-1 py-0.5">
              <span>{{ sym }}</span>
              <i class="pi pi-times text-xs opacity-70 hover:opacity-100" @click.stop="removeSymbol(sym)"></i>
            </span>
          </template>
        </Tag>
        <span v-if="selectedSymbols.length === 0" class="text-xs text-surface-400 italic">
          尚未加入任何標的，請從上方輸入代號或點選快捷預設
        </span>
      </div>
    </div>

    <!-- 比較報表表格 -->
    <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm overflow-hidden relative">
      <div v-if="loading" class="absolute inset-0 bg-surface-0/60 dark:bg-surface-900/60 backdrop-blur-xs z-10 flex items-center justify-center">
        <ProgressSpinner style="width: 50px; height: 50px" strokeWidth="4" />
      </div>

      <DataTable
        :value="compareRows"
        responsiveLayout="scroll"
        class="p-datatable-sm"
      >
        <Column field="symbol" header="代號" frozen style="min-width: 5.5rem">
          <template #body="{ data }">
            <router-link
              :to="`/stock/tw/${data.symbol}`"
              class="font-mono font-bold text-primary hover:underline"
            >
              {{ data.symbol }}
            </router-link>
          </template>
        </Column>

        <Column field="name" header="名稱" frozen style="min-width: 6.5rem">
          <template #body="{ data }">
            <span class="font-bold text-surface-900 dark:text-surface-0">{{ data.name }}</span>
          </template>
        </Column>

        <Column field="close" header="收盤價" style="min-width: 5.5rem; text-align: right">
          <template #body="{ data }">
            <span class="font-mono font-black" :class="getPriceColor(data.change_percent)">
              {{ data.close != null ? data.close.toFixed(2) : '—' }}
            </span>
          </template>
        </Column>

        <Column field="change_percent" header="漲跌幅" style="min-width: 5.5rem; text-align: right">
          <template #body="{ data }">
            <span class="font-mono font-bold" :class="getPriceColor(data.change_percent)">
              {{ data.change_percent != null ? `${data.change_percent > 0 ? '+' : ''}${data.change_percent.toFixed(2)}%` : '—' }}
            </span>
          </template>
        </Column>

        <!-- 估值面指標 -->
        <Column field="pe_ratio" header="本益比" style="min-width: 5.5rem; text-align: right">
          <template #body="{ data }">
            <span class="font-mono" :class="isLowestPe(data.pe_ratio) ? 'text-emerald-600 dark:text-emerald-400 font-black' : ''">
              {{ data.pe_ratio != null ? `${data.pe_ratio.toFixed(2)}x` : '—' }}
            </span>
          </template>
        </Column>

        <Column field="pb_ratio" header="淨值比" style="min-width: 5rem; text-align: right">
          <template #body="{ data }">
            <span class="font-mono">{{ data.pb_ratio != null ? data.pb_ratio.toFixed(2) : '—' }}</span>
          </template>
        </Column>

        <Column field="dividend_yield" header="殖利率" style="min-width: 5.5rem; text-align: right">
          <template #body="{ data }">
            <span class="font-mono" :class="isHighestYield(data.dividend_yield) ? 'text-emerald-600 dark:text-emerald-400 font-black' : ''">
              {{ data.dividend_yield != null ? `${data.dividend_yield.toFixed(2)}%` : '—' }}
            </span>
          </template>
        </Column>

        <!-- 成長動能 -->
        <Column field="revenue_yoy" header="營收 YoY" style="min-width: 6rem; text-align: right">
          <template #body="{ data }">
            <span class="font-mono" :class="data.revenue_yoy && data.revenue_yoy > 0 ? 'text-red-500 font-bold' : 'text-emerald-500'">
              {{ data.revenue_yoy != null ? `${data.revenue_yoy > 0 ? '+' : ''}${data.revenue_yoy.toFixed(1)}%` : '—' }}
            </span>
          </template>
        </Column>

        <Column field="revenue_mom" header="營收 MoM" style="min-width: 6rem; text-align: right">
          <template #body="{ data }">
            <span class="font-mono" :class="data.revenue_mom && data.revenue_mom > 0 ? 'text-red-500' : 'text-emerald-500'">
              {{ data.revenue_mom != null ? `${data.revenue_mom > 0 ? '+' : ''}${data.revenue_mom.toFixed(1)}%` : '—' }}
            </span>
          </template>
        </Column>

        <!-- 籌碼面 -->
        <Column field="foreign_net_5d" header="外資近5日(張)" style="min-width: 6.5rem; text-align: right">
          <template #body="{ data }">
            <span class="font-mono" :class="getChipColor(data.foreign_net_5d)">
              {{ data.foreign_net_5d != null ? Math.round(data.foreign_net_5d).toLocaleString() : '—' }}
            </span>
          </template>
        </Column>

        <Column field="trust_net_5d" header="投信近5日(張)" style="min-width: 6.5rem; text-align: right">
          <template #body="{ data }">
            <span class="font-mono" :class="getChipColor(data.trust_net_5d)">
              {{ data.trust_net_5d != null ? Math.round(data.trust_net_5d).toLocaleString() : '—' }}
            </span>
          </template>
        </Column>

        <!-- 技術面 -->
        <Column field="ma20" header="月線 (MA20)" style="min-width: 6rem; text-align: right">
          <template #body="{ data }">
            <span class="font-mono">{{ data.ma20 != null ? data.ma20.toFixed(2) : '—' }}</span>
          </template>
        </Column>

        <Column field="bias_ma20" header="MA20乖離率" style="min-width: 6rem; text-align: right">
          <template #body="{ data }">
            <span class="font-mono" :class="data.bias_ma20 && data.bias_ma20 > 0 ? 'text-red-500' : 'text-emerald-500'">
              {{ data.bias_ma20 != null ? `${data.bias_ma20 > 0 ? '+' : ''}${data.bias_ma20.toFixed(2)}%` : '—' }}
            </span>
          </template>
        </Column>

        <Column field="kd_k" header="KD (9,3,3)" style="min-width: 6rem; text-align: center">
          <template #body="{ data }">
            <span class="font-mono text-xs">
              {{ data.kd_k != null ? `${data.kd_k.toFixed(1)} / ${data.kd_d.toFixed(1)}` : '—' }}
            </span>
          </template>
        </Column>

        <template #empty>
          <div class="text-center p-8 text-surface-400">
            <i class="pi pi-sliders-h text-3xl mb-2 block"></i>
            請在上方加入股票代號以開始多股橫向比較
          </div>
        </template>
      </DataTable>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useToast } from 'primevue/usetoast';

const route = useRoute();
const router = useRouter();
const toast = useToast();

const selectedSymbols = ref(['2330', '2317', '2454']);
const inputSymbol = ref('');
const compareRows = ref([]);
const loading = ref(false);

const presets = [
  { label: '晶圓與代工 (2330, 2317, 2303)', symbols: ['2330', '2317', '2303'] },
  { label: 'IC設計三雄 (2454, 2379, 3034)', symbols: ['2454', '2379', '3034'] },
  { label: 'AI 伺服器 (2382, 3231, 2376)', symbols: ['2382', '3231', '2376'] },
  { label: '金控雙雄 (2881, 2882)', symbols: ['2881', '2882'] }
];

function getPriceColor(change) {
  if (change == null || change === 0) return 'text-surface-900 dark:text-surface-0';
  return change > 0 ? 'text-red-500' : 'text-emerald-500';
}

function getChipColor(val) {
  if (val == null || val === 0) return 'text-surface-500';
  return val > 0 ? 'text-red-500' : 'text-emerald-500';
}

function isLowestPe(pe) {
  if (pe == null || pe <= 0) return false;
  const validPes = compareRows.value.map(r => r.pe_ratio).filter(p => p != null && p > 0);
  return pe === Math.min(...validPes);
}

function isHighestYield(y) {
  if (y == null || y <= 0) return false;
  const validYields = compareRows.value.map(r => r.dividend_yield).filter(v => v != null && v > 0);
  return y === Math.max(...validYields);
}

function addSymbol() {
  const sym = inputSymbol.value.trim().toUpperCase();
  if (!sym) return;
  if (selectedSymbols.value.includes(sym)) {
    toast.add({ severity: 'info', summary: '提醒', detail: `股票 ${sym} 已在比較清單中`, life: 2000 });
    inputSymbol.value = '';
    return;
  }
  if (selectedSymbols.value.length >= 10) {
    toast.add({ severity: 'warn', summary: '上限已達', detail: '最多支援同時比較 10 檔股票', life: 3000 });
    return;
  }
  selectedSymbols.value.push(sym);
  inputSymbol.value = '';
  syncUrlAndFetch();
}

function removeSymbol(sym) {
  selectedSymbols.value = selectedSymbols.value.filter(s => s !== sym);
  syncUrlAndFetch();
}

function clearAll() {
  selectedSymbols.value = [];
  compareRows.value = [];
  syncUrlAndFetch();
}

function applyPreset(syms) {
  selectedSymbols.value = [...syms];
  syncUrlAndFetch();
}

function syncUrlAndFetch() {
  const symStr = selectedSymbols.value.join(',');
  router.replace({ query: { symbols: symStr || undefined } });
  fetchCompareData();
}

async function fetchCompareData() {
  if (!selectedSymbols.value.length) {
    compareRows.value = [];
    return;
  }
  loading.value = true;
  try {
    const syms = selectedSymbols.value.join(',');
    const res = await fetch(`${import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1'}/fundamentals/compare?symbols=${syms}&market=tw`);
    const data = await res.json();
    if (data.success && data.data) {
      compareRows.value = data.data.rows || [];
    }
  } catch (err) {
    toast.add({ severity: 'error', summary: '載入失敗', detail: String(err), life: 3000 });
  } finally {
    loading.value = false;
  }
}

function exportCompareCsv() {
  if (!compareRows.value.length) return;
  let csv = '代號,名稱,交易所,收盤價,漲跌幅%,本益比,淨值比,殖利率%,營收YoY%,外資近5日(張),投信近5日(張),月線MA20\n';
  for (const r of compareRows.value) {
    csv += `"${r.symbol}","${r.name}","${r.exchange}",${r.close || ''},${r.change_percent || ''},${r.pe_ratio || ''},${r.pb_ratio || ''},${r.dividend_yield || ''},${r.revenue_yoy || ''},${r.foreign_net_5d || ''},${r.trust_net_5d || ''},${r.ma20 || ''}\n`;
  }
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `compare_${new Date().toISOString().slice(0, 10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

onMounted(() => {
  const querySyms = route.query.symbols;
  if (querySyms) {
    selectedSymbols.value = querySyms.split(',').map(s => s.trim()).filter(Boolean);
  }
  fetchCompareData();
});
</script>
