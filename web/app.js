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
  const categoryList = document.getElementById('category-list');
  const summary = document.getElementById('graph-summary');
  const ns = 'http://www.w3.org/2000/svg';

  const nodesById = Object.fromEntries(graph.nodes.map(node => [node.id, node]));
  const categoryById = Object.fromEntries(graph.categories.map((category, index) => [category.id, {...category, index}]));
  const allEdges = [
    ...graph.edges.citation.map((edge, index) => ({...edge, type: 'citation', id: `citation-${index}`})),
    ...graph.edges.time.map((edge, index) => ({...edge, type: 'time', id: `time-${index}`})),
  ];
  const yearMin = graph.metadata.year_min;
  const yearMax = graph.metadata.year_max;
  const yearSpan = Math.max(1, yearMax - yearMin);

  let rotationX = -0.18;
  let rotationY = 0.26;
  let selectedNode = null;
  let activeCategory = null;
  let dragging = false;
  let moved = false;
  let lastPointer = null;
  let rotationAnimation = null;

  summary.textContent = `${graph.metadata.paper_files} PDFs · ${graph.metadata.unique_papers} 篇唯一论文 · ${graph.categories.length} 类`;

  graph.categories.forEach(category => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'category-button';
    button.dataset.category = category.id;
    button.style.setProperty('--category-color', `var(--cat-${categoryById[category.id].index})`);
    button.setAttribute('aria-pressed', 'false');
    button.innerHTML = `<span class="category-dot" aria-hidden="true"></span><span>${category.label}</span>`;
    button.addEventListener('click', () => activateCategory(category.id));
    categoryList.appendChild(button);
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
      let z = Math.sin(sector * 1.65 + index * 1.27) * 0.56;
      const length = Math.hypot(x, y, z) || 1;
      node.base = {x: x / length * radius, y: y / length * radius, z: z / length * radius};

      const groupElement = document.createElementNS(ns, 'g');
      groupElement.setAttribute('class', 'node');
      groupElement.dataset.node = node.id;

      if (node.is_main) {
        const halo = document.createElementNS(ns, 'circle');
        halo.setAttribute('class', 'main-halo');
        halo.setAttribute('r', '15');
        groupElement.appendChild(halo);
      }

      const mark = document.createElementNS(ns, 'circle');
      mark.setAttribute('class', 'node-mark');
      mark.setAttribute('r', node.is_main ? '10.5' : String(5.6 + Math.min(3.5, Math.sqrt(node.citation_count))));
      mark.style.fill = `var(--cat-${categoryIndex})`;
      groupElement.appendChild(mark);

      const label = document.createElementNS(ns, 'text');
      label.setAttribute('x', '15');
      label.setAttribute('y', '4');
      label.textContent = node.label;
      label.style.display = node.is_main ? '' : 'none';
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
      const sourceOffset = sourceNode.is_main ? 13 : 8;
      const targetOffset = targetNode.is_main ? 19 : 12;
      const start = {
        x: source.x + dx / distance * sourceOffset,
        y: source.y + dy / distance * sourceOffset,
      };
      const end = {
        x: target.x - dx / distance * targetOffset,
        y: target.y - dy / distance * targetOffset,
      };
      const bend = edge.type === 'citation' ? 0.027 : -0.035;
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
      node.labelElement.style.display = (node.is_main || node.id === selectedNode) ? '' : 'none';
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
      updateCategoryButtons();
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
    updateCategoryButtons();
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

  function updateCategoryButtons() {
    categoryList.querySelectorAll('button').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.category === activeCategory));
    });
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

  document.getElementById('show-time').addEventListener('change', event => {
    allEdges.filter(edge => edge.type === 'time').forEach(edge => {
      edge.element.style.display = event.target.checked ? '' : 'none';
    });
  });

  document.getElementById('reset-view').addEventListener('click', () => {
    selectedNode = null;
    activeCategory = null;
    rotationX = -0.18;
    rotationY = 0.26;
    updateCategoryButtons();
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
      updateCategoryButtons();
      detail.textContent = '点击节点查看关系；拖动球体可自由旋转。';
      render();
    }
  });

  render();
})();
