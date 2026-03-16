<template>
  <div class="h-screen flex flex-col bg-slate-50">
    <!-- Header -->
    <header class="bg-white border-b border-slate-200 sticky top-0 z-20 shrink-0">
      <div class="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <router-link to="/" class="text-lg font-bold text-slate-800 hover:text-blue-600 transition-colors">
            NB — OS
          </router-link>
          <span class="text-slate-300">|</span>
          <div>
            <h1 class="text-sm font-bold text-slate-800">NB Notes</h1>
            <p class="text-[10px] text-slate-400">個人知識整理區</p>
          </div>
        </div>

        <div class="flex items-center gap-3">
          <div class="text-xs text-slate-400">
            {{ notes.length }} 則筆記 · {{ allTags.length }} 個標籤
          </div>
          <router-link
            to="/insight"
            class="text-xs px-3 py-1.5 bg-slate-100 hover:bg-blue-50 text-slate-500 hover:text-blue-600 rounded-lg transition-colors"
          >
            🔍 Insight
          </router-link>
          <router-link
            to="/consult"
            class="text-xs px-3 py-1.5 bg-slate-100 hover:bg-teal-50 text-slate-500 hover:text-teal-600 rounded-lg transition-colors"
          >
            💬 Consult
          </router-link>
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

    <!-- Main layout -->
    <div v-else class="flex-1 overflow-hidden flex">

      <!-- Left panel: Tags + Note list -->
      <aside class="w-80 border-r border-slate-200 bg-white flex flex-col shrink-0">

        <!-- New note + search -->
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
      <main class="flex-1 min-w-0">
        <!-- Desktop -->
        <div class="hidden lg:flex flex-col h-full">
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
        </div>

        <!-- Mobile placeholder -->
        <div
          v-if="!selectedNote"
          class="lg:hidden flex items-center justify-center h-full text-slate-400"
        >
          <div class="text-center p-8">
            <div class="text-4xl mb-3">📝</div>
            <p class="text-sm">從左側選擇筆記</p>
          </div>
        </div>

        <!-- Mobile editor overlay -->
        <Teleport to="body">
          <div
            v-if="selectedNote && isMobile"
            class="fixed inset-0 bg-black/50 z-30 lg:hidden"
            @click="selectedId = null"
          >
            <div
              class="absolute inset-x-0 bottom-0 max-h-[90vh] overflow-hidden bg-white rounded-t-2xl flex flex-col"
              @click.stop
            >
              <div class="sticky top-0 bg-white p-3 border-b border-slate-100 flex justify-between items-center shrink-0">
                <span class="text-sm font-medium text-slate-600">編輯筆記</span>
                <button class="text-slate-400 hover:text-slate-600 text-lg" @click="selectedId = null">✕</button>
              </div>
              <div class="flex-1 overflow-y-auto">
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
              </div>
            </div>
          </div>
        </Teleport>
      </main>
    </div>
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
</script>
