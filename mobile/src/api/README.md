# Analysis 미러 API 스텁

Private `mobile/src/api/` 런타임 클라이언트는 미러에 포함하지 않는다.

본 디렉터리 파일만 `mobile/src/api/` 로 복사되며:

- LAN URL·`.env`·인증정보 없음
- HTTP는 호출하지 않음 (`ApiClientError` 반환)
- 함수 시그니처·타입은 Private와 동일 (단독 `vue-tsc` import 해소)

실제 앱 실행은 Private 저장소에서만 수행한다.
