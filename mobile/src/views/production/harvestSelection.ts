import type { HarvestConsumptionIn, HarvestRecord } from '@/api/production'

export type HarvestSelectionMap = Record<string, number>

export function isHarvestSelectable(row: HarvestRecord): boolean {
  return Number(row.remaining_container_qty ?? 0) > 0
}

export function harvestAnchor(
  rows: HarvestRecord[],
  selected: HarvestSelectionMap,
): HarvestRecord | null {
  const ids = Object.keys(selected)
  if (!ids.length) return null
  return rows.find((r) => r.work_id === ids[0]) ?? null
}

export function canSelectHarvestRow(
  row: HarvestRecord,
  anchor: HarvestRecord | null,
): { ok: boolean; message?: string } {
  if (!isHarvestSelectable(row)) {
    return { ok: false }
  }
  if (!anchor) return { ok: true }
  if (row.work_id === anchor.work_id) return { ok: true }
  if (row.variety_cd !== anchor.variety_cd) {
    return { ok: false, message: '같은 품종의 수확기록만 함께 사용할 수 있습니다.' }
  }
  if (Number(row.harvest_year) !== Number(anchor.harvest_year)) {
    return { ok: false, message: '같은 수확연도의 기록만 함께 사용할 수 있습니다.' }
  }
  return { ok: true }
}

export function formatHarvestRowLabel(row: HarvestRecord): string {
  const dt = String(row.work_dt || '').slice(0, 10)
  const variety = row.variety_nm || row.variety_cd || ''
  const orig = Number(row.harvest_container_qty || 0)
  const consumed = Number(row.consumed_container_qty || 0)
  const remaining = Number(row.remaining_container_qty || 0)
  return `${dt} ${variety} · 수확 ${orig} · 사용 ${consumed} · 남음 ${remaining}`
}

export function harvestSelectionSummary(selected: HarvestSelectionMap): string {
  const count = Object.keys(selected).length
  const total = Object.values(selected).reduce((sum, qty) => sum + qty, 0)
  if (count <= 0) return ''
  return `수확기록 ${count}건 · 사용 ${total}상자`
}

export function buildHarvestConsumptions(
  rows: HarvestRecord[],
  selected: HarvestSelectionMap,
): HarvestConsumptionIn[] {
  const byId = new Map(rows.map((r) => [r.work_id, r]))
  return Object.entries(selected)
    .map(([workId, qty]) => ({
      work_id: workId,
      qty: Number(qty),
    }))
    .filter((item) => {
      const row = byId.get(item.work_id)
      return row && Number.isInteger(item.qty) && item.qty >= 1
    })
}

export function validateHarvestSelections(
  rows: HarvestRecord[],
  selected: HarvestSelectionMap,
): string {
  const entries = buildHarvestConsumptions(rows, selected)
  if (!entries.length) return '수확 기록을 선택해 주세요.'
  const byId = new Map(rows.map((r) => [r.work_id, r]))
  for (const item of entries) {
    const row = byId.get(item.work_id)
    if (!row) return '수확 기록을 선택해 주세요.'
    if (item.qty > Number(row.remaining_container_qty || 0)) {
      return '선택한 수확량의 남은 상자수를 초과했습니다.'
    }
  }
  const years = new Set(entries.map((e) => Number(byId.get(e.work_id)?.harvest_year || 0)))
  const varieties = new Set(entries.map((e) => String(byId.get(e.work_id)?.variety_cd || '')))
  if (years.size > 1) return '같은 수확연도의 기록만 함께 사용할 수 있습니다.'
  if (varieties.size > 1) return '같은 품종의 수확기록만 함께 사용할 수 있습니다.'
  return ''
}

export function mapProductionHarvestError(
  code: string | undefined,
  fallback: string,
): string {
  switch (code) {
    case 'HARVEST_EXCEED':
      return '선택한 수확량의 남은 상자수를 초과했습니다.'
    case 'MIXED_VARIETY':
      return '같은 품종의 수확기록만 사용할 수 있습니다.'
    case 'MIXED_YEAR':
      return '같은 수확연도의 기록만 사용할 수 있습니다.'
    case 'HARVEST_SCHEMA':
    case 'HARVEST_TRACE_SCHEMA':
      return '시스템 준비가 필요합니다. 관리자에게 문의해 주세요.'
    default:
      return fallback
  }
}
