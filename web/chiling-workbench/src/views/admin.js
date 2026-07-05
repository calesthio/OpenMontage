import { escapeHtml, formatRelativeTime } from "../format.js";
import { metric } from "../components/ui.js";
import { taskStatusLabel } from "../task-model.js";

export function render({ state, page, referenceFrame, portraitFrame }) {
  if (page === "library") {
    return renderLibrary({ referenceFrame, portraitFrame });
  }

  if (page === "data") {
    return renderData({ state });
  }

  return renderWorks({ state });
}

function renderWorks({ state }) {
  const taskRows = state.tasks.length
    ? state.tasks.map(taskWorkItem).join("")
    : `
        ${workItem("律师口播复刻", "已交付 · 演示数据", "delivery", "查看交付")}
        ${workItem("门店探访短片", "待审核 · 演示数据", "review", "去审核")}
        ${workItem("品牌种草素材", "草稿 · 演示数据", "create", "继续编辑")}
      `;

  return `
    <section class="page-head">
      <div>
        <h1 class="hero-title hero-title--compact">作品</h1>
        <p class="lede">按状态查看所有项目，继续审核、下载交付或复制分享路径。</p>
      </div>
      <button class="button button--primary" data-route="create">新建作品</button>
    </section>
    <section class="recent-card" style="margin-top: 0;">
      <div class="delivery-list">
        ${taskRows}
      </div>
    </section>
  `;
}

function renderLibrary({ referenceFrame, portraitFrame }) {
  return `
    <section class="page-head">
      <div>
        <h1 class="hero-title hero-title--compact">素材库</h1>
        <p class="lede">集中管理参考视频、肖像图片和团队已授权素材。</p>
      </div>
      <button class="button button--primary" data-route="create">上传到新作品</button>
    </section>
    <section class="quick-grid">
      <div class="create-card">
        <h2 class="section-title">已授权素材</h2>
        <div class="recent-grid">
          ${assetCard(referenceFrame, "参考视频帧", "可用于复刻结构")}
          ${assetCard(portraitFrame, "肖像素材", "团队授权图片")}
          ${assetCard(referenceFrame, "字幕样式", "口播短句规则")}
        </div>
      </div>
      <aside class="side-card">
        <span class="pill pill--green">规则</span>
        <h2 class="section-title" style="margin-top: 24px;">素材先授权，再生产。</h2>
        <p class="lede">所有参考视频、肖像图和最终文案都需要在审核页确认，避免误用素材。</p>
        <button class="button button--primary" style="margin-top: 34px;" data-route="create">创建新任务</button>
      </aside>
    </section>
  `;
}

function renderData({ state }) {
  return `
    <section class="page-head">
      <div>
        <h1 class="hero-title hero-title--compact">数据</h1>
        <p class="lede">用运营视角看产能、审核耗时和交付情况。</p>
      </div>
    </section>
    <section class="dashboard-metrics">
      ${metric("本周成片", "126", "完成率 94%")}
      ${metric("平均审核", "3.8m", "较上周 -21%")}
      ${metric("批次成功率", "98%", "稳定运行")}
    </section>
    ${renderProductionServiceConfigurationPanel(state)}
    ${renderProductionAuditLogPanel(state)}
    <section class="recent-card">
      <h2 class="section-title">流程漏斗</h2>
      <div class="stage-list" style="margin-top: 32px;">
        ${stage("导入参考", "126 个任务", "done")}
        ${stage("人工审核", "118 个通过", "done")}
        ${stage("生成交付", "116 个完成", "done")}
        ${stage("团队下载", "104 次下载", "active")}
      </div>
    </section>
  `;
}

function renderProductionAuditLogPanel(state) {
  const auditLog = state.productionAuditLog || {
    events: [],
    paidGenerationStarted: false,
    safeForUsers: true,
  };
  const events = Array.isArray(auditLog.events) ? auditLog.events.slice(-8) : [];
  const eventRows = events.length
    ? events.map(productionAuditEventItem).join("")
    : `
      <div class="delivery-item">
        <i class="status-dot status-dot--amber"></i>
        <div>
          <strong>暂无审计记录</strong>
          <span>提交生产请求、领取任务、尝试执行生产服务或人工回填交付后会出现在这里。</span>
        </div>
      </div>
    `;

  return `
    <section class="recent-card" style="margin-top: 28px;">
      <div class="page-head" style="margin-bottom: 0;">
        <div>
          <h2 class="section-title">生产执行审计</h2>
          <p class="lede">按时间追踪提交生产请求、领取任务、尝试执行生产服务、生产服务预检、人工回填交付和进入交付区。</p>
        </div>
        <button class="button button--small" data-refresh-production-audit-log>刷新审计</button>
      </div>
      <div class="delivery-list" style="margin-top: 24px;">
        ${eventRows}
      </div>
      <p class="muted" style="margin: 12px 0 0; font-size: 13px;">审计日志只显示团队可理解的操作节点，不展示底层供应商、模型、命令或密钥。</p>
    </section>
  `;
}

function productionAuditEventItem(event) {
  const dotClass = event.state === "blocked" ? "status-dot--red" : "status-dot--green";
  const timeLabel = event.at ? formatRelativeTime(event.at) : "刚刚";

  return `
    <div class="delivery-item">
      <i class="status-dot ${dotClass}"></i>
      <div>
        <strong>${escapeHtml(event.label || "生产节点")} · ${escapeHtml(event.title || "参考视频复刻")}</strong>
        <span>${escapeHtml(event.detail || "已记录")} · ${escapeHtml(event.actor || "系统")} · ${escapeHtml(timeLabel)}</span>
      </div>
    </div>
  `;
}

function renderProductionServiceConfigurationPanel(state) {
  const configuration = state.productionServiceConfiguration || {
    title: "生产服务配置",
    editable: false,
    secretInputAllowed: false,
    status: state.productionServiceStatus || {
      status: "disabled",
      statusLabel: "未启用",
      paidGenerationStarted: false,
    },
    items: [],
    adminChecklist: ["在服务端开启真实生产服务", "补全生产服务连接配置", "完成内部审批后再开启受控执行"],
    guardrails: ["不在页面填写密钥", "不向普通用户展示底层供应商或模型名称", "配置诊断不会启动付费生成"],
    paidGenerationStarted: false,
  };
  const status = configuration.status || {};
  const statusLabelMap = {
    disabled: "未启用",
    missing_configuration: "待配置",
    ready: "可连接",
  };
  const statusLabel = statusLabelMap[status.status] || status.statusLabel || "未启用";
  const items = Array.isArray(configuration.items) ? configuration.items : [];
  const checklist = Array.isArray(configuration.adminChecklist) ? configuration.adminChecklist : [];
  const guardrails = Array.isArray(configuration.guardrails) ? configuration.guardrails : [];
  const itemRows = items.length
    ? items.map(configurationItem).join("")
    : `
      <div class="delivery-item">
        <i class="status-dot status-dot--amber"></i>
        <div>
          <strong>等待同步</strong>
          <span>刷新后读取管理员配置清单，不在页面填写密钥。</span>
        </div>
      </div>
    `;

  return `
    <section class="recent-card" style="margin-top: 28px;">
      <div class="page-head" style="margin-bottom: 0;">
        <div>
          <h2 class="section-title">管理员配置</h2>
          <p class="lede">生产服务配置为只读清单；不在页面填写密钥，敏感内容仅服务端配置。</p>
        </div>
        <div class="form-actions" style="gap: 8px;">
          <span class="pill">生产服务：${escapeHtml(statusLabel)}</span>
          <button class="button button--small" data-refresh-production-service-configuration>刷新配置</button>
        </div>
      </div>
      <div class="delivery-list" style="margin-top: 24px;">
        ${itemRows}
        <div class="delivery-item">
          <i class="status-dot status-dot--green"></i>
          <div>
            <strong>安全规则</strong>
            <span>${escapeHtml(guardrails.join(" · ") || "不在页面填写密钥 · 仅服务端配置")}</span>
          </div>
          <span class="pill pill--green">仅服务端配置</span>
        </div>
        <div class="delivery-item">
          <i class="status-dot status-dot--amber"></i>
          <div>
            <strong>管理员待办</strong>
            <span>${escapeHtml(checklist.join(" / ") || "等待配置清单")}</span>
          </div>
        </div>
      </div>
    </section>
  `;
}

function configurationItem(item) {
  const dotClass =
    item.state === "ok" || item.state === "server_only"
      ? "status-dot--green"
      : item.state === "blocked"
        ? "status-dot--red"
        : "status-dot--amber";
  const stateLabelMap = {
    ok: "已就绪",
    blocked: "待处理",
    waiting: "等待中",
    locked: "审批锁定",
    server_only: "仅服务端配置",
  };

  return `
    <div class="delivery-item">
      <i class="status-dot ${dotClass}"></i>
      <div>
        <strong>${escapeHtml(item.label || "配置项")}</strong>
        <span>${escapeHtml(stateLabelMap[item.state] || "待确认")} · ${escapeHtml(item.description || "等待管理员配置")}</span>
      </div>
    </div>
  `;
}

function workItem(title, subtitle, route, action) {
  return `
    <div class="delivery-item">
      <i class="status-dot ${route === "delivery" ? "status-dot--green" : "status-dot--amber"}"></i>
      <div>
        <strong>${escapeHtml(title)}</strong>
        <span>${escapeHtml(subtitle)}</span>
      </div>
      <button class="button button--small" data-route="${escapeHtml(route)}">${escapeHtml(action)}</button>
    </div>
  `;
}

function taskWorkItem(task) {
  const route = task.status === "completed" ? "delivery" : "generating";
  const action = task.status === "completed" ? "查看交付" : "看进度";
  const dotClass = task.status === "completed" ? "status-dot--green" : "status-dot--amber";

  return `
    <div class="delivery-item">
      <i class="status-dot ${dotClass}"></i>
      <div>
        <strong>${escapeHtml(task.title)}</strong>
        <span>${escapeHtml(taskStatusLabel(task))} · ${escapeHtml(task.progress || 0)}% · ${escapeHtml(formatRelativeTime(task.createdAt))}</span>
      </div>
      <div class="form-actions" style="gap: 8px;">
        <button class="button button--small" data-open-task-detail="${escapeHtml(task.id)}">查看详情</button>
        <button class="button button--small" data-open-task="${escapeHtml(task.id)}" data-open-route="${route}">${action}</button>
      </div>
    </div>
  `;
}

function assetCard(image, title, subtitle) {
  return `
    <button class="work-row" type="button" data-toast-title="已选择素材" data-toast-message="${escapeHtml(title)} 已加入当前草稿。">
      <img src="${escapeHtml(image)}" alt="${escapeHtml(title)}" style="width: 54px; height: 54px; border-radius: 16px; object-fit: cover;" />
      <span>
        <strong>${escapeHtml(title)}</strong>
        <span>${escapeHtml(subtitle)}</span>
      </span>
    </button>
  `;
}

function stage(title, subtitle, status) {
  const safeStatus = ["done", "active", "waiting"].includes(status) ? status : "";
  const mark = safeStatus === "done" ? "✓" : safeStatus === "active" ? "•" : "";

  return `
    <div class="stage ${safeStatus ? `is-${safeStatus}` : ""}">
      <span class="stage__mark">${mark}</span>
      <div>
        <strong>${escapeHtml(title)}</strong>
        <span>${escapeHtml(subtitle)}</span>
      </div>
    </div>
  `;
}
