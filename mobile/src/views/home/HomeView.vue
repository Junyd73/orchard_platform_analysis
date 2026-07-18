<script setup lang="ts">
import { onMounted } from 'vue'
import { storeToRefs } from 'pinia'

import MenuCard from '@/components/MenuCard.vue'
import StatusCard from '@/components/StatusCard.vue'
import MobileLayout from '@/layouts/MobileLayout.vue'
import { useAppStore } from '@/composables/stores/app'

const store = useAppStore()
const {
  connectionStatus,
  connectionMessage,
  farm,
  siteCount,
  farmError,
  farmCd,
} = storeToRefs(store)

onMounted(() => {
  void store.refreshAll()
})
</script>

<template>
  <MobileLayout>
    <div class="stack">
      <StatusCard
        title="서버 연결 상태"
        :status="connectionStatus"
        :message="connectionMessage"
        @retry="store.refreshAll()"
      />

      <section class="card">
        <h2>농장 정보</h2>
        <p v-if="connectionStatus === 'loading'" class="muted">불러오는 중…</p>
        <p v-else-if="farmError" class="error">{{ farmError }}</p>
        <dl v-else-if="farm" class="farm">
          <div>
            <dt>농장명</dt>
            <dd>{{ farm.farm_nm || farmCd }}</dd>
          </div>
          <div>
            <dt>농장주</dt>
            <dd>{{ farm.owner_nm || '—' }}</dd>
          </div>
          <div>
            <dt>주소</dt>
            <dd>{{ farm.address || '—' }}</dd>
          </div>
          <div>
            <dt>등록 필지 수</dt>
            <dd>{{ siteCount }}곳</dd>
          </div>
        </dl>
        <p v-else class="muted">표시할 농장 정보가 없습니다.</p>
      </section>

      <section>
        <h2 class="section-title">모바일 메뉴</h2>
        <div class="menu-grid">
          <MenuCard
            title="생육관찰"
            description="사진·병해충·생육상태 기록"
            to="/observation"
          />
          <MenuCard
            title="영농일지"
            description="작업·인력·경비 현장 입력"
            to="/work-log"
          />
          <MenuCard
            title="주문관리"
            description="고객·품목·배송·입금상태 관리"
            to="/orders"
          />
        </div>
      </section>

      <p class="footer-note">
        현재는 개발 테스트 버전입니다. 같은 Wi-Fi에서만 접속할 수 있습니다.
      </p>
    </div>
  </MobileLayout>
</template>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.card {
  background: #fff;
  border: 1px solid #eae7e2;
  border-radius: 14px;
  padding: 16px;
}
.card h2,
.section-title {
  margin: 0 0 10px;
  font-size: 16px;
  color: #2d3748;
}
.farm {
  margin: 0;
  display: grid;
  gap: 10px;
}
.farm div {
  display: grid;
  gap: 2px;
}
.farm dt {
  font-size: 12px;
  color: #718096;
}
.farm dd {
  margin: 0;
  font-size: 16px;
  color: #1a202c;
  line-height: 1.4;
  word-break: break-word;
}
.menu-grid {
  display: grid;
  gap: 10px;
}
.muted {
  margin: 0;
  color: #718096;
  font-size: 15px;
}
.error {
  margin: 0;
  color: #c53030;
  font-size: 15px;
}
.footer-note {
  margin: 8px 0 0;
  font-size: 13px;
  color: #a0aec0;
  line-height: 1.45;
  text-align: center;
}
</style>
