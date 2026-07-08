<template>
  <div class="bg-white rounded-xl border border-slate-200 p-4">
    <!-- Meta row -->
    <div class="flex items-center gap-2 mb-2 flex-wrap">
      <button
        v-if="conceptTitle"
        type="button"
        class="text-[10px] font-medium px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 hover:bg-blue-200 transition-colors"
        @click="$emit('view-concept', insight.concept_id)"
      >
        {{ conceptTitle }}
      </button>
      <span v-if="insight.ai_model" class="text-[10px] text-slate-400">{{ insight.ai_model }}</span>
      <span class="text-[10px] text-slate-400 ml-auto">{{ formatDate(insight.created_at) }}</span>
    </div>

    <!-- Insight body -->
    <div class="prose-review text-sm text-slate-700 mb-3" v-html="renderedInsight" />

    <!-- Source articles -->
    <div v-if="articleRefs.length" class="mb-3">
      <h5 class="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1">
        Source Articles
      </h5>
      <ul class="space-y-0.5">
        <li
          v-for="a in articleRefs"
          :key="a.id"
          class="text-[11px] text-slate-500 line-clamp-1"
        >
          {{ a.title }}
        </li>
      </ul>
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
import { renderMd } from '../../utils/renderMarkdown.js'

const props = defineProps({
  insight: { type: Object, required: true },
})

const emit = defineEmits(['view-concept'])

const { authFetch, API_BASE } = useAuth()

const submitting = ref(false)
const errorMsg = ref('')
const note = ref('')
const conceptTitle = ref('')
const articleRefs = ref([])

const renderedInsight = computed(() => renderMd(props.insight?.insight || ''))

function formatDate(ts) {
  if (!ts) return ''
  const d = ts.toDate ? ts.toDate() : new Date(ts)
  return d.toLocaleDateString('zh-TW', { month: 'short', day: 'numeric' })
}

async function review(action) {
  submitting.value = true
  errorMsg.value = ''
  try {
    const res = await authFetch(`${API_BASE}/kg/insights/${props.insight.id}/review`, {
      method: 'POST',
      body: JSON.stringify({ action, note: note.value }),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      errorMsg.value = data.error || `Request failed (${res.status})`
    }
    // On success the doc's status flips away from "pending" and the
    // usePendingInsights() onSnapshot listener removes it automatically.
  } catch (err) {
    errorMsg.value = err?.message || 'Network error'
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  // Resolve concept title for the "link to concept" chip
  const conceptId = props.insight?.concept_id
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

  // Resolve source article titles
  const ids = props.insight?.source_article_ids || []
  articleRefs.value = await Promise.all(
    ids.map(async (id) => {
      try {
        const snap = await getDoc(doc(db, 'articles_v2', id))
        return { id, title: snap.exists() ? (snap.data().title || id) : id }
      } catch {
        return { id, title: id }
      }
    })
  )
})
</script>

<style scoped>
/* Compact markdown typography for AI-generated insight text */
.prose-review {
  line-height: 1.7;
  overflow-wrap: break-word;
}
.prose-review :deep(h1),
.prose-review :deep(h2),
.prose-review :deep(h3),
.prose-review :deep(h4) {
  @apply text-sm font-semibold text-slate-800 mt-2 mb-1;
}
.prose-review :deep(:first-child) {
  margin-top: 0;
}
.prose-review :deep(p) {
  @apply mb-2 last:mb-0;
}
.prose-review :deep(ul),
.prose-review :deep(ol) {
  @apply pl-5 my-1.5 space-y-1;
}
.prose-review :deep(li) {
  @apply list-disc pl-1;
}
.prose-review :deep(li.ol) {
  @apply list-decimal;
}
.prose-review :deep(strong) {
  @apply font-bold text-slate-900;
}
.prose-review :deep(em) {
  @apply italic text-slate-600;
}
.prose-review :deep(a) {
  @apply text-blue-600 underline underline-offset-2 decoration-blue-300 hover:text-blue-800;
}
.prose-review :deep(.inline-code) {
  @apply bg-slate-100 text-red-600 text-xs px-1.5 py-0.5 rounded font-mono;
}
</style>
