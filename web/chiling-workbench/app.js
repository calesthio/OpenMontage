import {
  clampNumber,
  escapeHtml,
  lineBreaks,
  normalizeSubtitleText,
  formatRelativeTime,
} from "./src/format.js";
import {
  defaultDeliverables,
  taskStatusLabel,
} from "./src/task-model.js";
import { createInitialState } from "./src/state.js";
import { phonePreview } from "./src/components/ui.js";
import { renderTopbar } from "./src/components/topbar.js";
import { bindDelegatedClick, find, findAll } from "./src/dom.js";

const appRoot = document.querySelector("#app");
const toastRoot = document.querySelector("#toast-root");

const referenceFrame = "./assets/reference-frame.png";
const portraitFrame = "./assets/portrait.png";

const pages = [
  { id: "dashboard", label: "生产台" },
  { id: "works", label: "作品" },
  { id: "library", label: "素材库" },
  { id: "review", label: "团队审核" },
  { id: "data", label: "数据" },
];

const routeIds = new Set(["login", "dashboard", "create", "review", "generating", "delivery", "works", "library", "data"]);

const state = createInitialState({
  storage: window.localStorage,
  referenceFrame,
  portraitFrame,
});

function showToast(title, message) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.innerHTML = `<strong>${escapeHtml(title)}</strong><span>${escapeHtml(message)}</span>`;
  toastRoot.appendChild(toast);

  window.setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(-8px)";
  }, 2600);

  window.setTimeout(() => {
    toast.remove();
  }, 3100);
}

function navigate(page) {
  state.page = page;
  if (window.location.hash !== `#${page}`) {
    window.history.replaceState(null, "", `#${page}`);
  }
  render();
  if (page === "review") {
    Promise.all([refreshQueue(), refreshProductionRequests(), refreshProductionServiceStatus(), refreshReviewDraft()])
      .then(render)
      .catch(() => {});
  }
  if (page === "data") {
    Promise.all([refreshProductionServiceConfiguration(), refreshProductionAuditLog()])
      .then(render)
      .catch(() => {});
  }
}

function login() {
  state.loggedIn = true;
  state.page = "dashboard";
  window.history.replaceState(null, "", "#dashboard");
  render();
  showToast("已进入工作台", "可以开始导入参考视频并准备审核。");
}

function buildTaskPayload() {
  return {
    referenceUrl: state.form.referenceUrl,
    duration: state.form.duration,
    resolution: state.form.resolution,
    count: state.form.count,
    subtitleStyle: state.form.subtitleStyle,
    script: normalizeSubtitleText(state.form.script),
    analysisSummary: state.form.analysisSummary,
    referenceName: state.form.referenceName,
    portraitName: state.form.portraitName,
  };
}

async function startGeneration() {
  if (state.isSubmitting) return;

  state.isSubmitting = true;
  render();

  try {
    state.form.script = normalizeSubtitleText(state.form.script);
    const task = await window.ChilingTaskApi.createTask(buildTaskPayload());
    state.currentTask = task;
    state.currentTaskId = task.id;
    state.progress = task.progress || 0;
    window.localStorage.setItem("chiling-workbench.current-task-id", task.id);
    state.tasks = await window.ChilingTaskApi.listTasks();
    state.queueEntries = await window.ChilingTaskApi.listQueue();
    state.productionRequests = await window.ChilingTaskApi.listProductionRequests();
    state.productionServiceStatus = await window.ChilingTaskApi.listProductionServiceStatus();
    state.operationPanel = await window.ChilingTaskApi.listOperations(task.id);
    state.productionPrep = null;
    await refreshReviewDraft(task.id);
    state.isSubmitting = false;
    state.page = "generating";
    window.history.replaceState(null, "", "#generating");
    render();
    showToast("任务已提交", "生产任务已进入队列，完成后会进入交付区。");
    startTaskPolling({ navigateOnComplete: true });
  } catch (error) {
    state.isSubmitting = false;
    render();
    showToast("提交失败", error.message || "任务创建失败，请稍后重试。");
  }
}

function stopTaskPolling() {
  if (!state.taskPoller) return;
  window.clearInterval(state.taskPoller);
  state.taskPoller = null;
}

function startTaskPolling({ navigateOnComplete = false } = {}) {
  stopTaskPolling();
  refreshCurrentTask({ navigateOnComplete });
  state.taskPoller = window.setInterval(() => {
    refreshCurrentTask({ navigateOnComplete: navigateOnComplete && state.page === "generating" });
  }, 1000);
}

async function refreshCurrentTask({ navigateOnComplete = false } = {}) {
  if (!state.currentTaskId) return null;

  const task = await window.ChilingTaskApi.getTask(state.currentTaskId);
  if (!task) return null;

  const wasCompleted = state.currentTask?.status === "completed";
  state.currentTask = task;
  state.progress = task.progress || 0;
  await refreshOperations(task.id);
  await refreshProductionPrep(task.id);

  if (task.status === "completed") {
    stopTaskPolling();
    state.deliverables = await window.ChilingTaskApi.listDeliverables(task.id);
    state.tasks = await window.ChilingTaskApi.listTasks();

    if (!wasCompleted && navigateOnComplete) {
      navigate("delivery");
      showToast("成品已生成", "交付包已准备好，可下载或复制链接。");
      return task;
    }
  }

  if (state.page === "generating") {
    render();
  } else {
    updateProgressOnly();
  }

  return task;
}

async function refreshTasks() {
  state.tasks = await window.ChilingTaskApi.listTasks();
}

async function refreshQueue() {
  state.queueEntries = await window.ChilingTaskApi.listQueue();
}

async function refreshProductionRequests() {
  state.productionRequests = await window.ChilingTaskApi.listProductionRequests();
}

async function refreshProductionServiceStatus() {
  state.productionServiceStatus = await window.ChilingTaskApi.listProductionServiceStatus();
  return state.productionServiceStatus;
}

async function refreshProductionServiceConfiguration() {
  state.productionServiceConfiguration = await window.ChilingTaskApi.listProductionServiceConfiguration();
  if (state.productionServiceConfiguration?.status) {
    state.productionServiceStatus = state.productionServiceConfiguration.status;
  }
  return state.productionServiceConfiguration;
}

async function refreshProductionAuditLog() {
  state.productionAuditLog = await window.ChilingTaskApi.listProductionAuditLog();
  return state.productionAuditLog;
}

async function openTaskDetail(taskId) {
  if (!taskId) {
    showToast("暂无详情", "请先选择一个任务。");
    return null;
  }

  state.currentTaskId = taskId;
  window.localStorage.setItem("chiling-workbench.current-task-id", taskId);
  state.detailDrawerOpen = true;
  state.taskDetail = {
    taskId,
    title: "任务详情",
    statusLabel: "加载中",
    progress: 0,
    paidGenerationStarted: false,
    sections: [],
  };
  render();

  try {
    state.taskDetail = await window.ChilingTaskApi.listTaskDetail(taskId);
    render();
    return state.taskDetail;
  } catch (error) {
    state.taskDetail = {
      taskId,
      title: "任务详情",
      statusLabel: "读取失败",
      progress: 0,
      paidGenerationStarted: false,
      sections: [
        {
          title: "生产准备包",
          state: "blocked",
          items: [{ label: "详情读取", value: error.message || "请稍后重试。", state: "blocked" }],
        },
      ],
    };
    render();
    showToast("详情读取失败", error.message || "请稍后重试。");
    return null;
  }
}

function closeTaskDetail() {
  state.detailDrawerOpen = false;
  render();
}

async function claimProductionRequest(taskId) {
  if (!taskId) {
    showToast("没有可领取任务", "请先提交生产请求。");
    return null;
  }

  try {
    const result = await window.ChilingTaskApi.claimProductionRequest(taskId, "操作员");
    if (result.status !== "blocked") {
      state.currentTaskId = taskId;
      window.localStorage.setItem("chiling-workbench.current-task-id", taskId);
      state.currentTask = await window.ChilingTaskApi.getTask(taskId);
    }
    if (result.panel) {
      state.operationPanel = result.panel;
    }
    await refreshProductionServiceStatus();
    await refreshProductionRequests();
    await refreshQueue();
    render();
    showToast(result.status === "blocked" ? "领取失败" : "任务已领取", result.message || "执行队列状态已更新。");
    return result;
  } catch (error) {
    showToast("领取失败", error.message || "请稍后重试。");
    return null;
  }
}

async function completeProductionRequest(taskId) {
  if (!taskId) {
    showToast("没有可回填任务", "请先领取生产任务。");
    return null;
  }

  try {
    const result = await window.ChilingTaskApi.completeProductionRequest(taskId, {
      videoName: "成品视频.mp4",
      subtitleName: "字幕文件.srt",
      auditNote: "人工回填完成",
    });
    if (result.status !== "blocked") {
      state.currentTaskId = taskId;
      window.localStorage.setItem("chiling-workbench.current-task-id", taskId);
      state.currentTask = await window.ChilingTaskApi.getTask(taskId);
      state.deliverables = await window.ChilingTaskApi.listDeliverables(taskId);
    }
    await refreshProductionRequests();
    await refreshQueue();
    render();
    showToast(result.status === "blocked" ? "回填失败" : "交付已回填", result.message || "交付状态已更新。");
    if (result.status === "completed") {
      navigate("delivery");
    }
    return result;
  } catch (error) {
    showToast("回填失败", error.message || "请稍后重试。");
    return null;
  }
}

async function executeProductionAdapter(taskId) {
  if (!taskId) {
    showToast("没有可执行任务", "请先领取生产任务。");
    return null;
  }

  try {
    const result = await window.ChilingTaskApi.executeProductionAdapter(taskId, {
      operatorName: "操作员",
    });
    if (result.panel) {
      state.operationPanel = result.panel;
    }
    await refreshProductionRequests();
    await refreshQueue();
    render();
    const toastTitle =
      result.status === "disabled"
        ? "生产服务未启用"
        : result.status === "preflight_ready"
          ? "生产服务预检已通过"
          : "执行状态已更新";
    showToast(toastTitle, result.message || "等待服务端执行器接管。");
    return result;
  } catch (error) {
    showToast("执行失败", error.message || "请稍后重试。");
    return null;
  }
}

async function refreshOperations(taskId = state.currentTaskId) {
  if (!taskId) {
    state.operationPanel = null;
    return null;
  }

  try {
    state.operationPanel = await window.ChilingTaskApi.listOperations(taskId);
  } catch {
    return state.operationPanel;
  }

  return state.operationPanel;
}

async function refreshReviewDraft(taskId = state.currentTaskId) {
  if (!taskId) {
    return null;
  }

  const draft = await window.ChilingTaskApi.listReviewDraft(taskId);
  if (!draft) {
    return null;
  }

  state.reviewDraft = draft;
  state.form.analysisSummary = draft.analysisSummary || state.form.analysisSummary;
  state.form.script = draft.scriptDraft || state.form.script;
  return draft;
}

async function refreshProductionPrep(taskId = state.currentTaskId) {
  if (!taskId) {
    state.productionPrep = null;
    return null;
  }

  try {
    state.productionPrep = await window.ChilingTaskApi.listProductionPrep(taskId);
  } catch {
    return state.productionPrep;
  }

  return state.productionPrep;
}

async function saveReviewDecision(approved = false) {
  saveFormValues();

  if (!state.currentTaskId) {
    showToast("请先提交任务", "当前还没有后台任务，确认生成后会进入审核流。");
    return null;
  }

  try {
    const result = await window.ChilingTaskApi.saveReview(state.currentTaskId, {
      analysisSummary: state.form.analysisSummary,
      script: state.form.script,
      approved,
    });
    if (result.panel) {
      state.operationPanel = result.panel;
    }
    state.currentTask = await window.ChilingTaskApi.getTask(state.currentTaskId);
    await refreshQueue();
    await refreshProductionRequests();
    await refreshReviewDraft();
    await refreshProductionPrep();
    render();
    showToast(approved ? "审核已通过" : "审核稿已保存", result.message || "人工审核状态已更新。");
    return result;
  } catch (error) {
    showToast("保存失败", error.message || "请稍后重试。");
    return null;
  }
}

async function approveGenerationGate() {
  if (!state.currentTaskId) {
    showToast("请先提交任务", "当前还没有可审批的生产任务。");
    return null;
  }

  try {
    const result = await window.ChilingTaskApi.approveGeneration(state.currentTaskId, state.generationPhrase);
    if (result.panel) {
      state.operationPanel = result.panel;
    }
    state.currentTask = await window.ChilingTaskApi.getTask(state.currentTaskId);
    await refreshQueue();
    await refreshProductionRequests();
    await refreshProductionPrep();
    render();
    showToast(result.status === "blocked" ? "审批未通过" : "生成审批已通过", result.message || "生成审批状态已更新。");
    return result;
  } catch (error) {
    showToast("审批失败", error.message || "请稍后重试。");
    return null;
  }
}

async function submitProductionRequest() {
  if (!state.currentTaskId) {
    showToast("请先提交任务", "当前还没有可提交生产的任务。");
    return null;
  }

  try {
    const result = await window.ChilingTaskApi.requestProduction(state.currentTaskId, state.productionRequestPhrase);
    if (result.panel) {
      state.operationPanel = result.panel;
    }
    if (result.productionPrep) {
      state.productionPrep = result.productionPrep;
    }
    state.currentTask = await window.ChilingTaskApi.getTask(state.currentTaskId);
    await refreshQueue();
    await refreshProductionRequests();
    await refreshProductionPrep();
    render();
    showToast(result.status === "blocked" ? "提交未通过" : "生产请求已提交", result.message || "生产请求状态已更新。");
    return result;
  } catch (error) {
    showToast("提交失败", error.message || "请稍后重试。");
    return null;
  }
}

async function runOperationAction(operationId) {
  if (!state.currentTaskId) {
    showToast("没有可执行任务", "请先提交一个生产任务。");
    return;
  }

  try {
    const result = await window.ChilingTaskApi.runOperation(state.currentTaskId, operationId);
    if (result.panel) {
      state.operationPanel = result.panel;
    }
    if (typeof result.progress === "number") {
      state.progress = result.progress;
    }
    await refreshCurrentTask();
    await refreshQueue();
    if (operationId === "reference_analysis" || operationId === "copy_extract") {
      await refreshReviewDraft();
    }
    render();
    showToast(result.status === "blocked" ? "节点未执行" : "节点已完成", result.message || "后台操作状态已更新。");
  } catch (error) {
    showToast("执行失败", error.message || "请稍后重试。");
  }
}

function updateProgressOnly() {
  const ring = document.querySelector("[data-progress-ring]");
  if (ring) {
    ring.style.setProperty("--progress", state.progress);
    ring.dataset.progress = String(state.progress);
  }

  const stageState = document.querySelector("[data-generation-stage-state]");
  if (stageState) {
    stageState.textContent = `${state.progress}%`;
  }
}

function shell(content, activePage = state.page) {
  return `
    ${renderTopbar({ pages, activePage })}
    <main class="page">${content}</main>
  `;
}

function renderLogin() {
  return `
    <main class="page page--login">
      <header class="login-header">
        <div class="login-brand">
          <strong>赤灵AI运营工作台</strong>
          <span>企业内容生产入口</span>
        </div>
        <button class="button button--small" type="button" data-login>进入演示</button>
      </header>

      <section class="login-grid">
        <div class="panel panel--login panel--solid">
          <span class="pill">团队授权访问</span>
          <h1 class="hero-title" style="margin-top: 28px;">把参考视频变成可审核、可交付的运营素材。</h1>
          <p class="lede">粘贴视频链接，上传指定肖像，先由人工确认文案、字幕和素材授权，再进入批量生产。</p>

          <form class="form" data-login-form>
            <div class="field">
              <label for="account">账号</label>
              <div class="input-wrap">
                <input id="account" name="account" autocomplete="username" value="team@chiling.ai" />
              </div>
            </div>
            <div class="field">
              <label for="password">密码</label>
              <div class="input-wrap">
                <input id="password" name="password" type="password" autocomplete="current-password" value="chiling-demo" />
                <button class="text-link field-action" type="button" data-toast-title="验证码已发送" data-toast-message="演示环境已模拟发送。">验证码登录</button>
              </div>
            </div>
            <div class="form-row">
              <label class="check">
                <input type="checkbox" checked />
                <span>记住本设备</span>
              </label>
              <button class="text-link" type="button" data-toast-title="已切换入口" data-toast-message="企业验证码登录已准备。">企业验证码</button>
            </div>
            <button class="button button--primary button--wide" type="submit">登录工作台</button>
            <p class="fine-print">仅展示用户需要操作的流程信息，内部技术与接口不在前台暴露。</p>
          </form>
        </div>

        <aside class="panel panel--overview">
          <span class="pill pill--red">今日待处理 8</span>
          <h2 class="section-title section-title--large" style="margin-top: 30px;">从导入到交付，一条线完成。</h2>
          <p class="lede">团队成员可以在这里查看生产状态、审核文案、管理素材与下载交付包。</p>

          <div class="summary-card">
            <span class="pill pill--green">安全状态正常</span>
            <div class="metric-row">
              <div class="metric-card">
                <span class="metric-card__label">今日生成</span>
                <strong class="metric-card__value">24</strong>
                <i class="status-dot status-dot--green"></i>
              </div>
              <div class="metric-card">
                <span class="metric-card__label">待审核</span>
                <strong class="metric-card__value">6</strong>
                <i class="status-dot status-dot--amber"></i>
              </div>
            </div>
            <div class="status-row">
              <i class="status-dot status-dot--green"></i>
              <div>
                <strong>素材与肖像授权已纳入审核</strong>
                <span>每次生产前都需要人工确认。</span>
              </div>
            </div>
          </div>

          <div class="safe-note">
            <strong>面向运营人员设计</strong>
            <span>页面只说“要做什么、怎么做”，不展示任何底层模型或供应商信息。</span>
          </div>
        </aside>
      </section>
    </main>
  `;
}

function renderDashboard() {
  return shell(
    `
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
    `,
    "dashboard",
  );
}

function renderCreate() {
  return shell(
    `
      <section class="page-head">
        <div>
          <h1 class="hero-title hero-title--compact">创建作品</h1>
          <p class="lede">上传参考视频和指定肖像，设置生产参数，再交给团队人工确认。</p>
        </div>
        <button class="button" data-route="dashboard">返回生产台</button>
      </section>

      <section class="create-layout">
        <div class="create-card">
          <div class="steps">
            <span class="step-pill is-active">1 导入素材</span>
            <span class="step-pill">2 人工审核</span>
            <span class="step-pill">3 生成交付</span>
          </div>

          <section class="section-block">
            <h2 class="section-title">参考内容</h2>
            <p class="lede">支持粘贴视频链接，也可以先选择本地视频文件。文案、图片和提示说明都可以人工修改。</p>
            <div class="quick-form">
              <div class="input-wrap">
                <input data-field="referenceUrl" placeholder="粘贴参考视频链接" value="${escapeHtml(state.form.referenceUrl)}" />
              </div>
              <button class="button" data-save-form>保存</button>
            </div>
            <div class="upload-grid">
              ${uploadCard("reference", "参考视频", state.form.referenceName, "用于分析结构、节奏、文案和镜头风格。", "is-red", "选择视频")}
              ${uploadCard("portrait", "指定肖像", state.form.portraitName, "用于后续替换为团队授权的脸部肖像。", "is-amber", "选择图片")}
            </div>
          </section>

          <section class="section-block">
            <h2 class="section-title">生产参数</h2>
            <div class="settings-grid">
              <label class="setting">
                <span>单条时长</span>
                <input data-field="duration" type="number" min="1" max="15" value="${state.form.duration}" />
                <small>最长 15 秒，15 秒内可自定义。</small>
              </label>
              <label class="setting">
                <span>生成条数</span>
                <input data-field="count" type="number" min="1" max="5" value="${state.form.count}" />
                <small>单批最多 5 条，默认 1 条。</small>
              </label>
              <label class="setting">
                <span>清晰度</span>
                <select data-field="resolution">
                  <option value="480p" ${state.form.resolution === "480p" ? "selected" : ""}>标准 480p</option>
                  <option value="720p" ${state.form.resolution === "720p" ? "selected" : ""}>高清 720p</option>
                </select>
                <small>默认标准清晰度，便于快速批量。</small>
              </label>
              <label class="setting">
                <span>字幕呈现</span>
                <select data-field="subtitleStyle">
                  <option value="short" ${state.form.subtitleStyle === "short" ? "selected" : ""}>口播短句</option>
                  <option value="compact" ${state.form.subtitleStyle === "compact" ? "selected" : ""}>紧凑双行</option>
                </select>
                <small>句尾标点会自动清理。</small>
              </label>
            </div>
          </section>

          <section class="section-block">
            <h2 class="section-title">文案与提示说明</h2>
            <textarea class="review-script" data-field="script" style="min-height: 138px;">${escapeHtml(state.form.script)}</textarea>
            <div class="chip-row">
              <span class="pill pill--blue">可人工修改</span>
              <span class="pill pill--green">图片可替换</span>
              <span class="pill pill--amber">先审后产出</span>
            </div>
          </section>

          <div class="form-actions">
            <button class="button" data-route="dashboard">保存草稿</button>
            <button class="button button--primary" data-to-review>下一步：人工审核</button>
          </div>
        </div>

        <aside class="side-card">
          <span class="pill">实时预览</span>
          <h2 class="section-title" style="margin-top: 24px;">素材会在这里预览。</h2>
          <p class="lede">当前默认展示参考画面，上传图片后会同步更新肖像状态。</p>
          ${phonePreview(state.form.referencePreview, "参考画面", "phone--large")}
          <div class="status-row">
            <i class="status-dot status-dot--green"></i>
            <div>
              <strong>${state.form.duration}s · ${state.form.resolution} · ${state.form.count}条</strong>
              <span>参数已限制在当前版本可生产范围内。</span>
            </div>
          </div>
        </aside>
      </section>

      <input hidden type="file" accept="video/*" data-file-input="reference" />
      <input hidden type="file" accept="image/*" data-file-input="portrait" />
    `,
    "dashboard",
  );
}

function renderReview() {
  return shell(
    `
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
          ${renderQueueRows()}
        </div>
      </section>

      ${renderProductionServiceStatusPanel()}

      <section class="recent-card" style="margin-top: 28px;">
        <div class="page-head" style="margin-bottom: 0;">
          <div>
            <h2 class="section-title">生产执行队列</h2>
            <p class="lede">这里只显示已完成二次确认、等待操作员执行的生产请求。</p>
          </div>
          <button class="button button--small" data-refresh-production-requests>刷新执行队列</button>
        </div>
        <div class="delivery-list" style="margin-top: 24px;">
          ${renderProductionRequestRows()}
        </div>
      </section>

      <section class="review-grid">
        <aside class="review-card">
          <span class="pill pill--blue">参考预览</span>
          ${phonePreview(state.form.referencePreview, "参考视频", "phone--large")}
          <div class="chip-row">
            <span class="pill">${state.form.duration}s</span>
            <span class="pill">${state.form.resolution}</span>
          </div>
        </aside>

        <article class="review-card">
          ${renderReviewDraftPanel()}
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
            <span class="muted">单批 ${state.form.count} 条，单条 ${state.form.duration} 秒，清晰度 ${state.form.resolution}。</span>
          </div>
        </aside>
      </section>
    `,
    "review",
  );
}

function renderGenerating() {
  const task = state.currentTask;
  const payload = task?.payload || state.form;
  const taskStatus = !task ? "待创建" : task.status === "queued" ? "排队中" : "处理中";
  const taskButtonClass = task ? "button button--primary button--loading" : "button button--primary";
  const bannerTitle = task ? "已提交，生产任务正在进行" : "等待任务提交";
  const bannerSubtitle = task ? "可以离开页面，完成后会在交付区提示。" : "请从创建作品或人工审核页提交任务。";
  const visibleProgress = task ? state.progress : 0;

  return shell(
    `
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
          <p class="lede">系统正在处理画面、字幕和交付包。当前任务 ${task?.id || "待创建"}，状态会持续更新。</p>
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
            <div class="progress-ring progress-ring--large" data-progress-ring data-progress="${visibleProgress}" style="--progress: ${visibleProgress};"></div>
          </div>
          ${renderOperationPanel()}
          ${renderGenerationApprovalPanel()}
          ${renderProductionPrepPanel()}
        </article>

        <aside class="generation-side">
          <span class="pill pill--amber">任务抽屉</span>
          <h2 class="section-title" style="margin-top: 24px;">当前批次</h2>
          <p class="lede">生产 ${payload.count} 条，每条最长 ${payload.duration} 秒，清晰度 ${payload.resolution}。</p>
          ${phonePreview(state.form.portraitPreview, "指定肖像", "phone--large")}
        </aside>
      </section>
    `,
    "review",
  );
}

function renderDelivery() {
  const task = state.currentTask;
  const payload = task?.payload || state.form;
  const deliverables = state.deliverables.length ? state.deliverables : defaultDeliverables(payload);

  return shell(
    `
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
          <p class="lede">当前交付包来自任务 ${task?.id || "演示任务"}，下载按钮会模拟交付动作，后续可接入真实文件。</p>
          <div class="delivery-list">
            ${deliverables.map((item) => deliveryItem(item.title, item.subtitle, item.action, item.url)).join("")}
          </div>
        </div>
      </section>
    `,
    "works",
  );
}

function renderWorks() {
  const taskRows = state.tasks.length
    ? state.tasks.map(taskWorkItem).join("")
    : `
        ${workItem("律师口播复刻", "已交付 · 演示数据", "delivery", "查看交付")}
        ${workItem("门店探访短片", "待审核 · 演示数据", "review", "去审核")}
        ${workItem("品牌种草素材", "草稿 · 演示数据", "create", "继续编辑")}
      `;

  return shell(
    `
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
    `,
    "works",
  );
}

function renderLibrary() {
  return shell(
    `
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
    `,
    "library",
  );
}

function renderData() {
  return shell(
    `
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
      ${renderProductionServiceConfigurationPanel()}
      ${renderProductionAuditLogPanel()}
      <section class="recent-card">
        <h2 class="section-title">流程漏斗</h2>
        <div class="stage-list" style="margin-top: 32px;">
          ${stage("导入参考", "126 个任务", "done")}
          ${stage("人工审核", "118 个通过", "done")}
          ${stage("生成交付", "116 个完成", "done")}
          ${stage("团队下载", "104 次下载", "active")}
        </div>
      </section>
    `,
    "data",
  );
}

function renderProductionAuditLogPanel() {
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
        <span>${escapeHtml(event.detail || "已记录")} · ${escapeHtml(event.actor || "系统")} · ${timeLabel}</span>
      </div>
    </div>
  `;
}

function renderProductionServiceConfigurationPanel() {
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

function uploadCard(kind, title, fileName, description, tone, action) {
  return `
    <div class="upload-card ${tone}">
      <i class="upload-icon"></i>
      <div>
        <strong>${title}</strong>
        <p class="muted" style="margin: 6px 0 0; font-size: 13px;">${description}</p>
        <span class="muted" style="display: block; margin-top: 8px; font-size: 12px;">${escapeHtml(fileName)}</span>
      </div>
      <button class="button button--small" data-upload="${kind}">${action}</button>
    </div>
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
  const mark = status === "done" ? "✓" : status === "active" ? "•" : "";
  return `
    <div class="stage ${status ? `is-${status}` : ""}">
      <span class="stage__mark">${mark}</span>
      <div>
        <strong>${title}</strong>
        <span ${extraAttr}>${subtitle}</span>
      </div>
    </div>
  `;
}

function checkRow(title, stateText, status) {
  const warning = status === "warning";
  return `
    <div class="check-row">
      <span class="check-row__icon ${warning ? "is-warning" : ""}">${warning ? "!" : "✓"}</span>
      <strong>${title}</strong>
      <span class="check-row__state ${warning ? "is-warning" : ""}">${stateText}</span>
    </div>
  `;
}

function deliveryItem(title, subtitle, action, url = "") {
  return `
    <div class="delivery-item">
      <i class="status-dot status-dot--green"></i>
      <div>
        <strong>${escapeHtml(title)}</strong>
        <span>${escapeHtml(subtitle)}</span>
      </div>
      <button class="button button--small" data-delivery-action="${escapeHtml(action)}" data-delivery-url="${escapeHtml(url)}">${escapeHtml(action)}</button>
    </div>
  `;
}

function workItem(title, subtitle, route, action) {
  return `
    <div class="delivery-item">
      <i class="status-dot ${route === "delivery" ? "status-dot--green" : "status-dot--amber"}"></i>
      <div>
        <strong>${title}</strong>
        <span>${subtitle}</span>
      </div>
      <button class="button button--small" data-route="${route}">${action}</button>
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
        <span>${taskStatusLabel(task)} · ${task.progress || 0}% · ${formatRelativeTime(task.createdAt)}</span>
      </div>
      <div class="form-actions" style="gap: 8px;">
        <button class="button button--small" data-open-task-detail="${escapeHtml(task.id)}">查看详情</button>
        <button class="button button--small" data-open-task="${escapeHtml(task.id)}" data-open-route="${route}">${action}</button>
      </div>
    </div>
  `;
}

function renderQueueRows() {
  if (!state.queueEntries.length) {
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

  return state.queueEntries.map(queueItem).join("");
}

function renderProductionServiceStatusPanel() {
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

function renderProductionRequestRows() {
  if (!state.productionRequests.length) {
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

  return state.productionRequests.map(productionRequestItem).join("");
}

function productionRequestItem(item) {
  const dotClass = item.executionStarted ? "status-dot--green" : "status-dot--amber";
  const actionButton = item.executionStarted
    ? `
      <div class="form-actions" style="gap: 8px;">
        <button class="button button--small" data-open-task-detail="${escapeHtml(item.taskId || "")}">查看详情</button>
        <button class="button button--small" data-execute-production-adapter="${escapeHtml(item.taskId || "")}">执行生产服务</button>
        <button class="button button--small button--primary" data-complete-production-request="${escapeHtml(item.taskId || "")}">标记交付</button>
      </div>
    `
    : `
      <div class="form-actions" style="gap: 8px;">
        <button class="button button--small" data-open-task-detail="${escapeHtml(item.taskId || "")}">查看详情</button>
        <button class="button button--small button--primary" data-claim-production-request="${escapeHtml(item.taskId || "")}">领取任务</button>
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
  const route = item.route || (item.status === "completed" ? "delivery" : "generating");
  const action = item.status === "completed" ? "查看交付" : "看进度";
  const note = item.blockingNote ? ` · ${item.blockingNote}` : "";

  return `
    <div class="delivery-item">
      <i class="status-dot ${dotClass}"></i>
      <div>
        <strong>${escapeHtml(item.title || "参考视频复刻")}</strong>
        <span>${escapeHtml(item.statusLabel || "待处理")} · ${escapeHtml(item.sourceState || "等待提交")} · 下一步：${escapeHtml(item.nextAction || "等待后台处理")}${note}</span>
      </div>
      <div class="form-actions" style="gap: 8px;">
        <button class="button button--small" data-open-task-detail="${escapeHtml(item.taskId || "")}">查看详情</button>
        <button class="button button--small" data-open-task="${escapeHtml(item.taskId || "")}" data-open-route="${route}">${action}</button>
      </div>
    </div>
  `;
}

function renderTaskDetailDrawer() {
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

function renderReviewDraftPanel() {
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

function renderOperationPanel() {
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
        ${panel.steps.map(operationStepItem).join("")}
      </div>
    </section>
  `;
}

function renderGenerationApprovalPanel() {
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

function renderProductionPrepPanel() {
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

function assetCard(image, title, subtitle) {
  return `
    <button class="work-row" type="button" data-toast-title="已选择素材" data-toast-message="${title} 已加入当前草稿。">
      <img src="${image}" alt="${title}" style="width: 54px; height: 54px; border-radius: 16px; object-fit: cover;" />
      <span>
        <strong>${title}</strong>
        <span>${subtitle}</span>
      </span>
    </button>
  `;
}

function metric(label, value, helper) {
  return `
    <div class="metric-card">
      <span class="metric-card__label">${label}</span>
      <strong class="metric-card__value">${value}</strong>
      <span class="metric-card__helper">${helper}</span>
    </div>
  `;
}

function saveFormValues() {
  document.querySelectorAll("[data-field]").forEach((field) => {
    const key = field.dataset.field;
    if (!key) return;

    if (key === "duration") {
      state.form.duration = clampNumber(field.value, 1, 15);
      field.value = state.form.duration;
      return;
    }

    if (key === "count") {
      state.form.count = clampNumber(field.value, 1, 5);
      field.value = state.form.count;
      return;
    }

    state.form[key] = field.value;
  });
}

function cleanSubtitlePunctuation() {
  saveFormValues();
  state.form.script = normalizeSubtitleText(state.form.script);
  render();
  showToast("字幕已整理", "每行短句结尾标点已清理。");
}

function bindEvents() {
  findAll(document, "[data-route]").forEach((button) => {
    button.addEventListener("click", () => {
      saveFormValues();
      navigate(button.dataset.route);
    });
  });

  findAll(document, "[data-field]").forEach((field) => {
    field.addEventListener("input", saveFormValues);
    field.addEventListener("change", saveFormValues);
  });

  const loginForm = find(document, "[data-login-form]");
  if (loginForm) {
    loginForm.addEventListener("submit", (event) => {
      event.preventDefault();
      login();
    });
  }

  findAll(document, "[data-login]").forEach((button) => {
    button.addEventListener("click", login);
  });

  const quickImport = find(document, "[data-quick-import]");
  if (quickImport) {
    quickImport.addEventListener("submit", (event) => {
      event.preventDefault();
      const formData = new FormData(quickImport);
      state.form.referenceUrl = formData.get("referenceUrl") || "";
      navigate("create");
      showToast("已导入参考", "请补充肖像图和生产参数。");
    });
  }

  findAll(document, "[data-upload]").forEach((button) => {
    button.addEventListener("click", () => {
      const input = find(document, `[data-file-input="${button.dataset.upload}"]`);
      input?.click();
    });
  });

  findAll(document, "[data-file-input]").forEach((input) => {
    input.addEventListener("change", () => {
      const file = input.files?.[0];
      if (!file) return;

      if (input.dataset.fileInput === "reference") {
        state.form.referenceName = file.name;
        if (file.type.startsWith("image/")) {
          state.form.referencePreview = URL.createObjectURL(file);
        }
      }

      if (input.dataset.fileInput === "portrait") {
        state.form.portraitName = file.name;
        state.form.portraitPreview = URL.createObjectURL(file);
      }

      render();
      showToast("素材已更新", `${file.name} 已加入当前草稿。`);
    });
  });

  findAll(document, "[data-save-form]").forEach((button) => {
    button.addEventListener("click", () => {
      saveFormValues();
      showToast("草稿已保存", "参数、文案和素材状态已记录。");
    });
  });

  findAll(document, "[data-to-review]").forEach((button) => {
    button.addEventListener("click", () => {
      saveFormValues();
      navigate("review");
      showToast("进入人工审核", "请确认文案、授权和字幕规则。");
    });
  });

  findAll(document, "[data-clean-subtitles]").forEach((button) => {
    button.addEventListener("click", cleanSubtitlePunctuation);
  });

  findAll(document, "[data-save-review]").forEach((button) => {
    button.addEventListener("click", () => {
      saveReviewDecision(false);
    });
  });

  findAll(document, "[data-approve-review]").forEach((button) => {
    button.addEventListener("click", () => {
      saveReviewDecision(true);
    });
  });

  findAll(document, "[data-start-generation]").forEach((button) => {
    button.addEventListener("click", () => {
      saveFormValues();
      startGeneration();
    });
  });

  findAll(document, "[data-open-task]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.currentTaskId = button.dataset.openTask;
      window.localStorage.setItem("chiling-workbench.current-task-id", state.currentTaskId);
      await refreshCurrentTask();

      if (button.dataset.openRoute === "delivery") {
        state.deliverables = await window.ChilingTaskApi.listDeliverables(state.currentTaskId);
      }

      if (button.dataset.openRoute === "generating") {
        await refreshOperations(state.currentTaskId);
        startTaskPolling({ navigateOnComplete: true });
      }

      navigate(button.dataset.openRoute);
    });
  });

  findAll(document, "[data-open-task-detail]").forEach((button) => {
    button.addEventListener("click", () => {
      openTaskDetail(button.dataset.openTaskDetail);
    });
  });

  findAll(document, "[data-close-task-detail]").forEach((button) => {
    button.addEventListener("click", closeTaskDetail);
  });

  findAll(document, "[data-refresh-queue]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await refreshQueue();
        render();
        showToast("队列已刷新", "后台生产状态已更新。");
      } catch (error) {
        showToast("刷新失败", error.message || "请稍后重试。");
      }
    });
  });

  findAll(document, "[data-refresh-production-requests]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await refreshProductionRequests();
        render();
        showToast("执行队列已刷新", "待生产请求状态已更新。");
      } catch (error) {
        showToast("刷新失败", error.message || "请稍后重试。");
      }
    });
  });

  findAll(document, "[data-refresh-production-service-status]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await refreshProductionServiceStatus();
        render();
        showToast("诊断已刷新", "真实生产服务状态已更新。");
      } catch (error) {
        showToast("诊断失败", error.message || "请稍后重试。");
      }
    });
  });

  findAll(document, "[data-refresh-production-service-configuration]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await refreshProductionServiceConfiguration();
        render();
        showToast("配置已刷新", "管理员生产服务配置清单已更新。");
      } catch (error) {
        showToast("刷新失败", error.message || "请稍后重试。");
      }
    });
  });

  findAll(document, "[data-refresh-production-audit-log]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await refreshProductionAuditLog();
        render();
        showToast("审计已刷新", "生产执行审计时间线已更新。");
      } catch (error) {
        showToast("刷新失败", error.message || "请稍后重试。");
      }
    });
  });

  findAll(document, "[data-claim-production-request]").forEach((button) => {
    button.addEventListener("click", () => {
      claimProductionRequest(button.dataset.claimProductionRequest);
    });
  });

  findAll(document, "[data-complete-production-request]").forEach((button) => {
    button.addEventListener("click", () => {
      completeProductionRequest(button.dataset.completeProductionRequest);
    });
  });

  findAll(document, "[data-execute-production-adapter]").forEach((button) => {
    button.addEventListener("click", () => {
      executeProductionAdapter(button.dataset.executeProductionAdapter);
    });
  });

  findAll(document, "[data-refresh-operations]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await refreshOperations();
        render();
        showToast("状态已刷新", "后台操作状态已更新。");
      } catch (error) {
        showToast("刷新失败", error.message || "请稍后重试。");
      }
    });
  });

  findAll(document, "[data-refresh-review-draft]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        saveFormValues();
        await refreshReviewDraft();
        render();
        showToast("草稿已同步", "解析摘要和文案草稿已带入审核页，可继续修改。");
      } catch (error) {
        showToast("同步失败", error.message || "请稍后重试。");
      }
    });
  });

  findAll(document, "[data-refresh-production-prep]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await refreshProductionPrep();
        render();
        showToast("准备包已刷新", "生产准备状态已更新。");
      } catch (error) {
        showToast("刷新失败", error.message || "请稍后重试。");
      }
    });
  });

  findAll(document, "[data-run-operation]").forEach((button) => {
    button.addEventListener("click", () => {
      runOperationAction(button.dataset.runOperation);
    });
  });

  const generationPhraseInput = find(document, "[data-generation-phrase]");
  if (generationPhraseInput) {
    generationPhraseInput.addEventListener("input", () => {
      state.generationPhrase = generationPhraseInput.value;
    });
  }

  const productionRequestPhraseInput = find(document, "[data-production-request-phrase]");
  if (productionRequestPhraseInput) {
    productionRequestPhraseInput.addEventListener("input", () => {
      state.productionRequestPhrase = productionRequestPhraseInput.value;
    });
  }

  findAll(document, "[data-approve-generation]").forEach((button) => {
    button.addEventListener("click", () => {
      approveGenerationGate();
    });
  });

  findAll(document, "[data-submit-production-request]").forEach((button) => {
    button.addEventListener("click", () => {
      submitProductionRequest();
    });
  });

  findAll(document, "[data-delivery-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const action = button.dataset.deliveryAction;
      const url = button.dataset.deliveryUrl;

      if (url && action === "复制") {
        const absoluteUrl = new URL(url, window.location.origin).href;
        try {
          await navigator.clipboard.writeText(absoluteUrl);
        } catch {
          window.prompt("复制交付链接", absoluteUrl);
        }
        showToast("链接已复制", "交付链接已复制到剪贴板。");
        return;
      }

      if (url) {
        window.open(url, "_blank", "noopener");
        showToast(`${action}已打开`, "已打开任务交付文件。");
        return;
      }

      showToast(`${action}已准备`, "演示环境已模拟交付动作。");
    });
  });

  findAll(document, "[data-toast-title]").forEach((button) => {
    button.addEventListener("click", () => {
      showToast(button.dataset.toastTitle, button.dataset.toastMessage || "操作已完成。");
    });
  });
}

function render() {
  if (!state.loggedIn && state.page !== "login") {
    state.page = "login";
  }

  const pageRenderers = {
    login: renderLogin,
    dashboard: renderDashboard,
    create: renderCreate,
    review: renderReview,
    generating: renderGenerating,
    delivery: renderDelivery,
    works: renderWorks,
    library: renderLibrary,
    data: renderData,
  };

  appRoot.innerHTML = pageRenderers[state.page]() + renderTaskDetailDrawer();
  bindEvents();
  updateProgressOnly();
}

function applyRouteFromHash() {
  const route = window.location.hash.replace("#", "");
  if (!routeIds.has(route)) return;

  state.page = route;
  state.loggedIn = route !== "login";
}

window.addEventListener("hashchange", () => {
  applyRouteFromHash();
  render();
});

async function initialize() {
  applyRouteFromHash();
  render();

  try {
    await refreshTasks();
    await refreshQueue();

    if (state.currentTaskId) {
      await refreshCurrentTask();
      if (state.currentTask?.status !== "completed") {
        startTaskPolling({ navigateOnComplete: state.page === "generating" });
      } else {
        state.deliverables = await window.ChilingTaskApi.listDeliverables(state.currentTaskId);
      }
      await refreshOperations(state.currentTaskId);
      await refreshReviewDraft(state.currentTaskId);
    }

    render();
  } catch (error) {
    showToast("任务数据读取失败", error.message || "请刷新页面重试。");
  }
}

initialize();
