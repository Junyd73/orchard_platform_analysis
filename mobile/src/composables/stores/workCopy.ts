import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface WorkCopyDraft {
  workMidCd: string
  workContent: string
  workLocId: string
  siteNm: string
  startTime: string
  endTime: string
  rmk: string
  varietyCd?: string
  varietyNm?: string
  harvestContainerQty?: string
}

/** 작업복사 모달 → 대상 일간 페이지로 전달할 임시 데이터 */
export const useWorkCopyStore = defineStore('workCopy', () => {
  const draft = ref<WorkCopyDraft | null>(null)

  function set(data: WorkCopyDraft) {
    draft.value = { ...data }
  }

  function consume(): WorkCopyDraft | null {
    const v = draft.value
    draft.value = null
    return v
  }

  function clear() {
    draft.value = null
  }

  return { draft, set, consume, clear }
})
