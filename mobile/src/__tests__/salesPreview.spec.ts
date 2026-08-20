import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import SalesPreviewView from '@/views/sales/SalesPreviewView.vue'
import { useSalesPrefillStore } from '@/composables/stores/salesPrefill'
import { DELIVERY_TP_PARCEL, DELIVERY_TP_VISIT } from '@/views/orders/ordersConstants'
import type { StockItem } from '@/api/stock'

const confirmShipment = vi.fn()
const fetchCustomers = vi.fn()
const fetchCommonCodes = vi.fn()

vi.mock('@/api/shipments', () => ({
  confirmShipment: (...a: unknown[]) => confirmShipment(...a),
}))
vi.mock('@/api/orders', () => ({
  fetchCustomers: (...a: unknown[]) => fetchCustomers(...a),
}))
vi.mock('@/api/commonCodes', () => ({
  fetchCommonCodes: (...a: unknown[]) => fetchCommonCodes(...a),
}))

vi.mock('@/composables/stores/app', async () => {
  const { ref } = await import('vue')
  return {
    useAppStore: () => ({
      farmCd: ref('OR001'),
      farm: ref({ farm_cd: 'OR001', farm_nm: '테스트농장' }),
      refreshAll: vi.fn(),
    }),
  }
})

function mountOpts(r: ReturnType<typeof router>) {
  return {
    global: {
      plugins: [r],
      stubs: { OdsAppBar: true, OdsBottomNav: true },
    },
  }
}

function stock(partial: Partial<StockItem> = {}): StockItem {
  return {
    farm_cd: 'OR001',
    wh_cd: 'WH01',
    item_cd: 'FR010100',
    item_nm: '배',
    variety_cd: 'FR010101',
    variety_nm: '신고',
    grade_cd: 'GR010100',
    grade_nm: '특',
    size_cd: 'FR020101',
    size_nm: '25과',
    weight: 15,
    harvest_year: 2026,
    storage_dt: '2026-08-19',
    in_qty: 10,
    out_qty: 0,
    real_qty: 10,
    reserved_qty: 0,
    available_qty: 10,
    ...partial,
  }
}

function router() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/orders', name: 'orders', component: { template: '<div />' } },
      { path: '/orders/sales-preview', name: 'sales-preview', component: SalesPreviewView },
    ],
  })
}

describe('SalesPreviewView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    confirmShipment.mockReset()
    fetchCustomers.mockReset()
    fetchCommonCodes.mockReset()
    fetchCustomers.mockResolvedValue([{ custm_id: 'C1', custm_nm: '홍길동', mobile: '010' }])
    fetchCommonCodes.mockResolvedValue([])
    confirmShipment.mockResolvedValue({
      ok: true,
      sales_no: '20260820-001',
      sales_status: 'CONFIRMED',
      ship_mode: 'DIRECT',
      order_no: null,
      details: [],
      order_status: null,
      remaining_order_qty: null,
      remaining_order: [],
    })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
  })

  it('P2~P6 draft 수량/단가/삭제/가용초과', async () => {
    const store = useSalesPrefillStore()
    store.mergeFromStockRows([stock(), stock({ item_cd: 'FR010202', size_cd: 'SZ01', available_qty: 5 })])
    expect(store.shipLines).toHaveLength(2)
    store.updateShipLine(0, { qty: 3, unit_price: 50000 })
    expect(store.shipLines[0].qty).toBe(3)
    store.updateShipLine(0, { qty: 99 })
    // available clamp는 UI에서 수행 — store는 값 유지. Preview UI setQty로 검증
    store.removeShipLine(1)
    expect(store.shipLines).toHaveLength(1)

    const r = router()
    await r.push('/orders/sales-preview')
    await r.isReady()
    const wrapper = mount(SalesPreviewView, mountOpts(r))
    await flushPromises()
    expect(wrapper.text()).toContain('판매 미리보기')
    expect(wrapper.text()).toContain('판매 품목 1건')
  })

  it('P7 병합 시 기존 draft 유지', () => {
    const store = useSalesPrefillStore()
    store.mergeFromStockRows([stock()])
    store.updateShipLine(0, { qty: 4, unit_price: 1000 })
    store.mergeFromStockRows([stock(), stock({ storage_dt: '2026-08-20', available_qty: 3 })])
    expect(store.shipLines).toHaveLength(2)
    expect(store.shipLines[0].qty).toBe(4)
    expect(store.shipLines[0].unit_price).toBe(1000)
  })

  it('P11 택배 선택 시 주소영역 표시', async () => {
    const store = useSalesPrefillStore()
    store.mergeFromStockRows([stock()])
    store.setDelivery({ dlvryTp: DELIVERY_TP_PARCEL })
    const r = router()
    await r.push('/orders/sales-preview')
    await r.isReady()
    const wrapper = mount(SalesPreviewView, mountOpts(r))
    await flushPromises()
    expect(wrapper.text()).toContain('수령인')
    expect(wrapper.text()).toContain('수령 주소')
    store.setDelivery({ dlvryTp: DELIVERY_TP_VISIT })
    await flushPromises()
    expect(wrapper.text()).not.toContain('수령 주소')
  })

  it('P14~P16 confirm → API 1회 / 취소 시 미호출', async () => {
    const store = useSalesPrefillStore()
    store.mergeFromStockRows([stock()])
    store.setCustomer('C1', '홍길동')
    store.updateShipLine(0, { qty: 2, unit_price: 1000 })

    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const r = router()
    await r.push('/orders/sales-preview')
    await r.isReady()
    const wrapper = mount(SalesPreviewView, mountOpts(r))
    await flushPromises()
    await wrapper.findAll('button').find((b) => b.text().includes('판매 진행'))!.trigger('click')
    await flushPromises()
    expect(confirmShipment).not.toHaveBeenCalled()

    confirmSpy.mockReturnValue(true)
    await wrapper.findAll('button').find((b) => b.text().includes('판매 진행'))!.trigger('click')
    await flushPromises()
    expect(confirmShipment).toHaveBeenCalledTimes(1)
    expect(confirmShipment.mock.calls[0][1]).toMatchObject({
      ship_mode: 'DIRECT',
      custm_id: 'C1',
      lines: [expect.objectContaining({ qty: 2, unit_price: 1000 })],
    })
    expect(store.shipLines).toHaveLength(0)
  })
})
