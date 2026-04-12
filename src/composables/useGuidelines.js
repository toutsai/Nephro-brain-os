import { ref, computed, onUnmounted, watch } from 'vue'
import { collection, query, orderBy, onSnapshot } from 'firebase/firestore'
import { db } from '../firebase.js'

export function useGuidelines() {
  const guidelines = ref([])
  const loading = ref(true)

  const q = query(
    collection(db, 'guidelines'),
    orderBy('org', 'asc'),
    orderBy('year', 'desc')
  )

  const unsubscribe = onSnapshot(
    q,
    (snapshot) => {
      guidelines.value = snapshot.docs.map((doc) => ({
        id: doc.id,
        ...doc.data(),
      }))
      loading.value = false
    },
    (err) => {
      console.error('Guidelines Firestore error:', err)
      loading.value = false
    }
  )

  onUnmounted(() => {
    unsubscribe()
  })

  const kdigoGuidelines = computed(() =>
    guidelines.value.filter((g) => g.org === 'KDIGO')
  )

  const kdoqiGuidelines = computed(() =>
    guidelines.value.filter((g) => g.org === 'KDOQI')
  )

  const niceGuidelines = computed(() =>
    guidelines.value.filter((g) => g.org === 'NICE')
  )

  const erbpGuidelines = computed(() =>
    guidelines.value.filter((g) => g.org === 'ERBP')
  )

  const guidelinesByTopic = computed(() => {
    const grouped = {}
    for (const g of guidelines.value) {
      const topic = g.topic || 'Other'
      if (!grouped[topic]) {
        grouped[topic] = []
      }
      grouped[topic].push(g)
    }
    return grouped
  })

  return {
    guidelines,
    kdigoGuidelines,
    kdoqiGuidelines,
    niceGuidelines,
    erbpGuidelines,
    guidelinesByTopic,
    loading,
    unsubscribe,
  }
}
