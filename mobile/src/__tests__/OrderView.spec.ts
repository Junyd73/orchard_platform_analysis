import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import OrderView from '@/views/orders/OrderView.vue'
import {
  LABEL_DETAIL_LOOKUP,
  LABEL_FAB_ORDER,
  LABEL_FAB_SALES,
  LABEL_LOOKUP,
  LABEL_LOOKUP_PERIOD,
  LABEL_PAGE_NEXT,
  LABEL_PAGE_PREV,
  LABEL_QUICK_RANGE,
  LABEL_RESET,
  LABEL_SEARCH_PLACEHOLDER,
  LABEL_STATUS_ALL,
  MSG_ORDER_EMPTY_DESC,
  MSG_ORDER_EMPTY_FILTER,
  MSG_ORDER_EMPTY_TITLE,
  MSG_SALES_EMPTY_DESC,
  MSG_SALES_EMPTY_TITLE,
  MSG_STAGE_LATER,
  MSG_STOCK_EMPTY_DESC,
  MSG_STOCK_EMPTY_TITLE,
  ORDER_LIST_PAGE_SIZE,
  ORDER_STATUS_PREP,
  ORDER_STATUS_RESERVED,
  orderStatusLabelOf,
} from '@/views/orders/ordersConstants'
import { yearStartIso } from '@/views/orders/orderLookup'
import { todayIso } from '@/views/work-log/workLogConstants'
import type { OrderListItem, OrderListPage } from '@/types/order'

const fetchOrders = vi.fn()
const fetchCommonCodes = vi.fn()
const fetchHarvestRecords = vi.fn()
const fetchRawStock = vi.fn()
const listFruitStock = vi.fn()
const listStockLogs = vi.fn()

vi.mock('@/api/orders', () => ({
  fetchOrders: (...args: unknown[]) => fetchOrders(...args),
}))

vi.mock('@/api/commonCodes', () => ({
  fetchCommonCodes: (...args: unknown[]) => fetchCommonCodes(...args),
}))

vi.mock('@/api/production', () => ({
  fetchHarvestRecords: (...args: unknown[]) => fetchHarvestRecords(...args),
  fetchRawStock: (...args: unknown[]) => fetchRawStock(...args),
  confirmProduction: vi.fn(),
}))

vi.mock('@/api/stock', () => ({
  listFruitStock: (...args: unknown[]) => listFruitStock(...args),
  listStockLogs: (...args: unknown[]) => listStockLogs(...args),
}))

const SAMPLE: OrderListItem = {
  order_no: 'ORD20260817-001',
  order_dt: '2026-08-17',
  custm_id: 'C001',
  customer: '김고객',
  status_cd: ORDER_STATUS_RESERVED,
  status_nm: '예약수신',
  total_qty: 30,
  total_amt: 50000,
  pre_pay_amt: 10000,
  line_count: 2,
  rep_item_cd: 'FR010100',
  rep_variety_cd: 'FR010101',
  rep_variety_nm: '신고',
  rep_grade_cd: 'GR010100',
  rep_grade_nm: '특',
  rep_size_cd: 'FR020101',
  rep_size_nm: '18과',
  rep_weight: 15,
  delivery_tp_cd: 'LO010200',
  delivery_tp_nm: '택배',
  delivery_tp_count: 1,
  confirmed_shipped_qty: 10,
  remaining_order_qty: 20,
}

function pageOf(
  items: OrderListItem[],
  extra?: Partial<OrderListPage>,
): OrderListPage {
  return {
    items,
    total: extra?.total ?? items.length,
    page: extra?.page ?? 1,
    page_size: extra?.page_size ?? ORDER_LIST_PAGE_SIZE,
  }
}

async function mountOrders() {
  setActivePinia(createPinia())
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: { template: '<div />' } },
      { path: '/orders', name: 'orders', component: OrderView },
      { path: '/orders/new', name: 'order-new', component: { template: '<div class="new" />' } },
      { path: '/orders/ship', name: 'ship-confirm', component: { template: '<div class="ship" />' } },
      {
        path: '/orders/:orderNo',
        name: 'order-detail',
        component: { template: '<div class="detail" />' },
      },
      { path: '/settings', name: 'settings', component: { template: '<div />' } },
    ],
  })
  await router.push('/orders')
  await router.isReady()
  const wrapper = mount(OrderView, {
    global: {
      plugins: [router],
      stubs: {
        OdsAppBar: true,
        OdsBottomNav: true,
        OdsSkeleton: { template: '<div class="sk" />' },
        OdsFab: {
          props: ['label', 'ariaLabel'],
          emits: ['click'],
          template:
            '<button class="fab-stub" :aria-label="ariaLabel" @click="$emit(\'click\')">{{ label }}</button>',
        },
      },
    },
  })
  await flushPromises()
  return { wrapper, router }
}

describe('OrderView stage 2 lookup', () => {
  beforeEach(() => {
    fetchOrders.mockReset()
    fetchOrders.mockResolvedValue(pageOf([]))
    fetchCommonCodes.mockReset()
    fetchCommonCodes.mockResolvedValue([
      { code_cd: 'ST010100', code_nm: '예약수신', parent_cd: 'ST01' },
      { code_cd: 'ST010200', code_nm: '주문확정', parent_cd: 'ST01' },
      { code_cd: 'FR010101', code_nm: '신고', parent_cd: 'FR010100' },
      { code_cd: 'GR010100', code_nm: '특', parent_cd: 'GR01' },
      { code_cd: 'FR020101', code_nm: '18과', parent_cd: 'FR020100' },
      { code_cd: 'SZ010100', code_nm: '15kg', parent_cd: 'SZ01' },
    ])
    fetchHarvestRecords.mockReset()
    fetchHarvestRecords.mockResolvedValue([])
    fetchRawStock.mockReset()
    fetchRawStock.mockResolvedValue([])
    listFruitStock.mockReset()
    listFruitStock.mockResolvedValue([])
    listStockLogs.mockReset()
    listStockLogs.mockResolvedValue([])
  })

  it('shows empty state when there are no orders', async () => {
    const { wrapper } = await mountOrders()
    expect(wrapper.text()).not.toContain('판매관리')
    expect(wrapper.text()).toContain(MSG_ORDER_EMPTY_TITLE)
    expect(wrapper.text()).toContain(MSG_ORDER_EMPTY_DESC)
    expect(wrapper.find('.fab-stub').text()).toContain(LABEL_FAB_ORDER)
    const buttons = wrapper.findAll('.head .tab-bar__btn')
    expect(buttons).toHaveLength(4)
    expect(buttons[2].attributes('aria-selected')).toBe('true')
  })

  it('loads this-year range on first entry', async () => {
    await mountOrders()
    expect(fetchOrders).toHaveBeenCalledTimes(1)
    expect(fetchOrders.mock.calls[0][1]).toEqual({
      from_date: yearStartIso(todayIso()),
      to_date: todayIso(),
      status_cd: undefined,
      keyword: undefined,
      page: 1,
      page_size: ORDER_LIST_PAGE_SIZE,
    })
  })

  it('keeps filter collapsed with applied summary', async () => {
    const { wrapper } = await mountOrders()
    const today = todayIso()
    const summary = wrapper.find('.lookup-summary')
    expect(summary.text()).toContain(`${yearStartIso(today)} ~ ${today}`)
    expect(summary.text()).toContain(LABEL_DETAIL_LOOKUP)
    expect(summary.text()).not.toContain(LABEL_STATUS_ALL)
    expect(summary.find('.lookup-detail').exists()).toBe(true)
    expect(wrapper.find('.lookup-detail').attributes('aria-expanded')).toBe('false')
    expect(wrapper.find('.lookup-foot').exists()).toBe(false)
    expect(wrapper.text()).not.toContain(LABEL_LOOKUP_PERIOD)
    expect(wrapper.text()).not.toContain(LABEL_QUICK_RANGE)
    expect(wrapper.find('.lookup-body').exists()).toBe(true)
  })

  it('expands and collapses filter via 상세조회', async () => {
    const { wrapper } = await mountOrders()
    await wrapper.find('.lookup-detail').trigger('click')
    await nextTick()
    expect(wrapper.find('.lookup-summary .lookup-detail').exists()).toBe(true)
    expect(wrapper.find('.lookup-detail').attributes('aria-expanded')).toBe('true')
    expect(wrapper.text()).toContain('1개월')
    expect(wrapper.text()).toContain(LABEL_RESET)
    expect(wrapper.text()).toContain(LABEL_LOOKUP)
    expect(wrapper.text()).not.toContain(LABEL_LOOKUP_PERIOD)
    expect(wrapper.text()).not.toContain(LABEL_QUICK_RANGE)

    await wrapper.find('.lookup-detail').trigger('click')
    await nextTick()
    expect(wrapper.find('.lookup-detail').attributes('aria-expanded')).toBe('false')
  })

  it('renders compact 2-line order rows without order_no text', async () => {
    fetchOrders.mockResolvedValue(pageOf([SAMPLE]))
    const { wrapper } = await mountOrders()
    const rows = wrapper.findAll('.order-list__item')
    expect(rows).toHaveLength(1)
    expect(wrapper.find('.order-list__line1').exists()).toBe(true)
    expect(wrapper.find('.order-list__line2').exists()).toBe(true)
    // 목록 행은 OdsCard 로 감싸지 않는다 (조회 패널 카드와 구분)
    expect(wrapper.find('.order-list').find('.ods-card').exists()).toBe(false)

    const line1 = wrapper.find('.order-list__line1')
    expect(line1.text()).toContain('김고객')
    expect(line1.text()).toContain('30')
    expect(line1.text()).toContain('10/20')
    expect(line1.text()).toContain(orderStatusLabelOf(ORDER_STATUS_RESERVED))
    expect(line1.text()).toContain('예약접수')

    const line2 = wrapper.find('.order-list__line2')
    expect(line2.text()).toContain('신고')
    expect(line2.text()).toContain('외 1건')
    expect(line2.text()).toContain('택배')
    expect(line2.text()).toContain('08-17')

    // 주문번호는 본문에 노출하지 않는다 (a11y label 로만 제공)
    expect(wrapper.text()).not.toContain('ORD20260817-001')
    expect(wrapper.find('.order-list__row').attributes('aria-label')).toContain(
      'ORD20260817-001',
    )
    expect(wrapper.text()).not.toContain(MSG_ORDER_EMPTY_TITLE)
  })

  it('shows 부분출고 label for ST010300 rows', async () => {
    fetchOrders.mockResolvedValue(
      pageOf([{ ...SAMPLE, status_cd: ORDER_STATUS_PREP, status_nm: '배송준비' }]),
    )
    const { wrapper } = await mountOrders()
    expect(wrapper.find('.order-list__line1').text()).toContain('부분출고')
    expect(wrapper.text()).not.toContain('배송준비')
    expect(wrapper.find('.order-list__status').classes()).toContain('ods-badge--caution')
  })

  it('shows 복합배송 when the order mixes delivery types', async () => {
    fetchOrders.mockResolvedValue(
      pageOf([{ ...SAMPLE, delivery_tp_count: 2, delivery_tp_cd: '', delivery_tp_nm: '' }]),
    )
    const { wrapper } = await mountOrders()
    const line2 = wrapper.find('.order-list__line2')
    expect(line2.text()).toContain('복합배송')
    expect(line2.text()).not.toContain('택배')
  })

  it('opens order detail when a row is tapped', async () => {
    fetchOrders.mockResolvedValue(pageOf([SAMPLE]))
    const { wrapper, router } = await mountOrders()
    await wrapper.find('.order-list__row').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('order-detail')
    expect(router.currentRoute.value.params.orderNo).toBe('ORD20260817-001')
  })

  it('shows filtered empty copy and keeps accordion open after apply', async () => {
    fetchOrders.mockResolvedValue(pageOf([]))
    const { wrapper } = await mountOrders()
    await wrapper.find('.lookup-detail').trigger('click')
    await wrapper.find(`input[placeholder="${LABEL_SEARCH_PLACEHOLDER}"]`).setValue('없는고객')
    await wrapper.findAll('.ods-btn').find((btn) => btn.text() === LABEL_LOOKUP)?.trigger('click')
    await flushPromises()
    expect(fetchOrders.mock.calls.at(-1)?.[1]).toMatchObject({ keyword: '없는고객' })
    expect(wrapper.text()).toContain(MSG_ORDER_EMPTY_FILTER)
    expect(wrapper.find('.lookup-summary').text()).not.toContain('없는고객')
    expect(wrapper.find('.lookup-detail').attributes('aria-expanded')).toBe('true')
  })

  it('resets page to 1 when applying filters', async () => {
    fetchOrders.mockResolvedValue(pageOf([SAMPLE], { total: 25, page: 1 }))
    const { wrapper } = await mountOrders()
    fetchOrders.mockResolvedValue(pageOf([SAMPLE], { total: 25, page: 2 }))
    await wrapper.findAll('.ods-btn').find((btn) => btn.text() === LABEL_PAGE_NEXT)?.trigger('click')
    await flushPromises()
    expect(fetchOrders.mock.calls.at(-1)?.[1]).toMatchObject({ page: 2 })

    await wrapper.find('.lookup-detail').trigger('click')
    await wrapper.find(`input[placeholder="${LABEL_SEARCH_PLACEHOLDER}"]`).setValue('김고객')
    fetchOrders.mockResolvedValue(pageOf([SAMPLE], { total: 1, page: 1 }))
    await wrapper.findAll('.ods-btn').find((btn) => btn.text() === LABEL_LOOKUP)?.trigger('click')
    await flushPromises()
    expect(fetchOrders.mock.calls.at(-1)?.[1]).toMatchObject({
      keyword: '김고객',
      page: 1,
    })
    expect(wrapper.text()).toContain('김고객')
    expect(wrapper.find('.lookup-detail').attributes('aria-expanded')).toBe('true')
  })

  it('applies quick range when expanded', async () => {
    const { wrapper } = await mountOrders()
    await wrapper.find('.lookup-detail').trigger('click')
    const chips = wrapper.findAll('.quick__chip')
    expect(chips.length).toBeGreaterThanOrEqual(3)
    await chips[0].trigger('click')
    expect(wrapper.find('.date-iso__value').text()).not.toBe('')
  })

  it('resets lookup via outline action', async () => {
    const { wrapper } = await mountOrders()
    await wrapper.find('.lookup-detail').trigger('click')
    await wrapper.find(`input[placeholder="${LABEL_SEARCH_PLACEHOLDER}"]`).setValue('테스트')
    await wrapper.findAll('.ods-btn').find((btn) => btn.text() === LABEL_RESET)?.trigger('click')
    await flushPromises()
    expect(fetchOrders.mock.calls.at(-1)?.[1]).toMatchObject({
      from_date: yearStartIso(todayIso()),
      to_date: todayIso(),
      page: 1,
    })
    expect(wrapper.find('.lookup-summary').text()).not.toContain(LABEL_STATUS_ALL)
  })

  it('pages with previous/next', async () => {
    fetchOrders.mockResolvedValue(pageOf([SAMPLE], { total: 25, page: 1 }))
    const { wrapper } = await mountOrders()
    expect(wrapper.text()).toContain('1 / 2')
    expect(
      wrapper.findAll('.ods-btn').find((btn) => btn.text() === LABEL_PAGE_PREV)?.attributes('disabled'),
    ).toBeDefined()

    fetchOrders.mockResolvedValue(pageOf([{ ...SAMPLE, order_no: 'ORD20260817-002' }], { total: 25, page: 2 }))
    await wrapper.findAll('.ods-btn').find((btn) => btn.text() === LABEL_PAGE_NEXT)?.trigger('click')
    await flushPromises()
    expect(fetchOrders.mock.calls.at(-1)?.[1]).toMatchObject({ page: 2 })
    expect(wrapper.text()).toContain('2 / 2')
  })

  it('shows pack/prod panel and stock placeholder without FAB', async () => {
    const { wrapper } = await mountOrders()
    const buttons = wrapper.findAll('.head .tab-bar__btn')
    await buttons[0].trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('배 포장')
    expect(wrapper.text()).toContain('생산확정')
    expect(wrapper.find('.fab-stub').exists()).toBe(false)

    await buttons[1].trigger('click')
    await flushPromises()
    // 재고 탭은 StockView를 렌더링 (원물/상품/배즙 탭 포함)
    expect(wrapper.text()).toContain('상품')
    expect(wrapper.text()).toContain('원물')
    expect(wrapper.find('.fab-stub').exists()).toBe(false)
    expect(listFruitStock).toHaveBeenCalled()

    listFruitStock.mockClear()
    await buttons[0].trigger('click')
    await flushPromises()
    await buttons[1].trigger('click')
    await flushPromises()
    expect(listFruitStock).toHaveBeenCalled()
  })

  it('switches to 판매 segment and keeps empty sales copy', async () => {
    const { wrapper } = await mountOrders()
    const buttons = wrapper.findAll('.head .tab-bar__btn')
    await buttons[3].trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain(MSG_SALES_EMPTY_TITLE)
    expect(wrapper.text()).toContain(MSG_SALES_EMPTY_DESC)
    expect(wrapper.text()).not.toContain(MSG_ORDER_EMPTY_TITLE)
    expect(wrapper.find('.fab-stub').text()).toContain(LABEL_FAB_SALES)
    expect(wrapper.find('.lookup-detail').exists()).toBe(false)
  })

  it('order FAB navigates to /orders/new', async () => {
    const { wrapper, router } = await mountOrders()
    await wrapper.find('.fab-stub').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('order-new')
    expect(wrapper.text()).not.toContain(MSG_STAGE_LATER)
  })

  it('reloads list when returning from /orders/new', async () => {
    const { wrapper, router } = await mountOrders()
    expect(fetchOrders).toHaveBeenCalledTimes(1)
    await wrapper.find('.fab-stub').trigger('click')
    await flushPromises()
    fetchOrders.mockResolvedValue(pageOf([SAMPLE]))
    await router.push('/orders')
    await flushPromises()
    expect(fetchOrders.mock.calls.length).toBeGreaterThanOrEqual(2)
    expect(wrapper.text()).toContain('김고객')
    expect(wrapper.findAll('.order-list__item')).toHaveLength(1)
  })

  it('sales FAB without prefill switches to stock with hint', async () => {
    const { wrapper } = await mountOrders()
    const buttons = wrapper.findAll('.head .tab-bar__btn')
    await buttons[3].trigger('click')
    await wrapper.find('.fab-stub').trigger('click')
    expect(wrapper.text()).toContain('상품 재고에서 판매를 선택하세요.')
    expect(wrapper.text()).toContain('상품')
  })
})
