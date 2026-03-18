<template>
  <div v-if="!tree" class="text-center py-12 text-slate-400">
    <p class="text-sm">尚未生成心智圖</p>
    <slot name="empty" />
  </div>

  <div v-else class="mindmap-container overflow-x-auto pb-4">
    <!-- Root node -->
    <div class="flex flex-col items-center">
      <div
        class="px-5 py-2.5 bg-orange-500 text-white font-bold text-sm rounded-xl shadow-md cursor-pointer select-none"
        @click="$emit('nodeClick', tree)"
      >
        {{ tree.label }}
      </div>

      <!-- Children level 1 -->
      <div v-if="tree.children?.length" class="mt-4">
        <!-- Vertical connector from root -->
        <div class="flex justify-center mb-2">
          <div class="w-px h-4 bg-slate-300" />
        </div>

        <!-- Horizontal spread -->
        <div class="flex gap-6 items-start flex-wrap justify-center">
          <div
            v-for="(child, i) in tree.children"
            :key="i"
            class="flex flex-col items-center min-w-[160px] max-w-[240px]"
          >
            <!-- Connector -->
            <div class="w-px h-3 bg-slate-300" />

            <!-- Level 1 node -->
            <div
              class="px-4 py-2 rounded-lg text-xs font-bold cursor-pointer select-none border-2 transition-all"
              :class="expanded.has(i)
                ? 'bg-blue-50 border-blue-400 text-blue-800'
                : 'bg-white border-slate-200 text-slate-700 hover:border-blue-300'"
              @click="toggle(i)"
            >
              {{ child.label }}
              <span v-if="child.children?.length" class="ml-1 text-[10px] text-slate-400">
                {{ expanded.has(i) ? '−' : '+' }}{{ child.children.length }}
              </span>
            </div>

            <!-- Level 2 children (expandable) -->
            <div
              v-if="expanded.has(i) && child.children?.length"
              class="mt-2 space-y-1.5 w-full"
            >
              <div class="flex justify-center">
                <div class="w-px h-2 bg-slate-200" />
              </div>
              <div
                v-for="(sub, j) in child.children"
                :key="j"
                class="ml-2"
              >
                <div class="flex items-start gap-2">
                  <div class="w-2 h-px bg-slate-200 mt-2.5 shrink-0" />
                  <div>
                    <div
                      class="px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-[11px] text-slate-600 cursor-pointer hover:bg-purple-50 hover:border-purple-200 transition-colors"
                      @click="toggleSub(`${i}-${j}`)"
                    >
                      {{ sub.label }}
                      <span v-if="sub.children?.length" class="text-[10px] text-slate-400 ml-1">
                        {{ expandedSub.has(`${i}-${j}`) ? '−' : '+' }}
                      </span>
                    </div>

                    <!-- Level 3 (leaf details) -->
                    <div
                      v-if="expandedSub.has(`${i}-${j}`) && sub.children?.length"
                      class="mt-1 ml-3 space-y-0.5"
                    >
                      <div
                        v-for="(leaf, k) in sub.children"
                        :key="k"
                        class="flex items-start gap-1.5 text-[10px] text-slate-500"
                      >
                        <span class="text-slate-300 mt-0.5">•</span>
                        <span>{{ leaf.label }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  tree: { type: Object, default: null },
})

defineEmits(['nodeClick'])

const expanded = ref(new Set())
const expandedSub = ref(new Set())

// 預設展開前三個
watch(() => props.tree, (t) => {
  expanded.value = new Set()
  expandedSub.value = new Set()
  if (t?.children) {
    t.children.forEach((_, i) => {
      if (i < 3) expanded.value.add(i)
    })
  }
}, { immediate: true })

function toggle(i) {
  if (expanded.value.has(i)) {
    expanded.value.delete(i)
  } else {
    expanded.value.add(i)
  }
  expanded.value = new Set(expanded.value) // trigger reactivity
}

function toggleSub(key) {
  if (expandedSub.value.has(key)) {
    expandedSub.value.delete(key)
  } else {
    expandedSub.value.add(key)
  }
  expandedSub.value = new Set(expandedSub.value)
}
</script>
