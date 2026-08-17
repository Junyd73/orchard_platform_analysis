<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import MobileLayout from '@/layouts/MobileLayout.vue'
import { useAppStore } from '@/composables/stores/app'
import HomeBriefingCard from '@/views/home/components/HomeBriefingCard.vue'
import HomeHero from '@/views/home/components/HomeHero.vue'
import HomePesticideQuickModal from '@/views/home/components/HomePesticideQuickModal.vue'
import HomeQuickActions from '@/views/home/components/HomeQuickActions.vue'
import HomeRecentActivity from '@/views/home/components/HomeRecentActivity.vue'
import HomeSmartSprayCard from '@/views/home/components/HomeSmartSprayCard.vue'
import HomeWeatherCard from '@/views/home/components/HomeWeatherCard.vue'
import {
  HOME_KPI_EMPTY,
  HOME_SMART_SPRAY_EMPTY,
  HOME_WEATHER_EMPTY,
  loadHomeDashboard,
} from '@/views/home/homeData'
import type { HomeBriefingItem, HomeRecentItem } from '@/views/home/homeMock'
import { todayBizIso } from '@/shared/bizDate'

const router = useRouter()
const store = useAppStore()
const { farm, farmCd } = storeToRefs(store)

const toastMsg = ref('')
const pestModalOpen = ref(false)
let toastTimer = 0

const kpi = ref({ ...HOME_KPI_EMPTY })
const smartSpray = ref({ ...HOME_SMART_SPRAY_EMPTY })
const weather = ref({ ...HOME_WEATHER_EMPTY })
const briefing = ref<HomeBriefingItem[]>([])
const recent = ref<HomeRecentItem[]>([])

let loadSeq = 0
let lastHomeToday = ''

async function reloadHomeDashboard() {
  const cd = String(farmCd.value || '').trim()
  if (!cd) return
  const seq = ++loadSeq
  const data = await loadHomeDashboard(cd, {
    farmNm: farm.value?.farm_nm,
    farmAddress: farm.value?.address,
  })
  if (seq !== loadSeq) return
  kpi.value = data.kpi
  smartSpray.value = data.smartSpray
  weather.value = data.weather
  briefing.value = data.briefing
  recent.value = data.recent
  lastHomeToday = todayBizIso()
}

function onHomeVisibility() {
  if (document.visibilityState !== 'visible') return
  const t = todayBizIso()
  if (t !== lastHomeToday) void reloadHomeDashboard()
}

onMounted(() => {
  document.addEventListener('visibilitychange', onHomeVisibility)
  void (async () => {
    await store.refreshAll()
    await reloadHomeDashboard()
  })()
})

onUnmounted(() => {
  document.removeEventListener('visibilitychange', onHomeVisibility)
})

watch(farmCd, () => {
  void reloadHomeDashboard()
})

function showToast(msg: string) {
  toastMsg.value = msg
  window.clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => {
    toastMsg.value = ''
  }, 2200)
}

function onWeatherDetail() {
  void router.push({ name: 'weather-detail' })
}
</script>

<template>
  <MobileLayout>
    <div class="home">
      <HomeHero
        :farm-name="farm?.farm_nm || ''"
        :today-work="kpi.todayWork"
        :labor-count="kpi.laborCount"
        :pest-caution="kpi.pestCaution"
        :spray-plan="kpi.sprayPlan"
      />

      <HomeQuickActions
        @soon="showToast"
        @pesticide="pestModalOpen = true"
      />

      <div class="home__row">
        <HomeSmartSprayCard :spray="smartSpray" />
        <HomeWeatherCard
          :weather="weather"
          @detail="onWeatherDetail"
        />
      </div>

      <HomeBriefingCard :items="briefing" />

      <HomeRecentActivity :items="recent" />
    </div>

    <HomePesticideQuickModal
      :open="pestModalOpen"
      @close="pestModalOpen = false"
      @saved="showToast"
      @error="showToast"
    />

    <p v-if="toastMsg" class="toast" role="status">{{ toastMsg }}</p>
  </MobileLayout>
</template>

<style scoped>
.home {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
}
.home__row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--ods-space-12);
  align-items: stretch;
}
.toast {
  position: fixed;
  left: 50%;
  bottom: calc(var(--ods-space-64) + var(--ods-space-8) + env(safe-area-inset-bottom, 0px));
  z-index: 90;
  margin: 0;
  padding: 10px 14px;
  border-radius: 10px;
  background: rgba(33, 33, 33, 0.88);
  color: #fff;
  font: var(--ods-font-body-2);
  transform: translateX(-50%);
  white-space: nowrap;
}
</style>
