/* heading-indent.js
   Markdown描画後の DOM を走査し、見出し（H1〜H6）の後に続く兄弟要素に
   data-h-level="N" を付与する。CSS 側（styles.css）の
   #content [data-h-level="N"] / #preview-content [data-h-level="N"]
   ルールが margin-inline-start で字下げを当てる。

   設計方針:
   - 見出し自身には付けない（H1 click 委譲・TOC生成・id付与を保護）
   - DOM構造を変えない（<section> ラップしない）
   - 直接子に H1〜H6 を含む <div>（遅延ロード wrapper など）は「透過扱い」：
     その div 自身には data-h-level を付けず、内側に再帰する
     ctx を共有することで、wrapper を跨いだ level 引き継ぎも維持
   - <table-responsive>・<.mermaid>・edit_post の code-block <div> など、
     直下に見出しを持たない div は通常コンテンツ扱い（ブロック indent） */
(function () {
  'use strict';

  function applyHeadingIndent(root, ctx) {
    if (!root || !root.children) return;
    if (!ctx) ctx = { level: 0 };

    var children = Array.prototype.slice.call(root.children);
    children.forEach(function (el) {
      var tag = el.tagName;
      var hm = tag && tag.match(/^H([1-6])$/);

      if (hm) {
        ctx.level = parseInt(hm[1], 10);
        if (el.hasAttribute('data-h-level')) el.removeAttribute('data-h-level');
        return;
      }

      // 直下に見出しを持つ <div> = 透過 wrapper（遅延ロードのセクションコンテナ等）
      var isHeadingWrapper = tag === 'DIV' &&
        el.querySelector(':scope > h1, :scope > h2, :scope > h3, :scope > h4, :scope > h5, :scope > h6');

      if (isHeadingWrapper) {
        if (el.hasAttribute('data-h-level')) el.removeAttribute('data-h-level');
        applyHeadingIndent(el, ctx); // ctx 共有で level を引き継ぐ
        return;
      }

      // 通常コンテンツ：現在 level で属性付与（level=0 のときは付与しない）
      if (ctx.level > 0) {
        el.setAttribute('data-h-level', String(ctx.level));
      } else {
        if (el.hasAttribute('data-h-level')) el.removeAttribute('data-h-level');
      }
    });
  }

  window.PaperHeadingIndent = { apply: applyHeadingIndent };
})();
