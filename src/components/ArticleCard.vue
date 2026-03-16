<template>
  <div
    class="group relative rounded-xl border p-4 transition-all cursor-pointer hover:shadow-md"
    :class="[
      isNew
        ? 'bg-gradient-to-r from-emerald-50 to-white border-emerald-200'
        : 'bg-white border-slate-200',
      selected ? 'ring-2 ring-blue-400 shadow-md' : '',
    ]"
    @click="$emit('select', article)"
  >
    <!-- 頂部 badges -->
    <div class="flex items-center gap-2 mb-2 flex-wrap">
      <span
        v-if="isNew"
        class="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-emerald-500 text-white animate-pulse"
      >
        NEW
      </span>
      <span
        class="text-[10px] font-bold px-2 py-0.5 rounded-full"
        :class="levelBadgeClass"
      >
        {{ article.evidence_level }}
      </span>
      <span
        v-for="topic in article.topics"
        :key="topic"
        class="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-600"
      >
        {{ topic }}
      </span>
      <span class="text-[10px] text-slate-400 ml-auto">
        {{ article.pubdate }}
      </span>
    </div>

    <!-- 英文標題 -->
    <h4 class="text-xs text-slate-400 line-clamp-1 mb-1">
      {{ article.title }}
    </h4>

    <!-- 中文標題 -->
    <h3 class="text-sm font-bold text-slate-800 mb-2 line-clamp-2">
      {{ article.title_zh || '翻譯中...' }}
    </h3>

    <!-- 摘要重點第一條 -->
    <p
      v-if="article.summary_points?.length"
      class="text-xs text-slate-600 line-clamp-2 leading-relaxed"
      v-html="formatBold(article.summary_points[0])"
    />

    <!-- 底部資訊 -->
    <div class="flex items-center justify-between mt-3 pt-2 border-t border-slate-100">
      <span class="text-[10px] text-slate-400">
        {{ article.journal }}
      </span>
      <div class="flex items-center gap-2">
        <!-- 收藏按鈕 -->
        <button
          class="text-xs px-2 py-0.5 rounded transition-colors"
          :class="
            isSaved
              ? 'bg-amber-100 text-amber-700'
              : 'text-slate-400 hover:bg-amber-50 hover:text-amber-600'
          "
          @click.stop="$emit('toggleSave', article)"
        >
          {{ isSaved ? '✅ 已收藏' : '☆ 收藏' }}
        </button>
        <!-- PubMed 連結 -->
        <a
          :href="article.link"
          target="_blank"
          rel="noreferrer"
          class="text-[10px] text-slate-400 hover:text-blue-600"
          @click.stop
        >
          PubMed ↗
        </a>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  article: { type: Object, required: true },
  isNew: { type: Boolean, default: false },
  selected: { type: Boolean, default: false },
  isSaved: { type: Boolean, default: false },
})

defineEmits(['select', 'toggleSave'])

const levelBadgeClass = computed(() => {
  const lv = props.article.evidence_level
  if (lv === 'Level 1') return 'bg-red-100 text-red-700'
  if (lv === 'Level 2') return 'bg-blue-100 text-blue-700'
  if (lv === 'Level 3') return 'bg-amber-100 text-amber-700'
  return 'bg-slate-100 text-slate-600'
})

const formatBold = (text) => {
  if (!text) return ''
  return text.replace(/\*\*(.*?)\*\*/g, '<strong class="text-red-600">$1</strong>')
}
</script>
