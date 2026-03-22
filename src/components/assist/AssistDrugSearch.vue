<template>
  <div>
    <h2 class="text-lg font-bold text-slate-800 mb-1">📦 藥物資料庫搜尋</h2>
    <p class="text-xs text-slate-400 mb-4">搜尋腎臟科常用藥物的劑量調整、交互作用與注意事項（零 AI 成本）。</p>

    <!-- Search input -->
    <div class="relative mb-4">
      <input
        v-model="searchQuery"
        class="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 pr-20 focus:outline-none focus:ring-2 focus:ring-rose-400"
        placeholder="輸入藥物名稱（中英文皆可）... 例如：vancomycin、達格列淨"
        @input="debouncedSearch"
        @keydown.enter="doSearch"
      />
      <button
        class="absolute right-1 top-1 px-3 py-1 bg-rose-600 hover:bg-rose-500 text-white text-xs font-medium rounded-md transition-colors"
        @click="doSearch"
      >
        搜尋
      </button>
    </div>

    <!-- Search results list -->
    <div v-if="searchResults.length && !selectedDrug" class="space-y-2 mb-4">
      <div class="text-xs text-slate-500 mb-1">找到 {{ searchResults.length }} 種藥物：</div>
      <button
        v-for="drug in searchResults"
        :key="drug.drug_name_en"
        class="w-full text-left px-4 py-3 bg-white border border-slate-200 rounded-lg hover:border-rose-300 hover:bg-rose-50 transition-colors"
        @click="selectDrug(drug)"
      >
        <div class="flex items-center justify-between">
          <div>
            <span class="text-sm font-bold text-slate-800">{{ drug.drug_name_en }}</span>
            <span class="text-sm text-slate-500 ml-2">{{ drug.drug_name_zh }}</span>
          </div>
          <span class="text-[10px] px-2 py-0.5 rounded-full" :class="drug.nephrotoxic ? 'bg-red-100 text-red-600' : 'bg-green-100 text-green-600'">
            {{ drug.nephrotoxic ? '腎毒性' : '非腎毒性' }}
          </span>
        </div>
        <div class="text-xs text-slate-400 mt-1">{{ drug.class_zh }} | 排除: {{ drug.elimination }}</div>
      </button>
    </div>

    <!-- Drug detail card -->
    <div v-if="selectedDrug" class="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div class="bg-rose-50 px-5 py-3 border-b border-rose-100 flex items-center justify-between">
        <div>
          <div class="text-base font-bold text-slate-800">{{ selectedDrug.drug_name_en }}</div>
          <div class="text-sm text-slate-500">{{ selectedDrug.drug_name_zh }} — {{ selectedDrug.class_zh }}</div>
        </div>
        <button class="text-xs text-slate-400 hover:text-slate-600" @click="selectedDrug = null">✕ 關閉</button>
      </div>

      <div class="p-5 space-y-4 text-sm">
        <!-- Basic info -->
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div class="bg-slate-50 rounded-lg p-3 text-center">
            <div class="text-[10px] text-slate-400 mb-1">排除途徑</div>
            <div class="font-bold text-slate-700">{{ selectedDrug.elimination }}</div>
          </div>
          <div class="bg-slate-50 rounded-lg p-3 text-center">
            <div class="text-[10px] text-slate-400 mb-1">蛋白結合率</div>
            <div class="font-bold text-slate-700">{{ selectedDrug.protein_binding }}</div>
          </div>
          <div class="bg-slate-50 rounded-lg p-3 text-center">
            <div class="text-[10px] text-slate-400 mb-1">可透析</div>
            <div class="font-bold" :class="selectedDrug.dialyzable ? 'text-blue-600' : 'text-slate-500'">
              {{ selectedDrug.dialyzable ? '是' : '否' }}
            </div>
          </div>
          <div class="bg-slate-50 rounded-lg p-3 text-center">
            <div class="text-[10px] text-slate-400 mb-1">腎毒性</div>
            <div class="font-bold" :class="selectedDrug.nephrotoxic ? 'text-red-600' : 'text-green-600'">
              {{ selectedDrug.nephrotoxic ? '是' : '否' }}
            </div>
          </div>
        </div>

        <!-- Dose adjustments table -->
        <div>
          <div class="text-xs font-bold text-slate-600 mb-2">劑量調整</div>
          <div class="overflow-x-auto">
            <table class="w-full text-xs border-collapse">
              <thead>
                <tr class="bg-slate-50">
                  <th class="text-left px-3 py-2 border border-slate-200 font-bold">腎功能</th>
                  <th class="text-left px-3 py-2 border border-slate-200 font-bold">劑量</th>
                  <th class="text-left px-3 py-2 border border-slate-200 font-bold">頻率</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(adj, stage) in selectedDrug.dose_adjustments" :key="stage" class="hover:bg-slate-50">
                  <td class="px-3 py-2 border border-slate-200 font-medium" :class="stageClass(stage)">{{ stageLabel(stage) }}</td>
                  <td class="px-3 py-2 border border-slate-200">{{ adj.dose }}</td>
                  <td class="px-3 py-2 border border-slate-200">{{ adj.frequency }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Dialysis supplement -->
        <div v-if="selectedDrug.dialysis_supplement">
          <div class="text-xs font-bold text-slate-600 mb-1">透析補充</div>
          <div class="text-xs text-slate-600 bg-blue-50 border border-blue-200 rounded-lg px-3 py-2">
            {{ selectedDrug.dialysis_supplement }}
          </div>
        </div>

        <!-- Monitoring -->
        <div v-if="selectedDrug.monitoring?.length">
          <div class="text-xs font-bold text-slate-600 mb-1">監測項目</div>
          <div class="flex flex-wrap gap-1.5">
            <span v-for="m in selectedDrug.monitoring" :key="m" class="text-[10px] px-2 py-1 bg-emerald-50 text-emerald-700 rounded-full border border-emerald-200">
              {{ m }}
            </span>
          </div>
        </div>

        <!-- Interactions -->
        <div v-if="selectedDrug.interactions_major?.length">
          <div class="text-xs font-bold text-red-600 mb-1">重要交互作用</div>
          <ul class="list-disc list-inside text-xs text-slate-600 space-y-1">
            <li v-for="i in selectedDrug.interactions_major" :key="i">{{ i }}</li>
          </ul>
        </div>

        <!-- Contraindications -->
        <div v-if="selectedDrug.contraindications?.length">
          <div class="text-xs font-bold text-red-600 mb-1">禁忌症</div>
          <ul class="list-disc list-inside text-xs text-slate-600 space-y-1">
            <li v-for="c in selectedDrug.contraindications" :key="c">{{ c }}</li>
          </ul>
        </div>
      </div>
    </div>

    <!-- No result -->
    <div v-if="searched && !searchResults.length && !selectedDrug" class="text-center py-8">
      <div class="text-slate-400 text-sm">找不到藥物「{{ searchQuery }}」</div>
      <div class="text-xs text-slate-300 mt-1">可嘗試用英文名稱搜尋，或使用「劑量調整」模式透過 AI 查詢</div>
    </div>

    <!-- All drugs (when no search) -->
    <div v-if="!searched && !selectedDrug" class="space-y-2">
      <div class="text-xs text-slate-500 mb-1">資料庫共 {{ allDrugs.length }} 種藥物：</div>
      <button
        v-for="drug in allDrugs"
        :key="drug.drug_name_en"
        class="w-full text-left px-4 py-3 bg-white border border-slate-200 rounded-lg hover:border-rose-300 hover:bg-rose-50 transition-colors"
        @click="selectDrug(drug)"
      >
        <div class="flex items-center justify-between">
          <div>
            <span class="text-sm font-bold text-slate-800">{{ drug.drug_name_en }}</span>
            <span class="text-sm text-slate-500 ml-2">{{ drug.drug_name_zh }}</span>
          </div>
          <span class="text-[10px] px-2 py-0.5 rounded-full" :class="drug.nephrotoxic ? 'bg-red-100 text-red-600' : 'bg-green-100 text-green-600'">
            {{ drug.nephrotoxic ? '腎毒性' : '非腎毒性' }}
          </span>
        </div>
        <div class="text-xs text-slate-400 mt-1">{{ drug.class_zh }} | 排除: {{ drug.elimination }}</div>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import drugDB from '../../../backend/drug_database.json'

const searchQuery = ref('')
const searchResults = ref([])
const selectedDrug = ref(null)
const searched = ref(false)

// Build local drug list from imported JSON
const allDrugs = computed(() => Object.values(drugDB))

let debounceTimer = null

function debouncedSearch() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    if (searchQuery.value.trim().length >= 2) doSearch()
    else if (!searchQuery.value.trim()) { searched.value = false; searchResults.value = [] }
  }, 300)
}

function doSearch() {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return

  searched.value = true
  selectedDrug.value = null

  // Local search (instant, no API needed)
  const results = []
  for (const [key, drug] of Object.entries(drugDB)) {
    if (
      key.toLowerCase().includes(q) ||
      (drug.drug_name_en || '').toLowerCase().includes(q) ||
      (drug.drug_name_zh || '').includes(q) ||
      (drug.class_zh || '').includes(q) ||
      (drug.class_en || '').toLowerCase().includes(q)
    ) {
      results.push(drug)
    }
  }
  searchResults.value = results
}

function selectDrug(drug) {
  selectedDrug.value = drug
}

const STAGE_LABELS = {
  normal: '正常腎功能',
  ckd_3: 'CKD Stage 3',
  ckd_4: 'CKD Stage 4',
  ckd_5: 'CKD Stage 5',
  hd: '血液透析 (HD)',
  pd: '腹膜透析 (PD)',
  crrt: 'CRRT',
}

function stageLabel(stage) { return STAGE_LABELS[stage] || stage }
function stageClass(stage) {
  if (stage === 'hd' || stage === 'pd' || stage === 'crrt') return 'text-blue-600'
  if (stage === 'ckd_5') return 'text-red-600'
  if (stage === 'ckd_4') return 'text-orange-600'
  return 'text-slate-700'
}

// Expose for AssistPage integration
function setInput(input) { searchQuery.value = input?.query || ''; searchResults.value = []; selectedDrug.value = null; searched.value = false }
function getInput() { return { query: searchQuery.value } }
function getTitle() { return selectedDrug.value?.drug_name_en || searchQuery.value || '藥物搜尋' }

defineExpose({ setInput, getInput, getTitle })
</script>
