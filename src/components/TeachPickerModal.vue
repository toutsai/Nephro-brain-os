<template>
  <Teleport to="body">
    <div v-if="visible" class="fixed inset-0 z-[60] flex items-end sm:items-center justify-center">
      <!-- Backdrop -->
      <div class="absolute inset-0 bg-black/40" @click="$emit('close')" />

      <!-- Modal -->
      <div class="relative bg-white rounded-t-2xl sm:rounded-2xl w-full sm:max-w-sm max-h-[70vh] flex flex-col shadow-xl animate-slide-up">
        <!-- Header -->
        <div class="px-4 py-3 border-b border-slate-100 flex items-center justify-between shrink-0">
          <h3 class="text-sm font-bold text-slate-800">🎓 加到 Teach</h3>
          <button class="text-slate-400 hover:text-slate-600 text-lg" @click="$emit('close')">×</button>
        </div>

        <!-- New session option -->
        <div class="px-3 pt-3 pb-1 shrink-0">
          <button
            class="w-full flex items-center gap-2 px-3 py-2.5 bg-orange-50 hover:bg-orange-100 border border-orange-200 rounded-xl text-sm font-medium text-orange-700 transition-colors"
            @click="$emit('createNew')"
          >
            <span class="text-base">+</span> 新建 Teach 素材
          </button>
        </div>

        <!-- Divider -->
        <div class="px-4 py-2 shrink-0">
          <div class="flex items-center gap-2 text-[10px] text-slate-400">
            <div class="flex-1 border-t border-slate-100" />
            <span>或加入現有素材</span>
            <div class="flex-1 border-t border-slate-100" />
          </div>
        </div>

        <!-- Session list -->
        <div class="flex-1 overflow-y-auto px-3 pb-3">
          <div v-if="loading" class="text-center py-8 text-slate-400 text-xs">載入中...</div>
          <div v-else-if="!sessions.length" class="text-center py-8 text-slate-400 text-xs">
            還沒有 Teach 素材
          </div>
          <div
            v-for="s in sessions"
            :key="s.id"
            class="flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-slate-50 cursor-pointer transition-colors mb-1"
            @click="$emit('selectSession', s.id)"
          >
            <div class="min-w-0 flex-1">
              <div class="text-sm font-medium text-slate-700 truncate">{{ s.title || '未命名' }}</div>
              <div class="flex items-center gap-2 mt-0.5 text-[10px] text-slate-400">
                <span v-if="s.file_url" class="text-orange-400">📄 PDF</span>
                <span v-if="s.summary" class="text-emerald-500">✓ 摘要</span>
                <span v-if="s.flashcards" class="text-blue-500">✓ 卡片</span>
                <span v-if="s.relation" class="text-purple-500">✓ 關聯</span>
                <span v-if="s.ppt" class="text-orange-500">✓ PPT</span>
                <span v-if="!s.summary && !s.flashcards && !s.relation && !s.ppt" class="text-slate-300">尚未生成</span>
              </div>
            </div>
            <span class="text-xs text-slate-300 shrink-0">+</span>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
defineProps({
  visible: { type: Boolean, default: false },
  sessions: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
})

defineEmits(['close', 'createNew', 'selectSession'])
</script>

<style scoped>
.animate-slide-up {
  animation: slideUp 0.2s ease-out;
}
@keyframes slideUp {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
