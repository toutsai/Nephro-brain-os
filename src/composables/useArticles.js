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

  // 即時監聯 articles_v2（最近 150 篇，增加以涵蓋期刊）
  const q = query(
    collection(db, 'articles_v2'),
    where('process_status', '==', 'completed'),
    orderBy('created_at', 'desc'),
    limit(150)
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

  // 期刊文章（有 journals 欄位，或 sources 包含 "journal"）
  const journalArticles = computed(() =>
    articles.value.filter((a) =>
      (a.journals && a.journals.length > 0) ||
      (a.sources && a.sources.includes('journal'))
    )
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
    journalArticles,
    loading,
    error,
    isToday,
    unsubscribe,
  }
}
