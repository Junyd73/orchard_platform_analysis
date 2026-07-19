<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import {
  DAILY_SHELL_OBSERVATIONS,
  MSG_OBS_EMPTY,
  type DailyShellObsItem,
} from '@/views/work-log/workLogConstants'

const props = defineProps<{
  workDt: string
  /** Shell: 작업이 있을 때만 관찰 예시 표시 */
  showExamples?: boolean
}>()

const router = useRouter()

const items = computed(() =>
  props.showExamples ? DAILY_SHELL_OBSERVATIONS : ([] as readonly DailyShellObsItem[]),
)

const selectedId = ref<string>('')

watch(
  items,
  (list) => {
    selectedId.value = list[0]?.id || ''
  },
  { immediate: true },
)

const selected = computed(
  (): DailyShellObsItem | null =>
    items.value.find((it) => it.id === selectedId.value) || items.value[0] || null,
)

const photos = computed(() => selected.value?.photos || [])

function onSelect(obsId: string) {
  selectedId.value = obsId
}

function openDetail() {
  if (!selectedId.value) return
  void router.push({
    name: 'observation-detail',
    params: { obsId: selectedId.value },
    query: { work_dt: props.workDt },
  })
}
</script>

<template>
  <section class="obs-card" aria-label="생육관찰">
    <div class="obs-card__head">
      <h2 class="obs-card__title">생육관찰</h2>
      <button
        v-if="selected"
        type="button"
        class="obs-card__link"
        @click="openDetail"
      >
        자세히보기 ›
      </button>
    </div>

    <p v-if="items.length === 0" class="obs-card__empty">{{ MSG_OBS_EMPTY }}</p>

    <template v-else>
      <ul class="obs-list" aria-label="관찰 목록">
        <li v-for="it in items" :key="it.id">
          <button
            type="button"
            class="obs-list__item"
            :class="{ 'obs-list__item--on': selectedId === it.id }"
            @click="onSelect(it.id)"
          >
            <span class="obs-list__title">{{ it.title }}</span>
            <span class="obs-list__meta">{{ it.meta }}</span>
          </button>
        </li>
      </ul>

      <div class="photos" aria-label="선택 관찰 사진">
        <div
          v-for="(ph, idx) in photos"
          :key="ph.id"
          class="photos__slot"
          :class="`photos__slot--${ph.tone}`"
        >
          <span class="photos__label">{{ ph.label }}</span>
          <span v-if="idx === 0" class="photos__badge">대표</span>
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.obs-card {
  padding: var(--ods-space-16);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  box-shadow: var(--ods-shadow-card);
}

.obs-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  margin-bottom: var(--ods-space-12);
}

.obs-card__title {
  margin: 0;
  font: var(--ods-font-headline);
  color: var(--ods-color-text);
}

.obs-card__link {
  margin: 0;
  padding: 0;
  border: none;
  background: transparent;
  font: var(--ods-font-caption);
  font-weight: 700;
  color: var(--ods-color-primary);
  cursor: pointer;
  min-height: 28px;
}

.obs-card__empty {
  margin: 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
  text-align: center;
  padding: var(--ods-space-8) 0;
}

.obs-list {
  list-style: none;
  margin: 0 0 var(--ods-space-12);
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
}

.obs-list__item {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  margin: 0;
  padding: var(--ods-space-8) var(--ods-space-12);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-bg-muted);
  text-align: left;
  cursor: pointer;
}

.obs-list__item--on {
  border-color: var(--ods-color-primary);
  background: color-mix(in srgb, var(--ods-color-primary) 8%, var(--ods-color-white));
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--ods-color-primary) 25%, transparent);
}

.obs-list__title {
  font: var(--ods-font-body-2);
  font-weight: 700;
  color: var(--ods-color-text);
}

.obs-list__meta {
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}

.photos {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--ods-space-8);
}

.photos__slot {
  position: relative;
  aspect-ratio: 1;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--ods-color-border);
  display: grid;
  place-items: center;
}

.photos__slot--green {
  background: linear-gradient(145deg, #d8efe0, #a8d4b8);
}

.photos__slot--amber {
  background: linear-gradient(145deg, #f5e6c8, #e0c48a);
}

.photos__slot--sky {
  background: linear-gradient(145deg, #d6e8f5, #9ec0dc);
}

.photos__slot--rose {
  background: linear-gradient(145deg, #f0d6d8, #d9a8ae);
}

.photos__label {
  font: var(--ods-font-caption);
  font-weight: 700;
  color: color-mix(in srgb, var(--ods-color-text) 70%, transparent);
}

.photos__badge {
  position: absolute;
  top: 4px;
  left: 4px;
  padding: 1px 6px;
  border-radius: var(--ods-radius-badge);
  background: var(--ods-color-primary);
  color: var(--ods-color-white);
  font: var(--ods-font-caption);
  font-size: 9px;
  font-weight: 700;
}
</style>
