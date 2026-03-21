<template>
  <div>
    <h2 class="text-lg font-bold text-slate-800 mb-1">⚡ 藥物交互作用檢查</h2>
    <p class="text-xs text-slate-400 mb-4">輸入多種藥物，檢查交互作用及注意事項。也可拍處方單。</p>

    <textarea
      v-model="drugsInput"
      rows="6"
      class="w-full text-sm border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-rose-400 resize-none leading-relaxed"
      placeholder="列出要檢查的藥物，一行一個或用逗號分隔：

Amlodipine 5mg
Metformin 500mg BID
Lisinopril 10mg
Atorvastatin 20mg
Dapagliflozin 10mg

或直接拍照上傳處方單..."
    />

    <ImageUploader v-model="images" :to-base64="toBase64" class="mt-3" />

    <button
      :disabled="(!drugsInput.trim() && !images.length) || loading"
      class="mt-3 px-5 py-2.5 bg-rose-600 hover:bg-rose-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
      @click="handleSubmit"
    >
      {{ loading ? '檢查中...' : '⚡ 檢查交互作用' }}
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

const drugsInput = ref('')
const images = ref([])

function handleSubmit() {
  emit('submit', {
    mode: 'interaction',
    payload: { drugs: drugsInput.value },
    images: images.value.length ? images.value : undefined,
  })
}

function setInput(input) {
  drugsInput.value = input?.drugs || ''
  images.value = []
}

function getInput() {
  return { drugs: drugsInput.value }
}

function getTitle() {
  return (drugsInput.value || '').slice(0, 30) || '交互作用'
}

defineExpose({ setInput, getInput, getTitle })
</script>
