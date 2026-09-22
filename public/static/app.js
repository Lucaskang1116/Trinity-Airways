/* 2025 화물 매출 대시보드 - dashboard.json 렌더링 */
(async function () {
  const IDX = await fetch('data/index.json').then(r => r.json());
  const YOY = await fetch('data/yoy.json').then(r => r.json());
  const CACHE = {};
  const loadYear = async y => (CACHE[y] ||= await fetch(`data/dashboard_${y}.json`).then(r => r.json()));
  const CHARTS = [];
  const PALETTE = ['#1f3a5f', '#c8102e', '#2f80ed', '#f2994a', '#27ae60', '#9b51e0', '#eb5757', '#56ccf2', '#6fcf97', '#f2c94c', '#bb6bd9', '#828282', '#219653', '#2d9cdb', '#ff8a65', '#a0aec0'];
  Chart.register(ChartDataLabels);
  Chart.defaults.font.family = '"Noto Sans KR", system-ui, sans-serif';
  Chart.defaults.plugins.datalabels.display = false;
  Chart.defaults.plugins.legend.labels.boxWidth = 12;

  // ---------- 포맷터
  const eok = v => (v / 1e8).toLocaleString('ko-KR', { maximumFractionDigits: 1 });        // 억원
  const eok0 = v => (v / 1e8).toLocaleString('ko-KR', { maximumFractionDigits: 0 });
  const ton = v => (v / 1000).toLocaleString('ko-KR', { maximumFractionDigits: 0 });
  const num = v => (v == null ? '-' : Math.round(v).toLocaleString('ko-KR'));
  const pct = (v, d = 1) => (v == null ? '-' : (v * 100).toFixed(d) + '%');
  const signed = (v, d = 1) => (v == null ? '-' : `<span class="${v >= 0 ? 'pos' : 'neg'}">${v >= 0 ? '+' : ''}${v.toFixed(d)}%</span>`);
  const won = v => (v == null ? '-' : Math.round(v).toLocaleString('ko-KR') + '원');
  const tipEok = ctx => `${ctx.dataset.label}: ${eok(ctx.parsed.y ?? ctx.parsed.x ?? ctx.parsed)}억`;

  // ---------- 탭
  document.querySelectorAll('.tab').forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    document.getElementById('tab-' + b.dataset.tab).classList.add('active');
    window.dispatchEvent(new Event('resize'));
  }));


  // ---------- 공통 헬퍼
  const mk = (id, cfg) => { const c = new Chart(document.getElementById(id), cfg); CHARTS.push(c); return c; };
  const yEok = { ticks: { callback: v => eok0(v) + '억' }, grid: { color: '#eef1f5' } };
  const xNoGrid = { grid: { display: false } };
  const table = (id, cols, rows, opts = {}) => {
    const el = document.getElementById(id);
    const maxRev = Math.max(...rows.map(r => r.rev || 0), 1);
    let h = '<table><thead><tr>' + cols.map(c => `<th class="${c.left ? 'l' : ''}">${c.h}</th>`).join('') + '</tr></thead><tbody>';
    rows.forEach((r, i) => {
      h += `<tr class="${r._total ? 'total' : ''}">` + cols.map(c => {
        let v = c.f ? c.f(r, i, maxRev) : r[c.k];
        return `<td class="${c.left ? 'l' : ''}">${v ?? '-'}</td>`;
      }).join('') + '</tr>';
    });
    el.innerHTML = h + '</tbody></table>';
  };
  const barCell = (r, maxRev) => `<span class="bar" style="width:${Math.max(2, r.rev / maxRev * 80)}px"></span>${eok(r.rev)}`;
  const totalRow = rows => {
    const t = { _total: true, key: '합계', awb: 0, rev: 0, cw: 0 };
    rows.forEach(r => { t.awb += r.awb; t.rev += r.rev; t.cw += r.cw; });
    t.rev_per_awb = t.rev / t.awb; t.yield = t.rev / t.cw; t.share = rows.reduce((a, r) => a + (r.share || 0), 0);
    return t;
  };
  const STD_COLS = (keyLabel = '구분') => [
    { h: '#', f: (r, i) => r._total ? '' : i + 1 },
    { h: keyLabel, k: 'key', left: true },
    { h: 'AWB', f: r => num(r.awb) },
    { h: '매출(억원)', f: (r, i, m) => barCell(r, m) },
    { h: '비중', f: r => pct(r.share) },
    { h: '유상중량(톤)', f: r => ton(r.cw) },
    { h: '매출/AWB', f: r => won(r.rev_per_awb) },
    { h: 'kg당 단가', f: r => won(r.yield) },
  ];

  async function render(year) {
    CHARTS.forEach(c => c.destroy()); CHARTS.length = 0;
    const D = await loadYear(year);
    const M = D.meta.months.map(m => `${m}월`);
    const S0 = D.summary;
    document.getElementById('page-title').textContent = `${year} 화물 매출 분석 대시보드`;
    document.getElementById('meta-line').textContent = `${D.meta.source} · ${S0.period} · 생성 ${D.meta.generated}`;
    document.getElementById('foot-meta').textContent = `데이터 생성 ${D.meta.generated}` + (year === 2026 ? ` · ${D.meta.fx_note.split(' · ')[1] || ''}` : '');
    document.getElementById('year-note').textContent = S0.is_partial_year ? `${year}년은 1~${S0.last_month}월 ${S0.months_available}개월 실적 (부분연도)` : `${year}년 연간(12개월) 실적`;
    document.getElementById('c-nodata-title').textContent = `${year} 실적 없는 마스터 고객사`;
    document.querySelectorAll('#year-seg button').forEach(b => b.classList.toggle('active', +b.dataset.year === year));
    // =====================================================================
    // 종합
    // =====================================================================
    const S = D.summary;
    const kpis = [
      { cls: 'red', lbl: S.is_partial_year ? `1~${S.last_month}월 총매출` : '연간 총매출', val: eok(S.total_rev), unit: '억원', sub: `${S.last_month}월 vs 1월 ${S.dec_vs_jan >= 0 ? '+' : ''}${(S.dec_vs_jan * 100).toFixed(0)}%`, dir: S.dec_vs_jan >= 0 ? 'up' : 'down' },
      { cls: 'blue', lbl: '총 AWB 건수', val: num(S.total_awb), unit: '건', sub: `${S.route_count}개 노선 · ${S.dest_count}개 목적지` },
      { cls: '', lbl: '유상중량', val: ton(S.total_cw), unit: '톤', sub: `실중량 ${ton(S.total_gw)}톤 · ${num(S.total_pieces)}pcs` },
      { cls: 'green', lbl: 'kg당 단가(Yield)', val: num(S.yield), unit: '원/kg', sub: `AWB당 ${num(S.rev_per_awb / 1e4)}만원` },
      { cls: '', lbl: '최대 매출 월', val: `${S.best_month}월`, unit: '', sub: S.h2_vs_h1 != null ? `${eok(S.best_month_rev)}억 · 하반기 vs 상반기 +${(S.h2_vs_h1 * 100).toFixed(0)}%` : `${eok(S.best_month_rev)}억 · 월평균 ${eok(S.total_rev / S.months_available)}억`, dir: 'up' },
      { cls: 'blue', lbl: '대리점 집중도', val: pct(S.top5_agent_share, 0), unit: 'Top5', sub: `Top1 ${S.top1_agent} ${pct(S.top1_agent_share)}` },
    ];
    document.getElementById('kpi-grid').innerHTML = kpis.map(k =>
      `<div class="kpi ${k.cls}"><div class="lbl">${k.lbl}</div><div class="val">${k.val}<small>${k.unit}</small></div><div class="sub ${k.dir || ''}">${k.sub}</div></div>`).join('');
    document.getElementById('insights').innerHTML = D.insights.map(i => `<li>${i}</li>`).join('');
  
    mk('ov-monthly', {
      data: {
        labels: M, datasets: [
          { type: 'bar', label: '매출(억원)', data: D.monthly.map(m => m.rev), backgroundColor: '#1f3a5f', yAxisID: 'y', borderRadius: 4, datalabels: { display: true, anchor: 'end', align: 'top', formatter: v => eok0(v), font: { size: 10, weight: 700 }, color: '#1f3a5f' } },
          { type: 'line', label: '유상중량(톤)', data: D.monthly.map(m => m.cw), borderColor: '#c8102e', backgroundColor: '#c8102e', yAxisID: 'y1', tension: .3, pointRadius: 3 },
        ]
      },
      options: { maintainAspectRatio: false, interaction: { mode: 'index', intersect: false }, scales: { x: xNoGrid, y: { ...yEok, beginAtZero: true }, y1: { position: 'right', grid: { display: false }, ticks: { callback: v => ton(v) + 't' } } },
        plugins: { tooltip: { callbacks: { label: c => c.dataset.yAxisID === 'y' ? `매출: ${eok(c.parsed.y)}억원` : `유상중량: ${ton(c.parsed.y)}톤` } } } }
    });
    mk('ov-region', {
      type: 'doughnut',
      data: { labels: D.regions.map(r => r.key), datasets: [{ data: D.regions.map(r => r.rev), backgroundColor: PALETTE }] },
      options: { maintainAspectRatio: false, cutout: '55%', plugins: { legend: { position: 'right' }, datalabels: { display: c => c.dataset.data[c.dataIndex] / S.total_rev > .04, formatter: (v, c) => c.chart.data.labels[c.dataIndex] + '\n' + pct(v / S.total_rev, 0), color: '#fff', font: { weight: 700, size: 11 }, textAlign: 'center' }, tooltip: { callbacks: { label: c => `${c.label}: ${eok(c.parsed)}억 (${pct(c.parsed / S.total_rev)})` } } } }
    });
    const hbar = (id, rows, label = '매출(억원)') => mk(id, {
      type: 'bar', data: { labels: rows.map(r => r.key), datasets: [{ label, data: rows.map(r => r.rev), backgroundColor: rows.map((_, i) => i === 0 ? '#c8102e' : '#1f3a5f'), borderRadius: 4, datalabels: { display: true, anchor: 'end', align: 'right', formatter: (v, c) => `${eok(v)}억 (${pct(rows[c.dataIndex].share, 1)})`, font: { size: 10 }, color: '#1b2430' } }] },
      options: { indexAxis: 'y', maintainAspectRatio: false, layout: { padding: { right: 90 } }, scales: { x: { ...yEok, beginAtZero: true }, y: { grid: { display: false } } }, plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => `${eok(c.parsed.x)}억 · AWB ${num(rows[c.dataIndex].awb)}건 · ${won(rows[c.dataIndex].yield)}/kg` } } } }
    });
    hbar('ov-agent', D.agents_group.slice(0, 10));
    hbar('ov-route', D.routes.slice(0, 10));
  
    // =====================================================================
    // 월별
    // =====================================================================
    mk('m-rev', {
      data: { labels: M, datasets: [
        { type: 'bar', label: '매출(억원)', data: D.monthly.map(m => m.rev), backgroundColor: '#1f3a5f', borderRadius: 4, yAxisID: 'y' },
        { type: 'line', label: '전월 대비(%)', data: D.monthly.map(m => m.mom), borderColor: '#f2994a', backgroundColor: '#f2994a', yAxisID: 'y1', tension: .3, datalabels: { display: true, align: 'top', formatter: v => v == null ? '' : (v > 0 ? '+' : '') + v.toFixed(0) + '%', font: { size: 10, weight: 700 }, color: '#d97706' } }] },
      options: { maintainAspectRatio: false, interaction: { mode: 'index', intersect: false }, scales: { x: xNoGrid, y: { ...yEok, beginAtZero: true }, y1: { position: 'right', grid: { display: false }, ticks: { callback: v => v + '%' } } } }
    });
    mk('m-awb', {
      data: { labels: M, datasets: [
        { type: 'bar', label: 'AWB 건수', data: D.monthly.map(m => m.awb), backgroundColor: '#2f80ed', borderRadius: 4, yAxisID: 'y', datalabels: { display: true, anchor: 'end', align: 'top', formatter: v => num(v), font: { size: 10 } } },
        { type: 'line', label: 'AWB당 매출(만원)', data: D.monthly.map(m => m.rev_per_awb / 1e4), borderColor: '#c8102e', backgroundColor: '#c8102e', yAxisID: 'y1', tension: .3 }] },
      options: { maintainAspectRatio: false, interaction: { mode: 'index', intersect: false }, scales: { x: xNoGrid, y: { beginAtZero: true, grid: { color: '#eef1f5' } }, y1: { position: 'right', grid: { display: false }, ticks: { callback: v => num(v) + '만' } } } }
    });
    mk('m-yield', {
      type: 'line', data: { labels: M, datasets: [{ label: 'kg당 단가(원)', data: D.monthly.map(m => m.yield), borderColor: '#27ae60', backgroundColor: 'rgba(39,174,96,.15)', fill: true, tension: .3, datalabels: { display: true, align: 'top', formatter: v => num(v), font: { size: 10, weight: 700 }, color: '#15803d' } }] },
      options: { maintainAspectRatio: false, scales: { x: xNoGrid, y: { ticks: { callback: v => num(v) + '원' }, grid: { color: '#eef1f5' } } }, plugins: { legend: { display: false } } }
    });
    mk('m-cum', {
      type: 'line', data: { labels: M, datasets: [{ label: '누적 매출(억원)', data: D.monthly.map(m => m.cum_rev), borderColor: '#1f3a5f', backgroundColor: 'rgba(31,58,95,.12)', fill: true, tension: .2, datalabels: { display: true, align: 'top', formatter: v => eok0(v), font: { size: 10 } } }] },
      options: { maintainAspectRatio: false, scales: { x: xNoGrid, y: { ...yEok, beginAtZero: true } }, plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => `누적 ${eok(c.parsed.y)}억` } } } }
    });
    mk('m-quarter', {
      type: 'bar', data: { labels: D.quarterly.map(q => q.key), datasets: [{ label: '매출(억원)', data: D.quarterly.map(q => q.rev), backgroundColor: ['#a0aec0', '#2f80ed', '#1f3a5f', '#c8102e'], borderRadius: 6, datalabels: { display: true, anchor: 'end', align: 'top', formatter: (v, c) => `${eok(v)}억 (${pct(D.quarterly[c.dataIndex].share, 0)})`, font: { weight: 700 } } }] },
      options: { maintainAspectRatio: false, layout: { padding: { top: 20 } }, scales: { x: xNoGrid, y: { ...yEok, beginAtZero: true } }, plugins: { legend: { display: false } } }
    });
    mk('m-weekday', {
      type: 'bar', data: { labels: D.weekday.map(w => ({ Mon: '월', Tue: '화', Wed: '수', Thu: '목', Fri: '금', Sat: '토', Sun: '일' })[w.key]), datasets: [{ label: '매출(억원)', data: D.weekday.map(w => w.rev), backgroundColor: '#2f80ed', borderRadius: 6, datalabels: { display: true, anchor: 'end', align: 'top', formatter: v => eok0(v), font: { weight: 700 } } }] },
      options: { maintainAspectRatio: false, layout: { padding: { top: 20 } }, scales: { x: xNoGrid, y: { ...yEok, beginAtZero: true } }, plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => `${eok(c.parsed.y)}억 · AWB ${num(D.weekday[c.dataIndex].awb)}건` } } } }
    });
    const ma7 = D.daily.rev.map((_, i, a) => { const s = a.slice(Math.max(0, i - 6), i + 1); return s.reduce((x, y) => x + y, 0) / s.length; });
    mk('m-daily', {
      data: { labels: D.daily.date, datasets: [
        { type: 'bar', label: '일별 매출', data: D.daily.rev, backgroundColor: 'rgba(31,58,95,.35)' },
        { type: 'line', label: '7일 이동평균', data: ma7, borderColor: '#c8102e', pointRadius: 0, borderWidth: 2, tension: .3 }] },
      options: { maintainAspectRatio: false, interaction: { mode: 'index', intersect: false }, scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 12, callback: (v, i) => D.daily.date[i].slice(5) } }, y: { ...yEok, beginAtZero: true } }, plugins: { tooltip: { callbacks: { label: c => `${c.dataset.label}: ${(c.parsed.y / 1e6).toFixed(0)}백만원` } } } }
    });
    table('m-table', [
      { h: '월', f: r => r._total ? '합계' : `${r.month}월`, left: true },
      { h: 'AWB', f: r => num(r.awb) }, { h: '매출(억원)', f: (r, i, m) => barCell(r, m) }, { h: '비중', f: r => pct(r.share) },
      { h: '전월대비', f: r => r._total ? '' : (r.mom == null ? '-' : signed(r.mom)) },
      { h: '유상중량(톤)', f: r => ton(r.cw) }, { h: '실중량(톤)', f: r => ton(r.gw) }, { h: 'Pieces', f: r => num(r.pieces) },
      { h: '매출/AWB', f: r => won(r.rev_per_awb) }, { h: 'kg당 단가', f: r => won(r.yield) }, { h: '누적(억원)', f: r => r._total ? '' : eok(r.cum_rev) },
    ], [...D.monthly, (() => { const t = totalRow(D.monthly); t.gw = D.monthly.reduce((a, r) => a + r.gw, 0); t.pieces = D.monthly.reduce((a, r) => a + r.pieces, 0); return t; })()]);
  
    // =====================================================================
    // 노선/권역
    // =====================================================================
    const stacked = (id, series, keys, colors = PALETTE, fmt = eok) => mk(id, {
      type: 'bar', data: { labels: M, datasets: keys.map((k, i) => ({ label: k, data: series[k].rev, backgroundColor: colors[i % colors.length], stack: 's' })) },
      options: { maintainAspectRatio: false, interaction: { mode: 'index', intersect: false }, scales: { x: { ...xNoGrid, stacked: true }, y: { ...yEok, stacked: true, beginAtZero: true } }, plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: { label: c => `${c.dataset.label}: ${fmt(c.parsed.y)}억` } } } }
    });
    stacked('r-region-monthly', D.region_monthly, D.regions.map(r => r.key));
    stacked('r-direction', D.direction_monthly, D.direction.map(d => d.key), ['#1f3a5f', '#f2994a']);
    hbar('r-origin', D.origins.slice(0, 10));
    hbar('r-dest', D.dests.slice(0, 10));
    mk('r-region-yield', {
      data: { labels: D.regions.map(r => r.key), datasets: [
        { type: 'bar', label: 'kg당 단가(원)', data: D.regions.map(r => r.yield), backgroundColor: '#27ae60', borderRadius: 4, yAxisID: 'y', datalabels: { display: true, anchor: 'end', align: 'top', formatter: v => num(v), font: { size: 10, weight: 700 } } },
        { type: 'line', label: '매출(억원)', data: D.regions.map(r => r.rev), borderColor: '#c8102e', backgroundColor: '#c8102e', yAxisID: 'y1', pointRadius: 4 }] },
      options: { maintainAspectRatio: false, layout: { padding: { top: 16 } }, scales: { x: xNoGrid, y: { beginAtZero: true, ticks: { callback: v => num(v) + '원' } }, y1: { position: 'right', grid: { display: false }, ticks: { callback: v => eok0(v) + '억' } } } }
    });
    table('r-table', [
      { h: '#', f: (r, i) => r._total ? '' : i + 1 }, { h: '노선', k: 'key', left: true },
      { h: '방향', f: r => r._total ? '' : `<span class="tag">${r.direction.split('(')[0]}</span>`, left: true },
      { h: '권역', f: r => r.region, left: true },
      { h: 'AWB', f: r => num(r.awb) }, { h: '매출(억원)', f: (r, i, m) => barCell(r, m) }, { h: '비중', f: r => pct(r.share) },
      { h: '유상중량(톤)', f: r => ton(r.cw) }, { h: '매출/AWB', f: r => won(r.rev_per_awb) }, { h: 'kg당 단가', f: r => won(r.yield) },
    ], [...D.routes, Object.assign(totalRow(D.routes), { key: 'Top30 합계', region: '' })]);
    table('r-region-dir', [
      { h: '권역', k: 'market_region', left: true }, { h: '방향', k: 'direction', left: true },
      { h: 'AWB', f: r => num(r.awb) }, { h: '매출(억원)', f: (r, i, m) => barCell(r, m) }, { h: '비중', f: r => pct(r.share) },
      { h: '유상중량(톤)', f: r => ton(r.cw) }, { h: '매출/AWB', f: r => won(r.rev_per_awb) }, { h: 'kg당 단가', f: r => won(r.yield) },
    ], D.region_direction);
  
    // =====================================================================
    // 고객사 (해외발/인천발 업체 마스터)
    // =====================================================================
    const CT = D.customer_type;
    const ctColor = { '인천발': '#1f3a5f', '해외발': '#c8102e', '미분류': '#a0aec0' };
    const mappedRev = D.customers.filter(c => c.mapped).reduce((a, c) => a + c.rev, 0);
    document.getElementById('c-kpi').innerHTML = [
      ...CT.map(c => ({ cls: c.key === '인천발' ? '' : 'red', lbl: `${c.key} 업체 매출`, val: eok(c.rev), unit: '억원', sub: `${pct(c.share, 0)} · AWB ${num(c.awb)}건 · ${num(c.yield)}원/kg` })),
      { cls: 'blue', lbl: '마스터 매핑 매출 비중', val: pct(mappedRev / S.total_rev, 0), unit: '', sub: `${D.customers.filter(c => c.mapped).length}개 고객사 매칭 · 미등재 ${D.customers.filter(c => !c.mapped).length}개 Bill-To 그룹` },
      { cls: 'green', lbl: '해외발 Top', val: D.customers.filter(c => c.type === '해외발')[0].key.split(' ')[0], unit: '', sub: `${eok(D.customers.filter(c => c.type === '해외발')[0].rev)}억 · 해외발 내 ${pct(D.customers.filter(c => c.type === '해외발')[0].rev / CT.find(c => c.key === '해외발').rev, 0)}` },
      { cls: '', lbl: '인천발 Top', val: 'FTL 코리아', unit: '', sub: `${eok(D.customers.filter(c => c.type === '인천발')[0].rev)}억 · 인천발 내 ${pct(D.customers.filter(c => c.type === '인천발')[0].rev / CT.find(c => c.key === '인천발').rev, 0)}` },
      { cls: 'blue', lbl: '실적 없는 마스터 고객', val: D.customers_no_data.length, unit: '개사', sub: D.customers_no_data.map(c => c.name).slice(0, 3).join(', ') + '…' },
    ].map(k => `<div class="kpi ${k.cls}"><div class="lbl">${k.lbl}</div><div class="val">${k.val}<small>${k.unit}</small></div><div class="sub">${k.sub}</div></div>`).join('');
    mk('c-type-monthly', {
      type: 'bar', data: { labels: M, datasets: CT.map(c => ({ label: c.key, data: D.customer_type_monthly[c.key].rev, backgroundColor: ctColor[c.key], stack: 's', datalabels: { display: c.key === '인천발', color: '#fff', font: { size: 10, weight: 700 }, formatter: (v, ctx) => { const t = CT.reduce((a, cc) => a + D.customer_type_monthly[cc.key].rev[ctx.dataIndex], 0); return pct(v / t, 0); } } })) },
      options: { maintainAspectRatio: false, interaction: { mode: 'index', intersect: false }, scales: { x: { ...xNoGrid, stacked: true }, y: { ...yEok, stacked: true, beginAtZero: true } }, plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: { label: c => `${c.dataset.label}: ${eok(c.parsed.y)}억` } } } }
    });
    mk('c-type-yield', {
      type: 'line', data: { labels: M, datasets: CT.filter(c => c.key !== '미분류').map(c => ({ label: c.key, data: D.customer_type_yield_monthly[c.key], borderColor: ctColor[c.key], backgroundColor: ctColor[c.key], tension: .3, datalabels: { display: true, align: 'top', formatter: v => num(v), font: { size: 9 } } })) },
      options: { maintainAspectRatio: false, interaction: { mode: 'index', intersect: false }, scales: { x: xNoGrid, y: { ticks: { callback: v => num(v) + '원' }, grid: { color: '#eef1f5' } } }, plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: { label: c => `${c.dataset.label}: ${num(c.parsed.y)}원/kg` } } } }
    });
    const C15 = D.customers.slice(0, 15);
    mk('c-top', {
      type: 'bar', data: { labels: C15.map(c => c.key + (c.mapped ? '' : ' *')), datasets: [{ label: '매출(억원)', data: C15.map(c => c.rev), backgroundColor: C15.map(c => ctColor[c.type]), borderRadius: 4, datalabels: { display: true, anchor: 'end', align: 'right', formatter: (v, c) => `${eok(v)}억 (${pct(C15[c.dataIndex].share, 1)})`, font: { size: 10 } } }] },
      options: { indexAxis: 'y', maintainAspectRatio: false, layout: { padding: { right: 90 } }, scales: { x: { ...yEok, beginAtZero: true }, y: { grid: { display: false }, ticks: { font: { size: 11 } } } }, plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => `${C15[c.dataIndex].type} · ${eok(c.parsed.x)}억 · ${won(C15[c.dataIndex].yield)}/kg${C15[c.dataIndex].mapped ? '' : ' · 마스터 미등재(추정)'}` } } } }
    });
    stacked('c-monthly', D.customer_monthly, Object.keys(D.customer_monthly));
    const renderCust = view => {
      const rows = view === 'all' ? D.customers : D.customers.filter(c => c.type === view);
      table('c-table', [
        { h: '#', f: (r, i) => r._total ? '' : i + 1 }, { h: '고객번호', f: r => r.customer_no || (r._total ? '' : '<span class="tag" style="background:#fef3c7;color:#92400e">미등재</span>'), left: true },
        { h: '업체명', k: 'key', left: true }, { h: '구분', f: r => r._total ? '' : `<span class="tag" style="background:${ctColor[r.type]}22;color:${ctColor[r.type]}">${r.type}</span>`, left: true },
        { h: 'Bill-To (Quality Audit)', f: r => r._total ? '' : r.bill_to.join(' · '), left: true }, { h: '통화', f: r => r.currency || '', left: true }, { h: '주력 노선', f: r => r.top_route || '', left: true },
        { h: 'AWB', f: r => num(r.awb) }, { h: '매출(억원)', f: (r, i, m) => barCell(r, m) }, { h: '비중', f: r => pct(r.share) },
        { h: '유상중량(톤)', f: r => ton(r.cw) }, { h: '매출/AWB', f: r => won(r.rev_per_awb) }, { h: 'kg당 단가', f: r => won(r.yield) }, { h: 'Spot 비중', f: r => r._total ? '' : (r.spot_share ?? 0).toFixed(1) + '%' },
      ], [...rows, Object.assign(totalRow(rows), { key: `합계 (${rows.length}개)` })]);
    };
    renderCust('all');
    document.querySelectorAll('#c-seg .seg-btn').forEach(b => b.onclick = (() => {
      document.querySelectorAll('#c-seg .seg-btn').forEach(x => x.classList.remove('active')); b.classList.add('active'); renderCust(b.dataset.view);
    }));
    table('c-nodata', [
      { h: '고객번호', k: 'customer_no', left: true }, { h: '업체명', k: 'name', left: true }, { h: '구분', k: 'type', left: true }, { h: '통화', k: 'currency', left: true }, { h: '품목', f: r => r.origin + ' 화물운송수입', left: true },
      { h: '비고', f: () => '2025 Quality Audit에 해당 Bill-To 없음 (신규 계약 또는 타 Bill-To명으로 청구 가능성)', left: true },
    ], D.customers_no_data);
  
    // =====================================================================
    // 대리점
    // =====================================================================
    const AG = D.agents_group.slice(0, 20);
    mk('a-pareto', {
      data: { labels: AG.map(a => a.key), datasets: [
        { type: 'bar', label: '매출(억원)', data: AG.map(a => a.rev), backgroundColor: '#1f3a5f', borderRadius: 4, yAxisID: 'y' },
        { type: 'line', label: '누적 비중(%)', data: D.agent_cum_share.slice(0, 20).map(v => v * 100), borderColor: '#c8102e', backgroundColor: '#c8102e', yAxisID: 'y1', tension: .2, datalabels: { display: (c) => c.dataIndex < 8, align: 'top', formatter: v => v.toFixed(0) + '%', font: { size: 10, weight: 700 }, color: '#c8102e' } }] },
      options: { maintainAspectRatio: false, interaction: { mode: 'index', intersect: false }, scales: { x: { ...xNoGrid, ticks: { maxRotation: 60, minRotation: 45, font: { size: 10 } } }, y: { ...yEok, beginAtZero: true }, y1: { position: 'right', min: 0, max: 100, grid: { display: false }, ticks: { callback: v => v + '%' } } } }
    });
    mk('a-bubble', {
      type: 'bubble', data: { datasets: AG.slice(0, 15).map((a, i) => ({ label: a.key, data: [{ x: a.cw / 1000, y: a.yield, r: Math.max(5, Math.sqrt(a.rev / 1e8) * 3) }], backgroundColor: PALETTE[i % PALETTE.length] + 'bb' })) },
      options: { maintainAspectRatio: false, scales: { x: { title: { display: true, text: '유상중량(톤)' }, grid: { color: '#eef1f5' } }, y: { title: { display: true, text: 'kg당 단가(원)' }, grid: { color: '#eef1f5' } } },
        plugins: { legend: { position: 'right', labels: { font: { size: 10 } } }, tooltip: { callbacks: { label: c => `${c.dataset.label}: ${ton(AG[c.datasetIndex].cw)}톤 · ${num(c.parsed.y)}원/kg · 매출 ${eok(AG[c.datasetIndex].rev)}억` } } } }
    });
    stacked('a-monthly', D.agent_monthly, Object.keys(D.agent_monthly));
    const renderAgentTable = view => {
      if (view === 'group') {
        table('a-table', [
          { h: '#', f: (r, i) => r._total ? '' : i + 1 }, { h: '대리점 그룹', k: 'key', left: true },
          { h: '포함 Bill-To', f: r => r._total ? '' : r.members.join(' · '), left: true },
          { h: '주력 권역', f: r => r.main_region || '', left: true }, { h: '주력 노선', f: r => r.top_route || '', left: true },
          { h: 'AWB', f: r => num(r.awb) }, { h: '매출(억원)', f: (r, i, m) => barCell(r, m) }, { h: '비중', f: r => pct(r.share) },
          { h: '유상중량(톤)', f: r => ton(r.cw) }, { h: '매출/AWB', f: r => won(r.rev_per_awb) }, { h: 'kg당 단가', f: r => won(r.yield) },
        ], [...D.agents_group, Object.assign(totalRow(D.agents_group), { key: `합계 (${D.agents_group.length}개 그룹 · HHI ${D.agent_hhi})` })]);
      } else {
        table('a-table', [
          { h: '#', f: (r, i) => r._total ? '' : i + 1 }, { h: 'Bill-To Party Name', k: 'key', left: true },
          { h: '그룹', f: r => r.group || '', left: true }, { h: '통화', f: r => r.currency || '', left: true },
          { h: 'AWB', f: r => num(r.awb) }, { h: '매출(억원)', f: (r, i, m) => barCell(r, m) }, { h: '비중', f: r => pct(r.share) },
          { h: '유상중량(톤)', f: r => ton(r.cw) }, { h: '매출/AWB', f: r => won(r.rev_per_awb) }, { h: 'kg당 단가', f: r => won(r.yield) }, { h: 'Spot 비중', f: r => r._total ? '' : (r.spot_share ?? 0).toFixed(1) + '%' },
        ], [...D.agents_raw, Object.assign(totalRow(D.agents_raw), { key: `합계 (${D.agents_raw.length}개)` })]);
      }
    };
    renderAgentTable('group');
    document.querySelectorAll('#tab-agent .seg-btn').forEach(b => b.onclick = (() => {
      document.querySelectorAll('#tab-agent .seg-btn').forEach(x => x.classList.remove('active')); b.classList.add('active'); renderAgentTable(b.dataset.view);
    }));
  
    // =====================================================================
    // SHC
    // =====================================================================
    const T15 = D.shc_tags.slice(0, 15);
    mk('s-tags', {
      type: 'bar', data: { labels: T15.map(t => `${t.key} ${t.meaning ? '(' + t.meaning + ')' : ''}`), datasets: [{ label: '매출(억원)', data: T15.map(t => t.rev), backgroundColor: '#1f3a5f', borderRadius: 4, datalabels: { display: true, anchor: 'end', align: 'right', formatter: (v, c) => `${eok(v)}억 · ${num(T15[c.dataIndex].awb)}건`, font: { size: 10 } } }] },
      options: { indexAxis: 'y', maintainAspectRatio: false, layout: { padding: { right: 110 } }, scales: { x: { ...yEok, beginAtZero: true }, y: { grid: { display: false }, ticks: { font: { size: 11 } } } }, plugins: { legend: { display: false } } }
    });
    const YT = D.shc_tags.filter(t => t.awb >= 300 && t.yield).sort((a, b) => b.yield - a.yield);
    mk('s-yield', {
      type: 'bar', data: { labels: YT.map(t => `${t.key} ${t.meaning ? '(' + t.meaning + ')' : ''}`), datasets: [{ label: 'kg당 단가(원)', data: YT.map(t => t.yield), backgroundColor: YT.map(t => t.yield >= S.yield ? '#27ae60' : '#a0aec0'), borderRadius: 4, datalabels: { display: true, anchor: 'end', align: 'right', formatter: v => num(v) + '원', font: { size: 10 } } }] },
      options: { indexAxis: 'y', maintainAspectRatio: false, layout: { padding: { right: 60 } }, scales: { x: { beginAtZero: true, grid: { color: '#eef1f5' } }, y: { grid: { display: false }, ticks: { font: { size: 11 } } } }, plugins: { legend: { display: false }, tooltip: { callbacks: { afterLabel: () => `전체 평균 ${num(S.yield)}원/kg` } } } }
    });
    const SP = D.shc_primary.slice(0, 10);
    mk('s-primary', {
      type: 'doughnut', data: { labels: SP.map(s => `${s.key} ${s.meaning ? s.meaning : ''}`), datasets: [{ data: SP.map(s => s.rev), backgroundColor: PALETTE }] },
      options: { maintainAspectRatio: false, cutout: '50%', plugins: { legend: { position: 'right', labels: { font: { size: 11 } } }, datalabels: { display: c => c.dataset.data[c.dataIndex] / S.total_rev > .05, formatter: v => pct(v / S.total_rev, 0), color: '#fff', font: { weight: 700 } }, tooltip: { callbacks: { label: c => `${c.label}: ${eok(c.parsed)}억 (${pct(c.parsed / S.total_rev)})` } } } }
    });
    stacked('s-primary-monthly', D.shc_primary_monthly, Object.keys(D.shc_primary_monthly));
    table('s-table', [
      { h: '#', f: (r, i) => i + 1 }, { h: 'SHC', k: 'key', left: true }, { h: '의미(참고)', k: 'meaning', left: true },
      { h: 'AWB', f: r => num(r.awb) }, { h: 'AWB 비중', f: r => pct(r.awb_share) }, { h: '매출(억원)', f: (r, i, m) => barCell(r, m) }, { h: '매출 비중', f: r => pct(r.rev_share) },
      { h: '유상중량(톤)', f: r => ton(r.cw) }, { h: 'kg당 단가', f: r => won(r.yield) },
    ], D.shc_tags.filter(t => t.awb >= 5));
    table('s-commodity', STD_COLS('Commodity'), D.commodity);
  
    // =====================================================================
    // 기종
    // =====================================================================
    document.getElementById('ac-join').textContent = pct(1 - (D.aircraft.find(a => a.key === '미확인')?.awb || 0) / S.total_awb);
    const AC = D.aircraft.filter(a => a.key !== '미확인');
    mk('ac-share', {
      type: 'doughnut', data: { labels: D.aircraft.map(a => a.key), datasets: [{ data: D.aircraft.map(a => a.rev), backgroundColor: ['#1f3a5f', '#2f80ed', '#c8102e', '#f2994a', '#27ae60', '#a0aec0'] }] },
      options: { maintainAspectRatio: false, cutout: '55%', plugins: { legend: { position: 'right' }, datalabels: { display: c => c.dataset.data[c.dataIndex] / S.total_rev > .03, formatter: (v, c) => c.chart.data.labels[c.dataIndex] + '\n' + pct(v / S.total_rev, 0), color: '#fff', font: { weight: 700, size: 11 }, textAlign: 'center' }, tooltip: { callbacks: { label: c => `${c.label}: ${eok(c.parsed)}억 · ${num(D.aircraft[c.dataIndex].flights)}편` } } } }
    });
    stacked('ac-monthly', D.aircraft_monthly, D.aircraft.map(a => a.key), ['#1f3a5f', '#2f80ed', '#c8102e', '#f2994a', '#27ae60', '#a0aec0']);
    mk('ac-perflight', {
      data: { labels: AC.map(a => a.key), datasets: [
        { type: 'bar', label: '편당 유상중량(kg)', data: AC.map(a => a.cw_per_flight), backgroundColor: '#2f80ed', borderRadius: 4, yAxisID: 'y', datalabels: { display: true, anchor: 'end', align: 'top', formatter: v => num(v) + 'kg', font: { size: 10, weight: 700 } } },
        { type: 'line', label: 'kg당 단가(원)', data: AC.map(a => a.yield), borderColor: '#27ae60', backgroundColor: '#27ae60', yAxisID: 'y1', pointRadius: 5 }] },
      options: { maintainAspectRatio: false, layout: { padding: { top: 16 } }, scales: { x: xNoGrid, y: { beginAtZero: true, ticks: { callback: v => num(v) } }, y1: { position: 'right', grid: { display: false }, ticks: { callback: v => num(v) + '원' } } } }
    });
    const fams = [...new Set(D.aircraft_region.map(r => r.aircraft_family))].filter(f => f !== '미확인');
    const regs = D.regions.map(r => r.key);
    mk('ac-region', {
      type: 'bar', data: { labels: regs, datasets: fams.map((f, i) => ({ label: f, data: regs.map(rg => D.aircraft_region.find(x => x.aircraft_family === f && x.market_region === rg)?.rev || 0), backgroundColor: ['#1f3a5f', '#c8102e', '#f2994a'][i], stack: 's' })) },
      options: { maintainAspectRatio: false, scales: { x: { ...xNoGrid, stacked: true }, y: { ...yEok, stacked: true, beginAtZero: true } }, plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: { label: c => `${c.dataset.label}: ${eok(c.parsed.y)}억` } } } }
    });
    table('ac-table', [
      { h: '기종', k: 'key', left: true }, { h: '계열', k: 'family', left: true }, { h: '운항편(AWB 실린 편)', f: r => num(r.flights) },
      { h: 'AWB', f: r => num(r.awb) }, { h: '매출(억원)', f: (r, i, m) => barCell(r, m) }, { h: '비중', f: r => pct(r.share) },
      { h: '유상중량(톤)', f: r => ton(r.cw) }, { h: '편당 유상중량(kg)', f: r => num(r.cw_per_flight) }, { h: '편당 매출', f: r => won(r.rev / r.flights) }, { h: 'kg당 단가', f: r => won(r.yield) },
    ], D.aircraft);
    table('ac-route', [
      { h: '#', f: (r, i) => i + 1 }, { h: '기종', k: 'aircraft', left: true }, { h: '노선', k: 'route', left: true },
      { h: 'AWB', f: r => num(r.awb) }, { h: '매출(억원)', f: (r, i, m) => barCell(r, m) }, { h: '비중', f: r => pct(r.share) },
      { h: '유상중량(톤)', f: r => ton(r.cw) }, { h: 'kg당 단가', f: r => won(r.yield) },
    ], D.aircraft_route);
  
    // =====================================================================
    // 단가/무게
    // =====================================================================
    const dual = (id, rows, lbl) => mk(id, {
      data: { labels: rows.map(r => r.key), datasets: [
        { type: 'bar', label: 'AWB 건수', data: rows.map(r => r.awb), backgroundColor: '#2f80ed', borderRadius: 4, yAxisID: 'y', datalabels: { display: true, anchor: 'end', align: 'top', formatter: v => num(v), font: { size: 10 } } },
        { type: 'line', label: '매출(억원)', data: rows.map(r => r.rev), borderColor: '#c8102e', backgroundColor: '#c8102e', yAxisID: 'y1', tension: .3, pointRadius: 4 }] },
      options: { maintainAspectRatio: false, layout: { padding: { top: 16 } }, interaction: { mode: 'index', intersect: false }, scales: { x: { ...xNoGrid, title: { display: true, text: lbl } }, y: { beginAtZero: true }, y1: { position: 'right', grid: { display: false }, ticks: { callback: v => eok0(v) + '억' } } },
        plugins: { tooltip: { callbacks: { label: c => c.dataset.yAxisID === 'y' ? `AWB ${num(c.parsed.y)}건` : `매출 ${eok(c.parsed.y)}억 (${pct(rows[c.dataIndex].share)})` } } } }
    });
    dual('p-weight', D.weight_band, '유상중량 구간');
    dual('p-yield', D.yield_band, 'kg당 단가 구간(원)');
    mk('p-density', {
      type: 'pie', data: { labels: D.density.map(d => d.key), datasets: [{ data: D.density.map(d => d.rev), backgroundColor: ['#1f3a5f', '#2f80ed', '#f2994a', '#a0aec0'] }] },
      options: { maintainAspectRatio: false, plugins: { legend: { position: 'right' }, datalabels: { display: true, formatter: v => pct(v / S.total_rev, 0), color: '#fff', font: { weight: 700 } }, tooltip: { callbacks: { label: c => `${c.label}: ${eok(c.parsed)}억 · ${num(D.density[c.dataIndex].awb)}건 · ${won(D.density[c.dataIndex].yield)}/kg` } } } }
    });
    mk('p-currency', {
      type: 'doughnut', data: { labels: D.currency.map(c => c.key), datasets: [{ data: D.currency.map(c => c.rev), backgroundColor: PALETTE }] },
      options: { maintainAspectRatio: false, cutout: '55%', plugins: { legend: { position: 'right' }, datalabels: { display: c => c.dataset.data[c.dataIndex] / S.total_rev > .03, formatter: (v, c) => c.chart.data.labels[c.dataIndex] + '\n' + pct(v / S.total_rev, 0), color: '#fff', font: { weight: 700, size: 11 }, textAlign: 'center' }, tooltip: { callbacks: { label: c => `${c.label}: ${eok(c.parsed)}억 (${pct(c.parsed / S.total_rev)})` } } } }
    });
    mk('p-region-yield', {
      type: 'line', data: { labels: M, datasets: D.regions.slice(0, 8).map((r, i) => ({ label: r.key, data: D.yield_region_monthly[r.key], borderColor: PALETTE[i], backgroundColor: PALETTE[i], tension: .3, pointRadius: 2, spanGaps: true })) },
      options: { maintainAspectRatio: false, interaction: { mode: 'index', intersect: false }, scales: { x: xNoGrid, y: { ticks: { callback: v => num(v) + '원' }, grid: { color: '#eef1f5' } } }, plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: { label: c => `${c.dataset.label}: ${num(c.parsed.y)}원/kg` } } } }
    });
    table('p-currency-table', [
      { h: '통화', k: 'key', left: true }, { h: 'AWB', f: r => num(r.awb) }, { h: '원화 매출(억원)', f: (r, i, m) => barCell(r, m) }, { h: '비중', f: r => pct(r.share) },
      { h: '현지통화 합계', f: r => r._total ? '' : num(r.rev_local) }, { h: '적용 평균환율', f: r => r._total ? '' : (r.avg_rate || 0).toLocaleString('ko-KR', { maximumFractionDigits: 2 }) },
      { h: '유상중량(톤)', f: r => ton(r.cw) }, { h: '매출/AWB', f: r => won(r.rev_per_awb) }, { h: 'kg당 단가', f: r => won(r.yield) },
    ], [...D.currency, totalRow(D.currency)]);
  
    // =====================================================================
    // 감사/청구
    // =====================================================================
    mk('q-spot', {
      type: 'doughnut', data: { labels: D.spot.map(s => s.key), datasets: [{ data: D.spot.map(s => s.rev), backgroundColor: ['#1f3a5f', '#c8102e'] }] },
      options: { maintainAspectRatio: false, cutout: '55%', plugins: { legend: { position: 'right' }, datalabels: { display: true, formatter: (v, c) => `${pct(v / S.total_rev, 0)}\n${num(D.spot[c.dataIndex].awb)}건`, color: '#fff', font: { weight: 700 }, textAlign: 'center' }, tooltip: { callbacks: { label: c => `${c.label}: ${eok(c.parsed)}억 · ${won(D.spot[c.dataIndex].yield)}/kg` } } } }
    });
    const spotShare = M.map((_, i) => { const a = D.spot_monthly['Spot Rate'].rev[i], b = D.spot_monthly['Contract/Tariff'].rev[i]; return a / (a + b) * 100; });
    mk('q-spot-monthly', {
      data: { labels: M, datasets: [
        { type: 'bar', label: 'Spot Rate', data: D.spot_monthly['Spot Rate'].rev, backgroundColor: '#c8102e', stack: 's', yAxisID: 'y' },
        { type: 'bar', label: 'Contract/Tariff', data: D.spot_monthly['Contract/Tariff'].rev, backgroundColor: '#1f3a5f', stack: 's', yAxisID: 'y' },
        { type: 'line', label: 'Spot 비중(%)', data: spotShare, borderColor: '#f2994a', backgroundColor: '#f2994a', yAxisID: 'y1', tension: .3, datalabels: { display: true, align: 'top', formatter: v => v.toFixed(0) + '%', font: { size: 10, weight: 700 }, color: '#d97706' } }] },
      options: { maintainAspectRatio: false, interaction: { mode: 'index', intersect: false }, scales: { x: { ...xNoGrid, stacked: true }, y: { ...yEok, stacked: true, beginAtZero: true }, y1: { position: 'right', min: 0, max: 100, grid: { display: false }, ticks: { callback: v => v + '%' } } } }
    });
    mk('q-billing', {
      type: 'bar', data: { labels: D.billing_status.map(b => b.key), datasets: [{ label: '매출(억원)', data: D.billing_status.map(b => b.rev), backgroundColor: ['#1f3a5f', '#2f80ed', '#27ae60', '#a0aec0'], borderRadius: 6, datalabels: { display: true, anchor: 'end', align: 'top', formatter: (v, c) => `${eok(v)}억 · ${num(D.billing_status[c.dataIndex].awb)}건`, font: { weight: 700, size: 11 } } }] },
      options: { maintainAspectRatio: false, layout: { padding: { top: 20 } }, scales: { x: xNoGrid, y: { ...yEok, beginAtZero: true } }, plugins: { legend: { display: false } } }
    });
    const IB = D.iata_vs_billing;
    mk('q-iata', {
      type: 'bar', data: { labels: ['IATA 감사요금', '시장 감사요금', '실제 청구(Billing)'], datasets: [{ label: '금액(억원)', data: [IB.iata_charge_krw, IB.market_charge_krw, IB.billing_krw], backgroundColor: ['#a0aec0', '#2f80ed', '#c8102e'], borderRadius: 6, datalabels: { display: true, anchor: 'end', align: 'top', formatter: v => eok0(v) + '억', font: { weight: 700 } } }] },
      options: { maintainAspectRatio: false, layout: { padding: { top: 20 } }, scales: { x: xNoGrid, y: { ...yEok, beginAtZero: true } }, plugins: { legend: { display: false }, tooltip: { callbacks: { afterLabel: () => `청구/IATA = ${IB.billing_to_iata_ratio}%` } } } }
    });
    table('q-disc', STD_COLS('불일치 유형'), D.discrepancy);
    table('q-audit', STD_COLS('감사 상태'), D.audit_status);
  
  }

  // =====================================================================
  // YoY (전년 동기 대비) — 연도 선택과 무관하게 1회 렌더
  // =====================================================================
  function renderYoy() {
    const Y = YOY, S = Y.summary, cy = S.cur_year, by = S.base_year, N = S.months.length, lastM = S.months[N - 1];
    const M12 = Array.from({ length: 12 }, (_, i) => `${i + 1}월`);
    const cC = '#c8102e', cB = '#94a3b8';
    const badge = st => ({ '신규': '<span class="badge new">신규</span>', '이탈': '<span class="badge churn">이탈</span>', '동기無': '<span class="badge nobase">전년동기無</span>', '유지': '' })[st] || '';
    const pctCell = v => v == null ? '<span class="tag">n/a</span>' : signed(v);
    const yoyBadge = (v, d = 1) => v == null ? '' : `<span class="${v >= 0 ? 'pos' : 'neg'}">${v >= 0 ? '▲' : '▼'} ${Math.abs(v).toFixed(d)}%</span>`;
    const dlt = S.delta;

    document.getElementById('yoy-note').innerHTML = `※ <b>${cy}년 1~${lastM}월</b> vs <b>${by}년 1~${lastM}월</b> (전년 동기) 비교. 월별 차트에는 ${by}년 9~12월 실적도 참고로 표시. 신규/이탈 판정은 ${by}년 연간 실적 기준. 외화는 각 연도·월의 ECB 참고환율 월평균(원/외화) 적용.`;
    document.getElementById('yoy-monthly-title').textContent = `월별 매출 비교 (${by} vs ${cy})`;
    document.getElementById('yoy-kpi').innerHTML = [
      { cls: 'red', lbl: `${cy} 1~${lastM}월 매출`, val: eok(S.cur.rev), unit: '억원', sub: `전년 동기 ${eok(S.base.rev)}억 → ${yoyBadge(dlt.rev_pct)} (${dlt.rev_diff >= 0 ? '+' : ''}${eok(dlt.rev_diff)}억)` },
      { cls: '', lbl: '유상중량', val: ton(S.cur.cw), unit: '톤', sub: `전년 동기 ${ton(S.base.cw)}톤 → ${yoyBadge(dlt.cw_pct)}` },
      { cls: 'blue', lbl: 'AWB 건수', val: num(S.cur.awb), unit: '건', sub: `전년 동기 ${num(S.base.awb)}건 → ${yoyBadge(dlt.awb_pct)}` },
      { cls: 'green', lbl: 'kg당 단가', val: num(S.cur.yield), unit: '원/kg', sub: `전년 동기 ${num(S.base.yield)}원 → ${yoyBadge(dlt.yield_pct)}` },
      { cls: '', lbl: `${by} 연간 대비 진도`, val: pct(S.progress_vs_base_full, 0), unit: '', sub: `${N}개월 실적 / ${by} 연간 ${eok(S.base_full_year_rev)}억` },
      { cls: 'blue', lbl: `${cy} 단순 연환산`, val: eok0(S.cur_annualized_rev), unit: '억원', sub: `월평균 ${eok(S.cur.rev / N)}억 × 12` },
    ].map(k => `<div class="kpi ${k.cls}"><div class="lbl">${k.lbl}</div><div class="val">${k.val}<small>${k.unit}</small></div><div class="sub">${k.sub}</div></div>`).join('');
    document.getElementById('yoy-insights').innerHTML = Y.insights.map(i => `<li>${i}</li>`).join('');

    mk('y-monthly', {
      data: { labels: M12, datasets: [
        { type: 'bar', label: `${by}`, data: Y.monthly.map(m => m.base_rev), backgroundColor: cB, borderRadius: 4, yAxisID: 'y' },
        { type: 'bar', label: `${cy}`, data: Y.monthly.map(m => m.cur_rev), backgroundColor: cC, borderRadius: 4, yAxisID: 'y' },
        { type: 'line', label: 'YoY(%)', data: Y.monthly.map(m => m.yoy_pct), borderColor: '#f2994a', backgroundColor: '#f2994a', yAxisID: 'y1', tension: .3, spanGaps: false, datalabels: { display: true, align: 'top', formatter: v => v == null ? '' : (v > 0 ? '+' : '') + v.toFixed(0) + '%', font: { size: 10, weight: 700 }, color: '#d97706' } }] },
      options: { maintainAspectRatio: false, interaction: { mode: 'index', intersect: false }, scales: { x: xNoGrid, y: { ...yEok, beginAtZero: true }, y1: { position: 'right', grid: { display: false }, ticks: { callback: v => v + '%' } } },
        plugins: { tooltip: { callbacks: { label: c => c.dataset.yAxisID === 'y' ? `${c.dataset.label}: ${c.parsed.y == null ? '-' : eok(c.parsed.y) + '억'}` : `YoY ${c.parsed.y == null ? '-' : c.parsed.y.toFixed(1) + '%'}` } } } }
    });
    mk('y-cum', {
      type: 'line', data: { labels: M12, datasets: [
        { label: `${by} 누적`, data: Y.cumulative.base, borderColor: cB, backgroundColor: 'rgba(148,163,184,.15)', fill: true, tension: .2 },
        { label: `${cy} 누적`, data: Y.cumulative.cur, borderColor: cC, backgroundColor: 'rgba(200,16,46,.12)', fill: true, tension: .2, datalabels: { display: (c) => c.dataIndex === N - 1, align: 'top', formatter: v => eok0(v) + '억', font: { weight: 700 } } }] },
      options: { maintainAspectRatio: false, interaction: { mode: 'index', intersect: false }, scales: { x: xNoGrid, y: { ...yEok, beginAtZero: true } }, plugins: { tooltip: { callbacks: { label: c => `${c.dataset.label}: ${c.parsed.y == null ? '-' : eok(c.parsed.y) + '억'}` } } } }
    });
    mk('y-yield', {
      data: { labels: M12, datasets: [
        { type: 'bar', label: `${by} 유상중량(t)`, data: Y.monthly.map(m => m.base_cw), backgroundColor: cB + '99', yAxisID: 'y', borderRadius: 3 },
        { type: 'bar', label: `${cy} 유상중량(t)`, data: Y.monthly.map(m => m.cur_cw), backgroundColor: cC + '99', yAxisID: 'y', borderRadius: 3 },
        { type: 'line', label: `${by} 단가`, data: Y.monthly.map(m => m.base_yield), borderColor: '#475569', yAxisID: 'y1', tension: .3, pointRadius: 2 },
        { type: 'line', label: `${cy} 단가`, data: Y.monthly.map(m => m.cur_yield), borderColor: '#16a34a', backgroundColor: '#16a34a', yAxisID: 'y1', tension: .3, pointRadius: 3 }] },
      options: { maintainAspectRatio: false, interaction: { mode: 'index', intersect: false }, scales: { x: xNoGrid, y: { beginAtZero: true, ticks: { callback: v => ton(v) + 't' } }, y1: { position: 'right', grid: { display: false }, ticks: { callback: v => num(v) + '원' } } },
        plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: { label: c => c.parsed.y == null ? `${c.dataset.label}: -` : c.dataset.yAxisID === 'y' ? `${c.dataset.label}: ${ton(c.parsed.y)}톤` : `${c.dataset.label}: ${num(c.parsed.y)}원/kg` } } } }
    });
    const RG = [...Y.region].sort((a, b) => b.cur.rev - a.cur.rev);
    mk('y-region', {
      data: { labels: RG.map(r => r.key), datasets: [
        { type: 'bar', label: `${by} 동기`, data: RG.map(r => r.base.rev), backgroundColor: cB, borderRadius: 4, yAxisID: 'y' },
        { type: 'bar', label: `${cy}`, data: RG.map(r => r.cur.rev), backgroundColor: cC, borderRadius: 4, yAxisID: 'y', datalabels: { display: true, anchor: 'end', align: 'top', formatter: (v, c) => RG[c.dataIndex].rev_pct == null ? '신규' : (RG[c.dataIndex].rev_pct > 0 ? '+' : '') + RG[c.dataIndex].rev_pct.toFixed(0) + '%', font: { size: 10, weight: 700 }, color: (c) => (RG[c.dataIndex].rev_pct ?? 1) >= 0 ? '#15803d' : '#b91c1c' } }] },
      options: { maintainAspectRatio: false, layout: { padding: { top: 16 } }, scales: { x: xNoGrid, y: { ...yEok, beginAtZero: true } }, plugins: { tooltip: { callbacks: { label: c => `${c.dataset.label}: ${eok(c.parsed.y)}억` } } } }
    });
    const contrib = (id, up, down) => {
      const rows = [...up, ...[...down].reverse()];
      mk(id, {
        type: 'bar', data: { labels: rows.map(r => r.key + (r.status !== '유지' ? ` (${r.status})` : '')), datasets: [{ label: '증감(억원)', data: rows.map(r => r.rev_diff), backgroundColor: rows.map(r => r.rev_diff >= 0 ? '#16a34a' : '#dc2626'), borderRadius: 4, datalabels: { display: true, anchor: (c) => c.dataset.data[c.dataIndex] >= 0 ? 'end' : 'start', align: (c) => c.dataset.data[c.dataIndex] >= 0 ? 'right' : 'left', formatter: (v, c) => `${v >= 0 ? '+' : ''}${eok(v)}억${rows[c.dataIndex].rev_pct != null ? ` (${rows[c.dataIndex].rev_pct > 0 ? '+' : ''}${rows[c.dataIndex].rev_pct.toFixed(0)}%)` : ''}`, font: { size: 10 } } }] },
        options: { indexAxis: 'y', maintainAspectRatio: false, layout: { padding: { right: 100, left: 20 } }, scales: { x: { ticks: { callback: v => eok0(v) + '억' }, grid: { color: '#eef1f5' } }, y: { grid: { display: false }, ticks: { font: { size: 11 } } } },
          plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => `${cy}: ${eok(rows[c.dataIndex].cur.rev)}억 · ${by} 동기: ${eok(rows[c.dataIndex].base.rev)}억` } } } }
      });
    };
    contrib('y-route', Y.route_contrib_up, Y.route_contrib_down);
    contrib('y-customer', Y.customer_contrib_up, Y.customer_contrib_down);
    const AC = Y.aircraft.filter(a => a.key !== '미확인').sort((a, b) => b.cur.rev - a.cur.rev);
    mk('y-aircraft', {
      data: { labels: AC.map(a => a.key), datasets: [
        { type: 'bar', label: `${by} 동기`, data: AC.map(a => a.base.rev), backgroundColor: cB, borderRadius: 4 },
        { type: 'bar', label: `${cy}`, data: AC.map(a => a.cur.rev), backgroundColor: cC, borderRadius: 4, datalabels: { display: true, anchor: 'end', align: 'top', formatter: (v, c) => AC[c.dataIndex].rev_pct == null ? '' : (AC[c.dataIndex].rev_pct > 0 ? '+' : '') + AC[c.dataIndex].rev_pct.toFixed(0) + '%', font: { size: 10, weight: 700 } } }] },
      options: { maintainAspectRatio: false, layout: { padding: { top: 16 } }, scales: { x: xNoGrid, y: { ...yEok, beginAtZero: true } }, plugins: { tooltip: { callbacks: { label: c => `${c.dataset.label}: ${eok(c.parsed.y)}억 · ${won(AC[c.dataIndex][c.datasetIndex === 0 ? 'base' : 'cur'].yield)}/kg` } } } }
    });
    const CTy = Y.customer_type.filter(c => c.key !== '미분류');
    mk('y-ctype', {
      data: { labels: CTy.map(c => c.key + ' 업체'), datasets: [
        { type: 'bar', label: `${by} 동기`, data: CTy.map(c => c.base.rev), backgroundColor: cB, borderRadius: 4, yAxisID: 'y' },
        { type: 'bar', label: `${cy}`, data: CTy.map(c => c.cur.rev), backgroundColor: cC, borderRadius: 4, yAxisID: 'y', datalabels: { display: true, anchor: 'end', align: 'top', formatter: (v, c) => `${eok(v)}억 (${CTy[c.dataIndex].rev_pct > 0 ? '+' : ''}${CTy[c.dataIndex].rev_pct}%)`, font: { size: 11, weight: 700 } } },
        { type: 'line', label: 'kg당 단가(원)', data: CTy.map(c => c.cur.yield), borderColor: '#16a34a', backgroundColor: '#16a34a', yAxisID: 'y1', pointRadius: 5 }] },
      options: { maintainAspectRatio: false, layout: { padding: { top: 20 } }, scales: { x: xNoGrid, y: { ...yEok, beginAtZero: true }, y1: { position: 'right', grid: { display: false }, ticks: { callback: v => num(v) + '원' } } } }
    });

    const renderYTable = view => {
      const rows = Y[view];
      table('y-table', [
        { h: '#', f: (r, i) => i + 1 }, { h: '구분', f: r => `${r.key} ${badge(r.status)}`, left: true },
        { h: `${cy} 매출(억)`, f: r => eok(r.cur.rev) }, { h: `${by} 동기(억)`, f: r => eok(r.base.rev) }, { h: '증감(억)', f: r => `<span class="${r.rev_diff >= 0 ? 'pos' : 'neg'}">${r.rev_diff >= 0 ? '+' : ''}${eok(r.rev_diff)}</span>` }, { h: 'YoY', f: r => pctCell(r.rev_pct) },
        { h: `${cy} 비중`, f: r => pct(r.share_cur) }, { h: `${by} 비중`, f: r => pct(r.share_base) },
        { h: `${cy} 중량(t)`, f: r => ton(r.cur.cw) }, { h: '중량 YoY', f: r => pctCell(r.cw_pct) },
        { h: `${cy} AWB`, f: r => num(r.cur.awb) }, { h: 'AWB YoY', f: r => pctCell(r.awb_pct) },
        { h: `${cy} 단가`, f: r => won(r.cur.yield) }, { h: `${by} 단가`, f: r => won(r.base.yield) }, { h: '단가 YoY', f: r => pctCell(r.yield_pct) },
      ], rows);
    };
    renderYTable('customer');
    document.querySelectorAll('#y-seg .seg-btn').forEach(b => b.onclick = () => { document.querySelectorAll('#y-seg .seg-btn').forEach(x => x.classList.remove('active')); b.classList.add('active'); renderYTable(b.dataset.view); });
    table('y-monthly-table', [
      { h: '월', f: r => `${r.month}월`, left: true },
      { h: `${by} 매출(억)`, f: r => eok(r.base_rev) }, { h: `${cy} 매출(억)`, f: r => r.cur_rev == null ? '-' : eok(r.cur_rev) }, { h: 'YoY', f: r => r.yoy_pct == null ? '-' : signed(r.yoy_pct) },
      { h: `${by} 중량(t)`, f: r => ton(r.base_cw) }, { h: `${cy} 중량(t)`, f: r => r.cur_cw == null ? '-' : ton(r.cur_cw) },
      { h: `${by} AWB`, f: r => num(r.base_awb) }, { h: `${cy} AWB`, f: r => r.cur_awb == null ? '-' : num(r.cur_awb) },
      { h: `${by} 단가`, f: r => won(r.base_yield) }, { h: `${cy} 단가`, f: r => r.cur_yield == null ? '-' : won(r.cur_yield) },
    ], Y.monthly);
  }

  // ---------- 연도 선택
  document.getElementById('year-seg').innerHTML = IDX.years.map(y => `<button data-year="${y}">${y}</button>`).join('');
  document.querySelectorAll('#year-seg button').forEach(b => b.addEventListener('click', () => render(+b.dataset.year)));
  await render(IDX.current);
  renderYoy();
})();
