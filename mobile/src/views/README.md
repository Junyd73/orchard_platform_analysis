# Feature modules

기능별 화면·로직을 분리한다.

| Feature | ODS/SCR | 상태 |
|---------|---------|------|
| `home/` | 홈(연결·농장 스모크) | Step-08 골격 |
| `observation/` | SCR-001~003 생육관찰 | 플레이스홀더 → Project A |
| `work-log/` | 영농일지 | 준비중 |
| `orders/` | 주문관리 | 준비중 |

규칙: Feature는 `components/ods` 와 `shared` 를 사용하고, API는 `src/api` 를 경유한다.
