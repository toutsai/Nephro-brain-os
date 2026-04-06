<template>
  <div v-if="guideline" class="bg-white rounded-xl border border-slate-200 overflow-hidden">
    <!-- 標題區 -->
    <div class="bg-gradient-to-r from-blue-50 to-indigo-50 p-5 border-b border-slate-100">
      <div class="flex items-center gap-2 mb-3 flex-wrap">
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
      </div>
      <h2 class="text-lg font-bold text-slate-900 mb-1">
        {{ guideline.title_zh || guideline.title }}
      </h2>
      <p
        v-if="guideline.title_zh && guideline.title"
        class="text-xs text-slate-500 mb-2"
      >
        {{ guideline.title }}
      </p>
      <div v-if="guideline.topic" class="flex items-center gap-2 mt-2 flex-wrap">
        <span class="text-[10px] font-medium px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-600">
          {{ guideline.topic }}
        </span>
      </div>
    </div>

    <div class="p-5 space-y-5">
      <!-- 指引摘要 -->
      <div v-if="guideline.summary_zh" class="border-l-4 border-emerald-400 pl-4">
        <h3 class="text-sm font-bold text-slate-700 mb-2">指引摘要</h3>
        <p class="text-sm text-slate-700 leading-relaxed">
          {{ guideline.summary_zh }}
        </p>
      </div>

      <!-- 涵蓋主題 -->
      <div v-if="guideline.key_topics && guideline.key_topics.length" class="border-l-4 border-blue-400 pl-4">
        <h3 class="text-sm font-bold text-slate-700 mb-2">涵蓋主題</h3>
        <div class="flex flex-wrap gap-2">
          <span
            v-for="(topic, i) in guideline.key_topics"
            :key="i"
            class="text-xs font-medium px-2.5 py-1 rounded-full bg-blue-50 text-blue-700"
          >
            {{ topic }}
          </span>
        </div>
      </div>

      <!-- 操作按鈕 -->
      <div class="flex items-center gap-3 pt-3 border-t border-slate-100 flex-wrap">
        <a
          v-if="guideline.url"
          :href="guideline.url"
          target="_blank"
          rel="noreferrer"
          class="flex-1 py-2.5 rounded-lg text-sm font-medium text-center bg-blue-50 text-blue-700 hover:bg-blue-100 transition-colors"
        >
          前往官方頁面 ↗
        </a>
        <button
          class="flex-1 py-2.5 rounded-lg text-sm font-medium bg-slate-100 text-slate-700 hover:bg-slate-200 transition-colors"
          @click="$emit('deepConsult', guideline)"
        >
          深入問答
        </button>
        <button
          class="flex-1 py-2.5 rounded-lg text-sm font-medium bg-purple-50 text-purple-700 hover:bg-purple-100 transition-colors"
          @click="$emit('saveToNotes', guideline)"
        >
          存入 Notes
        </button>
      </div>
    </div>
  </div>

  <!-- 空狀態 -->
  <div v-else class="bg-white rounded-xl border border-slate-200 p-10 text-center text-slate-400">
    <p>點擊左側指引查看詳細內容</p>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  guideline: { type: Object, default: null },
})

defineEmits(['deepConsult', 'saveToNotes'])

const orgBadgeClass = computed(() => {
  const org = props.guideline?.org
  if (org === 'KDIGO') return 'bg-blue-100 text-blue-700'
  if (org === 'KDOQI') return 'bg-purple-100 text-purple-700'
  return 'bg-slate-100 text-slate-600'
})

const statusBadgeClass = computed(() => {
  const status = props.guideline?.status
  if (status === 'current') return 'bg-green-100 text-green-700'
  return 'bg-gray-100 text-gray-500'
})
</script>
