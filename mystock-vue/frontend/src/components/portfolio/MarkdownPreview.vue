<template>
  <div ref="root" v-html="renderedContent"></div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue';
import { renderMarkdown, renderMermaidDiagrams } from '@/utils/markdownRenderer';

const props = defineProps({
  source: { type: String, default: '' }
});

const root = ref(null);
const renderedContent = computed(() => renderMarkdown(props.source));

watch(
  renderedContent,
  async () => {
    await nextTick();
    await renderMermaidDiagrams(root.value);
  },
  { immediate: true, flush: 'post' }
);
</script>

<style scoped>
:deep(.mermaid-diagram) {
  margin: 1rem 0;
  padding: 1rem;
  overflow-x: auto;
  border: 1px solid var(--p-content-border-color);
  border-radius: 0.5rem;
  background: #fff;
}

:deep(.mermaid-diagram svg) {
  display: block;
  width: auto;
  max-width: 100%;
  height: auto;
  margin: 0 auto;
}

:deep(.mermaid-error-source) {
  border: 1px solid var(--p-red-300);
}

:deep(.mermaid-error-message) {
  margin: -0.5rem 0 1rem;
  color: var(--p-red-500);
  font-size: 0.8rem;
}
</style>