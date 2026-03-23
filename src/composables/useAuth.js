import { ref, computed } from 'vue'
import { auth, db } from '../firebase.js'
import {
  signInWithEmailAndPassword,
  signOut,
  onAuthStateChanged,
} from 'firebase/auth'
import { doc, getDoc } from 'firebase/firestore'

// 全域共用的 auth state
const user = ref(null)          // Firebase User object
const userProfile = ref(null)   // Firestore user profile { role, displayName, ... }
const authReady = ref(false)    // auth 初始化完成
const authLoading = ref(false)

// API base URL
const API_BASE = 'https://nephro-brain-api-761804517300.asia-east1.run.app'

// 監聽 auth 狀態（全域只需一次）
let _listenerInitialized = false
function initAuthListener() {
  if (_listenerInitialized) return
  _listenerInitialized = true

  onAuthStateChanged(auth, async (firebaseUser) => {
    user.value = firebaseUser
    if (firebaseUser) {
      // 讀取 Firestore user profile
      try {
        const snap = await getDoc(doc(db, 'users', firebaseUser.uid))
        userProfile.value = snap.exists() ? snap.data() : { role: 'user' }
      } catch {
        userProfile.value = { role: 'user' }
      }
    } else {
      userProfile.value = null
    }
    authReady.value = true
  })
}

export function useAuth() {
  initAuthListener()

  const isLoggedIn = computed(() => !!user.value)
  const isAdmin = computed(() => userProfile.value?.role === 'admin')
  const uid = computed(() => user.value?.uid || null)
  const displayName = computed(() =>
    userProfile.value?.displayName || user.value?.email?.split('@')[0] || ''
  )

  async function login(email, password) {
    authLoading.value = true
    try {
      await signInWithEmailAndPassword(auth, email, password)
      return { success: true }
    } catch (err) {
      const messages = {
        'auth/user-not-found': '帳號不存在',
        'auth/wrong-password': '密碼錯誤',
        'auth/invalid-credential': '帳號或密碼錯誤',
        'auth/too-many-requests': '嘗試過多，請稍後再試',
        'auth/invalid-email': '無效的 Email 格式',
      }
      return { success: false, error: messages[err.code] || err.message }
    } finally {
      authLoading.value = false
    }
  }

  async function logout() {
    await signOut(auth)
    userProfile.value = null
  }

  // 取得 ID token（供 API 呼叫用）
  async function getIdToken() {
    if (!user.value) return null
    return user.value.getIdToken()
  }

  // 帶 auth header 的 fetch wrapper
  async function authFetch(url, options = {}) {
    const token = await getIdToken()
    const headers = {
      ...options.headers,
      'Content-Type': 'application/json',
    }
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    return fetch(url, { ...options, headers })
  }

  return {
    user,
    userProfile,
    authReady,
    authLoading,
    isLoggedIn,
    isAdmin,
    uid,
    displayName,
    login,
    logout,
    getIdToken,
    authFetch,
    API_BASE,
  }
}
