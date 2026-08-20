import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import StockView from '@/views/stock/StockView.vue'
import { useSalesPrefillStore } from '@/composables/stores/salesPrefill'
import {
  REASON_COUNT_DIFF,
  REASON_DISPOSE,
  REASON_OTHER,
  REASON_RETURN,
} from '@/views/stock/stockAdjustConstants'

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
      { path: '/orders/sales-preview', name: 'sales-preview', component: { template: '<div />' } },
    ],
  })
}

async function openSheet() {
  const r = router()
  await r.push('/orders')
  await r.isReady()
  const wrapper = mount(StockView, { global: { plugins: [r] }, attachTo: document.body })
  await flushPromises()
  await wrapper.find('.stock-view__row').trigger('click')
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

  it('mount 시 fruit-stock을 조회하고 1행 리스트로 가용수량을 표시', async () => {
    const wrapper = mount(StockView, { global: { plugins: [router()] } })
    await flushPromises()
    expect(listFruitStock).toHaveBeenCalled()
    expect(wrapper.find('.stock-view__row').exists()).toBe(true)
    expect(wrapper.find('.stock-view__card').exists()).toBe(false)
    expect(wrapper.text()).toContain('10박스')
    expect(wrapper.text()).not.toContain('현재 10')
    expect(wrapper.text()).not.toMatch(/가용(?!\d)/)
  })

  it('T1~T4 목록 1행 구조: 체크/상품정보/가용수량 (개별 판매 없음)', async () => {
    const wrapper = mount(StockView, { global: { plugins: [router()] } })
    await flushPromises()
    const row = wrapper.find('.stock-view__row')
    expect(row.exists()).toBe(true)
    expect(row.find('.stock-view__pick input').exists()).toBe(true)
    expect(row.find('.stock-view__row-title').text()).toContain('신고 · 15kg · 25과 · 특')
    expect(row.find('.stock-view__row-qty').text()).toContain('10박스')
    expect(row.find('.stock-view__sell').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('현재 10')
  })

  it('T8 체크 클릭은 선택만 하고 조정 시트를 열지 않음', async () => {
    const wrapper = mount(StockView, { global: { plugins: [router()], attachTo: document.body } })
    await flushPromises()
    await wrapper.find('.stock-view__pick input').trigger('click')
    await flushPromises()
    expect(document.querySelector('.stock-log-sheet')).toBeNull()
    expect(wrapper.find('.stock-view__row--selected').exists()).toBe(true)
    wrapper.unmount()
  })

  it('P1 선택 후 판매 미리보기 진입', async () => {
    const r = router()
    await r.push('/orders')
    await r.isReady()
    const wrapper = mount(StockView, { global: { plugins: [r] } })
    await flushPromises()
    await wrapper.find('.stock-view__pick input').trigger('click')
    await flushPromises()
    await wrapper.get('.stock-view__batch button').trigger('click')
    await flushPromises()
    expect(r.currentRoute.value.name).toBe('sales-preview')
    const store = useSalesPrefillStore()
    expect(store.shipLines).toHaveLength(1)
    expect(store.shipLines[0].qty).toBe(1)
    wrapper.unmount()
  })

  it('T10 행 클릭 시 조정 시트 open', async () => {
    const wrapper = await openSheet()
    expect(document.querySelector('.stock-log-sheet')).toBeTruthy()
    wrapper.unmount()
  })

  it('T12 소진 재고는 선택 불가', async () => {
    listFruitStock.mockResolvedValue([
      {
        farm_cd: 'OR001', wh_cd: 'WH01', item_cd: 'FR010100', item_nm: '배 상품',
        variety_cd: 'FR010101', variety_nm: '신고',
        grade_cd: 'GR010100', grade_nm: '특',
        size_cd: 'FR020101', size_nm: '25과',
        weight: 15, harvest_year: 2026, storage_dt: '2026-08-19',
        in_qty: 0, out_qty: 0, real_qty: 0, reserved_qty: 0, available_qty: 0,
      },
    ])
    const wrapper = mount(StockView, { global: { plugins: [router()] } })
    await flushPromises()
    expect(wrapper.find('.stock-view__pick input').exists()).toBe(false)
    expect(wrapper.text()).toContain('0박스')
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

  it('T5~T7 판매예정 문구 + 선택0에서도 미리보기 활성', async () => {
    const r = router()
    await r.push('/orders')
    await r.isReady()
    const wrapper = mount(StockView, { global: { plugins: [r] } })
    await flushPromises()
    expect(wrapper.find('.stock-view__batch').exists()).toBe(false)

    const store = useSalesPrefillStore()
    store.mergeFromStockRows([
      {
        farm_cd: 'OR001', wh_cd: 'WH01', item_cd: 'FR010100', item_nm: '배 상품',
        variety_cd: 'FR010101', variety_nm: '신고',
        grade_cd: 'GR010100', grade_nm: '특',
        size_cd: 'FR020101', size_nm: '25과',
        weight: 15, harvest_year: 2026, storage_dt: '2026-08-19',
        in_qty: 10, out_qty: 0, real_qty: 10, reserved_qty: 0, available_qty: 10,
      },
    ])
    await flushPromises()
    expect(wrapper.find('.stock-view__batch').exists()).toBe(true)
    expect(wrapper.text()).toContain('선택 0건')
    expect(wrapper.text()).toContain('판매예정 1건')
    expect(wrapper.text()).not.toMatch(/\bdraft\b/i)
    expect(wrapper.find('.stock-view').classes()).toContain('stock-view--with-batch')
    expect(wrapper.find('.stock-view__batch').classes()).toContain('stock-view__batch')

    await wrapper.get('.stock-view__batch button').trigger('click')
    await flushPromises()
    expect(r.currentRoute.value.name).toBe('sales-preview')
    wrapper.unmount()
  })

  it('T1 선택 1건 → fixed action bar 표시', async () => {
    const wrapper = mount(StockView, { global: { plugins: [router()] } })
    await flushPromises()
    await wrapper.find('.stock-view__pick input').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('선택 1건')
    expect(wrapper.find('.stock-view__batch').exists()).toBe(true)
    expect(wrapper.find('.stock-view').classes()).toContain('stock-view--with-batch')
  })

  it('선택 다건은 판매 미리보기 draft에 병합한다', async () => {
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
        farm_cd: 'OR001', wh_cd: 'WH01', item_cd: 'FR010100', item_nm: '배 상품',
        variety_cd: 'FR010101', variety_nm: '신고',
        grade_cd: 'GR010200', grade_nm: '상',
        size_cd: 'FR020102', size_nm: '30과',
        weight: 15, harvest_year: 2026, storage_dt: '2026-08-19',
        in_qty: 5, out_qty: 0, real_qty: 5, reserved_qty: 0, available_qty: 5,
      },
    ])
    const r = router()
    await r.push('/orders')
    await r.isReady()
    const wrapper = mount(StockView, { global: { plugins: [r] } })
    await flushPromises()
    const boxes = wrapper.findAll('.stock-view__pick input')
    expect(boxes).toHaveLength(2)
    await boxes[0].trigger('click')
    await boxes[1].trigger('click')
    await flushPromises()
    await wrapper.get('.stock-view__batch button').trigger('click')
    await flushPromises()
    const store = useSalesPrefillStore()
    expect(store.shipLines).toHaveLength(2)
    expect(store.shipLines.map((l) => l.grade_cd).sort()).toEqual(['GR010100', 'GR010200'])
    expect(r.currentRoute.value.name).toBe('sales-preview')
    wrapper.unmount()
  })

  it('조정 시트: 헤더 단순화 + summary 제거 + 수량 min=1', async () => {
    const wrapper = await openSheet()
    const sheet = document.body.textContent || ''
    expect(sheet).toContain('신고 · 15kg · 25과 · 특')
    expect(sheet).not.toContain('신고 · 15kg · 25과 · 특 · 재고 조정')
    expect(sheet).not.toContain('배정 0')
    expect(sheet).not.toContain('가용 10')
    expect(listStockLogs).not.toHaveBeenCalled()
    expect(document.querySelector('.stock-log-adjust__row')).toBeTruthy()

    const qtyInput = document.querySelector('.stock-log-adjust input.ods-input') as HTMLInputElement | null
    expect(qtyInput?.getAttribute('min')).toBe('1')
    expect(qtyInput?.getAttribute('step')).toBe('1')
    wrapper.unmount()
  })

  it('T5 qty=0 차단 + API 호출 없음', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    confirmSpy.mockClear()
    const wrapper = await openSheet()
    await setQty('0')
    dirButtons().dec?.click()
    await flushPromises()
    expect(confirmSpy).not.toHaveBeenCalled()
    expect(adjustStock).not.toHaveBeenCalled()
    expect(document.body.textContent || '').toContain('조정 수량은 1 이상 입력해 주세요.')
    wrapper.unmount()
  })

  it('T6 qty=-1 차단 + 미리보기에 음수 반영 없음', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    confirmSpy.mockClear()
    const wrapper = await openSheet()
    await setQty('-1')
    const sheetBefore = document.body.textContent || ''
    expect(sheetBefore).toContain('조정 수량은 1 이상 입력해 주세요.')
    expect(sheetBefore).not.toContain('폐기 · -1박스 감소')
    dirButtons().dec?.click()
    await flushPromises()
    expect(confirmSpy).not.toHaveBeenCalled()
    expect(adjustStock).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('T7 qty=빈값 차단', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    confirmSpy.mockClear()
    const wrapper = await openSheet()
    await setQty('')
    dirButtons().dec?.click()
    await flushPromises()
    expect(confirmSpy).not.toHaveBeenCalled()
    expect(adjustStock).not.toHaveBeenCalled()
    expect(document.body.textContent || '').toContain('조정 수량은 1 이상 입력해 주세요.')
    wrapper.unmount()
  })

  it('T8 qty=3 + 감소 confirm 문구', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const wrapper = await openSheet()
    await setQty('3')
    dirButtons().dec?.click()
    await flushPromises()
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('3박스를 감소하시겠습니까?'))
    expect(adjustStock).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('T9 qty=3 + 증가 confirm 문구', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const wrapper = await openSheet()
    await setReason(REASON_RETURN)
    await setQty('3')
    dirButtons().inc?.click()
    await flushPromises()
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('3박스를 증가하시겠습니까?'))
    expect(adjustStock).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('T10 폐기/파손/증정은 감소만 가능', async () => {
    const wrapper = await openSheet()
    const reasons = ['AD010101', 'AD010102', 'AD010103']
    for (const reason of reasons) {
      await setReason(reason)
      const { inc, dec } = dirButtons()
      expect(inc?.disabled).toBe(true)
      expect(dec?.disabled).toBe(false)
    }
    wrapper.unmount()
  })

  it('T11 반품은 증가만 가능', async () => {
    const wrapper = await openSheet()
    await setReason(REASON_RETURN)
    const { inc, dec } = dirButtons()
    expect(inc?.disabled).toBe(false)
    expect(dec?.disabled).toBe(true)
    wrapper.unmount()
  })

  it('T12 실사차이/기타는 양방향 가능', async () => {
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

  it('T13 미리보기는 양수 수량만 사용', async () => {
    const wrapper = await openSheet()
    await setQty('-3')
    const sheet = document.body.textContent || ''
    expect(sheet).toContain('조정 수량은 1 이상 입력해 주세요.')
    expect(sheet).not.toContain('조정 후 13박스')
    expect(sheet).not.toContain('폐기 · -3박스 감소')
    wrapper.unmount()
  })

  it('T14 성공 시 목록 reload + sheet close + 메인 성공 메시지', async () => {
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

  it('T14 실패 시 sheet 유지 + 입력값 유지', async () => {
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
