<template>
  <div
    class="rounded-xl border p-3 flex flex-col items-center text-center transition-all hover:shadow-md cursor-default"
    :class="statusClass"
  >
    <!-- Book spine icon -->
    <div
      class="w-12 h-16 rounded-md flex items-center justify-center text-xl mb-2 shadow-sm"
      :class="iconClass"
    >
      {{ statusIcon }}
    </div>

    <!-- Title -->
    <h4 class="text-[11px] font-bold text-slate-800 leading-tight line-clamp-2 w-full min-h-[2.5em]">
      {{ book.title || book.filename || '未命名' }}
    </h4>

    <!-- Type badge -->
    <span
      v-if="book.type"
      class="text-[9px] px-1.5 py-0.5 rounded-full mt-1"
      :class="book.type === 'guideline' ? 'bg-violet-100 text-violet-600' : 'bg-slate-100 text-slate-500'"
    >
      {{ book.type === 'guideline' ? '指引' : '教科書' }}
    </span>

    <!-- Status -->
    <span
      class="text-[9px] font-bold px-2 py-0.5 rounded-full mt-1.5"
      :class="badgeClass"
    >
      {{ statusLabel }}
    </span>

    <!-- Chunks count -->
    <span v-if="book.chunks_count" class="text-[9px] text-slate-400 mt-1">
      {{ book.chunks_count }} 片段
    </span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  book: { type: Object, required: true },
})

const statusIcon = computed(() => {
  if (props.book.type === 'guideline') {
    switch (props.book.status) {
      case 'ready': return '📋'
      case 'processing': return '⏳'
      case 'pending': return '📤'
      case 'error': return '❌'
      default: return '📋'
    }
  }
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
    case 'error': return '失敗'
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
</script>
