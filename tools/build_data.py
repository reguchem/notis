"""엑셀 목록을 홈페이지 검색용 데이터로 변환합니다.
사용법: python tools/build_data.py   (저장소 폴더의 엑셀 파일을 자동으로 찾습니다)

- 이름에 '대리인'이 들어간 파일: 공동등록 완료 물질 목록 → data/substances.js
  (2행 머리글: 화학물질명, 고유번호, CAS No., 등록 예정시 문의처, 비고, 컨설팅사 / 4행부터 자료)
- 이름이 '별표'로 시작하는 파일: 기존화학물질 목록(별표1, 별표2) → data/existing.js
  (열: 고유번호, '화학물질명 (CAS No. ...)')
"""
import glob, json, os, re
import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
xlsx = [f for f in glob.glob(os.path.join(ROOT, '*.xlsx')) if not os.path.basename(f).startswith('~$')]
CAS_RE = re.compile(r'(\d{2,7})\s*-\s*(\d{2})\s*-\s*(\d)(?!\d)')

def s(v):
    return re.sub(r'\s+', ' ', str(v)).strip() if v is not None else ''

def asof_of(path):
    m = re.search(r'_(\d{6})', os.path.basename(path))
    return f"20{m.group(1)[:2]}.{m.group(1)[2:4]}.{m.group(1)[4:]}" if m else ''

def write(name, var, obj):
    out = os.path.join(ROOT, 'data', name)
    with open(out, 'w', encoding='utf-8') as f:
        f.write('// 자동 생성 파일: tools/build_data.py 로 다시 만드세요.\n')
        f.write(f'window.{var} = ' + json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + ';\n')
    return out

# 1) 공동등록 완료 목록
joint = [f for f in xlsx if '대리인' in os.path.basename(f)]
if joint:
    src = sorted(joint)[-1]
    ws = openpyxl.load_workbook(src, read_only=True, data_only=True).worksheets[0]
    header = [s(c) for c in next(ws.iter_rows(min_row=2, max_row=2, values_only=True))]
    col = {n: header.index(n) for n in ['화학물질명', '고유번호', 'CAS No.', '등록 예정시 문의처', '비고', '컨설팅사']}
    items = []
    for r in ws.iter_rows(min_row=4, values_only=True):
        name, ids, cas = s(r[col['화학물질명']]), s(r[col['고유번호']]), s(r[col['CAS No.']])
        if not (name or ids or cas):
            continue
        items.append({'n': name, 'id': [x.strip() for x in ids.split(',') if x.strip()],
                      'cas': ['-'.join(m) for m in CAS_RE.findall(cas)], 'casRaw': cas,
                      'tel': s(r[col['등록 예정시 문의처']]), 'note': s(r[col['비고']]), 'org': s(r[col['컨설팅사']])})
    write('substances.js', 'SUBSTANCE_DATA', {'asof': asof_of(src), 'source': os.path.basename(src), 'items': items})
    print(f'공동등록 완료 {len(items)}건 ← {os.path.basename(src)}')

# 2) 기존화학물질 목록 (별표1·2)
lists, total = [], 0
for src in sorted(f for f in xlsx if os.path.basename(f).startswith('별표')):
    label = '별표' + re.match(r'별표(\d+)', os.path.basename(src)).group(1)
    ws = openpyxl.load_workbook(src, read_only=True, data_only=True).worksheets[0]
    rows, removed = [], 0
    for r in ws.iter_rows(values_only=True):
        id_, text = s(r[0]), s(r[1] if len(r) > 1 else '')
        if not id_ or not text or id_ == '고유번호' or id_.startswith('[') or id_.startswith('*'):
            continue
        if text == '삭제':
            removed += 1
            continue
        i = text.rfind('CAS No')
        name = re.sub(r'[\s;(]+$', '', text[:i]).strip() if i >= 0 else text
        cas = ['-'.join(m) for m in CAS_RE.findall(text[i:])] if i >= 0 else []
        rows.append([id_, name, cas])
    lists.append({'label': label, 'file': os.path.basename(src), 'rows': rows})
    total += len(rows)
    print(f'{label} {len(rows)}건 (삭제 {removed}건 제외) ← {os.path.basename(src)}')
if lists:
    write('existing.js', 'EXISTING_DATA', {'lists': lists})
    print(f'기존화학물질 합계 {total}건')
