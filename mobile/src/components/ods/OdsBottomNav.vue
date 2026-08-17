<script setup lang="ts">
import { RouterLink, useRoute } from 'vue-router'
import { computed, inject } from 'vue'

import navHome from '@/assets/ods/common/nav-home.svg'
import navHomeFilled from '@/assets/ods/common/nav-home-filled.svg'
import navObservation from '@/assets/ods/common/nav-observation.svg'
import navObservationFilled from '@/assets/ods/common/nav-observation-filled.svg'
import navWorklog from '@/assets/ods/common/nav-worklog.svg'
import navWorklogFilled from '@/assets/ods/common/nav-worklog-filled.svg'
import navPesticide from '@/assets/ods/common/nav-pesticide.svg'
import navPesticideFilled from '@/assets/ods/common/nav-pesticide-filled.svg'
import navOrders from '@/assets/ods/common/nav-orders.svg'
import navOrdersFilled from '@/assets/ods/common/nav-orders-filled.svg'

type NavItem = {
  to: string
  label: string
  name: string
  ready: boolean
  icon: string
  iconActive: string
}

const route = useRoute()

/** 메인 탭 캐러셀 패널 안에서는 숨김 — App 바깥 단일 네비 사용(fixed+transform 충돌 방지) */
const suppressBottomNav = inject<boolean>('mainTabSuppressBottomNav', false)
const showNav = computed(() => !suppressBottomNav)

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
    to: '/pesticide',
    label: '농약관리',
    name: 'pesticide',
    ready: true,
    icon: navPesticide,
    iconActive: navPesticideFilled,
  },
  {
    to: '/orders',
    label: '주문/판매',
    name: 'orders',
    ready: true,
    icon: navOrders,
    iconActive: navOrdersFilled,
  },
]

const activePath = computed(() => route.path)

function isActive(item: NavItem): boolean {
  if (item.to === '/') return activePath.value === '/'
  if (item.name === 'pesticide') {
    return (
      activePath.value === '/pesticide'
      || activePath.value.startsWith('/pesticide/')
    )
  }
  if (item.name === 'orders') {
    return (
      activePath.value === '/orders'
      || activePath.value.startsWith('/orders/')
    )
  }
  return activePath.value === item.to || activePath.value.startsWith(`${item.to}/`)
}
</script>

<template>
  <nav v-if="showNav" class="ods-nav" aria-label="하단 메뉴">
    <template v-for="item in items" :key="item.name">
      <RouterLink
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
    </template>
  </nav>
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
  width: var(--ods-icon-2xl);
  height: var(--ods-icon-2xl);
  color: currentColor;
}
.ods-nav__label {
  max-width: 100%;
  padding: 0 1px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 10px;
  line-height: 1.2;
  text-align: center;
}
.ods-nav__item.is-active {
  color: var(--ods-color-primary);
  font-weight: 600;
}
</style>
