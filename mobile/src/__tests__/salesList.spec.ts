import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import OrderView from '@/features/orders/OrderView.vue'
import {
  LABEL_FAB_SALES,
  MSG_ORDER_LOAD_FAIL,
  MSG_SALES_EMPTY_DESC,
  MSG_SALES_EMPTY_TITLE,
  ORDER_LIST_PAGE_SIZE,
} from '@/features/orders/ordersConstants'
import {
  MSG_SALES_LOAD_FAIL,
  SALES_LIST_PAGE_SIZE,
} from '@/features/sales/salesConstants'
import type { OrderListPage } from '@/types/order'
import type { SalesListItem, SalesListPage } from '@/types/sales'

const fetchOrders = vi.fn()
const fetchSales = vi.fn()
const fetchCommonCodes = vi.fn()

vi.mock('@/api/orders', () => ({
  fetchOrders: (...args: unknown[]) => fetchOrders(...args),
}))

vi.mock('@/api/sales', () => ({
  fetchSales: (...args: unknown[]) => fetchSales(...args),
}))

vi.mock('@/api/commonCodes', () => ({
  fetchCommonCodes: (...args: unknown[]) => fetchCommonCodes(...args),
}))

vi.mock('@/api/production', () => ({
  fetchHarvestRecords: vi.fn().mockResolvedValue({ items: [] }),
  fetchRawStock: vi.fn().mockResolvedValue({ items: [] }),
  confirmProduction: vi.fn(),
}))

vi.mock('@/api/stock', () => ({
  listFruitStock: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  listStockLogs: vi.fn().mockResolvedValue({ items: [] }),
}))

const SALES_SAMPLE: SalesListItem = {
  sales_no: '20260822-01',
  sales_dt: '2026-08-22',
  custm_id: 'C001',
  customer: '홍길동',
  order_no: 'ORD20260822-001',
  sales_status: 'CONFIRMED',
  sales_source: 'ORDER',
  tot_sales_amt: 950000,
  paid_amt: 800000,
  unpaid_amt: 150000,
  payment_status: 'PARTIAL',
  rep_item_cd: 'FR010100',
  rep_variety_cd: 'FR010101',
  rep_variety_nm: '신고',
  rep_weight: 15,
  rep_grade_cd: 'GR010100',
  rep_grade_nm: '특',
  rep_size_cd: 'SZ010100',
  rep_size_nm: '20과',
}

async function mountOrders() {
  setActivePinia(createPinia())
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/orders', name: 'orders', component: OrderView },
      { path: '/orders/new', name: 'order-new', component: { template: '<div />' } },
      { path: '/orders/ship', name: 'ship-confirm', component: { template: '<div />' } },
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
        StockView: { template: '<div class="stock-stub" />' },
        PackProdPanel: { template: '<div class="pack-stub" />' },
      },
    },
  })
  await flushPromises()
  return { wrapper, router }
}

describe('OrderView sales list stage 5', () => {
  beforeEach(() => {
    fetchOrders.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: ORDER_LIST_PAGE_SIZE,
    } satisfies OrderListPage)
    fetchSales.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: SALES_LIST_PAGE_SIZE,
    } satisfies SalesListPage)
    fetchCommonCodes.mockResolvedValue([])
  })

  it('주문탭에서는 fetchSales를 호출하지 않는다', async () => {
    await mountOrders()
    expect(fetchOrders).toHaveBeenCalled()
    expect(fetchSales).not.toHaveBeenCalled()
  })

  it('판매탭 진입 시 fetchSales 호출', async () => {
    const { wrapper } = await mountOrders()
    const tabs = wrapper.findAll('.head .tab-bar__btn')
    await tabs[3].trigger('click')
    await flushPromises()
    expect(fetchSales).toHaveBeenCalledTimes(1)
    expect(wrapper.find('.lookup-detail').exists()).toBe(true)
  })

  it('판매탭 2줄 목록·배지', async () => {
    fetchSales.mockResolvedValue({
      items: [SALES_SAMPLE],
      total: 1,
      page: 1,
      page_size: SALES_LIST_PAGE_SIZE,
    })
    const { wrapper } = await mountOrders()
    await wrapper.findAll('.head .tab-bar__btn')[3].trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('홍길동')
    expect(wrapper.text()).toContain('950,000')
    expect(wrapper.text()).toContain('800,000')
    expect(wrapper.text()).toContain('150,000')
    expect(wrapper.text()).toContain('부분수금')
    expect(wrapper.text()).toContain('판매확정')
    expect(wrapper.text()).toContain('주문출고')
    expect(wrapper.findAll('.sales-list__item')).toHaveLength(1)
  })

  it('판매 empty copy', async () => {
    const { wrapper } = await mountOrders()
    await wrapper.findAll('.head .tab-bar__btn')[3].trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain(MSG_SALES_EMPTY_TITLE)
    expect(wrapper.text()).toContain(MSG_SALES_EMPTY_DESC)
    expect(wrapper.text()).not.toContain(MSG_ORDER_LOAD_FAIL)
  })

  it('판매 error copy', async () => {
    fetchSales.mockRejectedValue(new Error('fail'))
    const { wrapper } = await mountOrders()
    await wrapper.findAll('.head .tab-bar__btn')[3].trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain(MSG_SALES_LOAD_FAIL)
  })

  it('판매 FAB 기존 회귀', async () => {
    const { wrapper } = await mountOrders()
    await wrapper.findAll('.head .tab-bar__btn')[3].trigger('click')
    await flushPromises()
    expect(wrapper.find('.fab-stub').text()).toContain(LABEL_FAB_SALES)
    await wrapper.find('.fab-stub').trigger('click')
    expect(wrapper.text()).toContain('상품 재고에서 판매를 선택하세요.')
  })
})
