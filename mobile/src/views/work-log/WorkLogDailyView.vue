<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  onBeforeRouteLeave,
  useRoute,
  useRouter,
  type RouteLocationNormalized,
} from 'vue-router'
import { storeToRefs } from 'pinia'

import { fetchCommonCodes } from '@/api/commonCodes'
import {
  rememberRecentPurpose,
} from '@/views/pesticide/pesticideConstants'
import { ApiClientError } from '@/api/client'
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
import {
  confirmGoogleImport,
  fetchGoogleCalendarStatus,
  fetchGoogleImportPreview,
  pushWorkToGoogle,
  requestGoogleCalendarAuthUrl,
  type GoogleCalendarStatus,
  type GoogleImportPreviewItem,
} from '@/api/googleCalendar'
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
  buildDailySummaryCards,
  createEmptyWorkForm,
  DAILY_TAB_LABOR,
  DAILY_TAB_WORK,
  hasWorkLogWeather,
  isFutureDate,
  mapWorkItemToTimeline,
  sortWorksByStartTime,
  BTN_UNSAVED_LEAVE_DISCARD,
  BTN_UNSAVED_LEAVE_SAVE,
  BTN_UNSAVED_LEAVE_STAY,
  MSG_DETAIL_PENDING,
  MSG_DRAFT_OK,
  MSG_COPY_DATE_INVALID,
  MSG_COPY_OK,
  MSG_FUTURE_WORK_LOG,
  MSG_FUTURE_DETAIL_LOCKED,
  MSG_GOOGLE_IMPORT_EMPTY,
  MSG_GOOGLE_IMPORT_NEED_CONNECT,
  MSG_GOOGLE_IMPORT_SAVED,
  MSG_LOAD_DAILY_FAILED,
  MSG_SAVE_FAILED,
  MSG_SAVE_OK,
  MSG_UNSAVED_LEAVE_CONFIRM,
  MSG_WORK_CONTENT_REQUIRED,
  STATUS_PREPARING_CD,
  todayIso,
  WORK_STATUS_PARENT_CD,
  WORK_TYPE_PARENT_CD,
  type DailyShellExpenseRow,
  type DailyShellLaborRow,
  type DailyShellPesticideRow,
  type DailyShellSummaryCard,
  type DailyTimelineItem,
  type DailyWorkFormModel,
  type DailyWorkTabKey,
} from '@/views/work-log/workLogConstants'
import { HOME_DAILY_NEW_QUERY } from '@/views/home/homeConstants'
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
const isCopyMode = ref(false)
/** 복사 대상 작업일 (YYYY-MM-DD) */
const copyTargetDt = ref('')
/** 작업복사 모달 오픈 */
const copyModalOpen = ref(false)
/** 복사 버튼 클릭 시 원본 작업(work_id) — 취소 시 복원 */
const copySourceWorkId = ref<string | null>(null)
/** 복사 후 이동 시(다른 날짜) 인력 탭으로 전환 + 복사된 작업 선택 */
const goLaborAfterCopy = ref(false)
const copyCreatedWorkId = ref<string | null>(null)
const formModel = ref<DailyWorkFormModel>(createEmptyWorkForm())
const googleStatus = ref<GoogleCalendarStatus | null>(null)
const googleImportOpen = ref(false)
const googleImportLoading = ref(false)
const googleImportBusy = ref(false)
const googleImportItems = ref<GoogleImportPreviewItem[]>([])
const googleImportMessage = ref('')

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

/** 미저장 이탈 가드 */
const cleanSnapshot = ref('')
const leaveGuardBypass = ref(false)
const leaveConfirmOpen = ref(false)
let pendingLeaveTo: RouteLocationNormalized | null = null

const hasWorks = computed(() => workItems.value.length > 0)
const showForm = computed(() => isEditing.value || !hasWorks.value)

const selectedItem = computed(
  () => workItems.value.find((it) => it.id === selectedId.value) || null,
)

function serializeEditableState(): string {
  return JSON.stringify({
    form: showForm.value ? formModel.value : null,
    copy: isCopyMode.value ? copyTargetDt.value : null,
    labor: laborRows.value,
    expense: expenseRows.value,
    pest: pesticideRows.value,
    remR: removedResIds.value,
    remE: removedExpIds.value,
    replace: pesticideReplaceUseId.value,
  })
}

function captureCleanState() {
  cleanSnapshot.value = serializeEditableState()
}

function hasUnsavedRegisteredData(): boolean {
  if (!cleanSnapshot.value) return false
  return serializeEditableState() !== cleanSnapshot.value
}

function closeLeaveConfirm() {
  leaveConfirmOpen.value = false
  pendingLeaveTo = null
}

function proceedPendingLeave() {
  const to = pendingLeaveTo
  leaveConfirmOpen.value = false
  pendingLeaveTo = null
  if (!to) return
  leaveGuardBypass.value = true
  void router.push(to.fullPath || to)
}

async function onLeaveConfirmSave() {
  const to = pendingLeaveTo
  leaveConfirmOpen.value = false
  pendingLeaveTo = null
  const ok = await onSave('final', {
    navigateTo: to || undefined,
  })
  // 실패 시 다이얼로그를 다시 열지 않음(토스트가 가려짐). 화면 유지.
  if (!ok) return
}

function onLeaveConfirmDiscard() {
  proceedPendingLeave()
}

function onLeaveConfirmStay() {
  closeLeaveConfirm()
}

function applyWorksFromApi(works: WorkLogWorkItem[]) {
  sourceWorks.value = sortWorksByStartTime(works || [])
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

const summaryCards = ref<DailyShellSummaryCard[]>([])

function refreshSummaryCards() {
  summaryCards.value = buildDailySummaryCards({
    resources: cachedResources,
    expenses: cachedExpenses,
    pesticides: cachedPesticides,
  })
}

function clearCopyMode() {
  isCopyMode.value = false
  copyTargetDt.value = ''
  copyModalOpen.value = false
}

function onSelectTimeline(id: string) {
  selectedId.value = id
  activeTab.value = DAILY_TAB_WORK
  isEditing.value = false
  clearCopyMode()
  removedResIds.value = []
  removedExpIds.value = []
  loadSideForWork(id, cachedResources, cachedExpenses, cachedPesticides)
  captureCleanState()
}

function onAddWork() {
  selectedId.value = null
  isEditing.value = true
  clearCopyMode()
  activeTab.value = DAILY_TAB_WORK
  formModel.value = createEmptyWorkForm()
  if (isFuture.value) {
    const prep = statusOptions.value.find((o) => o.value === STATUS_PREPARING_CD)
    formModel.value = {
      ...formModel.value,
      statusCd: STATUS_PREPARING_CD,
      statusNm: prep?.label || '준비중',
    }
  }
  laborRows.value = []
  expenseRows.value = []
  pesticideRows.value = []
  pesticideAppliedYn.value = 'N'
  pesticideUseId.value = null
  pesticideReplaceUseId.value = null
  removedResIds.value = []
  removedExpIds.value = []
  captureCleanState()
}

function onRemoveLaborRes(resId: number) {
  const id = Number(resId)
  if (!(id > 0)) return
  if (!removedResIds.value.includes(id)) {
    removedResIds.value = [...removedResIds.value, id]
  }
}

function onRemoveExpenseExp(expId: number) {
  const id = Number(expId)
  if (!(id > 0)) return
  if (!removedExpIds.value.includes(id)) {
    removedExpIds.value = [...removedExpIds.value, id]
  }
}

function onEditSelected() {
  const w = sourceWorks.value.find((it) => it.work_id === selectedId.value)
  if (!w) {
    onPending()
    return
  }
  clearCopyMode()
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
    syncGoogle: false,
    googleEventId: String(w.google_event_id || '') || null,
  }
  isEditing.value = true
  activeTab.value = DAILY_TAB_WORK
  captureCleanState()
}

/** 작업 기본정보만 복사 · 인력/경비/농약/사진 제외 · 작업일 변경 가능 */
function onCopySelected() {
  const w = sourceWorks.value.find((it) => it.work_id === selectedId.value)
  if (!w) {
    onPending()
    return
  }
  copySourceWorkId.value = selectedId.value
  formModel.value = {
    workId: null,
    workMidCd: String(w.work_mid_cd || ''),
    workContent: String(w.work_mid_nm || ''),
    workLocId: String(w.work_loc_id || ''),
    siteNm: String(w.work_loc_nm || ''),
    startTime: String(w.start_tm || '08:00').slice(0, 5),
    endTime: String(w.end_tm || '09:00').slice(0, 5),
    statusCd: String(w.status_cd || ''),
    statusNm: String(w.status_nm || ''),
    rmk: String(w.rmk || ''),
    syncGoogle: false,
    googleEventId: null,
  }
  laborRows.value = []
  expenseRows.value = []
  pesticideRows.value = []
  pesticideAppliedYn.value = 'N'
  pesticideUseId.value = null
  pesticideReplaceUseId.value = null
  removedResIds.value = []
  removedExpIds.value = []
  selectedId.value = null
  isCopyMode.value = true
  copyTargetDt.value = todayIso()
  copyCreatedWorkId.value = null
  goLaborAfterCopy.value = false
  copyModalOpen.value = true
  isEditing.value = true
  activeTab.value = DAILY_TAB_WORK
  captureCleanState()
}

function onCancelCopyModal() {
  const restoreId = copySourceWorkId.value
  clearCopyMode()
  if (!restoreId) {
    selectedId.value = null
    isEditing.value = true
    formModel.value = createEmptyWorkForm()
    captureCleanState()
    return
  }
  selectedId.value = restoreId
  isEditing.value = false
  activeTab.value = DAILY_TAB_WORK
  loadSideForWork(
    restoreId,
    cachedResources,
    cachedExpenses,
    cachedPesticides,
  )
  captureCleanState()
}


/** 복사 모달 "적용" — 저장 없이 복사 날짜의 일간 화면으로 이동해 작업등록 폼을 열어줌 */
async function onCopyModalApply() {
  if (!formModel.value.workMidCd) {
    showToast(MSG_WORK_CONTENT_REQUIRED)
    return
  }
  const targetDt = String(copyTargetDt.value || '').trim()
  if (!targetDt || !/^\d{4}-\d{2}-\d{2}$/.test(targetDt)) {
    showToast(MSG_COPY_DATE_INVALID)
    return
  }

  // 현재 화면과 복사 날짜가 같으면 그냥 폼만 열기
  if (targetDt === workDt.value) {
    copyModalOpen.value = false
    isCopyMode.value = false
    selectedId.value = null
    isEditing.value = true
    activeTab.value = DAILY_TAB_WORK
    captureCleanState()
    return
  }

  // 복사 데이터 스냅샷
  const copyData = {
    workMidCd: formModel.value.workMidCd || '',
    workContent: formModel.value.workContent || '',
    workLocId: formModel.value.workLocId || '',
    siteNm: formModel.value.siteNm || '',
    startTime: formModel.value.startTime || '08:00',
    endTime: formModel.value.endTime || '09:00',
    rmk: formModel.value.rmk || '',
  }

  function applyCopyData() {
    formModel.value = {
      workId: null,
      workMidCd: copyData.workMidCd,
      workContent: copyData.workContent,
      workLocId: copyData.workLocId,
      siteNm: copyData.siteNm,
      startTime: copyData.startTime,
      endTime: copyData.endTime,
      statusCd: '',
      statusNm: '',
      rmk: copyData.rmk,
      syncGoogle: false,
      googleEventId: null,
    }
    selectedId.value = null
    isEditing.value = true
    activeTab.value = DAILY_TAB_WORK
    captureCleanState()
  }

  copyModalOpen.value = false
  isCopyMode.value = false

  // 이미 같은 날짜 페이지이면 watch가 안 트리거되므로 직접 loadDaily 후 복원
  if (targetDt === workDt.value) {
    await loadDaily()
    applyCopyData()
    return
  }

  // 다른 날짜: sessionStorage 저장 + push
  sessionStorage.setItem('__copy_form__', JSON.stringify(copyData))
  leaveGuardBypass.value = true
  await router.push({
    name: 'work-log-daily',
    params: { workDt: targetDt },
  })
}

function showToast(msg: string) {
  toastMessage.value = msg
  window.setTimeout(() => {
    if (toastMessage.value === msg) toastMessage.value = ''
  }, 2400)
}

function onPending(msg?: string) {
  showToast(msg || MSG_DETAIL_PENDING)
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

onBeforeRouteLeave((to) => {
  if (leaveGuardBypass.value) {
    leaveGuardBypass.value = false
    return true
  }
  if (saving.value) return false
  if (!hasUnsavedRegisteredData()) return true
  pendingLeaveTo = to
  leaveConfirmOpen.value = true
  return false
})

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
    cachedResources = []
    cachedExpenses = []
    cachedPesticides = []
    refreshSummaryCards()
    captureCleanState()
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
    removedResIds.value = []
    removedExpIds.value = []
    loadSideForWork(
      selectedId.value,
      cachedResources,
      cachedExpenses,
      cachedPesticides,
    )
    refreshSummaryCards()
  } catch {
    master.value = null
    sourceWorks.value = []
    workItems.value = []
    selectedId.value = null
    isEditing.value = true
    cachedResources = []
    cachedExpenses = []
    cachedPesticides = []
    refreshSummaryCards()
    showToast(MSG_LOAD_DAILY_FAILED)
  } finally {
    dailyLoading.value = false
    captureCleanState()
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
    const statusCd = isFuture.value
      ? STATUS_PREPARING_CD
      : formModel.value.statusCd || null
    const draft: WorkLogWorkUpsertItem = {
      work_id: formModel.value.workId,
      work_mid_cd: formModel.value.workMidCd,
      work_loc_id: formModel.value.workLocId || null,
      rmk: formModel.value.rmk || null,
      start_tm: formModel.value.startTime || null,
      end_tm: formModel.value.endTime || null,
      status_cd: statusCd,
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
  if (isFuture.value) {
    return valid.map((w) => ({ ...w, status_cd: STATUS_PREPARING_CD }))
  }
  return valid
}

/** 서버 채번(YYYYMMDD-SEQ)과 맞추기 — 인력/경비/농약 연결 대상 */
function resolveTargetWorkId(
  payload: WorkLogWorkUpsertItem[],
): string | null {
  if (selectedId.value) return String(selectedId.value)
  if (formModel.value.workId) return String(formModel.value.workId)
  // 신규 폼(미채번): body.works 열거 인덱스와 동일한 임시 ID
  if (showForm.value) {
    const idx = payload.findIndex((w) => !w.work_id)
    if (idx >= 0) {
      const ymd = workDt.value.replace(/-/g, '')
      if (/^\d{8}$/.test(ymd)) {
        return `${ymd}-${String(idx + 1).padStart(2, '0')}`
      }
    }
  }
  const first = payload[0]?.work_id
  return first ? String(first) : null
}

function sameWorkId(
  a: string | null | undefined,
  b: string | null | undefined,
): boolean {
  if (a == null && b == null) return true
  if (a == null || b == null) return false
  return String(a) === String(b)
}

async function loadGoogleStatus() {
  try {
    googleStatus.value = await fetchGoogleCalendarStatus(farmCd.value)
  } catch {
    googleStatus.value = { configured: false, connected: false }
  }
}

async function maybePushGoogleAfterSave(
  workId: string | null | undefined,
  opts?: { shouldPush?: boolean },
): Promise<string | null> {
  if (!googleStatus.value?.connected) return null
  const wid = String(workId || '').trim()
  if (!wid) return null
  const shouldPush =
    opts?.shouldPush ??
    (formModel.value.syncGoogle || Boolean(formModel.value.googleEventId))
  if (!shouldPush) return null
  try {
    await pushWorkToGoogle(farmCd.value, wid)
    return '구글 캘린더에 반영했습니다.'
  } catch (err) {
    return err instanceof ApiClientError
      ? err.message
      : '구글 반영에 실패했습니다.'
  }
}

/** loadDaily 이후 · 저장 응답/폼 힌트로 push 대상 확정 (selectedId=첫 카드 오인 방지) */
function resolvePushWorkIdAfterSave(
  idsBefore: Set<string>,
  saveWorkIds: string[] | undefined,
  hint: {
    workId: string | null
    workMidCd: string
    startTime: string
    endTime: string
    rmk: string
  },
): string | null {
  const prev = String(hint.workId || '').trim()
  if (prev) return prev
  const saved = (saveWorkIds || []).map((id) => String(id || '').trim()).filter(Boolean)
  const created = saved.filter((id) => !idsBefore.has(id))
  const pool = created.length > 0 ? created : saved
  if (pool.length === 1) return pool[0] || null

  const mid = String(hint.workMidCd || '').trim()
  const start = String(hint.startTime || '').slice(0, 5)
  const end = String(hint.endTime || '').slice(0, 5)
  const rmk = String(hint.rmk || '').trim()
  const candidates = sourceWorks.value.filter((w) => pool.includes(String(w.work_id)))
  const matched = (candidates.length ? candidates : sourceWorks.value).find((w) => {
    if (mid && String(w.work_mid_cd || '').trim() !== mid) return false
    if (start && String(w.start_tm || '').slice(0, 5) !== start) return false
    if (end && String(w.end_tm || '').slice(0, 5) !== end) return false
    if (rmk && String(w.rmk || '').trim() !== rmk) return false
    return true
  })
  if (matched?.work_id) return String(matched.work_id)
  return pool[pool.length - 1] || null
}

async function onPushGoogleNow() {
  const wid = String(formModel.value.workId || selectedId.value || '').trim()
  if (!wid) {
    showToast('먼저 작업을 저장한 뒤 보내 주세요.')
    return
  }
  try {
    await pushWorkToGoogle(farmCd.value, wid)
    await loadDaily()
    const w = sourceWorks.value.find((it) => it.work_id === wid)
    if (w) {
      formModel.value = {
        ...formModel.value,
        googleEventId: String(w.google_event_id || '') || null,
        syncGoogle: false,
      }
    }
    showToast('구글 캘린더에 반영했습니다.')
  } catch (err) {
    const msg =
      err instanceof ApiClientError ? err.message : '구글 반영에 실패했습니다.'
    showToast(msg)
  }
}

function openWorkForEdit(workId: string) {
  const w = sourceWorks.value.find((it) => it.work_id === workId)
  if (!w) return
  clearCopyMode()
  selectedId.value = workId
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
    syncGoogle: false,
    googleEventId: String(w.google_event_id || '') || null,
  }
  isEditing.value = true
  activeTab.value = DAILY_TAB_WORK
  loadSideForWork(workId, cachedResources, cachedExpenses, cachedPesticides)
  captureCleanState()
}

async function onImportGoogle() {
  await loadGoogleStatus()
  if (!googleStatus.value?.configured) {
    showToast('서버에 구글 연동 설정이 없습니다.')
    return
  }
  if (!googleStatus.value?.connected) {
    showToast(MSG_GOOGLE_IMPORT_NEED_CONNECT)
    await onGoogleConnect()
    return
  }
  googleImportOpen.value = true
  googleImportLoading.value = true
  googleImportMessage.value = ''
  googleImportItems.value = []
  try {
    const res = await fetchGoogleImportPreview(farmCd.value, workDt.value)
    googleImportItems.value = res.items || []
    googleImportMessage.value =
      res.message ||
      (googleImportItems.value.length ? '' : MSG_GOOGLE_IMPORT_EMPTY)
  } catch (err) {
    googleImportItems.value = []
    googleImportMessage.value =
      err instanceof ApiClientError
        ? err.message
        : '구글 일정을 불러오지 못했습니다.'
  } finally {
    googleImportLoading.value = false
  }
}

async function onGoogleConnect() {
  try {
    const successRedirect = `${window.location.origin}/work-log`
    const res = await requestGoogleCalendarAuthUrl(farmCd.value, successRedirect)
    if (res.auth_url) {
      window.location.href = res.auth_url
      return
    }
    showToast('구글 인증 주소를 받지 못했습니다.')
  } catch (err) {
    const msg =
      err instanceof ApiClientError
        ? err.message
        : '구글 연결을 시작하지 못했습니다.'
    showToast(msg)
  }
}

async function onGoogleImportItemClick(it: GoogleImportPreviewItem) {
  if (googleImportBusy.value) return
  googleImportBusy.value = true
  try {
    if (it.already_linked && it.linked_work_id) {
      googleImportOpen.value = false
      await loadDaily()
      openWorkForEdit(it.linked_work_id)
      showToast(MSG_GOOGLE_IMPORT_SAVED)
      return
    }
    const defaultMid =
      workOptions.value[0]?.value ||
      String(sourceWorks.value[0]?.work_mid_cd || '') ||
      'WK010100'
    const res = await confirmGoogleImport(farmCd.value, {
      google_event_id: it.google_event_id,
      work_dt: it.work_dt || workDt.value,
      kind: 'work',
      title: it.title,
      description: it.description,
      start_tm: it.start_tm,
      end_tm: it.end_tm,
      work_mid_cd: defaultMid,
      work_loc_id: null,
      work_id: it.linked_work_id,
      status_cd: isFuture.value ? STATUS_PREPARING_CD : undefined,
    })
    googleImportOpen.value = false
    await loadDaily()
    if (res.kind === 'work' && res.work_id) {
      openWorkForEdit(res.work_id)
      showToast(MSG_GOOGLE_IMPORT_SAVED)
      return
    }
    showToast('구글 일정을 반영했습니다.')
  } catch (err) {
    const msg =
      err instanceof ApiClientError
        ? err.message
        : '구글 일정 가져오기에 실패했습니다.'
    showToast(msg)
  } finally {
    googleImportBusy.value = false
  }
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

/** 임시저장: 작업만 · 저장하기: 통합(Ledger+농약 확정) · 복사: 기본정보만 */
async function onSave(
  mode: 'draft' | 'final',
  opts?: { navigateTo?: RouteLocationNormalized },
): Promise<boolean> {
  if (isCopyMode.value) {
    return saveCopiedWork(mode, opts)
  }
  if (isFuture.value && mode === 'final') {
    showToast(MSG_FUTURE_DETAIL_LOCKED)
    return false
  }
  const payload = buildWorksPayload()
  if (!payload) return false
  saving.value = true
  try {
    if (mode === 'draft') {
      if (!isFuture.value) {
        await persistMasterIfNeeded()
      }
      const wantSync =
        formModel.value.syncGoogle || Boolean(formModel.value.googleEventId)
      const pushHint = {
        workId: formModel.value.workId,
        workMidCd: formModel.value.workMidCd,
        startTime: formModel.value.startTime,
        endTime: formModel.value.endTime,
        rmk: formModel.value.rmk,
      }
      const idsBefore = new Set(
        sourceWorks.value.map((w) => String(w.work_id || '').trim()).filter(Boolean),
      )
      const saveRes = await saveWorkLogWorks(farmCd.value, workDt.value, {
        works: payload,
      })
      await loadDaily()
      const pushedId = resolvePushWorkIdAfterSave(
        idsBefore,
        saveRes.work_ids,
        pushHint,
      )
      let googleMsg: string | null = null
      if (wantSync) {
        if (!pushedId) {
          googleMsg = '저장은 됐으나 구글 반영 대상을 찾지 못했습니다.'
        } else {
          googleMsg = await maybePushGoogleAfterSave(pushedId, {
            shouldPush: true,
          })
        }
      }
      showToast(googleMsg || MSG_DRAFT_OK)
      return true
    }

    const laborWorkId = resolveTargetWorkId(payload)
    const isTargetWork = (w: WorkLogWorkUpsertItem) =>
      sameWorkId(w.work_id, laborWorkId) ||
      (!!laborWorkId && !w.work_id && showForm.value)

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
      works: payload.map((w) => {
        const attachSide = isTargetWork(w)
        return {
          ...w,
          // 신규 행에 서버와 동일한 work_id를 미리 넣어 SELECTED_WORK 검증·농약 연결 일치
          work_id: w.work_id || (attachSide ? laborWorkId : w.work_id),
          work_mid_nm:
            workOptions.value.find((o) => o.value === w.work_mid_cd)?.label ||
            null,
          replace_pesticide_use_id: attachSide
            ? pesticideReplaceUseId.value
            : null,
          pesticide_lines: attachSide
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
    const wantSync =
      formModel.value.syncGoogle || Boolean(formModel.value.googleEventId)
    const pushHint = {
      workId: laborWorkId || formModel.value.workId,
      workMidCd: formModel.value.workMidCd,
      startTime: formModel.value.startTime,
      endTime: formModel.value.endTime,
      rmk: formModel.value.rmk,
    }
    const idsBefore = new Set(
      sourceWorks.value.map((w) => String(w.work_id || '').trim()).filter(Boolean),
    )
    await saveWorkLogIntegrated(farmCd.value, workDt.value, integrated)
    for (const row of pesticideRows.value) {
      if (row.purpose?.trim()) {
        rememberRecentPurpose(farmCd.value, row.purpose.trim())
      }
    }
    removedResIds.value = []
    removedExpIds.value = []
    pesticideReplaceUseId.value = null
    await loadDaily()
    const pushedId = resolvePushWorkIdAfterSave(
      idsBefore,
      [laborWorkId || ''].filter(Boolean),
      pushHint,
    )
    const googleMsg = await maybePushGoogleAfterSave(pushedId || laborWorkId, {
      shouldPush: wantSync,
    })
    showToast(googleMsg || MSG_SAVE_OK)
    if (opts?.navigateTo) {
      leaveGuardBypass.value = true
      void router.push(opts.navigateTo.fullPath || opts.navigateTo)
    } else {
      leaveGuardBypass.value = true
      window.setTimeout(() => goBack(), 600)
    }
    return true
  } catch (err) {
    const msg =
      err instanceof ApiClientError && err.message
        ? err.message
        : MSG_SAVE_FAILED
    showToast(msg)
    return false
  } finally {
    saving.value = false
  }
}

function buildCopyDraftItem(): WorkLogWorkUpsertItem | null {
  if (!formModel.value.workMidCd) {
    showToast(MSG_WORK_CONTENT_REQUIRED)
    return null
  }
  return {
    work_id: null,
    work_mid_cd: formModel.value.workMidCd,
    work_loc_id: formModel.value.workLocId || null,
    rmk: formModel.value.rmk || null,
    start_tm: formModel.value.startTime || null,
    end_tm: formModel.value.endTime || null,
    status_cd: formModel.value.statusCd || null,
  }
}

/** 복사 저장: 기본정보만 · 대상일 기존 작업 유지 후 신규 추가 */
async function saveCopiedWork(
  mode: 'draft' | 'final',
  opts?: { navigateTo?: RouteLocationNormalized },
): Promise<boolean> {
  const targetDt = String(copyTargetDt.value || '').trim()
  if (!/^\d{4}-\d{2}-\d{2}$/.test(targetDt)) {
    showToast(MSG_COPY_DATE_INVALID)
    return false
  }
  const draft = buildCopyDraftItem()
  if (!draft) return false
  if (isFutureDate(targetDt)) {
    draft.status_cd = STATUS_PREPARING_CD
    if (mode === 'final') {
      showToast(MSG_FUTURE_DETAIL_LOCKED)
      return false
    }
  }

  saving.value = true
  try {
    if (targetDt === workDt.value) {
      goLaborAfterCopy.value = false
      const idsBefore = new Set(
        sourceWorks.value
          .map((w) => String(w.work_id || '').trim())
          .filter(Boolean),
      )
      const payload = buildWorksPayload()
      if (!payload) return false
      const res = await saveWorkLogWorks(farmCd.value, workDt.value, {
        works: payload,
      })
      clearCopyMode()
      const createdId =
        (res?.work_ids || []).find((id) => id && !idsBefore.has(id)) ||
        (res?.work_ids || [])[0] ||
        null
      copyCreatedWorkId.value = createdId
      await loadDaily()
      if (createdId) {
        selectedId.value = createdId
        isEditing.value = false
        activeTab.value = DAILY_TAB_LABOR
        loadSideForWork(
          createdId,
          cachedResources,
          cachedExpenses,
          cachedPesticides,
        )
        copyCreatedWorkId.value = null
      } else {
        activeTab.value = DAILY_TAB_LABOR
      }
      showToast(mode === 'draft' ? MSG_DRAFT_OK : MSG_COPY_OK)
      if (opts?.navigateTo) {
        leaveGuardBypass.value = true
        void router.push(opts.navigateTo.fullPath || opts.navigateTo)
      }
      return true
    }

    const daily = await fetchWorkLogDaily(farmCd.value, targetDt)
    const existingIds = new Set(
      (daily.works || [])
        .map((w) => String(w.work_id || '').trim())
        .filter(Boolean),
    )
    const works = (daily.works || []).map(toUpsertItem)
    works.push(draft)
    const res = await saveWorkLogWorks(farmCd.value, targetDt, { works })
    clearCopyMode()
    const createdId =
      (res?.work_ids || []).find((id) => id && !existingIds.has(id)) ||
      (res?.work_ids || [])[0] ||
      null
    copyCreatedWorkId.value = createdId
    goLaborAfterCopy.value = true
    showToast(mode === 'draft' ? MSG_DRAFT_OK : MSG_COPY_OK)
    leaveGuardBypass.value = true
    if (opts?.navigateTo) {
      void router.push(opts.navigateTo.fullPath || opts.navigateTo)
    } else {
      await router.push({
        name: 'work-log-daily',
        params: { workDt: targetDt },
      })
    }
    return true
  } catch (err) {
    const msg =
      err instanceof ApiClientError && err.message
        ? err.message
        : MSG_SAVE_FAILED
    showToast(msg)
    return false
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
  // 수정 진입만 — API/재고/DB 변경 없음(저장 시에만 replace)
  pesticideReplaceUseId.value = pesticideUseId.value
  showToast('수정 모드: 저장 시 기존 사용이 교체됩니다.')
}

defineExpose({
  onEditPesticide,
  onCancelPesticide,
  pesticideReplaceUseId,
  pesticideUseId,
  pesticideAppliedYn,
})

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

watch(workDt, async () => {
  clearCopyMode()
  await loadDaily()
  // 복사 적용 이동: sessionStorage에 저장된 복사 데이터가 있으면 폼에 복원
  const raw = sessionStorage.getItem('__copy_form__')
  if (raw) {
    sessionStorage.removeItem('__copy_form__')
    try {
      const snap = JSON.parse(raw)
      formModel.value = {
        workId: null,
        workMidCd: String(snap.workMidCd || ''),
        workContent: String(snap.workContent || ''),
        workLocId: String(snap.workLocId || ''),
        siteNm: String(snap.siteNm || ''),
        startTime: String(snap.startTime || '08:00'),
        endTime: String(snap.endTime || '09:00'),
        statusCd: '',
        statusNm: '',
        rmk: String(snap.rmk || ''),
        syncGoogle: false,
        googleEventId: null,
      }
      selectedId.value = null
      isEditing.value = true
      activeTab.value = DAILY_TAB_WORK
      captureCleanState()
    } catch {
      // 파싱 실패 시 무시
    }
  }
  if (goLaborAfterCopy.value) {
    activeTab.value = DAILY_TAB_LABOR
    if (copyCreatedWorkId.value) {
      selectedId.value = copyCreatedWorkId.value
      isEditing.value = false
      loadSideForWork(
        copyCreatedWorkId.value,
        cachedResources,
        cachedExpenses,
        cachedPesticides,
      )
      copyCreatedWorkId.value = null
    }
    goLaborAfterCopy.value = false
  }
})

onMounted(async () => {
  if (!farm.value) {
    await store.refreshAll()
  }
  await Promise.all([loadDaily(), loadPickOptions(), loadGoogleStatus()])
  if (String(route.query.new || '') === HOME_DAILY_NEW_QUERY) {
    onAddWork()
    void router.replace({
      name: 'work-log-daily',
      params: { workDt: workDt.value },
      query: {},
    })
  }
})
</script>

<template>
  <div class="page">
    <main class="content ods-page-content">
      <OdsAppBar show-back back-fallback="work-log" />

      <p v-if="isFuture" class="warn" role="alert">{{ MSG_FUTURE_WORK_LOG }}</p>

      <WorkLogDailyDateBar :work-dt="workDt" @go-today="goToday" />

      <WorkLogDailyWeatherStrip :master="master" :loading="dailyLoading" />

      <WorkLogDailyTimeline
        :items="workItems"
        :selected-id="selectedId"
        @select="onSelectTimeline"
        @add="onAddWork"
        @import-google="onImportGoogle"
      />

      <WorkLogDailyWorkForm
        v-if="showForm && !copyModalOpen && !isCopyMode"
        v-model="formModel"
        v-model:active-tab="activeTab"
        v-model:labor-rows="laborRows"
        v-model:expense-rows="expenseRows"
        v-model:pesticide-rows="pesticideRows"
        v-model:copy-work-dt="copyTargetDt"
        :copy-mode="isCopyMode"
        :detail-locked="isFuture"
        :work-options="workOptions"
        :site-options="siteOptions"
        :status-options="statusOptions"
        :work-dt="workDt"
        :farm-cd="farmCd"
        :stock-applied-yn="pesticideAppliedYn"
        :editing-replace="!!pesticideReplaceUseId"
        :google-configured="!!googleStatus?.configured"
        :google-connected="!!googleStatus?.connected"
        @pending="onPending"
        @cancel-pesticide="onCancelPesticide"
        @edit-pesticide="onEditPesticide"
        @remove-labor-res="onRemoveLaborRes"
        @remove-expense-exp="onRemoveExpenseExp"
        @push-google="onPushGoogleNow"
        @connect-google="onGoogleConnect"
      />
      <WorkLogDailyWorkCard
        v-else-if="selectedItem && !copyModalOpen"
        v-model:active-tab="activeTab"
        v-model:labor-rows="laborRows"
        v-model:expense-rows="expenseRows"
        v-model:pesticide-rows="pesticideRows"
        :item="selectedItem"
        :work-dt="workDt"
        :farm-cd="farmCd"
        :detail-locked="isFuture"
        :stock-applied-yn="pesticideAppliedYn"
        :editing-replace="!!pesticideReplaceUseId"
        @edit="onEditSelected"
        @copy="onCopySelected"
        @pending="onPending"
        @cancel-pesticide="onCancelPesticide"
        @edit-pesticide="onEditPesticide"
        @remove-labor-res="onRemoveLaborRes"
        @remove-expense-exp="onRemoveExpenseExp"
      />

      <WorkLogDailySummary
        :cards="summaryCards"
        :empty="!hasWorks"
      />

      <WorkLogDailyExtras
        :work-dt="workDt"
        :farm-cd="farmCd"
      />
    </main>

    <div
      v-if="showForm && !copyModalOpen && !isCopyMode"
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
        v-if="!isFuture"
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
    <div v-else-if="!showForm" class="footer-actions" aria-label="저장·삭제">
      <OdsButton
        v-if="!isFuture"
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

    <Teleport to="body">
      <div
        v-if="copyModalOpen"
        class="workcopy-modal"
        role="dialog"
        aria-modal="true"
        aria-label="작업 복사"
      >
        <button
          type="button"
          class="workcopy-modal__backdrop"
          aria-label="닫기"
          @click="onCancelCopyModal"
        />
        <div class="workcopy-modal__panel">
          <header class="workcopy-modal__head">
            <h3 class="workcopy-modal__title">작업 복사</h3>
            <button
              type="button"
              class="workcopy-modal__close"
              aria-label="닫기"
              @click="onCancelCopyModal"
            >✕</button>
          </header>

          <div class="workcopy-modal__body">
            <WorkLogDailyWorkForm
              v-model="formModel"
              v-model:active-tab="activeTab"
              v-model:labor-rows="laborRows"
              v-model:expense-rows="expenseRows"
              v-model:pesticide-rows="pesticideRows"
              v-model:copy-work-dt="copyTargetDt"
              :copy-mode="isCopyMode"
              :copy-date-fixed="false"
              :inline-pick="true"
              :detail-locked="isFuture"
              :work-options="workOptions"
              :site-options="siteOptions"
              :status-options="statusOptions"
              :work-dt="workDt"
              :farm-cd="farmCd"
              :stock-applied-yn="pesticideAppliedYn"
              :editing-replace="!!pesticideReplaceUseId"
              :google-configured="!!googleStatus?.configured"
              :google-connected="!!googleStatus?.connected"
              @pending="onPending"
              @cancel-pesticide="onCancelPesticide"
              @edit-pesticide="onEditPesticide"
              @remove-labor-res="onRemoveLaborRes"
              @remove-expense-exp="onRemoveExpenseExp"
              @push-google="onPushGoogleNow"
              @connect-google="onGoogleConnect"
            />
          </div>

          <div class="workcopy-modal__actions" aria-label="작업 복사">
            <button
              type="button"
              class="workcopy-modal__btn workcopy-modal__btn--cancel"
              @click="onCancelCopyModal"
            >
              취소
            </button>
            <button
              type="button"
              class="workcopy-modal__btn workcopy-modal__btn--apply"
              @click="onCopyModalApply"
            >
              적용
            </button>
          </div>
        </div>
      </div>
    </Teleport>


    <Teleport to="body">
      <div
        v-if="googleImportOpen"
        class="gimport"
        role="dialog"
        aria-modal="true"
        aria-label="구글 일정 불러오기"
      >
        <button
          type="button"
          class="gimport__backdrop"
          aria-label="닫기"
          @click="googleImportOpen = false"
        />
        <div class="gimport__panel">
          <header class="gimport__head">
            <h3 class="gimport__title">구글 일정 불러오기</h3>
            <button type="button" class="gimport__x" @click="googleImportOpen = false">
              닫기
            </button>
          </header>
          <div class="gimport__body">
            <p v-if="googleImportLoading" class="gimport__empty">불러오는 중…</p>
            <p v-else-if="!googleImportItems.length" class="gimport__empty">
              {{ googleImportMessage || MSG_GOOGLE_IMPORT_EMPTY }}
            </p>
            <ul v-else class="gimport__list">
              <li
                v-for="it in googleImportItems"
                :key="it.google_event_id"
                class="gimport__item"
              >
                <button
                  type="button"
                  class="gimport__btn"
                  :disabled="googleImportBusy"
                  @click="onGoogleImportItemClick(it)"
                >
                  <span class="gimport__name">{{ it.title }}</span>
                  <span class="gimport__meta">
                    <template v-if="it.start_tm">{{ it.start_tm }}</template>
                    <template v-if="it.end_tm"> ~ {{ it.end_tm }}</template>
                    <template v-if="it.already_linked"> · 이미 연동됨</template>
                    <template v-else>
                      · 영농일지로 저장
                    </template>
                  </span>
                  <span v-if="it.description" class="gimport__desc">{{ it.description }}</span>
                </button>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </Teleport>

    <div
      v-if="leaveConfirmOpen"
      class="leave-confirm"
      role="dialog"
      aria-modal="true"
      :aria-label="MSG_UNSAVED_LEAVE_CONFIRM"
    >
      <button
        type="button"
        class="leave-confirm__backdrop"
        aria-label="닫기"
        @click="onLeaveConfirmStay"
      />
      <div class="leave-confirm__card">
        <p class="leave-confirm__msg">{{ MSG_UNSAVED_LEAVE_CONFIRM }}</p>
        <div class="leave-confirm__actions">
          <button
            type="button"
            class="leave-confirm__btn leave-confirm__btn--primary"
            :disabled="saving"
            @click.stop="onLeaveConfirmSave"
          >
            {{ BTN_UNSAVED_LEAVE_SAVE }}
          </button>
          <button
            type="button"
            class="leave-confirm__btn leave-confirm__btn--secondary"
            :disabled="saving"
            @click.stop="onLeaveConfirmDiscard"
          >
            {{ BTN_UNSAVED_LEAVE_DISCARD }}
          </button>
          <button
            type="button"
            class="leave-confirm__btn leave-confirm__btn--ghost"
            :disabled="saving"
            @click.stop="onLeaveConfirmStay"
          >
            {{ BTN_UNSAVED_LEAVE_STAY }}
          </button>
        </div>
      </div>
    </div>

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
  /* padding/max-width/gap -> .ods-page-content (AppBar SSOT) */
}

.warn {
  margin: 0;
  padding: var(--ods-space-12);
  border-radius: var(--ods-radius-button);
  background: color-mix(in srgb, var(--ods-color-caution) 18%, transparent);
  color: var(--ods-color-text);
  font: var(--ods-font-form-help);
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
  max-width: var(--ods-page-content-max, 480px);
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
  min-height: var(--ods-button-height);
}
.footer-btn--outline :deep(.ods-btn),
.footer-actions :deep(.footer-btn--outline) {
  background: var(--ods-color-white);
  border: 2px solid var(--ods-color-primary);
  color: var(--ods-color-primary);
}
.footer-btn__inner {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--ods-space-8);
}
.footer-btn__inner img {
  width: var(--ods-icon-lg);
  height: var(--ods-icon-lg);
}

.toast {
  position: fixed;
  left: 50%;
  bottom: calc(150px + env(safe-area-inset-bottom));
  transform: translateX(-50%);
  z-index: 90;
  max-width: min(420px, calc(100vw - var(--ods-hit-sm)));
  margin: 0;
  padding: var(--ods-space-12) var(--ods-space-16);
  border-radius: var(--ods-radius-button);
  background: color-mix(in srgb, var(--ods-color-gray-900) 92%, transparent);
  color: var(--ods-color-white);
  font: var(--ods-font-form-help);
  font-weight: 600;
  text-align: center;
  box-shadow: var(--ods-shadow-card);
}

.leave-confirm {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--ods-space-16);
}
.leave-confirm__backdrop {
  position: absolute;
  inset: 0;
  border: 0;
  padding: 0;
  margin: 0;
  background: color-mix(in srgb, var(--ods-color-gray-900) 45%, transparent);
  cursor: pointer;
}
.leave-confirm__card {
  position: relative;
  z-index: 1;
  width: min(360px, 100%);
  padding: var(--ods-space-20) var(--ods-space-16);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  box-shadow: var(--ods-shadow-card);
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-16);
}
.leave-confirm__msg {
  margin: 0;
  font: var(--ods-font-body-1);
  font-weight: 600;
  color: var(--ods-color-text);
  text-align: center;
  line-height: 1.45;
}
.leave-confirm__actions {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
}
.leave-confirm__btn {
  width: 100%;
  min-height: var(--ods-button-height);
  border-radius: var(--ods-radius-button);
  font: var(--ods-font-form-value);
  font-weight: 700;
  cursor: pointer;
}
.leave-confirm__btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.leave-confirm__btn--primary {
  border: 0;
  background: var(--ods-color-primary);
  color: var(--ods-color-white);
}
.leave-confirm__btn--secondary {
  border: 2px solid var(--ods-color-primary);
  background: var(--ods-color-white);
  color: var(--ods-color-primary);
}
.leave-confirm__btn--ghost {
  border: 0;
  background: transparent;
  color: var(--ods-color-gray-700);
  font-weight: 600;
}

.workcopy-modal {
  position: fixed;
  inset: 0;
  z-index: 85;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--ods-space-16);
}

.workcopy-modal__backdrop {
  position: absolute;
  inset: 0;
  border: 0;
  padding: 0;
  margin: 0;
  background: color-mix(in srgb, var(--ods-color-gray-900) 45%, transparent);
  cursor: pointer;
}

.workcopy-modal__panel {
  position: relative;
  z-index: 1;
  width: min(520px, 100%);
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-bg-muted);
  box-shadow: var(--ods-shadow-card);
  overflow: hidden;
}

.workcopy-modal__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--ods-space-14) var(--ods-space-16);
  border-bottom: 1px solid var(--ods-color-border);
  background: var(--ods-color-white);
  flex-shrink: 0;
}

.workcopy-modal__title {
  margin: 0;
  font: var(--ods-font-headline);
  color: var(--ods-color-text);
}

.workcopy-modal__close {
  border: 0;
  background: transparent;
  color: var(--ods-color-text-secondary);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 4px;
}

.workcopy-modal__body {
  flex: 1 1 auto;
  overflow-y: auto;
  padding: var(--ods-space-12);
  -webkit-overflow-scrolling: touch;
  position: relative;
}

.workcopy-modal__actions {
  flex-shrink: 0;
  display: flex;
  gap: var(--ods-space-8);
  padding: var(--ods-space-12) var(--ods-space-16);
  border-top: 1px solid var(--ods-color-border);
  background: var(--ods-color-white);
}

.workcopy-modal__btn {
  flex: 1;
  min-height: var(--ods-button-height);
  border-radius: var(--ods-radius-button);
  font: var(--ods-font-form-value);
  font-weight: 700;
  cursor: pointer;
  border: 0;
}

.workcopy-modal__btn--cancel {
  background: var(--ods-color-white);
  border: 2px solid var(--ods-color-border);
  color: var(--ods-color-text-secondary);
}

.workcopy-modal__btn--apply {
  background: var(--ods-color-primary);
  color: var(--ods-color-white);
}

.copy-confirm {
  position: fixed;
  inset: 0;
  z-index: 86;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--ods-space-16);
}

.copy-confirm__backdrop {
  position: absolute;
  inset: 0;
  border: 0;
  padding: 0;
  margin: 0;
  background: color-mix(in srgb, var(--ods-color-gray-900) 45%, transparent);
  cursor: pointer;
}

.copy-confirm__card {
  position: relative;
  z-index: 1;
  width: min(380px, 100%);
  padding: var(--ods-space-20) var(--ods-space-16);
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  box-shadow: var(--ods-shadow-card);
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-16);
}

.copy-confirm__title {
  margin: 0;
  font: var(--ods-font-body-1);
  font-weight: 800;
  color: var(--ods-color-text);
  text-align: center;
}

.copy-confirm__msg {
  margin: 0;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
  line-height: 1.5;
}

.copy-confirm__actions {
  display: flex;
  gap: var(--ods-space-8);
}

.copy-confirm__btn {
  flex: 1;
  min-height: var(--ods-button-height);
  border-radius: var(--ods-radius-button);
  font: var(--ods-font-form-value);
  font-weight: 700;
  cursor: pointer;
  border: 0;
}

.copy-confirm__btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.copy-confirm__btn--primary {
  background: var(--ods-color-primary);
  color: var(--ods-color-white);
}

.copy-confirm__btn--secondary {
  background: var(--ods-color-white);
  border: 2px solid var(--ods-color-primary);
  color: var(--ods-color-primary);
}

.gimport {
  position: fixed;
  inset: 0;
  z-index: 90;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}
.gimport__backdrop {
  position: absolute;
  inset: 0;
  border: 0;
  margin: 0;
  padding: 0;
  background: color-mix(in srgb, var(--ods-color-gray-900) 45%, transparent);
  cursor: pointer;
}
.gimport__panel {
  position: relative;
  z-index: 1;
  max-height: 75vh;
  display: flex;
  flex-direction: column;
  border-radius: var(--ods-radius-card) var(--ods-radius-card) 0 0;
  background: var(--ods-color-white);
  box-shadow: var(--ods-shadow-card);
}
.gimport__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--ods-space-12) var(--ods-space-16);
  border-bottom: 1px solid var(--ods-color-border);
}
.gimport__title {
  margin: 0;
  font: var(--ods-font-headline);
  color: var(--ods-color-text);
}
.gimport__x {
  border: 0;
  background: transparent;
  color: var(--ods-color-text-secondary);
  font: var(--ods-font-form-help);
  cursor: pointer;
}
.gimport__body {
  overflow: auto;
  padding: var(--ods-space-12) var(--ods-space-16) var(--ods-space-24);
}
.gimport__empty {
  margin: var(--ods-space-16) 0;
  text-align: center;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
}
.gimport__list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
}
.gimport__btn {
  width: 100%;
  text-align: left;
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  padding: var(--ods-space-12) var(--ods-space-16);
  background: var(--ods-color-gray-100);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
}
.gimport__btn:disabled {
  opacity: 0.6;
  cursor: wait;
}
.gimport__name {
  font: var(--ods-font-body-1);
  font-weight: 600;
  color: var(--ods-color-text);
}
.gimport__meta {
  font: var(--ods-font-card-help);
  color: var(--ods-color-text-secondary);
}
.gimport__desc {
  font: var(--ods-font-card-help);
  color: var(--ods-color-text-secondary);
  white-space: pre-wrap;
}
</style>
