<template>
  <div class="min-h-screen flex items-center justify-center bg-surface-50 dark:bg-surface-950 p-4">
    <Toast />
    <div class="w-full max-w-sm rounded-2xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-lg p-8">
      <div class="flex flex-col items-center mb-6">
        <div class="w-14 h-14 rounded-2xl bg-primary-50 dark:bg-primary-900/30 text-primary flex items-center justify-center text-2xl mb-3">
          <i class="pi pi-bell"></i>
        </div>
        <h1 class="text-xl font-black text-surface-900 dark:text-surface-0">通知設定管理</h1>
        <p class="text-sm text-surface-500 mt-1">系統擁有者專用，需要密碼登入</p>
      </div>

      <form class="space-y-4" @submit.prevent="submit">
        <div>
          <label class="text-sm font-bold text-surface-600 dark:text-surface-300 mb-1.5 block">密碼</label>
          <Password v-model="password" :feedback="false" toggleMask fluid autofocus />
        </div>
        <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>
        <Button type="submit" label="登入" icon="pi pi-sign-in" class="w-full" :loading="loading" />
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useToast } from 'primevue/usetoast';
import { notifyApi } from '@/service/notifyApi';

const router = useRouter();
const route = useRoute();
const toast = useToast();

const password = ref('');
const loading = ref(false);
const error = ref('');

async function submit() {
  loading.value = true;
  error.value = '';
  try {
    await notifyApi.session.login(password.value);
    toast.add({ severity: 'success', summary: '登入成功', life: 2000 });
    router.replace(route.query.redirect || '/notify/channels');
  } catch (err) {
    error.value = err.message || '登入失敗，請確認密碼';
  } finally {
    loading.value = false;
  }
}
</script>
