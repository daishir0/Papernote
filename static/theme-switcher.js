/* theme-switcher.js
   Markdown 表示テーマの切替・永続化。
   - localStorage キー: 'paperTheme'
   - <html data-theme="..."> をセット
   - <link id="theme-css"> の href を /static/themes/<name>.css に差し替え
   - mermaid を data-theme 連動で再初期化（dark/business は dark/forest, それ以外は default）
   ※ <head> インラインで FOUC 回避済みの初期適用は post.html / edit_post.html 側で実施。
     ここでは UI からの切替・mermaid連動・他タブからのストレージ同期を担当。 */
(function () {
  'use strict';

  /* hidden:true のテーマはメニューには出さないが、localStorage 値としては有効。
     → 過去に切り替えた人や、URL/手動で paperTheme を設定した場合に備えて残す。 */
  var THEMES = [
    { id: 'mono',     label: '既定（モノクロ）' },
    { id: 'qiita',    label: 'Qiita風' },
    { id: 'business', label: 'ビジネス文書（MS Word風）' },
    { id: 'dark',     label: 'ダーク' },
    { id: 'default',  label: '古い既定',          hidden: true },
    { id: 'github',   label: 'GitHub風',           hidden: true },
    { id: 'zenn',     label: 'Zenn風',             hidden: true },
    { id: 'notion',   label: 'Notion風',           hidden: true },
    { id: 'academic', label: '学術論文（LaTeX風）', hidden: true },
    { id: 'formal',   label: '官公庁・契約書風',   hidden: true },
    { id: 'sepia',    label: 'セピア',             hidden: true }
  ];
  var STORAGE_KEY = 'paperTheme';
  var DEFAULT = 'mono';

  function isAllowed(name) {
    for (var i = 0; i < THEMES.length; i++) if (THEMES[i].id === name) return true;
    return false;
  }

  function getStoredTheme() {
    try {
      var t = localStorage.getItem(STORAGE_KEY);
      if (t && isAllowed(t)) return t;
    } catch (e) {}
    return DEFAULT;
  }

  function saveTheme(name) {
    try { localStorage.setItem(STORAGE_KEY, name); } catch (e) {}
  }

  function applyTheme(name) {
    if (!isAllowed(name)) name = DEFAULT;
    document.documentElement.setAttribute('data-theme', name);
    var link = document.getElementById('theme-css');
    if (link) {
      var newHref = '/static/themes/' + name + '.css';
      if (link.getAttribute('href') !== newHref) link.setAttribute('href', newHref);
    }
    // mermaid 連動（mermaid が読み込まれている時のみ）
    try {
      if (window.mermaid && typeof window.mermaid.initialize === 'function') {
        var mermaidTheme = (name === 'dark') ? 'dark' : 'default';
        window.mermaid.initialize({ startOnLoad: false, theme: mermaidTheme });
      }
    } catch (e) {}
    // ラジオの状態同期
    var radios = document.querySelectorAll('input[name="paper-theme-radio"]');
    radios.forEach(function (r) { r.checked = (r.value === name); });
  }

  function buildMenuItems(container) {
    if (!container) return;
    if (container.dataset.themeMenuBuilt === '1') return;
    container.dataset.themeMenuBuilt = '1';
    var current = getStoredTheme();
    THEMES.forEach(function (t) {
      if (t.hidden) return; // メニューには出さない（localStorage 値としては有効）
      var label = document.createElement('label');
      label.className = 'theme-menu-item';
      label.style.display = 'flex';
      label.style.alignItems = 'center';
      label.style.gap = '8px';
      label.style.padding = '6px 10px';
      label.style.cursor = 'pointer';
      label.style.whiteSpace = 'nowrap';
      /* 他メニュー項目（.options-menu-item: color #333）と揃える。
         dark テーマ時は body color が薄色になるため、ここで明示しないと灰色化する。 */
      label.style.color = '#333';

      var radio = document.createElement('input');
      radio.type = 'radio';
      radio.name = 'paper-theme-radio';
      radio.value = t.id;
      radio.checked = (t.id === current);
      radio.addEventListener('change', function () {
        if (radio.checked) {
          applyTheme(t.id);
          saveTheme(t.id);
        }
      });

      var span = document.createElement('span');
      span.textContent = t.label;

      label.appendChild(radio);
      label.appendChild(span);
      container.appendChild(label);
    });
  }

  // 他タブからの同期
  window.addEventListener('storage', function (e) {
    if (e.key === STORAGE_KEY && e.newValue) applyTheme(e.newValue);
  });

  // 初期化（FOUC回避ですでに data-theme は付いているはず。ここでは mermaid 連動・ラジオ同期）
  function init() {
    applyTheme(getStoredTheme());
    var containers = document.querySelectorAll('[data-theme-menu]');
    containers.forEach(buildMenuItems);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // 外部から呼べるよう公開
  window.PaperTheme = {
    apply: function (name) { applyTheme(name); saveTheme(name); },
    get: getStoredTheme,
    list: function () { return THEMES.slice(); }
  };
})();
