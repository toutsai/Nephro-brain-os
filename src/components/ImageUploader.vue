<template>
  <div
    ref="containerEl"
    @paste="handlePaste"
    @dragover.prevent="dragActive = true"
    @dragleave="dragActive = false"
    @drop.prevent="handleDrop"
    tabindex="-1"
    class="outline-none"
    :class="{ 'ring-2 ring-emerald-300 ring-offset-1 rounded-lg': dragActive }"
  >
    <div class="flex items-center gap-2 mb-2 flex-wrap">
      <label class="inline-flex items-center gap-1.5 px-3 py-1.5 border border-slate-200 rounded-lg text-xs text-slate-600 hover:bg-slate-50 cursor-pointer transition-colors">
        📷 上傳圖片
        <input type="file" accept="image/*" multiple class="hidden" @change="handleFiles" />
      </label>
      <span class="text-[10px] text-slate-400">支援 JPG、PNG｜可 Ctrl+V 貼上或拖曳圖片</span>
      <span v-if="pasteFlash" class="text-[10px] text-emerald-500 font-medium animate-pulse">已貼上 ✓</span>
      <button v-if="previews.length" class="text-[10px] text-slate-400 hover:text-red-500" @click="clear">清除全部</button>
    </div>
    <div v-if="previews.length" class="flex flex-wrap gap-2">
      <div v-for="(p, i) in previews" :key="i" class="relative group">
        <img :src="p.url" class="w-20 h-20 object-cover rounded-lg border border-slate-200" />
        <button
          class="absolute -top-1.5 -right-1.5 w-5 h-5 bg-red-500 text-white rounded-full text-[10px] flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
          @click="remove(i)"
        >×</button>
        <div class="text-[10px] text-slate-400 truncate w-20 mt-0.5">{{ p.name }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  toBase64: { type: Function, required: true },
})

const emit = defineEmits(['update:modelValue'])

const previews = ref([])
const pasteFlash = ref(false)
const dragActive = ref(false)
const containerEl = ref(null)
let pasteFlashTimer = null

async function processFile(file) {
  if (!file.type.startsWith('image/')) return
  const b64 = await props.toBase64(file)
  props.modelValue.push(b64)
  const reader = new FileReader()
  reader.onload = () => previews.value.push({ url: reader.result, name: file.name || '剪貼簿圖片' })
  reader.readAsDataURL(file)
}

async function handleFiles(e) {
  const files = Array.from(e.target.files || [])
  for (const file of files) {
    await processFile(file)
  }
  emit('update:modelValue', [...props.modelValue])
  e.target.value = ''
}

async function handlePaste(e) {
  const items = Array.from(e.clipboardData?.items || [])
  let found = false
  for (const item of items) {
    if (!item.type.startsWith('image/')) continue
    const file = item.getAsFile()
    if (file) {
      await processFile(file)
      found = true
    }
  }
  if (found) {
    emit('update:modelValue', [...props.modelValue])
    pasteFlash.value = true
    clearTimeout(pasteFlashTimer)
    pasteFlashTimer = setTimeout(() => { pasteFlash.value = false }, 2000)
  }
}

async function handleDrop(e) {
  dragActive.value = false
  const files = Array.from(e.dataTransfer?.files || [])
  for (const file of files) {
    await processFile(file)
  }
  if (files.length) emit('update:modelValue', [...props.modelValue])
}

// Also listen for paste on the document level when component is present
function globalPaste(e) {
  // Check if clipboard contains image data
  const hasImage = Array.from(e.clipboardData?.items || []).some(i => i.type.startsWith('image/'))
  if (!hasImage) return
  // If an input/textarea is focused but clipboard is an image (not text), still handle it
  handlePaste(e)
}

onMounted(() => {
  document.addEventListener('paste', globalPaste)
})

onUnmounted(() => {
  document.removeEventListener('paste', globalPaste)
  clearTimeout(pasteFlashTimer)
})

function remove(idx) {
  props.modelValue.splice(idx, 1)
  previews.value.splice(idx, 1)
  emit('update:modelValue', [...props.modelValue])
}

function clear() {
  props.modelValue.splice(0)
  previews.value.splice(0)
  emit('update:modelValue', [])
}
</script>
