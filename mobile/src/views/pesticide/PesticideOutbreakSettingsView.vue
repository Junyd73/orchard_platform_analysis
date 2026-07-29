<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'

import {
  fetchOutbreakParams,
  upsertOutbreakParam,
  type OutbreakParamItem,
} from '@/api/smartSpray'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import OdsBadge from '@/components/ods/OdsBadge.vue'
import OdsBottomNav from '@/components/ods/OdsBottomNav.vue'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsCard from '@/components/ods/OdsCard.vue'
import OdsInput from '@/components/ods/OdsInput.vue'
import OdsSegmented, {
  type OdsSegmentOption,
} from '@/components/ods/OdsSegmented.vue'
import OdsSkeleton from '@/components/ods/OdsSkeleton.vue'
import {
  LABEL_OUTBREAK_COMPARE,
  LABEL_OUTBREAK_COMPARE_GTE,
  LABEL_OUTBREAK_COMPARE_LTE,
  LABEL_OUTBREAK_COMPARE_MATCH,
  LABEL_OUTBREAK_COMPARE_NA,
  LABEL_OUTBREAK_EXAMPLE,
  LABEL_OUTBREAK_PARAM_KEY,
  LABEL_OUTBREAK_PARAM_VALUE,
  LABEL_OUTBREAK_PEST,
  LABEL_OUTBREAK_SAVE_ALL,
  LABEL_OUTBREAK_SCOPE_FARM,
  LABEL_OUTBREAK_SCOPE_MINE,
  LABEL_OUTBREAK_SOURCE,
  MSG_OUTBREAK_SETTINGS_NOTICE,
  MSG_OUTBREAK_SETTINGS_TITLE,
  OUTBREAK_PARAM_KEY_OPTIONS,
  formatOutbreakParamValueForStorage,
  outbreakCompareEnabled,
  outbreakParamKeyExample,
  outbreakRowCompareEnabled,
  outbreakValueIsRangeOrSet,
  splitOutbreakParamValue,
} from '@/views/pesticide/pesticideConstants'
import { PEST_DICT_NAMES } from '@/views/pesticide/pestDictConstants'
import { useAppStore } from '@/composables/stores/app'

const app = useAppStore()
const farmCd = computed(() => app.farmCd)

const scope = ref('mine')
const editPest = ref(PEST_DICT_NAMES[0] || '검은별무늬병')
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const status = ref('')

const scopeOptions: OdsSegmentOption[] = [
  { value: 'mine', label: LABEL_OUTBREAK_SCOPE_MINE },
  { value: 'farm', label: LABEL_OUTBREAK_SCOPE_FARM },
]

const formValues = reactive<Record<string, string>>({})
const formOps = reactive<Record<string, string>>({})
const formSources = reactive<Record<string, string>>({})
const formExamples = reactive<Record<string, string>>({})

const pestOptions = PEST_DICT_NAMES

function sourceText(src: string) {
  return LABEL_OUTBREAK_SOURCE[src] || src
}

function ensureFormKeys() {
  for (const opt of OUTBREAK_PARAM_KEY_OPTIONS) {
    if (formValues[opt.key] == null) formValues[opt.key] = ''
    if (formOps[opt.key] == null) {
      formOps[opt.key] = opt.compare ? '>=' : opt.key === 'current_month' ? 'match' : ''
    }
    if (formSources[opt.key] == null) formSources[opt.key] = ''
    if (formExamples[opt.key] == null) {
      formExamples[opt.key] = opt.example
    }
  }
}

function mapByKey(items: OutbreakParamItem[], pest: string) {
  const map = new Map<string, OutbreakParamItem>()
  for (const it of items) {
    if (it.pest_nm !== pest) continue
    map.set(it.param_key, it)
  }
  return map
}

function applyRow(optKey: string, row: OutbreakParamItem | undefined, sourceFallback: string) {
  const example = row?.example || outbreakParamKeyExample(optKey)
  formExamples[optKey] = example
  if (!row) {
    formValues[optKey] = ''
    formOps[optKey] = outbreakCompareEnabled(optKey)
      ? '>='
      : optKey === 'current_month'
        ? 'match'
        : ''
    formSources[optKey] = ''
    return
  }
  const split = splitOutbreakParamValue(
    optKey,
    String(row.param_value ?? ''),
    row.param_op,
  )
  formValues[optKey] =
    row.display_value != null && String(row.display_value).trim() !== ''
      ? String(row.display_value)
      : split.display
  if (
    outbreakRowCompareEnabled(
      optKey,
      formValues[optKey],
      row.compare_enabled,
    )
  ) {
    const op = row.param_op === '<=' || row.param_op === '>=' ? row.param_op : split.op
    formOps[optKey] = op === '<=' ? '<=' : '>='
  } else if (optKey === 'current_month' || split.op === 'match' || outbreakValueIsRangeOrSet(formValues[optKey])) {
    formOps[optKey] = 'match'
  } else {
    formOps[optKey] = ''
  }
  formSources[optKey] = row.source || sourceFallback
}

async function load() {
  const farm = farmCd.value
  if (!farm) return
  loading.value = true
  error.value = ''
  status.value = ''
  ensureFormKeys()
  try {
    const [scoped, effective] = await Promise.all([
      fetchOutbreakParams(farm, scope.value as 'mine' | 'farm'),
      fetchOutbreakParams(farm, 'effective'),
    ])
    const pest = editPest.value
    const scopedMap = mapByKey(scoped.items || [], pest)
    const effMap = mapByKey(effective.items || [], pest)
    for (const opt of OUTBREAK_PARAM_KEY_OPTIONS) {
      const mineOrFarm = scopedMap.get(opt.key)
      const eff = effMap.get(opt.key)
      if (mineOrFarm) {
        applyRow(opt.key, mineOrFarm, scope.value)
      } else if (eff) {
        applyRow(opt.key, eff, 'system')
      } else {
        applyRow(opt.key, undefined, '')
      }
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '불러오기 실패'
  } finally {
    loading.value = false
  }
}

async function saveAll() {
  const farm = farmCd.value
  if (!farm || saving.value) return
  saving.value = true
  status.value = ''
  error.value = ''
  try {
    const jobs = OUTBREAK_PARAM_KEY_OPTIONS.map((opt) => {
      const display = String(formValues[opt.key] ?? '').trim()
      if (!display) return null
      const param_value = formatOutbreakParamValueForStorage(
        opt.key,
        display,
        formOps[opt.key],
      )
      if (!param_value) return null
      return upsertOutbreakParam(farm, {
        pest_nm: editPest.value,
        param_key: opt.key,
        param_value,
        as_farm_default: scope.value === 'farm',
      })
    }).filter(Boolean)
    if (!jobs.length) {
      error.value = '저장할 기준값이 없습니다.'
      return
    }
    await Promise.all(jobs)
    status.value = `${editPest.value} 영향항목을 저장했습니다.`
    await load()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '저장 실패'
  } finally {
    saving.value = false
  }
}

function compareLabel(optKey: string): string {
  if (outbreakRowCompareEnabled(optKey, formValues[optKey] || '')) return ''
  if (
    optKey === 'current_month' ||
    formOps[optKey] === 'match' ||
    outbreakValueIsRangeOrSet(formValues[optKey] || '')
  ) {
    return LABEL_OUTBREAK_COMPARE_MATCH
  }
  return LABEL_OUTBREAK_COMPARE_NA
}

function rowCompareActive(optKey: string): boolean {
  return outbreakRowCompareEnabled(optKey, formValues[optKey] || '')
}

watch([farmCd, scope, editPest], () => {
  void load()
})

onMounted(() => {
  ensureFormKeys()
  void load()
})
</script>

<template>
  <div class="page">
    <main class="content ods-page-content">
      <OdsAppBar show-back back-fallback="pesticide" />

      <div class="stack">
        <header class="head">
          <h1 class="head__title">{{ MSG_OUTBREAK_SETTINGS_TITLE }}</h1>
        </header>

        <OdsCard role="note">{{ MSG_OUTBREAK_SETTINGS_NOTICE }}</OdsCard>

        <div class="scope-tabs">
          <OdsSegmented
            v-model="scope"
            :options="scopeOptions"
            aria-label="설정 범위"
          />
        </div>

        <section class="panel">
          <label class="field">
            <span>{{ LABEL_OUTBREAK_PEST }}</span>
            <select v-model="editPest">
              <option v-for="p in pestOptions" :key="p" :value="p">
                {{ p }}
              </option>
            </select>
          </label>

          <p v-if="error" class="msg msg--err" role="alert">{{ error }}</p>
          <p v-else-if="status" class="msg msg--ok" role="status">{{ status }}</p>
          <OdsSkeleton v-if="loading" height="160px" />

          <div v-else class="tbl-wrap">
            <table class="tbl">
              <thead>
                <tr>
                  <th scope="col">{{ LABEL_OUTBREAK_PARAM_KEY }}</th>
                  <th scope="col" class="tbl__val-h">
                    {{ LABEL_OUTBREAK_PARAM_VALUE }}
                  </th>
                  <th scope="col" class="tbl__cmp-h">{{ LABEL_OUTBREAK_COMPARE }}</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="opt in OUTBREAK_PARAM_KEY_OPTIONS"
                  :key="opt.key"
                >
                  <td>
                    <div class="tbl__nm-wrap">
                      <span class="tbl__nm">{{ opt.label }}</span>
                      <OdsBadge v-if="formSources[opt.key]" tone="ok">
                        {{ sourceText(formSources[opt.key]) }}
                      </OdsBadge>
                    </div>
                    <p class="tbl__ex">
                      <span class="tbl__ex-lab">{{ LABEL_OUTBREAK_EXAMPLE }}</span>
                      {{ formExamples[opt.key] || opt.example }}
                    </p>
                  </td>
                  <td class="tbl__val">
                    <OdsInput
                      v-model="formValues[opt.key]"
                      bare
                      :inputmode="opt.key === 'current_month' ? 'text' : 'decimal'"
                      :placeholder="opt.key === 'current_month' ? '5~9' : ''"
                      :aria-label="`${opt.label} ${LABEL_OUTBREAK_PARAM_VALUE}`"
                    />
                  </td>
                  <td class="tbl__cmp">
                    <select
                      v-if="rowCompareActive(opt.key)"
                      v-model="formOps[opt.key]"
                      :aria-label="`${opt.label} ${LABEL_OUTBREAK_COMPARE}`"
                    >
                      <option value=">=">{{ LABEL_OUTBREAK_COMPARE_GTE }}</option>
                      <option value="<=">{{ LABEL_OUTBREAK_COMPARE_LTE }}</option>
                    </select>
                    <span v-else class="tbl__na">{{ compareLabel(opt.key) }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <OdsButton
          type="button"
          :busy="saving"
          :disabled="loading || saving"
          @click="saveAll"
        >
          {{ saving ? '저장 중…' : LABEL_OUTBREAK_SAVE_ALL }}
        </OdsButton>
      </div>
    </main>
    <OdsBottomNav />
  </div>
</template>

<style scoped>
.page {
  min-height: 100dvh;
  background: var(--ods-color-bg-muted);
  padding-bottom: calc(var(--ods-thumb-sm) + env(safe-area-inset-bottom));
}

.stack {
  display: flex;
  flex-direction: column;
  gap: var(--ods-page-content-gap);
}

.head {
  margin: 0;
}
.head__title {
  margin: 0;
  font: var(--ods-font-title-2);
  font-weight: 800;
  color: var(--ods-color-text);
}

.scope-tabs {
  width: 100%;
}
.scope-tabs :deep(.ods-segmented) {
  width: 100%;
  max-width: none;
}

.panel {
  margin: 0;
  border-radius: var(--ods-radius-card);
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  box-shadow: var(--ods-shadow-card);
  overflow: hidden;
}

.field {
  display: flex;
  flex-direction: column;
  gap: var(--ods-form-label-gap);
  margin: 0;
  padding: var(--ods-space-12) var(--ods-card-padding);
  border-bottom: 1px solid var(--ods-color-border);
  font: var(--ods-font-form-label);
  color: var(--ods-color-text);
}
.field select {
  box-sizing: border-box;
  width: 100%;
  height: var(--ods-control-height);
  min-height: var(--ods-control-height);
  margin: 0;
  padding: 0 var(--ods-space-12);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-white);
  font: var(--ods-font-form-value);
  color: var(--ods-color-text);
}

.msg {
  margin: 0;
  padding: var(--ods-space-8) var(--ods-card-padding);
  font: var(--ods-font-form-help);
  font-weight: 700;
}
.msg--ok {
  color: var(--ods-color-primary);
}
.msg--err {
  color: var(--ods-color-danger);
}

.tbl-wrap {
  overflow-x: hidden;
  width: 100%;
}
.tbl {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font: var(--ods-font-card-meta);
}
.tbl th {
  padding: var(--ods-space-8);
  text-align: left;
  font: var(--ods-font-card-section);
  font-weight: 700;
  color: var(--ods-color-text);
  background: var(--ods-color-gray-100);
  border-bottom: 1px solid var(--ods-color-border);
  white-space: nowrap;
}
/* 영향항목 | 기준값 | 비교 — 좁은 폭에서도 가로 스크롤 없이 */
.tbl__val-h {
  width: 5.25rem;
  text-align: right;
}
.tbl__cmp-h {
  width: 4.25rem;
}
.tbl td {
  padding: var(--ods-space-8);
  border-bottom: 1px solid var(--ods-color-border);
  color: var(--ods-color-text);
  vertical-align: middle;
  word-break: keep-all;
}
.tbl tr:last-child td {
  border-bottom: none;
}

.tbl__nm-wrap {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--ods-space-4) var(--ods-space-8);
  min-width: 0;
}
.tbl__nm {
  font: var(--ods-font-card-emphasis);
  font-weight: 700;
  color: var(--ods-color-text);
  line-height: 1.3;
}

.tbl__cmp select {
  box-sizing: border-box;
  width: 100%;
  height: var(--ods-control-height);
  min-height: var(--ods-control-height);
  margin: 0;
  padding: 0;
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-white);
  font: var(--ods-font-form-value);
  color: var(--ods-color-text);
  text-align: center;
}
.tbl__val :deep(.ods-input) {
  padding: 0 var(--ods-space-4);
  font-variant-numeric: tabular-nums;
  text-align: right;
}
.tbl__na {
  display: inline-block;
  width: 100%;
  text-align: center;
  color: var(--ods-color-text-secondary);
  font: var(--ods-font-card-help);
  font-weight: 700;
}
.tbl__ex {
  margin: var(--ods-space-4) 0 0;
  font: var(--ods-font-card-help);
  color: var(--ods-color-text-secondary);
  line-height: 1.35;
  word-break: keep-all;
  overflow-wrap: anywhere;
}
.tbl__ex-lab {
  margin-right: var(--ods-space-4);
  font-weight: 700;
  color: var(--ods-color-gray-500);
}
</style>
