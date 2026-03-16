<template>
  <div class="min-h-screen bg-slate-950 text-white flex flex-col items-center justify-center px-4">
    <div class="text-center max-w-2xl">
      <div class="text-sm font-medium tracking-widest text-blue-400 mb-4">
        FROM LITERATURE TO INTELLIGENCE
      </div>
      <h1 class="text-4xl md:text-5xl font-bold mb-3">Nephro Brain OS</h1>
      <p class="text-lg text-slate-400 mb-2">腎臟科智慧中樞的作業系統</p>
      <p class="text-sm text-slate-500 mb-10">
        以 AI 強化的知識基礎設施，整合文獻、證據與臨床推理。
      </p>

      <div class="flex flex-col sm:flex-row gap-3 justify-center">
        <router-link
          to="/insight"
          class="px-6 py-3 bg-blue-600 hover:bg-blue-500 rounded-lg font-medium transition-colors"
        >
          🔍 NB Insight — 每日文獻
        </router-link>
        <router-link
          to="/consult"
          class="px-6 py-3 bg-slate-800 hover:bg-slate-700 text-white rounded-lg font-medium transition-colors"
        >
          💬 NB Consult — 知識問答
        </router-link>
      </div>
    </div>
  </div>
</template>
