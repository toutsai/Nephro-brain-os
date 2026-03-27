<template>
  <div class="h-[calc(100dvh-44px)] flex flex-col bg-slate-50 overflow-hidden pb-14 sm:pb-0">
    <!-- Header -->
    <header class="bg-white border-b border-slate-200 shrink-0">
      <div class="px-4 py-2 flex items-center justify-between">
        <div class="flex items-center gap-2">
          <h1 class="text-sm font-bold text-slate-800">NB Notes</h1>
          <span class="text-[10px] text-slate-400">個人知識整理區</span>
        </div>
        <div class="text-xs text-slate-400">
          {{ notes.length }} 則筆記 · {{ allTags.length }} 個標籤
        </div>
      </div>
    </header>

    <!-- Loading -->
    <div v-if="loading" class="flex-1 flex items-center justify-center">
      <div class="text-center">
        <div class="w-8 h-8 border-2 border-purple-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p class="text-sm text-slate-500">載入筆記中...</p>
      </div>
    </div>

    <!-- ==================== Desktop: side-by-side layout ==================== -->
    <div v-else class="flex-1 overflow-hidden hidden lg:flex">
      <!-- Left panel: Tags + Note list -->
      <aside class="w-72 border-r border-slate-200 bg-white flex flex-col shrink-0">
        <div class="p-3 border-b border-slate-100 space-y-2">
          <button
            class="w-full px-3 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-1.5"
            @click="handleNewNote"
          >
            <span class="text-lg leading-none">+</span> 新筆記
          </button>
          <input
            v-model="searchQuery"
            class="w-full text-xs border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-purple-400"
            placeholder="搜尋筆記..."
          />
        </div>

        <!-- Tags bar -->
        <div v-if="allTags.length" class="px-3 py-2 border-b border-slate-100">
          <div class="flex flex-wrap gap-1">
            <button
              class="text-[10px] px-2 py-0.5 rounded-full transition-colors"
              :class="!activeTag ? 'bg-purple-600 text-white' : 'bg-slate-100 text-slate-500 hover:bg-purple-50'"
              @click="activeTag = null"
            >
              全部
            </button>
            <button
              v-for="{ tag, count } in allTags"
              :key="tag"
              class="text-[10px] px-2 py-0.5 rounded-full transition-colors"
              :class="activeTag === tag ? 'bg-purple-600 text-white' : 'bg-purple-50 text-purple-600 hover:bg-purple-100'"
              @click="activeTag = activeTag === tag ? null : tag"
            >
              #{{ tag }} <span class="opacity-60">{{ count }}</span>
            </button>
          </div>
        </div>

        <!-- Note list -->
        <div class="flex-1 overflow-y-auto p-3 space-y-2">
          <div v-if="!filteredNotes.length" class="text-center py-12 text-slate-400">
            <div class="text-3xl mb-2">📝</div>
            <p class="text-xs">
              {{ searchQuery || activeTag ? '找不到符合的筆記' : '還沒有筆記，點上方按鈕開始' }}
            </p>
          </div>
          <NoteCard
            v-for="n in filteredNotes"
            :key="n.id"
            :note="n"
            :selected="selectedId === n.id"
            @select="selectedId = $event.id"
          />
        </div>
      </aside>

      <!-- Right panel: Editor -->
      <main class="flex-1 min-w-0 flex flex-col h-full">
        <NoteEditor
          :note="selectedNote"
          :all-notes="notes"
          :linked-notes="currentLinkedNotes"
          @update="handleUpdate"
          @delete="handleDelete"
          @select="selectedId = $event.id"
          @add-link="addLink"
          @remove-link="removeLink"
        />
      </main>
    </div>

    <!-- ==================== Mobile: list / editor toggle ==================== -->
    <template v-if="!loading">

      <!-- Mobile: full-page editor (when a note is selected) -->
      <div v-if="isMobile && selectedId" class="flex-1 flex flex-col overflow-hidden lg:hidden">
        <!-- Editor top bar -->
        <div class="flex items-center gap-2 px-4 py-2 bg-white border-b border-slate-100 shrink-0">
          <button
            class="shrink-0 flex items-center gap-1 text-xs text-purple-600 font-medium"
            @click="selectedId = null"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
            </svg>
            筆記列表
          </button>
          <span class="flex-1 text-xs text-slate-400 truncate text-right">
            {{ selectedNote?.title || '' }}
          </span>
        </div>
        <!-- Full-page editor -->
        <div class="flex-1 overflow-y-auto">
          <NoteEditor
            :note="selectedNote"
            :all-notes="notes"
            :linked-notes="currentLinkedNotes"
            @update="handleUpdate"
            @delete="handleDeleteMobile"
            @select="selectedId = $event.id"
            @add-link="addLink"
            @remove-link="removeLink"
          />
        </div>
      </div>

      <!-- Mobile: note list (default view when no note selected) -->
      <div v-if="isMobile && !selectedId" class="flex-1 flex flex-col overflow-hidden lg:hidden">
        <!-- Search + new note bar -->
        <div class="flex items-center gap-2 px-4 py-2 bg-white border-b border-slate-100 shrink-0">
          <button
            class="shrink-0 text-xs px-3 py-1.5 bg-purple-600 text-white rounded-lg font-medium"
            @click="handleNewNote"
          >
            + 新筆記
          </button>
          <input
            v-model="searchQuery"
            class="flex-1 min-w-0 text-xs border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-purple-400"
            placeholder="搜尋筆記..."
          />
        </div>

        <!-- Tags -->
        <div v-if="allTags.length" class="px-4 py-2 bg-white border-b border-slate-100 shrink-0">
          <div class="flex flex-wrap gap-1.5">
            <button
              class="text-xs px-2.5 py-1 rounded-full transition-colors"
              :class="!activeTag ? 'bg-purple-600 text-white' : 'bg-slate-100 text-slate-500'"
              @click="activeTag = null"
            >
              全部
            </button>
            <button
              v-for="{ tag, count } in allTags"
              :key="tag"
              class="text-xs px-2.5 py-1 rounded-full transition-colors"
              :class="activeTag === tag ? 'bg-purple-600 text-white' : 'bg-purple-50 text-purple-600'"
              @click="activeTag = activeTag === tag ? null : tag"
            >
              #{{ tag }} <span class="opacity-60">{{ count }}</span>
            </button>
          </div>
        </div>

        <!-- Note cards -->
        <div class="flex-1 overflow-y-auto p-4 space-y-3">
          <div v-if="!filteredNotes.length" class="text-center py-16 text-slate-400">
            <div class="text-4xl mb-3">📝</div>
            <p class="text-sm">
              {{ searchQuery || activeTag ? '找不到符合的筆記' : '還沒有筆記' }}
            </p>
            <button
              v-if="!searchQuery && !activeTag"
              class="mt-3 text-xs text-purple-600 font-medium"
              @click="handleNewNote"
            >
              建立第一則筆記
            </button>
          </div>
          <NoteCard
            v-for="n in filteredNotes"
            :key="n.id"
            :note="n"
            :selected="false"
            @select="selectedId = $event.id"
          />
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useNotes } from '../composables/useNotes.js'
import NoteCard from '../components/NoteCard.vue'
import NoteEditor from '../components/NoteEditor.vue'

const {
  notes,
  loading,
  searchQuery,
  activeTag,
  allTags,
  filteredNotes,
  createNote,
  updateNote,
  deleteNote,
  addLink,
  removeLink,
  getLinkedNotes,
  unsubscribe,
} = useNotes()

// 用 ID 追蹤，computed 自動同步 Firestore 最新資料
const selectedId = ref(null)

const selectedNote = computed(() => {
  if (!selectedId.value) return null
  return notes.value.find((n) => n.id === selectedId.value) || null
})

const currentLinkedNotes = computed(() => {
  if (!selectedId.value) return []
  return getLinkedNotes(selectedId.value)
})

// Mobile
const isMobile = ref(false)
function checkMobile() { isMobile.value = window.innerWidth < 1024 }
onMounted(() => { checkMobile(); window.addEventListener('resize', checkMobile) })
onUnmounted(() => { window.removeEventListener('resize', checkMobile); unsubscribe() })

// Actions
async function handleNewNote() {
  const id = await createNote({ title: '新筆記' })
  selectedId.value = id
}

function handleUpdate(noteId, updates) {
  updateNote(noteId, updates)
}

function handleDelete(noteId) {
  if (!confirm('確定要刪除這則筆記？')) return
  deleteNote(noteId)
  if (selectedId.value === noteId) selectedId.value = null
}

function handleDeleteMobile(noteId) {
  if (!confirm('確定要刪除這則筆記？')) return
  deleteNote(noteId)
  if (selectedId.value === noteId) selectedId.value = null
}
</script>
