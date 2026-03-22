<template>
  <div>
    <h2 class="text-lg font-bold text-slate-800 mb-1">🧮 臨床計算器</h2>
    <p class="text-xs text-slate-400 mb-4">腎臟科常用計算工具，純數學計算、零 AI 成本、即時結果。</p>

    <!-- Calculator selector -->
    <div class="mb-4">
      <label class="block text-xs font-bold text-slate-600 mb-1">選擇計算器</label>
      <select
        v-model="selectedCalc"
        class="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-rose-400 bg-white"
        @change="resetResult"
      >
        <option value="">-- 請選擇 --</option>
        <optgroup label="腎功能評估">
          <option value="egfr">eGFR (CKD-EPI 2021)</option>
          <option value="ckd_stage">CKD 分期</option>
          <option value="aki_staging">AKI 分期 (KDIGO)</option>
        </optgroup>
        <optgroup label="腎小管功能">
          <option value="fena">FENa (鈉排泄分率)</option>
          <option value="feurea">FEUrea (尿素排泄分率)</option>
          <option value="ttkg">TTKG (跨管鉀梯度)</option>
          <option value="urine_ag">Urine Anion Gap</option>
        </optgroup>
        <optgroup label="電解質">
          <option value="serum_ag">Serum Anion Gap</option>
          <option value="corrected_ca">校正鈣</option>
          <option value="ca_p_product">鈣磷乘積</option>
          <option value="corrected_na">校正鈉</option>
        </optgroup>
        <optgroup label="滲透壓">
          <option value="plasma_osm">血漿滲透壓</option>
          <option value="osm_gap">滲透壓差距</option>
          <option value="winter">Winter's Formula</option>
        </optgroup>
        <optgroup label="透析">
          <option value="kt_v">Kt/V (Daugirdas)</option>
          <option value="urr">URR</option>
        </optgroup>
        <optgroup label="病理分類">
          <option value="mest_c">MEST-C (IgA 腎病)</option>
        </optgroup>
      </select>
    </div>

    <!-- Dynamic parameter inputs -->
    <div v-if="selectedCalc && calcMeta" class="space-y-3 mb-4">
      <div class="text-sm font-bold text-slate-700">{{ calcMeta.name }}</div>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div v-for="param in calcMeta.params" :key="param">
          <label class="block text-xs font-bold text-slate-600 mb-1">{{ paramLabel(param) }}</label>
          <input
            v-if="param !== 'sex'"
            v-model="paramValues[param]"
            :type="paramInputType(param)"
            class="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-rose-400"
            :placeholder="paramPlaceholder(param)"
          />
          <select
            v-else
            v-model="paramValues[param]"
            class="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-rose-400 bg-white"
          >
            <option value="male">男 Male</option>
            <option value="female">女 Female</option>
          </select>
        </div>
      </div>
    </div>

    <button
      v-if="selectedCalc"
      :disabled="!canCompute || computing"
      class="px-5 py-2.5 bg-rose-600 hover:bg-rose-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
      @click="compute"
    >
      {{ computing ? '計算中...' : '🧮 計算' }}
    </button>

    <!-- Result -->
    <div v-if="calcResult" class="mt-5 bg-white rounded-xl border border-slate-200 p-5">
      <div class="flex items-baseline gap-3 mb-3">
        <span class="text-2xl font-bold text-rose-600">{{ calcResult.value }}</span>
        <span class="text-sm text-slate-500">{{ calcResult.unit }}</span>
      </div>
      <div class="text-sm text-slate-700 mb-2">{{ calcResult.interpretation }}</div>
      <div class="text-xs text-slate-400">
        <div>正常範圍: {{ calcResult.normal_range }}</div>
        <div class="mt-1">Reference: {{ calcResult.reference }}</div>
      </div>
    </div>

    <!-- Error -->
    <div v-if="calcError" class="mt-4 px-4 py-2 bg-red-50 border border-red-200 rounded-lg text-xs text-red-600">
      {{ calcError }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const API_BASE = 'https://nephro-brain-api-761804517300.asia-east1.run.app'

const CALC_META = {
  egfr: { name: 'eGFR (CKD-EPI 2021)', params: ['creatinine', 'age', 'sex'] },
  ckd_stage: { name: 'CKD 分期', params: ['egfr'] },
  aki_staging: { name: 'AKI 分期 (KDIGO)', params: ['baseline_cr', 'current_cr'] },
  fena: { name: 'FENa (鈉排泄分率)', params: ['urine_na', 'plasma_na', 'urine_cr', 'plasma_cr'] },
  feurea: { name: 'FEUrea', params: ['urine_urea', 'plasma_urea', 'urine_cr', 'plasma_cr'] },
  ttkg: { name: 'TTKG (跨管鉀梯度)', params: ['urine_k', 'plasma_k', 'urine_osm', 'plasma_osm'] },
  urine_ag: { name: 'Urine Anion Gap', params: ['urine_na', 'urine_k', 'urine_cl'] },
  serum_ag: { name: 'Serum Anion Gap', params: ['na', 'cl', 'hco3'] },
  corrected_ca: { name: '校正鈣', params: ['total_ca', 'albumin'] },
  ca_p_product: { name: '鈣磷乘積', params: ['ca', 'phos'] },
  kt_v: { name: 'Kt/V (Daugirdas)', params: ['pre_bun', 'post_bun', 't_hours', 'uf_liters', 'post_weight_kg'] },
  urr: { name: 'URR', params: ['pre_bun', 'post_bun'] },
  corrected_na: { name: '校正鈉', params: ['measured_na', 'glucose_mg_dl'] },
  plasma_osm: { name: '血漿滲透壓', params: ['na', 'bun_mg_dl', 'glucose_mg_dl'] },
  osm_gap: { name: '滲透壓差距', params: ['measured_osm', 'na', 'bun_mg_dl', 'glucose_mg_dl'] },
  winter: { name: "Winter's Formula", params: ['hco3'] },
  mest_c: { name: 'MEST-C (IgA 腎病)', params: ['m', 'e', 's', 't', 'c'] },
}

const PARAM_LABELS = {
  creatinine: 'Creatinine (mg/dL)', age: '年齡 (歲)', sex: '性別',
  egfr: 'eGFR (mL/min/1.73m²)',
  baseline_cr: '基礎 Cr (mg/dL)', current_cr: '目前 Cr (mg/dL)',
  urine_na: 'Urine Na (mEq/L)', plasma_na: 'Plasma Na (mEq/L)',
  urine_cr: 'Urine Cr (mg/dL)', plasma_cr: 'Plasma Cr (mg/dL)',
  urine_urea: 'Urine Urea (mg/dL)', plasma_urea: 'Plasma Urea (mg/dL)',
  urine_k: 'Urine K (mEq/L)', plasma_k: 'Plasma K (mEq/L)',
  urine_osm: 'Urine Osm (mOsm/kg)', plasma_osm: 'Plasma Osm (mOsm/kg)',
  urine_cl: 'Urine Cl (mEq/L)',
  na: 'Na (mEq/L)', cl: 'Cl (mEq/L)', hco3: 'HCO3 (mEq/L)',
  total_ca: 'Total Ca (mg/dL)', albumin: 'Albumin (g/dL)',
  ca: 'Ca (mg/dL)', phos: 'P (mg/dL)',
  pre_bun: 'Pre-dialysis BUN (mg/dL)', post_bun: 'Post-dialysis BUN (mg/dL)',
  t_hours: '透析時間 (hours)', uf_liters: '超濾量 (L)', post_weight_kg: '透析後體重 (kg)',
  measured_na: 'Measured Na (mEq/L)', glucose_mg_dl: 'Glucose (mg/dL)',
  bun_mg_dl: 'BUN (mg/dL)', measured_osm: 'Measured Osm (mOsm/kg)',
  m: 'M (Mesangial, 0-1)', e: 'E (Endocapillary, 0-1)',
  s: 'S (Segmental, 0-1)', t: 'T (Tubular, 0-2)', c: 'C (Crescent, 0-2)',
}

const selectedCalc = ref('')
const paramValues = ref({})
const calcResult = ref(null)
const calcError = ref(null)
const computing = ref(false)

const calcMeta = computed(() => CALC_META[selectedCalc.value] || null)

const canCompute = computed(() => {
  if (!calcMeta.value) return false
  return calcMeta.value.params.every(p => paramValues.value[p] !== undefined && paramValues.value[p] !== '')
})

function paramLabel(param) { return PARAM_LABELS[param] || param }
function paramInputType(param) {
  if (['m', 'e', 's', 't', 'c'].includes(param)) return 'number'
  return 'number'
}
function paramPlaceholder(param) {
  const hints = { creatinine: '1.5', age: '60', egfr: '45', baseline_cr: '0.8', current_cr: '2.0' }
  return hints[param] || ''
}

function resetResult() {
  calcResult.value = null
  calcError.value = null
  paramValues.value = {}
  if (calcMeta.value) {
    calcMeta.value.params.forEach(p => {
      paramValues.value[p] = p === 'sex' ? 'male' : ''
    })
  }
}

// ---- Local calculation implementations (zero API dependency) ----
const LOCAL_CALCS = {
  egfr(p) {
    const cr = parseFloat(p.creatinine), age = parseFloat(p.age), sex = (p.sex || '').toLowerCase()
    const isFemale = ['female', 'f', '女'].includes(sex)
    let egfr
    if (isFemale) {
      egfr = cr <= 0.7 ? 142 * (cr / 0.7) ** (-0.241) * (0.9938 ** age) * 1.012
                        : 142 * (cr / 0.7) ** (-1.200) * (0.9938 ** age) * 1.012
    } else {
      egfr = cr <= 0.9 ? 142 * (cr / 0.9) ** (-0.302) * (0.9938 ** age)
                        : 142 * (cr / 0.9) ** (-1.200) * (0.9938 ** age)
    }
    egfr = Math.round(egfr * 10) / 10
    const stage = egfr >= 90 ? 'Stage 1' : egfr >= 60 ? 'Stage 2' : egfr >= 45 ? 'Stage 3a' : egfr >= 30 ? 'Stage 3b' : egfr >= 15 ? 'Stage 4' : 'Stage 5'
    return { value: egfr, unit: 'mL/min/1.73m²', interpretation: `eGFR ${egfr} → CKD ${stage}`, reference: 'CKD-EPI 2021', normal_range: '>90 mL/min/1.73m²' }
  },
  ckd_stage(p) {
    const e = parseFloat(p.egfr)
    const stage = e >= 90 ? '1' : e >= 60 ? '2' : e >= 45 ? '3a' : e >= 30 ? '3b' : e >= 15 ? '4' : '5'
    return { value: stage, unit: '', interpretation: `CKD Stage ${stage}`, reference: 'KDIGO 2024', normal_range: 'Stage 1 (eGFR ≥90)' }
  },
  aki_staging(p) {
    const base = parseFloat(p.baseline_cr), curr = parseFloat(p.current_cr)
    const ratio = curr / base, diff = curr - base
    const stage = ratio >= 3 || curr >= 4 ? 3 : ratio >= 2 ? 2 : diff >= 0.3 || ratio >= 1.5 ? 1 : 0
    return { value: stage, unit: '', interpretation: stage === 0 ? '未達 AKI 標準' : `AKI Stage ${stage} (Cr ratio ${ratio.toFixed(1)}, diff ${diff.toFixed(1)})`, reference: 'KDIGO 2024', normal_range: 'No AKI' }
  },
  fena(p) {
    const v = (parseFloat(p.urine_na) * parseFloat(p.plasma_cr)) / (parseFloat(p.plasma_na) * parseFloat(p.urine_cr)) * 100
    const r = Math.round(v * 100) / 100
    return { value: r, unit: '%', interpretation: r < 1 ? `FENa ${r}% → Pre-renal (< 1%)` : `FENa ${r}% → Intrinsic renal (≥ 1%)`, reference: 'Nephrology standard', normal_range: '<1% suggests pre-renal' }
  },
  feurea(p) {
    const v = (parseFloat(p.urine_urea) * parseFloat(p.plasma_cr)) / (parseFloat(p.plasma_urea) * parseFloat(p.urine_cr)) * 100
    const r = Math.round(v * 100) / 100
    return { value: r, unit: '%', interpretation: r < 35 ? `FEUrea ${r}% → Pre-renal (<35%)` : `FEUrea ${r}% → Intrinsic renal (≥35%)`, reference: 'Works with diuretics', normal_range: '<35% suggests pre-renal' }
  },
  serum_ag(p) {
    const v = parseFloat(p.na) - parseFloat(p.cl) - parseFloat(p.hco3)
    const r = Math.round(v * 10) / 10
    return { value: r, unit: 'mEq/L', interpretation: r > 12 ? `AG ${r} → Elevated (HAGMA)` : `AG ${r} → Normal`, reference: 'Standard', normal_range: '8-12 mEq/L' }
  },
  corrected_ca(p) {
    const v = parseFloat(p.total_ca) + 0.8 * (4.0 - parseFloat(p.albumin))
    const r = Math.round(v * 10) / 10
    return { value: r, unit: 'mg/dL', interpretation: `Corrected Ca ${r} mg/dL`, reference: 'Standard formula', normal_range: '8.5-10.5 mg/dL' }
  },
  ca_p_product(p) {
    const v = parseFloat(p.ca) * parseFloat(p.phos)
    const r = Math.round(v * 10) / 10
    return { value: r, unit: 'mg²/dL²', interpretation: r > 55 ? `Ca×P ${r} → Elevated (>55)` : `Ca×P ${r} → Normal`, reference: 'KDIGO CKD-MBD', normal_range: '<55 mg²/dL²' }
  },
  corrected_na(p) {
    const v = parseFloat(p.measured_na) + 1.6 * ((parseFloat(p.glucose_mg_dl) - 100) / 100)
    const r = Math.round(v * 10) / 10
    return { value: r, unit: 'mEq/L', interpretation: `Corrected Na ${r} mEq/L`, reference: 'Hillier modification', normal_range: '135-145 mEq/L' }
  },
  plasma_osm(p) {
    const v = 2 * parseFloat(p.na) + parseFloat(p.bun_mg_dl) / 2.8 + parseFloat(p.glucose_mg_dl) / 18
    const r = Math.round(v * 10) / 10
    return { value: r, unit: 'mOsm/kg', interpretation: `Calculated Osm ${r}`, reference: 'Standard formula', normal_range: '275-295 mOsm/kg' }
  },
  osm_gap(p) {
    const calc = 2 * parseFloat(p.na) + parseFloat(p.bun_mg_dl) / 2.8 + parseFloat(p.glucose_mg_dl) / 18
    const gap = parseFloat(p.measured_osm) - calc
    const r = Math.round(gap * 10) / 10
    return { value: r, unit: 'mOsm/kg', interpretation: r > 10 ? `Osmolal gap ${r} → Elevated (>10, consider toxic alcohols)` : `Osmolal gap ${r} → Normal`, reference: 'Standard', normal_range: '<10 mOsm/kg' }
  },
  winter(p) {
    const hco3 = parseFloat(p.hco3)
    const expected = 1.5 * hco3 + 8
    const low = Math.round((expected - 2) * 10) / 10
    const high = Math.round((expected + 2) * 10) / 10
    return { value: `${low}-${high}`, unit: 'mmHg', interpretation: `Expected pCO2: ${low}-${high} mmHg`, reference: "Winter's Formula", normal_range: '35-45 mmHg' }
  },
  urr(p) {
    const v = (1 - parseFloat(p.post_bun) / parseFloat(p.pre_bun)) * 100
    const r = Math.round(v * 10) / 10
    return { value: r, unit: '%', interpretation: r >= 65 ? `URR ${r}% → Adequate (≥65%)` : `URR ${r}% → Inadequate (<65%)`, reference: 'KDOQI', normal_range: '≥65%' }
  },
  ttkg(p) {
    const v = (parseFloat(p.urine_k) / parseFloat(p.plasma_k)) / (parseFloat(p.urine_osm) / parseFloat(p.plasma_osm))
    const r = Math.round(v * 10) / 10
    return { value: r, unit: '', interpretation: `TTKG ${r}`, reference: 'Standard', normal_range: '6-12' }
  },
  urine_ag(p) {
    const v = parseFloat(p.urine_na) + parseFloat(p.urine_k) - parseFloat(p.urine_cl)
    const r = Math.round(v * 10) / 10
    return { value: r, unit: 'mEq/L', interpretation: r < 0 ? `UAG ${r} → Negative (GI loss likely)` : `UAG ${r} → Positive (RTA likely)`, reference: 'Standard', normal_range: 'Negative = appropriate NH4+ excretion' }
  },
  kt_v(p) {
    const pre = parseFloat(p.pre_bun), post = parseFloat(p.post_bun)
    const t = parseFloat(p.t_hours), uf = parseFloat(p.uf_liters), w = parseFloat(p.post_weight_kg)
    const r_val = post / pre
    const ktv = -Math.log(r_val - 0.008 * t) + (4 - 3.5 * r_val) * (uf / w)
    const r = Math.round(ktv * 100) / 100
    return { value: r, unit: '', interpretation: r >= 1.2 ? `Kt/V ${r} → Adequate (≥1.2)` : `Kt/V ${r} → Inadequate (<1.2)`, reference: 'Daugirdas 2nd gen', normal_range: '≥1.2' }
  },
  mest_c(p) {
    const parts = ['M' + p.m, 'E' + p.e, 'S' + p.s, 'T' + p.t, 'C' + p.c]
    return { value: parts.join(' '), unit: '', interpretation: `Oxford Classification: ${parts.join('')}`, reference: 'IgAN Oxford 2016/2017', normal_range: 'M0E0S0T0C0' }
  },
}

async function compute() {
  computing.value = true
  calcError.value = null
  calcResult.value = null

  // Try local calculation first (instant, no API dependency)
  const localFn = LOCAL_CALCS[selectedCalc.value]
  if (localFn) {
    try {
      calcResult.value = localFn(paramValues.value)
      computing.value = false
      return
    } catch (e) {
      // Fall through to API
    }
  }

  // Fallback to API
  try {
    const res = await fetch(`${API_BASE}/calculators/compute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        calculator: selectedCalc.value,
        params: paramValues.value,
      }),
    })

    if (!res.ok) {
      const text = await res.text()
      let errMsg
      try { errMsg = JSON.parse(text).error } catch { errMsg = `API 回應 ${res.status}` }
      throw new Error(errMsg)
    }

    const data = await res.json()
    calcResult.value = data.result
  } catch (e) {
    calcError.value = e.message
  } finally {
    computing.value = false
  }
}

// Expose for AssistPage history integration
function setInput() { resetResult() }
function getInput() { return { calculator: selectedCalc.value, params: paramValues.value } }
function getTitle() { return calcMeta.value?.name || '計算器' }

defineExpose({ setInput, getInput, getTitle })
</script>
