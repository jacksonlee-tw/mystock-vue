// 策略分類群組定義：後端 strategy.category 對應到顯示用的分組標題與圖示。
// AlertDashboard（篩選下拉選單分組）與 AlertTimeline（清單項目圖示）共用同一份定義，
// 避免兩處各自刻一份而日後改一邊漏改另一邊。
export const CATEGORY_GROUPS = [
    { category: 'technical', label: '均線', icon: 'pi pi-chart-line' },
    { category: 'chip', label: '籌碼選股', icon: 'pi pi-wallet' },
    { category: 'extreme_risk', label: '極端抄底', icon: 'pi pi-bolt' }
];

export const OTHER_CATEGORY = { category: 'other', label: '其他策略', icon: 'pi pi-sliders-h' };

export function categoryMeta(category) {
    return CATEGORY_GROUPS.find((g) => g.category === category) || OTHER_CATEGORY;
}
