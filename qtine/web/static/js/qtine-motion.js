/*!
 * Qtine WebUI Motion & Skeleton — SPA-style navigation + skeleton runtime
 *
 * 核心思路（解决 MPA 白屏）：
 *   点击侧栏导航 → preventDefault → fetch 目标页 HTML → 在【当前文档内】
 *   替换 <body> 与 per-page <style>，并用 View Transition 包裹这次替换。
 *   旧页面 DOM 在新内容就绪前始终可见，因此【任何浏览器都不会白屏】。
 *
 * 依照 mdui 2.x / MD3 规范，无第三方运行时依赖。
 */
(function () {
  'use strict';

  var win = window;
  var doc = document;

  /* ── 偏好检测 ───────────────────────────────────────── */
  function reducedMotion() {
    return win.matchMedia &&
           win.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  /* ── 切换前清理：停止旧页的轮询定时器，避免内存泄漏 / 重复请求 ─── */
  // 记录页面脚本执行前的定时器 ID 基线，清理时只清基线之后【应用层】新增的，
  // 不触碰 mdui / 浏览器内部的定时器（高 ID 或外部库的）。
  var timerBaseline = 0;
  function recordTimerBaseline() {
    timerBaseline = setTimeout(function () {}, 0); // 获取当前最大 ID 近似值
  }
  function cleanupPrevPage() {
    if (!timerBaseline) return;
    var now = setTimeout(function () {}, 0);
    for (var i = timerBaseline; i <= now + 1; i++) {
      clearInterval(i);
      clearTimeout(i);
    }
    // 更新基线到本次脚本执行前
    recordTimerBaseline();
  }

  /* ── 解析目标页 HTML ────────────────────────────────── */
  function parsePage(htmlText) {
    var doc2 = new DOMParser().parseFromString(htmlText, 'text/html');
    // per-page style（每个 Qtine 页面 head 内有且仅有 1 个 inline <style>）
    var style = doc2.querySelector('head > style');
    // 收集 body 内所有 script（含 src，如 dashboard 的 chart.js；以及 IIFE）
    var scripts = [];
    doc2.querySelectorAll('body > script').forEach(function (s) {
      // 跳过共享脚本（qtine-motion.js / mdui）—— 它们已在 head/当前文档加载过
      var src = s.getAttribute('src') || '';
      if (src.indexOf('qtine-motion.js') !== -1 || src.indexOf('mdui') !== -1) return;
      scripts.push(s);
    });
    return {
      head: doc2.head,
      body: doc2.body,
      title: doc2.title,
      style: style,
      scripts: scripts
    };
  }

  /* ── 执行目标页脚本（克隆后重插入才会执行）──────────────
   * 外部 <script src> 必须串行等待加载，否则依赖它的内联脚本会
   * 在依赖未就绪时执行（例如 dashboard 的 Chart.js → new Chart()）。
   */
  function runScripts(scriptList, done) {
    var i = 0;
    function next() {
      if (i >= scriptList.length) { if (done) done(); return; }
      var s = scriptList[i++];
      var clone = doc.createElement('script');
      if (s.src) {
        clone.src = s.src;
        if (s.type) clone.type = s.type;
        clone.onload = next;
        clone.onerror = next; // 加载失败也继续，避免卡死
        doc.body.appendChild(clone);
      } else {
        clone.textContent = s.textContent;
        if (s.type) clone.type = s.type;
        doc.body.appendChild(clone);
        doc.body.removeChild(clone); // 内联立即执行，可移除
        next();
      }
    }
    next();
  }

  /* ── 替换页面内容（不刷新文档）──────────────────────── */
  function applyPage(parsed) {
    // 1. 替换 per-page <style>：移除旧 #qtine-page-style，插入新的
    var oldStyle = doc.getElementById('qtine-page-style');
    if (oldStyle) oldStyle.remove();
    if (parsed.style) {
      var newStyle = parsed.style.cloneNode(true);
      newStyle.id = 'qtine-page-style';
      // 插在共享 motion.css 之前，让 per-page 样式优先级正确
      var motionCss = doc.querySelector('link[href*="qtine-motion.css"]');
      if (motionCss) motionCss.parentNode.insertBefore(newStyle, motionCss);
      else doc.head.appendChild(newStyle);
    }

    // 2. 替换 <body>（含顶栏、侧栏、main、modal、snackbar 等；
    //    script 由 innerHTML 注入后不会执行，下面手动 runScripts）
    doc.body.innerHTML = parsed.body.innerHTML;

    // 3. 标题
    if (parsed.title) doc.title = parsed.title;

    // 4. 重新执行目标页的脚本（含 chart.js 等外部 + IIFE 内联；
    //    load() 在 IIFE 中被调用，会自动渲染骨架+数据）
    //    执行前记录定时器基线，以便下次切换时只清理本页新增的定时器
    recordTimerBaseline();
    runScripts(parsed.scripts);
  }

  /* ── SPA 导航主流程 ─────────────────────────────────── */
  var navigating = false;

  function navigate(url, pushState) {
    if (navigating) return;
    if (url === win.location.pathname + win.location.search) {
      return; // 已在当前页，忽略
    }
    navigating = true;

    cleanupPrevPage();

    var doSwap = function () {
      fetch(url, { headers: { 'X-Requested-With': 'Qtine-SPA' }, credentials: 'same-origin' })
        .then(function (r) {
          if (r.status === 401) { win.location.href = '/webui/login'; return null; }
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.text();
        })
        .then(function (html) {
          if (html == null) return;
          var parsed = parsePage(html);
          var apply = function () { applyPage(parsed); };
          // 用 View Transition 包裹替换；不支持则直接替换（仍无白屏）
          if ('startViewTransition' in doc && !reducedMotion()) {
            doc.startViewTransition(apply);
          } else {
            apply();
          }
          if (pushState !== false) {
            win.history.pushState({ spa: true, url: url }, '', url);
          }
        })
        .catch(function (e) {
          // fetch 失败（离线/服务器错误）→ 回退为原生跳转
          win.location.href = url;
        })
        .finally(function () { navigating = false; });
    };

    doSwap();
  }
  win.qtineNavigate = navigate;

  /* ── 拦截侧栏导航点击 ───────────────────────────────── */
  function onClick(e) {
    var a = e.target.closest('a.nav-item');
    if (!a) return;
    var href = a.getAttribute('href');
    if (!href || href.indexOf('/webui/') !== 0) return;
    // 修饰键（新标签打开）→ 放行原生行为
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    e.preventDefault();
    navigate(href, true);
  }
  doc.addEventListener('click', onClick);

  /* ── 浏览器前进/后退 ────────────────────────────────── */
  win.addEventListener('popstate', function (e) {
    var url = win.location.pathname + win.location.search;
    navigate(url, false);
  });

  /* ── 骨架渲染助手（与之前一致）──────────────────────── */
  function el(tag, cls, html) {
    var n = doc.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    return n;
  }
  function container(sel) {
    return typeof sel === 'string' ? doc.querySelector(sel) : sel;
  }

  function qtineSkel(sel, count) {
    var box = container(sel);
    if (!box) return;
    box.innerHTML = '';
    for (var i = 0; i < count; i++) {
      var card = el('div', 'card skel-card');
      card.appendChild(el('span', 'skel skel-title'));
      card.appendChild(el('span', 'skel skel-meta'));
      card.appendChild(el('span', 'skel skel-line w90'));
      card.appendChild(el('span', 'skel skel-line w60'));
      var act = el('div', 'skel-actions');
      act.appendChild(el('span', 'skel a1'));
      act.appendChild(el('span', 'skel a2'));
      act.appendChild(el('span', 'skel a3'));
      card.appendChild(act);
      box.appendChild(card);
    }
  }
  win.qtineSkel = qtineSkel;

  function qtineSkelTable(sel, count) {
    var box = container(sel);
    if (!box) return;
    box.innerHTML = '';
    for (var i = 0; i < count; i++) {
      var card = el('div', 'card skel-card');
      var head = el('div');
      head.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:8px';
      head.appendChild(el('span', 'skel skel-title'));
      head.appendChild(el('span', 'skel'));
      head.lastChild.style.cssText = 'height:20px;width:56px;border-radius:8px';
      card.appendChild(head);
      var tbl = el('div', 'skel-table');
      for (var j = 0; j < 4; j++) tbl.appendChild(el('span', 'skel skel-line w80'));
      card.appendChild(tbl);
      box.appendChild(card);
    }
  }
  win.qtineSkelTable = qtineSkelTable;

  function qtineSkelText(sel, count) {
    var box = container(sel);
    if (!box) return;
    box.innerHTML = '';
    for (var i = 0; i < count; i++) {
      var row = el('div');
      row.style.cssText = 'padding:12px 0;border-bottom:1px solid var(--olv)';
      row.appendChild(el('span', 'skel skel-line w40'));
      row.appendChild(el('span', 'skel skel-line w80'));
      row.appendChild(el('span', 'skel skel-line w60'));
      box.appendChild(row);
    }
  }
  win.qtineSkelText = qtineSkelText;

  function qtineSkelBlock(sel, height) {
    var box = container(sel);
    if (!box) return;
    box.innerHTML = '';
    var b = el('div', 'skel skel-block');
    if (height) b.style.height = height;
    box.appendChild(b);
  }
  win.qtineSkelBlock = qtineSkelBlock;

  function qtineSkelStats(sel, count) {
    var box = container(sel);
    if (!box) return;
    box.innerHTML = '';
    for (var i = 0; i < count; i++) box.appendChild(el('div', 'skel skel-stat'));
  }
  win.qtineSkelStats = qtineSkelStats;

  function qtineSkelFields(sel, count) {
    var box = container(sel);
    if (!box) return;
    box.innerHTML = '';
    for (var i = 0; i < count; i++) {
      var f = el('div', 'skel-field');
      f.appendChild(el('span', 'skel skel-label'));
      f.appendChild(el('span', 'skel skel-input'));
      box.appendChild(f);
    }
  }
  win.qtineSkelFields = qtineSkelFields;

  function qtineSkelClear(sel) {
    var box = container(sel);
    if (box) box.innerHTML = '';
  }
  win.qtineSkelClear = qtineSkelClear;
})();
