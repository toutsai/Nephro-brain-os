<template>
  <div class="min-h-screen bg-slate-950 text-white px-4 py-8">
    <div class="max-w-5xl mx-auto">

      <!-- Section A: Hero (compact) -->
      <div class="text-center mb-10">
        <div class="text-xs font-medium tracking-widest text-blue-400 mb-2">
          FROM LITERATURE TO INTELLIGENCE
        </div>
        <h1 class="text-3xl md:text-4xl font-bold mb-1">Nephro Brain OS</h1>
        <p class="text-sm text-slate-400">腎臟科智慧中樞的作業系統</p>
      </div>

      <!-- Section B: Quick Stats Row -->
      <div
        class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-10"
        :class="{ 'lg:grid-cols-2': !isLoggedIn }"
      >
        <!-- 今日新文獻 -->
        <div class="rounded-xl border border-slate-700 bg-slate-900 p-5 text-center">
          <div class="text-2xl mb-1">&#x1F4C4;</div>
          <div class="text-3xl font-bold text-blue-400">
            <span v-if="articlesLoading" class="text-slate-500">--</span>
            <span v-else>{{ todayArticles.length }}</span>
          </div>
          <div class="text-xs text-slate-400 mt-1">今日新文獻</div>
        </div>

        <!-- 近30日文獻 -->
        <div class="rounded-xl border border-slate-700 bg-slate-900 p-5 text-center">
          <div class="text-2xl mb-1">&#x1F4DA;</div>
          <div class="text-3xl font-bold text-blue-400">
            <span v-if="articlesLoading" class="text-slate-500">--</span>
            <span v-else>{{ articles.length }}</span>
          </div>
          <div class="text-xs text-slate-400 mt-1">近30日文獻</div>
        </div>

        <!-- 知識庫 (auth only) -->
        <div v-if="isLoggedIn" class="rounded-xl border border-slate-700 bg-slate-900 p-5 text-center">
          <div class="text-2xl mb-1">&#x1F4D6;</div>
          <div class="text-3xl font-bold text-purple-400">{{ readyBooks.length }}</div>
          <div class="text-xs text-slate-400 mt-1">知識庫 ({{ totalChunks }} chunks)</div>
        </div>

        <!-- 本月 AI (auth only) -->
        <div v-if="isLoggedIn" class="rounded-xl border border-slate-700 bg-slate-900 p-5 text-center">
          <div class="text-2xl mb-1">&#x1F916;</div>
          <div class="text-3xl font-bold text-orange-400">
            <span v-if="tokenLoading" class="text-slate-500">--</span>
            <span v-else>{{ totalCalls }}</span>
          </div>
          <div class="text-xs text-slate-400 mt-1">
            本月 AI (NT${{ monthlyCostTWD }})
          </div>
        </div>
      </div>

      <!-- Section C: Module Entry Grid -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <router-link
          v-for="mod in modules"
          :key="mod.path"
          :to="mod.path"
          :class="mod.cardClass"
          class="block rounded-xl border border-slate-700 p-5 transition-colors"
        >
          <div class="flex items-center gap-3 mb-2">
            <span class="text-2xl">{{ mod.icon }}</span>
            <span class="text-lg font-semibold">{{ mod.name }}</span>
          </div>
          <p class="text-sm text-slate-300 mb-3">{{ mod.desc }}</p>
          <div v-if="mod.stat !== null" class="text-xs text-slate-400">
            {{ mod.stat }}
          </div>
        </router-link>
      </div>

    </div>
  </div>
</template>

<script setup>
import { computed, onUnmounted } from 'vue'
import { useArticles } from '../composables/useArticles'
import { useBooks } from '../composables/useBooks'
import { useTokenUsage } from '../composables/useTokenUsage'
import { useAuth } from '../composables/useAuth'

const { isLoggedIn } = useAuth()

const {
  articles,
  todayArticles,
  loading: articlesLoading,
  unsubscribe: unsubArticles,
} = useArticles()

// Books and token usage — always call composables at top level
const {
  readyBooks,
  totalChunks,
  unsubscribe: unsubBooks,
} = useBooks()

const {
  monthlyCostTWD,
  totalCalls,
  loading: tokenLoading,
} = useTokenUsage()

onUnmounted(() => {
  unsubArticles()
  unsubBooks()
})

const modules = computed(() => [
  {
    path: '/insight',
    icon: '\uD83D\uDD0D',
    name: 'NB Insight',
    desc: '每日自動摘要腎臟科最新文獻',
    cardClass: 'bg-blue-600/20 hover:bg-blue-600/30',
    stat: articlesLoading.value ? null : `${todayArticles.value.length} 篇今日新文獻`,
  },
  {
    path: '/consult',
    icon: '\uD83D\uDCAC',
    name: 'NB Consult',
    desc: '基於知識庫的 AI 問答系統',
    cardClass: 'bg-slate-800/50 hover:bg-slate-800/70',
    stat: isLoggedIn.value ? `${readyBooks.value.length} 本知識庫` : null,
  },
  {
    path: '/notes',
    icon: '\uD83D\uDCDD',
    name: 'NB Notes',
    desc: '結構化知識整理與筆記管理',
    cardClass: 'bg-purple-700/20 hover:bg-purple-700/30',
    stat: null,
  },
  {
    path: '/teach',
    icon: '\uD83C\uDF93',
    name: 'NB Teach',
    desc: 'AI 輔助教學素材生成',
    cardClass: 'bg-orange-600/20 hover:bg-orange-600/30',
    stat: null,
  },
  {
    path: '/assist',
    icon: '\uD83C\uDFE5',
    name: 'NB Assist',
    desc: '臨床決策支援與計算工具',
    cardClass: 'bg-rose-700/20 hover:bg-rose-700/30',
    stat: null,
  },
])
</script>
