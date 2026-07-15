(() => {
  const graph = window.PAPER_GRAPH;
  if (!graph) {
    document.getElementById('graph-summary').textContent = '未找到 web/data/graph-data.js，请先运行 make build。';
    return;
  }

  const svg = document.getElementById('graph-svg');
  const edgeLayer = document.getElementById('edge-layer');
  const nodeLayer = document.getElementById('node-layer');
  const tooltip = document.getElementById('tooltip');
  const detail = document.getElementById('selection-detail');
  const categorySelect = document.getElementById('category-select');
  const summary = document.getElementById('graph-summary');
  const ns = 'http://www.w3.org/2000/svg';

  const nodesById = Object.fromEntries(graph.nodes.map(node => [node.id, node]));
  const categoryById = Object.fromEntries(graph.categories.map((category, index) => [category.id, {...category, index}]));
  const allEdges = graph.edges.citation.map((edge, index) => ({...edge, type: 'citation', id: `citation-${index}`}));
  const yearMin = graph.metadata.year_min;
  const yearMax = graph.metadata.year_max;
  const yearSpan = Math.max(1, yearMax - yearMin);
  const NODE_RADIUS_MIN = 5.5;
  const NODE_RADIUS_MAX = 15;
  const maxCitationCount = Math.max(1, ...graph.nodes.map(node => node.citation_count));

  let rotationX = 0;
  let rotationY = 0;
  let selectedNode = null;
  let activeCategory = null;
  let dragging = false;
  let moved = false;
  let lastPointer = null;
  let rotationAnimation = null;

  summary.textContent = `${graph.metadata.paper_files} PDFs · ${graph.metadata.unique_papers} 篇唯一论文 · ${graph.categories.length} 类`;

  document.getElementById('year-inner').textContent = String(yearMin);
  document.getElementById('year-middle').textContent = String(Math.round((yearMin + yearMax) / 2));
  document.getElementById('year-outer').textContent = String(yearMax);

  graph.categories.forEach(category => {
    const option = document.createElement('option');
    option.value = category.id;
    option.textContent = `${category.label}（${category.paper_count}）`;
    categorySelect.appendChild(option);
  });

  const grouped = graph.nodes.reduce((result, node) => {
    (result[node.category] ??= []).push(node);
    return result;
  }, {});

  graph.categories.forEach((category, categoryIndex) => {
    const group = [...grouped[category.id]].sort((a, b) => (a.year - b.year) || a.title.localeCompare(b.title));
    const sector = (Math.PI * 2 * categoryIndex / graph.categories.length) - 0.55;
    group.forEach((node, index) => {
      const radius = 72 + ((node.year - yearMin) / yearSpan) * 205;
      const spread = (index - (group.length - 1) / 2) * 0.13;
      let x = Math.cos(sector + spread) * 0.82;
      let y = Math.sin(sector + spread) * 0.68;
      let z = 0;
      const length = Math.hypot(x, y, z) || 1;
      node.base = {x: x / length * radius, y: y / length * radius, z: z / length * radius};

      const groupElement = document.createElementNS(ns, 'g');
      groupElement.setAttribute('class', 'node');
      groupElement.dataset.node = node.id;

      const mark = document.createElementNS(ns, 'circle');
      mark.setAttribute('class', 'node-mark');
      node.radius = NODE_RADIUS_MIN + Math.sqrt(node.citation_count / maxCitationCount) * (NODE_RADIUS_MAX - NODE_RADIUS_MIN);
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
        if (!moved) focusNode(node.id);
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

  function rotate(point) {
    const cosY = Math.cos(rotationY);
    const sinY = Math.sin(rotationY);
    const cosX = Math.cos(rotationX);
    const sinX = Math.sin(rotationX);
    const x1 = point.x * cosY + point.z * sinY;
    const z1 = -point.x * sinY + point.z * cosY;
    return {x: x1, y: point.y * cosX - z1 * sinX, z: point.y * sinX + z1 * cosX};
  }

  function project(point) {
    const scale = 1 + point.z / 980;
    return {x: 480 + point.x * scale, y: 340 + point.y * scale, z: point.z, scale};
  }

  function connectedNodes(nodeId) {
    const connected = new Set([nodeId]);
    allEdges.forEach(edge => {
      if (edge.source === nodeId) connected.add(edge.target);
      if (edge.target === nodeId) connected.add(edge.source);
    });
    return connected;
  }

  function shouldFocusEdge(edge) {
    if (selectedNode) return edge.source === selectedNode || edge.target === selectedNode;
    if (activeCategory) {
      return nodesById[edge.source].category === activeCategory && nodesById[edge.target].category === activeCategory;
    }
    return false;
  }

  function render() {
    graph.nodes.forEach(node => {
      node.position = project(rotate(node.base));
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
      const targetOffset = targetNode.radius + 7;
      const start = {
        x: source.x + dx / distance * sourceOffset,
        y: source.y + dy / distance * sourceOffset,
      };
      const end = {
        x: target.x - dx / distance * targetOffset,
        y: target.y - dy / distance * targetOffset,
      };
      const bend = 0.027;
      const middleX = (start.x + end.x) / 2 + (end.y - start.y) * bend;
      const middleY = (start.y + end.y) / 2 - (end.x - start.x) * bend;
      edge.element.setAttribute(
        'd',
        `M ${start.x.toFixed(1)} ${start.y.toFixed(1)} Q ${middleX.toFixed(1)} ${middleY.toFixed(1)} ${end.x.toFixed(1)} ${end.y.toFixed(1)}`,
      );
      const focused = shouldFocusEdge(edge);
      edge.element.classList.toggle('focused', focused);
      edge.element.style.opacity = (selectedNode || activeCategory) && !focused ? '0.035' : '1';
    });

    const neighborhood = selectedNode ? connectedNodes(selectedNode) : null;
    [...graph.nodes].sort((a, b) => a.position.z - b.position.z).forEach(node => {
      node.element.setAttribute(
        'transform',
        `translate(${node.position.x.toFixed(1)} ${node.position.y.toFixed(1)}) scale(${node.position.scale.toFixed(3)})`,
      );
      node.element.classList.toggle('selected', node.id === selectedNode);
      node.element.classList.toggle('back', node.position.z < -35 && !selectedNode && !activeCategory);
      const dimForNode = neighborhood && !neighborhood.has(node.id);
      const dimForCategory = activeCategory && node.category !== activeCategory;
      node.element.classList.toggle('dimmed', Boolean(dimForNode || dimForCategory));
      node.labelElement.style.display = node.id === selectedNode ? '' : 'none';
      nodeLayer.appendChild(node.element);
    });
  }

  function nearestAngle(target, current) {
    while (target - current > Math.PI) target -= Math.PI * 2;
    while (target - current < -Math.PI) target += Math.PI * 2;
    return target;
  }

  function rotateToNode(node) {
    if (rotationAnimation) cancelAnimationFrame(rotationAnimation);
    const point = node.base;
    let targetY = Math.atan2(-point.x, point.z);
    const cosY = Math.cos(targetY);
    const sinY = Math.sin(targetY);
    const frontZ = -point.x * sinY + point.z * cosY;
    let targetX = Math.atan2(point.y, frontZ);
    targetY = nearestAngle(targetY, rotationY);
    targetX = nearestAngle(targetX, rotationX);

    const startX = rotationX;
    const startY = rotationY;
    const startTime = performance.now();
    const duration = matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 650;

    function step(now) {
      const progress = duration === 0 ? 1 : Math.min(1, (now - startTime) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      rotationX = startX + (targetX - startX) * eased;
      rotationY = startY + (targetY - startY) * eased;
      render();
      if (progress < 1) rotationAnimation = requestAnimationFrame(step);
    }
    rotationAnimation = requestAnimationFrame(step);
  }

  function focusNode(nodeId) {
    selectedNode = selectedNode === nodeId ? null : nodeId;
    if (selectedNode) {
      const node = nodesById[selectedNode];
      activeCategory = null;
      categorySelect.value = '';
      rotateToNode(node);
      const outgoing = graph.edges.citation.filter(edge => edge.source === node.id).length;
      const incoming = graph.edges.citation.filter(edge => edge.target === node.id).length;
      detail.textContent = `${node.title} · ${node.year} · ${node.category.replace(/^\d+_/, '')} · 引用他文 ${outgoing} / 被库内引用 ${incoming}${node.is_main ? ' · 类别主节点' : ''}`;
    } else {
      detail.textContent = '点击节点查看关系；拖动球体可自由旋转。';
      render();
    }
  }

  function activateCategory(categoryId) {
    activeCategory = activeCategory === categoryId ? null : categoryId;
    selectedNode = null;
    if (activeCategory) {
      const category = categoryById[activeCategory];
      const mainNode = nodesById[category.main_node];
      rotateToNode(mainNode);
      detail.textContent = `${category.label} · ${category.paper_count} 篇 · 主节点：${mainNode.title}（被库内引用 ${mainNode.citation_count} 次）`;
    } else {
      detail.textContent = '点击节点查看关系；拖动球体可自由旋转。';
      render();
    }
  }

  function showTooltip(node) {
    const panel = document.querySelector('.graph-panel');
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

  document.getElementById('show-citations').addEventListener('change', event => {
    allEdges.filter(edge => edge.type === 'citation').forEach(edge => {
      edge.element.style.display = event.target.checked ? '' : 'none';
    });
  });

  categorySelect.addEventListener('change', event => activateCategory(event.target.value || null));

  document.getElementById('reset-view').addEventListener('click', () => {
    selectedNode = null;
    activeCategory = null;
    rotationX = 0;
    rotationY = 0;
    categorySelect.value = '';
    detail.textContent = '点击节点查看关系；拖动球体可自由旋转。';
    render();
  });

  svg.addEventListener('pointerdown', event => {
    if (rotationAnimation) cancelAnimationFrame(rotationAnimation);
    dragging = true;
    moved = false;
    lastPointer = {x: event.clientX, y: event.clientY};
    svg.setPointerCapture(event.pointerId);
    svg.classList.add('dragging');
  });

  svg.addEventListener('pointermove', event => {
    if (!dragging) return;
    const dx = event.clientX - lastPointer.x;
    const dy = event.clientY - lastPointer.y;
    if (Math.abs(dx) + Math.abs(dy) > 2) moved = true;
    rotationY += dx * 0.008;
    rotationX -= dy * 0.008;
    lastPointer = {x: event.clientX, y: event.clientY};
    render();
  });

  svg.addEventListener('pointerup', event => {
    dragging = false;
    svg.releasePointerCapture(event.pointerId);
    svg.classList.remove('dragging');
  });

  svg.addEventListener('pointercancel', () => {
    dragging = false;
    svg.classList.remove('dragging');
  });

  svg.addEventListener('click', event => {
    if (event.target === svg) {
      selectedNode = null;
      activeCategory = null;
      categorySelect.value = '';
      detail.textContent = '点击节点查看关系；拖动球体可自由旋转。';
      render();
    }
  });

  render();
})();
