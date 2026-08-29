(() => {
  const graph = window.PAPER_GRAPH;
  let discovery = window.PAPER_DISCOVERY || {metadata: {}, topics: [], candidates: []};
  const releases = window.PAPER_RELEASES || {current_version: '', releases: []};
  if (!graph) {
    console.error('未找到 web/data/graph-data.js，请先运行 make build。');
    return;
  }

  const svg = document.getElementById('graph-svg');
  const edgeLayer = document.getElementById('edge-layer');
  const nodeLayer = document.getElementById('node-layer');
  const timelineGrid = document.getElementById('timeline-grid');
  const tooltip = document.getElementById('tooltip');
  const metricPapers = document.getElementById('metric-papers');
  const metricCitations = document.getElementById('metric-citations');
  const metricCategories = document.getElementById('metric-categories');
  const metricYears = document.getElementById('metric-years');
  const paperDetail = document.getElementById('paper-detail');
  const detailBackdrop = document.getElementById('detail-backdrop');
  const detailClose = document.getElementById('detail-close');
  const detailContent = document.getElementById('detail-content');
  const detailTitle = document.getElementById('detail-title');
  const detailMeta = document.getElementById('detail-meta');
  const detailAuthors = document.getElementById('detail-authors');
  const detailAbstract = document.getElementById('detail-abstract');
  const detailPdf = document.getElementById('detail-pdf');
  const removeGraphNodeButton = document.getElementById('remove-graph-node');
  const detailMainBadge = document.getElementById('detail-main-badge');
  const paperSearch = document.getElementById('paper-search');
  const clearSearch = document.getElementById('clear-search');
  const candidateSourceFilter = document.getElementById('candidate-source-filter');
  const candidateCategoryFilter = document.getElementById('candidate-category-filter');
  const discoveryList = document.getElementById('discovery-list');
  const discoveryEmpty = document.getElementById('discovery-empty');
  const discoveryCount = document.getElementById('discovery-count');
  const discoveryUpdated = document.getElementById('discovery-updated');
  const manageTopics = document.getElementById('manage-topics');
  const runDiscoveryButton = document.getElementById('run-discovery');
  const runHighlyCitedButton = document.getElementById('run-highly-cited');
  const runSharedDiscoveryButton = document.getElementById('run-shared-discovery');
  const runSelectedDiscoveryButton = document.getElementById('run-selected-discovery');
  const discoverySelectionSummary = document.getElementById('discovery-selection-summary');
  const discoveryTopicOptions = document.getElementById('discovery-topic-options');
  const clearCandidatesButton = document.getElementById('clear-candidates');
  const highlyCitedMinimum = document.getElementById('highly-cited-minimum');
  const sharedReferenceMinimum = document.getElementById('shared-reference-minimum');
  const topicsDialog = document.getElementById('topics-dialog');
  const topicsBackdrop = document.getElementById('topics-backdrop');
  const topicsClose = document.getElementById('topics-close');
  const topicTemplatesList = document.getElementById('topic-templates-list');
  const topicsList = document.getElementById('topics-list');
  const addTopicButton = document.getElementById('add-topic');
  const saveTopicsButton = document.getElementById('save-topics');
  const saveAndDiscoverButton = document.getElementById('save-and-discover');
  const appToast = document.getElementById('app-toast');
  const serviceNotice = document.getElementById('service-notice');
  const discoveryProgress = document.getElementById('discovery-progress');
  const discoveryProgressTitle = document.getElementById('discovery-progress-title');
  const discoveryProgressMeta = document.getElementById('discovery-progress-meta');
  const discoveryResult = document.getElementById('discovery-result');
  const discoveryResultTitle = document.getElementById('discovery-result-title');
  const discoveryResultMeta = document.getElementById('discovery-result-meta');
  const relationLegend = document.getElementById('relation-legend');
  const relationPaperTitle = document.getElementById('relation-paper-title');
  const legendOutgoingCount = document.getElementById('legend-outgoing-count');
  const legendIncomingCount = document.getElementById('legend-incoming-count');
  const healthPanel = document.getElementById('health-panel');
  const healthSummary = document.getElementById('health-summary');
  const healthIssues = document.getElementById('health-issues');
  const classificationReviewPanel = document.getElementById('classification-review-panel');
  const classificationReviewSummary = document.getElementById('classification-review-summary');
  const classificationReviewCount = document.getElementById('classification-review-count');
  const classificationReviewList = document.getElementById('classification-review-list');
  const discoveryDebugOutput = document.getElementById('discovery-debug-output');
  const rebuildGraphButton = document.getElementById('rebuild-graph');
  const runDiagnosticsButton = document.getElementById('run-diagnostics');
  const diagnosticsPanel = document.getElementById('diagnostics-panel');
  const diagnosticsSummary = document.getElementById('diagnostics-summary');
  const diagnosticsMetrics = document.getElementById('diagnostics-metrics');
  const diagnosticsChecks = document.getElementById('diagnostics-checks');
  const diagnosticsActions = document.getElementById('diagnostics-actions');
  const copyDiagnosticsButton = document.getElementById('copy-diagnostics');
  const openRuntimeLogsButton = document.getElementById('open-runtime-logs');
  const logsDialog = document.getElementById('logs-dialog');
  const logsBackdrop = document.getElementById('logs-backdrop');
  const logsClose = document.getElementById('logs-close');
  const logsTabs = document.getElementById('logs-tabs');
  const logsOutput = document.getElementById('logs-output');
  const refreshLogsButton = document.getElementById('refresh-logs');
  const copyLogButton = document.getElementById('copy-log');
  const taskList = document.getElementById('task-list');
  const saveTasksButton = document.getElementById('save-tasks');
  const exportBackupButton = document.getElementById('export-backup');
  const importBackupButton = document.getElementById('import-backup');
  const backupFile = document.getElementById('backup-file');
  const candidatePreview = document.getElementById('candidate-preview');
  const candidatePreviewEmpty = document.getElementById('candidate-preview-empty');
  const navDiscoveryCount = document.getElementById('nav-discovery-count');
  const navHealthDot = document.getElementById('nav-health-dot');
  const versionHistoryButton = document.getElementById('version-history');
  const releaseNotesDialog = document.getElementById('release-notes-dialog');
  const releaseNotesBackdrop = document.getElementById('release-notes-backdrop');
  const releaseNotesClose = document.getElementById('release-notes-close');
  const releaseNotesList = document.getElementById('release-notes-list');
  const resetViewButton = document.getElementById('reset-view');
  const resetViewLabel = resetViewButton.querySelector('.reset-label');
  const graphSearchResults = document.getElementById('graph-search-results');
  const graphSearchCount = document.getElementById('graph-search-count');
  const graphSearchPosition = document.getElementById('graph-search-position');
  const graphSearchPrev = document.getElementById('graph-search-prev');
  const graphSearchNext = document.getElementById('graph-search-next');
  const graphWorkspace = document.getElementById('graph-workspace');
  const graphInspector = document.getElementById('graph-inspector');
  const graphInspectorEmpty = document.getElementById('graph-inspector-empty');
  const graphInspectorContent = document.getElementById('graph-inspector-content');
  const graphInspectorTitle = document.getElementById('graph-inspector-title');
  const graphInspectorYear = document.getElementById('graph-inspector-year');
  const graphInspectorCategory = document.getElementById('graph-inspector-category');
  const graphInspectorAuthors = document.getElementById('graph-inspector-authors');
  const graphInspectorPreview = document.getElementById('graph-inspector-preview');
  const graphInspectorOpenPdf = document.getElementById('graph-inspector-open-pdf');
  const inspectorOutgoingCount = document.getElementById('inspector-outgoing-count');
  const inspectorIncomingCount = document.getElementById('inspector-incoming-count');
  const inspectorOutgoingList = document.getElementById('inspector-outgoing-list');
  const inspectorIncomingList = document.getElementById('inspector-incoming-list');
  const toggleGraphInspector = document.getElementById('toggle-graph-inspector');
  const graphResizer = document.getElementById('graph-resizer');
  const reviewWorkspace = document.getElementById('review-workspace');
  const reviewResizer = document.getElementById('review-resizer');
  const sidebarCollapse = document.getElementById('sidebar-collapse');
  const openDiscoverySheetButton = document.getElementById('open-discovery-sheet');
  const discoverySheet = document.getElementById('discovery-sheet');
  const discoverySheetBackdrop = document.getElementById('discovery-sheet-backdrop');
  const discoverySheetClose = document.getElementById('discovery-sheet-close');
  const discoveryManageTopics = document.getElementById('discovery-manage-topics');
  const automationTopicSummary = document.getElementById('automation-topic-summary');
  const batchToolbar = document.getElementById('batch-toolbar');
  const batchCount = document.getElementById('batch-count');
  const batchSelectAll = document.getElementById('batch-select-all');
  const batchDismiss = document.getElementById('batch-dismiss');
  const batchClear = document.getElementById('batch-clear');
  const activityTimeline = document.getElementById('activity-timeline');
  const activityCenter = document.getElementById('activity-center');
  const activityCenterTitle = document.getElementById('activity-center-title');
  const activityCenterDetail = document.getElementById('activity-center-detail');
  const activityCenterClose = document.getElementById('activity-center-close');
  const commandBackdrop = document.getElementById('command-backdrop');
  const commandPalette = document.getElementById('command-palette');
  const commandSearch = document.getElementById('command-search');
  const commandResults = document.getElementById('command-results');
  const groupToolbarActions = (view, ids, className = 'toolbar-actions') => {
    const toolbar = document.querySelector(`[data-view-panel="${view}"] .page-toolbar`);
    if (!toolbar) return;
    const actions = document.createElement('div');
    actions.className = className;
    ids.map(id => document.getElementById(id)).filter(Boolean).forEach(control => {
      if (control.parentElement?.classList.contains('toolbar-select')) actions.appendChild(control.parentElement);
      else actions.appendChild(control);
    });
    toolbar.appendChild(actions);
  };
  groupToolbarActions('automation', ['manage-topics', 'save-tasks']);
  groupToolbarActions('system', ['run-diagnostics', 'open-runtime-logs', 'version-history']);
  const discoveryToolbar = document.querySelector('[data-view-panel="discovery"] .page-toolbar');
  if (discoveryToolbar) {
    const reviewActions = document.createElement('div');
    reviewActions.className = 'toolbar-actions review-toolbar-actions';
    clearCandidatesButton.textContent = '清空审核';
    clearCandidatesButton.title = '移出当前全部待审核候选';
    [candidateSourceFilter, candidateCategoryFilter, openDiscoverySheetButton, clearCandidatesButton]
      .filter(Boolean)
      .forEach(control => {
        const parent = control.parentElement?.classList.contains('toolbar-select')
          ? control.parentElement
          : control;
        reviewActions.appendChild(parent);
      });
    discoveryToolbar.appendChild(reviewActions);
  }
  const viewButtons = [...document.querySelectorAll('[data-view]')];
  const viewPanels = [...document.querySelectorAll('[data-view-panel]')];
  const ns = 'http://www.w3.org/2000/svg';

  const nodesById = Object.fromEntries(graph.nodes.map(node => [node.id, node]));
  const allEdges = graph.edges.citation.map((edge, index) => ({...edge, type: 'citation', id: `citation-${index}`}));
  const yearMin = graph.metadata.year_min;
  const yearMax = graph.metadata.year_max;
  const yearSpan = Math.max(1, yearMax - yearMin);
  const NODE_RADIUS_MIN = 5.5;
  const NODE_RADIUS_MAX = 15;
  const TIMELINE_LEFT = 205;
  const TIMELINE_RIGHT = 905;
  const TIMELINE_TOP = 54;
  const TIMELINE_BOTTOM = 646;
  const maxCitationCount = Math.max(1, ...graph.nodes.map(node => node.citation_count));
  const TOPIC_TEMPLATES = [
    {
      id: 'category-01-model-architecture',
      label: '模型架构与基础组件',
      keywords: ['transformer architecture', 'normalization', 'positional encoding', 'residual connection'],
    },
    {
      id: 'category-02-training-optimization',
      label: '训练方法与优化器',
      keywords: ['optimizer', 'weight decay', 'training method', 'distillation', 'stochastic optimization'],
    },
    {
      id: 'category-02-attention-context',
      label: '注意力机制与长上下文',
      keywords: ['attention', 'long context', 'KV cache', 'FlashAttention', 'sparse attention'],
    },
    {
      id: 'category-03-moe-sparse',
      label: 'MoE 与稀疏模型',
      keywords: ['mixture of experts', 'MoE', 'expert routing', 'expert parallel'],
    },
    {
      id: 'category-04-quantization',
      label: '量化与低精度计算',
      keywords: ['quantization', 'low precision', 'FP4', 'INT4', 'mixed precision'],
    },
    {
      id: 'category-05-distributed-data',
      label: '分布式训练与数据基础设施',
      keywords: ['distributed training', 'model parallel', 'pipeline parallel', 'FSDP', 'data pipeline'],
    },
    {
      id: 'category-06-gpu-performance',
      aliases: ['gpu-kernel-optimization'],
      label: 'GPU 内核、编译器与性能工程',
      keywords: ['GPU kernel', 'tensor compiler', 'Triton kernel', 'CUDA optimization', 'kernel fusion'],
    },
    {
      id: 'category-07-kernel-agents',
      label: 'GPU 内核智能体与自动调优',
      keywords: ['GPU kernel agent', 'CUDA agent', 'LLM kernel optimization', 'automatic kernel generation'],
    },
    {
      id: 'category-08-general-agents',
      label: '通用智能体与自主发现',
      keywords: ['AI agent', 'research agent', 'tool use', 'self-play', 'open-ended discovery'],
    },
    {
      id: 'category-09-generative-video',
      label: '生成模型与视频系统',
      keywords: ['video generation', 'diffusion transformer', 'video inference', 'frame interpolation', 'text-to-video'],
    },
    {
      id: 'category-10-model-reports',
      label: '大模型技术报告与推理训练',
      keywords: ['reasoning model', 'technical report', 'reinforcement learning reasoning', 'test-time scaling', 'foundation model'],
    },
  ].map(template => {
    const normalizedLabel = value => String(value || '').toLowerCase().replace(/[\s_、，,]+/g, '');
    const category = graph.categories.find(item =>
      normalizedLabel(item.label) === normalizedLabel(template.label),
    )?.id;
    return {enabled: true, exclude_keywords: [], max_results: 5, category, ...template};
  });

  const displayCategoryLabel = label => String(label || '').replace(/_/g, ' · ');

  let selectedNode = null;
  let searchTerm = '';
  let discoverySource = 'all';
  let discoveryCategory = 'all';
  const selectedDiscoveryModes = new Set(['arxiv']);
  const selectedDiscoveryTopicIds = new Set();
  let graphSearchIndex = 0;
  let selectedCandidateId = null;
  let activeView = 'graph';
  let apiTopics = (discovery.topics || []).map(topic => ({enabled: true, max_results: 10, ...topic}));
  let reviewCategories = graph.categories.map(category => ({id: category.id, label: displayCategoryLabel(category.label)}));
  let toastTimer = null;
  let discoveryBusyTimer = null;
  let discoveryHighlightTimer = null;
  let discoveryBusyStarted = 0;
  let highlightedCandidateIds = new Set();
  let apiHealth = null;
  let apiTasks = {supported: false, tasks: []};
  let apiGraphRevision = null;
  let apiStatePollBusy = false;
  let runtimeLogs = [];
  let activeLogId = '';
  let visibleCandidateIds = [];
  let selectedCandidateIds = new Set();
  let activityEvents = loadLocalJson('paper-atlas-activity', []);
  let commandItems = [];
  let activeCommandIndex = 0;
  let detailReturnFocus = null;
  let discoverySheetReturnFocus = null;
  let topicsReturnFocus = null;
  let logsReturnFocus = null;
  let releaseNotesReturnFocus = null;
  const candidateCategoryOverrides = new Map(Object.entries(loadLocalJson('paper-atlas-category-overrides', {})));
  const topicTemplateButtons = new Map();
  const nativeRequests = new Map();
  const apiToken = document.querySelector('meta[name="paper-atlas-token"]')?.content || '';

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

  function nativeApiRequest(path, options) {
    return new Promise((resolve, reject) => {
      const id = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
      const timeout = setTimeout(() => {
        nativeRequests.delete(id);
        reject(new Error('应用操作超时，请稍后重试'));
      }, 370000);
      nativeRequests.set(id, {resolve, reject, timeout});
      try {
        window.webkit.messageHandlers.paperAtlas.postMessage({
          id,
          path,
          method: options.method || 'GET',
          headers: options.headers || {},
          body: options.body || '',
        });
      } catch (_error) {
        clearTimeout(timeout);
        nativeRequests.delete(id);
        reject(new Error('应用管理功能未连接，请重新打开 Paper Atlas'));
      }
    });
  }

  function normalizeSearch(value) {
    return String(value || '').toLocaleLowerCase().replace(/\s+/g, ' ').trim();
  }

  // Map the score itself onto a continuous traffic-light palette.  Each
  // candidate receives one solid colour; the track no longer contains a
  // misleading left-to-right rainbow.
  function scoreColor(value) {
    const score = Math.max(0, Math.min(100, Number(value) || 0));
    const stops = [[0, [223, 91, 103]], [50, [239, 177, 61]], [100, [56, 184, 106]]];
    let lower = stops[0];
    let upper = stops[stops.length - 1];
    for (let index = 1; index < stops.length; index += 1) {
      if (score <= stops[index][0]) { upper = stops[index]; lower = stops[index - 1]; break; }
    }
    const ratio = (score - lower[0]) / Math.max(1, upper[0] - lower[0]);
    const rgb = lower[1].map((channel, index) => Math.round(channel + (upper[1][index] - channel) * ratio));
    return `rgb(${rgb.join(', ')})`;
  }

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

  function nodeMatchesSearch(node) {
    if (!searchTerm) return true;
    return normalizeSearch([node.title, node.authors, node.abstract, node.category, node.year].join(' ')).includes(searchTerm);
  }

  metricPapers.textContent = String(graph.metadata.unique_papers);
  metricCitations.textContent = String(graph.metadata.citation_edges);
  metricCategories.textContent = String(graph.categories.length);
  const fullYearSpan = `${yearMin}–${yearMax}`;
  const shortYear = year => String(year).slice(-2).padStart(2, '0');
  metricYears.textContent = `${shortYear(yearMin)}–${shortYear(yearMax)}`;
  metricYears.title = fullYearSpan;
  metricYears.setAttribute('aria-label', fullYearSpan);
  function activateView(view, remember = true) {
    if (!viewPanels.some(panel => panel.dataset.viewPanel === view)) view = 'graph';
    activeView = view;
    viewButtons.forEach(button => {
      const active = button.dataset.view === view;
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', String(active));
    });
    viewPanels.forEach(panel => {
      const active = panel.dataset.viewPanel === view;
      panel.hidden = !active;
      panel.classList.toggle('active', active);
    });
    if (remember) {
      try { sessionStorage.setItem('paper-atlas-view', view); } catch (_error) { /* optional */ }
    }
    if (view === 'graph') requestAnimationFrame(render);
  }

  const grouped = graph.nodes.reduce((result, node) => {
    (result[node.category] ??= []).push(node);
    return result;
  }, {});

  function timelineX(year) {
    return TIMELINE_LEFT + (((year ?? yearMin) - yearMin) / yearSpan) * (TIMELINE_RIGHT - TIMELINE_LEFT);
  }

  function createSvgElement(tag, attributes = {}) {
    const element = document.createElementNS(ns, tag);
    Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
    return element;
  }

  function buildTimelineGrid() {
    const laneHeight = (TIMELINE_BOTTOM - TIMELINE_TOP) / graph.categories.length;
    timelineGrid.replaceChildren();
    graph.categories.forEach((category, index) => {
      const y = TIMELINE_TOP + index * laneHeight;
      const fill = createSvgElement('rect', {
        x: 8,
        y: y.toFixed(1),
        width: 944,
        height: laneHeight.toFixed(1),
        class: `lane-fill${index % 2 ? ' alternate' : ''}`,
      });
      const rule = createSvgElement('line', {
        x1: 8,
        y1: (y + laneHeight).toFixed(1),
        x2: 952,
        y2: (y + laneHeight).toFixed(1),
        class: 'lane-rule',
      });
      const label = createSvgElement('text', {
        x: 18,
        y: (y + laneHeight / 2 + 4).toFixed(1),
        class: 'lane-label',
      });
      label.textContent = displayCategoryLabel(category.label);
      timelineGrid.append(fill, rule, label);
    });

    for (let year = yearMin; year <= yearMax; year += 1) {
      const x = timelineX(year);
      const rule = createSvgElement('line', {
        x1: x.toFixed(1),
        y1: 35,
        x2: x.toFixed(1),
        y2: TIMELINE_BOTTOM,
        class: 'year-rule',
      });
      const label = createSvgElement('text', {
        x: x.toFixed(1),
        y: 25,
        class: 'year-label',
      });
      label.textContent = shortYear(year);
      timelineGrid.append(rule, label);
    }
  }

  function assignTimelinePositions() {
    const laneHeight = (TIMELINE_BOTTOM - TIMELINE_TOP) / graph.categories.length;
    graph.categories.forEach((category, categoryIndex) => {
      const nodes = [...(grouped[category.id] || [])].sort((a, b) =>
        (a.year ?? yearMin) - (b.year ?? yearMin)
        || b.citation_count - a.citation_count
        || a.title.localeCompare(b.title));
      if (!nodes.length) return;
      const centerY = TIMELINE_TOP + (categoryIndex + 0.5) * laneHeight;
      const cumulativeSpacing = [0];
      for (let index = 1; index < nodes.length; index += 1) {
        cumulativeSpacing[index] = cumulativeSpacing[index - 1]
          + nodes[index - 1].hitRadius + nodes[index].hitRadius + 3;
      }

      // Transform x positions by the required node spacing, then use pooled
      // adjacent violators to find the closest monotonic timeline. This keeps
      // chronological order while moving dense same-year groups only as much
      // as needed to prevent overlap.
      const blocks = [];
      nodes.forEach((node, index) => {
        blocks.push({start: index, end: index, weight: 1, mean: timelineX(node.year) - cumulativeSpacing[index]});
        while (
          blocks.length > 1
          && blocks[blocks.length - 2].mean > blocks[blocks.length - 1].mean
        ) {
          const right = blocks.pop();
          const left = blocks.pop();
          const weight = left.weight + right.weight;
          blocks.push({
            start: left.start,
            end: right.end,
            weight,
            mean: (left.mean * left.weight + right.mean * right.weight) / weight,
          });
        }
      });
      const offsets = new Array(nodes.length);
      blocks.forEach(block => {
        for (let index = block.start; index <= block.end; index += 1) offsets[index] = block.mean;
      });
      const leftBound = TIMELINE_LEFT - 25;
      const rightBound = TIMELINE_RIGHT + 10;
      const minimumOffset = leftBound;
      const maximumOffset = rightBound - cumulativeSpacing[cumulativeSpacing.length - 1];
      const boundedOffset = value => Math.max(minimumOffset, Math.min(maximumOffset, value));

      const yearCounts = new Map();
      nodes.forEach((node, index) => {
        const year = node.year ?? yearMin;
        const yearIndex = yearCounts.get(year) || 0;
        yearCounts.set(year, yearIndex + 1);
        const verticalRoom = Math.max(0, laneHeight / 2 - node.hitRadius - 3);
        const stagger = [0, -1, 1, -.5, .5][yearIndex % 5];
        node.timeline = {
          x: boundedOffset(offsets[index]) + cumulativeSpacing[index],
          y: centerY + stagger * verticalRoom,
        };
      });
    });
  }

  buildTimelineGrid();
  graph.nodes.forEach(node => {
    node.radius = NODE_RADIUS_MIN + Math.sqrt(node.citation_count / maxCitationCount) * (NODE_RADIUS_MAX - NODE_RADIUS_MIN);
    node.hitRadius = Math.max(8, node.radius + 2);
  });
  assignTimelinePositions();

  graph.categories.forEach((category, categoryIndex) => {
    const group = [...grouped[category.id]].sort((a, b) => ((a.year ?? yearMin) - (b.year ?? yearMin)) || a.title.localeCompare(b.title));
    group.forEach(node => {
      const groupElement = document.createElementNS(ns, 'g');
      groupElement.setAttribute('class', 'node');
      groupElement.dataset.node = node.id;
      groupElement.dataset.category = node.category;
      groupElement.dataset.year = String(node.year ?? yearMin);
      groupElement.setAttribute('role', 'button');
      groupElement.setAttribute('tabindex', '0');
      groupElement.setAttribute('aria-label', `${node.title}，${node.year ?? '年份未知'}，被库内引用 ${node.citation_count} 次。单击查看引用关系，按 Enter 或空格快速预览`);

      const hitArea = document.createElementNS(ns, 'circle');
      hitArea.setAttribute('class', 'node-hit');
      hitArea.setAttribute('r', String(node.hitRadius));
      groupElement.appendChild(hitArea);

      const mark = document.createElementNS(ns, 'circle');
      mark.setAttribute('class', 'node-mark');
      mark.setAttribute('r', node.radius.toFixed(2));
      mark.style.fill = `var(--cat-${categoryIndex})`;
      groupElement.appendChild(mark);

      const outgoingStem = document.createElementNS(ns, 'line');
      outgoingStem.setAttribute('class', 'node-port-stem outgoing-port-stem');
      outgoingStem.setAttribute('x1', String(-node.radius * 0.82));
      outgoingStem.setAttribute('y1', String(node.radius * 0.55));
      outgoingStem.setAttribute('x2', String(-(node.radius + 7)));
      outgoingStem.setAttribute('y2', '6');
      groupElement.appendChild(outgoingStem);

      const incomingStem = document.createElementNS(ns, 'line');
      incomingStem.setAttribute('class', 'node-port-stem incoming-port-stem');
      incomingStem.setAttribute('x1', String(node.radius * 0.82));
      incomingStem.setAttribute('y1', String(-node.radius * 0.55));
      incomingStem.setAttribute('x2', String(node.radius + 7));
      incomingStem.setAttribute('y2', '-6');
      groupElement.appendChild(incomingStem);

      const incomingPort = document.createElementNS(ns, 'circle');
      incomingPort.setAttribute('class', 'node-port incoming-port');
      incomingPort.setAttribute('cx', String(node.radius + 7));
      incomingPort.setAttribute('cy', '-6');
      incomingPort.setAttribute('r', '3.6');
      groupElement.appendChild(incomingPort);

      const outgoingPort = document.createElementNS(ns, 'circle');
      outgoingPort.setAttribute('class', 'node-port outgoing-port');
      outgoingPort.setAttribute('cx', String(-(node.radius + 7)));
      outgoingPort.setAttribute('cy', '6');
      outgoingPort.setAttribute('r', '3.6');
      groupElement.appendChild(outgoingPort);

      const label = document.createElementNS(ns, 'text');
      label.setAttribute('x', '15');
      label.setAttribute('y', '4');
      label.textContent = node.label;
      label.style.display = 'none';
      groupElement.appendChild(label);

      groupElement.addEventListener('pointerenter', () => showTooltip(node));
      groupElement.addEventListener('pointerleave', hideTooltip);
      groupElement.addEventListener('click', event => {
        event.stopPropagation();
        selectNode(node.id);
      });
      groupElement.addEventListener('keydown', event => {
        if (event.key === 'Enter') {
          event.preventDefault();
          openNodeDetail(node.id);
        } else if (event.key === ' ') {
          event.preventDefault();
          selectNode(node.id);
        }
      });

      node.element = groupElement;
      node.labelElement = label;
      node.incomingPortElement = incomingPort;
      node.outgoingPortElement = outgoingPort;
      node.incomingStemElement = incomingStem;
      node.outgoingStemElement = outgoingStem;
      nodeLayer.appendChild(groupElement);
    });
  });

  allEdges.forEach(edge => {
    const path = document.createElementNS(ns, 'path');
    path.setAttribute('class', `edge ${edge.type}`);
    edge.element = path;
    edgeLayer.appendChild(path);
  });

  function connectedNodes(nodeId) {
    const connected = new Set([nodeId]);
    allEdges.forEach(edge => {
      if (edge.source === nodeId) connected.add(edge.target);
      if (edge.target === nodeId) connected.add(edge.source);
    });
    return connected;
  }

  function shouldFocusEdge(edge) {
    return Boolean(selectedNode && (edge.source === selectedNode || edge.target === selectedNode));
  }

  function render() {
    graph.nodes.forEach(node => {
      node.position = {
        x: node.timeline.x,
        y: node.timeline.y,
        z: 0,
        scale: node.id === selectedNode ? 1.12 : 1,
      };
    });

    const outgoingEdges = selectedNode ? allEdges.filter(edge => edge.source === selectedNode) : [];
    const incomingEdges = selectedNode ? allEdges.filter(edge => edge.target === selectedNode) : [];
    const outgoingOrder = new Map(outgoingEdges.map((edge, index) => [edge, index]));
    const incomingOrder = new Map(incomingEdges.map((edge, index) => [edge, index]));
    const selected = selectedNode ? nodesById[selectedNode] : null;
    const spreadOffset = (index, count) => (index - (count - 1) / 2) * Math.min(8, 44 / Math.max(1, count - 1));
    const boundaryPoint = (node, toward) => {
      const dx = toward.x - node.position.x;
      const dy = toward.y - node.position.y;
      const distance = Math.hypot(dx, dy) || 1;
      const radius = node.radius * node.position.scale + 1.2;
      return {
        x: node.position.x + dx / distance * radius,
        y: node.position.y + dy / distance * radius,
      };
    };

    allEdges.forEach(edge => {
      const sourceNode = nodesById[edge.source];
      const targetNode = nodesById[edge.target];
      const focused = shouldFocusEdge(edge);
      edge.element.classList.toggle('focused', focused);
      edge.element.classList.toggle('outgoing', Boolean(selectedNode && edge.source === selectedNode));
      edge.element.classList.toggle('incoming', Boolean(selectedNode && edge.target === selectedNode));
      const searchMatch = !searchTerm || (nodeMatchesSearch(sourceNode) && nodeMatchesSearch(targetNode));
      const visible = focused;
      edge.element.style.display = visible && searchMatch ? '' : 'none';
      if (!visible) return;

      let start;
      let end;
      let direction;
      if (edge.source === selectedNode) {
        const fan = spreadOffset(outgoingOrder.get(edge), outgoingEdges.length);
        start = {
          x: selected.position.x - (selected.radius + 7) * selected.position.scale,
          y: selected.position.y + 6 * selected.position.scale,
        };
        end = boundaryPoint(targetNode, start);
        direction = {fan, polarity: 1};
      } else {
        const fan = spreadOffset(incomingOrder.get(edge), incomingEdges.length);
        end = {
          x: selected.position.x + (selected.radius + 7) * selected.position.scale,
          y: selected.position.y - 6 * selected.position.scale,
        };
        start = boundaryPoint(sourceNode, end);
        direction = {fan, polarity: -1};
      }
      const dx = end.x - start.x;
      const dy = end.y - start.y;
      const distance = Math.hypot(dx, dy) || 1;
      const unitX = dx / distance;
      const unitY = dy / distance;
      const normalX = -unitY;
      const normalY = unitX;
      const handle = Math.min(88, Math.max(28, distance * 0.32));
      const baseBend = Math.min(34, Math.max(10, distance * 0.09)) * direction.polarity;
      const bend = baseBend + direction.fan;
      const control1 = {
        x: start.x + unitX * handle + normalX * bend,
        y: start.y + unitY * handle + normalY * bend,
      };
      const control2 = {
        x: end.x - unitX * handle + normalX * bend,
        y: end.y - unitY * handle + normalY * bend,
      };
      edge.element.setAttribute(
        'd',
        `M ${start.x.toFixed(1)} ${start.y.toFixed(1)} C ${control1.x.toFixed(1)} ${control1.y.toFixed(1)}, ${control2.x.toFixed(1)} ${control2.y.toFixed(1)}, ${end.x.toFixed(1)} ${end.y.toFixed(1)}`,
      );
      edge.element.style.opacity = '1';
    });

    const neighborhood = selectedNode ? connectedNodes(selectedNode) : null;
    [...graph.nodes].sort((a, b) => a.position.z - b.position.z).forEach(node => {
      const referencedBySelected = Boolean(selectedNode && allEdges.some(edge => edge.source === selectedNode && edge.target === node.id));
      const citesSelected = Boolean(selectedNode && allEdges.some(edge => edge.source === node.id && edge.target === selectedNode));
      node.element.setAttribute(
        'transform',
        `translate(${node.position.x.toFixed(1)} ${node.position.y.toFixed(1)}) scale(${node.position.scale.toFixed(3)})`,
      );
      node.element.classList.toggle('selected', node.id === selectedNode);
      node.element.classList.toggle('referenced-by-selected', referencedBySelected);
      node.element.classList.toggle('cites-selected', citesSelected);
      const dimForNode = neighborhood && !neighborhood.has(node.id);
      const dimForSearch = !nodeMatchesSearch(node);
      node.element.classList.toggle('dimmed', Boolean(dimForNode || dimForSearch));
      node.element.classList.toggle('search-match', Boolean(searchTerm && !dimForSearch));
      const showLabel = node.id === selectedNode || (searchTerm && !dimForSearch);
      node.labelElement.style.display = showLabel ? '' : 'none';
      const alignLeft = node.position.x > (TIMELINE_LEFT + TIMELINE_RIGHT) / 2;
      node.labelElement.setAttribute('x', alignLeft ? '-15' : '15');
      node.labelElement.setAttribute('text-anchor', alignLeft ? 'end' : 'start');
      node.outgoingPortElement.style.display = node.id === selectedNode && outgoingEdges.length ? 'inline' : 'none';
      node.incomingPortElement.style.display = node.id === selectedNode && incomingEdges.length ? 'inline' : 'none';
      node.outgoingStemElement.style.display = node.id === selectedNode && outgoingEdges.length ? 'inline' : 'none';
      node.incomingStemElement.style.display = node.id === selectedNode && incomingEdges.length ? 'inline' : 'none';
      nodeLayer.appendChild(node.element);
    });

    if (selectedNode) {
      const node = nodesById[selectedNode];
      const outgoing = allEdges.filter(edge => edge.source === selectedNode).length;
      const incoming = allEdges.filter(edge => edge.target === selectedNode).length;
      relationLegend.hidden = false;
      relationPaperTitle.textContent = node.title;
      legendOutgoingCount.textContent = String(outgoing);
      legendIncomingCount.textContent = String(incoming);
    } else {
      relationLegend.hidden = true;
    }
    renderGraphSearchNavigator();
    renderGraphInspector();
  }

  function graphSearchMatches() {
    return searchTerm ? graph.nodes.filter(nodeMatchesSearch) : [];
  }

  function renderGraphSearchNavigator() {
    const matches = graphSearchMatches();
    graphSearchResults.hidden = !searchTerm;
    if (!searchTerm) return;
    graphSearchIndex = Math.max(0, Math.min(graphSearchIndex, Math.max(0, matches.length - 1)));
    graphSearchCount.textContent = `${matches.length} 个结果`;
    graphSearchPosition.textContent = matches.length ? `${graphSearchIndex + 1} / ${matches.length}` : '没有匹配';
    graphSearchPrev.disabled = matches.length < 2;
    graphSearchNext.disabled = matches.length < 2;
  }

  function stepGraphSearch(direction) {
    const matches = graphSearchMatches();
    if (!matches.length) return;
    graphSearchIndex = (graphSearchIndex + direction + matches.length) % matches.length;
    selectNode(matches[graphSearchIndex].id);
    matches[graphSearchIndex].element?.focus({preventScroll: true});
  }

  function inspectorRelationItem(node, edge) {
    if (!node) return null;
    const item = document.createElement('li');
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = `${node.year || '—'} · ${node.title}`;
    button.title = edge.evidence || '本地参考文献标题匹配';
    button.addEventListener('click', () => selectNode(node.id));
    item.appendChild(button);
    return item;
  }

  function renderGraphInspector() {
    const node = selectedNode ? nodesById[selectedNode] : null;
    graphInspectorEmpty.hidden = Boolean(node);
    graphInspectorContent.hidden = !node;
    if (!node) return;
    const outgoing = graph.edges.citation.filter(edge => edge.source === node.id);
    const incoming = graph.edges.citation.filter(edge => edge.target === node.id);
    graphInspectorTitle.textContent = node.title;
    graphInspectorYear.textContent = String(node.year || '年份未知');
    graphInspectorCategory.textContent = displayCategoryLabel(node.category.replace(/^\d+_/, ''));
    graphInspectorAuthors.textContent = node.authors || '作者信息未可靠提取';
    inspectorOutgoingCount.textContent = String(outgoing.length);
    inspectorIncomingCount.textContent = String(incoming.length);
    inspectorOutgoingList.replaceChildren(...outgoing.map(edge => inspectorRelationItem(nodesById[edge.target], edge)).filter(Boolean));
    inspectorIncomingList.replaceChildren(...incoming.map(edge => inspectorRelationItem(nodesById[edge.source], edge)).filter(Boolean));
    graphInspectorPreview.dataset.nodeId = node.id;
    graphInspectorOpenPdf.dataset.nodeId = node.id;
  }

  function candidateSourceLabel(source) {
    return source === 'shared_reference'
      ? '共同引用'
      : source === 'arxiv_topic'
        ? 'arXiv 最新'
        : source === 'highly_cited'
          ? '领域高被引'
          : source;
  }

  function makeExternalLink(label, href, className = '') {
    let safeUrl;
    try {
      safeUrl = new URL(href, window.location.href);
      if (!['http:', 'https:'].includes(safeUrl.protocol)) return null;
    } catch (_error) {
      return null;
    }
    const link = document.createElement('a');
    link.textContent = label;
    link.href = safeUrl.href;
    link.target = '_blank';
    link.rel = 'noopener';
    if (className) link.className = className;
    return link;
  }

  function showToast(message, tone = 'success') {
    if (toastTimer) clearTimeout(toastTimer);
    appToast.textContent = message;
    appToast.dataset.tone = tone;
    appToast.hidden = false;
    toastTimer = setTimeout(() => { appToast.hidden = true; }, 4200);
  }

  function activityNotice(title, detail = '') {
    activityCenterTitle.textContent = title;
    activityCenterDetail.textContent = detail;
    activityCenter.hidden = false;
  }

  function recordActivity(title, detail = '') {
    const event = {title, detail, timestamp: new Date().toISOString()};
    activityEvents = [event, ...activityEvents].slice(0, 40);
    saveLocalJson('paper-atlas-activity', activityEvents);
    renderActivityTimeline();
    activityNotice(title, detail);
  }

  function renderActivityTimeline() {
    if (!activityEvents.length) {
      const empty = document.createElement('p');
      empty.className = 'muted';
      empty.textContent = '活动将在任务运行后显示。';
      activityTimeline.replaceChildren(empty);
      return;
    }
    activityTimeline.replaceChildren(...activityEvents.map(event => {
      const article = document.createElement('article');
      article.className = 'activity-item';
      const time = document.createElement('time');
      const date = new Date(event.timestamp);
      time.textContent = Number.isNaN(date.valueOf()) ? '—' : date.toLocaleTimeString('zh-CN', {hour: '2-digit', minute: '2-digit'});
      const dot = document.createElement('i');
      const copy = document.createElement('div');
      const title = document.createElement('strong');
      title.textContent = event.title;
      const detail = document.createElement('span');
      detail.textContent = event.detail;
      copy.append(title, detail);
      article.append(time, dot, copy);
      return article;
    }));
  }

  function renderReleaseNotes() {
    releaseNotesList.replaceChildren(...(releases.releases || []).map(release => {
      const article = document.createElement('article');
      article.className = 'release-note';
      const version = document.createElement('div');
      version.className = 'release-note-version';
      const name = document.createElement('strong');
      name.textContent = `v${release.version}`;
      const date = document.createElement('time');
      date.textContent = release.date || '开发中';
      version.append(name, date);
      const changes = document.createElement('ul');
      (release.changes || []).forEach(change => {
        const item = document.createElement('li');
        item.textContent = change;
        changes.appendChild(item);
      });
      article.append(version, changes);
      return article;
    }));
  }

  function openReleaseNotes() {
    releaseNotesReturnFocus = document.activeElement;
    renderReleaseNotes();
    releaseNotesDialog.hidden = false;
    releaseNotesBackdrop.hidden = false;
    document.body.classList.add('topics-open');
    requestAnimationFrame(() => releaseNotesClose.focus({preventScroll: true}));
  }

  function closeReleaseNotes() {
    releaseNotesDialog.hidden = true;
    releaseNotesBackdrop.hidden = true;
    document.body.classList.remove('topics-open');
    (releaseNotesReturnFocus?.isConnected ? releaseNotesReturnFocus : versionHistoryButton)?.focus({preventScroll: true});
    releaseNotesReturnFocus = null;
  }

  function renderRuntimeLogs() {
    logsTabs.replaceChildren(...runtimeLogs.map(log => {
      const button = document.createElement('button');
      button.type = 'button';
      button.role = 'tab';
      button.textContent = log.label;
      button.className = 'logs-tab';
      button.classList.toggle('active', log.id === activeLogId);
      button.setAttribute('aria-selected', String(log.id === activeLogId));
      button.addEventListener('click', () => {
        activeLogId = log.id;
        renderRuntimeLogs();
      });
      return button;
    }));
    const active = runtimeLogs.find(log => log.id === activeLogId) || runtimeLogs[0];
    logsOutput.textContent = active?.content || '尚无日志';
  }

  async function loadRuntimeLogs() {
    refreshLogsButton.disabled = true;
    try {
      const result = await apiRequest('/api/logs', {method: 'POST', body: '{}'});
      runtimeLogs = result.logs || [];
      if (!runtimeLogs.some(log => log.id === activeLogId)) activeLogId = runtimeLogs[0]?.id || '';
      renderRuntimeLogs();
    } catch (error) {
      logsOutput.textContent = error.message;
      showToast(error.message, 'error');
    } finally {
      refreshLogsButton.disabled = false;
    }
  }

  function openRuntimeLogs() {
    logsReturnFocus = document.activeElement;
    logsDialog.hidden = false;
    logsBackdrop.hidden = false;
    document.body.classList.add('topics-open');
    logsOutput.textContent = '正在读取…';
    loadRuntimeLogs();
    requestAnimationFrame(() => logsClose.focus({preventScroll: true}));
  }

  function closeRuntimeLogs() {
    logsDialog.hidden = true;
    logsBackdrop.hidden = true;
    document.body.classList.remove('topics-open');
    (logsReturnFocus?.isConnected ? logsReturnFocus : openRuntimeLogsButton)?.focus({preventScroll: true});
    logsReturnFocus = null;
  }

  // Keep keyboard focus inside a sheet/Quick Look panel. WKWebView does not
  // provide the browser's native dialog focus management for custom dialogs.
  function installFocusTrap(dialog) {
    dialog.addEventListener('keydown', event => {
      if (event.key !== 'Tab' || dialog.hidden) return;
      const focusable = [...dialog.querySelectorAll(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      )].filter(element => element.getClientRects().length > 0);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus({preventScroll: true});
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus({preventScroll: true});
      }
    });
  }

  async function copyCurrentLog() {
    const text = logsOutput.textContent || '';
    try {
      await navigator.clipboard.writeText(text);
    } catch (_error) {
      const area = document.createElement('textarea');
      area.value = text;
      document.body.appendChild(area);
      area.select();
      document.execCommand('copy');
      area.remove();
    }
    showToast('当前日志已复制');
  }

  async function apiRequest(path, options = {}) {
    const prepared = prepareApiRequest(path, options);
    const payload = await sendApiRequest(prepared.path, prepared.options);
    if (!prepared.awaitJob || !payload?.job) return payload;
    return waitForApiJob(payload.job.id);
  }

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

  async function sendApiRequest(path, options = {}) {
    if (window.webkit?.messageHandlers?.paperAtlas) {
      return nativeApiRequest(path, options);
    }
    if (window.location.protocol === 'file:') {
      throw new Error('请使用 Paper Atlas.app 打开完整版本');
    }
    let response;
    try {
      response = await fetch(path, {
        ...options,
        headers: {'Content-Type': 'application/json', ...(apiToken ? {'X-Paper-Atlas-Token': apiToken} : {}), ...(options.headers || {})},
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

  async function waitForApiJob(jobId) {
    if (!jobId) return {};
    for (let attempt = 0; attempt < 1200; attempt += 1) {
      const record = await sendApiRequest(`/api/v1/jobs/${encodeURIComponent(jobId)}`, {method: 'GET'});
      if (record.status === 'succeeded') return record.result || {};
      if (['failed', 'cancelled', 'interrupted'].includes(record.status)) {
        throw new Error(record.error?.message || '任务未完成');
      }
      await new Promise(resolve => setTimeout(resolve, Math.min(2000, 250 + attempt * 25)));
    }
    throw new Error('任务等待超时，请到运行日志查看详情');
  }

  function suggestedCategory(candidate) {
    if (candidateCategoryOverrides.has(candidate.id)) return candidateCategoryOverrides.get(candidate.id);
    if (candidate.suggested_category) return candidate.suggested_category;
    const counts = {};
    (candidate.supporting_papers || []).forEach(paper => {
      if (paper.category) counts[paper.category] = (counts[paper.category] || 0) + 1;
    });
    return Object.entries(counts).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0]?.[0] || '';
  }

  function candidateCategory(candidate) {
    const id = suggestedCategory(candidate);
    const rank = reviewCategories.findIndex(category => category.id === id);
    const known = rank >= 0 ? reviewCategories[rank] : null;
    return {
      id: id || 'unclassified',
      label: known?.label || displayCategoryLabel(candidate.category_label) || '待确认类别',
      rank: rank >= 0 ? rank : reviewCategories.length,
    };
  }

  function renderCandidateCategoryFilter(candidates) {
    const counts = new Map();
    candidates.forEach(candidate => {
      const category = candidateCategory(candidate);
      counts.set(category.id, (counts.get(category.id) || 0) + 1);
    });
    const options = [];
    const all = document.createElement('option');
    all.value = 'all';
    all.textContent = `全部类别 · ${candidates.length}`;
    options.push(all);
    reviewCategories.forEach(category => {
      const count = counts.get(category.id) || 0;
      if (!count) return;
      const option = document.createElement('option');
      option.value = category.id;
      option.textContent = `${category.label} · ${count}`;
      options.push(option);
    });
    const unclassifiedCount = counts.get('unclassified') || 0;
    if (unclassifiedCount) {
      const option = document.createElement('option');
      option.value = 'unclassified';
      option.textContent = `待确认类别 · ${unclassifiedCount}`;
      options.push(option);
    }
    if (!options.some(option => option.value === discoveryCategory)) discoveryCategory = 'all';
    candidateCategoryFilter.replaceChildren(...options);
    candidateCategoryFilter.value = discoveryCategory;
  }

  function renderCandidateGroupHeader(category, count) {
    const header = document.createElement('div');
    header.className = 'candidate-group-header';
    header.dataset.categoryId = category.id;
    const label = document.createElement('strong');
    label.textContent = category.label;
    const total = document.createElement('span');
    total.textContent = String(count);
    header.append(label, total);
    if (category.id !== 'unclassified') {
      header.addEventListener('dragover', event => {
        event.preventDefault();
        header.classList.add('drop-target');
      });
      header.addEventListener('dragleave', () => header.classList.remove('drop-target'));
      header.addEventListener('drop', event => {
        event.preventDefault();
        header.classList.remove('drop-target');
        const candidateId = event.dataTransfer?.getData('text/paper-atlas-candidate');
        if (!candidateId) return;
        candidateCategoryOverrides.set(candidateId, category.id);
        saveLocalJson('paper-atlas-category-overrides', Object.fromEntries(candidateCategoryOverrides));
        showToast(`已将候选调整为“${category.label}”`);
        renderDiscovery();
      });
    }
    return header;
  }

  async function reviewCandidate(candidate, action, categorySelectControl, article, extras = {}) {
    const category = categorySelectControl.value;
    if (action === 'accept' && !category) {
      categorySelectControl.focus();
      showToast('请先为这篇论文选择类别', 'error');
      return;
    }
    const controls = article.querySelectorAll('button, select');
    controls.forEach(control => { control.disabled = true; });
    article.classList.add('is-busy');
    const startedAt = Date.now();
    const progress = document.createElement('p');
    progress.className = 'candidate-action-status';
    progress.setAttribute('role', 'status');
    progress.setAttribute('aria-live', 'polite');
    article.appendChild(progress);
    const acceptButton = article.querySelector('.candidate-action.primary-action');
    let commitDetected = false;
    let statusTimer = null;
    let commitPollTimer = null;

    const updateProgress = () => {
      const elapsed = Math.max(0, Math.floor((Date.now() - startedAt) / 1000));
      const minutes = String(Math.floor(elapsed / 60)).padStart(2, '0');
      const seconds = String(elapsed % 60).padStart(2, '0');
      if (action === 'accept' || action === 'replace') {
        progress.textContent = `正在下载、校验并更新图谱 · ${minutes}:${seconds}`;
        if (acceptButton && action === 'accept') acceptButton.textContent = '正在加入…';
      } else {
        progress.textContent = `正在移出候选 · ${minutes}:${seconds}`;
      }
    };

    const stopProgress = () => {
      clearInterval(statusTimer);
      clearInterval(commitPollTimer);
      statusTimer = null;
      commitPollTimer = null;
    };

    const detectCommittedDecision = async () => {
      if (commitDetected) return;
      try {
        const snapshotUrl = new URL('data/discovery.json', window.location.href);
        snapshotUrl.searchParams.set('review', String(Date.now()));
        const response = await fetch(snapshotUrl.href, {cache: 'no-store'});
        if (!response.ok) return;
        const snapshot = await response.json();
        const savedCandidate = (snapshot.candidates || []).find(item => item.id === candidate.id);
        const savedStatus = savedCandidate?.status || snapshot.decisions?.[candidate.id]?.status;
        if (!savedStatus || savedStatus === 'new') return;
        commitDetected = true;
        discovery = snapshot;
        renderDiscovery();
        showToast(
          action === 'accept' || action === 'replace'
            ? `${candidate.title} 已归档，图谱正在更新`
            : `${candidate.title} 已从候选中移除`,
        );
      } catch (_error) {
        // The main request still reports the authoritative result.
      }
    };

    updateProgress();
    statusTimer = setInterval(updateProgress, 1000);
    if (action === 'accept' || action === 'replace') {
      commitPollTimer = setInterval(detectCommittedDecision, 1500);
    }
    try {
      const payload = await apiRequest('/api/candidates/action', {
        method: 'POST',
        body: JSON.stringify({id: candidate.id, action, category, ...extras}),
      });
      discovery = payload.discovery;
      if (!commitDetected || payload.graph_updated === false) {
        showToast(payload.message, payload.graph_updated === false ? 'warning' : 'success');
      }
      if (action === 'accept' || action === 'replace') {
        if (payload.graph_updated === false) {
          renderDiscovery();
        } else {
          setTimeout(() => window.location.reload(), 650);
        }
      } else {
        renderDiscovery();
      }
    } catch (error) {
      await detectCommittedDecision();
      if (commitDetected) {
        showToast('论文已经归档；本次状态回传中断，图谱将在后台完成更新', 'warning');
      } else {
        controls.forEach(control => { control.disabled = false; });
        article.classList.remove('is-busy');
        progress.remove();
        if (acceptButton) acceptButton.textContent = '加入论文库';
        showToast(error.message, 'error');
      }
    } finally {
      stopProgress();
    }
  }

  function renderCandidateRow(candidate) {
    const row = document.createElement('div');
    row.className = 'candidate-row';
    row.dataset.candidateId = candidate.id;
    row.classList.toggle('active', candidate.id === selectedCandidateId);
    row.classList.toggle('is-discovery-result', highlightedCandidateIds.has(candidate.id));
    row.setAttribute('role', 'button');
    row.setAttribute('tabindex', '0');
    row.setAttribute('aria-pressed', String(candidate.id === selectedCandidateId));
    row.draggable = true;

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'candidate-row-select';
    checkbox.checked = selectedCandidateIds.has(candidate.id);
    checkbox.setAttribute('aria-label', `选择 ${candidate.title}`);
    checkbox.addEventListener('click', event => event.stopPropagation());
    checkbox.addEventListener('change', () => {
      if (checkbox.checked) selectedCandidateIds.add(candidate.id);
      else selectedCandidateIds.delete(candidate.id);
      updateBatchToolbar();
    });

    const source = document.createElement('span');
    source.className = `candidate-row-source source-${(candidate.sources || [])[0] || 'unknown'}`;
    source.textContent = candidateSourceLabel((candidate.sources || [])[0] || '推荐');
    const scoreValue = Number(candidate.recommendation_score);
    const score = document.createElement('span');
    score.className = 'candidate-row-score';
    const normalizedScore = Number.isFinite(scoreValue) ? Math.max(0, Math.min(100, scoreValue)) : null;
    score.dataset.tone = normalizedScore === null ? 'unknown' : normalizedScore >= 70 ? 'high' : normalizedScore >= 45 ? 'medium' : 'low';
    score.setAttribute('aria-label', normalizedScore === null ? '暂无推荐分' : `推荐分 ${normalizedScore}`);
    const scoreLabel = document.createElement('span');
    scoreLabel.textContent = normalizedScore === null ? '—' : String(Math.round(normalizedScore));
    const scoreTrack = document.createElement('span');
    scoreTrack.className = 'candidate-score-track';
    const scoreFill = document.createElement('i');
    scoreFill.style.width = `${normalizedScore || 0}%`;
    if (normalizedScore !== null) scoreFill.style.backgroundColor = scoreColor(normalizedScore);
    scoreTrack.appendChild(scoreFill);
    score.append(scoreLabel, scoreTrack);
    const title = document.createElement('strong');
    title.textContent = candidate.title;
    const category = document.createElement('span');
    category.className = 'candidate-row-category';
    category.textContent = candidateCategory(candidate).label;
    const meta = document.createElement('span');
    meta.className = 'candidate-row-meta';
    const citations = Number(candidate.cited_by_count);
    meta.textContent = `${candidate.year || '年份未知'}${Number.isFinite(citations) && citations > 0 ? ` · 被引 ${citations.toLocaleString('zh-CN')}` : ''}`;
    row.append(checkbox, source, score, title, category, meta);
    const selectCandidate = () => {
      selectedCandidateId = candidate.id;
      renderDiscovery();
    };
    row.addEventListener('click', selectCandidate);
    row.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        selectCandidate();
      }
    });
    row.addEventListener('dragstart', event => {
      event.dataTransfer?.setData('text/paper-atlas-candidate', candidate.id);
      event.dataTransfer.effectAllowed = 'move';
    });
    return row;
  }

  function updateBatchToolbar() {
    selectedCandidateIds = new Set([...selectedCandidateIds].filter(id =>
      (discovery.candidates || []).some(candidate => candidate.id === id && candidate.status === 'new'),
    ));
    batchToolbar.hidden = selectedCandidateIds.size === 0;
    batchCount.textContent = `已选择 ${selectedCandidateIds.size} 篇`;
  }

  async function dismissSelectedCandidates() {
    const ids = [...selectedCandidateIds];
    if (!ids.length) return;
    batchDismiss.disabled = true;
    activityNotice('正在批量移除', `${ids.length} 篇候选正在处理`);
    try {
      for (const id of ids) {
        const result = await apiRequest('/api/candidates/action', {
          method: 'POST', body: JSON.stringify({id, action: 'dismiss', category: ''}),
        });
        discovery = result.discovery || discovery;
      }
      selectedCandidateIds.clear();
      renderDiscovery();
      showToast(`已移除 ${ids.length} 篇候选`);
      recordActivity('批量审核完成', `移除 ${ids.length} 篇待审核论文`);
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      batchDismiss.disabled = false;
      updateBatchToolbar();
    }
  }

  async function sendCandidateFeedback(candidate, feedback) {
    const result = await apiRequest('/api/candidates/feedback', {
      method: 'POST', body: JSON.stringify({id: candidate.id, feedback}),
    });
    discovery = result.discovery;
    return result;
  }

  function openCandidateFeedbackDialog(candidate, onComplete) {
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop candidate-feedback-backdrop';
    const dialog = document.createElement('section');
    dialog.className = 'feedback-dialog';
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');
    dialog.setAttribute('aria-labelledby', 'candidate-feedback-title');
    const header = document.createElement('header');
    header.className = 'dialog-header';
    const heading = document.createElement('div');
    const title = document.createElement('h2');
    title.id = 'candidate-feedback-title';
    title.textContent = '这条推荐是否准确？';
    const summary = document.createElement('p');
    summary.textContent = candidate.title;
    heading.append(title, summary);
    header.appendChild(heading);
    const body = document.createElement('div');
    body.className = 'feedback-dialog-options';
    const options = [
      ['accurate', '准确', '与当前研究方向相关'],
      ['irrelevant', '不相关', '与论文库主题无关'],
      ['wrong_category', '分类不准', '论文有价值，但类别需要调整'],
    ];
    const close = () => {
      backdrop.remove();
      dialog.remove();
    };
    options.forEach(([value, label, detail]) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'feedback-option';
      const strong = document.createElement('strong');
      strong.textContent = label;
      const caption = document.createElement('span');
      caption.textContent = detail;
      button.append(strong, caption);
      button.addEventListener('click', async () => {
        button.disabled = true;
        body.querySelectorAll('button').forEach(item => { item.disabled = true; });
        try {
          await sendCandidateFeedback(candidate, value);
          close();
          renderDiscovery();
          showToast('推荐评价已记录');
          onComplete?.();
        } catch (error) {
          body.querySelectorAll('button').forEach(item => { item.disabled = false; });
          showToast(error.message, 'error');
        }
      });
      body.appendChild(button);
    });
    backdrop.addEventListener('click', close);
    document.body.append(backdrop, dialog);
    requestAnimationFrame(() => body.querySelector('button')?.focus());
  }

  function beginCandidateAction(candidate, action, article, categoryControl, extras = {}) {
    if (action === 'accept' && !categoryControl.value) {
      categoryControl.focus();
      showToast('请先为这篇论文选择类别', 'error');
      return;
    }
    const run = () => {
      const currentArticle = [...candidatePreview.querySelectorAll('[data-candidate-id]')]
        .find(item => item.dataset.candidateId === candidate.id) || article;
      const currentCategory = currentArticle?.querySelector('select[aria-label^="为 "]') || categoryControl;
      if (currentCategory && categoryControl.value) currentCategory.value = categoryControl.value;
      if (action === 'reject' && !window.confirm(`以后不再推荐“${candidate.title}”？`)) return;
      reviewCandidate(candidate, action, currentCategory, currentArticle, extras);
    };
    if (candidate.user_feedback) run();
    else openCandidateFeedbackDialog(candidate, run);
  }

  function renderCandidate(candidate) {
    const article = document.createElement('article');
    article.className = 'candidate-detail-card';
    article.dataset.candidateId = candidate.id;

    const header = document.createElement('header');
    header.className = 'candidate-detail-header';
    const badges = document.createElement('div');
    badges.className = 'candidate-badges';
    (candidate.sources || []).forEach(sourceName => {
      const badge = document.createElement('span');
      badge.className = `source-badge source-${sourceName}`;
      badge.textContent = candidateSourceLabel(sourceName);
      badges.appendChild(badge);
    });
    const links = document.createElement('div');
    links.className = 'candidate-links';
    if (candidate.url) {
      const sourceLink = makeExternalLink('来源页 ↗', candidate.url);
      if (sourceLink) links.appendChild(sourceLink);
    }
    if (candidate.pdf_url) {
      const pdfLink = makeExternalLink('PDF ↗', candidate.pdf_url);
      if (pdfLink) links.appendChild(pdfLink);
    }
    header.append(badges, links);

    const title = document.createElement('h3');
    title.textContent = candidate.title;
    const meta = document.createElement('p');
    meta.className = 'candidate-meta';
    const authors = (candidate.authors || []).slice(0, 6).join('、') || '作者未知';
    const citations = Number(candidate.cited_by_count);
    meta.textContent = `${candidate.year || '年份未知'} · ${authors}${(candidate.authors || []).length > 6 ? ' 等' : ''}${Number.isFinite(citations) && citations > 0 ? ` · 被引 ${citations.toLocaleString('zh-CN')} 次` : ''}`;

    const classification = document.createElement('div');
    classification.className = 'candidate-classification-summary';
    const categoryBadge = document.createElement('span');
    categoryBadge.className = `category-badge category-${candidate.category_confidence === '高' ? 'high' : candidate.category_confidence === '中' ? 'medium' : 'review'}`;
    categoryBadge.textContent = candidate.category_label ? `自动分类 · ${candidate.category_label}` : '自动分类 · 待确认';
    const reason = document.createElement('span');
    reason.textContent = candidate.reason || '匹配论文发现规则';
    classification.append(categoryBadge, reason);

    const tabs = document.createElement('div');
    tabs.className = 'candidate-detail-tabs';
    tabs.setAttribute('role', 'tablist');
    const panels = document.createElement('div');
    panels.className = 'candidate-detail-panels';
    const tabSpecs = [
      ['abstract', '摘要'],
      ['metadata', (candidate.metadata_warnings || []).length ? '校验提醒' : '元数据'],
      ['evidence', '推荐依据'],
    ];
    const tabButtons = [];
    const tabPanels = [];
    tabSpecs.forEach(([id, label], index) => {
      const tab = document.createElement('button');
      tab.type = 'button';
      tab.className = 'candidate-detail-tab';
      tab.textContent = label;
      tab.setAttribute('role', 'tab');
      tab.setAttribute('aria-selected', String(index === 0));
      tab.dataset.tab = id;
      const panelId = `candidate-panel-${candidate.id.replace(/[^a-zA-Z0-9_-]/g, '-')}-${id}`;
      tab.setAttribute('aria-controls', panelId);
      const panel = document.createElement('section');
      panel.className = 'candidate-detail-panel';
      panel.dataset.panel = id;
      panel.id = panelId;
      panel.hidden = index !== 0;
      tabButtons.push(tab);
      tabPanels.push(panel);
      tabs.appendChild(tab);
      panels.appendChild(panel);
    });

    const abstractText = document.createElement('p');
    abstractText.textContent = candidate.abstract || '暂未从公开元数据中获得摘要，可打开来源页进一步查看。';
    tabPanels[0].appendChild(abstractText);

    const quality = document.createElement('div');
    quality.className = 'candidate-quality';
    const confidence = document.createElement('span');
    const confidenceLabel = candidate.confidence_label || '需核验';
    confidence.className = `confidence-badge confidence-${confidenceLabel === '高' ? 'high' : confidenceLabel === '中' ? 'medium' : 'review'}`;
    confidence.textContent = `可信度 ${confidenceLabel}${Number.isFinite(Number(candidate.confidence)) ? ` ${candidate.confidence}` : ''}`;
    quality.appendChild(confidence);
    if (Number.isFinite(Number(candidate.relevance_score))) {
      const relevance = document.createElement('span');
      const relevanceLabel = candidate.relevance_label || '需确认';
      relevance.className = `relevance-badge relevance-${relevanceLabel === '高' ? 'high' : relevanceLabel === '中' ? 'medium' : 'review'}`;
      relevance.textContent = `主题相关 ${candidate.relevance_score}`;
      quality.appendChild(relevance);
    }
    const validationList = document.createElement('ul');
    validationList.className = 'candidate-validation-list';
    [...(candidate.metadata_warnings || []).map(message => ({message, warning: true})),
      ...(candidate.metadata_checks || []).map(message => ({message, warning: false}))].forEach(entry => {
      const item = document.createElement('li');
      item.classList.toggle('validation-warning', entry.warning);
      item.textContent = entry.message;
      validationList.appendChild(item);
    });
    tabPanels[1].append(quality, validationList);

    const evidenceReason = document.createElement('p');
    evidenceReason.className = 'candidate-evidence-reason';
    evidenceReason.textContent = candidate.category_reason || candidate.reason || '匹配论文发现规则';
    tabPanels[2].appendChild(evidenceReason);
    if ((candidate.relevance_evidence || []).length) {
      const evidence = document.createElement('p');
      evidence.textContent = candidate.relevance_evidence.join(' · ');
      tabPanels[2].appendChild(evidence);
    }
    if (Number.isFinite(Number(candidate.recommendation_score))) {
      const ranking = document.createElement('div');
      ranking.className = 'candidate-ranking';
      const rankingScore = document.createElement('strong');
      rankingScore.textContent = `推荐分 ${candidate.recommendation_score}`;
      const rankingReason = document.createElement('p');
      rankingReason.textContent = (candidate.ranking_explanation || []).join(' · ');
      ranking.append(rankingScore, rankingReason);
      tabPanels[2].appendChild(ranking);
    }
    if ((candidate.versions || []).length > 1) {
      const versions = document.createElement('p');
      versions.className = 'candidate-version-summary';
      versions.textContent = `已合并 ${candidate.versions.length} 条版本或来源记录`;
      tabPanels[2].appendChild(versions);
    }
    if ((candidate.supporting_papers || []).length) {
      const supportList = document.createElement('div');
      supportList.className = 'candidate-support-list';
      candidate.supporting_papers.forEach(paper => {
        const supportButton = document.createElement('button');
        supportButton.type = 'button';
        supportButton.textContent = paper.title;
        supportButton.addEventListener('click', () => {
          activateView('graph');
          selectNode(paper.id);
        });
        supportList.appendChild(supportButton);
      });
      tabPanels[2].appendChild(supportList);
    }
    tabButtons.forEach(tab => tab.addEventListener('click', () => {
      tabButtons.forEach(button => button.setAttribute('aria-selected', String(button === tab)));
      tabPanels.forEach(panel => { panel.hidden = panel.dataset.panel !== tab.dataset.tab; });
    }));

    const footer = document.createElement('footer');
    footer.className = 'candidate-detail-footer';
    const category = document.createElement('select');
    category.setAttribute('aria-label', `为 ${candidate.title} 选择类别`);
    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = '选择归档类别';
    category.appendChild(placeholder);
    reviewCategories.forEach(item => {
      const option = document.createElement('option');
      option.value = item.id;
      option.textContent = item.label;
      category.appendChild(option);
    });
    category.value = suggestedCategory(candidate);
    const dismiss = document.createElement('button');
    dismiss.type = 'button';
    dismiss.className = 'candidate-action candidate-action-quiet';
    dismiss.textContent = '移除';
    dismiss.title = '本次移出候选，下次发现时仍可重新出现';
    dismiss.addEventListener('click', () => {
      beginCandidateAction(candidate, 'dismiss', article, category);
    });
    const reject = document.createElement('button');
    reject.type = 'button';
    reject.className = 'candidate-action candidate-action-quiet candidate-action-danger';
    reject.textContent = '忽略';
    reject.title = '以后发现到相同论文时不再推荐';
    reject.addEventListener('click', () => {
      beginCandidateAction(candidate, 'reject', article, category);
    });
    const accept = document.createElement('button');
    accept.type = 'button';
    accept.className = 'candidate-action primary-action';
    accept.textContent = '加入论文库';
    accept.addEventListener('click', () => {
      beginCandidateAction(candidate, 'accept', article, category);
    });
    footer.append(category, dismiss, reject, accept);

    article.append(header, title, meta, classification, tabs, panels, footer);
    return article;
  }

  function candidateTimestamp(candidate) {
    const published = Date.parse(candidate.published || '');
    if (!Number.isNaN(published)) return published;
    const year = Number(candidate.year);
    return Number.isFinite(year) ? Date.UTC(year, 0, 1) : 0;
  }

  function renderDiscovery() {
    const activeCandidates = (discovery.candidates || []).filter(candidate => candidate.status === 'new');
    const sourceCandidates = activeCandidates.filter(candidate => {
      const sourceMatch = discoverySource === 'all' || (candidate.sources || []).includes(discoverySource);
      return sourceMatch;
    });
    renderCandidateCategoryFilter(sourceCandidates);
    const visible = sourceCandidates
      .filter(candidate => discoveryCategory === 'all' || candidateCategory(candidate).id === discoveryCategory)
      .sort((a, b) => {
        if (discoveryCategory === 'all') {
          const categoryOrder = candidateCategory(a).rank - candidateCategory(b).rank;
          if (categoryOrder) return categoryOrder;
        }
        return candidateTimestamp(b) - candidateTimestamp(a) || a.title.localeCompare(b.title);
      });
    if (!visible.some(candidate => candidate.id === selectedCandidateId)) {
      selectedCandidateId = visible[0]?.id || null;
    }
    const selectedCandidate = visible.find(candidate => candidate.id === selectedCandidateId);
    visibleCandidateIds = visible.map(candidate => candidate.id);
    const candidateNodes = [];
    if (discoveryCategory === 'all') {
      const groups = new Map();
      visible.forEach(candidate => {
        const category = candidateCategory(candidate);
        if (!groups.has(category.id)) groups.set(category.id, {category, candidates: []});
        groups.get(category.id).candidates.push(candidate);
      });
      groups.forEach(group => {
        candidateNodes.push(renderCandidateGroupHeader(group.category, group.candidates.length));
        candidateNodes.push(...group.candidates.map(renderCandidateRow));
      });
    } else {
      candidateNodes.push(...visible.map(renderCandidateRow));
    }
    discoveryList.replaceChildren(...candidateNodes);
    discoveryEmpty.hidden = visible.length > 0;
    candidatePreviewEmpty.hidden = Boolean(selectedCandidate);
    candidatePreview.replaceChildren(selectedCandidate ? renderCandidate(selectedCandidate) : candidatePreviewEmpty);
    updateBatchToolbar();
    discoveryCount.textContent = String(activeCandidates.length);
    navDiscoveryCount.textContent = String(activeCandidates.length);
    navDiscoveryCount.hidden = activeCandidates.length === 0;
    if (discovery.metadata.updated_at) {
      const updated = new Date(discovery.metadata.updated_at);
      discoveryUpdated.textContent = Number.isNaN(updated.valueOf())
        ? '发现任务已运行'
        : `更新于 ${updated.toLocaleString('zh-CN', {month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit'})}`;
    }
  }

  function sameDiscoveryTime(value, updatedAt) {
    const timestamp = Date.parse(value || '');
    const updatedTimestamp = Date.parse(updatedAt || '');
    return !Number.isNaN(timestamp)
      && !Number.isNaN(updatedTimestamp)
      && Math.abs(timestamp - updatedTimestamp) < 2000;
  }

  function discoveryRunSummary(currentDiscovery, mode) {
    const updatedAt = currentDiscovery.metadata?.updated_at;
    const expectedSources = mode === 'multi'
      ? ['arxiv_topic', 'highly_cited', 'shared_reference']
      : mode === 'topics'
      ? ['arxiv_topic', 'highly_cited']
      : [mode === 'shared' ? 'shared_reference' : mode === 'highly_cited' ? 'highly_cited' : 'arxiv_topic'];
    const activeCandidates = (currentDiscovery.candidates || []).filter(candidate => candidate.status === 'new');
    const found = activeCandidates.filter(candidate => (
      sameDiscoveryTime(candidate.last_seen, updatedAt)
      && expectedSources.some(source => (candidate.sources || []).includes(source))
    ));
    const added = found.filter(candidate => sameDiscoveryTime(candidate.first_seen, updatedAt));
    return {
      ids: found.map(candidate => candidate.id),
      found: found.length,
      added: added.length,
      arxiv: found.filter(candidate => (candidate.sources || []).includes('arxiv_topic')).length,
      highlyCited: found.filter(candidate => (candidate.sources || []).includes('highly_cited')).length,
      shared: found.filter(candidate => (candidate.sources || []).includes('shared_reference')).length,
    };
  }

  function selectDiscoverySource(source) {
    discoverySource = source;
    candidateSourceFilter.value = source;
  }

  function highlyCitedPipeline(metadata = {}) {
    const raw = Number(metadata.highly_cited_raw_count) || 0;
    const relevant = Number(metadata.highly_cited_relevant_count) || 0;
    const threshold = Number(metadata.highly_cited_threshold_count) || 0;
    const selected = Number(metadata.highly_cited_selected_count) || 0;
    return {
      raw,
      relevant,
      threshold,
      selected,
      text: `OpenAlex 语义召回 ${raw} 篇 · 排除词过滤后 ${relevant} 篇 · 达到被引下限 ${threshold} 篇 · 入选 ${selected} 篇`,
    };
  }

  function libraryMatchSummary(metadata = {}, mode) {
    const matches = mode === 'shared'
      ? metadata.shared_reference_library_matches || []
      : metadata.highly_cited_library_matches || [];
    if (!matches.length) return '';
    const titles = matches.slice(0, 3).map(item => item.title).join('、');
    return `另命中 ${matches.length} 篇库内论文（${titles}${matches.length > 3 ? ' 等' : ''}），已自动排除重复推荐`;
  }

  function belowThresholdLibrarySummary(metadata = {}) {
    const matches = metadata.highly_cited_library_below_threshold_matches || [];
    if (!matches.length) return '';
    const sample = matches.slice(0, 3).map(item => `${item.title}（OpenAlex ${Number(item.cited_by_count) || 0}）`).join('、');
    return `库内另有 ${matches.length} 篇语义命中但低于当前 OpenAlex 阈值：${sample}`;
  }

  function showDiscoveryOutcome(currentDiscovery, mode, summaryOverride = null) {
    const summary = summaryOverride || discoveryRunSummary(currentDiscovery, mode);
    const highlyCited = highlyCitedPipeline(currentDiscovery.metadata);
    const libraryMatches = libraryMatchSummary(currentDiscovery.metadata, mode);
    const belowThresholdMatches = mode === 'highly_cited'
      ? belowThresholdLibrarySummary(currentDiscovery.metadata)
      : '';
    const sourceLabel = mode === 'multi'
      ? '论文发现'
      : mode === 'topics'
      ? '主题发现'
      : mode === 'shared' ? '共同引用' : mode === 'highly_cited' ? '领域高被引' : 'arXiv 搜索';
    selectDiscoverySource(
      mode === 'multi' || mode === 'topics' ? 'all' : mode === 'shared' ? 'shared_reference' : mode === 'highly_cited' ? 'highly_cited' : 'arxiv_topic',
    );
    clearTimeout(discoveryHighlightTimer);
    highlightedCandidateIds = new Set(summary.ids);
    selectedCandidateId = summary.ids[0] || selectedCandidateId;
    discoveryResult.hidden = false;
    discoveryResult.dataset.tone = summary.found ? 'success' : 'empty';
    discoveryResultTitle.textContent = summary.found
      ? `${sourceLabel}找到 ${summary.found} 篇论文`
      : `${sourceLabel}没有找到符合条件的论文`;
    discoveryResultMeta.textContent = mode === 'highly_cited'
      ? summary.found
        ? `${highlyCited.text} · 本次新增 ${summary.added} 篇；下方结果已高亮${libraryMatches ? `；${libraryMatches}` : ''}${belowThresholdMatches ? `；${belowThresholdMatches}` : ''}`
        : highlyCited.selected
          ? `${highlyCited.text}；${libraryMatches || '入选论文可能已在候选或审核记录中'}${belowThresholdMatches ? `；${belowThresholdMatches}` : ''}`
          : highlyCited.threshold
            ? `${highlyCited.text}；可以提高每个主题的入选数量`
            : `${highlyCited.text}；${belowThresholdMatches || '可以降低被引下限或调整主题描述'}`
      : summary.found
        ? mode === 'multi' || mode === 'topics'
        ? `arXiv ${summary.arxiv} 篇 · 高被引 ${summary.highlyCited} 篇 · 新增 ${summary.added} 篇；下方结果已高亮`
        : `其中新增 ${summary.added} 篇；下方对应结果已高亮${libraryMatches ? `；${libraryMatches}` : ''}`
      : mode === 'shared'
        ? libraryMatches || '可以降低共同引用次数下限后再次计算'
        : mode === 'multi' || mode === 'topics'
            ? '可以调整搜索主题、扩大 arXiv 时间范围或降低高被引下限'
        : '可以调整搜索主题或扩大时间范围后再次尝试';
    renderDiscovery();
    showToast(
      summary.found
        ? `${sourceLabel}完成：找到 ${summary.found} 篇，新增 ${summary.added} 篇`
        : `${sourceLabel}完成：本次没有结果`,
    );

    requestAnimationFrame(() => {
      const firstHighlighted = discoveryList.querySelector('.candidate-row.is-discovery-result');
      if (firstHighlighted) firstHighlighted.scrollIntoView({behavior: 'smooth', block: 'nearest'});
    });
    discoveryHighlightTimer = setTimeout(() => {
      highlightedCandidateIds.clear();
      discoveryList.querySelectorAll('.candidate-row.is-discovery-result').forEach(card => {
        card.classList.remove('is-discovery-result');
      });
    }, 10000);
  }

  function topicRow(topic = {}) {
    const row = document.createElement('article');
    row.className = 'topic-row';
    row.dataset.id = topic.id || '';
    row.innerHTML = `
      <header class="topic-row-heading">
        <label class="topic-enabled"><input type="checkbox" ${topic.enabled === false ? '' : 'checked'}><span>启用</span></label>
        <input class="topic-label" type="text" maxlength="80" placeholder="主题名称，例如：长上下文优化" aria-label="主题名称">
        <label class="topic-maximum-field"><span>每天最多发现</span><input class="topic-maximum" type="number" min="1" max="50" value="${Number(topic.max_results) || 10}"></label>
        <button type="button" class="topic-remove" aria-label="删除这个搜索主题">删除</button>
      </header>
      <div class="topic-row-fields">
        <label><span>搜索关键词</span><textarea class="topic-keywords" rows="2" placeholder="long context, KV cache"></textarea></label>
        <label><span>排除词</span><textarea class="topic-excludes" rows="2" placeholder="可选，用逗号分隔"></textarea></label>
      </div>
      <div class="topic-reference-field">
        <div class="topic-reference-heading"><span>参考论文</span><span class="topic-reference-count">自动选择</span></div>
        <details class="topic-reference-picker">
          <summary>从论文库选择</summary>
          <div class="topic-reference-options"></div>
        </details>
      </div>
    `;
    row.querySelector('.topic-label').value = topic.label || '';
    row.querySelector('.topic-keywords').value = (topic.keywords || []).join('，');
    row.querySelector('.topic-excludes').value = (topic.exclude_keywords || []).join('，');
    const selectedReferences = new Set(topic.reference_paper_ids || []);
    const referenceOptions = row.querySelector('.topic-reference-options');
    const referenceCount = row.querySelector('.topic-reference-count');
    const category = TOPIC_TEMPLATES.find(template =>
      [template.id, ...(template.aliases || [])].includes(topic.id),
    )?.category;
    const availablePapers = [...graph.nodes].sort((left, right) => {
      const categoryOrder = Number(right.category === category) - Number(left.category === category);
      return categoryOrder
        || Number(right.citation_count || 0) - Number(left.citation_count || 0)
        || String(left.title || '').localeCompare(String(right.title || ''));
    });
    const updateReferenceCount = () => {
      const count = referenceOptions.querySelectorAll('input:checked').length;
      referenceCount.textContent = count ? `已选 ${count} 篇` : '自动选择';
    };
    availablePapers.forEach(node => {
      const referenceId = node.sha256 || node.id;
      if (!referenceId) return;
      const option = document.createElement('label');
      option.className = 'topic-reference-option';
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.value = referenceId;
      checkbox.checked = selectedReferences.has(referenceId) || selectedReferences.has(node.id);
      const copy = document.createElement('span');
      const title = document.createElement('strong');
      title.textContent = node.title || '未命名论文';
      const meta = document.createElement('small');
      meta.textContent = `${displayCategoryLabel(node.category)} · ${node.year || '年份未知'}`;
      copy.append(title, meta);
      option.append(checkbox, copy);
      checkbox.addEventListener('change', () => {
        const checked = referenceOptions.querySelectorAll('input:checked');
        if (checked.length > 8) {
          checkbox.checked = false;
          showToast('每个主题最多选择 8 篇参考论文', 'warning');
        }
        updateReferenceCount();
      });
      referenceOptions.appendChild(option);
    });
    updateReferenceCount();
    row.querySelector('.topic-remove').addEventListener('click', () => {
      row.remove();
      refreshTopicTemplateStates();
    });
    return row;
  }

  function templateRow(template) {
    const ids = new Set([template.id, ...(template.aliases || [])]);
    return [...topicsList.querySelectorAll('.topic-row')].find(row => ids.has(row.dataset.id));
  }

  function refreshTopicTemplateStates() {
    TOPIC_TEMPLATES.forEach(template => {
      const button = topicTemplateButtons.get(template.id);
      if (!button) return;
      const added = Boolean(templateRow(template));
      button.classList.toggle('added', added);
      button.setAttribute('aria-pressed', String(added));
      button.querySelector('span').textContent = added ? '已添加' : '添加';
    });
  }

  function addTopicTemplate(template) {
    const existing = templateRow(template);
    if (existing) {
      existing.scrollIntoView({behavior: 'smooth', block: 'center'});
      existing.querySelector('.topic-label').focus({preventScroll: true});
      showToast('该分类模板已经在搜索主题中');
      return;
    }
    const row = topicRow(template);
    topicsList.appendChild(row);
    refreshTopicTemplateStates();
    row.scrollIntoView({behavior: 'smooth', block: 'center'});
    row.querySelector('.topic-label').focus({preventScroll: true});
  }

  function renderTopicTemplates() {
    topicTemplatesList.replaceChildren();
    TOPIC_TEMPLATES.forEach((template, index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'topic-template-button';
      button.setAttribute('aria-pressed', 'false');
      button.innerHTML = `<strong>${String(index + 1).padStart(2, '0')} · ${template.label}</strong><span>添加</span>`;
      button.addEventListener('click', () => addTopicTemplate(template));
      topicTemplateButtons.set(template.id, button);
      topicTemplatesList.appendChild(button);
    });
  }

  function splitKeywords(value) {
    return value.split(/[,，\n]/).map(item => item.trim()).filter(Boolean);
  }

  function collectTopics() {
    return [...topicsList.querySelectorAll('.topic-row')].map(row => ({
      id: row.dataset.id,
      label: row.querySelector('.topic-label').value.trim(),
      keywords: splitKeywords(row.querySelector('.topic-keywords').value),
      exclude_keywords: splitKeywords(row.querySelector('.topic-excludes').value),
      enabled: row.querySelector('.topic-enabled input').checked,
      max_results: Number(row.querySelector('.topic-maximum').value),
      reference_paper_ids: [...row.querySelectorAll('.topic-reference-options input:checked')]
        .map(input => input.value),
    }));
  }

  function openTopicsDialog() {
    topicsReturnFocus = document.activeElement;
    topicsList.replaceChildren(...apiTopics.map(topicRow));
    refreshTopicTemplateStates();
    topicsDialog.hidden = false;
    topicsBackdrop.hidden = false;
    document.body.classList.add('topics-open');
    requestAnimationFrame(() => topicsClose.focus({preventScroll: true}));
  }

  function closeTopicsDialog() {
    topicsDialog.hidden = true;
    topicsBackdrop.hidden = true;
    document.body.classList.remove('topics-open');
    (topicsReturnFocus?.isConnected ? topicsReturnFocus : manageTopics)?.focus({preventScroll: true});
    topicsReturnFocus = null;
  }

  function openDiscoverySheet() {
    discoverySheetReturnFocus = document.activeElement;
    discoverySheet.hidden = false;
    discoverySheetBackdrop.hidden = false;
    renderDiscoveryTopicOptions();
    syncDiscoverySelection();
    requestAnimationFrame(() => discoverySheetClose.focus({preventScroll: true}));
  }

  const discoveryModeLabels = {arxiv: '最新 arXiv', highly_cited: '领域高被引', shared: '共同引用'};
  function renderDiscoveryTopicOptions() {
    const enabledTopics = apiTopics.filter(topic => topic.enabled !== false && topic.id);
    const enabledIds = new Set(enabledTopics.map(topic => topic.id));
    [...selectedDiscoveryTopicIds].forEach(identifier => {
      if (!enabledIds.has(identifier)) selectedDiscoveryTopicIds.delete(identifier);
    });
    if (!selectedDiscoveryTopicIds.size && enabledTopics.length) {
      selectedDiscoveryTopicIds.add(enabledTopics[0].id);
    }
    discoveryTopicOptions.replaceChildren(...enabledTopics.map(topic => {
      const label = document.createElement('label');
      label.className = 'discovery-topic-option';
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.value = topic.id;
      input.checked = selectedDiscoveryTopicIds.has(topic.id);
      label.classList.toggle('is-selected', input.checked);
      const text = document.createElement('span');
      text.textContent = topic.label || '未命名主题';
      input.addEventListener('change', () => {
        if (input.checked) selectedDiscoveryTopicIds.add(topic.id);
        else selectedDiscoveryTopicIds.delete(topic.id);
        label.classList.toggle('is-selected', input.checked);
        syncDiscoverySelection();
      });
      label.append(input, text);
      return label;
    }));
  }

  function syncDiscoverySelection() {
    const buttons = [runDiscoveryButton, runHighlyCitedButton, runSharedDiscoveryButton];
    buttons.forEach(button => {
      const mode = button.dataset.discoveryMode;
      const selected = selectedDiscoveryModes.has(mode);
      button.classList.toggle('is-selected', selected);
      button.setAttribute('aria-pressed', String(selected));
    });
    const selectedLabels = [...selectedDiscoveryModes].map(mode => discoveryModeLabels[mode]).filter(Boolean);
    const needsTopics = selectedDiscoveryModes.has('arxiv') || selectedDiscoveryModes.has('highly_cited');
    const topicCount = selectedDiscoveryTopicIds.size;
    discoveryTopicOptions.classList.toggle('is-required', needsTopics);
    discoverySelectionSummary.textContent = selectedLabels.length
      ? `已选择：${selectedLabels.join('、')}${needsTopics ? ` · ${topicCount} 个主题` : ''}`
      : '请选择至少一种发现方式';
    runSelectedDiscoveryButton.disabled = selectedLabels.length === 0 || (needsTopics && topicCount === 0);
  }

  function toggleDiscoveryMode(mode) {
    if (!mode) return;
    if (selectedDiscoveryModes.has(mode)) selectedDiscoveryModes.delete(mode);
    else selectedDiscoveryModes.add(mode);
    syncDiscoverySelection();
  }

  function closeDiscoverySheet() {
    discoverySheet.hidden = true;
    discoverySheetBackdrop.hidden = true;
    (discoverySheetReturnFocus?.isConnected ? discoverySheetReturnFocus : openDiscoverySheetButton)?.focus({preventScroll: true});
    discoverySheetReturnFocus = null;
  }

  function renderAutomationTopicSummary() {
    const enabledTopics = apiTopics.filter(topic => topic.enabled !== false);
    if (!enabledTopics.length) {
      const empty = document.createElement('div');
      empty.className = 'topic-summary-empty';
      empty.textContent = '暂无启用的搜索主题';
      automationTopicSummary.replaceChildren(empty);
      return;
    }
    automationTopicSummary.replaceChildren(...enabledTopics.map(topic => {
      const card = document.createElement('button');
      card.type = 'button';
      card.className = 'topic-summary-card';
      card.setAttribute('aria-label', `管理搜索主题：${topic.label || '未命名主题'}`);
      const heading = document.createElement('span');
      heading.className = 'topic-summary-heading';
      const title = document.createElement('strong');
      title.textContent = topic.label || '未命名主题';
      const state = document.createElement('span');
      state.textContent = `最多 ${Number(topic.max_results) || 10} 篇/日`;
      heading.append(title, state);
      const keywords = document.createElement('span');
      keywords.className = 'topic-summary-keywords';
      const terms = (topic.keywords || []).slice(0, 4);
      if (terms.length) {
        terms.forEach(term => {
          const chip = document.createElement('i');
          chip.textContent = term;
          keywords.appendChild(chip);
        });
      } else {
        const chip = document.createElement('i');
        chip.textContent = '尚未设置关键词';
        keywords.appendChild(chip);
      }
      card.append(heading, keywords);
      card.addEventListener('click', openTopicsDialog);
      return card;
    }));
  }

  function setDiscoveryBusy(busy, label = '正在搜索 arXiv…') {
    [runDiscoveryButton, runHighlyCitedButton, runSharedDiscoveryButton, runSelectedDiscoveryButton, clearCandidatesButton, saveTopicsButton, saveAndDiscoverButton, addTopicButton, ...topicTemplateButtons.values()].forEach(button => {
      button.disabled = busy;
    });
    sharedReferenceMinimum.disabled = busy;
    highlyCitedMinimum.disabled = busy;
    const isArxiv = label.includes('arXiv');
    const isHighlyCited = label.includes('高被引');
    const isShared = label.includes('共同引用');
    const isTopicDiscovery = label.includes('主题发现');
    const isMultiDiscovery = label.includes('所选发现');
    const setMethodLabel = (button, text) => {
      const strong = button?.querySelector('strong');
      if (strong) strong.textContent = text;
      else if (button) button.textContent = text;
    };
    setMethodLabel(runDiscoveryButton, busy && isArxiv ? '搜索中…' : '最新 arXiv');
    setMethodLabel(runHighlyCitedButton, busy && isHighlyCited ? '搜索中…' : '领域高被引');
    setMethodLabel(runSharedDiscoveryButton, busy && isShared ? '计算中…' : '共同引用');
    clearInterval(discoveryBusyTimer);
    discoveryBusyTimer = null;
    discoveryProgress.hidden = !busy;
    if (!busy) return;
    discoveryResult.hidden = true;
    highlightedCandidateIds.clear();
    clearTimeout(discoveryHighlightTimer);
    discoveryBusyStarted = Date.now();
    discoveryProgressTitle.textContent = isMultiDiscovery
      ? '正在执行所选发现方式'
      : isTopicDiscovery
      ? '正在搜索 arXiv 与领域高被引论文'
      : isShared
      ? '正在计算共同引用'
      : isHighlyCited
        ? '正在搜索领域高被引论文'
      : isArxiv
        ? '正在搜索最新 arXiv 论文'
        : label.includes('清空')
          ? '正在清空候选'
          : '正在保存搜索主题';
    const updateElapsed = () => {
      const elapsed = Math.max(0, Math.floor((Date.now() - discoveryBusyStarted) / 1000));
      const minutes = String(Math.floor(elapsed / 60)).padStart(2, '0');
      const seconds = String(elapsed % 60).padStart(2, '0');
      discoveryProgressMeta.textContent = isMultiDiscovery
        ? `将依次运行 ${selectedDiscoveryModes.size} 种发现方式 · 已用时 ${minutes}:${seconds}`
        : isTopicDiscovery
        ? `正在按搜索主题合并两类结果 · 已用时 ${minutes}:${seconds}`
        : isShared
        ? `下限 ${sharedReferenceMinimum.value} 次 · 正在分析库内论文引用 · 已用时 ${minutes}:${seconds}`
        : isHighlyCited
          ? `下限 ${highlyCitedMinimum.value} 次 · 正在按搜索主题获取高被引论文 · 已用时 ${minutes}:${seconds}`
        : isArxiv
          ? `正在按搜索主题获取 arXiv 论文 · 已用时 ${minutes}:${seconds}`
          : label.includes('清空')
            ? `正在移除待审核候选 · 已用时 ${minutes}:${seconds}`
            : `正在写入应用配置 · 已用时 ${minutes}:${seconds}`;
    };
    updateElapsed();
    discoveryBusyTimer = setInterval(updateElapsed, 1000);
  }

  async function saveTopics(runAfterSave = false) {
    setDiscoveryBusy(true, runAfterSave ? '正在进行主题发现…' : '正在保存…');
    try {
      const saved = await apiRequest('/api/topics', {
        method: 'PUT',
        body: JSON.stringify({topics: collectTopics()}),
      });
      apiTopics = saved.topics;
      renderAutomationTopicSummary();
      renderDiscoveryTopicOptions();
      if (runAfterSave) {
        closeTopicsDialog();
        const result = await apiRequest('/api/discover', {
          method: 'POST',
          body: JSON.stringify({mode: 'topics', topic_ids: [...selectedDiscoveryTopicIds]}),
        });
        discovery = result.discovery;
        showDiscoveryOutcome(discovery, 'topics');
      } else {
        showToast(saved.message);
        closeTopicsDialog();
      }
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      setDiscoveryBusy(false);
    }
  }

  async function runDiscoveryNow(mode = 'arxiv') {
    const requestedModes = [...new Set(Array.isArray(mode) ? mode : [mode])]
      .filter(item => ['arxiv', 'highly_cited', 'shared'].includes(item));
    if (!requestedModes.length) {
      showToast('请选择至少一种发现方式', 'error');
      return;
    }
    const usesTopics = requestedModes.includes('arxiv') || requestedModes.includes('highly_cited');
    if (usesTopics && !selectedDiscoveryTopicIds.size) {
      showToast('请至少选择一个搜索主题', 'error');
      return;
    }
    const modes = [];
    const hasArxiv = requestedModes.includes('arxiv');
    const hasHighlyCited = requestedModes.includes('highly_cited');
    if (hasArxiv && hasHighlyCited) modes.push('topics');
    else if (hasArxiv) modes.push('arxiv');
    else if (hasHighlyCited) modes.push('highly_cited');
    if (requestedModes.includes('shared')) modes.push('shared');
    const sharedMinimum = Number(sharedReferenceMinimum.value);
    const citationMinimum = Number(highlyCitedMinimum.value);
    if (modes.includes('shared') && (!Number.isInteger(sharedMinimum) || sharedMinimum < 2 || sharedMinimum > 20)) {
      sharedReferenceMinimum.focus();
      showToast('共同引用次数下限需要是 2–20 之间的整数', 'error');
      return;
    }
    if (modes.includes('topics') || modes.includes('highly_cited')) {
      if (!Number.isInteger(citationMinimum) || citationMinimum < 1 || citationMinimum > 1000000) {
      highlyCitedMinimum.focus();
      showToast('高被引次数下限需要是 1–1,000,000 之间的整数', 'error');
      return;
      }
    }
    closeDiscoverySheet();
    runDiscoveryButton.closest('details')?.removeAttribute('open');
    const busyLabel = modes.length > 1
      ? '正在执行所选发现…'
      : modes[0] === 'shared'
        ? '正在计算共同引用…'
        : modes[0] === 'highly_cited'
          ? '正在搜索领域高被引…'
          : modes[0] === 'topics'
            ? '正在搜索 arXiv 与领域高被引…'
            : '正在搜索 arXiv…';
    setDiscoveryBusy(
      true,
      busyLabel,
    );
    try {
      let lastResult = null;
      const combined = {ids: [], found: 0, added: 0, arxiv: 0, highlyCited: 0, shared: 0};
      for (const selectedMode of modes) {
        lastResult = await apiRequest('/api/discover', {
          method: 'POST',
          body: JSON.stringify({
            mode: selectedMode,
            ...(selectedMode === 'shared' ? {min_library_citations: sharedMinimum} : {}),
            ...(['highly_cited', 'topics'].includes(selectedMode) ? {min_citations: citationMinimum} : {}),
            ...(['arxiv', 'highly_cited', 'topics'].includes(selectedMode)
              ? {topic_ids: [...selectedDiscoveryTopicIds]}
              : {}),
          }),
        });
        discovery = lastResult.discovery;
        if (modes.length > 1) {
          const runSummary = discoveryRunSummary(discovery, selectedMode);
          combined.ids.push(...runSummary.ids);
          combined.found += runSummary.found;
          combined.added += runSummary.added;
          combined.arxiv += runSummary.arxiv;
          combined.highlyCited += runSummary.highlyCited;
          combined.shared += runSummary.shared;
        }
      }
      if (modes.length > 1) {
        combined.ids = [...new Set(combined.ids)];
        combined.found = combined.ids.length;
      }
      showDiscoveryOutcome(discovery, modes.length > 1 ? 'multi' : modes[0], modes.length > 1 ? combined : null);
      const labels = requestedModes.map(item => discoveryModeLabels[item]).join('、');
      recordActivity('论文发现完成', lastResult?.message || `${labels} 已完成`);
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      setDiscoveryBusy(false);
    }
  }

  async function clearCandidates() {
    const count = (discovery.candidates || []).filter(candidate => candidate.status === 'new').length;
    if (!count) {
      showToast('当前没有待清空的候选');
      return;
    }
    clearCandidatesButton.closest('details')?.removeAttribute('open');
    setDiscoveryBusy(true, '正在清空…');
    try {
      const result = await apiRequest('/api/candidates/clear', {method: 'POST', body: '{}'});
      discovery = result.discovery;
      highlightedCandidateIds.clear();
      discoveryResult.hidden = true;
      renderDiscovery();
      showToast(result.message);
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      setDiscoveryBusy(false);
    }
  }

  function formatTaskTime(value) {
    if (!value) return '尚未运行';
    const date = new Date(value);
    return Number.isNaN(date.valueOf()) ? '尚未运行' : date.toLocaleString('zh-CN', {
      month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  }

  async function runMaintenanceAction(action, button) {
    if (!action?.id) return;
    const originalLabel = button.textContent;
    button.disabled = true;
    button.textContent = '处理中…';
    try {
      const result = await apiRequest('/api/maintenance/rebuild', {
        method: 'POST', body: JSON.stringify({action: action.id}),
      });
      if (result.health) renderHealth(result.health);
      if (result.classification_review) renderClassificationReview(result.classification_review);
      if (result.discovery) {
        discovery = result.discovery;
        renderDiscovery();
      }
      if (result.tasks) renderTasks(result.tasks);
      showToast(result.message || `${action.label || '处理'}已完成`);
      if (result.graph_updated) {
        setTimeout(() => window.location.reload(), 600);
      } else {
        const state = await apiRequest('/api/state');
        if (state.health) renderHealth(state.health);
        if (state.classification_review) renderClassificationReview(state.classification_review);
        if (state.discovery) {
          discovery = state.discovery;
          renderDiscovery();
        }
        if (state.tasks) renderTasks(state.tasks);
        const diagnostics = await apiRequest('/api/diagnostics', {
          method: 'POST', body: JSON.stringify({include_network: false}),
        });
        renderDiagnostics(diagnostics.diagnostics);
      }
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      button.disabled = false;
      button.textContent = originalLabel;
    }
  }

  function maintenanceButton(action, className = 'health-action-button') {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = className;
    button.textContent = action.label || '立即处理';
    if (action.description) button.title = action.description;
    button.addEventListener('click', () => runMaintenanceAction(action, button));
    return button;
  }

  function renderHealth(health) {
    apiHealth = health || {status: 'error', summary: '无法读取论文库状态', issues: []};
    healthPanel.dataset.status = apiHealth.status;
    navHealthDot.dataset.status = apiHealth.status;
    healthSummary.textContent = apiHealth.summary || '论文库状态未知';
    healthIssues.replaceChildren();
    if (!(apiHealth.issues || []).length) {
      const message = document.createElement('strong');
      message.textContent = '文件、分类、图谱和候选数据一致';
      healthIssues.appendChild(message);
      return;
    }
    const renderedActions = new Set();
    (apiHealth.issues || []).forEach(item => {
      const issue = document.createElement('article');
      issue.className = `health-issue health-${item.severity}`;
      const copy = document.createElement('div');
      copy.className = 'health-issue-copy';
      const title = document.createElement('strong');
      title.textContent = item.title;
      const detail = document.createElement('span');
      detail.textContent = item.detail;
      copy.append(title, detail);
      issue.appendChild(copy);
      if (item.action) {
        const action = {
          id: item.action,
          label: item.action_label || '立即处理',
          description: item.action_description || '',
        };
        issue.appendChild(maintenanceButton(action));
        renderedActions.add(action.id);
      }
      healthIssues.appendChild(issue);
    });
    const extraActions = (apiHealth.actions || []).filter(action => action?.id && !renderedActions.has(action.id));
    if (extraActions.length) {
      const actionBar = document.createElement('div');
      actionBar.className = 'health-action-bar';
      extraActions.forEach(action => actionBar.appendChild(maintenanceButton(action)));
      healthIssues.appendChild(actionBar);
    }
  }

  function renderClassificationReview(review = {}) {
    const items = review.items || [];
    classificationReviewPanel.hidden = !items.length;
    classificationReviewCount.textContent = String(items.length);
    classificationReviewSummary.textContent = items.length
      ? `${items.length} 篇需要确认类别后归档`
      : '没有需要审核的论文';
    classificationReviewList.replaceChildren();
    items.forEach(item => {
      const row = document.createElement('article');
      row.className = 'classification-review-item';
      const copy = document.createElement('div');
      const title = document.createElement('strong');
      title.textContent = String(item.path || '').split('/').pop() || '未命名论文';
      const reason = document.createElement('p');
      reason.textContent = `${item.confidence || '需确认'} · ${item.reason || '分类依据不足'}`;
      copy.append(title, reason);
      const select = document.createElement('select');
      select.setAttribute('aria-label', `${title.textContent}的论文类别`);
      reviewCategories.forEach(category => {
        const option = document.createElement('option');
        option.value = category.id;
        option.textContent = category.label;
        option.selected = category.id === item.suggested_category;
        select.appendChild(option);
      });
      const confirm = document.createElement('button');
      confirm.type = 'button';
      confirm.className = 'primary-button';
      confirm.textContent = '确认归档';
      confirm.addEventListener('click', async () => {
        confirm.disabled = true;
        confirm.textContent = '归档中…';
        try {
          const result = await apiRequest('/api/classification/action', {
            method: 'POST', body: JSON.stringify({id: item.id, category: select.value}),
          });
          renderClassificationReview(result.classification_review);
          if (result.health) renderHealth(result.health);
          showToast(result.message);
          if (result.graph_updated) setTimeout(() => window.location.reload(), 500);
        } catch (error) {
          showToast(error.message, 'error');
          confirm.disabled = false;
          confirm.textContent = '确认归档';
        }
      });
      row.append(copy, select, confirm);
      classificationReviewList.appendChild(row);
    });
  }

  function renderDiscoveryLog(events = []) {
    if (!events.length) {
      discoveryDebugOutput.textContent = '尚无日志';
      return;
    }
    discoveryDebugOutput.textContent = [...events].reverse().map(event => {
      const {timestamp, event: name, ...details} = event;
      const time = timestamp ? new Date(timestamp).toLocaleString('zh-CN') : '未知时间';
      return `${time}  ${name}\n${JSON.stringify(details, null, 2)}`;
    }).join('\n\n');
  }

  function renderTasks(state) {
    apiTasks = state || {supported: false, tasks: []};
    taskList.replaceChildren();
    (apiTasks.tasks || []).forEach(task => {
      const article = document.createElement('article');
      article.className = 'task-item';
      article.dataset.taskId = task.id;

      const heading = document.createElement('div');
      heading.className = 'task-heading';
      const toggle = document.createElement('label');
      toggle.className = 'task-toggle';
      const enabled = document.createElement('input');
      enabled.type = 'checkbox';
      enabled.checked = task.enabled;
      const name = document.createElement('strong');
      name.textContent = task.label;
      toggle.append(enabled, name);
      const time = document.createElement('input');
      time.type = 'time';
      time.value = task.time;
      time.setAttribute('aria-label', `${task.label}运行时间`);
      heading.append(toggle, time);

      const status = document.createElement('p');
      status.className = `task-status task-${task.last_status}`;
      const next = task.next_run ? `下次 ${formatTaskTime(task.next_run)}` : task.enabled ? '等待保存并启用' : '已停用';
      status.textContent = `${next} · ${task.last_message || '尚未运行'}`;

      const actions = document.createElement('div');
      actions.className = 'task-actions';
      const run = document.createElement('button');
      run.type = 'button';
      run.className = 'secondary-button';
      run.textContent = '立即运行';
      run.addEventListener('click', () => runTaskNow(task.id, run));
      actions.appendChild(run);
      article.append(heading, status, actions);
      taskList.appendChild(article);
    });
  }

  async function runTaskNow(taskId, button) {
    button.disabled = true;
    button.textContent = '运行中…';
    try {
      const result = await apiRequest('/api/tasks', {
        method: 'POST', body: JSON.stringify({action: 'run', task_id: taskId}),
      });
      renderTasks(result);
      showToast(result.message);
      recordActivity('每日任务已运行', result.message || taskId);
      const state = await apiRequest('/api/state');
      if (state.health) renderHealth(state.health);
      if (state.discovery) {
        discovery = state.discovery;
        renderDiscovery();
      }
      renderClassificationReview(state.classification_review);
      renderDiscoveryLog(state.discovery_log);
      if (taskId === 'classification' && result.result?.graph_updated) {
        setTimeout(() => window.location.reload(), 500);
      }
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      button.disabled = false;
      button.textContent = '立即运行';
    }
  }

  async function saveTasks() {
    const tasks = {};
    taskList.querySelectorAll('.task-item').forEach(item => {
      tasks[item.dataset.taskId] = {
        enabled: item.querySelector('.task-toggle input').checked,
        time: item.querySelector('input[type="time"]').value,
      };
    });
    saveTasksButton.disabled = true;
    try {
      const result = await apiRequest('/api/tasks', {
        method: 'POST', body: JSON.stringify({action: 'configure', tasks}),
      });
      renderTasks(result);
      showToast(result.message);
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      saveTasksButton.disabled = false;
    }
  }

  async function rebuildGraph() {
    rebuildGraphButton.disabled = true;
    rebuildGraphButton.textContent = '正在构建…';
    try {
      const result = await apiRequest('/api/maintenance/rebuild', {method: 'POST', body: '{}'});
      if (result.health) renderHealth(result.health);
      showToast(result.message);
      setTimeout(() => window.location.reload(), 600);
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      rebuildGraphButton.disabled = false;
      rebuildGraphButton.textContent = '重新检查并构建';
    }
  }

  function renderDiagnostics(report) {
    diagnosticsPanel.hidden = false;
    diagnosticsPanel.dataset.status = report.status || 'warning';
    const statusLabels = {healthy: '所有关键检查均通过', warning: '诊断完成，存在需要留意的项目', failed: '诊断发现需要处理的问题'};
    diagnosticsSummary.textContent = statusLabels[report.status] || '诊断完成';
    diagnosticsPanel.dataset.copyText = report.copy_text || '';
    const metrics = report.evaluation?.metrics || {};
    const metricItems = [
      ['召回率', metrics.recall],
      ['精确率', metrics.precision],
      ['分类准确率', metrics.classification_accuracy],
      ['去重准确率', metrics.dedupe_accuracy],
    ];
    diagnosticsMetrics.replaceChildren(...metricItems.map(([label, value]) => {
      const item = document.createElement('div');
      item.className = 'diagnostics-metric';
      const strong = document.createElement('strong');
      strong.textContent = Number.isFinite(Number(value)) ? `${Math.round(Number(value) * 100)}%` : '—';
      const caption = document.createElement('span');
      caption.textContent = label;
      item.append(strong, caption);
      return item;
    }));
    const renderedActionIds = new Set();
    diagnosticsChecks.replaceChildren(...(report.checks || []).map(check => {
      const item = document.createElement('article');
      item.className = 'diagnostics-check';
      item.dataset.status = check.status;
      const dot = document.createElement('span');
      dot.className = 'diagnostics-check-dot';
      const copy = document.createElement('div');
      const label = document.createElement('strong');
      label.textContent = check.label;
      const summary = document.createElement('p');
      summary.textContent = check.summary;
      copy.append(label, summary);
      item.append(dot, copy);
      if ((check.actions || []).length) {
        const actions = document.createElement('div');
        actions.className = 'diagnostics-check-actions';
        check.actions.forEach(action => {
          actions.appendChild(maintenanceButton(action, 'diagnostics-action-button'));
          renderedActionIds.add(action.id);
        });
        item.appendChild(actions);
      }
      return item;
    }));
    const remainingActions = (report.actions || []).filter(action => !renderedActionIds.has(action.id));
    diagnosticsActions.replaceChildren(...remainingActions.map(action =>
      maintenanceButton(action, 'diagnostics-action-button'),
    ));
    diagnosticsActions.hidden = !remainingActions.length;
  }

  async function runDiagnostics() {
    runDiagnosticsButton.disabled = true;
    runDiagnosticsButton.textContent = '诊断中…';
    try {
      const result = await apiRequest('/api/diagnostics', {
        method: 'POST', body: JSON.stringify({include_network: true}),
      });
      renderDiagnostics(result.diagnostics);
      showToast(result.message, result.diagnostics.status === 'failed' ? 'warning' : 'success');
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      runDiagnosticsButton.disabled = false;
    runDiagnosticsButton.textContent = '检查系统';
    }
  }

  async function copyDiagnostics() {
    const text = diagnosticsPanel.dataset.copyText || '';
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      showToast('诊断报告已复制');
    } catch (_error) {
      const area = document.createElement('textarea');
      area.value = text;
      document.body.appendChild(area);
      area.select();
      document.execCommand('copy');
      area.remove();
      showToast('诊断报告已复制');
    }
  }

  async function exportBackup() {
    exportBackupButton.disabled = true;
    try {
      const result = await apiRequest('/api/backup', {
        method: 'POST', body: JSON.stringify({action: 'export'}),
      });
      const blob = new Blob([JSON.stringify(result.backup, null, 2)], {type: 'application/json'});
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `paper-atlas-backup-${new Date().toISOString().slice(0, 10)}.json`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      showToast('备份已导出，不包含论文 PDF');
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      exportBackupButton.disabled = false;
    }
  }

  async function restoreBackup(file) {
    try {
      const backup = JSON.parse(await file.text());
      const result = await apiRequest('/api/backup', {
        method: 'POST', body: JSON.stringify({action: 'restore', backup}),
      });
      discovery = result.discovery || discovery;
      showToast(result.message);
      await loadApiState();
    } catch (error) {
      showToast(error instanceof SyntaxError ? '备份文件不是有效 JSON' : error.message, 'error');
    } finally {
      backupFile.value = '';
    }
  }

  async function loadApiState() {
    try {
      const state = await apiRequest('/api/state');
      discovery = state.discovery;
      apiTopics = state.topics || [];
      renderAutomationTopicSummary();
      sharedReferenceMinimum.value = String(state.shared_reference_minimum || 2);
      highlyCitedMinimum.value = String(state.highly_cited_minimum || 50);
      reviewCategories = (state.categories || reviewCategories).map(category => ({
        ...category, label: displayCategoryLabel(category.label),
      }));
      apiGraphRevision = state.graph_revision || apiGraphRevision;
      renderHealth(state.health);
      renderTasks(state.tasks);
      renderClassificationReview(state.classification_review);
      renderDiscoveryLog(state.discovery_log);
      serviceNotice.hidden = true;
      renderDiscovery();
    } catch (_error) {
      serviceNotice.hidden = false;
    }
  }

  async function pollApiState() {
    if (apiStatePollBusy) return;
    apiStatePollBusy = true;
    try {
      const state = await apiRequest('/api/state');
      if (apiGraphRevision && state.graph_revision && state.graph_revision !== apiGraphRevision) {
        window.location.reload();
        return;
      }
      apiGraphRevision = state.graph_revision || apiGraphRevision;
      renderTasks(state.tasks);
      renderClassificationReview(state.classification_review);
      renderDiscoveryLog(state.discovery_log);
    } catch (_error) {
      // The next poll retries; transient background-task overlap is expected.
    } finally {
      apiStatePollBusy = false;
    }
  }

  function updateSearch(value) {
    searchTerm = normalizeSearch(value);
    graphSearchIndex = 0;
    clearSearch.hidden = !searchTerm;
    render();
  }

  function installPaneResizer(resizer, cssVariable, storageKey, min, max) {
    let dragging = false;
    const update = clientX => {
      const shellRect = document.querySelector('.app-shell').getBoundingClientRect();
      const value = cssVariable === '--candidate-list-width'
        ? clientX - shellRect.left - document.querySelector('.app-sidebar').getBoundingClientRect().width
        : shellRect.right - clientX;
      const bounded = Math.max(min, Math.min(max, value));
      document.documentElement.style.setProperty(cssVariable, `${bounded}px`);
      try { localStorage.setItem(storageKey, String(bounded)); } catch (_error) { /* optional */ }
    };
    resizer.addEventListener('pointerdown', event => {
      dragging = true;
      resizer.setPointerCapture(event.pointerId);
    });
    resizer.addEventListener('pointermove', event => { if (dragging) update(event.clientX); });
    resizer.addEventListener('pointerup', event => {
      dragging = false;
      resizer.releasePointerCapture(event.pointerId);
    });
    resizer.addEventListener('keydown', event => {
      if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
      event.preventDefault();
      const current = parseFloat(getComputedStyle(document.documentElement).getPropertyValue(cssVariable)) || min;
      const delta = event.key === 'ArrowLeft' ? -16 : 16;
      const next = cssVariable === '--candidate-list-width' ? current + delta : current - delta;
      const bounded = Math.max(min, Math.min(max, next));
      document.documentElement.style.setProperty(cssVariable, `${bounded}px`);
      try { localStorage.setItem(storageKey, String(bounded)); } catch (_error) { /* optional */ }
    });
    try {
      const saved = Number(localStorage.getItem(storageKey));
      if (Number.isFinite(saved) && saved >= min && saved <= max) {
        document.documentElement.style.setProperty(cssVariable, `${saved}px`);
      }
    } catch (_error) { /* optional */ }
  }

  function commandCatalog() {
    return [
      {label: '打开论文图谱', detail: '⌘1', run: () => activateView('graph')},
      {label: '打开待审核', detail: '⌘2', run: () => activateView('discovery')},
      {label: '打开自动化', detail: '⌘3', run: () => activateView('automation')},
      {label: '打开系统状态', detail: '⌘4', run: () => activateView('system')},
      {label: '发现论文', detail: '待审核', run: () => { activateView('discovery'); openDiscoverySheet(); }},
      {label: '检查系统', detail: '系统状态', run: () => { activateView('system'); runDiagnostics(); }},
      ...graph.nodes.slice(0, 120).map(node => ({label: node.title, detail: `${node.year || '—'} · 论文`, run: () => { activateView('graph'); selectNode(node.id); }})),
    ];
  }

  function renderCommands() {
    const query = normalizeSearch(commandSearch.value);
    commandItems = commandCatalog().filter(item => !query || normalizeSearch(`${item.label} ${item.detail}`).includes(query)).slice(0, 18);
    activeCommandIndex = Math.max(0, Math.min(activeCommandIndex, Math.max(0, commandItems.length - 1)));
    commandResults.replaceChildren(...commandItems.map((item, index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'command-item';
      button.classList.toggle('active', index === activeCommandIndex);
      const marker = document.createElement('strong');
      marker.textContent = item.detail === '论文' ? '●' : '⌘';
      const label = document.createElement('strong');
      label.textContent = item.label;
      const detail = document.createElement('span');
      detail.textContent = item.detail;
      button.append(marker, label, detail);
      button.addEventListener('click', () => { closeCommandPalette(); item.run(); });
      return button;
    }));
  }

  function openCommandPalette() {
    commandPalette.hidden = false;
    commandBackdrop.hidden = false;
    commandSearch.value = '';
    activeCommandIndex = 0;
    renderCommands();
    requestAnimationFrame(() => commandSearch.focus());
  }

  function closeCommandPalette() {
    commandPalette.hidden = true;
    commandBackdrop.hidden = true;
  }

  function paperUrl(node) {
    const encodedPath = node.path.split('/').map(encodeURIComponent).join('/');
    return window.location.protocol === 'file:' ? `../../${encodedPath}` : `/papers/${encodedPath}`;
  }

  function showPaperDetail(node) {
    detailReturnFocus = document.activeElement;
    paperDetail.hidden = false;
    detailBackdrop.hidden = false;
    detailContent.hidden = false;
    paperDetail.scrollTop = 0;
    document.body.classList.add('detail-open');
    detailTitle.textContent = node.title;
    detailMeta.textContent = `${node.year ?? '年份未知'} · ${displayCategoryLabel(node.category.replace(/^\d+_/, ''))}${node.is_main ? ' · 类别主节点' : ''}`;
    detailAuthors.textContent = node.authors ? `作者：${node.authors}` : '作者：未从 PDF 中可靠提取';
    detailAbstract.textContent = node.abstract || '未从 PDF 中提取到结构化摘要。';
    detailMainBadge.hidden = !node.is_main;
    detailPdf.href = paperUrl(node);
    detailPdf.setAttribute('aria-label', `打开 ${node.title} 的本地 PDF`);
    removeGraphNodeButton.dataset.nodeId = node.id;
    removeGraphNodeButton.dataset.nodeTitle = node.title;
    requestAnimationFrame(() => detailClose.focus({preventScroll: true}));
  }

  function clearPaperDetail() {
    paperDetail.hidden = true;
    detailBackdrop.hidden = true;
    document.body.classList.remove('detail-open');
    detailMainBadge.hidden = true;
    delete removeGraphNodeButton.dataset.nodeId;
    delete removeGraphNodeButton.dataset.nodeTitle;
  }

  async function removeGraphNode() {
    const id = removeGraphNodeButton.dataset.nodeId;
    const title = removeGraphNodeButton.dataset.nodeTitle;
    if (!id) return;
    if (!window.confirm(`确定将“${title}”从论文图谱移出吗？\n\nPDF 不会被删除，而会保存在论文库的可恢复归档中。`)) return;
    removeGraphNodeButton.disabled = true;
    removeGraphNodeButton.querySelector('span').textContent = '正在移出…';
    try {
      const result = await apiRequest('/api/graph/node/remove', {
        method: 'POST', body: JSON.stringify({id}),
      });
      showToast(result.message);
      clearPaperDetail();
      setTimeout(() => window.location.reload(), 500);
    } catch (error) {
      showToast(error.message, 'error');
      removeGraphNodeButton.disabled = false;
      removeGraphNodeButton.querySelector('span').textContent = '移出图谱';
    }
  }

  function closePaperDetail() {
    clearPaperDetail();
    render();
    (detailReturnFocus?.isConnected ? detailReturnFocus : nodesById[selectedNode]?.element)?.focus({preventScroll: true});
    detailReturnFocus = null;
  }

  function selectNode(nodeId) {
    const node = nodesById[nodeId];
    if (!node) return;
    hideTooltip();
    selectedNode = nodeId;
    render();
  }

  function openNodeDetail(nodeId) {
    const node = nodesById[nodeId];
    if (!node) return;
    selectNode(nodeId);
    showPaperDetail(node);
  }

  function showTooltip(node) {
    if (node.id === selectedNode) {
      hideTooltip();
      return;
    }
    const panel = document.querySelector('.graph-stage');
    const panelBox = panel.getBoundingClientRect();
    const point = svg.createSVGPoint();
    point.x = node.position.x;
    point.y = node.position.y;
    const screen = point.matrixTransform(svg.getScreenCTM());
    tooltip.textContent = `${node.title} · ${node.year} · 被库内引用 ${node.citation_count} 次${node.is_main ? ' · 类别主节点' : ''}`;
    tooltip.style.display = 'block';
    const width = tooltip.offsetWidth;
    const height = tooltip.offsetHeight;
    tooltip.style.left = `${Math.max(8, Math.min(screen.x - panelBox.left + 12, panelBox.width - width - 8))}px`;
    tooltip.style.top = `${Math.max(8, Math.min(screen.y - panelBox.top - height - 10, panelBox.height - height - 8))}px`;
  }

  function hideTooltip() {
    tooltip.style.display = 'none';
  }

  renderTopicTemplates();
  renderAutomationTopicSummary();
  renderActivityTimeline();
  [paperDetail, discoverySheet, topicsDialog, releaseNotesDialog, logsDialog, commandPalette].forEach(installFocusTrap);
  installPaneResizer(graphResizer, '--inspector-width', 'paper-atlas-inspector-width', 280, 480);
  installPaneResizer(reviewResizer, '--candidate-list-width', 'paper-atlas-candidate-width', 280, 520);
  detailClose.addEventListener('click', closePaperDetail);
  detailBackdrop.addEventListener('click', closePaperDetail);
  removeGraphNodeButton.addEventListener('click', removeGraphNode);
  manageTopics.addEventListener('click', openTopicsDialog);
  discoveryManageTopics.addEventListener('click', () => {
    closeDiscoverySheet();
    openTopicsDialog();
  });
  openDiscoverySheetButton.addEventListener('click', openDiscoverySheet);
  discoverySheetClose.addEventListener('click', closeDiscoverySheet);
  discoverySheetBackdrop.addEventListener('click', closeDiscoverySheet);
  runDiscoveryButton.addEventListener('click', () => toggleDiscoveryMode('arxiv'));
  runHighlyCitedButton.addEventListener('click', () => toggleDiscoveryMode('highly_cited'));
  runSharedDiscoveryButton.addEventListener('click', () => toggleDiscoveryMode('shared'));
  runSelectedDiscoveryButton.addEventListener('click', () => runDiscoveryNow([...selectedDiscoveryModes]));
  clearCandidatesButton.addEventListener('click', clearCandidates);
  rebuildGraphButton.addEventListener('click', rebuildGraph);
  runDiagnosticsButton.addEventListener('click', runDiagnostics);
  openRuntimeLogsButton.addEventListener('click', openRuntimeLogs);
  logsClose.addEventListener('click', closeRuntimeLogs);
  logsBackdrop.addEventListener('click', closeRuntimeLogs);
  refreshLogsButton.addEventListener('click', loadRuntimeLogs);
  copyLogButton.addEventListener('click', copyCurrentLog);
  copyDiagnosticsButton.addEventListener('click', copyDiagnostics);
  saveTasksButton.addEventListener('click', saveTasks);
  exportBackupButton.addEventListener('click', exportBackup);
  importBackupButton.addEventListener('click', () => backupFile.click());
  backupFile.addEventListener('change', () => {
    if (backupFile.files?.[0]) restoreBackup(backupFile.files[0]);
  });
  topicsClose.addEventListener('click', closeTopicsDialog);
  topicsBackdrop.addEventListener('click', closeTopicsDialog);
  versionHistoryButton.addEventListener('click', openReleaseNotes);
  releaseNotesClose.addEventListener('click', closeReleaseNotes);
  releaseNotesBackdrop.addEventListener('click', closeReleaseNotes);
  addTopicButton.addEventListener('click', () => {
    const row = topicRow({enabled: true, max_results: 10});
    topicsList.appendChild(row);
    row.querySelector('.topic-label').focus();
  });
  saveTopicsButton.addEventListener('click', () => saveTopics(false));
  saveAndDiscoverButton.addEventListener('click', () => saveTopics(true));
  graphSearchPrev.addEventListener('click', () => stepGraphSearch(-1));
  graphSearchNext.addEventListener('click', () => stepGraphSearch(1));
  toggleGraphInspector.addEventListener('click', () => {
    const hidden = graphWorkspace.classList.toggle('inspector-hidden');
    toggleGraphInspector.classList.toggle('active', !hidden);
    toggleGraphInspector.setAttribute('aria-pressed', String(!hidden));
    try { localStorage.setItem('paper-atlas-inspector-hidden', String(hidden)); } catch (_error) { /* optional */ }
  });
  graphInspectorPreview.addEventListener('click', () => {
    if (graphInspectorPreview.dataset.nodeId) openNodeDetail(graphInspectorPreview.dataset.nodeId);
  });
  graphInspectorOpenPdf.addEventListener('click', () => {
    const node = nodesById[graphInspectorOpenPdf.dataset.nodeId];
    if (node) window.open(paperUrl(node), '_blank', 'noopener');
  });
  document.querySelectorAll('.relation-tab').forEach(tab => tab.addEventListener('click', () => {
    const relation = tab.dataset.relationTab;
    document.querySelectorAll('.relation-tab').forEach(item => {
      const active = item === tab;
      item.classList.toggle('active', active);
      item.setAttribute('aria-selected', String(active));
    });
    inspectorOutgoingList.hidden = relation !== 'outgoing';
    inspectorIncomingList.hidden = relation !== 'incoming';
  }));
  document.querySelector('.relation-tab[data-relation-tab="outgoing"]')?.setAttribute('aria-controls', 'inspector-outgoing-list');
  document.querySelector('.relation-tab[data-relation-tab="incoming"]')?.setAttribute('aria-controls', 'inspector-incoming-list');
  sidebarCollapse.addEventListener('click', () => {
    const collapsed = document.querySelector('.app-shell').classList.toggle('sidebar-collapsed');
    sidebarCollapse.setAttribute('aria-label', collapsed ? '展开侧栏' : '折叠侧栏');
    try { localStorage.setItem('paper-atlas-sidebar-collapsed', String(collapsed)); } catch (_error) { /* optional */ }
  });
  batchSelectAll.addEventListener('click', () => {
    visibleCandidateIds.forEach(id => selectedCandidateIds.add(id));
    renderDiscovery();
  });
  batchClear.addEventListener('click', () => {
    selectedCandidateIds.clear();
    renderDiscovery();
  });
  batchDismiss.addEventListener('click', dismissSelectedCandidates);
  activityCenterClose.addEventListener('click', () => { activityCenter.hidden = true; });
  commandBackdrop.addEventListener('click', closeCommandPalette);
  commandSearch.addEventListener('input', () => { activeCommandIndex = 0; renderCommands(); });
  commandSearch.addEventListener('keydown', event => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      const direction = event.key === 'ArrowDown' ? 1 : -1;
      activeCommandIndex = (activeCommandIndex + direction + Math.max(1, commandItems.length)) % Math.max(1, commandItems.length);
      renderCommands();
    } else if (event.key === 'Enter' && commandItems[activeCommandIndex]) {
      event.preventDefault();
      const item = commandItems[activeCommandIndex];
      closeCommandPalette();
      item.run();
    }
  });
  document.addEventListener('keydown', event => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      openCommandPalette();
      return;
    }
    if ((event.metaKey || event.ctrlKey) && ['1', '2', '3', '4'].includes(event.key)) {
      event.preventDefault();
      activateView({1: 'graph', 2: 'discovery', 3: 'automation', 4: 'system'}[event.key]);
      return;
    }
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'f') {
      event.preventDefault();
      paperSearch.focus();
      return;
    }
    if (event.key === ' ' && activeView === 'graph' && selectedNode && !['INPUT', 'SELECT', 'BUTTON', 'TEXTAREA'].includes(document.activeElement?.tagName)) {
      event.preventDefault();
      openNodeDetail(selectedNode);
      return;
    }
    if (event.key !== 'Escape') return;
    if (!commandPalette.hidden) closeCommandPalette();
    else if (!discoverySheet.hidden) closeDiscoverySheet();
    else if (!logsDialog.hidden) closeRuntimeLogs();
    else if (!releaseNotesDialog.hidden) closeReleaseNotes();
    else if (!topicsDialog.hidden) closeTopicsDialog();
    else if (!paperDetail.hidden) closePaperDetail();
  });
  paperSearch.addEventListener('input', event => updateSearch(event.target.value));
  clearSearch.addEventListener('click', () => {
    paperSearch.value = '';
    paperSearch.focus();
    updateSearch('');
  });
  candidateSourceFilter.addEventListener('change', event => {
    selectDiscoverySource(event.target.value || 'all');
    renderDiscovery();
  });
  candidateCategoryFilter.addEventListener('change', event => {
    discoveryCategory = event.target.value || 'all';
    renderDiscovery();
  });

  viewButtons.forEach(button => {
    button.addEventListener('click', () => activateView(button.dataset.view));
  });

  let resetFeedbackTimer = null;
  resetViewButton.addEventListener('click', () => {
    selectedNode = null;
    clearPaperDetail();
    render();
    resetViewButton.classList.remove('is-confirmed');
    void resetViewButton.offsetWidth;
    resetViewButton.classList.add('is-confirmed');
    resetViewLabel.textContent = '已重置';
    showToast('图谱视图已重置');
    if (resetFeedbackTimer) clearTimeout(resetFeedbackTimer);
    resetFeedbackTimer = setTimeout(() => {
      resetViewButton.classList.remove('is-confirmed');
      resetViewLabel.textContent = '重置视图';
    }, 1500);
  });

  svg.addEventListener('click', event => {
    if (!event.target.closest('.node')) {
      selectedNode = null;
      clearPaperDetail();
      render();
    }
  });

  let initialView = 'graph';
  try { initialView = sessionStorage.getItem('paper-atlas-view') || 'graph'; } catch (_error) { /* optional */ }
  try {
    document.querySelector('.app-shell').classList.toggle('sidebar-collapsed', localStorage.getItem('paper-atlas-sidebar-collapsed') === 'true');
    const inspectorHidden = localStorage.getItem('paper-atlas-inspector-hidden') === 'true';
    graphWorkspace.classList.toggle('inspector-hidden', inspectorHidden);
    toggleGraphInspector.classList.toggle('active', !inspectorHidden);
    toggleGraphInspector.setAttribute('aria-pressed', String(!inspectorHidden));
  } catch (_error) { /* optional */ }
  activateView(initialView, false);
  renderDiscovery();
  loadApiState();
  setInterval(pollApiState, 60000);
})();
