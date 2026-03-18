<template>
  <div class="h-screen flex flex-col bg-slate-50">
    <!-- Header -->
    <header class="bg-white border-b border-slate-200 shrink-0">
      <div class="max-w-7xl mx-auto px-4 py-2 flex items-center justify-between">
        <div class="flex items-center gap-2">
          <h1 class="text-sm font-bold text-slate-800">NB Assist</h1>
          <span class="text-[10px] text-slate-400">臨床決策輔助</span>
        </div>
        <div class="text-[10px] text-amber-600 bg-amber-50 px-2 py-1 rounded-full">
          ⚠️ 僅供參考，不取代臨床判斷
        </div>
      </div>
    </header>

    <div class="flex-1 overflow-hidden flex">
      <!-- Left: mode selector + history -->
      <aside class="w-72 border-r border-slate-200 bg-white flex flex-col shrink-0">
        <div class="p-3 space-y-2 border-b border-slate-100">
          <button
            v-for="m in modes"
            :key="m.key"
            class="w-full text-left px-3 py-2.5 rounded-lg transition-colors"
            :class="activeMode === m.key
              ? 'bg-rose-50 border border-rose-200 text-rose-700'
              : 'hover:bg-slate-50 text-slate-600'"
            @click="activeMode = m.key; selectedHistoryId = null; currentResult = null"
          >
            <div class="flex items-center gap-2">
              <span class="text-base">{{ m.icon }}</span>
              <div>
                <div class="text-xs font-bold">{{ m.label }}</div>
                <div class="text-[10px] text-slate-400">{{ m.desc }}</div>
              </div>
            </div>
          </button>
        </div>

        <!-- History -->
        <div class="flex-1 overflow-y-auto">
          <div class="px-3 py-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">歷史紀錄</div>
          <div v-if="!history.length" class="px-3 py-4 text-xs text-slate-400 text-center">尚無紀錄</div>
          <div
            v-for="h in history"
            :key="h.id"
            class="group px-3 py-2.5 border-b border-slate-50 cursor-pointer hover:bg-slate-50 transition-colors"
            :class="selectedHistoryId === h.id ? 'bg-rose-50' : ''"
            @click="viewHistory(h)"
          >
            <div class="flex items-center gap-1.5">
              <span class="text-[10px]">{{ modeIcon(h.mode) }}</span>
              <span class="text-xs font-medium text-slate-700 truncate">{{ historyTitle(h) }}</span>
              <span v-if="h.has_images" class="text-[10px] text-slate-400">📷</span>
            </div>
            <div class="flex items-center justify-between mt-0.5">
              <span class="text-[10px] text-slate-400">{{ formatDate(h.created_at) }}</span>
              <button
                class="text-[10px] text-slate-300 hover:text-red-400 opacity-0 group-hover:opacity-100"
                @click.stop="handleDelete(h.id)"
              >刪除</button>
            </div>
          </div>
        </div>
      </aside>

      <!-- Right: input form + result -->
      <main class="flex-1 overflow-y-auto">
        <div class="max-w-3xl mx-auto px-6 py-6">

          <!-- ============ Clinical Scenario ============ -->
          <div v-if="activeMode === 'clinical'">
            <h2 class="text-lg font-bold text-slate-800 mb-1">🏥 臨床情境諮詢</h2>
            <p class="text-xs text-slate-400 mb-4">描述病人情況或貼上病歷截圖，取得實證指引建議。</p>

            <textarea
              v-model="clinicalInput"
              rows="5"
              class="w-full text-sm border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-rose-400 resize-none leading-relaxed"
              placeholder="例如：65 歲男性，DM + CKD stage 4 (eGFR 22)，近期出現持續性高血鉀 (K 6.2)..."
            />

            <!-- Image upload -->
            <ImageUploader v-model="clinicalImages" class="mt-3" />

            <button
              :disabled="(!clinicalInput.trim() && !clinicalImages.length) || generating"
              class="mt-3 px-5 py-2.5 bg-rose-600 hover:bg-rose-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              @click="submitClinical"
            >
              {{ generating ? '分析中...' : '🔍 實證分析' }}
            </button>
          </div>

          <!-- ============ Dose Adjustment ============ -->
          <div v-if="activeMode === 'dose'">
            <h2 class="text-lg font-bold text-slate-800 mb-1">💊 腎功能藥物劑量調整</h2>
            <p class="text-xs text-slate-400 mb-4">輸入藥物與腎功能，或貼上處方截圖。</p>

            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
              <div>
                <label class="block text-xs font-bold text-slate-600 mb-1">藥物名稱</label>
                <input
                  v-model="doseDrug"
                  class="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-rose-400"
                  placeholder="例如：Vancomycin"
                />
              </div>
              <div>
                <label class="block text-xs font-bold text-slate-600 mb-1">eGFR (mL/min/1.73m²)</label>
                <input
                  v-model.number="doseEgfr"
                  type="number"
                  class="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-rose-400"
                  placeholder="例如：25"
                />
              </div>
              <div>
                <label class="block text-xs font-bold text-slate-600 mb-1">CKD Stage</label>
                <select
                  v-model="doseCkdStage"
                  class="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-rose-400 bg-white"
                >
                  <option value="">自動判斷</option>
                  <option value="1">Stage 1 (eGFR ≥90)</option>
                  <option value="2">Stage 2 (eGFR 60-89)</option>
                  <option value="3a">Stage 3a (eGFR 45-59)</option>
                  <option value="3b">Stage 3b (eGFR 30-44)</option>
                  <option value="4">Stage 4 (eGFR 15-29)</option>
                  <option value="5">Stage 5 (eGFR &lt;15)</option>
                  <option value="5D">Stage 5D (透析中)</option>
                </select>
              </div>
              <div>
                <label class="block text-xs font-bold text-slate-600 mb-1">體重 (kg，選填)</label>
                <input
                  v-model.number="doseWeight"
                  type="number"
                  class="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-rose-400"
                  placeholder="例如：70"
                />
              </div>
            </div>

            <textarea
              v-model="doseExtra"
              rows="2"
              class="w-full text-sm border border-slate-200 rounded-xl px-4 py-2 focus:outline-none focus:ring-2 focus:ring-rose-400 resize-none mb-3"
              placeholder="其他備註（選填）"
            />

            <!-- Image upload -->
            <ImageUploader v-model="doseImages" class="mb-3" />

            <button
              :disabled="(!doseDrug.trim() && !doseImages.length) || generating"
              class="px-5 py-2.5 bg-rose-600 hover:bg-rose-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              @click="submitDose"
            >
              {{ generating ? '查詢中...' : '💊 查詢劑量' }}
            </button>
          </div>

          <!-- ============ Lab DDx ============ -->
          <div v-if="activeMode === 'lab'">
            <h2 class="text-lg font-bold text-slate-800 mb-1">🔬 Lab 鑑別診斷</h2>
            <p class="text-xs text-slate-400 mb-4">輸入檢驗數據或直接拍照上傳 lab 報告。</p>

            <textarea
              v-model="labInput"
              rows="6"
              class="w-full text-sm border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-rose-400 resize-none font-mono leading-relaxed"
              placeholder="貼上 lab data 或留空只上傳圖片...

BUN 85, Cr 4.2, K 6.1, Na 132
Ca 7.8, P 6.5, Albumin 2.8..."
            />

            <!-- Image upload -->
            <ImageUploader v-model="labImages" class="mt-3" />

            <button
              :disabled="(!labInput.trim() && !labImages.length) || generating"
              class="mt-3 px-5 py-2.5 bg-rose-600 hover:bg-rose-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              @click="submitLab"
            >
              {{ generating ? '分析中...' : '🔬 鑑別診斷' }}
            </button>
          </div>

          <!-- ============ NHI Rules ============ -->
          <div v-if="activeMode === 'nhi'">
            <h2 class="text-lg font-bold text-slate-800 mb-1">🏛️ 台灣健保給付查詢</h2>
            <p class="text-xs text-slate-400 mb-4">輸入藥物名稱或治療項目，查詢健保給付條件與規範。</p>

            <textarea
              v-model="nhiInput"
              rows="4"
              class="w-full text-sm border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-rose-400 resize-none leading-relaxed"
              placeholder="例如：
• Dapagliflozin 在 CKD 的健保給付條件？
• Sevelamer 的健保適應症和限制？
• CRRT 健保給付的條件和天數限制？
• Eculizumab 用於 aHUS 的給付規定？"
            />

            <ImageUploader v-model="nhiImages" class="mt-3" />

            <button
              :disabled="(!nhiInput.trim() && !nhiImages.length) || generating"
              class="mt-3 px-5 py-2.5 bg-rose-600 hover:bg-rose-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              @click="submitNhi"
            >
              {{ generating ? '查詢中...' : '🏛️ 查詢健保規定' }}
            </button>
          </div>

          <!-- ============ Drug Interaction ============ -->
          <div v-if="activeMode === 'interaction'">
            <h2 class="text-lg font-bold text-slate-800 mb-1">⚡ 藥物交互作用檢查</h2>
            <p class="text-xs text-slate-400 mb-4">輸入多種藥物，檢查交互作用及注意事項。也可拍處方單。</p>

            <textarea
              v-model="interactionInput"
              rows="6"
              class="w-full text-sm border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-rose-400 resize-none leading-relaxed"
              placeholder="列出要檢查的藥物，一行一個或用逗號分隔：

Amlodipine 5mg
Metformin 500mg BID
Lisinopril 10mg
Atorvastatin 20mg
Dapagliflozin 10mg

或直接拍照上傳處方單..."
            />

            <ImageUploader v-model="interactionImages" class="mt-3" />

            <button
              :disabled="(!interactionInput.trim() && !interactionImages.length) || generating"
              class="mt-3 px-5 py-2.5 bg-rose-600 hover:bg-rose-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              @click="submitInteraction"
            >
              {{ generating ? '檢查中...' : '⚡ 檢查交互作用' }}
            </button>
          </div>

          <!-- ============ Generating ============ -->
          <div v-if="generating" class="mt-6 flex items-center gap-3 px-4 py-3 bg-rose-50 border border-rose-200 rounded-xl">
            <div class="w-5 h-5 border-2 border-rose-500 border-t-transparent rounded-full animate-spin" />
            <span class="text-sm text-rose-700">AI 正在分析，搜尋最新實證...</span>
          </div>

          <!-- ============ Error ============ -->
          <div v-if="assistError" class="mt-4 px-4 py-2 bg-red-50 border border-red-200 rounded-lg text-xs text-red-600">
            ⚠️ {{ assistError }}
          </div>

          <!-- ============ Result ============ -->
          <div v-if="currentResult" class="mt-6">
            <div class="mb-4 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg text-[10px] text-amber-700">
              ⚠️ 此建議由 AI 根據實證醫學資料生成，僅供臨床參考。實際治療決策應由主治醫師根據完整病歷資訊做出判斷。
            </div>

            <div class="bg-white rounded-xl border border-slate-200 p-6">
              <div class="prose-assist text-sm text-slate-700 leading-relaxed" v-html="renderMd(currentResult)" />
            </div>

            <div class="flex items-center gap-2 mt-3">
              <button
                class="text-xs text-purple-500 hover:text-purple-700 transition-colors"
                @click="saveToNotes"
              >
                📝 收進 Notes
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, onUnmounted, defineComponent } from 'vue'
import { collection, addDoc, serverTimestamp } from 'firebase/firestore'
import { db } from '../firebase.js'
import { useAssist } from '../composables/useAssist.js'

const {
  history,
  loading,
  generating,
  error: assistError,
  queryAssist,
  deleteHistory,
  fileToBase64,
  unsubscribe,
} = useAssist()

// === Inline ImageUploader component ===
const ImageUploader = defineComponent({
  props: { modelValue: { type: Array, default: () => [] } },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    const previews = ref([])

    async function handleFiles(e) {
      const files = Array.from(e.target.files || [])
      for (const file of files) {
        if (!file.type.startsWith('image/')) continue
        const b64 = await fileToBase64(file)
        props.modelValue.push(b64)

        const reader = new FileReader()
        reader.onload = () => previews.value.push({ url: reader.result, name: file.name })
        reader.readAsDataURL(file)
      }
      emit('update:modelValue', [...props.modelValue])
      e.target.value = ''
    }

    function remove(idx) {
      props.modelValue.splice(idx, 1)
      previews.value.splice(idx, 1)
      emit('update:modelValue', [...props.modelValue])
    }

    function clear() {
      props.modelValue.splice(0)
      previews.value.splice(0)
      emit('update:modelValue', [])
    }

    return { previews, handleFiles, remove, clear }
  },
  template: `
    <div>
      <div class="flex items-center gap-2 mb-2">
        <label class="inline-flex items-center gap-1.5 px-3 py-1.5 border border-slate-200 rounded-lg text-xs text-slate-600 hover:bg-slate-50 cursor-pointer transition-colors">
          📷 上傳圖片
          <input type="file" accept="image/*" multiple class="hidden" @change="handleFiles" />
        </label>
        <span class="text-[10px] text-slate-400">支援 JPG、PNG（Lab 報告、病歷截圖、處方單）</span>
        <button v-if="previews.length" class="text-[10px] text-slate-400 hover:text-red-500" @click="clear">清除全部</button>
      </div>
      <div v-if="previews.length" class="flex flex-wrap gap-2">
        <div v-for="(p, i) in previews" :key="i" class="relative group">
          <img :src="p.url" class="w-20 h-20 object-cover rounded-lg border border-slate-200" />
          <button
            class="absolute -top-1.5 -right-1.5 w-5 h-5 bg-red-500 text-white rounded-full text-[10px] flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
            @click="remove(i)"
          >×</button>
          <div class="text-[10px] text-slate-400 truncate w-20 mt-0.5">{{ p.name }}</div>
        </div>
      </div>
    </div>
  `,
})

// Mode
const activeMode = ref('clinical')
const selectedHistoryId = ref(null)
const currentResult = ref(null)

const modes = [
  { key: 'clinical', icon: '🏥', label: '臨床情境', desc: '實證指引建議' },
  { key: 'dose', icon: '💊', label: '劑量調整', desc: '腎功能藥物劑量' },
  { key: 'lab', icon: '🔬', label: 'Lab 鑑別', desc: '檢驗鑑別診斷' },
  { key: 'nhi', icon: '🏛️', label: '健保查詢', desc: '台灣健保給付規則' },
  { key: 'interaction', icon: '⚡', label: '交互作用', desc: '藥物交互作用檢查' },
]

// Inputs
const clinicalInput = ref('')
const clinicalImages = ref([])
const doseDrug = ref('')
const doseEgfr = ref(null)
const doseCkdStage = ref('')
const doseWeight = ref(null)
const doseExtra = ref('')
const doseImages = ref([])
const labInput = ref('')
const labImages = ref([])
const nhiInput = ref('')
const nhiImages = ref([])
const interactionInput = ref('')
const interactionImages = ref([])

// === Submit ===
async function submitClinical() {
  const res = await queryAssist({
    mode: 'clinical',
    payload: { scenario: clinicalInput.value },
    images: clinicalImages.value.length ? clinicalImages.value : undefined,
  })
  if (res) currentResult.value = res.result
}

async function submitDose() {
  const res = await queryAssist({
    mode: 'dose',
    payload: {
      drug: doseDrug.value,
      egfr: doseEgfr.value,
      ckd_stage: doseCkdStage.value,
      weight: doseWeight.value,
      extra: doseExtra.value,
    },
    images: doseImages.value.length ? doseImages.value : undefined,
  })
  if (res) currentResult.value = res.result
}

async function submitLab() {
  const res = await queryAssist({
    mode: 'lab',
    payload: { lab_data: labInput.value },
    images: labImages.value.length ? labImages.value : undefined,
  })
  if (res) currentResult.value = res.result
}

async function submitNhi() {
  const res = await queryAssist({
    mode: 'nhi',
    payload: { query: nhiInput.value },
    images: nhiImages.value.length ? nhiImages.value : undefined,
  })
  if (res) currentResult.value = res.result
}

async function submitInteraction() {
  const res = await queryAssist({
    mode: 'interaction',
    payload: { drugs: interactionInput.value },
    images: interactionImages.value.length ? interactionImages.value : undefined,
  })
  if (res) currentResult.value = res.result
}

// === History ===
function viewHistory(h) {
  selectedHistoryId.value = h.id
  activeMode.value = h.mode
  currentResult.value = h.result
  if (h.mode === 'clinical') { clinicalInput.value = h.input?.scenario || ''; clinicalImages.value = [] }
  if (h.mode === 'dose') { doseDrug.value = h.input?.drug || ''; doseEgfr.value = h.input?.egfr || null; doseCkdStage.value = h.input?.ckd_stage || ''; doseWeight.value = h.input?.weight || null; doseExtra.value = h.input?.extra || ''; doseImages.value = [] }
  if (h.mode === 'lab') { labInput.value = h.input?.lab_data || ''; labImages.value = [] }
  if (h.mode === 'nhi') { nhiInput.value = h.input?.query || ''; nhiImages.value = [] }
  if (h.mode === 'interaction') { interactionInput.value = h.input?.drugs || ''; interactionImages.value = [] }
}

function handleDelete(id) {
  if (!confirm('確定要刪除？')) return
  deleteHistory(id)
  if (selectedHistoryId.value === id) { selectedHistoryId.value = null; currentResult.value = null }
}

function modeIcon(mode) { return modes.find((m) => m.key === mode)?.icon || '📋' }

function historyTitle(h) {
  if (h.mode === 'clinical') return (h.input?.scenario || '').slice(0, 30) || '臨床情境'
  if (h.mode === 'dose') return h.input?.drug || '藥物劑量'
  if (h.mode === 'lab') return (h.input?.lab_data || '').slice(0, 30) || 'Lab 鑑別'
  if (h.mode === 'nhi') return (h.input?.query || '').slice(0, 30) || '健保查詢'
  if (h.mode === 'interaction') return (h.input?.drugs || '').slice(0, 30) || '交互作用'
  return '查詢'
}

function formatDate(timestamp) {
  if (!timestamp) return ''
  const date = timestamp.toDate ? timestamp.toDate() : new Date(timestamp)
  const diff = Date.now() - date
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分鐘前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小時前`
  return date.toLocaleDateString('zh-TW', { month: 'short', day: 'numeric' })
}

function getCurrentInput() {
  if (activeMode.value === 'clinical') return { scenario: clinicalInput.value }
  if (activeMode.value === 'dose') return { drug: doseDrug.value }
  if (activeMode.value === 'lab') return { lab_data: labInput.value }
  if (activeMode.value === 'nhi') return { query: nhiInput.value }
  if (activeMode.value === 'interaction') return { drugs: interactionInput.value }
  return {}
}

async function saveToNotes() {
  if (!currentResult.value) return
  try {
    const title = historyTitle({ mode: activeMode.value, input: getCurrentInput() })
    await addDoc(collection(db, 'notes'), {
      title: `[Assist] ${title}`,
      content: currentResult.value,
      tags: ['Assist', activeMode.value],
      links: [],
      sources: [{ type: 'assist', mode: activeMode.value, saved_at: new Date().toISOString() }],
      created_at: serverTimestamp(),
      updated_at: serverTimestamp(),
    })
    const el = document.createElement('div')
    el.textContent = '已收進 Notes ✓'
    el.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);z-index:50;background:#7c3aed;color:white;padding:8px 16px;border-radius:12px;font-size:14px;box-shadow:0 4px 12px rgba(0,0,0,.15)'
    document.body.appendChild(el)
    setTimeout(() => el.remove(), 2000)
  } catch (e) { console.error('Save to notes error:', e) }
}

onUnmounted(() => unsubscribe())

function renderMd(text) {
  if (!text) return ''
  let html = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, l, c) => `<pre class="code-block"><code>${c.trim()}</code></pre>`)
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
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1 ↗</a>')
  html = html.replace(/\n\n/g, '</p><p>')
  html = html.replace(/\n/g, '<br>')
  html = `<p>${html}</p>`.replace(/<p>\s*<\/p>/g, '')
  return html
}
</script>

<style scoped>
.prose-assist :deep(h1) { font-size: 18px; font-weight: 600; margin: 16px 0 8px; }
.prose-assist :deep(h2) { font-size: 16px; font-weight: 600; margin: 14px 0 6px; color: #be123c; }
.prose-assist :deep(h3) { font-size: 14px; font-weight: 600; margin: 12px 0 4px; }
.prose-assist :deep(p) { margin-bottom: 8px; }
.prose-assist :deep(strong) { font-weight: 600; color: #1e293b; }
.prose-assist :deep(ul) { padding-left: 16px; margin: 8px 0; }
.prose-assist :deep(li) { list-style: disc; margin: 2px 0; }
.prose-assist :deep(li.ol) { list-style: decimal; }
.prose-assist :deep(blockquote) { border-left: 2px solid #e11d48; padding-left: 12px; color: #6b7280; font-style: italic; margin: 8px 0; }
.prose-assist :deep(.code-block) { background: #1e293b; color: #6ee7b7; font-size: 12px; padding: 12px; border-radius: 8px; margin: 8px 0; overflow-x: auto; }
.prose-assist :deep(.inline-code) { background: #fff1f2; color: #be123c; font-size: 12px; padding: 1px 6px; border-radius: 4px; font-family: monospace; }
.prose-assist :deep(a) { color: #e11d48; text-decoration: underline; }
</style>
