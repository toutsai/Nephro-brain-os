<template>
  <div
    class="group rounded-xl border p-4 transition-all cursor-pointer hover:shadow-md"
    :class="selected ? 'ring-2 ring-purple-400 shadow-md bg-purple-50/30 border-purple-200' : 'bg-white border-slate-200'"
    @click="$emit('select', note)"
  >
    <!-- Title -->
    <h3 class="text-sm font-bold text-slate-800 mb-1.5 line-clamp-1">
      {{ note.title || '未命名筆記' }}
    </h3>

    <!-- Content preview -->
    <p class="text-xs text-slate-500 line-clamp-2 leading-relaxed mb-2">
      {{ contentPreview }}
    </p>

    <!-- Tags -->
    <div v-if="note.tags?.length" class="flex flex-wrap gap-1 mb-2">
      <span
        v-for="tag in note.tags"
        :key="tag"
        class="text-[10px] font-medium px-2 py-0.5 rounded-full bg-purple-100 text-purple-700"
      >
        #{{ tag }}
      </span>
    </div>

    <!-- Footer -->
    <div class="flex items-center justify-between text-[10px] text-slate-400">
      <div class="flex items-center gap-2">
        <span v-if="note.links?.length">
          🔗 {{ note.links.length }} 連結
        </span>
        <span v-if="note.sources?.length">
          📎 {{ note.sources.length }} 來源
        </span>
      </div>
      <span>{{ formatDate(note.updated_at) }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  note: { type: Object, required: true },
  selected: { type: Boolean, default: false },
})

defineEmits(['select'])

const contentPreview = computed(() => {
  const text = props.note.content || ''
  // 去掉 markdown 符號
  return text
    .replace(/[#*_`~>\-\[\]()]/g, '')
    .replace(/\n+/g, ' ')
    .trim()
    .slice(0, 120) || '空白筆記'
})

function formatDate(timestamp) {
  if (!timestamp) return ''
  const date = timestamp.toDate ? timestamp.toDate() : new Date(timestamp)
  const now = new Date()
  const diff = now - date
  if (diff < 60000) return '剛剛'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分鐘前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小時前`
  return date.toLocaleDateString('zh-TW', { month: 'short', day: 'numeric' })
}
</script>
