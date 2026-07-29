<script setup lang="ts">
import OdsFormField from '@/components/ods/OdsFormField.vue'
import OdsInput from '@/components/ods/OdsInput.vue'
import OdsSelect from '@/components/ods/OdsSelect.vue'
import {
  FRUIT_ASYMMETRY_OPTIONS,
  FRUIT_DEFECT_OPTIONS,
  type FruitMeasureFormModel,
} from '@/shared/fruitMeasureForm'
import type { CommonCodeItem } from '@/types/commonCode'

defineProps<{
  shapeOptions: CommonCodeItem[]
  colorOptions: CommonCodeItem[]
  stalkOptions: CommonCodeItem[]
  calyxOptions: CommonCodeItem[]
  disabled?: boolean
}>()

const model = defineModel<FruitMeasureFormModel>({ required: true })
</script>

<template>
  <div class="fruit-form" aria-label="열매 측정">
    <div class="num-grid">
      <OdsInput
        v-model="model.widthMm"
        label="가로(폭) mm"
        variant="form"
        type="number"
        inputmode="decimal"
        :disabled="disabled"
        optional
      />
      <OdsInput
        v-model="model.heightMm"
        label="세로(길이) mm"
        variant="form"
        type="number"
        inputmode="decimal"
        :disabled="disabled"
        optional
      />
      <OdsInput
        v-model="model.circMm"
        label="둘레 mm"
        variant="form"
        type="number"
        inputmode="decimal"
        :disabled="disabled"
        optional
      />
      <OdsInput
        v-model="model.weightG"
        label="추정 무게 g"
        variant="form"
        type="number"
        inputmode="decimal"
        :disabled="disabled"
        optional
      />
    </div>

    <OdsFormField label="열매 형태" optional>
      <OdsSelect v-model="model.shapeCd" variant="form" :disabled="disabled">
        <option value="">선택</option>
        <option
          v-for="c in shapeOptions"
          :key="c.code_cd"
          :value="c.code_cd"
        >
          {{ c.code_nm }}
        </option>
      </OdsSelect>
    </OdsFormField>

    <OdsFormField label="과피색" optional>
      <OdsSelect v-model="model.skinColorCd" variant="form" :disabled="disabled">
        <option value="">선택</option>
        <option
          v-for="c in colorOptions"
          :key="c.code_cd"
          :value="c.code_cd"
        >
          {{ c.code_nm }}
        </option>
      </OdsSelect>
    </OdsFormField>

    <OdsFormField label="비대칭 등급" optional hint="0(대칭) ~ 5(심함)">
      <OdsSelect v-model="model.asymmetryLevel" variant="form" :disabled="disabled">
        <option
          v-for="opt in FRUIT_ASYMMETRY_OPTIONS"
          :key="opt.value || 'none'"
          :value="opt.value"
        >
          {{ opt.label }}
        </option>
      </OdsSelect>
    </OdsFormField>

    <OdsFormField label="이상 여부" optional as="fieldset">
      <div class="defect-grid" role="group" aria-label="이상 여부">
        <label
          v-for="opt in FRUIT_DEFECT_OPTIONS"
          :key="opt.key"
          class="defect"
        >
          <input
            v-model="model[opt.key]"
            type="checkbox"
            :disabled="disabled"
          >
          {{ opt.label }}
        </label>
      </div>
    </OdsFormField>

    <OdsFormField label="과경 상태" optional>
      <OdsSelect v-model="model.stalkStatusCd" variant="form" :disabled="disabled">
        <option value="">선택</option>
        <option
          v-for="c in stalkOptions"
          :key="c.code_cd"
          :value="c.code_cd"
        >
          {{ c.code_nm }}
        </option>
      </OdsSelect>
    </OdsFormField>

    <OdsFormField label="꽃받침 상태" optional>
      <OdsSelect v-model="model.calyxStatusCd" variant="form" :disabled="disabled">
        <option value="">선택</option>
        <option
          v-for="c in calyxOptions"
          :key="c.code_cd"
          :value="c.code_cd"
        >
          {{ c.code_nm }}
        </option>
      </OdsSelect>
    </OdsFormField>

    <OdsFormField label="비고" optional>
      <textarea
        v-model="model.fruitRmk"
        class="rmk"
        rows="3"
        maxlength="500"
        :disabled="disabled"
        placeholder="특이사항"
      />
    </OdsFormField>
  </div>
</template>

<style scoped>
.fruit-form {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-16);
}
.num-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--ods-space-12);
}
.defect-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--ods-space-8);
}
.defect {
  display: flex;
  align-items: center;
  gap: var(--ods-space-8);
  min-height: var(--ods-button-height-in-card);
  padding: 0 var(--ods-space-8);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-white);
  font: var(--ods-font-form-value);
  color: var(--ods-color-text);
}
.defect input {
  width: var(--ods-icon-lg);
  height: var(--ods-icon-lg);
  accent-color: var(--ods-color-primary);
}
.rmk {
  width: 100%;
  box-sizing: border-box;
  min-height: calc(2 * var(--ods-control-height));
  padding: var(--ods-space-12) var(--ods-space-16);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-button);
  font: var(--ods-font-form-value);
  color: var(--ods-color-text);
  background: var(--ods-color-white);
  resize: vertical;
}
.rmk:disabled {
  background: var(--ods-color-gray-100);
  color: var(--ods-color-gray-500);
}
@media (max-width: 360px) {
  .num-grid,
  .defect-grid {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
