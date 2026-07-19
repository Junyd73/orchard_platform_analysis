<script setup lang="ts">
import OdsInput from '@/components/ods/OdsInput.vue'

export type SiteOption = { site_id: string; site_nm: string | null }

const siteId = defineModel<string>('siteId', { default: '' })
const keyword = defineModel<string>('keyword', { default: '' })
const sort = defineModel<'obs_dt_desc' | 'obs_dt_asc'>('sort', {
  default: 'obs_dt_desc',
})
const dateFrom = defineModel<string>('dateFrom', { default: '' })
const dateTo = defineModel<string>('dateTo', { default: '' })

defineProps<{
  sites: SiteOption[]
  searching?: boolean
}>()

const emit = defineEmits<{
  apply: []
  'quick-range': [days: number]
}>()

function onSearch() {
  emit('apply')
}

function onQuick(days: number) {
  emit('quick-range', days)
}
</script>

<template>
  <section class="filters" aria-label="관찰 조회 필터">
    <div class="filters__row">
      <label class="field field--half">
        <span class="field__label">필지</span>
        <select
          v-model="siteId"
          class="select"
          :disabled="searching"
          @change="onSearch"
        >
          <option value="">전체 필지</option>
          <option v-for="s in sites" :key="s.site_id" :value="s.site_id">
            {{ s.site_nm || s.site_id }}
          </option>
        </select>
      </label>
      <label class="field field--half">
        <span class="field__label">정렬</span>
        <select
          v-model="sort"
          class="select"
          :disabled="searching"
          @change="onSearch"
        >
          <option value="obs_dt_desc">최신순</option>
          <option value="obs_dt_asc">오래된순</option>
        </select>
      </label>
    </div>

    <div class="filters__dates">
      <label class="field field--grow">
        <span class="field__label">기간</span>
        <div class="dates">
          <input
            v-model="dateFrom"
            class="select select--date"
            type="date"
            :disabled="searching"
            @change="onSearch"
          >
          <span class="dates__tilde">~</span>
          <input
            v-model="dateTo"
            class="select select--date"
            type="date"
            :disabled="searching"
            @change="onSearch"
          >
        </div>
      </label>
    </div>

    <div class="quick" role="group" aria-label="빠른 기간">
      <button
        type="button"
        class="quick__btn"
        :disabled="searching"
        @click="onQuick(3)"
      >
        최근 3일
      </button>
      <button
        type="button"
        class="quick__btn"
        :disabled="searching"
        @click="onQuick(7)"
      >
        최근 1주
      </button>
    </div>

    <div class="search-row">
      <OdsInput
        v-model="keyword"
        class="search-row__input"
        label="검색"
        placeholder="제목·내용·나무번호·표본·구역"
        :disabled="searching"
        @keydown.enter.prevent="onSearch"
      />
      <button
        type="button"
        class="search-btn"
        :disabled="searching"
        @click="onSearch"
      >
        {{ searching ? '검색 중' : '검색' }}
      </button>
    </div>
  </section>
</template>

<style scoped>
.filters {
  margin: 0;
  padding: var(--ods-space-12);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-card);
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
  box-shadow: var(--ods-shadow-card);
}
.filters__row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--ods-space-8);
}
.filters__dates {
  display: flex;
}
.field {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
  min-width: 0;
}
.field--grow {
  flex: 1;
}
.field__label {
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.select {
  height: 44px;
  padding: 0 var(--ods-space-12);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  font: var(--ods-font-body-2);
  background: var(--ods-color-white);
  color: var(--ods-color-text);
}
.select--date {
  flex: 1;
  min-width: 0;
  padding: 0 var(--ods-space-8);
}
.dates {
  display: flex;
  align-items: center;
  gap: var(--ods-space-4);
}
.dates__tilde {
  flex-shrink: 0;
  color: var(--ods-color-text-secondary);
  font: var(--ods-font-caption);
}
.quick {
  display: flex;
  gap: var(--ods-space-8);
}
.quick__btn {
  margin: 0;
  padding: 6px 12px;
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-badge);
  background: var(--ods-color-bg-muted);
  font: var(--ods-font-caption);
  font-weight: 700;
  color: var(--ods-color-text);
  cursor: pointer;
}
.quick__btn:disabled {
  opacity: 0.5;
  cursor: default;
}
.search-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: var(--ods-space-8);
  align-items: end;
}
.search-row__input {
  min-width: 0;
}
.search-row :deep(.ods-input) {
  height: 44px;
}
.search-btn {
  height: 44px;
  min-width: 72px;
  padding: 0 var(--ods-space-16);
  border: none;
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-primary);
  color: var(--ods-color-white);
  font: var(--ods-font-body-1);
  font-weight: 600;
  cursor: pointer;
}
.search-btn:disabled {
  background: var(--ods-color-gray-300);
  color: var(--ods-color-gray-500);
}
</style>
