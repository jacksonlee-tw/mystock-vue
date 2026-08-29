import AppLayout from '@/layout/AppLayout.vue';
import { createRouter, createWebHistory } from 'vue-router';
import { useMarket } from '@/composables/useMarket';
import { notifyApi } from '@/service/notifyApi';

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
                    // 大盤指數詳細頁（大盤指數功能規劃書 §10.1）：與個股路由平行但獨立，
                    // 共用 StockCharts.vue（kind='index'）與 ChartDetailView.vue（見下方 meta.kind）
                    path: '/index/:market/:code',
                    name: 'index-detail',
                    component: () => import('@/views/IndexDetailView.vue')
                },
                {
                    path: '/index/:market/:code/chart/:chartType',
                    name: 'index-chart-detail',
                    component: () => import('@/views/ChartDetailView.vue'),
                    meta: { kind: 'index' }
                },
                {
                    path: '/indices/sectors',
                    name: 'sector-rotation',
                    component: () => import('@/views/SectorRotationView.vue')
                },
                {
                    path: '/stocks',
                    name: 'stock-management',
                    component: () => import('@/views/StockManagement.vue')
                },
                {
                    path: '/stocks/symbols',
                    name: 'stock-symbol-browser',
                    component: () => import('@/views/StockSymbolBrowser.vue')
                },
                {
                    path: '/market',
                    name: 'market-screener',
                    component: () => import('@/views/MarketScreener.vue')
                },
                {
                    path: '/alerts',
                    name: 'alert-dashboard',
                    component: () => import('@/views/AlertDashboard.vue')
                },
                {
                    path: '/picking',
                    name: 'stock-picking',
                    component: () => import('@/views/StockPicking.vue')
                },
                {
                    path: '/compare',
                    name: 'stock-compare',
                    component: () => import('@/views/StockCompare.vue')
                },
                // AI 技術分析報告（docs/16.AI技術分析/AI技術分析規劃.md §7.4）
                {
                    path: '/ai/reports',
                    name: 'ai-report-history',
                    component: () => import('@/views/ai/AiReportHistory.vue')
                },
                {
                    path: '/notify/channels',
                    name: 'notify-channels',
                    component: () => import('@/views/notify/ChannelSettings.vue')
                },
                {
                    path: '/notify/recipients',
                    name: 'notify-recipients',
                    component: () => import('@/views/notify/RecipientManagement.vue')
                },
                {
                    path: '/notify/subscriptions',
                    name: 'notify-subscriptions',
                    component: () => import('@/views/notify/SubscriptionRules.vue')
                },
                {
                    path: '/notify/templates',
                    name: 'notify-templates',
                    component: () => import('@/views/notify/MessageTemplates.vue')
                },
                {
                    path: '/notify/logs',
                    name: 'notify-logs',
                    component: () => import('@/views/notify/DeliveryLogs.vue')
                },
                // ── 個人投資記帳與績效追蹤模組（docs/8.個人投資記帳功能/）─────────
                {
                    path: '/portfolio',
                    name: 'portfolio-dashboard',
                    component: () => import('@/views/portfolio/PortfolioDashboard.vue')
                },
                {
                    path: '/portfolio/transactions',
                    name: 'portfolio-transactions',
                    component: () => import('@/views/portfolio/TransactionList.vue')
                },
                {
                    path: '/portfolio/holdings',
                    name: 'portfolio-holdings',
                    component: () => import('@/views/portfolio/HoldingsView.vue')
                },
                {
                    path: '/portfolio/realized',
                    name: 'portfolio-realized',
                    component: () => import('@/views/portfolio/RealizedPnlView.vue')
                },
                {
                    path: '/portfolio/cashflow',
                    name: 'portfolio-cashflow',
                    component: () => import('@/views/portfolio/CashflowView.vue')
                },
                {
                    path: '/portfolio/watchlist',
                    name: 'portfolio-watchlist',
                    component: () => import('@/views/portfolio/WatchlistView.vue')
                },
                {
                    path: '/portfolio/notes',
                    name: 'portfolio-notes',
                    component: () => import('@/views/portfolio/InvestmentNotesView.vue')
                },
                {
                    path: '/portfolio/settings',
                    name: 'portfolio-settings',
                    component: () => import('@/views/portfolio/PortfolioSettingsView.vue')
                }
            ]
        },
        {
            // 管理端登入：不掛在 AppLayout 之下，避免未登入時先閃過整個殼層（見系統開發規格書 §9.1）
            path: '/notify/login',
            name: 'notify-login',
            component: () => import('@/views/notify/OwnerLogin.vue')
        },
        {
            path: '/ai/reports/:reportId',
            name: 'ai-report-detail',
            component: () => import('@/views/ai/AiReportDetail.vue')
        },
        {
            // 收件人自助頁：獨立路由樹，與管理介面入口完全分離（規格 §12.1「入口完全分離」）
            path: '/n/me',
            name: 'notify-self-service',
            component: () => import('@/views/notify/SelfService.vue')
        }
    ]
});

router.beforeEach(async (to, from, next) => {
    if (to.params.market) {
        const { setMarket } = useMarket();
        setMarket(to.params.market);
    }
    // 管理端頁面的登入檢查只是體驗上的導向；真正的授權一律由後端 require_owner 強制
    // （NFR-22，不得只靠前端隱藏），所以這裡失敗只導去登入頁，不做任何權限判斷邏輯。
    if (to.path.startsWith('/notify/') && to.name !== 'notify-login') {
        const authenticated = await notifyApi.session.whoami();
        if (!authenticated) {
            next({ name: 'notify-login', query: { redirect: to.fullPath } });
            return;
        }
    }
    next();
});

export default router;
