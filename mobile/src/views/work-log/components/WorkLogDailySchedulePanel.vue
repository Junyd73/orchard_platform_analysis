<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { ApiClientError } from '@/api/client'
import {
  convertWorkScheduleToDraft,
  createWorkSchedule,
  deleteWorkSchedule,
  fetchWorkSchedules,
} from '@/api/workSchedules'
import OdsButton from '@/components/ods/OdsButton.vue'
import WorkLogDailyPickSheet from '@/views/work-log/components/WorkLogDailyPickSheet.vue'
import {
  BTN_SCHEDULE_ADD,
  BTN_SCHEDULE_CONVERT,
  BTN_SCHEDULE_OPEN,
  LABEL_SCHEDULE_SECTION,
  MSG_SCHEDULE_CONVERT_FUTURE,
  MSG_SCHEDULE_CONVERT_OK,
  MSG_SCHEDULE_EMPTY,
  MSG_SCHEDULE_LOAD_FAILED,
  MSG_SCHEDULE_MID_REQUIRED,
  MSG_SCHEDULE_SAVE_OK,
} from '@/views/work-log/workLogConstants'
import type { DailyPickOption } from '@/views/work-log/components/WorkLogDailyWorkForm.vue'
import {
  SCHED_STATUS_CONVERTED,
  SCHED_STATUS_PENDING,
  type WorkScheduleItem,
} from '@/types/workSchedule'

const props = defineProps<{
  farmCd: string
  workDt: string
  isFuture: boolean
  workOptions: ReadonlyArray<DailyPickOption>
  siteOptions: ReadonlyArray<DailyPickOption>
}>()

const emit = defineEmits<{
  toast: [message: string]
  converted: [
    payload: {
      workId: string
      workMidCd: string
      workLocId: string
      memo: string
    },
  ]
}>()

const loading = ref(false)
const busy = ref(false)
const items = ref<WorkScheduleItem[]>([])
const sheetOpen = ref(false)
const formOpen = ref(false)
const formTitle = ref('')
const formContents = ref('')
const formMidCd = ref('')
const formLocId = ref('')
const pickKind = ref<'work' | 'site' | null>(null)

const pendingItems = computed(() =>
  items.value.filter((s) => s.sched_status_cd === SCHED_STATUS_PENDING),
)
const convertedItems = computed(() =>
  items.value.filter((s) => s.sched_status_cd === SCHED_STATUS_CONVERTED),
)

const formMidLabel = computed(() => {
  const hit = props.workOptions.find((o) => o.value === formMidCd.value)
  return hit?.label || formMidCd.value || '작업 유형 선택'
})
const formLocLabel = computed(() => {
  const hit = props.siteOptions.find((o) => o.value === formLocId.value)
  return hit?.label || formLocId.value || '필지 선택(선택)'
})

const pickOptions = computed(() =>
  pickKind.value === 'site' ? props.siteOptions : props.workOptions,
)
const pickTitle = computed(() =>
  pickKind.value === 'site' ? '필지 선택' : '작업 유형 선택',
)

async function load() {
  loading.value = true
  try {
    const res = await fetchWorkSchedules(props.farmCd, {
      start_dt: props.workDt,
      end_dt: props.workDt,
    })
    items.value = (res.data || []).filter(
      (s) => s.sched_status_cd !== 'WS010300',
    )
  } catch (err) {
    items.value = []
    const msg =
      err instanceof ApiClientError ? err.message : MSG_SCHEDULE_LOAD_FAILED
    emit('toast', msg)
  } finally {
    loading.value = false
  }
}

function openSheet() {
  sheetOpen.value = true
  void load()
}

function closeSheet() {
  sheetOpen.value = false
  formOpen.value = false
}

function midNm(cd: string): string {
  return props.workOptions.find((o) => o.value === cd)?.label || cd
}

function locNm(id: string | null | undefined): string {
  const v = String(id || '')
  if (!v) return ''
  return props.siteOptions.find((o) => o.value === v)?.label || v
}

async function onConvert(schedId: string) {
  if (props.isFuture) {
    emit('toast', MSG_SCHEDULE_CONVERT_FUTURE)
    return
  }
  busy.value = true
  try {
    const res = await convertWorkScheduleToDraft(props.farmCd, schedId)
    const pre = res.data.prefilled_data
    emit('converted', {
      workId: res.data.work_id,
      workMidCd: pre.work_mid_cd,
      workLocId: String(pre.work_loc_id || ''),
      memo: pre.memo || '',
    })
    emit('toast', MSG_SCHEDULE_CONVERT_OK)
    closeSheet()
    await load()
  } catch (err) {
    const msg =
      err instanceof ApiClientError
        ? err.errorCode === 'FUTURE_DATE_CONVERSION_DISALLOWED'
          ? MSG_SCHEDULE_CONVERT_FUTURE
          : err.message
        : MSG_SCHEDULE_LOAD_FAILED
    emit('toast', msg)
  } finally {
    busy.value = false
  }
}

async function onDelete(schedId: string) {
  busy.value = true
  try {
    await deleteWorkSchedule(props.farmCd, schedId)
    await load()
  } catch (err) {
    const msg =
      err instanceof ApiClientError ? err.message : MSG_SCHEDULE_LOAD_FAILED
    emit('toast', msg)
  } finally {
    busy.value = false
  }
}

async function onCreate() {
  if (!formMidCd.value) {
    emit('toast', MSG_SCHEDULE_MID_REQUIRED)
    return
  }
  busy.value = true
  try {
    await createWorkSchedule(props.farmCd, {
      work_dt: props.workDt,
      work_mid_cd: formMidCd.value,
      work_loc_id: formLocId.value || null,
      title: formTitle.value.trim() || formMidLabel.value,
      contents: formContents.value.trim() || null,
    })
    formTitle.value = ''
    formContents.value = ''
    formMidCd.value = ''
    formLocId.value = ''
    formOpen.value = false
    emit('toast', MSG_SCHEDULE_SAVE_OK)
    await load()
  } catch (err) {
    const msg =
      err instanceof ApiClientError ? err.message : MSG_SCHEDULE_LOAD_FAILED
    emit('toast', msg)
  } finally {
    busy.value = false
  }
}

function onPick(value: string) {
  if (pickKind.value === 'site') formLocId.value = value
  else formMidCd.value = value
  pickKind.value = null
}

watch(
  () => props.workDt,
  () => {
    if (sheetOpen.value) void load()
  },
)

onMounted(() => {
  void load()
})

defineExpose({ openSheet, reload: load })
</script>

<template>
  <section class="sched" :aria-label="LABEL_SCHEDULE_SECTION">
    <header class="sched__head">
      <h2 class="sched__title">{{ LABEL_SCHEDULE_SECTION }}</h2>
      <OdsButton
        variant="secondary"
        type="button"
        :block="false"
        class="sched__open"
        @click="openSheet"
      >
        {{ BTN_SCHEDULE_OPEN }}
      </OdsButton>
    </header>

    <p v-if="loading" class="sched__hint">불러오는 중…</p>
    <ul v-else-if="pendingItems.length" class="sched__mini">
      <li v-for="s in pendingItems.slice(0, 3)" :key="s.sched_id" class="sched__mini-item">
        <span class="sched__dot" aria-hidden="true" />
        <span class="sched__mini-text">
          {{ s.title || midNm(s.work_mid_cd) }}
        </span>
      </li>
      <li v-if="pendingItems.length > 3" class="sched__more">
        +{{ pendingItems.length - 3 }}건 더보기
      </li>
    </ul>
    <p v-else class="sched__hint">{{ MSG_SCHEDULE_EMPTY }}</p>
  </section>

  <Teleport to="body">
    <div v-if="sheetOpen" class="sheet" role="dialog" :aria-label="LABEL_SCHEDULE_SECTION">
      <button type="button" class="sheet__backdrop" aria-label="닫기" @click="closeSheet" />
      <div class="sheet__panel">
        <header class="sheet__head">
          <h3 class="sheet__title">{{ LABEL_SCHEDULE_SECTION }}</h3>
          <button type="button" class="sheet__x" @click="closeSheet">닫기</button>
        </header>

        <div class="sheet__body">
          <div class="sheet__toolbar">
            <OdsButton
              variant="secondary"
              type="button"
              :block="false"
              @click="formOpen = !formOpen"
            >
              {{ BTN_SCHEDULE_ADD }}
            </OdsButton>
          </div>

          <div v-if="formOpen" class="form">
            <button type="button" class="form__pick" @click="pickKind = 'work'">
              {{ formMidLabel }}
            </button>
            <button type="button" class="form__pick" @click="pickKind = 'site'">
              {{ formLocLabel }}
            </button>
            <input
              v-model="formTitle"
              class="form__input"
              type="text"
              maxlength="100"
              placeholder="일정 제목(선택)"
            >
            <textarea
              v-model="formContents"
              class="form__area"
              rows="3"
              maxlength="500"
              placeholder="메모(선택)"
            />
            <OdsButton
              type="button"
              :busy="busy"
              @click="onCreate"
            >
              저장
            </OdsButton>
          </div>

          <p v-if="loading" class="sheet__empty">불러오는 중…</p>
          <template v-else>
            <p v-if="!pendingItems.length && !convertedItems.length" class="sheet__empty">
              {{ MSG_SCHEDULE_EMPTY }}
            </p>
            <ul class="list">
              <li v-for="s in pendingItems" :key="s.sched_id" class="list__item">
                <div class="list__main">
                  <p class="list__title">{{ s.title || midNm(s.work_mid_cd) }}</p>
                  <p class="list__meta">
                    {{ midNm(s.work_mid_cd) }}
                    <template v-if="locNm(s.work_loc_id)"> · {{ locNm(s.work_loc_id) }}</template>
                  </p>
                  <p v-if="s.contents" class="list__body">{{ s.contents }}</p>
                </div>
                <div class="list__actions">
                  <OdsButton
                    v-if="!isFuture"
                    type="button"
                    :block="false"
                    :busy="busy"
                    class="list__btn"
                    @click="onConvert(s.sched_id)"
                  >
                    {{ BTN_SCHEDULE_CONVERT }}
                  </OdsButton>
                  <p v-else class="list__future">실적 전환은 당일·과거만</p>
                  <button
                    type="button"
                    class="list__del"
                    :disabled="busy"
                    @click="onDelete(s.sched_id)"
                  >
                    삭제
                  </button>
                </div>
              </li>
              <li
                v-for="s in convertedItems"
                :key="`c-${s.sched_id}`"
                class="list__item list__item--done"
              >
                <div class="list__main">
                  <p class="list__title">{{ s.title || midNm(s.work_mid_cd) }}</p>
                  <p class="list__meta">
                    실적 전환됨
                    <template v-if="s.converted_work_id"> · {{ s.converted_work_id }}</template>
                  </p>
                </div>
              </li>
            </ul>
          </template>
        </div>
      </div>
    </div>
  </Teleport>

  <WorkLogDailyPickSheet
    :open="pickKind != null"
    :title="pickTitle"
    :options="pickOptions"
    @close="pickKind = null"
    @select="onPick"
  />
</template>

<style scoped>
.sched {
  margin: var(--ods-space-12) var(--ods-space-16) 0;
  padding: var(--ods-space-12) var(--ods-space-14);
  border-radius: var(--ods-radius-button);
  background: color-mix(in srgb, var(--ods-color-ai) 8%, white);
  border: 1px solid color-mix(in srgb, var(--ods-color-ai) 22%, var(--ods-color-gray-100));
}
.sched__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
.sched__title {
  margin: 0;
  font: var(--ods-font-headline);
  color: var(--ods-color-text);
}
.sched__open {
  flex: 0 0 auto;
}
.sched__hint {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
}
.sched__mini {
  margin: var(--ods-space-8) 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.sched__mini-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text);
}
.sched__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--ods-color-ai);
  flex-shrink: 0;
}
.sched__more {
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.sheet {
  position: fixed;
  inset: 0;
  z-index: 85;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}
.sheet__backdrop {
  position: absolute;
  inset: 0;
  margin: 0;
  padding: 0;
  border: none;
  background: color-mix(in srgb, var(--ods-color-gray-900) 40%, transparent);
  cursor: pointer;
}
.sheet__panel {
  position: relative;
  max-height: min(78dvh, 640px);
  display: flex;
  flex-direction: column;
  border-radius: 16px 16px 0 0;
  background: var(--ods-color-white);
  box-shadow: var(--ods-shadow-card);
  padding-bottom: env(safe-area-inset-bottom);
}
.sheet__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--ods-space-12) var(--ods-space-16);
  border-bottom: 1px solid var(--ods-color-border);
}
.sheet__title {
  margin: 0;
  font: var(--ods-font-headline);
}
.sheet__x {
  border: none;
  background: transparent;
  font: var(--ods-font-body-1);
  color: var(--ods-color-primary);
  cursor: pointer;
}
.sheet__body {
  overflow: auto;
  padding: var(--ods-space-12) var(--ods-space-16) var(--ods-space-16);
}
.sheet__toolbar {
  margin-bottom: var(--ods-space-12);
}
.sheet__empty {
  margin: var(--ods-space-16) 0;
  text-align: center;
  color: var(--ods-color-text-secondary);
  font: var(--ods-font-body-2);
}
.form {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
  margin-bottom: var(--ods-space-16);
  padding: var(--ods-space-12);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-gray-50, #f7f7f7);
}
.form__pick,
.form__input,
.form__area {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--ods-color-border);
  border-radius: 10px;
  padding: 10px 12px;
  font: var(--ods-font-body-1);
  background: white;
  color: var(--ods-color-text);
}
.form__pick {
  text-align: left;
  cursor: pointer;
}
.form__area {
  resize: vertical;
  min-height: 72px;
}
.list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-10);
}
.list__item {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
  padding: var(--ods-space-12);
  border-radius: var(--ods-radius-button);
  border: 1px solid color-mix(in srgb, var(--ods-color-ai) 24%, var(--ods-color-gray-100));
  background: color-mix(in srgb, var(--ods-color-ai) 6%, white);
}
.list__item--done {
  opacity: 0.72;
  border-color: var(--ods-color-gray-100);
  background: var(--ods-color-gray-50, #f7f7f7);
}
.list__title {
  margin: 0;
  font: var(--ods-font-body-1);
  font-weight: 600;
}
.list__meta,
.list__body,
.list__future {
  margin: 4px 0 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
}
.list__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--ods-space-8);
}
.list__del {
  border: none;
  background: transparent;
  color: var(--ods-color-danger, #c62828);
  font: var(--ods-font-body-2);
  cursor: pointer;
}
</style>
