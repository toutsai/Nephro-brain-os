<script setup>
const props = defineProps({
  chapters: {
    type: Array,
    required: true
  },
  selectedChapter: {
    type: Object,
    default: null
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['select'])

function isSelected(chapter) {
  return props.selectedChapter && props.selectedChapter.id === chapter.id
}
</script>

<template>
  <div class="overflow-y-auto bg-white divide-y divide-slate-100">
    <!-- Loading state -->
    <div v-if="loading" class="flex items-center justify-center py-8">
      <svg
        class="animate-spin h-6 w-6 text-blue-500"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
      >
        <circle
          class="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          stroke-width="4"
        />
        <path
          class="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
        />
      </svg>
    </div>

    <!-- Empty state -->
    <div
      v-else-if="chapters.length === 0"
      class="text-center text-sm text-slate-400 py-8"
    >
      尚無章節資料
    </div>

    <!-- Chapter list -->
    <template v-else>
      <button
        v-for="chapter in chapters"
        :key="chapter.id"
        class="w-full flex items-center gap-3 px-3 py-2.5 text-left transition-colors"
        :class="isSelected(chapter) ? 'bg-blue-50 ring-1 ring-blue-200' : 'hover:bg-slate-50'"
        @click="emit('select', chapter)"
      >
        <span
          class="flex-shrink-0 flex items-center justify-center w-6 h-6 rounded-full text-[11px] font-bold"
          :class="isSelected(chapter) ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-500'"
        >
          {{ chapter.chapter_number }}
        </span>
        <span
          class="text-sm"
          :class="isSelected(chapter) ? 'font-bold text-slate-900' : 'text-slate-600'"
        >
          {{ chapter.chapter_title_zh || chapter.chapter_title }}
        </span>
      </button>
    </template>
  </div>
</template>
