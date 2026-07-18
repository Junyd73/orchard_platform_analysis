<script setup lang="ts">
withDefaults(
  defineProps<{
    /** 스켈레톤 행/블록 수 */
    lines?: number
    /** card | line | circle | hero */
    variant?: 'card' | 'line' | 'circle' | 'hero' | 'kpi'
    height?: string
  }>(),
  {
    lines: 1,
    variant: 'line',
    height: undefined,
  },
)
</script>

<template>
  <div
    class="ods-skel"
    :class="`ods-skel--${variant}`"
    :style="height ? { minHeight: height } : undefined"
    aria-hidden="true"
  >
    <template v-if="variant === 'kpi'">
      <span v-for="i in 3" :key="i" class="ods-skel__block ods-skel__block--kpi" />
    </template>
    <template v-else-if="variant === 'hero'">
      <span class="ods-skel__block ods-skel__block--hero" />
    </template>
    <template v-else>
      <span
        v-for="i in lines"
        :key="i"
        class="ods-skel__block"
        :class="{
          'ods-skel__block--card': variant === 'card',
          'ods-skel__block--circle': variant === 'circle',
        }"
      />
    </template>
  </div>
</template>

<style scoped>
.ods-skel {
  display: flex;
  flex-direction: column;
  gap: var(--ods-space-8);
}
.ods-skel--kpi {
  flex-direction: row;
  gap: var(--ods-space-12);
}
.ods-skel__block {
  display: block;
  width: 100%;
  height: 12px;
  border-radius: var(--ods-radius-button);
  background: linear-gradient(
    90deg,
    var(--ods-color-gray-100) 0%,
    var(--ods-color-gray-300) 50%,
    var(--ods-color-gray-100) 100%
  );
  background-size: 200% 100%;
  animation: ods-skel-shimmer var(--ods-motion-base) ease-in-out infinite alternate;
}
.ods-skel__block--card {
  height: 96px;
  border-radius: var(--ods-radius-card);
}
.ods-skel__block--circle {
  width: 40px;
  height: 40px;
  border-radius: var(--ods-radius-badge);
}
.ods-skel__block--hero {
  height: 300px;
  border-radius: var(--ods-radius-card-lg);
}
.ods-skel__block--kpi {
  flex: 1;
  height: 56px;
}
@keyframes ods-skel-shimmer {
  from {
    background-position: 100% 0;
  }
  to {
    background-position: 0 0;
  }
}
@media (prefers-reduced-motion: reduce) {
  .ods-skel__block {
    animation: none;
  }
}
</style>
