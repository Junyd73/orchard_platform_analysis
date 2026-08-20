import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import StockView from '@/features/stock/StockView.vue'
import { useSalesPrefillStore } from '@/shared/stores/salesPrefill'

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

describe('StockView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    listFruitStock.mockReset()
    listStockLogs.mockReset()
    adjustStock.mockReset()
    fetchCommonCodes.mockReset()
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

  it('T1~T9: 조정 시트 오픈 시 이력 자동조회 없음 + 폐기 방향 버튼', async () => {
    listStockLogs.mockRejectedValueOnce(new Error('boom'))
    const r = router()
    await r.push('/orders')
    await r.isReady()
    const wrapper = mount(StockView, {
      global: { plugins: [r] },
      attachTo: document.body,
    })
    await flushPromises()
    await wrapper.find('.stock-view__card').trigger('click')
    await flushPromises()
    const sheet = document.body.textContent || ''
    // 조정 시트 오픈 시 이력 API(listStockLogs)는 자동호출하지 않습니다.
    expect(listStockLogs).not.toHaveBeenCalled()
    // 오픈 직후 “이력을 불러오지 못했습니다” 문구가 노출되면 안 됩니다.
    expect(sheet).not.toContain('이력을 불러오지 못했습니다')

    // 입력 라벨/미리보기 표시 확인
    expect(sheet).toContain('조정 사유')
    expect(sheet).toContain('조정 수량')
    expect(sheet).toContain('조정 방향')
    expect(sheet).toContain('조정 후')

    expect(sheet).toContain('폐기')
    expect(sheet).toContain('파손')
    expect(sheet).toContain('실사차이')
    const btns = Array.from(document.querySelectorAll('.stock-log-adjust button'))
    const inc = btns.find((b) => (b.textContent || '').includes('증가')) as HTMLButtonElement | undefined
    const dec = btns.find((b) => (b.textContent || '').includes('감소')) as HTMLButtonElement | undefined
    expect(inc?.disabled).toBe(true)
    expect(dec?.disabled).toBe(false)
    wrapper.unmount()
  })

  it('T6~T7 조정 성공 시 완료 메시지(사유/증감/수량/결과수량) 표시', async () => {
    const r = router()
    await r.push('/orders')
    await r.isReady()
    const wrapper = mount(StockView, { global: { plugins: [r] }, attachTo: document.body })
    await flushPromises()

    await wrapper.find('.stock-view__card').trigger('click')
    await flushPromises()

    // 감소(OUT) 선택
    const decBtn = Array.from(document.querySelectorAll('.stock-log-adjust button')).find(
      (b) => (b.textContent || '').includes('감소'),
    ) as HTMLButtonElement | undefined
    expect(decBtn).toBeTruthy()
    decBtn?.click()
    await flushPromises()

    // 조정 적용
    const applyBtn = Array.from(document.querySelectorAll('.stock-log-adjust button')).find(
      (b) => (b.textContent || '').includes('조정 적용'),
    ) as HTMLButtonElement | undefined
    expect(applyBtn).toBeTruthy()
    applyBtn?.click()
    await flushPromises()

    const sheet = document.body.textContent || ''
    expect(sheet).toContain('재고 조정이 완료되었습니다')
    expect(sheet).toContain('폐기')
    expect(sheet).toContain('감소')
    expect(sheet).toContain('현재 10박스')
    wrapper.unmount()
  })

  it('T8 감소 초과 시 가용재고 초과 오류 안내 + API 호출 차단', async () => {
    const r = router()
    await r.push('/orders')
    await r.isReady()
    const wrapper = mount(StockView, { global: { plugins: [r] }, attachTo: document.body })
    await flushPromises()

    await wrapper.find('.stock-view__card').trigger('click')
    await flushPromises()

    // 감소(OUT) 선택
    const decBtn = Array.from(document.querySelectorAll('.stock-log-adjust button')).find(
      (b) => (b.textContent || '').includes('감소'),
    ) as HTMLButtonElement | undefined
    decBtn?.click()
    await flushPromises()

    // 조정 수량을 11(가용 10 초과)로 입력
    const qtyInput = document.querySelector('.stock-log-adjust input.ods-input') as HTMLInputElement | null
    expect(qtyInput).toBeTruthy()
    qtyInput!.value = '11'
    qtyInput!.dispatchEvent(new InputEvent('input', { bubbles: true }))
    await flushPromises()

    // Vue v-model이 반영되었는지(입력값이 유지되는지) 확인
    expect(qtyInput!.value).toBe('11')

    const sheetAfterEdit = document.body.textContent || ''
    expect(sheetAfterEdit).toContain('11박스')

    const applyBtn = Array.from(document.querySelectorAll('.stock-log-adjust button')).find(
      (b) => (b.textContent || '').includes('조정 적용'),
    ) as HTMLButtonElement | undefined
    expect(applyBtn).toBeTruthy()
    // 미리보기 경고 상태에서는 “조정 적용”이 비활성화되어 API 호출을 막습니다.
    expect(applyBtn?.disabled).toBe(true)

    const sheet = document.body.textContent || ''
    expect(sheet).toContain('가용재고보다 많이 줄일 수 없습니다')
    // 실패 시도이므로 adjustStock 호출은 0건이어야 합니다.
    expect(adjustStock).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('T9 이력 아코디언: 최초만 조회 + 접힘/재펼침은 캐시 사용', async () => {
    listStockLogs.mockRejectedValueOnce(new Error('boom'))
    const r = router()
    await r.push('/orders')
    await r.isReady()
    const wrapper = mount(StockView, { global: { plugins: [r] }, attachTo: document.body })
    await flushPromises()

    await wrapper.find('.stock-view__card').trigger('click')
    await flushPromises()
    expect(listStockLogs).not.toHaveBeenCalled()

    const histBtn = document.querySelector('.stock-log-history-accordion-btn') as HTMLButtonElement | null
    expect(histBtn).toBeTruthy()
    histBtn!.click() // 펼침(최초 조회)
    await flushPromises()

    expect(listStockLogs).toHaveBeenCalledTimes(1)
    const sheet = document.body.textContent || ''
    expect(sheet).toContain('이력을 불러오지 못했습니다')

    // 접힘: 추가 API 호출 없음
    histBtn!.click()
    await flushPromises()
    expect(listStockLogs).toHaveBeenCalledTimes(1)

    // 재펼침: 불필요 재호출 금지(캐시 유지)
    histBtn!.click()
    await flushPromises()
    expect(listStockLogs).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })
})
