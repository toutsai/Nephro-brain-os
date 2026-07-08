<template>
  <div class="bg-white rounded-xl border border-slate-200 p-4">
    <!-- Meta row -->
    <div class="flex items-center gap-2 mb-2 flex-wrap">
      <button
        v-if="conceptTitle"
        type="button"
        class="text-[10px] font-medium px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 hover:bg-blue-200 transition-colors"
        @click="$emit('view-concept', flag.concept_id)"
      >
        {{ conceptTitle }}
      </button>
      <span v-if="flag.ai_model" class="text-[10px] text-slate-400">{{ flag.ai_model }}</span>
      <span class="text-[10px] text-slate-400 ml-auto">{{ formatDate(flag.created_at) }}</span>
    </div>

    <!-- Chapter + article -->
    <h4 class="text-sm font-semibold text-slate-800 mb-0.5">
      {{ chapterTitle || flag.guideline_chapter_id }}
    </h4>
    <p v-if="articleTitle" class="text-[11px] text-slate-400 mb-2">
      New evidence: {{ articleTitle }}
    </p>

    <!-- Current recommendation -->
    <div v-if="flag.current_recommendation" class="mb-2 bg-slate-50 rounded-lg p-2.5">
      <h5 class="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1">
        Current Recommendation
      </h5>
      <p class="text-xs text-slate-600 whitespace-pre-wrap leading-relaxed">
        {{ flag.current_recommendation }}
      </p>
    </div>

    <!-- Suggested update reason -->
    <div class="mb-3">
      <h5 class="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1">
        Suggested Update Reason
      </h5>
      <p class="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">
        {{ flag.suggested_update_reason }}
      </p>
    </div>

    <!-- Error -->
    <p v-if="errorMsg" class="text-xs text-red-500 mb-2">{{ errorMsg }}</p>

    <!-- Review note -->
    <textarea
      v-model="note"
      rows="2"
      placeholder="Review note (optional)"
      class="w-full text-xs border border-slate-200 rounded-lg px-2 py-1.5 mb-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
    />

    <!-- Actions -->
    <div class="flex gap-2">
      <button
        type="button"
        :disabled="submitting"
        class="flex-1 text-xs font-semibold px-3 py-1.5 rounded-lg bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
        @click="review('approve')"
      >
        Approve
      </button>
      <button
        type="button"
        :disabled="submitting"
        class="flex-1 text-xs font-semibold px-3 py-1.5 rounded-lg bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
        @click="review('reject')"
      >
        Reject
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { doc, getDoc } from 'firebase/firestore'
import { db } from '../../firebase.js'
import { useAuth } from '../../composables/useAuth.js'

const props = defineProps({
  flag: { type: Object, required: true },
})

const emit = defineEmits(['view-concept'])

const { authFetch, API_BASE } = useAuth()

const submitting = ref(false)
const errorMsg = ref('')
const note = ref('')
const conceptTitle = ref('')
const chapterTitle = ref('')
const articleTitle = ref('')

function formatDate(ts) {
  if (!ts) return ''
  const d = ts.toDate ? ts.toDate() : new Date(ts)
  return d.toLocaleDateString('zh-TW', { month: 'short', day: 'numeric' })
}

async function review(action) {
  submitting.value = true
  errorMsg.value = ''
  try {
    const res = await authFetch(`${API_BASE}/kg/guideline-flags/${props.flag.id}/review`, {
      method: 'POST',
      body: JSON.stringify({ action, note: note.value }),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      errorMsg.value = data.error || `Request failed (${res.status})`
    }
    // On success the doc's status flips away from "pending" and the
    // usePendingGuidelineFlags() onSnapshot listener removes it automatically.
  } catch (err) {
    errorMsg.value = err?.message || 'Network error'
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  const conceptId = props.flag?.concept_id
  if (conceptId) {
    try {
      const snap = await getDoc(doc(db, 'kg_concepts', conceptId))
      conceptTitle.value = snap.exists()
        ? (snap.data().title_zh || snap.data().title || conceptId)
        : conceptId
    } catch {
      conceptTitle.value = conceptId
    }
  }

  const chapterId = props.flag?.guideline_chapter_id
  if (chapterId) {
    try {
      const snap = await getDoc(doc(db, 'guideline_chapters', chapterId))
      chapterTitle.value = snap.exists()
        ? (snap.data().chapter_title_zh || snap.data().chapter_title || chapterId)
        : chapterId
    } catch {
      chapterTitle.value = chapterId
    }
  }

  const articleId = props.flag?.article_id
  if (articleId) {
    try {
      const snap = await getDoc(doc(db, 'articles_v2', articleId))
      articleTitle.value = snap.exists() ? (snap.data().title || articleId) : articleId
    } catch {
      articleTitle.value = articleId
    }
  }
})
</script>
