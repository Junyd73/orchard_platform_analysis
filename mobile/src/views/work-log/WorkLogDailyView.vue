<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { fetchCommonCodes } from '@/api/commonCodes'
import { fetchFarmSites } from '@/api/farms'
import {
  cancelWorkLogPesticide,
  deleteWorkLogWork,
  fetchWorkLogDaily,
  fetchWorkLogWeather,
  saveWorkLogIntegrated,
  saveWorkLogMaster,
  saveWorkLogWorks,
} from '@/api/workLogs'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsButton from '@/components/ods/OdsButton.vue'
import WorkLogDailyDateBar from '@/views/work-log/components/WorkLogDailyDateBar.vue'
import WorkLogDailyExtras from '@/views/work-log/components/WorkLogDailyExtras.vue'
import WorkLogDailySummary from '@/views/work-log/components/WorkLogDailySummary.vue'
import WorkLogDailyTimeline from '@/views/work-log/components/WorkLogDailyTimeline.vue'
import WorkLogDailyWeatherStrip from '@/views/work-log/components/WorkLogDailyWeatherStrip.vue'
import WorkLogDailyWorkCard from '@/views/work-log/components/WorkLogDailyWorkCard.vue'
import WorkLogDailyWorkForm, {
  type DailyPickOption,
} from '@/views/work-log/components/WorkLogDailyWorkForm.vue'
import iconTrash from '@/assets/ods/scr004/icon-trash.svg'
import {
  createEmptyWorkForm,
  DAILY_SHELL_SUMMARY,
  DAILY_TAB_WORK,
  hasWorkLogWeather,
  isFutureDate,
  mapWorkItemToTimeline,
  MSG_DETAIL_PENDING,
  MSG_DRAFT_OK,
  MSG_FUTURE_WORK_LOG,
  MSG_LOAD_DAILY_FAILED,
  MSG_SAVE_FAILED,
  MSG_SAVE_OK,
  MSG_WORK_CONTENT_REQUIRED,
  todayIso,
  WORK_STATUS_PARENT_CD,
  WORK_TYPE_PARENT_CD,
  type DailyShellExpenseRow,
  type DailyShellLaborRow,
  type DailyShellPesticideRow,
  type DailyTimelineItem,
  type DailyWorkFormModel,
  type DailyWorkTabKey,
} from '@/views/work-log/workLogConstants'
import { useAppStore } from '@/composables/stores/app'
import type {
  WorkLogExpenseDto,
  WorkLogIntegratedSavePayload,
  WorkLogMasterDto,
  WorkLogPesticideDocDto,
  WorkLogResourceDto,
  WorkLogWorkItem,
  WorkLogWorkUpsertItem,
} from '@/types/workLog'

const store = useAppStore()
const router = useRouter()
const route = useRoute()
const { farmCd, farm } = storeToRefs(store)

const workDt = computed(() => String(route.params.workDt || '').trim())
const isFuture = computed(() => isFutureDate(workDt.value))

const dailyLoading = ref(false)
const saving = ref(false)
const master = ref<WorkLogMasterDto | null>(null)
const toastMessage = ref('')
const activeTab = ref<DailyWorkTabKey>(DAILY_TAB_WORK)

/** API 원본 작업 (저장 시 merge) */
const sourceWorks = ref<WorkLogWorkItem[]>([])
const workItems = ref<DailyTimelineItem[]>([])
const selectedId = ref<string | null>(null)
const isEditing = ref(true)
const formModel = ref<DailyWorkFormModel>(createEmptyWorkForm())

const laborRows = ref<DailyShellLaborRow[]>([])
const expenseRows = ref<DailyShellExpenseRow[]>([])
const pesticideRows = ref<DailyShellPesticideRow[]>([])
const pesticideAppliedYn = ref('N')
const pesticideUseId = ref<number | null>(null)
/** 수정 모드: 저장 시에만 기존 use_id 교체(진입만으로 재고 복원 안 함) */
const pesticideReplaceUseId = ref<number | null>(null)
const removedResIds = ref<number[]>([])
const removedExpIds = ref<number[]>([])

const workOptions = ref<DailyPickOption[]>([])
const siteOptions = ref<DailyPickOption[]>([])
const statusOptions = ref<DailyPickOption[]>([])

const hasWorks = computed(() => workItems.value.length > 0)
const showForm = computed(() => isEditing.value || !hasWorks.value)

const selectedItem = computed(
  () => workItems.value.find((it) => it.id === selectedId.value) || null,
)

function applyWorksFromApi(works: WorkLogWorkItem[]) {
  sourceWorks.value = [...(works || [])]
  const items = sourceWorks.value.map((w, i) => mapWorkItemToTimeline(w, i))
  workItems.value = items
  if (items.length > 0) {
    selectedId.value = items[0]?.id || null
    isEditing.value = false
    activeTab.value = DAILY_TAB_WORK
  } else {
    selectedId.value = null
    isEditing.value = true
    formModel.value = createEmptyWorkForm()
  }
}

function mapResourceToShell(r: WorkLogResourceDto): DailyShellLaborRow {
  return {
    id: `res-${r.res_id ?? r.emp_cd}`,
    resId: r.res_id ?? null,
    empCd: r.emp_cd || '',
    empNm: r.emp_nm || r.emp_cd || '',
    manHour: String(r.man_hour ?? 0),
    dayPay: String(Math.round(r.daily_wage ?? 0)),
    payMethodCd: r.pay_method_cd || '',
    payMethod: r.pay_method_nm || r.pay_method_cd || '',
    paidYn: r.pay_status || 'N',
    status: 'ORG',
  }
}

function mapExpenseToShell(e: WorkLogExpenseDto): DailyShellExpenseRow {
  return {
    id: `exp-${e.exp_id ?? e.acct_cd}`,
    expId: e.exp_id ?? null,
    occurDt: e.trans_dt || workDt.value,
    acctCd: e.acct_cd || '',
    expenseNm: e.acct_nm || e.acct_cd || '',
    detail: e.item_nm || '',
    amount: String(Math.round(e.total_amt ?? 0)),
    unitPrice: '0',
    qty: '1',
    payMethodCd: e.pay_method_cd || '',
    payMethod: e.pay_method_nm || e.pay_method_cd || '',
    paidYn: e.pay_status || 'N',
    status: 'ORG',
  }
}

function mapPesticideDoc(
  doc: WorkLogPesticideDocDto | undefined,
): void {
  pesticideAppliedYn.value = doc?.stock_applied_yn || 'N'
  pesticideUseId.value = doc?.use_id ?? null
  pesticideReplaceUseId.value = null
  pesticideRows.value = (doc?.lines || []).map((ln, i) => ({
    id: `pest-${doc?.use_id ?? 'x'}-${i}`,
    itemId: ln.item_id,
    itemNm: ln.item_nm_snapshot || '',
    spec: ln.spec_nm_snapshot || '',
    useQty: String(ln.use_qty ?? 0),
    purpose: ln.purpose_nm || '',
    rmk: ln.line_rmk || '',
  }))
}

function loadSideForWork(
  workId: string | null,
  resources: WorkLogResourceDto[],
  expenses: WorkLogExpenseDto[],
  pesticides: WorkLogPesticideDocDto[],
) {
  if (!workId) {
    laborRows.value = []
    expenseRows.value = []
    pesticideRows.value = []
    pesticideAppliedYn.value = 'N'
    pesticideUseId.value = null
    return
  }
  laborRows.value = resources
    .filter((r) => r.work_id === workId)
    .map(mapResourceToShell)
  expenseRows.value = expenses
    .filter((e) => e.work_id === workId)
    .map(mapExpenseToShell)
  mapPesticideDoc(pesticides.find((p) => p.work_id === workId))
}

let cachedResources: WorkLogResourceDto[] = []
let cachedExpenses: WorkLogExpenseDto[] = []
let cachedPesticides: WorkLogPesticideDocDto[] = []

function onSelectTimeline(id: string) {
  selectedId.value = id
  activeTab.value = DAILY_TAB_WORK
  isEditing.value = false
  loadSideForWork(id, cachedResources, cachedExpenses, cachedPesticides)
}

function onAddWork() {
  isEditing.value = true
  activeTab.value = DAILY_TAB_WORK
  formModel.value = createEmptyWorkForm()
  laborRows.value = []
  expenseRows.value = []
  pesticideRows.value = []
  pesticideAppliedYn.value = 'N'
  pesticideUseId.value = null
}

function onEditSelected() {
  const w = sourceWorks.value.find((it) => it.work_id === selectedId.value)
  if (!w) {
    onPending()
    return
  }
  formModel.value = {
    workId: w.work_id,
    workMidCd: String(w.work_mid_cd || ''),
    workContent: String(w.work_mid_nm || ''),
    workLocId: String(w.work_loc_id || ''),
    siteNm: String(w.work_loc_nm || ''),
    startTime: String(w.start_tm || '08:00').slice(0, 5),
    endTime: String(w.end_tm || '09:00').slice(0, 5),
    statusCd: String(w.status_cd || ''),
    statusNm: String(w.status_nm || ''),
    rmk: String(w.rmk || ''),
  }
  isEditing.value = true
  activeTab.value = DAILY_TAB_WORK
}

function showToast(msg: string) {
  toastMessage.value = msg
  window.setTimeout(() => {
    if (toastMessage.value === msg) toastMessage.value = ''
  }, 2400)
}

function onPending() {
  showToast(MSG_DETAIL_PENDING)
}

function goBack() {
  const dt = workDt.value
  const q: Record<string, string> = {}
  if (/^\d{4}-\d{2}-\d{2}$/.test(dt)) {
    q.year = dt.slice(0, 4)
    q.month = String(Number(dt.slice(5, 7)))
  }
  void router.push({ name: 'work-log', query: q })
}

function goToday() {
  const t = todayIso()
  if (workDt.value === t) return
  void router.push({ name: 'work-log-daily', params: { workDt: t } })
}

/** 기능2: DB(마스터·캐시 병합) → 없으면 외부 API */
async function ensureWeather(
  current: WorkLogMasterDto | null,
): Promise<WorkLogMasterDto | null> {
  if (hasWorkLogWeather(current) || isFutureDate(workDt.value)) {
    return current
  }
  try {
    const fetched = await fetchWorkLogWeather(farmCd.value, workDt.value)
    return fetched.master || current
  } catch {
    return current
  }
}

async function loadPickOptions() {
  const farm = farmCd.value
  if (!farm) return
  try {
    const [works, sites, statuses] = await Promise.all([
      fetchCommonCodes(farm, WORK_TYPE_PARENT_CD),
      fetchFarmSites(farm),
      fetchCommonCodes(farm, WORK_STATUS_PARENT_CD),
    ])
    workOptions.value = (works || [])
      .filter((c) => String(c.code_cd || '').length === 8)
      .map((c) => ({
        value: c.code_cd,
        label: String(c.code_nm || c.code_cd),
      }))
    siteOptions.value = (sites || []).map((s) => ({
      value: s.site_id,
      label: String(s.site_nm || s.site_id),
    }))
    statusOptions.value = (statuses || []).map((c) => ({
      value: c.code_cd,
      label: String(c.code_nm || c.code_cd),
    }))
  } catch {
    workOptions.value = []
    siteOptions.value = []
    statusOptions.value = []
  }
}

async function loadDaily() {
  if (!workDt.value || !/^\d{4}-\d{2}-\d{2}$/.test(workDt.value)) {
    master.value = null
    sourceWorks.value = []
    workItems.value = []
    selectedId.value = null
    isEditing.value = true
    return
  }
  dailyLoading.value = true
  try {
    const daily = await fetchWorkLogDaily(farmCd.value, workDt.value)
    master.value = await ensureWeather(daily.master)
    cachedResources = daily.resources || []
    cachedExpenses = daily.expenses || []
    cachedPesticides = daily.pesticides || []
    applyWorksFromApi(daily.works || [])
    loadSideForWork(
      selectedId.value,
      cachedResources,
      cachedExpenses,
      cachedPesticides,
    )
  } catch {
    master.value = null
    sourceWorks.value = []
    workItems.value = []
    selectedId.value = null
    isEditing.value = true
    showToast(MSG_LOAD_DAILY_FAILED)
  } finally {
    dailyLoading.value = false
  }
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

function buildWorksPayload(): WorkLogWorkUpsertItem[] | null {
  const list = sourceWorks.value.map(toUpsertItem)

  if (showForm.value) {
    if (!formModel.value.workMidCd) {
      showToast(MSG_WORK_CONTENT_REQUIRED)
      return null
    }
    const draft: WorkLogWorkUpsertItem = {
      work_id: formModel.value.workId,
      work_mid_cd: formModel.value.workMidCd,
      work_loc_id: formModel.value.workLocId || null,
      rmk: formModel.value.rmk || null,
      start_tm: formModel.value.startTime || null,
      end_tm: formModel.value.endTime || null,
      status_cd: formModel.value.statusCd || null,
    }
    if (draft.work_id) {
      const idx = list.findIndex((w) => w.work_id === draft.work_id)
      if (idx >= 0) list[idx] = draft
      else list.push(draft)
    } else {
      list.push(draft)
    }
  }

  const valid = list.filter((w) => String(w.work_mid_cd || '').trim())
  if (valid.length === 0) {
    showToast(MSG_WORK_CONTENT_REQUIRED)
    return null
  }
  return valid
}

async function persistMasterIfNeeded() {
  const m = master.value
  if (!m || !hasWorkLogWeather(m)) return
  await saveWorkLogMaster(farmCd.value, workDt.value, {
    day_of_week: m.day_of_week,
    weather_cd: m.weather_cd,
    temp_min: m.temp_min,
    temp_max: m.temp_max,
    precip: m.precip,
    humidity: m.humidity,
    sun_rise: m.sun_rise,
    sun_set: m.sun_set,
    sunshine_hr: m.sunshine_hr,
    wind_max: m.wind_max,
    wind_min: m.wind_min,
    work_rmk: m.work_rmk,
  })
}

/** 임시저장: 작업만 · 저장하기: 통합(Ledger+농약 확정) */
async function onSave(mode: 'draft' | 'final') {
  if (isFuture.value) {
    showToast(MSG_FUTURE_WORK_LOG)
    return
  }
  const payload = buildWorksPayload()
  if (!payload) return
  saving.value = true
  try {
    if (mode === 'draft') {
      await persistMasterIfNeeded()
      await saveWorkLogWorks(farmCd.value, workDt.value, { works: payload })
      await loadDaily()
      showToast(MSG_DRAFT_OK)
      return
    }

    const laborWorkId =
      selectedId.value ||
      formModel.value.workId ||
      payload[0]?.work_id ||
      null
    const integrated: WorkLogIntegratedSavePayload = {
      master: master.value
        ? {
            day_of_week: master.value.day_of_week,
            weather_cd: master.value.weather_cd,
            temp_min: master.value.temp_min,
            temp_max: master.value.temp_max,
            precip: master.value.precip,
            humidity: master.value.humidity,
            sun_rise: master.value.sun_rise,
            sun_set: master.value.sun_set,
            sunshine_hr: master.value.sunshine_hr,
            wind_max: master.value.wind_max,
            wind_min: master.value.wind_min,
            work_rmk: master.value.work_rmk,
          }
        : null,
      works: payload.map((w) => ({
        ...w,
        work_mid_nm:
          workOptions.value.find((o) => o.value === w.work_mid_cd)?.label ||
          null,
        replace_pesticide_use_id:
          w.work_id === laborWorkId || (!w.work_id && showForm.value)
            ? pesticideReplaceUseId.value
            : null,
        pesticide_lines:
          (w.work_id === laborWorkId || (!w.work_id && showForm.value)
            ? pesticideRows.value
            : []
          )
            .filter((p) => Number(p.itemId) > 0 && Number(p.useQty) > 0)
            .map((p) => ({
              item_id: Number(p.itemId),
              use_qty: Number(p.useQty || 0),
              item_nm_snapshot: p.itemNm || null,
              spec_nm_snapshot: p.spec || null,
              purpose_nm: p.purpose || null,
              line_rmk: p.rmk || null,
            })),
      })),
      labor_work_id: laborWorkId,
      expense_work_id: laborWorkId,
      labor_rows: laborRows.value
        .filter((r) => r.empCd || r.empNm)
        .map((r) => ({
          status: r.status || (r.resId ? 'ORG' : 'INS'),
          res_id: r.resId ?? null,
          emp_cd: r.empCd || r.empNm,
          emp_nm: r.empNm || null,
          man_hour: Number(r.manHour || 0),
          daily_wage: Number(String(r.dayPay || '0').replace(/,/g, '')),
          pay_method_cd: r.payMethodCd || '',
          pay_status: r.paidYn || 'N',
        })),
      expense_rows: expenseRows.value
        .filter((r) => r.acctCd)
        .map((r) => ({
          status: r.status || (r.expId ? 'ORG' : 'INS'),
          exp_id: r.expId ?? null,
          acct_cd: r.acctCd,
          item_nm: r.detail || r.expenseNm || null,
          amt: Number(String(r.amount || '0').replace(/,/g, '')),
          pay_method_cd: r.payMethodCd || '',
          pay_status: r.paidYn || 'N',
          trans_dt: r.occurDt || workDt.value,
        })),
      removed_res_ids: removedResIds.value,
      removed_exp_ids: removedExpIds.value,
    }
    await saveWorkLogIntegrated(farmCd.value, workDt.value, integrated)
    removedResIds.value = []
    removedExpIds.value = []
    pesticideReplaceUseId.value = null
    await loadDaily()
    showToast(MSG_SAVE_OK)
    window.setTimeout(() => goBack(), 600)
  } catch {
    showToast(MSG_SAVE_FAILED)
  } finally {
    saving.value = false
  }
}

async function onCancelPesticide() {
  if (!pesticideUseId.value) {
    showToast('취소할 농약 사용 ID가 없습니다.')
    return
  }
  saving.value = true
  try {
    await cancelWorkLogPesticide(farmCd.value, {
      use_id: pesticideUseId.value,
    })
    pesticideReplaceUseId.value = null
    await loadDaily()
    showToast('농약 사용이 취소되었습니다.')
  } catch {
    showToast(MSG_SAVE_FAILED)
  } finally {
    saving.value = false
  }
}

function onEditPesticide() {
  if (!pesticideUseId.value || pesticideAppliedYn.value !== 'Y') {
    onPending()
    return
  }
  pesticideReplaceUseId.value = pesticideUseId.value
  showToast('수정 모드: 저장 시 기존 사용이 교체됩니다.')
}

async function onDeleteSelected() {
  if (!selectedId.value) {
    onPending()
    return
  }
  saving.value = true
  try {
    await deleteWorkLogWork(farmCd.value, selectedId.value)
    await loadDaily()
    showToast(MSG_SAVE_OK)
  } catch {
    showToast(MSG_SAVE_FAILED)
  } finally {
    saving.value = false
  }
}

watch(workDt, () => {
  void loadDaily()
})

onMounted(async () => {
  if (!farm.value) {
    await store.refreshAll()
  }
  await Promise.all([loadDaily(), loadPickOptions()])
})
</script>

<template>
  <div class="page">
    <main class="content">
      <OdsAppBar show-back @back="goBack" />

      <p v-if="isFuture" class="warn" role="alert">{{ MSG_FUTURE_WORK_LOG }}</p>

      <WorkLogDailyDateBar :work-dt="workDt" @go-today="goToday" />

      <WorkLogDailyWeatherStrip :master="master" :loading="dailyLoading" />

      <WorkLogDailyTimeline
        :items="workItems"
        :selected-id="selectedId"
        @select="onSelectTimeline"
        @add="onAddWork"
      />

      <WorkLogDailyWorkForm
        v-if="showForm"
        v-model="formModel"
        v-model:active-tab="activeTab"
        v-model:labor-rows="laborRows"
        v-model:expense-rows="expenseRows"
        v-model:pesticide-rows="pesticideRows"
        :work-options="workOptions"
        :site-options="siteOptions"
        :status-options="statusOptions"
        :work-dt="workDt"
        :stock-applied-yn="pesticideAppliedYn"
        :editing-replace="!!pesticideReplaceUseId"
        @pending="onPending"
        @cancel-pesticide="onCancelPesticide"
        @edit-pesticide="onEditPesticide"
      />
      <WorkLogDailyWorkCard
        v-else-if="selectedItem"
        v-model:active-tab="activeTab"
        v-model:labor-rows="laborRows"
        v-model:expense-rows="expenseRows"
        v-model:pesticide-rows="pesticideRows"
        :item="selectedItem"
        :work-dt="workDt"
        :stock-applied-yn="pesticideAppliedYn"
        :editing-replace="!!pesticideReplaceUseId"
        @edit="onEditSelected"
        @copy="onPending"
        @pending="onPending"
        @cancel-pesticide="onCancelPesticide"
        @edit-pesticide="onEditPesticide"
      />

      <WorkLogDailySummary
        :cards="DAILY_SHELL_SUMMARY"
        :empty="!hasWorks"
      />

      <WorkLogDailyExtras
        :work-dt="workDt"
        :show-examples="hasWorks"
      />
    </main>

    <div
      v-if="showForm"
      class="footer-actions"
      aria-label="임시 저장·저장하기"
    >
      <OdsButton
        variant="secondary"
        type="button"
        :block="false"
        class="footer-btn footer-btn--outline"
        :busy="saving"
        @click="onSave('draft')"
      >
        임시 저장
      </OdsButton>
      <OdsButton
        variant="primary"
        type="button"
        :block="false"
        class="footer-btn"
        :busy="saving"
        @click="onSave('final')"
      >
        저장하기
      </OdsButton>
    </div>
    <div v-else class="footer-actions" aria-label="저장·삭제">
      <OdsButton
        variant="primary"
        type="button"
        :block="false"
        class="footer-btn"
        :busy="saving"
        @click="onSave('final')"
      >
        저장
      </OdsButton>
      <OdsButton
        variant="danger"
        type="button"
        :block="false"
        class="footer-btn"
        :busy="saving"
        @click="onDeleteSelected"
      >
        <span class="footer-btn__inner">
          <img :src="iconTrash" alt="" aria-hidden="true" />
          삭제
        </span>
      </OdsButton>
    </div>

    <p v-if="toastMessage" class="toast" role="status">{{ toastMessage }}</p>
    <OdsBottomNav />
  </div>
</template>

<style scoped>
.page {
  min-height: 100dvh;
  background: var(--ods-color-bg);
  padding-bottom: calc(160px + env(safe-area-inset-bottom));
}

.content {
  max-width: 480px;
  margin: 0 auto;
  padding: var(--ods-space-12) var(--ods-page-padding-x) var(--ods-space-20);
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-16);
}

.warn {
  margin: 0;
  padding: var(--ods-space-12);
  border-radius: var(--ods-radius-button);
  background: color-mix(in srgb, var(--ods-color-caution) 18%, transparent);
  color: var(--ods-color-text);
  font: var(--ods-font-body-2);
  font-weight: 600;
}

.footer-actions {
  position: fixed;
  left: 0;
  right: 0;
  bottom: calc(64px + env(safe-area-inset-bottom, 0px));
  z-index: 30;
  display: flex;
  gap: var(--ods-space-8);
  max-width: 480px;
  margin: 0 auto;
  padding: var(--ods-space-8) var(--ods-page-padding-x)
    calc(var(--ods-space-8) + env(safe-area-inset-bottom, 0px));
  background: color-mix(in srgb, var(--ods-color-bg) 92%, transparent);
  backdrop-filter: blur(8px);
}
.footer-btn {
  flex: 1;
}
.footer-actions :deep(.ods-btn) {
  min-height: 48px;
}
.footer-btn--outline :deep(.ods-btn),
.footer-actions :deep(.footer-btn--outline) {
  background: var(--ods-color-white);
  border: 1.5px solid var(--ods-color-primary);
  color: var(--ods-color-primary);
}
.footer-btn__inner {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--ods-space-8);
}
.footer-btn__inner img {
  width: 18px;
  height: 18px;
}

.toast {
  position: fixed;
  left: 50%;
  bottom: calc(150px + env(safe-area-inset-bottom));
  transform: translateX(-50%);
  z-index: 70;
  max-width: min(420px, calc(100vw - 32px));
  margin: 0;
  padding: var(--ods-space-12) var(--ods-space-16);
  border-radius: var(--ods-radius-button);
  background: color-mix(in srgb, var(--ods-color-gray-900) 92%, transparent);
  color: var(--ods-color-white);
  font: var(--ods-font-body-2);
  font-weight: 600;
  text-align: center;
  box-shadow: var(--ods-shadow-card);
}
</style>
