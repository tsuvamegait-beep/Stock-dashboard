"""DART(금감원 전자공시 오픈API) 자료를 이 폴더(dart/data)에 저장합니다.

사용법 (Stock-dashboard 폴더에서):
    python dart/dart_fetch.py 삼성전자 SK하이닉스        # 종목 이름이나 6자리 코드, 여러 개 가능
    python dart/dart_fetch.py 005930 --years 5          # 최근 5년(기본 3년)

인증키: 처음 한 번 `python dart/dart_fetch.py --setkey`로 저장 → dart/.dart_key (또는 환경 변수 DART_API_KEY). 이 파일은 GitHub에 올라가지 않습니다.

저장되는 것 (dart/data/<코드>_<회사명>/):
    reports/<연도>_<분기>Q_<CFS|OFS>.json   보고서별 전체 재무제표 원본(fnlttSinglAcntAll)
    reports/<연도>_<분기>Q_shares.json      주식 총수(stockTotqySttus)
    summary.csv                             분기별 요약(자본·매출·영업이익·순이익·BPS 등, 원 단위)
    disclosures.json                        최근 1년 공시 목록
이미 받은 보고서는 다시 받지 않습니다(최근 2개 분기는 정정 공시가 있을 수 있어 다시 받음).
"""
import csv
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'data')
BASE = 'https://opendart.fss.or.kr/api/'
RPT = {1: '11013', 2: '11012', 3: '11014', 4: '11011'}  # 분기 → 보고서 코드(1분기·반기·3분기·사업)


def key():
    k = os.environ.get('DART_API_KEY', '').strip()
    p = os.path.join(HERE, '.dart_key')
    if not k and os.path.exists(p):
        k = open(p, encoding='utf-8').read().strip()
    if not re.fullmatch(r'[0-9a-fA-F]{40}', k):
        sys.exit('DART 인증키가 없습니다. 먼저 python dart/dart_fetch.py --setkey 로 키를 저장해 주세요.')
    return k


def get(api, **params):
    params['crtfc_key'] = KEY
    url = BASE + api + '?' + urllib.parse.urlencode(params)
    for i in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                body = r.read()
            break
        except Exception as e:
            if i == 2:
                raise
            time.sleep(2 * (i + 1))
    time.sleep(0.12)  # DART 요청 간격
    if api.endswith('.xml'):
        return body
    j = json.loads(body.decode('utf-8'))
    if j.get('status') == '013':
        return []  # 조회된 데이터 없음
    if j.get('status') != '000':
        raise RuntimeError('DART %s %s' % (j.get('status'), j.get('message')))
    return j.get('list') or []


def corp_list():
    """상장사 {종목코드: (고유번호, 회사명)}. dart/data/corp_codes.json에 하루 동안 보관."""
    p = os.path.join(DATA, 'corp_codes.json')
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < 86400:
        return {k: tuple(v) for k, v in json.load(open(p, encoding='utf-8')).items()}
    z = zipfile.ZipFile(io.BytesIO(get('corpCode.xml')))
    xml = z.read(z.namelist()[0]).decode('utf-8')
    out = {}
    for part in xml.split('</list>'):
        sc = re.search(r'<stock_code>\s*([0-9A-Z]{6})\s*</stock_code>', part)
        cc = re.search(r'<corp_code>(\d{8})</corp_code>', part)
        nm = re.search(r'<corp_name>([^<]*)</corp_name>', part)
        if sc and cc:
            out[sc.group(1)] = (cc.group(1), nm.group(1).strip() if nm else '')
    os.makedirs(DATA, exist_ok=True)
    json.dump(out, open(p, 'w', encoding='utf-8'), ensure_ascii=False)
    return out


def find(corps, q):
    q = q.strip().upper().replace(' ', '')
    if q in corps:
        return q
    names = [(c, n.replace(' ', '').upper()) for c, (_, n) in corps.items()]
    for test in (lambda n: n == q, lambda n: n.startswith(q), lambda n: q in n):
        hit = sorted([c for c, n in names if test(n)], key=lambda c: len(corps[c][1]))
        if hit:
            return hit[0]
    return None


def num(v):
    s = str(v if v is not None else '').replace(',', '').strip()
    return float(s) if re.fullmatch(r'-?\d+(\.\d+)?', s) else None


def pick(lst, sjs, ids, names):
    norm = lambda s: re.sub(r'[\s·ㆍ()（）]', '', s or '')
    for test in (lambda x: x.get('account_id') in ids, lambda x: norm(x.get('account_nm')) in names):
        for sj in sjs:
            for x in lst:
                if x.get('sj_div') == sj and test(x):
                    return x
    return None


def summarize(rows):
    """보고서 원본 → 분기 한 줄. 손익은 분기 3개월 값(사업보고서는 1년 − 3분기 누적)."""
    out = []
    by = {(r['y'], r['q']): r for r in rows}
    for r in sorted(rows, key=lambda r: (r['y'], r['q'])):
        lst = r['list']
        bs = lambda ids, names: num((pick(lst, ['BS'], ids, names) or {}).get('thstrm_amount'))
        def flow(ids, names):
            x = pick(lst, ['IS', 'CIS'], ids, names)
            if not x:
                return None
            a = num(x.get('thstrm_amount'))
            if r['q'] != 4:
                return a
            p3 = by.get((r['y'], 3))
            x3 = p3 and pick(p3['list'], ['IS', 'CIS'], ids, names)
            c3 = x3 and num(x3.get('thstrm_add_amount'))
            return a - c3 if a is not None and c3 is not None else None
        eqo = bs(['ifrs-full_EquityAttributableToOwnersOfParent'], ['지배기업의소유주에게귀속되는자본', '지배기업소유주지분', '지배기업의소유지분'])
        eq = bs(['ifrs-full_Equity'], ['자본총계'])
        sh = r.get('shares') or {}
        out_sh = sh['issued'] - (sh.get('treasury') or 0) if sh.get('issued') else None
        base = eqo if eqo is not None else eq
        out.append({
            '연도': r['y'], '분기': r['q'], '구분': r['fs'],
            '자산총계': bs(['ifrs-full_Assets'], ['자산총계']),
            '부채총계': bs(['ifrs-full_Liabilities'], ['부채총계']),
            '자본총계': eq, '지배주주자본': eqo,
            '현금성자산': bs(['ifrs-full_CashAndCashEquivalents'], ['현금및현금성자산']),
            '매출(분기)': flow(['ifrs-full_Revenue'], ['매출액', '수익매출액', '영업수익', '매출']),
            '영업이익(분기)': flow(['dart_OperatingIncomeLoss'], ['영업이익', '영업이익손실']),
            '지배순이익(분기)': flow(['ifrs-full_ProfitLossAttributableToOwnersOfParent'], ['지배기업의소유주에게귀속되는당기순이익']),
            '발행주식수': sh.get('issued'), '자기주식수': sh.get('treasury'),
            'BPS': round(base / out_sh) if base and out_sh else None,
        })
    return out


def fetch(code, corp, name, years):
    folder = os.path.join(DATA, '%s_%s' % (code, re.sub(r'[\\/:*?"<>|]', '', name)))
    rep = os.path.join(folder, 'reports')
    os.makedirs(rep, exist_ok=True)
    today = date.today()
    periods = [(y, q) for y in range(today.year - years, today.year + 1) for q in (1, 2, 3, 4)]
    recent = set(periods[-6:])  # 최근 분기는 정정될 수 있어 다시 받음
    rows, got, skip = [], 0, 0
    for y, q in periods:
        base = os.path.join(rep, '%d_%dQ' % (y, q))
        cached = [f for f in ('_CFS.json', '_OFS.json') if os.path.exists(base + f)]
        if cached and (y, q) not in recent:
            lst, fs = json.load(open(base + cached[0], encoding='utf-8')), cached[0][1:4]
            skip += 1
        else:
            fs, lst = 'CFS', get('fnlttSinglAcntAll.json', corp_code=corp, bsns_year=y, reprt_code=RPT[q], fs_div='CFS')
            if not lst:
                fs, lst = 'OFS', get('fnlttSinglAcntAll.json', corp_code=corp, bsns_year=y, reprt_code=RPT[q], fs_div='OFS')
            if not lst:
                continue  # 아직 안 나온 보고서
            json.dump(lst, open(base + '_' + fs + '.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            got += 1
        sp = base + '_shares.json'
        if os.path.exists(sp) and (y, q) not in recent:
            st = json.load(open(sp, encoding='utf-8'))
        else:
            st = get('stockTotqySttus.json', corp_code=corp, bsns_year=y, reprt_code=RPT[q])
            json.dump(st, open(sp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        tot = next((x for x in st if '합계' in (x.get('se') or '')), None)
        part = [x for x in st if re.search('보통|우선', x.get('se') or '')]
        s = lambda k: num(tot.get(k)) if tot else (sum(num(x.get(k)) or 0 for x in part) or None)
        rows.append({'y': y, 'q': q, 'fs': fs, 'list': lst, 'shares': {'issued': s('istc_totqy'), 'treasury': s('tesstk_co')}})
    summ = summarize(rows)
    if summ:
        with open(os.path.join(folder, 'summary.csv'), 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(summ[0].keys()))
            w.writeheader()
            w.writerows(summ)
    disc = get('list.json', corp_code=corp, bgn_de=(today - timedelta(days=365)).strftime('%Y%m%d'), end_de=today.strftime('%Y%m%d'), page_count=100)
    json.dump(disc, open(os.path.join(folder, 'disclosures.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    last = summ[-1] if summ else None
    print('  %s(%s): 보고서 %d개 새로 받음, %d개는 저장된 것 사용, 공시 %d건 → %s' % (name, code, got, skip, len(disc), os.path.relpath(folder, os.path.dirname(HERE))))
    if last:
        print('    최근 %d년 %d분기: 지배주주자본 %s · BPS %s' % (last['연도'], last['분기'], '{:,.0f}'.format(last['지배주주자본'] or last['자본총계'] or 0), '{:,}'.format(last['BPS']) if last['BPS'] else '–'))


if __name__ == '__main__':
    if '--setkey' in sys.argv:  # 키 저장: 입력한 글자는 화면에 안 보임
        import getpass
        k = getpass.getpass('DART 인증키(40자리)를 붙여넣고 Enter: ').strip()
        if not re.fullmatch(r'[0-9a-fA-F]{40}', k):
            sys.exit('40자리 인증키가 아닙니다. 다시 확인해 주세요.')
        open(os.path.join(HERE, '.dart_key'), 'w', encoding='utf-8').write(k + '\n')
        sys.exit('저장했습니다: dart/.dart_key (GitHub에는 올라가지 않습니다)')
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    years = 3
    if '--years' in sys.argv:
        years = int(sys.argv[sys.argv.index('--years') + 1])
        args = [a for a in args if a != str(years)]
    if not args:
        sys.exit(__doc__)
    KEY = key()
    corps = corp_list()
    print('DART 상장사 %d곳 목록 확인 (%s)' % (len(corps), datetime.now().strftime('%H:%M')))
    for q in args:
        code = find(corps, q)
        if not code:
            print('  "%s" 종목을 찾지 못했습니다' % q)
            continue
        try:
            fetch(code, corps[code][0], corps[code][1], years)
        except Exception as e:
            print('  %s 실패: %s' % (q, e))
