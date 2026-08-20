import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import StockView from '@/views/stock/StockView.vue'
import { useSalesPrefillStore } from '@/composables/stores/salesPrefill'

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

  it('T9 폐기는 증가 버튼을 막고 감소는 허용한다', async () => {
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
})
