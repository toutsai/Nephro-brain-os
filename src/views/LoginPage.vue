<template>
  <div class="min-h-screen bg-slate-950 text-white flex flex-col items-center justify-center px-4">
    <div class="w-full max-w-sm">
      <div class="text-center mb-8">
        <div class="text-sm font-medium tracking-widest text-blue-400 mb-3">
          FROM LITERATURE TO INTELLIGENCE
        </div>
        <h1 class="text-3xl font-bold mb-1">Nephro Brain OS</h1>
        <p class="text-sm text-slate-500">請登入以繼續</p>
      </div>

      <form @submit.prevent="handleLogin" class="space-y-4">
        <div>
          <label class="block text-xs text-slate-400 mb-1">Email</label>
          <input
            v-model="email"
            type="email"
            autocomplete="email"
            required
            class="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder="you@example.com"
          />
        </div>

        <div>
          <label class="block text-xs text-slate-400 mb-1">密碼</label>
          <input
            v-model="password"
            type="password"
            autocomplete="current-password"
            required
            class="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder="••••••••"
          />
        </div>

        <button
          type="submit"
          :disabled="authLoading"
          class="w-full py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
        >
          {{ authLoading ? '登入中...' : '登入' }}
        </button>

        <p v-if="errorMsg" class="text-xs text-red-400 text-center">{{ errorMsg }}</p>
      </form>

      <p class="text-xs text-slate-600 text-center mt-6">
        帳號由管理員建立，如需帳號請聯繫管理員。
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth.js'

const router = useRouter()
const { login, authLoading } = useAuth()

const email = ref('')
const password = ref('')
const errorMsg = ref('')

async function handleLogin() {
  errorMsg.value = ''
  const result = await login(email.value, password.value)
  if (result.success) {
    router.replace('/')
  } else {
    errorMsg.value = result.error
  }
}
</script>
