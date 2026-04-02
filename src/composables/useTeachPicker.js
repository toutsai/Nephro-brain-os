import { ref } from 'vue'
import { collection, doc, addDoc, updateDoc, query, where, orderBy, limit, getDocs, serverTimestamp } from 'firebase/firestore'
import { db } from '../firebase.js'

export function useTeachPicker(uid, { sourceLabel = '摘錄' } = {}) {
  const showTeachPicker = ref(false)
  const teachPickerText = ref('')
  const teachSessions = ref([])
  const teachSessionsLoading = ref(false)
  const teachToast = ref(null)
  let teachToastTimer = null

  function showTeachToast(msg, sessionId = null) {
    teachToast.value = { msg, sessionId }
    clearTimeout(teachToastTimer)
    teachToastTimer = setTimeout(() => { teachToast.value = null }, sessionId ? 4000 : 2000)
  }

  async function loadTeachSessions() {
    if (!uid.value) return
    try {
      teachSessionsLoading.value = true
      const q = query(
        collection(db, 'teach_sessions'),
        where('userId', '==', uid.value),
        orderBy('created_at', 'desc'),
        limit(10)
      )
      const snap = await getDocs(q)
      teachSessions.value = snap.docs.map((d) => ({ id: d.id, ...d.data() }))
    } catch (e) {
      console.error('Load teach sessions error:', e)
    } finally {
      teachSessionsLoading.value = false
    }
  }

  function sendToTeach(content) {
    teachPickerText.value = content
    loadTeachSessions()
    showTeachPicker.value = true
  }

  async function handleTeachNew() {
    showTeachPicker.value = false
    const text = teachPickerText.value

    try {
      const firstLine = text.split('\n')[0].replace(/[#*_`>]/g, '').trim()
      const title = firstLine.length <= 30 ? firstLine : firstLine.slice(0, 30) + '…'
      const docRef = await addDoc(collection(db, 'teach_sessions'), {
        title,
        source_text: text,
        file_url: null,
        file_name: null,
        summary: null,
        flashcards: null,
        relation: null,
        mindmap: null,
        ppt: null,
        userId: uid.value,
        created_at: serverTimestamp(),
        updated_at: serverTimestamp(),
      })
      showTeachToast(`已建立「${title}」✓`, docRef.id)
    } catch (e) {
      console.error('Create teach session error:', e)
      showTeachToast('建立失敗')
    }
  }

  async function handleTeachAppend(sessionId) {
    const session = teachSessions.value.find((s) => s.id === sessionId)
    if (!session) return
    showTeachPicker.value = false

    try {
      const separator = '\n\n---\n\n'
      const timestamp = new Date().toLocaleString('zh-TW')
      const appendedText = `${session.source_text || ''}${separator}> 📎 ${sourceLabel} (${timestamp})\n\n${teachPickerText.value}`

      await updateDoc(doc(db, 'teach_sessions', sessionId), {
        source_text: appendedText,
        updated_at: serverTimestamp(),
      })

      showTeachToast(`已加入「${session.title}」✓`, sessionId)
    } catch (e) {
      console.error('Append to teach error:', e)
      showTeachToast('加入失敗')
    }
  }

  return {
    showTeachPicker,
    teachSessions,
    teachSessionsLoading,
    teachToast,
    sendToTeach,
    handleTeachNew,
    handleTeachAppend,
    showTeachToast,
  }
}
