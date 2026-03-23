<template>
  <div>
    <h2 class="text-lg font-bold text-slate-800 mb-1">🗺️ Clinical Pathway</h2>
    <p class="text-xs text-slate-400 mb-4">結構化臨床決策路徑，含流程圖與互動式 AI 解讀。</p>

    <!-- Pathway selector -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-4" v-if="!selectedPathway">
      <button
        v-for="pw in pathways"
        :key="pw.id"
        class="text-left px-4 py-3 bg-white border border-slate-200 rounded-lg hover:border-rose-300 hover:bg-rose-50 transition-colors"
        @click="loadPathway(pw.id)"
      >
        <div class="text-sm font-bold text-slate-800">{{ pw.title_zh }}</div>
        <div class="text-xs text-slate-400 mt-1">{{ pw.title }}</div>
        <div class="text-[10px] text-slate-300 mt-1">{{ pw.version }}</div>
      </button>

      <div v-if="pathwayError" class="col-span-full text-center py-6">
        <div class="text-sm text-amber-600">{{ pathwayError }}</div>
        <button class="mt-2 text-xs text-rose-500 hover:text-rose-700" @click="pathwayError = null; fetchPathways()">重試</button>
      </div>
      <div v-else-if="!pathways.length && !pathwayLoading" class="col-span-full text-center py-6 text-sm text-slate-400">
        載入中...
      </div>
    </div>

    <!-- Selected Pathway detail -->
    <div v-if="selectedPathway" class="space-y-4">
      <div class="flex items-center justify-between">
        <div>
          <div class="text-base font-bold text-slate-800">{{ selectedPathway.title_zh }}</div>
          <div class="text-xs text-slate-400">{{ selectedPathway.title }} — {{ selectedPathway.version }}</div>
        </div>
        <button class="text-xs text-slate-400 hover:text-slate-600" @click="selectedPathway = null; interactiveResult = null">
          ← 返回列表
        </button>
      </div>

      <!-- Mermaid diagram -->
      <div v-if="selectedPathway.mermaid" class="bg-white rounded-xl border border-slate-200 p-4 overflow-x-auto">
        <div class="text-xs font-bold text-slate-500 mb-2">流程圖</div>
        <div ref="mermaidEl" class="mermaid-block text-center"></div>
      </div>

      <!-- Steps detail -->
      <div class="bg-white rounded-xl border border-slate-200 p-4">
        <div class="text-xs font-bold text-slate-500 mb-3">步驟明細</div>
        <div class="space-y-2">
          <div
            v-for="step in selectedPathway.steps"
            :key="step.id"
            class="flex gap-3 px-3 py-2 rounded-lg hover:bg-slate-50 transition-colors"
          >
            <span class="shrink-0 w-8 h-8 flex items-center justify-center bg-rose-100 text-rose-600 text-xs font-bold rounded-full">
              {{ step.id }}
            </span>
            <div class="flex-1 min-w-0">
              <div class="text-sm font-bold text-slate-700">{{ step.label }}</div>
              <div class="text-xs text-slate-500 mt-0.5">{{ step.detail }}</div>
              <div v-if="step.next?.length" class="text-[10px] text-slate-300 mt-1">
                → {{ step.next.join(', ') }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- References -->
      <div v-if="selectedPathway.references?.length" class="text-[10px] text-slate-400 space-y-0.5">
        <div class="font-bold">References:</div>
        <div v-for="r in selectedPathway.references" :key="r">{{ r }}</div>
      </div>

      <!-- Interactive: patient data input -->
      <div class="bg-amber-50 border border-amber-200 rounded-xl p-4">
        <div class="text-xs font-bold text-amber-700 mb-2">互動式 AI 解讀：輸入病人資料，AI 會判斷在路徑中的位置</div>
        <textarea
          v-model="patientData"
          rows="4"
          class="w-full text-sm border border-amber-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-amber-400 resize-none bg-white"
          placeholder="輸入病人相關資料...
例如：68 歲男性，Cr 從 0.9 升至 3.2 (48h)，尿量 300mL/12h，目前使用 NSAIDs..."
        />
        <button
          :disabled="!patientData.trim() || interactiveLoading"
          class="mt-2 px-5 py-2.5 bg-amber-600 hover:bg-amber-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          @click="runInteractive"
        >
          {{ interactiveLoading ? 'AI 分析中...' : '🤖 AI 路徑解讀' }}
        </button>
      </div>

      <!-- Interactive result -->
      <div v-if="interactiveResult" class="bg-white rounded-xl border border-slate-200 p-5">
        <div class="prose-assist text-sm text-slate-700 leading-relaxed" ref="interactiveResultEl" v-html="renderMd(interactiveResult)" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick } from 'vue'
import { renderMd } from '../../utils/renderMarkdown.js'
import { renderMermaidIn } from '../../composables/useMermaid.js'
import { useAuth } from '../../composables/useAuth.js'

const { authFetch, API_BASE } = useAuth()

const pathways = ref([])
const selectedPathway = ref(null)
const pathwayLoading = ref(false)
const patientData = ref('')
const interactiveResult = ref(null)
const interactiveLoading = ref(false)
const mermaidEl = ref(null)
const interactiveResultEl = ref(null)

onMounted(fetchPathways)

const pathwayError = ref(null)

async function fetchPathways() {
  try {
    const res = await fetch(`${API_BASE}/pathways/list`)
    if (!res.ok) throw new Error(`API 回應 ${res.status}`)
    const data = await res.json()
    pathways.value = data.pathways || []
  } catch (e) {
    console.error('Fetch pathways error:', e)
    pathwayError.value = '無法載入 Clinical Pathways（後端 API 可能尚未部署此端點）'
  }
}

async function loadPathway(id) {
  pathwayLoading.value = true
  interactiveResult.value = null
  patientData.value = ''
  pathwayError.value = null

  try {
    const res = await fetch(`${API_BASE}/pathways/${id}`)
    if (!res.ok) throw new Error(`API 回應 ${res.status}`)
    const data = await res.json()
    selectedPathway.value = data
    await nextTick()
    renderMermaid()
  } catch (e) {
    console.error('Load pathway error:', e)
    pathwayError.value = `無法載入路徑: ${e.message}`
  } finally {
    pathwayLoading.value = false
  }
}

function renderMermaid() {
  if (!mermaidEl.value || !selectedPathway.value?.mermaid) return
  mermaidEl.value.innerHTML = `<pre class="mermaid">${selectedPathway.value.mermaid}</pre>`
  renderMermaidIn(mermaidEl.value)
}

watch(interactiveResult, () => nextTick(() => renderMermaidIn(interactiveResultEl.value)))

async function runInteractive() {
  if (!selectedPathway.value || !patientData.value.trim()) return
  interactiveLoading.value = true
  interactiveResult.value = null

  try {
    const res = await authFetch(`${API_BASE}/pathways/${selectedPathway.value.id}/interactive`, {
      method: 'POST',
      body: JSON.stringify({ patient_data: patientData.value }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.error || `API error ${res.status}`)
    interactiveResult.value = data.result
  } catch (e) {
    console.error('Interactive pathway error:', e)
    interactiveResult.value = `> ⚠️ 錯誤: ${e.message}`
  } finally {
    interactiveLoading.value = false
  }
}

// Expose for AssistPage
function setInput(input) {
  selectedPathway.value = null
  patientData.value = ''
  interactiveResult.value = null
}
function getInput() { return { pathway: selectedPathway.value?.id, patient_data: patientData.value } }
function getTitle() { return selectedPathway.value?.title_zh || 'Clinical Pathway' }

defineExpose({ setInput, getInput, getTitle })
</script>
