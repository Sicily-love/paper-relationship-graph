(() => {
  function prepareApiRequest(path, options = {}) {
    const method = String(options.method || 'GET').toUpperCase();
    let body = {};
    try { body = options.body ? JSON.parse(options.body) : {}; } catch (_error) { body = {}; }
    const prepared = {...options, method};
    const encode = value => encodeURIComponent(String(value || ''));
    if (path === '/api/state') return {path: '/api/v1/state', options: prepared};
    if (path === '/api/topics') return {path: '/api/v1/topics', options: prepared};
    if (path === '/api/logs') return {path: '/api/v1/logs', options: {...prepared, method: 'GET', body: undefined}};
    if (path === '/api/discover') return {path: '/api/v1/discovery-runs', options: prepared, awaitJob: true};
    if (path === '/api/candidates/action') return {path: `/api/v1/candidates/${encode(body.id)}/decision`, options: prepared, awaitJob: true};
    if (path === '/api/candidates/feedback') return {path: `/api/v1/candidates/${encode(body.id)}/feedback`, options: prepared};
    if (path === '/api/candidates/clear') return {path: '/api/v1/candidates', options: {...prepared, method: 'DELETE'}};
    if (path === '/api/classification/action') return {path: `/api/v1/classification-reviews/${encode(body.id)}/decision`, options: prepared, awaitJob: true};
    if (path === '/api/maintenance/rebuild') return {path: '/api/v1/maintenance-runs', options: prepared, awaitJob: true};
    if (path === '/api/diagnostics') return {path: '/api/v1/diagnostic-runs', options: prepared, awaitJob: true};
    if (path === '/api/graph/node/remove') return {path: `/api/v1/graph/nodes/${encode(body.id)}`, options: {...prepared, method: 'DELETE'}, awaitJob: true};
    if (path === '/api/papers/read-status') return {path: `/api/v1/papers/${encode(body.id)}/read-status`, options: {...prepared, method: 'PUT'}};
    if (path === '/api/tasks') {
      if (body.action === 'state') return {path: '/api/v1/tasks', options: {...prepared, method: 'GET', body: undefined}};
      if (body.action === 'run') return {path: `/api/v1/tasks/${encode(body.task_id)}/runs`, options: prepared, awaitJob: true};
      if (body.action === 'configure') return {path: '/api/v1/tasks', options: {...prepared, method: 'PUT'}};
    }
    if (path === '/api/backup') {
      if (body.action === 'restore') return {path: '/api/v1/backup-restores', options: prepared, awaitJob: true};
      return {path: '/api/v1/backups', options: prepared, awaitJob: true};
    }
    return {path, options};
  }

  function createApiClient({token = '', jobTimeoutAttempts = 1200} = {}) {
    const nativeRequests = new Map();

    window.__paperAtlasNativeResolve = (id, encodedPayload) => {
      const pending = nativeRequests.get(id);
      if (!pending) return;
      nativeRequests.delete(id);
      clearTimeout(pending.timeout);
      try {
        const bytes = Uint8Array.from(atob(encodedPayload), character => character.charCodeAt(0));
        const payload = JSON.parse(new TextDecoder().decode(bytes));
        if (payload.error) {
          const detail = typeof payload.error === 'string' ? payload.error : payload.error.message;
          pending.reject(new Error(detail || '本地任务运行失败'));
        } else {
          pending.resolve(payload.data !== undefined ? payload.data : payload);
        }
      } catch (_error) {
        pending.reject(new Error('应用返回的数据无法读取'));
      }
    };

    function nativeRequest(path, options) {
      return new Promise((resolve, reject) => {
        const id = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
        const timeout = setTimeout(() => {
          nativeRequests.delete(id);
          reject(new Error('应用操作超时，请稍后重试'));
        }, 370000);
        nativeRequests.set(id, {resolve, reject, timeout});
        try {
          window.webkit.messageHandlers.paperAtlas.postMessage({
            id, path, method: options.method || 'GET', headers: options.headers || {}, body: options.body || '',
          });
        } catch (_error) {
          clearTimeout(timeout);
          nativeRequests.delete(id);
          reject(new Error('应用管理功能未连接，请重新打开 Paper Atlas'));
        }
      });
    }

    async function send(path, options = {}) {
      if (window.webkit?.messageHandlers?.paperAtlas) return nativeRequest(path, options);
      if (window.location.protocol === 'file:') throw new Error('请使用 Paper Atlas.app 打开完整版本');
      let response;
      try {
        response = await fetch(path, {
          ...options,
          headers: {'Content-Type': 'application/json', ...(token ? {'X-Paper-Atlas-Token': token} : {}), ...(options.headers || {})},
        });
      } catch (_error) {
        throw new Error('应用管理功能未连接，请重新打开 Paper Atlas');
      }
      let payload = {};
      try { payload = await response.json(); } catch (_error) { /* handled below */ }
      if (!response.ok || payload.error) {
        const error = payload.error;
        throw new Error(typeof error === 'string' ? error : error?.message || '本地任务运行失败');
      }
      return payload.data !== undefined ? payload.data : payload;
    }

    async function waitForJob(jobId) {
      if (!jobId) return {};
      for (let attempt = 0; attempt < jobTimeoutAttempts; attempt += 1) {
        const record = await send(`/api/v1/jobs/${encodeURIComponent(jobId)}`, {method: 'GET'});
        if (record.status === 'succeeded') return record.result || {};
        if (['failed', 'cancelled', 'interrupted'].includes(record.status)) {
          throw new Error(record.error?.message || '任务未完成');
        }
        await new Promise(resolve => setTimeout(resolve, Math.min(2000, 250 + attempt * 25)));
      }
      throw new Error('任务等待超时，请到运行日志查看详情');
    }

    return Object.freeze({
      async request(path, options = {}) {
        const prepared = prepareApiRequest(path, options);
        const payload = await send(prepared.path, prepared.options);
        if (!prepared.awaitJob || !payload?.job) return payload;
        return waitForJob(payload.job.id);
      },
      send,
    });
  }

  window.PaperAtlasRuntime = Object.freeze({createApiClient, prepareApiRequest});
})();
