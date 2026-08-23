import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import SalesDetailView from '@/features/sales/SalesDetailView.vue'
import OdsAppBar from '@/components/ods/OdsAppBar.vue'
import { TAB_SALES } from '@/features/orders/ordersConstants'
import {
  LABEL_PAYMENT_REGISTER,
  MSG_PAYMENT_RESULT_CHECK,
  SALES_STATUS_CONFIRMED,
  SALES_STATUS_DRAFT,
} from '@/features/sales/salesConstants'
import { todayBizIso } from '@/shared/bizDate'
import type { SalesDetail, SalesPaymentHistory } from '@/types/sales'

const fetchSaleDetail = vi.fn()
const fetchSalePayments = vi.fn()
const createSalePayment = vi.fn()
const fetchWorkLogAccountCodes = vi.fn()

vi.mock('@/api/sales', () => ({
  fetchSaleDetail: (...args: unknown[]) => fetchSaleDetail(...args),
  fetchSalePayments: (...args: unknown[]) => fetchSalePayments(...args),
  createSalePayment: (...args: unknown[]) => createSalePayment(...args),
}))

vi.mock('@/api/workLogs', () => ({
  fetchWorkLogAccountCodes: (...args: unknown[]) => fetchWorkLogAccountCodes(...args),
}))

const PAY_METHODS = [
  { acct_cd: 'AS010101', acct_nm: '현금 (시재)', acct_level: 4 },
  { acct_cd: 'AS010102', acct_nm: '농협은행', acct_level: 4 },
]

const DETAIL: SalesDetail = {
  sales_no: '20260822-01',
  sales_dt: '2026-08-22',
  custm_id: 'C001',
  customer: '홍길동',
  order_no: 'ORD20260822-001',
  sales_status: SALES_STATUS_CONFIRMED,
  sales_source: 'ORDER',
  tot_sales_amt: 950000,
  paid_amt: 800000,
  unpaid_amt: 150000,
  payment_status: 'PARTIAL',
  lines: [
    {
      sale_detail_no: '20260822-01-S01',
      order_detail_id: 'ORD20260822-001-01',
      item_cd: 'FR010100',
      variety_cd: 'FR010101',
      variety_nm: '신고',
      grade_cd: 'GR010100',
      grade_nm: '특',
      size_cd: 'SZ010200',
      size_nm: '7.5kg',
      crop_nm: '16 ~ 20과',
      qty: 10,
      unit_price: 95000,
      item_amt: 950000,
    },
  ],
}

const PAYMENTS: SalesPaymentHistory = {
  sales_no: '20260822-01',
  sales_status: SALES_STATUS_CONFIRMED,
  tot_sales_amt: 950000,
  paid_amt: 800000,
  unpaid_amt: 150000,
  payment_status: 'PARTIAL',
  payments: [
    {
      paid_detail_no: '20260822-01-P01',
      pay_dt: '2026-08-21',
      pay_method_cd: 'AS010102',
      pay_method_nm: '농협은행',
      pay_amt: 100000,
      payment_source: 'GENERAL',
      source_order_no: null,
    },
    {
      paid_detail_no: '20260822-01-P02',
      pay_dt: '2026-08-21',
      pay_method_cd: 'AS010101',
      pay_method_nm: '현금 (시재)',
      pay_amt: 50000,
      payment_source: 'ORDER_PREPAY',
      source_order_no: 'ORD20260822-001',
    },
    {
      paid_detail_no: '20260822-01-P03',
      pay_dt: '2026-08-22',
      pay_method_cd: 'AS010102',
      pay_method_nm: '농협은행',
      pay_amt: 650000,
      payment_source: 'GENERAL',
      source_order_no: null,
    },
  ],
}

async function mountDetail() {
  setActivePinia(createPinia())
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/orders', name: 'orders', component: { template: '<div />' } },
      {
        path: '/orders/sales/:salesNo',
        name: 'sales-detail',
        component: SalesDetailView,
      },
    ],
  })
  await router.push('/orders/sales/20260822-01')
  await router.isReady()
  const wrapper = mount(SalesDetailView, {
    global: {
      plugins: [router],
      stubs: { OdsAppBar: true, OdsBottomNav: true, OdsSkeleton: true },
    },
  })
  await flushPromises()
  return { wrapper, router }
}

async function openForm(wrapper: ReturnType<typeof mount>) {
  const btn = wrapper.find('[data-testid="payment-register-btn"]')
  expect(btn.exists()).toBe(true)
  await btn.trigger('click')
  await flushPromises()
}

describe('SalesDetailView', () => {
  beforeEach(() => {
    fetchSaleDetail.mockReset()
    fetchSalePayments.mockReset()
    createSalePayment.mockReset()
    fetchWorkLogAccountCodes.mockReset()
    fetchSaleDetail.mockResolvedValue(DETAIL)
    fetchSalePayments.mockResolvedValue(PAYMENTS)
    fetchWorkLogAccountCodes.mockResolvedValue(PAY_METHODS)
  })

  it('상세 hero·요약·상품 표시', async () => {
    const { wrapper } = await mountDetail()
    expect(fetchSaleDetail).toHaveBeenCalled()
    expect(wrapper.text()).toContain('판매상세')
    expect(wrapper.text()).toContain('홍길동')
    expect(wrapper.text()).toContain('950,000')
    expect(wrapper.text()).toContain('신고')
  })

  it('CONFIRMED+미수 → 수금등록 버튼', async () => {
    const { wrapper } = await mountDetail()
    expect(wrapper.text()).toContain(LABEL_PAYMENT_REGISTER)
  })

  it('수금내역 N건·출처·결제수단명 표시', async () => {
    const { wrapper } = await mountDetail()
    expect(fetchSalePayments).toHaveBeenCalled()
    expect(wrapper.text()).toContain('수금내역')
    expect(wrapper.text()).toContain('농협은행')
    expect(wrapper.text()).toContain('일반수금')
    expect(wrapper.text()).not.toContain('AS010102')
  })

  it('DRAFT → 수금등록 버튼 없음', async () => {
    fetchSaleDetail.mockResolvedValue({
      ...DETAIL,
      sales_status: SALES_STATUS_DRAFT,
      payment_status: null,
      unpaid_amt: 100000,
    })
    fetchSalePayments.mockResolvedValue({
      ...PAYMENTS,
      sales_status: SALES_STATUS_DRAFT,
      payment_status: null,
      payments: [],
    })
    const { wrapper } = await mountDetail()
    expect(wrapper.find('[data-testid="payment-register-btn"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('수금대기')
  })

  it('수금완료 → 수금등록 버튼 없음', async () => {
    fetchSaleDetail.mockResolvedValue({
      ...DETAIL,
      paid_amt: 950000,
      unpaid_amt: 0,
      payment_status: 'PAID',
    })
    const { wrapper } = await mountDetail()
    expect(wrapper.find('[data-testid="payment-register-btn"]').exists()).toBe(false)
  })

  it('inline form open/close·기본값', async () => {
    const { wrapper } = await mountDetail()
    await openForm(wrapper)
    expect(wrapper.find('[data-testid="payment-form"]').exists()).toBe(true)
    const dateInput = wrapper.find('input[type="date"]')
    expect(dateInput.attributes('min')).toBe('2026-08-22')
    expect(dateInput.attributes('max')).toBe(todayBizIso())
    expect((wrapper.find('input[type="number"]').element as HTMLInputElement).value).toBe('150000')
    await wrapper.find('[data-testid="payment-form"] button').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="payment-form"]').exists()).toBe(false)
  })

  it('결제수단 API 사용·POST payload', async () => {
    const { wrapper } = await mountDetail()
    await openForm(wrapper)
    expect(fetchWorkLogAccountCodes).toHaveBeenCalled()
    const sel = wrapper.find('[data-testid="payment-method-select"]')
    await sel.setValue('AS010101')
    createSalePayment.mockResolvedValue({
      ...PAYMENTS,
      paid_amt: 900000,
      unpaid_amt: 50000,
      payment_status: 'PARTIAL',
    })
    await wrapper.find('[data-testid="payment-submit-btn"]').trigger('click')
    await flushPromises()
    expect(createSalePayment).toHaveBeenCalledTimes(1)
    const [, , payload] = createSalePayment.mock.calls[0]
    expect(payload).toEqual({
      pay_dt: todayBizIso(),
      pay_amt: 150000,
      pay_method_cd: 'AS010101',
    })
    expect(payload).not.toHaveProperty('source_order_no')
  })

  it('submitting 중 버튼 disabled·double click 1회', async () => {
    let resolvePost: (v: SalesPaymentHistory) => void
    createSalePayment.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolvePost = resolve
        }),
    )
    const { wrapper } = await mountDetail()
    await openForm(wrapper)
    await wrapper.find('[data-testid="payment-method-select"]').setValue('AS010101')
    const submit = wrapper.find('[data-testid="payment-submit-btn"]')
    await submit.trigger('click')
    await submit.trigger('click')
    expect(createSalePayment).toHaveBeenCalledTimes(1)
    resolvePost!({
      ...PAYMENTS,
      paid_amt: 950000,
      unpaid_amt: 0,
      payment_status: 'PAID',
    })
    fetchSaleDetail.mockResolvedValue({
      ...DETAIL,
      paid_amt: 950000,
      unpaid_amt: 0,
      payment_status: 'PAID',
    })
    fetchSalePayments.mockResolvedValue({
      ...PAYMENTS,
      paid_amt: 950000,
      unpaid_amt: 0,
      payment_status: 'PAID',
      payments: [...PAYMENTS.payments],
    })
    await flushPromises()
    expect(wrapper.text()).toContain('수금완료')
  })

  it('400 form error', async () => {
    const { ApiClientError } = await import('@/api/client')
    createSalePayment.mockRejectedValue(new ApiClientError('수금액이 미수금을 초과할 수 없습니다.', { status: 400 }))
    const { wrapper } = await mountDetail()
    await openForm(wrapper)
    await wrapper.find('[data-testid="payment-method-select"]').setValue('AS010101')
    await wrapper.find('[data-testid="payment-submit-btn"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('수금액이 미수금을 초과할 수 없습니다.')
    expect(wrapper.text()).toContain('판매상세')
  })

  it('network ambiguity → GET refresh·자동 POST retry 없음', async () => {
    createSalePayment.mockRejectedValue(new Error('network'))
    const { wrapper } = await mountDetail()
    const detailCalls = fetchSaleDetail.mock.calls.length
    const paymentCalls = fetchSalePayments.mock.calls.length
    await openForm(wrapper)
    await wrapper.find('[data-testid="payment-method-select"]').setValue('AS010101')
    await wrapper.find('[data-testid="payment-submit-btn"]').trigger('click')
    await flushPromises()
    expect(createSalePayment).toHaveBeenCalledTimes(1)
    expect(fetchSaleDetail.mock.calls.length).toBeGreaterThan(detailCalls)
    expect(fetchSalePayments.mock.calls.length).toBeGreaterThan(paymentCalls)
    expect(wrapper.text()).toContain(MSG_PAYMENT_RESULT_CHECK)
  })

  it('payment API 실패 시 판매상세 유지', async () => {
    fetchSalePayments.mockRejectedValue(new Error('network'))
    const { wrapper } = await mountDetail()
    expect(wrapper.text()).toContain('판매상세')
    expect(wrapper.text()).toContain('수금 내역을 불러오지 못했습니다.')
  })

  it('뒤로가기 sales tab', async () => {
    const { wrapper, router } = await mountDetail()
    const replaceSpy = vi.spyOn(router, 'replace')
    const pushSpy = vi.spyOn(router, 'push')
    await wrapper.findComponent(OdsAppBar).vm.$emit('back')
    expect(replaceSpy).toHaveBeenCalledWith({ name: 'orders', query: { tab: TAB_SALES } })
    expect(pushSpy).not.toHaveBeenCalled()
  })
})
