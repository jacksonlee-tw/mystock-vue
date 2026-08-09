<template>
  <Dialog
    :visible="localVisible"
    :header="header"
    :modal="modal"
    :style="dialogStyle"
    :maximizable="true"
    :closable="closable"
    :class="customClass"
    @hide="onHide"
    @update:visible="onUpdateVisible"
    v-bind="$attrs"
  >
    <slot />
    <template #footer>
      <slot name="footer" />
    </template>
  </Dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import Dialog from 'primevue/dialog'

const props = defineProps({
  visible: Boolean,
  header: {
    type: String,
    default: ''
  },
  modal: {
    type: Boolean,
    default: true
  },
  dialogStyle: {
    type: Object,
    default: () => ({ width: '80vw' })
  },
  closable: {
    type: Boolean,
    default: true
  },
  customClass: {
    type: String,
    default: ''
  }
})

const localVisible = ref(props.visible)

watch(() => props.visible, (val) => {
  localVisible.value = val
})

function onUpdateVisible(val) {
  localVisible.value = val
  emit('update:visible', val)
}

const emit = defineEmits(['update:visible', 'hide'])

function onHide() {
  emit('update:visible', false)
  emit('hide')
}
</script>

<style scoped>

</style>
