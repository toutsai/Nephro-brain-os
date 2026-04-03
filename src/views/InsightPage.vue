<template>
  <div class="h-[calc(100dvh-44px)] flex flex-col bg-slate-50 overflow-hidden pb-14 sm:pb-0">
    <!-- Header -->
    <header class="bg-white border-b border-slate-200 shrink-0">
      <div class="px-4 py-2 flex items-center justify-between">
        <div class="flex items-center gap-2">
          <h1 class="text-sm font-bold text-slate-800">NB Insight</h1>
          <span class="text-[10px] text-slate-400">每日文獻智慧引擎</span>
        </div>
        <div class="text-xs text-slate-400">
          {{ articleCount }} 篇文獻
        </div>
      </div>

      <!-- 手機版：本日快訊按鈕 -->
      <div v-if="isMobile && todayArticles.length" class="px-4 py-1.5 bg-emerald-50 border-b border-emerald-100 lg:hidden">
        <button
          class="w-full flex items-center justify-between text-xs font-semibold text-emerald-700"
          @click="showDailyBrief = true"
        >
          <span>📰 本日快訊 ({{ todayArticles.length }})</span>
          <span class="text-[10px]">→</span>
        </button>
      </div>

      <!-- 手機版：橫向 Tab bar (下拉選單) -->
      <div class="lg:hidden px-4 pb-2">
        <select
          v-model="activeTab"
          class="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          @change="selectedArticle = null"
        >
          <option v-for="tab in tabs" :key="tab.key" :value="tab.key">
            {{ tab.label }} ({{ tab.count }})
          </option>
        </select>
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
    <main v-else class="flex-1 overflow-hidden w-full">

      <!-- 桌面版：三欄式 (sidebar + 文章列表 + 文章詳情) -->
      <div class="hidden lg:grid lg:grid-cols-[180px_1fr_1fr] h-full">

        <!-- 左側 Sidebar -->
        <aside class="border-r border-slate-200 bg-white overflow-y-auto py-2">
          <!-- 本日快訊按鈕 -->
          <div v-if="todayArticles.length" class="px-3 pb-2 mb-2 border-b border-slate-100">
            <button
              class="w-full flex items-center justify-between py-1.5 text-xs font-semibold text-emerald-700 hover:bg-emerald-50 rounded-lg px-1 transition-colors"
              @click="showDailyBrief = true"
            >
              <span>📰 本日快訊 ({{ todayArticles.length }})</span>
              <span class="text-[10px]">→</span>
            </button>
          </div>

          <div class="px-2 mb-1">
            <p class="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-2 py-1">主題分類</p>
          </div>
          <button
            v-for="tab in topicTabs"
            :key="tab.key"
            class="w-full flex items-center justify-between px-3 py-2 text-sm transition-colors rounded-lg mx-1"
            :class="
              activeTab === tab.key
                ? 'bg-blue-50 text-blue-700 font-medium'
                : 'text-slate-600 hover:bg-slate-50 hover:text-slate-800'
            "
            style="width: calc(100% - 8px)"
            @click="activeTab = tab.key; selectedArticle = null"
          >
            <span class="truncate">{{ tab.label }}</span>
            <span class="flex items-center gap-1">
              <span
                v-if="tab.newCount"
                class="text-[10px] px-1.5 py-0.5 rounded-full bg-red-500 text-white font-bold"
              >
                {{ tab.newCount }}
              </span>
              <span
                class="text-[10px] px-1.5 py-0.5 rounded-full"
                :class="
                  activeTab === tab.key
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-slate-100 text-slate-500'
                "
              >
                {{ tab.count }}
              </span>
            </span>
          </button>

          <div class="mx-3 my-2 border-t border-slate-100" />

          <div class="px-2 mb-1">
            <p class="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-2 py-1">其他</p>
          </div>
          <button
            v-for="tab in specialTabs"
            :key="tab.key"
            class="w-full flex items-center justify-between px-3 py-2 text-sm transition-colors rounded-lg mx-1"
            :class="
              activeTab === tab.key
                ? 'bg-blue-50 text-blue-700 font-medium'
                : 'text-slate-600 hover:bg-slate-50 hover:text-slate-800'
            "
            style="width: calc(100% - 8px)"
            @click="activeTab = tab.key; selectedArticle = null"
          >
            <span class="truncate">{{ tab.label }}</span>
            <span class="flex items-center gap-1">
              <span
                v-if="tab.newCount"
                class="text-[10px] px-1.5 py-0.5 rounded-full bg-red-500 text-white font-bold"
              >
                {{ tab.newCount }}
              </span>
              <span
                class="text-[10px] px-1.5 py-0.5 rounded-full"
                :class="
                  activeTab === tab.key
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-slate-100 text-slate-500'
                "
              >
                {{ tab.count }}
              </span>
            </span>
          </button>
        </aside>

        <!-- 文章列表 -->
        <div class="overflow-y-auto border-r border-slate-100 p-3 space-y-3">
          <template v-if="activeTab === 'collection'">
            <div v-if="!savedArticles.length" class="text-center py-16 text-slate-400">
              <div class="text-4xl mb-3">📚</div>
              <p class="text-sm">還沒有收藏的文獻</p>
              <p class="text-xs mt-1">點擊文章卡片上的「收藏」按鈕開始收集</p>
            </div>
            <ArticleCard
              v-for="article in savedArticles"
              :key="article.id"
              :article="article"
              :selected="selectedArticle?.id === article.id"
              :is-saved="true"
              @select="selectedArticle = $event"
              @toggle-save="toggleSave"
            />
          </template>
          <template v-else>
            <div v-if="!currentArticles.length" class="text-center py-16 text-slate-400">
              <div class="text-4xl mb-3">📭</div>
              <p class="text-sm">此分區目前沒有文獻</p>
            </div>
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
          </template>
        </div>

        <!-- 文章詳情 -->
        <div class="overflow-y-auto p-3">
          <ArticleDetail
            :article="selectedArticle"
            :is-saved="selectedArticle ? isSaved(selectedArticle.id) : false"
            @toggle-save="toggleSave"
            @deep-consult="handleDeepConsult"
            @save-to-notes="handleSaveToNotes"
            @send-to-teach="handleSendToTeach"
          />
        </div>
      </div>

      <!-- 手機版：單欄 -->
      <div class="lg:hidden overflow-y-auto h-full px-4 py-4 space-y-3">
        <template v-if="activeTab === 'collection'">
          <div v-if="!savedArticles.length" class="text-center py-16 text-slate-400">
            <div class="text-4xl mb-3">📚</div>
            <p class="text-sm">還沒有收藏的文獻</p>
            <p class="text-xs mt-1">點擊文章卡片上的「收藏」按鈕開始收集</p>
          </div>
          <ArticleCard
            v-for="article in savedArticles"
            :key="article.id"
            :article="article"
            :selected="selectedArticle?.id === article.id"
            :is-saved="true"
            @select="selectedArticle = $event"
            @toggle-save="toggleSave"
          />
        </template>
        <template v-else>
          <div v-if="!currentArticles.length" class="text-center py-16 text-slate-400">
            <div class="text-4xl mb-3">📭</div>
            <p class="text-sm">此分區目前沒有文獻</p>
          </div>
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
        </template>
      </div>
    </main>

    <!-- 手機版：點擊文章後彈出詳細（所有 tab 共用） -->
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
            @deep-consult="handleDeepConsult"
            @save-to-notes="handleSaveToNotes"
            @send-to-teach="handleSendToTeach"
          />
        </div>
      </div>
    </Teleport>

    <!-- Selection toolbar -->
    <SelectionToolbar
      source-type="insight"
      :source-meta="selectedArticle ? { title: selectedArticle.title, pmid: selectedArticle.pmid } : {}"
    />

    <!-- Teach Picker Modal -->
    <TeachPickerModal
      :visible="showTeachPicker"
      :sessions="teachSessions"
      :loading="teachSessionsLoading"
      @close="showTeachPicker = false"
      @create-new="handleTeachNew"
      @select-session="handleTeachAppend"
    />

    <!-- Teach toast -->
    <Teleport to="body">
      <div
        v-if="teachToast"
        class="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2 bg-slate-800 text-white text-sm px-4 py-2.5 rounded-xl shadow-lg"
      >
        <span>{{ teachToast.msg }}</span>
        <button
          v-if="teachToast.sessionId"
          class="text-orange-300 hover:text-orange-100 text-xs font-medium whitespace-nowrap"
          @click="router.push({ path: '/teach', query: { sessionId: teachToast.sessionId } }); teachToast = null"
        >
          前往 Teach →
        </button>
      </div>
    </Teleport>

    <!-- 本日快訊 Popup -->
    <Teleport to="body">
      <div
        v-if="showDailyBrief"
        class="fixed inset-0 z-50 flex items-start justify-center pt-16 sm:pt-24 bg-black/30"
        @click.self="showDailyBrief = false"
      >
        <div class="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden animate-in">
          <div class="px-5 py-3 border-b border-slate-100 flex items-center justify-between bg-emerald-50">
            <h3 class="text-sm font-bold text-emerald-800">📰 本日快訊</h3>
            <button class="text-slate-400 hover:text-slate-600 text-lg" @click="showDailyBrief = false">✕</button>
          </div>
          <div class="max-h-[60vh] overflow-y-auto p-3 space-y-2">
            <div v-if="!todayArticles.length" class="text-center py-8 text-slate-400 text-sm">
              今日暫無新文章
            </div>
            <div
              v-for="a in todayArticles.slice(0, 20)"
              :key="'popup-' + a.id"
              class="p-3 bg-slate-50 rounded-xl cursor-pointer hover:bg-emerald-50 transition-colors"
              @click="activeTab = a.topics?.[0] || 'CKD'; selectedArticle = a; showDailyBrief = false"
            >
              <p class="text-sm font-medium text-slate-800 leading-snug">
                {{ a.title_zh || a.title }}
              </p>
              <div class="flex items-center gap-2 mt-1.5">
                <span
                  v-for="t in (a.topics || []).slice(0, 2)"
                  :key="t"
                  class="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700"
                >
                  {{ t }}
                </span>
                <span v-if="a.evidence_level" class="text-[10px] text-slate-400">{{ a.evidence_level }}</span>
                <span v-if="a.journal" class="text-[10px] text-slate-400 truncate">{{ a.journal }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useArticles } from '../composables/useArticles.js'
import { useCollection } from '../composables/useCollection.js'
import { useNotes } from '../composables/useNotes.js'
import { useAuth } from '../composables/useAuth.js'
import { useTeachPicker } from '../composables/useTeachPicker.js'
import ArticleCard from '../components/ArticleCard.vue'
import ArticleDetail from '../components/ArticleDetail.vue'
import SelectionToolbar from '../components/SelectionToolbar.vue'
import TeachPickerModal from '../components/TeachPickerModal.vue'

const router = useRouter()
const { uid } = useAuth()
const { saveFromModule } = useNotes()

const {
  showTeachPicker, teachSessions, teachSessionsLoading, teachToast,
  sendToTeach: triggerTeachPicker, handleTeachNew, handleTeachAppend,
} = useTeachPicker(uid, { sourceLabel: '論文摘錄' })

// Data
const {
  articles,
  esrdArticles,
  akiArticles,
  ckdArticles,
  gnArticles,
  transplantArticles,
  electrolyteArticles,
  pdArticles,
  ckmArticles,
  htnArticles,
  pkdArticles,
  ckdMbdArticles,
  stoneArticles,
  oncoNephroArticles,
  journalArticles,
  todayArticles,
  newCountByTopic,
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
const showDailyBrief = ref(false)

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

// Tabs config — 分為主題與特殊分類
const topicTabs = computed(() => [
  { key: 'ESRD/HD', label: 'ESRD / HD', count: esrdArticles.value.length, newCount: newCountByTopic.value['ESRD/HD'] || 0 },
  { key: 'AKI', label: 'AKI', count: akiArticles.value.length, newCount: newCountByTopic.value['AKI'] || 0 },
  { key: 'CKD', label: 'CKD', count: ckdArticles.value.length, newCount: newCountByTopic.value['CKD'] || 0 },
  { key: 'GN', label: 'GN', count: gnArticles.value.length, newCount: newCountByTopic.value['GN'] || 0 },
  { key: 'Transplant', label: 'Transplant', count: transplantArticles.value.length, newCount: newCountByTopic.value['Transplant'] || 0 },
  { key: 'Electrolyte', label: 'Electrolyte', count: electrolyteArticles.value.length, newCount: newCountByTopic.value['Electrolyte'] || 0 },
  { key: 'PD', label: 'PD', count: pdArticles.value.length, newCount: newCountByTopic.value['PD'] || 0 },
  { key: 'CKM', label: '心腎代謝', count: ckmArticles.value.length, newCount: newCountByTopic.value['CKM'] || 0 },
  { key: 'HTN', label: '高血壓腎病', count: htnArticles.value.length, newCount: newCountByTopic.value['HTN'] || 0 },
  { key: 'PKD', label: '遺傳腎病', count: pkdArticles.value.length, newCount: newCountByTopic.value['PKD'] || 0 },
  { key: 'CKD-MBD', label: '骨礦代謝', count: ckdMbdArticles.value.length, newCount: newCountByTopic.value['CKD-MBD'] || 0 },
  { key: 'Stone', label: '腎結石', count: stoneArticles.value.length, newCount: newCountByTopic.value['Stone'] || 0 },
  { key: 'Onco-Nephro', label: '腫瘤腎臟', count: oncoNephroArticles.value.length, newCount: newCountByTopic.value['Onco-Nephro'] || 0 },
])

const specialTabs = computed(() => [
  { key: 'journal', label: '📰 期刊', count: journalArticles.value.length, newCount: newCountByTopic.value['journal'] || 0 },
  { key: 'collection', label: '✅ 收藏庫', count: savedArticles.value.length, newCount: 0 },
])

// 合併所有 tabs（手機版 select 使用）
const tabs = computed(() => [...topicTabs.value, ...specialTabs.value])

const currentArticles = computed(() => {
  if (activeTab.value === 'ESRD/HD') return esrdArticles.value
  if (activeTab.value === 'AKI') return akiArticles.value
  if (activeTab.value === 'CKD') return ckdArticles.value
  if (activeTab.value === 'GN') return gnArticles.value
  if (activeTab.value === 'Transplant') return transplantArticles.value
  if (activeTab.value === 'Electrolyte') return electrolyteArticles.value
  if (activeTab.value === 'PD') return pdArticles.value
  if (activeTab.value === 'CKM') return ckmArticles.value
  if (activeTab.value === 'HTN') return htnArticles.value
  if (activeTab.value === 'PKD') return pkdArticles.value
  if (activeTab.value === 'CKD-MBD') return ckdMbdArticles.value
  if (activeTab.value === 'Stone') return stoneArticles.value
  if (activeTab.value === 'Onco-Nephro') return oncoNephroArticles.value
  if (activeTab.value === 'journal') return journalArticles.value
  return []
})

const articleCount = computed(() => articles.value.length)

// === 跨模組功能 ===
function showToast(msg) {
  const el = document.createElement('div')
  el.textContent = msg
  el.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);z-index:50;background:#7c3aed;color:white;padding:8px 16px;border-radius:12px;font-size:14px;box-shadow:0 4px 12px rgba(0,0,0,.15)'
  document.body.appendChild(el)
  setTimeout(() => el.remove(), 2000)
}

function handleSendToTeach(article) {
  const title = article.title_zh || article.title || ''
  const content = [
    `# ${title}`,
    '',
    article.journal ? `**Journal:** ${article.journal}` : '',
    article.pubdate ? `**Date:** ${article.pubdate}` : '',
    '',
    article.abstract || '',
    '',
    article.clinical_takeaways?.length ? '## Clinical Takeaways\n' + article.clinical_takeaways.map(t => `- ${t}`).join('\n') : '',
  ].filter(Boolean).join('\n')
  triggerTeachPicker(content)
}

function handleDeepConsult(article) {
  const question = article.title_zh || article.title || ''
  router.push({ path: '/consult', query: { q: question } })
}

async function handleSaveToNotes(article) {
  try {
    const content = [
      `# ${article.title_zh || article.title}`,
      '',
      article.title_zh && article.title ? `**原文標題**: ${article.title}` : '',
      `**期刊**: ${article.journal || ''} · ${article.pubdate || ''}`,
      article.link ? `**連結**: ${article.link}` : '',
      '',
      '## 摘要重點',
      ...(article.summary_points || []).map(p => `- ${p}`),
      '',
      '## 臨床重點',
      ...(article.clinical_takeaways || []).map((t, i) => `${i + 1}. ${t}`),
    ].filter(Boolean).join('\n')

    await saveFromModule(content, 'NB Insight', article.title_zh || article.title)
    showToast('已存入 Notes ✓')
  } catch (e) {
    console.error('Save to notes error:', e)
    showToast('儲存失敗')
  }
}
</script>
