import { ref, computed } from 'vue'
import { db } from '../firebase.js'
import {
  collection,
  query,
  orderBy,
  limit,
  where,
  onSnapshot,
} from 'firebase/firestore'

export function useArticles() {
  const articles = ref([])
  const loading = ref(true)
  const error = ref(null)

  // 即時監聽 articles_v2（最近 100 篇）
  const q = query(
    collection(db, 'articles_v2'),
    where('process_status', '==', 'completed'),
    orderBy('created_at', 'desc'),
    limit(100)
  )

  const unsubscribe = onSnapshot(
    q,
    (snapshot) => {
      articles.value = snapshot.docs.map((doc) => ({
        id: doc.id,
        ...doc.to_dict ? doc.to_dict() : doc.data(),
      }))
      loading.value = false
    },
    (err) => {
      console.error('Firestore error:', err)
      error.value = err.message
      loading.value = false
    }
  )

  // 依主題分區
  const esrdArticles = computed(() =>
    articles.value.filter((a) => a.topics?.includes('ESRD/HD'))
  )
  const akiArticles = computed(() =>
    articles.value.filter((a) => a.topics?.includes('AKI'))
  )
  const ckdArticles = computed(() =>
    articles.value.filter((a) => a.topics?.includes('CKD'))
  )

  // 今日文章判斷
  const isToday = (timestamp) => {
    if (!timestamp) return false
    const date = timestamp.toDate ? timestamp.toDate() : new Date(timestamp)
    return date.toDateString() === new Date().toDateString()
  }

  return {
    articles,
    esrdArticles,
    akiArticles,
    ckdArticles,
    loading,
    error,
    isToday,
    unsubscribe,
  }
}
