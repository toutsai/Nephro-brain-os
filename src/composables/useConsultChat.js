import { ref, computed, watch } from 'vue'
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
  where,
  serverTimestamp,
  limit,
} from 'firebase/firestore'
import { useAuth } from './useAuth.js'

export function useConsultChat() {
  const { uid, authFetch, API_BASE } = useAuth()

  const chats = ref([])
  const currentChatId = ref(null)
  const messages = ref([])
  const loading = ref(false)
  const answering = ref(false)
  const error = ref(null)
  const chatsLoading = ref(true)

  let unsubChats = null
  let unsubMessages = null

  // === 聊天列表（只看自己的）===
  function subscribeChats() {
    if (unsubChats) unsubChats()
    if (!uid.value) {
      chats.value = []
      chatsLoading.value = false
      return
    }
    const q = query(
      collection(db, 'chats'),
      where('userId', '==', uid.value),
      orderBy('updated_at', 'desc'),
      limit(50)
    )
    unsubChats = onSnapshot(q, (snap) => {
      chats.value = snap.docs.map((d) => ({ id: d.id, ...d.data() }))
      chatsLoading.value = false
    })
  }

  // 使用者登入/登出時自動重新訂閱
  watch(uid, () => { subscribeChats() })

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
      userId: uid.value,
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

    let chatId = currentChatId.value
    if (!chatId) {
      const title = question.length > 20 ? question.slice(0, 20) + '…' : question
      chatId = await createChat(title)
    }

    await addDoc(collection(db, 'chats', chatId, 'messages'), {
      role: 'user',
      content: question,
      created_at: serverTimestamp(),
    })

    await updateDoc(doc(db, 'chats', chatId), {
      updated_at: serverTimestamp(),
      last_message: question.slice(0, 60),
    })

    answering.value = true
    try {
      const res = await authFetch(`${API_BASE}/ask`, {
        method: 'POST',
        body: JSON.stringify({ question }),
      })

      if (!res.ok) throw new Error(`API 回應 ${res.status}`)

      const data = await res.json()
      const answer = data.answer || '❌ 無回應'

      await addDoc(collection(db, 'chats', chatId, 'messages'), {
        role: 'assistant',
        content: answer,
        created_at: serverTimestamp(),
      })

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

  // === SSE Streaming 發送問題 ===
  const streamingContent = ref('')
  const streamingSources = ref([])

  async function sendQuestionStream(question) {
    if (!question.trim()) return
    error.value = null

    let chatId = currentChatId.value
    if (!chatId) {
      const title = question.length > 20 ? question.slice(0, 20) + '…' : question
      chatId = await createChat(title)
    }

    await addDoc(collection(db, 'chats', chatId, 'messages'), {
      role: 'user',
      content: question,
      created_at: serverTimestamp(),
    })

    await updateDoc(doc(db, 'chats', chatId), {
      updated_at: serverTimestamp(),
      last_message: question.slice(0, 60),
    })

    answering.value = true
    streamingContent.value = ''

    try {
      const res = await authFetch(`${API_BASE}/consult/chat-stream`, {
        method: 'POST',
        body: JSON.stringify({ question }),
      })

      if (!res.ok) throw new Error(`API 回應 ${res.status}`)

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const payload = line.slice(6).trim()

          if (payload === '[DONE]') break

          try {
            const parsed = JSON.parse(payload)
            if (parsed.type === 'content') {
              streamingContent.value += parsed.content
            } else if (parsed.type === 'sources') {
              streamingSources.value = parsed.sources || []
            } else if (parsed.type === 'error') {
              throw new Error(parsed.content)
            }
          } catch (parseErr) {
            if (parseErr.message && !parseErr.message.includes('JSON')) {
              throw parseErr
            }
          }
        }
      }

      const finalAnswer = streamingContent.value || '❌ 無回應'

      // 將參考文獻附加到回答尾部
      let contentToSave = finalAnswer
      if (streamingSources.value.length > 0) {
        contentToSave += '\n\n---\n\n**📚 參考文獻：**\n'
        streamingSources.value.forEach((s, i) => {
          contentToSave += `${i + 1}. [${s.title || s.url}](${s.url})\n`
        })
      }

      await addDoc(collection(db, 'chats', chatId, 'messages'), {
        role: 'assistant',
        content: contentToSave,
        created_at: serverTimestamp(),
      })

      streamingContent.value = ''
      streamingSources.value = []
      apiStatus.value = 'online'
    } catch (err) {
      console.error('Stream API error:', err)
      error.value = err.message
      streamingContent.value = ''
      streamingSources.value = []

      await addDoc(collection(db, 'chats', chatId, 'messages'), {
        role: 'assistant',
        content: `⚠️ 串流回應失敗：${err.message}\n\n正在使用非串流模式重試...`,
        created_at: serverTimestamp(),
        is_error: true,
      })

      try {
        const fallbackRes = await authFetch(`${API_BASE}/ask`, {
          method: 'POST',
          body: JSON.stringify({ question }),
        })
        if (fallbackRes.ok) {
          const data = await fallbackRes.json()
          const answer = data.answer || '❌ 無回應'
          await addDoc(collection(db, 'chats', chatId, 'messages'), {
            role: 'assistant',
            content: answer,
            created_at: serverTimestamp(),
          })
          apiStatus.value = 'online'
        }
      } catch {
        // silent fallback failure
      }
    } finally {
      answering.value = false
    }
  }

  // === API 狀態檢查 ===
  const apiStatus = ref(null)
  async function checkApiHealth() {
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
    cleanup,
  }
}
