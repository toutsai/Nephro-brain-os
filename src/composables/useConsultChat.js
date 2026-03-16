import { ref, computed } from 'vue'
import { db } from '../firebase.js'
import {
  collection,
  doc,
  addDoc,
  setDoc,
  updateDoc,
  deleteDoc,
  onSnapshot,
  query,
  orderBy,
  serverTimestamp,
  limit,
} from 'firebase/firestore'

// Cloud Run API（nephro-brain-web 的 api_server.py）
const API_BASE = 'https://nephro-brain-api-761804517300.asia-east1.run.app'

export function useConsultChat() {
  const chats = ref([])
  const currentChatId = ref(null)
  const messages = ref([])
  const loading = ref(false)
  const answering = ref(false)
  const error = ref(null)
  const chatsLoading = ref(true)

  let unsubChats = null
  let unsubMessages = null

  // === 聊天列表 ===
  function subscribeChats() {
    const q = query(
      collection(db, 'chats'),
      orderBy('updated_at', 'desc'),
      limit(50)
    )
    unsubChats = onSnapshot(q, (snap) => {
      chats.value = snap.docs.map((d) => ({ id: d.id, ...d.data() }))
      chatsLoading.value = false
    })
  }

  // === 訊息監聽 ===
  function subscribeMessages(chatId) {
    if (unsubMessages) unsubMessages()
    if (!chatId) {
      messages.value = []
      return
    }

    const q = query(
      collection(db, 'chats', chatId, 'messages'),
      orderBy('created_at', 'asc')
    )
    unsubMessages = onSnapshot(q, (snap) => {
      messages.value = snap.docs.map((d) => ({ id: d.id, ...d.data() }))
    })
  }

  // === 選擇聊天 ===
  function selectChat(chatId) {
    currentChatId.value = chatId
    subscribeMessages(chatId)
  }

  // === 新建聊天 ===
  async function createChat(title = '新對話') {
    const docRef = await addDoc(collection(db, 'chats'), {
      title,
      created_at: serverTimestamp(),
      updated_at: serverTimestamp(),
      message_count: 0,
    })
    selectChat(docRef.id)
    return docRef.id
  }

  // === 刪除聊天 ===
  async function deleteChat(chatId) {
    await deleteDoc(doc(db, 'chats', chatId))
    if (currentChatId.value === chatId) {
      currentChatId.value = null
      messages.value = []
    }
  }

  // === 發送問題 ===
  async function sendQuestion(question) {
    if (!question.trim()) return
    error.value = null

    // 如果沒有 chat，先建一個
    let chatId = currentChatId.value
    if (!chatId) {
      const title = question.length > 20 ? question.slice(0, 20) + '…' : question
      chatId = await createChat(title)
    }

    // 1. 存使用者訊息
    await addDoc(collection(db, 'chats', chatId, 'messages'), {
      role: 'user',
      content: question,
      created_at: serverTimestamp(),
    })

    // 更新 chat metadata
    await updateDoc(doc(db, 'chats', chatId), {
      updated_at: serverTimestamp(),
      last_message: question.slice(0, 60),
    })

    // 2. 呼叫 Cloud Run API
    answering.value = true
    try {
      const res = await fetch(`${API_BASE}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })

      if (!res.ok) throw new Error(`API 回應 ${res.status}`)

      const data = await res.json()
      const answer = data.answer || '❌ 無回應'

      // 3. 存 AI 回覆
      await addDoc(collection(db, 'chats', chatId, 'messages'), {
        role: 'assistant',
        content: answer,
        created_at: serverTimestamp(),
      })

      // 問答成功 → API 確認在線
      apiStatus.value = 'online'
    } catch (err) {
      console.error('Ask API error:', err)
      error.value = err.message

      await addDoc(collection(db, 'chats', chatId, 'messages'), {
        role: 'assistant',
        content: `⚠️ 呼叫 API 失敗：${err.message}\n\n請確認 Cloud Run 服務是否正在運行。`,
        created_at: serverTimestamp(),
        is_error: true,
      })
    } finally {
      answering.value = false
    }
  }

  // === API 狀態檢查（更穩健：多種方式判定）===
  const apiStatus = ref(null) // 'online' | 'offline' | null
  async function checkApiHealth() {
    // 先試 /health
    try {
      const res = await fetch(`${API_BASE}/health`, {
        signal: AbortSignal.timeout(8000),
        mode: 'cors',
      })
      if (res.ok) {
        const data = await res.json()
        apiStatus.value = 'online'
        return data
      }
    } catch {
      // /health 失敗，改試 /stats（GET 請求，舊版 API 也支援）
      try {
        const res = await fetch(`${API_BASE}/stats`, {
          signal: AbortSignal.timeout(15000),
        })
        if (res.ok) {
          apiStatus.value = 'online'
          return await res.json()
        }
      } catch {
        // 都失敗
      }
    }
    apiStatus.value = 'offline'
    return null
  }

  // === 知識庫統計 ===
  const knowledgeStats = ref(null)
  async function fetchStats() {
    try {
      const res = await fetch(`${API_BASE}/stats`, {
        signal: AbortSignal.timeout(15000),
      })
      if (res.ok) {
        knowledgeStats.value = await res.json()
      }
    } catch {
      // silent
    }
  }

  // === 清理 ===
  function cleanup() {
    if (unsubChats) unsubChats()
    if (unsubMessages) unsubMessages()
  }

  return {
    chats,
    currentChatId,
    messages,
    loading,
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
    cleanup,
  }
}
