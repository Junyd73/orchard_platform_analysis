<script setup lang="ts">
import OdsBadge from '@/components/ods/OdsBadge.vue'
import {
  formatQtyPiece,
  formatThreshold,
  LABEL_LOW,
} from '@/views/pesticide/pesticideConstants'
import type { PesticideStockItem } from '@/types/pesticide'

defineProps<{
  item: PesticideStockItem
}>()
</script>

<template>
  <article class="card" :class="{ 'card--low': item.is_low }">
    <div class="card__head">
      <h3 class="card__title">{{ item.item_nm }}</h3>
      <OdsBadge v-if="item.is_low" tone="danger">{{ LABEL_LOW }}</OdsBadge>
    </div>
    <p class="card__meta">
      {{ formatQtyPiece(item.qty_piece) }}
      <template v-if="item.spec_nm"> · {{ item.spec_nm }}</template>
    </p>
    <p v-if="item.is_low" class="card__warn">
      {{ formatThreshold(item.warn_threshold, item.warn_source) }}
    </p>
    <p v-else-if="item.info_pesticide_nm" class="card__info">
      {{ item.info_pesticide_nm }}
    </p>
  </article>
</template>

<style scoped>
.card {
  padding: var(--ods-space-16) var(--ods-space-16);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  box-shadow: var(--ods-shadow-card);
}
.card--low {
  border: 1px solid color-mix(in srgb, var(--ods-color-danger) 35%, transparent);
}
.card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
.card__title {
  margin: 0;
  font: var(--ods-font-form-value);
  font-weight: 700;
  color: var(--ods-color-text);
}
.card__meta {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
}
.card__warn {
  margin: var(--ods-space-4) 0 0;
  font: var(--ods-font-card-help);
  color: var(--ods-color-danger);
}
.card__info {
  margin: var(--ods-space-4) 0 0;
  font: var(--ods-font-card-help);
  color: var(--ods-color-text-secondary);
}
</style>
