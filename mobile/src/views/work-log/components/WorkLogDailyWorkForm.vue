<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import WorkLogDailyExpensePanel from '@/views/work-log/components/WorkLogDailyExpensePanel.vue'
import WorkLogDailyLaborPanel from '@/views/work-log/components/WorkLogDailyLaborPanel.vue'
import WorkLogDailyPesticidePanel from '@/views/work-log/components/WorkLogDailyPesticidePanel.vue'
import WorkLogDailyPickSheet from '@/views/work-log/components/WorkLogDailyPickSheet.vue'
import WorkLogDailyWorkPhotoPanel from '@/views/work-log/components/WorkLogDailyWorkPhotoPanel.vue'
import {
  DAILY_TAB_EXPENSE,
  DAILY_TAB_FERTILIZER,
  DAILY_TAB_LABOR,
  DAILY_TAB_PESTICIDE,
  DAILY_TAB_PHOTO,
  DAILY_TAB_WORK,
  DAILY_WORK_TABS,
  isDailyWorkTabEnabled,
  isFertilizerWork,
  isHarvestWork,
  isPesticideWork,
  LABEL_COPY_WORK_DT,
  LABEL_HARVEST_QTY,
  LABEL_HARVEST_VARIETY,
  LABEL_WORK_MEMO,
  LABEL_WORK_SITE,
  LABEL_WORK_TYPE,
  MSG_COPY_HINT,
  MSG_WORK_FORM_TIP,
  MSG_WORK_MEMO_GUIDE,
  PLACEHOLDER_SELECT,
  PLACEHOLDER_WORK_RMK,
  SUFFIX_HARVEST_BOX,
  type DailyShellExpenseRow,
  type DailyShellLaborRow,
  type DailyShellPesticideRow,
  type DailyWorkFormModel,
  type DailyWorkTabKey,
} from '@/views/work-log/workLogConstants'

export type DailyPickOption = { value: string; label: string }

const activeTab = defineModel<DailyWorkTabKey>('activeTab', { required: true })
const modelValue = defineModel<DailyWorkFormModel>({ required: true })
const laborRows = defineModel<DailyShellLaborRow[]>('laborRows', { default: () => [] })
const expenseRows = defineModel<DailyShellExpenseRow[]>('expenseRows', { default: () => [] })
const pesticideRows = defineModel<DailyShellPesticideRow[]>('pesticideRows', {
  default: () => [],
})

const props = defineProps<{
  workOptions: readonly DailyPickOption[]
  siteOptions: readonly DailyPickOption[]
  statusOptions: readonly DailyPickOption[]
  varietyOptions?: readonly DailyPickOption[]
  workDt?: string
  farmCd: string
  stockAppliedYn?: string
  editingReplace?: boolean
  /** 미래일: 인력·경비·농약·사진 탭 잠금 */
  detailLocked?: boolean
  googleConfigured?: boolean
  googleConnected?: boolean
  /** 작업 복사 모드 */
  copyMode?: boolean
  /** 작업복사 시 작업일을 고정(오늘) 표시 */
  copyDateFixed?: boolean
}>()

const copyWorkDt = defineModel<string>('copyWorkDt', { default: '' })

const emit = defineEmits<{
  pending: [message?: string]
  cancelPesticide: []
  editPesticide: []
  removeLaborRes: [resId: number]
  removeExpenseExp: [expId: number]
  pushGoogle: []
  connectGoogle: []
}>()

const isPestWork = computed(() =>
  isPesticideWork(modelValue.value.workMidCd, modelValue.value.workContent),
)

const isFertWork = computed(() =>
  isFertilizerWork(modelValue.value.workMidCd, modelValue.value.workContent),
)

const isHarvest = computed(() =>
  isHarvestWork(modelValue.value.workMidCd, modelValue.value.workContent),
)

const visibleTabs = computed(() =>
  props.detailLocked
    ? DAILY_WORK_TABS.filter((t) => t.key === DAILY_TAB_WORK)
    : DAILY_WORK_TABS,
)

function isTabEnabled(key: DailyWorkTabKey): boolean {
  if (props.detailLocked && key !== DAILY_TAB_WORK) return false
  return isDailyWorkTabEnabled(
    key,
    modelValue.value.workMidCd,
    modelValue.value.workContent,
  )
}

/** 작업구분 변경 시 비활성 탭에 머무르지 않음 (입력 행은 유지 → 유실 방지) */
watch(
  () => [modelValue.value.workMidCd, modelValue.value.workContent] as const,
  () => {
    if (!isTabEnabled(activeTab.value)) {
      activeTab.value = DAILY_TAB_WORK
    }
    if (!isHarvestWork(modelValue.value.workMidCd, modelValue.value.workContent)) {
      if (modelValue.value.varietyCd || modelValue.value.harvestContainerQty) {
        patch({ varietyCd: '', varietyNm: '', harvestContainerQty: '' })
      }
    }
  },
)

type PickKind = 'work' | 'site' | 'status' | 'variety' | null
const pickKind = ref<PickKind>(null)

const pickTitle = {
  work: LABEL_WORK_TYPE,
  site: LABEL_WORK_SITE,
  status: '상태',
  variety: LABEL_HARVEST_VARIETY,
} as const

const pickOptions = {
  get work() {
    return props.workOptions
  },
  get site() {
    return props.siteOptions
  },
  get status() {
    return props.statusOptions
  },
  get variety() {
    return props.varietyOptions || []
  },
}

function selectTab(key: DailyWorkTabKey) {
  if (!isTabEnabled(key)) return
  activeTab.value = key
}

function patch(partial: Partial<DailyWorkFormModel>) {
  modelValue.value = { ...modelValue.value, ...partial }
}

function openPick(kind: Exclude<PickKind, null>) {
  pickKind.value = kind
}

function closePick() {
  pickKind.value = null
}

function onPick(value: string, label: string) {
  if (pickKind.value === 'work') {
    patch({ workMidCd: value, workContent: label })
  } else if (pickKind.value === 'site') {
    patch({ workLocId: value, siteNm: label })
  } else if (pickKind.value === 'status') {
    patch({ statusCd: value, statusNm: label })
  } else if (pickKind.value === 'variety') {
    patch({ varietyCd: value, varietyNm: label })
  }
  closePick()
}

function onSelectPending(msg?: string) {
  emit('pending', msg)
}
</script>

<template>
  <section class="form" :aria-label="copyMode ? '작업 복사' : '작업 등록'">
    <div
      v-if="!copyMode"
      class="form__tabs"
      role="tablist"
      aria-label="작업 상세 탭"
    >
      <button
        v-for="tab in visibleTabs"
        :key="tab.key"
        type="button"
        role="tab"
        class="form__tab"
        :class="{
          'form__tab--on': activeTab === tab.key,
          'form__tab--disabled': !isTabEnabled(tab.key),
        }"
        :aria-selected="activeTab === tab.key"
        :aria-disabled="!isTabEnabled(tab.key)"
        :disabled="!isTabEnabled(tab.key)"
        @click="selectTab(tab.key)"
      >
        <img class="form__tab-ico" :src="tab.icon" alt="" />
        <span>{{ tab.label }}</span>
      </button>
    </div>
    <header v-else class="form__copy-head">
      <h3 class="form__copy-title">작업 복사</h3>
      <p class="form__copy-hint" role="note">{{ MSG_COPY_HINT }}</p>
    </header>

    <div :key="copyMode ? 'copy' : activeTab" class="form__body" role="tabpanel">
      <template v-if="copyMode || activeTab === DAILY_TAB_WORK">
        <label v-if="copyMode && !copyDateFixed" class="field">
          <span class="field__label">
            {{ LABEL_COPY_WORK_DT }}
            <span class="field__req" aria-hidden="true">*</span>
          </span>
          <input
            class="field__input"
            type="date"
            :value="copyWorkDt"
            @input="
              copyWorkDt = ($event.target as HTMLInputElement).value
            "
          />
        </label>
        <div v-else-if="copyMode" class="field field--fixed">
          <span class="field__label">{{ LABEL_COPY_WORK_DT }}</span>
          <p class="field__fixed-val">{{ copyWorkDt }}</p>
        </div>

        <div class="field-row">
          <label class="field field--half">
            <span class="field__label">
              {{ LABEL_WORK_TYPE }}
              <span class="field__req" aria-hidden="true">*</span>
            </span>
            <button type="button" class="field__select" @click="openPick('work')">
              <span :class="{ 'field__ph': !modelValue.workContent }">
                {{ modelValue.workContent || PLACEHOLDER_SELECT }}
              </span>
              <span class="field__chev" aria-hidden="true">›</span>
            </button>
          </label>
          <label class="field field--half">
            <span class="field__label">{{ LABEL_WORK_SITE }}</span>
            <button type="button" class="field__select" @click="openPick('site')">
              <span :class="{ 'field__ph': !modelValue.siteNm }">
                {{ modelValue.siteNm || PLACEHOLDER_SELECT }}
              </span>
              <span class="field__chev field__chev--down" aria-hidden="true">▾</span>
            </button>
          </label>
        </div>

        <div v-if="isHarvest" class="field-row">
          <label class="field field--half">
            <span class="field__label">
              {{ LABEL_HARVEST_VARIETY }}
              <span class="field__req" aria-hidden="true">*</span>
            </span>
            <button type="button" class="field__select" @click="openPick('variety')">
              <span :class="{ 'field__ph': !modelValue.varietyNm }">
                {{ modelValue.varietyNm || PLACEHOLDER_SELECT }}
              </span>
              <span class="field__chev" aria-hidden="true">›</span>
            </button>
          </label>
          <label class="field field--half">
            <span class="field__label">
              {{ LABEL_HARVEST_QTY }}
              <span class="field__req" aria-hidden="true">*</span>
            </span>
            <div class="field__qty">
              <input
                class="field__input"
                type="number"
                inputmode="numeric"
                min="1"
                step="1"
                :value="modelValue.harvestContainerQty"
                :aria-label="LABEL_HARVEST_QTY"
                @input="
                  patch({
                    harvestContainerQty: ($event.target as HTMLInputElement).value,
                  })
                "
              />
              <span class="field__qty-unit">{{ SUFFIX_HARVEST_BOX }}</span>
            </div>
          </label>
        </div>

        <div class="field">
          <span class="field__label">시작 / 종료</span>
          <div class="field__times">
            <input
              class="field__time"
              type="time"
              :value="modelValue.startTime"
              @input="
                patch({
                  startTime: ($event.target as HTMLInputElement).value,
                })
              "
            />
            <span class="field__tilde">~</span>
            <input
              class="field__time"
              type="time"
              :value="modelValue.endTime"
              @input="
                patch({
                  endTime: ($event.target as HTMLInputElement).value,
                })
              "
            />
          </div>
        </div>

        <label class="field">
          <span class="field__label">{{ LABEL_WORK_MEMO }}</span>
          <p class="field__guide" role="note">{{ MSG_WORK_MEMO_GUIDE }}</p>
          <textarea
            class="field__textarea"
            rows="5"
            :placeholder="PLACEHOLDER_WORK_RMK"
            :value="modelValue.rmk"
            @input="
              patch({
                rmk: ($event.target as HTMLTextAreaElement).value,
              })
            "
          />
        </label>

        <label v-if="!copyMode" class="field">
          <span class="field__label">상태</span>
          <button type="button" class="field__select" @click="openPick('status')">
            <span :class="{ 'field__ph': !modelValue.statusNm }">
              {{ modelValue.statusNm || PLACEHOLDER_SELECT }}
            </span>
            <span class="field__chev field__chev--down" aria-hidden="true">▾</span>
          </button>
        </label>

        <div v-if="!copyMode && googleConfigured" class="gcal-field">
          <p v-if="modelValue.googleEventId" class="gcal-field__badge">구글 연동됨</p>
          <p v-else class="gcal-field__badge gcal-field__badge--off">미연동</p>
          <label v-if="googleConnected" class="gcal-field__check">
            <input
              type="checkbox"
              :checked="modelValue.syncGoogle"
              @change="
                patch({
                  syncGoogle: ($event.target as HTMLInputElement).checked,
                })
              "
            >
            <span>구글 캘린더에 반영</span>
          </label>
          <button
            v-if="googleConnected && modelValue.workId && !modelValue.googleEventId"
            type="button"
            class="gcal-field__push"
            @click="emit('pushGoogle')"
          >
            구글로 보내기
          </button>
          <p v-else-if="!googleConnected" class="gcal-field__hint">
            구글 캘린더를 연결하면 보낼 수 있습니다.
            <button type="button" class="gcal-field__push" @click="emit('connectGoogle')">
              구글 캘린더 연결
            </button>
          </p>
        </div>

        <p v-if="!copyMode" class="form__tip" role="note">💡 {{ MSG_WORK_FORM_TIP }}</p>
      </template>

      <WorkLogDailyLaborPanel
        v-else-if="activeTab === DAILY_TAB_LABOR"
        v-model="laborRows"
        :farm-cd="farmCd"
        @pending="onSelectPending"
        @remove-saved="(id) => emit('removeLaborRes', id)"
      />
      <WorkLogDailyExpensePanel
        v-else-if="activeTab === DAILY_TAB_EXPENSE"
        v-model="expenseRows"
        :work-dt="workDt"
        :farm-cd="farmCd"
        @pending="onSelectPending"
        @remove-saved="(id) => emit('removeExpenseExp', id)"
      />
      <!-- 농약/비료 탭: 동일 패널 재사용 (mode만 분기). key로 탭 전환 시 인스턴스 분리 -->
      <WorkLogDailyPesticidePanel
        v-else-if="
          activeTab === DAILY_TAB_PESTICIDE || activeTab === DAILY_TAB_FERTILIZER
        "
        :key="activeTab"
        v-model="pesticideRows"
        :mode="
          activeTab === DAILY_TAB_FERTILIZER ? 'fertilizer' : 'pesticide'
        "
        :farm-cd="farmCd"
        :is-target-work="
          activeTab === DAILY_TAB_FERTILIZER ? isFertWork : isPestWork
        "
        :stock-applied-yn="stockAppliedYn"
        :editing-replace="editingReplace"
        @pending="onSelectPending"
        @cancel-use="emit('cancelPesticide')"
        @edit-begin="emit('editPesticide')"
      />
      <WorkLogDailyWorkPhotoPanel
        v-else-if="activeTab === DAILY_TAB_PHOTO"
        :farm-cd="farmCd"
        :work-id="modelValue.workId"
      />
    </div>

    <WorkLogDailyPickSheet
      :open="pickKind != null"
      :title="pickKind ? pickTitle[pickKind] : ''"
      :options="pickKind ? pickOptions[pickKind] : []"
      @close="closePick"
      @select="onPick"
    />
  </section>
</template>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
  padding: var(--ods-space-16);
  border-radius: var(--ods-radius-card-lg);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  box-shadow: var(--ods-shadow-card);
}

.form__copy-head {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
}

.form__copy-title {
  margin: 0;
  font: var(--ods-font-title-2);
  color: var(--ods-color-text);
}

.form__copy-hint {
  margin: 0;
  font: var(--ods-font-card-help);
  color: var(--ods-color-text-secondary);
  line-height: 1.45;
}

.form__tabs {
  display: flex;
  gap: 0;
  width: 100%;
  overflow-x: visible;
  border-bottom: 1px solid var(--ods-color-border);
}

.form__tab {
  flex: 1 1 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--ods-space-4);
  min-height: var(--ods-button-height);
  margin: 0 0 -1px;
  padding: var(--ods-space-8) var(--ods-space-4);
  border: none;
  border-bottom: 2px solid transparent;
  background: transparent;
  font: var(--ods-font-card-emphasis);
  color: var(--ods-color-text-secondary);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.form__tab--on {
  color: var(--ods-color-primary);
  font-weight: 700;
  border-bottom-color: var(--ods-color-primary);
}

.form__tab--disabled,
.form__tab:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  color: var(--ods-color-text-secondary);
  border-bottom-color: transparent;
}

.form__tab-ico {
  width: var(--ods-icon-lg);
  height: var(--ods-icon-lg);
  pointer-events: none;
}

.form__body {
  display: flex;
  flex-direction: column;
  gap: var(--ods-form-field-gap);
  min-height: calc(3 * var(--ods-control-height));
  min-width: 0;
  max-width: 100%;
  overflow-x: hidden;
}

.field {
  display: flex;
  flex-direction: column;
  gap: var(--ods-form-label-gap);
}

.field--fixed {
  gap: var(--ods-space-6);
}

.field__fixed-val {
  margin: 0;
  padding: var(--ods-space-10) var(--ods-space-12);
  border-radius: var(--ods-radius-sm, 8px);
  background: var(--ods-color-bg-muted);
  color: var(--ods-color-text-secondary);
  font: var(--ods-font-body-1);
  font-weight: 700;
}

.field-row {
  display: flex;
  align-items: stretch;
  gap: var(--ods-space-8);
  min-width: 0;
}

.field--half {
  flex: 1 1 0;
  min-width: 0;
}

.field__label {
  font: var(--ods-font-form-label);
  color: var(--ods-color-text-label, var(--ods-color-text));
}

.field__guide {
  margin: 0;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
  line-height: 1.4;
}

.field__req {
  color: var(--ods-color-danger);
}

.field__select,
.field__input,
.field__time,
.field__textarea {
  width: 100%;
  box-sizing: border-box;
  height: var(--ods-control-height);
  min-height: var(--ods-control-height);
  padding: 0 var(--ods-space-12);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-white);
  font: var(--ods-font-form-value);
  color: var(--ods-color-text);
}

.field__textarea {
  height: auto;
  min-height: calc(3 * var(--ods-control-height));
  padding: var(--ods-space-12);
  resize: vertical;
  line-height: 1.45;
  white-space: pre-wrap;
}

.field__select {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
  text-align: left;
  cursor: pointer;
}

.field__ph {
  color: var(--ods-color-text-secondary);
}

.field__chev {
  color: var(--ods-color-text-secondary);
  font: var(--ods-font-headline);
  line-height: 1;
}

.field__chev--down {
  font: var(--ods-font-card-section);
}

.field__times {
  display: flex;
  align-items: center;
  gap: var(--ods-space-8);
}

.field__qty {
  display: flex;
  align-items: center;
  gap: var(--ods-space-8);
}

.field__qty .field__input {
  flex: 1;
}

.field__qty-unit {
  flex-shrink: 0;
  font: var(--ods-font-form-value);
  color: var(--ods-color-text-secondary);
}

.field__time {
  flex: 1;
  min-width: 0;
}

.field__tilde {
  flex-shrink: 0;
  color: var(--ods-color-text-secondary);
}

.form__tip {
  margin: 0;
  padding: var(--ods-space-12);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-bg-muted);
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
  line-height: 1.4;
}

.gcal-field {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
  margin-top: var(--ods-space-8);
  padding: var(--ods-space-12);
  border-radius: var(--ods-radius-button);
  background: color-mix(in srgb, var(--ods-color-ai) 8%, white);
  border: 1px solid color-mix(in srgb, var(--ods-color-ai) 22%, var(--ods-color-gray-100));
}
.gcal-field__badge {
  margin: 0;
  font: var(--ods-font-card-help);
  font-weight: 600;
  color: var(--ods-color-ai);
}
.gcal-field__badge--off {
  color: var(--ods-color-text-secondary);
  font-weight: 500;
}
.gcal-field__check {
  display: flex;
  align-items: center;
  gap: var(--ods-space-8);
  font: var(--ods-font-form-help);
  color: var(--ods-color-text);
}
.gcal-field__push {
  align-self: flex-start;
  border: 0;
  background: transparent;
  color: var(--ods-color-ai);
  font: var(--ods-font-form-help);
  font-weight: 600;
  padding: 0;
  cursor: pointer;
}
.gcal-field__hint {
  margin: 0;
  font: var(--ods-font-card-help);
  color: var(--ods-color-text-secondary);
}

.form__pending {
  margin: 0;
  padding: var(--ods-space-20);
  text-align: center;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
  background: var(--ods-color-bg-muted);
  border-radius: var(--ods-radius-button);
}
</style>
