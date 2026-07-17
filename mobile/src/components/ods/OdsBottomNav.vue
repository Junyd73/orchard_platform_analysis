<script setup lang="ts">
import { RouterLink, useRoute } from 'vue-router'
import { computed, ref } from 'vue'

import navHome from '@/assets/ods/common/nav-home.svg'
import navHomeFilled from '@/assets/ods/common/nav-home-filled.svg'
import navObservation from '@/assets/ods/common/nav-observation.svg'
import navObservationFilled from '@/assets/ods/common/nav-observation-filled.svg'
import navWorklog from '@/assets/ods/common/nav-worklog.svg'
import navWorklogFilled from '@/assets/ods/common/nav-worklog-filled.svg'
import navOrders from '@/assets/ods/common/nav-orders.svg'
import navOrdersFilled from '@/assets/ods/common/nav-orders-filled.svg'
import navProfile from '@/assets/ods/common/nav-profile.svg'
import navProfileFilled from '@/assets/ods/common/nav-profile-filled.svg'

type NavItem = {
  to?: string
  label: string
  name: string
  ready: boolean
  icon: string
  iconActive: string
}

const route = useRoute()
const profileHint = ref('')

const items: NavItem[] = [
  { to: '/', label: '홈', name: 'home', ready: true, icon: navHome, iconActive: navHomeFilled },
  {
    to: '/observation',
    label: '생육관찰',
    name: 'observation',
    ready: true,
    icon: navObservation,
    iconActive: navObservationFilled,
  },
  {
    to: '/work-log',
    label: '영농일지',
    name: 'work-log',
    ready: true,
    icon: navWorklog,
    iconActive: navWorklogFilled,
  },
  {
    to: '/orders',
    label: '주문관리',
    name: 'orders',
    ready: true,
    icon: navOrders,
    iconActive: navOrdersFilled,
  },
  {
    label: '내정보',
    name: 'profile',
    ready: false,
    icon: navProfile,
    iconActive: navProfileFilled,
  },
]

const activePath = computed(() => route.path)

function isActive(item: NavItem): boolean {
  if (!item.to) return false
  if (item.to === '/') return activePath.value === '/'
  return activePath.value === item.to || activePath.value.startsWith(`${item.to}/`)
}

function onProfileClick() {
  profileHint.value = '준비 중'
  window.setTimeout(() => {
    profileHint.value = ''
  }, 1800)
}
</script>

<template>
  <nav class="ods-nav" aria-label="하단 메뉴">
    <template v-for="item in items" :key="item.name">
      <RouterLink
        v-if="item.ready && item.to"
        class="ods-nav__item"
        :class="{ 'is-active': isActive(item) }"
        :to="item.to"
      >
        <img
          class="ods-nav__icon"
          :src="isActive(item) ? item.iconActive : item.icon"
          alt=""
          aria-hidden="true"
        >
        <span class="ods-nav__label">{{ item.label }}</span>
      </RouterLink>
      <button
        v-else
        type="button"
        class="ods-nav__item ods-nav__item--soon"
        @click="onProfileClick"
      >
        <img class="ods-nav__icon" :src="item.icon" alt="" aria-hidden="true">
        <span class="ods-nav__label">{{ item.label }}</span>
      </button>
    </template>
  </nav>
  <p v-if="profileHint" class="ods-nav__toast" role="status">{{ profileHint }}</p>
</template>

<style scoped>
.ods-nav {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 50;
  max-width: 480px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: var(--ods-space-4);
  min-height: var(--ods-space-56);
  padding: var(--ods-space-8) var(--ods-space-8) calc(var(--ods-space-8) + env(safe-area-inset-bottom));
  background: var(--ods-color-white);
  border-top: 1px solid var(--ods-color-border);
  box-shadow: 0 -2px 8px rgba(33, 33, 33, 0.04);
}
.ods-nav__item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  min-height: var(--ods-touch-min);
  text-decoration: none;
  color: var(--ods-color-gray-500);
  font: var(--ods-font-caption);
  font-weight: 500;
  background: transparent;
  border: none;
  padding: 0;
  cursor: pointer;
}
.ods-nav__icon {
  width: 24px;
  height: 24px;
  color: currentColor;
}
.ods-nav__item.is-active {
  color: var(--ods-color-primary);
  font-weight: 600;
}
.ods-nav__item--soon {
  color: var(--ods-color-gray-300);
}
.ods-nav__toast {
  position: fixed;
  left: 50%;
  bottom: calc(72px + env(safe-area-inset-bottom));
  transform: translateX(-50%);
  z-index: 60;
  margin: 0;
  padding: var(--ods-space-8) var(--ods-space-16);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-gray-900);
  color: var(--ods-color-white);
  font: var(--ods-font-caption);
}
</style>
