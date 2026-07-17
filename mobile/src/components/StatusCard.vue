<script setup lang="ts">
type ConnectionStatus = 'idle' | 'loading' | 'ok' | 'error'

defineProps<{
  title: string
  status: ConnectionStatus
  message: string
}>()

defineEmits<{
  retry: []
}>()

function statusLabel(status: ConnectionStatus): string {
  switch (status) {
    case 'loading':
      return '확인 중'
    case 'ok':
      return '정상 연결'
    case 'error':
      return '연결 실패'
    default:
      return '대기'
  }
}
</script>

<template>
  <section class="card" :data-status="status">
    <div class="row">
      <h2>{{ title }}</h2>
      <span class="badge">{{ statusLabel(status) }}</span>
    </div>
    <p class="msg">{{ message || '—' }}</p>
    <button
      v-if="status === 'error' || status === 'idle'"
      type="button"
      class="btn"
      @click="$emit('retry')"
    >
      다시 시도
    </button>
  </section>
</template>

<style scoped>
.card {
  background: var(--ods-color-white);
  border: 1px solid var(--ods-color-border);
  border-radius: var(--ods-radius-card);
  padding: var(--ods-card-padding);
}
.card[data-status='ok'] {
  border-color: var(--ods-color-secondary);
}
.card[data-status='error'] {
  border-color: var(--ods-color-danger);
}
.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ods-space-8);
}
h2 {
  margin: 0;
  font: var(--ods-font-headline);
  color: var(--ods-color-text);
}
.badge {
  font: var(--ods-font-caption);
  font-weight: 700;
  padding: var(--ods-space-4) var(--ods-space-8);
  border-radius: var(--ods-radius-badge);
  background: var(--ods-color-gray-100);
  color: var(--ods-color-gray-700);
}
.card[data-status='ok'] .badge {
  background: #e8f5e9;
  color: var(--ods-color-primary);
}
.card[data-status='error'] .badge {
  background: #fdecea;
  color: var(--ods-color-danger);
}
.msg {
  margin: var(--ods-space-12) 0 0;
  font: var(--ods-font-body-1);
  color: var(--ods-color-text-secondary);
  line-height: 1.45;
}
.btn {
  margin-top: var(--ods-space-12);
  min-height: var(--ods-control-height);
  width: 100%;
  border: none;
  border-radius: var(--ods-radius-button);
  background: var(--ods-color-primary);
  color: var(--ods-color-white);
  font: var(--ods-font-headline);
}
</style>
