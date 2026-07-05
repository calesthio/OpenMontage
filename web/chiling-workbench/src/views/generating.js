import { escapeHtml } from "../format.js";
import { phonePreview } from "../components/ui.js";
import { normalizeProgress } from "../action-safety.js";

export function render({ state }) {
  const task = state.currentTask;
  const payload = task?.payload || state.form;
  const taskStatus = !task ? "待创建" : task.status === "queued" ? "排队中" : "处理中";
  const taskButtonClass = task ? "button button--primary button--loading" : "button button--primary";
  const bannerTitle = task ? "已提交，生产任务正在进行" : "等待任务提交";
  const bannerSubtitle = task ? "可以离开页面，完成后会在交付区提示。" : "请从创建作品或人工审核页提交任务。";
  const visibleProgress = normalizeProgress(task ? state.progress : 0);

  return `
    <section class="generation-layout">
      <article class="generation-main">
        <div class="state-banner">
          <i class="status-dot status-dot--green"></i>
          <div>
            <strong>${bannerTitle}</strong>
            <span class="muted">${bannerSubtitle}</span>
          </div>
        </div>
        <h1 class="hero-title hero-title--compact">生成中</h1>
        <p class="lede">系统正在处理画面、字幕和交付包。当前任务 ${escapeHtml(task?.id || "待创建")}，状态会持续更新。</p>
        <div class="generation-body">
          <div>
            <div class="stage-list">
              ${generationStages(task)}
            </div>
            <div class="form-actions" style="justify-content: flex-start;">
              <button class="button" data-route="review">查看审核稿</button>
              <button class="${taskButtonClass}" disabled>${taskStatus}</button>
            </div>
          </div>
          <div class="progress-ring progress-ring--large" data-progress-ring data-progress="${escapeHtml(visibleProgress)}" style="--progress: ${escapeHtml(visibleProgress)};"></div>
        </div>
        ${renderOperationPanel(state)}
        ${renderGenerationApprovalPanel(state)}
        ${renderProductionPrepPanel(state)}
      </article>

      <aside class="generation-side">
        <span class="pill pill--amber">任务抽屉</span>
        <h2 class="section-title" style="margin-top: 24px;">当前批次</h2>
        <p class="lede">生产 ${escapeHtml(payload.count)} 条，每条最长 ${escapeHtml(payload.duration)} 秒，清晰度 ${escapeHtml(payload.resolution)}。</p>
        ${phonePreview(state.form.portraitPreview, "指定肖像", "phone--large")}
      </aside>
    </section>
  `;
}

function generationStages(task) {
  if (task?.stages?.length) {
    return task.stages
      .map((item) => stage(item.name, item.detail, item.state, item.state === "active" ? "data-generation-stage-state" : ""))
      .join("");
  }

  return `
    ${stage("解析参考", "等待", "active")}
    ${stage("整理文案", "等待", "waiting")}
    ${stage("生成画面", "等待", "waiting")}
    ${stage("合成字幕", "等待", "waiting")}
    ${stage("质检交付", "预计数分钟", "waiting")}
  `;
}

function stage(title, subtitle, status, extraAttr = "") {
  const safeStatus = ["done", "active", "waiting"].includes(status) ? status : "";
  const mark = safeStatus === "done" ? "✓" : safeStatus === "active" ? "•" : "";

  return `
    <div class="stage ${safeStatus ? `is-${safeStatus}` : ""}">
      <span class="stage__mark">${mark}</span>
      <div>
        <strong>${escapeHtml(title)}</strong>
        <span ${extraAttr}>${escapeHtml(subtitle)}</span>
      </div>
    </div>
  `;
}

function renderOperationPanel(state) {
  const panel = state.operationPanel;

  if (!panel) {
    return `
      <section class="recent-card" style="margin-top: 28px;">
        <div class="page-head" style="margin-bottom: 0;">
          <div>
            <h2 class="section-title">后台操作面板</h2>
            <p class="lede">提交任务后，这里会显示每个生产节点的可处理状态。</p>
          </div>
          <button class="button button--small" data-refresh-operations>刷新状态</button>
        </div>
      </section>
    `;
  }

  const steps = Array.isArray(panel.steps) ? panel.steps : [];

  return `
    <section class="recent-card" style="margin-top: 28px;">
      <div class="page-head" style="margin-bottom: 0;">
        <div>
          <h2 class="section-title">后台操作面板</h2>
          <p class="lede">${escapeHtml(panel.operatorHint || "正式生成前仍需人工审批。")}</p>
        </div>
        <button class="button button--small" data-refresh-operations>刷新状态</button>
      </div>
      <div class="delivery-list" style="margin-top: 24px;">
        ${steps.map(operationStepItem).join("")}
      </div>
    </section>
  `;
}

function renderGenerationApprovalPanel(state) {
  const task = state.currentTask;
  const reviewApproved = task?.review?.status === "approved";
  const generationReady = task?.generationApproval?.status === "ready_for_production";
  const disabled = reviewApproved && !generationReady ? "" : "disabled";
  const stateText = generationReady ? "已通过" : reviewApproved ? "等待确认短语" : "请先通过人工审核";

  return `
    <section class="recent-card" style="margin-top: 28px;">
      <div class="page-head" style="margin-bottom: 0;">
        <div>
          <h2 class="section-title">生成审批闸门</h2>
          <p class="lede">输入确认短语 <strong>确认进入生产</strong> 后，只进入生产准备，不会自动调用生成。</p>
        </div>
        <span class="pill ${generationReady ? "pill--green" : "pill--amber"}">${stateText}</span>
      </div>
      <div class="quick-form" style="margin-top: 24px;">
        <div class="input-wrap">
          <input data-generation-phrase placeholder="请输入：确认进入生产" value="${escapeHtml(state.generationPhrase)}" ${generationReady ? "disabled" : ""} />
        </div>
        <button class="button button--primary" data-approve-generation ${disabled}>确认审批</button>
      </div>
    </section>
  `;
}

function renderProductionPrepPanel(state) {
  const prep = state.productionPrep;
  const ready = prep?.status === "ready";
  const requested = prep?.productionRequest?.status === "production_requested" || state.currentTask?.productionRequest?.status === "production_requested";
  const title = ready ? "生产准备包已就绪" : "等待审批完成";
  const hint = ready
    ? prep.operatorHint || "准备包已生成，可进入生产端继续执行。"
    : prep?.message || "人工审核和生成审批都通过后，这里会显示生产准备包。";
  const constraints = prep?.constraints || {};
  const assets = prep?.assets || {};
  const review = prep?.review || {};
  const scriptPreview = Array.isArray(review.scriptLines) && review.scriptLines.length ? review.scriptLines.slice(0, 3).join(" / ") : "等待审核文案";
  const requestDisabled = ready && !requested ? "" : "disabled";

  return `
    <section class="recent-card" style="margin-top: 28px;">
      <div class="page-head" style="margin-bottom: 0;">
        <div>
          <h2 class="section-title">生产准备包</h2>
          <p class="lede">${escapeHtml(hint)}</p>
        </div>
        <button class="button button--small" data-refresh-production-prep>刷新准备包</button>
      </div>
      <div class="delivery-list" style="margin-top: 24px;">
        <div class="delivery-item">
          <i class="status-dot ${ready ? "status-dot--green" : "status-dot--amber"}"></i>
          <div>
            <strong>${requested ? "生产请求已提交" : title}</strong>
            <span>${requested ? "等待受控生产流程执行，不会在页面直接调用生成。" : ready ? "已完成审核与确认，可交给生产流程。" : "还需先完成人工审核和确认短语。"}</span>
          </div>
          <span class="pill ${ready ? "pill--green" : "pill--amber"}">${requested ? "已提交" : ready ? "可生产" : "未就绪"}</span>
        </div>
        <div class="delivery-item">
          <i class="status-dot status-dot--green"></i>
          <div>
            <strong>生产参数</strong>
            <span>单批 ${escapeHtml(constraints.batchCount || "-")} / ${escapeHtml(constraints.maxBatchCount || 5)} 条 · 单条 ${escapeHtml(constraints.durationSeconds || "-")} / ${escapeHtml(constraints.maxDurationSeconds || 15)} 秒 · ${escapeHtml(constraints.resolution || "-")}</span>
          </div>
        </div>
        <div class="delivery-item">
          <i class="status-dot status-dot--green"></i>
          <div>
            <strong>素材与文案</strong>
            <span>${escapeHtml(assets.referenceName || "参考素材待确认")} · ${escapeHtml(assets.portraitName || "肖像素材待确认")} · ${escapeHtml(scriptPreview)}</span>
          </div>
        </div>
      </div>
      <div class="quick-form" style="margin-top: 24px;">
        <div class="input-wrap">
          <input data-production-request-phrase placeholder="请输入：确认提交生产" value="${escapeHtml(state.productionRequestPhrase)}" ${requested ? "disabled" : ""} />
        </div>
        <button class="button button--primary" data-submit-production-request ${requestDisabled}>提交生产请求</button>
      </div>
      <p class="muted" style="margin: 12px 0 0; font-size: 13px;">提交后只进入受控队列，不会直接生成或扣费。</p>
    </section>
  `;
}

function operationStepItem(step) {
  const dotClass = step.state === "done" ? "status-dot--green" : step.state === "ready" ? "status-dot--amber" : "status-dot--red";
  const approval = step.approvalRequired ? " · 需人工确认" : "";
  const disabled = step.canExecute ? "" : "disabled";

  return `
    <div class="delivery-item">
      <i class="status-dot ${dotClass}"></i>
      <div>
        <strong>${escapeHtml(step.title)}</strong>
        <span>${escapeHtml(step.stateLabel)} · ${escapeHtml(step.actionLabel)}${approval} · ${escapeHtml(step.description)}</span>
      </div>
      <button class="button button--small" data-run-operation="${escapeHtml(step.id)}" ${disabled}>${escapeHtml(step.actionLabel)}</button>
    </div>
  `;
}
