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
  where,
  serverTimestamp,
  limit,
} from 'firebase/firestore'
import { useAuth } from './useAuth.js'

export function useTeach() {
  const { uid, authFetch, API_BASE } = useAuth()

  const sessions = ref([])
  const loading = ref(true)
  const generating = ref(false)
  const generatingMode = ref(null)
  const error = ref(null)

  let unsubscribe = null

  function subscribe() {
    if (unsubscribe) unsubscribe()
    if (!uid.value) return

    const q = query(
      collection(db, 'teach_sessions'),
      where('userId', '==', uid.value),
      orderBy('created_at', 'desc'),
      limit(30)
    )

    unsubscribe = onSnapshot(
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
  }

  subscribe()

  // === 建立 Session ===
  async function createSession(data = {}) {
    const docRef = await addDoc(collection(db, 'teach_sessions'), {
      title: data.title || '新素材',
      source_text: data.source_text || '',
      file_url: data.file_url || null,
      file_name: data.file_name || null,
      summary: null,
      flashcards: null,
      relation: null,
      mindmap: null,
      ppt: null,
      userId: uid.value,
      created_at: serverTimestamp(),
      updated_at: serverTimestamp(),
    })
    return docRef.id
  }

  // === 呼叫 API 生成 ===
  async function generate(sessionId, { text, fileUrl, mode, pptOptions }) {
    generating.value = true
    generatingMode.value = mode
    error.value = null

    try {
      const body = { mode }
      if (fileUrl) {
        body.file_url = fileUrl
      } else {
        body.text = text
      }
      if (mode === 'ppt' && pptOptions) {
        body.ppt_options = pptOptions
      }

      const res = await authFetch(`${API_BASE}/teach/generate`, {
        method: 'POST',
        body: JSON.stringify(body),
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.error || `API 回應 ${res.status}`)
      }
      const data = await res.json()

      const updates = { updated_at: serverTimestamp() }
      if (mode === 'all') {
        updates.summary = data.summary || null
        updates.flashcards = data.flashcards || null
        updates.relation = data.relation || null
        updates.mindmap = data.mindmap || null
      } else {
        updates[mode] = data[mode] || data.result || null
      }
      if (data.ppt_theme) updates.ppt_theme = data.ppt_theme

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
    unsubscribe: () => { if (unsubscribe) unsubscribe() },
  }
}
