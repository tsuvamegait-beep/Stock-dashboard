# 석유 수급 모니터

주소: `https://tsuvamegait-beep.github.io/Stock-dashboard/oil/` (Stock-dashboard에 배포한 경우)

사진의 네 항목을 별도 페이지에서 확인합니다. **EIA가 직접 제공하는 것은 ULSD/WTI/Brent 현물 가격과 미국 디스틸레이트 재고입니다.** 러시아의 실제 디젤 수출 선적량과 Valero의 실현 정제마진은 EIA 지표가 아닙니다. 검증된 원문을 보고 시트에 입력하면 페이지에 함께 표시됩니다. 수출 쿼터나 EIA 크랙으로 실제 수출·VLO 공시 마진을 채우지 않습니다.

## 준비

1. [이 프로젝트의 Google Sheets](https://docs.google.com/spreadsheets/d/14mtcTipZQ4UPazQCS29rHLBjS3Fad5OsAsxJe3a8aI0/edit)를 엽니다. 새 문서와 여섯 탭은 이미 만들어 두었습니다. Apps Script에는 이 시트 ID가 기본값으로 들어 있습니다.
2. [EIA Open Data](https://www.eia.gov/opendata/register.php)에서 무료 API 키를 발급받습니다.
3. 새 [Google Apps Script](https://script.google.com/) 프로젝트를 만들고 [`apps_script.gs.txt`](./apps_script.gs.txt) 전체를 붙여넣습니다.
4. Apps Script **프로젝트 설정 → 스크립트 속성**에 `EIA_API_KEY`를 추가합니다. 키를 GitHub 파일에 쓰지 않습니다. 다른 시트를 사용하려면 `OIL_SHEET_ID` 속성으로 변경할 수 있습니다.
5. Apps Script 편집기에서 `setupOilMonitor`를 한 번 실행하고 권한을 허용합니다. 함수는 시트와 트리거만 만든 뒤 빠르게 끝납니다. 첫 EIA 수집은 약 1분 뒤 별도로 시작되며, 이후 **서울시간 매일 19시**에 갱신됩니다. Google 시간 기반 트리거는 지정 시각보다 다소 늦게 실행될 수 있습니다.
6. **배포 → 새 배포 → 웹 앱**, 실행 계정 **나**, 액세스 권한 **모든 사용자**를 선택합니다. `/exec`로 끝나는 URL을 복사합니다.
7. `oil/` 페이지의 **Google Sheets 연결**에 URL을 붙여넣습니다. 한 번 저장하면 해당 기기 브라우저에 남습니다. 모든 기기에서 자동 연결하려면 `index.html`의 `API_URL`에 공개 `/exec` URL을 넣어 GitHub에 올립니다. 이 URL은 읽기 전용 응답이며 EIA 키를 포함하지 않습니다.

## 시트 탭

- `Oil_Prices`: EIA의 최근 약 2년 ULSD·WTI·Brent 일별 현물 가격과 계산한 크랙. 같은 날짜에 ULSD와 WTI가 모두 있을 때만 기록합니다.
- `Oil_Inventory`: EIA의 약 7년 주간 디스틸레이트 재고와 가능한 경우 5년 동주간 평균. 원본 EIA 단위인 **천 배럴을 백만 배럴로 변환**합니다.
- `Oil_Daily`: 하루 한 행의 수집 스냅샷. 같은 날 다시 실행하면 해당 행을 고칩니다. 원자료 관측일과 수집일은 별도 열입니다.
- `Oil_Russia`: `observation_date`, `exports_kbd`, `source_url`, `published_date`, `note` 순서로 입력합니다. `exports_kbd`는 실제 디젤 수출량 **하루 천 배럴**입니다. 발표일과 원문 URL을 함께 넣습니다.
- `Oil_Valero`: `quarter_end`, `gulf_coast_margin_usd_bbl`, `source_url`, `published_date`, `note` 순서로 입력합니다. 실적 발표문에서 **Gulf Coast refining margin per barrel of throughput**을 확인합니다.
- `Oil_Log`: 매일 수집 성공·실패 기록입니다. 오류가 있으면 Apps Script의 실행 기록도 확인합니다.

러시아·Valero 값을 시트에 새로 입력한 후 `refreshOilData`를 실행하면 그날 `Oil_Daily` 행도 갱신됩니다. 페이지를 다시 불러오면 카드의 수동 입력값은 즉시 나타납니다. 비공개 구글 시트의 다른 탭 내용은 웹 앱 응답에 포함하지 않습니다.

## 데이터 정의와 갱신

| 항목 | 계산/원문 | 주기 |
| --- | --- | --- |
| ULSD–WTI 크랙 | EIA Gulf Coast ULSD `PET.EER_EPD2DXL0_PF4_RGC_DPG.D` × 42 − WTI `PET.RWTC.D`; Brent `PET.RBRTE.D`는 보조 | 미국 영업일 |
| 미국 디스틸레이트 재고 | EIA `PET.WDISTUS1.W` ÷ 1000 | 주간 |
| 러시아 디젤 수출 | 외부 원문을 확인한 실제 수출/선적 관측값 | 입력 자료에 따름 |
| VLO 실현 정제마진 | [Valero 실적 공시](https://www.valero.com/investors)의 Gulf Coast refining margin per barrel of throughput | 분기 |

EIA API 문서: <https://www.eia.gov/opendata/documentation.php>. 스크립트는 EIA 값이 실패하면 그날의 새 스냅샷을 쓰지 않고 `Oil_Log`에 오류를 남깁니다. 과거 시트 값과 각 지표의 관측일이 그대로 보이므로 수집 실패를 새 수치로 오인하지 않도록 했습니다.

## 확인 사항

브라우저에서 `/exec` URL을 직접 열었을 때 JSON `ok:true`와 `latest`가 나타나는지 확인합니다. `Oil_Daily`에 오늘 한 행이 생겼는지 확인합니다. 다음 날 `Oil_Log`에 자동 실행 기록이 추가되는지 확인합니다. Google Apps Script 배포와 시트·EIA 키 설정은 계정 소유자의 권한으로 완료해야 합니다.
