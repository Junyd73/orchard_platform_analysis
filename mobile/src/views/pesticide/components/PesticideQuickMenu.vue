<script setup lang="ts">
import iconDict from '@/assets/ods/pesticide/icon-menu-dict.svg'
import iconLow from '@/assets/ods/pesticide/icon-menu-low.svg'
import iconPest from '@/assets/ods/common/icon-kpi-pest.svg'
import iconReceipt from '@/assets/ods/pesticide/icon-menu-receipt.svg'
import iconStats from '@/assets/ods/pesticide/icon-menu-stats.svg'
import iconStock from '@/assets/ods/pesticide/icon-menu-stock.svg'
import {
  PESTICIDE_QUICK_ACTIONS,
  type PesticideQuickActionKey,
} from '@/views/pesticide/pesticideConstants'

const emit = defineEmits<{
  select: [key: PesticideQuickActionKey]
}>()

const ICONS: Record<PesticideQuickActionKey, string> = {
  stock: iconStock,
  stats: iconStats,
  dict: iconDict,
  'pest-dict': iconPest,
  receipt: iconReceipt,
  low: iconLow,
}
</script>

<template>
  <div class="quick-wrap">
    <nav class="quick" aria-label="농약 빠른 메뉴">
      <button
        v-for="a in PESTICIDE_QUICK_ACTIONS"
        :key="a.key"
        type="button"
        class="quick__item"
        :class="{ 'quick__item--soon': !a.ready }"
        @click="emit('select', a.key)"
      >
        <span class="quick__ico-wrap" aria-hidden="true">
          <img class="quick__ico" :src="ICONS[a.key]" alt="" />
        </span>
        <span class="quick__label">{{ a.label }}</span>
      </button>
    </nav>
  </div>
</template>

<style scoped>
.quick-wrap {
  width: 100%;
  flex: 0 0 auto;
}
.quick {
  display: flex;
  flex-direction: row;
  flex-wrap: nowrap;
  align-items: flex-start;
  justify-content: space-between;
  width: 100%;
  gap: var(--ods-space-4);
  margin: 0;
  padding: var(--ods-space-4) 0;
  box-sizing: border-box;
}
.quick__item {
  display: flex;
  flex: 1 1 0;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  gap: var(--ods-space-8);
  width: 0;
  min-width: 0;
  max-width: none;
  min-height: var(--ods-thumb-md);
  margin: 0;
  padding: var(--ods-space-8) var(--ods-space-4) var(--ods-space-4);
  border: 0;
  border-radius: var(--ods-radius-button);
  background: transparent;
  cursor: pointer;
  color: var(--ods-color-text);
  appearance: none;
  -webkit-appearance: none;
}
.quick__item:active .quick__ico-wrap {
  background: color-mix(in srgb, var(--ods-color-primary) 14%, var(--ods-color-white));
}
.quick__item--soon {
  opacity: 0.72;
}
.quick__ico-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: var(--ods-button-height-in-card);
  height: var(--ods-button-height-in-card);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  box-shadow: var(--ods-shadow-card);
}
.quick__ico {
  width: var(--ods-icon-xl);
  height: var(--ods-icon-xl);
  filter: invert(34%) sepia(28%) saturate(900%) hue-rotate(78deg) brightness(90%)
    contrast(88%);
}
.quick__label {
  display: block;
  width: 100%;
  font: var(--ods-font-card-help);
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: -0.06em;
  text-align: center;
  color: var(--ods-color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
