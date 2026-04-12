<template>
  <div
    class="group relative rounded-xl border p-4 transition-all cursor-pointer hover:shadow-md"
    :class="[
      'bg-white border-slate-200',
      selected ? 'ring-2 ring-blue-400 shadow-md' : '',
    ]"
    @click="$emit('select', trial)"
  >
    <!-- 頂部 badges -->
    <div class="flex items-center gap-2 mb-2 flex-wrap">
      <!-- 狀態 badge -->
      <span
        class="text-[10px] font-bold px-2 py-0.5 rounded-full"
        :class="statusBadgeClass"
      >
        {{ statusLabel }}
      </span>
      <!-- Phase badge -->
      <span
        v-if="trial.phase"
        class="text-[10px] font-medium px-2 py-0.5 rounded-full bg-purple-100 text-purple-700"
      >
        {{ trial.phase }}
      </span>
      <!-- Taiwan 標記 -->
      <span
        v-if="trial.has_taiwan_site"
        class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-rose-100 text-rose-700"
      >
        TW 試驗站點
      </span>
      <!-- Topics -->
      <span
        v-for="topic in trial.topics"
        :key="topic"
        class="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-600"
      >
        {{ topic }}
      </span>
    </div>

    <!-- 英文標題 -->
    <h4 class="text-xs text-slate-400 line-clamp-1 mb-1">
      {{ trial.title }}
    </h4>

    <!-- 中文標題 -->
    <h3 class="text-sm font-bold text-slate-800 mb-2 line-clamp-2">
      {{ trial.title_zh || trial.title }}
    </h3>

    <!-- 摘要 -->
    <p
      v-if="trial.summary_zh"
      class="text-xs text-slate-600 line-clamp-2 leading-relaxed"
    >
      {{ trial.summary_zh }}
    </p>

    <!-- 底部資訊 -->
    <div class="flex items-center justify-between mt-3 pt-2 border-t border-slate-100">
      <div class="flex items-center gap-3">
        <span v-if="trial.sponsor" class="text-[10px] text-slate-400 truncate max-w-[180px]">
          {{ trial.sponsor }}
        </span>
        <span v-if="trial.enrollment" class="text-[10px] text-slate-400">
          N={{ trial.enrollment }}
        </span>
      </div>
      <a
        :href="trial.link"
        target="_blank"
        rel="noreferrer"
        class="text-[10px] text-slate-400 hover:text-blue-600"
        @click.stop
      >
        ClinicalTrials.gov ↗
      </a>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  trial: { type: Object, required: true },
  selected: { type: Boolean, default: false },
})

defineEmits(['select'])

const statusBadgeClass = computed(() => {
  const s = props.trial.status
  if (s === 'RECRUITING') return 'bg-emerald-100 text-emerald-700'
  if (s === 'ACTIVE_NOT_RECRUITING') return 'bg-blue-100 text-blue-700'
  return 'bg-slate-100 text-slate-600'
})

const statusLabel = computed(() => {
  const s = props.trial.status
  if (s === 'RECRUITING') return 'Recruiting'
  if (s === 'ACTIVE_NOT_RECRUITING') return 'Active'
  return s || 'Unknown'
})
</script>
