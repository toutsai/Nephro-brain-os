<template>
  <div class="h-[calc(100vh-44px)] flex flex-col bg-slate-50 overflow-hidden pb-14 sm:pb-0">
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

    <div class="flex-1 overflow-hidden flex flex-col lg:flex-row">

      <!-- Mobile mode selector + history toggle -->
      <div class="lg:hidden bg-white border-b border-slate-100 shrink-0">
        <div class="px-4 py-2 overflow-x-auto">
          <div class="flex gap-2 whitespace-nowrap">
            <button
              v-for="m in modes"
              :key="m.key"
              class="shrink-0 px-3 py-1.5 text-xs font-medium rounded-full transition-colors"
              :class="activeMode === m.key
                ? 'bg-rose-100 text-rose-700 border border-rose-200'
                : 'bg-slate-100 text-slate-600'"
              @click="switchMode(m.key)"
            >
              {{ m.icon }} {{ m.label }}
            </button>
            <button
              class="shrink-0 px-3 py-1.5 text-xs font-medium rounded-full bg-slate-100 text-slate-500"
              @click="showMobileHistory = true"
            >
              📜 歷史
            </button>
          </div>
        </div>
      </div>

      <!-- Mobile history bottom sheet -->
      <Teleport to="body">
        <div
          v-if="showMobileHistory && isMobile"
          class="fixed inset-0 bg-black/50 z-40 lg:hidden"
          @click="showMobileHistory = false"
        >
          <div
            class="absolute inset-x-0 bottom-0 max-h-[70vh] overflow-hidden bg-white rounded-t-2xl flex flex-col"
            @click.stop
          >
            <div class="sticky top-0 bg-white p-3 border-b border-slate-100 flex justify-between items-center shrink-0">
              <span class="text-sm font-medium text-slate-600">歷史紀錄</span>
              <button class="text-slate-400 hover:text-slate-600 text-lg" @click="showMobileHistory = false">✕</button>
            </div>
            <div class="flex-1 overflow-y-auto">
              <div v-if="!history.length" class="px-3 py-8 text-xs text-slate-400 text-center">尚無紀錄</div>
              <div
                v-for="h in history"
                :key="h.id"
                class="px-4 py-3 border-b border-slate-50 cursor-pointer active:bg-slate-50 transition-colors"
                @click="viewHistory(h); showMobileHistory = false"
              >
                <div class="flex items-center gap-1.5">
                  <span class="text-xs">{{ modeIcon(h.mode) }}</span>
                  <span class="text-sm font-medium text-slate-700 truncate">{{ historyTitle(h) }}</span>
                </div>
                <div class="flex items-center justify-between mt-1">
                  <span class="text-[10px] text-slate-400">{{ formatDate(h.created_at) }}</span>
                  <button
                    class="text-xs text-slate-300 hover:text-red-400"
                    @click.stop="handleDelete(h.id)"
                  >刪除</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Teleport>

      <!-- Left: mode selector + history (desktop only) -->
      <aside class="hidden lg:flex w-72 border-r border-slate-200 bg-white flex-col shrink-0">
        <!-- Mode groups -->
        <div class="p-3 space-y-1 border-b border-slate-100 max-h-[55vh] overflow-y-auto">
          <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider px-2 pt-1">AI 輔助</div>
          <button
            v-for="m in aiModes"
            :key="m.key"
            class="w-full text-left px-3 py-2 rounded-lg transition-colors"
            :class="activeMode === m.key
              ? 'bg-rose-50 border border-rose-200 text-rose-700'
              : 'hover:bg-slate-50 text-slate-600'"
            @click="switchMode(m.key)"
          >
            <div class="flex items-center gap-2">
              <span class="text-base">{{ m.icon }}</span>
              <div>
                <div class="text-xs font-bold">{{ m.label }}</div>
                <div class="text-[10px] text-slate-400">{{ m.desc }}</div>
              </div>
            </div>
          </button>

          <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider px-2 pt-2">零成本工具</div>
          <button
            v-for="m in toolModes"
            :key="m.key"
            class="w-full text-left px-3 py-2 rounded-lg transition-colors"
            :class="activeMode === m.key
              ? 'bg-emerald-50 border border-emerald-200 text-emerald-700'
              : 'hover:bg-slate-50 text-slate-600'"
            @click="switchMode(m.key)"
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
        <div class="max-w-4xl mx-auto px-4 sm:px-6 py-6">

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

            <ImageUploader v-model="clinicalImages" :to-base64="fileToBase64" class="mt-3" />

            <button
              :disabled="(!clinicalInput.trim() && !clinicalImages.length) || generating || !isLoggedIn"
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

            <ImageUploader v-model="doseImages" :to-base64="fileToBase64" class="mb-3" />

            <button
              :disabled="(!doseDrug.trim() && !doseImages.length) || generating || !isLoggedIn"
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

            <ImageUploader v-model="labImages" :to-base64="fileToBase64" class="mt-3" />

            <button
              :disabled="(!labInput.trim() && !labImages.length) || generating || !isLoggedIn"
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

            <ImageUploader v-model="nhiImages" :to-base64="fileToBase64" class="mt-3" />

            <button
              :disabled="(!nhiInput.trim() && !nhiImages.length) || generating || !isLoggedIn"
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

            <ImageUploader v-model="interactionImages" :to-base64="fileToBase64" class="mt-3" />

            <button
              :disabled="(!interactionInput.trim() && !interactionImages.length) || generating || !isLoggedIn"
              class="mt-3 px-5 py-2.5 bg-rose-600 hover:bg-rose-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              @click="submitInteraction"
            >
              {{ generating ? '檢查中...' : '⚡ 檢查交互作用' }}
            </button>
          </div>

          <!-- ============ Transplant ============ -->
          <div v-if="activeMode === 'transplant'">
            <AssistTransplant
              :loading="generating"
              :to-base64="fileToBase64"
              @submit="handleAiSubmit"
            />
          </div>

          <!-- ============ PD ============ -->
          <div v-if="activeMode === 'pd'">
            <AssistPD
              :loading="generating"
              :to-base64="fileToBase64"
              @submit="handleAiSubmit"
            />
          </div>

          <!-- ============ Calculator ============ -->
          <div v-if="activeMode === 'calculator'">
            <AssistCalculator />
          </div>

          <!-- ============ Drug Search ============ -->
          <div v-if="activeMode === 'drug_search'">
            <AssistDrugSearch />
          </div>

          <!-- ============ Pathway ============ -->
          <div v-if="activeMode === 'pathway'">
            <AssistPathway />
          </div>


          <!-- ============ Guest Lock ============ -->
          <GuestLock />

          <!-- ============ Generating ============ -->
          <div v-if="generating" class="mt-6 flex items-center gap-3 px-4 py-3 bg-rose-50 border border-rose-200 rounded-xl">
            <div class="w-5 h-5 border-2 border-rose-500 border-t-transparent rounded-full animate-spin" />
            <span class="text-sm text-rose-700">AI 正在分析，搜尋最新實證...</span>
          </div>

          <!-- ============ Error ============ -->
          <div v-if="assistError" class="mt-4 px-4 py-2 bg-red-50 border border-red-200 rounded-lg text-xs text-red-600">
            ⚠️ {{ assistError }}
          </div>

          <!-- ============ Result (AI modes only) ============ -->
          <div v-if="currentResult && !isToolMode(activeMode)" class="mt-6">
            <div class="mb-4 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg text-[10px] text-amber-700">
              ⚠️ 此建議由 AI 根據實證醫學資料生成，僅供臨床參考。實際治療決策應由主治醫師根據完整病歷資訊做出判斷。
            </div>

            <div class="bg-white rounded-xl border border-slate-200 p-6">
              <div ref="assistResultEl" class="prose-assist text-sm text-slate-700 leading-relaxed" v-html="renderMd(currentResult)" />
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

    <!-- Selection → Note / Teach toolbar -->
    <SelectionToolbar
      source-type="assist"
      :source-meta="{ mode: activeMode }"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { collection, addDoc, serverTimestamp } from 'firebase/firestore'
import { db } from '../firebase.js'
import { useAssist } from '../composables/useAssist.js'
import ImageUploader from '../components/ImageUploader.vue'
import SelectionToolbar from '../components/SelectionToolbar.vue'
import GuestLock from '../components/GuestLock.vue'
import { useAuth } from '../composables/useAuth.js'
import AssistCalculator from '../components/assist/AssistCalculator.vue'
import AssistDrugSearch from '../components/assist/AssistDrugSearch.vue'
import AssistPathway from '../components/assist/AssistPathway.vue'
import AssistTransplant from '../components/assist/AssistTransplant.vue'
import AssistPD from '../components/assist/AssistPD.vue'
import { renderMd } from '../utils/renderMarkdown.js'
import { renderMermaidIn } from '../composables/useMermaid.js'

const { isLoggedIn, uid } = useAuth()

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

// Mobile
const isMobile = ref(false)
const showMobileHistory = ref(false)
function checkMobile() { isMobile.value = window.innerWidth < 1024 }
onMounted(() => { checkMobile(); window.addEventListener('resize', checkMobile) })

// Mode
const activeMode = ref('clinical')
const selectedHistoryId = ref(null)
const currentResult = ref(null)
const assistResultEl = ref(null)

watch(currentResult, () => nextTick(() => renderMermaidIn(assistResultEl.value)))

// --- Mode definitions ---
const aiModes = [
  { key: 'clinical', icon: '🏥', label: '臨床情境', desc: '實證指引建議' },
  { key: 'dose', icon: '💊', label: '劑量調整', desc: '腎功能藥物劑量' },
  { key: 'lab', icon: '🔬', label: 'Lab 鑑別', desc: '檢驗鑑別診斷' },
  { key: 'nhi', icon: '🏛️', label: '健保查詢', desc: '台灣健保給付規則' },
  { key: 'interaction', icon: '⚡', label: '交互作用', desc: '藥物交互作用檢查' },
  { key: 'transplant', icon: '🫘', label: '移植諮詢', desc: '腎臟移植決策' },
  { key: 'pd', icon: '🔄', label: 'PD 諮詢', desc: '腹膜透析管理' },
]

const toolModes = [
  { key: 'calculator', icon: '🧮', label: '計算器', desc: '16 種臨床計算' },
  { key: 'drug_search', icon: '📦', label: '藥物搜尋', desc: '藥物資料庫查詢' },
  { key: 'pathway', icon: '🗺️', label: 'Pathway', desc: '臨床決策路徑' },
]

const modes = computed(() => [...aiModes, ...toolModes])

const TOOL_MODES = new Set(['calculator', 'drug_search', 'pathway'])
function isToolMode(mode) { return TOOL_MODES.has(mode) }

function switchMode(key) {
  activeMode.value = key
  selectedHistoryId.value = null
  currentResult.value = null
}

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

// === Submit (existing modes) ===
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

// === Generic AI submit handler (for transplant, pd) ===
async function handleAiSubmit({ mode, payload, images }) {
  const res = await queryAssist({ mode, payload, images })
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
  if (h.mode === 'transplant' || h.mode === 'pd') { /* sub-components handle their own state */ }
}

function handleDelete(id) {
  if (!confirm('確定要刪除？')) return
  deleteHistory(id)
  if (selectedHistoryId.value === id) { selectedHistoryId.value = null; currentResult.value = null }
}

function modeIcon(mode) { return modes.value.find((m) => m.key === mode)?.icon || '📋' }

function historyTitle(h) {
  if (h.mode === 'clinical') return (h.input?.scenario || '').slice(0, 30) || '臨床情境'
  if (h.mode === 'dose') return h.input?.drug || '藥物劑量'
  if (h.mode === 'lab') return (h.input?.lab_data || '').slice(0, 30) || 'Lab 鑑別'
  if (h.mode === 'nhi') return (h.input?.query || '').slice(0, 30) || '健保查詢'
  if (h.mode === 'interaction') return (h.input?.drugs || '').slice(0, 30) || '交互作用'
  if (h.mode === 'transplant') return (h.input?.scenario || '').slice(0, 30) || '移植諮詢'
  if (h.mode === 'pd') return (h.input?.scenario || '').slice(0, 30) || 'PD 諮詢'
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
      userId: uid.value,
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

onUnmounted(() => { window.removeEventListener('resize', checkMobile); unsubscribe() })


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
.prose-assist :deep(.table-wrap) { overflow-x: auto; margin: 12px 0; }
.prose-assist :deep(table) { width: 100%; border-collapse: collapse; font-size: 13px; }
.prose-assist :deep(th) { background: #f8fafc; font-weight: 600; color: #1e293b; padding: 8px 12px; border: 1px solid #e2e8f0; white-space: nowrap; }
.prose-assist :deep(td) { padding: 8px 12px; border: 1px solid #e2e8f0; color: #334155; }
.prose-assist :deep(tbody tr:hover) { background: #f8fafc; }
.prose-assist :deep(tr:nth-child(even) td) { background: #f8fafc; }

/* Summary card */
.prose-assist :deep(.summary-card) { background: linear-gradient(135deg, #fff1f2 0%, #fef2f2 100%); border: 1px solid #fecaca; border-radius: 12px; padding: 14px 18px; margin-bottom: 16px; }
.prose-assist :deep(.summary-card .summary-title) { font-weight: 700; font-size: 13px; color: #9f1239; margin-bottom: 8px; }
.prose-assist :deep(.summary-card ul) { padding-left: 18px; margin: 0; }
.prose-assist :deep(.summary-card li) { list-style: disc; font-size: 13px; color: #1e293b; line-height: 1.6; margin-bottom: 4px; }
.prose-assist :deep(.summary-card strong) { color: #9f1239; }

/* Mermaid */
.prose-assist :deep(.mermaid-block) { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; margin: 16px 0; overflow-x: auto; text-align: center; }
.prose-assist :deep(.mermaid-block svg) { max-width: 100%; height: auto; }
</style>
