const STAGE_NAMES = ["解析参考", "整理文案", "生成画面", "合成字幕", "质检交付"];
const STAGE_THRESHOLDS = [15, 34, 76, 92, 100];

function stageState(progress, index) {
  const start = index === 0 ? 0 : STAGE_THRESHOLDS[index - 1];
  const end = STAGE_THRESHOLDS[index];

  if (progress >= end) return "done";
  if (progress >= start) return "active";
  return "waiting";
}

export function deriveStageList(task = {}) {
  const progress = Number(task.progress || 0);
  return STAGE_NAMES.map((name, index) => {
    const state = stageState(progress, index);
    return {
      name,
      state,
      detail: state === "done" ? "完成" : state === "active" ? `${progress}%` : index === 4 ? "预计数分钟" : "等待",
    };
  });
}

export function taskStatusLabel(task = {}) {
  if (task.status === "completed") return "已交付";
  if (task.status === "processing") return "生产中";
  if (task.status === "queued") return "排队中";
  if (task.status === "failed") return "处理失败";
  return "待处理";
}

export function defaultDeliverables(payload = {}) {
  const resolution = payload.resolution || "480p";
  return [
    { title: "成片文件", subtitle: `${resolution} 视频，可直接发布`, action: "下载视频", url: "#" },
    { title: "字幕文件", subtitle: "可二次校对和归档", action: "下载字幕", url: "#" },
    { title: "审核记录", subtitle: "留存素材授权与审核意见", action: "查看记录", url: "#" },
  ];
}

export function getTaskTitle(payload = {}) {
  const scriptFirstLine = String(payload.script || "")
    .split("\n")
    .map((line) => line.trim())
    .find(Boolean);

  if (payload.referenceUrl) return "参考视频复刻";
  return scriptFirstLine ? `${scriptFirstLine.slice(0, 8)} · 口播复刻` : "新建口播复刻";
}
