export function createDefaultForm({ referenceFrame, portraitFrame }) {
  return {
    referenceUrl: "",
    duration: 15,
    resolution: "480p",
    count: 1,
    subtitleStyle: "short",
    referenceName: "参考视频已就绪",
    portraitName: "肖像图已就绪",
    referencePreview: referenceFrame,
    portraitPreview: portraitFrame,
    analysisSummary: "等待参考解析后生成摘要。",
    script:
      "在这些案子上面\n我积累了充足的实战经验\n如果你身边刚好缺一位靠谱律师朋友\n不妨留个关注",
  };
}

export function createInitialState({ storage, referenceFrame, portraitFrame }) {
  return {
    loggedIn: false,
    page: "login",
    progress: 0,
    taskPoller: null,
    currentTaskId: storage.getItem("chiling-workbench.current-task-id") || "",
    currentTask: null,
    deliverables: [],
    tasks: [],
    queueEntries: [],
    productionRequests: [],
    productionServiceStatus: null,
    productionServiceConfiguration: null,
    productionAuditLog: null,
    taskDetail: null,
    detailDrawerOpen: false,
    operationPanel: null,
    reviewDraft: null,
    productionPrep: null,
    generationPhrase: "",
    productionRequestPhrase: "",
    isSubmitting: false,
    form: createDefaultForm({ referenceFrame, portraitFrame }),
  };
}
