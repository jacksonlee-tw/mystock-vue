import AppLayout from '@/layout/AppLayout.vue';
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: AppLayout,
    children: [
      {
        path: '',
        name: 'weighbridge',
        component: () => import('@/views/weighbridge.vue')
      },
      {
        path: 'gold',
        name: 'gold-price',
        component: () => import('@/views/GoldPrice.vue')
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
