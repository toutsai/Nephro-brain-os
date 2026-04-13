<template>
  <div class="h-full flex flex-col overflow-hidden">
    <!-- Loading -->
    <div v-if="loading" class="flex-1 flex items-center justify-center">
      <div class="text-center">
        <div class="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p class="text-sm text-slate-500">Loading concept...</p>
      </div>
    </div>

    <!-- Not found -->
    <div v-else-if="!concept" class="flex-1 flex items-center justify-center">
      <p class="text-sm text-slate-400">Concept not found</p>
    </div>

    <!-- Detail content -->
    <template v-else>
      <!-- Header -->
      <div class="shrink-0 bg-white border-b border-slate-200 px-4 py-3">
        <button
          class="text-xs text-blue-600 hover:text-blue-800 mb-2 flex items-center gap-1 transition-colors"
          @click="$emit('back')"
        >
          <span>&larr;</span> Back to list
        </button>

        <div class="flex items-center gap-2 mb-1 flex-wrap">
          <span
            class="text-[10px] font-bold px-2 py-0.5 rounded-full"
            :class="statusBadgeClass"
          >
            {{ statusLabel }}
          </span>
          <span
            v-for="topic in concept.topics"
            :key="topic"
            class="text-[10px] font-medium px-2 py-0.5 rounded-full"
            :class="topicBadgeClass(topic)"
          >
            {{ topic }}
          </span>
        </div>

        <h2 class="text-base font-bold text-slate-800 mb-0.5">
          {{ concept.title }}
        </h2>
        <p v-if="concept.title_zh" class="text-sm text-slate-600 mb-1">
          {{ concept.title_zh }}
        </p>
        <p
          v-if="concept.aliases?.length"
          class="text-[10px] text-slate-400"
        >
          Aliases: {{ concept.aliases.join(', ') }}
        </p>
      </div>

      <!-- Scrollable body -->
      <div class="flex-1 overflow-y-auto">
        <!-- Synthesis Note -->
        <section v-if="concept.synthesis_note" class="px-4 py-3 border-b border-slate-100">
          <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
            Synthesis Note
          </h3>
          <pre class="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed font-sans">{{ concept.synthesis_note }}</pre>
        </section>

        <!-- Related Sources tabs -->
        <section class="px-4 py-3">
          <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
            Related Sources
          </h3>

          <!-- Tab buttons -->
          <div class="flex gap-1 mb-3 flex-wrap">
            <button
              v-for="tab in sourceTabs"
              :key="tab.key"
              class="text-xs px-3 py-1.5 rounded-full transition-colors font-medium"
              :class="activeSourceTab === tab.key
                ? 'bg-blue-100 text-blue-700'
                : 'bg-slate-100 text-slate-500 hover:bg-slate-200'"
              @click="activeSourceTab = tab.key"
            >
              {{ tab.icon }} {{ tab.label }} ({{ tab.count }})
            </button>
          </div>

          <!-- Source list -->
          <div v-if="activeSourceLinks.length" class="space-y-2">
            <div
              v-for="link in activeSourceLinks"
              :key="link.id"
              class="bg-white rounded-lg border border-slate-200 p-3"
            >
              <h4 class="text-sm font-medium text-slate-800 mb-1">
                {{ link.source_snapshot?.title || link.source_id }}
              </h4>

              <!-- Article meta -->
              <template v-if="link.source_type === 'article'">
                <p v-if="link.source_snapshot?.journal" class="text-[10px] text-slate-400">
                  {{ link.source_snapshot.journal }}
                </p>
                <p v-if="link.source_snapshot?.evidence_level" class="text-[10px] text-slate-400">
                  Evidence: {{ link.source_snapshot.evidence_level }}
                </p>
              </template>

              <!-- Guideline meta -->
              <template v-if="link.source_type === 'guideline'">
                <p v-if="link.source_snapshot?.org" class="text-[10px] text-slate-400">
                  {{ link.source_snapshot.org }} {{ link.source_snapshot.year || '' }}
                </p>
              </template>

              <!-- Trial meta -->
              <template v-if="link.source_type === 'trial'">
                <p v-if="link.source_snapshot?.phase" class="text-[10px] text-slate-400">
                  Phase {{ link.source_snapshot.phase }}
                  <span v-if="link.source_snapshot?.status"> &middot; {{ link.source_snapshot.status }}</span>
                </p>
              </template>

              <!-- Drug meta -->
              <template v-if="link.source_type === 'drug'">
                <p v-if="link.source_snapshot?.class" class="text-[10px] text-slate-400">
                  Class: {{ link.source_snapshot.class }}
                </p>
              </template>

              <!-- Relevance score -->
              <div class="flex items-center gap-2 mt-1.5">
                <div class="flex-1 bg-slate-100 rounded-full h-1">
                  <div
                    class="h-1 rounded-full bg-blue-400"
                    :style="{ width: `${(link.relevance_score || 0) * 100}%` }"
                  />
                </div>
                <span class="text-[10px] text-slate-400">
                  {{ ((link.relevance_score || 0) * 100).toFixed(0) }}%
                </span>
              </div>
            </div>
          </div>

          <div v-else class="text-sm text-slate-400 text-center py-6">
            No {{ activeSourceTab }} sources linked yet
          </div>
        </section>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, toRef } from 'vue'
import { useConceptDetail } from '../composables/useKnowledgeGraph.js'

const props = defineProps({
  conceptId: { type: String, required: true },
})

defineEmits(['back'])

const { concept, links, linksByType, loading } = useConceptDetail(toRef(props, 'conceptId'))

const activeSourceTab = ref('article')

const topicColorMap = {
  CKD: 'bg-blue-100 text-blue-700',
  AKI: 'bg-red-100 text-red-700',
  GN: 'bg-purple-100 text-purple-700',
  Transplant: 'bg-green-100 text-green-700',
  'ESRD/HD': 'bg-orange-100 text-orange-700',
  Electrolyte: 'bg-teal-100 text-teal-700',
  PD: 'bg-indigo-100 text-indigo-700',
  CKM: 'bg-pink-100 text-pink-700',
  HTN: 'bg-rose-100 text-rose-700',
  PKD: 'bg-cyan-100 text-cyan-700',
  'CKD-MBD': 'bg-amber-100 text-amber-700',
  Stone: 'bg-lime-100 text-lime-700',
  'Onco-Nephro': 'bg-fuchsia-100 text-fuchsia-700',
}

function topicBadgeClass(topic) {
  return topicColorMap[topic] || 'bg-slate-100 text-slate-600'
}

const statusBadgeClass = computed(() => {
  const s = concept.value?.synthesis_status
  if (s === 'approved') return 'bg-green-100 text-green-700'
  if (s === 'pending_review') return 'bg-orange-100 text-orange-700'
  return 'bg-yellow-100 text-yellow-700'
})

const statusLabel = computed(() => {
  const s = concept.value?.synthesis_status
  if (s === 'approved') return 'Approved'
  if (s === 'pending_review') return 'Pending'
  return 'Draft'
})

const sourceTabs = computed(() => [
  { key: 'article', label: 'Articles', icon: '\uD83D\uDCC4', count: (linksByType.value.article || []).length },
  { key: 'guideline', label: 'Guidelines', icon: '\uD83D\uDCCB', count: (linksByType.value.guideline || []).length },
  { key: 'trial', label: 'Trials', icon: '\uD83E\uDDEA', count: (linksByType.value.trial || []).length },
  { key: 'drug', label: 'Drugs', icon: '\uD83D\uDC8A', count: (linksByType.value.drug || []).length },
])

const activeSourceLinks = computed(() => {
  return linksByType.value[activeSourceTab.value] || []
})
</script>
