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
  const detailOutgoing = document.getElementById('detail-outgoing');
  const detailIncoming = document.getElementById('detail-incoming');
  const detailMainBadge = document.getElementById('detail-main-badge');
  const outgoingCount = document.getElementById('outgoing-count');
  const incomingCount = document.getElementById('incoming-count');
  const paperSearch = document.getElementById('paper-search');
  const clearSearch = document.getElementById('clear-search');
  const searchStatus = document.getElementById('search-status');
  const discoveryList = document.getElementById('discovery-list');
  const discoveryEmpty = document.getElementById('discovery-empty');
  const discoveryCount = document.getElementById('discovery-count');
  const discoveryUpdated = document.getElementById('discovery-updated');
  const manageTopics = document.getElementById('manage-topics');
  const runDiscoveryButton = document.getElementById('run-discovery');
  const runHighlyCitedButton = document.getElementById('run-highly-cited');
  const runSharedDiscoveryButton = document.getElementById('run-shared-discovery');
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
  const rebuildGraphButton = document.getElementById('rebuild-graph');
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
      label: '模型架构与训练优化',
      keywords: ['transformer architecture', 'optimizer', 'normalization', 'training method', 'distillation'],
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
      label: '通用智能体与自主学习',
      keywords: ['AI agent', 'research agent', 'tool use', 'self-play', 'autonomous search'],
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
  ].map(template => ({enabled: true, exclude_keywords: [], max_results: 5, ...template}));

  let selectedNode = null;
  let searchTerm = '';
  let discoverySource = 'all';
  let selectedCandidateId = null;
  let activeView = 'graph';
  let apiTopics = (discovery.topics || []).map(topic => ({enabled: true, max_results: 10, ...topic}));
  let reviewCategories = graph.categories.map(category => ({id: category.id, label: category.label}));
  let toastTimer = null;
  let discoveryBusyTimer = null;
  let discoveryHighlightTimer = null;
  let discoveryBusyStarted = 0;
  let highlightedCandidateIds = new Set();
  let apiHealth = null;
  let apiTasks = {supported: false, tasks: []};
  const topicTemplateButtons = new Map();
  const nativeRequests = new Map();

  window.__paperAtlasNativeResolve = (id, encodedPayload) => {
    const pending = nativeRequests.get(id);
    if (!pending) return;
    nativeRequests.delete(id);
    clearTimeout(pending.timeout);
    try {
      const bytes = Uint8Array.from(atob(encodedPayload), character => character.charCodeAt(0));
      const payload = JSON.parse(new TextDecoder().decode(bytes));
      if (payload.error) pending.reject(new Error(payload.error));
      else pending.resolve(payload);
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

  function nodeMatchesSearch(node) {
    if (!searchTerm) return true;
    return normalizeSearch([node.title, node.authors, node.abstract, node.category, node.year].join(' ')).includes(searchTerm);
  }

  metricPapers.textContent = String(graph.metadata.unique_papers);
  metricCitations.textContent = String(graph.metadata.citation_edges);
  metricCategories.textContent = String(graph.categories.length);
  metricYears.textContent = `${yearMin}–${yearMax}`;

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

  const timelineOffsets = [
    [0, 0], [-18, -14], [18, 14], [-18, 14], [18, -14],
    [-36, 0], [36, 0], [-36, -15], [36, 15], [0, -17], [0, 17],
  ];

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
      label.textContent = category.label;
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
      label.textContent = String(year);
      timelineGrid.append(rule, label);
    }
  }

  function assignTimelinePositions() {
    const laneHeight = (TIMELINE_BOTTOM - TIMELINE_TOP) / graph.categories.length;
    graph.categories.forEach((category, categoryIndex) => {
      const byYear = (grouped[category.id] || []).reduce((result, node) => {
        (result[node.year ?? yearMin] ??= []).push(node);
        return result;
      }, {});
      Object.values(byYear).forEach(nodes => {
        nodes.sort((a, b) => b.citation_count - a.citation_count || a.title.localeCompare(b.title));
        nodes.forEach((node, index) => {
          const offset = timelineOffsets[index % timelineOffsets.length];
          const overflowRing = Math.floor(index / timelineOffsets.length);
          node.timeline = {
            x: Math.max(TIMELINE_LEFT - 30, Math.min(TIMELINE_RIGHT + 12,
              timelineX(node.year) + offset[0] + overflowRing * 5)),
            y: TIMELINE_TOP + (categoryIndex + 0.5) * laneHeight + offset[1],
          };
        });
      });
    });
  }

  buildTimelineGrid();
  assignTimelinePositions();

  graph.categories.forEach((category, categoryIndex) => {
    const group = [...grouped[category.id]].sort((a, b) => ((a.year ?? yearMin) - (b.year ?? yearMin)) || a.title.localeCompare(b.title));
    group.forEach(node => {
      const groupElement = document.createElementNS(ns, 'g');
      groupElement.setAttribute('class', 'node');
      groupElement.dataset.node = node.id;
      groupElement.setAttribute('role', 'button');
      groupElement.setAttribute('tabindex', '0');
      groupElement.setAttribute('aria-label', `${node.title}，${node.year ?? '年份未知'}，被库内引用 ${node.citation_count} 次。单击查看引用关系，双击打开论文详情`);

      node.radius = NODE_RADIUS_MIN + Math.sqrt(node.citation_count / maxCitationCount) * (NODE_RADIUS_MAX - NODE_RADIUS_MIN);
      node.hitRadius = Math.max(16, node.radius + 5);
      const hitArea = document.createElementNS(ns, 'circle');
      hitArea.setAttribute('class', 'node-hit');
      hitArea.setAttribute('r', String(node.hitRadius));
      groupElement.appendChild(hitArea);

      const mark = document.createElementNS(ns, 'circle');
      mark.setAttribute('class', 'node-mark');
      mark.setAttribute('r', node.radius.toFixed(2));
      mark.style.fill = `var(--cat-${categoryIndex})`;
      groupElement.appendChild(mark);

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
      groupElement.addEventListener('dblclick', event => {
        event.preventDefault();
        event.stopPropagation();
        openNodeDetail(node.id);
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
      node.position = {x: node.timeline.x, y: node.timeline.y, z: 0, scale: 1};
    });

    allEdges.forEach(edge => {
      const sourceNode = nodesById[edge.source];
      const targetNode = nodesById[edge.target];
      const source = sourceNode.position;
      const target = targetNode.position;
      const dx = target.x - source.x;
      const dy = target.y - source.y;
      const distance = Math.hypot(dx, dy) || 1;
      const sourceOffset = sourceNode.radius + 3;
      const targetOffset = targetNode.radius + 3;
      const start = {
        x: source.x + dx / distance * sourceOffset,
        y: source.y + dy / distance * sourceOffset,
      };
      const end = {
        x: target.x - dx / distance * targetOffset,
        y: target.y - dy / distance * targetOffset,
      };
      const sameLane = sourceNode.category === targetNode.category;
      const curve = sameLane ? Math.min(42, 18 + Math.abs(dx) * 0.08) : 0;
      const controlY1 = sameLane ? start.y - curve : start.y;
      const controlY2 = sameLane ? end.y - curve : end.y;
      edge.element.setAttribute(
        'd',
        `M ${start.x.toFixed(1)} ${start.y.toFixed(1)} C ${(start.x + dx * 0.42).toFixed(1)} ${controlY1.toFixed(1)}, ${(end.x - dx * 0.42).toFixed(1)} ${controlY2.toFixed(1)}, ${end.x.toFixed(1)} ${end.y.toFixed(1)}`,
      );
      const focused = shouldFocusEdge(edge);
      edge.element.classList.toggle('focused', focused);
      edge.element.classList.toggle('outgoing', Boolean(selectedNode && edge.source === selectedNode));
      edge.element.classList.toggle('incoming', Boolean(selectedNode && edge.target === selectedNode));
      const searchMatch = !searchTerm || (nodeMatchesSearch(sourceNode) && nodeMatchesSearch(targetNode));
      const visible = focused;
      edge.element.style.display = visible && searchMatch ? '' : 'none';
      edge.element.style.opacity = focused ? '1' : selectedNode ? '0.035' : '0.16';
    });

    const neighborhood = selectedNode ? connectedNodes(selectedNode) : null;
    [...graph.nodes].sort((a, b) => a.position.z - b.position.z).forEach(node => {
      const referencedBySelected = Boolean(selectedNode && allEdges.some(edge => edge.source === selectedNode && edge.target === node.id));
      const citesSelected = Boolean(selectedNode && allEdges.some(edge => edge.source === node.id && edge.target === selectedNode));
      node.position.scale = node.id === selectedNode ? 1.12 : 1;
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
  }

  function candidateMatchesSearch(candidate) {
    if (!searchTerm) return true;
    const supportTitles = (candidate.supporting_papers || []).map(paper => paper.title).join(' ');
    return normalizeSearch([
      candidate.title,
      (candidate.authors || []).join(' '),
      candidate.abstract,
      candidate.reason,
      candidate.category_label,
      candidate.category_reason,
      (candidate.topics || []).join(' '),
      supportTitles,
    ].join(' ')).includes(searchTerm);
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
    versionHistoryButton.focus({preventScroll: true});
  }

  async function apiRequest(path, options = {}) {
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
        headers: {'Content-Type': 'application/json', ...(options.headers || {})},
      });
    } catch (_error) {
      throw new Error('应用管理功能未连接，请重新打开 Paper Atlas');
    }
    let payload = {};
    try { payload = await response.json(); } catch (_error) { /* handled below */ }
    if (!response.ok || payload.error) throw new Error(payload.error || '本地任务运行失败');
    return payload;
  }

  function suggestedCategory(candidate) {
    if (candidate.suggested_category) return candidate.suggested_category;
    const counts = {};
    (candidate.supporting_papers || []).forEach(paper => {
      if (paper.category) counts[paper.category] = (counts[paper.category] || 0) + 1;
    });
    return Object.entries(counts).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0]?.[0] || '';
  }

  async function reviewCandidate(candidate, action, categorySelectControl, article) {
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
      if (action === 'accept') {
        progress.textContent = `正在下载、校验并更新图谱 · ${minutes}:${seconds}`;
        if (acceptButton) acceptButton.textContent = '正在加入…';
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
          action === 'accept'
            ? `${candidate.title} 已归档，图谱正在更新`
            : `${candidate.title} 已从候选中移除`,
        );
      } catch (_error) {
        // The main request still reports the authoritative result.
      }
    };

    updateProgress();
    statusTimer = setInterval(updateProgress, 1000);
    if (action === 'accept') {
      commitPollTimer = setInterval(detectCommittedDecision, 1500);
    }
    try {
      const payload = await apiRequest('/api/candidates/action', {
        method: 'POST',
        body: JSON.stringify({id: candidate.id, action, category}),
      });
      discovery = payload.discovery;
      if (!commitDetected || payload.graph_updated === false) {
        showToast(payload.message, payload.graph_updated === false ? 'warning' : 'success');
      }
      if (action === 'accept') {
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
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'candidate-row';
    button.dataset.candidateId = candidate.id;
    button.classList.toggle('active', candidate.id === selectedCandidateId);
    button.classList.toggle('is-discovery-result', highlightedCandidateIds.has(candidate.id));
    button.setAttribute('aria-pressed', String(candidate.id === selectedCandidateId));

    const source = document.createElement('span');
    source.className = `candidate-row-source source-${(candidate.sources || [])[0] || 'unknown'}`;
    source.textContent = candidateSourceLabel((candidate.sources || [])[0] || '推荐');
    const title = document.createElement('strong');
    title.textContent = candidate.title;
    const category = document.createElement('span');
    category.className = 'candidate-row-category';
    category.textContent = candidate.category_label || '待确认类别';
    const meta = document.createElement('span');
    meta.className = 'candidate-row-meta';
    const citations = Number(candidate.cited_by_count);
    meta.textContent = `${candidate.year || '年份未知'}${Number.isFinite(citations) && citations > 0 ? ` · 被引 ${citations.toLocaleString('zh-CN')}` : ''}`;
    button.append(source, title, category, meta);
    button.addEventListener('click', () => {
      selectedCandidateId = candidate.id;
      renderDiscovery();
    });
    return button;
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
      const panel = document.createElement('section');
      panel.className = 'candidate-detail-panel';
      panel.dataset.panel = id;
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
    const ignore = document.createElement('button');
    ignore.type = 'button';
    ignore.className = 'candidate-action secondary-action';
    ignore.textContent = '忽略';
    ignore.addEventListener('click', () => reviewCandidate(candidate, 'reject', category, article));
    const accept = document.createElement('button');
    accept.type = 'button';
    accept.className = 'candidate-action primary-action';
    accept.textContent = '加入论文库';
    accept.addEventListener('click', () => reviewCandidate(candidate, 'accept', category, article));
    footer.append(category, ignore, accept);

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
    const visible = activeCandidates
      .filter(candidate => {
        const sourceMatch = discoverySource === 'all' || (candidate.sources || []).includes(discoverySource);
        return sourceMatch && candidateMatchesSearch(candidate);
      })
      .sort((a, b) => candidateTimestamp(b) - candidateTimestamp(a) || a.title.localeCompare(b.title));
    if (!visible.some(candidate => candidate.id === selectedCandidateId)) {
      selectedCandidateId = visible[0]?.id || null;
    }
    const selectedCandidate = visible.find(candidate => candidate.id === selectedCandidateId);
    discoveryList.replaceChildren(...visible.map(renderCandidateRow));
    discoveryEmpty.hidden = visible.length > 0;
    candidatePreviewEmpty.hidden = Boolean(selectedCandidate);
    candidatePreview.replaceChildren(selectedCandidate ? renderCandidate(selectedCandidate) : candidatePreviewEmpty);
    discoveryCount.textContent = String(activeCandidates.length);
    navDiscoveryCount.textContent = String(activeCandidates.length);
    navDiscoveryCount.hidden = activeCandidates.length === 0;
    if (discovery.metadata.updated_at) {
      const updated = new Date(discovery.metadata.updated_at);
      discoveryUpdated.textContent = Number.isNaN(updated.valueOf())
        ? '发现任务已运行'
        : `更新于 ${updated.toLocaleString('zh-CN', {month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit'})}`;
    }
    const graphMatches = graph.nodes.filter(nodeMatchesSearch).length;
    searchStatus.textContent = searchTerm
      ? `论文库 ${graphMatches} 篇 · 推荐 ${visible.length} 篇匹配`
      : `${visible.length} 篇候选`;
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
    const expectedSources = mode === 'topics'
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
    document.querySelectorAll('.filter-pill').forEach(item => {
      item.classList.toggle('active', item.dataset.source === source);
    });
  }

  function showDiscoveryOutcome(currentDiscovery, mode) {
    const summary = discoveryRunSummary(currentDiscovery, mode);
    const sourceLabel = mode === 'topics'
      ? '主题发现'
      : mode === 'shared' ? '共同引用' : mode === 'highly_cited' ? '领域高被引' : 'arXiv 搜索';
    selectDiscoverySource(
      mode === 'topics' ? 'all' : mode === 'shared' ? 'shared_reference' : mode === 'highly_cited' ? 'highly_cited' : 'arxiv_topic',
    );
    clearTimeout(discoveryHighlightTimer);
    highlightedCandidateIds = new Set(summary.ids);
    selectedCandidateId = summary.ids[0] || selectedCandidateId;
    discoveryResult.hidden = false;
    discoveryResult.dataset.tone = summary.found ? 'success' : 'empty';
    discoveryResultTitle.textContent = summary.found
      ? `${sourceLabel}找到 ${summary.found} 篇论文`
      : `${sourceLabel}没有找到符合条件的论文`;
    discoveryResultMeta.textContent = summary.found
      ? mode === 'topics'
        ? `arXiv ${summary.arxiv} 篇 · 高被引 ${summary.highlyCited} 篇 · 新增 ${summary.added} 篇；下方结果已高亮`
        : `其中新增 ${summary.added} 篇；下方对应结果已高亮`
      : mode === 'shared'
        ? '可以降低共同引用次数下限后再次计算'
        : mode === 'highly_cited'
          ? '可以增加搜索关键词，或降低配置中的最低被引次数'
          : mode === 'topics'
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
      <div class="topic-row-heading">
        <label class="topic-enabled"><input type="checkbox" ${topic.enabled === false ? '' : 'checked'}><span>启用</span></label>
        <button type="button" class="topic-remove" aria-label="删除这个搜索主题">删除</button>
      </div>
      <label>主题名称<input class="topic-label" type="text" maxlength="80" placeholder="例如：长上下文优化"></label>
      <label>搜索关键词<textarea class="topic-keywords" rows="2" placeholder="用逗号分隔，例如：long context, KV cache"></textarea></label>
      <label>排除词<textarea class="topic-excludes" rows="2" placeholder="可选，用逗号分隔"></textarea></label>
      <label>每天最多发现<input class="topic-maximum" type="number" min="1" max="50" value="${Number(topic.max_results) || 10}"></label>
    `;
    row.querySelector('.topic-label').value = topic.label || '';
    row.querySelector('.topic-keywords').value = (topic.keywords || []).join('，');
    row.querySelector('.topic-excludes').value = (topic.exclude_keywords || []).join('，');
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
    }));
  }

  function openTopicsDialog() {
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
  }

  function setDiscoveryBusy(busy, label = '正在搜索 arXiv…') {
    [runDiscoveryButton, runHighlyCitedButton, runSharedDiscoveryButton, clearCandidatesButton, saveTopicsButton, saveAndDiscoverButton, addTopicButton, ...topicTemplateButtons.values()].forEach(button => {
      button.disabled = busy;
    });
    sharedReferenceMinimum.disabled = busy;
    highlyCitedMinimum.disabled = busy;
    const isArxiv = label.includes('arXiv');
    const isHighlyCited = label.includes('高被引');
    const isShared = label.includes('共同引用');
    const isTopicDiscovery = label.includes('主题发现');
    runDiscoveryButton.textContent = busy && isArxiv ? '搜索中…' : '搜索 arXiv';
    runHighlyCitedButton.textContent = busy && isHighlyCited ? '搜索中…' : '领域高被引';
    runSharedDiscoveryButton.textContent = busy && isShared ? '计算中…' : '共同引用';
    clearInterval(discoveryBusyTimer);
    discoveryBusyTimer = null;
    discoveryProgress.hidden = !busy;
    if (!busy) return;
    discoveryResult.hidden = true;
    highlightedCandidateIds.clear();
    clearTimeout(discoveryHighlightTimer);
    discoveryBusyStarted = Date.now();
    discoveryProgressTitle.textContent = isTopicDiscovery
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
      discoveryProgressMeta.textContent = isTopicDiscovery
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
      if (runAfterSave) {
        closeTopicsDialog();
        const result = await apiRequest('/api/discover', {
          method: 'POST',
          body: JSON.stringify({mode: 'topics'}),
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
    const sharedMinimum = Number(sharedReferenceMinimum.value);
    const citationMinimum = Number(highlyCitedMinimum.value);
    if (mode === 'shared' && (!Number.isInteger(sharedMinimum) || sharedMinimum < 2 || sharedMinimum > 20)) {
      sharedReferenceMinimum.focus();
      showToast('共同引用次数下限需要是 2–20 之间的整数', 'error');
      return;
    }
    if (mode === 'highly_cited' && (!Number.isInteger(citationMinimum) || citationMinimum < 1 || citationMinimum > 1000000)) {
      highlyCitedMinimum.focus();
      showToast('高被引次数下限需要是 1–1,000,000 之间的整数', 'error');
      return;
    }
    runDiscoveryButton.closest('details')?.removeAttribute('open');
    setDiscoveryBusy(
      true,
      mode === 'shared' ? '正在计算共同引用…' : mode === 'highly_cited' ? '正在搜索领域高被引…' : '正在搜索 arXiv…',
    );
    try {
      const result = await apiRequest('/api/discover', {
        method: 'POST',
        body: JSON.stringify({
          mode,
          ...(mode === 'shared' ? {min_library_citations: sharedMinimum} : {}),
          ...(mode === 'highly_cited' ? {min_citations: citationMinimum} : {}),
        }),
      });
      discovery = result.discovery;
      showDiscoveryOutcome(discovery, mode);
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
    (apiHealth.issues || []).forEach(item => {
      const issue = document.createElement('article');
      issue.className = `health-issue health-${item.severity}`;
      const title = document.createElement('strong');
      title.textContent = item.title;
      const detail = document.createElement('span');
      detail.textContent = item.detail;
      issue.append(title, detail);
      healthIssues.appendChild(issue);
    });
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
      run.className = 'toolbar-action';
      run.textContent = '立即运行';
      run.addEventListener('click', () => runTaskNow(task.id, run));
      actions.appendChild(run);
      if (task.last_log) {
        const log = document.createElement('details');
        log.className = 'task-log';
        const summary = document.createElement('summary');
        const logLabel = document.createElement('span');
        logLabel.textContent = '运行日志';
        summary.appendChild(logLabel);
        const pre = document.createElement('pre');
        pre.textContent = task.last_log;
        log.append(summary, pre);
        actions.appendChild(log);
      }
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
      const state = await apiRequest('/api/state');
      if (state.health) renderHealth(state.health);
      if (state.discovery) {
        discovery = state.discovery;
        renderDiscovery();
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
      sharedReferenceMinimum.value = String(state.shared_reference_minimum || 2);
      highlyCitedMinimum.value = String(state.highly_cited_minimum || 50);
      reviewCategories = state.categories || reviewCategories;
      renderHealth(state.health);
      renderTasks(state.tasks);
      serviceNotice.hidden = true;
      renderDiscovery();
    } catch (_error) {
      serviceNotice.hidden = false;
    }
  }

  function updateSearch(value) {
    searchTerm = normalizeSearch(value);
    clearSearch.hidden = !searchTerm;
    render();
    renderDiscovery();
  }

  function paperUrl(node) {
    const encodedPath = node.path.split('/').map(encodeURIComponent).join('/');
    return window.location.protocol === 'file:' ? `../../${encodedPath}` : `/papers/${encodedPath}`;
  }

  function renderRelationList(container, relatedItems, emptyText) {
    container.replaceChildren();
    if (!relatedItems.length) {
      const item = document.createElement('li');
      item.className = 'empty-relation';
      item.textContent = emptyText;
      container.appendChild(item);
      return;
    }
    relatedItems
      .sort((a, b) => (a.node.year ?? 0) - (b.node.year ?? 0) || a.node.title.localeCompare(b.node.title))
      .forEach(({node, edge}) => {
        const item = document.createElement('li');
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'relation-button';
        button.textContent = `${node.year ?? '—'} · ${node.title}`;
        button.addEventListener('click', () => openNodeDetail(node.id));
        const confidence = document.createElement('span');
        confidence.className = `relation-confidence confidence-${edge.confidence || 'medium'}`;
        confidence.textContent = edge.confidence === 'high' ? '高可信' : '需核验';
        confidence.title = edge.evidence || '本地参考文献标题匹配';
        item.append(button, confidence);
        container.appendChild(item);
      });
  }

  function showPaperDetail(node) {
    const outgoingNodes = graph.edges.citation
      .filter(edge => edge.source === node.id)
      .map(edge => ({node: nodesById[edge.target], edge}));
    const incomingNodes = graph.edges.citation
      .filter(edge => edge.target === node.id)
      .map(edge => ({node: nodesById[edge.source], edge}));

    paperDetail.hidden = false;
    detailBackdrop.hidden = false;
    detailContent.hidden = false;
    paperDetail.scrollTop = 0;
    document.body.classList.add('detail-open');
    detailTitle.textContent = node.title;
    detailMeta.textContent = `${node.year ?? '年份未知'} · ${node.category.replace(/^\d+_/, '')}${node.is_main ? ' · 类别主节点' : ''}`;
    detailAuthors.textContent = node.authors ? `作者：${node.authors}` : '作者：未从 PDF 中可靠提取';
    detailAbstract.textContent = node.abstract || '未从 PDF 中提取到结构化摘要。';
    detailMainBadge.hidden = !node.is_main;
    outgoingCount.textContent = String(outgoingNodes.length);
    incomingCount.textContent = String(incomingNodes.length);
    detailPdf.href = paperUrl(node);
    detailPdf.setAttribute('aria-label', `打开 ${node.title} 的本地 PDF`);
    renderRelationList(detailOutgoing, outgoingNodes, '未检测到本文引用的库内论文');
    renderRelationList(detailIncoming, incomingNodes, '未检测到库内其他论文引用本文');
    requestAnimationFrame(() => detailClose.focus({preventScroll: true}));
  }

  function clearPaperDetail() {
    paperDetail.hidden = true;
    detailBackdrop.hidden = true;
    document.body.classList.remove('detail-open');
    detailMainBadge.hidden = true;
    outgoingCount.textContent = '0';
    incomingCount.textContent = '0';
    detailOutgoing.replaceChildren();
    detailIncoming.replaceChildren();
  }

  function closePaperDetail() {
    clearPaperDetail();
    render();
  }

  function selectNode(nodeId) {
    const node = nodesById[nodeId];
    if (!node) return;
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
  detailClose.addEventListener('click', closePaperDetail);
  detailBackdrop.addEventListener('click', closePaperDetail);
  manageTopics.addEventListener('click', openTopicsDialog);
  runDiscoveryButton.addEventListener('click', () => runDiscoveryNow('arxiv'));
  runHighlyCitedButton.addEventListener('click', () => runDiscoveryNow('highly_cited'));
  runSharedDiscoveryButton.addEventListener('click', () => runDiscoveryNow('shared'));
  clearCandidatesButton.addEventListener('click', clearCandidates);
  rebuildGraphButton.addEventListener('click', rebuildGraph);
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
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    const openLog = document.querySelector('.task-log[open]');
    if (openLog) openLog.removeAttribute('open');
    else if (!releaseNotesDialog.hidden) closeReleaseNotes();
    else if (!topicsDialog.hidden) closeTopicsDialog();
    else if (!paperDetail.hidden) closePaperDetail();
  });
  document.addEventListener('click', event => {
    document.querySelectorAll('.task-log[open]').forEach(log => {
      if (!log.contains(event.target)) log.removeAttribute('open');
    });
  });

  paperSearch.addEventListener('input', event => updateSearch(event.target.value));
  clearSearch.addEventListener('click', () => {
    paperSearch.value = '';
    paperSearch.focus();
    updateSearch('');
  });

  document.querySelectorAll('.filter-pill').forEach(button => {
    button.addEventListener('click', () => {
      selectDiscoverySource(button.dataset.source);
      renderDiscovery();
    });
  });

  viewButtons.forEach(button => {
    button.addEventListener('click', () => activateView(button.dataset.view));
  });

  document.getElementById('reset-view').addEventListener('click', () => {
    selectedNode = null;
    clearPaperDetail();
    render();
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
  activateView(initialView, false);
  renderDiscovery();
  loadApiState();
})();
