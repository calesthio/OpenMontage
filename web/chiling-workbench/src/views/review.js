import { escapeHtml } from "../format.js";
import { phonePreview } from "../components/ui.js";
import { normalizeTaskRoute } from "../action-safety.js";

export function render({ state }) {
  return `
    <section class="page-head">
      <div>
        <h1 class="hero-title hero-title--compact">人工审核</h1>
        <p class="lede">确认文案、字幕规则与授权状态，审核通过后才会进入生产。</p>
      </div>
      <button class="button" data-route="create">退回修改</button>
    </section>

    <section class="recent-card" style="margin-top: 28px;">
      <div class="page-head" style="margin-bottom: 0;">
        <div>
          <h2 class="section-title">后台生产队列</h2>
          <p class="lede">这里显示已提交任务的后台状态、下一步动作和是否等待人工确认。</p>
        </div>
        <button class="button button--small" data-refresh-queue>刷新队列</button>
      </div>
      <div class="delivery-list" style="margin-top: 24px;">
        ${renderQueueRows(state)}
      </div>
    </section>

    ${renderProductionServiceStatusPanel(state)}

    <section class="recent-card" style="margin-top: 28px;">
      <div class="page-head" style="margin-bottom: 0;">
        <div>
          <h2 class="section-title">生产执行队列</h2>
          <p class="lede">这里只显示已完成二次确认、等待操作员执行的生产请求。</p>
        </div>
        <button class="button button--small" data-refresh-production-requests>刷新执行队列</button>
      </div>
      <div class="delivery-list" style="margin-top: 24px;">
        ${renderProductionRequestRows(state)}
      </div>
    </section>

    <section class="review-grid">
      <aside class="review-card">
        <span class="pill pill--blue">参考预览</span>
        ${phonePreview(state.form.referencePreview, "参考视频", "phone--large")}
        <div class="chip-row">
          <span class="pill">${escapeHtml(state.form.duration)}s</span>
          <span class="pill">${escapeHtml(state.form.resolution)}</span>
        </div>
      </aside>

      <article class="review-card">
        ${renderReviewDraftPanel(state)}
        <h2 class="section-title">文案与字幕</h2>
        <p class="lede">短句结尾不显示逗号、句号等标点。这里修改后会带入生产。</p>
        <textarea class="review-script" data-field="script">${escapeHtml(state.form.script)}</textarea>
        <div class="chip-row">
          <span class="pill pill--blue">短句显示</span>
          <span class="pill pill--green">句尾无标点</span>
        </div>
        <div class="form-actions">
          <button class="button" data-clean-subtitles>清理句尾标点</button>
          <button class="button" data-save-review>保存审核稿</button>
          <button class="button button--primary" data-approve-review>审核通过</button>
          <button class="button button--primary" data-start-generation>确认并生成</button>
        </div>
      </article>

      <aside class="review-card">
        <h2 class="section-title">审核详情侧栏</h2>
        <p class="lede">从列表滑出，不打断主页面。</p>
        <div class="check-list">
          ${checkRow("素材授权", "已确认", "ok")}
          ${checkRow("肖像授权", "已确认", "ok")}
          ${checkRow("字幕规则", "已确认", "ok")}
          ${checkRow("画面方向", "需确认", "warning")}
        </div>
        <div class="review-note">
          <strong>当前生产设置</strong>
          <span class="muted">单批 ${escapeHtml(state.form.count)} 条，单条 ${escapeHtml(state.form.duration)} 秒，清晰度 ${escapeHtml(state.form.resolution)}。</span>
        </div>
      </aside>
    </section>
  `;
}

function renderQueueRows(state) {
  const entries = Array.isArray(state.queueEntries) ? state.queueEntries : [];

  if (!entries.length) {
    return `
      <div class="delivery-item">
        <i class="status-dot status-dot--amber"></i>
        <div>
          <strong>暂无后台任务</strong>
          <span>从人工审核页点击确认生成后，会在这里看到生产队列。</span>
        </div>
        <button class="button button--small" data-route="create">新建作品</button>
      </div>
    `;
  }

  return entries.map(queueItem).join("");
}

function renderProductionServiceStatusPanel(state) {
  const status = state.productionServiceStatus || {
    status: "disabled",
    statusLabel: "未启用",
    ready: false,
    summary: "真实生产服务未启用，当前不会启动付费生成。",
    nextAction: "需要管理员开启生产服务后再执行。",
    executionAllowed: false,
    paidGenerationStarted: false,
    checks: [],
  };
  const statusLabelMap = {
    disabled: "未启用",
    missing_configuration: "待配置",
    ready: "可连接",
  };
  const statusLabel = statusLabelMap[status.status] || status.statusLabel || "未启用";
  const pillClass = status.status === "ready" ? "pill--green" : status.status === "missing_configuration" ? "pill--amber" : "";
  const checks = Array.isArray(status.checks) ? status.checks : [];
  const checkRows = checks.length
    ? checks
        .map((check) => {
          const dotClass = check.state === "ok" ? "status-dot--green" : check.state === "blocked" ? "status-dot--red" : "status-dot--amber";
          return `
            <div class="delivery-item">
              <i class="status-dot ${dotClass}"></i>
              <div>
                <strong>${escapeHtml(check.label || "检测项")}</strong>
                <span>${escapeHtml(check.message || "等待检测")}</span>
              </div>
            </div>
          `;
        })
        .join("")
    : `
      <div class="delivery-item">
        <i class="status-dot status-dot--amber"></i>
        <div>
          <strong>等待诊断</strong>
          <span>点击刷新后检查真实生产服务状态，不会启动付费生成。</span>
        </div>
      </div>
    `;

  return `
    <section class="recent-card" style="margin-top: 28px;">
      <div class="page-head" style="margin-bottom: 0;">
        <div>
          <h2 class="section-title">生产服务诊断</h2>
          <p class="lede">${escapeHtml(status.summary || "真实生产服务状态待检查，不会启动付费生成。")}</p>
        </div>
        <div class="form-actions" style="gap: 8px;">
          <span class="pill ${pillClass}">真实生产服务：${escapeHtml(statusLabel)}</span>
          <button class="button button--small" data-refresh-production-service-status>刷新诊断</button>
        </div>
      </div>
      <div class="delivery-list" style="margin-top: 24px;">
        <div class="delivery-item">
          <i class="status-dot ${status.ready ? "status-dot--green" : "status-dot--amber"}"></i>
          <div>
            <strong>${escapeHtml(status.executionAllowed ? "可进入受控执行" : "仅诊断，不执行")}</strong>
            <span>下一步：${escapeHtml(status.nextAction || "等待管理员处理")} · ${status.paidGenerationStarted ? "已启动" : "不会启动付费生成"}</span>
          </div>
        </div>
        ${checkRows}
      </div>
    </section>
  `;
}

function renderProductionRequestRows(state) {
  const requests = Array.isArray(state.productionRequests) ? state.productionRequests : [];

  if (!requests.length) {
    return `
      <div class="delivery-item">
        <i class="status-dot status-dot--amber"></i>
        <div>
          <strong>暂无待执行请求</strong>
          <span>提交生产请求后，操作员会在这里看到待处理项目。</span>
        </div>
        <button class="button button--small" data-route="generating">查看当前任务</button>
      </div>
    `;
  }

  return requests.map(productionRequestItem).join("");
}

function productionRequestItem(item) {
  const dotClass = item.executionStarted ? "status-dot--green" : "status-dot--amber";
  const taskId = escapeHtml(item.taskId || "");
  const actionButton = item.executionStarted
    ? `
      <div class="form-actions" style="gap: 8px;">
        <button class="button button--small" data-open-task-detail="${taskId}">查看详情</button>
        <button class="button button--small" data-execute-production-adapter="${taskId}">执行生产服务</button>
        <button class="button button--small button--primary" data-complete-production-request="${taskId}">标记交付</button>
      </div>
    `
    : `
      <div class="form-actions" style="gap: 8px;">
        <button class="button button--small" data-open-task-detail="${taskId}">查看详情</button>
        <button class="button button--small button--primary" data-claim-production-request="${taskId}">领取任务</button>
      </div>
    `;

  return `
    <div class="delivery-item">
      <i class="status-dot ${dotClass}"></i>
      <div>
        <strong>${escapeHtml(item.title || "参考视频复刻")}</strong>
        <span>${escapeHtml(item.statusLabel || (item.executionStarted ? "执行中" : "等待生产"))} · 下一步：${escapeHtml(item.nextAction || "操作员执行")} · ${escapeHtml(item.batchCount || "-")}条 · ${escapeHtml(item.durationSeconds || "-")}s · ${escapeHtml(item.resolution || "-")}</span>
      </div>
      ${actionButton}
    </div>
  `;
}

function queueItem(item) {
  const dotClass = item.status === "completed" ? "status-dot--green" : item.queueItemReady ? "status-dot--amber" : "status-dot--red";
  const route = normalizeTaskRoute(item.route, item.status);
  const action = item.status === "completed" ? "查看交付" : "看进度";
  const note = item.blockingNote ? ` · ${escapeHtml(item.blockingNote)}` : "";

  return `
    <div class="delivery-item">
      <i class="status-dot ${dotClass}"></i>
      <div>
        <strong>${escapeHtml(item.title || "参考视频复刻")}</strong>
        <span>${escapeHtml(item.statusLabel || "待处理")} · ${escapeHtml(item.sourceState || "等待提交")} · 下一步：${escapeHtml(item.nextAction || "等待后台处理")}${note}</span>
      </div>
      <div class="form-actions" style="gap: 8px;">
        <button class="button button--small" data-open-task-detail="${escapeHtml(item.taskId || "")}">查看详情</button>
        <button class="button button--small" data-open-task="${escapeHtml(item.taskId || "")}" data-open-route="${escapeHtml(route)}">${escapeHtml(action)}</button>
      </div>
    </div>
  `;
}

function renderReviewDraftPanel(state) {
  const draft = state.reviewDraft;
  const hint = draft?.operatorHint || "点击同步后，可把后台解析摘要和文案草稿带入人工审核。";
  const rule = draft?.subtitleRule || "短句句尾不显示标点。";

  return `
    <section class="section-block" style="padding-top: 0; border-top: 0;">
      <div class="page-head" style="margin-bottom: 14px;">
        <div>
          <h2 class="section-title">解析摘要</h2>
          <p class="lede">${escapeHtml(hint)}</p>
        </div>
        <button class="button button--small" data-refresh-review-draft>同步解析结果</button>
      </div>
      <textarea class="review-script" data-field="analysisSummary" style="min-height: 112px;">${escapeHtml(state.form.analysisSummary)}</textarea>
      <div class="chip-row">
        <span class="pill pill--blue">可人工修改</span>
        <span class="pill pill--green">${escapeHtml(rule)}</span>
      </div>
    </section>
  `;
}

function checkRow(title, stateText, status) {
  const warning = status === "warning";

  return `
    <div class="check-row">
      <span class="check-row__icon ${warning ? "is-warning" : ""}">${warning ? "!" : "✓"}</span>
      <strong>${escapeHtml(title)}</strong>
      <span class="check-row__state ${warning ? "is-warning" : ""}">${escapeHtml(stateText)}</span>
    </div>
  `;
}
