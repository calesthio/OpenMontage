import { normalizeSubtitleText } from "./format.js";

const CURRENT_TASK_STORAGE_KEY = "chiling-workbench.current-task-id";
const noopHistory = { replaceState() {} };

function getDefaultHistory() {
  return globalThis.history || noopHistory;
}

export function createActions({ state, api, storage, render, showToast, refresh, history = getDefaultHistory() }) {
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
      const task = await api.createTask(buildTaskPayload());
      state.currentTask = task;
      state.currentTaskId = task.id;
      state.progress = task.progress || 0;
      storage.setItem(CURRENT_TASK_STORAGE_KEY, task.id);
      await refresh.afterTaskCreated(task);
      state.isSubmitting = false;
      state.page = "generating";
      history.replaceState(null, "", "#generating");
      render();
      showToast("任务已提交", "生产任务已进入队列，完成后会进入交付区。");
      refresh.startTaskPolling({ navigateOnComplete: true });
    } catch (error) {
      state.isSubmitting = false;
      render();
      showToast("提交失败", error.message || "任务创建失败，请稍后重试。");
    }
  }

  return {
    buildTaskPayload,
    startGeneration,
  };
}
