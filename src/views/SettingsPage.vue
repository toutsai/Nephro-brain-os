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

      <!-- 月份 -->
      <div class="text-xs text-slate-400 text-center">
        統計月份：{{ monthKey }}
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useTokenUsage } from '../composables/useTokenUsage.js'

const { monthlyData, monthlyCostTWD, USD_TO_TWD, loading, monthKey } = useTokenUsage()

const featureLabels = {
  consult: 'Consult 問答',
  teach: 'Teach 教學',
  assist: 'Assist 臨床輔助',
  other: '其他（爬蟲/摘要）',
}

const featureColors = {
  consult: 'bg-blue-500',
  teach: 'bg-emerald-500',
  assist: 'bg-purple-500',
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
