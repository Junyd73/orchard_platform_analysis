<script setup lang="ts">
import iconTitleAi from '@/assets/ods/common/icon-title-ai.svg'
import OdsSectionTitle from '@/components/ods/OdsSectionTitle.vue'
import ObservationAiRiskSection from '@/views/observation/components/ObservationAiRiskSection.vue'
import ObservationRecentAiSection from '@/views/observation/components/ObservationRecentAiSection.vue'
import {
  LABEL_AI_SECTION,
  type AiRiskCardItem,
  type RecentAiCardItem,
} from '@/views/observation/observationHomeCopy'

withDefaults(
  defineProps<{
    riskItems?: AiRiskCardItem[] | null
    recentItems?: RecentAiCardItem[] | null
    loading?: boolean
  }>(),
  {
    riskItems: null,
    recentItems: null,
    loading: false,
  },
)

const emit = defineEmits<{
  openRisk: [obsId: string]
  openRecent: [id: string]
  openAll: []
}>()
</script>

<template>
  <section class="ai-home" :aria-label="LABEL_AI_SECTION">
    <OdsSectionTitle :title="LABEL_AI_SECTION" :icon="iconTitleAi" />

    <div class="ai-home__body">
      <ObservationAiRiskSection
        :items="riskItems"
        :loading="loading"
        @open="emit('openRisk', $event)"
      />

      <ObservationRecentAiSection
        :items="recentItems"
        :loading="loading"
        @open-all="emit('openAll')"
        @select="emit('openRecent', $event)"
      />
    </div>
  </section>
</template>

<style scoped>
.ai-home {
  display: flex;
  flex-direction: column;
  gap: var(--ods-form-label-gap, var(--ods-space-8));
  margin: 0;
}
.ai-home__body {
  display: flex;
  flex-direction: column;
  gap: var(--ods-card-block-gap, var(--ods-space-16));
}
</style>
