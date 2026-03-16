<template>
  <div class="h-screen flex flex-col bg-slate-50">
    <!-- Header -->
    <header class="bg-white border-b border-slate-200 sticky top-0 z-20 shrink-0">
      <div class="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <router-link
            to="/"
            class="text-lg font-bold text-slate-800 hover:text-blue-600 transition-colors"
          >
            NB — OS
          </router-link>
          <span class="text-slate-300">|</span>
          <div>
            <h1 class="text-sm font-bold text-slate-800">NB Consult</h1>
            <p class="text-[10px] text-slate-400">腎臟知識問答引擎</p>
          </div>
        </div>

        <div class="flex items-center gap-3">
          <!-- API 狀態 -->
          <div
            class="flex items-center gap-1.5 text-[10px] px-2 py-1 rounded-full"
            :class="
              apiStatus === 'online'
                ? 'bg-emerald-50 text-emerald-700'
                : apiStatus === 'offline'
                ? 'bg-red-50 text-red-600'
                : 'bg-slate-100 text-slate-400'
            "
          >
            <span
              class="w-1.5 h-1.5 rounded-full"
              :class="
                apiStatus === 'online'
                  ? 'bg-emerald-500'
                  : apiStatus === 'offline'
                  ? 'bg-red-400'
                  : 'bg-slate-300'
              "
            />
            {{ apiStatus === 'online' ? 'API 在線' : apiStatus === 'offline' ? 'API 離線' : '檢查中...' }}
          </div>

          <!-- Tab 切換 -->
          <nav class="flex bg-slate-100 rounded-lg p-0.5">
            <button
              v-for="tab in mainTabs"
              :key="tab.key"
              class="px-3 py-1.5 text-xs font-medium rounded-md transition-colors"
              :class="
                activeTab === tab.key
                  ? 'bg-white text-slate-800 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              "
              @click="activeTab = tab.key"
            >
              {{ tab.icon }} {{ tab.label }}
            </button>
          </nav>
        </div>
      </div>
    </header>

    <!-- ===================== Chat View ===================== -->
    <template v-if="activeTab === 'chat'">
      <div class="flex-1 overflow-hidden flex">

        <!-- Sidebar: Chat list (desktop) -->
        <aside class="hidden lg:flex flex-col w-72 border-r border-slate-200 bg-white shrink-0">
          <div class="p-3 border-b border-slate-100">
            <button
              class="w-full px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-1.5"
              @click="startNewChat"
            >
              <span class="text-lg leading-none">+</span> 新對話
            </button>
          </div>

          <div class="flex-1 overflow-y-auto">
            <div
              v-if="chatsLoading"
              class="text-center py-8 text-slate-400 text-xs"
            >
              載入對話列表...
            </div>
            <div
              v-for="chat in chats"
              :key="chat.id"
              class="group px-3 py-3 border-b border-slate-50 cursor-pointer hover:bg-slate-50 transition-colors"
              :class="currentChatId === chat.id ? 'bg-blue-50 border-l-2 border-l-blue-500' : ''"
              @click="selectChat(chat.id)"
            >
              <div class="text-sm font-medium text-slate-700 truncate">
                {{ chat.title || '新對話' }}
              </div>
              <div class="text-[10px] text-slate-400 mt-0.5 truncate">
                {{ chat.last_message || '尚無訊息' }}
              </div>
              <div class="flex items-center justify-between mt-1">
                <span class="text-[10px] text-slate-300">
                  {{ formatDate(chat.updated_at) }}
                </span>
                <button
                  class="text-[10px] text-slate-300 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                  @click.stop="handleDeleteChat(chat.id)"
                >
                  刪除
                </button>
              </div>
            </div>
          </div>

          <!-- Stats -->
          <div
            v-if="knowledgeStats"
            class="p-3 border-t border-slate-100 bg-slate-50/50 text-[10px] text-slate-400 space-y-0.5"
          >
            <div>📚 教科書：{{ knowledgeStats.ready_books || 0 }} 本已就緒</div>
            <div>🧩 知識片段：{{ knowledgeStats.memory_chunks_ids || 0 }} 個</div>
          </div>
        </aside>

        <!-- Chat main area -->
        <div class="flex-1 flex flex-col min-w-0">

          <!-- Mobile: chat selector -->
          <div class="lg:hidden flex items-center gap-2 px-4 py-2 bg-white border-b border-slate-100">
            <button
              class="text-xs px-2 py-1 bg-blue-600 text-white rounded-md"
              @click="startNewChat"
            >
              + 新對話
            </button>
            <select
              class="flex-1 text-xs border border-slate-200 rounded-md px-2 py-1.5 bg-white"
              :value="currentChatId || ''"
              @change="selectChat($event.target.value)"
            >
              <option value="" disabled>選擇對話...</option>
              <option
                v-for="c in chats"
                :key="c.id"
                :value="c.id"
              >
                {{ c.title || '新對話' }}
              </option>
            </select>
          </div>

          <!-- Messages -->
          <div
            ref="messagesContainer"
            class="flex-1 overflow-y-auto px-4 py-4 space-y-4"
          >
            <!-- Empty state -->
            <div
              v-if="!messages.length && !answering"
              class="flex flex-col items-center justify-center h-full text-center"
            >
              <div class="text-5xl mb-4">💬</div>
              <h2 class="text-lg font-bold text-slate-700 mb-1">NB Consult</h2>
              <p class="text-sm text-slate-400 mb-6 max-w-md">
                基於你的教科書知識庫、PubMed 和即時網路搜尋，<br>
                為腎臟科臨床問題提供結構化的實證回答。
              </p>
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-lg w-full">
                <button
                  v-for="q in sampleQuestions"
                  :key="q"
                  class="text-left text-xs px-3 py-2.5 bg-white border border-slate-200 rounded-lg hover:border-blue-300 hover:bg-blue-50/50 transition-colors text-slate-600"
                  @click="inputText = q"
                >
                  {{ q }}
                </button>
              </div>
            </div>

            <!-- Message list -->
            <ChatMessage
              v-for="msg in messages"
              :key="msg.id"
              :msg="msg"
            />

            <!-- Typing indicator -->
            <div
              v-if="answering"
              class="flex gap-3"
            >
              <div class="w-8 h-8 rounded-full bg-gradient-to-br from-teal-500 to-emerald-600 flex items-center justify-center text-white text-sm font-bold shrink-0">
                NB
              </div>
              <div class="bg-white border border-slate-200 rounded-2xl rounded-bl-md px-4 py-3 shadow-sm">
                <div class="flex items-center gap-1">
                  <span class="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style="animation-delay: 0ms" />
                  <span class="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style="animation-delay: 150ms" />
                  <span class="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style="animation-delay: 300ms" />
                </div>
                <p class="text-[10px] text-slate-400 mt-1">搜尋教科書、PubMed 和網路中...</p>
              </div>
            </div>
          </div>

          <!-- Error banner -->
          <div
            v-if="error"
            class="mx-4 mb-2 px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-xs text-red-600 flex items-center justify-between"
          >
            <span>⚠️ {{ error }}</span>
            <button class="text-red-400 hover:text-red-600" @click="error = null">✕</button>
          </div>

          <!-- Input bar -->
          <div class="px-4 py-3 bg-white border-t border-slate-200 shrink-0">
            <div class="max-w-3xl mx-auto flex items-end gap-2">
              <div class="flex-1 relative">
                <textarea
                  ref="inputEl"
                  v-model="inputText"
                  :disabled="answering"
                  rows="1"
                  placeholder="詢問腎臟科相關問題... (Enter 發送，Shift+Enter 換行)"
                  class="w-full resize-none border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50 disabled:bg-slate-50"
                  :style="{ height: textareaHeight }"
                  @input="autoResize"
                  @keydown.enter.exact.prevent="handleSend"
                />
              </div>
              <button
                :disabled="!inputText.trim() || answering"
                class="shrink-0 w-10 h-10 rounded-xl flex items-center justify-center transition-colors"
                :class="
                  inputText.trim() && !answering
                    ? 'bg-blue-600 hover:bg-blue-500 text-white'
                    : 'bg-slate-100 text-slate-300 cursor-not-allowed'
                "
                @click="handleSend"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19V5m0 0l-7 7m7-7l7 7" />
                </svg>
              </button>
            </div>
            <p class="text-center text-[10px] text-slate-300 mt-1.5">
              問答引擎結合教科書 FAISS 向量搜尋 + PubMed + Perplexity + Gemini
            </p>
          </div>
        </div>
      </div>
    </template>

    <!-- ===================== Library View ===================== -->
    <template v-if="activeTab === 'library'">
      <main class="flex-1 overflow-y-auto max-w-4xl mx-auto w-full px-4 py-6">

        <!-- Stats cards -->
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          <div class="bg-white rounded-xl border border-slate-200 p-4 text-center">
            <div class="text-2xl font-bold text-slate-800">{{ books.length }}</div>
            <div class="text-[10px] text-slate-400 mt-0.5">教科書總數</div>
          </div>
          <div class="bg-white rounded-xl border border-emerald-200 p-4 text-center">
            <div class="text-2xl font-bold text-emerald-600">{{ readyBooks.length }}</div>
            <div class="text-[10px] text-slate-400 mt-0.5">已就緒</div>
          </div>
          <div class="bg-white rounded-xl border border-amber-200 p-4 text-center">
            <div class="text-2xl font-bold text-amber-600">{{ pendingBooks.length }}</div>
            <div class="text-[10px] text-slate-400 mt-0.5">等待 / 處理中</div>
          </div>
          <div class="bg-white rounded-xl border border-slate-200 p-4 text-center">
            <div class="text-2xl font-bold text-slate-800">{{ totalChunks }}</div>
            <div class="text-[10px] text-slate-400 mt-0.5">知識片段</div>
          </div>
        </div>

        <!-- Upload hint -->
        <div class="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-6">
          <h3 class="text-sm font-bold text-blue-800 mb-1">📤 如何上傳教科書？</h3>
          <p class="text-xs text-blue-600 leading-relaxed">
            教科書上傳需要在本地執行
            <code class="bg-blue-100 px-1 py-0.5 rounded text-[11px]">python local_pdf_processor.py</code>。
            此工具會解析 PDF → 切片 → 向量化 → 上傳到 Firestore + Firebase Storage。
            Cloud Run 重啟後會自動載入新知識。
          </p>
        </div>

        <!-- Book list -->
        <div v-if="booksLoading" class="text-center py-12 text-slate-400 text-sm">
          載入教科書列表中...
        </div>

        <div v-else-if="!books.length" class="text-center py-16 text-slate-400">
          <div class="text-4xl mb-3">📚</div>
          <p class="text-sm">尚未上傳任何教科書</p>
          <p class="text-xs mt-1">使用 local_pdf_processor.py 開始上傳</p>
        </div>

        <div v-else class="space-y-3">
          <h3 class="text-sm font-bold text-slate-600">
            教科書列表 ({{ books.length }})
          </h3>
          <BookCard
            v-for="book in books"
            :key="book.id"
            :book="book"
          />
        </div>
      </main>
    </template>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useConsultChat } from '../composables/useConsultChat.js'
import { useBooks } from '../composables/useBooks.js'
import ChatMessage from '../components/ChatMessage.vue'
import BookCard from '../components/BookCard.vue'

// === Chat ===
const {
  chats,
  currentChatId,
  messages,
  answering,
  error,
  chatsLoading,
  apiStatus,
  knowledgeStats,
  subscribeChats,
  selectChat,
  createChat,
  deleteChat,
  sendQuestion,
  checkApiHealth,
  fetchStats,
  cleanup: cleanupChat,
} = useConsultChat()

// === Books ===
const {
  books,
  loading: booksLoading,
  readyBooks,
  pendingBooks,
  totalChunks,
  unsubscribe: unsubBooks,
} = useBooks()

// === UI State ===
const activeTab = ref('chat')
const inputText = ref('')
const textareaHeight = ref('40px')
const messagesContainer = ref(null)
const inputEl = ref(null)

const mainTabs = [
  { key: 'chat', label: '問答', icon: '💬' },
  { key: 'library', label: '教科書', icon: '📚' },
]

const sampleQuestions = [
  'SGLT2 inhibitor 在 CKD 的適應症？',
  'AKI 時 Citrate vs Heparin 的比較？',
  'CRRT 的 dose 建議？',
  '懶人包：Finerenone',
]

// === Actions ===
function startNewChat() {
  currentChatId.value = null
  messages.value = []
  inputText.value = ''
}

function handleDeleteChat(chatId) {
  if (confirm('確定要刪除這個對話？')) {
    deleteChat(chatId)
  }
}

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || answering.value) return
  inputText.value = ''
  textareaHeight.value = '40px'
  await sendQuestion(text)
}

function autoResize() {
  if (!inputEl.value) return
  inputEl.value.style.height = '40px'
  const sh = inputEl.value.scrollHeight
  textareaHeight.value = Math.min(sh, 120) + 'px'
}

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

// Auto-scroll on new messages
watch(
  () => messages.value.length,
  async () => {
    await nextTick()
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  }
)

// Lifecycle
onMounted(() => {
  subscribeChats()
  checkApiHealth()
  fetchStats()
})

onUnmounted(() => {
  cleanupChat()
  unsubBooks()
})
</script>
