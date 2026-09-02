<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { listAuctionCorporations, listAuctionMarkets } from '@/api/auctionLookups'
import { createAuctionShipment } from '@/api/auctionShipments'
import { ApiClientError, readApiClientErrorCode } from '@/api/client'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsInput from '@/components/ods/OdsInput.vue'
import OdsSelect from '@/components/ods/OdsSelect.vue'
import {
  assessAuctionShipSubmit,
  buildAuctionShipmentPayload,
  CODE_AUCTION_SHIP_QTY_UNAVAILABLE,
  isAuctionQtyUnavailableError,
  MSG_AUCTION_SHIP_QTY_UNAVAILABLE,
} from '@/views/stock/auctionShipModel'
import type { ShipDraftLine } from '@/views/sales/shipConfirmModel'
import { todayBizIso } from '@/shared/bizDate'
import type { AuctionCorporationItem, AuctionMarketItem } from '@/types/auctionLookup'

const props = defineProps<{
  open: boolean
  farmCd: string
  lines: ShipDraftLine[]
}>()

const emit = defineEmits<{
  close: []
  success: []
  qtyUnavailable: []
}>()

const shipDt = ref(todayBizIso())
const markets = ref<AuctionMarketItem[]>([])
const corporations = ref<AuctionCorporationItem[]>([])
const selectedMarket = ref<AuctionMarketItem | null>(null)
const selectedCorp = ref<AuctionCorporationItem | null>(null)

const marketsLoading = ref(false)
const marketsError = ref('')
const corpsLoading = ref(false)
const corpsError = ref('')
const submitBusy = ref(false)
const submitError = ref('')

const submitAssessment = computed(() => assessAuctionShipSubmit(props.lines))

const canSubmit = computed(
  () =>
    Boolean(selectedMarket.value && selectedCorp.value) &&
    props.lines.length > 0 &&
    props.lines.every((ln) => Number(ln.qty) > 0) &&
    /^\d{4}-\d{2}-\d{2}$/.test(shipDt.value.trim()) &&
    !submitBusy.value &&
    !submitAssessment.value.blocked,
)

function lineTitle(ln: ShipDraftLine): string {
  const parts = [ln.variety_nm || ln.variety_cd]
  if (ln.weight > 0) parts.push(`${ln.weight}kg`)
  if (ln.size_nm || ln.size_cd) parts.push(ln.size_nm || ln.size_cd)
  return parts.filter(Boolean).join(' · ')
}

function resetFormState() {
  shipDt.value = todayBizIso()
  selectedMarket.value = null
  selectedCorp.value = null
  corporations.value = []
  submitError.value = ''
  marketsError.value = ''
  corpsError.value = ''
}

async function loadMarkets() {
  marketsLoading.value = true
  marketsError.value = ''
  try {
    const page = await listAuctionMarkets()
    markets.value = page.items ?? []
  } catch {
    markets.value = []
    marketsError.value = '시장 목록을 불러오지 못했습니다.'
  } finally {
    marketsLoading.value = false
  }
}

async function loadCorporations(marketCd: string) {
  corpsLoading.value = true
  corpsError.value = ''
  try {
    const page = await listAuctionCorporations(marketCd)
    corporations.value = page.items ?? []
  } catch {
    corporations.value = []
    corpsError.value = '청과회사 목록을 불러오지 못했습니다.'
  } finally {
    corpsLoading.value = false
  }
}

function onMarketCd(cd: string) {
  const found = markets.value.find((m) => m.market_cd === cd) ?? null
  selectedMarket.value = found
  selectedCorp.value = null
  corporations.value = []
  corpsError.value = ''
  if (found) void loadCorporations(found.market_cd)
}

function onCorpName(name: string) {
  selectedCorp.value = corporations.value.find((c) => c.corporation_name === name) ?? null
}

async function submitAuctionShip() {
  if (!canSubmit.value || !selectedMarket.value || !selectedCorp.value) return
  submitBusy.value = true
  submitError.value = ''
  try {
    const payload = buildAuctionShipmentPayload({
      shipDt: shipDt.value.trim(),
      marketCd: selectedMarket.value.market_cd,
      marketName: selectedMarket.value.market_name,
      corporationName: selectedCorp.value.corporation_name,
      custmId: selectedCorp.value.custm_id,
      lines: props.lines,
    })
    await createAuctionShipment(props.farmCd, payload)
    emit('success')
    emit('close')
  } catch (err) {
    const errorCode = readApiClientErrorCode(err)
    if (isAuctionQtyUnavailableError(err) || errorCode === CODE_AUCTION_SHIP_QTY_UNAVAILABLE) {
      submitError.value = MSG_AUCTION_SHIP_QTY_UNAVAILABLE
      emit('qtyUnavailable')
      return
    }
    if (err instanceof ApiClientError) {
      if (err.status === 422) {
        submitError.value = '입력값을 확인해 주세요.'
        return
      }
    }
    submitError.value = '경매 출하 등록에 실패했습니다. 다시 시도해 주세요.'
  } finally {
    submitBusy.value = false
  }
}

watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen) {
      resetFormState()
      return
    }
    resetFormState()
    void loadMarkets()
  },
)
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="auc-sheet"
      role="dialog"
      aria-modal="true"
      aria-label="경매 출하 확인"
      data-testid="auction-ship-sheet"
    >
      <button
        type="button"
        class="auc-sheet__backdrop"
        aria-label="닫기"
        @click="emit('close')"
      />
      <div class="auc-sheet__panel">
        <div class="auc-sheet__header">
          <p class="auc-sheet__title">경매 넘기기</p>
          <button type="button" class="auc-sheet__close" aria-label="닫기" @click="emit('close')">
            ✕
          </button>
        </div>

        <div class="auc-sheet__field">
          <label class="auc-sheet__lbl" for="auc-ship-dt">출하일</label>
          <OdsInput
            id="auc-ship-dt"
            v-model="shipDt"
            type="date"
            variant="form"
            data-testid="auction-ship-dt"
          />
        </div>

        <div class="auc-sheet__field">
          <label class="auc-sheet__lbl" for="auc-market">시장</label>
          <OdsSelect
            id="auc-market"
            variant="form"
            data-testid="auction-market-select"
            :disabled="marketsLoading"
            :model-value="selectedMarket?.market_cd ?? ''"
            @update:model-value="onMarketCd"
          >
            <option value="" disabled>시장 선택</option>
            <option v-for="m in markets" :key="m.market_cd" :value="m.market_cd">
              {{ m.market_name }}
            </option>
          </OdsSelect>
          <p v-if="marketsLoading" class="auc-sheet__hint">시장 목록 불러오는 중…</p>
          <p v-else-if="marketsError" class="auc-sheet__err">{{ marketsError }}</p>
          <p v-else-if="!markets.length && !marketsLoading" class="auc-sheet__hint">
            등록된 시장이 없습니다.
          </p>
          <button
            v-if="marketsError"
            type="button"
            class="auc-sheet__retry"
            data-testid="auction-market-retry"
            @click="loadMarkets"
          >
            다시 시도
          </button>
        </div>

        <div class="auc-sheet__field">
          <label class="auc-sheet__lbl" for="auc-corp">청과회사</label>
          <OdsSelect
            id="auc-corp"
            variant="form"
            data-testid="auction-corp-select"
            :disabled="!selectedMarket || corpsLoading"
            :model-value="selectedCorp?.corporation_name ?? ''"
            @update:model-value="onCorpName"
          >
            <option value="" disabled>청과회사 선택</option>
            <option v-for="c in corporations" :key="c.corporation_name" :value="c.corporation_name">
              {{ c.corporation_name }}
            </option>
          </OdsSelect>
          <p v-if="corpsLoading" class="auc-sheet__hint">청과회사 목록 불러오는 중…</p>
          <p v-else-if="corpsError" class="auc-sheet__err">{{ corpsError }}</p>
          <p
            v-else-if="selectedMarket && !corporations.length && !corpsLoading"
            class="auc-sheet__hint"
          >
            등록된 청과회사가 없습니다.
          </p>
        </div>

        <div class="auc-sheet__lines" data-testid="auction-ship-lines">
          <p class="auc-sheet__lbl">선택 상품 ({{ lines.length }}규격)</p>
          <ul class="auc-sheet__line-list">
            <li v-for="(ln, idx) in lines" :key="idx" class="auc-sheet__line">
              <span class="auc-sheet__line-name">{{ lineTitle(ln) }}</span>
              <span class="auc-sheet__line-meta">
                {{ ln.grade_nm || ln.grade_cd }} · 가용 {{ ln.available_qty ?? '-' }} · 출하
                {{ ln.qty }}박스
              </span>
            </li>
          </ul>
        </div>

        <p
          v-if="submitAssessment.message"
          class="auc-sheet__err"
          data-testid="auction-ship-block"
        >
          {{ submitAssessment.message }}
        </p>

        <p v-if="submitError" class="auc-sheet__err" data-testid="auction-ship-error">
          {{ submitError }}
        </p>

        <div class="auc-sheet__actions">
          <OdsButton
            type="button"
            variant="secondary"
            :block="false"
            class="auc-sheet__btn"
            :disabled="submitBusy"
            data-testid="auction-ship-cancel"
            @click="emit('close')"
          >
            취소
          </OdsButton>
          <OdsButton
            type="button"
            :block="false"
            class="auc-sheet__btn"
            :disabled="!canSubmit"
            :busy="submitBusy"
            data-testid="auction-ship-submit"
            @click="submitAuctionShip"
          >
            경매 넘기기
          </OdsButton>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.auc-sheet {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.auc-sheet__backdrop {
  position: absolute;
  inset: 0;
  border: none;
  background: color-mix(in srgb, black 45%, transparent);
  cursor: pointer;
}
.auc-sheet__panel {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: var(--ods-page-content-max);
  max-height: min(88vh, 640px);
  overflow: auto;
  background: var(--ods-color-white);
  border-radius: var(--ods-radius-card) var(--ods-radius-card) 0 0;
  padding: var(--ods-space-16) var(--ods-space-16)
    calc(var(--ods-space-16) + env(safe-area-inset-bottom));
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
}
.auc-sheet__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
.auc-sheet__title {
  margin: 0;
  font: var(--ods-font-headline);
  font-weight: 700;
}
.auc-sheet__close {
  padding: var(--ods-space-4);
  background: transparent;
  border: none;
  font-size: 16px;
  color: var(--ods-color-text-secondary);
  cursor: pointer;
}
.auc-sheet__field {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
}
.auc-sheet__lbl {
  margin: 0;
  font: var(--ods-font-form-label, var(--ods-font-body-2));
  font-weight: 700;
  color: var(--ods-color-text);
}
.auc-sheet__hint {
  margin: 0;
  font: var(--ods-font-footnote);
  color: var(--ods-color-text-secondary);
}
.auc-sheet__err {
  margin: 0;
  font: var(--ods-font-footnote);
  color: var(--ods-color-danger);
}
.auc-sheet__retry {
  align-self: flex-start;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--ods-color-primary);
  font: var(--ods-font-footnote);
  cursor: pointer;
  text-decoration: underline;
}
.auc-sheet__lines {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-4);
}
.auc-sheet__line-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-6);
}
.auc-sheet__line {
  padding: var(--ods-space-8);
  border: 1px solid var(--ods-color-border-light, #f0ede8);
  border-radius: var(--ods-radius-card);
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-2);
}
.auc-sheet__line-name {
  font: var(--ods-font-body-2);
  font-weight: 600;
}
.auc-sheet__line-meta {
  font: var(--ods-font-footnote);
  color: var(--ods-color-text-secondary);
}
.auc-sheet__actions {
  display: flex;
  gap: var(--ods-space-8);
  justify-content: flex-end;
  padding-top: var(--ods-space-4);
}
:deep(button.auc-sheet__btn.ods-btn) {
  min-height: 40px;
  height: 40px;
  padding: 0 var(--ods-space-12);
  font-size: var(--ods-font-size-body-2, 14px);
}
</style>
