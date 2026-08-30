import AppLayout from '@/layout/AppLayout.vue';
import { createRouter, createWebHistory } from 'vue-router';
import { useMarket } from '@/composables/useMarket';
import { ownerApi } from '@/service/ownerApi';

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
                // 產業鏈知識圖譜與輪動模型（docs/16.AI技術分析/Phase3-產業鏈知識圖譜與輪動模型.md §8）
                {
                    path: '/industry-chains',
                    name: 'industry-chains',
                    component: () => import('@/views/industry-chain/IndustryChainView.vue')
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
                // LLM 呼叫執行歷史（docs/16.AI技術分析/執行歷史頁面開發計劃.md §3.1）
                {
                    path: '/ai/executions',
                    name: 'ai-execution-history',
                    component: () => import('@/views/ai/AiExecutionHistory.vue')
                },
                {
                    path: '/notify/channels',
                    name: 'notify-channels',
                    component: () => import('@/views/notify/ChannelSettings.vue'),
                    meta: { requiresOwner: true }
                },
                {
                    path: '/notify/recipients',
                    name: 'notify-recipients',
                    component: () => import('@/views/notify/RecipientManagement.vue'),
                    meta: { requiresOwner: true }
                },
                {
                    path: '/notify/subscriptions',
                    name: 'notify-subscriptions',
                    component: () => import('@/views/notify/SubscriptionRules.vue'),
                    meta: { requiresOwner: true }
                },
                {
                    path: '/notify/templates',
                    name: 'notify-templates',
                    component: () => import('@/views/notify/MessageTemplates.vue'),
                    meta: { requiresOwner: true }
                },
                {
                    path: '/notify/logs',
                    name: 'notify-logs',
                    component: () => import('@/views/notify/DeliveryLogs.vue'),
                    meta: { requiresOwner: true }
                },
                // ── 個人投資記帳與績效追蹤模組（docs/8.個人投資記帳功能/）─────────
                {
                    path: '/portfolio',
                    name: 'portfolio-dashboard',
                    component: () => import('@/views/portfolio/PortfolioDashboard.vue'),
                    meta: { requiresOwner: true }
                },
                {
                    path: '/portfolio/transactions',
                    name: 'portfolio-transactions',
                    component: () => import('@/views/portfolio/TransactionList.vue'),
                    meta: { requiresOwner: true }
                },
                {
                    path: '/portfolio/holdings',
                    name: 'portfolio-holdings',
                    component: () => import('@/views/portfolio/HoldingsView.vue'),
                    meta: { requiresOwner: true }
                },
                {
                    path: '/portfolio/realized',
                    name: 'portfolio-realized',
                    component: () => import('@/views/portfolio/RealizedPnlView.vue'),
                    meta: { requiresOwner: true }
                },
                {
                    path: '/portfolio/cashflow',
                    name: 'portfolio-cashflow',
                    component: () => import('@/views/portfolio/CashflowView.vue'),
                    meta: { requiresOwner: true }
                },
                {
                    path: '/portfolio/watchlist',
                    name: 'portfolio-watchlist',
                    component: () => import('@/views/portfolio/WatchlistView.vue'),
                    meta: { requiresOwner: true }
                },
                {
                    path: '/portfolio/notes',
                    name: 'portfolio-notes',
                    component: () => import('@/views/portfolio/InvestmentNotesView.vue'),
                    meta: { requiresOwner: true }
                },
                {
                    path: '/portfolio/settings',
                    name: 'portfolio-settings',
                    component: () => import('@/views/portfolio/PortfolioSettingsView.vue'),
                    meta: { requiresOwner: true }
                }
            ]
        },
        {
            // 管理端登入：不掛在 AppLayout 之下，避免未登入時先閃過整個殼層（見系統開發規格書 §9.1）
            path: '/login',
            alias: '/notify/login',
            name: 'owner-login',
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
    if (to.meta.requiresOwner) {
        const authenticated = await ownerApi.whoami();
        if (!authenticated) {
            next({ name: 'owner-login', query: { redirect: to.fullPath } });
            return;
        }
    }
    next();
});

export default router;
