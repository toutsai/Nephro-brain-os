import { createRouter, createWebHistory } from 'vue-router'

const routes = [
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
    path: '/knowledge',
    name: 'knowledge',
    component: () => import('./views/KnowledgePage.vue'),
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('./views/SettingsPage.vue'),
  },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
