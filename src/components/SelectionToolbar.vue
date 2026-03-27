<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="fixed z-50 flex items-center gap-1 bg-white border border-slate-200 rounded-xl shadow-lg px-2 py-1.5 animate-fade-in"
      :style="{ top: position.y + 'px', left: position.x + 'px' }"
    >
      <button
        class="flex items-center gap-1.5 text-xs font-medium text-purple-600 hover:bg-purple-50 px-2.5 py-1.5 rounded-lg transition-colors"
        @mousedown.prevent="saveToNotes"
      >
        📝 收進 Notes
      </button>
      <button
        v-if="showAppendOption && existingNotes.length"
        class="flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:bg-slate-50 px-2.5 py-1.5 rounded-lg transition-colors"
        @mousedown.prevent="showNoteList = !showNoteList"
      >
        📎 加到現有筆記
      </button>
      <button
        class="flex items-center gap-1.5 text-xs font-medium text-orange-600 hover:bg-orange-50 px-2.5 py-1.5 rounded-lg transition-colors"
        @mousedown.prevent="sendToTeach"
      >
        🎓 加到 Teach 產生
      </button>

      <!-- Note list dropdown -->
      <div
        v-if="showNoteList"
        class="absolute top-full left-0 mt-1 w-64 max-w-[calc(100vw-16px)] max-h-48 overflow-y-auto bg-white border border-slate-200 rounded-xl shadow-lg"
      >
        <div
          v-for="note in existingNotes"
          :key="note.id"
          class="px-3 py-2 text-xs text-slate-600 hover:bg-purple-50 cursor-pointer border-b border-slate-50 last:border-0"
          @mousedown.prevent="appendToNote(note.id)"
        >
          <div class="font-medium text-slate-700 truncate">{{ note.title }}</div>
          <div class="text-[10px] text-slate-400 mt-0.5 flex gap-2">
            <span v-for="tag in (note.tags || []).slice(0, 3)" :key="tag">#{{ tag }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Toast notification -->
    <div
      v-if="toast"
      class="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-purple-600 text-white text-sm px-4 py-2.5 rounded-xl shadow-lg animate-fade-in"
    >
      {{ toast }}
    </div>
  </Teleport>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { db } from '../firebase.js'
import {
  collection,
  doc,
  addDoc,
  updateDoc,
  query,
  where,
  orderBy,
  limit,
  getDocs,
  serverTimestamp,
} from 'firebase/firestore'
import { useAuth } from '../composables/useAuth.js'

const router = useRouter()
const { uid } = useAuth()

const props = defineProps({
  // 來源類型：'insight' | 'consult' | 'teach'
  sourceType: { type: String, required: true },
  // 來源附加資訊（論文標題、chat ID 等）
  sourceMeta: { type: Object, default: () => ({}) },
  // 監聽選取的容器 ref
  containerRef: { type: Object, default: null },
  // 是否顯示「加到現有筆記」
  showAppendOption: { type: Boolean, default: true },
})

const visible = ref(false)
const position = ref({ x: 0, y: 0 })
const selectedText = ref('')
const showNoteList = ref(false)
const existingNotes = ref([])
const toast = ref(null)

let toastTimer = null

function showToast(msg) {
  toast.value = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = null }, 2000)
}

// 監聽選取事件
function handleMouseUp(e) {
  // 如果點到工具列本身，不處理
  if (e.target.closest('[class*="animate-fade-in"]')) return

  setTimeout(() => {
    const selection = window.getSelection()
    const text = selection?.toString().trim()

    if (text && text.length > 5) {
      selectedText.value = text

      // 計算位置（在選取文字上方）
      const range = selection.getRangeAt(0)
      const rect = range.getBoundingClientRect()
      position.value = {
        x: Math.max(8, Math.min(rect.left + rect.width / 2 - 80, window.innerWidth - 260)),
        y: Math.max(8, rect.top + window.scrollY - 50),
      }
      visible.value = true
      showNoteList.value = false
    } else {
      visible.value = false
      showNoteList.value = false
    }
  }, 10)
}

function handleMouseDown(e) {
  if (!e.target.closest('[class*="animate-fade-in"]')) {
    visible.value = false
    showNoteList.value = false
  }
}

// 載入最近的筆記（for 「加到現有筆記」）
async function loadRecentNotes() {
  if (!uid.value) return
  try {
    const q = query(
      collection(db, 'notes'),
      where('userId', '==', uid.value),
      orderBy('updated_at', 'desc'),
      limit(10)
    )
    const snap = await getDocs(q)
    existingNotes.value = snap.docs.map((d) => ({ id: d.id, ...d.data() }))
  } catch (e) {
    console.error('Load notes error:', e)
  }
}

// === 核心功能：建立新筆記 ===
async function saveToNotes() {
  if (!selectedText.value) return

  const source = {
    type: props.sourceType,
    snippet: selectedText.value.slice(0, 200),
    ...props.sourceMeta,
    saved_at: new Date().toISOString(),
  }

  try {
    const title = generateTitle(selectedText.value)

    await addDoc(collection(db, 'notes'), {
      title,
      content: selectedText.value,
      tags: suggestTags(selectedText.value),
      links: [],
      sources: [source],
      userId: uid.value,
      created_at: serverTimestamp(),
      updated_at: serverTimestamp(),
    })

    showToast('已收進 Notes ✓')
    visible.value = false
    window.getSelection()?.removeAllRanges()
  } catch (e) {
    console.error('Save to notes error:', e)
    showToast('儲存失敗')
  }
}

// === 加到現有筆記 ===
async function appendToNote(noteId) {
  if (!selectedText.value) return

  const note = existingNotes.value.find((n) => n.id === noteId)
  if (!note) return

  const source = {
    type: props.sourceType,
    snippet: selectedText.value.slice(0, 200),
    ...props.sourceMeta,
    saved_at: new Date().toISOString(),
  }

  try {
    const separator = '\n\n---\n\n'
    const timestamp = new Date().toLocaleString('zh-TW')
    const sourceLabel = { insight: '論文摘錄', consult: '問答摘錄', teach: '教材摘錄', assist: '臨床輔助摘錄' }[props.sourceType] || '摘錄'
    const appendedContent = `${note.content || ''}${separator}> 📎 ${sourceLabel} (${timestamp})\n\n${selectedText.value}`

    await updateDoc(doc(db, 'notes', noteId), {
      content: appendedContent,
      sources: [...(note.sources || []), source],
      updated_at: serverTimestamp(),
    })

    showToast(`已加入「${note.title}」✓`)
    visible.value = false
    showNoteList.value = false
    window.getSelection()?.removeAllRanges()
  } catch (e) {
    console.error('Append to note error:', e)
    showToast('儲存失敗')
  }
}

// === 加到 Teach 產生 ===
function sendToTeach() {
  if (!selectedText.value) return
  visible.value = false
  window.getSelection()?.removeAllRanges()
  router.push({ path: '/teach', query: { text: selectedText.value } })
}

// === 輔助：從選取文字生成標題 ===
function generateTitle(text) {
  // 取第一行或前 30 字
  const firstLine = text.split('\n')[0].replace(/[#*_`>]/g, '').trim()
  if (firstLine.length <= 30) return firstLine
  return firstLine.slice(0, 30) + '…'
}

// === 輔助：從文字建議標籤 ===
function suggestTags(text) {
  const tags = []
  const lower = text.toLowerCase()

  const keywords = {
    'AKI': ['aki', 'acute kidney', '急性腎'],
    'CKD': ['ckd', 'chronic kidney', '慢性腎'],
    'ESRD': ['esrd', 'end-stage', '末期腎', 'hemodialysis', '血液透析'],
    'CRRT': ['crrt', 'continuous renal replacement'],
    'Dialysis': ['dialysis', '透析', 'hemodialysis', 'peritoneal'],
    'Transplant': ['transplant', '移植', 'graft'],
    'Hypertension': ['hypertension', '高血壓', 'blood pressure'],
    'Diabetes': ['diabetes', '糖尿病', 'dkd', 'sglt2'],
    'Electrolyte': ['electrolyte', '電解質', 'potassium', 'sodium', 'calcium'],
    'Guideline': ['guideline', 'kdigo', '指引', 'recommendation'],
  }

  for (const [tag, kws] of Object.entries(keywords)) {
    if (kws.some((kw) => lower.includes(kw))) {
      tags.push(tag)
    }
  }

  return tags.slice(0, 4) // 最多 4 個自動標籤
}

onMounted(() => {
  document.addEventListener('mouseup', handleMouseUp)
  document.addEventListener('mousedown', handleMouseDown)
  loadRecentNotes()
})

onUnmounted(() => {
  document.removeEventListener('mouseup', handleMouseUp)
  document.removeEventListener('mousedown', handleMouseDown)
})
</script>

<style scoped>
.animate-fade-in {
  animation: fadeIn 0.15s ease-out;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
