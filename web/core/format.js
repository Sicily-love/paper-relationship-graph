(() => {
  function normalizeSearch(value) {
    return String(value || '').toLocaleLowerCase().replace(/\s+/g, ' ').trim();
  }

  function displayCategoryLabel(label) {
    return String(label || '').replace(/_/g, ' · ');
  }

  function shortYear(year) {
    return String(year).slice(-2).padStart(2, '0');
  }

  function formatTaskTime(value) {
    if (!value) return '尚未运行';
    const date = new Date(value);
    return Number.isNaN(date.valueOf()) ? '尚未运行' : date.toLocaleString('zh-CN', {
      month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  }

  // A score maps to one solid colour on the shared red–amber–green scale.
  function scoreColor(value) {
    const score = Math.max(0, Math.min(100, Number(value) || 0));
    const stops = [[0, [223, 91, 103]], [50, [239, 177, 61]], [100, [56, 184, 106]]];
    let lower = stops[0];
    let upper = stops[stops.length - 1];
    for (let index = 1; index < stops.length; index += 1) {
      if (score <= stops[index][0]) {
        upper = stops[index];
        lower = stops[index - 1];
        break;
      }
    }
    const ratio = (score - lower[0]) / Math.max(1, upper[0] - lower[0]);
    const rgb = lower[1].map((channel, index) => Math.round(channel + (upper[1][index] - channel) * ratio));
    return `rgb(${rgb.join(', ')})`;
  }

  window.PaperAtlasFormat = Object.freeze({
    displayCategoryLabel,
    formatTaskTime,
    normalizeSearch,
    scoreColor,
    shortYear,
  });
})();
