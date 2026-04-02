<template>
  <div v-if="article" class="bg-white rounded-xl border border-slate-200 overflow-hidden">
    <!-- 標題區 -->
    <div class="bg-gradient-to-r from-blue-50 to-indigo-50 p-5 border-b border-slate-100">
      <div class="flex items-center gap-2 mb-3 flex-wrap">
        <span
          class="text-[10px] font-bold px-2 py-0.5 rounded-full"
          :class="levelBadgeClass"
        >
          {{ article.evidence_level }}
        </span>
        <span class="text-[10px] font-medium px-2 py-0.5 rounded-full bg-purple-100 text-purple-700">
          {{ article.evidence_group }}
        </span>
        <span
          v-for="topic in article.topics"
          :key="topic"
          class="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-200 text-slate-600"
        >
          {{ topic }}
        </span>
      </div>
      <h2 class="text-lg font-bold text-slate-900 mb-1">
        {{ article.title_zh }}
      </h2>
      <p class="text-xs text-slate-500 mb-2">{{ article.title }}</p>
      <p class="text-xs text-slate-400">
        {{ article.journal }} · {{ article.pubdate }}
      </p>
      <p v-if="article.study_design" class="text-sm text-slate-600 mt-2">
        {{ article.study_design }}
      </p>
    </div>

    <div class="p-5 space-y-5">
      <!-- 摘要重點 -->
      <Section title="摘要重點" color="emerald">
        <ul class="space-y-1.5">
          <li
            v-for="(point, i) in article.summary_points"
            :key="i"
            class="text-sm text-slate-700 leading-relaxed pl-4 relative before:content-[''] before:absolute before:left-0 before:top-2 before:w-1.5 before:h-1.5 before:rounded-full before:bg-emerald-400"
            v-html="formatBold(point)"
          />
        </ul>
      </Section>

      <!-- PICO -->
      <Section title="PICO" color="blue">
        <div class="grid grid-cols-[40px_1fr] gap-x-3 gap-y-2">
          <template v-for="key in ['P', 'I', 'C', 'O']" :key="key">
            <span class="text-sm font-bold text-blue-600">{{ key }}</span>
            <span class="text-sm text-slate-700 leading-relaxed">
              {{ article.pico?.[key] || '—' }}
            </span>
          </template>
        </div>
      </Section>

      <!-- 臨床重點 -->
      <Section title="臨床重點" color="amber">
        <ol class="space-y-1.5">
          <li
            v-for="(item, i) in article.clinical_takeaways"
            :key="i"
            class="text-sm text-slate-700 leading-relaxed flex gap-2"
          >
            <span class="text-amber-600 font-bold shrink-0">{{ i + 1 }}.</span>
            <span>{{ item }}</span>
          </li>
        </ol>
      </Section>

      <!-- 限制 -->
      <Section title="限制與偏差" color="red">
        <ul class="space-y-1.5">
          <li
            v-for="(item, i) in article.limitations"
            :key="i"
            class="text-sm text-slate-700 leading-relaxed flex gap-2"
          >
            <span class="text-red-500 shrink-0">⚠</span>
            <span>{{ item }}</span>
          </li>
        </ul>
      </Section>

      <!-- 建議下一步 -->
      <Section v-if="article.next_steps" title="建議下一步" color="purple">
        <p class="text-sm text-slate-700 leading-relaxed">
          {{ article.next_steps }}
        </p>
      </Section>

      <!-- 底部操作 -->
      <div class="flex items-center gap-3 pt-3 border-t border-slate-100 flex-wrap">
        <button
          class="flex-1 py-2.5 rounded-lg text-sm font-medium transition-colors"
          :class="
            isSaved
              ? 'bg-amber-100 text-amber-700 hover:bg-amber-200'
              : 'bg-blue-50 text-blue-700 hover:bg-blue-100'
          "
          @click="$emit('toggleSave', article)"
        >
          {{ isSaved ? '✅ 已收藏' : '☆ 加入收藏知識庫' }}
        </button>
        <a
          :href="article.link"
          target="_blank"
          rel="noreferrer"
          class="px-4 py-2.5 rounded-lg text-sm font-medium bg-slate-100 text-slate-600 hover:bg-slate-200 transition-colors"
        >
          PubMed ↗
        </a>
      </div>
      <div class="flex items-center gap-2 pt-2">
        <button
          class="flex-1 py-2 rounded-lg text-xs font-medium bg-blue-50 text-blue-600 hover:bg-blue-100 transition-colors"
          @click="$emit('deepConsult', article)"
        >
          🔍 深入問答
        </button>
        <button
          class="flex-1 py-2 rounded-lg text-xs font-medium bg-purple-50 text-purple-600 hover:bg-purple-100 transition-colors"
          @click="$emit('saveToNotes', article)"
        >
          📝 存入筆記
        </button>
        <button
          class="flex-1 py-2 rounded-lg text-xs font-medium bg-orange-50 text-orange-600 hover:bg-orange-100 transition-colors"
          @click="$emit('sendToTeach', article)"
        >
          🎓 加到 Teach
        </button>
      </div>
    </div>
  </div>

  <!-- 空狀態 -->
  <div v-else class="bg-white rounded-xl border border-slate-200 p-10 text-center text-slate-400">
    <div class="text-4xl mb-3">📄</div>
    <p>點擊左側文章查看詳細內容</p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import Section from './DetailSection.vue'

const props = defineProps({
  article: { type: Object, default: null },
  isSaved: { type: Boolean, default: false },
})

defineEmits(['toggleSave', 'deepConsult', 'saveToNotes', 'sendToTeach'])

const levelBadgeClass = computed(() => {
  const lv = props.article?.evidence_level
  if (lv === 'Level 1') return 'bg-red-100 text-red-700'
  if (lv === 'Level 2') return 'bg-blue-100 text-blue-700'
  if (lv === 'Level 3') return 'bg-amber-100 text-amber-700'
  return 'bg-slate-100 text-slate-600'
})

const formatBold = (text) => {
  if (!text) return ''
  return text.replace(
    /\*\*(.*?)\*\*/g,
    '<strong class="text-red-600 font-semibold">$1</strong>'
  )
}
</script>
