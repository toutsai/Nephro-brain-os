import { ref, computed } from 'vue'
import { db } from '../firebase.js'
import {
  collection,
  doc,
  setDoc,
  deleteDoc,
  onSnapshot,
  query,
  orderBy,
  serverTimestamp,
} from 'firebase/firestore'

export function useCollection() {
  const savedArticles = ref([])
  const savedIds = computed(() => new Set(savedArticles.value.map((a) => a.id)))
  const loading = ref(true)

  // 即時監聽收藏庫
  const q = query(
    collection(db, 'insight_collection'),
    orderBy('saved_at', 'desc')
  )

  const unsubscribe = onSnapshot(q, (snapshot) => {
    savedArticles.value = snapshot.docs.map((d) => ({
      id: d.id,
      ...d.data(),
    }))
    loading.value = false
  })

  // 收藏 / 取消收藏
  const toggleSave = async (article) => {
    const docRef = doc(db, 'insight_collection', article.id)

    if (savedIds.value.has(article.id)) {
      await deleteDoc(docRef)
    } else {
      await setDoc(docRef, {
        ...article,
        saved_at: serverTimestamp(),
      })
    }
  }

  const isSaved = (articleId) => savedIds.value.has(articleId)

  return {
    savedArticles,
    loading,
    toggleSave,
    isSaved,
    unsubscribe,
  }
}
