const previewTableBody = document.querySelector('#previewTable tbody');
const eventsTableBody = document.querySelector('#eventsTable tbody');
const statusEl = document.querySelector('#status');
const runButton = document.querySelector('#runButton');
const downloadButton = document.querySelector('#downloadButton');
const equityCanvas = document.querySelector('#equityCanvas');

const totalReturnEl = document.querySelector('#totalReturn');
const maxDrawdownEl = document.querySelector('#maxDrawdown');
const winRateEl = document.querySelector('#winRate');
const tradesCountEl = document.querySelector('#tradesCount');

const inputs = {
  ma10: document.querySelector('#ma10'),
  ma20: document.querySelector('#ma20'),
  ma60: document.querySelector('#ma60'),
  x: document.querySelector('#x'),
  y: document.querySelector('#y'),
  a: document.querySelector('#a'),
  b: document.querySelector('#b'),
  initialLeverage: document.querySelector('#initialLeverage'),
  feeRate: document.querySelector('#feeRate'),
  slippageRate: document.querySelector('#slippageRate'),
  maxLeverage: document.querySelector('#maxLeverage')
};

let rawData = [];
let lastResult = null;

const formatDate = (date) => {
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  const day = `${date.getDate()}`.padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const parseDate = (value) => {
  if (!value) return null;
  const parts = value.trim().split('/').map((part) => part.trim());
  if (parts.length !== 3) return null;
  const [year, month, day] = parts.map((part) => Number(part));
  if (!year || !month || !day) return null;
  return new Date(year, month - 1, day);
};

const parseCsv = (text) => {
  const lines = text.trim().split(/\r?\n/);
  if (lines.length === 0) return [];
  const headers = splitCsvLine(lines[0]);
  const rows = [];

  for (let i = 1; i < lines.length; i += 1) {
    if (!lines[i].trim()) continue;
    const values = splitCsvLine(lines[i]);
    const row = {};
    headers.forEach((header, index) => {
      row[header] = values[index] ?? '';
    });
    rows.push(row);
  }
  return rows;
};

const splitCsvLine = (line) => {
  const result = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    if (char === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (char === ',' && !inQuotes) {
      result.push(current.trim());
      current = '';
    } else {
      current += char;
    }
  }
  result.push(current.trim());
  return result;
};

const rollingMean = (values, window) => {
  const result = new Array(values.length).fill(null);
  let sum = 0;

  for (let i = 0; i < values.length; i += 1) {
    sum += values[i];
    if (i >= window) {
      sum -= values[i - window];
    }
    if (i >= window - 1) {
      result[i] = sum / window;
    }
  }
  return result;
};

const renderPreview = (data) => {
  previewTableBody.innerHTML = '';
  data.slice(0, 20).forEach((row) => {
    const tr = document.createElement('tr');
    const dateTd = document.createElement('td');
    const closeTd = document.createElement('td');
    dateTd.textContent = formatDate(row.date);
    closeTd.textContent = row.close.toFixed(2);
    tr.append(dateTd, closeTd);
    previewTableBody.appendChild(tr);
  });
};

const parseInputNumber = (input, fallback = 0) => {
  const value = Number(input.value);
  return Number.isFinite(value) ? value : fallback;
};

const backtest = (data) => {
  const ma10Period = Math.max(1, Math.floor(parseInputNumber(inputs.ma10, 10)));
  const ma20Period = Math.max(1, Math.floor(parseInputNumber(inputs.ma20, 20)));
  const ma60Period = Math.max(1, Math.floor(parseInputNumber(inputs.ma60, 60)));

  const x = parseInputNumber(inputs.x, 1);
  const y = parseInputNumber(inputs.y, -1);
  const a = parseInputNumber(inputs.a, 1);
  const b = parseInputNumber(inputs.b, -1);
  const initialLeverage = parseInputNumber(inputs.initialLeverage, 0);
  const feeRate = parseInputNumber(inputs.feeRate, 0);
  const slippageRate = parseInputNumber(inputs.slippageRate, 0);

  const maxLeverageValue = inputs.maxLeverage.value.trim();
  const maxLeverage = maxLeverageValue === '' ? null : Math.abs(Number(maxLeverageValue));

  const closeValues = data.map((row) => row.close);
  const ma10 = rollingMean(closeValues, ma10Period);
  const ma20 = rollingMean(closeValues, ma20Period);
  const ma60 = rollingMean(closeValues, ma60Period);

  const leverage = new Array(data.length).fill(initialLeverage);
  const returns = new Array(data.length).fill(0);
  const strategyReturns = new Array(data.length).fill(0);
  const equity = new Array(data.length).fill(1);
  const upEventYday = new Array(data.length).fill(false);
  const downEventYday = new Array(data.length).fill(false);
  const seasonUpYday = new Array(data.length).fill(false);
  const events = [];

  if (data.length > 1) {
    leverage[1] = initialLeverage;
  }

  for (let t = 2; t < data.length; t += 1) {
    const c1 = closeValues[t - 1];
    const c2 = closeValues[t - 2];
    const ma10_1 = ma10[t - 1];
    const ma10_2 = ma10[t - 2];
    const ma20_1 = ma20[t - 1];
    const ma20_2 = ma20[t - 2];
    const ma60_1 = ma60[t - 1];

    if (
      ma10_1 !== null &&
      ma10_2 !== null &&
      ma20_1 !== null &&
      ma20_2 !== null &&
      ma60_1 !== null
    ) {
      const upEvent = c2 <= ma10_2 && c2 <= ma20_2 && c1 >= ma10_1 && c1 >= ma20_1;
      const downEvent = c2 >= ma10_2 && c2 >= ma20_2 && c1 <= ma10_1 && c1 <= ma20_1;
      const seasonUp = c1 >= ma60_1;

      upEventYday[t] = upEvent;
      downEventYday[t] = downEvent;
      seasonUpYday[t] = seasonUp;

      let target = null;
      if (upEvent && seasonUp) {
        target = x;
      } else if (downEvent && seasonUp) {
        target = y;
      } else if (upEvent && !seasonUp) {
        target = a;
      } else if (downEvent && !seasonUp) {
        target = b;
      }

      leverage[t] = leverage[t - 1];
      if (target !== null) {
        leverage[t] = target;
        events.push({
          actionDate: data[t].date,
          eventDate: data[t - 1].date,
          event: upEvent ? 'UP' : 'DOWN',
          season: seasonUp ? '季線上' : '季線下',
          leverage: leverage[t]
        });
      }
    } else {
      leverage[t] = leverage[t - 1];
    }

    if (maxLeverage !== null && Number.isFinite(maxLeverage) && maxLeverage > 0) {
      if (Math.abs(leverage[t]) > maxLeverage) {
        leverage[t] = Math.sign(leverage[t]) * maxLeverage;
      }
    }
  }

  for (let t = 1; t < data.length; t += 1) {
    const r = closeValues[t] / closeValues[t - 1] - 1;
    returns[t] = r;
    let strategyReturn = r * leverage[t];
    if (leverage[t] !== leverage[t - 1]) {
      strategyReturn -= feeRate + slippageRate;
    }
    strategyReturns[t] = strategyReturn;
    equity[t] = equity[t - 1] * (1 + strategyReturn);
  }

  return {
    ma10,
    ma20,
    ma60,
    leverage,
    returns,
    strategyReturns,
    equity,
    upEventYday,
    downEventYday,
    seasonUpYday,
    events
  };
};

const computeMetrics = (result) => {
  const equity = result.equity;
  const totalReturn = equity.length ? equity[equity.length - 1] - 1 : 0;

  let runningMax = -Infinity;
  let maxDrawdown = 0;
  equity.forEach((value) => {
    runningMax = Math.max(runningMax, value);
    const drawdown = runningMax === 0 ? 0 : value / runningMax - 1;
    maxDrawdown = Math.min(maxDrawdown, drawdown);
  });

  const validReturns = result.strategyReturns.filter((value) => value !== 0);
  const winRate =
    validReturns.length === 0
      ? 0
      : validReturns.filter((value) => value > 0).length / validReturns.length;

  let tradesCount = 0;
  for (let i = 1; i < result.leverage.length; i += 1) {
    if (result.leverage[i] !== result.leverage[i - 1]) {
      tradesCount += 1;
    }
  }

  return {
    totalReturn,
    maxDrawdown,
    winRate,
    tradesCount
  };
};

const renderMetrics = (metrics) => {
  totalReturnEl.textContent = `${(metrics.totalReturn * 100).toFixed(2)}%`;
  maxDrawdownEl.textContent = `${(metrics.maxDrawdown * 100).toFixed(2)}%`;
  winRateEl.textContent = `${(metrics.winRate * 100).toFixed(2)}%`;
  tradesCountEl.textContent = `${metrics.tradesCount}`;
};

const renderEvents = (events) => {
  eventsTableBody.innerHTML = '';
  if (events.length === 0) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 5;
    cell.textContent = '沒有觸發事件';
    row.appendChild(cell);
    eventsTableBody.appendChild(row);
    return;
  }

  events.forEach((event) => {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td>${formatDate(event.actionDate)}</td>
      <td>${formatDate(event.eventDate)}</td>
      <td>${event.event}</td>
      <td>${event.season}</td>
      <td>${event.leverage.toFixed(2)}</td>
    `;
    eventsTableBody.appendChild(row);
  });
};

const drawEquityCurve = (dates, equity) => {
  const ctx = equityCanvas.getContext('2d');
  const width = equityCanvas.clientWidth;
  const height = equityCanvas.height;
  equityCanvas.width = width;
  equityCanvas.height = height;

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, width, height);

  if (equity.length === 0) {
    ctx.fillStyle = '#64748b';
    ctx.fillText('No data', 10, 20);
    return;
  }

  const padding = 40;
  const minValue = Math.min(...equity);
  const maxValue = Math.max(...equity);
  const range = maxValue - minValue || 1;

  ctx.strokeStyle = '#e2e8f0';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(padding, padding);
  ctx.lineTo(padding, height - padding);
  ctx.lineTo(width - padding, height - padding);
  ctx.stroke();

  ctx.strokeStyle = '#2563eb';
  ctx.lineWidth = 2;
  ctx.beginPath();

  equity.forEach((value, index) => {
    const x =
      padding + (index / Math.max(1, equity.length - 1)) * (width - padding * 2);
    const y =
      height -
      padding -
      ((value - minValue) / range) * (height - padding * 2);

    if (index === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });

  ctx.stroke();
  ctx.fillStyle = '#475569';
  ctx.fillText(
    `Equity: ${equity[equity.length - 1].toFixed(2)}`,
    padding,
    padding - 10
  );
};

const buildCsv = (data, result) => {
  const headers = [
    'date',
    'close',
    'ma10',
    'ma20',
    'ma60',
    'leverage',
    'strategy_return',
    'equity',
    'up_event_yday',
    'down_event_yday',
    'season_up_yday'
  ];

  const lines = [headers.join(',')];

  data.forEach((row, index) => {
    const values = [
      formatDate(row.date),
      row.close.toFixed(4),
      result.ma10[index] === null ? '' : result.ma10[index].toFixed(4),
      result.ma20[index] === null ? '' : result.ma20[index].toFixed(4),
      result.ma60[index] === null ? '' : result.ma60[index].toFixed(4),
      result.leverage[index].toFixed(4),
      result.strategyReturns[index].toFixed(6),
      result.equity[index].toFixed(6),
      result.upEventYday[index] ? '1' : '0',
      result.downEventYday[index] ? '1' : '0',
      result.seasonUpYday[index] ? '1' : '0'
    ];
    lines.push(values.join(','));
  });

  return lines.join('\n');
};

const runBacktest = () => {
  if (!rawData.length) return;
  lastResult = backtest(rawData);
  const metrics = computeMetrics(lastResult);

  renderMetrics(metrics);
  renderEvents(lastResult.events);
  drawEquityCurve(
    rawData.map((row) => row.date),
    lastResult.equity
  );

  downloadButton.disabled = false;
};

const downloadResults = () => {
  if (!lastResult) return;
  const csv = buildCsv(rawData, lastResult);
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'backtest_results.csv';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

const loadData = async () => {
  try {
    statusEl.textContent = '讀取資料中…';
    const response = await fetch('data/taiex.csv');
    if (!response.ok) {
      throw new Error(`無法讀取 CSV (${response.status})`);
    }

    const text = await response.text();
    const rows = parseCsv(text);
    const cleaned = rows
      .map((row) => ({
        date: parseDate(row['交易日期']),
        close: Number(row['收盤'])
      }))
      .filter((row) => row.date instanceof Date && !Number.isNaN(row.close))
      .sort((a, b) => a.date - b.date);

    if (!cleaned.length) {
      throw new Error('CSV 解析後沒有有效資料');
    }

    rawData = cleaned;
    renderPreview(rawData);
    statusEl.textContent = `資料載入完成，共 ${rawData.length} 筆。`;
  } catch (error) {
    statusEl.textContent = `讀取失敗：${error.message}`;
  }
};

runButton.addEventListener('click', runBacktest);
downloadButton.addEventListener('click', downloadResults);

loadData();
