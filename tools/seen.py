"""어제와 비교해 새로 나타난 항목을 표시하기 위한 도우미.
각 항목에 'firstSeen'(처음 수집된 날짜)을 붙입니다. 화면에서는 firstSeen == updated 이면 NEW로 표시합니다."""
import json, os

def load_prev(path):
    if not os.path.exists(path):
        return {}
    txt = open(path, encoding='utf-8').read()
    try:
        return json.loads(txt[txt.index('=') + 1:].rstrip().rstrip(';'))
    except Exception:
        return {}

def mark(items, prev_items, key, today, prev_updated):
    """prev_items에 있던 항목은 처음 본 날짜를 이어받고, 처음 보는 항목은 today를 붙입니다."""
    seen = {key(x): (x.get('firstSeen') or prev_updated or today) for x in (prev_items or [])}
    for x in items:
        x['firstSeen'] = seen.get(key(x), today)
    return sum(1 for x in items if x['firstSeen'] == today)
