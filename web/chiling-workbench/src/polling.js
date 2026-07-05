const defaultTimers = {
  clearInterval: (timerId) => globalThis.clearInterval(timerId),
  setInterval: (callback, delay) => globalThis.setInterval(callback, delay),
};

export function createPollingController({ state, refreshCurrentTask, timers = defaultTimers }) {
  function stopTaskPolling() {
    if (!state.taskPoller) return;
    timers.clearInterval(state.taskPoller);
    state.taskPoller = null;
  }

  function startTaskPolling({ navigateOnComplete = false } = {}) {
    stopTaskPolling();
    refreshCurrentTask({ navigateOnComplete });
    state.taskPoller = timers.setInterval(() => {
      refreshCurrentTask({ navigateOnComplete: navigateOnComplete && state.page === "generating" });
    }, 1000);
  }

  return {
    startTaskPolling,
    stopTaskPolling,
  };
}
