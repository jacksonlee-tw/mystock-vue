<template>
  <main class="min-h-screen bg-surface-100 dark:bg-surface-950">
    <AiAnalysisDialog
      :visible="true"
      stage="result"
      fullscreen
      :loading="loading"
      :error="error"
      :report="report"
      :market="report?.market || 'tw'"
      :allow-reselect="false"
    />
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import AiAnalysisDialog from '@/components/AiAnalysisDialog.vue';
import { aiAnalysisApi } from '@/service/aiAnalysisApi';

const route = useRoute();
const loading = ref(true);
const error = ref(null);
const report = ref(null);

onMounted(async () => {
  try {
    const response = await aiAnalysisApi.getReport(route.params.reportId);
    report.value = response.data;
    document.title = `${report.value.symbol} AI 診股報告 | MyStock`;
  } catch (err) {
    error.value = err.response?.data?.error?.message || err.message || '讀取報告失敗';
  } finally {
    loading.value = false;
  }
});
</script>