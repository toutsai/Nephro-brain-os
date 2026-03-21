<template>
  <div>
    <h2 class="text-lg font-bold text-slate-800 mb-1">💊 腎功能藥物劑量調整</h2>
    <p class="text-xs text-slate-400 mb-4">輸入藥物與腎功能，或貼上處方截圖。</p>

    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
      <div>
        <label class="block text-xs font-bold text-slate-600 mb-1">藥物名稱</label>
        <input
          v-model="drug"
          class="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-rose-400"
          placeholder="例如：Vancomycin"
        />
      </div>
      <div>
        <label class="block text-xs font-bold text-slate-600 mb-1">eGFR (mL/min/1.73m²)</label>
        <input
          v-model.number="egfr"
          type="number"
          class="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-rose-400"
          placeholder="例如：25"
        />
      </div>
      <div>
        <label class="block text-xs font-bold text-slate-600 mb-1">CKD Stage</label>
        <select
          v-model="ckdStage"
          class="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-rose-400 bg-white"
        >
          <option value="">自動判斷</option>
          <option value="1">Stage 1 (eGFR ≥90)</option>
          <option value="2">Stage 2 (eGFR 60-89)</option>
          <option value="3a">Stage 3a (eGFR 45-59)</option>
          <option value="3b">Stage 3b (eGFR 30-44)</option>
          <option value="4">Stage 4 (eGFR 15-29)</option>
          <option value="5">Stage 5 (eGFR &lt;15)</option>
          <option value="5D">Stage 5D (透析中)</option>
        </select>
      </div>
      <div>
        <label class="block text-xs font-bold text-slate-600 mb-1">體重 (kg，選填)</label>
        <input
          v-model.number="weight"
          type="number"
          class="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-rose-400"
          placeholder="例如：70"
        />
      </div>
    </div>

    <textarea
      v-model="extra"
      rows="2"
      class="w-full text-sm border border-slate-200 rounded-xl px-4 py-2 focus:outline-none focus:ring-2 focus:ring-rose-400 resize-none mb-3"
      placeholder="其他備註（選填）"
    />

    <ImageUploader v-model="images" :to-base64="toBase64" class="mb-3" />

    <button
      :disabled="(!drug.trim() && !images.length) || loading"
      class="px-5 py-2.5 bg-rose-600 hover:bg-rose-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
      @click="handleSubmit"
    >
      {{ loading ? '查詢中...' : '💊 查詢劑量' }}
    </button>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import ImageUploader from '../ImageUploader.vue'

const props = defineProps({
  loading: { type: Boolean, default: false },
  toBase64: { type: Function, required: true },
})

const emit = defineEmits(['submit'])

const drug = ref('')
const egfr = ref(null)
const ckdStage = ref('')
const weight = ref(null)
const extra = ref('')
const images = ref([])

function handleSubmit() {
  emit('submit', {
    mode: 'dose',
    payload: {
      drug: drug.value,
      egfr: egfr.value,
      ckd_stage: ckdStage.value,
      weight: weight.value,
      extra: extra.value,
    },
    images: images.value.length ? images.value : undefined,
  })
}

function setInput(input) {
  drug.value = input?.drug || ''
  egfr.value = input?.egfr || null
  ckdStage.value = input?.ckd_stage || ''
  weight.value = input?.weight || null
  extra.value = input?.extra || ''
  images.value = []
}

function getInput() {
  return { drug: drug.value, egfr: egfr.value, ckd_stage: ckdStage.value, weight: weight.value, extra: extra.value }
}

function getTitle() {
  return drug.value || '藥物劑量'
}

defineExpose({ setInput, getInput, getTitle })
</script>
