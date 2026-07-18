import { createRouter, createWebHistory } from 'vue-router'

import HomeView from '@/views/home/HomeView.vue'
import ObservationDetailView from '@/views/observation/ObservationDetailView.vue'
import ObservationFruitMeasureView from '@/views/observation/ObservationFruitMeasureView.vue'
import ObservationNewView from '@/views/observation/ObservationNewView.vue'
import ObservationPhotoView from '@/views/observation/ObservationPhotoView.vue'
import ObservationView from '@/views/observation/ObservationView.vue'
import OrderView from '@/views/orders/OrderView.vue'
import WorkLogView from '@/views/work-log/WorkLogView.vue'
import NotFoundView from '@/shared/NotFoundView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'home', component: HomeView },
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
    { path: '/orders', name: 'orders', component: OrderView },
    { path: '/:pathMatch(.*)*', name: 'not-found', component: NotFoundView },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})

export default router
