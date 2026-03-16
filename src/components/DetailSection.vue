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

const borderClass = computed(() => `border-${props.color}-400`)
const textClass = computed(() => `text-${props.color}-600`)
</script>
