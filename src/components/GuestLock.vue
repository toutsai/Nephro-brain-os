<template>
  <div v-if="!isLoggedIn" class="mt-4 px-4 py-5 bg-slate-50 border border-slate-200 rounded-xl text-center">
    <div class="text-2xl mb-2">🔒</div>
    <p class="text-sm font-medium text-slate-700 mb-1">此功能需要登入</p>
    <p class="text-xs text-slate-400 mb-3">請在上方導覽列輸入帳號密碼登入</p>
  </div>
</template>

<script setup>
import { useAuth } from '../composables/useAuth.js'
const { isLoggedIn } = useAuth()
</script>
