<template>
  <div>
    <h2 class="text-lg font-bold text-slate-800 mb-1">🔬 Lab 鑑別診斷</h2>
    <p class="text-xs text-slate-400 mb-4">輸入檢驗數據或直接拍照上傳 lab 報告。</p>

    <textarea
      v-model="labData"
      rows="6"
      class="w-full text-sm border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-rose-400 resize-none font-mono leading-relaxed"
      placeholder="貼上 lab data 或留空只上傳圖片...

BUN 85, Cr 4.2, K 6.1, Na 132
Ca 7.8, P 6.5, Albumin 2.8..."
    />

    <ImageUploader v-model="images" :to-base64="toBase64" class="mt-3" />

    <button
      :disabled="(!labData.trim() && !images.length) || loading"
      class="mt-3 px-5 py-2.5 bg-rose-600 hover:bg-rose-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
      @click="handleSubmit"
    >
      {{ loading ? '分析中...' : '🔬 鑑別診斷' }}
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

const labData = ref('')
const images = ref([])

function handleSubmit() {
  emit('submit', {
    mode: 'lab',
    payload: { lab_data: labData.value },
    images: images.value.length ? images.value : undefined,
  })
}

function setInput(input) {
  labData.value = input?.lab_data || ''
  images.value = []
}

function getInput() {
  return { lab_data: labData.value }
}

function getTitle() {
  return (labData.value || '').slice(0, 30) || 'Lab 鑑別'
}

defineExpose({ setInput, getInput, getTitle })
</script>
