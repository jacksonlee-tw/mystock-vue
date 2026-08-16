<template>
  <div class="p-4 sm:p-6 max-w-7xl mx-auto space-y-6">
    <!-- 頁面頂部 Header -->
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
      <div>
        <div class="flex flex-wrap items-center gap-3">
          <h1 class="text-2xl sm:text-3xl font-black text-surface-900 dark:text-surface-0 flex items-center gap-3">
            <i class="pi pi-sync text-primary text-2xl"></i>
            台股類股輪動監控
          </h1>
          <!-- 醒目資料日期標籤 -->
          <div class="flex items-center gap-2">
            <span
              class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-primary/10 dark:bg-primary/20 border border-primary/30 text-primary font-bold text-xs sm:text-sm shadow-sm"
              :title="`統計起迄: ${periodStartDate || dataDate} ~ ${dataDate}`"
            >
              <i class="pi pi-calendar text-primary"></i>
              <span>資料日期：</span>
              <span class="num font-black tracking-wide">{{ dataDate || '載入中...' }}</span>
            </span>
            <span v-if="selectedPeriod !== '1d' && periodStartDate" class="text-xs text-surface-500 font-semibold hidden lg:inline">
              (週期起算: {{ periodStartDate }})
            </span>
          </div>
        </div>
        <p class="text-xs sm:text-sm text-surface-500 mt-1">
          即時掌握資金板塊流向、類股強弱位階與輪動趨勢（規劃書 FR-IDX-30/31）
        </p>
      </div>

      <div class="flex items-center gap-2 self-start md:self-auto shrink-0">
        <button
          @click="fetchData"
          :disabled="loading"
          class="px-3 py-2 text-xs font-bold bg-surface-100 hover:bg-surface-200 dark:bg-surface-800 dark:hover:bg-surface-700 text-surface-700 dark:text-surface-300 rounded-xl flex items-center gap-1.5 transition-colors border border-surface-200 dark:border-surface-700 shadow-sm"
          title="重新整理數據"
        >
          <i :class="['pi pi-refresh', { 'pi-spin': loading }]"></i>
          <span>重新整理</span>
        </button>

        <button
          @click="handleSync"
          :disabled="syncing"
          class="px-3 py-2 text-xs font-bold bg-primary text-primary-contrast hover:bg-primary-emphasis rounded-xl flex items-center gap-1.5 transition-all shadow-sm active:scale-95"
          title="觸發背景同步最新類股快照"
        >
          <i :class="['pi pi-cloud-download', { 'pi-spin': syncing }]"></i>
          <span>{{ syncing ? '同步中...' : '同步類股' }}</span>
        </button>

        <button
          @click="router.push('/')"
          class="px-3 py-2 text-xs font-bold bg-surface-100 hover:bg-surface-200 dark:bg-surface-800 dark:hover:bg-surface-700 text-surface-700 dark:text-surface-300 rounded-xl flex items-center gap-1.5 transition-colors border border-surface-200 dark:border-surface-700 shadow-sm"
        >
          <i class="pi pi-home"></i> 回熱力圖
        </button>
      </div>
    </div>

    <!-- 頂部 4 大 KPI 總覽卡片 -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <!-- 最強領漲 -->
      <div
        v-if="topGainer"
        @click="goToSector(topGainer)"
        class="card !m-0 p-4 rounded-2xl bg-surface-0 dark:bg-surface-900 border border-surface-200 dark:border-surface-700 shadow-sm hover:shadow-md hover:border-primary/50 cursor-pointer transition-all flex flex-col justify-between"
      >
        <div class="flex items-center justify-between">
          <span class="text-xs font-extrabold uppercase tracking-wider text-surface-500 flex items-center gap-1.5">
            <i class="pi pi-bolt text-red-500"></i> 最強領漲板塊
          </span>
          <span class="text-[10px] font-bold px-2 py-0.5 rounded-md bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-400">
            {{ topGainer.category_name }}
          </span>
        </div>
        <div class="mt-3 flex items-baseline justify-between">
          <div>
            <div class="text-lg font-black text-surface-900 dark:text-surface-0">{{ topGainer.stock_name }}</div>
            <div class="text-xs text-surface-400 font-medium">{{ topGainer.industry_code }}</div>
          </div>
          <div class="text-right">
            <div class="num text-xl font-black text-up">
              {{ topGainer.change_percent > 0 ? '+' : '' }}{{ topGainer.change_percent.toFixed(2) }}%
            </div>
            <div class="num text-xs text-surface-500 font-semibold">{{ formatIndexValue(topGainer.latest_close) }}</div>
          </div>
        </div>
      </div>

      <!-- 最弱回檔 -->
      <div
        v-if="topLoser"
        @click="goToSector(topLoser)"
        class="card !m-0 p-4 rounded-2xl bg-surface-0 dark:bg-surface-900 border border-surface-200 dark:border-surface-700 shadow-sm hover:shadow-md hover:border-primary/50 cursor-pointer transition-all flex flex-col justify-between"
      >
        <div class="flex items-center justify-between">
          <span class="text-xs font-extrabold uppercase tracking-wider text-surface-500 flex items-center gap-1.5">
            <i class="pi pi-arrow-down-right text-emerald-500"></i> 最弱回檔板塊
          </span>
          <span class="text-[10px] font-bold px-2 py-0.5 rounded-md bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-400">
            {{ topLoser.category_name }}
          </span>
        </div>
        <div class="mt-3 flex items-baseline justify-between">
          <div>
            <div class="text-lg font-black text-surface-900 dark:text-surface-0">{{ topLoser.stock_name }}</div>
            <div class="text-xs text-surface-400 font-medium">{{ topLoser.industry_code }}</div>
          </div>
          <div class="text-right">
            <div class="num text-xl font-black text-down">
              {{ topLoser.change_percent > 0 ? '+' : '' }}{{ topLoser.change_percent.toFixed(2) }}%
            </div>
            <div class="num text-xs text-surface-500 font-semibold">{{ formatIndexValue(topLoser.latest_close) }}</div>
          </div>
        </div>
      </div>

      <!-- 類股多空分佈 (Breadth) -->
      <div class="card !m-0 p-4 rounded-2xl bg-surface-0 dark:bg-surface-900 border border-surface-200 dark:border-surface-700 shadow-sm flex flex-col justify-between">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs font-extrabold uppercase tracking-wider text-surface-500 flex items-center gap-1.5">
            <i class="pi pi-chart-pie text-primary"></i> 類股多空分佈
          </span>
          <span class="text-xs font-bold text-surface-600 dark:text-surface-400">共 {{ breadthStats.total || withData.length }} 類股</span>
        </div>
        <div class="flex items-baseline justify-between my-1">
          <span class="num text-sm font-black text-up flex items-center gap-1">
            <i class="pi pi-arrow-up text-xs"></i> {{ breadthStats.up_count || 0 }} 漲
          </span>
          <span class="num text-xs font-bold text-surface-500">
            {{ breadthStats.flat_count || 0 }} 平
          </span>
          <span class="num text-sm font-black text-down flex items-center gap-1">
            <i class="pi pi-arrow-down text-xs"></i> {{ breadthStats.down_count || 0 }} 跌
          </span>
        </div>
        <!-- 比例進度條 -->
        <div class="w-full h-2.5 rounded-full overflow-hidden flex bg-surface-200 dark:bg-surface-700 mt-2">
          <div
            class="h-full bg-up transition-all duration-500"
            :style="{ width: `${breadthPercent.up}%` }"
            :title="`上漲 ${breadthPercent.up}%`"
          ></div>
          <div
            class="h-full bg-surface-400 dark:bg-surface-500 transition-all duration-500"
            :style="{ width: `${breadthPercent.flat}%` }"
            :title="`平盤 ${breadthPercent.flat}%`"
          ></div>
          <div
            class="h-full bg-down transition-all duration-500"
            :style="{ width: `${breadthPercent.down}%` }"
            :title="`下跌 ${breadthPercent.down}%`"
          ></div>
        </div>
      </div>

      <!-- 加權指數基準對照 (TWII Benchmark) -->
      <div
        @click="router.push('/index/tw/TWII')"
        class="card !m-0 p-4 rounded-2xl bg-surface-0 dark:bg-surface-900 border border-surface-200 dark:border-surface-700 shadow-sm hover:shadow-md hover:border-primary/50 cursor-pointer transition-all flex flex-col justify-between"
      >
        <div class="flex items-center justify-between">
          <span class="text-xs font-extrabold uppercase tracking-wider text-surface-500 flex items-center gap-1.5">
            <i class="pi pi-building text-primary"></i> 加權指數 (TWII) 基準
          </span>
          <span class="text-[10px] font-bold px-2 py-0.5 rounded-md bg-primary/10 text-primary">
            大盤基準
          </span>
        </div>
        <div class="mt-3 flex items-baseline justify-between">
          <div>
            <div class="num text-lg font-black text-surface-900 dark:text-surface-0">
              {{ twiiStats.latest_close ? formatIndexValue(twiiStats.latest_close) : '—' }}
            </div>
            <div class="text-xs text-surface-400 font-medium">同週期漲跌</div>
          </div>
          <div class="text-right">
            <div
              class="num text-xl font-black"
              :class="twiiStats.change_percent >= 0 ? 'text-up' : 'text-down'"
            >
              {{ twiiStats.change_percent > 0 ? '+' : '' }}{{ twiiStats.change_percent ? twiiStats.change_percent.toFixed(2) : '0.00' }}%
            </div>
            <div class="text-xs font-bold text-surface-500">
              {{ outperformingCount }} 類股超越大盤
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 控制工具列：週期選擇、視圖模式切換、大板塊篩選、搜尋 -->
    <div class="card !m-0 p-4 rounded-2xl bg-surface-0 dark:bg-surface-900 border border-surface-200 dark:border-surface-700 shadow-sm space-y-4">
      <div class="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        <!-- 輪動週期切換 (Time Horizon) -->
        <div class="flex items-center gap-1.5 overflow-x-auto pb-1 lg:pb-0">
          <span class="text-xs font-bold text-surface-500 shrink-0 mr-1 flex items-center gap-1">
            <i class="pi pi-clock text-xs"></i> 週期:
          </span>
          <div class="flex items-center gap-1 bg-surface-100 dark:bg-surface-800 p-1 rounded-xl border border-surface-200 dark:border-surface-700">
            <button
              v-for="p in periods"
              :key="p.value"
              @click="setPeriod(p.value)"
              :class="[
                'px-3 py-1.5 text-xs font-black rounded-lg transition-all',
                selectedPeriod === p.value
                  ? 'bg-primary text-primary-contrast shadow-sm scale-105'
                  : 'text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-0'
              ]"
            >
              {{ p.label }}
            </button>
          </div>
        </div>

        <!-- 視覺視圖模式切換 (View Modes) -->
        <div class="flex items-center gap-1 bg-surface-100 dark:bg-surface-800 p-1 rounded-xl border border-surface-200 dark:border-surface-700 self-start lg:self-auto shrink-0">
          <button
            v-for="mode in viewModes"
            :key="mode.value"
            @click="activeViewMode = mode.value"
            :class="[
              'px-3 py-1.5 text-xs font-bold rounded-lg transition-all flex items-center gap-1.5',
              activeViewMode === mode.value
                ? 'bg-surface-0 dark:bg-surface-900 text-primary shadow-sm font-black'
                : 'text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-0'
            ]"
          >
            <i :class="mode.icon"></i>
            <span>{{ mode.label }}</span>
          </button>
        </div>
      </div>

      <!-- 分類標籤、搜尋與排序 -->
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2 border-t border-surface-100 dark:border-surface-800">
        <!-- 大板塊標籤 (Super Sector Tabs) -->
        <div class="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
          <button
            v-for="cat in categoryOptions"
            :key="cat.value"
            @click="selectedCategory = cat.value"
            :class="[
              'px-2.5 py-1 text-xs font-bold rounded-lg transition-colors shrink-0',
              selectedCategory === cat.value
                ? 'bg-primary/15 text-primary border border-primary/30 font-black'
                : 'bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-400 hover:bg-surface-200 dark:hover:bg-surface-700'
            ]"
          >
            {{ cat.label }}
            <span v-if="cat.count !== undefined" class="text-[10px] opacity-75 ml-1">({{ cat.count }})</span>
          </button>
        </div>

        <!-- 搜尋與排序 -->
        <div class="flex items-center gap-2 shrink-0">
          <div class="relative w-40 sm:w-48">
            <i class="pi pi-search absolute left-2.5 top-1/2 -translate-y-1/2 text-surface-400 text-xs"></i>
            <input
              v-model="searchQuery"
              type="text"
              placeholder="搜尋類股或代碼..."
              class="w-full pl-8 pr-7 py-1.5 text-xs rounded-xl bg-surface-100 dark:bg-surface-800 border border-surface-200 dark:border-surface-700 text-surface-900 dark:text-surface-0 placeholder:text-surface-400 focus:outline-none focus:ring-1 focus:ring-primary transition-all"
            />
            <button
              v-if="searchQuery"
              @click="searchQuery = ''"
              class="absolute right-2 top-1/2 -translate-y-1/2 text-surface-400 hover:text-surface-600 text-xs"
            >
              <i class="pi pi-times-circle"></i>
            </button>
          </div>

          <select
            v-model="sortBy"
            class="px-2.5 py-1.5 text-xs font-bold rounded-xl bg-surface-100 dark:bg-surface-800 border border-surface-200 dark:border-surface-700 text-surface-700 dark:text-surface-300 focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="change_desc">漲幅由高到低</option>
            <option value="change_asc">漲幅由低到高</option>
            <option value="alpha_desc">超越大盤 (Alpha)</option>
            <option value="code_asc">依產業代碼</option>
          </select>
        </div>
      </div>
    </div>

    <!-- 載入中狀態 -->
    <div v-if="loading && !filteredSectors.length" class="flex flex-col items-center justify-center p-16 card bg-surface-0 dark:bg-surface-900 rounded-2xl border border-surface-200 dark:border-surface-700 shadow-sm">
      <i class="pi pi-spin pi-spinner text-primary text-4xl mb-3"></i>
      <p class="text-sm font-bold text-surface-700 dark:text-surface-300">載入類股輪動資料中...</p>
      <p class="text-xs text-surface-400 mt-1">計算 {{ selectedPeriodLabel }} 資金流向與板塊強弱度...</p>
    </div>

    <!-- 錯誤狀態 -->
    <div v-else-if="error" class="card p-6 border border-red-300 bg-red-50 dark:bg-red-900/20 rounded-2xl text-red-700 dark:text-red-300">
      <div class="flex items-center gap-3">
        <i class="pi pi-exclamation-circle text-2xl"></i>
        <div>
          <h4 class="font-bold">資料讀取失敗</h4>
          <p class="text-sm mt-0.5">{{ error }}</p>
          <button @click="fetchData" class="mt-3 px-3 py-1.5 text-xs font-bold bg-red-600 text-white rounded-lg hover:bg-red-700">
            重試
          </button>
        </div>
      </div>
    </div>

    <!-- 無符合資料 -->
    <div v-else-if="!filteredSectors.length" class="card p-12 text-center text-surface-500 rounded-2xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900">
      <i class="pi pi-inbox text-4xl mb-3 block text-surface-400"></i>
      <p class="font-bold text-surface-700 dark:text-surface-300">無符合條件之類股資料</p>
      <p class="text-xs text-surface-400 mt-1">請嘗試變更搜尋關鍵字或板塊分類。</p>
    </div>

    <!-- 主要內容區：依 activeViewMode 切換 -->
    <template v-else>
      <!-- 視圖 1: 📊 輪動排行圖 (Ranking Bar Chart) -->
      <div v-show="activeViewMode === 'ranking'" class="card !m-0 p-5 rounded-2xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm space-y-3">
        <div class="flex items-center justify-between text-xs text-surface-500 font-semibold px-1">
          <span class="flex items-center gap-1.5">
            <i class="pi pi-chart-bar text-primary"></i>
            {{ selectedPeriodLabel }} 各類股漲跌幅排行（紅漲綠跌，點擊長條可查看指數詳情）
          </span>
          <span v-if="twiiStats.change_percent !== undefined" class="hidden sm:inline text-primary font-bold">
            --- 加權基準線: {{ twiiStats.change_percent > 0 ? '+' : '' }}{{ twiiStats.change_percent.toFixed(2) }}%
          </span>
        </div>
        <div class="rank-chart-container">
          <v-chart
            ref="rankChartRef"
            class="rank-chart-stage"
            :option="rankOption"
            :update-options="{ notMerge: true }"
            autoresize
            @click="onBarClick"
          />
        </div>
      </div>

      <!-- 視圖 2: 🗺️ 板塊熱力卡片網格 (Heatmap Grid) -->
      <div v-show="activeViewMode === 'grid'" class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        <div
          v-for="sector in filteredSectors"
          :key="sector.stock_id"
          @click="goToSector(sector)"
          class="card !m-0 p-4 rounded-2xl border bg-surface-0 dark:bg-surface-900 shadow-sm cursor-pointer hover:-translate-y-1 hover:shadow-xl transition-all duration-200 relative group overflow-hidden"
          :class="getCardBorderClass(sector)"
        >
          <!-- 頂部：排名徽章、名稱與類別 -->
          <div class="flex justify-between items-start mb-2">
            <div>
              <div class="flex items-center gap-1.5">
                <span
                  class="text-[11px] font-black px-1.5 py-0.5 rounded-md"
                  :class="getRankBadgeClass(sector.rank)"
                >
                  #{{ sector.rank }}
                </span>
                <span class="text-base font-bold text-surface-900 dark:text-surface-0 group-hover:text-primary transition-colors">
                  {{ sector.stock_name }}
                </span>
              </div>
              <div class="flex items-center gap-2 mt-1">
                <span class="text-xs text-surface-400 font-mono">{{ sector.industry_code }}</span>
                <span class="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-surface-100 dark:bg-surface-800 text-surface-500">
                  {{ sector.category_name }}
                </span>
              </div>
            </div>

            <!-- 報價與漲跌 -->
            <div class="text-right">
              <div class="num text-lg font-black" :class="getPriceColorClass(sector)">
                {{ formatIndexValue(sector.latest_close) }}
              </div>
              <div class="num text-xs font-black flex items-center justify-end gap-0.5" :class="getPriceColorClass(sector)">
                <span>{{ sector.change_percent > 0 ? '+' : '' }}{{ sector.change_percent.toFixed(2) }}%</span>
              </div>
            </div>
          </div>

          <!-- 超額報酬 (Alpha) 標籤 -->
          <div class="flex items-center justify-between text-[11px] mb-2 px-0.5">
            <span class="text-surface-400 font-medium">vs 大盤</span>
            <span
              class="num font-bold"
              :class="sector.alpha >= 0 ? 'text-up' : 'text-down'"
            >
              {{ sector.alpha > 0 ? '+' : '' }}{{ sector.alpha ? sector.alpha.toFixed(2) : '0.00' }}%
            </span>
          </div>

          <!-- Sparkline 折線走勢 -->
          <div class="h-14 w-full pt-1">
            <v-chart :option="getSparklineOption(sector)" :update-options="{ notMerge: true }" autoresize />
          </div>
        </div>
      </div>

      <!-- 視圖 3: 🔄 強弱輪動矩陣 (Sector Momentum Matrix) -->
      <div v-show="activeViewMode === 'matrix'" class="space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <!-- 象限 1: 🚀 強勢領漲板塊 (Alpha > 0 & 漲幅 > 0) -->
          <div class="card !m-0 p-5 rounded-2xl bg-surface-0 dark:bg-surface-900 border-2 border-red-500/30 dark:border-red-500/20 shadow-sm space-y-3">
            <div class="flex items-center justify-between border-b border-surface-100 dark:border-surface-800 pb-2">
              <div class="flex items-center gap-2">
                <span class="w-7 h-7 rounded-lg bg-red-500/10 text-red-600 dark:text-red-400 flex items-center justify-center font-bold">
                  🚀
                </span>
                <div>
                  <h3 class="text-sm font-black text-surface-900 dark:text-surface-0">強勢領漲板塊</h3>
                  <p class="text-[11px] text-surface-400 font-medium">打敗大盤且正報酬（資金聚集焦點）</p>
                </div>
              </div>
              <span class="text-xs font-black px-2 py-0.5 rounded-full bg-red-500/10 text-red-600">
                {{ matrixGroups.leading.length }} 檔
              </span>
            </div>
            <div class="flex flex-wrap gap-2 pt-1">
              <button
                v-for="s in matrixGroups.leading"
                :key="s.stock_id"
                @click="goToSector(s)"
                class="px-3 py-2 rounded-xl bg-surface-100 hover:bg-surface-200 dark:bg-surface-800 dark:hover:bg-surface-700 border border-surface-200 dark:border-surface-700 text-left transition-all flex items-center gap-2 group"
              >
                <span class="text-xs font-bold text-surface-800 dark:text-surface-200 group-hover:text-primary">{{ s.stock_name }}</span>
                <span class="num text-xs font-black text-up">+{{ s.change_percent.toFixed(2) }}%</span>
              </button>
              <div v-if="!matrixGroups.leading.length" class="text-xs text-surface-400 py-3 italic">暫無符合此象限之類股</div>
            </div>
          </div>

          <!-- 象限 2: 🛡️ 抗跌轉強板塊 (Alpha > 0 & 漲跌 <= 0) -->
          <div class="card !m-0 p-5 rounded-2xl bg-surface-0 dark:bg-surface-900 border-2 border-amber-500/30 dark:border-amber-500/20 shadow-sm space-y-3">
            <div class="flex items-center justify-between border-b border-surface-100 dark:border-surface-800 pb-2">
              <div class="flex items-center gap-2">
                <span class="w-7 h-7 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center font-bold">
                  🛡️
                </span>
                <div>
                  <h3 class="text-sm font-black text-surface-900 dark:text-surface-0">抗跌防禦板塊</h3>
                  <p class="text-[11px] text-surface-400 font-medium">跌幅小於大盤（抗跌轉強潛力）</p>
                </div>
              </div>
              <span class="text-xs font-black px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-600">
                {{ matrixGroups.defensive.length }} 檔
              </span>
            </div>
            <div class="flex flex-wrap gap-2 pt-1">
              <button
                v-for="s in matrixGroups.defensive"
                :key="s.stock_id"
                @click="goToSector(s)"
                class="px-3 py-2 rounded-xl bg-surface-100 hover:bg-surface-200 dark:bg-surface-800 dark:hover:bg-surface-700 border border-surface-200 dark:border-surface-700 text-left transition-all flex items-center gap-2 group"
              >
                <span class="text-xs font-bold text-surface-800 dark:text-surface-200 group-hover:text-primary">{{ s.stock_name }}</span>
                <span class="num text-xs font-black text-surface-600 dark:text-surface-400">{{ s.change_percent.toFixed(2) }}%</span>
                <span class="text-[10px] font-bold text-primary">α +{{ s.alpha.toFixed(2) }}%</span>
              </button>
              <div v-if="!matrixGroups.defensive.length" class="text-xs text-surface-400 py-3 italic">暫無符合此象限之類股</div>
            </div>
          </div>

          <!-- 象限 3: ⚠️ 漲勢落後板塊 (Alpha <= 0 & 漲幅 > 0) -->
          <div class="card !m-0 p-5 rounded-2xl bg-surface-0 dark:bg-surface-900 border-2 border-blue-500/30 dark:border-blue-500/20 shadow-sm space-y-3">
            <div class="flex items-center justify-between border-b border-surface-100 dark:border-surface-800 pb-2">
              <div class="flex items-center gap-2">
                <span class="w-7 h-7 rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center justify-center font-bold">
                  ⚠️
                </span>
                <div>
                  <h3 class="text-sm font-black text-surface-900 dark:text-surface-0">漲勢落後板塊</h3>
                  <p class="text-[11px] text-surface-400 font-medium">正報酬但漲幅遜於大盤（落後補漲觀察）</p>
                </div>
              </div>
              <span class="text-xs font-black px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-600">
                {{ matrixGroups.lagging.length }} 檔
              </span>
            </div>
            <div class="flex flex-wrap gap-2 pt-1">
              <button
                v-for="s in matrixGroups.lagging"
                :key="s.stock_id"
                @click="goToSector(s)"
                class="px-3 py-2 rounded-xl bg-surface-100 hover:bg-surface-200 dark:bg-surface-800 dark:hover:bg-surface-700 border border-surface-200 dark:border-surface-700 text-left transition-all flex items-center gap-2 group"
              >
                <span class="text-xs font-bold text-surface-800 dark:text-surface-200 group-hover:text-primary">{{ s.stock_name }}</span>
                <span class="num text-xs font-black text-up">+{{ s.change_percent.toFixed(2) }}%</span>
              </button>
              <div v-if="!matrixGroups.lagging.length" class="text-xs text-surface-400 py-3 italic">暫無符合此象限之類股</div>
            </div>
          </div>

          <!-- 象限 4: ❄️ 拉回修正板塊 (Alpha <= 0 & 跌幅 <= 0) -->
          <div class="card !m-0 p-5 rounded-2xl bg-surface-0 dark:bg-surface-900 border-2 border-emerald-500/30 dark:border-emerald-500/20 shadow-sm space-y-3">
            <div class="flex items-center justify-between border-b border-surface-100 dark:border-surface-800 pb-2">
              <div class="flex items-center gap-2">
                <span class="w-7 h-7 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center font-bold">
                  ❄️
                </span>
                <div>
                  <h3 class="text-sm font-black text-surface-900 dark:text-surface-0">弱勢修正板塊</h3>
                  <p class="text-[11px] text-surface-400 font-medium">跌幅重於大盤（資金流出整理區）</p>
                </div>
              </div>
              <span class="text-xs font-black px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600">
                {{ matrixGroups.correcting.length }} 檔
              </span>
            </div>
            <div class="flex flex-wrap gap-2 pt-1">
              <button
                v-for="s in matrixGroups.correcting"
                :key="s.stock_id"
                @click="goToSector(s)"
                class="px-3 py-2 rounded-xl bg-surface-100 hover:bg-surface-200 dark:bg-surface-800 dark:hover:bg-surface-700 border border-surface-200 dark:border-surface-700 text-left transition-all flex items-center gap-2 group"
              >
                <span class="text-xs font-bold text-surface-800 dark:text-surface-200 group-hover:text-primary">{{ s.stock_name }}</span>
                <span class="num text-xs font-black text-down">{{ s.change_percent.toFixed(2) }}%</span>
              </button>
              <div v-if="!matrixGroups.correcting.length" class="text-xs text-surface-400 py-3 italic">暫無符合此象限之類股</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 視圖 4: 📈 走勢比較 (Top 5 Rebased Comparison) -->
      <div v-show="activeViewMode === 'compare'" class="card !m-0 p-5 rounded-2xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-sm space-y-3">
        <div class="flex items-center justify-between text-xs text-surface-500 font-semibold px-1">
          <span class="flex items-center gap-1.5">
            <i class="pi pi-chart-line text-primary"></i>
            領先類股 Top 5 與加權指數 Rebase=100 累積報酬走勢比較
          </span>
          <span class="text-xs text-surface-400">週期: {{ selectedPeriodLabel }}</span>
        </div>
        <div class="h-96 w-full">
          <v-chart
            class="w-full h-full"
            :option="rebaseCompareOption"
            :update-options="{ notMerge: true }"
            autoresize
          />
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useToast } from 'primevue/usetoast';
import { indexApi } from '@/service/indexApi';
import { useMarket } from '@/composables/useMarket';
import { getUpDownColor } from '@/utils/marketColors';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart, LineChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components';
import VChart from 'vue-echarts';

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent]);

const router = useRouter();
const toast = useToast();
const { currentMarket } = useMarket();

// 狀態
const sectors = ref([]);
const dataDate = ref('');
const periodStartDate = ref('');
const twiiStats = ref({ latest_close: 0, change: 0, change_percent: 0, date: '' });
const breadthStats = ref({ up_count: 0, down_count: 0, flat_count: 0, total: 0 });
const superSectorsMap = ref({});

const loading = ref(true);
const syncing = ref(false);
const error = ref(null);

const selectedPeriod = ref('1d');
const activeViewMode = ref('ranking');
const selectedCategory = ref('all');
const searchQuery = ref('');
const sortBy = ref('change_desc');

// 週期設定
const periods = [
  { label: '當日 (1D)', value: '1d' },
  { label: '近5日 (5D)', value: '5d' },
  { label: '近1月 (1M)', value: '1m' },
  { label: '近3月 (3M)', value: '3m' },
  { label: '近半年 (6M)', value: '6m' }
];

const selectedPeriodLabel = computed(() => {
  const p = periods.find((item) => item.value === selectedPeriod.value);
  return p ? p.label : '當日';
});

// 視圖模式
const viewModes = [
  { label: '排行長條圖', value: 'ranking', icon: 'pi pi-chart-bar' },
  { label: '板塊熱力卡', value: 'grid', icon: 'pi pi-th-large' },
  { label: '強弱矩陣', value: 'matrix', icon: 'pi pi-compass' },
  { label: '走勢比較', value: 'compare', icon: 'pi pi-chart-line' }
];

// 有資料之類股清單
const withData = computed(() => sectors.value.filter((s) => s.has_data));

// 板塊分類選項清單（含家數）
const categoryOptions = computed(() => {
  const all = withData.value;
  const groups = [
    { label: '全部板塊', value: 'all', count: all.length },
    { label: '⚡ 電子科技', value: 'electronic', count: all.filter((s) => s.category === 'electronic').length },
    { label: '🏭 傳統製造', value: 'traditional', count: all.filter((s) => s.category === 'traditional').length },
    { label: '🏦 金融保險', value: 'finance', count: all.filter((s) => s.category === 'finance').length },
    { label: '🚢 民生消費', value: 'consumption', count: all.filter((s) => s.category === 'consumption').length },
    { label: '🌿 生醫綠能', value: 'biotech_green', count: all.filter((s) => s.category === 'biotech_green').length }
  ];
  return groups;
});

// 篩選與排序後之類股
const filteredSectors = computed(() => {
  let list = [...withData.value];

  // 1. 板塊分類過濾
  if (selectedCategory.value !== 'all') {
    list = list.filter((s) => s.category === selectedCategory.value);
  }

  // 2. 搜尋過濾
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase();
    list = list.filter(
      (s) =>
        s.stock_name?.toLowerCase().includes(q) ||
        s.industry_code?.toLowerCase().includes(q) ||
        s.stock_id?.toLowerCase().includes(q) ||
        s.category_name?.toLowerCase().includes(q)
    );
  }

  // 3. 排序
  if (sortBy.value === 'change_desc') {
    list.sort((a, b) => (b.change_percent || 0) - (a.change_percent || 0));
  } else if (sortBy.value === 'change_asc') {
    list.sort((a, b) => (a.change_percent || 0) - (b.change_percent || 0));
  } else if (sortBy.value === 'alpha_desc') {
    list.sort((a, b) => (b.alpha || 0) - (a.alpha || 0));
  } else if (sortBy.value === 'code_asc') {
    list.sort((a, b) => String(a.industry_code).localeCompare(String(b.industry_code)));
  }

  return list;
});

// 最強 / 最弱類股
const topGainer = computed(() => {
  const sorted = [...withData.value].sort((a, b) => (b.change_percent || 0) - (a.change_percent || 0));
  return sorted.length ? sorted[0] : null;
});

const topLoser = computed(() => {
  const sorted = [...withData.value].sort((a, b) => (a.change_percent || 0) - (b.change_percent || 0));
  return sorted.length ? sorted[0] : null;
});

// 多空比例
const breadthPercent = computed(() => {
  const total = breadthStats.value.total || withData.value.length || 1;
  const up = Math.round(((breadthStats.value.up_count || 0) / total) * 100);
  const down = Math.round(((breadthStats.value.down_count || 0) / total) * 100);
  const flat = Math.max(0, 100 - up - down);
  return { up, down, flat };
});

// 打敗大盤家數
const outperformingCount = computed(() => {
  return withData.value.filter((s) => (s.alpha || 0) > 0).length;
});

// 四象限分組 (Momentum Matrix)
const matrixGroups = computed(() => {
  const list = withData.value;
  return {
    leading: list.filter((s) => s.change_percent > 0 && s.alpha > 0),
    defensive: list.filter((s) => s.change_percent <= 0 && s.alpha > 0),
    lagging: list.filter((s) => s.change_percent > 0 && s.alpha <= 0),
    correcting: list.filter((s) => s.change_percent <= 0 && s.alpha <= 0)
  };
});

// 載入資料
async function fetchData() {
  loading.value = true;
  error.value = null;
  try {
    const res = await indexApi.getSectors('tw', selectedPeriod.value);
    if (res.success && res.data) {
      if (Array.isArray(res.data)) {
        sectors.value = res.data;
      } else if (res.data.items) {
        sectors.value = res.data.items || [];
        dataDate.value = res.data.data_date || '';
        periodStartDate.value = res.data.period_start_date || '';
        twiiStats.value = res.data.twii || { latest_close: 0, change: 0, change_percent: 0, date: '' };
        breadthStats.value = res.data.breadth || { up_count: 0, down_count: 0, flat_count: 0, total: 0 };
        superSectorsMap.value = res.data.super_sectors || {};
      }
    }
  } catch (err) {
    error.value = '無法載入類股輪動資料，請確認後端服務狀態。';
  } finally {
    loading.value = false;
  }
}

function setPeriod(p) {
  selectedPeriod.value = p;
  fetchData();
}

// 手動觸發背景同步
async function handleSync() {
  if (syncing.value) return;
  syncing.value = true;
  try {
    await indexApi.triggerSync(null, 'tw', null, 'incremental');
    toast?.add({
      severity: 'info',
      summary: '已啟動資料同步',
      detail: '正在背景同步類股最新快照與歷史，數秒後自動刷新...',
      life: 4000
    });
    setTimeout(async () => {
      await fetchData();
      syncing.value = false;
      toast?.add({
        severity: 'success',
        summary: '同步完成',
        detail: `類股資料已更新至 ${dataDate.value}`,
        life: 3000
      });
    }, 3500);
  } catch (err) {
    syncing.value = false;
    toast?.add({
      severity: 'error',
      summary: '同步失敗',
      detail: '無法觸發指數同步任務',
      life: 3000
    });
  }
}

onMounted(() => {
  fetchData();
});

// 監聽市場配色切換
watch(currentMarket, () => {
  // 觸發 ECharts 更新
});

// 格式化工具
function formatIndexValue(value) {
  return Number(value).toLocaleString('zh-TW', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function getPriceColorClass(s) {
  if (s.change_percent > 0) return 'text-up';
  if (s.change_percent < 0) return 'text-down';
  return 'text-surface-500';
}

function getCardBorderClass(s) {
  if (s.change_percent > 0) return 'border-surface-200 dark:border-surface-700 hover:border-up';
  if (s.change_percent < 0) return 'border-surface-200 dark:border-surface-700 hover:border-down';
  return 'border-surface-200 dark:border-surface-700 hover:border-primary/50';
}

function getRankBadgeClass(rank) {
  if (rank === 1) return 'bg-amber-500 text-white shadow-sm';
  if (rank === 2) return 'bg-slate-400 text-white shadow-sm';
  if (rank === 3) return 'bg-amber-700 text-white shadow-sm';
  return 'bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-400';
}

function goToSector(sector) {
  if (sector?.stock_id) {
    router.push(`/index/tw/${sector.stock_id}`);
  }
}

// Sparkline 圖表選項
function getSparklineOption(sector) {
  const isUp = (sector.change_percent || 0) >= 0;
  const { up, down } = getUpDownColor(currentMarket.value);
  const color = isUp ? up : down;
  const data = sector.sparkline && sector.sparkline.length ? sector.sparkline : [sector.latest_close || 0];

  return {
    grid: { left: 0, right: 0, top: 4, bottom: 4 },
    xAxis: { type: 'category', show: false, boundaryGap: false },
    yAxis: { type: 'value', show: false, min: 'dataMin', max: 'dataMax' },
    series: [
      {
        type: 'line',
        data,
        showSymbol: false,
        smooth: true,
        lineStyle: { width: 2, color },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: color + '40' },
              { offset: 1, color: color + '05' }
            ]
          }
        }
      }
    ]
  };
}

// 排行長條圖選項 (Ranking Bar Option)
const rankOption = computed(() => {
  const list = [...filteredSectors.value].sort((a, b) => (a.change_percent || 0) - (b.change_percent || 0));
  const { up, down } = getUpDownColor(currentMarket.value);
  const twiiVal = twiiStats.value?.change_percent || 0;

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => {
        if (!params || !params.length) return '';
        const item = params[0];
        const sector = list[item.dataIndex];
        if (!sector) return '';
        const chgSign = sector.change_percent > 0 ? '+' : '';
        const alphaSign = sector.alpha > 0 ? '+' : '';
        return `
          <div class="p-2 space-y-1 text-xs">
            <div class="font-bold text-sm text-surface-900 dark:text-surface-0 flex items-center gap-1.5">
              <span>#${sector.rank || item.dataIndex + 1}</span>
              <span>${sector.stock_name}</span>
              <span class="text-surface-400 font-normal">(${sector.industry_code})</span>
            </div>
            <div class="text-surface-500">${sector.category_name}</div>
            <div class="flex justify-between gap-4 mt-1">
              <span class="text-surface-500">最新收盤:</span>
              <span class="font-bold">${formatIndexValue(sector.latest_close)}</span>
            </div>
            <div class="flex justify-between gap-4">
              <span class="text-surface-500">累積漲跌:</span>
              <span class="font-bold" style="color:${sector.change_percent >= 0 ? up : down}">
                ${chgSign}${sector.change_percent.toFixed(2)}%
              </span>
            </div>
            <div class="flex justify-between gap-4 border-t border-surface-200 dark:border-surface-700 pt-1 mt-1">
              <span class="text-surface-500">領先大盤 (Alpha):</span>
              <span class="font-bold" style="color:${sector.alpha >= 0 ? up : down}">
                ${alphaSign}${sector.alpha.toFixed(2)}%
              </span>
            </div>
          </div>
        `;
      }
    },
    grid: { left: '4%', right: '8%', bottom: '4%', top: '4%', containLabel: true },
    xAxis: {
      type: 'value',
      name: '漲跌幅 (%)',
      nameTextStyle: { fontSize: 11, color: '#888' },
      axisLabel: { formatter: '{value}%', fontSize: 11 },
      splitLine: { lineStyle: { type: 'dashed', opacity: 0.25 } }
    },
    yAxis: {
      type: 'category',
      data: list.map((s) => s.stock_name),
      axisLabel: { fontSize: 11, fontWeight: 'bold' },
      axisTick: { show: false }
    },
    series: [
      {
        type: 'bar',
        data: list.map((s) => ({
          value: s.change_percent,
          itemStyle: {
            color: s.change_percent >= 0 ? up : down,
            borderRadius: s.change_percent >= 0 ? [0, 4, 4, 0] : [4, 0, 0, 4]
          }
        })),
        barMaxWidth: 16,
        markLine: {
          symbol: 'none',
          data: [
            {
              xAxis: 0,
              lineStyle: { color: '#888888', width: 1.5, type: 'solid' }
            },
            {
              xAxis: twiiVal,
              lineStyle: { color: '#6366f1', width: 1.5, type: 'dashed' },
              label: {
                show: true,
                formatter: `大盤 ${twiiVal > 0 ? '+' : ''}${twiiVal.toFixed(2)}%`,
                position: 'end',
                fontSize: 10,
                color: '#6366f1'
              }
            }
          ]
        }
      }
    ]
  };
});

function onBarClick(params) {
  const list = [...filteredSectors.value].sort((a, b) => (a.change_percent || 0) - (b.change_percent || 0));
  const sector = list[params.dataIndex];
  if (sector) goToSector(sector);
}

// 走勢比較圖選項 (Rebase Comparison Option)
const rebaseCompareOption = computed(() => {
  const topSectors = [...withData.value]
    .sort((a, b) => (b.change_percent || 0) - (a.change_percent || 0))
    .slice(0, 5);

  if (!topSectors.length) return {};

  const colors = ['#ef4444', '#f97316', '#eab308', '#06b6d4', '#8b5cf6', '#64748b'];
  const series = [];
  const legendData = [];

  topSectors.forEach((s, idx) => {
    const raw = s.sparkline || [];
    if (!raw.length) return;
    const base = raw[0] || 1;
    const rebased = raw.map((val) => Number(((val / base) * 100).toFixed(2)));
    legendData.push(s.stock_name);
    series.push({
      name: s.stock_name,
      type: 'line',
      data: rebased,
      showSymbol: false,
      smooth: true,
      lineStyle: { width: 2.5, color: colors[idx % colors.length] }
    });
  });

  const sampleLen = topSectors[0]?.sparkline?.length || 10;
  const xData = Array.from({ length: sampleLen }, (_, i) => `T-${sampleLen - i - 1}`);

  return {
    tooltip: { trigger: 'axis' },
    legend: { data: legendData, bottom: 0, textStyle: { fontSize: 11 } },
    grid: { left: '3%', right: '4%', bottom: '12%', top: '6%', containLabel: true },
    xAxis: { type: 'category', data: xData, boundaryGap: false, axisLabel: { fontSize: 10 } },
    yAxis: {
      type: 'value',
      name: 'Rebase (起點=100)',
      scale: true,
      splitLine: { lineStyle: { type: 'dashed', opacity: 0.25 } }
    },
    series
  };
});
</script>

<style scoped>
.rank-chart-stage {
  width: 100%;
  height: 760px;
}

@media (max-width: 640px) {
  .rank-chart-stage {
    height: 640px;
  }
}
</style>
