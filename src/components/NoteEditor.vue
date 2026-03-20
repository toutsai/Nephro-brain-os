<template>
  <div v-if="!note" class="flex items-center justify-center h-full text-slate-400">
    <div class="text-center">
      <div class="text-4xl mb-3">📝</div>
      <p class="text-sm">選擇一則筆記或建立新的</p>
    </div>
  </div>

  <div v-else class="flex flex-col h-full">
    <!-- Header -->
    <div class="shrink-0 px-4 pt-4 pb-2">
      <!-- Title -->
      <input
        :value="note.title"
        @input="debouncedUpdate({ title: $event.target.value })"
        class="w-full text-lg font-bold text-slate-800 border-none outline-none bg-transparent placeholder:text-slate-300"
        placeholder="筆記標題..."
      />

      <!-- Tags -->
      <div class="flex flex-wrap items-center gap-1.5 mt-2">
        <span
          v-for="tag in (note.tags || [])"
          :key="tag"
          class="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-purple-100 text-purple-700"
        >
          #{{ tag }}
          <button
            class="text-purple-400 hover:text-purple-700 leading-none"
            @click="removeTag(tag)"
          >×</button>
        </span>
        <div class="inline-flex items-center">
          <input
            v-model="newTag"
            @keydown.enter.prevent="addTag"
            @keydown.tab.prevent="addTag"
            class="text-[11px] w-20 border-none outline-none bg-transparent text-slate-500 placeholder:text-slate-300"
            placeholder="+ 標籤"
          />
        </div>
      </div>

      <!-- Sources -->
      <div v-if="note.sources?.length" class="flex flex-wrap gap-1.5 mt-2">
        <span
          v-for="(src, i) in note.sources"
          :key="i"
          class="text-[10px] px-2 py-0.5 rounded-full"
          :class="sourceClass(src.type)"
        >
          {{ sourceLabel(src) }}
        </span>
      </div>

      <!-- Toolbar -->
      <div class="flex items-center gap-2 mt-3 pt-2 border-t border-slate-100">
        <button
          class="text-[11px] px-2 py-1 rounded transition-colors"
          :class="editMode === 'write' ? 'bg-slate-200 text-slate-700' : 'text-slate-400 hover:bg-slate-100'"
          @click="editMode = 'write'"
        >
          編輯
        </button>
        <button
          class="text-[11px] px-2 py-1 rounded transition-colors"
          :class="editMode === 'preview' ? 'bg-slate-200 text-slate-700' : 'text-slate-400 hover:bg-slate-100'"
          @click="editMode = 'preview'"
        >
          預覽
        </button>
        <button
          class="text-[11px] px-2 py-1 rounded transition-colors"
          :class="editMode === 'links' ? 'bg-purple-100 text-purple-700' : 'text-slate-400 hover:bg-slate-100'"
          @click="editMode = 'links'"
        >
          🔗 連結 ({{ (note.links || []).length }})
        </button>
        <div class="flex-1" />
        <span v-if="saving" class="text-[10px] text-slate-300">儲存中...</span>
        <span v-else class="text-[10px] text-emerald-400">已儲存</span>
        <button
          class="text-[11px] text-slate-300 hover:text-red-500 transition-colors"
          @click="$emit('delete', note.id)"
        >
          刪除
        </button>
      </div>
    </div>

    <!-- Content area -->
    <div class="flex-1 overflow-y-auto px-4 pb-4">
      <!-- Write mode -->
      <textarea
        v-if="editMode === 'write'"
        :value="note.content"
        @input="debouncedUpdate({ content: $event.target.value })"
        class="w-full h-full resize-none border-none outline-none text-sm text-slate-700 leading-relaxed bg-transparent placeholder:text-slate-300 font-mono"
        placeholder="用 Markdown 寫筆記...

# 標題
## 子標題
**粗體** *斜體*
- 列表項目
> 引用

支援所有 Markdown 語法"
      />

      <!-- Preview mode -->
      <div
        v-else-if="editMode === 'preview'"
        class="prose-note text-sm text-slate-700 leading-relaxed"
        v-html="renderedContent"
      />

      <!-- Links mode -->
      <div v-else-if="editMode === 'links'" class="space-y-4">
        <!-- Linked notes -->
        <div>
          <h4 class="text-xs font-bold text-slate-600 mb-2">已連結的筆記</h4>
          <div v-if="!linkedNotes.length" class="text-xs text-slate-400">
            尚無連結。在下方搜尋並連結其他筆記。
          </div>
          <div v-else class="space-y-1.5">
            <div
              v-for="ln in linkedNotes"
              :key="ln.id"
              class="flex items-center justify-between px-3 py-2 bg-purple-50 rounded-lg"
            >
              <span
                class="text-xs text-purple-700 cursor-pointer hover:underline"
                @click="$emit('select', ln)"
              >
                {{ ln.title || '未命名' }}
              </span>
              <button
                class="text-[10px] text-purple-300 hover:text-red-500"
                @click="$emit('removeLink', note.id, ln.id)"
              >
                移除
              </button>
            </div>
          </div>
        </div>

        <!-- Search to add link -->
        <div>
          <h4 class="text-xs font-bold text-slate-600 mb-2">連結其他筆記</h4>
          <input
            v-model="linkSearch"
            class="w-full text-xs border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-purple-400"
            placeholder="搜尋筆記標題..."
          />
          <div v-if="linkSearch.trim()" class="mt-2 space-y-1">
            <div
              v-for="candidate in linkCandidates"
              :key="candidate.id"
              class="flex items-center justify-between px-3 py-2 bg-slate-50 hover:bg-purple-50 rounded-lg cursor-pointer transition-colors"
              @click="$emit('addLink', note.id, candidate.id); linkSearch = ''"
            >
              <span class="text-xs text-slate-600">{{ candidate.title }}</span>
              <span class="text-[10px] text-purple-500">+ 連結</span>
            </div>
            <div v-if="!linkCandidates.length" class="text-xs text-slate-400 py-2">
              找不到符合的筆記
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { renderMd } from '../utils/renderMarkdown.js'

const props = defineProps({
  note: { type: Object, default: null },
  allNotes: { type: Array, default: () => [] },
  linkedNotes: { type: Array, default: () => [] },
})

const emit = defineEmits(['update', 'delete', 'select', 'addLink', 'removeLink'])

const editMode = ref('write') // 'write' | 'preview' | 'links'
const newTag = ref('')
const linkSearch = ref('')
const saving = ref(false)

// 切換筆記時重設
watch(() => props.note?.id, () => {
  editMode.value = 'write'
  newTag.value = ''
  linkSearch.value = ''
})

// === Tag 管理 ===
function addTag() {
  const tag = newTag.value.trim().replace(/^#/, '')
  if (!tag || !props.note) return
  const currentTags = props.note.tags || []
  if (!currentTags.includes(tag)) {
    emit('update', props.note.id, { tags: [...currentTags, tag] })
  }
  newTag.value = ''
}

function removeTag(tag) {
  if (!props.note) return
  emit('update', props.note.id, {
    tags: (props.note.tags || []).filter((t) => t !== tag),
  })
}

// === Debounced update ===
let updateTimer = null
function debouncedUpdate(updates) {
  saving.value = true
  clearTimeout(updateTimer)
  updateTimer = setTimeout(() => {
    emit('update', props.note.id, updates)
    saving.value = false
  }, 600)
}

// === Link candidates ===
const linkCandidates = computed(() => {
  if (!linkSearch.value.trim() || !props.note) return []
  const q = linkSearch.value.toLowerCase()
  const linkedIds = new Set(props.note.links || [])
  return props.allNotes.filter(
    (n) =>
      n.id !== props.note.id &&
      !linkedIds.has(n.id) &&
      (n.title || '').toLowerCase().includes(q)
  )
})

// === Source helpers ===
function sourceClass(type) {
  switch (type) {
    case 'insight': return 'bg-blue-100 text-blue-700'
    case 'consult': return 'bg-teal-100 text-teal-700'
    default: return 'bg-slate-100 text-slate-600'
  }
}

function sourceLabel(src) {
  switch (src.type) {
    case 'insight': return `📄 ${src.title || '論文'}`
    case 'consult': return `💬 ${src.snippet?.slice(0, 20) || '問答'}...`
    default: return '📎 來源'
  }
}

// === Markdown 渲染（使用共用 renderMd） ===
const renderedContent = computed(() => {
  const text = props.note?.content
  if (!text) return '<p class="text-slate-400">空白筆記</p>'
  return renderMd(text)
})
</script>

<style scoped>
.prose-note :deep(h1) { font-size: 18px; font-weight: 600; margin: 16px 0 8px; color: var(--color-text-primary); }
.prose-note :deep(h2) { font-size: 16px; font-weight: 600; margin: 14px 0 6px; color: var(--color-text-primary); }
.prose-note :deep(h3) { font-size: 14px; font-weight: 600; margin: 12px 0 4px; color: var(--color-text-primary); }
.prose-note :deep(p) { margin-bottom: 8px; }
.prose-note :deep(strong) { font-weight: 600; }
.prose-note :deep(ul) { padding-left: 16px; margin: 8px 0; }
.prose-note :deep(li) { list-style: disc; margin: 2px 0; }
.prose-note :deep(li.ol) { list-style: decimal; }
.prose-note :deep(blockquote) { border-left: 2px solid #c4b5fd; padding-left: 12px; color: #6b7280; font-style: italic; margin: 8px 0; }
.prose-note :deep(hr) { border-color: #e5e7eb; margin: 12px 0; }
.prose-note :deep(a) { color: #7c3aed; text-decoration: underline; }
.prose-note :deep(.code-block) { background: #1e293b; color: #6ee7b7; font-size: 12px; padding: 12px; border-radius: 8px; margin: 8px 0; overflow-x: auto; }
.prose-note :deep(.inline-code) { background: #f1f5f9; color: #dc2626; font-size: 12px; padding: 1px 6px; border-radius: 4px; font-family: monospace; }
.prose-note :deep(.table-wrap) { overflow-x: auto; margin: 8px 0; }
.prose-note :deep(table) { width: 100%; border-collapse: collapse; font-size: 12px; }
.prose-note :deep(th) { background: #f1f5f9; font-weight: 600; color: #1e293b; padding: 6px 10px; border: 1px solid #e2e8f0; white-space: nowrap; }
.prose-note :deep(td) { padding: 6px 10px; border: 1px solid #e2e8f0; color: #334155; }
</style>
