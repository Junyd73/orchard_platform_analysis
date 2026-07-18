<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { fetchCommonCodes } from '@/api/commonCodes'
import { fetchFarmSites } from '@/api/farms'
import {
  deleteWorkLogWork,
  fetchWorkLogDaily,
  saveWorkLogMaster,
  saveWorkLogWorks,
} from '@/api/workLogs'
import { ApiClientError } from '@/api/client'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsFormField from '@/components/ods/OdsFormField.vue'
import OdsInput from '@/components/ods/OdsInput.vue'
import OdsSelect from '@/components/ods/OdsSelect.vue'
import WorkLogHero from '@/views/work-log/components/WorkLogHero.vue'
import {
  isFutureDate,
  MSG_FUTURE_WORK_LOG,
  WEATHER_PARENT_CD,
  WEEKDAY_LABELS,
  WORK_STATUS_PARENT_CD,
  WORK_TYPE_PARENT_CD,
} from '@/views/work-log/workLogConstants'
import { useAppStore } from '@/composables/stores/app'
import type { CommonCodeItem } from '@/types/commonCode'
import type { FarmSiteSummary } from '@/types/farm'
import type { WorkLogWorkUpsertItem } from '@/types/workLog'

type DraftWork = {
  key: string
  work_id: string | null
  work_mid_cd: string
  work_loc_id: string
  start_tm: string
  end_tm: string
  status_cd: string
  rmk: string
}

const store = useAppStore()
const router = useRouter()
const route = useRoute()
const { farmCd, farm } = storeToRefs(store)

const workDt = computed(() => String(route.params.workDt || '').trim())
const isFuture = computed(() => isFutureDate(workDt.value))
const weekdayLabel = computed(() => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(workDt.value)) return ''
  const d = new Date(`${workDt.value}T12:00:00`)
  return WEEKDAY_LABELS[d.getDay()] || ''
})
const heroContext = computed(() => {
  const w = weekdayLabel.value
  return w ? `${workDt.value} (${w})` : workDt.value
})

const loading = ref(true)
const saving = ref(false)
const errorMessage = ref('')
const toastMessage = ref('')

const weatherCodes = ref<CommonCodeItem[]>([])
const workCodes = ref<CommonCodeItem[]>([])
const statusCodes = ref<CommonCodeItem[]>([])
const sites = ref<FarmSiteSummary[]>([])

const weatherCd = ref('')
const tempMin = ref('')
const tempMax = ref('')
const precip = ref('')
const humidity = ref('')
const workRmk = ref('')
const works = ref<DraftWork[]>([])

let draftSeq = 0

function newDraft(partial?: Partial<DraftWork>): DraftWork {
  draftSeq += 1
  return {
    key: `d-${draftSeq}`,
    work_id: null,
    work_mid_cd: '',
    work_loc_id: '',
    start_tm: '',
    end_tm: '',
    status_cd: statusCodes.value[0]?.code_cd || '',
    rmk: '',
    ...partial,
  }
}

function toNum(v: string): number | null {
  const t = v.trim()
  if (!t) return null
  const n = Number(t)
  return Number.isFinite(n) ? n : null
}

function goBack() {
  void router.push({ name: 'work-log' })
}

function showToast(msg: string) {
  toastMessage.value = msg
  window.setTimeout(() => {
    if (toastMessage.value === msg) toastMessage.value = ''
  }, 2800)
}

async function loadCodes() {
  const [wt, wk, wo, st] = await Promise.all([
    fetchCommonCodes(farmCd.value, WEATHER_PARENT_CD).catch(() => []),
    fetchCommonCodes(farmCd.value, WORK_TYPE_PARENT_CD).catch(() => []),
    fetchCommonCodes(farmCd.value, WORK_STATUS_PARENT_CD).catch(() => []),
    fetchFarmSites(farmCd.value, true).catch(() => []),
  ])
  weatherCodes.value = wt
  workCodes.value = wk
  statusCodes.value = wo
  sites.value = st
}

async function loadDaily() {
  loading.value = true
  errorMessage.value = ''
  try {
    const res = await fetchWorkLogDaily(farmCd.value, workDt.value)
    const m = res.master
    weatherCd.value = m?.weather_cd || ''
    tempMin.value = m?.temp_min != null ? String(m.temp_min) : ''
    tempMax.value = m?.temp_max != null ? String(m.temp_max) : ''
    precip.value = m?.precip != null ? String(m.precip) : ''
    humidity.value = m?.humidity != null ? String(m.humidity) : ''
    workRmk.value = m?.work_rmk || ''
    works.value = (res.works || []).map((w) =>
      newDraft({
        work_id: w.work_id,
        work_mid_cd: w.work_mid_cd || '',
        work_loc_id: w.work_loc_id || '',
        start_tm: w.start_tm || '',
        end_tm: w.end_tm || '',
        status_cd: w.status_cd || '',
        rmk: w.rmk || '',
      }),
    )
  } catch (err) {
    errorMessage.value =
      err instanceof ApiClientError ? err.message : '일간 영농일지를 불러오지 못했습니다.'
  } finally {
    loading.value = false
  }
}

function addWork() {
  works.value.push(newDraft())
}

async function removeWork(idx: number) {
  const row = works.value[idx]
  if (!row) return
  if (row.work_id) {
    const ok = window.confirm('이 작업을 삭제할까요?')
    if (!ok) return
    try {
      await deleteWorkLogWork(farmCd.value, row.work_id)
    } catch (err) {
      showToast(err instanceof ApiClientError ? err.message : '작업 삭제에 실패했습니다.')
      return
    }
  }
  works.value.splice(idx, 1)
}

async function onSave() {
  if (isFuture.value) {
    showToast(MSG_FUTURE_WORK_LOG)
    return
  }
  for (const w of works.value) {
    if (!w.work_mid_cd) {
      showToast('작업 유형을 선택해 주세요.')
      return
    }
  }
  saving.value = true
  errorMessage.value = ''
  try {
    await saveWorkLogMaster(farmCd.value, workDt.value, {
      day_of_week: weekdayLabel.value || null,
      weather_cd: weatherCd.value || null,
      temp_min: toNum(tempMin.value),
      temp_max: toNum(tempMax.value),
      precip: toNum(precip.value),
      humidity: toNum(humidity.value),
      work_rmk: workRmk.value.trim() || null,
    })
    const payload: WorkLogWorkUpsertItem[] = works.value.map((w) => ({
      work_id: w.work_id,
      work_mid_cd: w.work_mid_cd,
      work_loc_id: w.work_loc_id || null,
      start_tm: w.start_tm || null,
      end_tm: w.end_tm || null,
      status_cd: w.status_cd || null,
      rmk: w.rmk.trim() || null,
    }))
    await saveWorkLogWorks(farmCd.value, workDt.value, { works: payload })
    showToast('저장되었습니다.')
    await loadDaily()
  } catch (err) {
    errorMessage.value =
      err instanceof ApiClientError ? err.message : '저장에 실패했습니다.'
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(workDt.value)) {
    errorMessage.value = '잘못된 작업일입니다.'
    loading.value = false
    return
  }
  if (!farm.value) {
    await store.refreshAll()
  }
  await loadCodes()
  await loadDaily()
})
</script>

<template>
  <div class="page">
    <main class="content">
      <OdsAppBar show-back @back="goBack" />

      <WorkLogHero
        mode="daily"
        :farm-name="farm?.farm_nm || undefined"
        :context-label="heroContext"
      />

      <p v-if="isFuture" class="warn" role="alert">{{ MSG_FUTURE_WORK_LOG }}</p>
      <p v-if="errorMessage" class="error" role="alert">{{ errorMessage }}</p>
      <p v-else-if="loading" class="status" role="status">불러오는 중…</p>

      <form
        v-if="!loading && !errorMessage"
        id="work-log-daily-form"
        class="stack"
        @submit.prevent="onSave"
      >
        <section class="form" aria-label="기상">
          <h2 class="form__title">기상</h2>
          <OdsFormField label="날씨" optional>
            <OdsSelect v-model="weatherCd" variant="form" :disabled="isFuture">
              <option value="">선택</option>
              <option
                v-for="c in weatherCodes"
                :key="c.code_cd"
                :value="c.code_cd"
              >
                {{ c.code_nm }}
              </option>
            </OdsSelect>
          </OdsFormField>
          <div class="row2">
            <OdsInput
              v-model="tempMin"
              label="최저(℃)"
              type="number"
              inputmode="decimal"
              variant="form"
              optional
              :disabled="isFuture"
            />
            <OdsInput
              v-model="tempMax"
              label="최고(℃)"
              type="number"
              inputmode="decimal"
              variant="form"
              optional
              :disabled="isFuture"
            />
          </div>
          <div class="row2">
            <OdsInput
              v-model="precip"
              label="강수(mm)"
              type="number"
              inputmode="decimal"
              variant="form"
              optional
              :disabled="isFuture"
            />
            <OdsInput
              v-model="humidity"
              label="습도(%)"
              type="number"
              inputmode="decimal"
              variant="form"
              optional
              :disabled="isFuture"
            />
          </div>
        </section>

        <section class="form" aria-label="이슈">
          <h2 class="form__title">이슈</h2>
          <OdsFormField label="특이사항" optional>
            <textarea
              v-model="workRmk"
              class="textarea"
              rows="3"
              placeholder="현장 이슈·특이사항"
              :disabled="isFuture"
            />
          </OdsFormField>
        </section>

        <section class="form" aria-label="작업 목록">
          <div class="form__head">
            <h2 class="form__title">작업</h2>
            <button
              type="button"
              class="add-btn"
              :disabled="isFuture || saving"
              @click="addWork"
            >
              + 추가
            </button>
          </div>

          <p v-if="!works.length" class="empty">등록된 작업이 없습니다.</p>

          <article
            v-for="(w, idx) in works"
            :key="w.key"
            class="work"
          >
            <p class="work__idx">작업 {{ idx + 1 }}</p>
            <OdsFormField label="유형" required>
              <OdsSelect
                v-model="w.work_mid_cd"
                variant="form"
                required
                :disabled="isFuture"
              >
                <option value="" disabled>유형 선택</option>
                <option
                  v-for="c in workCodes"
                  :key="c.code_cd"
                  :value="c.code_cd"
                >
                  {{ c.code_nm }}
                </option>
              </OdsSelect>
            </OdsFormField>
            <OdsFormField label="장소" optional>
              <OdsSelect v-model="w.work_loc_id" variant="form" :disabled="isFuture">
                <option value="">선택</option>
                <option
                  v-for="s in sites"
                  :key="s.site_id"
                  :value="s.site_id"
                >
                  {{ s.site_nm }}
                </option>
              </OdsSelect>
            </OdsFormField>
            <div class="row2">
              <OdsInput
                v-model="w.start_tm"
                label="시작"
                type="time"
                variant="form"
                optional
                :disabled="isFuture"
              />
              <OdsInput
                v-model="w.end_tm"
                label="종료"
                type="time"
                variant="form"
                optional
                :disabled="isFuture"
              />
            </div>
            <OdsFormField label="상태" optional>
              <OdsSelect v-model="w.status_cd" variant="form" :disabled="isFuture">
                <option value="">선택</option>
                <option
                  v-for="c in statusCodes"
                  :key="c.code_cd"
                  :value="c.code_cd"
                >
                  {{ c.code_nm }}
                </option>
              </OdsSelect>
            </OdsFormField>
            <OdsInput
              v-model="w.rmk"
              label="비고"
              type="text"
              variant="form"
              optional
              :disabled="isFuture"
            />
            <OdsButton
              variant="danger"
              type="button"
              :disabled="isFuture || saving"
              @click="removeWork(idx)"
            >
              삭제
            </OdsButton>
          </article>
        </section>
      </form>
    </main>

    <div v-if="!loading && !errorMessage" class="footer-actions">
      <OdsButton
        variant="secondary"
        type="button"
        :disabled="saving"
        :block="false"
        class="footer-btn"
        @click="goBack"
      >
        취소
      </OdsButton>
      <OdsButton
        variant="primary"
        type="submit"
        form="work-log-daily-form"
        :disabled="isFuture"
        :busy="saving"
        :block="false"
        class="footer-btn"
      >
        {{ saving ? '저장 중…' : '저장' }}
      </OdsButton>
    </div>

    <p v-if="toastMessage" class="toast" role="status">{{ toastMessage }}</p>
    <OdsBottomNav />
  </div>
</template>

<style scoped>
.page {
  min-height: 100dvh;
  background: var(--ods-color-bg-muted);
  padding-bottom: calc(148px + env(safe-area-inset-bottom, 0px));
}
.content {
  max-width: 480px;
  margin: 0 auto;
  padding: var(--ods-space-12) var(--ods-page-padding-x) var(--ods-space-16);
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-16);
}
.stack {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-16);
  margin: 0;
}
.form {
  display: flex;
  flex-direction: column;
  gap: var(--ods-form-field-gap);
  padding: var(--ods-space-16);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-card);
  box-shadow: var(--ods-shadow-card);
}
.form__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
.form__title {
  margin: 0;
  font: var(--ods-font-headline);
  color: var(--ods-color-text);
}
.row2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--ods-space-8);
}
.textarea {
  width: 100%;
  box-sizing: border-box;
  min-height: 108px;
  padding: var(--ods-space-12) var(--ods-space-16);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  font: var(--ods-font-form-value);
  color: var(--ods-color-text);
  background: var(--ods-color-white);
  resize: vertical;
}
.textarea::placeholder {
  font: var(--ods-font-form-placeholder);
  color: var(--ods-color-gray-500);
}
.textarea:disabled {
  background: var(--ods-color-gray-100);
  color: var(--ods-color-gray-500);
}
.add-btn {
  border: none;
  background: transparent;
  color: var(--ods-color-primary);
  font: var(--ods-font-body-2);
  font-weight: 700;
  min-height: 40px;
  cursor: pointer;
}
.add-btn:disabled {
  color: var(--ods-color-gray-500);
  cursor: not-allowed;
}
.work {
  display: flex;
  flex-direction: column;
  gap: var(--ods-form-field-gap);
  padding-top: var(--ods-space-12);
  border-top: 1px solid var(--ods-color-border);
}
.work__idx {
  margin: 0;
  font: var(--ods-font-caption);
  font-weight: 700;
  color: var(--ods-color-primary);
}
.empty {
  margin: 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
}
.warn {
  margin: 0;
  font: var(--ods-font-body-2);
  font-weight: 600;
  color: var(--ods-color-danger);
}
.error {
  margin: 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-danger);
}
.status {
  margin: 0;
  font: var(--ods-font-body-2);
  color: var(--ods-color-text-secondary);
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
  padding: 0 var(--ods-page-padding-x);
  box-sizing: border-box;
}
.footer-btn {
  flex: 1;
}
.toast {
  position: fixed;
  left: 50%;
  bottom: calc(120px + env(safe-area-inset-bottom));
  transform: translateX(-50%);
  z-index: 70;
  max-width: min(420px, calc(100vw - 32px));
  margin: 0;
  padding: 12px 16px;
  border-radius: 10px;
  background: rgba(33, 33, 33, 0.92);
  color: var(--ods-color-white);
  font: var(--ods-font-body-2);
  font-weight: 600;
  text-align: center;
  box-shadow: var(--ods-shadow-card);
}
</style>
