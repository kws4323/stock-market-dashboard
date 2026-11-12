# Stock Dashboard

한국·미국 시장과 관심종목을 확인하는 GitHub Pages 대시보드입니다.

## 접속

https://kws4323.github.io/stock-market-dashboard/

## 시세와 새로고침

- GitHub Actions가 평일(UTC) 매시 17분·47분에 Yahoo Finance 데이터를 수집한 뒤 페이지를 배포합니다. GitHub 일정 실행은 지연 또는 누락될 수 있으며 실시간 시세가 아닙니다.
- 화면의 **저장 시세 새로고침**은 마지막으로 배포된 스냅샷을 다시 읽습니다. 버튼이 데이터 수집 작업을 즉시 실행하지는 않습니다.
- 즉시 수집: 저장소 Actions → Update market dashboard → Run workflow.
- 수집 시각과 각 종목의 시세 기준 시각을 별도로 표시합니다. 수집 실패 종목은 숫자를 만들어 표시하지 않습니다. 전체 수집 실패 시 기존 배포가 유지됩니다.
- 가격 차트의 마지막 일봉은 장중일 수 있습니다. 선물은 만기 교체 영향을 받을 수 있습니다. Yahoo Finance 데이터의 지연·누락·수정 가능성이 있습니다.

## 관심종목과 개인 메모

- 관심종목 목록과 메모는 현재 브라우저 localStorage에만 저장되며 GitHub로 전송하지 않습니다. 기기 간 동기화되지 않습니다.
- 수집 대상 종목은 `symbols.json`에 정의합니다. 목록에 없는 종목은 이 파일에 추가하고 workflow를 실행해야 시세를 볼 수 있습니다.
- 공개 저장소 및 공개 사이트입니다. 계좌 정보, API 비밀키, 보유 잔고는 넣지 마세요. 거래 기능은 없습니다.

## 구성

`site/index.html`: 반응형 화면 · `scripts/collect.py`: 실제 시세 수집 · `.github/workflows/pages.yml`: 수집 및 배포.

외국인·기관·개인 수급과 실적 캘린더 자동 연결은 포함하지 않습니다. 화면에서 공식 자료로 이동할 수 있습니다.

## 처음 설정

Settings → Pages → Build and deployment → Source를 **GitHub Actions**로 선택합니다.
