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

  const monthlyCost = computed(() => {
    if (!monthlyData.value) return '0.00'
    const cost = monthlyData.value.total_cost_usd || 0
    // 小金額顯示更多位數，避免一直顯示 $0.00
    if (cost > 0 && cost < 0.01) return cost.toFixed(4)
    return cost.toFixed(2)
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

  return { monthlyData, monthlyCost, totalCalls, loading, monthKey }
}
