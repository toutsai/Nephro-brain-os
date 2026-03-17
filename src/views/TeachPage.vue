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
            <h1 class="text-sm font-bold text-slate-800">NB Teach</h1>
            <p class="text-[10px] text-slate-400">教學素材產生器</p>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <router-link to="/notes" class="text-xs px-3 py-1.5 bg-slate-100 hover:bg-purple-50 text-slate-500 hover:text-purple-600 rounded-lg transition-colors">📝 Notes</router-link>
          <router-link to="/consult" class="text-xs px-3 py-1.5 bg-slate-100 hover:bg-teal-50 text-slate-500 hover:text-teal-600 rounded-lg transition-colors">💬 Consult</router-link>
        </div>
      </div>
    </header>

    <div class="flex-1 overflow-hidden flex">
      <!-- Left: Sessions + Input -->
      <aside class="w-80 border-r border-slate-200 bg-white flex flex-col shrink-0">
        <!-- New session -->
        <div class="p-3 border-b border-slate-100">
          <button
            class="w-full px-3 py-2 bg-orange-500 hover:bg-orange-400 text-white text-sm font-medium rounded-lg transition-colors"
            @click="startNewSession"
          >
            + 新教學素材
          </button>
        </div>

        <!-- Session list -->
        <div class="flex-1 overflow-y-auto">
          <div v-if="sessionsLoading" class="text-center py-8 text-slate-400 text-xs">載入中...</div>
          <div
            v-for="s in sessions"
            :key="s.id"
            class="group px-3 py-3 border-b border-slate-50 cursor-pointer hover:bg-slate-50 transition-colors"
            :class="selectedId === s.id ? 'bg-orange-50 border-l-2 border-l-orange-500' : ''"
            @click="selectSession(s.id)"
          >
            <div class="text-sm font-medium text-slate-700 truncate">{{ s.title || '未命名' }}</div>
            <div class="flex items-center gap-2 mt-1 text-[10px] text-slate-400">
              <span v-if="s.summary" class="text-emerald-500">✓ 摘要</span>
              <span v-if="s.flashcards" class="text-blue-500">✓ 卡片</span>
              <span v-if="s.outline" class="text-purple-500">✓ 大綱</span>
            </div>
            <button
              class="text-[10px] text-slate-300 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity mt-1"
              @click.stop="handleDelete(s.id)"
            >刪除</button>
          </div>
        </div>
      </aside>

      <!-- Right: Content -->
      <main class="flex-1 overflow-y-auto">
        <!-- No session selected -->
        <div v-if="!selectedId" class="flex items-center justify-center h-full">
          <div class="text-center max-w-md px-8">
            <div class="text-5xl mb-4">🎓</div>
            <h2 class="text-lg font-bold text-slate-700 mb-2">NB Teach</h2>
            <p class="text-sm text-slate-400 mb-6">
              貼上教科書內容、論文摘要或任何學習素材，<br>
              AI 會自動產生摘要、Flashcards 和學習大綱。
            </p>
            <button
              class="px-6 py-3 bg-orange-500 hover:bg-orange-400 text-white font-medium rounded-lg transition-colors"
              @click="startNewSession"
            >
              開始建立
            </button>
          </div>
        </div>

        <!-- Session content -->
        <div v-else class="max-w-4xl mx-auto px-4 py-6">
          <!-- Input area (only if no content generated yet) -->
          <div v-if="isNewSession" class="mb-6">
            <label class="block text-sm font-bold text-slate-700 mb-2">學習素材</label>
            <input
              v-model="sessionTitle"
              class="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 mb-3 focus:outline-none focus:ring-2 focus:ring-orange-400"
              placeholder="標題（例如：KDIGO AKI Guideline 2024）"
            />
            <textarea
              v-model="sourceText"
              rows="12"
              class="w-full text-sm border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-orange-400 font-mono leading-relaxed resize-none"
              placeholder="在此貼上教科書章節、論文摘要、筆記、或任何學習素材...

支援中英文混合。內容越完整，產出品質越好。"
            />
            <div class="flex items-center gap-3 mt-3">
              <button
                :disabled="!sourceText.trim() || generating"
                class="px-5 py-2.5 bg-orange-500 hover:bg-orange-400 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                @click="generateAll"
              >
                {{ generating ? '生成中...' : '🚀 一鍵生成全部' }}
              </button>
              <button
                :disabled="!sourceText.trim() || generating"
                class="px-4 py-2.5 border border-slate-200 text-sm text-slate-600 hover:bg-slate-50 rounded-lg transition-colors disabled:opacity-40"
                @click="generateOne('summary')"
              >
                📋 只要摘要
              </button>
              <button
                :disabled="!sourceText.trim() || generating"
                class="px-4 py-2.5 border border-slate-200 text-sm text-slate-600 hover:bg-slate-50 rounded-lg transition-colors disabled:opacity-40"
                @click="generateOne('flashcards')"
              >
                🃏 只要卡片
              </button>
              <button
                :disabled="!sourceText.trim() || generating"
                class="px-4 py-2.5 border border-slate-200 text-sm text-slate-600 hover:bg-slate-50 rounded-lg transition-colors disabled:opacity-40"
                @click="generateOne('outline')"
              >
                🗺️ 只要大綱
              </button>
            </div>
          </div>

          <!-- Generating indicator -->
          <div v-if="generating" class="flex items-center gap-3 mb-6 px-4 py-3 bg-orange-50 border border-orange-200 rounded-xl">
            <div class="w-5 h-5 border-2 border-orange-500 border-t-transparent rounded-full animate-spin" />
            <span class="text-sm text-orange-700">
              正在生成{{ generatingMode === 'all' ? '摘要 + Flashcards + 大綱' : generatingMode === 'summary' ? '摘要' : generatingMode === 'flashcards' ? 'Flashcards' : '大綱' }}...
            </span>
          </div>

          <!-- Error -->
          <div v-if="teachError" class="mb-4 px-4 py-2 bg-red-50 border border-red-200 rounded-lg text-xs text-red-600">
            ⚠️ {{ teachError }}
          </div>

          <!-- Results tabs -->
          <div v-if="currentSession && !isNewSession">
            <!-- Re-generate button -->
            <div class="flex items-center justify-between mb-4">
              <h2 class="text-lg font-bold text-slate-800">{{ currentSession.title }}</h2>
              <button
                class="text-xs text-slate-400 hover:text-orange-500 transition-colors"
                @click="isNewSession = true; sourceText = currentSession.source_text || ''"
              >
                重新生成
              </button>
            </div>

            <!-- Tab nav -->
            <div class="flex gap-1 mb-4 bg-slate-100 rounded-lg p-1">
              <button
                v-for="tab in contentTabs"
                :key="tab.key"
                class="flex-1 px-3 py-2 text-xs font-medium rounded-md transition-colors"
                :class="activeTab === tab.key
                  ? 'bg-white text-slate-800 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'"
                @click="activeTab = tab.key"
              >
                {{ tab.icon }} {{ tab.label }}
                <span v-if="tab.ready" class="ml-1 text-emerald-500">✓</span>
              </button>
            </div>

            <!-- Summary -->
            <div v-if="activeTab === 'summary'">
              <div v-if="!currentSession.summary" class="text-center py-12 text-slate-400">
                <p class="text-sm">尚未生成摘要</p>
                <button class="mt-2 text-xs text-orange-500 hover:underline" @click="regenOne('summary')">生成摘要</button>
              </div>
              <div v-else class="bg-white rounded-xl border border-slate-200 p-6">
                <div class="prose-teach text-sm text-slate-700 leading-relaxed" v-html="renderMd(currentSession.summary)" />
              </div>
            </div>

            <!-- Flashcards -->
            <div v-if="activeTab === 'flashcards'">
              <div v-if="!parsedCards.length" class="text-center py-12 text-slate-400">
                <p class="text-sm">尚未生成 Flashcards</p>
                <button class="mt-2 text-xs text-orange-500 hover:underline" @click="regenOne('flashcards')">生成 Flashcards</button>
              </div>
              <div v-else>
                <div class="flex items-center justify-between mb-4">
                  <span class="text-sm text-slate-500">{{ cardIndex + 1 }} / {{ parsedCards.length }}</span>
                  <div class="flex gap-2">
                    <button
                      :disabled="cardIndex === 0"
                      class="px-3 py-1 text-xs border border-slate-200 rounded-lg disabled:opacity-30"
                      @click="cardIndex--"
                    >← 上一張</button>
                    <button
                      :disabled="cardIndex >= parsedCards.length - 1"
                      class="px-3 py-1 text-xs border border-slate-200 rounded-lg disabled:opacity-30"
                      @click="cardIndex++"
                    >下一張 →</button>
                  </div>
                </div>
                <FlashCard
                  :card="parsedCards[cardIndex]"
                  :index="cardIndex"
                  :total="parsedCards.length"
                />
                <!-- Card list below -->
                <div class="mt-6 space-y-2">
                  <h4 class="text-xs font-bold text-slate-500 mb-2">所有卡片</h4>
                  <div
                    v-for="(c, i) in parsedCards"
                    :key="i"
                    class="flex items-start gap-3 px-3 py-2 rounded-lg cursor-pointer transition-colors"
                    :class="cardIndex === i ? 'bg-blue-50' : 'hover:bg-slate-50'"
                    @click="cardIndex = i"
                  >
                    <span class="text-[10px] text-slate-400 mt-0.5 shrink-0">#{{ i + 1 }}</span>
                    <div class="min-w-0">
                      <p class="text-xs font-medium text-slate-700 truncate">{{ c.question }}</p>
                      <p class="text-[10px] text-slate-400 truncate">{{ c.answer }}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Outline -->
            <div v-if="activeTab === 'outline'">
              <div v-if="!currentSession.outline" class="text-center py-12 text-slate-400">
                <p class="text-sm">尚未生成大綱</p>
                <button class="mt-2 text-xs text-orange-500 hover:underline" @click="regenOne('outline')">生成大綱</button>
              </div>
              <div v-else class="bg-white rounded-xl border border-slate-200 p-6">
                <div class="prose-teach text-sm text-slate-700 leading-relaxed" v-html="renderMd(currentSession.outline)" />
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted, watch } from 'vue'
import { useTeach } from '../composables/useTeach.js'
import FlashCard from '../components/FlashCard.vue'

const {
  sessions,
  loading: sessionsLoading,
  generating,
  generatingMode,
  error: teachError,
  createSession,
  generate,
  deleteSession,
  unsubscribe,
} = useTeach()

const selectedId = ref(null)
const sourceText = ref('')
const sessionTitle = ref('')
const activeTab = ref('summary')
const cardIndex = ref(0)
const isNewSession = ref(false)

const currentSession = computed(() => {
  if (!selectedId.value) return null
  return sessions.value.find((s) => s.id === selectedId.value) || null
})

const contentTabs = computed(() => [
  { key: 'summary', label: '摘要', icon: '📋', ready: !!currentSession.value?.summary },
  { key: 'flashcards', label: 'Flashcards', icon: '🃏', ready: !!currentSession.value?.flashcards },
  { key: 'outline', label: '大綱', icon: '🗺️', ready: !!currentSession.value?.outline },
])

// 解析 flashcards JSON
const parsedCards = computed(() => {
  const raw = currentSession.value?.flashcards
  if (!raw) return []
  // 嘗試 JSON 解析
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw)
      return Array.isArray(parsed) ? parsed : parsed.flashcards || parsed.cards || []
    } catch {
      // 嘗試從 markdown 解析
      return parseCardsFromText(raw)
    }
  }
  if (Array.isArray(raw)) return raw
  return []
})

function parseCardsFromText(text) {
  const cards = []
  const blocks = text.split(/\n(?=Q:|問題:|Question:|\d+\.)/i)
  for (const block of blocks) {
    const qMatch = block.match(/(?:Q:|問題:|Question:|\d+\.)\s*(.+)/i)
    const aMatch = block.match(/(?:A:|答案:|Answer:)\s*([\s\S]+?)(?=\n(?:Q:|問題:|Question:|\d+\.)|$)/i)
    if (qMatch && aMatch) {
      cards.push({ question: qMatch[1].trim(), answer: aMatch[1].trim() })
    }
  }
  return cards
}

// === Actions ===
function selectSession(id) {
  selectedId.value = id
  isNewSession.value = false
  cardIndex.value = 0
  activeTab.value = 'summary'
}

function startNewSession() {
  selectedId.value = 'new'
  sourceText.value = ''
  sessionTitle.value = ''
  isNewSession.value = true
}

async function generateAll() {
  if (!sourceText.value.trim()) return
  const title = sessionTitle.value.trim() || sourceText.value.slice(0, 30) + '…'

  let sid = selectedId.value
  if (sid === 'new') {
    sid = await createSession(title, sourceText.value)
    selectedId.value = sid
  }

  await generate(sid, sourceText.value, 'all')
  isNewSession.value = false
  activeTab.value = 'summary'
}

async function generateOne(mode) {
  if (!sourceText.value.trim()) return
  const title = sessionTitle.value.trim() || sourceText.value.slice(0, 30) + '…'

  let sid = selectedId.value
  if (sid === 'new') {
    sid = await createSession(title, sourceText.value)
    selectedId.value = sid
  }

  await generate(sid, sourceText.value, mode)
  isNewSession.value = false
  activeTab.value = mode
}

async function regenOne(mode) {
  if (!currentSession.value?.source_text) return
  sourceText.value = currentSession.value.source_text
  await generate(selectedId.value, sourceText.value, mode)
  activeTab.value = mode
}

function handleDelete(sid) {
  if (!confirm('確定要刪除？')) return
  deleteSession(sid)
  if (selectedId.value === sid) selectedId.value = null
}

// 換卡片時重設 index
watch(() => currentSession.value?.flashcards, () => { cardIndex.value = 0 })

onUnmounted(() => unsubscribe())

// === Markdown 渲染 ===
function renderMd(text) {
  if (!text) return ''
  let html = text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, l, c) =>
    `<pre class="code-block"><code>${c.trim()}</code></pre>`)
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
  html = html.replace(/^#### (.+)$/gm, '<h4>$1</h4>')
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>')
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>')
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>')
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
  html = html.replace(/^[\-\*] (.+)$/gm, '<li>$1</li>')
  html = html.replace(/(<li>[\s\S]*?<\/li>)(\n(?!<li)|\s*$)/g, '<ul>$1</ul>')
  html = html.replace(/^\d+\. (.+)$/gm, '<li class="ol">$1</li>')
  html = html.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>')
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g,
    '<a href="$2" target="_blank" rel="noreferrer">$1 ↗</a>')
  html = html.replace(/\n\n/g, '</p><p>')
  html = html.replace(/\n/g, '<br>')
  html = `<p>${html}</p>`.replace(/<p>\s*<\/p>/g, '')
  return html
}
</script>

<style scoped>
.prose-teach :deep(h1) { font-size: 18px; font-weight: 600; margin: 16px 0 8px; }
.prose-teach :deep(h2) { font-size: 16px; font-weight: 600; margin: 14px 0 6px; }
.prose-teach :deep(h3) { font-size: 14px; font-weight: 600; margin: 12px 0 4px; }
.prose-teach :deep(p) { margin-bottom: 8px; }
.prose-teach :deep(strong) { font-weight: 600; color: #1e293b; }
.prose-teach :deep(ul) { padding-left: 16px; margin: 8px 0; }
.prose-teach :deep(li) { list-style: disc; margin: 2px 0; }
.prose-teach :deep(li.ol) { list-style: decimal; }
.prose-teach :deep(blockquote) { border-left: 2px solid #f97316; padding-left: 12px; color: #6b7280; font-style: italic; margin: 8px 0; }
.prose-teach :deep(.code-block) { background: #1e293b; color: #6ee7b7; font-size: 12px; padding: 12px; border-radius: 8px; margin: 8px 0; overflow-x: auto; }
.prose-teach :deep(.inline-code) { background: #f1f5f9; color: #dc2626; font-size: 12px; padding: 1px 6px; border-radius: 4px; font-family: monospace; }
.prose-teach :deep(a) { color: #f97316; text-decoration: underline; }
</style>
