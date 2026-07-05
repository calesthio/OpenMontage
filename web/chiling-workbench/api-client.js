(function () {
  const STORAGE_KEY = "chiling-workbench.tasks.v1";
  const API_BASE_KEY = "chiling-workbench.api-base";
  const DEFAULT_LATENCY = 180;

  function delay(ms = DEFAULT_LATENCY) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
  }

  function readTasks() {
    try {
      return JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "[]");
    } catch {
      return [];
    }
  }

  function writeTasks(tasks) {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks));
  }

  function getApiBase() {
    return window.CHILING_API_BASE || window.localStorage.getItem(API_BASE_KEY) || "";
  }

  function getTaskTitle(payload) {
    const scriptFirstLine = String(payload.script || "")
      .split("\n")
      .map((line) => line.trim())
      .find(Boolean);

    if (payload.referenceUrl) {
      return "参考视频复刻";
    }

    return scriptFirstLine ? `${scriptFirstLine.slice(0, 8)} · 口播复刻` : "新建口播复刻";
  }

  function createMockTask(payload) {
    const now = Date.now();
    return {
      id: `task_${now}_${Math.random().toString(16).slice(2, 8)}`,
      title: getTaskTitle(payload),
      status: "queued",
      progress: 8,
      createdAt: now,
      updatedAt: now,
      completedAt: null,
      estimatedSeconds: Math.max(6, Number(payload.count || 1) * 5),
      payload,
    };
  }

  function stageState(progress, index) {
    const thresholds = [15, 34, 76, 92, 100];
    const start = index === 0 ? 0 : thresholds[index - 1];
    const end = thresholds[index];

    if (progress >= end) return "done";
    if (progress >= start) return "active";
    return "waiting";
  }

  function addTaskDerivedFields(task) {
    const progress = Number(task.progress || 0);
    const stageNames = ["解析参考", "整理文案", "生成画面", "合成字幕", "质检交付"];

    return {
      ...task,
      stages: stageNames.map((name, index) => ({
        name,
        state: stageState(progress, index),
        detail:
          stageState(progress, index) === "done"
            ? "完成"
            : stageState(progress, index) === "active"
              ? `${progress}%`
              : index === 4
                ? "预计数分钟"
                : "等待",
      })),
    };
  }

  function refreshMockTask(task) {
    const deliveryReady = task.deliveryBackfill?.status === "delivered";
    if (deliveryReady || task.status === "completed") {
      return addTaskDerivedFields({
        ...task,
        status: "completed",
        progress: 100,
        completedAt: task.completedAt || Date.now(),
      });
    }

    const elapsed = Math.max(0, Date.now() - task.createdAt);
    const estimatedMs = Math.max(6000, Number(task.estimatedSeconds || 10) * 1000);
    const progress = Math.min(99, Math.max(task.progress || 0, Math.round((elapsed / estimatedMs) * 100)));

    return addTaskDerivedFields({
      ...task,
      status: progress < 16 ? "queued" : "processing",
      progress,
      updatedAt: Date.now(),
      completedAt: null,
    });
  }

  async function request(path, options = {}) {
    const base = getApiBase();

    if (!base) {
      return null;
    }

    const response = await window.fetch(`${base}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
    });

    if (!response.ok) {
      throw new Error(`接口请求失败：${response.status}`);
    }

    return response.json();
  }

  async function createTask(payload) {
    const remote = await request("/tasks", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    if (remote) {
      return remote;
    }

    await delay();
    const task = createMockTask(payload);
    const tasks = [task, ...readTasks()];
    writeTasks(tasks);
    return addTaskDerivedFields(task);
  }

  async function getTask(taskId) {
    const remote = await request(`/tasks/${encodeURIComponent(taskId)}`);

    if (remote) {
      return remote;
    }

    await delay(120);
    const tasks = readTasks();
    const task = tasks.find((item) => item.id === taskId);

    if (!task) {
      return null;
    }

    const refreshed = refreshMockTask(task);
    writeTasks(tasks.map((item) => (item.id === taskId ? refreshed : item)));
    return refreshed;
  }

  async function listTasks() {
    const remote = await request("/tasks");

    if (remote) {
      return remote;
    }

    await delay(120);
    const tasks = readTasks().map(refreshMockTask);
    writeTasks(tasks);
    return tasks.sort((a, b) => b.createdAt - a.createdAt);
  }

  function queueEntryFromTask(task) {
    const handoffStatus = task.pipeline_handoff?.status || task.pipeline?.handoffStatus || "";
    const nextStage = task.pipeline_handoff?.next_stage || task.pipeline?.nextStage || "";
    const status = task.status || "queued";

    return {
      id: `queue_${task.id}`,
      taskId: task.id,
      title: task.title || "参考视频复刻",
      status,
      statusLabel: taskStatusLabel(status),
      progress: Number(task.progress || 0),
      sourceState: sourceStateLabel(handoffStatus),
      nextAction: status === "completed" ? "查看交付" : nextActionLabel(nextStage),
      approvalRequired: task.pipeline?.requiresHumanApproval !== false,
      queueItemReady: Boolean(task.pipeline_handoff?.queue_item_path),
      createdAt: task.createdAt,
      updatedAt: task.updatedAt,
      route: status === "completed" ? "delivery" : "generating",
      blockingNote:
        handoffStatus === "source_needs_resolution"
          ? "链接类参考需先由后台解析；如平台限制访问，请补充本地视频。"
          : "",
    };
  }

  function taskStatusLabel(status) {
    if (status === "completed") return "已交付";
    if (status === "processing") return "生产中";
    if (status === "queued") return "排队中";
    if (status === "failed") return "处理失败";
    return "待处理";
  }

  function sourceStateLabel(status) {
    if (status === "source_imported_needs_analysis") return "素材已导入";
    if (status === "source_needs_resolution") return "等待获取参考";
    return "等待提交";
  }

  function nextActionLabel(nextStage) {
    if (nextStage === "analyze") return "解析参考";
    if (nextStage === "ingest") return "处理参考来源";
    return "等待后台处理";
  }

  async function listQueue() {
    const remote = await request("/pipeline-queue");

    if (remote) {
      return remote;
    }

    await delay(120);
    const tasks = readTasks().map(refreshMockTask);
    writeTasks(tasks);
    return tasks.sort((a, b) => b.createdAt - a.createdAt).map(queueEntryFromTask);
  }

  function productionRequestEntryFromTask(task) {
    const payload = task.payload || {};
    const productionRequest = task.productionRequest || {};
    const executionStarted = Boolean(productionRequest.executionStarted);
    return {
      id: `production_${task.id}`,
      taskId: task.id,
      title: task.title || "参考视频复刻",
      status: executionStarted ? "execution_in_progress" : "production_requested",
      statusLabel: executionStarted ? "执行中" : "等待生产",
      nextAction: executionStarted ? "操作员处理中" : "操作员执行",
      durationSeconds: payload.duration || 15,
      resolution: payload.resolution || "480p",
      batchCount: payload.count || 1,
      requestedAt: productionRequest.requestedAt,
      claimedAt: productionRequest.claimedAt,
      operatorName: productionRequest.operatorName || "",
      createdAt: task.createdAt,
      updatedAt: task.updatedAt,
      executionStarted,
      paidGenerationStarted: false,
      route: "generating",
    };
  }

  async function listProductionRequests() {
    const remote = await request("/production-requests");

    if (remote) {
      return remote;
    }

    await delay(120);
    const tasks = readTasks().map(refreshMockTask);
    writeTasks(tasks);
    return tasks
      .filter((task) => ["production_requested", "execution_in_progress"].includes(task.productionRequest?.status))
      .sort((a, b) => Number(b.productionRequest?.requestedAt || 0) - Number(a.productionRequest?.requestedAt || 0))
      .map(productionRequestEntryFromTask);
  }

  async function listProductionServiceStatus() {
    const remote = await request("/production-service/status");

    if (remote) {
      return remote;
    }

    await delay(120);
    return {
      status: "disabled",
      statusLabel: "未启用",
      ready: false,
      summary: "真实生产服务未启用，当前不会启动付费生成。",
      nextAction: "需要管理员开启生产服务后再执行。",
      executionAllowed: false,
      paidGenerationStarted: false,
      executionRequiresApproval: true,
      safeForUsers: true,
      checks: [
        {
          id: "manual_gate",
          label: "人工审批闸门",
          state: "ok",
          message: "正式生产前必须经过人工确认。",
        },
        {
          id: "service_switch",
          label: "生产服务开关",
          state: "blocked",
          message: "未启用。",
        },
        {
          id: "service_connection",
          label: "服务连接",
          state: "waiting",
          message: "启用后检测连接配置。",
        },
        {
          id: "paid_generation_guard",
          label: "付费生成保护",
          state: "ok",
          message: "当前诊断不会启动付费生成。",
        },
      ],
    };
  }

  function productionServiceConfigurationFromStatus(status) {
    const serviceEnabled = status.status !== "disabled";
    const connectionReady = status.status === "ready";
    const connectionState = connectionReady ? "ok" : serviceEnabled ? "blocked" : "waiting";

    return {
      title: "生产服务配置",
      editable: false,
      secretInputAllowed: false,
      status,
      items: [
        {
          id: "service_switch",
          label: "服务开关",
          state: serviceEnabled ? "ok" : "blocked",
          description: "控制真实生产服务是否进入可检测状态。",
        },
        {
          id: "service_connection",
          label: "连接配置",
          state: connectionState,
          description: "检查生产服务连接是否已由管理员配置完成。",
        },
        {
          id: "execution_approval",
          label: "执行审批",
          state: "locked",
          description: "即使配置就绪，正式执行仍需单独审批开启。",
        },
        {
          id: "secret_hosting",
          label: "密钥托管",
          state: "server_only",
          description: "不在页面填写密钥；敏感配置仅服务端配置。",
        },
      ],
      adminChecklist: ["在服务端开启真实生产服务", "补全生产服务连接配置", "完成内部审批后再开启受控执行"],
      guardrails: ["不在页面填写密钥", "不向普通用户展示底层供应商或模型名称", "配置诊断不会启动付费生成"],
      paidGenerationStarted: false,
    };
  }

  async function listProductionServiceConfiguration() {
    const remote = await request("/production-service/configuration");

    if (remote) {
      return remote;
    }

    await delay(120);
    const status = await listProductionServiceStatus();
    return productionServiceConfigurationFromStatus(status);
  }

  function productionAuditLogFromTasks(tasks) {
    const events = [];
    tasks.forEach((task) => {
      const productionRequest = task.productionRequest || {};
      const deliveryBackfill = task.deliveryBackfill || {};
      const title = task.title || "参考视频复刻";
      if (productionRequest.requestedAt) {
        events.push(productionAuditEvent(task.id, title, "production_requested", "提交生产请求", "已进入受控生产队列。", productionRequest.requestedAt, "审核员", "done", 10));
      }
      if (productionRequest.claimedAt) {
        events.push(
          productionAuditEvent(
            task.id,
            title,
            "production_claimed",
            "领取任务",
            "操作员已领取生产任务。",
            productionRequest.claimedAt,
            productionRequest.operatorName || "操作员",
            "done",
            20,
          ),
        );
      }
      if (productionRequest.executionStarted && productionRequest.status === "execution_in_progress") {
        events.push(
          productionAuditEvent(
            task.id,
            title,
            "production_service_waiting",
            "尝试执行生产服务",
            "真实生产服务未启用，未启动付费生成。",
            productionRequest.claimedAt || task.updatedAt,
            productionRequest.operatorName || "操作员",
            "blocked",
            30,
          ),
        );
      }
      if (deliveryBackfill.deliveredAt) {
        events.push(
          productionAuditEvent(
            task.id,
            title,
            "delivery_backfilled",
            "人工回填交付",
            deliveryBackfill.auditNote || "人工回填完成",
            deliveryBackfill.deliveredAt,
            productionRequest.operatorName || "操作员",
            "done",
            40,
          ),
        );
      }
      if (task.completedAt) {
        events.push(productionAuditEvent(task.id, title, "delivery_ready", "进入交付区", "交付包已准备，可进入成品交付页。", task.completedAt, "系统", "done", 50));
      }
    });

    events.sort((a, b) => Number(a.at || 0) - Number(b.at || 0) || Number(a.order || 0) - Number(b.order || 0));
    return {
      events,
      paidGenerationStarted: false,
      safeForUsers: true,
    };
  }

  function productionAuditEvent(taskId, title, event, label, detail, at, actor, state, order) {
    const timestamp = Number(at || 0);
    return {
      id: `${taskId}_${event}_${timestamp}`,
      taskId,
      title,
      event,
      label,
      detail,
      at: timestamp,
      actor,
      state,
      order,
      paidGenerationStarted: false,
    };
  }

  async function listProductionAuditLog() {
    const remote = await request("/production-audit-log");

    if (remote) {
      return remote;
    }

    await delay(120);
    const tasks = readTasks().map(refreshMockTask);
    writeTasks(tasks);
    return productionAuditLogFromTasks(tasks);
  }

  function operationPanelFromTask(task) {
    const handoffStatus = task.pipeline_handoff?.status || task.pipeline?.handoffStatus || "";
    const progress = Number(task.progress || 0);
    const status = task.status || "queued";
    const sourceReady = handoffStatus === "source_imported_needs_analysis";
    const sourcePending = handoffStatus === "source_needs_resolution";
    const completed = status === "completed";
    const reviewApproved = task.review?.status === "approved";
    const generationReady = task.generationApproval?.status === "ready_for_production";
    const productionRequested = ["production_requested", "execution_in_progress"].includes(task.productionRequest?.status);

    const panel = {
      taskId: task.id,
      title: task.title || "参考视频复刻",
      status,
      statusLabel: taskStatusLabel(status),
      progress,
      safeAutoExecute: false,
      operatorHint: "当前面板只展示可执行状态；正式生成仍需人工审批。",
      steps: [
        operationStep(
          "reference_source",
          "参考素材",
          "确认参考视频或链接来源，保留素材与授权记录。",
          sourceReady || completed ? "done" : sourcePending ? "ready" : "waiting",
          sourceReady || completed ? "已导入" : "处理参考来源",
          false,
          sourcePending && !completed,
        ),
        operationStep(
          "reference_analysis",
          "参考解析",
          "解析视频结构、节奏、镜头与可复用信息。",
          progressState(progress, 34, sourceReady, completed),
          completed || progress >= 34 ? "已完成" : sourceReady ? "开始解析" : "等待素材",
          false,
          sourceReady && progress < 34 && !completed,
        ),
        operationStep(
          "copy_extract",
          "文案提取",
          "整理口播文案、字幕短句和人工可编辑内容。",
          progressState(progress, 76, progress >= 34, completed),
          completed || progress >= 76 ? "已完成" : progress >= 34 ? "整理文案" : "等待解析",
          false,
          progress >= 34 && progress < 76 && !completed,
        ),
        operationStep(
          "human_review",
          "人工确认",
          "团队确认文案、字幕、肖像授权和画面方向。",
          completed || reviewApproved ? "done" : progress >= 76 ? "ready" : "locked",
          completed || reviewApproved ? "已完成" : progress >= 76 ? "进入审核" : "等待文案",
          true,
          false,
        ),
        operationStep(
          "generation_approval",
          "生成审批",
          "正式生产前进行最终确认，避免误触发付费生成。",
          completed || generationReady ? "done" : reviewApproved ? "ready" : "locked",
          completed || generationReady ? "已完成" : reviewApproved ? "输入确认短语" : "等待人工批准",
          true,
          false,
        ),
      ],
    };

    if (generationReady || productionRequested || completed) {
      panel.steps.push(
        operationStep(
          "production_handoff",
          "生产交接",
          "把审核后的准备包提交给受控生产队列。",
          completed || productionRequested ? "done" : "ready",
          completed || productionRequested ? "已提交" : "等待提交",
          true,
          false,
        ),
      );
    }

    return panel;
  }

  function operationStep(id, title, description, state, actionLabel, approvalRequired, canExecute) {
    return {
      id,
      title,
      description,
      state,
      stateLabel: operationStateLabel(state),
      actionLabel,
      approvalRequired,
      canExecute,
    };
  }

  function progressState(progress, doneAt, readyWhen, completed) {
    if (completed || progress >= doneAt) return "done";
    if (readyWhen) return "ready";
    return "waiting";
  }

  function operationStateLabel(state) {
    const labels = {
      done: "已完成",
      ready: "可处理",
      waiting: "等待中",
      locked: "需前置确认",
    };
    return labels[state] || "待处理";
  }

  async function listOperations(taskId) {
    const remote = await request(`/tasks/${encodeURIComponent(taskId)}/operations`);

    if (remote) {
      return remote;
    }

    await delay(120);
    const task = await getTask(taskId);
    return task ? operationPanelFromTask(task) : null;
  }

  async function runOperation(taskId, operationId) {
    const base = getApiBase();

    if (base) {
      const response = await window.fetch(`${base}/tasks/${encodeURIComponent(taskId)}/operations/actions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ operationId }),
      });
      const payload = await response.json();
      if (!response.ok && response.status !== 409) {
        throw new Error(payload.error || `接口请求失败：${response.status}`);
      }
      return payload;
    }

    await delay(160);
    const tasks = readTasks();
    const storedTask = tasks.find((item) => item.id === taskId);
    if (!storedTask) {
      return { status: "not_found", operationId, message: "任务不存在", paidGenerationStarted: false };
    }

    const task = refreshMockTask(storedTask);
    const result = runMockOperation(task, operationId);
    writeTasks(tasks.map((item) => (item.id === taskId ? result.task : item)));
    return result.response;
  }

  function runMockOperation(task, operationId) {
    if (operationId === "reference_analysis") {
      const updated = {
        ...task,
        status: "processing",
        progress: Math.max(Number(task.progress || 0), 34),
        updatedAt: Date.now(),
      };
      return {
        task: updated,
        response: {
          status: "completed",
          operationId,
          message: "参考解析已完成，已整理视频结构、节奏和画面方向。",
          progress: updated.progress,
          paidGenerationStarted: false,
          panel: operationPanelFromTask(updated),
        },
      };
    }

    if (operationId === "copy_extract") {
      if (Number(task.progress || 0) < 34) {
        return {
          task,
          response: blockedOperationResponse(task, operationId, "请先完成参考解析。"),
        };
      }

      const updated = {
        ...task,
        status: "processing",
        progress: Math.max(Number(task.progress || 0), 76),
        updatedAt: Date.now(),
      };
      return {
        task: updated,
        response: {
          status: "completed",
          operationId,
          message: "文案提取已完成，已整理短句字幕和审核文本。",
          progress: updated.progress,
          paidGenerationStarted: false,
          panel: operationPanelFromTask(updated),
        },
      };
    }

    return {
      task,
      response: blockedOperationResponse(task, operationId, "该节点需要人工审批，当前不会自动执行。"),
    };
  }

  function blockedOperationResponse(task, operationId, message) {
    return {
      status: "blocked",
      operationId,
      message,
      progress: Number(task.progress || 0),
      paidGenerationStarted: false,
      panel: operationPanelFromTask(task),
    };
  }

  function reviewDraftFromTask(task) {
    const scriptDraft = String(task.payload?.script || "")
      .split("\n")
      .map((line) => line.trim().replace(/[，。,.！？!?；;：:、]+$/g, ""))
      .filter(Boolean)
      .join("\n");

    return {
      taskId: task.id,
      title: task.title || "参考视频复刻",
      editable: true,
      analysisSummary: task.payload?.analysisSummary || (Number(task.progress || 0) >= 34 ? "参考结构已完成本地整理。" : "等待参考解析后生成摘要。"),
      scriptDraft,
      subtitleRule: "短句句尾不显示标点。",
      reviewChecks: ["素材授权", "肖像授权", "字幕规则", "画面方向"],
      operatorHint: "这里的摘要和文案可人工修改，确认后再进入生产。",
    };
  }

  async function listReviewDraft(taskId) {
    const remote = await request(`/tasks/${encodeURIComponent(taskId)}/review-draft`);

    if (remote) {
      return remote;
    }

    await delay(120);
    const task = await getTask(taskId);
    return task ? reviewDraftFromTask(task) : null;
  }

  async function saveReview(taskId, reviewPayload) {
    const base = getApiBase();

    if (base) {
      const response = await window.fetch(`${base}/tasks/${encodeURIComponent(taskId)}/review-approval`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(reviewPayload),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || `接口请求失败：${response.status}`);
      }
      return payload;
    }

    await delay(160);
    const tasks = readTasks();
    const task = tasks.find((item) => item.id === taskId);
    if (!task) {
      return { status: "not_found", message: "任务不存在", paidGenerationStarted: false };
    }

    const approved = Boolean(reviewPayload.approved);
    const cleanScript = String(reviewPayload.script || task.payload?.script || "")
      .split("\n")
      .map((line) => line.trim().replace(/[，。,.！？!?；;：:、]+$/g, ""))
      .filter(Boolean)
      .join("\n");
    const updated = {
      ...task,
      status: "processing",
      progress: Math.max(Number(task.progress || 0), approved ? 82 : Number(task.progress || 0)),
      updatedAt: Date.now(),
      payload: {
        ...(task.payload || {}),
        analysisSummary: String(reviewPayload.analysisSummary || task.payload?.analysisSummary || "").trim(),
        script: cleanScript,
      },
      review: {
        status: approved ? "approved" : "saved",
        approved,
        updatedAt: Date.now(),
        approvedAt: approved ? Date.now() : null,
      },
    };
    writeTasks(tasks.map((item) => (item.id === taskId ? updated : item)));
    return {
      status: approved ? "approved" : "saved",
      taskId,
      message: approved ? "审核已通过，等待生成审批。" : "审核稿已保存。",
      review: updated.review,
      paidGenerationStarted: false,
      panel: operationPanelFromTask(updated),
    };
  }

  async function approveGeneration(taskId, confirmationPhrase) {
    const base = getApiBase();

    if (base) {
      const response = await window.fetch(`${base}/tasks/${encodeURIComponent(taskId)}/generation-approval`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirmationPhrase }),
      });
      const payload = await response.json();
      if (!response.ok && response.status !== 409) {
        throw new Error(payload.error || `接口请求失败：${response.status}`);
      }
      return payload;
    }

    await delay(160);
    const tasks = readTasks();
    const task = tasks.find((item) => item.id === taskId);
    if (!task) {
      return { status: "not_found", message: "任务不存在", requiredPhrase: "确认进入生产", paidGenerationStarted: false };
    }

    if (task.review?.status !== "approved") {
      return generationBlocked(task, "请先完成人工审核。");
    }

    if (String(confirmationPhrase || "").trim() !== "确认进入生产") {
      return generationBlocked(task, "确认短语不匹配。");
    }

    const updated = {
      ...task,
      status: "processing",
      progress: Math.max(Number(task.progress || 0), 88),
      updatedAt: Date.now(),
      generationApproval: {
        status: "ready_for_production",
        approvedAt: Date.now(),
        confirmationMatched: true,
        paidGenerationStarted: false,
      },
    };
    writeTasks(tasks.map((item) => (item.id === taskId ? updated : item)));
    return {
      status: "ready_for_production",
      taskId,
      message: "生成审批已通过，等待生产准备。",
      productionPrepared: true,
      requiredPhrase: "确认进入生产",
      paidGenerationStarted: false,
      panel: operationPanelFromTask(updated),
    };
  }

  function generationBlocked(task, message) {
    return {
      status: "blocked",
      taskId: task.id,
      message,
      productionPrepared: false,
      requiredPhrase: "确认进入生产",
      paidGenerationStarted: false,
      panel: operationPanelFromTask(task),
    };
  }

  function productionPrepFromTask(task) {
    if (task.review?.status !== "approved") {
      return {
        status: "blocked",
        taskId: task.id,
        title: task.title || "参考视频复刻",
        message: "请先完成人工审核。",
        paidGenerationStarted: false,
      };
    }

    if (task.generationApproval?.status !== "ready_for_production") {
      return {
        status: "blocked",
        taskId: task.id,
        title: task.title || "参考视频复刻",
        message: "请先完成生成审批确认。",
        paidGenerationStarted: false,
      };
    }

    const payload = task.payload || {};
    const scriptLines = String(payload.script || "")
      .split("\n")
      .map((line) => line.trim().replace(/[，。,.！？!?；;：:、]+$/g, ""))
      .filter(Boolean);

    return {
      status: "ready",
      taskId: task.id,
      title: task.title || "参考视频复刻",
      operatorHint: "生产准备包已就绪，可交给生产端继续执行；当前接口不会启动正式生成。",
      assets: {
        referenceName: payload.referenceName || "参考视频已就绪",
        portraitName: payload.portraitName || "肖像图已就绪",
        sourceState: sourceStateLabel(task.pipeline_handoff?.status || task.pipeline?.handoffStatus || ""),
      },
      constraints: {
        durationSeconds: payload.duration || 15,
        maxDurationSeconds: 15,
        resolution: payload.resolution || "480p",
        allowedResolutions: ["480p", "720p"],
        batchCount: payload.count || 1,
        maxBatchCount: 5,
        subtitleRule: "短句句尾不显示标点。",
      },
      review: {
        analysisSummary: payload.analysisSummary || "",
        scriptLines,
        checks: ["素材授权", "肖像授权", "字幕规则", "画面方向"],
      },
      productionRequest: {
        status: task.productionRequest?.status || "not_requested",
        executionStarted: Boolean(task.productionRequest?.executionStarted),
      },
      approval: {
        humanReview: "approved",
        generationApproval: "ready_for_production",
      },
      nextActions: ["进入受控生产流程", "正式生成前再次确认"],
      paidGenerationStarted: false,
    };
  }

  async function listProductionPrep(taskId) {
    const base = getApiBase();

    if (base) {
      const response = await window.fetch(`${base}/tasks/${encodeURIComponent(taskId)}/production-prep`);
      const payload = await response.json();
      if (!response.ok && response.status !== 409) {
        throw new Error(payload.error || `接口请求失败：${response.status}`);
      }
      return payload;
    }

    await delay(120);
    const task = await getTask(taskId);
    return task ? productionPrepFromTask(task) : null;
  }

  function productionRequestBlocked(task, message) {
    return {
      status: "blocked",
      taskId: task.id,
      message,
      requiredPhrase: "确认提交生产",
      executionStarted: false,
      paidGenerationStarted: false,
      panel: operationPanelFromTask(task),
    };
  }

  async function requestProduction(taskId, confirmationPhrase) {
    const base = getApiBase();

    if (base) {
      const response = await window.fetch(`${base}/tasks/${encodeURIComponent(taskId)}/production-request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirmationPhrase }),
      });
      const payload = await response.json();
      if (!response.ok && response.status !== 409) {
        throw new Error(payload.error || `接口请求失败：${response.status}`);
      }
      return payload;
    }

    await delay(160);
    const tasks = readTasks();
    const task = tasks.find((item) => item.id === taskId);
    if (!task) {
      return { status: "not_found", message: "任务不存在", requiredPhrase: "确认提交生产", paidGenerationStarted: false };
    }

    const prep = productionPrepFromTask(task);
    if (prep.status !== "ready") {
      return productionRequestBlocked(task, "请先完成生产准备包。");
    }

    if (String(confirmationPhrase || "").trim() !== "确认提交生产") {
      return productionRequestBlocked(task, "确认短语不匹配。");
    }

    const updated = {
      ...task,
      status: "processing",
      progress: Math.max(Number(task.progress || 0), 90),
      updatedAt: Date.now(),
      productionRequest: {
        status: "production_requested",
        requestedAt: Date.now(),
        confirmationMatched: true,
        executionStarted: false,
        paidGenerationStarted: false,
      },
    };
    writeTasks(tasks.map((item) => (item.id === taskId ? updated : item)));
    return {
      status: "production_requested",
      taskId,
      message: "生产请求已提交，等待受控生产流程执行。",
      requiredPhrase: "确认提交生产",
      executionStarted: false,
      paidGenerationStarted: false,
      panel: operationPanelFromTask(updated),
      productionPrep: productionPrepFromTask(updated),
    };
  }

  function productionClaimBlocked(task, message) {
    return {
      status: "blocked",
      taskId: task.id,
      message,
      executionStarted: false,
      paidGenerationStarted: false,
      panel: operationPanelFromTask(task),
    };
  }

  async function claimProductionRequest(taskId, operatorName) {
    const base = getApiBase();

    if (base) {
      const response = await window.fetch(`${base}/tasks/${encodeURIComponent(taskId)}/production-claim`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ operatorName }),
      });
      const payload = await response.json();
      if (!response.ok && response.status !== 409) {
        throw new Error(payload.error || `接口请求失败：${response.status}`);
      }
      return payload;
    }

    await delay(160);
    const tasks = readTasks();
    const task = tasks.find((item) => item.id === taskId);
    if (!task) {
      return { status: "not_found", message: "任务不存在", paidGenerationStarted: false };
    }

    if (!["production_requested", "execution_in_progress"].includes(task.productionRequest?.status)) {
      return productionClaimBlocked(task, "请先提交生产请求。");
    }

    const updatedRequest = {
      ...(task.productionRequest || {}),
      status: "execution_in_progress",
      claimedAt: task.productionRequest?.claimedAt || Date.now(),
      operatorName: task.productionRequest?.operatorName || String(operatorName || "操作员").trim() || "操作员",
      executionStarted: true,
      paidGenerationStarted: false,
    };
    const updated = {
      ...task,
      status: "processing",
      progress: Math.max(Number(task.progress || 0), 94),
      updatedAt: Date.now(),
      productionRequest: updatedRequest,
    };
    writeTasks(tasks.map((item) => (item.id === taskId ? updated : item)));
    return {
      status: "execution_in_progress",
      taskId,
      message: "任务已领取，已标记为执行中。",
      operatorName: updatedRequest.operatorName,
      executionStarted: true,
      paidGenerationStarted: false,
      productionRequest: updatedRequest,
      panel: operationPanelFromTask(updated),
    };
  }

  function productionCompleteBlocked(task, message) {
    return {
      status: "blocked",
      taskId: task.id,
      message,
      deliveryReady: false,
      paidGenerationStarted: false,
      panel: operationPanelFromTask(task),
    };
  }

  async function completeProductionRequest(taskId, deliveryPayload) {
    const base = getApiBase();

    if (base) {
      const response = await window.fetch(`${base}/tasks/${encodeURIComponent(taskId)}/production-complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(deliveryPayload || {}),
      });
      const payload = await response.json();
      if (!response.ok && response.status !== 409) {
        throw new Error(payload.error || `接口请求失败：${response.status}`);
      }
      return payload;
    }

    await delay(160);
    const tasks = readTasks();
    const task = tasks.find((item) => item.id === taskId);
    if (!task) {
      return { status: "not_found", message: "任务不存在", paidGenerationStarted: false };
    }

    if (task.productionRequest?.status !== "execution_in_progress") {
      return productionCompleteBlocked(task, "请先领取任务并标记为执行中。");
    }

    const now = Date.now();
    const backfill = {
      status: "delivered",
      deliveredAt: now,
      videoName: String(deliveryPayload?.videoName || "成品视频.mp4").trim() || "成品视频.mp4",
      subtitleName: String(deliveryPayload?.subtitleName || "字幕文件.srt").trim() || "字幕文件.srt",
      auditNote: String(deliveryPayload?.auditNote || "人工回填完成").trim() || "人工回填完成",
      paidGenerationStarted: false,
    };
    const updated = {
      ...task,
      status: "completed",
      progress: 100,
      updatedAt: now,
      completedAt: now,
      deliveryBackfill: backfill,
      productionRequest: {
        ...(task.productionRequest || {}),
        status: "delivered",
        completedAt: now,
        executionStarted: true,
        paidGenerationStarted: false,
      },
    };
    writeTasks(tasks.map((item) => (item.id === taskId ? updated : item)));
    return {
      status: "completed",
      taskId,
      message: "交付结果已回填，任务已进入交付区。",
      deliveryReady: true,
      paidGenerationStarted: false,
      deliveryBackfill: backfill,
    };
  }

  function productionExecuteBlocked(task, message) {
    return {
      status: "blocked",
      taskId: task.id,
      message,
      adapterExecutionStarted: false,
      paidGenerationStarted: false,
      panel: operationPanelFromTask(task),
    };
  }

  async function executeProductionAdapter(taskId, executionPayload) {
    const base = getApiBase();

    if (base) {
      const response = await window.fetch(`${base}/tasks/${encodeURIComponent(taskId)}/production-execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(executionPayload || {}),
      });
      const payload = await response.json();
      if (!response.ok && response.status !== 409) {
        throw new Error(payload.error || `接口请求失败：${response.status}`);
      }
      return payload;
    }

    await delay(160);
    const task = readTasks().find((item) => item.id === taskId);
    if (!task) {
      return { status: "not_found", message: "任务不存在", paidGenerationStarted: false };
    }

    if (task.productionRequest?.status !== "execution_in_progress") {
      return productionExecuteBlocked(task, "请先领取任务并标记为执行中。");
    }

    return {
      status: "disabled",
      taskId,
      message: "真实生产服务未启用，请继续使用人工回填。",
      adapterExecutionStarted: false,
      executionStarted: Boolean(task.productionRequest?.executionStarted),
      paidGenerationStarted: false,
      panel: operationPanelFromTask(task),
    };
  }

  async function listDeliverables(taskId) {
    const remote = await request(`/tasks/${encodeURIComponent(taskId)}/deliverables`);

    if (remote) {
      return remote;
    }

    await delay(120);
    const task = await getTask(taskId);

    if (!task || task.status !== "completed") {
      return [];
    }

    const resolution = task.payload?.resolution || "480p";
    const duration = task.payload?.duration || 15;
    const backfill = task.deliveryBackfill || {};
    const videoName = backfill.videoName || "成品视频";
    const subtitleName = backfill.subtitleName || "字幕文件";
    const auditNote = backfill.auditNote || "素材授权 · 肖像授权 · 文案确认";

    return [
      { id: "video", title: "成品视频", subtitle: `${videoName} · ${resolution} · ${duration}s`, action: "下载" },
      { id: "subtitle", title: "字幕文件", subtitle: `${subtitleName} · 句尾标点已清理`, action: "下载" },
      { id: "audit", title: "审核记录", subtitle: auditNote, action: "查看" },
      { id: "share", title: "交付链接", subtitle: "团队内部可访问", action: "复制" },
    ];
  }

  function taskDetailFromTask(task, deliverables) {
    const payload = task.payload || {};
    const review = task.review || {};
    const auditLog = productionAuditLogFromTasks([task]);
    const scriptPreview = String(payload.script || "")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .slice(0, 3)
      .join(" / ") || "等待审核文案";
    const prepReady = review.status === "approved" && task.generationApproval?.status === "ready_for_production";

    return {
      taskId: task.id,
      title: task.title || "参考视频复刻",
      status: task.status || "queued",
      statusLabel: taskStatusLabel(task.status || "queued"),
      progress: Number(task.progress || 0),
      paidGenerationStarted: false,
      safeForUsers: true,
      sections: [
        {
          id: "production_prep",
          title: "生产准备包",
          state: prepReady ? "ready" : "waiting",
          items: [
            detailItem("生产参数", `${payload.duration || 15}s · ${payload.resolution || "480p"} · ${payload.count || 1}条`),
            detailItem("素材", `${payload.referenceName || "参考视频已就绪"} · ${payload.portraitName || "肖像图已就绪"}`),
            detailItem("字幕规则", "短句句尾不显示标点"),
          ],
        },
        {
          id: "review_record",
          title: "人工审核记录",
          state: review.status || "waiting",
          items: [
            detailItem("解析摘要", payload.analysisSummary || "等待人工确认"),
            detailItem("文案预览", scriptPreview),
            detailItem("审核项", "素材授权 · 肖像授权 · 字幕规则 · 画面方向"),
          ],
        },
        {
          id: "production_audit",
          title: "生产执行审计",
          state: auditLog.events.length ? "ready" : "waiting",
          items: auditLog.events.length
            ? auditLog.events.map((event) => detailItem(event.label, `${event.detail} · ${event.actor}`, event.state || "done"))
            : [detailItem("暂无审计记录", "提交生产请求后开始记录", "waiting")],
        },
        {
          id: "deliverables",
          title: "交付物",
          state: deliverables.length ? "ready" : "waiting",
          items: deliverables.length
            ? deliverables.map((item) => detailItem(item.title || "交付物", item.subtitle || "等待交付"))
            : [detailItem("等待交付", "操作员回填后显示成品、字幕和审核记录", "waiting")],
        },
      ],
    };
  }

  function detailItem(label, value, state = "done") {
    return {
      label,
      value,
      state,
      paidGenerationStarted: false,
    };
  }

  async function listTaskDetail(taskId) {
    const remote = await request(`/tasks/${encodeURIComponent(taskId)}/detail`);

    if (remote) {
      return remote;
    }

    await delay(120);
    const task = await getTask(taskId);
    if (!task) {
      return { status: "not_found", message: "任务不存在", paidGenerationStarted: false };
    }
    const deliverables = await listDeliverables(taskId);
    return taskDetailFromTask(task, deliverables);
  }

  function setApiBase(baseUrl) {
    if (baseUrl) {
      window.localStorage.setItem(API_BASE_KEY, baseUrl);
    } else {
      window.localStorage.removeItem(API_BASE_KEY);
    }
  }

  window.ChilingTaskApi = {
    createTask,
    getTask,
    listTasks,
    listQueue,
    listProductionRequests,
    listProductionServiceStatus,
    listProductionServiceConfiguration,
    listProductionAuditLog,
    listOperations,
    runOperation,
    listReviewDraft,
    saveReview,
    approveGeneration,
    listProductionPrep,
    requestProduction,
    claimProductionRequest,
    completeProductionRequest,
    executeProductionAdapter,
    listDeliverables,
    listTaskDetail,
    setApiBase,
    getApiBase,
  };
})();
