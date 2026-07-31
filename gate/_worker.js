// 비밀번호 게이트 — dist/_worker.js 로 복사되어 Pages 앞단에서 모든 요청을 가로챕니다.
//
// 왜 이게 필요한가
//   Cloudflare Access 는 "본인 계정에 등록된 도메인(zone)" 에만 걸 수 있습니다.
//   pages.dev 는 Cloudflare 소유 공용 도메인이라 누구도 Access 를 적용할 수 없고,
//   이 계정에는 등록된 도메인이 0개입니다. 그래서 사이트 자체가 인증을 합니다.
//
// 동작
//   쿠키 없음        → 비밀번호 입력 화면 (401)
//   POST /__login    → 비밀번호 일치 시 서명된 쿠키 발급 후 / 로 이동
//   쿠키 유효        → env.ASSETS 로 원래 파일 전달
//
// 비밀번호는 Pages 프로젝트의 환경변수 SITE_PASSWORD (Secret) 로 둡니다.
// 코드·리포에는 들어가지 않습니다.
//
// 미설정이면 전부 차단합니다(fail closed). 설정을 깜빡한 채 배포했을 때
// 사이트가 무방비로 열리는 것보다, 나에게도 안 열리는 편이 낫습니다.

const COOKIE = 'ins_auth';
const SESSION_DAYS = 30;
const VERSION = 'v1';        // 쿠키 형식이 바뀌면 올려서 기존 세션을 무효화

const enc = new TextEncoder();

async function hmac(keyStr, msgStr) {
  const key = await crypto.subtle.importKey(
    'raw', enc.encode(keyStr), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign'],
  );
  const sig = await crypto.subtle.sign('HMAC', key, enc.encode(msgStr));
  return [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

// 길이가 다르면 즉시 false 를 반환하는 비교는 길이를 흘립니다.
// 임의 키로 양쪽을 HMAC 해 고정 길이로 만든 뒤 비교합니다.
async function equals(a, b) {
  const nonce = crypto.getRandomValues(new Uint8Array(32)).join('');
  const [x, y] = await Promise.all([hmac(nonce, a), hmac(nonce, b)]);
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x.charCodeAt(i) ^ y.charCodeAt(i);
  return diff === 0;
}

function readCookie(request, name) {
  const raw = request.headers.get('Cookie') || '';
  for (const part of raw.split(';')) {
    const i = part.indexOf('=');
    if (i > 0 && part.slice(0, i).trim() === name) return part.slice(i + 1).trim();
  }
  return null;
}

async function issue(password) {
  const exp = Date.now() + SESSION_DAYS * 86400 * 1000;
  return `${exp}.${await hmac(password, `${VERSION}|${exp}`)}`;
}

async function valid(cookie, password) {
  if (!cookie) return false;
  const dot = cookie.indexOf('.');
  if (dot < 1) return false;
  const exp = cookie.slice(0, dot);
  if (!/^\d+$/.test(exp) || Number(exp) < Date.now()) return false;
  return equals(cookie.slice(dot + 1), await hmac(password, `${VERSION}|${exp}`));
}

function loginPage(failed) {
  return `<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>한국 보험사 정보 시스템</title>
<style>
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body { margin:0; min-height:100vh; display:grid; place-items:center;
         background:#f0efec; color:#1c1c1a; padding:24px;
         font:15px/1.6 system-ui,-apple-system,"Segoe UI","Malgun Gothic",sans-serif; }
  .card { width:100%; max-width:380px; background:#fff; border:1px solid #dcdad4;
          border-radius:12px; padding:28px; }
  h1 { margin:0 0 4px; font-size:17px; letter-spacing:-.01em; }
  p.sub { margin:0 0 20px; font-size:13px; color:#6b6a65; }
  label { display:block; font-size:13px; margin-bottom:6px; color:#44433f; }
  input { width:100%; padding:9px 11px; font-size:15px; border:1px solid #c9c7c0;
          border-radius:7px; background:#fff; color:inherit; }
  input:focus { outline:2px solid #2a78d6; outline-offset:1px; border-color:#2a78d6; }
  button { width:100%; margin-top:14px; padding:10px; font-size:15px; font-weight:600;
           border:0; border-radius:7px; background:#2a78d6; color:#fff; cursor:pointer; }
  button:hover { background:#2569bb; }
  .err { margin:14px 0 0; padding:9px 11px; border-radius:7px; font-size:13px;
         background:#fbeceb; border:1px solid #e8b4b3; color:#a82523; }
  @media (prefers-color-scheme: dark) {
    body { background:#22221f; color:#eceae4; }
    .card { background:#2b2b28; border-color:#403f3a; }
    p.sub { color:#9c9a93; } label { color:#c3c1ba; }
    input { background:#22221f; border-color:#4a4944; }
    .err { background:#3a2422; border-color:#6d3230; color:#f0a9a7; }
  }
</style>
</head><body>
  <form class="card" method="POST" action="/__login">
    <h1>한국 보험사 정보 시스템</h1>
    <p class="sub">계속하려면 비밀번호를 입력하세요.</p>
    <label for="pw">비밀번호</label>
    <input id="pw" name="pw" type="password" autocomplete="current-password" autofocus required>
    <button type="submit">열기</button>
    ${failed ? '<p class="err">비밀번호가 맞지 않습니다.</p>' : ''}
  </form>
</body></html>`;
}

function html(body, status) {
  return new Response(body, {
    status,
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'no-store',
      'X-Robots-Tag': 'noindex, nofollow',
      'Referrer-Policy': 'same-origin',
    },
  });
}

export default {
  async fetch(request, env) {
    const password = env.SITE_PASSWORD;

    // 미설정 = 전부 차단. 무방비로 열리는 것보다 안 열리는 편이 안전합니다.
    if (!password) {
      return html(
        '<!doctype html><meta charset="utf-8"><title>설정 필요</title>'
        + '<p style="font:15px system-ui;padding:24px">'
        + 'SITE_PASSWORD 환경변수가 설정되지 않아 접근을 차단했습니다.<br>'
        + 'Cloudflare → Workers &amp; Pages → insuranceinfo → Settings → '
        + 'Variables and Secrets 에서 <b>SITE_PASSWORD</b> 를 Secret 으로 추가하세요.</p>',
        503,
      );
    }

    const url = new URL(request.url);

    if (url.pathname === '/__logout') {
      return new Response(null, {
        status: 303,
        headers: {
          Location: '/',
          'Set-Cookie': `${COOKIE}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax`,
        },
      });
    }

    if (url.pathname === '/__login') {
      if (request.method !== 'POST') return html(loginPage(false), 200);

      const form = await request.formData();
      if (await equals(String(form.get('pw') || ''), password)) {
        return new Response(null, {
          status: 303,
          headers: {
            Location: '/',
            'Set-Cookie': `${COOKIE}=${await issue(password)}; Path=/; `
              + `Max-Age=${SESSION_DAYS * 86400}; HttpOnly; Secure; SameSite=Lax`,
          },
        });
      }
      // KV 없이 시도 횟수를 셀 수 없으므로, 실패에 지연을 줘 대입 속도를 떨어뜨립니다.
      // 근본 대비는 충분히 긴 비밀번호입니다.
      await new Promise((r) => setTimeout(r, 700));
      return html(loginPage(true), 401);
    }

    if (await valid(readCookie(request, COOKIE), password)) {
      return env.ASSETS.fetch(request);
    }
    return html(loginPage(false), 401);
  },
};
