<script setup lang="ts">
import { computed, ref } from 'vue'

import iconPlus from '@/assets/ods/work-log/icon-plus.svg'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsEmptyState from '@/components/ods/OdsEmptyState.vue'
import OdsFab from '@/components/ods/OdsFab.vue'
import OdsSegmented from '@/components/ods/OdsSegmented.vue'
import {
  LABEL_FAB_ORDER,
  LABEL_FAB_SALES,
  LABEL_PAGE_TITLE,
  LABEL_SEGMENT_ARIA,
  MSG_ORDER_EMPTY_DESC,
  MSG_ORDER_EMPTY_TITLE,
  MSG_SALES_EMPTY_DESC,
  MSG_SALES_EMPTY_TITLE,
  MSG_STAGE_LATER,
  ORDER_SALES_SEGMENT_OPTIONS,
  TAB_ORDER,
} from '@/views/orders/ordersConstants'

const segment = ref<string>(TAB_ORDER)
const toastMsg = ref('')
let toastTimer = 0

const segmentOptions = ORDER_SALES_SEGMENT_OPTIONS.map((opt) => ({
  value: opt.value,
  label: opt.label,
}))

const isOrderTab = computed(() => segment.value === TAB_ORDER)
const fabLabel = computed(() => (isOrderTab.value ? LABEL_FAB_ORDER : LABEL_FAB_SALES))
const emptyTitle = computed(() =>
  isOrderTab.value ? MSG_ORDER_EMPTY_TITLE : MSG_SALES_EMPTY_TITLE,
)
const emptyDesc = computed(() =>
  isOrderTab.value ? MSG_ORDER_EMPTY_DESC : MSG_SALES_EMPTY_DESC,
)

function showToast(msg: string) {
  toastMsg.value = msg
  window.clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => {
    toastMsg.value = ''
  }, 1800)
}

function onFab() {
  showToast(MSG_STAGE_LATER)
}
</script>

<template>
  <div class="page">
    <main class="content ods-page-content">
      <OdsAppBar />
      <header class="head">
        <h1 class="head__title">{{ LABEL_PAGE_TITLE }}</h1>
        <OdsSegmented
          v-model="segment"
          :options="segmentOptions"
          :aria-label="LABEL_SEGMENT_ARIA"
        />
      </header>
      <OdsEmptyState :title="emptyTitle" :description="emptyDesc" />
    </main>
    <!-- eslint-disable vue/attribute-hyphenation -->
    <OdsFab :label="fabLabel" :ariaLabel="fabLabel" @click="onFab">
      <img :src="iconPlus" alt="">
    </OdsFab>
    <!-- eslint-enable vue/attribute-hyphenation -->
    <p v-if="toastMsg" class="toast" role="status">{{ toastMsg }}</p>
    <OdsBottomNav />
  </div>
</template>

<style scoped>
.page {
  min-height: 100dvh;
  background: var(--ods-color-bg-muted);
  padding-bottom: calc(140px + env(safe-area-inset-bottom));
}
.head {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
}
.head__title {
  margin: 0;
  font: var(--ods-font-title-2);
  font-weight: 800;
  color: var(--ods-color-text);
}
.toast {
  position: fixed;
  left: 50%;
  bottom: calc(var(--ods-space-64) + var(--ods-space-8) + env(safe-area-inset-bottom));
  transform: translateX(-50%);
  z-index: 60;
  margin: 0;
  padding: var(--ods-space-8) var(--ods-space-16);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-gray-900);
  color: var(--ods-color-white);
  font: var(--ods-font-form-help);
}
</style>
