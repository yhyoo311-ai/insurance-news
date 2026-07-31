/* 웹 관리자 — 서버 없이 GitHub API 로 설정을 읽고 커밋합니다.
 *
 * 왜 이런 구조인가
 *   정적 호스팅(Cloudflare Pages)에는 실행할 백엔드가 없습니다. 그런데 설정은
 *   어딘가에 영구히 남아야 하고, 매일 07시 다이제스트 파이프라인은 이미
 *   GitHub 의 settings.json 을 읽습니다. 그래서 GitHub 를 그대로 저장소로 쓰고
 *   브라우저가 Contents API 로 커밋합니다. 서버·DB 를 새로 두지 않아도 됩니다.
 *
 * 토큰은 localStorage 에만 있습니다. 이 페이지는 github.com 외 어디에도
 * 토큰을 보내지 않습니다.
 */

(function () {
  'use strict';

  var REPO = (window.__REPO__ || '').trim();          // 'owner/name'
  var BRANCH = window.__BRANCH__ || 'main';
  var API = 'https://api.github.com';
  var TOKEN_KEY = 'insurance_admin_token';

  var state = { token: '', files: {} };  // files: path -> {sha, obj}

  /* ─────────────────────── 유틸 ─────────────────────── */

  function el(id) { return document.getElementById(id); }

  function esc(s) {
    return String(s === null || s === undefined ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function b64encode(str) {
    var bytes = new TextEncoder().encode(str);
    var bin = '';
    for (var i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return btoa(bin);
  }

  function b64decode(b64) {
    var bin = atob(String(b64).replace(/\s/g, ''));
    var bytes = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new TextDecoder().decode(bytes);
  }

  function say(msg, ok) {
    el('banner').innerHTML =
      '<div class="banner ' + (ok ? 'ok' : 'bad') + '">' + esc(msg) + '</div>';
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function clearSay() { el('banner').innerHTML = ''; }

  function lines(text) {
    return (text || '').split('\n').map(function (x) { return x.trim(); })
      .filter(function (x) { return x; });
  }

  function terms(text) {
    return (text || '').split(/[\n,]/).map(function (x) { return x.trim(); })
      .filter(function (x) { return x; });
  }

  function toInt(v, dflt) {
    var n = parseInt(String(v).trim(), 10);
    return isNaN(n) ? dflt : n;
  }

  function toFloat(v, dflt) {
    var n = parseFloat(String(v).trim());
    return isNaN(n) ? dflt : n;
  }

  /* ─────────────────────── GitHub API ─────────────────────── */

  function gh(path, opts) {
    opts = opts || {};
    var headers = {
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
    };
    if (state.token) headers.Authorization = 'Bearer ' + state.token;
    if (opts.body) headers['Content-Type'] = 'application/json';

    return fetch(API + path, {
      method: opts.method || 'GET',
      headers: headers,
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    }).then(function (r) {
      if (r.status === 204) return null;                 // dispatch 성공
      return r.json().catch(function () { return {}; }).then(function (data) {
        if (!r.ok) {
          var m = (data && data.message) || ('HTTP ' + r.status);
          if (r.status === 401) m = '토큰이 유효하지 않습니다 (401). 다시 발급해 주세요.';
          if (r.status === 403) m = '권한이 없습니다 (403). 토큰의 Contents/Actions 권한을 확인하세요.';
          if (r.status === 404) {
            m = '대상을 찾지 못했습니다 (404). 토큰이 이 리포에 접근 가능한지, ' +
                '워크플로우가 main 브랜치에 있는지 확인하세요.';
          }
          if (r.status === 409) m = '다른 곳에서 먼저 수정됐습니다 (409). 새로고침 후 다시 저장하세요.';
          var err = new Error(m);
          err.status = r.status;
          throw err;
        }
        return data;
      });
    });
  }

  function loadFile(path) {
    return gh('/repos/' + REPO + '/contents/' + path + '?ref=' + encodeURIComponent(BRANCH))
      .then(function (d) {
        var obj = JSON.parse(b64decode(d.content));
        state.files[path] = { sha: d.sha, obj: obj };
        return obj;
      });
  }

  function saveFile(path, obj, message) {
    var entry = state.files[path] || {};
    var text = JSON.stringify(obj, null, 2) + '\n';
    return gh('/repos/' + REPO + '/contents/' + path, {
      method: 'PUT',
      body: {
        message: message,
        content: b64encode(text),
        sha: entry.sha,
        branch: BRANCH,
      },
    }).then(function (d) {
      // 다음 저장을 위해 새 sha 를 반드시 갱신해야 합니다 (안 하면 409)
      state.files[path] = { sha: d.content.sha, obj: obj };
      return d;
    });
  }

  function dispatch(workflowFile) {
    return gh('/repos/' + REPO + '/actions/workflows/' + workflowFile + '/dispatches', {
      method: 'POST',
      body: { ref: BRANCH },
    });
  }

  function loadRuns() {
    return gh('/repos/' + REPO + '/actions/runs?per_page=8').then(function (d) {
      var runs = (d.workflow_runs || []);
      if (!runs.length) {
        el('runs').innerHTML = '<p class="hint">실행 기록이 없습니다.</p>';
        return;
      }
      el('runs').innerHTML = '<div class="rows">' + runs.map(function (r) {
        var stat = r.status === 'completed' ? r.conclusion : r.status;
        var cls = stat === 'success' ? 'listed' : '';
        return '<a class="row" href="' + esc(r.html_url) + '" target="_blank" rel="noopener">' +
          '<span class="rn">' + esc(r.name) + '</span>' +
          '<span class="badge ' + cls + '">' + esc(stat) + '</span>' +
          '<span class="rr">' + esc((r.created_at || '').replace('T', ' ').replace('Z', ' UTC')) + '</span>' +
          '</a>';
      }).join('') + '</div>';
    });
  }

  /* ─────────────────────── 뉴스·텔레그램 설정 폼 ─────────────────────── */

  function renderNews(s) {
    var sections = s.sections || [];
    var total = sections.length + 2;   // 새 섹션 추가용 빈 슬롯 2개
    var h = '<input type="hidden" id="secCount" value="' + total + '">';

    h += '<fieldset><legend>🗂 대구분 섹션 (위→아래 순서로 다이제스트에 표시)</legend>' +
      '<div class="hint">기사를 주제별로 묶어 섹션마다 <b>최소~최대</b> 건수로 정리합니다. ' +
      '키워드는 제목을 우선 매칭하며 위쪽 섹션이 먼저 배정됩니다. 키워드를 비운 섹션은 ' +
      '<b>기타</b>가 되어 나머지를 모두 담습니다(맨 아래 권장). 이름을 비우면 삭제됩니다.</div>';

    for (var i = 0; i < total; i++) {
      var q = sections[i] || { name: '', min: 3, max: 5, terms: [] };
      var isNew = i >= sections.length;
      h += '<div class="quota"><div class="qrow">' +
        '<label style="flex:1"><span class="ord' + (isNew ? ' new' : '') + '">' +
        (isNew ? '+' : (i + 1)) + '</span> 섹션 이름' +
        '<input type="text" data-sec="name" data-i="' + i + '" value="' + esc(q.name) +
        '" placeholder="(비우면 삭제)"></label>' +
        '<label class="minbox">최소<input type="number" min="0" data-sec="min" data-i="' + i +
        '" value="' + esc(q.min) + '"></label>' +
        '<label class="minbox">최대<input type="number" min="1" data-sec="max" data-i="' + i +
        '" value="' + esc(q.max) + '"></label></div>' +
        '<label>포함 키워드 (줄바꿈/콤마 구분)' +
        '<textarea rows="2" data-sec="terms" data-i="' + i + '">' +
        esc((q.terms || []).join('\n')) + '</textarea></label></div>';
    }
    h += '</fieldset>';

    h += '<fieldset><legend>📌 핀 지정 회사 (반드시 포함)</legend>' +
      '<label>회사명 (한 줄에 하나)<textarea id="pinned" rows="3">' +
      esc((s.pinned_companies || []).join('\n')) + '</textarea></label>' +
      '<label class="minbox">최대 보장 건수<input type="number" min="0" id="pinnedMax" value="' +
      esc(s.pinned_max === undefined ? 2 : s.pinned_max) + '"></label></fieldset>';

    h += '<fieldset><legend>🔎 검색 키워드 (네이버 뉴스 검색어)</legend>' +
      '<div class="hint">한 줄에 하나. 많을수록 수집 범위가 넓어집니다.</div>' +
      '<textarea id="queries" rows="8">' +
      esc((s.naver_search_queries || []).join('\n')) + '</textarea></fieldset>';

    h += '<fieldset><legend>🚫 제외 키워드 (노이즈 제거)</legend>' +
      '<div class="hint">제목에 이 단어가 있으면 제외됩니다 (핀 회사 기사는 예외). ' +
      '정보사이트의 회사별 뉴스에도 함께 적용됩니다.</div>' +
      '<textarea id="excludes" rows="6">' +
      esc((s.exclude_keywords || []).join('\n')) + '</textarea></fieldset>';

    var imp = Object.keys(s.importance_keywords || {}).map(function (k) {
      return k + ': ' + s.importance_keywords[k];
    }).join('\n');
    h += '<fieldset><legend>⭐ 중요도 가중치 (제목 포함 시 가산점)</legend>' +
      '<div class="hint">형식: <code>키워드: 점수</code> (한 줄에 하나).</div>' +
      '<textarea id="importance" rows="10">' + esc(imp) + '</textarea></fieldset>';

    h += '<div class="stickybar">' +
      '<button type="button" class="btn primary" id="saveNews">✅ 저장 &amp; 배포</button>' +
      '<button type="button" class="btn" data-run="daily.yml">👁 지금 미리보기 발송</button>' +
      '</div>';

    el('newsForm').innerHTML = h;
    el('saveNews').addEventListener('click', saveNews);
    wireRunButtons(el('newsForm'));
  }

  function collectNews() {
    var base = state.files['settings.json'].obj;
    var out = JSON.parse(JSON.stringify(base));   // 모르는 키는 그대로 보존
    var total = toInt(el('secCount').value, 0);
    var sections = [];

    for (var i = 0; i < total; i++) {
      var name = (val('name', i) || '').trim();
      if (!name) continue;                          // 이름 비면 삭제
      sections.push({
        name: name,
        min: Math.max(0, toInt(val('min', i), 3)),
        max: Math.max(1, toInt(val('max', i), 5)),
        terms: terms(val('terms', i)),
      });
    }

    var imp = {};
    (el('importance').value || '').split('\n').forEach(function (line) {
      line = line.trim();
      var at = line.lastIndexOf(':');
      if (!line || at < 0) return;
      var k = line.slice(0, at).trim();
      var v = parseInt(line.slice(at + 1).trim(), 10);
      if (k && !isNaN(v)) imp[k] = v;
    });

    out.sections = sections;
    out.pinned_companies = lines(el('pinned').value);
    out.pinned_max = Math.max(0, toInt(el('pinnedMax').value, 2));
    out.naver_search_queries = lines(el('queries').value);
    out.exclude_keywords = lines(el('excludes').value);
    out.importance_keywords = imp;
    return out;

    function val(kind, idx) {
      var node = el('newsForm').querySelector('[data-sec="' + kind + '"][data-i="' + idx + '"]');
      return node ? node.value : '';
    }
  }

  function saveNews() {
    var btn = el('saveNews');
    btn.disabled = true;
    btn.textContent = '저장 중…';
    saveFile('settings.json', collectNews(), 'Update news settings via web admin')
      .then(function () {
        say('설정을 저장했습니다 — 익일 오전 7시 다이제스트부터 적용됩니다.', true);
        return loadFile('settings.json').then(renderNews);
      })
      .catch(function (e) { say('저장 실패: ' + e.message, false); })
      .then(function () { btn.disabled = false; btn.textContent = '✅ 저장 & 배포'; });
  }

  /* ─────────────────────── 보험사 데이터 폼 ─────────────────────── */

  function shText(list) {
    return (list || []).map(function (s) {
      return [s.name || '', (s.stake === null || s.stake === undefined) ? '' : s.stake,
              s.role || ''].join(' | ');
    }).join('\n');
  }

  function renderCompanies(d) {
    var gname = {};
    (d.groups || []).forEach(function (g) { gname[g.id] = g.name; });

    var unverified = (d.companies || []).filter(function (c) { return !c.verified; });
    var h = '';

    if (unverified.length) {
      h += '<div class="banner bad">⚠ <b>' + unverified.length + '개사</b>는 DART 정기보고서를 ' +
        '제출하지 않아 재무가 <b>개략치</b>입니다 — ' +
        esc(unverified.map(function (c) { return c.name; }).join(', ')) + '. ' +
        '각 행의 <b>공시</b> 링크에서 감사보고서 원문을 열어 값을 채우고 <b>검증</b>을 체크하세요.</div>';
    }

    h += '<fieldset><legend>기준일</legend><label class="minbox" style="max-width:170px">' +
      '재무 기준일 (YYYY-MM-DD)<input type="text" id="asOf" value="' + esc(d.as_of || '') +
      '"></label></fieldset>';

    h += '<div class="tablescroll"><table class="cotable"><thead><tr>' +
      '<th>회사</th><th>분야</th><th>기준</th><th>공시</th>' +
      '<th>티커<br><span class="hint">비우면 비상장</span></th>' +
      '<th style="text-align:right">자산총계<br><span class="hint">억원</span></th>' +
      '<th style="text-align:right">부채총계<br><span class="hint">억원</span></th>' +
      '<th style="text-align:right">자본총계<br><span class="hint">억원</span></th>' +
      '<th style="text-align:right">보험계약부채<br><span class="hint">억원</span></th>' +
      '<th style="text-align:right">영업이익<br><span class="hint">억원</span></th>' +
      '<th style="text-align:right">당기순이익<br><span class="hint">억원</span></th>' +
      '<th style="text-align:right">K-ICS<br><span class="hint">% · DART 없음</span></th>' +
      '<th>검증</th>' +
      '<th>주요 주주<br><span class="hint">이름 | 지분% | 구분</span></th>' +
      '</tr></thead><tbody>';

    (d.companies || []).forEach(function (c) {
      var f = c.dart_filing;
      h += '<tr data-id="' + esc(c.id) + '">' +
        '<td class="co">' + esc(c.name) + '</td>' +
        '<td>' + esc(gname[c.group] || c.group) + '</td>' +
        '<td>' + (c.verified
          ? esc((c.dart_year || '') + ' ' + (c.fs_basis || ''))
          : '<span style="color:var(--critical)">개략치</span>') + '</td>' +
        '<td>' + (f ? '<a href="' + esc(f.url) + '" target="_blank" rel="noopener" title="' +
          esc(f.report_nm) + '">' + esc(f.kind) + ' ↗</a>' : '—') + '</td>' +
        num('ticker', c.ticker || '', 'text') +
        num('assets', c.assets) +
        num('liabilities', c.liabilities) +
        num('equity', c.equity) +
        num('insurance_liabilities', c.insurance_liabilities) +
        num('operating_income', c.operating_income) +
        num('net_income', c.net_income) +
        num('kics', c.kics) +
        '<td style="text-align:center"><input type="checkbox" data-f="verified"' +
          (c.verified ? ' checked' : '') + '></td>' +
        '<td><textarea rows="3" data-f="shareholders">' + esc(shText(c.shareholders)) +
          '</textarea></td></tr>';
    });

    h += '</tbody></table></div>';
    h += '<div class="stickybar">' +
      '<button type="button" class="btn primary" id="saveCo">✅ 저장 &amp; 배포</button>' +
      '<button type="button" class="btn" data-run="sync-dart.yml">📥 DART 전체 갱신</button>' +
      '<button type="button" class="btn" data-run="sync-fisis.yml">📊 K-ICS·감독통계 갱신</button>' +
      '</div>';

    el('coForm').innerHTML = h;
    el('saveCo').addEventListener('click', saveCompanies);
    wireRunButtons(el('coForm'));

    function num(field, value, type) {
      var v = (value === null || value === undefined) ? '' : value;
      return '<td><input type="' + (type || 'number') + '" data-f="' + field +
        '" value="' + esc(v) + '"></td>';
    }
  }

  function collectCompanies() {
    var base = state.files['data/insurers.json'].obj;
    var out = JSON.parse(JSON.stringify(base));
    out.as_of = (el('asOf').value || out.as_of || '').trim();

    var byId = {};
    out.companies.forEach(function (c) { byId[c.id] = c; });

    el('coForm').querySelectorAll('tbody tr').forEach(function (tr) {
      var c = byId[tr.dataset.id];
      if (!c) return;

      var ticker = (get(tr, 'ticker') || '').trim();
      c.ticker = ticker || null;
      c.listed = !!ticker;

      // 필수 3항목 — 비우면 0
      c.assets = toInt(get(tr, 'assets'), 0);
      c.equity = toInt(get(tr, 'equity'), 0);
      c.net_income = toInt(get(tr, 'net_income'), 0);

      // 선택 항목 — 비우면 키를 지웁니다 (0 으로 남기면 '부채 0원'이 표시됩니다)
      ['liabilities', 'insurance_liabilities', 'operating_income'].forEach(function (k) {
        var raw = (get(tr, k) || '').trim();
        if (raw === '') delete c[k]; else c[k] = toInt(raw, 0);
      });

      var kics = (get(tr, 'kics') || '').trim();
      c.kics = kics === '' ? null : toFloat(kics, null);
      c.verified = tr.querySelector('[data-f="verified"]').checked;

      var parsed = parseShareholders(get(tr, 'shareholders'));
      if (parsed.length) c.shareholders = parsed;
    });

    return out;

    function get(tr, field) {
      var node = tr.querySelector('[data-f="' + field + '"]');
      return node ? node.value : '';
    }
  }

  function parseShareholders(text) {
    return (text || '').split('\n').map(function (line) {
      var parts = line.split('|').map(function (p) { return p.trim(); });
      if (!parts[0]) return null;
      var stake = parts.length > 1 && parts[1] !== '' ? toFloat(parts[1], null) : null;
      return { name: parts[0], stake: stake, role: parts.length > 2 ? parts[2] : '' };
    }).filter(Boolean);
  }

  function saveCompanies() {
    var btn = el('saveCo');
    btn.disabled = true;
    btn.textContent = '저장 중…';
    saveFile('data/insurers.json', collectCompanies(), 'Update insurer data via web admin')
      .then(function () {
        say('보험사 데이터를 저장했습니다 — 사이트가 자동으로 다시 배포됩니다 (1~2분).', true);
        return loadFile('data/insurers.json').then(renderCompanies);
      })
      .catch(function (e) { say('저장 실패: ' + e.message, false); })
      .then(function () { btn.disabled = false; btn.textContent = '✅ 저장 & 배포'; });
  }

  /* ─────────────────────── 워크플로우 실행 버튼 ─────────────────────── */

  var RUN_LABEL = {
    'site.yml': '사이트 갱신',
    'sync-dart.yml': 'DART 갱신',
    'sync-fisis.yml': 'K-ICS 갱신',
    'daily.yml': '미리보기 발송',
  };

  function wireRunButtons(root) {
    root.querySelectorAll('[data-run]').forEach(function (b) {
      if (b.dataset.wired) return;
      b.dataset.wired = '1';
      b.addEventListener('click', function () {
        var wf = b.dataset.run;
        var label = RUN_LABEL[wf] || wf;
        var old = b.textContent;
        b.disabled = true;
        b.textContent = '요청 중…';
        dispatch(wf)
          .then(function () {
            say(label + ' 을 시작했습니다. 1~2분 뒤 결과가 반영됩니다. ' +
                '(진행 상황은 [배포·갱신] 탭의 최근 실행에서 확인)', true);
            return loadRuns();
          })
          .catch(function (e) { say(label + ' 실행 실패: ' + e.message, false); })
          .then(function () { b.disabled = false; b.textContent = old; });
      });
    });
  }

  /* ─────────────────────── 탭 ─────────────────────── */

  function showTab(name) {
    ['news', 'companies', 'jobs'].forEach(function (t) {
      el('tab-' + t).hidden = t !== name;
    });
    document.querySelectorAll('#tabs a').forEach(function (a) {
      a.classList.toggle('on', a.dataset.tab === name);
    });
  }

  function wireTabs() {
    document.querySelectorAll('#tabs a').forEach(function (a) {
      a.addEventListener('click', function (e) {
        e.preventDefault();
        location.hash = '#' + a.dataset.tab;
        showTab(a.dataset.tab);
      });
    });
    var initial = (location.hash || '#news').slice(1);
    showTab(['news', 'companies', 'jobs'].indexOf(initial) >= 0 ? initial : 'news');
  }

  /* ─────────────────────── 인증 흐름 ─────────────────────── */

  function showAuthForm(message) {
    el('authState').textContent = message || '설정을 바꾸려면 GitHub 토큰이 필요합니다.';
    el('authForm').hidden = false;
    el('authOk').hidden = true;
    el('tabs').hidden = true;
    ['news', 'companies', 'jobs'].forEach(function (t) { el('tab-' + t).hidden = true; });
  }

  function connect() {
    el('authState').textContent = '연결 확인 중…';
    el('authForm').hidden = true;

    return gh('/repos/' + REPO).then(function (repo) {
      if (!repo.permissions || !repo.permissions.push) {
        throw new Error('이 토큰은 쓰기 권한이 없습니다. Contents: Read and write 를 켜 주세요.');
      }
      el('authState').textContent = '';
      el('authOk').hidden = false;
      el('authWho').textContent = '연결됨 · ' + repo.full_name;
      el('tabs').hidden = false;
      wireTabs();
      clearSay();

      return Promise.all([
        loadFile('settings.json').then(renderNews).catch(function (e) {
          el('newsForm').innerHTML = '<p class="empty">settings.json 을 불러오지 못했습니다: ' +
            esc(e.message) + '</p>';
        }),
        loadFile('data/insurers.json').then(renderCompanies).catch(function (e) {
          el('coForm').innerHTML = '<p class="empty">data/insurers.json 을 불러오지 못했습니다: ' +
            esc(e.message) + '</p>';
        }),
        loadRuns().catch(function () {}),
      ]);
    }).catch(function (e) {
      localStorage.removeItem(TOKEN_KEY);
      state.token = '';
      showAuthForm('연결 실패: ' + e.message);
    });
  }

  function init() {
    if (!REPO) {
      el('authState').textContent =
        '대상 리포지토리를 알 수 없습니다. build_static.py 를 다시 실행해 주세요.';
      return;
    }
    el('repoName').textContent = REPO;
    el('repoName2').textContent = REPO;

    el('tokenSave').addEventListener('click', function () {
      var t = el('tokenInput').value.trim();
      if (!t) { say('토큰을 입력하세요.', false); return; }
      state.token = t;
      localStorage.setItem(TOKEN_KEY, t);
      el('tokenInput').value = '';
      connect();
    });
    el('tokenInput').addEventListener('keydown', function (e) {
      if (e.key === 'Enter') el('tokenSave').click();
    });
    el('tokenClear').addEventListener('click', function () {
      localStorage.removeItem(TOKEN_KEY);
      state.token = '';
      showAuthForm('토큰을 삭제했습니다.');
    });

    wireRunButtons(document);

    state.token = localStorage.getItem(TOKEN_KEY) || '';
    if (state.token) connect(); else showAuthForm();
  }

  init();
})();
