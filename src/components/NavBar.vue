<template>
  <nav class="bg-slate-900 text-white sticky top-0 z-30 shrink-0">
    <div class="max-w-7xl mx-auto px-4 flex items-center justify-between h-11">
      <!-- Logo -->
      <router-link to="/" class="flex items-center gap-2 shrink-0">
        <span class="text-sm font-bold tracking-tight">NB — OS</span>
      </router-link>

      <!-- Desktop nav -->
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
      </div>

      <!-- Mobile hamburger -->
      <button
        class="sm:hidden text-slate-400 hover:text-white p-1"
        @click="mobileOpen = !mobileOpen"
      >
        <svg v-if="!mobileOpen" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/>
        </svg>
        <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>
    </div>

    <!-- Mobile dropdown -->
    <div
      v-if="mobileOpen"
      class="sm:hidden border-t border-slate-700 pb-2"
    >
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="flex items-center gap-2 px-4 py-2.5 text-sm transition-colors"
        :class="isActive(item.path)
          ? 'bg-white/10 text-white'
          : 'text-slate-400 hover:text-white hover:bg-white/5'"
        @click="mobileOpen = false"
      >
        <span>{{ item.icon }}</span>
        <span>{{ item.label }}</span>
      </router-link>
    </div>
  </nav>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const mobileOpen = ref(false)

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
</script>
