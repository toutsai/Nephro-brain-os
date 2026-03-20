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
      class="min-w-0"
      :class="msg.role === 'user' ? 'max-w-[80%] text-right' : 'max-w-[90%]'"
    >
      <div
        class="inline-block text-left rounded-2xl text-sm leading-relaxed"
        :class="[bubbleClass, msg.role === 'user' ? 'px-4 py-3' : 'px-5 py-4']"
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
/* ── Chat markdown typography ── */

/* Base: comfortable line height & color */
.prose-chat {
  @apply text-[13.5px] leading-[1.75] text-slate-700;
}

/* ── Headings ── */
.prose-chat :deep(h1) {
  @apply text-base font-bold text-slate-900 mt-5 mb-2 pb-1.5 border-b border-slate-200;
}
.prose-chat :deep(h2) {
  @apply text-[15px] font-bold text-slate-800 mt-5 mb-2 pb-1 border-b border-slate-100;
}
.prose-chat :deep(h3) {
  @apply text-sm font-semibold text-slate-800 mt-4 mb-1.5;
}
.prose-chat :deep(h4) {
  @apply text-[13px] font-semibold text-slate-600 mt-3 mb-1;
}
/* Remove top margin for the very first heading */
.prose-chat :deep(:first-child) {
  margin-top: 0;
}

/* ── Paragraphs ── */
.prose-chat :deep(p) {
  @apply mb-3 last:mb-0;
}

/* ── Links ── */
.prose-chat :deep(a) {
  @apply text-blue-600 underline underline-offset-2 decoration-blue-300 hover:text-blue-800 hover:decoration-blue-500;
}

/* ── Lists ── */
.prose-chat :deep(ul),
.prose-chat :deep(ol) {
  @apply pl-5 my-2.5 space-y-1.5;
}
.prose-chat :deep(li) {
  @apply list-disc pl-1;
}
.prose-chat :deep(li.ol) {
  @apply list-decimal;
}
/* Nested list */
.prose-chat :deep(li > ul),
.prose-chat :deep(li > ol) {
  @apply mt-1 mb-0;
}

/* ── Blockquote ── */
.prose-chat :deep(blockquote) {
  @apply border-l-[3px] border-teal-400 pl-4 py-1 text-slate-600 italic my-3 bg-teal-50/40 rounded-r-lg;
}

/* ── Horizontal rule ── */
.prose-chat :deep(hr) {
  @apply border-slate-200 my-4;
}

/* ── Code ── */
.prose-chat :deep(.code-block) {
  @apply bg-slate-900 text-emerald-300 text-xs rounded-lg p-4 my-3 overflow-x-auto leading-relaxed;
}
.prose-chat :deep(.inline-code) {
  @apply bg-slate-100 text-red-600 text-xs px-1.5 py-0.5 rounded font-mono;
}

/* ── Inline formatting ── */
.prose-chat :deep(strong) {
  @apply font-bold text-slate-900;
}
.prose-chat :deep(em) {
  @apply italic text-slate-600;
}

/* ── Tables ── */
.prose-chat :deep(.table-wrap) { overflow-x: auto; margin: 12px 0; border-radius: 8px; }
.prose-chat :deep(table) { width: 100%; border-collapse: collapse; font-size: 12.5px; line-height: 1.5; }
.prose-chat :deep(th) { background: #f1f5f9; font-weight: 600; color: #1e293b; padding: 8px 12px; border: 1px solid #e2e8f0; white-space: nowrap; }
.prose-chat :deep(td) { padding: 8px 12px; border: 1px solid #e2e8f0; color: #334155; }
.prose-chat :deep(tr:nth-child(even) td) { background: #f8fafc; }
</style>
