/**
 * Generates report.html from the current pipeline.csv data.
 * Run manually or as the last step of the GitHub Actions workflow.
 */

import { readFileSync, writeFileSync, existsSync } from 'fs';
import { parse } from 'csv-parse/sync';

const PIPELINE_FILE = 'pipeline.csv';
const REPORT_FILE   = 'report.html';

function loadPipeline() {
  if (!existsSync(PIPELINE_FILE)) return [];
  const raw = readFileSync(PIPELINE_FILE, 'utf8').trim();
  if (!raw) return [];
  try { return parse(raw, { columns: true, skip_empty_lines: true, relax_column_count: true }); }
  catch (_) { return []; }
}

function buildReport(rows) {
  const total       = rows.length;
  const sent        = rows.filter(r => r.outcome === 'sent').length;
  const followedUp  = rows.filter(r => r.outcome === 'followup-sent').length;
  const replied     = rows.filter(r => r.outcome === 'replied').length;
  const optOut      = rows.filter(r => r.outcome === 'opt-out').length;
  const demoReq     = rows.filter(r => r.outcome === 'demo-requested').length;
  const replyRate   = total ? ((replied + demoReq) / total * 100).toFixed(1) : '0.0';
  const optOutRate  = total ? (optOut / total * 100).toFixed(1) : '0.0';

  // Last 10 rows (most recent first)
  const recent = [...rows].reverse().slice(0, 10);

  // Activity by date (emails sent per day)
  const byDate = {};
  rows.forEach(r => {
    if (r.sent_date) byDate[r.sent_date] = (byDate[r.sent_date] || 0) + 1;
  });
  const dates  = Object.keys(byDate).sort();
  const counts = dates.map(d => byDate[d]);

  const outcomeData = [sent, followedUp, replied, demoReq, optOut];
  const generated   = new Date().toLocaleString('en-GB', { timeZone: 'Europe/London' });

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Sara AI — Outreach Report</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --navy: #0f1f3d; --teal: #00b4a6; --teal2: #007f76;
      --white: #fff; --off: #f5f8ff; --border: #dde3ee; --grey: #64748b;
    }
    body { font-family: 'Segoe UI', system-ui, sans-serif; background: var(--off); color: var(--navy); }

    header {
      background: var(--navy); color: #fff;
      padding: 28px 40px; display: flex; align-items: center; justify-content: space-between;
    }
    header h1 { font-size: 1.4rem; }
    header h1 span { color: var(--teal); }
    .generated { font-size: .8rem; opacity: .6; margin-top: 4px; }

    main { max-width: 1100px; margin: 0 auto; padding: 32px 24px; }

    /* KPI cards */
    .kpi-grid {
      display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; margin-bottom: 32px;
    }
    .kpi {
      background: var(--white); border: 1px solid var(--border); border-radius: 14px;
      padding: 24px 20px; text-align: center;
    }
    .kpi-num { font-size: 2.4rem; font-weight: 800; color: var(--teal); line-height: 1; }
    .kpi-label { font-size: .8rem; color: var(--grey); margin-top: 6px; }
    .kpi.highlight { border-color: var(--teal); background: rgba(0,180,166,0.04); }

    /* Charts */
    .charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 32px; }
    @media(max-width:700px) { .charts-row { grid-template-columns: 1fr; } }
    .chart-card {
      background: var(--white); border: 1px solid var(--border); border-radius: 14px; padding: 24px;
    }
    .chart-card h3 { font-size: .95rem; margin-bottom: 18px; color: var(--navy); }

    /* Pipeline table */
    .table-card {
      background: var(--white); border: 1px solid var(--border); border-radius: 14px;
      padding: 24px; overflow-x: auto;
    }
    .table-card h3 { font-size: .95rem; margin-bottom: 18px; }
    table { width: 100%; border-collapse: collapse; font-size: .85rem; }
    th { text-align: left; padding: 10px 12px; border-bottom: 2px solid var(--border); color: var(--grey); font-weight: 600; white-space: nowrap; }
    td { padding: 10px 12px; border-bottom: 1px solid var(--border); vertical-align: middle; }
    tr:last-child td { border-bottom: none; }

    .badge {
      display: inline-block; padding: 3px 10px; border-radius: 50px;
      font-size: .75rem; font-weight: 700; white-space: nowrap;
    }
    .badge-sent        { background: #e0f2fe; color: #0369a1; }
    .badge-followup    { background: #fef9c3; color: #92400e; }
    .badge-replied     { background: #dcfce7; color: #166534; }
    .badge-demo        { background: #d1fae5; color: #065f46; }
    .badge-optout      { background: #fee2e2; color: #991b1b; }

    .empty-state { text-align: center; padding: 60px 20px; color: var(--grey); }
    .empty-state p { margin-top: 8px; font-size: .9rem; }
  </style>
</head>
<body>

<header>
  <div>
    <h1>Sara<span>AI</span> — Outreach Report</h1>
    <div class="generated">Generated ${generated} · pipeline.csv</div>
  </div>
</header>

<main>

  <!-- KPIs -->
  <div class="kpi-grid">
    <div class="kpi">
      <div class="kpi-num">${total}</div>
      <div class="kpi-label">Total prospects</div>
    </div>
    <div class="kpi">
      <div class="kpi-num">${sent + followedUp}</div>
      <div class="kpi-label">Emails sent</div>
    </div>
    <div class="kpi">
      <div class="kpi-num">${followedUp}</div>
      <div class="kpi-label">Follow-ups sent</div>
    </div>
    <div class="kpi highlight">
      <div class="kpi-num">${replied + demoReq}</div>
      <div class="kpi-label">Replies received</div>
    </div>
    <div class="kpi highlight">
      <div class="kpi-num">${replyRate}%</div>
      <div class="kpi-label">Reply rate</div>
    </div>
    <div class="kpi">
      <div class="kpi-num">${optOut}</div>
      <div class="kpi-label">Opt-outs honoured</div>
    </div>
  </div>

  <!-- Charts -->
  <div class="charts-row">
    <div class="chart-card">
      <h3>Pipeline by outcome</h3>
      <canvas id="outcomeChart" height="220"></canvas>
    </div>
    <div class="chart-card">
      <h3>Emails sent per day</h3>
      <canvas id="activityChart" height="220"></canvas>
    </div>
  </div>

  <!-- Recent pipeline table -->
  <div class="table-card">
    <h3>Recent prospects (last 10)</h3>
    ${recent.length === 0 ? `
      <div class="empty-state">
        <strong>No data yet</strong>
        <p>The pipeline will populate after the first outreach run.</p>
      </div>` : `
    <table>
      <thead>
        <tr>
          <th>Clinic</th>
          <th>Location</th>
          <th>Email</th>
          <th>Sent</th>
          <th>Follow-up</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        ${recent.map(r => `
        <tr>
          <td><strong>${escHtml(r.clinic_name)}</strong></td>
          <td>${escHtml(r.location)}</td>
          <td><a href="mailto:${escHtml(r.email)}">${escHtml(r.email)}</a></td>
          <td>${escHtml(r.sent_date)}</td>
          <td>${escHtml(r.followup_sent || '—')}</td>
          <td>${badgeHtml(r.outcome)}</td>
        </tr>`).join('')}
      </tbody>
    </table>`}
  </div>

</main>

<script>
// Outcome doughnut
new Chart(document.getElementById('outcomeChart'), {
  type: 'doughnut',
  data: {
    labels: ['Awaiting reply', 'Follow-up sent', 'Replied', 'Demo requested', 'Opted out'],
    datasets: [{
      data: ${JSON.stringify(outcomeData)},
      backgroundColor: ['#60a5fa','#fbbf24','#34d399','#10b981','#f87171'],
      borderWidth: 2,
      borderColor: '#fff',
    }],
  },
  options: {
    plugins: { legend: { position: 'bottom', labels: { font: { size: 12 } } } },
    cutout: '60%',
  },
});

// Activity line chart
new Chart(document.getElementById('activityChart'), {
  type: 'bar',
  data: {
    labels: ${JSON.stringify(dates)},
    datasets: [{
      label: 'Emails sent',
      data: ${JSON.stringify(counts)},
      backgroundColor: 'rgba(0,180,166,0.7)',
      borderRadius: 6,
    }],
  },
  options: {
    plugins: { legend: { display: false } },
    scales: {
      y: { beginAtZero: true, ticks: { stepSize: 1 } },
      x: { ticks: { maxRotation: 45 } },
    },
  },
});
</script>
</body>
</html>`;
}

function escHtml(str = '') {
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function badgeHtml(outcome = '') {
  const map = {
    'sent':            ['Awaiting reply', 'badge-sent'],
    'followup-sent':   ['Followed up',    'badge-followup'],
    'replied':         ['Replied',        'badge-replied'],
    'demo-requested':  ['Demo requested', 'badge-demo'],
    'opt-out':         ['Opted out',      'badge-optout'],
  };
  const [label, cls] = map[outcome] || [outcome, 'badge-sent'];
  return `<span class="badge ${cls}">${label}</span>`;
}

const rows = loadPipeline();
const html = buildReport(rows);
writeFileSync(REPORT_FILE, html);
console.log(`report.html generated (${rows.length} prospects)`);
