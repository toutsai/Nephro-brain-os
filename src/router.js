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
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
