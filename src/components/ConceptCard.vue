<template>
  <div
    class="group relative bg-white rounded-xl border border-slate-200 p-4 transition-all cursor-pointer hover:shadow-md"
    @click="$emit('select', concept)"
  >
    <!-- Top badges -->
    <div class="flex items-center gap-2 mb-2 flex-wrap">
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

    <!-- English title -->
    <h4 class="text-xs text-slate-400 line-clamp-1 mb-1">
      {{ concept.title }}
    </h4>

    <!-- Chinese title -->
    <h3 class="text-sm font-bold text-slate-800 mb-2 line-clamp-2">
      {{ concept.title_zh || concept.title }}
    </h3>

    <!-- Aliases -->
    <p
      v-if="concept.aliases?.length"
      class="text-[10px] text-slate-400 line-clamp-1 mb-2"
    >
      {{ concept.aliases.join(', ') }}
    </p>

    <!-- Link counts -->
    <div class="flex items-center gap-3 mt-3 pt-2 border-t border-slate-100">
      <span
        v-if="linkCount('article')"
        class="text-[10px] text-slate-500 flex items-center gap-0.5"
        title="Articles"
      >
        <span>&#x1F4C4;</span> {{ linkCount('article') }}
      </span>
      <span
        v-if="linkCount('guideline')"
        class="text-[10px] text-slate-500 flex items-center gap-0.5"
        title="Guidelines"
      >
        <span>&#x1F4CB;</span> {{ linkCount('guideline') }}
      </span>
      <span
        v-if="linkCount('trial')"
        class="text-[10px] text-slate-500 flex items-center gap-0.5"
        title="Trials"
      >
        <span>&#x1F9EA;</span> {{ linkCount('trial') }}
      </span>
      <span
        v-if="linkCount('drug')"
        class="text-[10px] text-slate-500 flex items-center gap-0.5"
        title="Drugs"
      >
        <span>&#x1F48A;</span> {{ linkCount('drug') }}
      </span>
      <span
        v-if="totalLinks === 0"
        class="text-[10px] text-slate-400 italic"
      >
        No linked sources yet
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  concept: { type: Object, required: true },
})

defineEmits(['select'])

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
  const s = props.concept.synthesis_status
  if (s === 'approved') return 'bg-green-100 text-green-700'
  if (s === 'pending_review') return 'bg-orange-100 text-orange-700'
  return 'bg-yellow-100 text-yellow-700' // draft or undefined
})

const statusLabel = computed(() => {
  const s = props.concept.synthesis_status
  if (s === 'approved') return 'Approved'
  if (s === 'pending_review') return 'Pending'
  return 'Draft'
})

function linkCount(type) {
  return props.concept.link_counts?.[type] || 0
}

const totalLinks = computed(() => {
  const lc = props.concept.link_counts
  if (!lc) return 0
  return Object.values(lc).reduce((sum, v) => sum + (v || 0), 0)
})
</script>
