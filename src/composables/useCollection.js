import { ref, computed, watch } from 'vue'
import { db } from '../firebase.js'
import {
  collection,
  doc,
  setDoc,
  deleteDoc,
  onSnapshot,
  query,
  orderBy,
  where,
  serverTimestamp,
} from 'firebase/firestore'
import { useAuth } from './useAuth.js'

export function useCollection() {
  const { uid } = useAuth()

  const savedArticles = ref([])
  const savedIds = computed(() => new Set(savedArticles.value.map((a) => a.id)))
  const loading = ref(true)

  let unsubscribe = null

  function subscribe() {
    if (unsubscribe) unsubscribe()
    if (!uid.value) return

    const q = query(
      collection(db, 'insight_collection'),
      where('userId', '==', uid.value),
      orderBy('saved_at', 'desc')
    )

    unsubscribe = onSnapshot(q, (snapshot) => {
      savedArticles.value = snapshot.docs.map((d) => ({
        id: d.id,
        ...d.data(),
      }))
      loading.value = false
    })
  }

  subscribe()
  watch(uid, () => { subscribe() })

  const toggleSave = async (article) => {
    const docRef = doc(db, 'insight_collection', `${uid.value}_${article.id}`)

    if (savedIds.value.has(article.id)) {
      await deleteDoc(docRef)
    } else {
      await setDoc(docRef, {
        ...article,
        userId: uid.value,
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
    unsubscribe: () => { if (unsubscribe) unsubscribe() },
  }
}
