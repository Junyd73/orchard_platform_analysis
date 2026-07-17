<script setup lang="ts">
import MobileLayout from '@/layouts/MobileLayout.vue'
</script>

<template>
  <MobileLayout>
    <h1>주문관리</h1>
    <p class="desc">고객·품목·배송·입금상태 관리</p>
    <p class="note">준비중입니다. 다음 단계에서 구현됩니다.</p>
    <RouterLink class="btn" to="/">홈으로 돌아가기</RouterLink>
  </MobileLayout>
</template>

<style scoped>
h1 {
  margin: 8px 0 0;
  font-size: 22px;
  color: #1a202c;
}
.desc {
  margin: 8px 0 0;
  font-size: 16px;
  color: #4a5568;
}
.note {
  margin: 16px 0;
  padding: 14px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #eae7e2;
  color: #718096;
  font-size: 15px;
}
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  padding: 0 16px;
  border-radius: 10px;
  background: #2d5a27;
  color: #fff;
  text-decoration: none;
  font-size: 16px;
  font-weight: 600;
}
</style>
