/**
 * 견적 산출 '직접입력' 정보를 이 스프레드시트에 쌓는 웹 앱입니다.
 * 설치: 스프레드시트 > 확장 프로그램 > Apps Script 에 이 코드를 붙여넣고
 *       배포 > 새 배포 > 유형 '웹 앱', 실행 사용자 '나', 액세스 권한 '모든 사용자' 로 배포합니다.
 *       받은 웹 앱 URL(https://script.google.com/macros/s/.../exec)을 index.html 의 LEAD_ENDPOINT 에 넣습니다.
 * 보관 기간: purgeOld() 를 매일 실행되는 트리거로 등록하면 1년 지난 행이 자동 삭제됩니다.
 */
const SHEET_NAME = '견적요청';
const HEADERS = ['접수일시', '요청ID', '의뢰기관', '의뢰자', '이메일', '연락처', 'CAS/KE 번호', '물질명', '개인정보 동의',
                 '등록희망톤수', '별지26호 의뢰', '기업규모', '용도수', '견적금액(VAT 별도)', '견적일시', '접속 페이지'];
const KEEP_DAYS = 365;

function sheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) {
    sh = ss.insertSheet(SHEET_NAME);
    sh.appendRow(HEADERS);
    sh.setFrozenRows(1);
    sh.getRange(1, 1, 1, HEADERS.length).setFontWeight('bold').setBackground('#dce6f0');
  }
  return sh;
}

// 수식 실행 방지 + 길이 제한
function clean_(v, max) {
  let s = String(v == null ? '' : v).replace(/[\r\n\t]+/g, ' ').trim().slice(0, max || 200);
  if (/^[=+\-@]/.test(s)) s = "'" + s;
  return s;
}

function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.tryLock(10000);
  try {
    const d = JSON.parse(e.postData.contents || '{}');
    const sh = sheet_();
    const id = clean_(d.id, 40);
    if (!id) return out_('no id');
    if (d.type === 'lead') {
      if (!d.email || !d.name || d.consent !== '동의') return out_('invalid');
      sh.appendRow([new Date(), id, clean_(d.org, 100), clean_(d.name, 50), clean_(d.email, 100), clean_(d.tel, 30),
                    clean_(d.cas, 60), clean_(d.substance, 200), '동의', '', '', '', '', '', '', clean_(d.page, 300)]);
    } else if (d.type === 'quote') {
      const last = sh.getLastRow();
      if (last < 2) return out_('no rows');
      const from = Math.max(2, last - 500);
      const ids = sh.getRange(from, 2, last - from + 1, 1).getValues();
      for (let i = ids.length - 1; i >= 0; i--) {
        if (ids[i][0] === id) {
          sh.getRange(from + i, 10, 1, 6).setValues([[clean_(d.ton, 20), clean_(d.form26, 5), clean_(d.size, 20),
                                                     clean_(d.uses, 5), Number(d.total) || '', new Date()]]);
          break;
        }
      }
    }
    return out_('ok');
  } catch (err) {
    return out_('error');
  } finally {
    lock.releaseLock();
  }
}

function out_(msg) {
  return ContentService.createTextOutput(msg).setMimeType(ContentService.MimeType.TEXT);
}

// 1년 지난 행 삭제 (트리거: 시간 기반, 매일)
function purgeOld() {
  const sh = sheet_();
  const limit = new Date(Date.now() - KEEP_DAYS * 864e5);
  const vals = sh.getRange(2, 1, Math.max(0, sh.getLastRow() - 1), 1).getValues();
  for (let i = vals.length - 1; i >= 0; i--) {
    if (vals[i][0] instanceof Date && vals[i][0] < limit) sh.deleteRow(i + 2);
  }
}
