import { ref, computed } from 'vue'
import { db } from '../firebase.js'
import {
  collection,
  query,
  orderBy,
  onSnapshot,
} from 'firebase/firestore'

const API_BASE = 'https://nephro-brain-api-761804517300.asia-east1.run.app'

export function useBooks() {
  const books = ref([])
  const loading = ref(true)
  const apiChunks = ref(0) // 從 API /stats 取得的真實 chunks 數

  // 即時監聽 books collection
  const q = query(
    collection(db, 'books'),
    orderBy('uploadedAt', 'desc')  // 舊專案用 camelCase
  )

  const unsubscribe = onSnapshot(
    q,
    (snap) => {
      books.value = snap.docs.map((d) => ({ id: d.id, ...d.data() }))
      loading.value = false
    },
    (err) => {
      console.error('Books snapshot error:', err)
      loading.value = false
    }
  )

  // 從 /stats API 取得知識片段總數
  async function fetchChunksCount() {
    try {
      const res = await fetch(`${API_BASE}/stats`, { signal: AbortSignal.timeout(15000) })
      if (res.ok) {
        const data = await res.json()
        apiChunks.value = data.memory_chunks_ids || data.total_chunks || 0
      }
    } catch (e) {
      console.warn('Failed to fetch chunks count:', e)
    }
  }
  fetchChunksCount()

  // 分類統計
  const readyBooks = computed(() => books.value.filter((b) => b.status === 'ready'))
  const pendingBooks = computed(() =>
    books.value.filter((b) => b.status === 'pending' || b.status === 'processing')
  )
  const errorBooks = computed(() => books.value.filter((b) => b.status === 'error'))

  // chunks 優先用 API 回傳的數字
  const totalChunks = computed(() => {
    if (apiChunks.value > 0) return apiChunks.value
    return books.value.reduce((sum, b) => sum + (b.chunks_count || 0), 0)
  })

  return {
    books,
    loading,
    readyBooks,
    pendingBooks,
    errorBooks,
    totalChunks,
    unsubscribe,
  }
}
