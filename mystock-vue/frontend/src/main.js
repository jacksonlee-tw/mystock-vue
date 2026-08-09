import { createApp } from 'vue';
import App from './App.vue';
import router from './router';

import Aura from '@primevue/themes/aura';
import PrimeVue from 'primevue/config';
import ConfirmationService from 'primevue/confirmationservice';
import ToastService from 'primevue/toastservice';

// 品牌強調色（brass／黃銅）實際生效的地方是 assets/layout/variables/_common-brass.scss。
// 該檔以 !important 覆寫 --p-primary-*，會蓋掉這裡透過 PrimeVue JS 主題設定的任何顏色，
// 所以主色不在這裡（definePreset）調整，維持專案既有的「一份 _common-*.scss 定義一組主色」慣例。

// import 'primeicons/primeicons.css'; // PrimeVue icon 樣式 (已在 index.html 載入)

import '@/assets/project-style.css'; // TCCI 樣式
import '@/assets/styles.scss';

// PrimeVue 元件全域註冊
import Button from 'primevue/button';
import Card from 'primevue/card';
import Column from 'primevue/column';
import ConfirmDialog from 'primevue/confirmdialog';
import DataTable from 'primevue/datatable';
import Tab from 'primevue/tab';
import TabList from 'primevue/tablist';
import TabPanel from 'primevue/tabpanel';
import TabPanels from 'primevue/tabpanels';
import Tabs from 'primevue/tabs';
import Tag from 'primevue/tag';
import Toast from 'primevue/toast';

const app = createApp(App);

app.use(router);
app.use(PrimeVue, {
    theme: {
        preset: Aura,
        options: {
            darkModeSelector: '.app-dark'
        }
    }
});
app.use(ToastService);
app.use(ConfirmationService);

app.component('Button', Button);
app.component('Card', Card);
app.component('Tag', Tag);
app.component('DataTable', DataTable);
app.component('Column', Column);
app.component('Tabs', Tabs);
app.component('TabList', TabList);
app.component('Tab', Tab);
app.component('TabPanel', TabPanel);
app.component('TabPanels', TabPanels);
app.component('Toast', Toast);
app.component('ConfirmDialog', ConfirmDialog);

app.mount('#app');
