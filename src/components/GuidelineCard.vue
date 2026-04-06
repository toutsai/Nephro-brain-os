<template>
  <div
    class="group relative bg-white rounded-xl border border-slate-200 p-4 transition-all cursor-pointer hover:shadow-md"
    :class="selected ? 'ring-2 ring-blue-400 shadow-md' : ''"
    @click="$emit('select', guideline)"
  >
    <!-- 頂部 badges -->
    <div class="flex items-center gap-2 mb-2 flex-wrap">
      <span
        class="text-[10px] font-bold px-2 py-0.5 rounded-full"
        :class="orgBadgeClass"
      >
        {{ guideline.org }}
      </span>
      <span class="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">
        {{ guideline.year }}
      </span>
      <span
        class="text-[10px] font-medium px-2 py-0.5 rounded-full"
        :class="statusBadgeClass"
      >
        {{ guideline.status === 'current' ? 'Current' : 'Superseded' }}
      </span>
      <span
        v-if="guideline.topic"
        class="text-[10px] font-medium px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-600"
      >
        {{ guideline.topic }}
      </span>
    </div>

    <!-- 中文標題 -->
    <h3 class="text-sm font-bold text-slate-800 mb-1 line-clamp-2">
      {{ guideline.title_zh || guideline.title }}
    </h3>

    <!-- 英文標題 -->
    <p
      v-if="guideline.title_zh && guideline.title"
      class="text-xs text-slate-400 line-clamp-1 mb-2"
    >
      {{ guideline.title }}
    </p>

    <!-- 底部：外部連結 -->
    <div class="flex items-center justify-end mt-2 pt-2 border-t border-slate-100">
      <a
        v-if="guideline.url"
        :href="guideline.url"
        target="_blank"
        rel="noreferrer"
        class="text-[10px] text-slate-400 hover:text-blue-600 transition-colors"
        @click.stop
      >
        Official ↗
      </a>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  guideline: { type: Object, required: true },
  selected: { type: Boolean, default: false },
})

defineEmits(['select'])

const orgBadgeClass = computed(() => {
  const org = props.guideline.org
  if (org === 'KDIGO') return 'bg-blue-100 text-blue-700'
  if (org === 'KDOQI') return 'bg-purple-100 text-purple-700'
  return 'bg-slate-100 text-slate-600'
})

const statusBadgeClass = computed(() => {
  const status = props.guideline.status
  if (status === 'current') return 'bg-green-100 text-green-700'
  return 'bg-gray-100 text-gray-500'
})
</script>
