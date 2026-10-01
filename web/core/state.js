(() => {
  function loadLocalJson(key, fallback) {
    try {
      const value = JSON.parse(localStorage.getItem(key) || 'null');
      return value && typeof value === 'object' ? value : fallback;
    } catch (_error) {
      return fallback;
    }
  }

  function saveLocalJson(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (_error) { /* optional */ }
  }

  function createStore(initialState = {}) {
    let snapshot = {...initialState};
    const listeners = new Set();
    return Object.freeze({
      get: () => snapshot,
      set(update) {
        const patch = typeof update === 'function' ? update(snapshot) : update;
        if (!patch || typeof patch !== 'object') return snapshot;
        snapshot = {...snapshot, ...patch};
        listeners.forEach(listener => listener(snapshot, patch));
        return snapshot;
      },
      subscribe(listener) {
        listeners.add(listener);
        return () => listeners.delete(listener);
      },
    });
  }

  window.PaperAtlasState = Object.freeze({createStore, loadLocalJson, saveLocalJson});
})();
