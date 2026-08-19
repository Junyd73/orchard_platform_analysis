import { createRouter, createWebHistory } from 'vue-router'

import HomeView from '@/views/home/HomeView.vue'
import NotificationView from '@/views/notification/NotificationView.vue'
import ObservationDetailView from '@/views/observation/ObservationDetailView.vue'
import ObservationFruitMeasureView from '@/views/observation/ObservationFruitMeasureView.vue'
import ObservationNewView from '@/views/observation/ObservationNewView.vue'
import ObservationPhotoView from '@/views/observation/ObservationPhotoView.vue'
import ObservationView from '@/views/observation/ObservationView.vue'
import OrderView from '@/views/orders/OrderView.vue'
import OrderNewView from '@/views/orders/OrderNewView.vue'
import OrderDetailView from '@/views/orders/OrderDetailView.vue'
import SettingsView from '@/views/settings/SettingsView.vue'
import PesticideStockView from '@/views/pesticide/PesticideStockView.vue'
import PesticideItemDetailView from '@/views/pesticide/PesticideItemDetailView.vue'
import PesticideStatsView from '@/views/pesticide/PesticideStatsView.vue'
import PesticideDictView from '@/views/pesticide/PesticideDictView.vue'
import PesticidePestDictView from '@/views/pesticide/PesticidePestDictView.vue'
import PesticideReceiptListView from '@/views/pesticide/PesticideReceiptListView.vue'
import PesticideReceiptEditView from '@/views/pesticide/PesticideReceiptEditView.vue'
import PesticideStockManageView from '@/views/pesticide/PesticideStockManageView.vue'
import PesticideStockHistView from '@/views/pesticide/PesticideStockHistView.vue'
import PesticideSmartSprayView from '@/views/pesticide/PesticideSmartSprayView.vue'
import PesticideOutbreakSettingsView from '@/views/pesticide/PesticideOutbreakSettingsView.vue'
import WeatherDetailView from '@/views/weather/WeatherDetailView.vue'
import WorkLogView from '@/views/work-log/WorkLogView.vue'
import WorkLogDailyView from '@/views/work-log/WorkLogDailyView.vue'
import NotFoundView from '@/shared/NotFoundView.vue'
import { resolveMainTabIndex } from '@/shared/mainTabNav'
import { setMainTabSlideByIndex } from '@/shared/mainTabSlide'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    {
      path: '/weather',
      name: 'weather-detail',
      component: WeatherDetailView,
    },
    { path: '/observation', name: 'observation', component: ObservationView },
    {
      path: '/observation/new',
      name: 'observation-new',
      component: ObservationNewView,
    },
    /* 문서·직접 URL 호환 */
    {
      path: '/observations/new',
      redirect: { name: 'observation-new' },
    },
    {
      path: '/observation/:obsId/photos',
      name: 'observation-photos',
      component: ObservationPhotoView,
    },
    {
      path: '/observation/:obsId/fruit',
      name: 'observation-fruit',
      component: ObservationFruitMeasureView,
    },
    {
      path: '/observation/:obsId',
      name: 'observation-detail',
      component: ObservationDetailView,
    },
    { path: '/work-log', name: 'work-log', component: WorkLogView },
    {
      path: '/work-log/:workDt',
      name: 'work-log-daily',
      component: WorkLogDailyView,
    },
    {
      path: '/notifications',
      name: 'notifications',
      component: NotificationView,
    },
    { path: '/pesticide', name: 'pesticide', component: PesticideStockView },
    {
      path: '/pesticide/smart-spray',
      name: 'pesticide-smart-spray',
      component: PesticideSmartSprayView,
    },
    {
      path: '/pesticide/outbreak-settings',
      name: 'pesticide-outbreak-settings',
      component: PesticideOutbreakSettingsView,
    },
    {
      path: '/pesticide/stats',
      name: 'pesticide-stats',
      component: PesticideStatsView,
    },
    {
      path: '/pesticide/dict',
      name: 'pesticide-dict',
      component: PesticideDictView,
    },
    {
      path: '/pesticide/pest-dict',
      name: 'pesticide-pest-dict',
      component: PesticidePestDictView,
    },
    {
      path: '/pesticide/receipts',
      name: 'pesticide-receipts',
      component: PesticideReceiptListView,
    },
    {
      path: '/pesticide/receipts/new',
      name: 'pesticide-receipt-new',
      component: PesticideReceiptEditView,
    },
    {
      path: '/pesticide/receipts/:receiptId',
      name: 'pesticide-receipt-detail',
      component: PesticideReceiptEditView,
    },
    {
      path: '/pesticide/stock',
      name: 'pesticide-stock',
      component: PesticideStockManageView,
    },
    {
      path: '/pesticide/stock/:itemId/hist',
      name: 'pesticide-stock-hist',
      component: PesticideStockHistView,
    },
    {
      path: '/pesticide/:itemId',
      name: 'pesticide-detail',
      component: PesticideItemDetailView,
    },
    { path: '/orders', name: 'orders', component: OrderView },
    {
      path: '/orders/ship',
      name: 'ship-confirm',
      component: () => import('@/views/sales/ShipConfirmView.vue'),
    },
    { path: '/orders/new', name: 'order-new', component: OrderNewView },
    {
      path: '/orders/:orderNo/edit',
      name: 'order-edit',
      component: OrderNewView,
    },
    {
      path: '/orders/:orderNo',
      name: 'order-detail',
      component: OrderDetailView,
    },
    { path: '/settings', name: 'settings', component: SettingsView },
    { path: '/:pathMatch(.*)*', name: 'not-found', component: NotFoundView },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})

router.beforeEach((to, from) => {
  setMainTabSlideByIndex(
    resolveMainTabIndex(from.path),
    resolveMainTabIndex(to.path),
  )
})

export default router
