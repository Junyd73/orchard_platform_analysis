<script setup lang="ts">
import OdsInput from '@/components/ods/OdsInput.vue'

export type SiteOption = { site_id: string; site_nm: string | null }

const siteId = defineModel<string>('siteId', { default: '' })
const keyword = defineModel<string>('keyword', { default: '' })
const sort = defineModel<'obs_dt_desc' | 'obs_dt_asc'>('sort', {
  default: 'obs_dt_desc',
})

defineProps<{
  sites: SiteOption[]
  searching?: boolean
}>()

const emit = defineEmits<{
  apply: []
}>()

function onSearch() {
  emit('apply')
}
</script>

<template>
  <section class="filters" aria-label="목록 필터">
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
  margin: var(--ods-space-12) 0 var(--ods-space-16);
  padding: var(--ods-space-12);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-card);
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
}
.filters__row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--ods-space-8);
}
.field {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
  min-width: 0;
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
}
.search-btn:disabled {
  background: var(--ods-color-gray-300);
  color: var(--ods-color-gray-500);
}
</style>
