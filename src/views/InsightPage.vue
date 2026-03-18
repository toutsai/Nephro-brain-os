<template>
  <div class="h-screen flex flex-col bg-slate-50">
    <!-- Header -->
    <header class="bg-white border-b border-slate-200 sticky top-0 z-20 shrink-0">
      <div class="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <router-link to="/" class="text-lg font-bold text-slate-800 hover:text-blue-600 transition-colors">
            NB — OS
          </router-link>
          <span class="text-slate-300">|</span>
          <div>
            <h1 class="text-sm font-bold text-slate-800">NB Insight</h1>
            <p class="text-[10px] text-slate-400">每日文獻智慧引擎</p>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <div class="text-xs text-slate-400">
            {{ articleCount }} 篇文獻
          </div>
          <router-link
            to="/consult"
            class="text-xs px-3 py-1.5 bg-slate-100 hover:bg-blue-50 text-slate-500 hover:text-blue-600 rounded-lg transition-colors"
          >
            💬 Consult
          </router-link>
          <router-link
            to="/notes"
            class="text-xs px-3 py-1.5 bg-slate-100 hover:bg-purple-50 text-slate-500 hover:text-purple-600 rounded-lg transition-colors"
          >
            📝 Notes
          </router-link>
        </div>
      </div>

      <!-- Tab bar -->
      <div class="max-w-7xl mx-auto px-4">
        <nav class="flex gap-1 -mb-px">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            class="px-4 py-2.5 text-sm font-medium border-b-2 transition-colors"
            :class="
              activeTab === tab.key
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            "
            @click="activeTab = tab.key; selectedArticle = null"
          >
            {{ tab.label }}
            <span
              class="ml-1.5 text-[10px] px-1.5 py-0.5 rounded-full"
              :class="
                activeTab === tab.key
                  ? 'bg-blue-100 text-blue-700'
                  : 'bg-slate-100 text-slate-500'
              "
            >
              {{ tab.count }}
            </span>
          </button>
        </nav>
      </div>
    </header>

    <!-- Loading -->
    <div v-if="loading" class="flex-1 flex items-center justify-center">
      <div class="text-center">
        <div class="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p class="text-sm text-slate-500">載入文獻中...</p>
      </div>
    </div>

    <!-- Main content -->
    <main v-else class="flex-1 overflow-hidden max-w-7xl mx-auto w-full px-4 py-4">

      <!-- 收藏知識庫 tab -->
      <template v-if="activeTab === 'collection'">
        <div v-if="!savedArticles.length" class="text-center py-16 text-slate-400">
          <div class="text-4xl mb-3">📚</div>
          <p class="text-sm">還沒有收藏的文獻</p>
          <p class="text-xs mt-1">點擊文章卡片上的「收藏」按鈕開始收集</p>
        </div>

        <!-- 桌面版：左右獨立捲軸 -->
        <div v-else class="hidden lg:grid lg:grid-cols-[1fr_1fr] gap-4 h-full">
          <div class="overflow-y-auto pr-2 space-y-3 pb-4">
            <ArticleCard
              v-for="article in savedArticles"
              :key="article.id"
              :article="article"
              :selected="selectedArticle?.id === article.id"
              :is-saved="true"
              @select="selectedArticle = $event"
              @toggle-save="toggleSave"
            />
          </div>
          <div class="overflow-y-auto pl-2 pb-4">
            <ArticleDetail
              :article="selectedArticle"
              :is-saved="selectedArticle ? isSaved(selectedArticle.id) : false"
              @toggle-save="toggleSave"
            />
          </div>
        </div>

        <!-- 手機版：單欄 -->
        <div v-if="savedArticles.length" class="lg:hidden space-y-3 overflow-y-auto h-full pb-4">
          <ArticleCard
            v-for="article in savedArticles"
            :key="article.id"
            :article="article"
            :selected="selectedArticle?.id === article.id"
            :is-saved="true"
            @select="selectedArticle = $event"
            @toggle-save="toggleSave"
          />
        </div>
      </template>

      <!-- 文獻分區 tabs (ESRD/HD, AKI, CKD) -->
      <template v-else>
        <div v-if="!currentArticles.length" class="text-center py-16 text-slate-400">
          <div class="text-4xl mb-3">📭</div>
          <p class="text-sm">此分區目前沒有文獻</p>
        </div>

        <!-- 桌面版：左右獨立捲軸 -->
        <div v-else class="hidden lg:grid lg:grid-cols-[1fr_1fr] gap-4 h-full">
          <div class="overflow-y-auto pr-2 space-y-3 pb-4">
            <ArticleCard
              v-for="article in currentArticles"
              :key="article.id"
              :article="article"
              :is-new="isToday(article.created_at)"
              :selected="selectedArticle?.id === article.id"
              :is-saved="isSaved(article.id)"
              @select="selectedArticle = $event"
              @toggle-save="toggleSave"
            />
          </div>
          <div class="overflow-y-auto pl-2 pb-4">
            <ArticleDetail
              :article="selectedArticle"
              :is-saved="selectedArticle ? isSaved(selectedArticle.id) : false"
              @toggle-save="toggleSave"
            />
          </div>
        </div>

        <!-- 手機版：單欄 -->
        <div v-if="currentArticles.length" class="lg:hidden space-y-3 overflow-y-auto h-full pb-4">
          <ArticleCard
            v-for="article in currentArticles"
            :key="article.id"
            :article="article"
            :is-new="isToday(article.created_at)"
            :selected="selectedArticle?.id === article.id"
            :is-saved="isSaved(article.id)"
            @select="selectedArticle = $event"
            @toggle-save="toggleSave"
          />
        </div>

        <!-- 手機版：點擊文章後彈出詳細 -->
        <Teleport to="body">
          <div
            v-if="selectedArticle && isMobile"
            class="fixed inset-0 bg-black/50 z-30 lg:hidden"
            @click="selectedArticle = null"
          >
            <div
              class="absolute inset-x-0 bottom-0 max-h-[85vh] overflow-y-auto bg-white rounded-t-2xl"
              @click.stop
            >
              <div class="sticky top-0 bg-white p-3 border-b border-slate-100 flex justify-between items-center">
                <span class="text-sm font-medium text-slate-600">文獻詳情</span>
                <button
                  class="text-slate-400 hover:text-slate-600 text-lg"
                  @click="selectedArticle = null"
                >
                  ✕
                </button>
              </div>
              <ArticleDetail
                :article="selectedArticle"
                :is-saved="isSaved(selectedArticle.id)"
                @toggle-save="toggleSave"
              />
            </div>
          </div>
        </Teleport>
      </template>
    </main>

    <!-- Selection toolbar -->
    <SelectionToolbar
      source-type="insight"
      :source-meta="selectedArticle ? { title: selectedArticle.title, pmid: selectedArticle.pmid } : {}"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useArticles } from '../composables/useArticles.js'
import { useCollection } from '../composables/useCollection.js'
import ArticleCard from '../components/ArticleCard.vue'
import ArticleDetail from '../components/ArticleDetail.vue'
import SelectionToolbar from '../components/SelectionToolbar.vue'

// Data
const {
  articles,
  esrdArticles,
  akiArticles,
  ckdArticles,
  journalArticles,
  loading,
  isToday,
  unsubscribe: unsubArticles,
} = useArticles()

const {
  savedArticles,
  toggleSave,
  isSaved,
  unsubscribe: unsubCollection,
} = useCollection()

// UI state
const activeTab = ref('ESRD/HD')
const selectedArticle = ref(null)

// Mobile detection
const isMobile = ref(false)
const checkMobile = () => {
  isMobile.value = window.innerWidth < 1024
}
onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
})
onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
  unsubArticles()
  unsubCollection()
})

// Tabs config
const tabs = computed(() => [
  { key: 'ESRD/HD', label: 'ESRD / HD', count: esrdArticles.value.length },
  { key: 'AKI', label: 'AKI', count: akiArticles.value.length },
  { key: 'CKD', label: 'CKD', count: ckdArticles.value.length },
  { key: 'journal', label: '📰 期刊', count: journalArticles.value.length },
  { key: 'collection', label: '✅ 收藏庫', count: savedArticles.value.length },
])

const currentArticles = computed(() => {
  if (activeTab.value === 'ESRD/HD') return esrdArticles.value
  if (activeTab.value === 'AKI') return akiArticles.value
  if (activeTab.value === 'CKD') return ckdArticles.value
  if (activeTab.value === 'journal') return journalArticles.value
  return []
})

const articleCount = computed(() => articles.value.length)
</script>