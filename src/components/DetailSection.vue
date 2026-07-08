<template>
  <div class="rounded-lg border-l-4 pl-4" :class="borderClass">
    <h3 class="text-xs font-semibold uppercase tracking-wide mb-2" :class="textClass">
      {{ title }}
    </h3>
    <slot />
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  title: { type: String, required: true },
  color: { type: String, default: 'slate' },
})

// Tailwind 會 purge 動態組出的 class，必須用完整字面值對照表
const COLOR_CLASSES = {
  emerald: { border: 'border-emerald-400', text: 'text-emerald-600' },
  blue: { border: 'border-blue-400', text: 'text-blue-600' },
  amber: { border: 'border-amber-400', text: 'text-amber-600' },
  red: { border: 'border-red-400', text: 'text-red-600' },
  purple: { border: 'border-purple-400', text: 'text-purple-600' },
  slate: { border: 'border-slate-400', text: 'text-slate-600' },
}

const borderClass = computed(() => (COLOR_CLASSES[props.color] || COLOR_CLASSES.slate).border)
const textClass = computed(() => (COLOR_CLASSES[props.color] || COLOR_CLASSES.slate).text)
</script>
