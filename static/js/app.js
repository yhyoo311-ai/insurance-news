/* 한국 보험사 정보 시스템 — 히트맵 + 회사 패널
 *
 * 데이터는 두 경로로 들어옵니다.
 *   · 로컬 Flask : window.__BOOT__ (초기) + /api/company/<id> (패널)
 *   · 정적 스냅샷 : window.__BOOT__ + window.__DETAILS__ (build_static.py 가 구워둠)
 */

(function () {
  'use strict';

  var BOOT = window.__BOOT__ || { companies: [], groups: [] };
  var DETAILS = window.__DETAILS__ || null; // 정적 스냅샷일 때만 존재
  var EOK = 1e8; // 1억원

  var state = {
    group: 'all',
    metric: 'assets', // 'assets' | 'mcap'
    currency: 'KRW',
    view: 'map', // 'map' | 'table'
  };

  var detailCache = {};

  /* ─────────────────────── 포맷 ─────────────────────── */

  function fx(won) {
    if (state.currency === 'KRW') return won;
    var rate = BOOT.usdkrw;
    return rate ? won / rate : null;
  }

  function sym() {
    return state.currency === 'KRW' ? '₩' : '$';
  }

  /** 큰 금액: KRW는 조/억, USD는 B/M */
  function bigMoney(won) {
    if (won === null || won === undefined) return '—';
    var v = fx(won);
    if (v === null) return '—';
    var neg = v < 0 ? '-' : '';
    v = Math.abs(v);
    if (state.currency === 'KRW') {
      if (v >= 1e12) return neg + '₩' + (v / 1e12).toFixed(1) + '조';
      if (v >= 1e8) return neg + '₩' + Math.round(v / 1e8).toLocaleString('ko-KR') + '억';
      return neg + '₩' + Math.round(v).toLocaleString('ko-KR');
    }
    if (v >= 1e9) return neg + '$' + (v / 1e9).toFixed(1) + 'B';
    if (v >= 1e6) return neg + '$' + (v / 1e6).toFixed(1) + 'M';
    return neg + '$' + Math.round(v).toLocaleString('en-US');
  }

  /** 주가 */
  function price(won) {
    if (won === null || won === undefined) return '—';
    var v = fx(won);
    if (v === null) return '—';
    if (state.currency === 'KRW') return '₩' + Math.round(v).toLocaleString('ko-KR');
    return '$' + v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function pct(v) {
    if (v === null || v === undefined) return '—';
    return (v > 0 ? '+' : '') + v.toFixed(2) + '%';
  }

  /* ─────────────────────── 색 구간 ─────────────────────── */

  function bin(p) {
    if (p === null || p === undefined) return 't-na';
    if (p <= -3) return 't-dn3';
    if (p <= -1.5) return 't-dn2';
    if (p <= -0.5) return 't-dn1';
    if (p < 0.5) return 't-flat';
    if (p < 1.5) return 't-up1';
    if (p < 3) return 't-up2';
    return 't-up3';
  }

  /* ─────────────────────── squarified treemap ─────────────────────── */

  function worstRatio(row, short, scale) {
    var areas = row.map(function (d) { return d.value * scale; });
    var sum = areas.reduce(function (a, b) { return a + b; }, 0);
    var mx = Math.max.apply(null, areas);
    var mn = Math.min.apply(null, areas);
    if (sum <= 0 || mn <= 0) return Infinity;
    return Math.max((short * short * mx) / (sum * sum), (sum * sum) / (short * short * mn));
  }

  function squarify(data, rect) {
    var out = [];
    var items = data.slice().filter(function (d) { return d.value > 0; })
      .sort(function (a, b) { return b.value - a.value; });
    var remTotal = items.reduce(function (s, d) { return s + d.value; }, 0);
    if (remTotal <= 0) return out;

    var x = rect.x, y = rect.y, w = rect.w, h = rect.h;

    while (items.length && w > 0.5 && h > 0.5) {
      var short = Math.min(w, h);
      var scale = (w * h) / remTotal;

      var row = [items[0]];
      var rowSum = items[0].value;
      var best = worstRatio(row, short, scale);
      for (var i = 1; i < items.length; i++) {
        var cand = row.concat([items[i]]);
        var r = worstRatio(cand, short, scale);
        if (r > best) break;
        row = cand;
        rowSum += items[i].value;
        best = r;
      }

      var rowArea = rowSum * scale;
      if (w >= h) {
        var rw = rowArea / h;
        var cy = y;
        for (var a = 0; a < row.length; a++) {
          var dh = (row[a].value * scale) / rw;
          out.push(place(row[a], x, cy, rw, dh));
          cy += dh;
        }
        x += rw; w -= rw;
      } else {
        var rh = rowArea / w;
        var cx = x;
        for (var b = 0; b < row.length; b++) {
          var dw = (row[b].value * scale) / rh;
          out.push(place(row[b], cx, y, dw, rh));
          cx += dw;
        }
        y += rh; h -= rh;
      }

      items = items.slice(row.length);
      remTotal -= rowSum;
    }
    return out;
  }

  function place(d, x, y, w, h) {
    var o = {};
    for (var k in d) o[k] = d[k];
    o.x = x; o.y = y; o.w = w; o.h = h;
    return o;
  }

  /* ─────────────────────── 데이터 선택 ─────────────────────── */

  function sizeOf(c) {
    if (state.metric === 'mcap') return c.market_cap || 0;
    return (c.assets || 0) * EOK;
  }

  /** 현재 필터·기준에 해당하는 회사. 시총 기준에서는 시가총액이 없는 회사를 제외합니다. */
  function visible() {
    return BOOT.companies.filter(function (c) {
      if (state.group !== 'all' && c.group !== state.group) return false;
      return sizeOf(c) > 0;
    });
  }

  function excludedCount() {
    var all = BOOT.companies.filter(function (c) {
      return state.group === 'all' || c.group === state.group;
    });
    return all.length - visible().length;
  }

  /* ─────────────────────── 렌더: 트리맵 ─────────────────────── */

  function renderMap() {
    var el = document.getElementById('map');
    var W = el.clientWidth;
    if (!W) return;

    var narrow = W < 720;
    var cos = visible();

    if (!cos.length) {
      el.style.height = '160px';
      el.innerHTML = '<p class="skel">표시할 회사가 없습니다.</p>';
      renderNote();
      return;
    }

    var H = narrow
      ? Math.max(700, Math.round(W * 1.9))
      : Math.max(460, Math.round(window.innerHeight * 0.74));
    el.style.height = H + 'px';

    // 그룹 묶음 (필터로 비게 된 그룹은 제외)
    var groups = BOOT.groups.map(function (g) {
      var members = cos.filter(function (c) { return c.group === g.id; });
      return {
        id: g.id, no: g.no, name: g.name, members: members,
        value: members.reduce(function (s, c) { return s + sizeOf(c); }, 0),
      };
    }).filter(function (g) { return g.value > 0; });

    var gpad = 3;
    var boxes;
    if (narrow) {
      // 좁은 화면에서는 그룹을 위→아래로 쌓습니다 (가로 압축 방지)
      var total = groups.reduce(function (s, g) { return s + g.value; }, 0);
      var cy = 0;
      boxes = groups.map(function (g) {
        var gh = Math.max(150, (g.value / total) * H);
        var box = place(g, 0, cy, W, gh);
        cy += gh;
        return box;
      });
      el.style.height = Math.round(cy) + 'px';
    } else {
      boxes = squarify(groups, { x: 0, y: 0, w: W, h: H });
    }

    var html = '';
    boxes.forEach(function (g) {
      var iw = g.w - gpad * 2;
      var ih = g.h - 24 - gpad; // 헤더 높이 제외

      // 그룹 상자 면적은 실제 합계에 비례합니다. 그래서 작은 분야(재보험·보증은
      // 업계 총자산의 2% 남짓)는 트리맵으로 그리면 읽을 수 없는 띠가 됩니다.
      // 면적을 부풀려 속이는 대신, 그 그룹만 균등폭 칩으로 바꾸고 헤더에 밝힙니다.
      var asStrip = ih < 64;

      html +=
        '<div class="grp" style="left:' + g.x + 'px;top:' + g.y + 'px;width:' + (g.w - 1) + 'px;height:' + (g.h - 1) + 'px">' +
        '<div class="ghead"><span class="no">' + esc(g.no) + '</span><b>' + esc(g.name) + '</b>' +
        '<span class="gtot">' + g.members.length + '개사 · ' + bigMoney(g.value) +
        (asStrip ? ' · 좁아서 균등폭 표시' : '') + '</span></div>';

      var members = g.members.map(function (c) {
        var o = {}; for (var k in c) o[k] = c[k];
        o.value = sizeOf(c);
        return o;
      });

      if (asStrip) {
        html += '<div class="chips">';
        members.sort(function (a, b) { return b.value - a.value; }).forEach(function (c) {
          html += '<button type="button" class="chiptile ' + bin(c.listed ? c.change_pct : null) + '" ' +
            'data-id="' + esc(c.id) + '" ' +
            'aria-label="' + esc(c.name + ' ' + (c.listed ? pct(c.change_pct) : '비상장')) + '">' +
            '<span class="tname">' + esc(c.name) + '</span>' +
            '<span class="tpct">' + (c.listed ? pct(c.change_pct) : '비상장') + '</span>' +
            '</button>';
        });
        html += '</div>';
      } else if (iw > 10 && ih > 10) {
        squarify(members, { x: gpad, y: 24, w: iw, h: ih })
          .forEach(function (t) { html += tileHtml(t); });
      }
      html += '</div>';
    });

    el.innerHTML = html;
    el.classList.remove('stale');
    renderNote();
    wireTiles();
  }

  function tileHtml(t) {
    var w = t.w - 2, h = t.h - 2;
    var showName = w > 42 && h > 22;
    var showPct = w > 52 && h > 34;
    var fsName = Math.max(9, Math.min(16, Math.round(Math.min(w / 6.2, h / 2.6))));
    var fsPct = Math.max(9, Math.min(13, fsName - 2));

    var inner = '';
    if (showName) {
      inner += '<span class="tname" style="font-size:' + fsName + 'px">' + esc(t.name) + '</span>';
      if (showPct) {
        inner += t.listed
          ? '<span class="tpct" style="font-size:' + fsPct + 'px">' + pct(t.change_pct) + '</span>'
          : '<span class="tflag" style="font-size:' + fsPct + 'px">비상장</span>';
      }
    }

    return '<button type="button" class="tile ' + bin(t.listed ? t.change_pct : null) + '" ' +
      'data-id="' + esc(t.id) + '" ' +
      'style="left:' + (t.x + 1) + 'px;top:' + (t.y + 1) + 'px;width:' + w + 'px;height:' + h + 'px" ' +
      'aria-label="' + esc(t.name + ' ' + (t.listed ? pct(t.change_pct) : '비상장')) + '">' +
      inner + '</button>';
  }

  function renderNote() {
    var n = excludedCount();
    var box = document.getElementById('note');
    if (state.metric === 'mcap' && n > 0) {
      box.hidden = false;
      box.textContent =
        '시가총액 기준에서는 시세가 없는 비상장 ' + n + '개사가 히트맵에서 제외됩니다. ' +
        '전체를 함께 비교하려면 크기 기준을 [총자산]으로 바꾸거나 [표로 보기]를 사용하세요.';
    } else {
      box.hidden = true;
    }
  }

  /* ─────────────────────── 렌더: 표 보기 ─────────────────────── */

  function renderTable() {
    var gname = {};
    BOOT.groups.forEach(function (g) { gname[g.id] = g.name; });

    var rows = BOOT.companies
      .filter(function (c) { return state.group === 'all' || c.group === state.group; })
      .sort(function (a, b) { return (b.assets || 0) - (a.assets || 0); })
      .map(function (c) {
        var cls = c.change_pct === null || c.change_pct === undefined ? ''
          : (c.change_pct > 0 ? 'up' : c.change_pct < 0 ? 'dn' : '');
        return '<tr><td>' + esc(gname[c.group] || c.group) + '</td>' +
          '<td><button type="button" class="linklike" data-id="' + esc(c.id) + '">' + esc(c.name) + '</button></td>' +
          '<td>' + (c.ticker ? esc(c.ticker) : '비상장') + '</td>' +
          '<td class="num">' + (c.listed ? price(c.price) : '—') + '</td>' +
          '<td class="num ' + cls + '">' + (c.listed ? pct(c.change_pct) : '—') + '</td>' +
          '<td class="num">' + (c.market_cap ? bigMoney(c.market_cap) : '—') + '</td>' +
          '<td class="num">' + bigMoney((c.assets || 0) * EOK) + '</td></tr>';
      }).join('');

    document.getElementById('tbody').innerHTML = rows;
    document.querySelectorAll('#tbody .linklike').forEach(function (b) {
      b.addEventListener('click', function () { openPanel(b.dataset.id); });
    });
  }

  /* ─────────────────────── 타일 상호작용 ─────────────────────── */

  var tip = null;

  function wireTiles() {
    document.querySelectorAll('#map .tile, #map .chiptile').forEach(function (t) {
      var c = byId(t.dataset.id);
      t.addEventListener('click', function () { openPanel(t.dataset.id); });
      t.addEventListener('mouseenter', function (e) { showTip(c, e); });
      t.addEventListener('mousemove', moveTip);
      t.addEventListener('mouseleave', hideTip);
      t.addEventListener('focus', function (e) { showTip(c, e); });
      t.addEventListener('blur', hideTip);
    });
  }

  function showTip(c, e) {
    if (!tip) {
      tip = document.createElement('div');
      tip.className = 'tip';
      document.body.appendChild(tip);
    }
    var rows =
      row('분야', groupName(c.group)) +
      (c.listed
        ? row('현재가', price(c.price)) + row('전일 대비', pct(c.change_pct)) + row('시가총액', bigMoney(c.market_cap))
        : row('상장 여부', '비상장')) +
      row('총자산', bigMoney((c.assets || 0) * EOK));
    tip.innerHTML = '<div class="tt">' + esc(c.name) + '</div><dl>' + rows + '</dl>';
    tip.hidden = false;
    moveTip(e);
  }

  function row(k, v) {
    return '<dt>' + esc(k) + '</dt><dd>' + esc(v) + '</dd>';
  }

  function moveTip(e) {
    if (!tip) return;
    var pad = 14;
    var w = tip.offsetWidth, h = tip.offsetHeight;
    var x = e.clientX + pad, y = e.clientY + pad;
    if (x + w > window.innerWidth - 8) x = e.clientX - w - pad;
    if (y + h > window.innerHeight - 8) y = e.clientY - h - pad;
    tip.style.left = Math.max(8, x) + 'px';
    tip.style.top = Math.max(8, y) + 'px';
  }

  function hideTip() {
    if (tip) tip.hidden = true;
  }

  /* ─────────────────────── 회사 패널 ─────────────────────── */

  function openPanel(id) {
    hideTip();
    if (location.hash !== '#c=' + id) {
      history.replaceState(null, '', '#c=' + id); // 주소 복사로 회사를 바로 열 수 있게
    }
    var panel = document.getElementById('panel');
    var scrim = document.getElementById('scrim');
    panel.hidden = false;
    scrim.hidden = false;
    panel.scrollTop = 0;
    panel.innerHTML = '<p class="skel">불러오는 중…</p>';

    getDetail(id).then(function (d) {
      panel.innerHTML = panelHtml(d);
      panel.querySelector('.xbtn').addEventListener('click', closePanel);
      panel.querySelectorAll('[data-cur]').forEach(function (b) {
        b.addEventListener('click', function () {
          state.currency = b.dataset.cur;
          syncControls();
          rerender();
          openPanel(id);
        });
      });
      wireChart(panel, d);
    }).catch(function () {
      panel.innerHTML =
        '<div class="phead"><div></div><button class="xbtn" type="button" aria-label="닫기">✕</button></div>' +
        '<p class="empty">회사 정보를 불러오지 못했습니다.</p>';
      panel.querySelector('.xbtn').addEventListener('click', closePanel);
    });
  }

  function closePanel() {
    document.getElementById('panel').hidden = true;
    document.getElementById('scrim').hidden = true;
    if (location.hash) history.replaceState(null, '', location.pathname + location.search);
  }

  function getDetail(id) {
    if (detailCache[id]) return Promise.resolve(detailCache[id]);
    if (DETAILS) {
      var d = DETAILS[id];
      if (!d) return Promise.reject(new Error('no snapshot'));
      detailCache[id] = d;
      return Promise.resolve(d);
    }
    return fetch('/api/company/' + encodeURIComponent(id))
      .then(function (r) {
        if (!r.ok) throw new Error('http ' + r.status);
        return r.json();
      })
      .then(function (d) { detailCache[id] = d; return d; });
  }

  function panelHtml(d) {
    var q = d.quote;
    var h = '';

    h += '<div class="phead"><div>' +
      '<div class="eyebrow">' + esc(d.group_no) + ' · ' + esc(d.group_name) + '</div>' +
      '<h2>' + esc(d.name) + '</h2>' +
      '<div class="idline">' + esc(d.name_en || '') +
      (d.ticker ? ' · ' + esc(d.ticker) : '') + '</div>' +
      '</div><button class="xbtn" type="button" aria-label="닫기">✕</button></div>';

    h += '<div class="badges">' +
      '<span class="badge' + (d.ticker ? ' listed' : '') + '">' + (d.ticker ? '상장' : '비상장') + '</span>' +
      '<span class="badge">' + esc(d.hq || '') + '</span>' +
      (d.verified ? '' : '<span class="badge">재무 개략치</span>') +
      '</div>';

    if (d.note) h += '<p class="fxnote">※ ' + esc(d.note) + '</p>';

    // 현재가 (상장사) / 비상장 안내
    if (q) {
      var pc = q.change_pct;
      var dcls = pc === null ? 'fl' : pc > 0 ? 'up' : pc < 0 ? 'dn' : 'fl';
      h += '<div class="hero"><span class="px">' + price(q.price) + '</span>' +
        '<span class="delta ' + dcls + '">' + pct(pc) + '</span></div>';
      h += currencyToggle();
      if (state.currency === 'USD') {
        h += '<p class="fxnote">Yahoo Finance 환율 기준 환산 (USD/KRW ' +
          (d.usdkrw ? Math.round(d.usdkrw).toLocaleString('ko-KR') : '—') + ')</p>';
      }
    } else if (d.quote_failed) {
      h += '<p class="empty" style="margin-top:14px">시세를 불러오지 못했습니다 (티커 ' + esc(d.ticker || '') + ').</p>';
    } else {
      h += '<p class="empty" style="margin-top:14px">비상장 — 시장 주가가 없습니다.' +
        (d.proxy_quote ? ' 참고로 상장 모회사 ' + esc(d.proxy_quote.ticker) + '는 ' +
          price(d.proxy_quote.price) + ' (' + pct(d.proxy_quote.change_pct) + ')입니다.' : '') +
        '</p>';
      h += currencyToggle();
    }

    // 주가 차트 — 단일 시리즈이므로 범례 없이 제목이 무엇을 그렸는지 말합니다
    var chartQ = q || d.proxy_quote;
    if (chartQ) {
      h += '<div class="sect"><h3>주가 차트 · 최근 ' + chartQ.series.length + '거래일' +
        (q ? '' : ' (모회사 ' + esc(chartQ.ticker) + ')') + '</h3>' + chartCard(chartQ) + '</div>';
    }

    // 재무 분석 — 출처와 기준(별도/연결)을 제목에 밝힙니다
    var finLabel = d.verified
      ? (d.dart_year || '') + ' 사업보고서' + (d.fs_basis ? ' · ' + d.fs_basis : '') + ' (DART)'
      : '개략치 · DART 정기보고서 미제출';
    h += '<div class="sect"><h3>재무 분석 <span class="qual">' + esc(finLabel) + '</span></h3><div class="stats">';
    h += stat('시가총액', d.market_cap ? bigMoney(d.market_cap) : '—');
    h += stat('총자산', bigMoney((d.assets || 0) * EOK));
    if (d.liabilities) h += stat('부채총계', bigMoney(d.liabilities * EOK));
    h += stat('자본총계', bigMoney((d.equity || 0) * EOK), (d.equity || 0) < 0);
    if (d.insurance_liabilities) {
      h += stat('보험계약부채', bigMoney(d.insurance_liabilities * EOK));
    }
    if (d.operating_income !== undefined && d.operating_income !== null) {
      h += stat('영업이익', bigMoney(d.operating_income * EOK), d.operating_income < 0);
    }
    h += stat('당기순이익', bigMoney((d.net_income || 0) * EOK), (d.net_income || 0) < 0);
    h += stat('PER', d.ratios.per !== null ? d.ratios.per.toFixed(1) : '—', false, true);
    h += stat('PBR', d.ratios.pbr !== null ? d.ratios.pbr.toFixed(2) : '—', false, true);
    h += stat('ROE', d.ratios.roe !== null ? d.ratios.roe.toFixed(1) + '%' : '—',
      (d.ratios.roe || 0) < 0, true);
    h += stat('K-ICS 비율', d.kics ? d.kics.toFixed(1) + '%' : '—', false, false, '직접 입력');
    if (q) {
      h += stat('52주 최고', price(q.high_52w));
      h += stat('52주 최저', price(q.low_52w));
    }
    h += '</div></div>';

    // 주요 주주
    var shSrc = (d.shareholders || []).some(function (s) { return s.source; })
      ? '최대주주 현황 · 대량보유 보고 (DART)' : '';
    h += '<div class="sect"><h3>주요 주주' +
      (shSrc ? ' <span class="qual">' + esc(shSrc) + '</span>' : '') + '</h3>';
    if (d.shareholders && d.shareholders.length) {
      h += '<div class="rows">';
      d.shareholders.forEach(function (s) {
        h += '<div class="row"><span class="rn">' + esc(s.name) + '</span>' +
          '<span class="rs">' + (s.stake === null || s.stake === undefined ? '—' : s.stake.toFixed(2) + '%') + '</span>' +
          '<span class="rr">' + esc(s.role || '') + '</span></div>';
      });
      h += '</div>';
    } else {
      h += '<p class="empty">등록된 주주 정보가 없습니다. 관리자모드 → 보험사 데이터에서 추가하세요.</p>';
    }
    h += '</div>';

    // 최근 뉴스
    h += '<div class="sect"><h3>최근 주요 뉴스</h3>';
    if (d.news && d.news.length) {
      h += '<div class="rows news">';
      d.news.forEach(function (n) {
        h += '<a href="' + esc(n.url) + '" target="_blank" rel="noopener">' +
          '<div class="nt">' + esc(n.title) + '</div>' +
          '<div class="ns">' + esc(n.source) + (n.date ? ' · ' + esc(n.date) : '') + '</div></a>';
      });
      h += '</div>';
    } else if (!d.news_available) {
      h += '<p class="empty">네이버 API 키(NAVER_CLIENT_ID/SECRET)가 없어 뉴스를 조회하지 않았습니다.</p>';
    } else {
      h += '<p class="empty">최근 관련 기사를 찾지 못했습니다.</p>';
    }
    h += '</div>';

    // 출처 — DART 공시 원문으로 바로 갈 수 있게
    h += '<div class="sect"><h3>출처</h3><div class="rows src">';
    h += '<div class="row"><span class="rn">주가 · 시가총액 · 52주 고저 · 주가차트</span>' +
      '<span class="rr">Yahoo Finance</span></div>';
    if (d.dart_filing) {
      h += '<a class="row" href="' + esc(d.dart_filing.url) + '" target="_blank" rel="noopener">' +
        '<span class="rn">' + esc(d.dart_filing.report_nm) + '</span>' +
        '<span class="rr">DART 원문 ↗</span></a>';
    }
    if (d.news && d.news.length) {
      h += '<div class="row"><span class="rn">최근 주요 뉴스</span>' +
        '<span class="rr">네이버 뉴스 검색</span></div>';
    }
    h += '</div>';

    h += '<p class="fxnote">' + (d.verified
      ? '재무는 ' + esc(d.dart_period || d.as_of || '') + ' DART 사업보고서 ' +
        esc(d.fs_basis || '') + ' 기준입니다. '
      : '이 회사는 DART 정기보고서를 제출하지 않아 재무가 <b>개략치</b>입니다. ' +
        '위 감사보고서 원문을 열어 관리자모드에서 교정하세요. ') +
      'PER·PBR·ROE는 시가총액을 이 재무값으로 나눈 추정치이고, K-ICS 비율은 DART 에 없는 ' +
      '감독지표라 직접 입력값입니다.</p></div>';

    return h;
  }

  function currencyToggle() {
    return '<div class="ctl" style="margin-top:10px"><div class="seg">' +
      ['KRW', 'USD'].map(function (c) {
        return '<button type="button" data-cur="' + c + '" aria-pressed="' +
          (state.currency === c) + '">' + c + '</button>';
      }).join('') + '</div></div>';
  }

  function stat(k, v, neg, est, note) {
    return '<div class="stat' + (est ? ' est' : '') + '"><div class="k">' + esc(k) +
      (note ? '<span class="kn">' + esc(note) + '</span>' : '') + '</div>' +
      '<div class="v' + (neg ? ' neg' : '') + '">' + esc(v) + '</div></div>';
  }

  /* ─────────────────────── 주가 차트 (SVG) ─────────────────────── */

  var CH = { w: 400, h: 132, pad: 8 };

  function chartCard(q) {
    var pts = q.series;
    var lo = q.series_min, hi = q.series_max;
    var span = hi - lo || 1;
    var innerW = CH.w - CH.pad * 2;
    var innerH = CH.h - CH.pad * 2;

    var xy = pts.map(function (p, i) {
      return {
        x: CH.pad + (pts.length === 1 ? innerW / 2 : (i / (pts.length - 1)) * innerW),
        y: CH.pad + innerH - ((p.c - lo) / span) * innerH,
        c: p.c,
        t: p.t,
      };
    });

    var line = xy.map(function (p, i) {
      return (i ? 'L' : 'M') + p.x.toFixed(1) + ' ' + p.y.toFixed(1);
    }).join(' ');
    var area = line + ' L' + xy[xy.length - 1].x.toFixed(1) + ' ' + (CH.h - CH.pad) +
      ' L' + xy[0].x.toFixed(1) + ' ' + (CH.h - CH.pad) + ' Z';

    var last = xy[xy.length - 1];

    return '<div class="card chartcard" data-series=\'' + JSON.stringify(xy).replace(/'/g, '&#39;') + '\'>' +
      '<div class="cmeta"><span>최저 ' + price(lo) + '</span><span>최고 ' + price(hi) + '</span></div>' +
      '<svg viewBox="0 0 ' + CH.w + ' ' + CH.h + '" preserveAspectRatio="none" role="img" ' +
      'aria-label="최근 ' + pts.length + '거래일 종가 추이">' +
      '<path d="' + area + '" fill="var(--series-1)" fill-opacity="0.1"/>' +
      '<path d="' + line + '" fill="none" stroke="var(--series-1)" stroke-width="2" ' +
      'stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>' +
      '<line class="cross" x1="0" y1="0" x2="0" y2="' + CH.h + '" stroke="var(--baseline)" ' +
      'stroke-width="1" vector-effect="non-scaling-stroke" visibility="hidden"/>' +
      '<circle class="dot" r="4.5" cx="' + last.x.toFixed(1) + '" cy="' + last.y.toFixed(1) + '" ' +
      'fill="var(--series-1)" stroke="var(--surface-1)" stroke-width="2"/>' +
      '</svg>' +
      '<div class="xlab"><span>' + dstr(pts[0].t) + '</span><span>' + dstr(pts[pts.length - 1].t) + '</span></div>' +
      '</div>';
  }

  function wireChart(panel, d) {
    var card = panel.querySelector('.chartcard');
    if (!card) return;
    var svg = card.querySelector('svg');
    var cross = card.querySelector('.cross');
    var dot = card.querySelector('.dot');
    var xy = JSON.parse(card.dataset.series);
    var lastCx = dot.getAttribute('cx');
    var lastCy = dot.getAttribute('cy');

    // 히트 영역은 마크보다 크게 — 차트 카드 전체가 크로스헤어 대상
    svg.addEventListener('mousemove', function (e) {
      var r = svg.getBoundingClientRect();
      var vx = ((e.clientX - r.left) / r.width) * CH.w;
      var near = xy[0], bestd = Infinity;
      for (var i = 0; i < xy.length; i++) {
        var dd = Math.abs(xy[i].x - vx);
        if (dd < bestd) { bestd = dd; near = xy[i]; }
      }
      cross.setAttribute('x1', near.x);
      cross.setAttribute('x2', near.x);
      cross.setAttribute('visibility', 'visible');
      dot.setAttribute('cx', near.x);
      dot.setAttribute('cy', near.y);
      showTipRaw('<div class="tt">' + price(near.c) + '</div><dl>' +
        row('일자', dstr(near.t)) + '</dl>', e);
    });
    svg.addEventListener('mouseleave', function () {
      cross.setAttribute('visibility', 'hidden');
      dot.setAttribute('cx', lastCx);
      dot.setAttribute('cy', lastCy);
      hideTip();
    });
  }

  function showTipRaw(html, e) {
    if (!tip) {
      tip = document.createElement('div');
      tip.className = 'tip';
      document.body.appendChild(tip);
    }
    tip.innerHTML = html;
    tip.hidden = false;
    moveTip(e);
  }

  function dstr(unixSec) {
    var d = new Date(unixSec * 1000);
    return d.getFullYear() + '.' +
      String(d.getMonth() + 1).padStart(2, '0') + '.' +
      String(d.getDate()).padStart(2, '0');
  }

  /* ─────────────────────── 컨트롤 ─────────────────────── */

  function syncControls() {
    document.querySelectorAll('[data-group]').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.dataset.group === state.group));
    });
    document.querySelectorAll('[data-metric]').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.dataset.metric === state.metric));
    });
    document.querySelectorAll('#controls [data-cur]').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.dataset.cur === state.currency));
    });
    document.querySelectorAll('[data-view]').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.dataset.view === state.view));
    });
  }

  function rerender() {
    var mapWrap = document.getElementById('mapwrap');
    var table = document.getElementById('tableview');
    mapWrap.hidden = state.view !== 'map';
    table.hidden = state.view !== 'table';
    if (state.view === 'map') renderMap(); else renderTable();
  }

  function wireControls() {
    document.getElementById('controls').addEventListener('click', function (e) {
      var b = e.target.closest('button');
      if (!b) return;
      if (b.dataset.group) state.group = b.dataset.group;
      else if (b.dataset.metric) state.metric = b.dataset.metric;
      else if (b.dataset.cur) state.currency = b.dataset.cur;
      else if (b.dataset.view) state.view = b.dataset.view;
      else return;
      syncControls();
      document.getElementById('map').classList.add('stale');
      rerender();
    });

    document.getElementById('scrim').addEventListener('click', closePanel);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closePanel();
    });

    var t;
    window.addEventListener('resize', function () {
      clearTimeout(t);
      t = setTimeout(function () { if (state.view === 'map') renderMap(); }, 140);
    });
  }

  /* ─────────────────────── 유틸 ─────────────────────── */

  function byId(id) {
    return BOOT.companies.filter(function (c) { return c.id === id; })[0] || {};
  }

  function groupName(gid) {
    var g = BOOT.groups.filter(function (x) { return x.id === gid; })[0];
    return g ? g.name : gid;
  }

  function esc(s) {
    return String(s === null || s === undefined ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  /* ─────────────────────── 시작 ─────────────────────── */

  wireControls();
  syncControls();
  rerender();

  // #c=<회사id> 로 들어오면 그 회사 패널을 바로 엽니다 (주소 공유용)
  var deep = /^#c=(.+)$/.exec(location.hash || '');
  if (deep && byId(decodeURIComponent(deep[1])).id) {
    openPanel(decodeURIComponent(deep[1]));
  }
  window.addEventListener('hashchange', function () {
    var m = /^#c=(.+)$/.exec(location.hash || '');
    if (m) openPanel(decodeURIComponent(m[1]));
    else closePanel();
  });
})();
