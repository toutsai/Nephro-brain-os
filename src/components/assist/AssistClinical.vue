<template>
  <div>
    <h2 class="text-lg font-bold text-slate-800 mb-1">🏥 臨床情境諮詢</h2>
    <p class="text-xs text-slate-400 mb-4">描述病人情況或貼上病歷截圖，取得實證指引建議。</p>

    <textarea
      v-model="scenario"
      rows="5"
      class="w-full text-sm border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-rose-400 resize-none leading-relaxed"
      placeholder="例如：65 歲男性，DM + CKD stage 4 (eGFR 22)，近期出現持續性高血鉀 (K 6.2)..."
    />

    <ImageUploader v-model="images" :to-base64="toBase64" class="mt-3" />

    <button
      :disabled="(!scenario.trim() && !images.length) || loading"
      class="mt-3 px-5 py-2.5 bg-rose-600 hover:bg-rose-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
      @click="handleSubmit"
    >
      {{ loading ? '分析中...' : '🔍 實證分析' }}
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
    mode: 'clinical',
    payload: { scenario: scenario.value },
    images: images.value.length ? images.value : undefined,
  })
}

function setInput(input) {
  scenario.value = input?.scenario || ''
  images.value = []
}

function getInput() {
  return { scenario: scenario.value }
}

function getTitle() {
  return (scenario.value || '').slice(0, 30) || '臨床情境'
}

defineExpose({ setInput, getInput, getTitle })
</script>
