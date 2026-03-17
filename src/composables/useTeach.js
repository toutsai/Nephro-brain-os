import { ref } from 'vue'
import { db } from '../firebase.js'
import {
  collection,
  doc,
  addDoc,
  updateDoc,
  deleteDoc,
  onSnapshot,
  query,
  orderBy,
  serverTimestamp,
  limit,
} from 'firebase/firestore'

const API_BASE = 'https://nephro-brain-api-761804517300.asia-east1.run.app'

export function useTeach() {
  const sessions = ref([])
  const loading = ref(true)
  const generating = ref(false)
  const generatingMode = ref(null) // 'summary' | 'flashcards' | 'outline' | 'all'
  const error = ref(null)

  // 監聽 teach_sessions
  const q = query(
    collection(db, 'teach_sessions'),
    orderBy('created_at', 'desc'),
    limit(30)
  )

  const unsubscribe = onSnapshot(
    q,
    (snap) => {
      sessions.value = snap.docs.map((d) => ({ id: d.id, ...d.data() }))
      loading.value = false
    },
    (err) => {
      console.error('Teach sessions error:', err)
      loading.value = false
    }
  )

  // === 建立新 Session ===
  async function createSession(title, sourceText) {
    const docRef = await addDoc(collection(db, 'teach_sessions'), {
      title,
      source_text: sourceText,
      summary: null,
      flashcards: null,
      outline: null,
      created_at: serverTimestamp(),
      updated_at: serverTimestamp(),
    })
    return docRef.id
  }

  // === 呼叫 API 生成內容 ===
  async function generate(sessionId, sourceText, mode) {
    generating.value = true
    generatingMode.value = mode
    error.value = null

    try {
      const res = await fetch(`${API_BASE}/teach/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: sourceText,
          mode, // 'summary' | 'flashcards' | 'outline' | 'all'
        }),
      })

      if (!res.ok) throw new Error(`API 回應 ${res.status}`)
      const data = await res.json()

      // 根據模式更新 Firestore
      const updates = { updated_at: serverTimestamp() }
      if (mode === 'all') {
        updates.summary = data.summary || null
        updates.flashcards = data.flashcards || null
        updates.outline = data.outline || null
      } else {
        updates[mode] = data[mode] || data.result || null
      }

      await updateDoc(doc(db, 'teach_sessions', sessionId), updates)
      return data
    } catch (err) {
      console.error('Teach generate error:', err)
      error.value = err.message
      return null
    } finally {
      generating.value = false
      generatingMode.value = null
    }
  }

  // === 刪除 Session ===
  async function deleteSession(sessionId) {
    await deleteDoc(doc(db, 'teach_sessions', sessionId))
  }

  return {
    sessions,
    loading,
    generating,
    generatingMode,
    error,
    createSession,
    generate,
    deleteSession,
    unsubscribe,
  }
}
