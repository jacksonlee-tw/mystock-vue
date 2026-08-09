import { createApp } from 'vue'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import ConfirmationService from 'primevue/confirmationservice'
import Ripple from 'primevue/ripple'

import App from './App.vue'
import router from './router'

// PrimeVue 3 theme（定義 --primary-color 等 CSS 變數）
import 'primevue/resources/themes/lara-light-blue/theme.css'  // PrimeVue 3 藍色主題（TCCI Blue）
import 'primeicons/primeicons.css'
import 'primeflex/primeflex.css'
// 全域樣式（含 layout SCSS）
import './assets/styles/main.scss'

const app = createApp(App)

app.use(PrimeVue, { ripple: true })
app.use(ToastService)
app.use(ConfirmationService)
app.use(router)

app.directive('ripple', Ripple)

app.mount('#app')
