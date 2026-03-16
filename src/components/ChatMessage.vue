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
            v-html="renderMarkdown(msg.content)"
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

// === 簡易 Markdown → HTML 轉換 ===
function renderMarkdown(text) {
  if (!text) return ''

  let html = escapeHtml(text)

  // Code blocks (```...```)
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
    return `<pre class="code-block"><code>${code.trim()}</code></pre>`
  })

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')

  // Headers
  html = html.replace(/^#### (.+)$/gm, '<h4 class="md-h4">$1</h4>')
  html = html.replace(/^### (.+)$/gm, '<h3 class="md-h3">$1</h3>')
  html = html.replace(/^## (.+)$/gm, '<h2 class="md-h2">$1</h2>')
  html = html.replace(/^# (.+)$/gm, '<h1 class="md-h1">$1</h1>')

  // Bold + italic
  html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')

  // Links
  html = html.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g,
    '<a href="$2" target="_blank" rel="noreferrer" class="md-link">$1 ↗</a>'
  )

  // Standalone URLs
  html = html.replace(
    /(?<!["\(href=])(https?:\/\/[^\s<]+)/g,
    '<a href="$1" target="_blank" rel="noreferrer" class="md-link">$1</a>'
  )

  // Unordered list items
  html = html.replace(/^[\-\*] (.+)$/gm, '<li class="md-li">$1</li>')
  // Wrap consecutive <li> in <ul>
  html = html.replace(
    /(<li class="md-li">[\s\S]*?<\/li>)(\n(?!<li)|\s*$)/g,
    '<ul class="md-ul">$1</ul>'
  )

  // Numbered list items
  html = html.replace(/^\d+\. (.+)$/gm, '<li class="md-oli">$1</li>')
  html = html.replace(
    /(<li class="md-oli">[\s\S]*?<\/li>)(\n(?!<li)|\s*$)/g,
    '<ol class="md-ol">$1</ol>'
  )

  // Blockquote
  html = html.replace(/^&gt; (.+)$/gm, '<blockquote class="md-quote">$1</blockquote>')

  // Horizontal rule
  html = html.replace(/^---$/gm, '<hr class="md-hr" />')

  // Paragraphs (double newline)
  html = html.replace(/\n\n/g, '</p><p class="md-p">')
  // Single newlines within paragraphs
  html = html.replace(/\n/g, '<br>')

  // Wrap in paragraph
  html = `<p class="md-p">${html}</p>`
  // Clean up empty paragraphs
  html = html.replace(/<p class="md-p">\s*<\/p>/g, '')

  return html
}

function escapeHtml(text) {
  const div = { '&': '&amp;', '<': '&lt;', '>': '&gt;' }
  return text.replace(/[&<>]/g, (c) => div[c])
}
</script>

<style scoped>
/* Chat-specific markdown styles */
.prose-chat :deep(.md-h1) {
  @apply text-base font-bold text-slate-900 mt-3 mb-1;
}
.prose-chat :deep(.md-h2) {
  @apply text-sm font-bold text-slate-800 mt-3 mb-1;
}
.prose-chat :deep(.md-h3) {
  @apply text-sm font-semibold text-slate-700 mt-2 mb-1;
}
.prose-chat :deep(.md-h4) {
  @apply text-xs font-semibold text-slate-600 mt-2 mb-1;
}
.prose-chat :deep(.md-p) {
  @apply mb-2 last:mb-0;
}
.prose-chat :deep(.md-link) {
  @apply text-blue-600 underline underline-offset-2 hover:text-blue-800;
}
.prose-chat :deep(.md-ul),
.prose-chat :deep(.md-ol) {
  @apply pl-4 my-1.5 space-y-0.5;
}
.prose-chat :deep(.md-li) {
  @apply list-disc;
}
.prose-chat :deep(.md-oli) {
  @apply list-decimal;
}
.prose-chat :deep(.md-quote) {
  @apply border-l-2 border-teal-400 pl-3 text-slate-600 italic my-2;
}
.prose-chat :deep(.md-hr) {
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
</style>
