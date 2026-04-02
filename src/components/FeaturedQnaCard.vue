<template>
  <div class="bg-white rounded-xl border border-slate-200 overflow-hidden transition-shadow hover:shadow-sm">
    <!-- Header -->
    <div
      class="px-4 py-3 cursor-pointer flex items-start gap-3"
      @click="expanded = !expanded"
    >
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2 mb-1">
          <span
            v-if="qna.category"
            class="shrink-0 text-[10px] px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 font-medium"
          >
            {{ qna.category }}
          </span>
          <span
            v-for="tag in (qna.tags || []).slice(0, 3)"
            :key="tag"
            class="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-500"
          >
            {{ tag }}
          </span>
        </div>
        <h4 class="text-sm font-semibold text-slate-800 leading-snug">
          {{ qna.question }}
        </h4>
        <div class="text-[10px] text-slate-400 mt-1">
          {{ formatDate(qna.created_at) }}
        </div>
      </div>
      <span class="shrink-0 text-slate-400 text-xs mt-1">{{ expanded ? '▲' : '▼' }}</span>
    </div>

    <!-- Answer (expandable) -->
    <div v-if="expanded" class="px-4 pb-4 border-t border-slate-100 pt-3">
      <div
        class="prose-chat text-sm text-slate-700 leading-relaxed"
        v-html="renderedAnswer"
      />
      <div class="flex items-center gap-2 mt-3 pt-2 border-t border-slate-50">
        <button
          class="text-xs text-blue-500 hover:text-blue-700 transition-colors"
          @click.stop="$emit('askInConsult', qna.question)"
        >
          🔍 在 Consult 提問
        </button>
        <button
          v-if="isOwner"
          class="text-xs text-red-400 hover:text-red-600 transition-colors"
          @click.stop="$emit('delete', qna.id)"
        >
          刪除
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { renderMd } from '../utils/renderMarkdown.js'

const props = defineProps({
  qna: { type: Object, required: true },
  isOwner: { type: Boolean, default: false },
})

defineEmits(['askInConsult', 'delete'])

const expanded = ref(false)

const renderedAnswer = computed(() => {
  return renderMd(props.qna?.answer || '')
})

function formatDate(ts) {
  if (!ts) return ''
  const d = ts.toDate ? ts.toDate() : new Date(ts)
  return d.toLocaleDateString('zh-TW', { month: 'short', day: 'numeric' })
}
</script>
