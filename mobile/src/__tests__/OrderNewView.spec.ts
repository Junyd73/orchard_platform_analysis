import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import { createCustomer, createOrder, fetchCustomers, fetchOrder, updateOrder } from '@/api/orders'
import OrderNewView from '@/views/orders/OrderNewView.vue'
import {
  LABEL_ALLOC,
  LABEL_CUSTOMER,
  LABEL_CUSTOMER_SAVE,
  LABEL_DELIVERY_INFO,
  LABEL_DELIVERY_TP,
  LABEL_DEST_QTY,
  LABEL_EDIT_ORDER,
  LABEL_LINE,
  LABEL_NEW_ORDER,
  LABEL_ORDER_DT,
  LABEL_QTY,
  LABEL_REMOVE_LINE,
  LABEL_RCV_ADDR,
  LABEL_RCV_NAME,
  LABEL_RCV_TEL,
  LABEL_SAVE_ORDER,
  LABEL_SIZE,
  LABEL_UNASSIGNED,
  LABEL_VARIETY,
  LABEL_WEIGHT,
  MSG_LINE_REQUIRED,
  MSG_PARCEL_QTY_MISMATCH,
  formatOrderLineSpec,
  parseWeightFromCodeNm,
  pickDefaultWeightCd,
} from '@/views/orders/ordersConstants'

vi.mock('@/api/orders', () => ({
  fetchCustomers: vi.fn().mockResolvedValue([
    { custm_id: 'C001', custm_nm: '김고객', mobile: '010-0000-0000' },
  ]),
  createOrder: vi.fn().mockResolvedValue({ order_no: 'ORD20260817-001' }),
  createCustomer: vi.fn(),
  fetchOrder: vi.fn(),
  updateOrder: vi.fn(),
}))

vi.mock('@/api/commonCodes', () => ({
  fetchCommonCodes: vi.fn().mockImplementation((_farm: string, parent: string) => {
    if (parent === 'FR01') {
      return Promise.resolve([
        { farm_cd: 'OR001', code_cd: 'FR010100', code_nm: '배', parent_cd: 'FR01' },
        { farm_cd: 'OR001', code_cd: 'FR010200', code_nm: '배즙', parent_cd: 'FR01' },
      ])
    }
    if (parent === 'FR010100') {
      return Promise.resolve([
        { farm_cd: 'OR001', code_cd: 'FR010101', code_nm: '신고배', parent_cd: 'FR010100' },
        { farm_cd: 'OR001', code_cd: 'FR010102', code_nm: '원황배', parent_cd: 'FR010100' },
      ])
    }
    if (parent === 'GR01') {
      return Promise.resolve([
        { farm_cd: 'OR001', code_cd: 'GR010100', code_nm: '골드특', parent_cd: 'GR01' },
      ])
    }
    if (parent === 'SZ01') {
      return Promise.resolve([
        { farm_cd: 'OR001', code_cd: 'SZ010100', code_nm: '5kg', parent_cd: 'SZ01' },
        { farm_cd: 'OR001', code_cd: 'SZ010200', code_nm: '7.5kg', parent_cd: 'SZ01' },
        { farm_cd: 'OR001', code_cd: 'SZ010300', code_nm: '15kg', parent_cd: 'SZ01' },
        { farm_cd: 'OR001', code_cd: 'SZ010400', code_nm: '10포', parent_cd: 'SZ01' },
      ])
    }
    if (parent === 'FR020100') {
      return Promise.resolve([
        { farm_cd: 'OR001', code_cd: 'FR020101', code_nm: '20과이내', parent_cd: 'FR020100' },
        { farm_cd: 'OR001', code_cd: 'FR020102', code_nm: '25과이내', parent_cd: 'FR020100' },
      ])
    }
    if (parent === 'LO01') {
      return Promise.resolve([
        { farm_cd: 'OR001', code_cd: 'LO010100', code_nm: '방문수령', parent_cd: 'LO01' },
        { farm_cd: 'OR001', code_cd: 'LO010200', code_nm: '택배', parent_cd: 'LO01' },
      ])
    }
    return Promise.resolve([])
  }),
}))

function fieldByLabel(wrapper: ReturnType<typeof mount>, label: string) {
  return wrapper.findAll('.ods-form-field').find((f) => {
    const lab = f.find('.ods-form-field__label-text')
    return lab.exists() && lab.text() === label
  })
}

async function openShip(wrapper: ReturnType<typeof mount>) {
  if (!fieldByLabel(wrapper, LABEL_DELIVERY_TP)) {
    await wrapper.find('.ship-head').trigger('click')
  }
}

async function selectParcel(wrapper: ReturnType<typeof mount>) {
  await openShip(wrapper)
  await fieldByLabel(wrapper, LABEL_DELIVERY_TP)?.find('select').setValue('LO010200')
  await flushPromises()
}

async function fillOpenDest(
  wrapper: ReturnType<typeof mount>,
  dest: { qty: string; name: string; tel: string; addr: string },
) {
  await fieldByLabel(wrapper, LABEL_DEST_QTY)?.find('input').setValue(dest.qty)
  await fieldByLabel(wrapper, LABEL_RCV_NAME)?.find('input').setValue(dest.name)
  await fieldByLabel(wrapper, LABEL_RCV_TEL)?.find('input').setValue(dest.tel)
  await fieldByLabel(wrapper, LABEL_RCV_ADDR)?.find('input').setValue(dest.addr)
}

async function clickSave(wrapper: ReturnType<typeof mount>) {
  const saveBtn = wrapper.findAll('button').find((b) => b.text().includes(LABEL_SAVE_ORDER))
  await saveBtn?.trigger('click')
  await flushPromises()
}

async function mountNewOrder() {
  setActivePinia(createPinia())
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/orders', name: 'orders', component: { template: '<div />' } },
      { path: '/orders/new', name: 'order-new', component: OrderNewView },
      {
        path: '/orders/:orderNo/edit',
        name: 'order-edit',
        component: OrderNewView,
      },
      {
        path: '/orders/:orderNo',
        name: 'order-detail',
        component: { template: '<div class="detail" />' },
      },
    ],
  })
  await router.push('/orders/new')
  await router.isReady()
  const wrapper = mount(OrderNewView, {
    global: {
      plugins: [router],
      stubs: { OdsAppBar: true, OdsBottomNav: true },
    },
    attachTo: document.body,
  })
  await flushPromises()
  return wrapper
}

function sampleEditDetail() {
  return {
    order_no: 'ORD20260817-001',
    order_dt: '2026-08-17',
    custm_id: 'C001',
    customer: '김고객',
    status_cd: 'ST010100',
    status_nm: '예약접수',
    total_qty: 10,
    total_amt: 500000,
    pre_pay_amt: 1000,
    mobile: '010-0000-0000',
    stock_status: 'N',
    season_type_cd: '',
    tot_order_amt: 500000,
    tot_ship_fee: 0,
    tot_pay_amt: 1000,
    rmk: '기존비고',
    sales_no: '',
    lines: [
      {
        order_detail_id: 'ORD20260817-001-01',
        item_cd: 'FR010100',
        variety_cd: 'FR010101',
        variety_nm: '신고배',
        grade_cd: 'GR010100',
        grade_nm: '골드특',
        size_cd: 'FR020102',
        size_nm: '25과이내',
        weight: 7.5,
        qty: 10,
        unit_price: 50000,
        item_amt: 500000,
        harvest_year: 2026,
        wh_cd: 'WH01',
        dlvry_tp: 'LO010200',
        dlvry_tp_nm: '택배',
        deliveries: [
          {
            order_dlvry_id: 'ORD20260817-001-01-P01',
            order_detail_id: 'ORD20260817-001-01',
            delivery_tp_cd: 'LO010200',
            qty: 3,
            planned_dt: '2026-08-17',
            snd_name: '',
            snd_tel: '',
            snd_addr: '',
            rcv_name: '이문자',
            rcv_tel: '010-1111-0001',
            rcv_addr: '경기 A',
            dlvry_msg: '',
          },
          {
            order_dlvry_id: 'ORD20260817-001-01-P02',
            order_detail_id: 'ORD20260817-001-01',
            delivery_tp_cd: 'LO010200',
            qty: 7,
            planned_dt: '2026-08-17',
            snd_name: '',
            snd_tel: '',
            snd_addr: '',
            rcv_name: '김수령',
            rcv_tel: '010-1111-0002',
            rcv_addr: '경기 B',
            dlvry_msg: '',
          },
        ],
      },
    ],
  }
}

async function mountEditOrder() {
  setActivePinia(createPinia())
  vi.mocked(fetchOrder).mockResolvedValue(sampleEditDetail() as never)
  vi.mocked(updateOrder).mockResolvedValue(sampleEditDetail() as never)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/orders', name: 'orders', component: { template: '<div />' } },
      { path: '/orders/new', name: 'order-new', component: OrderNewView },
      {
        path: '/orders/:orderNo/edit',
        name: 'order-edit',
        component: OrderNewView,
      },
      {
        path: '/orders/:orderNo',
        name: 'order-detail',
        component: { template: '<div class="detail" />' },
      },
    ],
  })
  await router.push('/orders/ORD20260817-001/edit')
  await router.isReady()
  const wrapper = mount(OrderNewView, {
    global: {
      plugins: [router],
      stubs: { OdsAppBar: true, OdsBottomNav: true },
    },
    attachTo: document.body,
  })
  await flushPromises()
  return wrapper
}

describe('order spec helpers', () => {
  it('parses kg code names and defaults to 15kg', () => {
    expect(parseWeightFromCodeNm('5kg')).toBe(5)
    expect(parseWeightFromCodeNm('7.5kg')).toBe(7.5)
    expect(parseWeightFromCodeNm('15kg')).toBe(15)
    expect(
      pickDefaultWeightCd([
        { code_cd: 'SZ010100', code_nm: '5kg' },
        { code_cd: 'SZ010300', code_nm: '15kg' },
      ]),
    ).toBe('SZ010300')
  })

  it('formats line spec with code names', () => {
    expect(
      formatOrderLineSpec({
        variety_cd: 'FR010101',
        variety_nm: '신고배',
        weight: 7.5,
        grade_cd: 'GR010200',
        grade_nm: '특',
        size_cd: 'FR020101',
        size_nm: '25과 이내',
      }),
    ).toBe('신고배 · 7.5kg · 특 · 25과 이내')
    expect(
      formatOrderLineSpec({
        item_cd: 'FR010202',
        item_nm: '순배즙',
        variety_cd: 'FR010101',
        variety_nm: '신고배',
        weight: 30,
        grade_cd: 'QT010100',
        grade_nm: '30포',
        size_cd: 'SZ010100',
        size_nm: '5kg',
      }),
    ).toBe('일반배즙')
  })
})

describe('OrderNewView', () => {
  beforeEach(() => {
    vi.mocked(createCustomer).mockReset()
    vi.mocked(createOrder).mockClear()
    vi.mocked(updateOrder).mockReset()
    vi.mocked(fetchOrder).mockReset()
    vi.mocked(fetchCustomers).mockReset()
    vi.mocked(fetchCustomers).mockResolvedValue([
      { custm_id: 'C001', custm_nm: '김고객', mobile: '010-0000-0000' },
    ])
  })
  it('renders order form fields', async () => {
    const wrapper = await mountNewOrder()
    expect(wrapper.text()).toContain(LABEL_NEW_ORDER)
    expect(wrapper.text()).toContain(LABEL_CUSTOMER)
    expect(wrapper.text()).toContain(LABEL_VARIETY)
    expect(wrapper.text()).toContain(LABEL_SAVE_ORDER)
    expect(wrapper.text()).toContain('김고객')
    wrapper.unmount()
  })

  it('품종 select는 중분류(배)가 아니라 소분류(신고배)만 표시', async () => {
    const wrapper = await mountNewOrder()
    const varietyField = fieldByLabel(wrapper, LABEL_VARIETY)
    const opts = varietyField?.findAll('option') || []
    const labels = opts.map((o) => o.text())
    expect(labels).toContain('신고배')
    expect(labels).toContain('원황배')
    expect(labels).not.toContain('배')
    expect(labels).not.toContain('배즙')
    const select = varietyField?.find('select')
    expect((select?.element as HTMLSelectElement | undefined)?.value).toBe('FR010101')
    wrapper.unmount()
  })

  it('uses a two-column form grid and full-width address', async () => {
    const wrapper = await mountNewOrder()
    expect(wrapper.findAll('.form-grid').length).toBeGreaterThan(0)
    const grids = wrapper.findAll('.form-grid')
    const basic = grids[0]
    expect(basic.classes()).toContain('form-grid')
    expect(getComputedStyle(basic.element).gridTemplateColumns.split(' ').length).toBeGreaterThanOrEqual(1)
    expect(wrapper.text()).toContain(LABEL_ORDER_DT)
    await wrapper.find('.ship-head').trigger('click')
    expect(wrapper.findAll('.form-span-2').length).toBeGreaterThan(0)
    wrapper.unmount()
  })

  it('collapses to one column under 360px without clipping labels', async () => {
    const wrapper = await mountNewOrder()
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 320 })
    window.dispatchEvent(new Event('resize'))
    await flushPromises()
    expect(wrapper.text()).toContain(LABEL_CUSTOMER)
    expect(wrapper.text()).toContain(LABEL_WEIGHT)
    expect(wrapper.find('.form-grid').exists()).toBe(true)
    wrapper.unmount()
  })

  it('uses SZ01 kg codes for weight and FR020100 for size', async () => {
    const wrapper = await mountNewOrder()
    const weight = fieldByLabel(wrapper, LABEL_WEIGHT)
    const size = fieldByLabel(wrapper, LABEL_SIZE)
    expect(weight?.find('select').exists()).toBe(true)
    expect(weight?.text()).toContain('5kg')
    expect(weight?.text()).toContain('7.5kg')
    expect(weight?.text()).toContain('15kg')
    expect(weight?.text()).not.toContain('10포')
    expect(weight?.find('select').element).toMatchObject({ value: 'SZ010300' })
    expect(size?.text()).toContain('20과이내')
    expect(size?.text()).toContain('25과이내')
    expect(size?.text()).not.toContain('5kg')
    expect(size?.find('select').element).toMatchObject({ value: 'FR020101' })
    wrapper.unmount()
  })

  it('keeps existing customer selectable', async () => {
    const wrapper = await mountNewOrder()
    const customer = fieldByLabel(wrapper, LABEL_CUSTOMER)
    await customer?.find('select').setValue('C001')
    expect((customer?.find('select').element as HTMLSelectElement).value).toBe('C001')
    wrapper.unmount()
  })

  it('registers a customer then auto-selects it', async () => {
    vi.mocked(createCustomer).mockResolvedValueOnce({
      custm_id: 'C260817120000',
      custm_nm: '신규고객',
      mobile: '010-9999-0000',
    })
    vi.mocked(fetchCustomers).mockResolvedValueOnce([
      { custm_id: 'C001', custm_nm: '김고객', mobile: '010-0000-0000' },
    ])
    vi.mocked(fetchCustomers).mockResolvedValueOnce([
      { custm_id: 'C001', custm_nm: '김고객', mobile: '010-0000-0000' },
      { custm_id: 'C260817120000', custm_nm: '신규고객', mobile: '010-9999-0000' },
    ])
    const wrapper = await mountNewOrder()
    await wrapper.find('.link-btn').trigger('click')
    await flushPromises()
    const modal = wrapper.find('.modal')
    expect(modal.exists()).toBe(true)
    const nameField = fieldByLabel(wrapper, '고객명')
    const mobileField = fieldByLabel(wrapper, '연락처')
    await nameField?.find('input').setValue('신규고객')
    await mobileField?.find('input').setValue('010-9999-0000')
    const saveBtn = wrapper.findAll('button').find((b) => b.text().includes(LABEL_CUSTOMER_SAVE))
    await saveBtn?.trigger('click')
    await flushPromises()
    expect(createCustomer).toHaveBeenCalled()
    const customer = fieldByLabel(wrapper, LABEL_CUSTOMER)
    expect((customer?.find('select').element as HTMLSelectElement).value).toBe('C260817120000')
    expect(wrapper.text()).toContain('신규고객')
    expect(wrapper.find('.modal').exists()).toBe(false)
    wrapper.unmount()
  })

  it('keeps order form data when customer save fails', async () => {
    const { ApiClientError } = await import('@/api/client')
    vi.mocked(createCustomer).mockRejectedValueOnce(new ApiClientError('이미 등록된 연락처입니다.'))
    const wrapper = await mountNewOrder()
    const customer = fieldByLabel(wrapper, LABEL_CUSTOMER)
    await customer?.find('select').setValue('C001')
    const prepay = wrapper.findAll('input').find((i) => i.attributes('type') === 'number')
    if (prepay) await prepay.setValue('5000')
    await wrapper.find('.link-btn').trigger('click')
    await flushPromises()
    const saveBtn = wrapper.findAll('button').find((b) => b.text().includes(LABEL_CUSTOMER_SAVE))
    await saveBtn?.trigger('click')
    await flushPromises()
    expect(wrapper.find('.modal').exists()).toBe(true)
    expect(wrapper.text()).toContain('이미 등록된 연락처입니다.')
    expect((customer?.find('select').element as HTMLSelectElement).value).toBe('C001')
    wrapper.unmount()
  })

  it('saves numeric weight from the kg code and pear size_cd', async () => {
    const wrapper = await mountNewOrder()
    const customer = fieldByLabel(wrapper, LABEL_CUSTOMER)
    await customer?.find('select').setValue('C001')
    const buttons = wrapper.findAll('button')
    const saveBtn = buttons.find((b) => b.text().includes(LABEL_SAVE_ORDER))
    await saveBtn?.trigger('click')
    await flushPromises()
    expect(createOrder).toHaveBeenCalled()
    const payload = vi.mocked(createOrder).mock.calls.at(-1)?.[1] as {
      lines: { weight: number; size_cd: string }[]
    }
    expect(payload.lines[0].weight).toBe(15)
    expect(payload.lines[0].size_cd).toBe('FR020101')
    wrapper.unmount()
  })

  it('keeps only the first product expanded on entry', async () => {
    const wrapper = await mountNewOrder()
    expect(wrapper.findAll('.line-card')).toHaveLength(1)
    expect(wrapper.findAll('.line-card--open')).toHaveLength(1)
    expect(wrapper.find('.spec-grid').exists()).toBe(true)
    expect(wrapper.find('.line-summary').exists()).toBe(false)
    wrapper.unmount()
  })

  it('collapses the previous product and expands the new one', async () => {
    const wrapper = await mountNewOrder()
    await wrapper.find('.add-line-btn').trigger('click')
    await flushPromises()
    const cards = wrapper.findAll('.line-card')
    expect(cards).toHaveLength(2)
    expect(wrapper.findAll('.line-card--open')).toHaveLength(1)
    expect(cards[1].classes()).toContain('line-card--open')
    const summary = wrapper.find('.line-summary')
    expect(summary.exists()).toBe(true)
    expect(summary.text()).toContain(`${LABEL_LINE} 1`)
    expect(summary.text()).toContain('신고배')
    expect(summary.text()).toContain('15kg')
    expect(summary.text()).toContain('골드특')
    expect(summary.text()).toContain(LABEL_QTY)
    wrapper.unmount()
  })

  it('expands a collapsed product and keeps a single open card', async () => {
    const wrapper = await mountNewOrder()
    await wrapper.find('.add-line-btn').trigger('click')
    await wrapper.find('.line-summary').trigger('click')
    await flushPromises()
    const cards = wrapper.findAll('.line-card')
    expect(wrapper.findAll('.line-card--open')).toHaveLength(1)
    expect(cards[0].classes()).toContain('line-card--open')
    expect(cards[1].classes()).not.toContain('line-card--open')
    wrapper.unmount()
  })

  it('removes a product and keeps one expanded', async () => {
    const wrapper = await mountNewOrder()
    await wrapper.find('.add-line-btn').trigger('click')
    await wrapper.find('.line-head__del').trigger('click')
    expect(wrapper.findAll('.line-card')).toHaveLength(1)
    expect(wrapper.findAll('.line-card--open')).toHaveLength(1)
    expect(wrapper.findAll('button').some((b) => b.text() === LABEL_REMOVE_LINE)).toBe(false)
    wrapper.unmount()
  })

  it('toggles delivery fields inside the open product', async () => {
    const wrapper = await mountNewOrder()
    expect(fieldByLabel(wrapper, LABEL_DELIVERY_TP)).toBeUndefined()
    expect(wrapper.text()).toContain(LABEL_DELIVERY_INFO)
    expect(wrapper.text()).toContain('방문수령')
    await wrapper.find('.ship-head').trigger('click')
    expect(fieldByLabel(wrapper, LABEL_DELIVERY_TP)?.find('select').exists()).toBe(true)
    await wrapper.find('.ship-head').trigger('click')
    expect(fieldByLabel(wrapper, LABEL_DELIVERY_TP)).toBeUndefined()
    wrapper.unmount()
  })

  it('expands the invalid product when save validation fails', async () => {
    const wrapper = await mountNewOrder()
    const customer = fieldByLabel(wrapper, LABEL_CUSTOMER)
    await customer?.find('select').setValue('C001')
    await wrapper.find('.add-line-btn').trigger('click')
    const openQty = fieldByLabel(wrapper, LABEL_QTY)
    await openQty?.find('input').setValue('0')
    await wrapper.find('.line-summary').trigger('click')
    const firstQty = fieldByLabel(wrapper, LABEL_QTY)
    await firstQty?.find('input').setValue('0')
    const saveBtn = wrapper.findAll('button').find((b) => b.text().includes(LABEL_SAVE_ORDER))
    await saveBtn?.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain(MSG_LINE_REQUIRED)
    expect(wrapper.findAll('.line-card--open')).toHaveLength(1)
    expect(wrapper.findAll('.line-card')[0].classes()).toContain('line-card--open')
    expect(fieldByLabel(wrapper, LABEL_DELIVERY_TP)).toBeUndefined()
    wrapper.unmount()
  })

  it('saves parcel destinations 3+2+5 on one line', async () => {
    const wrapper = await mountNewOrder()
    await fieldByLabel(wrapper, LABEL_CUSTOMER)?.find('select').setValue('C001')
    await fieldByLabel(wrapper, LABEL_QTY)?.find('input').setValue('10')
    await selectParcel(wrapper)
    await wrapper.find('.dest-summary').trigger('click')
    await fillOpenDest(wrapper, {
      qty: '3',
      name: '이문자',
      tel: '010-1111-0001',
      addr: '경기 하남시 A',
    })
    await wrapper.find('.add-dest-btn').trigger('click')
    await fillOpenDest(wrapper, {
      qty: '2',
      name: '김수령',
      tel: '010-1111-0002',
      addr: '경기 하남시 B',
    })
    await wrapper.find('.add-dest-btn').trigger('click')
    await fillOpenDest(wrapper, {
      qty: '5',
      name: '박수령',
      tel: '010-1111-0003',
      addr: '경기 하남시 C',
    })
    await clickSave(wrapper)
    expect(createOrder).toHaveBeenCalled()
    const payload = vi.mocked(createOrder).mock.calls.at(-1)?.[1] as {
      lines: { qty: number; deliveries: { qty: number }[] }[]
    }
    expect(payload.lines).toHaveLength(1)
    expect(payload.lines[0].qty).toBe(10)
    expect(payload.lines[0].deliveries.map((d) => d.qty)).toEqual([3, 2, 5])
    wrapper.unmount()
  })

  it('blocks parcel save when dest qty sum is 8 or 12', async () => {
    const wrapper = await mountNewOrder()
    await fieldByLabel(wrapper, LABEL_CUSTOMER)?.find('select').setValue('C001')
    await fieldByLabel(wrapper, LABEL_QTY)?.find('input').setValue('10')
    await selectParcel(wrapper)
    await wrapper.find('.dest-summary').trigger('click')
    await fillOpenDest(wrapper, {
      qty: '8',
      name: '이문자',
      tel: '010-1111-0001',
      addr: '경기 하남시 A',
    })
    await clickSave(wrapper)
    expect(wrapper.text()).toContain(MSG_PARCEL_QTY_MISMATCH)
    expect(createOrder).not.toHaveBeenCalled()
    await fillOpenDest(wrapper, {
      qty: '12',
      name: '이문자',
      tel: '010-1111-0001',
      addr: '경기 하남시 A',
    })
    await clickSave(wrapper)
    expect(wrapper.text()).toContain(MSG_PARCEL_QTY_MISMATCH)
    expect(createOrder).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('recalculates alloc after deleting a destination', async () => {
    const wrapper = await mountNewOrder()
    await fieldByLabel(wrapper, LABEL_QTY)?.find('input').setValue('10')
    await selectParcel(wrapper)
    expect(wrapper.text()).toContain(LABEL_ALLOC)
    expect(wrapper.text()).toContain(LABEL_UNASSIGNED)
    await wrapper.find('.dest-summary').trigger('click')
    await fillOpenDest(wrapper, {
      qty: '4',
      name: '이문자',
      tel: '010-1111-0001',
      addr: '경기 하남시 A',
    })
    await wrapper.find('.add-dest-btn').trigger('click')
    await fillOpenDest(wrapper, {
      qty: '3',
      name: '김수령',
      tel: '010-1111-0002',
      addr: '경기 하남시 B',
    })
    expect(wrapper.text()).toContain(`${LABEL_ALLOC} 7 / 10`)
    await wrapper.find('.line-head__del').trigger('click')
    expect(wrapper.findAll('.dest-card')).toHaveLength(1)
    expect(wrapper.text()).toContain(`${LABEL_ALLOC} 4 / 10`)
    wrapper.unmount()
  })

  it('keeps destinations independent per product', async () => {
    const wrapper = await mountNewOrder()
    await fieldByLabel(wrapper, LABEL_CUSTOMER)?.find('select').setValue('C001')
    await fieldByLabel(wrapper, LABEL_QTY)?.find('input').setValue('3')
    await selectParcel(wrapper)
    await wrapper.find('.dest-summary').trigger('click')
    await fillOpenDest(wrapper, {
      qty: '3',
      name: '상품1수령',
      tel: '010-2000-0001',
      addr: '서울 1',
    })
    await wrapper.find('.add-line-btn').trigger('click')
    await fieldByLabel(wrapper, LABEL_QTY)?.find('input').setValue('5')
    await selectParcel(wrapper)
    await wrapper.find('.dest-summary').trigger('click')
    await fillOpenDest(wrapper, {
      qty: '2',
      name: '상품2수령A',
      tel: '010-2000-0002',
      addr: '서울 2A',
    })
    await wrapper.find('.add-dest-btn').trigger('click')
    await fillOpenDest(wrapper, {
      qty: '3',
      name: '상품2수령B',
      tel: '010-2000-0003',
      addr: '서울 2B',
    })
    await clickSave(wrapper)
    const payload = vi.mocked(createOrder).mock.calls.at(-1)?.[1] as {
      lines: { qty: number; deliveries: { qty: number; rcv_name: string }[] }[]
    }
    expect(payload.lines).toHaveLength(2)
    expect(payload.lines[0].deliveries.map((d) => d.rcv_name)).toEqual(['상품1수령'])
    expect(payload.lines[1].deliveries.map((d) => d.qty)).toEqual([2, 3])
    wrapper.unmount()
  })

  it('saves ten parcel destinations of qty 1', async () => {
    const wrapper = await mountNewOrder()
    await fieldByLabel(wrapper, LABEL_CUSTOMER)?.find('select').setValue('C001')
    await fieldByLabel(wrapper, LABEL_QTY)?.find('input').setValue('10')
    await selectParcel(wrapper)
    await wrapper.find('.dest-summary').trigger('click')
    for (let i = 1; i <= 10; i += 1) {
      if (i > 1) await wrapper.find('.add-dest-btn').trigger('click')
      await fillOpenDest(wrapper, {
        qty: '1',
        name: `수령${i}`,
        tel: `010-3000-${String(i).padStart(4, '0')}`,
        addr: `서울 ${i}`,
      })
    }
    await clickSave(wrapper)
    const payload = vi.mocked(createOrder).mock.calls.at(-1)?.[1] as {
      lines: { deliveries: { qty: number }[] }[]
    }
    expect(payload.lines[0].deliveries).toHaveLength(10)
    expect(payload.lines[0].deliveries.every((d) => d.qty === 1)).toBe(true)
    wrapper.unmount()
  })

  it('preloads existing order into the shared form', async () => {
    const wrapper = await mountEditOrder()
    expect(wrapper.text()).toContain(LABEL_EDIT_ORDER)
    expect(fetchOrder).toHaveBeenCalled()
    const customer = fieldByLabel(wrapper, LABEL_CUSTOMER)?.find('select').element as HTMLSelectElement
    expect(customer.value).toBe('C001')
    expect(fieldByLabel(wrapper, LABEL_QTY)?.find('input').element).toMatchObject({ value: '10' })
    expect(fieldByLabel(wrapper, LABEL_WEIGHT)?.find('select').element).toMatchObject({
      value: 'SZ010200',
    })
    await wrapper.find('.ship-head').trigger('click')
    expect(wrapper.text()).toContain('이문자')
    expect(wrapper.findAll('.dest-card')).toHaveLength(2)
    wrapper.unmount()
  })

  it('saves edit through updateOrder and keeps dest qty sum', async () => {
    const wrapper = await mountEditOrder()
    await fieldByLabel(wrapper, LABEL_QTY)?.find('input').setValue('12')
    await wrapper.find('.ship-head').trigger('click')
    await wrapper.find('.dest-summary').trigger('click')
    await fieldByLabel(wrapper, LABEL_DEST_QTY)?.find('input').setValue('5')
    await wrapper.findAll('.dest-summary').at(-1)?.trigger('click')
    const destQtyFields = wrapper.findAll('.ods-form-field').filter((f) => {
      const lab = f.find('.ods-form-field__label-text')
      return lab.exists() && lab.text() === LABEL_DEST_QTY
    })
    await destQtyFields.at(-1)?.find('input').setValue('7')
    await clickSave(wrapper)
    expect(createOrder).not.toHaveBeenCalled()
    expect(updateOrder).toHaveBeenCalled()
    const payload = vi.mocked(updateOrder).mock.calls.at(-1)?.[2] as {
      lines: { qty: number; deliveries: { qty: number }[] }[]
    }
    expect(payload.lines[0].qty).toBe(12)
    expect(payload.lines[0].deliveries.map((d) => d.qty)).toEqual([5, 7])
    wrapper.unmount()
  })
})
