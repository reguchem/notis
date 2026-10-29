"""하나은행 최종 고시환율(송금 보낼 때)을 받아 data/quotes.js 의 환율을 갱신합니다.
견적산출.xlsx 의 '하나은행환율' 파워쿼리와 같은 방식입니다. GitHub Actions 가 매일 실행합니다.
직접 실행: python tools/update_rates.py
"""
import datetime as dt, json, os, re, sys, time, urllib.request

URL = 'https://www.kebhana.com/cms/rate/wpfxd651_01i_01.do'
REFERER = 'https://www.kebhana.com/cms/rate/index.do?contentUrl=/cms/rate/wpfxd651_01i.do'
CURRENCIES = ['USD', 'EUR']
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'quotes.js')

def fetch(day):
    body = (f'ajax=true&curCd=&tmpInqStrDt={day:%Y-%m-%d}&pbldDvCd=3&pbldSqn=&hid_key_data='
            f'&inqStrDt={day:%Y%m%d}&inqKindCd=1&hid_enc_data=&requestTarget=searchContentDiv').encode()
    req = urllib.request.Request(URL, data=body, headers={
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Referer': REFERER,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    txt = raw.decode('utf-8', 'replace')
    return txt if '미국' in txt else raw.decode('cp949', 'replace')

def parse(html):
    """표 열 순서: 통화, 현찰 사실때, 스프레드, 현찰 파실때, 스프레드, 송금 보낼때, 송금 받을때, 외화수표 파실때, 매매기준율, ..."""
    rates = {}
    for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.S):
        tds = [re.sub(r'<[^>]+>|\s+', ' ', td).strip() for td in re.findall(r'<td[^>]*>(.*?)</td>', tr, re.S)]
        if len(tds) < 9:
            continue
        code = re.sub(r'[^A-Z]', '', tds[0])
        if code in CURRENCIES and code not in rates:
            num = lambda x: float(x.replace(',', ''))
            try:
                rates[code] = {'send': num(tds[5]), 'base': num(tds[8])}
            except ValueError:
                pass
    return rates

def main():
    today = (dt.datetime.utcnow() + dt.timedelta(hours=9)).date()
    rates, day = {}, today
    for back in range(0, 11):          # 주말·공휴일이면 하루씩 거슬러 올라감
        day = today - dt.timedelta(days=back)
        for attempt in range(3):
            try:
                rates = parse(fetch(day))
                break
            except Exception as e:
                print(f'  재시도 {attempt + 1}/3 ({day}): {e}', file=sys.stderr)
                time.sleep(3 * (attempt + 1))
        if all(c in rates for c in CURRENCIES):
            break
    if not all(c in rates for c in CURRENCIES):
        raise SystemExit('환율을 가져오지 못했습니다. 기존 환율을 그대로 둡니다.')
    txt = open(OUT, encoding='utf-8').read()
    head, body = txt.split('=', 1)
    data = json.loads(body.strip().rstrip(';'))
    for c in CURRENCIES:
        data['rates'][c] = {'send': rates[c]['send'], 'date': day.isoformat()}
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(head.rstrip() + ' = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';\n')
    print('환율 갱신:', ', '.join(f"{c} {rates[c]['send']:,}" for c in CURRENCIES), f'({day})')

if __name__ == '__main__':
    main()
