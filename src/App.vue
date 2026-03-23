<template>
  <NavBar v-if="showNav" />
  <router-view />
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import NavBar from './components/NavBar.vue'
import { useAuth } from './composables/useAuth.js'

// 觸發 auth listener 初始化（全域只需一次）
useAuth()

const route = useRoute()
const showNav = computed(() => route.path !== '/')
</script>
