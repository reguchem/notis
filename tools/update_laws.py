"""기후에너지환경부(+화학물질안전원, 국립환경과학원)의 최근 법령 동향을 모아 data/laws.js 를 만듭니다.
GitHub Actions(.github/workflows/update-notices.yml)가 매일 실행합니다. 직접 실행: python tools/update_laws.py

자료 출처
 1. 입법예고   : 국민참여입법센터 (opinion.lawmaking.go.kr/gcom/ogLmPp) - 예고 시작일 기준
 2. 행정예고   : 국민참여입법센터 (opinion.lawmaking.go.kr/gcom/admpp)  - 예고 시작일 기준
 3. 법령 공포·시행·시행예정 : 국가법령정보센터 최신법령 (law.go.kr/LSW/nwRvsLsPop.do 등)
 4. 고시·훈령·예규 : 기후에너지환경부 누리집 (mcee.go.kr/home/web/law/list.do?typeCode=admrul) - 발령일자 기준
"""
import datetime as dt, html, json, os, re, sys, time, urllib.parse, urllib.request
from html.parser import HTMLParser

DAYS = 3                     # 최근 며칠
AHEAD = 7                    # 시행예정: 앞으로 며칠 안에 시행되는 법령
ORGS = ['기후에너지환경부', '화학물질안전원', '국립환경과학원']
MINISTRY_CODE = '1482000'    # 기후에너지환경부 기관코드
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'laws.js')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
OPINION = 'https://opinion.lawmaking.go.kr'
LAW = 'https://www.law.go.kr/LSW/'
MCEE = 'https://www.mcee.go.kr'

def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9'})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception as e:
            print(f'  재시도 {i + 1}/{tries}: {url} ({e})', file=sys.stderr)
            time.sleep(3 * (i + 1))
    raise RuntimeError(f'접속 실패: {url}')

class Tables(HTMLParser):
    """문서 안의 표를 [{'head': [...], 'rows': [[{'text','href','title'}, ...], ...]}] 로 바꿉니다."""
    BREAK = {'p', 'br', 'div', 'li'}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.t, self.row, self.cell, self.in_head = [], None, None, None, False
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'table':
            self.t = {'head': [], 'rows': []}
            self.tables.append(self.t)
        elif self.t is None:
            return
        elif tag == 'thead':
            self.in_head = True
        elif tag == 'tr':
            self.row = []
        elif tag in ('td', 'th') and self.row is not None:
            self.cell = {'text': '', 'href': '', 'title': '', 'head': tag == 'th' or self.in_head}
            self.row.append(self.cell)
        elif tag == 'a' and self.cell is not None and not self.cell['href']:
            self.cell['href'] = a.get('href') or ''
            self.cell['title'] = a.get('title') or ''
        elif tag in self.BREAK and self.cell is not None:
            self.cell['text'] += '\n'
    def handle_endtag(self, tag):
        if self.t is None:
            return
        if tag == 'thead':
            self.in_head = False
        elif tag in ('td', 'th'):
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            cells = [dict(c, text=clean(c['text'])) for c in self.row]
            if cells and all(c['head'] for c in cells):
                self.t['head'] = [c['text'] for c in cells]
            elif cells:
                self.t['rows'].append(cells)
            self.row = None
        elif tag == 'table':
            self.t = None
    def handle_data(self, data):
        if self.cell is not None:
            self.cell['text'] += data

def clean(s):
    lines = [re.sub(r'\s+', ' ', l.replace('\xa0', ' ')).strip() for l in s.split('\n')]
    return '\n'.join(l for l in lines if l)

def table(page, must):
    p = Tables()
    p.feed(page)
    for t in p.tables:
        if any(must in h for h in t['head']):
            return t['rows']
    return []

def ymd(s):
    """'2026. 9. 30.' / '2026-09-30' → date"""
    m = re.search(r'(\d{4})\D+(\d{1,2})\D+(\d{1,2})', s or '')
    return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None

def iso(d):
    return d.isoformat() if d else ''

# 1. 입법예고 ---------------------------------------------------------------
def legislative(since, today):
    q = urllib.parse.urlencode({'cptOfiOrgCd': MINISTRY_CODE, 'stYd': since.strftime('%Y%m%d'), 'edYd': today.strftime('%Y%m%d'), 'isOgYn': 'Y', 'opYn': 'Y'})
    out = []
    for page in range(1, 6):
        rows = table(get(f'{OPINION}/gcom/ogLmPp?{q}&pageIndex={page}'), '법령 제명')
        rows = [r for r in rows if len(r) >= 6]
        for r in rows:
            org = r[2]['text'].split('\n')
            period = r[4]['text'].replace('\n', ' ')
            m = re.match(r'(/gcom/ogLmPp/\d+)', r[1]['href'])
            title = r[1]['title'] or r[1]['text']
            kind = r[1]['text'].replace(title, '').strip()
            out.append({'title': title, 'url': OPINION + m.group(1) if m else '', 'kind': kind,
                        'org': org[0], 'lawType': org[1].strip('()') if len(org) > 1 else '', 'field': r[3]['text'].replace('\n', ', '),
                        'period': period, 'start': iso(ymd(period)), 'remain': r[5]['text']})
        if len(rows) < 10:
            break
    return out

# 2. 행정예고 ---------------------------------------------------------------
def administrative(since, today):
    out = []
    for org in ORGS:
        q = urllib.parse.urlencode({'stYd': since.strftime('%Y%m%d'), 'edYd': today.strftime('%Y%m%d'), 'asndOfiNm': org})
        for page in range(1, 6):
            rows = table(get(f'{OPINION}/gcom/admpp?{q}&pageIndex={page}'), '행정예고명')
            rows = [r for r in rows if len(r) >= 5]
            for r in rows:
                agency = r[3]['text']
                if org not in agency:
                    continue
                m = re.match(r'(/gcom/admpp/\d+)', r[1]['href'])
                title = re.sub(r'^(진행|종료)\s*', '', re.sub(r'\s*이동$', '', r[1]['title'] or r[1]['text']).strip())
                if m and (title.endswith('...') or title.endswith('…')):
                    full = re.search(r"else\s*\{\s*document\.title\s*=\s*'(.*?)'\s*\+", get(OPINION + m.group(1)))
                    title = html.unescape(full.group(1)).strip() if full else title
                period = r[4]['text'].replace('\n', ' ')
                out.append({'title': title, 'url': OPINION + m.group(1) if m else '', 'ruleType': r[2]['text'],
                            'org': re.sub(r'\s*\(.*$', '', agency), 'notice': (re.search(r'\((.*)\)', agency) or [None, ''])[1],
                            'period': period, 'start': iso(ymd(period))})
            if len(rows) < 20:
                break
    out.sort(key=lambda x: x['start'], reverse=True)
    return out

# 3. 법령 공포·시행·시행예정 ------------------------------------------------
def laws(since, today):
    found = {}
    pages = [('공포', 'nwRvsLsPop.do', lambda pub, ef: pub >= since, lambda pub, ef: pub),
             ('시행', 'nwEfLsPop.do', lambda pub, ef: since <= ef <= today, lambda pub, ef: ef),
             ('시행예정', 'efLsPop.do', lambda pub, ef: today < ef <= today + dt.timedelta(days=AHEAD), lambda pub, ef: ef)]
    for label, path, keep, sortdate in pages:
        for pg in range(1, 6):
            rows = [r for r in table(get(f'{LAW}{path}?cptOfi={MINISTRY_CODE}&pg={pg}'), '법령명') if len(r) >= 8]
            stop = not rows
            for r in rows:
                pub, ef = ymd(r[6]['text']), ymd(r[7]['text'])
                if not pub or not ef:
                    continue
                if not keep(pub, ef):
                    # 공포·시행 목록은 날짜 역순, 시행예정 목록은 날짜 순
                    if (label != '시행예정' and sortdate(pub, ef) < since) or (label == '시행예정' and ef > today + dt.timedelta(days=AHEAD)):
                        stop = True
                    continue
                m = re.search(r'lsiSeq=(\d+)', r[1]['href'])
                key = (m.group(1) if m else r[1]['text'], iso(ef))
                item = found.setdefault(key, {
                    'title': re.sub(r'\s*팝업으로 이동$', '', r[1]['title']) or r[1]['text'],
                    'url': f'{LAW}lsInfoP.do?lsiSeq={m.group(1)}&viewCls=lsRvsDocInfoR' if m else '',
                    'org': r[2]['text'], 'revision': r[3]['text'], 'lawType': r[4]['text'], 'number': r[5]['text'],
                    'promulgated': iso(pub), 'effective': iso(ef), 'tags': []})
                if label not in item['tags']:
                    item['tags'].append(label)
            if stop:
                break
    return sorted(found.values(), key=lambda x: (x['promulgated'], x['effective']), reverse=True)

# 4. 고시·훈령·예규 ---------------------------------------------------------
def admin_rules(since, today):
    out = []
    for offset in range(0, 200, 10):
        url = f'{MCEE}/home/web/law/list.do?maxPageItems=10&maxIndexPages=10&menuId=71&condition.typeCode=admrul&pagerOffset={offset}'
        rows = [r for r in table(get(url), '행정규칙명') if len(r) >= 5]
        if not rows:
            break
        older = True
        for r in rows:
            d = ymd(r[2]['text'])
            if not d or d < since:
                continue
            older = False
            if not any(o in r[4]['text'] for o in ORGS):
                continue
            m = re.search(r'lawSeq=(\d+)', r[1]['href'])
            out.append({'title': r[1]['title'] or r[1]['text'], 'date': iso(d), 'number': r[3]['text'], 'org': r[4]['text'],
                        'url': f'{MCEE}/home/web/law/read.do?menuId=71&typeCode=admrul&condition.typeCode=admrul&lawSeq={m.group(1)}' if m else ''})
        if older:
            break
    return out

def main():
    today = (dt.datetime.utcnow() + dt.timedelta(hours=9)).date()
    since = today - dt.timedelta(days=DAYS)
    data = {'updated': iso(today), 'from': iso(since), 'to': iso(today), 'ahead': AHEAD, 'orgs': ORGS}
    errors = {}
    for key, fn in [('legislative', legislative), ('administrative', administrative), ('laws', laws), ('rules', admin_rules)]:
        try:
            data[key] = fn(since, today)
            print(f'{key}: {len(data[key])}건')
        except Exception as e:
            errors[key] = str(e)
            print(f'{key}: 실패 - {e}', file=sys.stderr)
    if errors:
        # 실패한 항목은 지난번 자료를 그대로 둡니다.
        old = {}
        if os.path.exists(OUT):
            txt = open(OUT, encoding='utf-8').read()
            old = json.loads(txt[txt.index('=') + 1:].rstrip().rstrip(';'))
        for k in errors:
            data[k] = old.get(k, [])
        data['stale'] = sorted(errors)
        if len(errors) == 4:
            raise SystemExit('모든 자료를 가져오지 못했습니다.')
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('// 자동 생성 파일: tools/update_laws.py 가 매일 갱신합니다.\n')
        f.write('window.LAW_DATA = ' + json.dumps(data, ensure_ascii=False, indent=1) + ';\n')
    print(f'저장 → {OUT}')

if __name__ == '__main__':
    main()
