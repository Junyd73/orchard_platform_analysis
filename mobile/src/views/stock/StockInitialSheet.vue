<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { createInitialStock } from '@/api/stock'
import { fetchCommonCodes } from '@/api/commonCodes'
import { ApiClientError } from '@/api/client'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsInput from '@/components/ods/OdsInput.vue'
import OdsSelect from '@/components/ods/OdsSelect.vue'
import {
  ADJUST_REASON_OPTIONS,
  PARENT_ADJUST_REASON,
  reasonAllowsIn,
} from '@/views/stock/stockAdjustConstants'
import {
  DEFAULT_WH_CD,
  JUICE_INITIAL_ITEM_OPTIONS,
  LABEL_JUICE_KIND,
  LABEL_MEMO,
  LABEL_PACK,
  LABEL_QTY,
  LABEL_REASON,
  LABEL_STOCK_INITIAL,
  LABEL_WH,
  LABEL_YEAR,
  MSG_INITIAL_SPEC_EXISTS,
  PARENT_JUICE_QTY,
  buildJuiceInitialPayload,
  emptyJuiceInitialDraft,
  isJuiceInitialDuplicateError,
  juiceInitialSummary,
  resolveDefaultVarietyCd,
  type JuiceInitialDraft,
} from '@/views/stock/stockInitialModel'
import { PARENT_PEAR_VARIETY } from '@/views/stock/stockInitialConstants'
import { todayBizIso } from '@/shared/bizDate'

const props = defineProps<{
  open: boolean
  farmCd: string
}>()

const emit = defineEmits<{
  close: []
  success: []
}>()

const draft = ref<JuiceInitialDraft>(emptyJuiceInitialDraft(Number(todayBizIso().slice(0, 4))))
const packCodes = ref<{ code_cd: string; code_nm: string }[]>([])
const reasonOptions = ref<{ value: string; label: string }[]>(
  ADJUST_REASON_OPTIONS.filter((r) => reasonAllowsIn(r.value)).map((r) => ({
    value: r.value,
    label: r.label,
  })),
)
const varietyCd = ref('')
const busy = ref(false)
const errorMsg = ref('')
const mastersLoading = ref(false)

const packLabel = computed(() => {
  const hit = packCodes.value.find((c) => c.code_cd === draft.value.grade_cd)
  return hit?.code_nm || draft.value.grade_cd || '—'
})

const itemLabel = computed(() => {
  const hit = JUICE_INITIAL_ITEM_OPTIONS.find((o) => o.value === draft.value.item_cd)
  return hit?.label || draft.value.item_cd
})

const summaryText = computed(() =>
  juiceInitialSummary({
    itemLabel: itemLabel.value,
    packLabel: packLabel.value,
    qty: draft.value.qty,
    wh_cd: draft.value.wh_cd || DEFAULT_WH_CD,
  }),
)

async function loadMasters() {
  if (!props.farmCd) return
  mastersLoading.value = true
  errorMsg.value = ''
  try {
    const year = Number(todayBizIso().slice(0, 4))
    draft.value = emptyJuiceInitialDraft(year)
    const [qt, varieties, reasons] = await Promise.all([
      fetchCommonCodes(props.farmCd, PARENT_JUICE_QTY),
      fetchCommonCodes(props.farmCd, PARENT_PEAR_VARIETY),
      fetchCommonCodes(props.farmCd, PARENT_ADJUST_REASON),
    ])
    packCodes.value = qt.map((c) => ({ code_cd: c.code_cd, code_nm: c.code_nm || c.code_cd }))
    if (packCodes.value[0] && !draft.value.grade_cd) {
      draft.value.grade_cd = packCodes.value[0].code_cd
    }
    varietyCd.value = resolveDefaultVarietyCd(varieties)
    const allowIn = new Set<string>(
      ADJUST_REASON_OPTIONS.filter((r) => reasonAllowsIn(r.value)).map((r) => r.value),
    )
    const mapped = reasons
      .filter((c) => allowIn.has(c.code_cd))
      .map((c) => ({ value: c.code_cd, label: c.code_nm || c.code_cd }))
    if (mapped.length) reasonOptions.value = mapped
  } catch {
    errorMsg.value = '등록 옵션을 불러오지 못했습니다.'
  } finally {
    mastersLoading.value = false
  }
}

watch(
  () => props.open,
  (open) => {
    if (open) void loadMasters()
    else errorMsg.value = ''
  },
  { immediate: true },
)

function close() {
  if (busy.value) return
  emit('close')
}

async function submit() {
  if (busy.value) return
  errorMsg.value = ''
  const built = buildJuiceInitialPayload(draft.value, { variety_cd: varietyCd.value })
  if ('error' in built) {
    errorMsg.value = built.error
    return
  }
  busy.value = true
  try {
    await createInitialStock(props.farmCd, built)
    emit('success')
    emit('close')
  } catch (err) {
    if (err instanceof ApiClientError && isJuiceInitialDuplicateError(err)) {
      errorMsg.value = MSG_INITIAL_SPEC_EXISTS
    } else {
      errorMsg.value = err instanceof ApiClientError ? err.message : '재고를 등록하지 못했습니다.'
    }
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="stock-initial-overlay"
      role="dialog"
      aria-modal="true"
      :aria-label="LABEL_STOCK_INITIAL"
      data-testid="stock-initial-sheet"
      @click.self="close"
    >
      <div class="stock-initial-sheet">
        <div class="stock-initial-sheet__header">
          <span class="stock-initial-sheet__title">{{ LABEL_STOCK_INITIAL }}</span>
          <button
            type="button"
            class="stock-initial-sheet__close"
            aria-label="닫기"
            @click="close"
          >
            ✕
          </button>
        </div>

        <div class="stock-initial-sheet__body">
          <label class="stock-initial-field">
            <span>{{ LABEL_JUICE_KIND }}</span>
            <OdsSelect v-model="draft.item_cd" variant="form" data-testid="stock-initial-kind">
              <option
                v-for="opt in JUICE_INITIAL_ITEM_OPTIONS"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </option>
            </OdsSelect>
          </label>

          <label class="stock-initial-field">
            <span>{{ LABEL_PACK }}</span>
            <OdsSelect
              v-model="draft.grade_cd"
              variant="form"
              :disabled="mastersLoading || !packCodes.length"
              data-testid="stock-initial-pack"
            >
              <option value="" disabled>포장규격 선택</option>
              <option
                v-for="p in packCodes"
                :key="p.code_cd"
                :value="p.code_cd"
              >
                {{ p.code_nm }}
              </option>
            </OdsSelect>
          </label>

          <div class="stock-initial-row">
            <label class="stock-initial-field">
              <span>{{ LABEL_YEAR }}</span>
              <OdsInput
                v-model="draft.harvest_year"
                type="number"
                inputmode="numeric"
                variant="form"
                bare
                data-testid="stock-initial-year"
              />
            </label>
            <label class="stock-initial-field">
              <span>{{ LABEL_WH }}</span>
              <OdsSelect v-model="draft.wh_cd" variant="form" data-testid="stock-initial-wh">
                <option :value="DEFAULT_WH_CD">{{ DEFAULT_WH_CD }}</option>
              </OdsSelect>
            </label>
          </div>

          <label class="stock-initial-field">
            <span>{{ LABEL_QTY }}</span>
            <OdsInput
              v-model="draft.qty"
              type="number"
              min="1"
              step="1"
              inputmode="numeric"
              variant="form"
              bare
              data-testid="stock-initial-qty"
            />
          </label>

          <label class="stock-initial-field">
            <span>{{ LABEL_REASON }}</span>
            <OdsSelect v-model="draft.reason_cd" variant="form" data-testid="stock-initial-reason">
              <option v-for="r in reasonOptions" :key="r.value" :value="r.value">
                {{ r.label }}
              </option>
            </OdsSelect>
          </label>

          <label class="stock-initial-field">
            <span>{{ LABEL_MEMO }}</span>
            <OdsInput
              v-model="draft.memo"
              variant="form"
              bare
              data-testid="stock-initial-memo"
            />
          </label>

          <p class="stock-initial-summary" data-testid="stock-initial-summary">
            {{ summaryText }}
          </p>
          <p v-if="errorMsg" class="stock-initial-err" data-testid="stock-initial-error">
            {{ errorMsg }}
          </p>
        </div>

        <div class="stock-initial-sheet__footer">
          <OdsButton type="button" variant="secondary" :disabled="busy" @click="close">
            취소
          </OdsButton>
          <OdsButton
            type="button"
            :busy="busy"
            :disabled="busy || mastersLoading"
            data-testid="stock-initial-save"
            @click="submit"
          >
            등록
          </OdsButton>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.stock-initial-overlay {
  position: fixed;
  inset: 0;
  z-index: 80;
  background: rgba(20, 20, 20, 0.45);
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.stock-initial-sheet {
  width: min(100%, 520px);
  max-height: min(88vh, 720px);
  overflow: auto;
  background: var(--ods-color-surface, #fff);
  border-radius: 16px 16px 0 0;
  padding: 16px 16px calc(16px + env(safe-area-inset-bottom, 0px));
  box-sizing: border-box;
}
.stock-initial-sheet__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.stock-initial-sheet__title {
  font: var(--ods-font-form-label);
  font-weight: 700;
}
.stock-initial-sheet__close {
  border: none;
  background: transparent;
  font-size: 18px;
  cursor: pointer;
  color: var(--ods-color-text-secondary);
}
.stock-initial-sheet__body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.stock-initial-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.stock-initial-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.stock-initial-summary {
  margin: 4px 0 0;
  font: var(--ods-font-body-1);
  font-weight: 600;
  color: var(--ods-color-text);
}
.stock-initial-err {
  margin: 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-danger);
}
.stock-initial-sheet__footer {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: 16px;
}
</style>
