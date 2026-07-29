<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'

import { ApiClientError } from '@/api/client'
import { fetchWeatherDetail } from '@/api/weather'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsEmptyState from '@/components/ods/OdsEmptyState.vue'
import WeatherCurrentPanel from '@/views/weather/components/WeatherCurrentPanel.vue'
import WeatherHourlyStrip from '@/views/weather/components/WeatherHourlyStrip.vue'
import WeatherWeeklyList from '@/views/weather/components/WeatherWeeklyList.vue'
import {
  LABEL_WEATHER_DETAIL,
  LABEL_WEATHER_UPDATED,
  MSG_WEATHER_EMPTY,
  MSG_WEATHER_LOAD_FAILED,
  MSG_WEATHER_LOADING,
} from '@/views/weather/weatherConstants'
import { formatUpdatedAt } from '@/views/weather/weatherFormat'
import { useAppStore } from '@/composables/stores/app'
import type { WeatherDetailResponse } from '@/types/weather'

const store = useAppStore()
const { farmCd } = storeToRefs(store)

const loading = ref(true)
const errorMsg = ref('')
const detail = ref<WeatherDetailResponse | null>(null)

const hasData = computed(() => Boolean(detail.value?.current))

async function loadDetail() {
  const farm = String(farmCd.value || '').trim()
  if (!farm) {
    loading.value = false
    errorMsg.value = MSG_WEATHER_LOAD_FAILED
    detail.value = null
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    detail.value = await fetchWeatherDetail(farm)
  } catch (err) {
    detail.value = null
    errorMsg.value =
      err instanceof ApiClientError ? err.message : MSG_WEATHER_LOAD_FAILED
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void (async () => {
    await store.refreshAll()
    await loadDetail()
  })()
})

watch(farmCd, () => {
  void loadDetail()
})
</script>

<template>
  <div class="page">
    <main class="content ods-page-content">
      <OdsAppBar show-back back-fallback="home" />
      <div class="body">
        <header class="head">
          <h1 class="head__title">{{ LABEL_WEATHER_DETAIL }}</h1>
          <p v-if="detail?.updated_at" class="head__updated">
            {{ LABEL_WEATHER_UPDATED }} {{ formatUpdatedAt(detail.updated_at) }}
          </p>
        </header>

        <p v-if="loading" class="state" role="status">{{ MSG_WEATHER_LOADING }}</p>
        <OdsEmptyState
          v-else-if="errorMsg"
          :title="MSG_WEATHER_LOAD_FAILED"
          :description="errorMsg"
        />
        <OdsEmptyState
          v-else-if="!hasData"
          :title="MSG_WEATHER_EMPTY"
        />
        <template v-else-if="detail">
          <WeatherCurrentPanel
            :current="detail.current"
            :location="detail.location"
            :tomorrow-am="detail.tomorrow_am"
          />
          <WeatherHourlyStrip :items="detail.hourly" />
          <WeatherWeeklyList :items="detail.weekly" />
        </template>
      </div>
    </main>
    <OdsBottomNav />
  </div>
</template>

<style scoped>
.page {
  min-height: 100dvh;
  background: var(--ods-color-bg-muted);
  padding-bottom: calc(148px + env(safe-area-inset-bottom, 0px));
}
.body {
  display: flex;
  flex-direction: column;
  gap: var(--ods-page-content-gap);
  min-width: 0;
}
.head__title {
  margin: 0;
  font: 700 20px/1.3 var(--ods-font-family);
  color: var(--ods-color-text);
}
.head__updated {
  margin: 4px 0 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.state {
  margin: 0;
  padding: 24px 8px;
  text-align: center;
  font: var(--ods-font-body);
  color: var(--ods-color-text-secondary);
}
</style>
