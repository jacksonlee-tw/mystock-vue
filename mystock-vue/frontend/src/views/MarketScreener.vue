<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6">
    <Toast />

    <!-- 標題列 -->
    <div class="flex items-center flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h1 class="text-3xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
          <i class="pi pi-table text-primary text-3xl"></i>
          全市場數據查詢
        </h1>
        <p class="text-base text-surface-500 mt-1">
          全市場每日收盤行情、三大法人買賣超、融資融券與價值面指標篩選（伺服器端即時排序與分頁）
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
          label="匯出 CSV"
          icon="pi pi-download"
          size="small"
          severity="secondary"
          :loading="exporting"
          @click="exportCsv"
        />
      </div>
    </div>

    <!-- 頂部 KPI 卡片（同列加 !m-0 確保高度一致，滿足 CLAUDE.md 硬規則 2） -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 p-4 shadow-sm !m-0 flex items-center gap-3">
        <div class="w-10 h-10 rounded-lg bg-primary-50 dark:bg-primary-900/30 text-primary flex items-center justify-center text-lg shrink-0">
          <i class="pi pi-calendar"></i>
        </div>
        <div class="min-w-0">
          <div class="text-xs font-bold text-surface-400 uppercase tracking-wide">資料交易日</div>
          <div class="text-xl font-black text-surface-900 dark:text-surface-0 num truncate">
            {{ currentDate || '載入中...' }}
          </div>
        </div>
      </div>

      <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 p-4 shadow-sm !m-0 flex items-center gap-3">
        <div class="w-10 h-10 rounded-lg bg-blue-50 dark:bg-blue-900/30 text-blue-500 flex items-center justify-center text-lg shrink-0">
          <i class="pi pi-list"></i>
        </div>
        <div class="min-w-0">
          <div class="text-xs font-bold text-surface-400 uppercase tracking-wide">全市場檔數</div>
          <div class="text-xl font-black text-surface-900 dark:text-surface-0 num truncate">
            {{ totalRecords.toLocaleString() }} 檔
          </div>
        </div>
      </div>

      <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 p-4 shadow-sm !m-0 flex items-center gap-3">
        <div class="w-10 h-10 rounded-lg bg-emerald-50 dark:bg-emerald-900/30 text-emerald-500 flex items-center justify-center text-lg shrink-0">
          <i class="pi pi-chart-line"></i>
        </div>
        <div class="min-w-0">
          <div class="text-xs font-bold text-surface-400 uppercase tracking-wide">目前排序方式</div>
          <div class="text-xl font-black text-surface-900 dark:text-surface-0 num truncate">
            {{ sortLabels[sortField] || sortField }} ({{ sortOrder === 'desc' ? '降序' : '升序' }})
          </div>
        </div>
      </div>

      <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 p-4 shadow-sm !m-0 flex items-center gap-3">
        <div class="w-10 h-10 rounded-lg bg-amber-50 dark:bg-amber-900/30 text-amber-500 flex items-center justify-center text-lg shrink-0">
          <i class="pi pi-shield"></i>
        </div>
        <div class="min-w-0">
          <div class="text-xs font-bold text-surface-400 uppercase tracking-wide">資料健康狀態</div>
          <div class="text-xl font-black text-surface-900 dark:text-surface-0 num truncate">
            {{ statusInfo?.quote_suspect > 0 ? `${statusInfo.quote_suspect} 筆可疑` : '正常 (100% OK)' }}
          </div>
        </div>
      </div>
    </div>

    <!-- 資料同步：目前唯一能手動觸發／查看全市場批次抓取（market/fetch）進度的入口 -->
    <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 p-4 shadow-sm space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center gap-3">
          <i class="pi pi-sync text-primary text-lg"></i>
          <div>
            <div class="text-sm font-bold text-surface-900 dark:text-surface-0">全市場資料同步</div>
            <div class="text-xs text-surface-500">
              <template v-if="isJobRunning">
                進行中：{{ jobInfo.scope === 'backfill' ? '批次回補' : '每日排程' }}
                <span v-if="jobInfo.cursor_date">，目前處理到 {{ jobInfo.cursor_date }}</span>
              </template>
              <template v-else-if="jobInfo && jobInfo.status === 'failed'">
                <span class="text-red-500">上次同步失敗：{{ jobInfo.last_error || '未知錯誤' }}</span>
              </template>
              <template v-else-if="jobInfo && jobInfo.status === 'interrupted'">
                <span class="text-amber-500">上次同步已中止（{{ jobInfo.done_days }}/{{ jobInfo.total_days }} 天）：{{ jobInfo.last_error || '使用者主動取消' }}</span>
              </template>
              <template v-else-if="jobInfo && jobInfo.status === 'completed_with_errors'">
                <span class="text-amber-500">上次同步完成但有失敗（成功 {{ jobInfo.done_days }} 天／失敗 {{ jobInfo.failed_days }} 天）</span>
              </template>
              <template v-else-if="jobInfo && jobInfo.status === 'completed'">
                上次同步完成於 {{ jobInfo.created_at }}（{{ jobInfo.done_days }}/{{ jobInfo.total_days }} 天）
              </template>
              <template v-else>
                尚無同步紀錄，選擇日期區間後點擊「立即同步」
              </template>
            </div>
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <DatePicker v-model="syncStart" placeholder="起始日期" dateFormat="yy-mm-dd" showIcon iconDisplay="input" class="w-44" inputClass="text-sm" :disabled="isJobRunning" />
          <span class="text-surface-400 text-xs">~</span>
          <DatePicker v-model="syncEnd" placeholder="結束日期" dateFormat="yy-mm-dd" showIcon iconDisplay="input" class="w-44" inputClass="text-sm" :disabled="isJobRunning" />
          <Button
            v-if="!isJobRunning"
            label="立即同步"
            icon="pi pi-cloud-download"
            size="small"
            :loading="triggering"
            @click="triggerSync"
          />
          <Button
            v-else
            label="取消同步"
            icon="pi pi-times"
            size="small"
            severity="danger"
            outlined
            :loading="cancelling"
            @click="cancelSync"
          />
        </div>
      </div>

      <div v-if="isJobRunning" class="space-y-1">
        <ProgressBar :value="jobProgressPercent" :showValue="true" style="height: 8px" />
        <div class="text-xs text-surface-500 text-right">{{ jobInfo.done_days }} / {{ jobInfo.total_days }} 天（失敗 {{ jobInfo.failed_days }} 天）</div>
      </div>
    </div>

    <!-- 篩選器與控制列 -->
    <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 p-4 shadow-sm space-y-4">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="flex flex-wrap items-center gap-3">
          <!-- 日期選單 -->
          <div class="flex items-center gap-2">
            <span class="text-xs font-bold text-surface-500">交易日:</span>
            <Select
              v-model="selectedDate"
              :options="availableDates"
              placeholder="選擇日期"
              class="w-36 text-sm"
              @change="fetchData(1)"
            />
          </div>

          <!-- 交易所 -->
          <div class="flex items-center gap-2">
            <span class="text-xs font-bold text-surface-500">交易所:</span>
            <Select
              v-model="filters.exchange"
              :options="exchangeOptions"
              optionLabel="label"
              optionValue="value"
              placeholder="全部"
              class="w-32 text-sm"
              @change="fetchData(1)"
            />
          </div>

          <!-- 搜尋代號 / 名稱 -->
          <div class="flex items-center gap-2">
            <span class="p-input-icon-left">
              <i class="pi pi-search text-surface-400"></i>
              <InputText
                v-model="filters.q"
                placeholder="搜尋代號或名稱..."
                class="w-44 text-sm"
                @keydown.enter="fetchData(1)"
              />
            </span>
            <Button icon="pi pi-search" size="small" @click="fetchData(1)" />
          </div>
        </div>

        <div class="flex items-center gap-2">
          <!-- 批次比較按鈕 -->
          <Button
            v-if="selectedRows.length > 0"
            :label="`加入比較 (${selectedRows.length})`"
            icon="pi pi-sliders-h"
            size="small"
            severity="info"
            @click="goToCompare"
          />

          <!-- 欄位多選切換 (MultiSelect) -->
          <MultiSelect
            v-model="visibleColumns"
            :options="allColumns"
            optionLabel="header"
            optionValue="field"
            placeholder="自訂欄位"
            display="chip"
            class="w-48 text-sm"
            @change="onColumnToggle"
          />

          <Button
            :label="showAdvancedFilters ? '收合進階' : '進階篩選'"
            :icon="showAdvancedFilters ? 'pi pi-chevron-up' : 'pi pi-chevron-down'"
            size="small"
            severity="secondary"
            outlined
            @click="showAdvancedFilters = !showAdvancedFilters"
          />
        </div>
      </div>

      <!-- 進階數值區間篩選面板 -->
      <div v-if="showAdvancedFilters" class="pt-3 border-t border-surface-100 dark:border-surface-800 grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
        <div>
          <label class="font-bold text-surface-500 mb-1 block">本益比 (PE) 區間</label>
          <div class="flex items-center gap-1">
            <InputNumber v-model="filters.min_pe_ratio" placeholder="Min" class="w-full text-xs" :minFractionDigits="1" />
            <span>~</span>
            <InputNumber v-model="filters.max_pe_ratio" placeholder="Max" class="w-full text-xs" :minFractionDigits="1" />
          </div>
        </div>

        <div>
          <label class="font-bold text-surface-500 mb-1 block">殖利率 (%) 下限</label>
          <InputNumber v-model="filters.min_dividend_yield" placeholder="例如: 5.0" class="w-full text-xs" :minFractionDigits="1" suffix="%" />
        </div>

        <div>
          <label class="font-bold text-surface-500 mb-1 block">股價淨值比 (PB) 上限</label>
          <InputNumber v-model="filters.max_pb_ratio" placeholder="例如: 2.0" class="w-full text-xs" :minFractionDigits="1" />
        </div>

        <div>
          <label class="font-bold text-surface-500 mb-1 block">三大法人買賣超 (張) 下限</label>
          <InputNumber v-model="filters.min_institutional_net" placeholder="例如: 1000" class="w-full text-xs" />
        </div>

        <div class="col-span-2 md:col-span-4 flex items-center justify-end gap-2 pt-2">
          <Button label="重設篩選" icon="pi pi-refresh" severity="secondary" text size="small" @click="resetFilters" />
          <Button label="套用篩選" icon="pi pi-check" size="small" @click="fetchData(1)" />
        </div>
      </div>
    </div>

    <!-- 全市場資料 DataTable（Lazy 伺服器端分頁與排序） -->
    <div class="rounded-xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm overflow-hidden relative">
      <!-- 重新整理/載入時的半透明遮罩（不整頁卸載，滿足 CLAUDE.md 硬規則 1） -->
      <div v-if="loading" class="absolute inset-0 bg-surface-0/60 dark:bg-surface-900/60 backdrop-blur-xs z-10 flex items-center justify-center">
        <ProgressSpinner style="width: 50px; height: 50px" strokeWidth="4" />
      </div>

      <DataTable
        :value="tableData"
        :lazy="true"
        :paginator="true"
        :rows="pageSize"
        :first="(currentPage - 1) * pageSize"
        :totalRecords="totalRecords"
        :rowsPerPageOptions="[20, 50, 100]"
        v-model:selection="selectedRows"
        dataKey="symbol"
        responsiveLayout="scroll"
        class="p-datatable-sm"
        @page="onPage($event)"
        @sort="onSort($event)"
      >
        <Column selectionMode="multiple" headerStyle="width: 3rem" />

        <Column field="symbol" header="代號" :sortable="true" style="min-width: 5.5rem">
          <template #body="{ data }">
            <router-link
              :to="`/stock/${currentMarket}/${data.symbol}`"
              class="font-mono font-bold text-primary hover:underline"
            >
              {{ data.symbol }}
            </router-link>
          </template>
        </Column>

        <Column field="name" header="名稱" style="min-width: 6.5rem">
          <template #body="{ data }">
            <span class="font-bold text-surface-900 dark:text-surface-0">{{ data.name }}</span>
          </template>
        </Column>

        <Column v-if="isColVisible('exchange')" field="exchange" header="交易所" style="min-width: 4.5rem">
          <template #body="{ data }">
            <Tag :value="data.exchange" :severity="data.exchange === 'TWSE' ? 'primary' : 'info'" />
          </template>
        </Column>

        <Column v-if="isColVisible('close')" field="close" header="收盤價" :sortable="true" style="min-width: 5.5rem; text-align: right">
          <template #body="{ data }">
            <span class="font-mono font-black" :class="getPriceColor(data.change_amount)">
              {{ formatNumber(data.close) }}
            </span>
          </template>
        </Column>

        <Column v-if="isColVisible('change_percent')" field="change_percent" header="漲跌幅" :sortable="true" style="min-width: 5.5rem; text-align: right">
          <template #body="{ data }">
            <span class="font-mono font-bold" :class="getPriceColor(data.change_amount)">
              {{ data.change_percent != null ? `${data.change_percent > 0 ? '+' : ''}${data.change_percent.toFixed(2)}%` : '—' }}
            </span>
          </template>
        </Column>

        <Column v-if="isColVisible('volume')" field="volume" header="成交張數" :sortable="true" style="min-width: 6rem; text-align: right">
          <template #body="{ data }">
            <span class="font-mono text-surface-700 dark:text-surface-300">
              {{ data.volume != null ? Math.round(data.volume / 1000).toLocaleString() : '—' }}
            </span>
          </template>
        </Column>

        <Column v-if="isColVisible('turnover')" field="turnover" header="成交金額" :sortable="true" style="min-width: 6.5rem; text-align: right">
          <template #body="{ data }">
            <span class="font-mono text-surface-700 dark:text-surface-300">
              {{ formatAmount(data.turnover) }}
            </span>
          </template>
        </Column>

        <Column v-if="isColVisible('pe_ratio')" field="pe_ratio" header="本益比" :sortable="true" style="min-width: 5rem; text-align: right">
          <template #body="{ data }">
            <span class="font-mono" :class="data.pe_ratio && data.pe_ratio < 15 ? 'text-emerald-500 font-bold' : ''">
              {{ data.pe_ratio != null ? data.pe_ratio.toFixed(2) : '—' }}
            </span>
          </template>
        </Column>

        <Column v-if="isColVisible('pb_ratio')" field="pb_ratio" header="股價淨值比" :sortable="true" style="min-width: 5.5rem; text-align: right">
          <template #body="{ data }">
            <span class="font-mono">
              {{ data.pb_ratio != null ? data.pb_ratio.toFixed(2) : '—' }}
            </span>
          </template>
        </Column>

        <Column v-if="isColVisible('dividend_yield')" field="dividend_yield" header="殖利率" :sortable="true" style="min-width: 5rem; text-align: right">
          <template #body="{ data }">
            <span class="font-mono" :class="data.dividend_yield && data.dividend_yield >= 5 ? 'text-emerald-500 font-bold' : ''">
              {{ data.dividend_yield != null ? `${data.dividend_yield.toFixed(2)}%` : '—' }}
            </span>
          </template>
        </Column>

        <Column v-if="isColVisible('foreign_net')" field="foreign_net" header="外資(張)" :sortable="true" style="min-width: 5.5rem; text-align: right">
          <template #body="{ data }">
            <span class="font-mono" :class="getChipColor(data.foreign_net)">
              {{ data.foreign_net != null ? Math.round(data.foreign_net / 1000).toLocaleString() : '—' }}
            </span>
          </template>
        </Column>

        <Column v-if="isColVisible('trust_net')" field="trust_net" header="投信(張)" :sortable="true" style="min-width: 5.5rem; text-align: right">
          <template #body="{ data }">
            <span class="font-mono" :class="getChipColor(data.trust_net)">
              {{ data.trust_net != null ? Math.round(data.trust_net / 1000).toLocaleString() : '—' }}
            </span>
          </template>
        </Column>

        <Column v-if="isColVisible('institutional_net')" field="institutional_net" header="三大法人(張)" :sortable="true" style="min-width: 6.5rem; text-align: right">
          <template #body="{ data }">
            <span class="font-mono font-bold" :class="getChipColor(data.institutional_net)">
              {{ data.institutional_net != null ? Math.round(data.institutional_net / 1000).toLocaleString() : '—' }}
            </span>
          </template>
        </Column>

        <Column v-if="isColVisible('margin_balance')" field="margin_balance" header="融資餘額(張)" :sortable="true" style="min-width: 6rem; text-align: right">
          <template #body="{ data }">
            <span class="font-mono text-surface-600 dark:text-surface-400">
              {{ data.margin_balance != null ? data.margin_balance.toLocaleString() : '—' }}
            </span>
          </template>
        </Column>

        <Column v-if="isColVisible('mcap_rank')" field="mcap_rank" header="市值排名" :sortable="true" style="min-width: 5.5rem; text-align: center">
          <template #body="{ data }">
            <Tag v-if="data.mcap_rank && data.mcap_rank <= 50" value="Top 50" severity="warning" />
            <Tag v-else-if="data.mcap_rank && data.mcap_rank <= 100" value="Top 100" severity="secondary" />
            <span v-else class="font-mono text-xs text-surface-400">{{ data.mcap_rank || '—' }}</span>
          </template>
        </Column>

        <Column header="操作" style="min-width: 4rem; text-align: center">
          <template #body="{ data }">
            <Button
              icon="pi pi-plus"
              size="small"
              text
              rounded
              v-tooltip.top="'加入追蹤清單'"
              @click="addToWatchlist(data.symbol)"
            />
          </template>
        </Column>

        <template #empty>
          <div class="text-center p-8 text-surface-400">
            <i class="pi pi-search text-3xl mb-2 block"></i>
            查無符合條件之全市場資料
          </div>
        </template>
      </DataTable>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { useToast } from 'primevue/usetoast';
import { marketApi } from '@/service/marketApi';
import { stockApi } from '@/service/stockApi';

const router = useRouter();
const toast = useToast();

const currentMarket = ref('tw');
const marketOptions = [
  { label: '台股 (TW)', value: 'tw' },
  { label: '美股 (US)', value: 'us' }
];

const exchangeOptions = [
  { label: '全部交易所', value: null },
  { label: '上市 (TWSE)', value: 'TWSE' },
  { label: '上櫃 (TPEx)', value: 'TPEx' }
];

const availableDates = ref([]);
const selectedDate = ref('');
const currentDate = ref('');
const statusInfo = ref(null);

const tableData = ref([]);
const totalRecords = ref(0);
const currentPage = ref(1);
const pageSize = ref(50);
const sortField = ref('turnover');
const sortOrder = ref('desc');
const loading = ref(false);
const exporting = ref(false);
const selectedRows = ref([]);
const showAdvancedFilters = ref(false);

const sortLabels = {
  turnover: '成交金額',
  volume: '成交量',
  close: '收盤價',
  change_percent: '漲跌幅',
  pe_ratio: '本益比',
  dividend_yield: '殖利率',
  foreign_net: '外資買賣超',
  institutional_net: '三大法人買賣超',
  margin_balance: '融資餘額',
  mcap_rank: '市值排名'
};

const allColumns = [
  { field: 'exchange', header: '交易所' },
  { field: 'close', header: '收盤價' },
  { field: 'change_percent', header: '漲跌幅' },
  { field: 'volume', header: '成交張數' },
  { field: 'turnover', header: '成交金額' },
  { field: 'pe_ratio', header: '本益比' },
  { field: 'pb_ratio', header: '股價淨值比' },
  { field: 'dividend_yield', header: '殖利率' },
  { field: 'foreign_net', header: '外資買賣超' },
  { field: 'trust_net', header: '投信買賣超' },
  { field: 'institutional_net', header: '三大法人合計' },
  { field: 'margin_balance', header: '融資餘額' },
  { field: 'mcap_rank', header: '市值排名' }
];

const STORAGE_KEY = 'mystock:market:visible-columns';
const defaultVisibleCols = ['exchange', 'close', 'change_percent', 'volume', 'turnover', 'pe_ratio', 'dividend_yield', 'institutional_net', 'mcap_rank'];
const visibleColumns = ref(JSON.parse(localStorage.getItem(STORAGE_KEY) || JSON.stringify(defaultVisibleCols)));

const filters = reactive({
  exchange: null,
  q: '',
  min_pe_ratio: null,
  max_pe_ratio: null,
  min_dividend_yield: null,
  max_pb_ratio: null,
  min_institutional_net: null
});

function isColVisible(field) {
  return visibleColumns.value.includes(field);
}

function onColumnToggle() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(visibleColumns.value));
}

function setMarket(m) {
  currentMarket.value = m;
  fetchDates();
}

function getPriceColor(change) {
  if (change == null || change === 0) return 'text-surface-900 dark:text-surface-0';
  // 台股紅漲綠跌
  return change > 0 ? 'text-red-500' : 'text-emerald-500';
}

function getChipColor(val) {
  if (val == null || val === 0) return 'text-surface-500';
  return val > 0 ? 'text-red-500' : 'text-emerald-500';
}

function formatNumber(val) {
  if (val == null) return '—';
  return val.toFixed(2);
}

function formatAmount(amt) {
  if (amt == null) return '—';
  if (amt >= 100000000) {
    return `${(amt / 100000000).toFixed(2)} 億`;
  }
  if (amt >= 10000) {
    return `${(amt / 10000).toFixed(0)} 萬`;
  }
  return amt.toLocaleString();
}

async function fetchDates() {
  try {
    const res = await marketApi.getMarketDates(currentMarket.value);
    if (res.success && res.data) {
      availableDates.value = res.data;
      if (res.data.length > 0 && !selectedDate.value) {
        selectedDate.value = res.data[0];
      }
    }
  } catch (e) {
    console.error('Fetch dates failed', e);
  }
  fetchData(1);
  fetchStatus();
}

// ── 資料同步（手動觸發全市場批次抓取 + 進度輪詢）──────────────────────────
const syncStart = ref(null);
const syncEnd = ref(null);
const triggering = ref(false);
const cancelling = ref(false);
let pollTimer = null;

const jobInfo = computed(() => statusInfo.value?.last_job || null);
const isJobRunning = computed(() => jobInfo.value?.status === 'running');
const jobProgressPercent = computed(() => {
  const j = jobInfo.value;
  if (!j || !j.total_days) return 0;
  return Math.round((j.done_days / j.total_days) * 100);
});

function toDateStr(d) {
  if (!d) return null;
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

// 預設區間：從目前最新資料日的隔天補到昨天；若完全沒有資料，回補最近 30 天。
function initDefaultSyncRange() {
  if (syncStart.value || syncEnd.value) return;
  const end = new Date();
  end.setDate(end.getDate() - 1);
  let start;
  if (statusInfo.value?.latest_trade_date) {
    start = new Date(statusInfo.value.latest_trade_date);
    start.setDate(start.getDate() + 1);
  } else {
    start = new Date(end);
    start.setDate(start.getDate() - 30);
  }
  syncStart.value = start;
  syncEnd.value = end;
}

let lastSeenJobStatus = null;

async function fetchStatus() {
  try {
    const res = await marketApi.getMarketStatus(currentMarket.value);
    if (res.success) {
      const prevStatus = lastSeenJobStatus;
      statusInfo.value = res.data;
      initDefaultSyncRange();

      const newStatus = jobInfo.value?.status;
      const justFinished = prevStatus === 'running' && newStatus && newStatus !== 'running';
      lastSeenJobStatus = newStatus || null;

      if (justFinished) {
        stopPolling();
        if (newStatus === 'completed') {
          toast.add({ severity: 'success', summary: '同步完成', detail: `已完成 ${jobInfo.value.done_days}/${jobInfo.value.total_days} 天`, life: 4000 });
        } else if (newStatus === 'completed_with_errors') {
          toast.add({ severity: 'warn', summary: '同步完成（部分失敗）', detail: `成功 ${jobInfo.value.done_days} 天，失敗 ${jobInfo.value.failed_days} 天`, life: 5000 });
        } else if (newStatus === 'interrupted') {
          // 中止是取消／熔斷的正常結果，不是錯誤，不該報紅
          toast.add({ severity: 'info', summary: '同步已中止', detail: jobInfo.value?.last_error || `已完成 ${jobInfo.value.done_days}/${jobInfo.value.total_days} 天`, life: 4000 });
        } else {
          toast.add({ severity: 'error', summary: '同步失敗', detail: jobInfo.value?.last_error || '未知錯誤', life: 5000 });
        }
        fetchDates();
      } else if (isJobRunning.value) {
        startPolling();
      } else {
        stopPolling();
      }
    }
  } catch (e) {
    console.error('Fetch status failed', e);
  }
}

function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(fetchStatus, 3000);
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function triggerSync() {
  if (!syncStart.value || !syncEnd.value) {
    toast.add({ severity: 'warn', summary: '請選擇日期區間', life: 3000 });
    return;
  }
  triggering.value = true;
  try {
    const res = await marketApi.triggerMarketFetch({
      start: toDateStr(syncStart.value),
      end: toDateStr(syncEnd.value)
    });
    if (res.success) {
      toast.add({ severity: 'success', summary: '已啟動同步', detail: res.message, life: 3000 });
      await fetchStatus();
      startPolling();
    }
  } catch (err) {
    toast.add({ severity: 'error', summary: '啟動同步失敗', detail: err.response?.data?.detail || err.message, life: 4000 });
  } finally {
    triggering.value = false;
  }
}

async function cancelSync() {
  cancelling.value = true;
  try {
    const res = await marketApi.cancelMarketFetch();
    // 顯示後端實際的處理結果：作業可能是「已送出取消旗標」，也可能是殘留紀錄被直接收掉，
    // 兩者對使用者的意義不同，不能一律報「已送出取消請求」。
    toast.add({ severity: 'info', summary: '取消同步', detail: res.message || '已送出取消請求', life: 4000 });
    await fetchStatus(); // 立刻回抓一次，殘留紀錄被收掉時進度卡才會馬上恢復
  } catch (err) {
    toast.add({ severity: 'error', summary: '取消失敗', detail: err.response?.data?.detail || err.message, life: 3000 });
  } finally {
    cancelling.value = false;
  }
}

async function fetchData(page = 1) {
  currentPage.value = page;
  loading.value = true;
  try {
    const params = {
      date: selectedDate.value || undefined,
      market: currentMarket.value,
      exchange: filters.exchange || undefined,
      q: filters.q.trim() || undefined,
      sort: sortField.value,
      order: sortOrder.value,
      page: currentPage.value,
      page_size: pageSize.value,
      min_pe_ratio: filters.min_pe_ratio ?? undefined,
      max_pe_ratio: filters.max_pe_ratio ?? undefined,
      min_dividend_yield: filters.min_dividend_yield ?? undefined,
      max_pb_ratio: filters.max_pb_ratio ?? undefined,
      min_institutional_net: filters.min_institutional_net ? filters.min_institutional_net * 1000 : undefined
    };

    const res = await marketApi.getMarketDaily(params);
    if (res.success && res.data) {
      tableData.value = res.data.rows || [];
      totalRecords.value = res.data.total || 0;
      currentDate.value = res.data.trade_date || selectedDate.value;
      if (!selectedDate.value && res.data.trade_date) {
        selectedDate.value = res.data.trade_date;
      }
    }
  } catch (err) {
    toast.add({ severity: 'error', summary: '查詢失敗', detail: err.message || '無法取得全市場資料', life: 3000 });
  } finally {
    loading.value = false;
  }
}

function onPage(event) {
  pageSize.value = event.rows;
  fetchData(event.page + 1);
}

function onSort(event) {
  sortField.value = event.sortField || 'turnover';
  sortOrder.value = event.sortOrder === 1 ? 'asc' : 'desc';
  fetchData(1);
}

function resetFilters() {
  filters.exchange = null;
  filters.q = '';
  filters.min_pe_ratio = null;
  filters.max_pe_ratio = null;
  filters.min_dividend_yield = null;
  filters.max_pb_ratio = null;
  filters.min_institutional_net = null;
  fetchData(1);
}

function goToCompare() {
  const syms = selectedRows.value.map(r => r.symbol).join(',');
  router.push({ path: '/compare', query: { symbols: syms } });
}

async function addToWatchlist(symbol) {
  try {
    await stockApi.addTrackedStock(symbol, currentMarket.value);
    toast.add({
      severity: 'success', summary: '已加入追蹤',
      detail: `股票 ${symbol} 已加入追蹤清單；可至「追蹤與觀察名單」頁補充追蹤原因、標籤或目標買進價`,
      life: 4000
    });
  } catch (err) {
    toast.add({ severity: 'warn', summary: '提醒', detail: err.message || '加入追蹤失敗或已在清單中', life: 3000 });
  }
}

async function exportCsv() {
  exporting.value = true;
  try {
    const params = new URLSearchParams({
      date: selectedDate.value || '',
      market: currentMarket.value,
      format: 'csv',
      sort: sortField.value,
      order: sortOrder.value
    });
    window.open(`${import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1'}/market/daily?${params.toString()}`);
  } catch (e) {
    toast.add({ severity: 'error', summary: '匯出失敗', detail: String(e), life: 3000 });
  } finally {
    exporting.value = false;
  }
}

onMounted(() => {
  fetchDates();
});

onUnmounted(() => {
  stopPolling();
});
</script>
