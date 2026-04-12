import { ref, computed, onUnmounted } from 'vue'
import { collection, query, where, orderBy, limit, onSnapshot, Timestamp } from 'firebase/firestore'
import { db } from '../firebase.js'

export function useClinicalTrials() {
  const trials = ref([])
  const loading = ref(true)
  const error = ref(null)

  const q = query(
    collection(db, 'clinical_trials'),
    where('process_status', '==', 'completed'),
    orderBy('updated_at', 'desc'),
    limit(200)
  )

  const unsubscribe = onSnapshot(
    q,
    (snapshot) => {
      trials.value = snapshot.docs.map((doc) => ({
        id: doc.id,
        ...doc.data(),
      }))
      loading.value = false
    },
    (err) => {
      console.error('Firestore clinical_trials error:', err)
      error.value = err.message
      loading.value = false
    }
  )

  onUnmounted(() => {
    unsubscribe()
  })

  // 依主題分組
  const trialsByTopic = computed(() => {
    const grouped = {}
    for (const trial of trials.value) {
      for (const topic of trial.topics || []) {
        if (!grouped[topic]) grouped[topic] = []
        grouped[topic].push(trial)
      }
    }
    return grouped
  })

  // 僅 Recruiting 狀態
  const recruitingTrials = computed(() =>
    trials.value.filter((t) => t.status === 'RECRUITING')
  )

  // 僅有台灣試驗站點
  const taiwanTrials = computed(() =>
    trials.value.filter((t) => t.has_taiwan_site === true)
  )

  return {
    trials,
    trialsByTopic,
    recruitingTrials,
    taiwanTrials,
    loading,
    error,
    unsubscribe,
  }
}
