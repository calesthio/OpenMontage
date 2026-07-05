import { escapeHtml } from "../format.js";

export function renderTopbar({ pages, activePage }) {
  return `
    <header class="topbar">
      <div class="brand">
        <span class="brand__name">赤灵AI运营工作台</span>
        <span class="brand__tagline">内容复刻 · 审核 · 交付</span>
      </div>
      <nav class="nav" aria-label="主导航">
        ${pages
          .map(
            (page) => `
              <button class="nav__item ${page.id === activePage ? "is-active" : ""}" data-route="${escapeHtml(page.id)}">
                ${escapeHtml(page.label)}
              </button>
            `,
          )
          .join("")}
      </nav>
      <div class="topbar__spacer"></div>
      <button class="button button--primary button--small" data-route="create">新建作品</button>
    </header>
  `;
}
