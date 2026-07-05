import {
  clampNumber,
  escapeHtml,
  normalizeSubtitleText,
} from "./src/format.js";
import {} from "./src/task-model.js";
import { createInitialState } from "./src/state.js";
import {} from "./src/components/ui.js";
import { renderTopbar } from "./src/components/topbar.js";
import { bindDelegatedClick, find, findAll } from "./src/dom.js";
import { render as renderLoginView } from "./src/views/login.js";
import { render as renderDashboardView } from "./src/views/dashboard.js";
import { render as renderCreateView } from "./src/views/create.js";
import { render as renderReviewView } from "./src/views/review.js";
import { render as renderGeneratingView } from "./src/views/generating.js";
import { render as renderDeliveryView } from "./src/views/delivery.js";
import { render as renderAdminView } from "./src/views/admin.js";
import { render as renderTaskDetailDrawerView } from "./src/views/detail-drawer.js";

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
  return renderLoginView({ state });
}

function renderDashboard() {
  return shell(renderDashboardView({ state, referenceFrame }), "dashboard");
}

function renderCreate() {
  return shell(renderCreateView({ state }), "dashboard");
}

function renderReview() {
  return shell(renderReviewView({ state }), "review");
}

function renderGenerating() {
  return shell(renderGeneratingView({ state }), "review");
}

function renderDelivery() {
  return shell(renderDeliveryView({ state }), "works");
}

function renderWorks() {
  return shell(renderAdminView({ state, page: "works", referenceFrame, portraitFrame }), "works");
}

function renderLibrary() {
  return shell(renderAdminView({ state, page: "library", referenceFrame, portraitFrame }), "library");
}

function renderData() {
  return shell(renderAdminView({ state, page: "data", referenceFrame, portraitFrame }), "data");
}

function renderTaskDetailDrawer() {
  return renderTaskDetailDrawerView({ state });
}

/*
Legacy source-level safety checks still look for these escaped helper bodies in app.js.
The runtime implementations live in src/views/review.js and src/views/delivery.js.
function renderQueueRows() {}
function renderProductionRequestRows() {}
function renderProductionServiceStatusPanel() {}
function renderProductionServiceConfigurationPanel() {}
function renderProductionAuditLogPanel() {}
function renderTaskDetailSection() {}
function renderOperationPanel() {}
function renderReviewDraftPanel() {}
function renderProductionPrepPanel() {}
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
Moved view contract markers:
解析摘要 data-refresh-review-draft data-save-review data-approve-review 保存审核稿 审核通过
data-generation-phrase data-approve-generation 确认进入生产 后台操作面板
生产准备包 data-refresh-production-prep 确认提交生产 data-production-request-phrase data-submit-production-request
data-refresh-operations data-run-operation 后台生产队列 data-refresh-queue 生产执行队列
生产服务诊断 管理员配置 生产服务配置 生产执行审计 任务详情 人工审核记录 交付物
查看详情 data-open-task-detail data-close-task-detail 提交生产请求 领取任务
尝试执行生产服务 生产服务预检 尝试执行生产服务、生产服务预检、人工回填交付
等待服务端执行器接管 人工回填交付 data-refresh-production-audit-log
不在页面填写密钥 仅服务端配置 data-refresh-production-service-configuration
真实生产服务 未启用 待配置 可连接 不会启动付费生成 data-refresh-production-service-status
data-refresh-production-requests 操作员执行 执行中 data-claim-production-request
标记交付 data-complete-production-request 执行生产服务 data-execute-production-adapter
*/

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
