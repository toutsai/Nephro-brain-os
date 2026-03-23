<template>
  <div class="h-screen flex flex-col bg-slate-50 pb-14 sm:pb-0">
    <!-- Header -->
    <header class="bg-white border-b border-slate-200 shrink-0">
      <div class="max-w-7xl mx-auto px-4 py-2 flex items-center justify-between">
        <div class="flex items-center gap-2">
          <h1 class="text-sm font-bold text-slate-800">NB Consult</h1>
          <span class="text-[10px] text-slate-400">腎臟知識問答引擎</span>
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
            class="flex-1 overflow-y-auto overflow-x-hidden px-4 py-4 space-y-4"
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
              @save-to-notes="saveFullReplyToNotes"
              @send-to-teach="sendToTeach"
            />

            <!-- Selection toolbar for text selection -->
            <SelectionToolbar
              source-type="consult"
              :source-meta="{ chatId: currentChatId }"
            />

            <!-- Streaming content (SSE) -->
            <div
              v-if="answering && streamingContent"
              class="flex gap-3"
            >
              <div class="w-8 h-8 rounded-full bg-gradient-to-br from-teal-500 to-emerald-600 flex items-center justify-center text-white text-sm font-bold shrink-0">
                NB
              </div>
              <div class="max-w-[90%] min-w-0">
                <div class="inline-block text-left bg-white text-slate-800 border border-slate-200 rounded-2xl rounded-bl-md px-5 py-4 shadow-sm max-w-full overflow-hidden">
                  <div ref="streamingProseEl" class="prose-chat text-[13.5px] leading-[1.75] text-slate-700" v-html="renderMd(streamingContent)" />
                  <span class="inline-block w-1.5 h-4 bg-teal-500 rounded-sm animate-pulse ml-0.5 align-middle" />
                  <!-- 網路搜尋來源 -->
                  <div v-if="streamingSources.length" class="mt-3 pt-3 border-t border-slate-100">
                    <div class="text-[11px] font-semibold text-slate-500 mb-1.5">🔗 網路搜尋來源</div>
                    <ul class="space-y-1">
                      <li v-for="(src, i) in streamingSources" :key="i" class="text-[11px]">
                        <a :href="src.url" target="_blank" rel="noopener noreferrer" class="text-blue-600 hover:text-blue-800 underline underline-offset-2">{{ src.title || src.url }}</a>
                      </li>
                    </ul>
                  </div>
                </div>
                <div class="text-[10px] text-slate-400 mt-1 px-1">串流回應中...</div>
              </div>
            </div>

            <!-- Typing indicator (before streaming starts) -->
            <div
              v-else-if="answering"
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
            <GuestLock />
            <div v-if="isLoggedIn" class="max-w-3xl mx-auto flex items-end gap-2">
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
            <p v-if="role === 'pro'" class="text-center text-[10px] text-slate-300 mt-1.5">
              問答引擎結合教科書 FAISS 向量搜尋 + PubMed + Google Search + Gemini 2.5 Flash
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

        <!-- Upload section -->
        <div class="bg-white border border-slate-200 rounded-xl p-4 mb-6">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-bold text-slate-700">📤 上傳教科書 PDF</h3>
            <label
              class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium rounded-lg cursor-pointer transition-colors"
              :class="uploading ? 'opacity-50 cursor-not-allowed' : ''"
            >
              {{ uploading ? '上傳中...' : '選擇 PDF' }}
              <input
                type="file"
                accept=".pdf"
                class="hidden"
                :disabled="uploading"
                @change="handleUpload"
              />
            </label>
          </div>

          <!-- Upload progress -->
          <div v-if="uploading" class="mb-3">
            <div class="h-2 bg-slate-100 rounded-full overflow-hidden">
              <div
                class="h-full bg-blue-500 rounded-full transition-all duration-300"
                :style="{ width: uploadProgress + '%' }"
              />
            </div>
            <p class="text-[10px] text-slate-400 mt-1">{{ Math.round(uploadProgress) }}% 已上傳</p>
          </div>

          <p class="text-xs text-slate-400 leading-relaxed">
            PDF 上傳後狀態為「等待處理」。需在本地執行
            <code class="bg-slate-100 px-1 py-0.5 rounded text-[11px]">python local_pdf_processor.py</code>
            進行切片與向量化。處理完成後 Cloud Run 重啟會自動載入新知識。
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
import { useRoute, useRouter } from 'vue-router'
import { collection, addDoc, serverTimestamp } from 'firebase/firestore'
import { ref as storageRef, uploadBytesResumable, getDownloadURL } from 'firebase/storage'
import { db, storage } from '../firebase.js'
import { useConsultChat } from '../composables/useConsultChat.js'
import { useBooks } from '../composables/useBooks.js'
import ChatMessage from '../components/ChatMessage.vue'
import BookCard from '../components/BookCard.vue'
import SelectionToolbar from '../components/SelectionToolbar.vue'
import GuestLock from '../components/GuestLock.vue'
import { useAuth } from '../composables/useAuth.js'
import { renderMd } from '../utils/renderMarkdown.js'
import { renderMermaidIn } from '../composables/useMermaid.js'

const { isLoggedIn, uid } = useAuth()
const router = useRouter()

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
  streamingContent,
  streamingSources,
  subscribeChats,
  selectChat,
  createChat,
  deleteChat,
  sendQuestion,
  sendQuestionStream,
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
const uploading = ref(false)
const uploadProgress = ref(0)
const streamingProseEl = ref(null)

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

// === PDF 上傳 ===
async function handleUpload(e) {
  const file = e.target.files?.[0]
  if (!file || !file.name.endsWith('.pdf')) {
    alert('請選擇 PDF 檔案')
    return
  }

  uploading.value = true
  uploadProgress.value = 0

  const path = `books/${Date.now()}_${file.name}`
  const fileRef = storageRef(storage, path)
  const uploadTask = uploadBytesResumable(fileRef, file)

  uploadTask.on(
    'state_changed',
    (snapshot) => {
      uploadProgress.value = (snapshot.bytesTransferred / snapshot.totalBytes) * 100
    },
    (err) => {
      console.error('Upload error:', err)
      alert('上傳失敗，請重試')
      uploading.value = false
      uploadProgress.value = 0
    },
    async () => {
      try {
        const downloadURL = await getDownloadURL(uploadTask.snapshot.ref)
        const sizeMb = `${(file.size / (1024 * 1024)).toFixed(2)} MB`

        await addDoc(collection(db, 'books'), {
          title: file.name.replace(/\.pdf$/i, ''),
          url: downloadURL,
          storagePath: path,
          size: sizeMb,
          status: 'pending',
          uploadedAt: serverTimestamp(),
        })
      } catch (err) {
        console.error('Save error:', err)
        alert('儲存書籍記錄失敗')
      } finally {
        uploading.value = false
        uploadProgress.value = 0
        e.target.value = '' // reset file input
      }
    }
  )
}

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || answering.value) return
  inputText.value = ''
  textareaHeight.value = '40px'
  // 優先使用 SSE streaming，失敗會自動 fallback
  await sendQuestionStream(text)
}

// === 整則回覆收進 Notes ===
async function saveFullReplyToNotes(content) {
  try {
    const title = content.split('\n')[0].replace(/[#*_`>]/g, '').trim().slice(0, 30) || '問答摘錄'
    await addDoc(collection(db, 'notes'), {
      title: title + (title.length >= 30 ? '…' : ''),
      content,
      tags: [],
      links: [],
      sources: [{
        type: 'consult',
        chatId: currentChatId.value,
        snippet: content.slice(0, 200),
        saved_at: new Date().toISOString(),
      }],
      userId: uid.value,
      created_at: serverTimestamp(),
      updated_at: serverTimestamp(),
    })
    // 簡易 toast
    const el = document.createElement('div')
    el.textContent = '已收進 Notes ✓'
    el.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);z-index:50;background:#7c3aed;color:white;padding:8px 16px;border-radius:12px;font-size:14px;box-shadow:0 4px 12px rgba(0,0,0,.15)'
    document.body.appendChild(el)
    setTimeout(() => el.remove(), 2000)
  } catch (e) {
    console.error('Save to notes error:', e)
    alert('儲存失敗')
  }
}

// === 加入 Teach ===
function sendToTeach(content) {
  router.push({ path: '/teach', query: { text: content } })
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

// Auto-scroll during streaming
watch(
  () => streamingContent.value,
  async () => {
    await nextTick()
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  }
)

// Render mermaid blocks when streaming completes
watch(
  () => answering.value,
  async (newVal, oldVal) => {
    if (oldVal === true && newVal === false && streamingProseEl.value) {
      await nextTick()
      renderMermaidIn(streamingProseEl.value)
    }
  }
)

// Lifecycle
const route = useRoute()

onMounted(() => {
  subscribeChats()
  checkApiHealth()
  fetchStats()

  // 從其他模組帶入的問題（例如 InsightPage 的「深入問答」）
  if (route.query.q) {
    inputText.value = route.query.q
    activeTab.value = 'chat'
  }
})

onUnmounted(() => {
  cleanupChat()
  unsubBooks()
})
</script>

<style scoped>
/* ── Summary card (streaming phase) ── */
.prose-chat :deep(.summary-card) {
  background: linear-gradient(135deg, #ecfdf5 0%, #f0f9ff 100%);
  border: 1px solid #a7f3d0;
  border-radius: 12px;
  padding: 14px 18px;
  margin-bottom: 16px;
}
.prose-chat :deep(.summary-card .summary-title) {
  font-weight: 700;
  font-size: 13px;
  color: #065f46;
  margin-bottom: 8px;
}
.prose-chat :deep(.summary-card ul) {
  padding-left: 18px;
  margin: 0;
}
.prose-chat :deep(.summary-card li) {
  list-style: disc;
  font-size: 13px;
  color: #1e293b;
  line-height: 1.6;
  margin-bottom: 4px;
  padding-left: 2px;
}
.prose-chat :deep(.summary-card li:last-child) {
  margin-bottom: 0;
}
.prose-chat :deep(.summary-card strong) {
  color: #065f46;
}

/* ── Mermaid flowchart (streaming phase) ── */
.prose-chat :deep(.mermaid-block) {
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 20px 16px;
  margin: 16px 0;
  overflow-x: auto;
  text-align: center;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}
.prose-chat :deep(.mermaid-block svg) {
  max-width: 100%;
  height: auto;
}
.prose-chat :deep(.mermaid-block .node polygon) {
  fill: #fef3c7 !important;
  stroke: #f59e0b !important;
  stroke-width: 1.5px;
}
.prose-chat :deep(.mermaid-block .node rect) {
  fill: #eff6ff !important;
  stroke: #93c5fd !important;
  stroke-width: 1.5px;
  rx: 8;
  ry: 8;
  filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.06));
}
.prose-chat :deep(.mermaid-block .edgePath .path) {
  stroke: #94a3b8 !important;
  stroke-width: 1.5px;
}
.prose-chat :deep(.mermaid-block .edgeLabel) {
  background-color: #ffffff !important;
  font-size: 12px;
  padding: 2px 6px;
  border-radius: 4px;
}
.prose-chat :deep(.mermaid-block .nodeLabel) {
  font-family: -apple-system, "Noto Sans TC", system-ui, sans-serif;
  font-size: 13px;
  font-weight: 500;
}
.prose-chat :deep(.mermaid-block .arrowheadPath) {
  fill: #94a3b8 !important;
}
.prose-chat :deep(.flowchart-svg) {
  max-width: 100%;
  height: auto;
}
.prose-chat :deep(.mermaid-fallback) {
  text-align: left;
  padding: 8px 0;
}
</style>
