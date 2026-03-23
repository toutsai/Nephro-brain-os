import { createRouter, createWebHistory } from 'vue-router'
import { auth } from './firebase.js'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('./views/LoginPage.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    name: 'landing',
    component: () => import('./views/LandingPage.vue'),
  },
  {
    path: '/insight',
    name: 'insight',
    component: () => import('./views/InsightPage.vue'),
  },
  {
    path: '/consult',
    name: 'consult',
    component: () => import('./views/ConsultPage.vue'),
  },
  {
    path: '/notes',
    name: 'notes',
    component: () => import('./views/NotesPage.vue'),
  },
  {
    path: '/teach',
    name: 'teach',
    component: () => import('./views/TeachPage.vue'),
  },
  {
    path: '/assist',
    name: 'assist',
    component: () => import('./views/AssistPage.vue'),
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('./views/SettingsPage.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 等 Firebase Auth 初始化完成的 promise
let _authReady = null
function waitForAuth() {
  if (_authReady) return _authReady
  _authReady = new Promise((resolve) => {
    const unsub = auth.onAuthStateChanged(() => {
      unsub()
      resolve()
    })
  })
  return _authReady
}

// Navigation guard — 未登入一律導向 /login
router.beforeEach(async (to) => {
  await waitForAuth()
  if (!to.meta.public && !auth.currentUser) {
    return { name: 'login' }
  }
  if (to.name === 'login' && auth.currentUser) {
    return { name: 'landing' }
  }
})

export default router
