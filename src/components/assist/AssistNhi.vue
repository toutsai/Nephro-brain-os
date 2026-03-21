<template>
  <div>
    <h2 class="text-lg font-bold text-slate-800 mb-1">🏛️ 台灣健保給付查詢</h2>
    <p class="text-xs text-slate-400 mb-4">輸入藥物名稱或治療項目，查詢健保給付條件與規範。</p>

    <textarea
      v-model="nhiQuery"
      rows="4"
      class="w-full text-sm border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-rose-400 resize-none leading-relaxed"
      placeholder="例如：
• Dapagliflozin 在 CKD 的健保給付條件？
• Sevelamer 的健保適應症和限制？
• CRRT 健保給付的條件和天數限制？
• Eculizumab 用於 aHUS 的給付規定？"
    />

    <ImageUploader v-model="images" :to-base64="toBase64" class="mt-3" />

    <button
      :disabled="(!nhiQuery.trim() && !images.length) || loading"
      class="mt-3 px-5 py-2.5 bg-rose-600 hover:bg-rose-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
      @click="handleSubmit"
    >
      {{ loading ? '查詢中...' : '🏛️ 查詢健保規定' }}
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

const nhiQuery = ref('')
const images = ref([])

function handleSubmit() {
  emit('submit', {
    mode: 'nhi',
    payload: { query: nhiQuery.value },
    images: images.value.length ? images.value : undefined,
  })
}

function setInput(input) {
  nhiQuery.value = input?.query || ''
  images.value = []
}

function getInput() {
  return { query: nhiQuery.value }
}

function getTitle() {
  return (nhiQuery.value || '').slice(0, 30) || '健保查詢'
}

defineExpose({ setInput, getInput, getTitle })
</script>
