import { createApp } from 'vue';
import App from './App.vue';
import router from './router';

import Aura from '@primevue/themes/aura';
import PrimeVue from 'primevue/config';
import ConfirmationService from 'primevue/confirmationservice';
import ToastService from 'primevue/toastservice';

// import 'primeicons/primeicons.css'; // PrimeVue icon 樣式 (已在 index.html 載入)

import '@/assets/project-style.css'; // TCCI 樣式
import '@/assets/styles.scss';

// PrimeVue 元件全域註冊
import Button from 'primevue/button';
import Card from 'primevue/card';
import Column from 'primevue/column';
import DataTable from 'primevue/datatable';
import Tab from 'primevue/tab';
import TabList from 'primevue/tablist';
import TabPanel from 'primevue/tabpanel';
import TabPanels from 'primevue/tabpanels';
import Tabs from 'primevue/tabs';
import Tag from 'primevue/tag';

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

app.mount('#app');
