<template>
  <div
    class="rounded-xl border p-4 transition-all"
    :class="statusClass"
  >
    <div class="flex items-start gap-3">
      <!-- Book icon -->
      <div
        class="shrink-0 w-10 h-10 rounded-lg flex items-center justify-center text-lg"
        :class="iconClass"
      >
        {{ statusIcon }}
      </div>

      <div class="min-w-0 flex-1">
        <!-- Title -->
        <h4 class="text-sm font-bold text-slate-800 truncate">
          {{ book.title || book.filename || '未命名書籍' }}
        </h4>

        <!-- Meta -->
        <div class="flex items-center gap-3 mt-1 text-[10px] text-slate-400">
          <span v-if="book.pages_count">{{ book.pages_count }} 頁</span>
          <span v-if="book.chunks_count">{{ book.chunks_count }} 片段</span>
          <span v-if="book.uploaded_at">
            {{ formatDate(book.uploaded_at) }}
          </span>
        </div>

        <!-- Status badge -->
        <div class="mt-2">
          <span
            class="text-[10px] font-bold px-2 py-0.5 rounded-full"
            :class="badgeClass"
          >
            {{ statusLabel }}
          </span>
          <span
            v-if="book.status === 'processing'"
            class="text-[10px] text-slate-400 ml-2"
          >
            處理中...
          </span>
          <span
            v-if="book.error_message"
            class="text-[10px] text-red-400 ml-2"
          >
            {{ book.error_message }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  book: { type: Object, required: true },
})

const statusIcon = computed(() => {
  switch (props.book.status) {
    case 'ready': return '📗'
    case 'processing': return '⏳'
    case 'pending': return '📤'
    case 'error': return '❌'
    default: return '📄'
  }
})

const statusLabel = computed(() => {
  switch (props.book.status) {
    case 'ready': return '已就緒'
    case 'processing': return '處理中'
    case 'pending': return '等待處理'
    case 'error': return '處理失敗'
    default: return props.book.status || '未知'
  }
})

const statusClass = computed(() => {
  switch (props.book.status) {
    case 'ready': return 'bg-white border-slate-200'
    case 'processing': return 'bg-amber-50/50 border-amber-200'
    case 'pending': return 'bg-blue-50/50 border-blue-200'
    case 'error': return 'bg-red-50/50 border-red-200'
    default: return 'bg-white border-slate-200'
  }
})

const iconClass = computed(() => {
  switch (props.book.status) {
    case 'ready': return 'bg-emerald-100'
    case 'processing': return 'bg-amber-100 animate-pulse'
    case 'pending': return 'bg-blue-100'
    case 'error': return 'bg-red-100'
    default: return 'bg-slate-100'
  }
})

const badgeClass = computed(() => {
  switch (props.book.status) {
    case 'ready': return 'bg-emerald-100 text-emerald-700'
    case 'processing': return 'bg-amber-100 text-amber-700'
    case 'pending': return 'bg-blue-100 text-blue-700'
    case 'error': return 'bg-red-100 text-red-700'
    default: return 'bg-slate-100 text-slate-600'
  }
})

function formatDate(timestamp) {
  if (!timestamp) return ''
  const date = timestamp.toDate ? timestamp.toDate() : new Date(timestamp)
  return date.toLocaleDateString('zh-TW', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}
</script>
