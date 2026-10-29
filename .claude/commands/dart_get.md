---
description: DART 공시·재무 자료를 dart/data에 받아 저장하고 짧게 요약 (예: /dart_get 삼성전자 SK하이닉스)
argument-hint: 종목 이름이나 코드 (여러 개, 선택: --years N)
---

DART 자료를 받아 저장하고 결과를 알려 줘.

1. Stock-dashboard 폴더에서 `python dart/dart_fetch.py $ARGUMENTS` 실행. 인자가 없으면 어떤 종목을 받을지 물어본다. "인증키가 없습니다"가 나오면 터미널에서 `python dart/dart_fetch.py --setkey`를 직접 실행하라고 안내한다(키를 채팅에 붙여넣게 하지 않는다).
2. 받은 종목마다 `dart/data/<코드>_<회사명>/summary.csv`의 최근 4개 분기와 `disclosures.json`의 최근 공시 5건(날짜, `report_nm`)을 읽는다.
3. 한국어로 짧게 보고: 최근 분기 지배주주 자본, BPS, 분기 매출·영업이익 흐름, 눈에 띄는 최근 공시, 저장된 폴더. 숫자는 조·억으로 바꾸고, 비어 있는 칸은 비었다고 말한다. 매수·매도 추천은 하지 않는다.
