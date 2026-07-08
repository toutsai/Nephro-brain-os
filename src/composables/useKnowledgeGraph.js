import { ref, computed, onUnmounted, watch } from 'vue'
import { collection, query, orderBy, where, onSnapshot, doc, getDoc, getDocs } from 'firebase/firestore'
import { db } from '../firebase.js'

/**
 * Real-time listener on kg_concepts collection
 */
export function useKnowledgeConcepts() {
  const concepts = ref([])
  const loading = ref(true)
  const selectedTopic = ref(null)
  const searchQuery = ref('')

  const q = query(
    collection(db, 'kg_concepts'),
    orderBy('updated_at', 'desc')
  )

  const unsubscribe = onSnapshot(
    q,
    (snapshot) => {
      concepts.value = snapshot.docs.map((d) => ({
        id: d.id,
        ...d.data(),
      }))
      loading.value = false
    },
    (err) => {
      console.error('kg_concepts Firestore error:', err)
      loading.value = false
    }
  )

  onUnmounted(() => {
    unsubscribe()
  })

  const conceptsByTopic = computed(() => {
    const grouped = {}
    for (const c of concepts.value) {
      const topic = c.topics?.[0] || 'Other'
      if (!grouped[topic]) grouped[topic] = []
      grouped[topic].push(c)
    }
    return grouped
  })

  const approvedConcepts = computed(() =>
    concepts.value.filter(
      (c) => c.synthesis_status === 'approved' || c.synthesis_status === 'draft' || !c.synthesis_status
    )
  )

  function searchConcepts(q) {
    if (!q || !q.trim()) return concepts.value
    const lower = q.toLowerCase()
    return concepts.value.filter((c) => {
      const text = (c.search_text || `${c.title} ${c.title_zh} ${(c.aliases || []).join(' ')}`).toLowerCase()
      return text.includes(lower)
    })
  }

  const filteredConcepts = computed(() => {
    let result = approvedConcepts.value

    // Apply topic filter
    if (selectedTopic.value) {
      result = result.filter((c) => c.topics?.includes(selectedTopic.value))
    }

    // Apply search filter
    if (searchQuery.value && searchQuery.value.trim()) {
      const lower = searchQuery.value.toLowerCase()
      result = result.filter((c) => {
        const text = (c.search_text || `${c.title} ${c.title_zh} ${(c.aliases || []).join(' ')}`).toLowerCase()
        return text.includes(lower)
      })
    }

    return result
  })

  return {
    concepts,
    loading,
    conceptsByTopic,
    approvedConcepts,
    searchConcepts,
    selectedTopic,
    searchQuery,
    filteredConcepts,
    unsubscribe,
  }
}

/**
 * Real-time listener on pending kg_insights (cross-literature AI insights awaiting review)
 */
export function usePendingInsights() {
  const insights = ref([])
  const loading = ref(true)

  const q = query(
    collection(db, 'kg_insights'),
    where('status', '==', 'pending'),
    orderBy('created_at', 'desc')
  )

  const unsubscribe = onSnapshot(
    q,
    (snapshot) => {
      insights.value = snapshot.docs.map((d) => ({
        id: d.id,
        ...d.data(),
      }))
      loading.value = false
    },
    (err) => {
      console.error('kg_insights Firestore error:', err)
      loading.value = false
    }
  )

  onUnmounted(() => {
    unsubscribe()
  })

  return {
    insights,
    loading,
  }
}

/**
 * Real-time listener on pending kg_guideline_flags (AI-flagged guideline updates awaiting review)
 */
export function usePendingGuidelineFlags() {
  const flags = ref([])
  const loading = ref(true)

  const q = query(
    collection(db, 'kg_guideline_flags'),
    where('status', '==', 'pending'),
    orderBy('created_at', 'desc')
  )

  const unsubscribe = onSnapshot(
    q,
    (snapshot) => {
      flags.value = snapshot.docs.map((d) => ({
        id: d.id,
        ...d.data(),
      }))
      loading.value = false
    },
    (err) => {
      console.error('kg_guideline_flags Firestore error:', err)
      loading.value = false
    }
  )

  onUnmounted(() => {
    unsubscribe()
  })

  return {
    flags,
    loading,
  }
}

/**
 * Fetch single concept + its links
 */
export function useConceptDetail(conceptId) {
  const concept = ref(null)
  const links = ref([])
  const loading = ref(true)
  let unsubLinks = null

  const linksByType = computed(() => {
    const grouped = {}
    for (const link of links.value) {
      const type = link.source_type || 'other'
      if (!grouped[type]) grouped[type] = []
      grouped[type].push(link)
    }
    return grouped
  })

  async function fetchConcept(id) {
    if (!id) return
    loading.value = true

    try {
      const docRef = doc(db, 'kg_concepts', id)
      const snap = await getDoc(docRef)
      if (snap.exists()) {
        concept.value = { id: snap.id, ...snap.data() }
      } else {
        concept.value = null
      }
    } catch (err) {
      console.error('kg_concepts fetch error:', err)
      concept.value = null
    }

    // Listen to links for this concept
    if (unsubLinks) unsubLinks()
    const linksQuery = query(
      collection(db, 'kg_links'),
      where('concept_id', '==', id),
      orderBy('relevance_score', 'desc')
    )

    unsubLinks = onSnapshot(
      linksQuery,
      (snapshot) => {
        links.value = snapshot.docs.map((d) => ({
          id: d.id,
          ...d.data(),
        }))
        loading.value = false
      },
      (err) => {
        console.error('kg_links Firestore error:', err)
        loading.value = false
      }
    )
  }

  // Watch for conceptId changes (supports ref or computed)
  if (typeof conceptId === 'object' && conceptId.value !== undefined) {
    watch(conceptId, (newId) => {
      if (newId) fetchConcept(newId)
      else {
        concept.value = null
        links.value = []
        loading.value = false
      }
    }, { immediate: true })
  } else if (conceptId) {
    fetchConcept(conceptId)
  }

  onUnmounted(() => {
    if (unsubLinks) unsubLinks()
  })

  return {
    concept,
    links,
    linksByType,
    loading,
  }
}
