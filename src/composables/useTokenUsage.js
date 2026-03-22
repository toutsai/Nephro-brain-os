import { ref, computed, onMounted, onUnmounted } from 'vue'
import { doc, onSnapshot } from 'firebase/firestore'
import { db } from '../firebase.js'

export function useTokenUsage() {
  const monthlyData = ref(null)
  const loading = ref(true)
  let unsubscribe = null

  const monthKey = computed(() => {
    const d = new Date()
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
  })

  const USD_TO_TWD = 32.5

  const monthlyCostTWD = computed(() => {
    if (!monthlyData.value) return '0'
    const twd = (monthlyData.value.total_cost_usd || 0) * USD_TO_TWD
    if (twd > 0 && twd < 1) return twd.toFixed(2)
    return Math.round(twd).toString()
  })

  const totalCalls = computed(() => {
    if (!monthlyData.value?.by_feature) return 0
    return Object.values(monthlyData.value.by_feature)
      .reduce((sum, f) => sum + (f.calls || 0), 0)
  })

  onMounted(() => {
    const docRef = doc(db, 'token_usage', monthKey.value)
    unsubscribe = onSnapshot(docRef, (snap) => {
      monthlyData.value = snap.exists() ? snap.data() : null
      loading.value = false
    })
  })

  onUnmounted(() => {
    if (unsubscribe) unsubscribe()
  })

  return { monthlyData, monthlyCostTWD, USD_TO_TWD, totalCalls, loading, monthKey }
}
