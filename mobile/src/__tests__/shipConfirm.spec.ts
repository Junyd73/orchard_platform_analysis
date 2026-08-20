import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import ShipConfirmView from '@/views/sales/ShipConfirmView.vue'
import {
  LABEL_CONFIRM_SHIP,
  LABEL_MODE_DIRECT,
  LABEL_MODE_STOCK,
  MSG_QTY_OVER_REMAINING,
  SHIP_MODE_DIRECT,
  SHIP_MODE_STOCK,
  buildShipConfirmRequest,
  defaultShipMode,
} from '@/views/sales/shipConfirmModel'
import { useSalesPrefillStore } from '@/composables/stores/salesPrefill'
import type { OrderDetail, OrderLine } from '@/types/order'
import type { StockItem } from '@/api/stock'

const confirmShipment = vi.fn()
const fetchCustomers = vi.fn()

vi.mock('@/api/shipments', () => ({
  confirmShipment: (...args: unknown[]) => confirmShipment(...args),
}))

vi.mock('@/api/orders', () => ({
  fetchCustomers: (...args: unknown[]) => fetchCustomers(...args),
}))

const LINE: OrderLine = {
  order_detail_id: 'ORD1-01',
  item_cd: 'FR010100',
  variety_cd: 'FR010101',
  grade_cd: 'GR010100',
  size_cd: 'FR020102',
  weight: 15,
  qty: 10,
  unit_price: 1000,
  item_amt: 10000,
  harvest_year: 2026,
  wh_cd: 'WH01',
  dlvry_tp: 'LO010100',
  variety_nm: '신고',
  grade_nm: '특',
  size_nm: '25과',
  reserved_unshipped_qty: 6,
  deliveries: [],
}

const ORDER: OrderDetail = {
  order_no: 'ORD1',
  order_dt: '2026-08-19',
  custm_id: 'C001',
  customer: '김고객',
  status_cd: 'ST010100',
  status_nm: '예약접수',
  total_qty: 10,
  total_amt: 10000,
  pre_pay_amt: 0,
  mobile: '',
  stock_status: 'N',
  season_type_cd: '',
  tot_order_amt: 10000,
  tot_ship_fee: 0,
  tot_pay_amt: 0,
  rmk: '',
  sales_no: '',
  lines: [LINE],
}

const STOCK: StockItem = {
  farm_cd: 'OR001',
  wh_cd: 'WH01',
  item_cd: 'FR010100',
  item_nm: '배',
  variety_cd: 'FR010101',
  variety_nm: '신고',
  grade_cd: 'GR010100',
  grade_nm: '특',
  size_cd: 'FR020102',
  size_nm: '25과',
  weight: 15,
  harvest_year: 2026,
  storage_dt: '2026-01-01',
  in_qty: 10,
  out_qty: 0,
  real_qty: 10,
  reserved_qty: 0,
  available_qty: 8,
}

async function mountShip() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/orders', name: 'orders', component: { template: '<div />' } },
      { path: '/orders/ship', name: 'ship-confirm', component: ShipConfirmView },
      {
        path: '/orders/:orderNo',
        name: 'order-detail',
        component: { template: '<div class="od" />' },
      },
    ],
  })
  await router.push('/orders/ship')
  await router.isReady()
  const wrapper = mount(ShipConfirmView, {
    global: { plugins: [router], stubs: { OdsAppBar: true, OdsBottomNav: true } },
  })
  await flushPromises()
  return { wrapper, router }
}

describe('shipConfirmModel / ShipConfirmView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    confirmShipment.mockReset()
    fetchCustomers.mockResolvedValue([])
  })

  it('T-MOB-SHIP-01: 생산 N line prefill → 판매화면 N line', async () => {
    const store = useSalesPrefillStore()
    store.setFromProduction([
      {
        item_cd: 'FR010100',
        variety_cd: 'FR010101',
        grade_cd: 'GR010100',
        size_cd: 'FR020102',
        weight: 15,
        qty: 4,
        harvest_year: 2026,
        wh_cd: 'WH01',
      },
      {
        item_cd: 'FR010100',
        variety_cd: 'FR010101',
        grade_cd: 'GR010100',
        size_cd: 'FR020102',
        weight: 7.5,
        qty: 2,
        harvest_year: 2026,
        wh_cd: 'WH01',
      },
    ])
    const { wrapper } = await mountShip()
    expect(wrapper.text()).toContain('출고 1')
    expect(wrapper.text()).toContain('출고 2')
  })

  it('T-MOB-SHIP-02/03: 생산 qty 변경 가능, 기본 DIRECT', async () => {
    const store = useSalesPrefillStore()
    store.setFromProduction([
      {
        item_cd: 'FR010100',
        variety_cd: 'FR010101',
        grade_cd: 'GR010100',
        size_cd: 'FR020102',
        weight: 15,
        qty: 10,
        harvest_year: 2026,
        wh_cd: 'WH01',
      },
    ])
    expect(store.shipMode).toBe(SHIP_MODE_DIRECT)
    const { wrapper } = await mountShip()
    const qty = wrapper.find('input[type="number"]')
    await qty.setValue('8')
    expect(store.shipLines[0].qty).toBe(10)
    confirmShipment.mockResolvedValue({
      ok: true,
      sales_no: '20260819-01',
      sales_status: 'CONFIRMED',
      ship_mode: 'DIRECT',
      order_no: null,
      details: [{ sale_detail_no: '20260819-01-S01', order_detail_id: null, stock_seq: 1, qty: 8 }],
      order_status: null,
      remaining_order_qty: null,
      remaining_order: [],
    })
    await wrapper.findAll('button').find((b) => b.text().includes(LABEL_CONFIRM_SHIP))?.trigger('click')
    await flushPromises()
    const payload = confirmShipment.mock.calls[0][1]
    expect(payload.ship_mode).toBe(SHIP_MODE_DIRECT)
    expect(payload.lines[0].qty).toBe(8)
    expect(payload).not.toHaveProperty('stock_seq')
    expect(JSON.stringify(payload)).not.toContain('stock_seq')
  })

  it('확정 중 중복 클릭은 1회만 호출', async () => {
    const store = useSalesPrefillStore()
    store.setFromProduction([
      {
        item_cd: 'FR010100',
        variety_cd: 'FR010101',
        grade_cd: 'GR010100',
        size_cd: 'FR020102',
        weight: 15,
        qty: 1,
        harvest_year: 2026,
        wh_cd: 'WH01',
      },
    ])
    let release!: () => void
    confirmShipment.mockImplementation(
      () => new Promise((resolve) => {
        release = () => resolve({
          ok: true,
          sales_no: '20260819-dup',
          sales_status: 'CONFIRMED',
          ship_mode: 'DIRECT',
          order_no: null,
          details: [],
          order_status: null,
          remaining_order_qty: null,
          remaining_order: [],
        })
      }),
    )
    const { wrapper } = await mountShip()
    const btn = wrapper.findAll('button').find((b) => b.text().includes(LABEL_CONFIRM_SHIP))
    await btn?.trigger('click')
    await btn?.trigger('click')
    expect(confirmShipment).toHaveBeenCalledTimes(1)
    release()
    await flushPromises()
  })

  it('T-MOB-SHIP-04: alloc 잔여 있으면 배정재고 기본', () => {
    expect(defaultShipMode(6, true)).toBe(SHIP_MODE_STOCK)
    const store = useSalesPrefillStore()
    store.setFromOrder(ORDER, LINE)
    expect(store.shipMode).toBe(SHIP_MODE_STOCK)
  })

  it('T-MOB-SHIP-05: alloc 0이면 일반재고 기본', () => {
    expect(defaultShipMode(0, true)).toBe(SHIP_MODE_DIRECT)
    const store = useSalesPrefillStore()
    store.setFromOrder(ORDER, { ...LINE, reserved_unshipped_qty: 0 })
    expect(store.shipMode).toBe(SHIP_MODE_DIRECT)
  })

  it('T-MOB-SHIP-06: STOCK/DIRECT 영문 미노출', async () => {
    const store = useSalesPrefillStore()
    store.setFromOrder(ORDER, LINE)
    const { wrapper } = await mountShip()
    expect(wrapper.text()).toContain(LABEL_MODE_STOCK)
    expect(wrapper.text()).toContain(LABEL_MODE_DIRECT)
    expect(wrapper.text()).not.toMatch(/\bSTOCK\b/)
    expect(wrapper.text()).not.toMatch(/\bDIRECT\b/)
  })

  it('T-MOB-SHIP-07: remaining 초과 1차 validation', async () => {
    const store = useSalesPrefillStore()
    store.setFromOrder(ORDER, LINE)
    const { wrapper } = await mountShip()
    const qty = wrapper.find('input[type="number"]')
    await qty.setValue('99')
    await wrapper.findAll('button').find((b) => b.text().includes(LABEL_CONFIRM_SHIP))?.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain(MSG_QTY_OVER_REMAINING)
    expect(confirmShipment).not.toHaveBeenCalled()
  })

  it('T-MOB-SHIP-08/12: remaining_order[] 표시 후 주문상세 복귀', async () => {
    const store = useSalesPrefillStore()
    store.setFromOrder(ORDER, LINE)
    confirmShipment.mockResolvedValue({
      ok: true,
      sales_no: '20260819-01',
      sales_status: 'CONFIRMED',
      ship_mode: 'STOCK',
      order_no: 'ORD1',
      details: [{ sale_detail_no: '20260819-01-S01', order_detail_id: 'ORD1-01', stock_seq: 3, qty: 6 }],
      order_status: 'ST010300',
      remaining_order_qty: 4,
      remaining_order: [
        {
          order_detail_id: 'ORD1-01',
          order_qty: 10,
          confirmed_shipped_qty: 6,
          remaining_order_qty: 4,
        },
      ],
    })
    const { wrapper, router } = await mountShip()
    await wrapper.findAll('button').find((b) => b.text().includes(LABEL_CONFIRM_SHIP))?.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('잔여 4')
    expect(wrapper.text()).toContain('배송준비')
    expect(wrapper.text()).not.toContain(LABEL_CONFIRM_SHIP)
    await wrapper.findAll('button').find((b) => b.text() === '확인')?.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('order-detail')
  })

  it('T-MOB-SHIP-09/10/11: 재고 규격 prefill, stock_seq 미전송, DIRECT만', () => {
    const store = useSalesPrefillStore()
    store.setFromStock(STOCK)
    expect(store.shipMode).toBe(SHIP_MODE_DIRECT)
    expect(store.allowModeChange).toBe(false)
    expect(store.shipLines[0].variety_cd).toBe('FR010101')
    expect(store.shipLines[0].weight).toBe(15)
    const req = buildShipConfirmRequest({
      shipMode: store.shipMode,
      salesDt: '2026-08-19',
      orderNo: store.orderNo,
      custmId: store.custmId,
      lines: store.shipLines,
    })
    expect(JSON.stringify(req)).not.toContain('stock_seq')
    expect(JSON.stringify(STOCK)).not.toContain('stock_seq')
    expect(req.ship_mode).toBe(SHIP_MODE_DIRECT)
    expect(req.order_no).toBeNull()
  })

  it('재고 여러 줄 prefill', () => {
    const store = useSalesPrefillStore()
    store.setFromStockRows([
      STOCK,
      { ...STOCK, item_cd: 'FR010202', item_nm: '순배즙', weight: 30 },
    ])
    expect(store.shipLines).toHaveLength(2)
    expect(store.shipLines[1].item_cd).toBe('FR010202')
  })

  it('배즙 출고 스펙은 제품명만 보여 준다', async () => {
    const store = useSalesPrefillStore()
    store.setFromStock({
      ...STOCK,
      item_cd: 'FR010202',
      item_nm: '순배즙',
      variety_nm: '신고배',
      weight: 30,
      grade_nm: '30포',
      size_nm: '5kg',
    })
    const { wrapper } = await mountShip()
    expect(wrapper.text()).toContain('일반배즙')
    expect(wrapper.text()).not.toContain('30kg')
    expect(wrapper.text()).not.toContain('30포')
    expect(wrapper.text()).not.toContain('5kg')
  })

  it('T-MOB-SHIP-13: 재고 판매 성공 후 재고 탭 복귀', async () => {
    const store = useSalesPrefillStore()
    store.setFromStock(STOCK)
    confirmShipment.mockResolvedValue({
      ok: true,
      sales_no: '20260819-02',
      sales_status: 'CONFIRMED',
      ship_mode: 'DIRECT',
      order_no: null,
      details: [{ sale_detail_no: 'x', order_detail_id: null, stock_seq: 9, qty: 1 }],
      order_status: null,
      remaining_order_qty: null,
      remaining_order: [],
    })
    const { wrapper, router } = await mountShip()
    store.shipLines[0].qty = 1
    await wrapper.findAll('button').find((b) => b.text().includes(LABEL_CONFIRM_SHIP))?.trigger('click')
    await flushPromises()
    await wrapper.findAll('button').find((b) => b.text() === '확인')?.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('orders')
    expect(router.currentRoute.value.query.tab).toBe('stock')
  })

  it('T-MOB-SHIP-14: 생산 바로판매 성공 후 판매 탭 복귀', async () => {
    const store = useSalesPrefillStore()
    store.setFromProduction([
      {
        item_cd: 'FR010100',
        variety_cd: 'FR010101',
        grade_cd: 'GR010100',
        size_cd: 'FR020102',
        weight: 15,
        qty: 1,
        harvest_year: 2026,
        wh_cd: 'WH01',
      },
    ])
    confirmShipment.mockResolvedValue({
      ok: true,
      sales_no: '20260819-03',
      sales_status: 'CONFIRMED',
      ship_mode: 'DIRECT',
      order_no: null,
      details: [{ sale_detail_no: 'y', order_detail_id: null, stock_seq: 2, qty: 1 }],
      order_status: null,
      remaining_order_qty: null,
      remaining_order: [],
    })
    const { wrapper, router } = await mountShip()
    await wrapper.findAll('button').find((b) => b.text().includes(LABEL_CONFIRM_SHIP))?.trigger('click')
    await flushPromises()
    await wrapper.findAll('button').find((b) => b.text() === '확인')?.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query.tab).toBe('sales')
  })

  it('T-MOB-PREFILL-NAME-01/03: 생산 prefill name 표시, N line', async () => {
    const store = useSalesPrefillStore()
    store.setFromProduction([
      {
        item_cd: 'FR010100',
        variety_cd: 'FR010102',
        grade_cd: 'GR010200',
        size_cd: 'FR020101',
        weight: 15,
        qty: 3,
        variety_nm: '신고배',
        grade_nm: '특',
        size_nm: '1다이',
      },
      {
        item_cd: 'FR010100',
        variety_cd: 'FR010102',
        grade_cd: 'GR010300',
        size_cd: 'FR020102',
        weight: 15,
        qty: 2,
        variety_nm: '신고배',
        grade_nm: '상',
        size_nm: '2다이',
      },
    ])
    const { wrapper } = await mountShip()
    expect(wrapper.text()).toContain('신고배 · 15kg · 특 · 1다이')
    expect(wrapper.text()).toContain('신고배 · 15kg · 상 · 2다이')
    expect(wrapper.text()).not.toContain('FR010102')
    expect(wrapper.text()).not.toContain('GR010200')
  })

  it('T-MOB-PREFILL-NAME-02: confirm payload는 code 유지', async () => {
    const store = useSalesPrefillStore()
    store.setFromProduction([
      {
        item_cd: 'FR010100',
        variety_cd: 'FR010102',
        grade_cd: 'GR010200',
        size_cd: 'FR020101',
        weight: 15,
        qty: 1,
        variety_nm: '신고배',
        grade_nm: '특',
        size_nm: '1다이',
        harvest_year: 2026,
        wh_cd: 'WH01',
      },
    ])
    confirmShipment.mockResolvedValue({
      ok: true,
      sales_no: '20260819-n',
      sales_status: 'CONFIRMED',
      ship_mode: 'DIRECT',
      order_no: null,
      details: [],
      order_status: null,
      remaining_order_qty: null,
      remaining_order: [],
    })
    const { wrapper } = await mountShip()
    await wrapper.findAll('button').find((b) => b.text().includes(LABEL_CONFIRM_SHIP))?.trigger('click')
    await flushPromises()
    const line = confirmShipment.mock.calls[0][1].lines[0]
    expect(line.variety_cd).toBe('FR010102')
    expect(line.grade_cd).toBe('GR010200')
    expect(line.size_cd).toBe('FR020101')
    expect(line).not.toHaveProperty('variety_nm')
    expect(JSON.stringify(confirmShipment.mock.calls[0][1])).not.toContain('신고배')
  })

  it('T-MOB-PREFILL-NAME-04: 주문/재고 진입 명칭 회귀', async () => {
    const store = useSalesPrefillStore()
    store.setFromOrder(ORDER, LINE)
    const orderMount = await mountShip()
    expect(orderMount.wrapper.text()).toContain('신고 · 15kg · 특 · 25과')
    expect(orderMount.wrapper.text()).not.toContain('FR010101')
    orderMount.wrapper.unmount()

    setActivePinia(createPinia())
    const store2 = useSalesPrefillStore()
    store2.setFromStock(STOCK)
    const stockMount = await mountShip()
    expect(stockMount.wrapper.text()).toContain('신고 · 15kg · 특 · 25과')
    expect(stockMount.wrapper.text()).not.toContain('FR010101')
  })

  it('주문 출고 안내에 주문확정 정책 문구가 없다', async () => {
    const store = useSalesPrefillStore()
    store.setFromOrder(ORDER, LINE)
    const { wrapper } = await mountShip()
    expect(wrapper.text()).toContain('주문 출고')
    expect(wrapper.text()).not.toContain('주문확정 버튼')
    expect(wrapper.text()).not.toContain('주문확정 단계는')
    wrapper.unmount()
  })
})
