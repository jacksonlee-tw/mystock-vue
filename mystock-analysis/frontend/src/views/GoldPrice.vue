<script setup>
import { ref, onMounted } from 'vue'
import { getGoldLatest } from '@/services/goldService'
import { useToast } from 'primevue/usetoast'

const toast = useToast()
const goldData = ref([])
const loading = ref(false)
const lastUpdated = ref(null)

const columns = ref([])

async function fetchGoldPrice() {
  loading.value = true
  try {
    const res = await getGoldLatest()
    if (res.status === 'ok' && Array.isArray(res.data)) {
      goldData.value = res.data
      // 動態從第一筆資料萃取欄位名稱
      if (res.data.length > 0) {
        columns.value = Object.keys(res.data[0])
      }
      lastUpdated.value = new Date().toLocaleString('zh-TW')
    }
  } catch (err) {
    toast.add({
      severity: 'error',
      summary: '載入失敗',
      detail: err?.response?.data?.detail || '無法連線至黃金價格 API',
      life: 5000
    })
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchGoldPrice()
})
</script>

<template>
  <div class="p-4">
    <!-- 頁首 -->
    <div class="flex align-items-center justify-content-between mb-4">
      <div class="flex align-items-center gap-3">
        <i class="pi pi-chart-line text-yellow-500 text-4xl"></i>
        <div>
          <h2 class="text-2xl font-bold text-surface-800 dark:text-surface-100 m-0">黃金價格</h2>
          <p class="text-surface-500 text-sm m-0">資料來源：證券櫃檯買賣中心 TPEX</p>
        </div>
      </div>
      <div class="flex align-items-center gap-2">
        <span v-if="lastUpdated" class="text-surface-400 text-sm">
          更新時間：{{ lastUpdated }}
        </span>
        <Button
          icon="pi pi-refresh"
          label="重新整理"
          severity="secondary"
          :loading="loading"
          @click="fetchGoldPrice"
        />
      </div>
    </div>

    <!-- 說明卡片 -->
    <div class="mb-4 p-3 border-round surface-50 border-1 border-yellow-200">
      <div class="flex align-items-center gap-2 text-yellow-700">
        <i class="pi pi-info-circle"></i>
        <span class="text-sm">以下價格均為台幣計價，資料由 TPEX OpenAPI 即時提供。</span>
      </div>
    </div>

    <!-- 資料表 -->
    <DataTable
      :value="goldData"
      :loading="loading"
      stripedRows
      showGridlines
      class="p-datatable-sm"
      emptyMessage="目前無黃金價格資料"
    >
      <template #loading>
        <div class="flex align-items-center gap-2 justify-content-center py-4">
          <i class="pi pi-spin pi-spinner text-yellow-500 text-xl"></i>
          <span class="text-surface-600">正在取得黃金價格中...</span>
        </div>
      </template>

      <Column
        v-for="col in columns"
        :key="col"
        :field="col"
        :header="col"
        sortable
      >
        <template #body="{ data }">
          <span
            :class="{
              'text-green-600 font-semibold': col.includes('買') || col.includes('Buy'),
              'text-red-600 font-semibold': col.includes('賣') || col.includes('Sell')
            }"
          >
            {{ data[col] ?? '-' }}
          </span>
        </template>
      </Column>

      <template #empty>
        <div class="text-center py-6 text-surface-400">
          <i class="pi pi-inbox text-4xl mb-2 block"></i>
          目前無黃金價格資料，請稍後再試
        </div>
      </template>
    </DataTable>

    <!-- 資料來源 footer -->
    <div class="mt-3 text-right">
      <a
        href="https://www.tpex.org.tw/openapi/"
        target="_blank"
        rel="noopener noreferrer"
        class="text-xs text-surface-400 hover:text-primary no-underline"
      >
        <i class="pi pi-external-link mr-1"></i>
        TPEX OpenAPI
      </a>
    </div>
  </div>

  <Toast />
</template>
