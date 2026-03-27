<template>
  <!-- Desktop top nav -->
  <nav class="bg-slate-900 text-white sticky top-0 z-30 shrink-0">
    <div class="max-w-7xl mx-auto px-4 flex items-center h-11">
      <!-- Logo -->
      <router-link to="/" class="flex items-center gap-2 shrink-0">
        <span class="text-sm font-bold tracking-tight">Nephro Brain OS</span>
        <span class="hidden md:inline text-[10px] text-slate-400 font-normal">腎臟科智慧中樞</span>
      </router-link>

      <!-- Desktop nav links（靠左接在 logo 後） -->
      <div class="hidden sm:flex items-center gap-1 ml-4">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors"
          :class="isActive(item.path)
            ? 'bg-white/15 text-white'
            : 'text-slate-400 hover:text-white hover:bg-white/5'"
        >
          <span>{{ item.icon }}</span>
          <span>{{ item.label }}</span>
        </router-link>
      </div>

      <div class="flex-1" />

      <!-- Mobile: login/user status -->
      <div class="sm:hidden flex items-center gap-1.5">
        <template v-if="isLoggedIn">
          <span class="text-[10px] text-emerald-400 bg-emerald-900/40 px-2 py-0.5 rounded-full">
            {{ displayName }}
          </span>
          <button class="text-[10px] text-slate-500 hover:text-slate-300" @click="handleLogout">登出</button>
        </template>
        <template v-else>
          <button
            class="text-[10px] text-white bg-blue-600 hover:bg-blue-500 px-2.5 py-1 rounded-full transition-colors"
            @click="showMobileLogin = !showMobileLogin"
          >
            {{ showMobileLogin ? '取消' : '登入' }}
          </button>
        </template>
      </div>

      <!-- Desktop user info（靠右） -->
      <div class="hidden sm:flex items-center gap-1.5">
          <!-- 已登入 -->
          <template v-if="isLoggedIn">
            <span class="text-[10px] text-emerald-400 bg-emerald-900/40 px-2 py-0.5 rounded-full">
              {{ displayName }}
            </span>
            <span v-if="isAdmin" class="text-[10px] text-amber-400 bg-amber-900/40 px-1.5 py-0.5 rounded-full">Admin</span>
            <button class="text-[10px] text-slate-500 hover:text-slate-300" @click="handleLogout">登出</button>
            <router-link
              to="/settings"
              class="text-[10px] text-amber-400 bg-amber-900/30 px-2 py-0.5 rounded-full hover:bg-amber-900/50 transition-colors"
              title="當月 API 費用"
            >
              NT${{ monthlyCostTWD }}
            </router-link>
          </template>

          <!-- 未登入：帳密輸入框 -->
          <template v-else>
            <form class="flex items-center gap-1" @submit.prevent="handleLogin">
              <input
                v-model="email"
                type="email"
                placeholder="Email"
                class="w-28 px-2 py-0.5 text-[10px] bg-slate-800 border border-slate-700 rounded text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <input
                v-model="password"
                type="password"
                placeholder="密碼"
                class="w-20 px-2 py-0.5 text-[10px] bg-slate-800 border border-slate-700 rounded text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <button
                type="submit"
                :disabled="authLoading || !email || !password"
                class="px-2 py-0.5 text-[10px] bg-blue-600 hover:bg-blue-500 rounded text-white disabled:opacity-40 transition-colors"
              >
                {{ authLoading ? '...' : '登入' }}
              </button>
            </form>
            <span v-if="loginError" class="text-[10px] text-red-400">{{ loginError }}</span>
            <span v-else class="text-[10px] text-slate-500 bg-slate-800 px-2 py-0.5 rounded-full">訪客</span>
          </template>
        </span>
      </div>
    </div>
  </nav>

  <!-- Mobile login dropdown -->
  <div v-if="showMobileLogin && !isLoggedIn" class="sm:hidden bg-slate-800 border-b border-slate-700 px-4 py-3 sticky top-11 z-30">
    <form class="flex items-center gap-2" @submit.prevent="handleMobileLogin">
      <input
        v-model="email"
        type="email"
        placeholder="Email"
        class="flex-1 px-3 py-1.5 text-xs bg-slate-900 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      />
      <input
        v-model="password"
        type="password"
        placeholder="密碼"
        class="w-24 px-3 py-1.5 text-xs bg-slate-900 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      />
      <button
        type="submit"
        :disabled="authLoading || !email || !password"
        class="px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-500 rounded-lg text-white disabled:opacity-40 transition-colors shrink-0"
      >
        {{ authLoading ? '...' : '登入' }}
      </button>
    </form>
    <p v-if="loginError" class="text-[10px] text-red-400 mt-1.5">{{ loginError }}</p>
  </div>

  <!-- Mobile bottom tab bar -->
  <div class="sm:hidden fixed bottom-0 inset-x-0 bg-slate-900 border-t border-slate-700 z-30" style="padding-bottom: env(safe-area-inset-bottom, 0px)">
    <div class="flex justify-around">
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="flex flex-col items-center py-2 flex-1 min-w-0 transition-colors"
        :class="isActive(item.path) ? 'text-white' : 'text-slate-500'"
      >
        <span class="text-lg leading-none">{{ item.icon }}</span>
        <span class="text-[10px] mt-0.5 truncate">{{ item.label }}</span>
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { useAuth } from '../composables/useAuth.js'
import { useTokenUsage } from '../composables/useTokenUsage.js'

const route = useRoute()
const { displayName, isAdmin, isLoggedIn, login, logout, authLoading } = useAuth()
const { monthlyCostTWD } = useTokenUsage()

const email = ref('')
const password = ref('')
const loginError = ref('')
const showMobileLogin = ref(false)

const navItems = [
  { path: '/insight', icon: '🔍', label: 'Insight' },
  { path: '/consult', icon: '💬', label: 'Consult' },
  { path: '/notes',   icon: '📝', label: 'Notes' },
  { path: '/teach',   icon: '🎓', label: 'Teach' },
  { path: '/assist',  icon: '🏥', label: 'Assist' },
]

function isActive(path) {
  return route.path === path
}

async function handleLogin() {
  loginError.value = ''
  const result = await login(email.value, password.value)
  if (result.success) {
    email.value = ''
    password.value = ''
  } else {
    loginError.value = result.error
  }
}

async function handleMobileLogin() {
  loginError.value = ''
  const result = await login(email.value, password.value)
  if (result.success) {
    email.value = ''
    password.value = ''
    showMobileLogin.value = false
  } else {
    loginError.value = result.error
  }
}

async function handleLogout() {
  await logout()
}
</script>
