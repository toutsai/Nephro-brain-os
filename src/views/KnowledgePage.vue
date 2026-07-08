<template>
  <div class="h-[calc(100dvh-44px)] flex flex-col bg-slate-50 overflow-hidden pb-14 sm:pb-0">
    <!-- Header -->
    <header class="bg-white border-b border-slate-200 shrink-0">
      <div class="px-4 py-2 flex items-center justify-between">
        <div class="flex items-center gap-2">
          <h1 class="text-sm font-bold text-slate-800">Knowledge Graph</h1>
          <span class="text-[10px] text-slate-400">Concept Explorer</span>
        </div>
        <div class="text-xs text-slate-400">
          {{ filteredConcepts.length }} concepts
        </div>
      </div>

      <!-- Search -->
      <div class="px-4 pb-2">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search concepts..."
          class="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <!-- Topic filter chips -->
      <div class="px-4 pb-2 flex gap-1.5 overflow-x-auto no-scrollbar">
        <button
          class="shrink-0 text-[11px] px-3 py-1 rounded-full font-medium transition-colors"
          :class="!selectedTopic
            ? 'bg-blue-600 text-white'
            : 'bg-slate-100 text-slate-500 hover:bg-slate-200'"
          @click="selectedTopic = null; showReview = false"
        >
          All
        </button>
        <button
          v-for="topic in allTopics"
          :key="topic"
          class="shrink-0 text-[11px] px-3 py-1 rounded-full font-medium transition-colors"
          :class="selectedTopic === topic && !showReview
            ? topicActiveClass(topic)
            : 'bg-slate-100 text-slate-500 hover:bg-slate-200'"
          @click="selectedTopic = topic; showReview = false"
        >
          {{ topic }}
        </button>
        <button
          v-if="isAdmin"
          class="shrink-0 text-[11px] px-3 py-1 rounded-full font-medium transition-colors"
          :class="showReview
            ? 'bg-amber-600 text-white'
            : 'bg-amber-100 text-amber-700 hover:bg-amber-200'"
          @click="showReview = !showReview"
        >
          待審核 Review{{ pendingReviewCount ? ` (${pendingReviewCount})` : '' }}
        </button>
      </div>
    </header>

    <!-- Loading -->
    <div v-if="loading" class="flex-1 flex items-center justify-center">
      <div class="text-center">
        <div class="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p class="text-sm text-slate-500">Loading concepts...</p>
      </div>
    </div>

    <!-- Main content -->
    <main v-else class="flex-1 overflow-hidden">
      <!-- Review section (admin only) -->
      <div v-if="showReview && isAdmin" class="h-full overflow-y-auto px-4 py-3 space-y-5">
        <section>
          <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
            Pending Insights ({{ pendingInsights.length }})
          </h3>
          <div v-if="insightsLoading" class="text-sm text-slate-400 text-center py-6">
            Loading...
          </div>
          <div v-else-if="!pendingInsights.length" class="text-sm text-slate-400 text-center py-6">
            No pending insights
          </div>
          <div v-else class="space-y-3">
            <InsightReviewCard
              v-for="insight in pendingInsights"
              :key="insight.id"
              :insight="insight"
              @view-concept="onViewConcept"
            />
          </div>
        </section>

        <section>
          <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
            Pending Guideline Flags ({{ pendingFlags.length }})
          </h3>
          <div v-if="flagsLoading" class="text-sm text-slate-400 text-center py-6">
            Loading...
          </div>
          <div v-else-if="!pendingFlags.length" class="text-sm text-slate-400 text-center py-6">
            No pending guideline flags
          </div>
          <div v-else class="space-y-3">
            <GuidelineFlagCard
              v-for="flag in pendingFlags"
              :key="flag.id"
              :flag="flag"
              @view-concept="onViewConcept"
            />
          </div>
        </section>
      </div>

      <template v-else>
        <!-- Detail view -->
        <div v-if="selectedConceptId" class="h-full bg-white">
          <ConceptDetail
            :concept-id="selectedConceptId"
            @back="selectedConceptId = null"
          />
        </div>

        <!-- Grid view -->
        <div v-else class="h-full overflow-y-auto px-4 py-3">
          <!-- Empty state -->
          <div
            v-if="filteredConcepts.length === 0"
            class="flex items-center justify-center h-full"
          >
            <div class="text-center">
              <p class="text-2xl mb-2">&#x1F50D;</p>
              <p class="text-sm text-slate-500">No concepts found</p>
              <p class="text-xs text-slate-400 mt-1">Try a different search or topic filter</p>
            </div>
          </div>

          <!-- Concept grid -->
          <div
            v-else
            class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3"
          >
            <ConceptCard
              v-for="c in filteredConcepts"
              :key="c.id"
              :concept="c"
              @select="selectedConceptId = c.id"
            />
          </div>
        </div>
      </template>
    </main>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import {
  useKnowledgeConcepts,
  usePendingInsights,
  usePendingGuidelineFlags,
} from '../composables/useKnowledgeGraph.js'
import { useAuth } from '../composables/useAuth.js'
import ConceptCard from '../components/ConceptCard.vue'
import ConceptDetail from '../components/ConceptDetail.vue'
import InsightReviewCard from '../components/kg/InsightReviewCard.vue'
import GuidelineFlagCard from '../components/kg/GuidelineFlagCard.vue'

const {
  filteredConcepts,
  loading,
  selectedTopic,
  searchQuery,
} = useKnowledgeConcepts()

const { isAdmin } = useAuth()

const { insights: pendingInsights, loading: insightsLoading } = usePendingInsights()
const { flags: pendingFlags, loading: flagsLoading } = usePendingGuidelineFlags()

const pendingReviewCount = computed(() => pendingInsights.value.length + pendingFlags.value.length)

const selectedConceptId = ref(null)
const showReview = ref(false)

function onViewConcept(conceptId) {
  showReview.value = false
  selectedConceptId.value = conceptId
}

const allTopics = [
  'CKD', 'AKI', 'GN', 'Transplant', 'ESRD/HD', 'Electrolyte',
  'PD', 'CKM', 'HTN', 'PKD', 'CKD-MBD', 'Stone', 'Onco-Nephro',
]

const topicActiveColors = {
  CKD: 'bg-blue-600 text-white',
  AKI: 'bg-red-600 text-white',
  GN: 'bg-purple-600 text-white',
  Transplant: 'bg-green-600 text-white',
  'ESRD/HD': 'bg-orange-600 text-white',
  Electrolyte: 'bg-teal-600 text-white',
  PD: 'bg-indigo-600 text-white',
  CKM: 'bg-pink-600 text-white',
  HTN: 'bg-rose-600 text-white',
  PKD: 'bg-cyan-600 text-white',
  'CKD-MBD': 'bg-amber-600 text-white',
  Stone: 'bg-lime-600 text-white',
  'Onco-Nephro': 'bg-fuchsia-600 text-white',
}

function topicActiveClass(topic) {
  return topicActiveColors[topic] || 'bg-blue-600 text-white'
}
</script>

<style scoped>
.no-scrollbar::-webkit-scrollbar {
  display: none;
}
.no-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>
