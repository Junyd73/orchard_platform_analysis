import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import ParcelDestinationSheet from '@/components/sales/ParcelDestinationSheet.vue'
import ShipConfirmView from '@/views/sales/ShipConfirmView.vue'
import {
  DELIVERY_TP_PARCEL,
  DELIVERY_TP_VISIT,
  MSG_UNTRACKED_DEST_RECHECK,
  ORDER_STATUS_FILTER_FALLBACK,
  ORDER_STATUS_PREP,
  hasMixedDeliveryTp,
  orderStatusLabelOf,
} from '@/views/orders/ordersConstants'
import {
  LABEL_CONFIRM_SHIP,
  orderStatusLabel,
  toApiDeliveryAllocation,
} from '@/views/sales/shipConfirmModel'
import { emptyDeliveryDraft } from '@/views/sales/shipDeliveryModel'
import { useSalesPrefillStore } from '@/composables/stores/salesPrefill'
import type { OrderDelivery, OrderDetail, OrderLine } from '@/types/order'

const confirmShipment = vi.fn()
const fetchCustomers = vi.fn()

vi.mock('@/api/shipments', () => ({
  confirmShipment: (...args: unknown[]) => confirmShipment(...args),
}))

vi.mock('@/api/orders', () => ({
  fetchCustomers: (...args: unknown[]) => fetchCustomers(...args),
}))

function delivery(id: string, qty: number, remaining: number): OrderDelivery {
  return {
    order_dlvry_id: id,
    order_detail_id: 'ORD1-01',
    delivery_tp_cd: DELIVERY_TP_PARCEL,
    qty,
    planned_dt: '2026-08-21',
    snd_name: '',
    snd_tel: '',
    snd_addr: '',
    rcv_name: `수령${id}`,
    rcv_tel: '010-0000-0000',
    rcv_addr: `주소 ${id}`,
    dlvry_msg: '메모',
    confirmed_shipped_qty: qty - remaining,
    remaining_qty: remaining,
  }
}

function line(patch: Partial<OrderLine> = {}): OrderLine {
  return {
    order_detail_id: 'ORD1-01',
    item_cd: 'FR010100',
    variety_cd: 'FR010101',
    grade_cd: 'GR010100',
    size_cd: 'FR020102',
    weight: 15,
    qty: 6,
    unit_price: 1000,
    item_amt: 6000,
    harvest_year: 2026,
    wh_cd: 'WH01',
    dlvry_tp: DELIVERY_TP_PARCEL,
    variety_nm: '신고',
    grade_nm: '특',
    size_nm: '25과',
    reserved_unshipped_qty: 0,
    confirmed_shipped_qty: 0,
    remaining_order_qty: 6,
    untracked_delivery_shipped_qty: 0,
    deliveries: [delivery('ORD1-01-001', 4, 4), delivery('ORD1-01-002', 2, 2)],
    ...patch,
  }
}

function order(lines: OrderLine[]): OrderDetail {
  return {
    order_no: 'ORD1',
    order_dt: '2026-08-21',
    custm_id: 'C001',
    customer: '김고객',
    status_cd: 'ST010200',
    status_nm: '주문확정',
    total_qty: 6,
    total_amt: 6000,
    pre_pay_amt: 0,
    mobile: '',
    stock_status: 'N',
    season_type_cd: '',
    tot_order_amt: 6000,
    tot_ship_fee: 0,
    tot_pay_amt: 0,
    rmk: '',
    sales_no: '',
    lines,
  }
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
    attachTo: document.body,
  })
  await flushPromises()
  return { wrapper, router }
}

function shipOkResponse() {
  return {
    ok: true,
    sales_no: '20260821-01',
    sales_status: 'CONFIRMED',
    ship_mode: 'DIRECT',
    order_no: 'ORD1',
    details: [],
    order_status: ORDER_STATUS_PREP,
    remaining_order_qty: 0,
    remaining_order: [],
  }
}

beforeEach(() => {
  setActivePinia(createPinia())
  confirmShipment.mockReset()
  fetchCustomers.mockResolvedValue([])
  document.body.innerHTML = ''
})

describe('Step3 주문 배송지 prefill', () => {
  it('택배 잔량 배송지를 전량 seed 한다', () => {
    const store = useSalesPrefillStore()
    const ln = line()
    store.setFromOrder(order([ln]), ln)
    const allocs = store.shipLines[0].delivery_allocations || []
    expect(allocs).toHaveLength(2)
    expect(allocs.map((a) => a.order_dlvry_id)).toEqual(['ORD1-01-001', 'ORD1-01-002'])
    expect(allocs.map((a) => a.qty)).toEqual([4, 2])
    expect(allocs[0].rcv_addr).toBe('주소 ORD1-01-001')
    expect(allocs.every((a) => a.ship_fee === 0)).toBe(true)
  })

  it('상품 잔량을 넘으면 마지막 배송지를 잘라 담는다', () => {
    const store = useSalesPrefillStore()
    const ln = line({
      remaining_order_qty: 5,
      deliveries: [delivery('D1', 4, 4), delivery('D2', 3, 3)],
    })
    store.setFromOrder(order([ln]), ln)
    const allocs = store.shipLines[0].delivery_allocations || []
    expect(allocs.map((a) => a.qty)).toEqual([4, 1])
    expect(allocs.reduce((s, a) => s + a.qty, 0)).toBe(5)
  })

  it('잔량 배송지가 없으면 빈 배송지로 시작한다', () => {
    const store = useSalesPrefillStore()
    const ln = line({ deliveries: [delivery('D1', 4, 0), delivery('D2', 2, 0)] })
    store.setFromOrder(order([ln]), ln)
    expect(store.shipLines[0].delivery_allocations).toEqual([])
  })

  it('추적 불가 출고이력이 있으면 자동 seed 하지 않는다', () => {
    const store = useSalesPrefillStore()
    const ln = line({ untracked_delivery_shipped_qty: 2, remaining_order_qty: 4 })
    store.setFromOrder(order([ln]), ln)
    expect(store.shipLines[0].delivery_allocations).toBeUndefined()
  })

  it('택배가 아니면 배송지를 seed 하지 않는다', () => {
    const store = useSalesPrefillStore()
    const ln = line({ dlvry_tp: DELIVERY_TP_VISIT })
    store.setFromOrder(order([ln]), ln)
    expect(store.shipLines[0].delivery_allocations).toBeUndefined()
  })

  it('주문 line 배송방식을 판매 배송방식으로 이어받는다', () => {
    const store = useSalesPrefillStore()
    const ln = line()
    store.setFromOrder(order([ln]), ln)
    expect(store.dlvryTp).toBe(DELIVERY_TP_PARCEL)
  })
})

describe('Step3 주문 택배 출고 화면', () => {
  it('수량을 줄여도 배송지를 자동으로 축소·삭제하지 않는다', async () => {
    const store = useSalesPrefillStore()
    const ln = line()
    store.setFromOrder(order([ln]), ln)
    const { wrapper } = await mountShip()
    await wrapper.find('input[type="number"]').setValue('5')
    await flushPromises()
    const status = wrapper.find('[data-testid="ship-confirm-delivery-status"]')
    expect(status.text()).toContain('6/5')
    expect(status.classes()).toContain('line__dest--danger')
    wrapper.unmount()
  })

  it('보내는 사람 미설정이면 확정을 막는다', async () => {
    const store = useSalesPrefillStore()
    const ln = line()
    store.setFromOrder(order([ln]), ln)
    const { wrapper } = await mountShip()
    await wrapper.findAll('button').find((b) => b.text().includes(LABEL_CONFIRM_SHIP))?.trigger('click')
    await flushPromises()
    expect(confirmShipment).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('보내는 사람')
    wrapper.unmount()
  })

  it('order_dlvry_id와 보내는 사람을 confirm payload에 담는다', async () => {
    const store = useSalesPrefillStore()
    const ln = line()
    store.setFromOrder(order([ln]), ln)
    store.setSender({ name: '삼육농원', tel: '010-1234-5678', addr: '화성시 1' })
    confirmShipment.mockResolvedValue(shipOkResponse())
    const { wrapper } = await mountShip()
    await wrapper.findAll('button').find((b) => b.text().includes(LABEL_CONFIRM_SHIP))?.trigger('click')
    await flushPromises()
    const payload = confirmShipment.mock.calls[0][1]
    expect(payload.dlvry_tp).toBe(DELIVERY_TP_PARCEL)
    expect(payload.snd_name).toBe('삼육농원')
    expect(payload.lines[0].delivery_allocations.map((a: { order_dlvry_id: string }) => a.order_dlvry_id))
      .toEqual(['ORD1-01-001', 'ORD1-01-002'])
    wrapper.unmount()
  })

  it('추적 불가 출고이력이 있으면 배송지 재확인을 안내한다', async () => {
    const store = useSalesPrefillStore()
    const ln = line({ untracked_delivery_shipped_qty: 2, remaining_order_qty: 4 })
    store.setFromOrder(order([ln]), ln)
    const { wrapper } = await mountShip()
    expect(wrapper.find('[data-testid="ship-confirm-untracked-hint"]').text())
      .toBe(MSG_UNTRACKED_DEST_RECHECK)
    wrapper.unmount()
  })

  it('방문수령이면 배송지 편집 UI가 없다', async () => {
    const store = useSalesPrefillStore()
    const ln = line({ dlvry_tp: DELIVERY_TP_VISIT })
    store.setFromOrder(order([ln]), ln)
    const { wrapper } = await mountShip()
    expect(wrapper.find('[data-testid="ship-confirm-dest-open"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="ship-confirm-sender-bar"]').exists()).toBe(false)
    wrapper.unmount()
  })
})

describe('Step3 공통 규칙', () => {
  it('신규 배송지의 order_dlvry_id는 null로 전송한다', () => {
    expect(toApiDeliveryAllocation(emptyDeliveryDraft({ qty: 2 })).order_dlvry_id).toBeNull()
    expect(
      toApiDeliveryAllocation(emptyDeliveryDraft({ qty: 2, order_dlvry_id: 'D9' })).order_dlvry_id,
    ).toBe('D9')
  })

  it('배송방식이 섞이면 혼합으로 판정한다', () => {
    expect(hasMixedDeliveryTp([{ dlvry_tp: DELIVERY_TP_PARCEL }])).toBe(false)
    expect(
      hasMixedDeliveryTp([{ dlvry_tp: DELIVERY_TP_PARCEL }, { dlvry_tp: DELIVERY_TP_PARCEL }]),
    ).toBe(false)
    expect(
      hasMixedDeliveryTp([{ dlvry_tp: DELIVERY_TP_PARCEL }, { dlvry_tp: DELIVERY_TP_VISIT }]),
    ).toBe(true)
  })

  it('ST010300은 부분출고로 표시한다', () => {
    expect(orderStatusLabelOf(ORDER_STATUS_PREP)).toBe('부분출고')
    expect(orderStatusLabel(ORDER_STATUS_PREP)).toBe('부분출고')
    expect(
      ORDER_STATUS_FILTER_FALLBACK.find((r) => r.value === ORDER_STATUS_PREP)?.label,
    ).toBe('부분출고')
  })

  it('실배송 시트는 배송비를 입력받고 order_dlvry_id를 유지한다', async () => {
    const wrapper = mount(ParcelDestinationSheet, {
      props: {
        open: true,
        productSummary: '신고 · 15kg',
        orderQty: 3,
        unitLabel: '박스',
        initialDests: [
          emptyDeliveryDraft({
            order_dlvry_id: 'ORD1-01-001',
            qty: 3,
            rcv_name: '홍길동',
            rcv_tel: '010-1111-2222',
            rcv_addr: '서울',
          }),
        ],
        customerDefaults: { rcv_name: '김고객', rcv_tel: '010-0000-0000' },
        ordererName: '김고객',
        showShipFee: true,
        testIdPrefix: 'ship-confirm',
      },
      attachTo: document.body,
    })
    await flushPromises()
    const sheet = document.querySelector('[data-testid="ship-confirm-dest-sheet"]')!
    ;(sheet.querySelector('[data-testid="ship-confirm-dest-edit"]') as HTMLButtonElement).click()
    await flushPromises()
    const fee = document.querySelector('[data-testid="ship-confirm-dest-fee"]') as HTMLInputElement
    expect(fee).toBeTruthy()
    fee.value = '3000'
    fee.dispatchEvent(new Event('input'))
    await flushPromises()
    ;(document.querySelector('[data-testid="ship-confirm-dest-done"]') as HTMLButtonElement).click()
    await flushPromises()
    const cleaned = wrapper.emitted('complete')?.at(-1)?.[0] as { ship_fee: number; order_dlvry_id: string }[]
    expect(cleaned[0].ship_fee).toBe(3000)
    expect(cleaned[0].order_dlvry_id).toBe('ORD1-01-001')
    wrapper.unmount()
  })
})
