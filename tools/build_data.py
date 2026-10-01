"""엑셀 목록(공동등록 완료 물질)을 홈페이지 검색용 data/substances.js 로 변환합니다.
사용법: python tools/build_data.py [엑셀파일경로]
엑셀 형식: 2행이 머리글(화학물질명, 고유번호, CAS No., 등록 예정시 문의처, 비고, 컨설팅사), 4행부터 자료.
"""
import glob, json, os, re, sys
import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = sys.argv[1] if len(sys.argv) > 1 else sorted(glob.glob(os.path.join(ROOT, '*.xlsx')))[-1]
m = re.search(r'_(\d{6})', os.path.basename(src))
asof = f"20{m.group(1)[:2]}.{m.group(1)[2:4]}.{m.group(1)[4:]}" if m else ''

wb = openpyxl.load_workbook(src, read_only=True, data_only=True)
ws = wb.worksheets[0]
header = [str(c).strip() if c else '' for c in next(ws.iter_rows(min_row=2, max_row=2, values_only=True))]
col = {name: header.index(name) for name in ['화학물질명', '고유번호', 'CAS No.', '등록 예정시 문의처', '비고', '컨설팅사']}

def s(v):
    return re.sub(r'\s+', ' ', str(v)).strip() if v is not None else ''

items = []
for r in ws.iter_rows(min_row=4, values_only=True):
    name, ids, cas = s(r[col['화학물질명']]), s(r[col['고유번호']]), s(r[col['CAS No.']])
    if not (name or ids or cas):
        continue
    items.append({
        'n': name,
        'id': [x.strip() for x in ids.split(',') if x.strip()],
        'cas': cas if re.match(r'^\d{2,7}-\d{2}-\d$', cas) else '',
        'casRaw': cas,
        'tel': s(r[col['등록 예정시 문의처']]),
        'note': s(r[col['비고']]),
        'org': s(r[col['컨설팅사']]),
    })

out = os.path.join(ROOT, 'data', 'substances.js')
with open(out, 'w', encoding='utf-8') as f:
    f.write('// 자동 생성 파일: tools/build_data.py 로 다시 만드세요.\n')
    f.write('window.SUBSTANCE_DATA = ' + json.dumps({'asof': asof, 'source': os.path.basename(src), 'items': items}, ensure_ascii=False, separators=(',', ':')) + ';\n')
print(f'{len(items)}건 → {out} (기준일 {asof})')
