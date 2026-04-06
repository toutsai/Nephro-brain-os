<template>
  <div class="h-full flex flex-col bg-white rounded-xl border border-slate-200 overflow-hidden">
    <!-- Header -->
    <div class="bg-gradient-to-r from-blue-50 to-indigo-50 px-4 py-3 border-b border-slate-100 shrink-0">
      <div class="flex items-center justify-between mb-1">
        <div class="flex items-center gap-2">
          <span
            class="text-[10px] font-bold px-2 py-0.5 rounded-full"
            :class="guideline.org === 'KDIGO' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'"
          >
            {{ guideline.org }}
          </span>
          <span class="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">
            {{ guideline.year }}
          </span>
        </div>
        <button
          class="text-xs text-slate-400 hover:text-slate-600 transition-colors"
          @click="$emit('back')"
        >
          ← 返回
        </button>
      </div>
      <h2 class="text-sm font-bold text-slate-900 leading-snug">
        {{ guideline.title_zh || guideline.title }}
      </h2>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex-1 flex items-center justify-center">
      <div class="text-center">
        <div class="w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
        <p class="text-xs text-slate-400">載入章節中...</p>
      </div>
    </div>

    <!-- No chapters -->
    <div v-else-if="!chapters.length" class="flex-1 flex items-center justify-center p-6">
      <div class="text-center text-slate-400">
        <p class="text-sm mb-1">尚無章節內容</p>
        <p class="text-xs">需先執行 process_guideline_content.py 解析此指引</p>
      </div>
    </div>

    <!-- Content area -->
    <div v-else class="flex-1 flex overflow-hidden">
      <!-- Chapter nav (desktop) -->
      <div class="hidden lg:block w-48 shrink-0 border-r border-slate-100 overflow-y-auto">
        <GuidelineChapterNav
          :chapters="chapters"
          :selected-chapter="selectedChapter"
          @select="selectChapter"
        />
      </div>

      <!-- Chapter nav (mobile: horizontal pills) -->
      <div class="lg:hidden px-3 py-2 border-b border-slate-100 shrink-0 overflow-x-auto flex gap-1.5">
        <button
          v-for="ch in chapters"
          :key="ch.id"
          class="shrink-0 px-3 py-1.5 text-xs rounded-full border transition-colors whitespace-nowrap"
          :class="
            selectedChapter?.id === ch.id
              ? 'border-blue-400 bg-blue-50 text-blue-700 font-medium'
              : 'border-slate-200 text-slate-500 hover:border-slate-300'
          "
          @click="selectChapter(ch)"
        >
          Ch.{{ ch.chapter_number }}
        </button>
      </div>

      <!-- Chapter content -->
      <div class="flex-1 overflow-y-auto p-4 space-y-5">
        <template v-if="selectedChapter">
          <!-- Chapter title -->
          <div>
            <h3 class="text-base font-bold text-slate-900 mb-1">
              {{ selectedChapter.chapter_title_zh || selectedChapter.chapter_title }}
            </h3>
            <p v-if="selectedChapter.chapter_title_zh && selectedChapter.chapter_title" class="text-xs text-slate-400">
              {{ selectedChapter.chapter_title }}
            </p>
          </div>

          <!-- Content (rendered markdown) -->
          <div
            v-if="selectedChapter.content_zh"
            class="border-l-4 border-emerald-400 pl-4"
          >
            <div
              ref="contentEl"
              class="prose-chapter text-sm text-slate-700 leading-relaxed"
              v-html="renderMd(selectedChapter.content_zh)"
            />
          </div>

          <!-- Key Recommendations -->
          <div
            v-if="selectedChapter.key_recommendations && selectedChapter.key_recommendations.length"
            class="border-l-4 border-amber-400 pl-4"
          >
            <h4 class="text-sm font-bold text-slate-700 mb-3">關鍵建議</h4>
            <div class="space-y-2.5">
              <div
                v-for="(rec, i) in selectedChapter.key_recommendations"
                :key="i"
                class="bg-slate-50 rounded-lg p-3"
              >
                <div class="flex items-start gap-2">
                  <RecommendationBadge :grade="rec.grade" class="mt-0.5 shrink-0" />
                  <div class="min-w-0">
                    <p class="text-sm text-slate-800 font-medium leading-snug">{{ rec.text }}</p>
                    <p v-if="rec.description" class="text-xs text-slate-500 mt-1">{{ rec.description }}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Treatment flowchart (Mermaid) -->
          <div
            v-if="selectedChapter.flowchart_mermaid"
            class="border-l-4 border-blue-400 pl-4"
          >
            <h4 class="text-sm font-bold text-slate-700 mb-3">診斷/治療流程</h4>
            <div
              ref="flowchartEl"
              class="bg-slate-50 rounded-lg p-4 overflow-x-auto"
            >
              <pre class="mermaid text-xs">{{ selectedChapter.flowchart_mermaid }}</pre>
            </div>
          </div>

          <!-- Version diff -->
          <div
            v-if="selectedChapter.diff_from_previous"
            class="border-l-4 border-rose-400 pl-4"
          >
            <h4 class="text-sm font-bold text-slate-700 mb-3">與前版差異</h4>
            <div
              ref="diffEl"
              class="prose-chapter text-sm text-slate-700 leading-relaxed bg-rose-50/50 rounded-lg p-3"
              v-html="renderMd(selectedChapter.diff_from_previous)"
            />
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, toRef } from 'vue'
import { useGuidelineChapters } from '../composables/useGuidelineChapters.js'
import { renderMd } from '../utils/renderMarkdown.js'
import { renderMermaidIn } from '../composables/useMermaid.js'
import GuidelineChapterNav from './GuidelineChapterNav.vue'
import RecommendationBadge from './RecommendationBadge.vue'

const props = defineProps({
  guideline: { type: Object, required: true },
})

defineEmits(['back'])

const guidelineId = ref(null)

// Find the guideline's Firestore doc ID
watch(
  () => props.guideline,
  (g) => {
    guidelineId.value = g?.id || null
  },
  { immediate: true }
)

const {
  chapters,
  loading,
  selectedChapter,
  selectChapter,
} = useGuidelineChapters(guidelineId)

// Refs for rendering
const contentEl = ref(null)
const flowchartEl = ref(null)
const diffEl = ref(null)

// Re-render Mermaid when chapter changes
watch(
  () => selectedChapter.value,
  async () => {
    await nextTick()
    if (flowchartEl.value) {
      renderMermaidIn(flowchartEl.value)
    }
  }
)
</script>

<style scoped>
.prose-chapter :deep(h2) {
  font-size: 14px;
  font-weight: 700;
  color: #1e293b;
  margin-top: 16px;
  margin-bottom: 8px;
}
.prose-chapter :deep(h3) {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  margin-top: 12px;
  margin-bottom: 6px;
}
.prose-chapter :deep(ul) {
  padding-left: 18px;
  margin: 6px 0;
}
.prose-chapter :deep(li) {
  list-style: disc;
  font-size: 13px;
  margin-bottom: 4px;
}
.prose-chapter :deep(strong) {
  color: #0f172a;
}
.prose-chapter :deep(table) {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  margin: 8px 0;
}
.prose-chapter :deep(th) {
  background: #f1f5f9;
  padding: 6px 8px;
  text-align: left;
  font-weight: 600;
  border: 1px solid #e2e8f0;
}
.prose-chapter :deep(td) {
  padding: 6px 8px;
  border: 1px solid #e2e8f0;
}
</style>
