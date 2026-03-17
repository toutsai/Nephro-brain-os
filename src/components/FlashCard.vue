<template>
  <div class="perspective-800">
    <div
      class="relative w-full min-h-[160px] cursor-pointer transition-transform duration-500 preserve-3d"
      :class="flipped ? 'rotate-y-180' : ''"
      @click="flipped = !flipped"
    >
      <!-- Front (Question) -->
      <div class="absolute inset-0 backface-hidden rounded-xl border-2 border-blue-200 bg-gradient-to-br from-blue-50 to-white p-5 flex flex-col">
        <div class="flex items-center justify-between mb-2">
          <span class="text-[10px] font-bold text-blue-400 uppercase tracking-wider">Question</span>
          <span class="text-[10px] text-slate-400">#{{ index + 1 }} / {{ total }}</span>
        </div>
        <div class="flex-1 flex items-center justify-center">
          <p class="text-sm font-medium text-slate-800 text-center leading-relaxed">{{ card.question }}</p>
        </div>
        <p class="text-[10px] text-slate-300 text-center mt-2">點擊翻面看答案</p>
      </div>

      <!-- Back (Answer) -->
      <div class="absolute inset-0 backface-hidden rotate-y-180 rounded-xl border-2 border-emerald-200 bg-gradient-to-br from-emerald-50 to-white p-5 flex flex-col">
        <div class="flex items-center justify-between mb-2">
          <span class="text-[10px] font-bold text-emerald-500 uppercase tracking-wider">Answer</span>
          <span class="text-[10px] text-slate-400">#{{ index + 1 }} / {{ total }}</span>
        </div>
        <div class="flex-1 flex items-center">
          <p class="text-sm text-slate-700 leading-relaxed">{{ card.answer }}</p>
        </div>
        <p class="text-[10px] text-slate-300 text-center mt-2">點擊翻回問題</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  card: { type: Object, required: true },
  index: { type: Number, default: 0 },
  total: { type: Number, default: 1 },
})

const flipped = ref(false)

// 換卡片時重設
watch(() => props.card, () => { flipped.value = false })
</script>

<style scoped>
.perspective-800 { perspective: 800px; }
.preserve-3d { transform-style: preserve-3d; }
.backface-hidden { backface-visibility: hidden; }
.rotate-y-180 { transform: rotateY(180deg); }
</style>
