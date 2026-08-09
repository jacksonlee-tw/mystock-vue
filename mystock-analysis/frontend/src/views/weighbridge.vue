<script setup>
// ① Vue 核心
import { ref, reactive } from 'vue'

// ② Composable
import { useWebSocket } from '@/composables/useWebSocket'
import { useWeighbridgeApi } from '@/composables/useWeighbridgeApi'
import { useCardOperation } from '@/composables/useCardOperation'

// ③ PrimeVue 服務
import { useToast } from 'primevue/usetoast'

// ④ API 服務
import { getPoInfo, getTicket as getTicketApi } from '@/services/weighbridgeService'

// ④ Layout 元件
import WeightBoard from '@/components/layout/WeightBoard.vue'

// ⑤ Dialog 元件
import EntryResultDialog from '@/components/modals/EntryResultDialog.vue'
import ExitResultDialog from '@/components/modals/ExitResultDialog.vue'
import OverweightAuthDialog from '@/components/modals/OverweightAuthDialog.vue'
import CardWriteDialog from '@/components/modals/CardWriteDialog.vue'
import CardReadDialog from '@/components/modals/CardReadDialog.vue'
import ReturnConfirmDialog from '@/components/modals/ReturnConfirmDialog.vue'
import PrintDialog from '@/components/modals/PrintDialog.vue'

// ── 常數 ──
const WEIGHT_LIMIT = 5000

// ── 實例化服務 ──
const toast = useToast()
const { connected, currentWeight, weightPulse, wsConnect, wsDisconnect, getCurrentWeightValue } = useWebSocket(toast)
const { confirmEntry, confirmExit, printTicket } = useWeighbridgeApi(toast)
const { cardReadState, cardWriteState, doCardRead, openCardWriteDialog, doCardWrite } = useCardOperation(toast)

// ── 承運單位下拉 ──
const carrierOptions = ref([
  { name: '台泥通運', code: 'TCC' },
  { name: '詠翔物流', code: 'YON' },
  { name: '外部承攬商', code: 'EXT' },
  { name: '自有車輛', code: 'OWN' }
])

// ── 採購量資訊 ──
const poQtyInfo = ref(null)

// ── 入廠表單 ──
const defaultFormIn = () => ({
  carNo: '', shipNo: '', poNo: '', batchNo: '',
  carrier: null, netWeightSupplier: null, netWeightNotary: null,
  materialName: '', supplier: '',
  entryDate: new Date(), entryTime: new Date(),
  entryWeightA1: null, scaleType: 'double'
})
const formIn = ref(defaultFormIn())

// UC-001 + UC-005：採購單號帶入（呼叫後端 API）
const onPoNoBlur = async () => {
  const poNo = formIn.value.poNo.trim()
  if (!poNo) return

  try {
    const result = await getPoInfo(poNo)
    if (result.status === 'found') {
      formIn.value.materialName = result.materialName
      formIn.value.supplier = result.supplier
      const ratio = result.ratio || (result.usedQty / result.planQty)
      poQtyInfo.value = { ...result, ratio }
      if (ratio >= 1)
        toast.add({ severity: 'error', summary: '❌ 採購量超限', detail: `此採購單已超過採購上限（${(ratio * 100).toFixed(1)}%），請停止！`, life: 8000 })
      else if (ratio >= 0.9)
        toast.add({ severity: 'warn', summary: '⚠️ 採購量警示 90%', detail: `此採購單已進貨達 ${(ratio * 100).toFixed(1)}%，請注意！`, life: 4000 })
      else if (ratio >= 0.8)
        toast.add({ severity: 'warn', summary: '⚠️ 採購量警示 80%', detail: `此採購單已進貨達 ${(ratio * 100).toFixed(1)}%，請注意！`, life: 4000 })
      else
        toast.add({ severity: 'success', summary: '✅ 採購單帶入', detail: `原料：${result.materialName}，供應商：${result.supplier}`, life: 3000 })
    } else {
      poQtyInfo.value = null
      formIn.value.materialName = ''
      formIn.value.supplier = ''
      toast.add({ severity: 'warn', summary: '採購單號不存在', detail: `查無採購單「${poNo}」`, life: 4000 })
    }
  } catch {
    poQtyInfo.value = null
    toast.add({ severity: 'error', summary: '查詢失敗', detail: '採購單查詢異常', life: 4000 })
  }
}

const fillEntryWeight = () => {
  const w = getCurrentWeightValue()
  if (w) {
    formIn.value.entryWeightA1 = w
    toast.add({ severity: 'info', summary: '磅值已帶入', detail: `入廠重量 A1 = ${w} Kg`, life: 3000 })
  } else {
    toast.add({ severity: 'warn', summary: '無法帶入', detail: '磅秤目前無有效重量，請先建立連線', life: 3000 })
  }
}

const resetIn = () => {
  formIn.value = defaultFormIn()
  poQtyInfo.value = null
  toast.add({ severity: 'info', summary: '已重設', detail: '入廠表單已清空', life: 3000 })
}

// ── Dialog 狀態 ──
const dlg = reactive({
  inResult: { visible: false, data: null },
  outResult: { visible: false, data: null, netWeight: null },
  overweight: { visible: false },
  returnConfirm: { visible: false },
  print: { visible: false, type: 'in', ticketNo: '' }
})

// UC-001：入廠確認
const doConfirmInEntry = async () => {
  try {
    const result = await confirmEntry(formIn.value)
    if (result.status === 'success') {
      dlg.inResult.data = { ...formIn.value, ticketNo: result.ticketNo, timestamp: result.timestamp }
      dlg.inResult.visible = true
    }
  } catch {
    // handled by composable
  }
}

const handleConfirmIn = async () => {
  if (!formIn.value.carNo.trim()) {
    toast.add({ severity: 'error', summary: '驗証失敗', detail: '車號為必填欄位', life: 3000 }); return
  }
  if (!formIn.value.poNo.trim()) {
    toast.add({ severity: 'error', summary: '驗証失敗', detail: '採購單號為必填欄位', life: 3000 }); return
  }
  if (!formIn.value.entryWeightA1 || formIn.value.entryWeightA1 <= 0) {
    toast.add({ severity: 'error', summary: '驗証失敗', detail: '入廠重量-A1 不能為 0', life: 3000 }); return
  }
  if (poQtyInfo.value && poQtyInfo.value.ratio >= 1) {
    toast.add({ severity: 'error', summary: '已超過採購上限', detail: '此採購單已超過採購上限，無法繼續存檔！', life: 5000 }); return
  }
  if (formIn.value.entryWeightA1 > WEIGHT_LIMIT) {
    dlg.overweight.visible = true
    return
  }
  await doConfirmInEntry()
}

const onOverweightAuthorized = () => {
  doConfirmInEntry()
}

// ── 列印 ──
const printOption = ref({ type: 'in', ticketNo: '' })

const resetPrint = () => {
  printOption.value = { type: 'in', ticketNo: '' }
  toast.add({ severity: 'info', summary: '已取消', detail: '列印作業取消', life: 3000 })
}

const doPrint = () => {
  if (!printOption.value.ticketNo.trim()) {
    toast.add({ severity: 'warn', summary: '請輸入磅單號碼', detail: '磅單號碼不能為空', life: 3000 }); return
  }
  openPrintDialog(printOption.value.type, printOption.value.ticketNo)
}

const openPrintDialog = (type, ticketNo = '') => {
  dlg.print.type = type
  dlg.print.ticketNo = ticketNo
  dlg.print.visible = true
}

const handleDialogPrint = async (ticketNo, type) => {
  try {
    await printTicket(ticketNo, type)
    dlg.print.visible = false
  } catch {
    // handled by composable
  }
}

// ── 讀卡結果套用 ──
const applyCardRead = () => {
  if (cardReadState.mode === 'out') {
    formOut.value.ticketNo = cardReadState.ticketNo
    onTicketNoBlur()
  } else {
    formIn.value.carNo = cardReadState.carNo
    toast.add({ severity: 'success', summary: '讀卡完成', detail: `車號 ${cardReadState.carNo} 已帶入`, life: 3000 })
  }
  cardReadState.visible = false
}

// 寫卡 (入廠成功後)
const onEntryWriteCard = (data) => {
  openCardWriteDialog(data)
}

// ── 出廠表單 ──
const defaultFormOut = () => ({
  isReturn: false,
  storageWeightA2: null, storageStatus: 'normal',
  outboundWeightB2: null,
  ticketNo: '',
  corrCarNo: '', corrPoNo: '', corrBatchNo: '',
  corrNetWeightSupplier: null, corrNetWeightNotary: null,
  corrMaterialName: '', corrSupplierName: '',
  exitDate: new Date(), exitTime: new Date(),
  exitWeightB1: null, exitStatus: 'normal'
})
const formOut = ref(defaultFormOut())
const _inEntryWeightA1 = ref(null)

// UC-002：磅單號查詢 → 自動帶入（呼叫後端 API）
const onTicketNoBlur = async () => {
  const ticketNo = formOut.value.ticketNo.trim()
  if (!ticketNo) return

  try {
    const result = await getTicketApi(ticketNo)
    if (result.status === 'found') {
      formOut.value.corrCarNo = result.truckNo || ''
      formOut.value.corrPoNo = result.poNo || ''
      formOut.value.corrBatchNo = result.batchNo || ''
      formOut.value.corrMaterialName = result.prodName || ''
      formOut.value.corrSupplierName = result.supplier || ''
      _inEntryWeightA1.value = result.weigth1 || result.entryWeightA1 || null
      toast.add({ severity: 'success', summary: '✅ 磅單帶入', detail: `車號：${result.truckNo || ''}，原料：${result.prodName || ''}，進廠 A1：${result.weigth1 || ''} Kg`, life: 4000 })
    } else {
      _inEntryWeightA1.value = null
      toast.add({ severity: 'warn', summary: '磅單不存在', detail: `查無磅單「${ticketNo}」`, life: 4000 })
    }
  } catch {
    _inEntryWeightA1.value = null
    toast.add({ severity: 'error', summary: '查詢失敗', detail: '磅單查詢異常', life: 4000 })
  }
}

const fillExitWeight = () => {
  const w = getCurrentWeightValue()
  if (w) {
    formOut.value.exitWeightB1 = w
    toast.add({ severity: 'info', summary: '磅值已帶入', detail: `出廠重量 B1 = ${w} Kg`, life: 3000 })
  } else {
    toast.add({ severity: 'warn', summary: '無法帶入', detail: '磅秤目前無有效重量，請先建立連線', life: 3000 })
  }
}

const resetOut = () => {
  formOut.value = defaultFormOut()
  _inEntryWeightA1.value = null
  toast.add({ severity: 'info', summary: '已重設', detail: '出廠表單已清空', life: 3000 })
}

// UC-002：出廠確認
const doConfirmOutExit = async () => {
  try {
    const result = await confirmExit(formOut.value)
    if (result.status === 'success') {
      const netWeight = _inEntryWeightA1.value != null
        ? (_inEntryWeightA1.value - (formOut.value.exitWeightB1 || 0))
        : null
      dlg.outResult.data = { ...formOut.value, timestamp: result.timestamp }
      dlg.outResult.netWeight = netWeight
      dlg.outResult.visible = true
    }
  } catch {
    // handled by composable
  }
}

const handleConfirmOut = async () => {
  if (!formOut.value.ticketNo.trim()) {
    toast.add({ severity: 'error', summary: '驗証失敗', detail: '磅單號為必填欄位', life: 3000 }); return
  }
  if (!formOut.value.exitWeightB1 || formOut.value.exitWeightB1 <= 0) {
    toast.add({ severity: 'error', summary: '驗証失敗', detail: '出廠重量-B1 不能為 0', life: 3000 }); return
  }
  if (formOut.value.isReturn) {
    dlg.returnConfirm.visible = true; return
  }
  await doConfirmOutExit()
}

const onReturnConfirmed = () => {
  dlg.returnConfirm.visible = false
  doConfirmOutExit()
}
</script>

<template>
  <div>
    <!-- 即時重量 + 連線控制 -->
    <WeightBoard
      :connected="connected"
      :currentWeight="currentWeight"
      :weightPulse="weightPulse"
      @connect="wsConnect"
      @disconnect="wsDisconnect"
    />

    <!-- 主表單區 -->
    <div class="weighbridge-container">
      <div class="grid">

        <!-- ═══ 左側：入廠作業 A1（UC-001）═══ -->
        <div class="col-12 md:col-6">
          <Fieldset legend="入廠作業 - A1（UC-001）" class="h-full">
            <div class="p-fluid formgrid grid">

              <div class="field col-12 flex align-items-center">
                <label class="w-8rem text-right mr-2 label-required flex-shrink-0">車號</label>
                <InputText v-model="formIn.carNo" class="flex-1" placeholder="例：ABC-1234" />
                <label class="w-4rem text-right mx-2 flex-shrink-0">船號</label>
                <InputText v-model="formIn.shipNo" class="flex-1" placeholder="選填" />
              </div>

              <div class="field col-12 flex align-items-center">
                <label class="w-8rem text-right mr-2 label-required flex-shrink-0">採購/合約/生產單號</label>
                <InputText v-model="formIn.poNo" class="flex-1"
                           placeholder="PO001 / PO002 / PO003 / PO004"
                           @blur="onPoNoBlur" @keyup.enter="onPoNoBlur" />
              </div>

              <!-- UC-005：採購量警示進度條 -->
              <div v-if="poQtyInfo" class="field col-12">
                <div class="qty-bar-wrap">
                  <div class="qty-bar-label flex justify-content-between">
                    <span>採購單使用量：{{ poQtyInfo.usedQty.toLocaleString() }} / {{ poQtyInfo.planQty.toLocaleString() }} Kg</span>
                    <span :class="poQtyInfo.ratio >= 1 ? 'error-text' : poQtyInfo.ratio >= 0.9 ? 'warn-text' : ''">
                      {{ (poQtyInfo.ratio * 100).toFixed(1) }}%
                    </span>
                  </div>
                  <div class="qty-bar">
                    <div class="qty-bar-fill" :style="{ width: Math.min(poQtyInfo.ratio, 1) * 100 + '%',
                      background: poQtyInfo.ratio >= 1 ? '#ef4444' : poQtyInfo.ratio >= 0.9 ? '#f97316' : '#22c55e' }"></div>
                  </div>
                </div>
              </div>

              <div class="field col-12 flex align-items-center">
                <label class="w-8rem text-right mr-2 flex-shrink-0">批次</label>
                <InputText v-model="formIn.batchNo" class="flex-1" placeholder="選填" />
              </div>

              <div class="field col-12 flex align-items-center">
                <label class="w-8rem text-right mr-2 flex-shrink-0">承運單位</label>
                <Dropdown v-model="formIn.carrier" :options="carrierOptions"
                          optionLabel="name" optionValue="code"
                          placeholder="請選擇承運單位" class="flex-1" :showClear="true" />
              </div>

              <div class="field col-12 flex align-items-center">
                <label class="w-8rem text-right mr-2 flex-shrink-0">貨物淨重-供應商</label>
                <div class="p-inputgroup flex-1">
                  <InputNumber v-model="formIn.netWeightSupplier" :minFractionDigits="0" :maxFractionDigits="2" />
                  <span class="p-inputgroup-addon">Kg</span>
                </div>
              </div>

              <div class="field col-12 flex align-items-center">
                <label class="w-8rem text-right mr-2 flex-shrink-0">貨物淨重-公證單位</label>
                <div class="p-inputgroup flex-1">
                  <InputNumber v-model="formIn.netWeightNotary" :minFractionDigits="0" :maxFractionDigits="2" />
                  <span class="p-inputgroup-addon">Kg</span>
                </div>
              </div>

              <div class="field col-12 flex align-items-center">
                <label class="w-8rem text-right mr-2 flex-shrink-0">原料名稱</label>
                <InputText v-model="formIn.materialName" class="flex-1" placeholder="輸入採購單號後自動帶入" />
              </div>

              <div class="field col-12 flex align-items-center">
                <label class="w-8rem text-right mr-2 flex-shrink-0">供應商</label>
                <InputText v-model="formIn.supplier" class="flex-1" placeholder="輸入採購單號後自動帶入" />
              </div>

              <div class="field col-12 flex align-items-center">
                <label class="w-8rem text-right mr-2 flex-shrink-0">入廠日期</label>
                <Calendar v-model="formIn.entryDate" dateFormat="yy-mm-dd" showIcon class="flex-1" />
              </div>

              <div class="field col-12 flex align-items-center">
                <label class="w-8rem text-right mr-2 flex-shrink-0">入廠時間</label>
                <Calendar v-model="formIn.entryTime" :timeOnly="true" showIcon class="flex-1" />
              </div>

              <div class="field col-12 flex align-items-center">
                <label class="w-8rem text-right mr-2 label-required flex-shrink-0">入廠重量-A1</label>
                <div class="p-inputgroup flex-1">
                  <InputNumber v-model="formIn.entryWeightA1" :minFractionDigits="0" :maxFractionDigits="2" />
                  <span class="p-inputgroup-addon font-bold">Kg</span>
                </div>
                <Button icon="pi pi-download" label="帶入" class="p-button-sm p-button-outlined ml-2"
                        @click="fillEntryWeight" title="帶入當前磅值" />
              </div>

              <!-- 地磅選擇 -->
              <div class="field col-12 flex justify-content-center gap-4 my-2">
                <div class="flex align-items-center">
                  <RadioButton v-model="formIn.scaleType" inputId="scaleDouble" value="double" />
                  <label for="scaleDouble" class="ml-2">雙磅作業</label>
                </div>
                <div class="flex align-items-center">
                  <RadioButton v-model="formIn.scaleType" inputId="scale1" value="scale1" />
                  <label for="scale1" class="ml-2">1# 地磅</label>
                </div>
                <div class="flex align-items-center">
                  <RadioButton v-model="formIn.scaleType" inputId="scale2" value="scale2" />
                  <label for="scale2" class="ml-2">2# 地磅</label>
                </div>
              </div>

              <!-- 入廠主要操作按鈕 -->
              <div class="field col-12 flex justify-content-center gap-3">
                <Button label="作業取消" icon="pi pi-times"
                        class="p-button-secondary p-button-outlined"
                        @click="resetIn" />
                <Button label="確認過磅/存檔" icon="pi pi-check"
                        class="p-button-success" @click="handleConfirmIn" />
              </div>

              <Divider />

              <!-- UC-004：補印 / 讀卡 / 寫卡 -->
              <div class="field col-12 flex gap-2 flex-wrap">
                <Button label="重印入廠磅單 R" icon="pi pi-print"
                        class="p-button-sm p-button-info p-button-outlined"
                        @click="openPrintDialog('in')" />
                <Button label="重新寫卡" icon="pi pi-pencil"
                        class="p-button-sm p-button-help p-button-outlined"
                        @click="openCardWriteDialog(null)" />
                <Button label="讀卡" icon="pi pi-credit-card"
                        class="p-button-sm p-button-outlined"
                        @click="doCardRead('in')" />
              </div>

              <!-- UC-003：磅單列印選項 -->
              <div class="field col-12 mt-2 p-3 surface-50 border-round border-1 surface-border">
                <div class="flex align-items-center gap-4 mb-2">
                  <span class="font-bold text-sm">補印磅單</span>
                  <div class="flex align-items-center">
                    <RadioButton v-model="printOption.type" inputId="printIn" value="in" />
                    <label for="printIn" class="ml-2 text-sm">入廠磅單</label>
                  </div>
                  <div class="flex align-items-center">
                    <RadioButton v-model="printOption.type" inputId="printOut" value="out" />
                    <label for="printOut" class="ml-2 text-sm">出廠磅單</label>
                  </div>
                </div>
                <div class="flex align-items-center mb-3">
                  <label class="w-6rem text-right mr-2 text-sm flex-shrink-0">磅單號碼</label>
                  <InputText v-model="printOption.ticketNo" class="flex-1" placeholder="輸入磅單號碼" />
                </div>
                <div class="flex gap-2">
                  <Button label="列印確定 P" icon="pi pi-print"
                          class="p-button-sm" @click="doPrint" />
                  <Button label="列印取消" icon="pi pi-times"
                          class="p-button-sm p-button-secondary p-button-outlined"
                          @click="resetPrint" />
                </div>
              </div>

            </div>
          </Fieldset>
        </div>

        <!-- ═══ 右側：出廠作業 B1（UC-002）═══ -->
        <div class="col-12 md:col-6">
          <Fieldset class="h-full">
            <template #legend>
              <div class="flex align-items-center gap-2">
                <span class="font-bold" style="color: #0f766e">出廠作業 - B1（UC-002）</span>
                <Checkbox v-model="formOut.isReturn" :binary="true" inputId="isReturn" />
                <label for="isReturn" class="text-sm font-normal" style="cursor: pointer">
                  <span class="text-red-500 font-bold">退貨</span>
                </label>
              </div>
            </template>

            <div class="p-fluid formgrid grid">

              <!-- 入庫作業 A2 -->
              <div class="col-12 border-bottom-1 surface-border pb-3 mb-2">
                <div class="font-bold mb-2 text-teal-700 text-sm">── 入庫作業（A2）──</div>
                <div class="field flex align-items-center mb-2">
                  <label class="w-8rem text-right mr-2 flex-shrink-0 text-sm">入庫重量-A2</label>
                  <div class="p-inputgroup flex-1">
                    <InputNumber v-model="formOut.storageWeightA2" :minFractionDigits="0" :maxFractionDigits="2" />
                    <span class="p-inputgroup-addon">Kg</span>
                  </div>
                </div>
                <div class="field flex align-items-center mb-0">
                  <label class="w-8rem text-right mr-2 flex-shrink-0 text-sm">狀態燈號</label>
                  <div class="flex gap-4">
                    <div class="flex align-items-center">
                      <RadioButton v-model="formOut.storageStatus" inputId="inWarn" value="warning" />
                      <label for="inWarn" class="ml-1 text-sm">
                        <span class="status-light light-orange"></span>警告
                      </label>
                    </div>
                    <div class="flex align-items-center">
                      <RadioButton v-model="formOut.storageStatus" inputId="inNormal" value="normal" />
                      <label for="inNormal" class="ml-1 text-sm">
                        <span class="status-light light-green"></span>正常
                      </label>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 出庫作業 B2 -->
              <div class="col-12 border-bottom-1 surface-border pb-3 mb-2">
                <div class="font-bold mb-2 text-teal-700 text-sm">── 出庫作業（B2）──</div>
                <div class="field flex align-items-center mb-0">
                  <label class="w-8rem text-right mr-2 flex-shrink-0 text-sm">出庫重量-B2</label>
                  <div class="p-inputgroup flex-1">
                    <InputNumber v-model="formOut.outboundWeightB2" :minFractionDigits="0" :maxFractionDigits="2" />
                    <span class="p-inputgroup-addon">Kg</span>
                  </div>
                </div>
              </div>

              <!-- 出廠過磅 B1 -->
              <div class="col-12">
                <div class="font-bold mb-2 text-teal-700 text-sm">── 出廠過磅（B1）──</div>

                <div class="field flex align-items-center">
                  <label class="w-8rem text-right mr-2 label-required flex-shrink-0 text-sm">磅單號</label>
                  <div class="p-inputgroup flex-1">
                    <InputText v-model="formOut.ticketNo" placeholder="輸入或刷卡帶入（IN20240101000001）"
                               @blur="onTicketNoBlur" @keyup.enter="onTicketNoBlur" />
                    <Button label="讀卡" icon="pi pi-credit-card"
                            class="p-button-secondary p-button-outlined"
                            @click="doCardRead('out')" />
                  </div>
                </div>

                <div class="field flex align-items-center">
                  <label class="w-8rem text-right mr-2 flex-shrink-0 text-sm">修正車號</label>
                  <InputText v-model="formOut.corrCarNo" class="flex-1" placeholder="自動帶入或手動修正" />
                </div>

                <div class="field flex align-items-center">
                  <label class="w-8rem text-right mr-2 flex-shrink-0 text-sm">修正採購單號</label>
                  <InputText v-model="formOut.corrPoNo" class="flex-1" />
                </div>

                <div class="field flex align-items-center">
                  <label class="w-8rem text-right mr-2 flex-shrink-0 text-sm">修正批次</label>
                  <InputText v-model="formOut.corrBatchNo" class="flex-1" />
                </div>

                <div class="field flex align-items-center">
                  <label class="w-8rem text-right mr-2 flex-shrink-0 text-sm">修正淨重-供應商</label>
                  <div class="p-inputgroup flex-1">
                    <InputNumber v-model="formOut.corrNetWeightSupplier" :minFractionDigits="0" :maxFractionDigits="2" />
                    <span class="p-inputgroup-addon">Kg</span>
                  </div>
                </div>

                <div class="field flex align-items-center">
                  <label class="w-8rem text-right mr-2 flex-shrink-0 text-sm">修正淨重-公證單位</label>
                  <div class="p-inputgroup flex-1">
                    <InputNumber v-model="formOut.corrNetWeightNotary" :minFractionDigits="0" :maxFractionDigits="2" />
                    <span class="p-inputgroup-addon">Kg</span>
                  </div>
                </div>

                <div class="field flex align-items-center">
                  <label class="w-8rem text-right mr-2 flex-shrink-0 text-sm">修正原料名稱</label>
                  <InputText v-model="formOut.corrMaterialName" class="flex-1" />
                </div>

                <div class="field flex align-items-center">
                  <label class="w-8rem text-right mr-2 flex-shrink-0 text-sm">修正供應商名稱</label>
                  <InputText v-model="formOut.corrSupplierName" class="flex-1" />
                </div>

                <div class="field flex align-items-center">
                  <label class="w-8rem text-right mr-2 flex-shrink-0 text-sm">出廠日期</label>
                  <Calendar v-model="formOut.exitDate" dateFormat="yy-mm-dd" showIcon class="flex-1" />
                </div>

                <div class="field flex align-items-center">
                  <label class="w-8rem text-right mr-2 flex-shrink-0 text-sm">出廠時間</label>
                  <Calendar v-model="formOut.exitTime" :timeOnly="true" showIcon class="flex-1" />
                </div>

                <div class="field flex align-items-center">
                  <label class="w-8rem text-right mr-2 label-required flex-shrink-0 text-sm">出廠重量-B1</label>
                  <div class="p-inputgroup flex-1">
                    <InputNumber v-model="formOut.exitWeightB1" :minFractionDigits="0" :maxFractionDigits="2" />
                    <span class="p-inputgroup-addon font-bold">Kg</span>
                  </div>
                  <Button icon="pi pi-download" label="帶入" class="p-button-sm p-button-outlined ml-2"
                          @click="fillExitWeight" title="帶入當前磅值" />
                </div>

                <!-- 出廠狀態燈號 + 操作按鈕 -->
                <div class="field flex justify-content-between align-items-center mt-3 flex-wrap gap-2">
                  <div class="flex align-items-center surface-50 p-2 border-round border-1 surface-border">
                    <span class="mr-2 font-bold text-sm">狀態</span>
                    <div class="flex gap-3">
                      <div class="flex align-items-center">
                        <RadioButton v-model="formOut.exitStatus" inputId="outWarn" value="warning" />
                        <label for="outWarn" class="ml-1 text-sm">
                          <span class="status-light light-orange"></span>警告
                        </label>
                      </div>
                      <div class="flex align-items-center">
                        <RadioButton v-model="formOut.exitStatus" inputId="outNormal" value="normal" />
                        <label for="outNormal" class="ml-1 text-sm">
                          <span class="status-light light-green"></span>正常
                        </label>
                      </div>
                    </div>
                  </div>
                  <div class="flex gap-2">
                    <Button label="作業取消" icon="pi pi-times"
                            class="p-button-secondary p-button-outlined"
                            @click="resetOut" />
                    <Button label="重量確認" icon="pi pi-check"
                            class="p-button-success" @click="handleConfirmOut" />
                  </div>
                </div>

                <div class="mt-2">
                  <Button label="重印出廠磅單 R" icon="pi pi-print"
                          class="p-button-sm p-button-info p-button-outlined"
                          @click="openPrintDialog('out')" />
                </div>
              </div>
            </div>
          </Fieldset>
        </div>

      </div>
    </div>

    <!-- ── Dialogs ── -->
    <EntryResultDialog
      v-model:visible="dlg.inResult.visible"
      :data="dlg.inResult.data"
      @writeCard="onEntryWriteCard"
    />

    <ExitResultDialog
      v-model:visible="dlg.outResult.visible"
      :data="dlg.outResult.data"
      :netWeight="dlg.outResult.netWeight"
    />

    <OverweightAuthDialog
      v-model:visible="dlg.overweight.visible"
      :entryWeight="formIn.entryWeightA1"
      :weightLimit="WEIGHT_LIMIT"
      @authorized="onOverweightAuthorized"
    />

    <CardWriteDialog
      v-model:visible="cardWriteState.visible"
      :data="cardWriteState.data"
      @write="doCardWrite"
    />

    <CardReadDialog
      v-model:visible="cardReadState.visible"
      :ticketNo="cardReadState.ticketNo"
      :carNo="cardReadState.carNo"
      :materialName="cardReadState.materialName"
      @apply="applyCardRead"
    />

    <ReturnConfirmDialog
      v-model:visible="dlg.returnConfirm.visible"
      :ticketNo="formOut.ticketNo"
      @confirmed="onReturnConfirmed"
    />

    <PrintDialog
      v-model:visible="dlg.print.visible"
      :type="dlg.print.type"
      :ticketNo="dlg.print.ticketNo"
      @print="handleDialogPrint"
    />
  </div>
</template>
