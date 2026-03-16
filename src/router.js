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
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
