import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import SalesPreviewView from '@/features/sales/SalesPreviewView.vue'
import { useSalesPrefillStore } from '@/shared/stores/salesPrefill'
import { stockSaleSpecKey } from '@/features/sales/shipConfirmModel'
import { DELIVERY_TP_PARCEL, DELIVERY_TP_VISIT } from '@/features/orders/ordersConstants'
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

vi.mock('@/shared/stores/app', async () => {
  const { ref } = await import('vue')
  return {
    useAppStore: () => ({
      farmCd: ref('OR001'),
      farm: ref({
        farm_cd: 'OR001',
        farm_nm: '테스트농장',
        owner_nm: null,
        address: '경기도 화성시 테스트로 1',
        lat: null,
        lon: null,
        nx: null,
        ny: null,
        reg_dt: null,
      }),
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

async function mountPreview() {
  const r = router()
  await r.push('/orders/sales-preview')
  await r.isReady()
  const wrapper = mount(SalesPreviewView, mountOpts(r))
  await flushPromises()
  return { wrapper, r }
}

describe('SalesPreviewView 2B', () => {
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

  it('T1~T2 모바일 프레임 class · footer fixed 구조', async () => {
    const store = useSalesPrefillStore()
    store.addStockLine(stock(), 1)
    const { wrapper } = await mountPreview()
    expect(wrapper.find('[data-testid="sales-preview-page"]').classes()).toContain('sales-preview-frame')
    const frame = wrapper.find('[data-testid="sales-preview-frame"]')
    expect(frame.classes()).toContain('ods-page-content')
    expect(frame.classes()).toContain('content')
    const footer = wrapper.find('[data-testid="sales-preview-footer"]')
    expect(footer.exists()).toBe(true)
    expect(footer.classes()).toContain('footer')
    wrapper.unmount()
  })

  it('미리보기 품목명은 품종부터 표기 · 공통 formatOrderLineSpec 유지', async () => {
    const store = useSalesPrefillStore()
    store.addStockLine(stock({ variety_nm: '신고', size_nm: '2다이전', weight: 5, grade_nm: '상' }), 1)
    const { wrapper } = await mountPreview()
    const title = wrapper.find('.line__title').text()
    expect(title).toContain('신고')
    expect(title).toContain('5kg')
    expect(title).toContain('상')
    expect(title).not.toMatch(/^배 ·/)
    expect(wrapper.find('.header-row').exists()).toBe(true)
    expect(wrapper.text()).toMatch(/배송/)
    wrapper.unmount()
  })

  it('T1~T2 품목별 카드 반복 없음 · divider 리스트 · 섹션 card 허용', async () => {
    const store = useSalesPrefillStore()
    store.addStockLine(stock(), 2)
    const { wrapper } = await mountPreview()
    expect(wrapper.find('[data-testid="sales-preview-lines"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-testid="sales-preview-line"]')).toHaveLength(1)
    // 섹션용 OdsCard는 허용, 품목 li에 card 클래스 반복 금지
    expect(wrapper.find('[data-testid="sales-preview-header"]').classes().join(' ')).toMatch(/preview-card/)
    expect(wrapper.find('[data-testid="sales-preview-lines"]').classes().join(' ')).toMatch(/preview-card/)
    expect(wrapper.find('.line').classes().join(' ')).not.toMatch(/card/i)
    expect(wrapper.text()).toContain('판매 품목')
    expect(wrapper.text()).toContain('1건')
    expect(wrapper.text()).not.toContain('2026-08-19')
    expect(wrapper.text()).not.toContain('포장')
    expect(wrapper.text()).not.toContain('저장일')
    wrapper.unmount()
  })

  it('T3~T4 단가 변경 → Store·총액 즉시 동기 · 수량 stepper 없음', async () => {
    const store = useSalesPrefillStore()
    store.addStockLine(stock({ available_qty: 10 }), 2)
    store.updateShipLine(0, { unit_price: 1000 })
    const { wrapper } = await mountPreview()
    expect(wrapper.find('[data-testid="sales-preview-qty"]').text()).toBe('2')
    expect(wrapper.find('.qty__btn').exists()).toBe(false)
    expect(wrapper.find('[data-testid="sales-preview-subtotal"]').exists()).toBe(false)

    const priceInput = wrapper.find('[data-testid="sales-preview-price"]')
    await new DOMWrapper(priceInput.element).setValue('5000')
    await flushPromises()
    expect(store.shipLines[0].unit_price).toBe(5000)
    expect(store.shipLines[0].qty).toBe(2)
    expect(wrapper.find('[data-testid="sales-preview-footer"]').text()).toContain('10,000')
    wrapper.unmount()
  })

  it('수정 아이콘 → 재고 탭 · prefill(동일 규격 행) 유지', async () => {
    const store = useSalesPrefillStore()
    const row = stock({ available_qty: 10 })
    store.addStockLine(row, 3)
    store.setCustomer('C1', '홍길동')
    store.updateShipLine(0, { unit_price: 2000 })
    const { wrapper, r } = await mountPreview()
    await wrapper.find('[data-testid="sales-preview-edit"]').trigger('click')
    await flushPromises()
    expect(r.currentRoute.value.name).toBe('orders')
    expect(r.currentRoute.value.query.tab).toBe('stock')
    expect(store.source).toBe('STOCK')
    expect(store.shipLines).toHaveLength(1)
    expect(store.shipLines[0].qty).toBe(3)
    expect(store.shipLines[0].unit_price).toBe(2000)
    expect(store.hasStockLine(stockSaleSpecKey(row))).toBe(true)
    store.updateStockLineQty(stockSaleSpecKey(row), 5)
    expect(store.shipLines).toHaveLength(1)
    expect(store.shipLines[0].qty).toBe(5)
    wrapper.unmount()
  })

  it('T5 품목 삭제 → Store 제거', async () => {
    const store = useSalesPrefillStore()
    store.addStockLine(stock(), 1)
    store.addStockLine(stock({ grade_cd: 'GR010200', grade_nm: '상', available_qty: 5 }), 1)
    const { wrapper } = await mountPreview()
    expect(wrapper.findAll('[data-testid="sales-preview-line"]')).toHaveLength(2)
    await wrapper.findAll('[data-testid="sales-preview-remove"]')[1].trigger('click')
    await flushPromises()
    expect(store.shipLines).toHaveLength(1)
    expect(store.shipLines[0].grade_cd).toBe('GR010100')
    wrapper.unmount()
  })

  it('T6 마지막 품목 삭제 → STOCK 세션/header 유지 · 판매진행 disabled', async () => {
    const store = useSalesPrefillStore()
    store.addStockLine(stock(), 2)
    store.setCustomer('C1', '홍길동')
    store.setDelivery({ dlvryTp: DELIVERY_TP_PARCEL, shipFee: 4000, rcvName: '홍', rcvTel: '010', rcvAddr: '서울' })
    const { wrapper } = await mountPreview()
    await wrapper.find('[data-testid="sales-preview-remove"]').trigger('click')
    await flushPromises()
    expect(store.source).toBe('STOCK')
    expect(store.shipLines).toHaveLength(0)
    expect(store.custmId).toBe('C1')
    expect(store.dlvryTp).toBe(DELIVERY_TP_PARCEL)
    expect(store.shipFee).toBe(4000)
    expect(wrapper.text()).toContain('판매 품목이 없습니다')
    expect((wrapper.find('[data-testid="sales-preview-submit"]').element as HTMLButtonElement).disabled).toBe(true)
    wrapper.unmount()
  })

  it('T7~T10 +품목추가 왕복 · 수량복원 · 중복 line 없음', async () => {
    const store = useSalesPrefillStore()
    const a = stock({ available_qty: 10 })
    const b = stock({ grade_cd: 'GR010200', grade_nm: '상', available_qty: 8 })
    const c = stock({ weight: 7.5, size_cd: 'FR020102', size_nm: '30과', available_qty: 5 })
    store.addStockLine(a, 3)
    store.addStockLine(b, 2)
    store.setCustomer('C1', '홍길동')
    store.setDelivery({ dlvryTp: DELIVERY_TP_VISIT, shipFee: 0 })

    const { wrapper, r } = await mountPreview()
    store.updateShipLine(0, { qty: 5 })
    expect(store.shipLines[0].qty).toBe(5)
    store.removeShipLine(1)
    expect(store.shipLines).toHaveLength(1)

    await wrapper.find('[data-testid="sales-preview-add"]').trigger('click')
    await flushPromises()
    expect(r.currentRoute.value.name).toBe('orders')
    expect(r.currentRoute.value.query.tab).toBe('stock')
    expect(store.source).toBe('STOCK')
    expect(store.custmId).toBe('C1')
    expect(store.shipLines[0].qty).toBe(5)
    expect(store.hasStockLine(stockSaleSpecKey(a))).toBe(true)
    expect(store.hasStockLine(stockSaleSpecKey(b))).toBe(false)

    store.addStockLine(c, 1)
    expect(store.shipLines).toHaveLength(2)
    expect(store.shipLines.map((ln) => stockSaleSpecKey(ln))).toEqual([
      stockSaleSpecKey(a),
      stockSaleSpecKey(c),
    ])
    wrapper.unmount()
  })

  it('T11 판매 준비 취소 confirm OK → clear + 재고 복귀', async () => {
    const store = useSalesPrefillStore()
    store.addStockLine(stock(), 2)
    store.setCustomer('C1', '홍길동')
    store.setDelivery({ shipFee: 3000, dlvryTp: DELIVERY_TP_PARCEL, rcvName: 'A', rcvTel: '1', rcvAddr: 'B' })
    const { wrapper, r } = await mountPreview()
    await wrapper.find('[data-testid="sales-preview-cancel-prep"]').trigger('click')
    await flushPromises()
    expect(window.confirm).toHaveBeenCalledWith('진행 중인 판매 준비를 취소하시겠습니까?')
    expect(store.source).toBeNull()
    expect(store.shipLines).toHaveLength(0)
    expect(store.custmId).toBeNull()
    expect(store.shipFee).toBe(0)
    expect(r.currentRoute.value.name).toBe('orders')
    expect(r.currentRoute.value.query.tab).toBe('stock')
    wrapper.unmount()
  })

  it('T12 판매 준비 취소 confirm cancel → 데이터 유지', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const store = useSalesPrefillStore()
    store.addStockLine(stock(), 2)
    store.setCustomer('C1', '홍길동')
    const { wrapper } = await mountPreview()
    await wrapper.find('[data-testid="sales-preview-cancel-prep"]').trigger('click')
    await flushPromises()
    expect(store.shipLines).toHaveLength(1)
    expect(store.custmId).toBe('C1')
    expect(store.source).toBe('STOCK')
    wrapper.unmount()
  })

  it('T13~T15 판매 confirm 취소/실패/성공', async () => {
    const store = useSalesPrefillStore()
    store.addStockLine(stock(), 2)
    store.setCustomer('C1', '홍길동')
    store.updateShipLine(0, { qty: 2, unit_price: 1000 })

    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const { wrapper } = await mountPreview()
    await wrapper.find('[data-testid="sales-preview-submit"]').trigger('click')
    await flushPromises()
    expect(confirmShipment).not.toHaveBeenCalled()
    expect(store.shipLines).toHaveLength(1)

    confirmSpy.mockReturnValue(true)
    confirmShipment.mockRejectedValueOnce(new Error('boom'))
    await wrapper.find('[data-testid="sales-preview-submit"]').trigger('click')
    await flushPromises()
    expect(store.shipLines).toHaveLength(1)
    expect(store.custmId).toBe('C1')

    confirmShipment.mockResolvedValueOnce({
      ok: true,
      sales_no: '20260820-002',
      sales_status: 'CONFIRMED',
      ship_mode: 'DIRECT',
      order_no: null,
      details: [],
      order_status: null,
      remaining_order_qty: null,
      remaining_order: [],
    })
    await wrapper.find('[data-testid="sales-preview-submit"]').trigger('click')
    await flushPromises()
    expect(confirmShipment).toHaveBeenCalled()
    expect(store.shipLines).toHaveLength(0)
    expect(store.source).toBeNull()
    wrapper.unmount()
  })

  it('T16 합계 = Σ(qty×unit_price) + 배송비', async () => {
    const store = useSalesPrefillStore()
    store.addStockLine(stock(), 3)
    store.addStockLine(stock({ grade_cd: 'GR010200', grade_nm: '상', available_qty: 5 }), 2)
    store.updateShipLine(0, { unit_price: 50000 })
    store.updateShipLine(1, { unit_price: 65000 })
    store.setDelivery({ shipFee: 4000 })
    store.setCustomer('C1', '홍길동')
    const { wrapper } = await mountPreview()
    const foot = wrapper.find('[data-testid="sales-preview-footer"]').text()
    expect(foot).toContain('2품목 · 5박스')
    expect(foot).toContain('280,000') // 150000+130000
    expect(foot).toContain('284,000') // +4000
    wrapper.unmount()
  })

  it('T17~T18 overflow 클래스 · storage_dt 미노출', async () => {
    const store = useSalesPrefillStore()
    store.addStockLine(stock({ storage_dt: '2026-01-01' }), 1)
    store.addStockLine(
      stock({ storage_dt: '2026-12-31', grade_cd: 'GR010200', grade_nm: '상', available_qty: 3 }),
      1,
    )
    const { wrapper } = await mountPreview()
    expect(wrapper.find('.page').classes()).toContain('page')
    expect(wrapper.html()).not.toContain('2026-01-01')
    expect(wrapper.html()).not.toContain('2026-12-31')
    expect(wrapper.text()).not.toMatch(/LOT|포장일|저장일/)
    wrapper.unmount()
  })

  it('T1~T6 compact 표형 1행 · 수량 stepper/소계 없음', async () => {
    const store = useSalesPrefillStore()
    store.addStockLine(stock(), 3)
    store.updateShipLine(0, { unit_price: 50000 })
    const { wrapper } = await mountPreview()
    const line = wrapper.find('[data-testid="sales-preview-line"]')
    expect(line.find('.line__row').exists()).toBe(true)
    expect(line.find('.line__title').exists()).toBe(true)
    expect(line.find('[data-testid="sales-preview-qty"]').text()).toBe('3')
    expect(line.find('[data-testid="sales-preview-price"]').exists()).toBe(true)
    expect((line.find('[data-testid="sales-preview-price"]').element as HTMLInputElement).value).toBe(
      '50,000',
    )
    expect(line.find('[data-testid="sales-preview-edit"]').exists()).toBe(true)
    expect(line.find('[data-testid="sales-preview-remove"]').exists()).toBe(true)
    expect(line.find('.qty__btn').exists()).toBe(false)
    expect(line.find('[data-testid="sales-preview-subtotal"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('품목')
    expect(wrapper.text()).toContain('수량')
    expect(wrapper.text()).toContain('단가')
    wrapper.unmount()
  })

  it('T7~T11 배송비 clamp · 음수 방어 · 총액 미감소', async () => {
    const store = useSalesPrefillStore()
    store.addStockLine(stock(), 2)
    store.updateShipLine(0, { unit_price: 50000 })
    store.setCustomer('C1', '홍길동')
    const { wrapper } = await mountPreview()
    const fee = wrapper.find('[data-testid="sales-preview-ship-fee"]')

    await new DOMWrapper(fee.element).setValue('4000')
    await flushPromises()
    expect(store.shipFee).toBe(4000)
    expect(wrapper.find('[data-testid="sales-preview-footer"]').text()).toContain('104,000')

    await new DOMWrapper(fee.element).setValue('0')
    await flushPromises()
    expect(store.shipFee).toBe(0)

    await new DOMWrapper(fee.element).setValue('-4000')
    await flushPromises()
    expect(store.shipFee).toBe(0)
    expect(Number(store.shipFee)).toBeGreaterThanOrEqual(0)
    expect(wrapper.find('[data-testid="sales-preview-footer"]').text()).toContain('100,000')
    expect(wrapper.find('[data-testid="sales-preview-footer"]').text()).not.toContain('96,000')

    // submit 방어: Store에 음수가 직접 들어간 경우
    store.setDelivery({ shipFee: -1 })
    await flushPromises()
    expect(Number(store.shipFee)).toBeLessThan(0)
    expect((wrapper.find('[data-testid="sales-preview-submit"]').element as HTMLButtonElement).disabled).toBe(true)
    await wrapper.find('[data-testid="sales-preview-submit"]').trigger('click')
    await flushPromises()
    expect(confirmShipment).not.toHaveBeenCalled()
    // 합계는 safeShipFee(0) 기준 — 음수 배송비로 총액 감소 없음
    expect(wrapper.find('[data-testid="sales-preview-footer"]').text()).toContain('100,000')
    wrapper.unmount()
  })

  it('P11 택배 선택 시 공통 수령폼 없음 · 품목별 배송상태(2C)', async () => {
    const store = useSalesPrefillStore()
    store.addStockLine(stock(), 3)
    store.setDelivery({ dlvryTp: DELIVERY_TP_PARCEL })
    const { wrapper } = await mountPreview()
    expect(wrapper.find('[data-testid="sales-preview-addr"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="sales-preview-delivery-status"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('배송 0/3박스')
    expect(wrapper.find('[data-testid="sales-preview-ship-fee"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="sales-preview-ship-fee-sum"]').exists()).toBe(true)
    store.setDelivery({ dlvryTp: DELIVERY_TP_VISIT })
    await flushPromises()
    expect(wrapper.find('[data-testid="sales-preview-delivery-status"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="sales-preview-ship-fee"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('2C 배송지 sheet · 지정합=판매수량 → 진행 가능 · 미지정 disabled', async () => {
    const store = useSalesPrefillStore()
    store.addStockLine(stock({ available_qty: 10 }), 3)
    store.updateShipLine(0, { unit_price: 1000 })
    store.setCustomer('C1', '홍길동')
    store.setDelivery({ dlvryTp: DELIVERY_TP_PARCEL })
    store.setSender({ name: '삼육농원', tel: '010-0000-0000', addr: '과수원주소' })
    const r = router()
    await r.push('/orders/sales-preview')
    await r.isReady()
    const wrapper = mount(SalesPreviewView, {
      attachTo: document.body,
      ...mountOpts(r),
    })
    await flushPromises()
    expect((wrapper.find('[data-testid="sales-preview-submit"]').element as HTMLButtonElement).disabled).toBe(true)

    await wrapper.find('[data-testid="sales-preview-dest-open"]').trigger('click')
    await flushPromises()
    const sheet = document.querySelector('[data-testid="sales-preview-dest-sheet"]')
    expect(sheet).toBeTruthy()
    const addBtn = sheet!.querySelector('[data-testid="sales-preview-dest-add"]') as HTMLButtonElement
    addBtn.click()
    await flushPromises()
    const row = sheet!.querySelector('[data-testid="sales-preview-dest-row"]')!
    const inputs = row.querySelectorAll('input')
    /* 수령인 · 연락처 · 수량 · 배송비 · 주소 · 배송메모 */
    await new DOMWrapper(inputs[0]).setValue('홍길동')
    await new DOMWrapper(inputs[1]).setValue('010')
    await new DOMWrapper(inputs[2]).setValue('3')
    await new DOMWrapper(inputs[3]).setValue('4000')
    await new DOMWrapper(inputs[4]).setValue('서울')
    ;(sheet!.querySelector('[data-testid="sales-preview-dest-save"]') as HTMLButtonElement).click()
    await flushPromises()
    expect(sheet!.querySelector('[data-testid="sales-preview-dest-summary-row"]')).toBeTruthy()
    expect(sheet!.querySelector('[data-testid="sales-preview-dest-row"]')).toBeFalsy()
    ;(sheet!.querySelector('[data-testid="sales-preview-dest-done"]') as HTMLButtonElement).click()
    await flushPromises()
    expect(store.shipLines[0].delivery_allocations).toHaveLength(1)
    expect(store.shipLines[0].delivery_allocations?.[0].qty).toBe(3)
    expect(wrapper.text()).toContain('배송지 등록 완료')
    expect(wrapper.find('[data-testid="sales-preview-ship-fee-sum"]').text()).toContain('4,000')
    expect((wrapper.find('[data-testid="sales-preview-submit"]').element as HTMLButtonElement).disabled).toBe(false)

    store.updateShipLine(0, { qty: 2 })
    await flushPromises()
    expect(store.shipLines[0].delivery_allocations?.[0].qty).toBe(3)
    expect(wrapper.text()).toContain('초과')
    expect((wrapper.find('[data-testid="sales-preview-submit"]').element as HTMLButtonElement).disabled).toBe(true)

    /* 재고 updateStockLineQty도 allocation 자동 축소 없음 */
    store.updateStockLineQty(stockSaleSpecKey(stock()), 7)
    await flushPromises()
    expect(store.shipLines[0].delivery_allocations?.[0].qty).toBe(3)
    expect(store.shipLines[0].qty).toBe(7)
    expect(wrapper.text()).toContain('미지정')
    expect((wrapper.find('[data-testid="sales-preview-submit"]').element as HTMLButtonElement).disabled).toBe(true)
    wrapper.unmount()
  })

  it('2C nested payload · confirm 취소 시 allocations 유지', async () => {
    const store = useSalesPrefillStore()
    store.addStockLine(stock(), 2)
    store.updateShipLine(0, { unit_price: 1000 })
    store.setCustomer('C1', '홍길동')
    store.setDelivery({ dlvryTp: DELIVERY_TP_PARCEL })
    store.setSender({ name: '삼육농원', tel: '010-0000-0000', addr: '과수원주소' })
    store.setShipLineDeliveries(0, [
      {
        draft_id: 'd1',
        qty: 1,
        rcv_name: 'A',
        rcv_tel: '1',
        rcv_addr: 'addr1',
        dlvry_msg: '',
        ship_fee: 1000,
      },
      {
        draft_id: 'd2',
        qty: 1,
        rcv_name: 'B',
        rcv_tel: '2',
        rcv_addr: 'addr2',
        dlvry_msg: '문앞',
        ship_fee: 2000,
      },
    ])
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const { wrapper } = await mountPreview()
    await wrapper.find('[data-testid="sales-preview-submit"]').trigger('click')
    await flushPromises()
    expect(confirmShipment).not.toHaveBeenCalled()
    expect(store.shipLines[0].delivery_allocations).toHaveLength(2)

    vi.spyOn(window, 'confirm').mockReturnValue(true)
    await wrapper.find('[data-testid="sales-preview-submit"]').trigger('click')
    await flushPromises()
    const body = confirmShipment.mock.calls[0][1] as {
      ship_fee: number
      snd_name: string
      lines: { delivery_allocations: unknown[] }[]
    }
    expect(body.ship_fee).toBe(3000)
    expect(body.snd_name).toBe('삼육농원')
    expect(body.lines[0].delivery_allocations).toHaveLength(2)
    expect(store.shipLines).toHaveLength(0)
    wrapper.unmount()
  })

  it('U1~U2 Sheet 단위는 현재 destEditIdx 품목 기준', async () => {
    const store = useSalesPrefillStore()
    store.addStockLine(stock({ item_cd: 'FR010100', item_nm: '배', available_qty: 10 }), 2)
    store.addStockLine(
      stock({
        item_cd: 'FR010300',
        item_nm: '배즙',
        variety_cd: 'FR010301',
        variety_nm: '배즙',
        grade_cd: 'GR010100',
        size_cd: 'SZ010000',
        weight: 0,
        available_qty: 5,
      }),
      1,
    )
    store.setDelivery({ dlvryTp: DELIVERY_TP_PARCEL })
    const r = router()
    await r.push('/orders/sales-preview')
    await r.isReady()
    const wrapper = mount(SalesPreviewView, {
      attachTo: document.body,
      ...mountOpts(r),
    })
    await flushPromises()

    const opens = wrapper.findAll('[data-testid="sales-preview-dest-open"]')
    await opens[0].trigger('click')
    await flushPromises()
    let sheet = document.querySelector('[data-testid="sales-preview-dest-sheet"]')
    expect(sheet?.textContent || '').toMatch(/주문량\s*:\s*2박스/)
    expect(sheet?.textContent || '').toMatch(/미지정\s*:\s*2박스/)
    ;(sheet!.querySelector('[aria-label="닫기"]') as HTMLButtonElement).click()
    await flushPromises()

    await opens[1].trigger('click')
    await flushPromises()
    sheet = document.querySelector('[data-testid="sales-preview-dest-sheet"]')
    expect(sheet?.textContent || '').toMatch(/주문량\s*:\s*1통/)
    expect(sheet?.textContent || '').not.toMatch(/주문량\s*:\s*1박스/)
    wrapper.unmount()
  })

  it('공통 배송메모 — 주문자 선택 시 신규 배송지에 반영', async () => {
    const store = useSalesPrefillStore()
    store.addStockLine(stock({ available_qty: 10 }), 2)
    store.updateShipLine(0, { unit_price: 1000 })
    store.setCustomer('C1', '홍길동')
    store.setDelivery({ dlvryTp: DELIVERY_TP_PARCEL })
    const r = router()
    await r.push('/orders/sales-preview')
    await r.isReady()
    const wrapper = mount(SalesPreviewView, {
      attachTo: document.body,
      ...mountOpts(r),
    })
    await flushPromises()
    await wrapper.find('[data-testid="sales-preview-dest-open"]').trigger('click')
    await flushPromises()
    const sheet = document.querySelector('[data-testid="sales-preview-dest-sheet"]')!
    expect(sheet.querySelector('[data-testid="sales-preview-dest-common-memo"]')).toBeTruthy()
    const mode = sheet.querySelector(
      '[data-testid="sales-preview-dest-common-mode"]',
    ) as HTMLSelectElement
    mode.value = 'orderer'
    mode.dispatchEvent(new Event('change'))
    await flushPromises()
    const commonInput = sheet.querySelector(
      '[data-testid="sales-preview-dest-common-input"]',
    ) as HTMLInputElement
    expect(commonInput.value).toBe('홍길동')
    await new DOMWrapper(commonInput).setValue('문앞에 두세요')
    await flushPromises()
    expect(mode.value).toBe('custom')
    ;(sheet.querySelector('[data-testid="sales-preview-dest-add"]') as HTMLButtonElement).click()
    await flushPromises()
    const row = sheet.querySelector('[data-testid="sales-preview-dest-row"]')!
    const inputs = row.querySelectorAll('input')
    expect((inputs[5] as HTMLInputElement).value).toBe('문앞에 두세요')
    wrapper.unmount()
  })

  it('주문량 초과 — 수량 미상승 · tip · 배송지 추가 차단', async () => {
    const store = useSalesPrefillStore()
    store.addStockLine(stock({ available_qty: 10 }), 5)
    store.updateShipLine(0, { unit_price: 1000 })
    store.setCustomer('C1', '홍길동')
    store.setDelivery({ dlvryTp: DELIVERY_TP_PARCEL })
    const r = router()
    await r.push('/orders/sales-preview')
    await r.isReady()
    const wrapper = mount(SalesPreviewView, {
      attachTo: document.body,
      ...mountOpts(r),
    })
    await flushPromises()
    await wrapper.find('[data-testid="sales-preview-dest-open"]').trigger('click')
    await flushPromises()
    const sheet = document.querySelector('[data-testid="sales-preview-dest-sheet"]')!

    ;(sheet.querySelector('[data-testid="sales-preview-dest-add"]') as HTMLButtonElement).click()
    await flushPromises()
    const row = sheet.querySelector('[data-testid="sales-preview-dest-row"]')!
    const inputs = row.querySelectorAll('input')
    await new DOMWrapper(inputs[0]).setValue('A')
    await new DOMWrapper(inputs[1]).setValue('010')
    await new DOMWrapper(sheet.querySelector('[data-testid="sales-preview-dest-qty"]')!).setValue(
      '9',
    )
    await flushPromises()
    expect(
      (sheet.querySelector('[data-testid="sales-preview-dest-qty"]') as HTMLInputElement).value,
    ).toBe('1')
    expect(document.querySelector('[data-testid="sales-preview-dest-tip"]')?.textContent || '').toContain(
      '주문량을 초과',
    )
    expect(sheet.querySelector('[data-testid="sales-preview-dest-err"]')).toBeFalsy()

    await new DOMWrapper(
      sheet.querySelector('[data-testid="sales-preview-dest-qty"]')!,
    ).setValue('5')
    await flushPromises()
    const inputsAfter = sheet
      .querySelector('[data-testid="sales-preview-dest-row"]')!
      .querySelectorAll('input')
    await new DOMWrapper(inputsAfter[4]).setValue('서울')
    ;(sheet.querySelector('[data-testid="sales-preview-dest-save"]') as HTMLButtonElement).click()
    await flushPromises()

    ;(sheet.querySelector('[data-testid="sales-preview-dest-add"]') as HTMLButtonElement).click()
    await flushPromises()
    expect(sheet.querySelector('[data-testid="sales-preview-dest-row"]')).toBeFalsy()
    expect(document.querySelector('[data-testid="sales-preview-dest-tip"]')?.textContent || '').toContain(
      '모두 지정',
    )
    expect(sheet.querySelector('[data-testid="sales-preview-dest-err"]')).toBeFalsy()
    wrapper.unmount()
  })

  it('P7 동일 판매규격 storage_dt 달라도 1 line(회귀)', () => {
    const store = useSalesPrefillStore()
    store.addStockLine(stock({ storage_dt: '2026-08-01', available_qty: 10 }), 4)
    store.updateShipLine(0, { unit_price: 1000 })
    store.addStockLine(stock({ storage_dt: '2026-08-20', available_qty: 3 }), 1)
    expect(store.shipLines).toHaveLength(1)
    expect(store.shipLines[0].qty).toBe(1)
    expect(store.shipLines[0].unit_price).toBe(1000)
  })

  it('보내는 사람 sheet · 과수원주소 · prefill 유지 · confirm snd_*', async () => {
    const store = useSalesPrefillStore()
    store.addStockLine(stock({ available_qty: 10 }), 2)
    store.updateShipLine(0, { unit_price: 1000 })
    store.setCustomer('C1', '홍길동')
    store.setDelivery({ dlvryTp: DELIVERY_TP_PARCEL })
    store.setShipLineDeliveries(0, [
      {
        draft_id: 'd1',
        qty: 2,
        rcv_name: '김수령',
        rcv_tel: '010-1111-2222',
        rcv_addr: '서울',
        dlvry_msg: '',
        ship_fee: 3000,
      },
    ])
    const r = router()
    await r.push('/orders/sales-preview')
    await r.isReady()
    const wrapper = mount(SalesPreviewView, {
      attachTo: document.body,
      ...mountOpts(r),
    })
    await flushPromises()

    expect(wrapper.find('[data-testid="sales-preview-sender-bar"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="sales-preview-submit"]').attributes('disabled')).toBeDefined()
    expect(wrapper.find('[data-testid="sales-preview-sender"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="sales-preview-sender-setup"]').text()).toContain('설정')
    expect(wrapper.find('[data-testid="sales-preview-sender-summary"]').text()).toContain('미설정')

    await wrapper.find('[data-testid="sales-preview-sender-setup"]').trigger('click')
    await flushPromises()
    const sheet = document.querySelector('[data-testid="sales-preview-sender-sheet"]')!
    expect(sheet).toBeTruthy()
    expect(sheet.textContent || '').toContain('판매 전체 공통 적용')
    expect(sheet.textContent || '').not.toContain('수령 주소')
    expect(
      (sheet.querySelector('[data-testid="sales-preview-sender-addr"]') as HTMLInputElement).value,
    ).toContain('경기도 화성시')

    await new DOMWrapper(
      sheet.querySelector('[data-testid="sales-preview-sender-name"]')!,
    ).setValue('삼육농원')
    await new DOMWrapper(
      sheet.querySelector('[data-testid="sales-preview-sender-tel"]')!,
    ).setValue('01012345678')
    await flushPromises()
    expect(
      (sheet.querySelector('[data-testid="sales-preview-sender-tel"]') as HTMLInputElement).value,
    ).toBe('010-1234-5678')
    ;(sheet.querySelector('[data-testid="sales-preview-sender-apply"]') as HTMLButtonElement).click()
    await flushPromises()

    expect(store.senderName).toBe('삼육농원')
    expect(store.senderTel).toBe('010-1234-5678')
    expect(store.senderAddr).toBe('경기도 화성시 테스트로 1')
    expect(wrapper.find('[data-testid="sales-preview-sender-setup"]').text()).toContain('편집')
    expect(wrapper.find('[data-testid="sales-preview-sender-summary"]').text()).toContain('삼육농원')
    expect(wrapper.find('[data-testid="sales-preview-sender-bar"]').text()).not.toContain('미지정')

    await wrapper.find('[data-testid="sales-preview-submit"]').trigger('click')
    await flushPromises()
    expect(confirmShipment).toHaveBeenCalled()
    const body = confirmShipment.mock.calls[0][1] as Record<string, unknown>
    expect(body.snd_name).toBe('삼육농원')
    expect(body.snd_tel).toBe('010-1234-5678')
    expect(body.snd_addr).toBe('경기도 화성시 테스트로 1')
    expect(body.lines).toBeTruthy()
    wrapper.unmount()
  })

  it('보내는 사람 · 직접입력 · 재고 왕복 유지 · clear', async () => {
    const store = useSalesPrefillStore()
    store.addStockLine(stock(), 1)
    store.setSender({ name: '직접발신', tel: '010-9999-8888', addr: '직접주소 99' })
    store.setDelivery({ dlvryTp: DELIVERY_TP_PARCEL })
    expect(store.senderName).toBe('직접발신')
    store.addStockLine(stock({ available_qty: 5 }), 1)
    expect(store.senderName).toBe('직접발신')
    expect(store.senderAddr).toBe('직접주소 99')
    store.clear()
    expect(store.senderName).toBe('')
    expect(store.senderTel).toBe('')
    expect(store.senderAddr).toBe('')
  })
})
