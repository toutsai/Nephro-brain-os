<template>
  <div class="max-w-3xl mx-auto px-4 py-6 space-y-6">
    <h1 class="text-lg font-bold text-slate-800">API 用量統計</h1>

    <!-- Loading -->
    <div v-if="loading" class="text-sm text-slate-400">載入中...</div>

    <!-- No data -->
    <div v-else-if="!monthlyData" class="text-sm text-slate-400">
      {{ monthKey }} 尚無使用紀錄
    </div>

    <template v-else>
      <!-- 總覽卡片 -->
      <div class="grid grid-cols-3 gap-3">
        <div class="bg-white rounded-xl border p-4 text-center">
          <div class="text-2xl font-bold text-amber-500">NT${{ monthlyCostTWD }}</div>
          <div class="text-xs text-slate-500 mt-1">當月預估費用</div>
        </div>
        <div class="bg-white rounded-xl border p-4 text-center">
          <div class="text-2xl font-bold text-blue-500">{{ formatTokens(monthlyData.total_input_tokens) }}</div>
          <div class="text-xs text-slate-500 mt-1">Input Tokens</div>
        </div>
        <div class="bg-white rounded-xl border p-4 text-center">
          <div class="text-2xl font-bold text-purple-500">{{ formatTokens(monthlyData.total_output_tokens) }}</div>
          <div class="text-xs text-slate-500 mt-1">Output Tokens</div>
        </div>
      </div>

      <!-- 功能別消耗 -->
      <div class="bg-white rounded-xl border p-4">
        <h2 class="text-sm font-semibold text-slate-700 mb-3">功能別消耗</h2>
        <div class="space-y-3">
          <div v-for="(data, key) in featureData" :key="key">
            <div class="flex items-center justify-between text-sm mb-1">
              <span class="text-slate-600">{{ featureLabels[key] || key }}</span>
              <span class="font-medium">NT${{ formatCostTWD(data.cost) }}
                <span class="text-slate-400 font-normal ml-1">{{ data.calls || 0 }} 次</span>
              </span>
            </div>
            <div class="h-2 bg-slate-100 rounded-full overflow-hidden">
              <div
                class="h-full rounded-full transition-all"
                :class="featureColors[key] || 'bg-slate-400'"
                :style="{ width: featurePct(data.cost) + '%' }"
              />
            </div>
          </div>
          <div v-if="!Object.keys(featureData).length" class="text-xs text-slate-400">尚無資料</div>
        </div>
      </div>

      <!-- 模型別消耗 -->
      <div class="bg-white rounded-xl border p-4">
        <h2 class="text-sm font-semibold text-slate-700 mb-3">模型別消耗</h2>
        <div class="space-y-2">
          <div v-for="(data, model) in modelData" :key="model" class="flex items-center justify-between text-sm">
            <span class="text-slate-600 font-mono text-xs">{{ model.replaceAll('_', '.') }}</span>
            <span>
              <span class="font-medium">NT${{ formatCostTWD(data.cost) }}</span>
              <span class="text-slate-400 ml-2">{{ formatTokens(data.input) }} in / {{ formatTokens(data.output) }} out</span>
            </span>
          </div>
          <div v-if="!Object.keys(modelData).length" class="text-xs text-slate-400">尚無資料</div>
        </div>
      </div>

      <!-- 各功能定價參考 -->
      <details class="bg-white rounded-xl border">
        <summary class="px-4 py-3 text-sm font-semibold text-slate-700 cursor-pointer select-none hover:bg-slate-50 rounded-xl">
          各功能定價參考 ▾
        </summary>
        <div class="px-4 pb-4 space-y-4">
          <!-- 定價基準 -->
          <div>
            <h3 class="text-xs font-semibold text-slate-500 mb-1">定價基準</h3>
            <table class="w-full text-xs">
              <thead>
                <tr class="text-left text-slate-400 border-b">
                  <th class="py-1">模型</th><th class="py-1">Input</th><th class="py-1">Output</th>
                </tr>
              </thead>
              <tbody class="text-slate-600">
                <tr class="border-b border-slate-50"><td class="py-1 font-mono">gemini-2.5-flash</td><td>$0.15/M</td><td>$0.60/M</td></tr>
                <tr><td class="py-1 font-mono">gemini-2.5-pro</td><td>$1.25/M</td><td>$10.00/M</td></tr>
              </tbody>
            </table>
          </div>

          <!-- 各模組呼叫明細 -->
          <div v-for="group in pricingGroups" :key="group.label">
            <h3 class="text-xs font-semibold text-slate-500 mb-1">{{ group.label }}</h3>
            <table class="w-full text-xs">
              <thead>
                <tr class="text-left text-slate-400 border-b">
                  <th class="py-1">功能</th><th class="py-1">模型</th><th class="py-1 text-right">預估/次</th>
                </tr>
              </thead>
              <tbody class="text-slate-600">
                <tr v-for="item in group.items" :key="item.name" class="border-b border-slate-50">
                  <td class="py-1">{{ item.name }}</td>
                  <td class="py-1">
                    <span :class="item.model.includes('Pro') ? 'text-amber-600 font-medium' : 'text-slate-500'">{{ item.model }}</span>
                  </td>
                  <td class="py-1 text-right whitespace-nowrap">{{ item.cost }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <p class="text-[10px] text-slate-400">* 根據問題複雜度自動路由 Flash 或 Pro。費用以 USD→TWD 32.5 估算。</p>
        </div>
      </details>

      <!-- 月份 -->
      <div class="text-xs text-slate-400 text-center">
        統計月份：{{ monthKey }}
      </div>
    </template>

    <!-- ============ Admin Panel ============ -->
    <template v-if="isAdmin">
      <div class="border-t border-slate-200 pt-6">
        <h2 class="text-lg font-bold text-slate-800 mb-4">管理員面板</h2>

        <!-- 新增使用者 -->
        <div class="bg-white rounded-xl border p-4 mb-4">
          <h3 class="text-sm font-semibold text-slate-700 mb-3">新增使用者</h3>
          <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
            <input
              v-model="newUser.email"
              type="email"
              placeholder="Email"
              class="border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <input
              v-model="newUser.password"
              type="text"
              placeholder="密碼（至少 6 碼）"
              class="border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <input
              v-model="newUser.displayName"
              type="text"
              placeholder="顯示名稱"
              class="border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div class="flex items-center gap-2 mt-2">
            <select v-model="newUser.role" class="border border-slate-200 rounded-lg px-3 py-2 text-sm">
              <option value="user">一般使用者</option>
              <option value="admin">管理員</option>
            </select>
            <button
              :disabled="!newUser.email || !newUser.password || adminLoading"
              class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg disabled:opacity-40 transition-colors"
              @click="createUser"
            >
              {{ adminLoading ? '建立中...' : '建立帳號' }}
            </button>
          </div>
          <p v-if="adminMsg" class="text-xs mt-2" :class="adminError ? 'text-red-500' : 'text-emerald-600'">
            {{ adminMsg }}
          </p>
        </div>

        <!-- 使用者列表 -->
        <div class="bg-white rounded-xl border p-4 mb-4">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-semibold text-slate-700">使用者列表</h3>
            <button
              class="text-xs text-blue-500 hover:text-blue-700"
              @click="fetchUsers"
            >
              重新整理
            </button>
          </div>
          <div v-if="users.length === 0" class="text-sm text-slate-400">尚無使用者資料</div>
          <div v-else class="space-y-2">
            <div
              v-for="u in users"
              :key="u.uid"
              class="flex items-center justify-between py-2 px-3 bg-slate-50 rounded-lg"
            >
              <div>
                <span class="text-sm font-medium text-slate-700">{{ u.displayName }}</span>
                <span class="text-xs text-slate-400 ml-2">{{ u.email }}</span>
                <span
                  v-if="u.role === 'admin'"
                  class="ml-2 text-[10px] text-amber-600 bg-amber-100 px-1.5 py-0.5 rounded-full"
                >Admin</span>
              </div>
              <button
                v-if="u.uid !== uid"
                class="text-xs text-red-400 hover:text-red-600"
                @click="deleteUser(u.uid, u.email)"
              >
                刪除
              </button>
            </div>
          </div>
        </div>

        <!-- 資料遷移 -->
        <div class="bg-white rounded-xl border p-4">
          <h3 class="text-sm font-semibold text-slate-700 mb-2">舊資料遷移</h3>
          <p class="text-xs text-slate-400 mb-2">將所有沒有 userId 的舊資料歸給你的帳號</p>
          <button
            :disabled="adminLoading"
            class="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white text-sm rounded-lg disabled:opacity-40 transition-colors"
            @click="migrateData"
          >
            {{ adminLoading ? '遷移中...' : '執行遷移' }}
          </button>
          <p v-if="migrateMsg" class="text-xs text-emerald-600 mt-2">{{ migrateMsg }}</p>
        </div>

        <!-- OpenEvidence Cookie 管理 -->
        <div class="bg-white rounded-xl border p-4">
          <h3 class="text-sm font-semibold text-slate-700 mb-3">OpenEvidence Cookie 管理</h3>

          <!-- Status indicator -->
          <div class="flex items-center gap-2 mb-3">
            <span
              class="w-2.5 h-2.5 rounded-full shrink-0"
              :class="oeStatus?.valid === true ? 'bg-emerald-500' : oeStatus?.valid === false ? 'bg-red-400' : 'bg-slate-300'"
            />
            <span class="text-xs" :class="oeStatus?.valid === true ? 'text-emerald-600' : oeStatus?.valid === false ? 'text-red-500' : 'text-slate-400'">
              {{ oeStatus?.valid === true ? 'Cookie 有效' : oeStatus?.valid === false ? 'Cookie 已過期' : (oeStatus?.has_cookies ? '未驗證' : '未設定') }}
            </span>
            <span v-if="oeStatus?.user_email" class="text-[10px] text-slate-400">
              ({{ oeStatus.user_email }})
            </span>
            <button
              class="text-xs text-blue-500 hover:text-blue-700 ml-auto"
              :disabled="oeValidating"
              @click="validateOeCookies"
            >
              {{ oeValidating ? '驗證中...' : '重新驗證' }}
            </button>
          </div>

          <!-- Cookie input -->
          <div class="mb-3">
            <label class="text-xs text-slate-500 mb-1 block">貼上 Cookie（支援 JSON array 或 name=value; 格式）</label>
            <textarea
              v-model="oeCookieInput"
              rows="4"
              class="w-full border border-slate-200 rounded-lg p-2.5 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-indigo-400 resize-none"
              placeholder='[{"name":"...", "value":"..."}, ...] 或 name1=value1; name2=value2'
            />
          </div>

          <div class="flex items-center gap-2">
            <button
              :disabled="!oeCookieInput.trim() || oeSaving"
              class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium rounded-lg disabled:opacity-40 transition-colors"
              @click="saveOeCookies"
            >
              {{ oeSaving ? '儲存中...' : '儲存 & 驗證' }}
            </button>
            <span v-if="oeMsg" class="text-xs" :class="oeMsg.includes('失敗') || oeMsg.includes('error') ? 'text-red-500' : 'text-emerald-600'">
              {{ oeMsg }}
            </span>
          </div>

          <p class="text-[10px] text-slate-400 mt-3 leading-relaxed">
            從瀏覽器登入 OpenEvidence 後，使用 Cookie 匯出工具（如 Cookie-Editor 擴充套件）匯出 JSON，貼上後儲存即可。Cookie 過期後需重新匯出。
          </p>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useTokenUsage } from '../composables/useTokenUsage.js'
import { useAuth } from '../composables/useAuth.js'

const { monthlyData, monthlyCostTWD, USD_TO_TWD, loading, monthKey } = useTokenUsage()
const { isAdmin, uid, authFetch, API_BASE } = useAuth()

// === Admin state ===
const users = ref([])
const adminLoading = ref(false)
const adminMsg = ref('')
const adminError = ref(false)
const migrateMsg = ref('')
const newUser = ref({ email: '', password: '', displayName: '', role: 'user' })

async function fetchUsers() {
  try {
    const res = await authFetch(`${API_BASE}/admin/users`)
    if (res.ok) {
      const data = await res.json()
      users.value = data.users || []
    }
  } catch { /* silent */ }
}

async function createUser() {
  adminLoading.value = true
  adminMsg.value = ''
  adminError.value = false
  try {
    const res = await authFetch(`${API_BASE}/admin/users`, {
      method: 'POST',
      body: JSON.stringify(newUser.value),
    })
    const data = await res.json()
    if (res.ok) {
      adminMsg.value = data.message
      newUser.value = { email: '', password: '', displayName: '', role: 'user' }
      fetchUsers()
    } else {
      adminMsg.value = data.error
      adminError.value = true
    }
  } catch (e) {
    adminMsg.value = e.message
    adminError.value = true
  } finally {
    adminLoading.value = false
  }
}

async function deleteUser(userId, email) {
  if (!confirm(`確定要刪除 ${email} 嗎？`)) return
  adminLoading.value = true
  try {
    const res = await authFetch(`${API_BASE}/admin/users/${userId}`, { method: 'DELETE' })
    if (res.ok) fetchUsers()
  } catch { /* silent */ }
  finally { adminLoading.value = false }
}

async function migrateData() {
  adminLoading.value = true
  migrateMsg.value = ''
  try {
    const res = await authFetch(`${API_BASE}/admin/migrate-data`, {
      method: 'POST',
      body: JSON.stringify({ targetUid: uid.value }),
    })
    const data = await res.json()
    if (res.ok) {
      migrateMsg.value = `遷移完成：${JSON.stringify(data.migrated)}`
    }
  } catch { /* silent */ }
  finally { adminLoading.value = false }
}

// === OpenEvidence Cookie 管理 ===
const oeStatus = ref(null)
const oeCookieInput = ref('')
const oeSaving = ref(false)
const oeValidating = ref(false)
const oeMsg = ref('')

async function checkOeStatus() {
  try {
    const res = await authFetch(`${API_BASE}/admin/oe-status`)
    if (res.ok) oeStatus.value = await res.json()
  } catch { /* silent */ }
}

async function saveOeCookies() {
  oeSaving.value = true
  oeMsg.value = ''
  try {
    const raw = oeCookieInput.value.trim()
    let body = {}

    // Detect format: JSON array or raw string
    if (raw.startsWith('[') || raw.startsWith('{')) {
      body = { cookies_json: raw }
    } else {
      body = { cookies_raw: raw }
    }

    const res = await authFetch(`${API_BASE}/admin/oe-cookies`, {
      method: 'POST',
      body: JSON.stringify(body),
    })
    const data = await res.json()
    if (res.ok) {
      oeMsg.value = data.valid ? 'Cookie 儲存成功，驗證通過' : 'Cookie 已儲存，但驗證失敗'
      oeCookieInput.value = ''
      checkOeStatus()
    } else {
      oeMsg.value = data.error || '儲存失敗'
    }
  } catch (e) {
    oeMsg.value = `錯誤：${e.message}`
  } finally {
    oeSaving.value = false
  }
}

async function validateOeCookies() {
  oeValidating.value = true
  try {
    const res = await authFetch(`${API_BASE}/admin/oe-validate`, { method: 'POST' })
    const data = await res.json()
    oeMsg.value = data.valid ? '驗證通過' : '驗證失敗，Cookie 可能已過期'
    checkOeStatus()
  } catch (e) {
    oeMsg.value = `驗證錯誤：${e.message}`
  } finally {
    oeValidating.value = false
  }
}

onMounted(() => {
  if (isAdmin.value) {
    fetchUsers()
    checkOeStatus()
  }
})

const pricingGroups = [
  {
    label: 'Consult 問答 — 3 個呼叫點',
    items: [
      { name: '一般問答', model: 'Flash / Pro*', cost: 'NT$0.5~5' },
      { name: '懶人包', model: 'Flash', cost: '~NT$0.5' },
      { name: '串流問答', model: 'Flash / Pro*', cost: 'NT$0.5~5' },
    ],
  },
  {
    label: 'Teach 教學 — 5 個呼叫點',
    items: [
      { name: '摘要', model: 'Flash', cost: '~NT$0.5' },
      { name: '閃卡', model: 'Flash', cost: '~NT$0.5' },
      { name: '概念圖', model: 'Flash', cost: '~NT$0.5' },
      { name: '心智圖', model: 'Flash', cost: '~NT$0.5' },
      { name: '簡報', model: 'Flash', cost: '~NT$0.5' },
    ],
  },
  {
    label: 'Assist 臨床輔助 — 8 個呼叫點',
    items: [
      { name: '臨床分析', model: 'Pro', cost: 'NT$5~15' },
      { name: '劑量調整', model: 'Flash', cost: '~NT$0.5' },
      { name: '檢驗判讀', model: 'Pro', cost: 'NT$3~10' },
      { name: '健保規定', model: 'Flash', cost: '~NT$0.5' },
      { name: '藥物交互作用', model: 'Flash', cost: '~NT$0.5' },
      { name: '移植諮詢', model: 'Pro', cost: 'NT$5~15' },
      { name: '腹膜透析', model: 'Flash', cost: '~NT$0.5' },
      { name: '臨床路徑', model: 'Flash', cost: '~NT$0.5' },
    ],
  },
  {
    label: 'Other — 2 個呼叫點',
    items: [
      { name: '文獻摘要', model: 'Flash', cost: '~NT$0.5' },
      { name: '期刊處理', model: 'Flash', cost: '~NT$0.5' },
    ],
  },
]

const featureLabels = {
  consult: 'Consult 問答',
  deep_research: 'Deep Research',
  teach: 'Teach 教學',
  assist: 'Assist 臨床輔助',
  openevidence: 'OpenEvidence',
  other: '其他（爬蟲/摘要）',
}

const featureColors = {
  consult: 'bg-blue-500',
  deep_research: 'bg-indigo-500',
  teach: 'bg-emerald-500',
  assist: 'bg-purple-500',
  openevidence: 'bg-rose-500',
  other: 'bg-slate-400',
}

const featureData = computed(() => monthlyData.value?.by_feature || {})
const modelData = computed(() => monthlyData.value?.by_model || {})

const maxFeatureCost = computed(() => {
  const costs = Object.values(featureData.value).map(d => d.cost || 0)
  return Math.max(...costs, 0.001)
})

function featurePct(cost) {
  return Math.min(((cost || 0) / maxFeatureCost.value) * 100, 100)
}

function formatCostTWD(usdValue) {
  const twd = (usdValue || 0) * USD_TO_TWD
  if (twd > 0 && twd < 1) return twd.toFixed(2)
  return Math.round(twd).toString()
}

function formatTokens(n) {
  if (!n) return '0'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}
</script>
