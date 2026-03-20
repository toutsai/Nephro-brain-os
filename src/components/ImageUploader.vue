<template>
  <div>
    <div class="flex items-center gap-2 mb-2 flex-wrap">
      <label class="inline-flex items-center gap-1.5 px-3 py-1.5 border border-slate-200 rounded-lg text-xs text-slate-600 hover:bg-slate-50 cursor-pointer transition-colors">
        📷 上傳圖片
        <input type="file" accept="image/*" multiple class="hidden" @change="handleFiles" />
      </label>
      <span class="text-[10px] text-slate-400">支援 JPG、PNG（Lab 報告、病歷截圖、處方單）</span>
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
import { ref } from 'vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  toBase64: { type: Function, required: true },
})

const emit = defineEmits(['update:modelValue'])

const previews = ref([])

async function handleFiles(e) {
  const files = Array.from(e.target.files || [])
  for (const file of files) {
    if (!file.type.startsWith('image/')) continue
    const b64 = await props.toBase64(file)
    props.modelValue.push(b64)

    const reader = new FileReader()
    reader.onload = () => previews.value.push({ url: reader.result, name: file.name })
    reader.readAsDataURL(file)
  }
  emit('update:modelValue', [...props.modelValue])
  e.target.value = ''
}

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
