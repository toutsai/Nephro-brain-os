<template>
  <template v-if="authReady">
    <NavBar v-if="showNav" />
    <router-view />
  </template>
  <div v-else class="min-h-screen bg-slate-950 flex items-center justify-center">
    <div class="text-slate-500 text-sm">載入中...</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import NavBar from './components/NavBar.vue'
import { useAuth } from './composables/useAuth.js'

const route = useRoute()
const { authReady } = useAuth()
const showNav = computed(() => route.path !== '/' && route.path !== '/login')
</script>
