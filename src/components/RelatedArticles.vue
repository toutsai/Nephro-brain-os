<template>
  <div v-if="articles.length > 0" class="border border-slate-200 rounded-xl bg-slate-50 overflow-hidden">
    <!-- Header -->
    <div class="px-4 py-2.5 border-b border-slate-200 flex items-center gap-2">
      <span class="w-2 h-2 rounded-full bg-blue-500 shrink-0"></span>
      <span class="text-sm font-semibold text-slate-700">相關文獻</span>
      <span class="text-[10px] text-slate-400 ml-auto">{{ articles.length }} 篇</span>
    </div>

    <!-- Article list (scrollable) -->
    <ul class="max-h-[320px] overflow-y-auto divide-y divide-slate-100">
      <li
        v-for="article in articles.slice(0, 5)"
        :key="article.id"
        class="px-4 py-3 hover:bg-white transition-colors cursor-pointer"
        @click="$emit('navigate', article)"
      >
        <!-- Title -->
        <p class="text-sm font-medium text-slate-800 leading-snug line-clamp-1">
          {{ article.title_zh || article.title }}
        </p>

        <!-- Journal + Date -->
        <p class="text-[10px] text-slate-400 mt-1 truncate">
          <span v-if="article.journal">{{ article.journal }}</span>
          <span v-if="article.journal && article.pubdate"> · </span>
          <span v-if="article.pubdate">{{ article.pubdate }}</span>
        </p>

        <!-- Topic badges -->
        <div v-if="article.topics && article.topics.length" class="flex flex-wrap gap-1 mt-1.5">
          <span
            v-for="topic in article.topics"
            :key="topic"
            class="text-[10px] font-medium px-1.5 py-0.5 rounded-full"
            :class="topicBadgeClass(topic)"
          >
            {{ topic }}
          </span>
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup>
defineProps({
  articles: {
    type: Array,
    required: true,
  },
})

defineEmits(['navigate'])

const TOPIC_COLORS = {
  'ESRD/HD':      'bg-red-100 text-red-700',
  'AKI':          'bg-orange-100 text-orange-700',
  'CKD':          'bg-blue-100 text-blue-700',
  'GN':           'bg-purple-100 text-purple-700',
  'Transplant':   'bg-teal-100 text-teal-700',
  'Electrolyte':  'bg-amber-100 text-amber-700',
  'PD':           'bg-cyan-100 text-cyan-700',
  'CKM':          'bg-rose-100 text-rose-700',
  'HTN':          'bg-indigo-100 text-indigo-700',
  'PKD':          'bg-lime-100 text-lime-700',
  'CKD-MBD':      'bg-yellow-100 text-yellow-700',
  'Stone':        'bg-emerald-100 text-emerald-700',
  'Onco-Nephro':  'bg-fuchsia-100 text-fuchsia-700',
}

function topicBadgeClass(topic) {
  return TOPIC_COLORS[topic] || 'bg-slate-100 text-slate-600'
}
</script>
