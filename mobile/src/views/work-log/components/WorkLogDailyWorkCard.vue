<script setup lang="ts">
import { computed } from 'vue'

import iconCopy from '@/assets/ods/scr004/icon-copy.svg'
import iconEdit from '@/assets/ods/scr004/icon-edit.svg'
import iconFarm from '@/assets/ods/common/icon-farm.svg'
import WorkLogDailyExpensePanel from '@/views/work-log/components/WorkLogDailyExpensePanel.vue'
import WorkLogDailyLaborPanel from '@/views/work-log/components/WorkLogDailyLaborPanel.vue'
import WorkLogDailyPesticidePanel from '@/views/work-log/components/WorkLogDailyPesticidePanel.vue'
import WorkLogDailyWorkPhotoPanel from '@/views/work-log/components/WorkLogDailyWorkPhotoPanel.vue'
import {
  DAILY_TAB_EXPENSE,
  DAILY_TAB_FERTILIZER,
  DAILY_TAB_LABOR,
  DAILY_TAB_PESTICIDE,
  DAILY_TAB_PHOTO,
  DAILY_TAB_WORK,
  DAILY_WORK_TABS,
  formatDailyTimeRange,
  isPesticideWork,
  MSG_FERTILIZER_PENDING,
  type DailyShellExpenseRow,
  type DailyShellLaborRow,
  type DailyShellPesticideRow,
  type DailyTimelineItem,
  type DailyWorkTabKey,
} from '@/views/work-log/workLogConstants'

const props = defineProps<{
  item: DailyTimelineItem
  workDt?: string
  farmCd: string
  stockAppliedYn?: string
  editingReplace?: boolean
  detailLocked?: boolean
}>()

const activeTab = defineModel<DailyWorkTabKey>('activeTab', { required: true })
const laborRows = defineModel<DailyShellLaborRow[]>('laborRows', { default: () => [] })
const expenseRows = defineModel<DailyShellExpenseRow[]>('expenseRows', { default: () => [] })
const pesticideRows = defineModel<DailyShellPesticideRow[]>('pesticideRows', {
  default: () => [],
})

const emit = defineEmits<{
  edit: []
  copy: []
  pending: [message?: string]
  cancelPesticide: []
  editPesticide: []
  removeLaborRes: [resId: number]
  removeExpenseExp: [expId: number]
}>()

const timeRange = computed(() => formatDailyTimeRange(props.item))
const isPestWork = computed(() =>
  isPesticideWork(props.item.workMidCd || '', props.item.title),
)

const visibleTabs = computed(() =>
  props.detailLocked
    ? DAILY_WORK_TABS.filter((t) => t.key === DAILY_TAB_WORK)
    : DAILY_WORK_TABS,
)

function selectTab(key: DailyWorkTabKey) {
  if (props.detailLocked && key !== DAILY_TAB_WORK) return
  activeTab.value = key
}

function onPending(msg?: string) {
  emit('pending', msg)
}
</script>

<template>
  <section class="card" aria-label="선택 작업 상세">
    <header class="card__head">
      <div class="card__titles">
        <div class="card__title-row">
          <span class="card__badge">{{ item.statusLabel }}</span>
          <h3 class="card__title">{{ item.title }}</h3>
        </div>
        <p class="card__time">{{ timeRange }}</p>
        <div class="card__meta">
          <span class="card__meta-item">
            <img :src="iconFarm" alt="" />
            {{ item.location }}
          </span>
        </div>
      </div>
      <div class="card__actions">
        <button type="button" class="card__copy" @click="emit('copy')">
          <img :src="iconCopy" alt="" />
          작업 복사
        </button>
        <button type="button" class="card__edit" @click="emit('edit')">
          <img :src="iconEdit" alt="" />
          수정
        </button>
      </div>
    </header>

    <div class="card__tabs" role="tablist" aria-label="작업 상세 탭">
      <button
        v-for="tab in visibleTabs"
        :key="tab.key"
        type="button"
        role="tab"
        class="card__tab"
        :class="{ 'card__tab--on': activeTab === tab.key }"
        :aria-selected="activeTab === tab.key"
        @click="selectTab(tab.key)"
      >
        <img class="card__tab-ico" :src="tab.icon" alt="" />
        <span>{{ tab.label }}</span>
      </button>
    </div>

    <div :key="activeTab" class="card__body" role="tabpanel">
      <template v-if="activeTab === DAILY_TAB_WORK">
        <dl class="rows">
          <div class="row row--pair">
            <div class="row__col">
              <dt>작업구분</dt>
              <dd>{{ item.title }}</dd>
            </div>
            <div class="row__col">
              <dt>작업장소</dt>
              <dd>{{ item.location || '—' }}</dd>
            </div>
          </div>
          <div class="row">
            <dt>시작 / 종료</dt>
            <dd>{{ timeRange }}</dd>
          </div>
          <div class="row">
            <dt>메모</dt>
            <dd class="row__memo">{{ item.rmk || '—' }}</dd>
          </div>
          <div class="row">
            <dt>상태</dt>
            <dd>{{ item.statusLabel }}</dd>
          </div>
        </dl>
      </template>

      <WorkLogDailyLaborPanel
        v-else-if="activeTab === DAILY_TAB_LABOR"
        v-model="laborRows"
        :farm-cd="farmCd"
        @pending="onPending"
        @remove-saved="(id) => emit('removeLaborRes', id)"
      />
      <WorkLogDailyExpensePanel
        v-else-if="activeTab === DAILY_TAB_EXPENSE"
        v-model="expenseRows"
        :work-dt="workDt"
        :farm-cd="farmCd"
        @pending="onPending"
        @remove-saved="(id) => emit('removeExpenseExp', id)"
      />
      <WorkLogDailyPesticidePanel
        v-else-if="activeTab === DAILY_TAB_PESTICIDE"
        v-model="pesticideRows"
        :farm-cd="farmCd"
        :is-pesticide-work="isPestWork"
        :stock-applied-yn="stockAppliedYn"
        :editing-replace="editingReplace"
        @pending="onPending"
        @cancel-use="emit('cancelPesticide')"
        @edit-begin="emit('editPesticide')"
      />
      <p v-else-if="activeTab === DAILY_TAB_FERTILIZER" class="pending">
        {{ MSG_FERTILIZER_PENDING }}
      </p>
      <WorkLogDailyWorkPhotoPanel
        v-else-if="activeTab === DAILY_TAB_PHOTO"
        :farm-cd="farmCd"
        :work-id="item.id"
      />
    </div>
  </section>
</template>

<style scoped>
.card {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
  padding: var(--ods-space-16);
  border-radius: var(--ods-radius-card-lg);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  box-shadow: var(--ods-shadow-card);
}

.card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ods-space-12);
}

.card__title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--ods-space-8);
}

.card__badge {
  display: inline-block;
  padding: var(--ods-space-4) var(--ods-space-8);
  border-radius: var(--ods-radius-badge);
  background: color-mix(in srgb, var(--ods-color-primary) 12%, white);
  color: var(--ods-color-primary);
  font: var(--ods-font-card-help);
  font-weight: 700;
}

.card__title {
  margin: 0;
  font: var(--ods-font-title-2);
  color: var(--ods-color-text);
}

.card__time {
  margin: var(--ods-space-8) 0 0;
  font: var(--ods-font-body-1);
  font-weight: 600;
  color: var(--ods-color-text);
}

.card__meta {
  margin: var(--ods-space-8) 0 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
}

.card__meta-item {
  display: inline-flex;
  align-items: center;
  gap: var(--ods-space-8);
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
}

.card__meta-item img {
  width: var(--ods-icon-sm);
  height: var(--ods-icon-sm);
  opacity: 0.75;
}

.card__actions {
  flex-shrink: 0;
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  gap: var(--ods-space-4);
}

.card__edit {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--ods-space-4);
  margin: 0;
  padding: var(--ods-space-8) var(--ods-space-12);
  border: none;
  border-radius: var(--ods-radius-button);
  background: transparent;
  font: var(--ods-font-form-help);
  font-weight: 700;
  color: var(--ods-color-primary);
  cursor: pointer;
  min-height: var(--ods-button-height-in-card);
}

.card__edit img {
  width: var(--ods-icon-sm);
  height: var(--ods-icon-sm);
}

.card__copy {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--ods-space-4);
  margin: 0;
  padding: var(--ods-space-8) var(--ods-space-12);
  border: none;
  border-radius: var(--ods-radius-button);
  background: transparent;
  font: var(--ods-font-form-help);
  font-weight: 700;
  color: var(--ods-color-primary);
  cursor: pointer;
  min-height: var(--ods-button-height-in-card);
  white-space: nowrap;
}

.card__copy img {
  width: var(--ods-icon-sm);
  height: var(--ods-icon-sm);
}

.card__tabs {
  display: flex;
  gap: 0;
  width: 100%;
  overflow-x: hidden;
  border-bottom: 1px solid var(--ods-color-border);
}

.card__body {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
  min-width: 0;
  max-width: 100%;
  overflow-x: hidden;
}

.card__tabs::-webkit-scrollbar {
  display: none;
}

.card__tab {
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

.card__tab--on {
  color: var(--ods-color-primary);
  font-weight: 700;
  border-bottom-color: var(--ods-color-primary);
}

.card__tab-ico {
  width: var(--ods-icon-lg);
  height: var(--ods-icon-lg);
  pointer-events: none;
}

.rows {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0;
}

.row {
  display: grid;
  grid-template-columns: var(--ods-thumb-md) 1fr;
  gap: var(--ods-space-12);
  font: var(--ods-font-form-help);
  padding: var(--ods-space-8) 0;
  border-bottom: 1px solid var(--ods-color-gray-100);
}

.row--pair {
  display: flex;
  gap: var(--ods-space-12);
  grid-template-columns: unset;
}

.row__col {
  flex: 1 1 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
}

.row:last-child {
  border-bottom: none;
}

.row dt {
  margin: 0;
  color: var(--ods-color-text-secondary);
}

.row dd {
  margin: 0;
  color: var(--ods-color-text);
  font-weight: 600;
  line-height: 1.45;
}

.row__memo {
  white-space: pre-wrap;
  word-break: break-word;
}

.pending {
  margin: 0;
  padding: var(--ods-space-20);
  text-align: center;
  font: var(--ods-font-form-help);
  color: var(--ods-color-text-secondary);
  background: var(--ods-color-bg-muted);
  border-radius: var(--ods-radius-button);
}
</style>
