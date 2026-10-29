"""관세청 수출입 통계(공공데이터포털 API)로 메모리 반도체 수출을 받아 이 폴더(trade/data)에 저장합니다.

사용법 (Stock-dashboard 폴더에서):
    python trade/trade_fetch.py --setkey      처음 한 번: 공공데이터포털 인증키 저장(일반 인증키 Decoding 값 권장)
    python trade/trade_fetch.py --probe       API가 실제로 어떻게 답하는지 확인(필드 이름·건수 출력)
    python trade/trade_fetch.py               메모리(HS 854232) 월별 수출을 최근 36개월 받아 저장
    python trade/trade_fetch.py --months 60   기간 바꾸기

저장: trade/data/memory_exports.csv (월, 국가, 수출금액 달러, 중량 kg, kg당 단가)
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


def fetch(n):
    ms = months_back(n)
    rows = []
    for i in range(0, len(ms), 12):  # 한 번에 1년까지
        a, b = ms[i], ms[min(i + 11, len(ms) - 1)]
        for c in COUNTRIES:
            code, msg, items, _ = call(NITEM, strtYymm=a, endYymm=b, hsSgn=MEMORY, cntyCd=c)
            if code not in ('', '00', '0', '000'):
                print('  %s %s~%s 실패: %s %s' % (c, a, b, code, msg))
                continue
            for it in items:
                ym = re.sub(r'\D', '', it.get('year', ''))
                if len(ym) != 6:
                    continue  # '총계' 같은 줄은 건너뜀
                rows.append({'월': ym, '국가': it.get('statCd') or c, '수출금액(달러)': float(it.get('expDlr') or 0), '수출중량(kg)': float(it.get('expWgt') or 0)})
        print('  %s~%s 받음' % (a, b))
    os.makedirs(DATA, exist_ok=True)
    rows.sort(key=lambda r: (r['월'], r['국가']))
    for r in rows:
        r['kg당 단가(달러)'] = round(r['수출금액(달러)'] / r['수출중량(kg)'], 1) if r['수출중량(kg)'] else ''
    p = os.path.join(DATA, 'memory_exports.csv')
    with open(p, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['월', '국가', '수출금액(달러)', '수출중량(kg)', 'kg당 단가(달러)'])
        w.writeheader(); w.writerows(rows)
    tot = {}
    for r in rows:
        t = tot.setdefault(r['월'], [0, 0]); t[0] += r['수출금액(달러)']; t[1] += r['수출중량(kg)']
    print('저장:', os.path.relpath(p, os.path.dirname(HERE)), '%d줄' % len(rows))
    for m in sorted(tot)[-6:]:
        print('  %s  메모리 수출 %.2f억 달러 · kg당 %.0f달러' % (m, tot[m][0] / 1e8, tot[m][0] / tot[m][1] if tot[m][1] else 0))


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
        fetch(n)
