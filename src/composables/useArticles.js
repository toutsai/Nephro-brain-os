import { ref, computed } from 'vue'
import { db } from '../firebase.js'
import {
  collection,
  query,
  orderBy,
  limit,
  where,
  onSnapshot,
  Timestamp,
} from 'firebase/firestore'

export function useArticles() {
  const articles = ref([])
  const loading = ref(true)
  const error = ref(null)

  // 即時監聽 articles_v2（最近 30 天 + 上限 300 篇）
  const thirtyDaysAgo = new Date()
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30)

  const q = query(
    collection(db, 'articles_v2'),
    where('process_status', '==', 'completed'),
    where('created_at', '>=', Timestamp.fromDate(thirtyDaysAgo)),
    orderBy('created_at', 'desc'),
    limit(300)
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
  const gnArticles = computed(() =>
    articles.value.filter((a) => a.topics?.includes('GN'))
  )
  const transplantArticles = computed(() =>
    articles.value.filter((a) => a.topics?.includes('Transplant'))
  )
  const electrolyteArticles = computed(() =>
    articles.value.filter((a) => a.topics?.includes('Electrolyte'))
  )
  const pdArticles = computed(() =>
    articles.value.filter((a) => a.topics?.includes('PD'))
  )

  // Phase 3: 擴充主題
  const ckmArticles = computed(() =>
    articles.value.filter((a) => a.topics?.includes('CKM'))
  )
  const htnArticles = computed(() =>
    articles.value.filter((a) => a.topics?.includes('HTN'))
  )
  const pkdArticles = computed(() =>
    articles.value.filter((a) => a.topics?.includes('PKD'))
  )
  const ckdMbdArticles = computed(() =>
    articles.value.filter((a) => a.topics?.includes('CKD-MBD'))
  )
  const stoneArticles = computed(() =>
    articles.value.filter((a) => a.topics?.includes('Stone'))
  )
  const oncoNephroArticles = computed(() =>
    articles.value.filter((a) => a.topics?.includes('Onco-Nephro'))
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
    gnArticles,
    transplantArticles,
    electrolyteArticles,
    pdArticles,
    ckmArticles,
    htnArticles,
    pkdArticles,
    ckdMbdArticles,
    stoneArticles,
    oncoNephroArticles,
    journalArticles,
    loading,
    error,
    isToday,
    unsubscribe,
  }
}
