<template>
  <!-- Desktop top nav -->
  <nav class="bg-slate-900 text-white sticky top-0 z-30 shrink-0">
    <div class="max-w-7xl mx-auto px-4 flex items-center justify-between h-11">
      <!-- Logo -->
      <router-link to="/" class="flex items-center gap-2 shrink-0">
        <span class="text-sm font-bold tracking-tight">NB — OS</span>
      </router-link>

      <!-- Desktop nav links -->
      <div class="hidden sm:flex items-center gap-1">
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

        <span class="ml-2 border-l border-slate-700 pl-2 flex items-center gap-1.5">
          <span class="flex items-center gap-1">
            <span class="text-[10px] text-emerald-400 bg-emerald-900/40 px-2 py-0.5 rounded-full">
              {{ displayName }}
            </span>
            <span v-if="isAdmin" class="text-[10px] text-amber-400 bg-amber-900/40 px-1.5 py-0.5 rounded-full">Admin</span>
            <button class="text-[10px] text-slate-500 hover:text-slate-300" @click="handleLogout">登出</button>
          </span>
          <router-link
            to="/settings"
            class="text-[10px] text-amber-400 bg-amber-900/30 px-2 py-0.5 rounded-full hover:bg-amber-900/50 transition-colors"
            title="當月 API 費用"
          >
            NT${{ monthlyCostTWD }}
          </router-link>
        </span>
      </div>
    </div>
  </nav>

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
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth.js'
import { useTokenUsage } from '../composables/useTokenUsage.js'

const route = useRoute()
const router = useRouter()
const { displayName, isAdmin, logout } = useAuth()
const { monthlyCostTWD } = useTokenUsage()

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

async function handleLogout() {
  await logout()
  router.push('/login')
}
</script>
