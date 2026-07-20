<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { fetchNotificationSummary } from '@/api/notifications'
import iconBack from '@/assets/ods/common/icon-back.svg'
import iconBell from '@/assets/ods/common/icon-bell.svg'
import iconChevronDown from '@/assets/ods/common/icon-chevron-down.svg'
import iconFarm from '@/assets/ods/common/icon-farm.svg'
import iconSettings from '@/assets/ods/common/icon-settings.svg'
import { useAppStore } from '@/composables/stores/app'

/** 이 스크롤 거리에서 Glass → Surface 전환 완료 */
const SCROLL_RANGE_PX = 64

withDefaults(
  defineProps<{
    /** Wizard/Camera/Viewer/Modal 예외용 Back */
    showBack?: boolean
  }>(),
  { showBack: false },
)

const emit = defineEmits<{
  back: []
  notification: []
  settings: []
}>()

const router = useRouter()
const store = useAppStore()
const { farm, farmCd } = storeToRefs(store)
const toast = ref('')
const unreadCount = ref(0)
/** 0(Glass) ~ 1(Surface) */
const progress = ref(0)

let ticking = false

const farmName = () => farm.value?.farm_nm || farmCd.value

const barStyle = computed(() => ({
  '--ods-appbar-p': String(progress.value),
}))

const unreadBadge = computed(() => {
  const n = unreadCount.value
  if (n <= 0) return ''
  return n > 99 ? '99+' : String(n)
})

function readScrollY(): number {
  return window.scrollY || document.documentElement.scrollTop || 0
}

function updateProgress() {
  const next = Math.min(1, Math.max(0, readScrollY() / SCROLL_RANGE_PX))
  // 미세 떨림·깜빡임 방지
  if (Math.abs(next - progress.value) < 0.004) return
  progress.value = next
}

function onScroll() {
  if (ticking) return
  ticking = true
  requestAnimationFrame(() => {
    updateProgress()
    ticking = false
  })
}

function showSoon(label: string) {
  toast.value = `${label} 준비 중`
  window.setTimeout(() => {
    toast.value = ''
  }, 1600)
}

async function refreshUnread() {
  const farm = farmCd.value
  if (!farm) return
  try {
    const s = await fetchNotificationSummary(farm)
    unreadCount.value = Number(s.unread_count || 0)
  } catch {
    /* 배지 실패는 무시 */
  }
}

function onNotification() {
  emit('notification')
  void router.push({ name: 'notifications' })
}

function onSettings() {
  emit('settings')
  showSoon('환경설정')
}

onMounted(() => {
  updateProgress()
  window.addEventListener('scroll', onScroll, { passive: true })
  void refreshUnread()
})

onUnmounted(() => {
  window.removeEventListener('scroll', onScroll)
})
</script>

<template>
  <header
    class="ods-appbar"
    :class="{ 'is-solid': progress > 0.55 }"
    :style="barStyle"
    aria-label="앱 상단바"
  >
    <div class="ods-appbar__inner">
      <div class="ods-appbar__left">
        <button
          v-if="showBack"
          type="button"
          class="ods-appbar__icon-btn"
          aria-label="뒤로"
          @click="emit('back')"
        >
          <img :src="iconBack" alt="" aria-hidden="true">
        </button>
        <button type="button" class="ods-appbar__farm" aria-label="농장 선택">
          <img class="ods-appbar__farm-mark" :src="iconFarm" alt="" aria-hidden="true">
          <span class="ods-appbar__farm-name">{{ farmName() }}</span>
          <img class="ods-appbar__farm-chev" :src="iconChevronDown" alt="" aria-hidden="true">
        </button>
      </div>
      <div class="ods-appbar__right">
        <button
          type="button"
          class="ods-appbar__icon-btn"
          aria-label="알림"
          @click="onNotification"
        >
          <img :src="iconBell" alt="" aria-hidden="true">
          <span v-if="unreadBadge" class="ods-appbar__badge">{{ unreadBadge }}</span>
        </button>
        <button
          type="button"
          class="ods-appbar__icon-btn"
          aria-label="환경설정"
          @click="onSettings"
        >
          <img :src="iconSettings" alt="" aria-hidden="true">
        </button>
      </div>
    </div>
  </header>
  <p v-if="toast" class="ods-appbar__toast" role="status">{{ toast }}</p>
</template>

<style scoped>
.ods-appbar {
  --ods-appbar-p: 0;
  /* Sticky: 스크롤 시 상단 고정, Hero는 아래로 자연스럽게 통과 */
  position: sticky;
  top: 0;
  z-index: 50;
  /* 부모 page padding을 상쇄해 Surface가 가로 full-bleed
     (부모는 .ods-page-content — --ods-page-padding-x SSOT) */
  margin-inline: calc(-1 * var(--ods-page-padding-x));
  /* 스크롤 전: page gap을 상쇄해 AppBar↔다음(Hero) = --ods-appbar-content-gap
     (= --ods-appbar-pad-y, 상단 패딩과 동일) */
  margin-bottom: calc(
    (var(--ods-page-content-gap) - var(--ods-appbar-content-gap)) * -1 *
      (1 - var(--ods-appbar-p))
  );
  padding-top: env(safe-area-inset-top, 0px);
  /* Glass 투명도 고정 (스크롤 전·후 동일). Elevation·Border만 progress로 보강 */
  background: rgba(255, 255, 255, 0.22);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  box-shadow: 0
    calc(var(--ods-appbar-p) * 1px)
    calc(var(--ods-appbar-p) * 8px)
    rgba(33, 33, 33, calc(var(--ods-appbar-p) * 0.08));
  border-bottom: 1px solid
    rgba(224, 224, 224, calc(var(--ods-appbar-p) * 0.55));
  /* 스크롤 rAF로 progress가 이미 보간되므로 짧은 transition만 보조 */
  transition:
    box-shadow 80ms linear,
    border-color 80ms linear,
    margin-bottom 80ms linear;
  will-change: box-shadow;
}

.ods-appbar.is-solid {
  /* 투명도는 유지. Navigation 인식은 elevation·border로만 보강 */
  background: rgba(255, 255, 255, 0.22);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.ods-appbar__inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-12);
  min-height: 48px;
  /* 아이콘(22px)이 카드 좌·우 여백(--ods-page-padding-x)과 시각 정렬되도록
     터치영역(44px) 보정: (44-22)/2 = 11px 바깥으로 당김 */
  padding: var(--ods-appbar-pad-y)
    calc(var(--ods-page-padding-x) - ((var(--ods-touch-min) - 22px) / 2));
}

.ods-appbar__left {
  display: flex;
  align-items: center;
  gap: var(--ods-space-4);
  min-width: 0;
  flex: 1 1 auto;
}

/* Back 없을 때 Farm Mark도 동일 좌측 정렬 */
.ods-appbar__left > .ods-appbar__farm:first-child {
  margin-left: calc((var(--ods-touch-min) - 22px) / 2);
}

.ods-appbar__right {
  display: flex;
  align-items: center;
  /* 아이콘 간격: 좁지 않게 */
  gap: var(--ods-space-8);
  flex: 0 0 auto;
}

.ods-appbar__farm {
  display: inline-flex;
  align-items: center;
  gap: var(--ods-space-8);
  min-width: 0;
  max-width: 100%;
  border: none;
  background: transparent;
  padding: 0;
  min-height: var(--ods-touch-min);
  cursor: pointer;
  color: var(--ods-color-text);
}

.ods-appbar__farm-mark {
  width: 22px;
  height: 22px;
  flex: 0 0 auto;
}

.ods-appbar__farm-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 17px;
  line-height: 1.3;
  /* 크기보다 Weight로 강조 */
  font-weight: 800;
  letter-spacing: -0.01em;
  color: var(--ods-color-text);
}

.ods-appbar__farm-chev {
  width: 16px;
  height: 16px;
  flex: 0 0 auto;
  opacity: 0.72;
}

.ods-appbar__icon-btn {
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
  color: var(--ods-color-text-secondary);
  flex: 0 0 auto;
}

.ods-appbar__icon-btn img {
  width: 22px;
  height: 22px;
  display: block;
}

.ods-appbar__badge {
  position: absolute;
  top: 6px;
  right: 4px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 999px;
  background: var(--ods-color-danger);
  color: var(--ods-color-white);
  font-size: 10px;
  font-weight: 700;
  line-height: 16px;
  text-align: center;
}

.ods-appbar__toast {
  position: fixed;
  left: 50%;
  top: calc(12px + env(safe-area-inset-top, 0px));
  transform: translateX(-50%);
  z-index: 60;
  margin: 0;
  padding: var(--ods-space-8) var(--ods-space-16);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-gray-900);
  color: var(--ods-color-white);
  font: var(--ods-font-caption);
}

@media (prefers-reduced-motion: reduce) {
  .ods-appbar {
    transition: none;
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
  }
}
</style>
