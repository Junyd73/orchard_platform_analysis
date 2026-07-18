<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  farmName?: string
  /** 월간: 연월 라벨 / 일간: 작업일 YYYY-MM-DD */
  contextLabel?: string
  mode?: 'monthly' | 'daily'
}>()

const todayLabel = computed(() => {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const week = ['일', '월', '화', '수', '목', '금', '토'][d.getDay()]
  return `${y}. ${m}. ${day} (${week})`
})

const greeting = computed(() => {
  const name = (props.farmName || '').trim()
  if (props.mode === 'daily') {
    return name ? `${name} · 당일 작업·이슈 기록` : '당일 작업·이슈를 기록하세요'
  }
  return name ? `${name}의 한 달 영농 현황` : '한 달의 작업과 이슈를 한눈에'
})

const stripLabel = computed(() =>
  props.mode === 'daily' ? '작업일' : '조회 월',
)
</script>

<template>
  <header class="hero">
    <p class="hero__date">{{ todayLabel }}</p>
    <h1 class="hero__title">영농일지</h1>
    <p class="hero__msg">{{ greeting }}</p>
    <div class="hero__strip" role="status">
      <span class="hero__strip-label">{{ stripLabel }}</span>
      <span class="hero__strip-value">
        <slot name="strip">{{ contextLabel || '—' }}</slot>
      </span>
    </div>
  </header>
</template>

<style scoped>
.hero {
  padding: var(--ods-space-8) 0 var(--ods-space-16);
}
.hero__date {
  margin: 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.hero__title {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-title-1);
  color: var(--ods-color-text);
}
.hero__msg {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-body-1);
  color: var(--ods-color-text-secondary);
}
.hero__strip {
  margin-top: var(--ods-space-16);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  min-height: var(--ods-control-height);
  padding: 0 var(--ods-space-16);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  box-shadow: var(--ods-shadow-card);
}
.hero__strip-label {
  flex-shrink: 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
}
.hero__strip-value {
  min-width: 0;
  font: var(--ods-font-body-1);
  font-weight: 700;
  color: var(--ods-color-text);
  text-align: right;
}
</style>
