import { ref, watch, onUnmounted } from 'vue'
import { collection, query, where, orderBy, onSnapshot } from 'firebase/firestore'
import { db } from '../firebase.js'

export function useGuidelineChapters(guidelineId) {
  const chapters = ref([])
  const loading = ref(false)
  const selectedChapter = ref(null)
  let unsubscribe = null

  function selectChapter(chapter) {
    selectedChapter.value = chapter
  }

  function subscribe(id) {
    // Clean up previous subscription
    if (unsubscribe) {
      unsubscribe()
      unsubscribe = null
    }

    if (!id) {
      chapters.value = []
      selectedChapter.value = null
      loading.value = false
      return
    }

    loading.value = true

    const q = query(
      collection(db, 'guideline_chapters'),
      where('guideline_id', '==', id),
      where('processing_status', '==', 'ready'),
      orderBy('chapter_number', 'asc')
    )

    unsubscribe = onSnapshot(q, (snapshot) => {
      chapters.value = snapshot.docs.map((doc) => ({
        id: doc.id,
        ...doc.data()
      }))
      // Default to first chapter when chapters load
      if (chapters.value.length > 0 && !selectedChapter.value) {
        selectedChapter.value = chapters.value[0]
      }
      loading.value = false
    }, (error) => {
      console.error('Error fetching guideline chapters:', error)
      loading.value = false
    })
  }

  // Watch for guidelineId changes
  watch(
    guidelineId,
    (newId) => {
      selectedChapter.value = null
      subscribe(newId)
    },
    { immediate: true }
  )

  onUnmounted(() => {
    if (unsubscribe) {
      unsubscribe()
      unsubscribe = null
    }
  })

  return {
    chapters,
    loading,
    selectedChapter,
    selectChapter,
    unsubscribe: () => {
      if (unsubscribe) {
        unsubscribe()
        unsubscribe = null
      }
    }
  }
}
