<script setup lang="ts">
import { computed } from 'vue'

import OdsBadge from '@/components/ods/OdsBadge.vue'
import type { ObservationDraftItem } from '@/types/observation'

const props = defineProps<{
  drafts: ObservationDraftItem[]
  busy?: boolean
}>()

const emit = defineEmits<{
  resume: [obsId: string]
  cancel: [obsId: string]
}>()

const titleText = computed(() => `작성 중인 관찰 (${props.drafts.length})`)

/** "2026-07-17 12:56:03" → "12:56" */
function formatModTime(modDt: string | null | undefined): string {
  const raw = String(modDt || '').trim()
  if (!raw) return ''
  const m = raw.match(/(\d{1,2}):(\d{2})(?::\d{2})?/)
  if (m) return `${m[1].padStart(2, '0')}:${m[2]}`
  return raw
}

function siteLabel(d: ObservationDraftItem): string {
  return (d.site_nm || d.location_text || '필지').trim() || '필지'
}
</script>

<template>
  <section v-if="drafts.length" class="drafts" aria-label="작성 중인 관찰">
    <header class="head">
      <h2 class="title">{{ titleText }}</h2>
      <OdsBadge tone="caution">작성중</OdsBadge>
    </header>
    <ul class="list">
      <li v-for="d in drafts" :key="d.obs_id" class="item">
        <div class="meta">
          <p class="date">{{ d.obs_dt }}</p>
          <p class="summary">
            {{ siteLabel(d) }}
            <span class="dot">·</span>
            {{ d.target_type_nm || '대상' }}
          </p>
          <p class="sub">
            사진 {{ d.photo_count }}장
            <template v-if="formatModTime(d.mod_dt)">
              <span class="dot">·</span>
              수정 {{ formatModTime(d.mod_dt) }}
            </template>
          </p>
        </div>
        <div class="actions">
          <button
            type="button"
            class="btn btn--primary"
            :disabled="busy"
            @click="emit('resume', d.obs_id)"
          >
            이어쓰기
          </button>
          <button
            type="button"
            class="btn btn--danger"
            :disabled="busy"
            @click="emit('cancel', d.obs_id)"
          >
            작성 취소
          </button>
        </div>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.drafts {
  margin: 0 0 var(--ods-space-12);
  padding: var(--ods-space-8) var(--ods-space-12);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-card);
  box-shadow: var(--ods-shadow-card);
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  margin: 0 0 var(--ods-space-8);
}
.title {
  margin: 0;
  font: var(--ods-font-form-label);
  color: var(--ods-color-text);
}
.list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
}
.item {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
  padding: var(--ods-space-8);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-bg-muted);
  min-width: 0;
}
.meta {
  min-width: 0;
}
.date {
  margin: 0;
  font: var(--ods-font-card-emphasis);
  color: var(--ods-color-text);
}
.summary {
  margin: var(--ods-space-4) 0 0;
  font: var(--ods-font-card-body);
  font-weight: 600;
  color: var(--ods-color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dot {
  margin: 0 var(--ods-space-4);
  color: var(--ods-color-text-secondary);
  font-weight: 400;
}
.sub {
  margin: var(--ods-space-4) 0 0;
  font: var(--ods-font-card-help);
  color: var(--ods-color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.actions {
  display: flex;
  flex-wrap: nowrap;
  gap: var(--ods-space-4);
}
.btn {
  flex: 1;
  min-height: var(--ods-button-height-in-card);
  border-radius: var(--ods-radius-button);
  font: var(--ods-font-card-section);
  cursor: pointer;
  border: 1px solid var(--ods-color-border);
  background: var(--ods-color-white);
}
.btn--primary {
  background: var(--ods-color-primary);
  border-color: var(--ods-color-primary);
  color: var(--ods-color-white);
}
.btn--danger {
  color: var(--ods-color-danger);
  border-color: color-mix(in srgb, var(--ods-color-danger) 40%, white);
}
.btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
</style>
