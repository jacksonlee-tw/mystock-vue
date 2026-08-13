import AppLayout from '@/layout/AppLayout.vue';
import { createRouter, createWebHistory } from 'vue-router';
import { useMarket } from '@/composables/useMarket';

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
                    redirect: to => {
                        return { path: `/stock/tw/${to.params.id}` };
                    }
                },
                {
                    path: '/stock/:market/:id',
                    name: 'stock-dashboard',
                    component: () => import('@/views/StockDashboard.vue')
                },
                {
                    path: '/stock/:id/chart/:chartType',
                    redirect: to => {
                        return { path: `/stock/tw/${to.params.id}/chart/${to.params.chartType}` };
                    }
                },
                {
                    path: '/stock/:market/:id/chart/:chartType',
                    name: 'chart-detail',
                    component: () => import('@/views/ChartDetailView.vue')
                },
                {
                    path: '/stocks',
                    name: 'stock-management',
                    component: () => import('@/views/StockManagement.vue')
                },
                {
                    path: '/alerts',
                    name: 'alert-dashboard',
                    component: () => import('@/views/AlertDashboard.vue')
                }
            ]
        }
    ]
});

router.beforeEach((to, from, next) => {
    if (to.params.market) {
        const { setMarket } = useMarket();
        setMarket(to.params.market);
    }
    next();
});

export default router;
