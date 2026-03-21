<template>
  <div>
    <h2 class="text-lg font-bold text-slate-800 mb-1">🫘 腎臟移植諮詢</h2>
    <p class="text-xs text-slate-400 mb-4">免疫抑制方案、Banff 分類、排斥處理、感染管理。</p>

    <textarea
      v-model="scenario"
      rows="6"
      class="w-full text-sm border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-rose-400 resize-none leading-relaxed"
      placeholder="描述移植相關問題...

例如：
• 腎移植後 3 個月，Cr 從 1.2 升至 2.1，tacrolimus level 8.2
• 移植腎切片 Banff i2t2，如何調整免疫抑制？
• KT 後 6 個月 BK virus load 上升，目前 MMF 1000mg BID + FK 0.1mg/kg BID
• 移植評估：ABO incompatible，如何進行去敏感化？"
    />

    <ImageUploader v-model="images" :to-base64="toBase64" class="mt-3" />

    <button
      :disabled="(!scenario.trim() && !images.length) || loading"
      class="mt-3 px-5 py-2.5 bg-rose-600 hover:bg-rose-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
      @click="handleSubmit"
    >
      {{ loading ? '分析中...' : '🫘 移植諮詢' }}
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
    mode: 'transplant',
    payload: { scenario: scenario.value },
    images: images.value.length ? images.value : undefined,
  })
}

function setInput(input) {
  scenario.value = input?.scenario || ''
  images.value = []
}

function getInput() { return { scenario: scenario.value } }
function getTitle() { return (scenario.value || '').slice(0, 30) || '移植諮詢' }

defineExpose({ setInput, getInput, getTitle })
</script>
