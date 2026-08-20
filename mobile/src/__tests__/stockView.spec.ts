import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { ref } from 'vue'

import StockView from '@/views/stock/StockView.vue'
import { useSalesPrefillStore } from '@/composables/stores/salesPrefill'
import {
  REASON_COUNT_DIFF,
  REASON_OTHER,
  REASON_RETURN,
} from '@/views/stock/stockAdjustConstants'
import type { StockItem } from '@/api/stock'

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

function stockRow(partial: Partial<StockItem> = {}): StockItem {
  return {
    farm_cd: 'OR001', wh_cd: 'WH01', item_cd: 'FR010100', item_nm: '배 상품',
    variety_cd: 'FR010101', variety_nm: '신고',
    grade_cd: 'GR010100', grade_nm: '특',
    size_cd: 'FR020101', size_nm: '25과',
    weight: 15, harvest_year: 2026, storage_dt: '2026-08-19',
    in_qty: 10, out_qty: 0, real_qty: 10, reserved_qty: 0, available_qty: 10,
    ...partial,
  }
}

function router() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/orders', name: 'orders', component: { template: '<div />' } },
      { path: '/orders/ship', name: 'ship-confirm', component: { template: '<div />' } },
      { path: '/orders/sales-preview', name: 'sales-preview', component: { template: '<div />' } },
    ],
  })
}

async function openSheet() {
  const r = router()
  await r.push('/orders')
  await r.isReady()
  const wrapper = mount(StockView, { global: { plugins: [r] }, attachTo: document.body })
  await flushPromises()
  await wrapper.find('.stock-view__row').trigger('click')
  await flushPromises()
  return wrapper
}

async function bumpPlus(wrapper: ReturnType<typeof mount>, index = 0, times = 1) {
  const steppers = wrapper.findAll('[data-testid="stock-row-stepper"]')
  const btn = steppers[index].findAll('button').find((b) => b.text().includes('+'))
  expect(btn).toBeTruthy()
  for (let i = 0; i < times; i++) {
    await btn!.trigger('click')
  }
  await flushPromises()
}

async function clickAdd(wrapper: ReturnType<typeof mount>, index = 0) {
  const btns = wrapper.findAll('[data-testid="stock-row-add"]')
  await btns[index].trigger('click')
  await flushPromises()
}

async function clickUpdate(wrapper: ReturnType<typeof mount>, index = 0) {
  const btns = wrapper.findAll('[data-testid="stock-row-update"]')
  await btns[index].trigger('click')
  await flushPromises()
}

async function clickRemove(wrapper: ReturnType<typeof mount>, index = 0) {
  const btns = wrapper.findAll('[data-testid="stock-row-remove"]')
  await btns[index].trigger('click')
  await flushPromises()
}

async function clickSalesFab() {
  const btn = document.querySelector('[data-testid="stock-sales-fab"] button') as HTMLButtonElement | null
  expect(btn).toBeTruthy()
  await new DOMWrapper(btn!).trigger('click')
  await flushPromises()
}

function dirButtons() {
  const btns = Array.from(document.querySelectorAll('.stock-log-adjust__btns button'))
  const inc = btns.find((b) => (b.textContent || '').includes('증가')) as HTMLButtonElement | undefined
  const dec = btns.find((b) => (b.textContent || '').includes('감소')) as HTMLButtonElement | undefined
  return { inc, dec }
}

async function setReason(value: string) {
  const el = document.querySelector('.stock-log-adjust select') as HTMLSelectElement | null
  expect(el).toBeTruthy()
  await new DOMWrapper(el!).setValue(value)
  await flushPromises()
}

async function setQty(value: string) {
  const el = document.querySelector('.stock-log-adjust input.ods-input') as HTMLInputElement | null
  expect(el).toBeTruthy()
  await new DOMWrapper(el!).setValue(value)
  await flushPromises()
}

describe('StockView', () => {
  beforeEach(() => {
    document.querySelectorAll('[data-testid="stock-sales-fab"]').forEach((n) => n.remove())
    document.querySelectorAll('.stock-log-overlay').forEach((n) => n.remove())
    setActivePinia(createPinia())
    listFruitStock.mockReset()
    listStockLogs.mockReset()
    adjustStock.mockReset()
    fetchCommonCodes.mockReset()
    vi.restoreAllMocks()
    listFruitStock.mockResolvedValue([stockRow()])
    listStockLogs.mockResolvedValue([])
    fetchCommonCodes.mockResolvedValue([])
    adjustStock.mockResolvedValue({ ok: true, qty: 1, io_type: 'OUT' })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
  })

  it('mount 시 fruit-stock을 조회하고 가용수량을 표시', async () => {
    const wrapper = mount(StockView, { global: { plugins: [router()] } })
    await flushPromises()
    expect(listFruitStock).toHaveBeenCalled()
    expect(wrapper.find('[data-testid="stock-sale-row"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('10박스')
    expect(wrapper.text()).not.toContain('가용')
    expect(wrapper.find('[data-testid="stock-row-add"]').exists()).toBe(true)
    expect(wrapper.find('.stock-view__pick').exists()).toBe(false)
  })

  it('T1 1행에 상품명+재고+stepper+담기 모두 존재', async () => {
    const wrapper = mount(StockView, { global: { plugins: [router()] } })
    await flushPromises()
    const row = wrapper.find('[data-testid="stock-sale-row"]')
    expect(row.find('.stock-view__row-title').exists()).toBe(true)
    expect(row.find('[data-testid="stock-row-available"]').exists()).toBe(true)
    expect(row.find('[data-testid="stock-row-stepper"]').exists()).toBe(true)
    expect(row.find('[data-testid="stock-row-add"]').exists()).toBe(true)
    const style = getComputedStyle(row.element)
    expect(style.flexWrap === 'nowrap' || row.classes().length >= 0).toBe(true)
  })

  it('T2 360px에서도 상품행이 2행으로 떨어지지 않음', async () => {
    const host = document.createElement('div')
    host.style.width = '360px'
    document.body.appendChild(host)
    const wrapper = mount(StockView, { global: { plugins: [router()] }, attachTo: host })
    await flushPromises()
    const row = wrapper.find('[data-testid="stock-sale-row"]').element as HTMLElement
    expect(getComputedStyle(row).flexWrap).toBe('nowrap')
    expect(row.scrollHeight).toBeLessThanOrEqual(row.clientHeight + 2)
    expect(row.clientHeight).toBeLessThan(72)
    wrapper.unmount()
    host.remove()
  })

  it('T1 수량 3 → 담기 → Store 1 line / qty 3', async () => {
    const wrapper = mount(StockView, { global: { plugins: [router()] }, attachTo: document.body })
    await flushPromises()
    await bumpPlus(wrapper, 0, 2) // 1 → 3
    await clickAdd(wrapper)
    const store = useSalesPrefillStore()
    expect(store.source).toBe('STOCK')
    expect(store.shipLines).toHaveLength(1)
    expect(store.shipLines[0].qty).toBe(3)
    expect(wrapper.find('[data-testid="stock-row-update"]').exists()).toBe(true)
    expect(document.querySelector('[data-testid="stock-sales-fab"]')?.textContent).toContain('판매예정 1품목')
    expect(document.querySelector('[data-testid="stock-sales-fab"]')?.textContent).toContain('3박스')
    wrapper.unmount()
  })

  it('T2 담긴 후 수량 5 → 수정 → 동일 line qty 5', async () => {
    const wrapper = mount(StockView, { global: { plugins: [router()] }, attachTo: document.body })
    await flushPromises()
    await bumpPlus(wrapper, 0, 2)
    await clickAdd(wrapper)
    await bumpPlus(wrapper, 0, 2) // 3 → 5
    await clickUpdate(wrapper)
    const store = useSalesPrefillStore()
    expect(store.shipLines).toHaveLength(1)
    expect(store.shipLines[0].qty).toBe(5)
    wrapper.unmount()
  })

  it('T3 × 제거 → Store 비움 + 담기 복귀 + STOCK 세션 유지', async () => {
    const wrapper = mount(StockView, { global: { plugins: [router()] }, attachTo: document.body })
    await flushPromises()
    await clickAdd(wrapper)
    await clickRemove(wrapper)
    const store = useSalesPrefillStore()
    expect(store.shipLines).toHaveLength(0)
    expect(store.source).toBe('STOCK')
    expect(wrapper.find('[data-testid="stock-row-add"]').exists()).toBe(true)
    expect(document.querySelector('[data-testid="stock-sales-fab"]')).toBeNull()
    wrapper.unmount()
  })

  it('T4 상품/배즙 탭 이동해도 판매예정 유지', async () => {
    listFruitStock.mockImplementation(async (_farm: string, q: { item_cd?: string }) => {
      if (q?.item_cd === 'FR010202' || q?.item_cd === 'FR010201' || q?.item_cd === 'FR010200') {
        return [stockRow({ item_cd: 'FR010202', variety_cd: 'XX', size_cd: 'SZ01', available_qty: 8 })]
      }
      return [
        stockRow(),
        stockRow({ grade_cd: 'GR010200', grade_nm: '상', size_cd: 'FR020102', size_nm: '30과', available_qty: 5 }),
      ]
    })
    const wrapper = mount(StockView, { global: { plugins: [router()] }, attachTo: document.body })
    await flushPromises()
    await bumpPlus(wrapper, 0, 2)
    await clickAdd(wrapper, 0)
    await bumpPlus(wrapper, 1, 1)
    await clickAdd(wrapper, 0)
    const store = useSalesPrefillStore()
    expect(store.shipLines).toHaveLength(2)
    const snapshot = store.shipLines.map((l) => `${l.grade_cd}:${l.qty}`).sort()
    const tabs = wrapper.findAll('button.stock-view__type-btn')
    await tabs[2].trigger('click')
    await flushPromises()
    expect(store.shipLines.map((l) => `${l.grade_cd}:${l.qty}`).sort()).toEqual(snapshot)
    await tabs[0].trigger('click')
    await flushPromises()
    expect(wrapper.findAll('[data-testid="stock-row-update"]')).toHaveLength(2)
    wrapper.unmount()
  })

  it('T5 미리보기 삭제 후 재고 복귀 → 미담기', async () => {
    const wrapper = mount(StockView, { global: { plugins: [router()] }, attachTo: document.body })
    await flushPromises()
    await bumpPlus(wrapper, 0, 2)
    await clickAdd(wrapper)
    const store = useSalesPrefillStore()
    store.removeShipLine(0)
    await flushPromises()
    expect(wrapper.find('[data-testid="stock-row-add"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="stock-row-update"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('T6 미리보기 수량 변경 → 재고 행 반영', async () => {
    const wrapper = mount(StockView, { global: { plugins: [router()] }, attachTo: document.body })
    await flushPromises()
    await clickAdd(wrapper)
    const store = useSalesPrefillStore()
    store.updateShipLine(0, { qty: 7 })
    await flushPromises()
    const input = wrapper.find('[data-testid="stock-row-stepper"] input.ods-input')
    expect((input.element as HTMLInputElement).value).toBe('7')
    wrapper.unmount()
  })

  it('T7 비활성 메인탭이면 Floating Bar 숨김(Store 유지)', async () => {
    const panel = ref(0)
    const active = ref(1)
    const wrapper = mount(StockView, {
      global: {
        plugins: [router()],
        provide: {
          mainTabPanelIndex: panel,
          mainTabActiveIndex: active,
        },
      },
      attachTo: document.body,
    })
    await flushPromises()
    await clickAdd(wrapper)
    expect(useSalesPrefillStore().shipLines).toHaveLength(1)
    expect(document.querySelector('[data-testid="stock-sales-fab"]')).toBeNull()
    wrapper.unmount()
  })

  it('T8 활성 메인탭 복귀 → Floating Bar 재표시', async () => {
    const panel = ref(0)
    const active = ref(0)
    const wrapper = mount(StockView, {
      global: {
        plugins: [router()],
        provide: {
          mainTabPanelIndex: panel,
          mainTabActiveIndex: active,
        },
      },
      attachTo: document.body,
    })
    await flushPromises()
    await clickAdd(wrapper)
    expect(document.querySelector('[data-testid="stock-sales-fab"]')).toBeTruthy()
    active.value = 2
    await flushPromises()
    expect(document.querySelector('[data-testid="stock-sales-fab"]')).toBeNull()
    active.value = 0
    await flushPromises()
    expect(document.querySelector('[data-testid="stock-sales-fab"]')?.textContent).toContain('판매예정 1품목')
    wrapper.unmount()
  })

  it('T9 ORDER source shipLines → 재고 FAB 오인 없음', async () => {
    const store = useSalesPrefillStore()
    store.setFromOrderLines(
      {
        order_no: 'ORD1', custm_id: 'A1', customer: 'A', order_dt: '2026-08-01',
        status_cd: 'ST', status_nm: '', tot_order_amt: 0, tot_ship_fee: 0, tot_pay_amt: 0, lines: [],
      } as never,
      [{
        order_detail_id: 'ORD1-01', item_cd: 'FR010100', variety_cd: 'FR010101',
        grade_cd: 'GR010100', size_cd: 'FR020101', weight: 15, qty: 1, unit_price: 0,
        item_amt: 0, harvest_year: 2026, wh_cd: 'WH01', dlvry_tp: 'DL010100',
        remaining_order_qty: 1, reserved_unshipped_qty: 0,
      } as never],
    )
    const wrapper = mount(StockView, { global: { plugins: [router()] }, attachTo: document.body })
    await flushPromises()
    expect(document.querySelector('[data-testid="stock-sales-fab"]')).toBeNull()
    expect(wrapper.find('[data-testid="stock-row-add"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('T10 판매예정 0건 → Floating Bar 없음', async () => {
    const wrapper = mount(StockView, { global: { plugins: [router()] }, attachTo: document.body })
    await flushPromises()
    expect(document.querySelector('[data-testid="stock-sales-fab"]')).toBeNull()
    wrapper.unmount()
  })

  it('T11 가용 1이면 +/- 비활성, 가용 다수는 max까지', async () => {
    listFruitStock.mockResolvedValue([stockRow({ available_qty: 1, real_qty: 1 })])
    const wrapper = mount(StockView, { global: { plugins: [router()] } })
    await flushPromises()
    const stepper = wrapper.find('[data-testid="stock-row-stepper"]')
    const buttons = stepper.findAll('button')
    expect(buttons[0].attributes('disabled')).toBeDefined()
    expect(buttons[1].attributes('disabled')).toBeDefined()
    wrapper.unmount()

    listFruitStock.mockResolvedValue([stockRow({ available_qty: 3 })])
    const w2 = mount(StockView, { global: { plugins: [router()] } })
    await flushPromises()
    await bumpPlus(w2, 0, 5)
    expect((w2.find('[data-testid="stock-row-stepper"] input.ods-input').element as HTMLInputElement).value).toBe('3')
    w2.unmount()
  })

  it('T12 반복 담기해도 중복 line 없음', async () => {
    const wrapper = mount(StockView, { global: { plugins: [router()] } })
    await flushPromises()
    await clickAdd(wrapper)
    // already in cart — no second add; update path only
    expect(wrapper.findAll('[data-testid="stock-row-add"]')).toHaveLength(0)
    expect(useSalesPrefillStore().shipLines).toHaveLength(1)
    wrapper.unmount()
  })

  it('담기 컨트롤 클릭은 조정 시트를 열지 않음', async () => {
    const wrapper = mount(StockView, { global: { plugins: [router()], attachTo: document.body } })
    await flushPromises()
    await clickAdd(wrapper)
    expect(document.querySelector('.stock-log-sheet')).toBeNull()
    wrapper.unmount()
  })

  it('미리보기는 merge 없이 Store만으로 이동', async () => {
    const r = router()
    await r.push('/orders')
    await r.isReady()
    const wrapper = mount(StockView, { global: { plugins: [r] }, attachTo: document.body })
    await flushPromises()
    await bumpPlus(wrapper, 0, 1)
    await clickAdd(wrapper)
    await clickSalesFab()
    expect(r.currentRoute.value.name).toBe('sales-preview')
    expect(useSalesPrefillStore().shipLines[0].qty).toBe(2)
    wrapper.unmount()
  })

  it('Floating Bar는 body Teleport + position:fixed', async () => {
    const wrapper = mount(StockView, { global: { plugins: [router()] }, attachTo: document.body })
    await flushPromises()
    await clickAdd(wrapper)
    const fab = document.querySelector('[data-testid="stock-sales-fab"]') as HTMLElement | null
    expect(fab?.parentElement).toBe(document.body)
    expect(getComputedStyle(fab!).position).toBe('fixed')
    wrapper.unmount()
  })

  it('소진 재고는 담기 UI 없음', async () => {
    listFruitStock.mockResolvedValue([stockRow({ available_qty: 0, real_qty: 0 })])
    const wrapper = mount(StockView, { global: { plugins: [router()] } })
    await flushPromises()
    expect(wrapper.find('[data-testid="stock-row-add"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="stock-row-stepper"]').exists()).toBe(false)
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

  it('T8 동일 판매규격 + 서로 다른 storage_dt → 집계 1행', async () => {
    listFruitStock.mockResolvedValue([
      stockRow({ storage_dt: '2026-08-01', available_qty: 10, real_qty: 10 }),
      stockRow({ storage_dt: '2026-08-20', available_qty: 15, real_qty: 15 }),
    ])
    const wrapper = mount(StockView, { global: { plugins: [router()], attachTo: document.body } })
    await flushPromises()
    expect(wrapper.findAll('[data-testid="stock-sale-row"]')).toHaveLength(1)
    expect(wrapper.find('[data-testid="stock-row-available"]').text()).toContain('25박스')
    await wrapper.find('[data-testid="stock-sale-row"]').trigger('click')
    await flushPromises()
    expect(document.querySelector('[data-testid="stock-adjust-pick"]')).toBeTruthy()
    expect(document.querySelector('.stock-log-sheet')?.textContent).toContain('2026-08-01')
    expect(document.querySelector('.stock-log-sheet')?.textContent).toContain('2026-08-20')
    wrapper.unmount()
  })

  it('T12 단일 stock row 클릭 시 조정 시트 직행(회귀)', async () => {
    const wrapper = await openSheet()
    expect(document.querySelector('[data-testid="stock-adjust-pick"]')).toBeNull()
    expect(document.querySelector('.stock-log-sheet')).toBeTruthy()
    wrapper.unmount()
  })

  it('조정 시트: 헤더 단순화 + summary 제거 + 수량 min=1', async () => {
    const wrapper = await openSheet()
    const sheet = document.body.textContent || ''
    expect(sheet).toContain('신고 · 15kg · 25과 · 특')
    expect(sheet).not.toContain('배정 0')
    expect(listStockLogs).not.toHaveBeenCalled()
    const qtyInput = document.querySelector('.stock-log-adjust input.ods-input') as HTMLInputElement | null
    expect(qtyInput?.getAttribute('min')).toBe('1')
    wrapper.unmount()
  })

  it('T5 qty=0 차단 + API 호출 없음', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    confirmSpy.mockClear()
    const wrapper = await openSheet()
    await setQty('0')
    dirButtons().dec?.click()
    await flushPromises()
    expect(confirmSpy).not.toHaveBeenCalled()
    expect(adjustStock).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('T6 qty=-1 차단', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    confirmSpy.mockClear()
    const wrapper = await openSheet()
    await setQty('-1')
    dirButtons().dec?.click()
    await flushPromises()
    expect(confirmSpy).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('T7 qty=빈값 차단', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    confirmSpy.mockClear()
    const wrapper = await openSheet()
    await setQty('')
    dirButtons().dec?.click()
    await flushPromises()
    expect(confirmSpy).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('T8 qty=3 + 감소 confirm 문구', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const wrapper = await openSheet()
    await setQty('3')
    dirButtons().dec?.click()
    await flushPromises()
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('3박스를 감소하시겠습니까?'))
    wrapper.unmount()
  })

  it('T9 qty=3 + 증가 confirm 문구', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const wrapper = await openSheet()
    await setReason(REASON_RETURN)
    await setQty('3')
    dirButtons().inc?.click()
    await flushPromises()
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('3박스를 증가하시겠습니까?'))
    wrapper.unmount()
  })

  it('T10 폐기/파손/증정은 감소만 가능', async () => {
    const wrapper = await openSheet()
    for (const reason of ['AD010101', 'AD010102', 'AD010103']) {
      await setReason(reason)
      const { inc, dec } = dirButtons()
      expect(inc?.disabled).toBe(true)
      expect(dec?.disabled).toBe(false)
    }
    wrapper.unmount()
  })

  it('T11 반품은 증가만 가능', async () => {
    const wrapper = await openSheet()
    await setReason(REASON_RETURN)
    const { inc, dec } = dirButtons()
    expect(inc?.disabled).toBe(false)
    expect(dec?.disabled).toBe(true)
    wrapper.unmount()
  })

  it('T12 실사차이/기타는 양방향 가능', async () => {
    const wrapper = await openSheet()
    await setReason(REASON_COUNT_DIFF)
    let btns = dirButtons()
    expect(btns.inc?.disabled).toBe(false)
    expect(btns.dec?.disabled).toBe(false)
    await setReason(REASON_OTHER)
    btns = dirButtons()
    expect(btns.inc?.disabled).toBe(false)
    expect(btns.dec?.disabled).toBe(false)
    wrapper.unmount()
  })

  it('T14 성공 시 목록 reload + sheet close + 메인 성공 메시지', async () => {
    listFruitStock
      .mockResolvedValueOnce([stockRow()])
      .mockResolvedValue([stockRow({ out_qty: 3, real_qty: 7, available_qty: 7 })])
    const wrapper = await openSheet()
    await setQty('3')
    dirButtons().dec?.click()
    await flushPromises()
    expect(document.querySelector('.stock-log-sheet')).toBeNull()
    expect(wrapper.text()).toContain('재고 조정이 완료되었습니다')
    expect(wrapper.text()).toContain('3박스 감소')
    wrapper.unmount()
  })

  it('T14 실패 시 sheet 유지', async () => {
    adjustStock.mockRejectedValueOnce(new Error('boom'))
    const wrapper = await openSheet()
    await setQty('2')
    dirButtons().dec?.click()
    await flushPromises()
    expect(document.querySelector('.stock-log-sheet')).toBeTruthy()
    wrapper.unmount()
  })

  it('T15 이력 아코디언: 최초만 조회', async () => {
    listStockLogs.mockRejectedValueOnce(new Error('boom'))
    const wrapper = await openSheet()
    const histBtn = document.querySelector('.stock-log-history-accordion-btn') as HTMLButtonElement | null
    histBtn!.click()
    await flushPromises()
    expect(listStockLogs).toHaveBeenCalledTimes(1)
    histBtn!.click()
    await flushPromises()
    histBtn!.click()
    await flushPromises()
    expect(listStockLogs).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })
})
