<template>
  <div class="min-h-screen flex items-center justify-center bg-surface-50 dark:bg-surface-950 p-4">
    <Toast />
    <div class="w-full max-w-sm rounded-2xl border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 shadow-lg p-8">
      <div class="flex flex-col items-center mb-6">
        <div class="w-14 h-14 rounded-2xl bg-primary-50 dark:bg-primary-900/30 text-primary flex items-center justify-center text-2xl mb-3">
          <i class="pi pi-lock"></i>
        </div>
        <h1 class="text-xl font-black text-surface-900 dark:text-surface-0">私人功能驗證</h1>
        <p class="text-sm text-surface-500 mt-1">個人投資與系統設定需要密碼登入</p>
      </div>

      <form v-if="!changingPassword" class="space-y-4" @submit.prevent="submit">
        <div>
          <label class="text-sm font-bold text-surface-600 dark:text-surface-300 mb-1.5 block">密碼</label>
          <Password v-model="password" :feedback="false" toggleMask fluid autofocus />
        </div>
        <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>
        <Button type="submit" label="登入" icon="pi pi-sign-in" class="w-full" :loading="loading" />
        <Button type="button" label="變更密碼" icon="pi pi-key" severity="secondary" text class="w-full" @click="showChangePassword" />
      </form>

      <form v-else class="space-y-4" @submit.prevent="changePassword">
        <div>
          <label class="text-sm font-bold text-surface-600 dark:text-surface-300 mb-1.5 block">原密碼</label>
          <Password v-model="currentPassword" :feedback="false" toggleMask fluid autofocus />
        </div>
        <div>
          <label class="text-sm font-bold text-surface-600 dark:text-surface-300 mb-1.5 block">新密碼</label>
          <Password v-model="newPassword" :feedback="false" toggleMask fluid />
        </div>
        <div>
          <label class="text-sm font-bold text-surface-600 dark:text-surface-300 mb-1.5 block">確認新密碼</label>
          <Password v-model="confirmPassword" :feedback="false" toggleMask fluid />
        </div>
        <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>
        <Button type="submit" label="確認變更" icon="pi pi-check" class="w-full" :loading="loading" />
        <Button type="button" label="返回登入" icon="pi pi-arrow-left" severity="secondary" text class="w-full" @click="showLogin" />
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useToast } from 'primevue/usetoast';
import { ownerApi } from '@/service/ownerApi';

const router = useRouter();
const route = useRoute();
const toast = useToast();

const password = ref('');
const currentPassword = ref('');
const newPassword = ref('');
const confirmPassword = ref('');
const changingPassword = ref(false);
const loading = ref(false);
const error = ref('');

function showChangePassword() {
  changingPassword.value = true;
  password.value = '';
  error.value = '';
}

function showLogin() {
  changingPassword.value = false;
  currentPassword.value = '';
  newPassword.value = '';
  confirmPassword.value = '';
  error.value = '';
}

async function submit() {
  loading.value = true;
  error.value = '';
  try {
    await ownerApi.login(password.value);
    toast.add({ severity: 'success', summary: '登入成功', life: 2000 });
    router.replace(route.query.redirect || '/portfolio/notes');
  } catch (err) {
    error.value = err.message || '登入失敗，請確認密碼';
  } finally {
    loading.value = false;
  }
}

async function changePassword() {
  error.value = '';
  if (newPassword.value.length < 8) {
    error.value = '新密碼至少需要 8 個字元';
    return;
  }
  if (newPassword.value !== confirmPassword.value) {
    error.value = '兩次輸入的新密碼不一致';
    return;
  }

  loading.value = true;
  try {
    await ownerApi.changePassword(currentPassword.value, newPassword.value);
    toast.add({ severity: 'success', summary: '密碼已變更', life: 2000 });
    router.replace(route.query.redirect || '/portfolio/notes');
  } catch (err) {
    error.value = err.message || '密碼變更失敗';
  } finally {
    loading.value = false;
  }
}
</script>
