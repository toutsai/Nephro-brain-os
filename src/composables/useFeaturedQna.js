import { ref, computed, watch } from 'vue'
import { db } from '../firebase.js'
import {
  collection,
  query,
  orderBy,
  onSnapshot,
  addDoc,
  deleteDoc,
  doc,
  serverTimestamp,
} from 'firebase/firestore'

export function useFeaturedQna(uid) {
  const qnas = ref([])
  const loading = ref(true)
  let unsub = null

  function subscribe() {
    if (unsub) unsub()
    const q = query(
      collection(db, 'featured_qna'),
      orderBy('created_at', 'desc')
    )
    unsub = onSnapshot(
      q,
      (snap) => {
        qnas.value = snap.docs.map((d) => ({ id: d.id, ...d.data() }))
        loading.value = false
      },
      (err) => {
        console.error('Featured QnA error:', err)
        loading.value = false
      }
    )
  }

  // Auto subscribe when uid is available
  watch(
    () => uid?.value,
    (v) => { if (v) subscribe() },
    { immediate: true }
  )

  const categories = computed(() => {
    const cats = new Set()
    for (const q of qnas.value) {
      if (q.category) cats.add(q.category)
    }
    return Array.from(cats).sort()
  })

  async function createQna({ question, answer, category, tags = [] }) {
    if (!uid?.value) return
    return addDoc(collection(db, 'featured_qna'), {
      question,
      answer,
      category: category || '一般',
      tags,
      authorId: uid.value,
      created_at: serverTimestamp(),
      updated_at: serverTimestamp(),
    })
  }

  async function deleteQna(id) {
    await deleteDoc(doc(db, 'featured_qna', id))
  }

  function unsubscribe() {
    if (unsub) unsub()
  }

  return {
    qnas,
    loading,
    categories,
    createQna,
    deleteQna,
    unsubscribe,
  }
}
