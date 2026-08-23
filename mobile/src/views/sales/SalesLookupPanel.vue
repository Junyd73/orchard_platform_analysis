<script setup lang="ts">
import { computed } from 'vue'

import OdsButton from '@/components/ods/OdsButton.vue'
import OdsCard from '@/components/ods/OdsCard.vue'
import OdsInput from '@/components/ods/OdsInput.vue'
import OdsSelect from '@/components/ods/OdsSelect.vue'
import {
  LABEL_DATE_FROM,
  LABEL_DATE_TO,
  LABEL_DETAIL_LOOKUP,
  LABEL_LOOKUP,
  LABEL_QUICK_RANGE,
  LABEL_RESET,
  LABEL_SEARCH,
} from '@/views/orders/ordersConstants'
import {
  ORDER_QUICK_SEGMENT_OPTIONS,
  quickKeyForRange,
} from '@/views/orders/orderLookup'
import {
  LABEL_PAYMENT_STATUS,
  LABEL_SALES_SEARCH_PLACEHOLDER,
  LABEL_SALES_STATUS,
  PAYMENT_STATUS_FILTER_OPTIONS,
  SALES_STATUS_FILTER_OPTIONS,
} from '@/views/sales/salesConstants'

const expanded = defineModel<boolean>('expanded', { default: false })
const fromDate = defineModel<string>('fromDate', { default: '' })
const toDate = defineModel<string>('toDate', { default: '' })
const salesStatus = defineModel<string>('salesStatus', { default: '' })
const paymentStatus = defineModel<string>('paymentStatus', { default: '' })
const keyword = defineModel<string>('keyword', { default: '' })

defineProps<{
  appliedFrom: string
  appliedTo: string
  searching?: boolean
}>()

const emit = defineEmits<{
  apply: []
  reset: []
  'quick-range': [key: string]
}>()

const quickKey = computed(() => quickKeyForRange(fromDate.value, toDate.value))

function toggleExpanded() {
  expanded.value = !expanded.value
}

function onQuick(key: string) {
  emit('quick-range', key)
}
</script>

<template>
  <OdsCard class="lookup" aria-label="판매 조회조건">
    <div class="lookup-summary">
      <span class="lookup-summary__period">{{ appliedFrom }} ~ {{ appliedTo }}</span>
      <button
        type="button"
        class="lookup-detail"
        :aria-expanded="expanded"
        aria-controls="sales-lookup-body"
        @click="toggleExpanded"
      >
        {{ LABEL_DETAIL_LOOKUP }}
        <span aria-hidden="true">{{ expanded ? '˄' : '˅' }}</span>
      </button>
    </div>

    <div v-show="expanded" id="sales-lookup-body" class="lookup-body">
      <div class="lookup-row">
        <div class="dates">
          <div class="date-iso">
            <span class="date-iso__value">{{ fromDate }}</span>
            <input
              v-model="fromDate"
              class="date-iso__native"
              type="date"
              :aria-label="LABEL_DATE_FROM"
              :disabled="searching"
            >
          </div>
          <span class="dates__tilde">~</span>
          <div class="date-iso">
            <span class="date-iso__value">{{ toDate }}</span>
            <input
              v-model="toDate"
              class="date-iso__native"
              type="date"
              :aria-label="LABEL_DATE_TO"
              :disabled="searching"
            >
          </div>
        </div>

        <div class="quick" role="group" :aria-label="LABEL_QUICK_RANGE">
          <button
            v-for="opt in ORDER_QUICK_SEGMENT_OPTIONS"
            :key="opt.value"
            type="button"
            class="quick__chip"
            :class="{ 'quick__chip--active': quickKey === opt.value }"
            :disabled="searching"
            @click="onQuick(opt.value)"
          >
            {{ opt.label }}
          </button>
        </div>
      </div>

      <div class="lookup-row lookup-row--filters">
        <OdsSelect
          v-model="salesStatus"
          variant="form"
          :aria-label="LABEL_SALES_STATUS"
          :disabled="searching"
        >
          <option
            v-for="opt in SALES_STATUS_FILTER_OPTIONS"
            :key="`sales-${opt.value || 'all'}`"
            :value="opt.value"
          >
            {{ opt.label }}
          </option>
        </OdsSelect>
        <OdsSelect
          v-model="paymentStatus"
          variant="form"
          :aria-label="LABEL_PAYMENT_STATUS"
          :disabled="searching"
        >
          <option
            v-for="opt in PAYMENT_STATUS_FILTER_OPTIONS"
            :key="`pay-${opt.value || 'all'}`"
            :value="opt.value"
          >
            {{ opt.label }}
          </option>
        </OdsSelect>
      </div>

      <div class="lookup-row lookup-row--search">
        <OdsInput
          v-model="keyword"
          variant="form"
          bare
          :aria-label="LABEL_SEARCH"
          :placeholder="LABEL_SALES_SEARCH_PLACEHOLDER"
          :disabled="searching"
          @keydown.enter.prevent="emit('apply')"
        />
      </div>

      <div class="lookup-actions">
        <OdsButton
          variant="secondary"
          :disabled="searching"
          @click="emit('reset')"
        >
          {{ LABEL_RESET }}
        </OdsButton>
        <OdsButton
          variant="primary"
          :disabled="searching"
          :busy="searching"
          @click="emit('apply')"
        >
          {{ LABEL_LOOKUP }}
        </OdsButton>
      </div>
    </div>
  </OdsCard>
</template>

<style scoped>
.lookup {
  padding: var(--ods-space-4) var(--ods-space-12);
  background: var(--ods-color-bg-muted);
  box-shadow: none;
}
.lookup-summary {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--ods-space-8);
  align-items: center;
  min-height: var(--ods-control-height);
}
.lookup-summary__period {
  font: var(--ods-font-form-value);
  font-weight: 600;
  color: var(--ods-color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.lookup-body {
  margin-top: var(--ods-space-8);
  padding-top: var(--ods-space-8);
  border-top: 1px solid var(--ods-color-border);
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
}
.lookup-row {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
  gap: var(--ods-space-8);
  align-items: center;
}
.lookup-row--filters {
  grid-template-columns: 1fr 1fr;
}
.lookup-row--search {
  grid-template-columns: 1fr;
}
.dates {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: var(--ods-space-4);
  min-width: 0;
}
.dates__tilde {
  color: var(--ods-color-text-secondary);
  font: var(--ods-font-card-help);
}
.date-iso {
  position: relative;
  height: var(--ods-control-height);
  min-height: var(--ods-control-height);
  box-sizing: border-box;
  display: flex;
  align-items: center;
  padding: 0 var(--ods-space-8);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-white);
  min-width: 0;
}
.date-iso__value {
  font: var(--ods-font-form-value);
  color: var(--ods-color-text);
  pointer-events: none;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.date-iso__native {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  margin: 0;
  padding: 0;
  border: 0;
  opacity: 0;
  cursor: pointer;
}
.quick {
  display: flex;
  gap: var(--ods-space-4);
  min-width: 0;
}
.quick__chip {
  flex: 1 1 0;
  min-width: 0;
  min-height: var(--ods-control-height);
  margin: 0;
  padding: 0 var(--ods-space-4);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-badge);
  background: var(--ods-color-white);
  font: var(--ods-font-card-emphasis);
  color: var(--ods-color-text-secondary);
  cursor: pointer;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.quick__chip--active {
  background: var(--ods-color-bg-muted);
  border-color: var(--ods-color-text-secondary);
  color: var(--ods-color-text);
  font-weight: 700;
}
.quick__chip:disabled {
  opacity: 0.5;
  cursor: default;
}
.lookup-row :deep(.ods-input),
.lookup-row :deep(.ods-select) {
  width: 100%;
  height: var(--ods-control-height);
  min-height: var(--ods-control-height);
}
.lookup-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--ods-space-8);
  align-items: center;
}
.lookup-actions :deep(.ods-btn) {
  min-height: var(--ods-button-height-in-card);
}
.lookup-detail {
  margin: 0;
  padding: 0;
  border: none;
  background: transparent;
  font: var(--ods-font-card-emphasis);
  color: var(--ods-color-text-secondary);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: var(--ods-space-4);
  white-space: nowrap;
  -webkit-tap-highlight-color: transparent;
}
.lookup-detail:active {
  opacity: 0.7;
}
@media (max-width: 340px) {
  .lookup-row,
  .lookup-row--filters {
    grid-template-columns: 1fr;
  }
}
</style>
