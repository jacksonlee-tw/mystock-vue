<template>
  <div class="p-4 sm:p-6 max-w-7xl mx-auto space-y-6">
    <Toast />

    <!-- 頁面頂部 Header -->
    <div class="flex items-center flex-col md:flex-row md:items-center justify-between gap-4">
      <div>
        <h1 class="text-2xl sm:text-3xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
          <i class="pi pi-share-alt text-primary text-2xl"></i>
          產業鏈知識圖譜與輪動雷達
        </h1>
        <p class="text-xs sm:text-sm text-surface-500 mt-1">
          產業鏈關聯圖 + 輪動外溢雷達清單（docs/16.AI技術分析/Phase3-產業鏈知識圖譜與輪動模型.md §7、§8）
        </p>
      </div>

      <div class="flex items-center gap-2 self-start md:self-auto shrink-0 flex-wrap">
        <Select
          v-model="chainId"
          :options="chains"
          optionLabel="name"
          optionValue="chain_id"
          placeholder="選擇產業鏈"
          class="w-56"
          @change="fetchGraphAndRadar"
        />
        <Button label="重新整理" icon="pi pi-refresh" :loading="loading" text @click="fetchAll" />
        <Button label="管理產業鏈" icon="pi pi-cog" outlined @click="configVisible = true" />
        <Button label="觸發本鏈萃取" icon="pi pi-bolt" severity="warn" :loading="triggering" @click="confirmTrigger" />
      </div>
    </div>

    <IndustryChainConfigDialog v-model:visible="configVisible" @saved="fetchAll" />

    <!-- 功能未啟用 / 資料庫不可用（AC-IC-15、AC-IC-5）-->
    <div v-if="disabledMessage" class="card p-6 border border-amber-300 bg-amber-50 dark:bg-amber-900/20 rounded-2xl text-amber-700 dark:text-amber-300">
      <div class="flex items-center gap-3">
        <i class="pi pi-info-circle text-2xl"></i>
        <div>
          <h4 class="font-bold">功能未啟用</h4>
          <p class="text-sm mt-0.5">{{ disabledMessage }}</p>
        </div>
      </div>
    </div>

    <!-- 初次載入：整頁 loading（只在完全沒有資料時顯示，見 CLAUDE.md 鐵則 1）-->
    <div v-else-if="loading && !graphData" class="flex flex-col items-center justify-center p-12 card bg-surface-0 dark:bg-surface-900 rounded-2xl border border-surface-200 dark:border-surface-700">
      <i class="pi pi-spin pi-spinner text-primary text-4xl mb-3"></i>
      <p class="text-sm font-semibold text-surface-600 dark:text-surface-400">正在載入產業鏈圖譜...</p>
    </div>

    <!-- 完全沒有既有資料時的錯誤畫面；刷新中途失敗則保留舊資料原地顯示 -->
    <div v-else-if="error && !graphData" class="card p-6 border border-red-300 bg-red-50 dark:bg-red-900/20 rounded-2xl text-red-700 dark:text-red-300">
      <div class="flex items-center gap-3">
        <i class="pi pi-exclamation-circle text-2xl"></i>
        <div>
          <h4 class="font-bold">資料讀取失敗</h4>
          <p class="text-sm mt-0.5">{{ error }}</p>
        </div>
      </div>
    </div>

    <!-- 主視圖：切換產業鏈時 loading 為 true，但保留舊內容掛載、只用覆蓋層提示刷新中，
         不整頁卸載，避免捲動位置被重置到頂部（CLAUDE.md 鐵則 1，比照 StockDashboard.vue）。-->
    <template v-else-if="graphData">
      <div class="relative">
        <div v-if="loading" class="absolute inset-0 z-10 flex items-start justify-center pt-24 bg-surface-0/60 dark:bg-surface-900/60 rounded-2xl">
          <i class="pi pi-spin pi-spinner text-primary text-3xl"></i>
        </div>
        <div :class="{ 'opacity-50 pointer-events-none transition-opacity duration-150': loading }" class="space-y-6">
          <!-- 沒有下游龍頭：無法點火偵測與 LLM 萃取（§6.1 既有限制）-->
          <div v-if="!currentChain?.downstream_leaders?.length" class="card p-8 text-center rounded-2xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900">
            <i class="pi pi-sitemap text-3xl text-surface-400 mb-2"></i>
            <p class="font-bold text-surface-700 dark:text-surface-200">此鏈尚未核定下游龍頭標的</p>
            <p class="text-xs text-surface-500 mt-1">無法執行點火偵測與 LLM 自動萃取，僅能透過人工新增邊（見 §6.1）</p>
          </div>

          <template v-else>
            <!-- KPI 卡片矩陣（同列等高 + !m-0，CLAUDE.md 鐵則 2）-->
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div class="card !m-0 bg-surface-0 dark:bg-surface-900 p-5 rounded-2xl border border-surface-200 dark:border-surface-700/80 shadow-sm flex flex-col justify-between">
                <span class="text-xs font-bold tracking-wide uppercase text-surface-400">邊總數</span>
                <span class="num text-2xl font-black text-surface-900 dark:text-surface-0 mt-2">{{ graphData.edges.length }}</span>
                <span class="text-xs text-surface-500 mt-1">{{ graphData.nodes.length }} 個節點</span>
              </div>
              <div class="card !m-0 bg-surface-0 dark:bg-surface-900 p-5 rounded-2xl border border-surface-200 dark:border-surface-700/80 shadow-sm flex flex-col justify-between">
                <span class="text-xs font-bold tracking-wide uppercase text-surface-400">已核可比例</span>
                <span class="num text-2xl font-black text-emerald-600 mt-2">{{ verifiedRatioLabel }}</span>
                <span class="text-xs text-surface-500 mt-1">{{ verifiedCount }} / {{ graphData.edges.length }} 筆</span>
              </div>
              <div class="card !m-0 bg-surface-0 dark:bg-surface-900 p-5 rounded-2xl border border-surface-200 dark:border-surface-700/80 shadow-sm flex flex-col justify-between">
                <span class="text-xs font-bold tracking-wide uppercase text-surface-400">已突破（下游）</span>
                <span class="num text-2xl font-black text-primary mt-2">{{ ignitedCount }}</span>
                <span class="text-xs text-surface-500 mt-1">今日已有點火事件</span>
              </div>
              <div class="card !m-0 bg-surface-0 dark:bg-surface-900 p-5 rounded-2xl border border-surface-200 dark:border-surface-700/80 shadow-sm flex flex-col justify-between">
                <span class="text-xs font-bold tracking-wide uppercase text-surface-400">輪動候選</span>
                <span class="num text-2xl font-black text-amber-600 mt-2">{{ radarItems.length }}</span>
                <span class="text-xs text-surface-500 mt-1">通過全部濾網</span>
              </div>
            </div>

            <!-- 力導向圖 + 輪動雷達清單 -->
            <div class="grid grid-cols-1 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)] gap-6">
              <div class="card !m-0 bg-surface-0 dark:bg-surface-900 rounded-2xl border border-surface-200 dark:border-surface-700/80 shadow-sm overflow-hidden">
                <div class="p-4 border-b border-surface-200 dark:border-surface-700 flex items-center justify-between flex-wrap gap-2">
                  <h3 class="font-bold text-surface-800 dark:text-surface-100 flex items-center gap-2">
                    <i class="pi pi-share-alt text-primary"></i>產業鏈關聯圖
                  </h3>
                  <div class="flex items-center gap-3 text-[11px] text-surface-500 flex-wrap">
                    <span class="flex items-center gap-1"><i class="inline-block w-2 h-2 rounded-full" style="background:#8F6413"></i>已突破</span>
                    <span class="flex items-center gap-1"><i class="inline-block w-2 h-2 rounded-full" style="background:#B26A00"></i>低位階候選</span>
                    <span class="flex items-center gap-1"><i class="inline-block w-2 h-2 rounded-full" style="background:#a8a29a"></i>尚未連動</span>
                    <span class="flex items-center gap-1"><i class="inline-block w-4 border-t border-surface-500"></i>已核可</span>
                    <span class="flex items-center gap-1"><i class="inline-block w-4 border-t border-dashed border-amber-600"></i>待核對（LLM）</span>
                  </div>
                </div>
                <!-- 目前只有下游龍頭、沒有任何邊（例如剛核定完鏈骨架、還沒觸發過萃取）：所有
                     節點會落在同一個 x 座標，力導向圖的自動縮放算不出有意義的比例尺會裂版，
                     不如直接給明確的空狀態（見對話紀錄：AI 伺服器鏈截圖就是這個情況裂掉的樣子）-->
                <div v-if="!graphData.edges.length" class="p-10 text-center text-surface-400">
                  <i class="pi pi-sitemap text-2xl mb-2"></i>
                  <p class="text-sm">此鏈目前只有下游龍頭、還沒有任何上下游邊資料</p>
                  <p class="text-xs mt-1">按上方「觸發本鏈萃取」讓 AI 找一批候選關聯，或透過「管理產業鏈」核定骨架後再萃取</p>
                </div>
                <template v-else>
                  <div class="pt-3 flex text-[11px] font-bold text-surface-400 tracking-wide" :style="{ paddingLeft: PAD_X + 'px', paddingRight: PAD_X + 'px' }">
                    <span class="flex-1 text-left">← 上游</span>
                    <span class="flex-1 text-center">中游</span>
                    <span class="flex-1 text-right">下游龍頭 →</span>
                  </div>
                  <p class="px-4 pt-1 text-[11px] text-surface-400">滑鼠移到節點可聚焦其上下游關聯，其餘淡化</p>
                  <!-- ref 用來量測實際可用寬度，據以算出欄距讓座標系維持 1:1 不縮放（見 layoutMetrics）-->
                  <div ref="chartBoxRef">
                    <v-chart ref="chartRef" class="graph-chart" :style="{ height: chartHeight + 'px' }" :option="graphOption" autoresize />
                  </div>
                </template>
              </div>

              <div class="card !m-0 bg-surface-0 dark:bg-surface-900 rounded-2xl border border-surface-200 dark:border-surface-700/80 shadow-sm overflow-hidden">
                <div class="p-4 border-b border-surface-200 dark:border-surface-700">
                  <h3 class="font-bold text-surface-800 dark:text-surface-100 flex items-center gap-2">
                    <i class="pi pi-bullseye text-primary"></i>輪動外溢雷達清單
                  </h3>
                  <p class="text-xs text-surface-500 mt-0.5">{{ ignitedHint }}</p>
                </div>
                <div v-if="!radarItems.length" class="p-10 text-center text-surface-400">
                  <i class="pi pi-inbox text-2xl mb-2"></i>
                  <p class="text-sm">目前無符合條件的候選標的</p>
                </div>
                <div v-else class="divide-y divide-surface-100 dark:divide-surface-800 max-h-[520px] overflow-y-auto">
                  <div v-for="item in radarItems" :key="`${item.downstream_leader}-${item.symbol}`" class="p-4">
                    <div class="flex items-center justify-between gap-2 mb-2">
                      <div>
                        <span class="font-black text-surface-900 dark:text-surface-0">{{ item.symbol }}</span>
                        <span class="text-xs text-surface-400 ml-1">Tier {{ item.relation_tier }}</span>
                      </div>
                      <Tag :value="item.is_verified ? '已核可' : '待核對'" :severity="item.is_verified ? 'success' : 'warn'" />
                    </div>
                    <div class="text-xs text-surface-500 mb-2">{{ item.component_type }} · 供應 {{ item.downstream_leader }}</div>
                    <div class="flex items-center gap-3 text-xs text-surface-600 dark:text-surface-300 flex-wrap">
                      <span>領先 <b class="num">{{ item.peak_lag_days ?? '—' }}</b> 天</span>
                      <span>相關係數 <b class="num">{{ item.correlation_coefficient ?? '—' }}</b></span>
                      <span v-if="item.sample_size" class="text-[10px] px-1.5 py-0.5 rounded" :class="item.sample_size < 250 ? 'bg-amber-100 text-amber-700' : 'bg-surface-100 text-surface-500'">
                        樣本 {{ item.sample_size }}
                      </span>
                    </div>
                    <div v-if="item.win_rate" class="text-xs mt-1.5" :class="item.win_rate.total < 5 ? 'text-surface-400' : 'text-emerald-600 font-semibold'">
                      跟漲勝率 {{ Math.round(item.win_rate.rate * 100) }}%（{{ item.win_rate.total }} 次{{ item.win_rate.total < 5 ? '・樣本不足' : '' }}）
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 節點清單：圖上文字太密看不清楚時的備援，完整列出全部公司名稱 -->
            <div class="card !m-0 bg-surface-0 dark:bg-surface-900 rounded-2xl border border-surface-200 dark:border-surface-700/80 shadow-sm overflow-hidden">
              <div class="p-4 border-b border-surface-200 dark:border-surface-700">
                <h3 class="font-bold text-surface-800 dark:text-surface-100 flex items-center gap-2">
                  <i class="pi pi-list text-primary"></i>節點清單
                </h3>
                <p class="text-xs text-surface-500 mt-0.5">依上游→中游→下游排序，圖上標籤被截到或太密看不清楚時可在這裡查完整名稱</p>
              </div>
              <div class="overflow-x-auto">
                <table class="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr class="bg-surface-50 dark:bg-surface-800 text-surface-400 uppercase tracking-wide">
                      <th class="p-2">分層</th>
                      <th class="p-2">代碼</th>
                      <th class="p-2">名稱</th>
                      <th class="p-2">角色／供應內容</th>
                      <th class="p-2">狀態</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="n in nodeTableRows" :key="n.symbol" class="border-t border-surface-100 dark:border-surface-800">
                      <td class="p-2"><span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-300">{{ TIER_LABEL[n.role] || n.role }}</span></td>
                      <td class="p-2 font-bold num text-surface-700 dark:text-surface-200">{{ n.symbol }}</td>
                      <td class="p-2">{{ n.name }}</td>
                      <td class="p-2 text-surface-500">{{ n.componentType || (n.role === 'downstream' ? '下游龍頭（點火偵測錨點）' : '—') }}</td>
                      <td class="p-2">
                        <span class="inline-flex items-center gap-1.5">
                          <i class="inline-block w-2 h-2 rounded-full shrink-0" :style="{ background: STATE_COLOR[n.state] || STATE_COLOR.dormant }"></i>
                          {{ STATE_LABEL[n.state] || '尚未連動' }}
                        </span>
                      </td>
                    </tr>
                    <tr v-if="!nodeTableRows.length"><td colspan="5" class="p-6 text-center text-surface-400">尚無節點資料</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
          </template>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useToast } from 'primevue/usetoast';
import { useConfirm } from 'primevue/useconfirm';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { GraphChart } from 'echarts/charts';
import { TooltipComponent, LegendComponent } from 'echarts/components';
import VChart from 'vue-echarts';
import { industryChainApi } from '@/service/industryChainApi';
import IndustryChainConfigDialog from '@/components/IndustryChainConfigDialog.vue';

use([CanvasRenderer, GraphChart, TooltipComponent, LegendComponent]);

const toast = useToast();
const confirm = useConfirm();

const configVisible = ref(false);
const chains = ref([]);
const chainId = ref(null);
const graphData = ref(null);
const radarItems = ref([]);
const loading = ref(false);
const triggering = ref(false);
const error = ref(null);
const disabledMessage = ref(null);

const currentChain = computed(() => chains.value.find((c) => c.chain_id === chainId.value) || null);
const verifiedCount = computed(() => (graphData.value ? graphData.value.edges.filter((e) => e.is_verified).length : 0));
const verifiedRatioLabel = computed(() => {
  if (!graphData.value || !graphData.value.edges.length) return '—';
  return `${Math.round((verifiedCount.value / graphData.value.edges.length) * 100)}%`;
});
const ignitedCount = computed(() => (graphData.value ? graphData.value.nodes.filter((n) => n.state === 'ignited').length : 0));
const ignitedHint = computed(() => {
  const leaders = graphData.value?.nodes.filter((n) => n.state === 'ignited').map((n) => n.symbol) || [];
  return leaders.length ? `點火：${leaders.join('、')}` : '本鏈今日無下游龍頭點火事件';
});

const STATE_COLOR = { ignited: '#8F6413', candidate: '#B26A00', dormant: '#a8a29a' };
const STATE_BG = { ignited: '#F8EEDA', candidate: '#FFF3E0', dormant: '#f0efec' };

// 已突破（點火）節點的呼吸光暈——只在真的有點火節點時才跑計時器，平常（多半是 dormant）
// 完全不佔資源。用 setInterval 而非 requestAnimationFrame：呼吸效果本來就慢（~1.8 秒一輪），
// 10Hz 取樣已經滑順，不需要 60fps 白白重算整個 graphOption／重丟 setOption。
const PULSE_CYCLE_SEC = 1.8;
const pulsePhase = ref(0);
let pulseTimer = null;

const hasIgnitedNode = computed(() => (graphData.value?.nodes || []).some((n) => n.state === 'ignited'));

watch(hasIgnitedNode, (has) => {
  if (has && !pulseTimer) {
    pulseTimer = setInterval(() => { pulsePhase.value = performance.now() / 1000; }, 100);
  } else if (!has && pulseTimer) {
    clearInterval(pulseTimer);
    pulseTimer = null;
  }
}, { immediate: true });

onBeforeUnmount(() => {
  if (pulseTimer) clearInterval(pulseTimer);
});

// 分層版面（上游｜中游｜下游），取代原本的純力導向排版——邊一多（例如 CPO 矽光子鏈 63
// 條）force 布局會糊成一坨看不出方向，改成固定欄位＋欄內平均分佈，天生不會互相遮擋
// （見對話紀錄的優化評估）。欄序：tier2（上游）在左，downstream（下游龍頭）在右。
const ROLE_COLUMN = { tier2: 0, tier1: 1, downstream: 2 };
const ROLE_LABEL_POSITION = { tier2: 'left', tier1: 'bottom', downstream: 'right' };
const TIER_LABEL = { tier2: '上游', tier1: '中游', downstream: '下游龍頭' };
const STATE_LABEL = { ignited: '已突破', candidate: '低位階候選', dormant: '尚未連動' };
const PAD_X = 100;   // 左右留白：給欄外標籤（上游靠左、下游靠右）用，太小會被裁掉
const PAD_Y = 28;
const ROW_GAP = 64;

// 量測圖表實際可用寬度。ECharts 的 view 座標系會把節點座標的包圍盒「縮放」到繪圖區，
// 而且 x/y 是各自獨立縮放的——一旦包圍盒與繪圖區長寬比不同，圓就會被壓成橢圓（前一版
// 指定了 left/right/top/bottom 把寬高都寫死，正是壓扁的原因）。量到寬度後即可反推欄距，
// 讓包圍盒與繪圖區完全等比（縮放 1:1），圓才會保持正圓、列距也精準等於 ROW_GAP。
const chartBoxRef = ref(null);
const chartBoxWidth = ref(0);
let resizeObs = null;

// 圖表在 v-if 分支內，掛載時機不固定；watch 樣板 ref 才能在分支切換時重新觀察
watch(chartBoxRef, (el) => {
  resizeObs?.disconnect();
  resizeObs = null;
  if (!el || typeof ResizeObserver === 'undefined') return;
  resizeObs = new ResizeObserver(([entry]) => { chartBoxWidth.value = entry.contentRect.width; });
  resizeObs.observe(el);
});

onBeforeUnmount(() => resizeObs?.disconnect());

// 節點座標：欄內依代號排序、置中對齊到最長欄（短欄不會全擠在頂端）；欄距由實際寬度反推
const layoutMetrics = computed(() => {
  const byCol = [[], [], []];
  (graphData.value?.nodes || []).forEach((n) => byCol[ROLE_COLUMN[n.role] ?? 1].push(n));
  byCol.forEach((col) => col.sort((a, b) => a.symbol.localeCompare(b.symbol)));

  const maxRows = Math.max(1, ...byCol.map((col) => col.length));
  const contentHeight = (maxRows - 1) * ROW_GAP;
  // 尚未量到寬度時（首次算 option 早於 ResizeObserver 首次回呼）先用一個合理預設值
  const viewWidth = Math.max(240, (chartBoxWidth.value || 660) - PAD_X * 2);
  const colGap = viewWidth / 2;

  const posBySymbol = {};
  byCol.forEach((col, colIdx) => {
    const offsetY = ((maxRows - col.length) * ROW_GAP) / 2;
    col.forEach((n, rowIdx) => { posBySymbol[n.symbol] = { x: colIdx * colGap, y: offsetY + rowIdx * ROW_GAP }; });
  });
  return { posBySymbol, contentHeight };
});

// 高度 = 內容高 + 上下留白，讓繪圖區剛好等於包圍盒（不多留無謂空白，也不壓縮）
const chartHeight = computed(() => Math.max(260, layoutMetrics.value.contentHeight + PAD_Y * 2));

const graphOption = computed(() => {
  if (!graphData.value) return {};
  const { posBySymbol } = layoutMetrics.value;
  // 0~1 的呼吸強度（sin 正規化），非點火節點固定 0，省得每個節點都各自算一次 sin
  const pulse = (Math.sin((pulsePhase.value * 2 * Math.PI) / PULSE_CYCLE_SEC) + 1) / 2;
  const nodes = graphData.value.nodes.map((n) => {
    const baseSize = n.role === 'downstream' ? 40 : n.role === 'tier1' ? 30 : 22;
    const ignited = n.state === 'ignited';
    return {
      id: n.symbol,
      name: `${n.symbol} ${n.name}`,
      x: posBySymbol[n.symbol].x,
      y: posBySymbol[n.symbol].y,
      // 已突破節點：大小＋外發光隨 pulse 呼吸（3px／6~20px），視覺上一眼就能跟其餘節點分開；
      // 其餘節點給一圈很淡的陰影做立體感，不然純灰底圓圈在白卡片上會顯得死板扁平
      symbolSize: ignited ? baseSize + pulse * 6 : baseSize,
      itemStyle: {
        color: STATE_BG[n.state] || STATE_BG.dormant,
        borderColor: STATE_COLOR[n.state] || STATE_COLOR.dormant,
        borderWidth: ignited ? 3 : 2,
        shadowColor: ignited ? STATE_COLOR.ignited : 'rgba(15, 23, 42, 0.12)',
        shadowBlur: ignited ? 6 + pulse * 14 : 5,
        shadowOffsetY: ignited ? 0 : 1
      },
      // 分層版面每欄節點是固定座標、垂直平均分佈，不會像力導向那樣互相飄移遮擋，所以三欄
      // 標籤都常駐顯示是安全的；hover 時仍會加粗＋固定鄰接節點，方便在密集鏈裡追一條線
      label: {
        show: true, fontSize: 10, position: ROLE_LABEL_POSITION[n.role] || 'bottom',
        fontWeight: ignited ? 'bold' : 'normal',
        color: ignited ? STATE_COLOR.ignited : undefined,
        formatter: (p) => p.data.name
      },
      emphasis: { label: { show: true, fontWeight: 'bold' } }
    };
  });
  // 靜止狀態刻意調淡（opacity 0.45／0.6）——邊一多（CPO 鏈 63 條）全部滿彩實線會很「吵」，
  // 平常淡一點、hover 時 emphasis 才拉回 opacity:1，對比出來反而更看得出「聚焦」的效果
  const links = graphData.value.edges.map((e) => ({
    source: e.upstream_symbol,
    target: e.downstream_symbol,
    lineStyle: {
      color: e.is_verified ? '#79746c' : '#B26A00',
      type: e.is_verified ? 'solid' : 'dashed',
      width: 1.4,
      opacity: e.is_verified ? 0.45 : 0.6,
      curveness: 0.15,
      cap: 'round'
    },
    tooltip: { formatter: () => `${e.upstream_symbol} → ${e.downstream_symbol}<br/>${e.component_type || ''}` }
  }));
  return {
    tooltip: {},
    series: [
      {
        type: 'graph',
        layout: 'none',
        roam: true,
        draggable: true,
        // 邊界留白給欄外標籤（上游往左、下游往右），數值與 layoutMetrics 反推欄距時一致，
        // 因此包圍盒與繪圖區等比、縮放 1:1。preserveAspect 是保險：萬一量到的寬度暫時過期
        // （例如 resize 當下那一幀），ECharts 會改以等比「contain」縮放，圓仍是正圓不會壓扁
        left: PAD_X,
        right: PAD_X,
        top: PAD_Y,
        bottom: PAD_Y,
        preserveAspect: true,
        data: nodes,
        links,
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: 6,
        // hover 節點時只保留跟它相連的節點/邊，其餘淡化——密集鏈（多對多）平常看起來還是
        // 一坨線，靠這個才聚焦得出「這顆點到底接誰」
        emphasis: { focus: 'adjacency', lineStyle: { width: 3, opacity: 1 } },
        blur: { itemStyle: { opacity: 0.15 }, lineStyle: { opacity: 0.06 }, label: { opacity: 0.15 } }
      }
    ]
  };
});

// 圖上文字太密、或欄外標籤被截到看不清楚時的備援：完整節點清單，依「上游→中游→下游」
// 閱讀順序分組，component_type 取該公司在邊資料裡作為 upstream_symbol 時的第一筆描述
// （下游龍頭本身不供應誰，component_type 留空、改標示為點火錨點）
const nodeTableRows = computed(() => {
  if (!graphData.value) return [];
  return [...graphData.value.nodes]
    .sort((a, b) => (ROLE_COLUMN[a.role] ?? 1) - (ROLE_COLUMN[b.role] ?? 1) || a.symbol.localeCompare(b.symbol))
    .map((n) => ({
      ...n,
      componentType: graphData.value.edges.find((e) => e.upstream_symbol === n.symbol)?.component_type || ''
    }));
});

function resetErrorState() {
  error.value = null;
  disabledMessage.value = null;
}

function handleFetchError(err) {
  const code = err?.response?.data?.error?.code;
  const message = err?.response?.data?.error?.message || err.message;
  if (code === 'IC_DISABLED') {
    disabledMessage.value = message || '產業鏈知識圖譜功能未啟用（INDUSTRY_CHAIN_ENABLED=false）';
  } else if (code === 'IC_STORAGE_UNAVAILABLE') {
    error.value = `資料庫目前無法使用：${message}`;
  } else {
    error.value = message || '讀取失敗，請稍後再試';
  }
}

async function fetchChainList() {
  const res = await industryChainApi.listChains();
  chains.value = res.data.items;
  if (!chainId.value && chains.value.length) {
    chainId.value = chains.value[0].chain_id;
  }
}

async function fetchGraphAndRadar() {
  if (!chainId.value) return;
  loading.value = true;
  resetErrorState();
  try {
    const [graphRes, radarRes] = await Promise.all([
      industryChainApi.getChainGraph(chainId.value),
      industryChainApi.getSpilloverRadar(chainId.value)
    ]);
    graphData.value = graphRes.data;
    radarItems.value = radarRes.data.items;
  } catch (err) {
    handleFetchError(err);
  } finally {
    loading.value = false;
  }
}

async function fetchAll() {
  loading.value = true;
  resetErrorState();
  try {
    await fetchChainList();
    await fetchGraphAndRadar();
  } catch (err) {
    handleFetchError(err);
    loading.value = false;
  }
}

function confirmTrigger() {
  if (!chainId.value) return;
  const chainName = currentChain.value?.name || chainId.value;
  confirm.require({
    header: '確認付費觸發 AI 萃取',
    message: `執行「${chainName}」的 AI 自動萃取將發送請求給大語言模型 (LLM) 進行產業鏈深度分析，此操作會消耗 API Token（將產生付費費用）。是否確定執行？`,
    icon: 'pi pi-exclamation-triangle',
    rejectProps: {
      label: '取消',
      severity: 'secondary',
      outlined: true
    },
    acceptProps: {
      label: '確定執行 (付費/消耗 Token)',
      severity: 'warning'
    },
    accept: () => {
      executeTrigger();
    }
  });
}

async function executeTrigger() {
  if (!chainId.value) return;
  triggering.value = true;
  try {
    const res = await industryChainApi.triggerExtract({ chainId: chainId.value });
    toast.add({ severity: 'success', summary: '已觸發萃取', detail: '已成功啟動 LLM 產業鏈萃取任務', life: 4000 });
    await fetchGraphAndRadar();
  } catch (err) {
    const message = err?.response?.data?.error?.message || err.message;
    toast.add({ severity: 'error', summary: '觸發失敗', detail: message, life: 5000 });
  } finally {
    triggering.value = false;
  }
}

onMounted(fetchAll);
</script>

<style scoped>
.graph-chart {
  width: 100%;
}
</style>
