<template>
  <div
    class="flex gap-3"
    :class="msg.role === 'user' ? 'flex-row-reverse' : ''"
  >
    <!-- Avatar -->
    <div
      class="shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold"
      :class="
        msg.role === 'user'
          ? 'bg-blue-600 text-white'
          : 'bg-gradient-to-br from-teal-500 to-emerald-600 text-white'
      "
    >
      {{ msg.role === 'user' ? 'H' : 'NB' }}
    </div>

    <!-- Bubble -->
    <div
      class="max-w-[80%] min-w-0"
      :class="msg.role === 'user' ? 'text-right' : ''"
    >
      <div
        class="inline-block text-left rounded-2xl px-4 py-3 text-sm leading-relaxed"
        :class="bubbleClass"
      >
        <!-- User message: plain text -->
        <template v-if="msg.role === 'user'">
          <p class="whitespace-pre-wrap">{{ msg.content }}</p>
        </template>

        <!-- Assistant message: rendered markdown -->
        <template v-else>
          <div
            class="prose-chat"
            v-html="renderMd(msg.content)"
          />
        </template>
      </div>

      <!-- Timestamp + actions -->
      <div class="flex items-center gap-2 text-[10px] text-slate-400 mt-1 px-1">
        <span>{{ formatTime(msg.created_at) }}</span>
        <button
          v-if="msg.role === 'assistant' && !msg.is_error"
          class="text-slate-300 hover:text-purple-500 transition-colors"
          @click="$emit('saveToNotes', msg.content)"
        >
          📝 收進 Notes
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { renderMd } from '../utils/renderMarkdown.js'

const props = defineProps({
  msg: { type: Object, required: true },
})

defineEmits(['saveToNotes'])

const bubbleClass = computed(() => {
  if (props.msg.role === 'user') {
    return 'bg-blue-600 text-white rounded-br-md'
  }
  if (props.msg.is_error) {
    return 'bg-red-50 text-red-800 border border-red-200 rounded-bl-md'
  }
  return 'bg-white text-slate-800 border border-slate-200 rounded-bl-md shadow-sm'
})

function formatTime(timestamp) {
  if (!timestamp) return ''
  const date = timestamp.toDate ? timestamp.toDate() : new Date(timestamp)
  return date.toLocaleString('zh-TW', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

</script>

<style scoped>
/* Chat-specific markdown styles */
.prose-chat :deep(h1) {
  @apply text-base font-bold text-slate-900 mt-3 mb-1;
}
.prose-chat :deep(h2) {
  @apply text-sm font-bold text-slate-800 mt-3 mb-1;
}
.prose-chat :deep(h3) {
  @apply text-sm font-semibold text-slate-700 mt-2 mb-1;
}
.prose-chat :deep(h4) {
  @apply text-xs font-semibold text-slate-600 mt-2 mb-1;
}
.prose-chat :deep(p) {
  @apply mb-2 last:mb-0;
}
.prose-chat :deep(a) {
  @apply text-blue-600 underline underline-offset-2 hover:text-blue-800;
}
.prose-chat :deep(ul),
.prose-chat :deep(ol) {
  @apply pl-4 my-1.5 space-y-0.5;
}
.prose-chat :deep(li) {
  @apply list-disc;
}
.prose-chat :deep(li.ol) {
  @apply list-decimal;
}
.prose-chat :deep(blockquote) {
  @apply border-l-2 border-teal-400 pl-3 text-slate-600 italic my-2;
}
.prose-chat :deep(hr) {
  @apply border-slate-200 my-3;
}
.prose-chat :deep(.code-block) {
  @apply bg-slate-900 text-emerald-300 text-xs rounded-lg p-3 my-2 overflow-x-auto;
}
.prose-chat :deep(.inline-code) {
  @apply bg-slate-100 text-red-600 text-xs px-1.5 py-0.5 rounded font-mono;
}
.prose-chat :deep(strong) {
  @apply font-bold text-slate-900;
}
.prose-chat :deep(em) {
  @apply italic;
}
.prose-chat :deep(.table-wrap) { overflow-x: auto; margin: 8px 0; }
.prose-chat :deep(table) { width: 100%; border-collapse: collapse; font-size: 12px; }
.prose-chat :deep(th) { background: #f1f5f9; font-weight: 600; color: #1e293b; padding: 6px 10px; border: 1px solid #e2e8f0; white-space: nowrap; }
.prose-chat :deep(td) { padding: 6px 10px; border: 1px solid #e2e8f0; color: #334155; }
</style>
