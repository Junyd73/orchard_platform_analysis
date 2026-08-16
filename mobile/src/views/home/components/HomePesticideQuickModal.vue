<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'

import { ApiClientError } from '@/api/client'
import { fetchCommonCodes } from '@/api/commonCodes'
import { fetchFarmSites } from '@/api/farms'
import {
  fetchGoogleCalendarStatus,
  pushWorkToGoogle,
  type GoogleCalendarStatus,
} from '@/api/googleCalendar'
import {
  fetchWorkLogDaily,
  fetchWorkLogPartners,
  saveWorkLogIntegrated,
  saveWorkLogWorks,
  type WorkLogPartnerOption,
} from '@/api/workLogs'
import { rememberRecentPurpose } from '@/views/pesticide/pesticideConstants'
import OdsButton from '@/components/ods/OdsButton.vue'
import WorkLogDailyPesticidePanel from '@/views/work-log/components/WorkLogDailyPesticidePanel.vue'
import WorkLogDailyPickSheet from '@/views/work-log/components/WorkLogDailyPickSheet.vue'
import {
  BTN_PEST_QUICK_CANCEL,
  BTN_PEST_QUICK_SAVE,
  LABEL_PEST_QUICK_DATE,
  LABEL_PEST_QUICK_GOOGLE,
  LABEL_PEST_QUICK_MEMO,
  LABEL_PEST_QUICK_SITE,
  LABEL_PEST_QUICK_STATUS,
  LABEL_PEST_QUICK_TIME,
  LABEL_PEST_QUICK_TITLE,
  LABEL_PEST_QUICK_WORK_GROUP,
  LABEL_PEST_QUICK_WORK_GROUP_FIXED,
  LABEL_PEST_QUICK_WORKER,
  MSG_PEST_QUICK_SAVE_FAIL,
  MSG_PEST_QUICK_SAVE_OK,
  MSG_PEST_QUICK_SITE_OPTIONAL,
  PEST_QUICK_STATUS_DEFAULT_CD,
  PEST_QUICK_STATUS_PREPARING_CD,
} from '@/views/home/homeConstants'
import {
  MSG_WORK_MEMO_GUIDE,
  MSG_DETAIL_PENDING,
  PLACEHOLDER_SELECT,
  PLACEHOLDER_WORK_RMK,
  WORK_MID_CD_PESTICIDE,
  WORK_STATUS_PARENT_CD,
  createEmptyLaborRow,
  todayIso,
  type DailyShellLaborRow,
  type DailyShellPesticideRow,
} from '@/views/work-log/workLogConstants'
import { useAppStore } from '@/composables/stores/app'
import type {
  WorkLogIntegratedSavePayload,
  WorkLogWorkItem,
  WorkLogWorkUpsertItem,
} from '@/types/workLog'

type PickOption = { value: string; label: string }

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  close: []
  saved: [message: string]
  error: [message: string]
}>()

const store = useAppStore()
const { farmCd } = storeToRefs(store)

const workDt = ref(todayIso())
const siteId = ref('')
const siteNm = ref('')
const startTm = ref('08:00')
const endTm = ref('09:00')
const statusCd = ref(PEST_QUICK_STATUS_DEFAULT_CD)
const statusNm = ref('완료')
const rmk = ref('')
const syncGoogle = ref(false)
const pesticideRows = ref<DailyShellPesticideRow[]>([])
const laborRows = ref<DailyShellLaborRow[]>([])
const saving = ref(false)

const siteOptions = ref<PickOption[]>([])
const statusOptions = ref<PickOption[]>([])
const partners = ref<WorkLogPartnerOption[]>([])
const googleStatus = ref<GoogleCalendarStatus | null>(null)
const sitePickOpen = ref(false)
const workerPickOpen = ref(false)
const statusPickOpen = ref(false)

const workerLabel = computed(() => {
  const row = laborRows.value[0]
  return row?.empNm || MSG_PEST_QUICK_SITE_OPTIONAL
})

const siteLabel = computed(() => siteNm.value || MSG_PEST_QUICK_SITE_OPTIONAL)

const statusLabel = computed(
  () => statusNm.value || PLACEHOLDER_SELECT,
)

function applyDefaultStatus() {
  const done = statusOptions.value.find(
    (o) => o.value === PEST_QUICK_STATUS_DEFAULT_CD,
  )
  if (done) {
    statusCd.value = done.value
    statusNm.value = done.label
    return
  }
  statusCd.value = PEST_QUICK_STATUS_DEFAULT_CD
  statusNm.value = '완료'
}

function resetForm() {
  workDt.value = todayIso()
  siteId.value = ''
  siteNm.value = ''
  startTm.value = '08:00'
  endTm.value = '09:00'
  applyDefaultStatus()
  rmk.value = ''
  syncGoogle.value = false
  pesticideRows.value = []
  laborRows.value = []
}

async function loadLookups() {
  if (!farmCd.value) return
  try {
    const [sites, pts, statuses, g] = await Promise.all([
      fetchFarmSites(farmCd.value),
      fetchWorkLogPartners(farmCd.value),
      fetchCommonCodes(farmCd.value, WORK_STATUS_PARENT_CD),
      fetchGoogleCalendarStatus(farmCd.value).catch(() => null),
    ])
    siteOptions.value = (sites || []).map((s) => ({
      value: s.site_id,
      label: String(s.site_nm || s.site_id),
    }))
    partners.value = pts || []
    statusOptions.value = (statuses || []).map((c) => ({
      value: c.code_cd,
      label: String(c.code_nm || c.code_cd),
    }))
    googleStatus.value = g
    applyDefaultStatus()
  } catch {
    siteOptions.value = []
    partners.value = []
    statusOptions.value = []
  }
}

watch(
  () => props.open,
  (v) => {
    if (v) {
      resetForm()
      void loadLookups()
    }
  },
)

onMounted(() => {
  if (props.open) void loadLookups()
})

function onPickSite(value: string, label: string) {
  siteId.value = value
  siteNm.value = label
  sitePickOpen.value = false
}

function onPickWorker(value: string, label: string) {
  const row = createEmptyLaborRow('labor-quick-1')
  row.empCd = value
  row.empNm = label
  row.manHour = '1'
  laborRows.value = [row]
  workerPickOpen.value = false
}

function onPickStatus(value: string, label: string) {
  statusCd.value = value
  statusNm.value = label
  statusPickOpen.value = false
}

function clearWorker() {
  laborRows.value = []
}

function onPestPending(msg?: string) {
  emit('error', msg || MSG_DETAIL_PENDING)
}

function toUpsertItem(w: WorkLogWorkItem): WorkLogWorkUpsertItem {
  return {
    work_id: w.work_id,
    work_mid_cd: String(w.work_mid_cd || ''),
    work_loc_id: w.work_loc_id || null,
    rmk: w.rmk || null,
    start_tm: w.start_tm || null,
    end_tm: w.end_tm || null,
    status_cd: w.status_cd || null,
  }
}

function predictNewWorkId(existingIds: readonly (string | null | undefined)[]): string {
  const ymd = workDt.value.replace(/-/g, '')
  const prefix = `${ymd}-`
  let maxSeq = 0
  const occupied = new Set<string>()
  for (const raw of existingIds) {
    const id = String(raw || '').trim()
    if (!id) continue
    occupied.add(id)
    if (id.startsWith(prefix)) {
      const tail = id.slice(prefix.length)
      if (/^\d+$/.test(tail)) maxSeq = Math.max(maxSeq, Number(tail))
    }
  }
  let seq = maxSeq
  while (true) {
    seq += 1
    const cand = `${ymd}-${String(seq).padStart(2, '0')}`
    if (!occupied.has(cand)) return cand
  }
}

async function onSave() {
  if (!farmCd.value) return
  saving.value = true
  let googleTarget = ''
  try {
    const daily = await fetchWorkLogDaily(farmCd.value, workDt.value)
    const existing = (daily.works || []).map(toUpsertItem)
    const draft: WorkLogWorkUpsertItem = {
      work_id: null,
      work_mid_cd: WORK_MID_CD_PESTICIDE,
      work_loc_id: siteId.value || null,
      rmk: rmk.value.trim() || null,
      start_tm: startTm.value || null,
      end_tm: endTm.value || null,
      status_cd: statusCd.value,
    }
    const works = [...existing, draft]
    const newWorkId = predictNewWorkId(existing.map((w) => w.work_id))
    googleTarget = newWorkId
    const isPreparing = statusCd.value === PEST_QUICK_STATUS_PREPARING_CD
    const hasSide =
      pesticideRows.value.some(
        (p) => Number(p.itemId) > 0 && Number(p.useQty) > 0,
      ) || laborRows.value.some((r) => r.empCd || r.empNm)

    // 준비중(만) + 부속 없음 → works draft / 그 외(기본 완료 포함) → integrated
    if (!isPreparing || hasSide) {
      const master = daily.master
      const integrated: WorkLogIntegratedSavePayload = {
        master: master
          ? {
              day_of_week: master.day_of_week,
              weather_cd: master.weather_cd,
              temp_min: master.temp_min,
              temp_max: master.temp_max,
              precip: master.precip,
              humidity: master.humidity,
              sun_rise: master.sun_rise,
              sun_set: master.sun_set,
              sunshine_hr: master.sunshine_hr,
              wind_max: master.wind_max,
              wind_min: master.wind_min,
              work_rmk: master.work_rmk,
            }
          : null,
        works: works.map((w) => {
          const isNew = !w.work_id
          return {
            ...w,
            work_id: w.work_id || (isNew ? newWorkId : w.work_id),
            work_mid_nm: isNew ? LABEL_PEST_QUICK_WORK_GROUP_FIXED : null,
            pesticide_lines: isNew
              ? pesticideRows.value
                  .filter((p) => Number(p.itemId) > 0 && Number(p.useQty) > 0)
                  .map((p) => ({
                    item_id: Number(p.itemId),
                    use_qty: Number(p.useQty || 0),
                    item_nm_snapshot: p.itemNm || null,
                    spec_nm_snapshot: p.spec || null,
                    purpose_nm: p.purpose || null,
                    line_rmk: p.rmk || null,
                  }))
              : [],
          }
        }),
        labor_work_id: newWorkId,
        expense_work_id: newWorkId,
        labor_rows: laborRows.value
          .filter((r) => r.empCd || r.empNm)
          .map((r) => ({
            status: 'INS',
            res_id: null,
            emp_cd: r.empCd || r.empNm,
            emp_nm: r.empNm || null,
            man_hour: Number(r.manHour || 0),
            daily_wage: Number(String(r.dayPay || '0').replace(/,/g, '')),
            pay_method_cd: r.payMethodCd || '',
            pay_status: r.paidYn || 'N',
          })),
        expense_rows: [],
        removed_res_ids: [],
        removed_exp_ids: [],
      }
      await saveWorkLogIntegrated(farmCd.value, workDt.value, integrated)
      for (const row of pesticideRows.value) {
        if (row.purpose?.trim()) {
          rememberRecentPurpose(farmCd.value, row.purpose.trim())
        }
      }
    } else {
      const saveRes = await saveWorkLogWorks(farmCd.value, workDt.value, {
        works,
      })
      const existingIds = new Set(
        existing.map((w) => String(w.work_id || '').trim()).filter(Boolean),
      )
      const fromServer = (saveRes.work_ids || []).find(
        (id) => !existingIds.has(String(id)),
      )
      googleTarget = fromServer || newWorkId
    }

    let msg = MSG_PEST_QUICK_SAVE_OK
    if (syncGoogle.value && googleStatus.value?.connected) {
      try {
        await pushWorkToGoogle(farmCd.value, googleTarget)
        msg = `${MSG_PEST_QUICK_SAVE_OK} (구글 반영)`
      } catch (err) {
        msg =
          err instanceof ApiClientError
            ? `${MSG_PEST_QUICK_SAVE_OK} · ${err.message}`
            : `${MSG_PEST_QUICK_SAVE_OK} · 구글 반영 실패`
      }
    }
    emit('saved', msg)
    emit('close')
  } catch (err) {
    emit(
      'error',
      err instanceof ApiClientError ? err.message : MSG_PEST_QUICK_SAVE_FAIL,
    )
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="overlay"
      role="dialog"
      aria-modal="true"
      :aria-label="LABEL_PEST_QUICK_TITLE"
    >
      <div class="sheet">
        <header class="sheet__head">
          <h2 class="sheet__title">{{ LABEL_PEST_QUICK_TITLE }}</h2>
          <button type="button" class="sheet__close" @click="emit('close')">
            ×
          </button>
        </header>

        <div class="sheet__body">
          <!-- 1행: 날짜 | 작업그룹 -->
          <div class="row2">
            <label class="field">
              <span class="field__label">{{ LABEL_PEST_QUICK_DATE }}</span>
              <input v-model="workDt" class="field__input" type="date" />
            </label>
            <div class="field">
              <span class="field__label">{{ LABEL_PEST_QUICK_WORK_GROUP }}</span>
              <p class="field__fixed">{{ LABEL_PEST_QUICK_WORK_GROUP_FIXED }}</p>
            </div>
          </div>

          <!-- 2행: 작업장소 | 작업자 -->
          <div class="row2">
            <div class="field">
              <span class="field__label">{{ LABEL_PEST_QUICK_SITE }}</span>
              <button
                type="button"
                class="field__pick"
                @click="sitePickOpen = true"
              >
                {{ siteLabel }}
              </button>
            </div>
            <div class="field">
              <span class="field__label">{{ LABEL_PEST_QUICK_WORKER }}</span>
              <div class="worker-row">
                <button
                  type="button"
                  class="field__pick"
                  @click="workerPickOpen = true"
                >
                  {{ workerLabel }}
                </button>
                <button
                  v-if="laborRows.length"
                  type="button"
                  class="worker-clear"
                  @click="clearWorker"
                >
                  ×
                </button>
              </div>
            </div>
          </div>

          <!-- 3행: 시간 From ~ To -->
          <div class="field">
            <span class="field__label">{{ LABEL_PEST_QUICK_TIME }}</span>
            <div class="time-row">
              <input v-model="startTm" class="field__input" type="time" />
              <span class="time-row__sep">~</span>
              <input v-model="endTm" class="field__input" type="time" />
            </div>
          </div>

          <!-- 4행: 농약추가 -->
          <div class="field field--pest">
            <WorkLogDailyPesticidePanel
              v-model="pesticideRows"
              mode="pesticide"
              :farm-cd="farmCd"
              :is-target-work="true"
              :show-stock-link="false"
              stock-applied-yn="N"
              @pending="onPestPending"
            />
          </div>

          <!-- 5행: 메모 (편집 중에도 Guide 유지) -->
          <label class="field">
            <span class="field__label">{{ LABEL_PEST_QUICK_MEMO }}</span>
            <p class="field__guide" role="note">{{ MSG_WORK_MEMO_GUIDE }}</p>
            <textarea
              v-model="rmk"
              class="field__textarea"
              rows="4"
              :placeholder="PLACEHOLDER_WORK_RMK"
            />
          </label>

          <!-- 6행: 상태 (WO01, 기본=완료) -->
          <div class="field">
            <span class="field__label">{{ LABEL_PEST_QUICK_STATUS }}</span>
            <button
              type="button"
              class="field__pick"
              @click="statusPickOpen = true"
            >
              {{ statusLabel }}
            </button>
          </div>

          <!-- 7행: 구글 반영 (기본 비체크) -->
          <label class="gcal">
            <input
              v-model="syncGoogle"
              type="checkbox"
              :disabled="!googleStatus?.connected"
            />
            <span>{{ LABEL_PEST_QUICK_GOOGLE }}</span>
            <span v-if="!googleStatus?.connected" class="gcal__hint">
              (미연결)
            </span>
          </label>
        </div>

        <footer class="sheet__foot">
          <OdsButton variant="secondary" @click="emit('close')">
            {{ BTN_PEST_QUICK_CANCEL }}
          </OdsButton>
          <OdsButton variant="primary" :busy="saving" @click="onSave">
            {{ BTN_PEST_QUICK_SAVE }}
          </OdsButton>
        </footer>
      </div>

      <WorkLogDailyPickSheet
        :open="sitePickOpen"
        :title="LABEL_PEST_QUICK_SITE"
        :options="siteOptions"
        @close="sitePickOpen = false"
        @select="onPickSite"
      />
      <WorkLogDailyPickSheet
        :open="workerPickOpen"
        :title="LABEL_PEST_QUICK_WORKER"
        :options="
          partners.map((p) => ({ value: String(p.pt_id), label: p.pt_nm }))
        "
        @close="workerPickOpen = false"
        @select="onPickWorker"
      />
      <WorkLogDailyPickSheet
        :open="statusPickOpen"
        :title="LABEL_PEST_QUICK_STATUS"
        :options="statusOptions"
        @close="statusPickOpen = false"
        @select="onPickStatus"
      />
    </div>
  </Teleport>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  background: rgba(0, 0, 0, 0.4);
}
.sheet {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: 480px;
  max-height: min(92dvh, 860px);
  border-radius: 16px 16px 0 0;
  background: var(--ods-color-bg-muted);
  box-shadow: 0 -4px 24px rgba(0, 0, 0, 0.12);
}
.sheet__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 14px 16px 10px;
  background: var(--ods-color-white);
  border-bottom: 1px solid var(--ods-color-border);
}
.sheet__title {
  margin: 0;
  font: var(--ods-font-headline);
}
.sheet__close {
  width: 36px;
  height: 36px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  font-size: 24px;
  line-height: 1;
  color: var(--ods-color-text-secondary);
  cursor: pointer;
}
.sheet__body {
  flex: 1 1 auto;
  overflow: auto;
  padding: 12px 16px 8px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.row2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  min-width: 0;
}
.field--pest {
  padding: 8px 10px;
}
.field__label {
  font: 600 12px/1.3 var(--ods-font-family);
  color: var(--ods-color-text-secondary);
}
.field__fixed {
  margin: 0;
  min-height: 40px;
  display: flex;
  align-items: center;
  font: 600 14px/1.35 var(--ods-font-family);
  color: var(--ods-color-primary);
}
.field__input {
  width: 100%;
  min-height: 40px;
  padding: 8px 10px;
  border: 1px solid var(--ods-color-border);
  border-radius: 10px;
  font: var(--ods-font-body-1);
  box-sizing: border-box;
  background: #fff;
}
.field__pick {
  width: 100%;
  min-height: 40px;
  padding: 8px 10px;
  border: 1px solid var(--ods-color-border);
  border-radius: 10px;
  background: #fff;
  text-align: left;
  font: var(--ods-font-body-1);
  color: var(--ods-color-text);
  cursor: pointer;
}
.field__guide {
  margin: 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.field__textarea {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--ods-color-border);
  border-radius: 10px;
  font: var(--ods-font-body-2);
  resize: vertical;
  box-sizing: border-box;
}
.time-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.time-row__sep {
  color: var(--ods-color-text-secondary);
  flex-shrink: 0;
}
.worker-row {
  display: flex;
  gap: 4px;
  align-items: center;
}
.worker-row .field__pick {
  flex: 1;
  min-width: 0;
}
.worker-clear {
  flex-shrink: 0;
  width: var(--ods-hit-sm);
  height: 40px;
  border: 0;
  background: transparent;
  color: var(--ods-color-text-secondary);
  font-size: 18px;
  cursor: pointer;
}
.gcal {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 4px 4px;
  font: var(--ods-font-body-2);
}
.gcal__hint {
  color: var(--ods-color-text-secondary);
  font: var(--ods-font-caption);
}
.sheet__foot {
  display: flex;
  gap: 8px;
  padding: 12px 16px calc(12px + env(safe-area-inset-bottom, 0px));
  background: var(--ods-color-white);
  border-top: 1px solid var(--ods-color-border);
}
.sheet__foot :deep(.ods-btn) {
  flex: 1;
}
</style>
