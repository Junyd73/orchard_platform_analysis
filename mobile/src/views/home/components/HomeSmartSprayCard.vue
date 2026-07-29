<script setup lang="ts">
import { useRouter } from 'vue-router'

import iconPest from '@/assets/ods/common/icon-kpi-pest.svg'
import iconSmart from '@/assets/ods/home/icon-title-smart-spray.svg'
import HomeCardHead from '@/views/home/components/HomeCardHead.vue'
import {
  BTN_HOME_DETAIL,
  LABEL_HOME_SMART_SPRAY,
} from '@/views/home/homeConstants'
import type { HomeSmartSprayMock } from '@/views/home/homeMock'

defineProps<{
  spray: HomeSmartSprayMock
}>()

const router = useRouter()

function goSmartSpray() {
  void router.push({ name: 'pesticide-smart-spray' })
}
</script>

<template>
  <section class="card" aria-label="스마트 방제">
    <HomeCardHead
      :title="LABEL_HOME_SMART_SPRAY"
      :icon="iconSmart"
      :detail-label="BTN_HOME_DETAIL"
      @detail="goSmartSpray"
    />
    <div class="body">
      <img class="body__ico" :src="iconPest" alt="" aria-hidden="true" />
      <div class="body__text">
        <div class="body__top">
          <p class="body__pest">{{ spray.pestName }}</p>
          <span class="badge">{{ spray.riskLabel }}</span>
        </div>
        <p class="body__hint">{{ spray.hint }}</p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.card {
  display: flex;
  flex-direction: column;
  min-height: 100%;
  min-width: 0;
  padding: var(--ods-space-12);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  box-shadow: var(--ods-shadow-card);
  box-sizing: border-box;
}
.body {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  flex: 1 1 auto;
}
.body__ico {
  width: 36px;
  height: 36px;
  padding: 7px;
  border-radius: 10px;
  background: color-mix(in srgb, var(--ods-color-primary) 10%, #fff);
  box-sizing: border-box;
}
.body__text {
  min-width: 0;
  flex: 1;
}
.body__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}
.body__pest {
  margin: 0;
  font: 600 14px/1.3 var(--ods-font-family);
  color: var(--ods-color-text);
}
.badge {
  flex-shrink: 0;
  padding: 2px 6px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--ods-color-danger) 16%, #fff);
  color: var(--ods-color-danger);
  font: 600 10px/1.2 var(--ods-font-family);
}
.body__hint {
  margin: 4px 0 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
