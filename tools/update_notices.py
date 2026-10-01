"""산업계도움센터 공지사항에서 최근 1개월 글을 모아 data/notices.js 를 만듭니다.
GitHub Actions(.github/workflows/update-notices.yml)가 매일 실행합니다. 직접 실행도 가능합니다:
    python tools/update_notices.py
외부 라이브러리 없이 파이썬 기본 기능만 사용합니다.
"""
import datetime as dt, html, json, os, re, sys, time, urllib.request
from html.parser import HTMLParser
from seen import load_prev, mark

BASE = 'https://www.chemnavi.or.kr'
LIST_URL = BASE + '/chemnavi/spboard/notice.do?pageIndex={}'
DETAIL_URL = BASE + '/chemnavi/spboard/noticedetail.do?idx={}'
DAYS = 30          # 최근 며칠까지 모을지
MAX_PAGES = 5      # 목록을 최대 몇 쪽까지 볼지
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'notices.js')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'

def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception as e:
            print(f'  재시도 {i + 1}/{tries}: {url} ({e})', file=sys.stderr)
            time.sleep(3 * (i + 1))
    raise RuntimeError(f'접속 실패: {url}')

def text(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s))).strip()

def parse_list(page):
    rows = []
    for block in re.findall(r'<div class="board_g1_list\d"[^>]*>(.*?)</div>', page, re.S):
        m = re.search(r"getDetail\('(\d+)'\)", block)
        if not m:
            continue
        li = lambda cls: (re.search(r'<li class="%s[^"]*"[^>]*>(.*?)</li>' % cls, block, re.S) or [None, ''])[1]
        title = re.search(r'<span>(.*?)</span>', block, re.S)
        rows.append({
            'idx': m.group(1),
            'title': text(title.group(1) if title else li('width_title')),
            'date': text(li('width_date')),
            'views': int(re.sub(r'\D', '', text(li('width_hit'))) or 0),
            'pinned': not text(li('width_num')),
            'file': '첨부파일아이콘' in block,
        })
    return rows

class BodyText(HTMLParser):
    """본문 칸(td.pad_10)의 글자만 줄 단위로 뽑습니다."""
    BREAK = {'p', 'div', 'li', 'tr', 'br', 'h1', 'h2', 'h3', 'h4', 'table'}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth, self.parts = 0, []
    def handle_starttag(self, tag, attrs):
        if self.depth:
            if tag == 'td':
                self.depth += 1
            if tag in self.BREAK:
                self.parts.append('\n')
        elif tag == 'td' and 'pad_10' in (dict(attrs).get('class') or ''):
            self.depth = 1
    def handle_endtag(self, tag):
        if self.depth:
            if tag == 'td':
                self.depth -= 1
                self.parts.append('\n')
            elif tag in self.BREAK:
                self.parts.append('\n')
    def handle_data(self, data):
        if self.depth:
            self.parts.append(data)
    def result(self):
        lines = [re.sub(r'\s+', ' ', l.replace('\xa0', ' ')).strip() for l in ''.join(self.parts).split('\n')]
        return '\n'.join(l for l in lines if l)

def summary(idx):
    p = BodyText()
    p.feed(get(DETAIL_URL.format(idx)))
    t = p.result()
    return re.sub(r'\s\S*$', '', t[:300]) + '…' if len(t) > 300 else t

def main():
    today = (dt.datetime.utcnow() + dt.timedelta(hours=9)).date()
    since = today - dt.timedelta(days=DAYS)
    items, seen = [], set()
    for n in range(1, MAX_PAGES + 1):
        rows = parse_list(get(LIST_URL.format(n)))
        if not rows:
            break
        older = False
        for r in rows:
            if r['date'] < since.isoformat():
                older = True
                continue
            if r['idx'] not in seen:
                seen.add(r['idx'])
                items.append(r)
        if older:
            break
    if not items and n == 1:
        raise SystemExit('목록을 하나도 읽지 못했습니다. 사이트 구조가 바뀌었는지 확인하세요.')
    for it in items:
        it['summary'] = summary(it['idx'])
        time.sleep(0.5)
    items.sort(key=lambda x: (x['date'], int(x['idx'])), reverse=True)
    prev = load_prev(OUT)
    new = mark(items, prev.get('items'), lambda x: x['idx'], today.isoformat(), prev.get('updated'))
    data = {'updated': today.isoformat(), 'from': since.isoformat(), 'to': today.isoformat(), 'newCount': new, 'items': items}
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('// 자동 생성 파일: tools/update_notices.py 가 매일 갱신합니다.\n')
        f.write('window.NOTICE_DATA = ' + json.dumps(data, ensure_ascii=False, indent=1) + ';\n')
    print(f'{len(items)}건 저장 ({since} ~ {today}) → {OUT}')

if __name__ == '__main__':
    main()
