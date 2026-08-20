import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import StockView from '@/features/stock/StockView.vue'
import { useSalesPrefillStore } from '@/shared/stores/salesPrefill'
import {
  REASON_COUNT_DIFF,
  REASON_DISPOSE,
  REASON_OTHER,
  REASON_RETURN,
} from '@/features/stock/stockAdjustConstants'

const listFruitStock = vi.fn()
const listStockLogs = vi.fn()
const adjustStock = vi.fn()
const fetchCommonCodes = vi.fn()

vi.mock('@/api/stock', () => ({
  listFruitStock: (...args: unknown[]) => listFruitStock(...args),
  listStockLogs: (...args: unknown[]) => listStockLogs(...args),
  adjustStock: (...args: unknown[]) => adjustStock(...args),
}))

vi.mock('@/api/commonCodes', () => ({
  fetchCommonCodes: (...args: unknown[]) => fetchCommonCodes(...args),
}))

function router() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/orders', name: 'orders', component: { template: '<div />' } },
      { path: '/orders/ship', name: 'ship-confirm', component: { template: '<div />' } },
    ],
  })
}

async function openSheet() {
  const r = router()
  await r.push('/orders')
  await r.isReady()
  const wrapper = mount(StockView, { global: { plugins: [r] }, attachTo: document.body })
  await flushPromises()
  await wrapper.find('.stock-view__card').trigger('click')
  await flushPromises()
  return wrapper
}

function dirButtons() {
  const btns = Array.from(document.querySelectorAll('.stock-log-adjust__btns button'))
  const inc = btns.find((b) => (b.textContent || '').includes('증가')) as HTMLButtonElement | undefined
  const dec = btns.find((b) => (b.textContent || '').includes('감소')) as HTMLButtonElement | undefined
  return { inc, dec }
}

async function setReason(value: string) {
  const el = document.querySelector('.stock-log-adjust select') as HTMLSelectElement | null
  expect(el).toBeTruthy()
  await new DOMWrapper(el!).setValue(value)
  await flushPromises()
}

async function setQty(value: string) {
  const el = document.querySelector('.stock-log-adjust input.ods-input') as HTMLInputElement | null
  expect(el).toBeTruthy()
  await new DOMWrapper(el!).setValue(value)
  await flushPromises()
}

describe('StockView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    listFruitStock.mockReset()
    listStockLogs.mockReset()
    adjustStock.mockReset()
    fetchCommonCodes.mockReset()
    vi.restoreAllMocks()
    listFruitStock.mockResolvedValue([
      {
        farm_cd: 'OR001', wh_cd: 'WH01', item_cd: 'FR010100', item_nm: '배 상품',
        variety_cd: 'FR010101', variety_nm: '신고',
        grade_cd: 'GR010100', grade_nm: '특',
        size_cd: 'FR020101', size_nm: '25과',
        weight: 15, harvest_year: 2026, storage_dt: '2026-08-19',
        in_qty: 10, out_qty: 0, real_qty: 10, reserved_qty: 0, available_qty: 10,
      },
    ])
    listStockLogs.mockResolvedValue([])
    fetchCommonCodes.mockResolvedValue([])
    adjustStock.mockResolvedValue({ ok: true, qty: 1, io_type: 'OUT' })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
  })

  it('mount 시 fruit-stock을 조회하고 가용/현재를 표시', async () => {
    const wrapper = mount(StockView, { global: { plugins: [router()] } })
    await flushPromises()
    expect(listFruitStock).toHaveBeenCalled()
    expect(wrapper.text()).toContain('가용')
    expect(wrapper.text()).toContain('현재 10')
  })

  it('원물 탭 전환 시 item_cd=FR010300으로 재조회', async () => {
    const wrapper = mount(StockView, { global: { plugins: [router()] } })
    await flushPromises()
    listFruitStock.mockClear()
    const tabs = wrapper.findAll('button.stock-view__type-btn')
    await tabs[1].trigger('click')
    await flushPromises()
    expect(listFruitStock.mock.calls.at(-1)?.[1]).toMatchObject({ item_cd: 'FR010300' })
  })

  it('배즙 탭은 일반·도라지·레거시 item_cd를 함께 조회한다', async () => {
    const wrapper = mount(StockView, { global: { plugins: [router()] } })
    await flushPromises()
    listFruitStock.mockClear()
    const tabs = wrapper.findAll('button.stock-view__type-btn')
    await tabs[2].trigger('click')
    await flushPromises()
    const itemCds = listFruitStock.mock.calls.map((c) => c[1]?.item_cd).sort()
    expect(itemCds).toEqual(['FR010200', 'FR010201', 'FR010202'])
  })

  it('상품 카드 판매는 규격만 넘기고 stock_seq 없음', async () => {
    const r = router()
    await r.push('/orders')
    await r.isReady()
    const wrapper = mount(StockView, { global: { plugins: [r] } })
    await flushPromises()
    const store = useSalesPrefillStore()
    await wrapper.find('.stock-view__sell').trigger('click')
    expect(store.shipLines[0].variety_cd).toBe('FR010101')
    expect(JSON.stringify(store.shipLines[0])).not.toContain('stock_seq')
    expect(store.shipMode).toBe('DIRECT')
    expect(store.orderNo).toBeNull()
  })

  it('선택 판매는 여러 재고를 한 번에 담는다', async () => {
    listFruitStock.mockResolvedValue([
      {
        farm_cd: 'OR001', wh_cd: 'WH01', item_cd: 'FR010100', item_nm: '배 상품',
        variety_cd: 'FR010101', variety_nm: '신고',
        grade_cd: 'GR010100', grade_nm: '특',
        size_cd: 'FR020101', size_nm: '25과',
        weight: 15, harvest_year: 2026, storage_dt: '2026-08-19',
        in_qty: 10, out_qty: 0, real_qty: 10, reserved_qty: 0, available_qty: 10,
      },
      {
        farm_cd: 'OR001', wh_cd: 'WH01', item_cd: 'FR010202', item_nm: '순배즙',
        variety_cd: 'FR010101', variety_nm: '신고',
        grade_cd: 'NONE', grade_nm: '',
        size_cd: 'SZ010100', size_nm: '5kg',
        weight: 30, harvest_year: 2026, storage_dt: '2026-08-19',
        in_qty: 5, out_qty: 0, real_qty: 5, reserved_qty: 0, available_qty: 5,
      },
    ])
    const r = router()
    await r.push('/orders')
    await r.isReady()
    const wrapper = mount(StockView, { global: { plugins: [r] } })
    await flushPromises()
    const boxes = wrapper.findAll('.stock-view__pick input')
    await boxes[0].trigger('click')
    await boxes[1].trigger('click')
    await flushPromises()
    await wrapper.get('.stock-view__batch button').trigger('click')
    const store = useSalesPrefillStore()
    expect(store.shipLines).toHaveLength(2)
    expect(store.shipLines[1].item_cd).toBe('FR010202')
  })

  it('T1 폐기: 증가 disabled / 감소 enabled + 이력 자동조회 없음', async () => {
    const wrapper = await openSheet()
    expect(listStockLogs).not.toHaveBeenCalled()
    const { inc, dec } = dirButtons()
    expect(inc?.disabled).toBe(true)
    expect(dec?.disabled).toBe(false)
    expect(document.body.textContent || '').toContain('감소')
    expect(document.body.textContent || '').not.toContain('조정 적용')
    expect(document.querySelector('.stock-log-adjust__row')).toBeTruthy()
    wrapper.unmount()
  })

  it('T2 반품: 증가 enabled / 감소 disabled', async () => {
    const wrapper = await openSheet()
    await setReason(REASON_RETURN)
    const { inc, dec } = dirButtons()
    expect(inc?.disabled).toBe(false)
    expect(dec?.disabled).toBe(true)
    expect(document.body.textContent || '').toContain('증가')
    wrapper.unmount()
  })

  it('T3 실사차이/기타: 증가·감소 모두 enabled', async () => {
    const wrapper = await openSheet()
    await setReason(REASON_COUNT_DIFF)
    let btns = dirButtons()
    expect(btns.inc?.disabled).toBe(false)
    expect(btns.dec?.disabled).toBe(false)
    await setReason(REASON_OTHER)
    btns = dirButtons()
    expect(btns.inc?.disabled).toBe(false)
    expect(btns.dec?.disabled).toBe(false)
    wrapper.unmount()
  })

  it('T4 사유 변경 시 금지 방향이 남지 않음', async () => {
    const wrapper = await openSheet()
    await setReason(REASON_RETURN)
    expect((document.body.textContent || '')).toContain('증가')
    await setReason(REASON_DISPOSE)
    const sheet = document.body.textContent || ''
    expect(sheet).toContain('감소')
    expect(sheet).not.toMatch(/폐기 · \d+박스 증가/)
    const { inc, dec } = dirButtons()
    expect(inc?.disabled).toBe(true)
    expect(dec?.disabled).toBe(false)
    wrapper.unmount()
  })

  it('T5 폐기 + qty3 → 미리보기 감소 / 조정 후 7', async () => {
    const wrapper = await openSheet()
    await setQty('3')
    const sheet = document.body.textContent || ''
    expect(sheet).toContain('폐기 · 3박스 감소')
    expect(sheet).toContain('조정 후 7박스')
    wrapper.unmount()
  })

  it('T6 반품 + qty2 → 미리보기 증가 / 조정 후 12', async () => {
    const wrapper = await openSheet()
    await setReason(REASON_RETURN)
    await setQty('2')
    const sheet = document.body.textContent || ''
    expect(sheet).toContain('반품 · 2박스 증가')
    expect(sheet).toContain('조정 후 12박스')
    wrapper.unmount()
  })

  it('T7~T9 confirm 후 adjustStock 호출 / 취소 시 미호출', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const wrapper = await openSheet()
    await setQty('3')
    const { dec } = dirButtons()
    dec?.click()
    await flushPromises()
    expect(confirmSpy).toHaveBeenCalled()
    expect(adjustStock).not.toHaveBeenCalled()
    expect(document.querySelector('.stock-log-sheet')).toBeTruthy()

    confirmSpy.mockReturnValue(true)
    confirmSpy.mockClear()
    dec?.click()
    await flushPromises()
    expect(confirmSpy).toHaveBeenCalledTimes(1)
    expect(adjustStock).toHaveBeenCalledTimes(1)
    expect(adjustStock.mock.calls[0][1]).toMatchObject({ io_type: 'OUT', qty: 3, reason_cd: REASON_DISPOSE })
    wrapper.unmount()
  })

  it('T10 OUT 초과 시 confirm/API 금지 + 오류 표시', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    confirmSpy.mockClear()
    const wrapper = await openSheet()
    await setQty('11')
    const { dec } = dirButtons()
    dec?.click()
    await flushPromises()
    expect(confirmSpy).not.toHaveBeenCalled()
    expect(adjustStock).not.toHaveBeenCalled()
    expect(document.body.textContent || '').toContain('가용재고보다 많이 줄일 수 없습니다')
    expect(document.querySelector('.stock-log-sheet')).toBeTruthy()
    wrapper.unmount()
  })

  it('T11 성공 시 목록 reload + sheet close + 메인 성공 메시지', async () => {
    listFruitStock
      .mockResolvedValueOnce([
        {
          farm_cd: 'OR001', wh_cd: 'WH01', item_cd: 'FR010100', item_nm: '배 상품',
          variety_cd: 'FR010101', variety_nm: '신고',
          grade_cd: 'GR010100', grade_nm: '특',
          size_cd: 'FR020101', size_nm: '25과',
          weight: 15, harvest_year: 2026, storage_dt: '2026-08-19',
          in_qty: 10, out_qty: 0, real_qty: 10, reserved_qty: 0, available_qty: 10,
        },
      ])
      .mockResolvedValue([
        {
          farm_cd: 'OR001', wh_cd: 'WH01', item_cd: 'FR010100', item_nm: '배 상품',
          variety_cd: 'FR010101', variety_nm: '신고',
          grade_cd: 'GR010100', grade_nm: '특',
          size_cd: 'FR020101', size_nm: '25과',
          weight: 15, harvest_year: 2026, storage_dt: '2026-08-19',
          in_qty: 10, out_qty: 3, real_qty: 7, reserved_qty: 0, available_qty: 7,
        },
      ])
    const wrapper = await openSheet()
    await setQty('3')
    dirButtons().dec?.click()
    await flushPromises()
    expect(document.querySelector('.stock-log-sheet')).toBeNull()
    expect(wrapper.text()).toContain('재고 조정이 완료되었습니다')
    expect(wrapper.text()).toContain('폐기')
    expect(wrapper.text()).toContain('3박스 감소')
    expect(wrapper.text()).toContain('현재 7박스')
    expect(wrapper.text()).toContain('현재 7')
    wrapper.unmount()
  })

  it('T12 실패 시 sheet 유지 + 입력값 유지', async () => {
    adjustStock.mockRejectedValueOnce(new Error('boom'))
    const wrapper = await openSheet()
    await setQty('2')
    dirButtons().dec?.click()
    await flushPromises()
    expect(document.querySelector('.stock-log-sheet')).toBeTruthy()
    const qtyInput = document.querySelector('.stock-log-adjust input.ods-input') as HTMLInputElement
    expect(qtyInput.value).toBe('2')
    expect(document.body.textContent || '').toContain('재고를 조정하지 못했습니다')
    wrapper.unmount()
  })

  it('T14 조정 적용/취소 버튼 제거', async () => {
    const wrapper = await openSheet()
    const text = document.body.textContent || ''
    expect(text).not.toContain('조정 적용')
    const cancelOnly = Array.from(document.querySelectorAll('.stock-log-adjust button'))
      .filter((b) => (b.textContent || '').trim() === '취소')
    expect(cancelOnly).toHaveLength(0)
    wrapper.unmount()
  })

  it('T15 이력 아코디언: 최초만 조회 + 접힘/재펼침 캐시', async () => {
    listStockLogs.mockRejectedValueOnce(new Error('boom'))
    const wrapper = await openSheet()
    expect(listStockLogs).not.toHaveBeenCalled()

    const histBtn = document.querySelector('.stock-log-history-accordion-btn') as HTMLButtonElement | null
    expect(histBtn).toBeTruthy()
    histBtn!.click()
    await flushPromises()
    expect(listStockLogs).toHaveBeenCalledTimes(1)
    expect(document.body.textContent || '').toContain('이력을 불러오지 못했습니다')

    histBtn!.click()
    await flushPromises()
    expect(listStockLogs).toHaveBeenCalledTimes(1)

    histBtn!.click()
    await flushPromises()
    expect(listStockLogs).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })
})
