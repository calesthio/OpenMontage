import { escapeHtml } from "../format.js";

export function render({ state }) {
  if (!state.detailDrawerOpen) return "";

  const detail = state.taskDetail || {
    title: "任务详情",
    statusLabel: "加载中",
    progress: 0,
    paidGenerationStarted: false,
    sections: [],
  };
  const sections = Array.isArray(detail.sections) ? detail.sections : [];
  const sectionRows = sections.length
    ? sections.map(renderTaskDetailSection).join("")
    : `
      <section class="task-detail-section">
        <h3>生产准备包</h3>
        <div class="delivery-item">
          <i class="status-dot status-dot--amber"></i>
          <div>
            <strong>正在读取任务详情</strong>
            <span>请稍候，系统正在整理生产准备包、人工审核记录、生产执行审计和交付物。</span>
          </div>
        </div>
      </section>
    `;

  return `
    <aside class="task-detail-drawer" role="dialog" aria-modal="true" aria-label="任务详情">
      <button class="task-detail-drawer__scrim" type="button" aria-label="关闭任务详情" data-close-task-detail></button>
      <section class="task-detail-drawer__panel">
        <header class="task-detail-drawer__head">
          <div>
            <span class="pill pill--blue">任务详情</span>
            <h2 class="section-title" style="margin-top: 16px;">${escapeHtml(detail.title || "参考视频复刻")}</h2>
            <p class="lede">集中查看生产准备包、人工审核记录、生产执行审计和交付物。</p>
          </div>
          <button class="button button--small" data-close-task-detail>关闭</button>
        </header>
        <div class="task-detail-summary">
          <span>${escapeHtml(detail.statusLabel || "处理中")}</span>
          <strong>${escapeHtml(detail.progress || 0)}%</strong>
          <small>${detail.paidGenerationStarted ? "已启动生产" : "不会启动付费生成"}</small>
        </div>
        <div class="task-detail-sections">
          ${sectionRows}
        </div>
      </section>
    </aside>
  `;
}

function renderTaskDetailSection(section) {
  const items = Array.isArray(section.items) ? section.items : [];
  const itemRows = items.length
    ? items
        .map((item) => {
          const dotClass = item.state === "blocked" ? "status-dot--red" : item.state === "waiting" ? "status-dot--amber" : "status-dot--green";
          return `
            <div class="delivery-item">
              <i class="status-dot ${dotClass}"></i>
              <div>
                <strong>${escapeHtml(item.label || "详情")}</strong>
                <span>${escapeHtml(item.value || "等待更新")}</span>
              </div>
            </div>
          `;
        })
        .join("")
    : `
      <div class="delivery-item">
        <i class="status-dot status-dot--amber"></i>
        <div>
          <strong>等待更新</strong>
          <span>该部分暂无可展示信息。</span>
        </div>
      </div>
    `;

  return `
    <section class="task-detail-section">
      <div class="task-detail-section__head">
        <h3>${escapeHtml(section.title || "任务详情")}</h3>
        <span class="pill ${section.state === "ready" ? "pill--green" : "pill--amber"}">${section.state === "ready" ? "已就绪" : "待更新"}</span>
      </div>
      <div class="delivery-list">
        ${itemRows}
      </div>
    </section>
  `;
}
