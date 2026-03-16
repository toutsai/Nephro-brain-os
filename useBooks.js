import { ref, computed } from 'vue'
import { db } from '../firebase.js'
import {
  collection,
  query,
  orderBy,
  onSnapshot,
} from 'firebase/firestore'

export function useBooks() {
  const books = ref([])
  const loading = ref(true)

  // 即時監聽 books collection
  const q = query(
    collection(db, 'books'),
    orderBy('uploaded_at', 'desc')
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

  // 分類統計
  const readyBooks = computed(() => books.value.filter((b) => b.status === 'ready'))
  const pendingBooks = computed(() =>
    books.value.filter((b) => b.status === 'pending' || b.status === 'processing')
  )
  const errorBooks = computed(() => books.value.filter((b) => b.status === 'error'))

  const totalChunks = computed(() =>
    books.value.reduce((sum, b) => sum + (b.chunks_count || 0), 0)
  )

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
