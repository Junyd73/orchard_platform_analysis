<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { listConfirmedAuctionMatches } from '@/api/auctionMatches'
import { listAuctionCorporations, listAuctionMarkets } from '@/api/auctionLookups'
import {
  getAuctionCandidates,
  listAuctionShipments,
} from '@/api/auctionShipments'
import { fetchMarketAuctions } from '@/api/marketAuctions'
import OdsButton from '@/components/ods/OdsButton.vue'
import OdsCard from '@/components/ods/OdsCard.vue'
import OdsEmptyState from '@/components/ods/OdsEmptyState.vue'
import OdsFormField from '@/components/ods/OdsFormField.vue'
import OdsSelect from '@/components/ods/OdsSelect.vue'
import OdsSkeleton from '@/components/ods/OdsSkeleton.vue'
import {
  AUCTION_DEFAULT_MARKET_CD,
  AUCTION_FILTER_ALL,
  AUCTION_MATCH_STATUS_CANDIDATE,
  AUCTION_MATCH_STATUS_CONFIRMED,
  AUCTION_MODE_ALL,
  AUCTION_MODE_MINE,
  AUCTION_PAGE_SIZE,
  LABEL_AUCTION_COL_AMOUNT,
  LABEL_AUCTION_COL_AMOUNT_UNIT,
  LABEL_AUCTION_COL_CORP,
  LABEL_AUCTION_COL_ORIGIN,
  LABEL_AUCTION_COL_PRICE,
  LABEL_AUCTION_COL_PRICE_UNIT,
  LABEL_AUCTION_COL_QTY,
  LABEL_AUCTION_COL_QTY_UNIT,
  LABEL_AUCTION_COL_SPEC,
  LABEL_AUCTION_COL_TIME,
  LABEL_AUCTION_COL_VARIETY,
  LABEL_AUCTION_COL_WEIGHT,
  LABEL_AUCTION_COL_WEIGHT_UNIT,
  LABEL_AUCTION_CORP,
  LABEL_AUCTION_DATE_NEXT,
  LABEL_AUCTION_DATE_PREV,
  LABEL_AUCTION_FILTER_ALL,
  LABEL_AUCTION_FILTER_DETAIL,
  LABEL_AUCTION_LOOKUP,
  LABEL_AUCTION_MARKET,
  LABEL_AUCTION_MODE_ALL,
  LABEL_AUCTION_MODE_MINE,
  LABEL_AUCTION_MORE,
  LABEL_AUCTION_ORIGIN,
  LABEL_AUCTION_RESET,
  LABEL_AUCTION_RETRY,
  LABEL_AUCTION_SORT_HINT,
  LABEL_AUCTION_STATUS_CANDIDATE,
  LABEL_AUCTION_STATUS_CONFIRMED,
  LABEL_AUCTION_TRADE_DATE,
  LABEL_AUCTION_VARIETY,
  MSG_AUCTION_EMPTY,
  MSG_AUCTION_LOAD_FAIL,
  MSG_AUCTION_MINE_EMPTY,
  MSG_AUCTION_MINE_NO_CANDIDATE,
  MSG_AUCTION_STALE,
  auctionRowKey,
  auctionTimeLabel,
  clampTradeDateToToday,
  formatAuctionQtyCell,
  formatAuctionResultTitle,
  formatAuctionWeightCell,
  formatAuctionWon,
  joinAuctionOriginCds,
  originDisplayLabel,
  shiftTradeDate,
  type AuctionResultMode,
} from '@/views/orders/auctionLookupFormat'
import {
  candidateToTableRow,
  confirmedMatchToTableRow,
  dedupeAuctionTableRows,
  marketItemToTableRow,
  passesAuctionTableFilters,
  sortAuctionTableRows,
  type AuctionTableRow,
} from '@/views/orders/auctionTableModel'
import { defaultTradeDt } from '@/views/stock/auctionMatchModel'
import { AUCTION_STATUS_IN_TRANSIT } from '@/views/stock/auctionShipModel'
import AuctionMatchSheet from '@/views/stock/AuctionMatchSheet.vue'
import { todayIso } from '@/views/work-log/workLogConstants'
import iconChevronRight from '@/assets/ods/scr004/icon-chevron-right.svg'
import type { MarketAuctionItem } from '@/types/marketAuction'

type SelectOption = { value: string; label: string }

const props = defineProps<{
  farmCd: string
}>()

const filterExpanded = ref(false)
const draftTradeDate = ref(todayIso())
const draftMarketCd = ref(AUCTION_DEFAULT_MARKET_CD)
const draftCorp = ref(AUCTION_FILTER_ALL)
const draftOrigins = ref<string[]>([])
const draftVariety = ref(AUCTION_FILTER_ALL)

const appliedTradeDate = ref(todayIso())
const appliedMarketCd = ref(AUCTION_DEFAULT_MARKET_CD)
const appliedCorp = ref(AUCTION_FILTER_ALL)
const appliedOrigins = ref<string[]>([])
const appliedVariety = ref(AUCTION_FILTER_ALL)

const marketOptions = ref<SelectOption[]>([])
const corpOptions = ref<SelectOption[]>([])
const originOptions = ref<SelectOption[]>([])
const varietyOptions = ref<SelectOption[]>([])

const resultMode = ref<AuctionResultMode>(AUCTION_MODE_ALL)
const loading = ref(false)
const loadingMore = ref(false)
const loadError = ref('')
const stale = ref(false)
/** ALL 모드 원본(페이징·더보기용). MINE에서는 비운다. */
const marketItems = ref<MarketAuctionItem[]>([])
const tableRows = ref<AuctionTableRow[]>([])
const totalCount = ref(0)
const page = ref(1)
const hasMore = ref(false)
const initialLoaded = ref(false)
const suppressFilters = ref(true)
const mineHadTransitForDate = ref(false)
const matchSheetOpen = ref(false)
const matchShipmentId = ref('')
const tableScrollRef = ref<HTMLElement | null>(null)
const tableDragging = ref(false)
let fetchSeq = 0
let tableDragPointerId: number | null = null
let tableDragStartX = 0
let tableDragScrollLeft = 0
let tableDragMoved = false
let suppressRowClickUntil = 0

type FacetKeep = {
  variety?: boolean
  origin?: boolean
}

const todayMax = computed(() => todayIso())
const canGoNextDate = computed(() => draftTradeDate.value < todayMax.value)
const isAllMode = computed(() => resultMode.value === AUCTION_MODE_ALL)
const isMineMode = computed(() => resultMode.value === AUCTION_MODE_MINE)
const resultTitle = computed(() => formatAuctionResultTitle(totalCount.value))
const emptyMessage = computed(() => {
  if (isAllMode.value) return MSG_AUCTION_EMPTY
  if (mineHadTransitForDate.value) return MSG_AUCTION_MINE_NO_CANDIDATE
  return MSG_AUCTION_MINE_EMPTY
})
const showEmpty = computed(
  () =>
    !loading.value &&
    !loadError.value &&
    initialLoaded.value &&
    tableRows.value.length === 0,
)
const showTable = computed(() => !loading.value && tableRows.value.length > 0)
const showStaleHint = computed(
  () => isAllMode.value && stale.value && tableRows.value.length > 0,
)

const colQtyHeader = `${LABEL_AUCTION_COL_QTY}${LABEL_AUCTION_COL_QTY_UNIT}`
const colWeightHeader = `${LABEL_AUCTION_COL_WEIGHT}${LABEL_AUCTION_COL_WEIGHT_UNIT}`
const colPriceHeader = `${LABEL_AUCTION_COL_PRICE}${LABEL_AUCTION_COL_PRICE_UNIT}`
const colAmountHeader = `${LABEL_AUCTION_COL_AMOUNT}${LABEL_AUCTION_COL_AMOUNT_UNIT}`

function toggleFilterExpanded() {
  filterExpanded.value = !filterExpanded.value
}

function resetDraftFilters() {
  const today = todayIso()
  draftTradeDate.value = today
  draftMarketCd.value = AUCTION_DEFAULT_MARKET_CD
  draftCorp.value = AUCTION_FILTER_ALL
  draftOrigins.value = []
  draftVariety.value = AUCTION_FILTER_ALL
}

function applyDraftToApplied() {
  const today = todayIso()
  draftTradeDate.value = clampTradeDateToToday(draftTradeDate.value, today)
  appliedTradeDate.value = draftTradeDate.value
  appliedMarketCd.value = draftMarketCd.value || AUCTION_DEFAULT_MARKET_CD
  appliedCorp.value = draftCorp.value
  appliedOrigins.value = [...draftOrigins.value]
  appliedVariety.value = draftVariety.value
}

function onTradeDateInput(ev: Event) {
  const el = ev.target as HTMLInputElement
  draftTradeDate.value = clampTradeDateToToday(el.value, todayIso())
}

function shiftDraftTradeDate(delta: number) {
  if (loading.value) return
  draftTradeDate.value = shiftTradeDate(draftTradeDate.value, delta, todayIso())
}

const tradeDateInputRef = ref<HTMLInputElement | null>(null)

function openTradeDatePicker(ev?: Event) {
  if (loading.value) return
  const el = tradeDateInputRef.value
  if (!el || el.disabled) return
  const picker = el as HTMLInputElement & { showPicker?: () => void }
  try {
    if (typeof picker.showPicker === 'function') {
      ev?.preventDefault()
      picker.showPicker()
    }
  } catch {
    /* unsupported / needs gesture — native click still opens picker */
  }
}

function clearOrigins() {
  draftOrigins.value = []
}

function toggleOrigin(value: string) {
  const key = String(value || '').trim()
  if (!key) return
  const next = new Set(draftOrigins.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  draftOrigins.value = Array.from(next)
}

function isOriginSelected(value: string) {
  return draftOrigins.value.includes(value)
}

function statusBadgeLabel(row: AuctionTableRow): string {
  if (row.match_status === AUCTION_MATCH_STATUS_CONFIRMED) {
    return LABEL_AUCTION_STATUS_CONFIRMED
  }
  if (row.match_status === AUCTION_MATCH_STATUS_CANDIDATE) {
    return LABEL_AUCTION_STATUS_CANDIDATE
  }
  return ''
}

function onRowClick(row: AuctionTableRow) {
  if (Date.now() < suppressRowClickUntil) return
  if (!row.selectable || !row.shipment_id) return
  matchShipmentId.value = row.shipment_id
  matchSheetOpen.value = true
}

function onTablePointerDown(ev: PointerEvent) {
  const el = tableScrollRef.value
  if (!el || ev.button !== 0) return
  if (el.scrollWidth <= el.clientWidth + 1) return
  tableDragPointerId = ev.pointerId
  tableDragStartX = ev.clientX
  tableDragScrollLeft = el.scrollLeft
  tableDragMoved = false
  tableDragging.value = true
  try {
    el.setPointerCapture(ev.pointerId)
  } catch {
    /* capture optional */
  }
}

function onTablePointerMove(ev: PointerEvent) {
  if (tableDragPointerId !== ev.pointerId) return
  const el = tableScrollRef.value
  if (!el) return
  const dx = ev.clientX - tableDragStartX
  if (Math.abs(dx) > 4) tableDragMoved = true
  el.scrollLeft = tableDragScrollLeft - dx
  if (tableDragMoved) ev.preventDefault()
}

function endTablePointerDrag(ev: PointerEvent) {
  if (tableDragPointerId !== ev.pointerId) return
  const el = tableScrollRef.value
  if (el) {
    try {
      el.releasePointerCapture(ev.pointerId)
    } catch {
      /* already released */
    }
  }
  if (tableDragMoved) suppressRowClickUntil = Date.now() + 180
  tableDragPointerId = null
  tableDragMoved = false
  tableDragging.value = false
}

function closeMatchSheet() {
  matchSheetOpen.value = false
}

async function onMatchSuccess() {
  matchSheetOpen.value = false
  if (isMineMode.value) {
    await runLookup(false)
  }
}

function onMatchStatusConflict() {
  matchSheetOpen.value = false
  if (isMineMode.value) {
    void runLookup(false)
  }
}

async function setResultMode(mode: AuctionResultMode) {
  if (resultMode.value === mode) return
  resultMode.value = mode
  if (!initialLoaded.value) return
  await runLookup(false)
}

async function loadMarkets() {
  try {
    const pageData = await listAuctionMarkets()
    marketOptions.value = (pageData.items || []).map((row) => ({
      value: row.market_cd,
      label: row.market_name,
    }))
    if (!marketOptions.value.some((o) => o.value === draftMarketCd.value)) {
      draftMarketCd.value = AUCTION_DEFAULT_MARKET_CD
    }
  } catch {
    marketOptions.value = [{ value: AUCTION_DEFAULT_MARKET_CD, label: '가락' }]
  }
}

async function loadCorporations(marketCd: string) {
  const cd = String(marketCd || '').trim()
  if (!cd) {
    corpOptions.value = []
    return
  }
  try {
    const pageData = await listAuctionCorporations(cd)
    corpOptions.value = (pageData.items || []).map((row) => ({
      value: row.corporation_name,
      label: row.corporation_name,
    }))
  } catch {
    corpOptions.value = []
  }
  if (
    draftCorp.value &&
    !corpOptions.value.some((o) => o.value === draftCorp.value)
  ) {
    draftCorp.value = AUCTION_FILTER_ALL
  }
}

function collectOrigins(rows: MarketAuctionItem[], seed: SelectOption[] = []) {
  const originMap = new Map(seed.map((o) => [o.value, o]))
  for (const row of rows) {
    const originValue = String(row.origin_cd || row.origin_name || '').trim()
    const originLabel = String(row.origin_name || row.origin_cd || '').trim()
    if (originValue && originLabel && !originMap.has(originValue)) {
      originMap.set(originValue, { value: originValue, label: originLabel })
    }
  }
  return Array.from(originMap.values()).sort((a, b) =>
    a.label.localeCompare(b.label, 'ko'),
  )
}

function collectVarieties(rows: MarketAuctionItem[], seed: SelectOption[] = []) {
  const varietyMap = new Map(seed.map((o) => [o.value, o]))
  for (const row of rows) {
    const varietyValue = String(row.variety_cd || row.variety_name || '').trim()
    const varietyLabel = String(row.variety_name || row.variety_cd || '').trim()
    if (varietyValue && varietyLabel && !varietyMap.has(varietyValue)) {
      varietyMap.set(varietyValue, { value: varietyValue, label: varietyLabel })
    }
  }
  return Array.from(varietyMap.values()).sort((a, b) =>
    a.label.localeCompare(b.label, 'ko'),
  )
}

function collectOriginsFromTable(
  rows: AuctionTableRow[],
  seed: SelectOption[] = [],
) {
  const originMap = new Map(seed.map((o) => [o.value, o]))
  for (const row of rows) {
    const originValue = String(row.origin_cd || row.origin_name || '').trim()
    const originLabel = String(row.origin_name || row.origin_cd || '').trim()
    if (originValue && originLabel && !originMap.has(originValue)) {
      originMap.set(originValue, { value: originValue, label: originLabel })
    }
  }
  return Array.from(originMap.values()).sort((a, b) =>
    a.label.localeCompare(b.label, 'ko'),
  )
}

function collectVarietiesFromTable(
  rows: AuctionTableRow[],
  seed: SelectOption[] = [],
) {
  const varietyMap = new Map(seed.map((o) => [o.value, o]))
  for (const row of rows) {
    const varietyLabel = String(row.variety_name || '').trim()
    if (varietyLabel && !varietyMap.has(varietyLabel)) {
      varietyMap.set(varietyLabel, { value: varietyLabel, label: varietyLabel })
    }
  }
  return Array.from(varietyMap.values()).sort((a, b) =>
    a.label.localeCompare(b.label, 'ko'),
  )
}

/** 조회 facet. 자기 필터가 걸린 결과로 칩을 다시 만들면 선택지가 축소되므로 유지한다. */
function applyFacets(rows: MarketAuctionItem[], keep?: FacetKeep) {
  if (!keep?.origin && appliedOrigins.value.length === 0) {
    originOptions.value = collectOrigins(rows)
  }
  if (!keep?.variety && !appliedVariety.value) {
    varietyOptions.value = collectVarieties(rows)
  }
}

function applyMineFacets(rows: AuctionTableRow[], keep?: FacetKeep) {
  if (!keep?.origin && appliedOrigins.value.length === 0) {
    originOptions.value = collectOriginsFromTable(rows)
  }
  if (!keep?.variety && !appliedVariety.value) {
    varietyOptions.value = collectVarietiesFromTable(rows)
  }
}

/** 더보기: 선택지 추가 병합. */
function mergeFilterOptions(rows: MarketAuctionItem[]) {
  originOptions.value = collectOrigins(rows, originOptions.value)
  varietyOptions.value = collectVarieties(rows, varietyOptions.value)
}

function buildQuery(pageNo: number, refresh: boolean) {
  return {
    trade_date: appliedTradeDate.value,
    market_cd: appliedMarketCd.value,
    corporation_cd: appliedCorp.value || undefined,
    origin_cd: joinAuctionOriginCds(appliedOrigins.value),
    variety: appliedVariety.value || undefined,
    refresh: refresh || undefined,
    page: pageNo,
    page_size: AUCTION_PAGE_SIZE,
  }
}

function syncAllTableRows(items: MarketAuctionItem[]) {
  marketItems.value = items
  tableRows.value = items.map((row, index) => marketItemToTableRow(row, index))
}

async function fetchAllPage(
  pageNo: number,
  opts: { append: boolean; refresh: boolean; keepFacets?: FacetKeep },
) {
  const seq = ++fetchSeq
  const keepItems = marketItems.value
  const keepRows = tableRows.value
  const keepTotal = totalCount.value
  const keepHasMore = hasMore.value
  const keepStale = stale.value

  if (opts.append) loadingMore.value = true
  else loading.value = true
  loadError.value = ''
  mineHadTransitForDate.value = false

  try {
    const data = await fetchMarketAuctions(buildQuery(pageNo, opts.refresh))
    if (seq !== fetchSeq) return
    totalCount.value = Number(data.total_count || 0)
    page.value = Number(data.page || pageNo)
    hasMore.value = Boolean(data.has_more)
    stale.value = Boolean(data.stale)
    if (opts.append) {
      mergeFilterOptions(data.items || [])
      const seen = new Set(marketItems.value.map((row) => auctionRowKey(row)))
      const next = [...marketItems.value]
      for (const row of data.items || []) {
        const key = auctionRowKey(row)
        if (seen.has(key)) continue
        seen.add(key)
        next.push(row)
      }
      syncAllTableRows(next)
    } else {
      applyFacets(data.items || [], opts.keepFacets)
      syncAllTableRows([...(data.items || [])])
    }
    initialLoaded.value = true
  } catch {
    if (seq !== fetchSeq) return
    loadError.value = MSG_AUCTION_LOAD_FAIL
    if (!opts.append && keepItems.length === 0) {
      marketItems.value = []
      tableRows.value = []
      totalCount.value = 0
      hasMore.value = false
      stale.value = false
    } else {
      marketItems.value = keepItems
      tableRows.value = keepRows
      totalCount.value = keepTotal
      hasMore.value = keepHasMore
      stale.value = keepStale
    }
    initialLoaded.value = true
  } finally {
    if (seq === fetchSeq) {
      loading.value = false
      loadingMore.value = false
    }
  }
}

async function fetchMine(keepFacets?: FacetKeep) {
  const seq = ++fetchSeq
  const keepRows = tableRows.value
  const keepItems = marketItems.value
  const keepTotal = totalCount.value
  const keepTransit = mineHadTransitForDate.value

  loading.value = true
  loadingMore.value = false
  loadError.value = ''
  hasMore.value = false
  stale.value = false
  page.value = 1

  const farm = String(props.farmCd || '').trim()
  if (!farm) {
    loadError.value = MSG_AUCTION_LOAD_FAIL
    marketItems.value = []
    tableRows.value = []
    totalCount.value = 0
    mineHadTransitForDate.value = false
    initialLoaded.value = true
    loading.value = false
    return
  }

  try {
    const tradeDt = appliedTradeDate.value
    const [confirmedPage, shipPage] = await Promise.all([
      listConfirmedAuctionMatches(farm, tradeDt),
      listAuctionShipments(farm, { status: AUCTION_STATUS_IN_TRANSIT }),
    ])
    if (seq !== fetchSeq) return

    const ships = (shipPage.items || []).filter(
      (ship) => defaultTradeDt(ship.ship_dt) === tradeDt,
    )
    mineHadTransitForDate.value = ships.length > 0

    const candidateParts = await Promise.all(
      ships.map(async (ship) => {
        try {
          const res = await getAuctionCandidates(farm, ship.shipment_id, tradeDt)
          return (res.items || []).map((c) =>
            candidateToTableRow(c, ship.shipment_id),
          )
        } catch {
          return [] as AuctionTableRow[]
        }
      }),
    )
    if (seq !== fetchSeq) return

    const confirmedRows = (confirmedPage.items || []).map(confirmedMatchToTableRow)
    const candidateRows = candidateParts.flat()
    const deduped = dedupeAuctionTableRows([...confirmedRows, ...candidateRows])
    applyMineFacets(deduped, keepFacets)

    const filtered = deduped.filter((row) =>
      passesAuctionTableFilters(row, {
        marketCd: appliedMarketCd.value,
        corporation: appliedCorp.value,
        origins: appliedOrigins.value,
        variety: appliedVariety.value,
      }),
    )
    marketItems.value = []
    tableRows.value = sortAuctionTableRows(filtered)
    totalCount.value = tableRows.value.length
    initialLoaded.value = true
  } catch {
    if (seq !== fetchSeq) return
    loadError.value = MSG_AUCTION_LOAD_FAIL
    if (keepRows.length === 0) {
      marketItems.value = []
      tableRows.value = []
      totalCount.value = 0
      mineHadTransitForDate.value = false
    } else {
      marketItems.value = keepItems
      tableRows.value = keepRows
      totalCount.value = keepTotal
      mineHadTransitForDate.value = keepTransit
    }
    initialLoaded.value = true
  } finally {
    if (seq === fetchSeq) {
      loading.value = false
      loadingMore.value = false
    }
  }
}

async function runLookup(refresh: boolean, keepFacets?: FacetKeep) {
  applyDraftToApplied()
  page.value = 1
  if (isMineMode.value) {
    await fetchMine(keepFacets)
    return
  }
  await fetchAllPage(1, { append: false, refresh, keepFacets })
}

async function onLookup() {
  await runLookup(true)
}

async function onReset() {
  suppressFilters.value = true
  resetDraftFilters()
  await loadCorporations(draftMarketCd.value)
  await runLookup(false)
  suppressFilters.value = false
}

async function onRetry() {
  if (isMineMode.value) {
    await fetchMine()
    return
  }
  await fetchAllPage(page.value || 1, {
    append: false,
    refresh: true,
  })
}

async function onMore() {
  if (!isAllMode.value) return
  if (!hasMore.value || loading.value || loadingMore.value) return
  await fetchAllPage(page.value + 1, { append: true, refresh: false })
}

function pruneVarietyIfMissing() {
  if (
    draftVariety.value &&
    !varietyOptions.value.some((o) => o.value === draftVariety.value)
  ) {
    draftVariety.value = AUCTION_FILTER_ALL
    return true
  }
  return false
}

/**
 * 연쇄 필터: 날짜 → 품종 → 시장 → 청과법인 → 산지.
 * 상위 변경 시 하위 조건을 비우고 즉시 재조회한다.
 */
watch(draftTradeDate, async (next, prev) => {
  if (suppressFilters.value) return
  if (next === prev) return
  if (!initialLoaded.value) return
  suppressFilters.value = true
  draftVariety.value = AUCTION_FILTER_ALL
  draftMarketCd.value = AUCTION_DEFAULT_MARKET_CD
  draftCorp.value = AUCTION_FILTER_ALL
  draftOrigins.value = []
  suppressFilters.value = false
  await loadCorporations(draftMarketCd.value)
  await runLookup(false)
})

watch(draftVariety, async (next, prev) => {
  if (suppressFilters.value) return
  if (next === prev) return
  if (!initialLoaded.value) return
  suppressFilters.value = true
  draftCorp.value = AUCTION_FILTER_ALL
  draftOrigins.value = []
  suppressFilters.value = false
  await runLookup(false, { variety: true })
})

watch(draftMarketCd, async (next, prev) => {
  if (suppressFilters.value) return
  if (next === prev) return
  if (!initialLoaded.value) return
  suppressFilters.value = true
  draftCorp.value = AUCTION_FILTER_ALL
  draftOrigins.value = []
  suppressFilters.value = false
  await loadCorporations(next)
  await runLookup(false, { variety: true })
  if (pruneVarietyIfMissing()) {
    await runLookup(false)
  }
})

watch(draftCorp, async (next, prev) => {
  if (suppressFilters.value) return
  if (next === prev) return
  if (!initialLoaded.value) return
  suppressFilters.value = true
  draftOrigins.value = []
  suppressFilters.value = false
  await runLookup(false, { variety: true })
})

watch(
  draftOrigins,
  async (next, prev) => {
    if (suppressFilters.value) return
    if (!initialLoaded.value) return
    const nextKey = next.join(',')
    const prevKey = (prev || []).join(',')
    if (nextKey === prevKey) return
    // 산지 선택 중이면 칩 유지, 전체(비움)로 돌리면 결과에서 칩 복구
    const keepOriginChips = next.length > 0
    await runLookup(false, { variety: true, origin: keepOriginChips })
  },
  { deep: true },
)

onMounted(async () => {
  suppressFilters.value = true
  resetDraftFilters()
  await loadMarkets()
  await loadCorporations(draftMarketCd.value)
  await runLookup(false)
  suppressFilters.value = false
})
</script>

<template>
  <section class="auction" aria-label="경매조회">
    <OdsCard class="auction-filter" aria-label="조회조건">
      <div class="auction-filter__head">
        <OdsFormField :label="LABEL_AUCTION_TRADE_DATE" as="fieldset">
          <div class="date-stepper" role="group" :aria-label="LABEL_AUCTION_TRADE_DATE">
            <button
              type="button"
              class="date-stepper__btn"
              :aria-label="LABEL_AUCTION_DATE_PREV"
              :disabled="loading"
              @click="shiftDraftTradeDate(-1)"
            >
              <img class="date-stepper__icon date-stepper__icon--prev" :src="iconChevronRight" alt="">
            </button>
            <div class="date-stepper__value">
              <span class="date-stepper__text">{{ draftTradeDate }}</span>
              <input
                ref="tradeDateInputRef"
                class="date-stepper__native"
                type="date"
                :value="draftTradeDate"
                :max="todayMax"
                :aria-label="LABEL_AUCTION_TRADE_DATE"
                :disabled="loading"
                @click="openTradeDatePicker"
                @input="onTradeDateInput"
                @change="onTradeDateInput"
              >
            </div>
            <button
              type="button"
              class="date-stepper__btn"
              :aria-label="LABEL_AUCTION_DATE_NEXT"
              :disabled="loading || !canGoNextDate"
              @click="shiftDraftTradeDate(1)"
            >
              <img class="date-stepper__icon" :src="iconChevronRight" alt="">
            </button>
          </div>
        </OdsFormField>

        <button
          type="button"
          class="auction-filter__toggle"
          :aria-expanded="filterExpanded"
          aria-controls="auction-filter-body"
          @click="toggleFilterExpanded"
        >
          {{ LABEL_AUCTION_FILTER_DETAIL }}
          <span aria-hidden="true">{{ filterExpanded ? '˄' : '˅' }}</span>
        </button>
      </div>

      <div
        v-show="filterExpanded"
        id="auction-filter-body"
        class="auction-filter__body"
      >
        <div class="auction-filter__row auction-filter__row--3">
          <OdsFormField :label="LABEL_AUCTION_VARIETY">
            <OdsSelect
              v-model="draftVariety"
              variant="form"
              :disabled="loading"
              :aria-label="LABEL_AUCTION_VARIETY"
            >
              <option :value="AUCTION_FILTER_ALL">{{ LABEL_AUCTION_FILTER_ALL }}</option>
              <option
                v-for="opt in varietyOptions"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </option>
            </OdsSelect>
          </OdsFormField>

          <OdsFormField :label="LABEL_AUCTION_MARKET">
            <OdsSelect
              v-model="draftMarketCd"
              variant="form"
              :disabled="loading"
              :aria-label="LABEL_AUCTION_MARKET"
            >
              <option
                v-for="opt in marketOptions"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </option>
            </OdsSelect>
          </OdsFormField>

          <OdsFormField :label="LABEL_AUCTION_CORP">
            <OdsSelect
              v-model="draftCorp"
              variant="form"
              :disabled="loading"
              :aria-label="LABEL_AUCTION_CORP"
            >
              <option :value="AUCTION_FILTER_ALL">{{ LABEL_AUCTION_FILTER_ALL }}</option>
              <option
                v-for="opt in corpOptions"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </option>
            </OdsSelect>
          </OdsFormField>
        </div>

        <div class="auction-filter__row auction-filter__row--origin">
          <OdsFormField :label="LABEL_AUCTION_ORIGIN" as="fieldset">
            <div
              class="origin-multi"
              role="group"
              :aria-label="LABEL_AUCTION_ORIGIN"
            >
              <button
                type="button"
                class="origin-multi__chip"
                :class="{ 'origin-multi__chip--on': draftOrigins.length === 0 }"
                :disabled="loading"
                @click="clearOrigins"
              >
                {{ LABEL_AUCTION_FILTER_ALL }}
              </button>
              <button
                v-for="opt in originOptions"
                :key="opt.value"
                type="button"
                class="origin-multi__chip"
                :class="{ 'origin-multi__chip--on': isOriginSelected(opt.value) }"
                :disabled="loading"
                @click="toggleOrigin(opt.value)"
              >
                {{ originDisplayLabel(opt.label) }}
              </button>
            </div>
          </OdsFormField>
        </div>

        <div class="auction-filter__actions" role="group" aria-label="조회 실행">
          <OdsButton variant="secondary" :disabled="loading" @click="onReset">
            {{ LABEL_AUCTION_RESET }}
          </OdsButton>
          <OdsButton :disabled="loading" @click="onLookup">
            {{ LABEL_AUCTION_LOOKUP }}
          </OdsButton>
        </div>
      </div>
    </OdsCard>

    <div class="auction-mode" role="tablist" aria-label="경매 결과 범위">
      <button
        type="button"
        role="tab"
        class="auction-mode__btn"
        :class="{ 'auction-mode__btn--on': isAllMode }"
        :aria-selected="isAllMode"
        :disabled="loading"
        @click="setResultMode(AUCTION_MODE_ALL)"
      >
        {{ LABEL_AUCTION_MODE_ALL }}
      </button>
      <button
        type="button"
        role="tab"
        class="auction-mode__btn"
        :class="{ 'auction-mode__btn--on': isMineMode }"
        :aria-selected="isMineMode"
        :disabled="loading"
        @click="setResultMode(AUCTION_MODE_MINE)"
      >
        {{ LABEL_AUCTION_MODE_MINE }}
      </button>
    </div>

    <OdsSkeleton v-if="loading && tableRows.length === 0" />

    <template v-else>
      <p v-if="showStaleHint" class="auction-stale" role="status">{{ MSG_AUCTION_STALE }}</p>

      <div v-if="loadError" class="auction-err" role="alert">
        <p class="auction-err__msg">{{ loadError }}</p>
        <OdsButton variant="secondary" :block="false" @click="onRetry">
          {{ LABEL_AUCTION_RETRY }}
        </OdsButton>
      </div>

      <div class="auction-result-head">
        <h2 class="auction-result-title">{{ resultTitle }}</h2>
        <span class="auction-result-sort">{{ LABEL_AUCTION_SORT_HINT }}</span>
      </div>

      <OdsEmptyState v-if="showEmpty" :title="emptyMessage" description="" />

      <div
        v-else-if="showTable"
        ref="tableScrollRef"
        class="auction-table-scroll"
        :class="{ 'auction-table-scroll--dragging': tableDragging }"
        @pointerdown="onTablePointerDown"
        @pointermove="onTablePointerMove"
        @pointerup="endTablePointerDrag"
        @pointercancel="endTablePointerDrag"
      >
        <table class="auction-table">
          <thead>
            <tr>
              <th scope="col" class="auction-table__th auction-table__th--time">
                {{ LABEL_AUCTION_COL_TIME }}
              </th>
              <th scope="col" class="auction-table__th">{{ LABEL_AUCTION_COL_CORP }}</th>
              <th scope="col" class="auction-table__th">{{ LABEL_AUCTION_COL_VARIETY }}</th>
              <th scope="col" class="auction-table__th">{{ LABEL_AUCTION_COL_ORIGIN }}</th>
              <th scope="col" class="auction-table__th">{{ LABEL_AUCTION_COL_SPEC }}</th>
              <th scope="col" class="auction-table__th auction-table__th--num">
                {{ colQtyHeader }}
              </th>
              <th scope="col" class="auction-table__th auction-table__th--num">
                {{ colWeightHeader }}
              </th>
              <th scope="col" class="auction-table__th auction-table__th--num">
                {{ colPriceHeader }}
              </th>
              <th scope="col" class="auction-table__th auction-table__th--num">
                {{ colAmountHeader }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in tableRows"
              :key="row.row_key"
              class="auction-table__row"
              :class="{ 'auction-table__row--clickable': row.selectable }"
              @click="onRowClick(row)"
            >
              <td class="auction-table__td auction-table__td--time">
                <span class="auction-table__time">{{ auctionTimeLabel(row.auction_time) }}</span>
                <span
                  v-if="isMineMode && statusBadgeLabel(row)"
                  class="auction-table__badge"
                  :class="{
                    'auction-table__badge--confirmed':
                      row.match_status === AUCTION_MATCH_STATUS_CONFIRMED,
                    'auction-table__badge--candidate':
                      row.match_status === AUCTION_MATCH_STATUS_CANDIDATE,
                  }"
                >
                  {{ statusBadgeLabel(row) }}
                </span>
              </td>
              <td class="auction-table__td">{{ row.corporation_name || '' }}</td>
              <td class="auction-table__td">{{ row.variety_name || '' }}</td>
              <td class="auction-table__td">
                {{ originDisplayLabel(row.origin_name) }}
              </td>
              <td class="auction-table__td">{{ row.spec_text || '' }}</td>
              <td class="auction-table__td auction-table__td--num">
                {{ formatAuctionQtyCell(row.auction_box_qty) }}
              </td>
              <td class="auction-table__td auction-table__td--num">
                {{ formatAuctionWeightCell(row.auction_weight_kg) }}
              </td>
              <td class="auction-table__td auction-table__td--num">
                {{
                  row.auction_price == null ? '' : formatAuctionWon(row.auction_price)
                }}
              </td>
              <td class="auction-table__td auction-table__td--num">
                {{ formatAuctionWon(row.auction_amount) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="isAllMode && hasMore" class="auction-more">
        <OdsButton
          variant="secondary"
          :disabled="loadingMore || loading"
          @click="onMore"
        >
          {{ LABEL_AUCTION_MORE }}
        </OdsButton>
      </div>
    </template>

    <AuctionMatchSheet
      :open="matchSheetOpen"
      :farm-cd="farmCd"
      :shipment-id="matchShipmentId"
      @close="closeMatchSheet"
      @success="onMatchSuccess"
      @status-conflict="onMatchStatusConflict"
    />
  </section>
</template>

<style scoped>
.auction {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-12);
  overflow-x: hidden;
}
.auction-filter__head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--ods-space-8);
  align-items: end;
}
.auction-filter__head :deep(.ods-form-field__label) {
  font: var(--ods-font-caption);
  font-weight: 600;
}
.auction-filter__toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin: 0;
  padding: 0 var(--ods-space-4);
  min-height: var(--ods-control-height);
  border: 0;
  background: transparent;
  color: var(--ods-color-text-secondary);
  font: var(--ods-font-caption);
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
  -webkit-tap-highlight-color: transparent;
}
.auction-filter__body {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
  margin-top: var(--ods-space-8);
  padding-top: var(--ods-space-8);
  border-top: 1px solid var(--ods-color-border);
}
.auction-filter__row {
  display: grid;
  gap: var(--ods-space-8);
  align-items: end;
}
.auction-filter__row--3 {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.auction-filter__row--origin {
  grid-template-columns: minmax(0, 1fr);
}
.auction-filter__row :deep(.ods-form-field__label) {
  font: var(--ods-font-caption);
  font-weight: 600;
}
.auction-filter__row :deep(.ods-select) {
  padding-left: var(--ods-space-8);
  padding-right: var(--ods-space-8);
}
.date-stepper {
  display: grid;
  grid-template-columns: var(--ods-touch-min) minmax(0, 1fr) var(--ods-touch-min);
  align-items: center;
  gap: var(--ods-space-4);
  min-height: var(--ods-control-height);
  padding: 0 var(--ods-space-4);
  border: 0;
  border-radius: var(--ods-radius-button);
  background: transparent;
}
.date-stepper__btn {
  display: grid;
  place-items: center;
  width: var(--ods-touch-min);
  height: var(--ods-touch-min);
  margin: 0;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--ods-color-text);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.date-stepper__btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
.date-stepper__icon {
  width: 18px;
  height: 18px;
}
.date-stepper__icon--prev {
  transform: scaleX(-1);
}
.date-stepper__value {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
  min-height: var(--ods-control-height);
}
.date-stepper__text {
  font: var(--ods-font-body-2);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--ods-color-text);
  pointer-events: none;
}
.date-stepper__native {
  position: absolute;
  inset: 0;
  z-index: 1;
  width: 100%;
  height: 100%;
  margin: 0;
  padding: 0;
  border: 0;
  opacity: 0;
  cursor: pointer;
}
.origin-multi {
  display: flex;
  flex-wrap: wrap;
  gap: var(--ods-space-6);
  max-height: 7.5rem;
  overflow-y: auto;
  padding: var(--ods-space-4);
  border: 0;
  border-radius: var(--ods-radius-button);
  background: transparent;
}
.origin-multi__chip {
  margin: 0;
  padding: 4px 10px;
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-bg-muted, #f5f5f5);
  color: var(--ods-color-text-secondary);
  font: var(--ods-font-caption);
  font-weight: 600;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.origin-multi__chip--on {
  border-color: var(--ods-color-text);
  background: var(--ods-color-white);
  color: var(--ods-color-text);
  font-weight: 700;
}
.origin-multi__chip:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.auction-filter__actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--ods-space-6);
  min-height: var(--ods-control-height);
}
.auction-filter__actions :deep(.ods-btn) {
  min-width: 0;
  padding: 0 var(--ods-space-8);
  font: var(--ods-font-caption);
  font-weight: 700;
}
.auction-mode {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
  border-bottom: 1px solid var(--ods-color-border);
}
.auction-mode__btn {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  margin: 0 0 -1px;
  padding: 0 var(--ods-space-8);
  border: none;
  border-bottom: 2px solid transparent;
  background: transparent;
  font: var(--ods-font-body-2);
  font-weight: 600;
  color: var(--ods-color-text-secondary);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.auction-mode__btn--on {
  color: var(--ods-color-primary);
  border-bottom-color: var(--ods-color-primary);
  font-weight: 700;
}
.auction-mode__btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.auction-stale {
  margin: 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.auction-err {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
.auction-err__msg {
  margin: 0;
  color: var(--ods-color-danger);
  font: var(--ods-font-form-help);
}
.auction-result-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
.auction-result-title {
  margin: 0;
  font: var(--ods-font-body-1);
  font-weight: 700;
  color: var(--ods-color-text);
}
.auction-result-sort {
  flex-shrink: 0;
  font: var(--ods-font-caption);
  color: var(--ods-color-text-secondary);
}
.auction-table-scroll {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  overflow-x: auto;
  overflow-y: hidden;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior-x: contain;
  touch-action: pan-x;
  cursor: grab;
  background: var(--ods-color-white);
  border-top: 1px solid var(--ods-color-border);
  scrollbar-width: thin;
}
.auction-table-scroll--dragging {
  cursor: grabbing;
  user-select: none;
}
.auction-table-scroll--dragging * {
  cursor: grabbing;
}
.auction-table {
  width: max-content;
  min-width: 0;
  border-collapse: collapse;
  table-layout: auto;
  font: var(--ods-font-caption);
  color: var(--ods-color-text);
}
.auction-table__th,
.auction-table__td {
  width: 1%;
  padding: 6px 6px;
  border-bottom: 1px solid var(--ods-color-border);
  text-align: left;
  white-space: nowrap;
  vertical-align: middle;
}
.auction-table__th {
  font-weight: 700;
  color: var(--ods-color-text-secondary);
  background: var(--ods-color-white);
}
.auction-table__th--num,
.auction-table__td--num {
  text-align: right;
  font-variant-numeric: tabular-nums;
  padding-left: 8px;
}
.auction-table__th--time,
.auction-table__td--time {
  position: sticky;
  left: 0;
  z-index: 1;
  width: auto;
  min-width: 3.25rem;
  padding-right: 8px;
  background: var(--ods-color-white);
  box-shadow: 1px 0 0 var(--ods-color-border);
}
.auction-table__th--time {
  z-index: 2;
}
.auction-table__time {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}
.auction-table__badge {
  display: inline-block;
  margin-left: 4px;
  padding: 0 4px;
  border-radius: 2px;
  font-size: 10px;
  font-weight: 700;
  line-height: 1.4;
  vertical-align: middle;
}
.auction-table__badge--candidate {
  color: var(--ods-color-text-secondary);
  background: var(--ods-color-bg-muted, #f5f5f5);
}
.auction-table__badge--confirmed {
  color: var(--ods-color-primary);
  background: color-mix(in srgb, var(--ods-color-primary) 12%, white);
}
.auction-table__row--clickable {
  cursor: pointer;
}
.auction-table__row--clickable:active {
  background: var(--ods-color-bg-muted, #f5f5f5);
}
.auction-table__row--clickable:active .auction-table__td--time {
  background: var(--ods-color-bg-muted, #f5f5f5);
}
.auction-more {
  display: flex;
  justify-content: center;
}
</style>
