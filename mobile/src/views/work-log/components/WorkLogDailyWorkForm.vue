<script setup lang="ts">
import { computed, ref } from 'vue'

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
  isPesticideWork,
  LABEL_COPY_WORK_DT,
  MSG_COPY_HINT,
  MSG_FERTILIZER_PENDING,
  MSG_WORK_FORM_TIP,
  PLACEHOLDER_SELECT,
  PLACEHOLDER_WORK_RMK,
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
  workDt?: string
  farmCd: string
  stockAppliedYn?: string
  editingReplace?: boolean
  /** 작업 복사: 기본정보만 · 작업일 변경 가능 */
  copyMode?: boolean
}>()

const copyWorkDt = defineModel<string>('copyWorkDt', { default: '' })

const emit = defineEmits<{
  pending: []
  cancelPesticide: []
  editPesticide: []
  removeLaborRes: [resId: number]
  removeExpenseExp: [expId: number]
}>()

const isPestWork = computed(() =>
  isPesticideWork(modelValue.value.workMidCd, modelValue.value.workContent),
)

type PickKind = 'work' | 'site' | 'status' | null
const pickKind = ref<PickKind>(null)

const pickTitle = {
  work: '작업내용',
  site: '작업장소',
  status: '상태',
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
}

function selectTab(key: DailyWorkTabKey) {
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
  }
  closePick()
}

function onSelectPending() {
  emit('pending')
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
        v-for="tab in DAILY_WORK_TABS"
        :key="tab.key"
        type="button"
        role="tab"
        class="form__tab"
        :class="{ 'form__tab--on': activeTab === tab.key }"
        :aria-selected="activeTab === tab.key"
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
        <label v-if="copyMode" class="field">
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

        <label class="field">
          <span class="field__label">
            작업내용 <span class="field__req" aria-hidden="true">*</span>
          </span>
          <button type="button" class="field__select" @click="openPick('work')">
            <span :class="{ 'field__ph': !modelValue.workContent }">
              {{ modelValue.workContent || PLACEHOLDER_SELECT }}
            </span>
            <span class="field__chev" aria-hidden="true">›</span>
          </button>
        </label>

        <label class="field">
          <span class="field__label">작업장소</span>
          <button type="button" class="field__select" @click="openPick('site')">
            <span :class="{ 'field__ph': !modelValue.siteNm }">
              {{ modelValue.siteNm || PLACEHOLDER_SELECT }}
            </span>
            <span class="field__chev field__chev--down" aria-hidden="true">▾</span>
          </button>
        </label>

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
          <span class="field__label">상태</span>
          <button type="button" class="field__select" @click="openPick('status')">
            <span :class="{ 'field__ph': !modelValue.statusNm }">
              {{ modelValue.statusNm || PLACEHOLDER_SELECT }}
            </span>
            <span class="field__chev field__chev--down" aria-hidden="true">▾</span>
          </button>
        </label>

        <label class="field">
          <span class="field__label">비고</span>
          <input
            class="field__input"
            type="text"
            :placeholder="PLACEHOLDER_WORK_RMK"
            :value="modelValue.rmk"
            @input="
              patch({
                rmk: ($event.target as HTMLInputElement).value,
              })
            "
          />
        </label>

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
      <WorkLogDailyPesticidePanel
        v-else-if="activeTab === DAILY_TAB_PESTICIDE"
        v-model="pesticideRows"
        :farm-cd="farmCd"
        :is-pesticide-work="isPestWork"
        :stock-applied-yn="stockAppliedYn"
        :editing-replace="editingReplace"
        @pending="onSelectPending"
        @cancel-use="emit('cancelPesticide')"
        @edit-begin="emit('editPesticide')"
      />
      <p v-else-if="activeTab === DAILY_TAB_FERTILIZER" class="form__pending">
        {{ MSG_FERTILIZER_PENDING }}
      </p>
      <WorkLogDailyWorkPhotoPanel
        v-else-if="activeTab === DAILY_TAB_PHOTO"
        @pending="onSelectPending"
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
  font: var(--ods-font-caption);
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
  gap: 2px;
  min-height: 48px;
  margin: 0 0 -1px;
  padding: 8px 2px 10px;
  border: none;
  border-bottom: 2px solid transparent;
  background: transparent;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.form__tab--on {
  color: var(--ods-color-primary);
  font-weight: 700;
  border-bottom-color: var(--ods-color-primary);
}

.form__tab-ico {
  width: 18px;
  height: 18px;
  pointer-events: none;
}

.form__body {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
  min-height: 120px;
  min-width: 0;
  max-width: 100%;
  overflow-x: hidden;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field__label {
  font: var(--ods-font-caption);
  font-weight: 700;
  color: var(--ods-color-text);
}

.field__req {
  color: var(--ods-color-danger);
}

.field__select,
.field__input,
.field__time {
  width: 100%;
  box-sizing: border-box;
  min-height: 44px;
  padding: 0 12px;
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-white);
  font: var(--ods-font-body-2);
  color: var(--ods-color-text);
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
  font-size: 16px;
  line-height: 1;
}

.field__chev--down {
  font-size: 12px;
}

.field__times {
  display: flex;
  align-items: center;
  gap: var(--ods-space-8);
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
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
  line-height: 1.4;
}

.form__pending {
  margin: 0;
  padding: var(--ods-space-20);
  text-align: center;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
  background: var(--ods-color-bg-muted);
  border-radius: var(--ods-radius-button);
}
</style>
