import { afterEach, describe, expect, it } from 'vitest'
import { DOMWrapper, flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'

import ParcelDestinationSheet from '@/components/sales/ParcelDestinationSheet.vue'
import { emptyDeliveryDraft } from '@/views/sales/shipDeliveryModel'

const baseProps = {
  open: false,
  productSummary: '신고배 · 7.5kg',
  orderQty: 3,
  unitLabel: '박스',
  initialDests: [] as ReturnType<typeof emptyDeliveryDraft>[],
  customerDefaults: { rcv_name: '홍길동', rcv_tel: '010-1111-2222' },
  ordererName: '홍길동',
  showShipFee: true,
  lockStructure: false,
  testIdPrefix: 'sales-preview',
}

function mountSheet(overrides: Partial<typeof baseProps> = {}) {
  return mount(ParcelDestinationSheet, {
    props: { ...baseProps, ...overrides },
    attachTo: document.body,
  })
}

function sheetEl(prefix = 'sales-preview') {
  return document.querySelector(`[data-testid="${prefix}-dest-sheet"]`)
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('ParcelDestinationSheet', () => {
  it('opens empty and allows add', async () => {
    const wrapper = mountSheet({ open: true })
    await flushPromises()
    const sheet = sheetEl()
    expect(sheet).toBeTruthy()
    expect(sheet!.querySelector('[data-testid="sales-preview-dest-add"]')).toBeTruthy()
    ;(sheet!.querySelector('[data-testid="sales-preview-dest-add"]') as HTMLButtonElement).click()
    await flushPromises()
    expect(sheet!.querySelector('[data-testid="sales-preview-dest-row"]')).toBeTruthy()
    wrapper.unmount()
  })

  it('blocks qty over-cap with tip near input', async () => {
    const wrapper = mountSheet({ open: true, orderQty: 2 })
    await flushPromises()
    const sheet = sheetEl()!
    ;(sheet.querySelector('[data-testid="sales-preview-dest-add"]') as HTMLButtonElement).click()
    await flushPromises()
    await new DOMWrapper(sheet.querySelector('[data-testid="sales-preview-dest-qty"]')!).setValue(
      '5',
    )
    await flushPromises()
    expect(
      (sheet.querySelector('[data-testid="sales-preview-dest-qty"]') as HTMLInputElement).value,
    ).toBe('1')
    expect(document.querySelector('[data-testid="sales-preview-dest-tip"]')?.textContent || '').toContain(
      '초과',
    )
    wrapper.unmount()
  })

  it('rejects incomplete dest on complete', async () => {
    const wrapper = mountSheet({ open: true })
    await flushPromises()
    const sheet = sheetEl()!
    ;(sheet.querySelector('[data-testid="sales-preview-dest-add"]') as HTMLButtonElement).click()
    await flushPromises()
    ;(sheet.querySelector('[data-testid="sales-preview-dest-done"]') as HTMLButtonElement).click()
    await flushPromises()
    expect(wrapper.emitted('complete')).toBeFalsy()
    expect(sheet.querySelector('[data-testid="sales-preview-dest-err"]')?.textContent || '').toContain(
      '수령인',
    )
    wrapper.unmount()
  })

  it('close discards local draft changes', async () => {
    const wrapper = mountSheet({
      open: true,
      initialDests: [
        emptyDeliveryDraft({
          qty: 2,
          rcv_name: '기존',
          rcv_tel: '010',
          rcv_addr: '서울',
          ship_fee: 0,
        }),
      ],
    })
    await flushPromises()
    let sheet = sheetEl()!
    ;(sheet.querySelector('[data-testid="sales-preview-dest-edit"]') as HTMLButtonElement).click()
    await flushPromises()
    const row = sheet.querySelector('[data-testid="sales-preview-dest-row"]')!
    await new DOMWrapper(row.querySelectorAll('input')[0]).setValue('변경됨')
    await flushPromises()
    ;(sheet.querySelector('.dest-sheet__x') as HTMLButtonElement).click()
    await flushPromises()
    expect(wrapper.emitted('close')).toBeTruthy()
    expect(wrapper.emitted('complete')).toBeFalsy()
    wrapper.unmount()

    const wrapper2 = mountSheet({
      open: true,
      initialDests: [
        emptyDeliveryDraft({
          qty: 2,
          rcv_name: '기존',
          rcv_tel: '010',
          rcv_addr: '서울',
          ship_fee: 0,
        }),
      ],
    })
    await flushPromises()
    sheet = sheetEl()!
    expect(sheet.textContent || '').toContain('기존')
    expect(sheet.textContent || '').not.toContain('변경됨')
    wrapper2.unmount()
  })

  it('complete emits cleaned drafts', async () => {
    const wrapper = mountSheet({ open: true, orderQty: 3 })
    await flushPromises()
    const sheet = sheetEl()!
    ;(sheet.querySelector('[data-testid="sales-preview-dest-add"]') as HTMLButtonElement).click()
    await flushPromises()
    const row = sheet.querySelector('[data-testid="sales-preview-dest-row"]')!
    const inputs = row.querySelectorAll('input')
    await new DOMWrapper(inputs[0]).setValue('홍길동')
    await new DOMWrapper(inputs[1]).setValue('010')
    await new DOMWrapper(inputs[2]).setValue('3')
    await new DOMWrapper(inputs[3]).setValue('4,000')
    await new DOMWrapper(inputs[4]).setValue('서울')
    ;(sheet.querySelector('[data-testid="sales-preview-dest-save"]') as HTMLButtonElement).click()
    await flushPromises()
    ;(sheet.querySelector('[data-testid="sales-preview-dest-done"]') as HTMLButtonElement).click()
    await flushPromises()
    const emitted = wrapper.emitted('complete')
    expect(emitted).toBeTruthy()
    expect(emitted![0][0]).toEqual([
      expect.objectContaining({
        qty: 3,
        rcv_name: '홍길동',
        rcv_tel: '010',
        rcv_addr: '서울',
        ship_fee: 4000,
      }),
    ])
    wrapper.unmount()
  })

  it('showShipFee=false hides fee and still emits ship_fee 0', async () => {
    const wrapper = mountSheet({
      open: true,
      showShipFee: false,
      testIdPrefix: 'order-new',
      orderQty: 1,
    })
    await flushPromises()
    const sheet = sheetEl('order-new')!
    expect(sheet.querySelector('[data-testid="order-new-dest-fee"]')).toBeFalsy()
    ;(sheet.querySelector('[data-testid="order-new-dest-add"]') as HTMLButtonElement).click()
    await flushPromises()
    const row = sheet.querySelector('[data-testid="order-new-dest-row"]')!
    const inputs = row.querySelectorAll('input')
    await new DOMWrapper(inputs[0]).setValue('수령')
    await new DOMWrapper(inputs[1]).setValue('010')
    await new DOMWrapper(inputs[2]).setValue('1')
    await new DOMWrapper(inputs[3]).setValue('주소')
    ;(sheet.querySelector('[data-testid="order-new-dest-save"]') as HTMLButtonElement).click()
    await flushPromises()
    ;(sheet.querySelector('[data-testid="order-new-dest-done"]') as HTMLButtonElement).click()
    await flushPromises()
    expect(wrapper.emitted('complete')![0][0][0].ship_fee).toBe(0)
    wrapper.unmount()
  })

  it('lockStructure hides add/remove', async () => {
    const wrapper = mountSheet({
      open: true,
      lockStructure: true,
      initialDests: [
        emptyDeliveryDraft({
          qty: 1,
          rcv_name: '잠김',
          rcv_tel: '010',
          rcv_addr: '서울',
          ship_fee: 0,
        }),
      ],
    })
    await flushPromises()
    const sheet = sheetEl()!
    expect(sheet.querySelector('[data-testid="sales-preview-dest-add"]')).toBeFalsy()
    expect(sheet.querySelector('[data-testid="sales-preview-dest-remove"]')).toBeFalsy()
    expect(sheet.querySelector('[data-testid="sales-preview-dest-edit"]')).toBeTruthy()
    wrapper.unmount()
  })

  it('allows complete with empty list', async () => {
    const wrapper = mountSheet({ open: true, initialDests: [] })
    await flushPromises()
    const sheet = sheetEl()!
    ;(sheet.querySelector('[data-testid="sales-preview-dest-done"]') as HTMLButtonElement).click()
    await flushPromises()
    await nextTick()
    expect(wrapper.emitted('complete')?.[0]?.[0]).toEqual([])
    wrapper.unmount()
  })

  it('X close emits close without complete', async () => {
    const wrapper = mountSheet({ open: true })
    await flushPromises()
    const sheet = sheetEl()!
    ;(sheet.querySelector('.dest-sheet__x') as HTMLButtonElement).click()
    await flushPromises()
    expect(wrapper.emitted('close')).toBeTruthy()
    expect(wrapper.emitted('complete')).toBeFalsy()
    wrapper.unmount()
  })
})
