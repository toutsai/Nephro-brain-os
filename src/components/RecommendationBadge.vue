<script setup>
const props = defineProps({
  grade: {
    type: String,
    required: true
  }
})

const colorMap = {
  '1A': 'bg-green-100 text-green-700',
  '1B': 'bg-blue-100 text-blue-700',
  '1C': 'bg-cyan-100 text-cyan-700',
  '2A': 'bg-amber-100 text-amber-700',
  '2B': 'bg-gray-100 text-gray-600',
  '2C': 'bg-slate-100 text-slate-500',
  '2D': 'bg-slate-50 text-slate-400',
  'Not Graded': 'bg-white border border-slate-200 text-slate-400'
}

function badgeClasses(grade) {
  return colorMap[grade] || 'bg-gray-100 text-gray-500'
}
</script>

<template>
  <span
    :class="[
      'inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold',
      badgeClasses(grade)
    ]"
  >
    {{ grade }}
  </span>
</template>
