<template>
  <!-- 首頁「自訂版面」：勾選要顯示哪些 widget。被取消勾選的 widget 不會發任何請求（見各 panel 的 isEnabled 判斷）。 -->
  <div class="inline-flex">
    <button
      type="button"
      class="inline-flex items-center gap-1.5 rounded-lg border border-surface-300 dark:border-surface-600 bg-surface-0 dark:bg-surface-900 px-3 py-1.5 text-sm font-bold text-surface-700 dark:text-surface-200 hover:border-primary hover:text-primary transition-colors"
      aria-haspopup="dialog"
      :aria-expanded="open"
      @click="toggleOverlay"
    >
      <i class="pi pi-sliders-h text-xs" aria-hidden="true"></i>
      <span>自訂版面 <span class="num">{{ enabledCount }}/{{ registry.length }}</span></span>
    </button>

    <!-- 寬度以視窗為上限，手機（375px）不會溢出畫面；內容過長時內部捲動 -->
    <Popover ref="panelRef" class="home-widget-settings" @show="open = true" @hide="open = false">
      <div class="w-80 max-w-[calc(100vw-2rem)] max-h-[70vh] overflow-y-auto" role="group" aria-label="首頁顯示項目">
        <p class="text-xs text-surface-500 mt-0 mb-3">勾選要顯示在首頁的項目；取消勾選的項目不會載入資料。</p>

        <section v-for="section in sections" :key="section" class="mb-3 last:mb-0">
          <h4 class="text-xs font-bold text-surface-500 uppercase tracking-wide m-0 mb-1.5">{{ section }}</h4>
          <ul class="m-0 p-0 list-none space-y-1">
            <li v-for="w in itemsOf(section)" :key="w.id" class="flex items-center gap-2">
              <Checkbox
                :model-value="isEnabled(w.id)"
                :input-id="`home-widget-${w.id}`"
                binary
                :disabled="isLocked(w)"
                @update:model-value="(v) => toggle(w.id, v)"
              />
              <label
                :for="`home-widget-${w.id}`"
                class="flex-1 min-w-0 flex items-center gap-1.5 text-sm select-none"
                :class="isLocked(w) ? 'text-surface-400 cursor-not-allowed' : 'text-surface-800 dark:text-surface-100 cursor-pointer'"
              >
                <i :class="['pi', w.icon, 'text-xs text-surface-400']" aria-hidden="true"></i>
                <span class="truncate">{{ w.label }}</span>
                <span
                  v-if="isLocked(w)"
                  class="shrink-0 text-[10px] font-bold px-1.5 py-0.5 rounded bg-surface-200 dark:bg-surface-700 text-surface-600 dark:text-surface-300"
                >需登入</span>
              </label>
            </li>
          </ul>
        </section>

        <div class="pt-3 mt-3 border-t border-surface-200 dark:border-surface-700 flex justify-end">
          <button
            type="button"
            class="text-xs font-bold text-primary hover:underline"
            @click="resetAll"
          >全部重設</button>
        </div>
      </div>
    </Popover>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useHomeWidgets } from '@/composables/useHomeWidgets';

const props = defineProps({
  ownerAuthenticated: { type: Boolean, default: false }
});

const { registry, sections, isEnabled, toggle, resetAll, enabledCount } = useHomeWidgets();

const panelRef = ref(null);
const open = ref(false); // 只用來同步 aria-expanded

function toggleOverlay(event) {
  panelRef.value?.toggle(event);
}

function itemsOf(section) {
  return registry.filter((w) => w.section === section);
}

// 需登入的項目在未登入時無法勾選（首頁本來就不會渲染它）
function isLocked(widget) {
  return widget.requiresOwner && !props.ownerAuthenticated;
}
</script>
