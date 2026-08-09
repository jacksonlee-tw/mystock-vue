import AppLayout from '@/layout/AppLayout.vue';
import { createRouter, createWebHistory } from 'vue-router';

const router = createRouter({
    history: createWebHistory(),
    routes: [
        {
            path: '/',
            component: AppLayout,
            children: [
                {
                    path: '/',
                    name: 'heatmap-dashboard',
                    component: () => import('@/views/HeatmapDashboard.vue')
                },
                {
                    path: '/stock/:id',
                    name: 'stock-dashboard',
                    component: () => import('@/views/StockDashboard.vue')
                },
                {
                    path: '/stock/:id/chart/:chartType',
                    name: 'chart-detail',
                    component: () => import('@/views/ChartDetailView.vue')
                },
                {
                    path: '/stocks',
                    name: 'stock-management',
                    component: () => import('@/views/StockManagement.vue')
                }
            ]
        }
    ]
});

export default router;
