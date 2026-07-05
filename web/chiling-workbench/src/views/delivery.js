import { escapeHtml } from "../format.js";
import { phonePreview } from "../components/ui.js";
import { defaultDeliverables } from "../task-model.js";
import { normalizeDeliveryUrl } from "../action-safety.js";

export function render({ state }) {
  const task = state.currentTask;
  const payload = task?.payload || state.form;
  const deliverables = state.deliverables.length ? state.deliverables : defaultDeliverables(payload);

  return `
    <section class="page-head">
      <div>
        <h1 class="hero-title hero-title--compact">成品交付</h1>
        <p class="lede">成片、字幕和审核记录都在交付包中，方便团队复核与归档。</p>
      </div>
      <button class="button button--primary" data-route="create">继续新建</button>
    </section>

    <section class="delivery-card">
      ${phonePreview(state.form.referencePreview, "成片预览", "phone--large")}
      <div>
        <span class="pill pill--green">已完成</span>
        <h2 class="section-title" style="margin-top: 24px;">${escapeHtml(task?.title || "律师口播复刻")} · 交付包</h2>
        <p class="lede">当前交付包来自任务 ${escapeHtml(task?.id || "演示任务")}，下载按钮会模拟交付动作，后续可接入真实文件。</p>
        <div class="delivery-list">
          ${deliverables.map((item) => deliveryItem(item.title, item.subtitle, item.action, item.url)).join("")}
        </div>
      </div>
    </section>
  `;
}

function deliveryItem(title, subtitle, action, url = "") {
  const deliveryUrl = normalizeDeliveryUrl(url);

  return `
    <div class="delivery-item">
      <i class="status-dot status-dot--green"></i>
      <div>
        <strong>${escapeHtml(title)}</strong>
        <span>${escapeHtml(subtitle)}</span>
      </div>
      <button class="button button--small" data-delivery-action="${escapeHtml(action)}" data-delivery-url="${escapeHtml(deliveryUrl)}">${escapeHtml(action)}</button>
    </div>
  `;
}
