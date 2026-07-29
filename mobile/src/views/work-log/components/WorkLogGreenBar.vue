<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import iconBell from '@/assets/ods/common/icon-bell.svg'
import iconChevronDown from '@/assets/ods/common/icon-chevron-down.svg'
import iconSettings from '@/assets/ods/common/icon-settings.svg'
import { useAppStore } from '@/composables/stores/app'
import { useNotificationBadgeStore } from '@/composables/stores/notificationBadge'

/** SCR-010 전용: 시안3 녹색 상단바 (전역 OdsAppBar 대체) */
const router = useRouter()
const store = useAppStore()
const badgeStore = useNotificationBadgeStore()
const { farm, farmCd } = storeToRefs(store)
const { unreadBadge } = storeToRefs(badgeStore)
const toast = ref('')

const farmName = computed(() => farm.value?.farm_nm || farmCd.value)

function showSoon(label: string) {
  toast.value = `${label} 준비 중`
  window.setTimeout(() => {
    if (toast.value.startsWith(label)) toast.value = ''
  }, 1600)
}

function goNotifications() {
  void router.push({ name: 'notifications' })
}

onMounted(() => {
  void badgeStore.refresh(farmCd.value)
})
</script>

<template>
  <header class="wl-bar" aria-label="앱 상단바">
    <div class="wl-bar__inner">
      <button type="button" class="wl-bar__farm" aria-label="농장 선택" @click="showSoon('농장 선택')">
        <span class="wl-bar__farm-name">{{ farmName }}</span>
        <img class="wl-bar__chev" :src="iconChevronDown" alt="" aria-hidden="true" />
      </button>
      <div class="wl-bar__right">
        <button type="button" class="wl-bar__icon" aria-label="알림" @click="goNotifications">
          <img :src="iconBell" alt="" aria-hidden="true" />
          <span v-if="unreadBadge" class="wl-bar__badge">{{ unreadBadge }}</span>
        </button>
        <button type="button" class="wl-bar__icon" aria-label="환경설정" @click="showSoon('환경설정')">
          <img :src="iconSettings" alt="" aria-hidden="true" />
        </button>
      </div>
    </div>
  </header>
  <p v-if="toast" class="wl-bar__toast" role="status">{{ toast }}</p>
</template>

<style scoped>
.wl-bar {
  padding-top: env(safe-area-inset-top, 0px);
  background: transparent;
  color: var(--ods-color-white);
}
.wl-bar__inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-12);
  min-height: var(--ods-thumb-sm);
  height: var(--ods-thumb-sm);
  padding: 0 var(--ods-space-16);
}
.wl-bar__farm {
  display: inline-flex;
  align-items: center;
  gap: var(--ods-space-8);
  min-width: 0;
  max-width: 70%;
  border: none;
  background: transparent;
  padding: 0;
  min-height: var(--ods-touch-min);
  cursor: pointer;
  color: var(--ods-color-white);
}
.wl-bar__farm-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font: var(--ods-font-title-2);
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--ods-color-white);
}
.wl-bar__chev {
  width: var(--ods-icon-md);
  height: var(--ods-icon-md);
  flex-shrink: 0;
  filter: brightness(0) invert(1);
  opacity: 0.92;
}
.wl-bar__right {
  display: flex;
  align-items: center;
  gap: var(--ods-space-4);
  flex-shrink: 0;
}
.wl-bar__icon {
  position: relative;
  width: var(--ods-touch-min);
  height: var(--ods-touch-min);
  border: none;
  background: transparent;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.wl-bar__icon img {
  width: var(--ods-icon-xl);
  height: var(--ods-icon-xl);
  filter: brightness(0) invert(1);
}
.wl-bar__badge {
  position: absolute;
  top: var(--ods-space-4);
  right: var(--ods-space-4);
  min-width: var(--ods-icon-md);
  height: var(--ods-icon-md);
  padding: 0 var(--ods-space-4);
  border-radius: var(--ods-radius-badge);
  background: var(--ods-color-danger);
  color: var(--ods-color-white);
  font: var(--ods-font-card-help);
  font-weight: 700;
  line-height: var(--ods-icon-md);
  text-align: center;
}
.wl-bar__toast {
  position: fixed;
  left: 50%;
  top: calc(var(--ods-space-12) + env(safe-area-inset-top, 0px));
  transform: translateX(-50%);
  z-index: 80;
  margin: 0;
  padding: var(--ods-space-8) var(--ods-space-16);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-gray-900);
  color: var(--ods-color-white);
  font: var(--ods-font-form-help);
}
</style>
