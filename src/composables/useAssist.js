import { ref, watch } from 'vue'
import { db } from '../firebase.js'
import {
  collection,
  doc,
  addDoc,
  deleteDoc,
  onSnapshot,
  query,
  orderBy,
  where,
  serverTimestamp,
  limit,
} from 'firebase/firestore'
import { useAuth } from './useAuth.js'

export function useAssist() {
  const { uid, authFetch, API_BASE } = useAuth()

  const history = ref([])
  const loading = ref(true)
  const generating = ref(false)
  const error = ref(null)

  let unsubscribe = null

  function subscribe() {
    if (unsubscribe) unsubscribe()
    if (!uid.value) return

    const q = query(
      collection(db, 'assist_history'),
      where('userId', '==', uid.value),
      orderBy('created_at', 'desc'),
      limit(30)
    )

    unsubscribe = onSnapshot(
      q,
      (snap) => {
        history.value = snap.docs.map((d) => ({ id: d.id, ...d.data() }))
        loading.value = false
      },
      (err) => {
        console.error('Assist history error:', err)
        loading.value = false
      }
    )
  }

  subscribe()
  watch(uid, () => { subscribe() })

  // === 呼叫 API（支援文字 + 圖片）===
  async function queryAssist({ mode, payload, images }) {
    generating.value = true
    error.value = null

    try {
      const body = { mode, ...payload }

      if (images && images.length > 0) {
        body.images = images
      }

      const res = await authFetch(`${API_BASE}/assist/query`, {
        method: 'POST',
        body: JSON.stringify(body),
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.error || `API 回應 ${res.status}`)
      }

      const data = await res.json()

      const docRef = await addDoc(collection(db, 'assist_history'), {
        mode,
        input: payload,
        has_images: !!(images && images.length),
        image_count: images ? images.length : 0,
        result: data.result,
        userId: uid.value,
        created_at: serverTimestamp(),
      })

      return { id: docRef.id, result: data.result }
    } catch (err) {
      console.error('Assist query error:', err)
      error.value = err.message
      return null
    } finally {
      generating.value = false
    }
  }

  async function deleteHistory(id) {
    await deleteDoc(doc(db, 'assist_history', id))
  }

  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => {
        const base64 = reader.result.split(',')[1]
        resolve({ data: base64, mime_type: file.type })
      }
      reader.onerror = reject
      reader.readAsDataURL(file)
    })
  }

  return {
    history,
    loading,
    generating,
    error,
    queryAssist,
    deleteHistory,
    fileToBase64,
    unsubscribe: () => { if (unsubscribe) unsubscribe() },
  }
}
