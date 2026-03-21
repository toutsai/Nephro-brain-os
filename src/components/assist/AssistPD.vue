<template>
  <div>
    <h2 class="text-lg font-bold text-slate-800 mb-1">🔄 腹膜透析諮詢</h2>
    <p class="text-xs text-slate-400 mb-4">PD 處方調整、PET 解讀、腹膜炎處理、透析充分性評估。</p>

    <textarea
      v-model="scenario"
      rows="6"
      class="w-full text-sm border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-rose-400 resize-none leading-relaxed"
      placeholder="描述 PD 相關問題...

例如：
• CAPD 病人，4 exchanges/day 2L 1.5%，Kt/V 1.5 但超濾量不足
• PET 結果：D/P Cr 0.81 (4h)，如何解讀及調整處方？
• PD 腹膜炎：引流液混濁，WBC 520/μL，95% PMN，如何經驗性治療？
• APD 處方建議：殘餘腎功能 GFR 3 mL/min"
    />

    <ImageUploader v-model="images" :to-base64="toBase64" class="mt-3" />

    <button
      :disabled="(!scenario.trim() && !images.length) || loading"
      class="mt-3 px-5 py-2.5 bg-rose-600 hover:bg-rose-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
      @click="handleSubmit"
    >
      {{ loading ? '分析中...' : '🔄 PD 諮詢' }}
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

const scenario = ref('')
const images = ref([])

function handleSubmit() {
  emit('submit', {
    mode: 'pd',
    payload: { scenario: scenario.value },
    images: images.value.length ? images.value : undefined,
  })
}

function setInput(input) {
  scenario.value = input?.scenario || ''
  images.value = []
}

function getInput() { return { scenario: scenario.value } }
function getTitle() { return (scenario.value || '').slice(0, 30) || 'PD 諮詢' }

defineExpose({ setInput, getInput, getTitle })
</script>
