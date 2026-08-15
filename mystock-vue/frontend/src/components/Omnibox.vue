<template>
  <Dialog 
    v-model:visible="visible" 
    modal 
    :showHeader="false" 
    :dismissableMask="true"
    contentClass="p-0 border-none bg-transparent shadow-none"
    class="w-full max-w-2xl mx-4 my-auto mt-[10vh]"
    @show="focusInput"
    @hide="onHide"
  >
    <div class="bg-surface-0 dark:bg-surface-900 rounded-xl shadow-2xl border border-surface-200 dark:border-surface-700 overflow-hidden flex flex-col max-h-[80vh]">
      <!-- 搜尋框區塊 -->
      <div class="relative flex items-center p-4 border-b border-surface-200 dark:border-surface-700">
        <i class="pi pi-search text-surface-400 text-xl absolute left-6"></i>
        <input 
          ref="searchInput"
          v-model="searchQuery"
          @input="onInput"
          @keydown.down.prevent="moveSelection(1)"
          @keydown.up.prevent="moveSelection(-1)"
          @keydown.enter.prevent="selectCurrent"
          @keydown.esc.prevent="visible = false"
          type="text" 
          class="w-full bg-transparent border-none outline-none pl-10 pr-4 py-2 text-lg text-surface-900 dark:text-surface-0 placeholder-surface-400 font-semibold"
          placeholder="搜尋股票代號或名稱..."
        />
        <div class="flex items-center gap-2">
          <button @click="visible = false" class="text-surface-400 hover:text-surface-600 dark:hover:text-surface-200 px-2">
            <i class="pi pi-times"></i>
          </button>
        </div>
      </div>

      <!-- 市場篩選 -->
      <div class="flex items-center gap-2 px-4 py-2 bg-surface-50 dark:bg-surface-800/50 border-b border-surface-200 dark:border-surface-700 text-xs font-bold">
        <span class="text-surface-500">搜尋範圍：</span>
        <button 
          @click="searchMarket = 'all'"
          :class="['px-2 py-1 rounded transition-colors', searchMarket === 'all' ? 'bg-primary text-primary-contrast' : 'text-surface-600 hover:bg-surface-200 dark:text-surface-300 dark:hover:bg-surface-700']"
        >全部市場</button>
        <button 
          v-for="m in enabledMarkets"
          :key="m.code"
          @click="searchMarket = m.code"
          :class="['px-2 py-1 rounded transition-colors', searchMarket === m.code ? 'bg-primary text-primary-contrast' : 'text-surface-600 hover:bg-surface-200 dark:text-surface-300 dark:hover:bg-surface-700']"
        >{{ m.label }}</button>
      </div>

      <!-- 搜尋結果區塊 -->
      <div class="overflow-y-auto flex-1 p-2 min-h-[200px]" ref="resultsContainer">
        <!-- 載入中 -->
        <div v-if="loading" class="flex justify-center items-center p-8 text-surface-500">
          <i class="pi pi-spin pi-spinner text-2xl mr-3"></i> 搜尋中...
        </div>
        
        <!-- 無結果 -->
        <div v-else-if="!loading && searchQuery && results.length === 0" class="flex justify-center items-center p-8 text-surface-500">
          找不到符合「{{ searchQuery }}」的股票
        </div>
        
        <!-- 未輸入時提示 -->
        <div v-else-if="!searchQuery" class="flex flex-col justify-center items-center p-8 text-surface-400 space-y-2">
          <i class="pi pi-search text-3xl mb-2 text-surface-300"></i>
          <p>輸入股票代號或名稱進行跨市場搜尋</p>
          <div class="flex items-center gap-4 mt-4 text-xs font-bold">
            <span class="flex items-center gap-1"><kbd class="px-1.5 py-0.5 bg-surface-200 dark:bg-surface-700 rounded">↑</kbd><kbd class="px-1.5 py-0.5 bg-surface-200 dark:bg-surface-700 rounded">↓</kbd> 選擇</span>
            <span class="flex items-center gap-1"><kbd class="px-1.5 py-0.5 bg-surface-200 dark:bg-surface-700 rounded">Enter</kbd> 開啟</span>
            <span class="flex items-center gap-1"><kbd class="px-1.5 py-0.5 bg-surface-200 dark:bg-surface-700 rounded">Esc</kbd> 關閉</span>
          </div>
        </div>

        <!-- 結果清單 -->
        <template v-else>
          <div v-for="(group, idx) in groupedResults" :key="group.market" class="mb-4 last:mb-0">
            <div class="px-3 py-1.5 text-[11px] font-bold text-surface-500 uppercase tracking-wider sticky top-0 bg-surface-0/95 dark:bg-surface-900/95 backdrop-blur z-10 border-b border-surface-100 dark:border-surface-800">
              {{ group.marketLabel }}
            </div>
            <ul class="m-0 p-0 list-none">
              <li 
                v-for="item in group.items" 
                :key="item.symbol"
                @click="selectItem(item)"
                @mouseenter="hoverItem(item)"
                :class="[
                  'px-4 py-3 cursor-pointer flex items-center justify-between border-b border-surface-100 dark:border-surface-800/50 last:border-0 transition-colors',
                  selectedIndex === item._index ? 'bg-primary-50 dark:bg-primary-900/20' : 'hover:bg-surface-50 dark:hover:bg-surface-800/40'
                ]"
              >
                <div class="flex items-center gap-3">
                  <div :class="[
                    'w-8 h-8 rounded-lg flex items-center justify-center font-bold text-xs',
                    selectedIndex === item._index ? 'bg-primary text-primary-contrast' : 'bg-surface-200 dark:bg-surface-700 text-surface-700 dark:text-surface-300'
                  ]">
                    {{ item.symbol.substring(0, 1) }}
                  </div>
                  <div>
                    <div class="font-bold text-surface-900 dark:text-surface-0 flex items-center gap-2">
                      <span class="num" v-html="highlight(item.symbol)"></span>
                      <span v-if="item.security_type" class="text-[10px] bg-surface-200 dark:bg-surface-700 text-surface-600 dark:text-surface-300 px-1 rounded">{{ item.security_type }}</span>
                    </div>
                    <div class="text-xs text-surface-500 font-medium" v-html="highlight(item.name || '')"></div>
                  </div>
                </div>
                <div class="text-right">
                  <div class="text-[11px] font-bold text-surface-400">{{ item.exchange }}</div>
                  <i v-if="selectedIndex === item._index" class="pi pi-chevron-right text-primary text-xs mt-1"></i>
                </div>
              </li>
            </ul>
          </div>
        </template>
      </div>
    </div>
  </Dialog>
</template>

<script setup>
import { ref, watch, computed, nextTick, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { useMarket } from '@/composables/useMarket';
import { stockApi } from '@/service/stockApi';
import debounce from 'lodash/debounce';

const visible = ref(false);
const searchQuery = ref('');
const searchMarket = ref('all');
const loading = ref(false);
const results = ref([]);
const selectedIndex = ref(0);
const searchInput = ref(null);
const resultsContainer = ref(null);

const router = useRouter();
const { enabledMarkets, setMarket } = useMarket();

// 將 Omnibox 掛載到全域快捷鍵 Ctrl+K
function handleGlobalKeydown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    visible.value = true;
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleGlobalKeydown);
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleGlobalKeydown);
});

function focusInput() {
  // 自動將 searchMarket 設為 'all' 或當前 active market
  searchQuery.value = '';
  results.value = [];
  selectedIndex.value = 0;
  nextTick(() => {
    if (searchInput.value) {
      searchInput.value.focus();
    }
  });
}

function onHide() {
  searchQuery.value = '';
  results.value = [];
}

const performSearch = debounce(async () => {
  if (!searchQuery.value.trim()) {
    results.value = [];
    return;
  }
  loading.value = true;
  try {
    // suggestSymbols 是模糊建議（代號前綴或名稱片段），回傳陣列；searchSymbols 是精確驗證，
    // 回傳以代號為 key 的物件——兩者形狀不同，Omnibox 這裡的分組/清單渲染需要的是前者。
    const market = searchMarket.value === 'all' ? null : searchMarket.value;
    const res = await stockApi.suggestSymbols(searchQuery.value.trim(), market, 30);
    if (res.success) {
      // 為所有結果加上絕對索引以便上下鍵選取
      let currentIdx = 0;
      results.value = res.data.map(item => ({ ...item, _index: currentIdx++ }));
      selectedIndex.value = 0;
    }
  } catch (err) {
    console.error('搜尋失敗', err);
    results.value = [];
  } finally {
    loading.value = false;
  }
}, 300);

function onInput() {
  performSearch();
}

watch(searchMarket, () => {
  performSearch();
});

const groupedResults = computed(() => {
  if (!results.value || results.value.length === 0) return [];
  const groups = {};
  for (const item of results.value) {
    if (!groups[item.market]) {
      const marketLabel = enabledMarkets.value.find(m => m.code === item.market)?.label || item.market;
      groups[item.market] = { market: item.market, marketLabel, items: [] };
    }
    groups[item.market].items.push(item);
  }
  return Object.values(groups);
});

function moveSelection(step) {
  if (results.value.length === 0) return;
  const maxIdx = results.value.length - 1;
  let newIdx = selectedIndex.value + step;
  if (newIdx < 0) newIdx = maxIdx;
  if (newIdx > maxIdx) newIdx = 0;
  selectedIndex.value = newIdx;
  
  // 捲動至可視範圍
  nextTick(() => {
    const activeEl = resultsContainer.value?.querySelector('.bg-primary-50, .dark\\:bg-primary-900\\/20');
    if (activeEl) {
      activeEl.scrollIntoView({ block: 'nearest' });
    }
  });
}

function selectCurrent() {
  if (results.value.length === 0) return;
  const item = results.value.find(r => r._index === selectedIndex.value);
  if (item) selectItem(item);
}

function selectItem(item) {
  visible.value = false;
  // 更新當前市場
  setMarket(item.market);
  // 導向個股頁
  router.push(`/stock/${item.market}/${item.symbol}`);
}

function hoverItem(item) {
  selectedIndex.value = item._index;
}

function highlight(text) {
  if (!searchQuery.value) return text;
  const query = searchQuery.value.trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const regex = new RegExp(`(${query})`, 'gi');
  return text.replace(regex, '<span class="text-primary font-black">$1</span>');
}

// 供外部父元件主動開啟
defineExpose({
  open: () => { visible.value = true; }
});
</script>

<style scoped>
/* 可加上針對高亮字的額外樣式調整 */
</style>
