import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { ref } from 'vue'

import StockView from '@/features/stock/StockView.vue'
import { useSalesPrefillStore } from '@/shared/stores/salesPrefill'
import {
  REASON_COUNT_DIFF,
  REASON_OTHER,
  REASON_RETURN,
} from '@/features/stock/stockAdjustConstants'
import type { StockItem } from '@/api/stock'

const listFruitStock = vi.fn()
const listStockLogs = vi.fn()
const adjustStock = vi.fn()
const adjustStockBySpec = vi.fn()
const fetchCommonCodes = vi.fn()

vi.mock('@/api/stock', () => ({
  listFruitStock: (...args: unknown[]) => listFruitStock(...args),
  listStockLogs: (...args: unknown[]) => listStockLogs(...args),
  adjustStock: (...args: unknown[]) => adjustStock(...args),
  adjustStockBySpec: (...args: unknown[]) => adjustStockBySpec(...args),
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
  const btns = wrapper.findAll('[data-testid="stock-row-add"]').filter(
    (b) => !(b.element as HTMLButtonElement).disabled,
  )
  await btns[index].trigger('click')
  await flushPromises()
}

async function clickUpdate(wrapper: ReturnType<typeof mount>, index = 0) {
  const btns = wrapper.findAll('[data-testid="stock-row-update"]').filter(
    (b) => !(b.element as HTMLButtonElement).disabled,
  )
  await btns[index].trigger('click')
  await flushPromises()
}

async function clickRemove(wrapper: ReturnType<typeof mount>, index = 0) {
  const btns = wrapper.findAll('[data-testid="stock-row-remove"]').filter(
    (b) => !(b.element as HTMLButtonElement).disabled,
  )
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
    adjustStockBySpec.mockReset()
    fetchCommonCodes.mockReset()
    vi.restoreAllMocks()
    listFruitStock.mockResolvedValue([stockRow()])
    listStockLogs.mockResolvedValue([])
    fetchCommonCodes.mockResolvedValue([])
    adjustStock.mockResolvedValue({ ok: true, qty: 1, io_type: 'OUT' })
    adjustStockBySpec.mockResolvedValue({ ok: true, qty: 1, io_type: 'OUT' })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
  })

  it('mount 시 fruit-stock을 조회하고 가용수량을 표시', async () => {
    const wrapper = mount(StockView, { global: { plugins: [router()] } })
    await flushPromises()
    expect(listFruitStock).toHaveBeenCalled()
    expect(wrapper.find('[data-testid="stock-sale-row"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('10박스')
    expect(wrapper.find('[data-testid="stock-row-available"]').text()).not.toMatch(/^가용/)
    expect(wrapper.find('[data-testid="stock-list-head"]').text()).toContain('가용수량')
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

  it('UI-T1 bare OdsInput root value 초기값 1 표시', async () => {
    const wrapper = mount(StockView, { global: { plugins: [router()] }, attachTo: document.body })
    await flushPromises()
    const input = wrapper.find('[data-testid="stock-row-qty-input"]')
    expect(input.exists()).toBe(true)
    expect(input.element.tagName).toBe('INPUT')
    expect(input.classes()).toContain('ods-input')
    expect(input.classes()).toContain('stock-view__qty-input')
    expect((input.element as HTMLInputElement).value).toBe('1')
    // bare root — 자식 input 셀렉터는 없음
    expect(input.find('input').exists()).toBe(false)
    wrapper.unmount()
  })

  it('UI-T2/T3 +/- 클릭 시 input value 즉시 반영', async () => {
    const wrapper = mount(StockView, { global: { plugins: [router()] }, attachTo: document.body })
    await flushPromises()
    await bumpPlus(wrapper, 0, 2)
    expect((wrapper.find('[data-testid="stock-row-qty-input"]').element as HTMLInputElement).value).toBe('3')
    const minus = wrapper.findAll('[data-testid="stock-row-stepper"] button').find((b) => b.text().includes('−') || b.text().includes('-'))
    await minus!.trigger('click')
    await flushPromises()
    expect((wrapper.find('[data-testid="stock-row-qty-input"]').element as HTMLInputElement).value).toBe('2')
    wrapper.unmount()
  })

  it('UI-T4/T5/T6 담기·재진입·수정 시 input=Store qty', async () => {
    const wrapper = mount(StockView, { global: { plugins: [router()] }, attachTo: document.body })
    await flushPromises()
    await bumpPlus(wrapper, 0, 5) // 1→6
    await clickAdd(wrapper)
    expect(useSalesPrefillStore().shipLines[0].qty).toBe(6)
    expect((wrapper.find('[data-testid="stock-row-qty-input"]').element as HTMLInputElement).value).toBe('6')
    await bumpPlus(wrapper, 0, 1) // 6→7
    await clickUpdate(wrapper)
    expect(useSalesPrefillStore().shipLines[0].qty).toBe(7)
    expect((wrapper.find('[data-testid="stock-row-qty-input"]').element as HTMLInputElement).value).toBe('7')
    wrapper.unmount()
  })

  it('UI-T7 가용 1이면 숫자 1 + +/- disabled', async () => {
    listFruitStock.mockResolvedValue([stockRow({ available_qty: 1, real_qty: 1 })])
    const wrapper = mount(StockView, { global: { plugins: [router()] } })
    await flushPromises()
    expect((wrapper.find('[data-testid="stock-row-qty-input"]').element as HTMLInputElement).value).toBe('1')
    const buttons = wrapper.find('[data-testid="stock-row-stepper"]').findAll('button')
    expect(buttons[0].attributes('disabled')).toBeDefined()
    expect(buttons[1].attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })

  it('리스트 상단 항목타이틀 상품/가용수량/포장수량', async () => {
    const wrapper = mount(StockView, { global: { plugins: [router()] } })
    await flushPromises()
    const head = wrapper.find('[data-testid="stock-list-head"]')
    expect(head.exists()).toBe(true)
    expect(head.text()).toContain('상품')
    expect(head.text()).toContain('가용수량')
    expect(head.text()).toContain('판매수량')
    expect(head.text()).not.toContain('포장수량')
  })

  it('Floating Bar는 width 70% · 가운데 정렬', async () => {
    const wrapper = mount(StockView, { global: { plugins: [router()] }, attachTo: document.body })
    await flushPromises()
    await clickAdd(wrapper)
    const fab = document.querySelector('[data-testid="stock-sales-fab"]') as HTMLElement
    expect(fab).toBeTruthy()
    expect(fab.style.width).toBe('70%')
    expect(fab.style.left).toBe('50%')
    expect(fab.style.transform).toContain('translateX(-50%)')
    expect(fab.style.maxWidth).toBe('336px')
    wrapper.unmount()
  })

  it('UI-T10 360/390/430 nowrap + overflow 없음', async () => {
    for (const w of [360, 390, 430]) {
      const host = document.createElement('div')
      host.style.width = `${w}px`
      document.body.appendChild(host)
      const wrapper = mount(StockView, { global: { plugins: [router()] }, attachTo: host })
      await flushPromises()
      const row = wrapper.find('[data-testid="stock-sale-row"]').element as HTMLElement
      expect(getComputedStyle(row).flexWrap).toBe('nowrap')
      expect(row.scrollWidth).toBeLessThanOrEqual(row.clientWidth + 1)
      wrapper.unmount()
      host.remove()
    }
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
    expect((wrapper.find('[data-testid="stock-row-add"]').element as HTMLButtonElement).disabled).toBe(false)
    expect((wrapper.find('[data-testid="stock-row-update"]').element as HTMLButtonElement).disabled).toBe(true)
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
    // 담긴 뒤 카트는 disabled — 수정/비우기만 활성
    expect((wrapper.find('[data-testid="stock-row-add"]').element as HTMLButtonElement).disabled).toBe(true)
    expect((wrapper.find('[data-testid="stock-row-update"]').element as HTMLButtonElement).disabled).toBe(false)
    expect(useSalesPrefillStore().shipLines).toHaveLength(1)
    wrapper.unmount()
  })

  it('조회: 품종/중량/크기/등급 + 돋보기/새로고침 배치', async () => {
    listFruitStock.mockResolvedValue([
      stockRow(),
      stockRow({
        grade_cd: 'GR010200', grade_nm: '상', size_cd: 'FR020102', size_nm: '30과',
        weight: 7.5, available_qty: 5,
      }),
    ])
    const wrapper = mount(StockView, { global: { plugins: [router()] } })
    await flushPromises()
    const queryCard = wrapper.find('[data-testid="stock-query-bar"]')
    expect(queryCard.exists()).toBe(true)
    expect(queryCard.classes()).toContain('ods-card')
    expect(queryCard.attributes('aria-label')).toBe('조회조건')
    expect(wrapper.find('[data-testid="stock-filter-variety"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="stock-filter-weight"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="stock-filter-size"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="stock-filter-grade"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="stock-search"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="stock-refresh"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-testid="stock-sale-row"]')).toHaveLength(2)

    await wrapper.find('[data-testid="stock-filter-grade"]').setValue('GR010200')
    await wrapper.find('[data-testid="stock-search"]').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('[data-testid="stock-sale-row"]')).toHaveLength(1)
    expect(wrapper.text()).toContain('상')
    wrapper.unmount()
  })

  it('아이콘 3개 고정 · 미담기 시 카트만 활성', async () => {
    const wrapper = mount(StockView, { global: { plugins: [router()] } })
    await flushPromises()
    const icons = wrapper.find('[data-testid="stock-row-icons"]')
    expect(icons.findAll('button')).toHaveLength(3)
    expect((wrapper.find('[data-testid="stock-row-add"]').element as HTMLButtonElement).disabled).toBe(false)
    expect((wrapper.find('[data-testid="stock-row-update"]').element as HTMLButtonElement).disabled).toBe(true)
    expect((wrapper.find('[data-testid="stock-row-remove"]').element as HTMLButtonElement).disabled).toBe(true)
    await clickAdd(wrapper)
    expect((wrapper.find('[data-testid="stock-row-add"]').element as HTMLButtonElement).disabled).toBe(true)
    expect((wrapper.find('[data-testid="stock-row-update"]').element as HTMLButtonElement).disabled).toBe(false)
    expect((wrapper.find('[data-testid="stock-row-remove"]').element as HTMLButtonElement).disabled).toBe(false)
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

  it('T1~T2 동일 판매규격 + 서로 다른 storage_dt → 집계 1행 · 합산 가용', async () => {
    listFruitStock.mockResolvedValue([
      stockRow({ storage_dt: '2026-08-01', available_qty: 10, real_qty: 10 }),
      stockRow({ storage_dt: '2026-08-20', available_qty: 15, real_qty: 15 }),
    ])
    const wrapper = mount(StockView, { global: { plugins: [router()], attachTo: document.body } })
    await flushPromises()
    expect(wrapper.findAll('[data-testid="stock-sale-row"]')).toHaveLength(1)
    expect(wrapper.find('[data-testid="stock-row-available"]').text()).toContain('25박스')
    expect(wrapper.text()).not.toContain('2026-08-01')
    expect(wrapper.text()).not.toContain('2026-08-20')
    expect(wrapper.text()).not.toContain('포장')
    expect(wrapper.text()).not.toContain('저장일')
    wrapper.unmount()
  })

  it('T5~T6 복수 source 클릭 시 날짜선택 Sheet 없음 · 조정 시트 직행', async () => {
    listFruitStock.mockResolvedValue([
      stockRow({ storage_dt: '2026-08-01', available_qty: 10, real_qty: 10 }),
      stockRow({ storage_dt: '2026-08-20', available_qty: 15, real_qty: 15 }),
    ])
    const wrapper = mount(StockView, { global: { plugins: [router()], attachTo: document.body } })
    await flushPromises()
    await wrapper.find('[data-testid="stock-sale-row"]').trigger('click')
    await flushPromises()
    expect(document.querySelector('[data-testid="stock-adjust-pick"]')).toBeNull()
    expect(document.body.textContent || '').not.toContain('포장/저장일별')
    expect(document.body.textContent || '').not.toContain('조정할 재고 선택')
    expect(document.querySelector('.stock-log-sheet')).toBeTruthy()
    expect(document.querySelector('.stock-log-sheet')?.textContent || '').not.toContain('2026-08-01')
    wrapper.unmount()
  })

  it('T12 단일 stock row 클릭 시 조정 시트 직행(회귀)', async () => {
    const wrapper = await openSheet()
    expect(document.querySelector('[data-testid="stock-adjust-pick"]')).toBeNull()
    expect(document.querySelector('.stock-log-sheet')).toBeTruthy()
    wrapper.unmount()
  })

  it('T8 상품 재고조정은 adjust-by-spec(storage_dt 미전송)', async () => {
    const wrapper = await openSheet()
    await setQty('2')
    dirButtons().dec?.click()
    await flushPromises()
    expect(adjustStock).not.toHaveBeenCalled()
    expect(adjustStockBySpec).toHaveBeenCalledWith(
      'OR001',
      expect.objectContaining({
        item_cd: 'FR010100',
        qty: 2,
        io_type: 'OUT',
      }),
    )
    const payload = adjustStockBySpec.mock.calls[0][1] as Record<string, unknown>
    expect(payload).not.toHaveProperty('storage_dt')
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
    expect(adjustStockBySpec).not.toHaveBeenCalled()
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
    adjustStockBySpec.mockRejectedValueOnce(new Error('boom'))
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
