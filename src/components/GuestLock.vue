<template>
  <div v-if="isGuest()" class="mt-4 px-4 py-5 bg-slate-50 border border-slate-200 rounded-xl text-center">
    <div class="text-2xl mb-2">🔒</div>
    <p class="text-sm font-medium text-slate-700 mb-1">此功能僅限授權用戶使用</p>
    <p class="text-xs text-slate-400 mb-3">請輸入授權碼以解鎖 AI 功能</p>
    <div class="flex items-center justify-center gap-2">
      <input
        v-model="code"
        type="password"
        class="w-40 text-sm border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-rose-400 text-center"
        placeholder="授權碼"
        @keyup.enter="tryActivate"
      />
      <button
        class="px-3 py-1.5 bg-rose-600 hover:bg-rose-500 text-white text-sm rounded-lg transition-colors"
        @click="tryActivate"
      >
        解鎖
      </button>
    </div>
    <p v-if="error" class="text-xs text-red-500 mt-2">授權碼不正確</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useUserRole } from '../composables/useUserRole.js'

const { isGuest, activatePro } = useUserRole()
const code = ref('')
const error = ref(false)

function tryActivate() {
  error.value = false
  if (activatePro(code.value)) {
    code.value = ''
  } else {
    error.value = true
  }
}
</script>
