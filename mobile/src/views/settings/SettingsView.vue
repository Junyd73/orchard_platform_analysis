<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'

import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsCard from '@/components/ods/OdsCard.vue'
import {
  LABEL_CONN,
  LABEL_FARM_CD,
  LABEL_FARM_NM,
  LABEL_PROFILE_HINT,
  LABEL_PROFILE_SECTION,
  LABEL_ROLE,
  LABEL_SESSION_SECTION,
  LABEL_SETTINGS_TITLE,
  LABEL_USER_ID,
  PLACEHOLDER_DASH,
} from '@/views/settings/settingsConstants'
import { getCurrentUser } from '@/shared/auth/userContext'
import { useAppStore } from '@/composables/stores/app'

const store = useAppStore()
const { farm, farmCd, farmTitle, connectionMessage, connectionStatus } = storeToRefs(store)

const user = computed(() => getCurrentUser())
const userId = computed(() => user.value?.userId || PLACEHOLDER_DASH)
const roleCd = computed(() => user.value?.roleCd || PLACEHOLDER_DASH)
const farmName = computed(() => {
  const nm = String(farm.value?.farm_nm || '').trim()
  return nm || farmTitle.value || PLACEHOLDER_DASH
})

onMounted(() => {
  void store.refreshAll()
})
</script>

<template>
  <div class="page">
    <main class="content ods-page-content">
      <OdsAppBar show-back back-fallback="home" />
      <header class="head">
        <h1 class="head__title">{{ LABEL_SETTINGS_TITLE }}</h1>
      </header>
      <OdsCard :title="LABEL_SESSION_SECTION">
        <dl class="kv">
          <div class="kv__row">
            <dt>{{ LABEL_FARM_CD }}</dt>
            <dd>{{ farmCd || PLACEHOLDER_DASH }}</dd>
          </div>
          <div class="kv__row">
            <dt>{{ LABEL_FARM_NM }}</dt>
            <dd>{{ farmName }}</dd>
          </div>
          <div class="kv__row">
            <dt>{{ LABEL_CONN }}</dt>
            <dd>{{ connectionStatus }} · {{ connectionMessage || PLACEHOLDER_DASH }}</dd>
          </div>
        </dl>
      </OdsCard>
      <OdsCard :title="LABEL_PROFILE_SECTION">
        <dl class="kv">
          <div class="kv__row">
            <dt>{{ LABEL_USER_ID }}</dt>
            <dd>{{ userId }}</dd>
          </div>
          <div class="kv__row">
            <dt>{{ LABEL_ROLE }}</dt>
            <dd>{{ roleCd }}</dd>
          </div>
        </dl>
        <p class="hint">{{ LABEL_PROFILE_HINT }}</p>
      </OdsCard>
    </main>
    <OdsBottomNav />
  </div>
</template>

<style scoped>
.page {
  min-height: 100dvh;
  background: var(--ods-color-bg-muted);
  padding-bottom: calc(var(--ods-space-56) + env(safe-area-inset-bottom));
}
.head__title {
  margin: 0;
  font: var(--ods-font-title-2);
  font-weight: 800;
  color: var(--ods-color-text);
}
.kv {
  margin: 0;
}
.kv__row {
  display: flex;
  justify-content: space-between;
  gap: var(--ods-space-12);
  padding: var(--ods-space-8) 0;
  border-bottom: 1px solid var(--ods-color-border);
}
.kv__row:last-of-type {
  border-bottom: none;
  padding-bottom: 0;
}
.kv__row:first-of-type {
  padding-top: 0;
}
dt {
  margin: 0;
  font: var(--ods-font-form-label);
  color: var(--ods-color-text-secondary);
}
dd {
  margin: 0;
  font: var(--ods-font-form-value);
  font-weight: 600;
  color: var(--ods-color-text);
  text-align: right;
  word-break: break-all;
}
.hint {
  margin: var(--ods-space-12) 0 0;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
}
</style>
