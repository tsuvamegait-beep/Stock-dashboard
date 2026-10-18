# 주식 투자 대시보드 — Claude Code 작업 안내

사용자는 한국어를 쓰는 개인 투자자(웹 개발 첫 경험)입니다. 답변은 한국어로, 쉬운 단계별 설명, 모바일에서 읽으므로 표보다 문장 위주로 합니다.

## 구조
- 배포: GitHub Pages (`main` 브랜치 루트). `index.html` 한 파일이 전부입니다(HTML+CSS+JS, 파서까지 인라인). 빌드 도구 없음. push하면 1~2분 뒤 반영됩니다.
- 저장소: `index.html`(앱), `apps_script.gs.txt`(구글 Apps Script 서버 코드 — 사용자가 구글에 직접 붙여넣어 배포), `README.md`(기능별 사용법).
- 서버 없음. 데이터는 브라우저 localStorage + 구글 시트 + Apps Script 웹 앱.
- `index.html` 안의 화면별 함수: `renderHoldings`(보유 현황) `renderDetail`(상세 현황) `renderRS`(RS) `renderAna`(종목분석: 주가+코스피 신용잔고, 아래쪽 `renderPeers` 관련 종목 비교+자동 추천 — 예전 "분석" 탭을 합침) `renderTrades` `renderPrices`(시세·환율) `renderOpening`(연초 잔고) `renderAccounts`(계좌 관리) `renderTheme`. 진입점은 `render()`.

## 데이터 흐름
- 거래내역: 증권사 엑셀(삼성 종합 거래내역, 나무/NH HTML형 xls)을 올려 파싱. 이동평균 단가로 보유·실현손익·배당 계산(`replay`). 원화 원가는 거래일 환율(구글 시트 "환율" 탭)로 쌓음.
- 시세: 구글 시트 `StockCode` 게시 CSV(GOOGLEFINANCE). 종목코드/종목명/현재가/현지가/분류 열.
- 과거 시세(RS·분석·종목분석): Apps Script `?series=1`이 시트에서 GOOGLEFINANCE를 계산해 반환. 하루 한 번 브라우저에 캐시(`portfolio-rs-cache`).
- 코스피 신용잔고: Apps Script `?credit=1&refresh=1`이 금투협 FreeSIS 내부 조회 주소(`POST https://freesis.kofia.or.kr/meta/getMetaDataList.do`, 본문 `{"dmSearch":{"OBJ_NM":"STATSCU0100000070BO","tmpV1":"D","tmpV45":"yyyyMMdd","tmpV46":"yyyyMMdd"}}`, 응답 `ds1[].TMPV1` 날짜·`TMPV3` 유가증권 신용거래융자 백만원)에서 받아 시트 "신용잔고" 탭에 쌓음(3시간 캐시, `setupCreditTrigger`로 매일 19시). 엑셀/CSV 업로드도 그대로 지원.
- localStorage 키: `portfolio-data-v1` `portfolio-sheet-url` `portfolio-sync` `portfolio-history` `portfolio-ui` `portfolio-sectors` `portfolio-data-ts` `portfolio-theme` `portfolio-fxhist` `portfolio-rs` `portfolio-rs-cache` `portfolio-ana` `portfolio-credit` `portfolio-an`.

## Apps Script (`apps_script.gs.txt`)
- 설정값: `SECRET_KEY`, `SHEET_ID`(시세 시트), `AI_MODEL`, 스크립트 속성 `ANTHROPIC_API_KEY`.
- `doGet` 파라미터: `history` `trades` `series` `credit` `peers` `fx`(없으면 동기화 데이터). `doPost`: `saveTrades` `deleteTrades` `saveCredit` 및 동기화 저장.
- 코드를 바꾸면 사용자가 Apps Script에 다시 붙여넣고 "배포 관리 → 새 버전"으로 배포해야 반영됩니다(주소가 바뀌는 "새 배포"는 금지).
- 비밀번호·웹 앱 주소·API 키는 저장소에 넣지 않습니다(브라우저 localStorage / 스크립트 속성에만).

## 지켜야 할 것
- 시트의 "거래내역" 탭은 공개(게시)하지 않습니다. 시세 시트만 게시 CSV로 공개.
- 화면 갱신(`render`)은 텍스트 입력에 포커스가 있으면 미뤄집니다. 입력 후 바로 다시 그리려면 `blur()` 후 `render()`.
- 폰(Samsung Internet)의 강제 다크모드 대응으로 밝은 테마는 `color-scheme: only light`.
- 커밋 메시지는 한국어로 짧게.

## 테스트 방법
- Playwright(chromium)로 `file://.../index.html`을 열고, SheetJS(xlsx)·docs.google.com·script.google.com 요청은 `route`로 가짜 응답 처리. 강제 다크 재현은 `--blink-settings=forceDarkModeEnabled=true`.
- 실제 구글 서비스(GOOGLEFINANCE, Apps Script)에 대한 호출은 확인하지 못한 부분이 있습니다(아래).

## 확인되지 않은 것 / 알려진 한계
- 지수·종목 티커의 GOOGLEFINANCE 지원: `KRX:KOSPI` `INDEXSP:.INX` `INDEXNASDAQ:.IXIC` `INDEXNASDAQ:NDX` `INDEXDJX:.DJI` `INDEXNASDAQ:SOX` `INDEXNIKKEI:NI225`, 신규 KRX 영문 포함 코드(예: 0167A0), 관련 종목 비교의 업종표(`PEER_GROUPS`) 티커 전부.
- Apps Script의 `fx`/`series`/`peers`(Claude API 호출) 엔드포인트는 모의 테스트만 했고 실서비스 확인은 사용자 쪽.
- 외부 환율은 일 종가(증권사 적용환율 아님). 보유 종목 표의 손익 열은 현지통화. RS는 배당·환율 제외. 과거 시세 조회는 최대 약 400일(1년).
- 계좌별 선택 시 기간별 추이 그래프는 전체 합계만 저장돼서 숨김.
- 연금 매입금액이 나무증권 앱과 약 2,071,539원 차이: 조선TOP3플러스만 연초 잔고 평균단가에 의존. 앱의 조선 평균단가를 받으면 "연초 잔고" 탭의 평균단가로 맞출 수 있음(미확정).

## 다음 할 일(논의 중)
- 신용잔고 자동 수집은 구현됨. 확인 안 된 것: 구글(Apps Script) 서버에서 FreeSIS 접속이 막히지 않는지, FreeSIS가 짧은 시간 여러 요청을 보내면 잠시 차단하는지(PC에서 10여 회 요청 후 접속이 끊긴 적 있음). 막히면 대안은 GitHub Actions로 `credit.csv` 커밋.
- 종목분석·RS 5년 등 더 긴 기간 지원(과거 시세 조회 길이 확장).
