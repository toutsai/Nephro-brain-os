import { ref, computed } from 'vue'
import { db } from '../firebase.js'
import {
  collection,
  doc,
  addDoc,
  updateDoc,
  deleteDoc,
  onSnapshot,
  query,
  orderBy,
  serverTimestamp,
} from 'firebase/firestore'

export function useNotes() {
  const notes = ref([])
  const loading = ref(true)
  const searchQuery = ref('')
  const activeTag = ref(null) // null = 全部

  // 即時監聽 notes collection
  const q = query(
    collection(db, 'notes'),
    orderBy('updated_at', 'desc')
  )

  const unsubscribe = onSnapshot(
    q,
    (snap) => {
      notes.value = snap.docs.map((d) => ({ id: d.id, ...d.data() }))
      loading.value = false
    },
    (err) => {
      console.error('Notes snapshot error:', err)
      loading.value = false
    }
  )

  // === 所有標籤（自動統計）===
  const allTags = computed(() => {
    const tagMap = {}
    notes.value.forEach((n) => {
      ;(n.tags || []).forEach((t) => {
        tagMap[t] = (tagMap[t] || 0) + 1
      })
    })
    return Object.entries(tagMap)
      .map(([tag, count]) => ({ tag, count }))
      .sort((a, b) => b.count - a.count)
  })

  // === 篩選後的筆記 ===
  const filteredNotes = computed(() => {
    let result = notes.value

    // 標籤篩選
    if (activeTag.value) {
      result = result.filter((n) => n.tags?.includes(activeTag.value))
    }

    // 搜尋篩選
    if (searchQuery.value.trim()) {
      const q = searchQuery.value.toLowerCase()
      result = result.filter(
        (n) =>
          (n.title || '').toLowerCase().includes(q) ||
          (n.content || '').toLowerCase().includes(q) ||
          (n.tags || []).some((t) => t.toLowerCase().includes(q))
      )
    }

    return result
  })

  // === CRUD ===
  async function createNote(data = {}) {
    const docRef = await addDoc(collection(db, 'notes'), {
      title: data.title || '新筆記',
      content: data.content || '',
      tags: data.tags || [],
      links: data.links || [],
      sources: data.sources || [],
      created_at: serverTimestamp(),
      updated_at: serverTimestamp(),
    })
    return docRef.id
  }

  async function updateNote(noteId, updates) {
    await updateDoc(doc(db, 'notes', noteId), {
      ...updates,
      updated_at: serverTimestamp(),
    })
  }

  async function deleteNote(noteId) {
    // 移除其他筆記中對此筆記的連結
    const linkedNotes = notes.value.filter((n) => n.links?.includes(noteId))
    for (const n of linkedNotes) {
      await updateDoc(doc(db, 'notes', n.id), {
        links: (n.links || []).filter((id) => id !== noteId),
      })
    }
    await deleteDoc(doc(db, 'notes', noteId))
  }

  // === 雙向連結 ===
  async function addLink(fromId, toId) {
    if (fromId === toId) return

    const fromNote = notes.value.find((n) => n.id === fromId)
    const toNote = notes.value.find((n) => n.id === toId)
    if (!fromNote || !toNote) return

    // 雙向加
    const fromLinks = [...new Set([...(fromNote.links || []), toId])]
    const toLinks = [...new Set([...(toNote.links || []), fromId])]

    await updateDoc(doc(db, 'notes', fromId), { links: fromLinks })
    await updateDoc(doc(db, 'notes', toId), { links: toLinks })
  }

  async function removeLink(fromId, toId) {
    const fromNote = notes.value.find((n) => n.id === fromId)
    const toNote = notes.value.find((n) => n.id === toId)

    if (fromNote) {
      await updateDoc(doc(db, 'notes', fromId), {
        links: (fromNote.links || []).filter((id) => id !== toId),
      })
    }
    if (toNote) {
      await updateDoc(doc(db, 'notes', toId), {
        links: (toNote.links || []).filter((id) => id !== fromId),
      })
    }
  }

  // === 輔助 ===
  function getNoteById(id) {
    return notes.value.find((n) => n.id === id)
  }

  function getLinkedNotes(noteId) {
    const note = getNoteById(noteId)
    if (!note?.links?.length) return []
    return note.links.map((id) => getNoteById(id)).filter(Boolean)
  }

  return {
    notes,
    loading,
    searchQuery,
    activeTag,
    allTags,
    filteredNotes,
    createNote,
    updateNote,
    deleteNote,
    addLink,
    removeLink,
    getNoteById,
    getLinkedNotes,
    unsubscribe,
  }
}
