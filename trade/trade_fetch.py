"""관세청 수출입 통계(공공데이터포털 API)로 메모리 반도체 수출을 받아 이 폴더(trade/data)에 저장합니다.

사용법 (Stock-dashboard 폴더에서):
    python trade/trade_fetch.py --setkey      처음 한 번: 공공데이터포털 인증키 저장(일반 인증키 Decoding 값 권장)
    python trade/trade_fetch.py --probe       API가 실제로 어떻게 답하는지 확인(필드 이름·건수 출력)
    python trade/trade_fetch.py               메모리(HS 854232) 월별 수출을 최근 36개월 받아 저장
    python trade/trade_fetch.py --months 60   기간 바꾸기

저장: trade/data/memory_items.csv (월, 세부 품목, 수출 달러·중량·kg당 단가) — 관세청_품목별 수출입실적(GW)
      trade/data/memory_exports_sido.csv (월, 시도, 메모리 수출 천 달러, 건수) — 관세청_시도별 품목별 수출입실적(GW)
인증키는 trade/.data_key에만 저장되고 GitHub에 올라가지 않습니다.
"""
import csv
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'data')
KEYF = os.path.join(HERE, '.data_key')
NITEM = 'https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList'
SIGUNGU = 'https://apis.data.go.kr/1220000/sigunguperprlstperacrs/getSigunguperprlstperacrsList'
MEMORY = '854232'  # 메모리 집적회로
# 메모리 수출이 큰 나라(국가코드가 꼭 필요한 API라서 나라별로 받아 더함)
COUNTRIES = ['CN', 'HK', 'TW', 'VN', 'US', 'JP', 'SG', 'PH', 'MY', 'IN', 'MX', 'DE', 'TH', 'IE', 'BR', 'CZ', 'HU', 'IL', 'GB', 'NL']


def key():
    if not os.path.exists(KEYF):
        sys.exit('인증키가 없습니다. 먼저 python trade/trade_fetch.py --setkey 로 저장해 주세요.')
    k = open(KEYF, encoding='utf-8').read().strip()
    return urllib.parse.unquote(k)  # Encoding 키를 넣었어도 한 번 풀어서 씀


def call(url, **params):
    params['serviceKey'] = key()
    full = url + '?' + urllib.parse.urlencode(params)
    for i in range(3):
        try:
            with urllib.request.urlopen(full, timeout=30) as r:
                body = r.read()
            break
        except Exception:
            if i == 2:
                raise
            time.sleep(2 * (i + 1))
    time.sleep(0.15)
    text = body.decode('utf-8', errors='replace')
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        raise RuntimeError('XML이 아닌 응답: ' + text[:200])
    code = (root.findtext('.//resultCode') or root.findtext('.//returnReasonCode') or '').strip()
    msg = (root.findtext('.//resultMsg') or root.findtext('.//returnAuthMsg') or root.findtext('.//errMsg') or '').strip()
    items = [{c.tag: (c.text or '').strip() for c in it} for it in root.iter('item')]
    return code, msg, items, text


def months_back(n):
    t = date.today()
    y, m = t.year, t.month - 1  # 이번 달은 아직 없음
    out = []
    for _ in range(n):
        if m == 0:
            y, m = y - 1, 12
        out.append('%d%02d' % (y, m))
        m -= 1
    return sorted(out)


def probe():
    ym = months_back(3)[0]
    print('== 확인 기준 월', ym)
    tries = [('품목별 국가별, 6자리, 중국', NITEM, dict(strtYymm=ym, endYymm=ym, hsSgn=MEMORY, cntyCd='CN')),
             ('품목별 국가별, 6자리, 국가 빈칸', NITEM, dict(strtYymm=ym, endYymm=ym, hsSgn=MEMORY, cntyCd='')),
             ('품목별 국가별, 4자리 8542, 중국', NITEM, dict(strtYymm=ym, endYymm=ym, hsSgn='8542', cntyCd='CN')),
             ('시군구별, 경기(41)', SIGUNGU, dict(strtYymm=ym, endYymm=ym, HsSgn=MEMORY, sidoCd='41')),
             ('시군구별, 충북(43)', SIGUNGU, dict(strtYymm=ym, endYymm=ym, HsSgn=MEMORY, sidoCd='43'))]
    for name, url, p in tries:
        try:
            code, msg, items, text = call(url, **p)
            print('\n--', name, '| 결과', code, msg, '| 줄 수', len(items))
            if items:
                print('   필드:', ', '.join(items[0].keys()))
                for it in items[:4]:
                    print('  ', it)
            else:
                print('   응답 앞부분:', re.sub(r'\s+', ' ', text)[:300])
        except Exception as e:
            print('\n--', name, '| 실패:', e)


SIDO_API = 'https://apis.data.go.kr/1220000/sidoitemtrade/getSidoitemtradeList'  # 관세청_시도별 품목별 수출입실적(GW)
SIDO = {'11': '서울', '26': '부산', '27': '대구', '28': '인천', '29': '광주', '30': '대전', '31': '울산', '36': '세종', '41': '경기', '42': '강원', '51': '강원',
        '43': '충북', '44': '충남', '45': '전북', '52': '전북', '46': '전남', '47': '경북', '48': '경남', '50': '제주'}
num = lambda v: float(str(v or '0').replace(',', '').strip() or 0)


def sido_exp(a, b, sd):
    """시도·기간의 메모리 수출(천 달러), 수출 건수. 여러 달을 물으면 합계만 옴"""
    code, msg, items, _ = call(SIDO_API, strtYymm=a, endYymm=b, hsSgn=MEMORY, sidoCd=sd)
    it = next((x for x in items if x.get('hsSgn')), None)
    return (num(it.get('expUsdAmt')), num(it.get('expLnCnt'))) if it else (0.0, 0.0)


def fetch(n):
    """시도별 메모리 수출을 달마다 받아 trade/data/memory_exports_sido.csv에 저장(이미 받은 달은 다시 받지 않음, 최근 2개월은 다시 받음)"""
    ms = months_back(n)
    p = os.path.join(DATA, 'memory_exports_sido.csv')
    have = {}
    if os.path.exists(p):
        for r in csv.DictReader(open(p, encoding='utf-8-sig')):
            have[(r['월'], r['시도코드'])] = r
    # 메모리 수출이 있는 시도만 고름(최근 1년 합계로 판단)
    print('메모리 수출이 있는 시도 찾는 중…')
    tot, keep = {}, []
    for sd in SIDO:
        tot[sd] = sido_exp(ms[-12], ms[-1], sd)[0]
    allv = sum(tot.values()) or 1
    keep = [sd for sd, v in tot.items() if v / allv > 0.001]
    print('  ' + ', '.join('%s %.1f%%' % (SIDO[sd], tot[sd] / allv * 100) for sd in sorted(keep, key=lambda x: -tot[x])))
    rows, fresh = [], 0
    for m in ms:
        for sd in keep:
            r = have.get((m, sd))
            if r and m not in ms[-2:]:
                rows.append(r); continue
            e, c = sido_exp(m, m, sd); fresh += 1
            rows.append({'월': m, '시도코드': sd, '시도': SIDO[sd], '수출(천달러)': '%d' % e, '수출건수': '%d' % c})
        print('  %s 완료' % m)
    os.makedirs(DATA, exist_ok=True)
    with open(p, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['월', '시도코드', '시도', '수출(천달러)', '수출건수'])
        w.writeheader(); w.writerows(rows)
    print('저장: %s (%d줄, 새로 받은 것 %d건)' % (os.path.relpath(p, os.path.dirname(HERE)), len(rows), fresh))
    by = {}
    for r in rows:
        by[r['월']] = by.get(r['월'], 0) + float(r['수출(천달러)'])
    for m in sorted(by)[-6:]:
        print('  %s  메모리 수출 %.1f억 달러' % (m, by[m] / 1e5))



ITEM_API = 'https://apis.data.go.kr/1220000/Itemtrade/getItemtradeList'  # 관세청_품목별 수출입실적(GW): 10자리 세부 품목, 금액(달러)·중량(kg), 여러 달이면 달마다 나옴


def fetch_items(n):
    """메모리 세부 품목(디램·플래시·복합구조칩 등) 월별 수출 금액·중량·kg당 단가 → trade/data/memory_items.csv"""
    ms = months_back(n)
    rows = []
    for i in range(0, len(ms), 12):  # 한 번에 1년까지
        a, b = ms[i], ms[min(i + 11, len(ms) - 1)]
        code, msg, items, _ = call(ITEM_API, strtYymm=a, endYymm=b, hsSgn=MEMORY)
        for it in items:
            ym = re.sub(r'\D', '', it.get('year', ''))
            if len(ym) != 6 or not it.get('hsCode', '').isdigit():
                continue  # 총계 줄
            e, w = num(it.get('expDlr')), num(it.get('expWgt'))
            rows.append({'월': ym, 'HS': it['hsCode'], '품목': it.get('statKor', ''), '수출(달러)': '%d' % e, '수출중량(kg)': '%d' % w,
                         'kg당 단가(달러)': '%.0f' % (e / w) if w else ''})
        print('  품목별 %s~%s %d줄' % (a, b, len(items)))
    os.makedirs(DATA, exist_ok=True)
    p = os.path.join(DATA, 'memory_items.csv')
    with open(p, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['월', 'HS', '품목', '수출(달러)', '수출중량(kg)', 'kg당 단가(달러)'])
        w.writeheader(); w.writerows(sorted(rows, key=lambda r: (r['월'], r['HS'])))
    print('저장: %s (%d줄)' % (os.path.relpath(p, os.path.dirname(HERE)), len(rows)))


if __name__ == '__main__':
    if '--setkey' in sys.argv:
        import getpass
        k = getpass.getpass('공공데이터포털 일반 인증키를 붙여넣고 Enter(화면에 안 보임): ').strip()
        if len(k) < 20:
            sys.exit('인증키가 너무 짧습니다. 다시 확인해 주세요.')
        open(KEYF, 'w', encoding='utf-8').write(k + '\n')
        sys.exit('저장했습니다: trade/.data_key (GitHub에는 올라가지 않습니다)')
    if '--probe' in sys.argv:
        probe()
    else:
        n = int(sys.argv[sys.argv.index('--months') + 1]) if '--months' in sys.argv else 36
        fetch_items(n)
        fetch(n)
