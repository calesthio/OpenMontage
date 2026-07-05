import { escapeHtml } from "../format.js";
import { phonePreview } from "../components/ui.js";

export function render({ state, referenceFrame }) {
  return `
    <section class="page-head">
      <div>
        <h1 class="hero-title hero-title--compact">生产台</h1>
        <p class="lede">导入参考视频，查看当前任务，把待审核内容快速推进到交付。</p>
      </div>
      <button class="button button--primary" data-route="create">新建作品</button>
    </section>

    <section class="quick-grid">
      <div>
        <div class="quick-card">
          <span class="pill pill--blue">快速导入</span>
          <h2 class="section-title" style="margin-top: 22px;">粘贴视频链接，开始准备复刻素材。</h2>
          <form class="quick-form" data-quick-import>
            <div class="input-wrap">
              <input name="referenceUrl" placeholder="粘贴抖音/短视频链接，或先输入项目说明" value="${escapeHtml(state.form.referenceUrl)}" />
            </div>
            <button class="button button--primary" type="submit">开始</button>
          </form>
        </div>

        <div class="dashboard-metrics">
          <div class="metric-card">
            <span class="metric-card__label">今日成片</span>
            <strong class="metric-card__value">24</strong>
            <span class="metric-card__helper">较昨日 +18%</span>
          </div>
          <div class="metric-card">
            <span class="metric-card__label">审核中</span>
            <strong class="metric-card__value">6</strong>
            <span class="metric-card__helper">平均 3 分钟</span>
          </div>
          <div class="metric-card">
            <span class="metric-card__label">素材库</span>
            <strong class="metric-card__value">128</strong>
            <span class="metric-card__helper">已授权素材</span>
          </div>
        </div>

        <div class="recent-card">
          <div class="page-head" style="margin-bottom: 0;">
            <div>
              <h2 class="section-title">最近作品</h2>
              <p class="lede">点击作品可以继续查看审核或交付状态。</p>
            </div>
            <button class="action-link" data-route="works">查看全部</button>
          </div>
          <div class="recent-grid">
            ${["律师口播复刻", "门店探访短片", "品牌种草素材"]
              .map(
                (title, index) => `
                  <button class="work-row" type="button" data-route="${index === 0 ? "delivery" : "review"}">
                    <i class="status-dot ${index === 0 ? "status-dot--green" : "status-dot--amber"}"></i>
                    <span>
                      <strong>${title}</strong>
                      <span>${index === 0 ? "已交付" : "待人工确认"}</span>
                    </span>
                  </button>
                `,
              )
              .join("")}
          </div>
        </div>
      </div>

      <aside class="task-card">
        <span class="pill pill--amber">当前任务</span>
        <div class="task-card__body">
          <div>
            <h2 class="section-title" style="margin-top: 22px;">律师口播素材</h2>
            <p class="lede">已完成参考解析，等待团队确认文案与字幕规则。</p>
            <div class="stage-list" style="margin-top: 34px;">
              ${stageList("review")}
            </div>
            <button class="button button--primary" style="margin-top: 34px;" data-route="review">继续审核</button>
          </div>
          ${phonePreview(referenceFrame, "参考画面", "")}
        </div>
      </aside>
    </section>
  `;
}

function stageList(active) {
  return `
    ${stage("导入素材", "参考视频和肖像已准备", "done")}
    ${stage("整理文案", "可人工修改", active === "script" ? "active" : "done")}
    ${stage("人工审核", "等待确认", active === "review" ? "active" : "")}
    ${stage("生产交付", "审核后开始", "")}
  `;
}

function stage(title, subtitle, status) {
  const mark = status === "done" ? "✓" : status === "active" ? "•" : "";
  return `
    <div class="stage ${status ? `is-${status}` : ""}">
      <span class="stage__mark">${mark}</span>
      <div>
        <strong>${title}</strong>
        <span>${subtitle}</span>
      </div>
    </div>
  `;
}
