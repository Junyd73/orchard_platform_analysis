import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import { cancelOrder, confirmOrder, fetchOrder } from '@/api/orders'
import OrderDetailView from '@/views/orders/OrderDetailView.vue'
import { useSalesPrefillStore } from '@/composables/stores/salesPrefill'
import {
  LABEL_CANCEL_ORDER,
  LABEL_CLOSE,
  LABEL_CONFIRM_ORDER,
  LABEL_EDIT,
  LABEL_ORDER_DETAIL,
  LABEL_SHIP,
  LABEL_SHIP_BATCH,
  LABEL_SHIP_SELECTED,
  MSG_MIXED_DLVRY_TP,
  MSG_ORDER_CANCEL_CONFIRM,
  MSG_ORDER_LOCKED_DELIVERED,
} from '@/views/orders/ordersConstants'

vi.mock('@/api/orders', () => ({
  fetchOrder: vi.fn(),
  cancelOrder: vi.fn(),
  confirmOrder: vi.fn(),
}))

function detail(statusCd: string, statusNm: string) {
  return {
    order_no: 'ORD20260817-001',
    order_dt: '2026-08-17',
    custm_id: 'C001',
    customer: '김고객',
    status_cd: statusCd,
    status_nm: statusNm,
    total_qty: 10,
    total_amt: 500000,
    pre_pay_amt: 0,
    mobile: '',
    stock_status: 'N',
    season_type_cd: '',
    tot_order_amt: 500000,
    tot_ship_fee: 0,
    tot_pay_amt: 0,
    rmk: '',
    sales_no: '',
    lines: [
      {
        order_detail_id: 'ORD20260817-001-01',
        item_cd: 'FR010100',
        variety_cd: 'FR010101',
        variety_nm: '신고배',
        grade_cd: 'GR010200',
        grade_nm: '특',
        size_cd: 'FR020101',
        size_nm: '25과 이내',
        weight: 7.5,
        qty: 10,
        unit_price: 50000,
        item_amt: 500000,
        harvest_year: 2026,
        wh_cd: 'WH01',
        dlvry_tp: 'LO010200',
        dlvry_tp_nm: '택배',
        deliveries: Array.from({ length: 10 }, (_, i) => ({
          order_dlvry_id: `ORD20260817-001-01-P${String(i + 1).padStart(2, '0')}`,
          order_detail_id: 'ORD20260817-001-01',
          delivery_tp_cd: 'LO010200',
          qty: 1,
          planned_dt: '2026-08-17',
          snd_name: '',
          snd_tel: '',
          snd_addr: '',
          rcv_name: `수령${i + 1}`,
          rcv_tel: '010-0000-0000',
          rcv_addr: '서울',
          dlvry_msg: '',
        })),
      },
    ],
  }
}

async function mountDetail(
  statusCd = 'ST010100',
  statusNm = '예약접수',
  body?: ReturnType<typeof detail>,
) {
  setActivePinia(createPinia())
  vi.mocked(fetchOrder).mockResolvedValue((body || detail(statusCd, statusNm)) as never)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/orders', name: 'orders', component: { template: '<div />' } },
      {
        path: '/orders/:orderNo/edit',
        name: 'order-edit',
        component: { template: '<div class="edit" />' },
      },
      {
        path: '/orders/:orderNo',
        name: 'order-detail',
        component: OrderDetailView,
      },
      { path: '/orders/ship', name: 'ship-confirm', component: { template: '<div class="ship" />' } },
    ],
  })
  await router.push('/orders/ORD20260817-001')
  await router.isReady()
  const wrapper = mount(OrderDetailView, {
    global: {
      plugins: [router],
      stubs: { OdsAppBar: true, OdsBottomNav: true },
    },
    attachTo: document.body,
  })
  await flushPromises()
  return { wrapper, router }
}

describe('OrderDetailView', () => {
  beforeEach(() => {
    vi.mocked(fetchOrder).mockReset()
    vi.mocked(cancelOrder).mockReset()
    vi.mocked(confirmOrder).mockReset()
  })

  it('T1 reserved hint points to confirm-before-ship', async () => {
    const { wrapper } = await mountDetail()
    expect(wrapper.text()).toContain('예약접수 상태입니다. 주문확정 후 출고할 수 있습니다.')
    expect(wrapper.text()).toContain(LABEL_CONFIRM_ORDER)
    wrapper.unmount()
  })

  it('hides ship actions for reserved orders', async () => {
    const { wrapper } = await mountDetail()
    const ship = wrapper.findAll('button').find((b) => b.text().includes(LABEL_SHIP))
    expect(ship).toBeFalsy()
    expect(wrapper.text()).not.toContain(LABEL_SHIP_BATCH)
    expect(wrapper.text()).not.toContain('출고 선택')
    wrapper.unmount()
  })

  it('shows ship action for confirmed orders', async () => {
    const { wrapper, router } = await mountDetail('ST010200', '주문확정')
    const ship = wrapper.findAll('button').find((b) => b.text().includes(LABEL_SHIP))
    expect(ship).toBeTruthy()
    await ship?.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('ship-confirm')
    wrapper.unmount()
  })

  it('confirms reserved order via dialog', async () => {
    vi.mocked(confirmOrder).mockResolvedValue(detail('ST010200', '주문확정') as never)
    const { wrapper } = await mountDetail()
    const btn = wrapper
      .findAll('.footer-actions button')
      .find((b) => b.text().includes(LABEL_CONFIRM_ORDER))
    expect(btn).toBeTruthy()
    await btn?.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('이 주문을 확정하시겠습니까?')
    const ok = wrapper
      .findAll('.dlg button')
      .find((b) => b.text().includes(LABEL_CONFIRM_ORDER))
    await ok?.trigger('click')
    await flushPromises()
    expect(confirmOrder).toHaveBeenCalled()
    expect(wrapper.text()).toContain('주문확정')
    wrapper.unmount()
  })

  it('shows code names and an edit action for reserved orders', async () => {
    const { wrapper } = await mountDetail()
    expect(wrapper.text()).toContain(LABEL_ORDER_DETAIL)
    expect(wrapper.text()).toContain('신고배 · 7.5kg · 특 · 25과 이내')
    expect(wrapper.text()).not.toContain('FR010101')
    expect(wrapper.text()).toContain('배송 택배 · 10/10 배정')
    const edit = wrapper.findAll('.footer-actions button').find((b) => b.text().includes(LABEL_EDIT))
    expect(edit).toBeTruthy()
    expect(edit?.attributes('disabled')).toBeUndefined()
    expect(wrapper.find('.footer-actions').text()).toContain(LABEL_CANCEL_ORDER)
    wrapper.unmount()
  })

  it('disables edit for delivered orders', async () => {
    const { wrapper } = await mountDetail('ST010400', '배송완료')
    expect(wrapper.text()).toContain(MSG_ORDER_LOCKED_DELIVERED)
    const edit = wrapper.findAll('.footer-actions button').find((b) => b.text().includes(LABEL_EDIT))
    expect(edit?.attributes('disabled')).toBeDefined()
    expect(wrapper.find('.footer-actions').text()).not.toContain(LABEL_CANCEL_ORDER)
    wrapper.unmount()
  })

  it('hides cancel for prep and already canceled orders', async () => {
    const prep = await mountDetail('ST010300', '배송준비')
    expect(prep.wrapper.find('.footer-actions').text()).toContain(LABEL_EDIT)
    expect(prep.wrapper.find('.footer-actions').text()).not.toContain(LABEL_CANCEL_ORDER)
    prep.wrapper.unmount()
    const canceled = await mountDetail('ST010500', '취소')
    expect(canceled.wrapper.text()).toContain('취소')
    const edit = canceled.wrapper
      .findAll('.footer-actions button')
      .find((b) => b.text().includes(LABEL_EDIT))
    expect(edit?.attributes('disabled')).toBeDefined()
    expect(canceled.wrapper.find('.footer-actions').text()).not.toContain(LABEL_CANCEL_ORDER)
    expect(canceled.wrapper.text()).toContain('신고배 · 7.5kg · 특 · 25과 이내')
    canceled.wrapper.unmount()
  })

  it('opens confirm dialog and cancels only after confirm', async () => {
    vi.mocked(cancelOrder).mockResolvedValue(detail('ST010500', '취소') as never)
    const { wrapper } = await mountDetail()
    await wrapper.find('.footer-actions .ods-btn--danger').trigger('click')
    await flushPromises()
    expect(wrapper.find('.dlg').exists()).toBe(true)
    expect(wrapper.text()).toContain(MSG_ORDER_CANCEL_CONFIRM)
    const closeBtn = wrapper.findAll('.dlg button').find((b) => b.text() === LABEL_CLOSE)
    await closeBtn?.trigger('click')
    await flushPromises()
    expect(cancelOrder).not.toHaveBeenCalled()
    expect(wrapper.find('.dlg').exists()).toBe(false)

    await wrapper.find('.footer-actions .ods-btn--danger').trigger('click')
    const confirmBtn = wrapper
      .findAll('.dlg button')
      .find((b) => b.text() === LABEL_CANCEL_ORDER)
    await confirmBtn?.trigger('click')
    await flushPromises()
    expect(cancelOrder).toHaveBeenCalledTimes(1)
    expect(wrapper.find('.dlg').exists()).toBe(false)
    expect(wrapper.text()).toContain('취소')
    expect(wrapper.find('.footer-actions').text()).not.toContain(LABEL_CANCEL_ORDER)
    const edit = wrapper.findAll('.footer-actions button').find((b) => b.text().includes(LABEL_EDIT))
    expect(edit?.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('신고배 · 7.5kg · 특 · 25과 이내')
    wrapper.unmount()
  })

  it('상품이 두 줄이면 일괄출고가 보인다', async () => {
    const two = detail('ST010200', '주문확정')
    const base = two.lines[0]
    two.lines = [base, { ...base, order_detail_id: 'ORD20260817-001-02' }]
    const { wrapper } = await mountDetail('ST010200', '주문확정', two)
    expect(wrapper.text()).toContain(LABEL_SHIP_BATCH)
    wrapper.unmount()
  })

  it('배송방식이 다른 상품은 일괄/선택 출고를 막는다', async () => {
    const body = detail('ST010200', '주문확정')
    const base = body.lines[0]
    body.lines = [
      base,
      { ...base, order_detail_id: 'ORD20260817-001-02', dlvry_tp: 'LO010100', dlvry_tp_nm: '방문수령' },
    ]
    const alert = vi.spyOn(window, 'alert').mockImplementation(() => {})
    const { wrapper, router } = await mountDetail('ST010200', '주문확정', body)
    await wrapper.findAll('button').find((b) => b.text().includes(LABEL_SHIP_BATCH))?.trigger('click')
    await flushPromises()
    expect(alert).toHaveBeenCalledWith(MSG_MIXED_DLVRY_TP)
    expect(router.currentRoute.value.name).toBe('order-detail')
    alert.mockRestore()
    wrapper.unmount()
  })

  it('배송방식이 같으면 선택 출고로 진행한다', async () => {
    const body = detail('ST010200', '주문확정')
    const base = body.lines[0]
    body.lines = [base, { ...base, order_detail_id: 'ORD20260817-001-02' }]
    const alert = vi.spyOn(window, 'alert').mockImplementation(() => {})
    const { wrapper, router } = await mountDetail('ST010200', '주문확정', body)
    for (const box of wrapper.findAll('input[type="checkbox"]')) {
      await box.setValue(true)
    }
    await wrapper
      .findAll('button')
      .find((b) => b.text().includes(LABEL_SHIP_SELECTED))
      ?.trigger('click')
    await flushPromises()
    expect(alert).not.toHaveBeenCalled()
    expect(router.currentRoute.value.name).toBe('ship-confirm')
    alert.mockRestore()
    wrapper.unmount()
  })

  it('A2/A6: remainingQty는 서버 remaining_order_qty SSOT', async () => {
    const body = detail('ST010100', '예약접수')
    body.lines[0].qty = 10
    body.lines[0].confirmed_shipped_qty = 6
    body.lines[0].remaining_order_qty = 4
    const { wrapper } = await mountDetail('ST010100', '예약접수', body)
    expect(wrapper.text()).toContain('잔여 4')
    expect(wrapper.text()).toContain('출고 6')
    wrapper.unmount()
  })

  it('A3: prefill.clear 후 재조회해도 서버 잔여 유지', async () => {
    const body = detail('ST010100', '예약접수')
    body.lines[0].confirmed_shipped_qty = 6
    body.lines[0].remaining_order_qty = 4
    const { wrapper } = await mountDetail('ST010100', '예약접수', body)
    useSalesPrefillStore().clear()
    await flushPromises()
    expect(wrapper.text()).toContain('잔여 4')
    wrapper.unmount()
  })

  it('A5: remaining 0 line은 출고 선택 대상 제외', async () => {
    const body = detail('ST010100', '예약접수')
    body.lines[0].confirmed_shipped_qty = 0
    body.lines[0].remaining_order_qty = 10
    const { wrapper } = await mountDetail('ST010100', '예약접수', body)
    expect(wrapper.text()).toContain('잔여 10')
    wrapper.unmount()
  })

  it('A5: remaining 0 line은 출고 버튼 없음', async () => {
    const body = detail('ST010100', '예약접수')
    body.lines[0].confirmed_shipped_qty = 10
    body.lines[0].remaining_order_qty = 0
    const { wrapper } = await mountDetail('ST010100', '예약접수', body)
    const shipBtn = wrapper.findAll('button').find((b) => b.text().trim() === LABEL_SHIP)
    expect(shipBtn).toBeUndefined()
    expect(wrapper.text()).not.toContain(LABEL_SHIP_BATCH)
    wrapper.unmount()
  })
})
