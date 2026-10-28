# 주식 투자 대시보드 — Claude Code 작업 안내

사용자는 한국어를 쓰는 개인 투자자(웹 개발 첫 경험)입니다. 답변은 한국어로, 쉬운 설명. 비교·목록·단계·정리는 **항상 표로**(열 2~4개, 칸은 짧게 — 폰에서 읽음). 긴 문장 나열은 보기 어려워함.

## 구조
- 배포: GitHub Pages (`main` 브랜치 루트). `index.html` 한 파일이 전부입니다(HTML+CSS+JS, 파서까지 인라인). 빌드 도구 없음. push하면 1~2분 뒤 반영됩니다.
- 저장소: `index.html`(앱), `apps_script.gs.txt`(구글 Apps Script 서버 코드 — 사용자가 구글에 직접 붙여넣어 배포), `README.md`(기능별 사용법).
- 서버 없음. 데이터는 브라우저 localStorage + 구글 시트 + Apps Script 웹 앱.
- `index.html` 안의 화면별 함수: `renderHoldings`(보유 현황) `renderDetail`(상세 현황) `renderRS`(RS) `renderAna`(종목분석: 종목 직접 입력 `ana.base`, 보기 `ana.view` = 주가(기본, 안에 관련 종목 비교 `anaPeerControls`/`anaPeerChart` — 자동 추천) / 신용잔고 비교 `anaCreditData`) `renderTrades` `renderPrices`(시세·환율) `renderOpening`(연초 잔고) `renderAccounts`(계좌 관리) `renderTheme`. 진입점은 `render()`.

## 백테스트(`backtest/`, 대시보드와 분리)
- `backtest/index.html`(GitHub Pages `/backtest/`) + `backtest/apps_script.gs.txt`(대시보드와 다른 **새 Apps Script 프로젝트**, 자체 `SECRET_KEY`, 스크립트 속성 `NH_APP_KEY`/`NH_APP_SECRET`). 대시보드 코드·키와 공유하지 않음(테마 `portfolio-theme`만 읽음).
- Apps Script: `?universe=1` 나무 종목 마스터 `m_new_stock.mst`(CP949 237바이트, 코스피200=off168≠0, 코스닥150=off172 Y) → `[코드, 이름, 시장, k200, q150, 정지]`. `?candles=코드:시장,…&n=` 일봉(`/krstock/quote/v1/period`, gubun 1, 응답 `Output_1`), 30종목/요청, 220ms 간격. 나무에는 순위·조건검색 API가 없음.
- 전략(`cfg.strat`, 신호는 `signal(s, i)`): 이동평균(`ma`) / RSI(`rsi`, 와일더 평균 `rsi()`, 기간 `rp`, 매수 기준 `rlo` 아래→위 돌파, 매도 기준 `rhi` 위→아래). 종목 차트는 RSI일 때 아래에 RSI 그래프.
- 화면: 골든크로스 다음 날 시가 매수 / 데드크로스 다음 날 시가 매도, 손절 선택, 최대 보유 종목 수(빈자리는 20일 평균 거래대금 큰 순), 비용(수수료·매도세·슬리피지), 비교 = 첫날 상장 종목 동일금액 보유. 분할·배당락은 락구분코드가 있는 날 기준가÷전일종가로 과거 가격 보정(`prep`).
- 화면 저장: localStorage `backtest-sync` `backtest-cfg` `backtest-univ`(종목 목록, 업데이트 때만 새로), IndexedDB `backtest`(3판)/`bars` {c, gz(압축 일봉), n, last, at}. "실행"은 폰에 있는 시세로 계산하고 없거나 기간이 모자란 종목만 받음. "최신으로 업데이트"는 마지막 날짜 뒤만 받아 붙임(오늘 이미 받았으면 건너뜀, 16시 전에 받은 건 16시 뒤 한 번 더). 압축은 `CompressionStream`, 화면에 저장 용량·마지막 날짜와 "지우기". 구글 드라이브 창고 방식은 사용자 결정으로 쓰지 않음(2026-10-28).
- 미확인: 실제 나무 응답(Output_1 필드·순서, array_cnt 상한, 수정주가 여부, 기준가 의미), Apps Script `MS949` 디코딩. 두 Apps Script가 같은 앱키로 토큰을 따로 받으면 서로의 토큰을 무효로 만드는지 모름.

## 데이터 흐름
- 거래내역: 증권사 엑셀(삼성 종합 거래내역, 나무/NH HTML형 xls)을 올려 파싱. 이동평균 단가로 보유·실현손익·배당 계산(`replay`). 원화 원가는 거래일 환율(구글 시트 "환율" 탭)로 쌓음.
- 시세: 구글 시트 `StockCode` 게시 CSV(GOOGLEFINANCE). 종목코드/종목명/현재가/현지가/분류 열.
- 과거 시세(RS·분석·종목분석): Apps Script `?series=1`이 시트에서 GOOGLEFINANCE를 계산해 반환. 하루 한 번 브라우저에 캐시(`portfolio-rs-cache`).
- 코스피 신용잔고: Apps Script `?credit=1&refresh=1`이 금투협 FreeSIS 내부 조회 주소(`POST https://freesis.kofia.or.kr/meta/getMetaDataList.do`, 본문 `{"dmSearch":{"OBJ_NM":"STATSCU0100000070BO","tmpV1":"D","tmpV45":"yyyyMMdd","tmpV46":"yyyyMMdd","tmpV40":"1000000","tmpV41":"1"}}` — tmpV40/41(단위)이 없으면 값이 전부 null, 응답 `ds1[].TMPV1` 날짜·`TMPV3` 유가증권 신용거래융자 백만원)에서 받아 시트 "신용잔고" 탭에 쌓음(3시간 캐시, `setupCreditTrigger`로 매일 19시). 엑셀/CSV 업로드도 그대로 지원.
- 올해 기록 복원(보유 현황 > 기간별 추이 카드의 "올해 빠진 기록 복원", 별도 함수 `rhBuild`/`rhRecord`/`rhApply`/`rhUi`): 거래내역을 그날까지만 `replay`해 수량을 구하고 그날 종가(`?series=1`, 티커는 `rsTicker`)·환율(`fxAt`)을 곱함. 현금은 지금 잔고에서 그 뒤의 매매·배당·입출금을 거꾸로 뺌(환전은 거래내역에 없어 미반영). 이미 있는 날은 덮어쓰지 않고 `r:1`(복원)로 표시, 그래프에서 속이 빈 점. 시트 저장은 doPost `saveHistoryFill`(기록 탭 H열 "구분"=복원, 날짜순 정렬). 검증: 같은 식으로 오늘을 계산해 화면 총자산과 비교해 보여줌. 시세·티커가 빠진 종목은 `plan.fix`(지금 보유 중인 것 먼저)로 보여주고, 티커를 입력해 `rs.tk`에 저장 후 `rhBuild(true)`로 다시 계산. "빠진 티커 자동으로 채우기"(`rhGuess`)는 doPost `resolveTickers`(Apps Script `resolveTickers_`, Claude API; 확실하지 않으면 빈값)로 종목명→구글 티커를 받아 입력칸에만 채움(사용자 확인 후 적용).
- localStorage 키: `portfolio-data-v1` `portfolio-sheet-url` `portfolio-sync` `portfolio-history` `portfolio-ui` `portfolio-sectors` `portfolio-data-ts` `portfolio-theme` `portfolio-fxhist` `portfolio-rs` `portfolio-rs-cache` `portfolio-ana` `portfolio-credit` `portfolio-an`.

## Apps Script (`apps_script.gs.txt`)
- 설정값: `SECRET_KEY`, `SHEET_ID`(시세 시트), `AI_MODEL`, 스크립트 속성 `ANTHROPIC_API_KEY` `NH_APP_KEY` `NH_APP_SECRET`.
- 나무증권 Open API(NH PLUG, https://www.nhplug.com/llms.txt): `?nh=accounts` 계좌 목록, `?nh=trades&acct=&from=&to=` 종합거래내역(`/common/inquiry/v1/totalTransaction`, HTS 8203, 연속조회는 응답 헤더 `cts`/`cts_flag`). 토큰은 24시간 유효, 발급마다 보안 알림 → 스크립트 속성 `NH_TOKEN`/`NH_TOKEN_EXP`에 보관하고 만료·401일 때만 재발급. 주문 API는 `NH_PATHS` 허용 목록에 넣지 않음(조회 전용). 편집기에서 `testNh` 실행하면 적요별 건수·예시를 로그로 확인.
- `doGet` 파라미터: `history` `trades` `series` `credit` `peers` `nh` `fx`(없으면 동기화 데이터). `doPost`: `saveTrades` `deleteTrades` `saveCredit` `saveHistoryFill` `resolveTickers` 및 동기화 저장.
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
- 나무 API 거래내역: 구현 완료(2026-10-26). Apps Script `?nh=accounts`/`?nh=trades`(+`/gbstock/inquiry/v1/margin`으로 달러·엔 예수금 `fx`), 대시보드 계좌 관리 탭 "나무증권에서 바로 가져오기" → `nhApiToData` → `namooBuild(data, {api: true, fxCash})`(나무 엑셀 파서 `parseNamooRows`와 계산 공유) → 기존 "올린 파일 확인" 화면(`compareAccts`로 기존 계좌와 비교) → 저장 시 계좌 문서에 `nhAcct` 저장(다음부터 바로 갱신). 실제 계좌: 종합매매 1개만 사용(금현물·CMA는 거래 없음, 연금은 API에 없음 → 엑셀). 남은 확인: 실데이터로 첫 가져오기 결과를 기존 엑셀 데이터와 비교(종목명 표기, 해외 수수료 통화 — 외화 금액의 2% 넘으면 원화로 보고 뺌, 외화배당 금액이 세전인지).
- 종목분석·RS 5년 등 더 긴 기간 지원(과거 시세 조회 길이 확장).
