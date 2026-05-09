import { refreshPmApiBase, getPmApiBase, pmFetch } from './api/registry.js';
import {
  S,
  defaultDeptGroups,
  QUARTER_MONTH_LABELS,
  QUARTER_MONTHS,
  PHASE_FIELD_KEYS,
  PHASE_FIELD_LABELS,
  STORAGE_KEY_MANPOWER,
  STORAGE_KEY_REGISTER_COLS,
  STORAGE_KEY_RISK,
  STORAGE_KEY_PHASE,
  STORAGE_KEY_LEGACY,
  STORAGE_KEY_APP_SETTINGS
} from './state.js';
import {
  ymKey,
  getProgramProjectSets,
  getSubProjects,
  countSubProjectsInSet,
  newPhaseMonthRow,
  ensurePhaseByMonth,
  getPhaseMonthSlice
} from './domain/dept-phase-core.js';
import { MANPOWER_CHART_COLORS } from './charts/colors.js';

refreshPmApiBase();

function scrollMainToTop() {
  try {
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
  } catch (e) {
    window.scrollTo(0, 0);
  }
  document.documentElement.scrollTop = 0;
  document.body.scrollTop = 0;
}

function normalizeDeptGroups(g) {
  if (!Array.isArray(g) || g.length === 0) return defaultDeptGroups();
  const out = [];
  g.forEach(function (group) {
    const name = String((group && group.name) || '').trim() || '部门分组';
    const depts = Array.isArray(group && group.depts)
      ? group.depts.map(function (d) { return String(d || '').trim() || '子部门'; }).filter(Boolean)
      : [];
    if (depts.length) out.push({ name: name, depts: depts.slice() });
  });
  return out.length ? out : defaultDeptGroups();
}

function deptFlatCount() {
  return S.deptGroups.reduce(function (n, gr) { return n + gr.depts.length; }, 0);
}

function flatDeptIndex(gi, di) {
  let n = 0;
  for (let i = 0; i < gi; i++) n += S.deptGroups[i].depts.length;
  return n + di;
}

function newManpowerRow() {
  const len = deptFlatCount();
  return Array.from({ length: len }, function () { return 0; });
}

function syncPhaseRowPointer() {
  S.phaseData.forEach(function (set) {
    getProgramProjectSets(set).forEach(function (projectSet) {
      getSubProjects(projectSet).forEach(function (p) {
        p._phaseSlice = getPhaseMonthSlice(p, S.phaseSelYear, S.phaseSelMonth);
      });
    });
  });
}

function mapPhaseDataFromStorage(arr) {
  if (!Array.isArray(arr)) return [];
  return arr.map(function (set) {
    var projectSets = getProgramProjectSets(set).map(function (projectSet) {
      var subProjects = getSubProjects(projectSet).map(function (p) {
        var pm = (p && p.phaseByMonth && typeof p.phaseByMonth === 'object') ? p.phaseByMonth : {};
        return {
          name: p && p.name != null ? String(p.name) : '新子项目',
          phaseByMonth: JSON.parse(JSON.stringify(pm))
        };
      });
      return {
        name: projectSet && projectSet.name != null ? String(projectSet.name) : '子项目集',
        subProjects: subProjects
      };
    });
    return {
      name: set && set.name != null ? String(set.name) : '项目集',
      projectSets: projectSets
    };
  });
}

function fixPhaseInData(arr) {
  if (!Array.isArray(arr)) return;
  arr.forEach(function (set) {
    if (!set) return;
    if (!Array.isArray(set.projectSets)) set.projectSets = [];
    set.projectSets.forEach(function (projectSet) {
      if (!projectSet) return;
      if (!Array.isArray(projectSet.subProjects)) projectSet.subProjects = [];
      projectSet.subProjects.forEach(function (p) {
        if (!p) return;
        ensurePhaseByMonth(p);
        Object.keys(p.phaseByMonth).forEach(function (k) {
          var row = p.phaseByMonth[k];
          if (!row || typeof row !== 'object') row = newPhaseMonthRow();
          PHASE_FIELD_KEYS.forEach(function (fk) {
            row[fk] = row[fk] != null ? String(row[fk]) : '';
          });
          p.phaseByMonth[k] = row;
        });
      });
    });
  });
}

/** 无阶段存档时，用人力表中的项目集/项目名称生成阶段表骨架（phaseByMonth 为空） */
function phaseStructureNamesFromData(src) {
  if (!Array.isArray(src)) return [];
  return src.map(function (set) {
    return {
      name: set && set.name != null ? String(set.name) : '项目集',
      projectSets: getProgramProjectSets(set).map(function (projectSet) {
        return {
          name: projectSet && projectSet.name != null ? String(projectSet.name) : '子项目集',
          subProjects: getSubProjects(projectSet).map(function (p) {
            return { name: p && p.name != null ? String(p.name) : '新子项目', phaseByMonth: {} };
          })
        };
      })
    };
  });
}

/**
 * 部门项目人力登记 S.data 与项目阶段状态 S.phaseData 对齐：项目集/项目以阶段表为准；
 * 同集内旧新项目数一致则按下标合并 manpowerByMonth，否则按项目名称从旧行池中匹配。
 */
function syncManpowerStructureFromPhase() {
  if (!Array.isArray(S.phaseData)) S.phaseData = [];
  if (!Array.isArray(S.data)) S.data = [];
  var oldData = S.data.map(function (set) {
    if (!set) return { name: '项目集', projectSets: [] };
    return {
      name: set.name != null ? String(set.name) : '项目集',
      projectSets: getProgramProjectSets(set).map(function (projectSet) {
        return {
          name: projectSet && projectSet.name != null ? String(projectSet.name) : '子项目集',
          subProjects: getSubProjects(projectSet).map(function (p) {
            if (!p) return { name: '新子项目', manpowerByMonth: {} };
            var mb = (p.manpowerByMonth && typeof p.manpowerByMonth === 'object')
              ? JSON.parse(JSON.stringify(p.manpowerByMonth)) : {};
            return { name: p.name != null ? String(p.name) : '新子项目', manpowerByMonth: mb };
          })
        };
      })
    };
  });
  var next = [];
  S.phaseData.forEach(function (phSet, si) {
    if (!phSet) return;
    var phProjectSets = getProgramProjectSets(phSet);
    var oldSet = oldData[si];
    var oldProjectSets = oldSet ? getProgramProjectSets(oldSet) : [];
    var mergedProjectSets = [];
    phProjectSets.forEach(function (phProjectSet, psi) {
      var phProjs = getSubProjects(phProjectSet);
      var oldPs = oldProjectSets[psi];
      var oldProjs = oldPs ? getSubProjects(oldPs).slice() : [];
      var oldLen = oldProjs.length;
      var newLen = phProjs.length;
      var mergedProjs = [];
      if (oldLen === newLen) {
        for (var j = 0; j < newLen; j++) {
          var phP = phProjs[j];
          var oldP = oldProjs[j];
          var mb = (oldP && oldP.manpowerByMonth && typeof oldP.manpowerByMonth === 'object')
            ? JSON.parse(JSON.stringify(oldP.manpowerByMonth)) : {};
          mergedProjs.push({
            name: phP && phP.name != null ? String(phP.name) : '新子项目',
            manpowerByMonth: mb
          });
        }
      } else {
        var pool = oldProjs.map(function (op) {
          return {
            nm: op && op.name != null ? String(op.name) : '',
            manpowerByMonth: (op && op.manpowerByMonth && typeof op.manpowerByMonth === 'object')
              ? JSON.parse(JSON.stringify(op.manpowerByMonth)) : {}
          };
        });
        phProjs.forEach(function (phP) {
          var wantName = phP && phP.name != null ? String(phP.name) : '新子项目';
          var idx = -1;
          for (var pi = 0; pi < pool.length; pi++) {
            if (pool[pi].nm === wantName) {
              idx = pi;
              break;
            }
          }
          var taken = idx >= 0 ? pool.splice(idx, 1)[0] : { nm: wantName, manpowerByMonth: {} };
          mergedProjs.push({ name: wantName, manpowerByMonth: taken.manpowerByMonth });
        });
      }
      mergedProjectSets.push({
        name: phProjectSet && phProjectSet.name != null ? String(phProjectSet.name) : '子项目集',
        subProjects: mergedProjs
      });
    });
    next.push({
      name: phSet.name != null ? String(phSet.name) : '项目集',
      projectSets: mergedProjectSets
    });
  });
  S.data = next;
  fixManpowerInData(S.data);
  syncProjectManpowerPointerToMonth();
}

function ensureProjectHasManpowerByMonth(p) {
  if (!p.manpowerByMonth || typeof p.manpowerByMonth !== 'object') p.manpowerByMonth = {};
}

function getMonthSlice(p, y, m) {
  ensureProjectHasManpowerByMonth(p);
  const need = deptFlatCount();
  const k = ymKey(y, m);
  if (!Array.isArray(p.manpowerByMonth[k])) {
    p.manpowerByMonth[k] = Array.from({ length: need }, function () { return 0; });
  }
  var row = p.manpowerByMonth[k];
  while (row.length < need) row.push(0);
  if (row.length > need) row.splice(need, row.length - need);
  return row;
}

function getDeptValueForMonth(p, y, month, deptIdx) {
  ensureProjectHasManpowerByMonth(p);
  var k = ymKey(y, month);
  if (!Array.isArray(p.manpowerByMonth[k])) return 0;
  var v = p.manpowerByMonth[k][deptIdx];
  return isNaN(Number(v)) ? 0 : Number(v);
}

function sumYearDept(p, year, deptIdx) {
  var s = 0;
  for (var mo = 1; mo <= 12; mo++) s += getDeptValueForMonth(p, year, mo, deptIdx);
  return s;
}

function sumQuarterDept(p, year, qIndex, deptIdx) {
  var s = 0;
  QUARTER_MONTHS[qIndex].forEach(function (mo) {
    s += getDeptValueForMonth(p, year, mo, deptIdx);
  });
  return s;
}

function requireManpowerMonthViewForStructure() {
  if (S.manpowerSubView !== 'month') {
    alert('请在「月度」页面中修改部门结构或人力单元格。');
    return false;
  }
  return true;
}

function syncProjectManpowerPointerToMonth() {
  S.data.forEach(function (set) {
    getProgramProjectSets(set).forEach(function (projectSet) {
      getSubProjects(projectSet).forEach(function (p) {
        p.manpower = getMonthSlice(p, S.manpowerSelYear, S.manpowerSelMonth);
      });
    });
  });
}

function manpowerProjectRowTotal(p) {
  if (!p || !Array.isArray(p.manpower)) return 0;
  return p.manpower.reduce(function (s, x) {
    var n = Number(x);
    return s + (isNaN(n) ? 0 : n);
  }, 0);
}

function buildManpowerMonthAnalysisStats() {
  var setRows = [];
  var allProj = [];
  var grand = 0;
  S.data.forEach(function (set) {
    var setName = set && set.name != null ? String(set.name) : '（未命名项目集）';
    var setSum = 0;
    var projs = [];
    getProgramProjectSets(set).forEach(function (projectSet) {
      var psName = projectSet && projectSet.name != null ? String(projectSet.name) : '（未命名子项目集）';
      getSubProjects(projectSet).forEach(function (p) {
        var t = manpowerProjectRowTotal(p);
        setSum += t;
        var pn = p && p.name != null ? String(p.name) : '（未命名）';
        projs.push({ name: psName + ' · ' + pn, total: t });
        allProj.push({ label: setName + ' · ' + psName + ' · ' + pn, total: t });
      });
    });
    grand += setSum;
    setRows.push({ name: setName, total: setSum, projects: projs });
  });
  allProj.sort(function (a, b) { return b.total - a.total; });
  return { setRows: setRows, allProj: allProj, grand: grand };
}

function destroyManpowerAnalysisCharts() {
  S.manpowerAnalysisCharts.forEach(function (c) {
    try { c.destroy(); } catch (e) {}
  });
  S.manpowerAnalysisCharts = [];
}

function manpowerAnalysisSliceColors(n) {
  var out = [];
  for (var i = 0; i < n; i++) {
    out.push(MANPOWER_CHART_COLORS[i % MANPOWER_CHART_COLORS.length]);
  }
  return out;
}

function closeManpowerAnalysisModal() {
  var mask = document.getElementById('manpower-analysis-mask');
  if (!mask) return;
  if (window._manpowerAnalysisOnKey) {
    document.removeEventListener('keydown', window._manpowerAnalysisOnKey);
    window._manpowerAnalysisOnKey = null;
  }
  destroyManpowerAnalysisCharts();
  mask.classList.remove('active');
  mask.setAttribute('aria-hidden', 'true');
}

function renderManpowerAnalysisCharts(stats) {
  var ChartLib = typeof Chart !== 'undefined' ? Chart : null;
  if (!ChartLib || !stats) return;

  var ctxSet = document.getElementById('manpower-chart-set-pie');
  if (ctxSet) {
    var setLabels = [];
    var setVals = [];
    stats.setRows.forEach(function (r) {
      if (r.total > 0) {
        setLabels.push(r.name);
        setVals.push(r.total);
      }
    });
    var setSum = setVals.reduce(function (a, b) { return a + b; }, 0);
    if (setLabels.length > 0 && setSum > 0) {
      S.manpowerAnalysisCharts.push(new ChartLib(ctxSet, {
        type: 'pie',
        data: {
          labels: setLabels,
          datasets: [{
            data: setVals,
            backgroundColor: manpowerAnalysisSliceColors(setLabels.length),
            borderWidth: 1,
            borderColor: '#fff'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'bottom' },
            tooltip: {
              callbacks: {
                label: function (context) {
                  var num = Number(context.raw);
                  var pct = setSum > 0 ? ((num / setSum) * 100).toFixed(1) : '0.0';
                  return context.label + ': ' + num + '（' + pct + '%）';
                }
              }
            }
          }
        }
      }));
    }
  }

  var grid = document.getElementById('manpower-analysis-set-pies-grid');
  if (grid) {
    grid.innerHTML = '';
    stats.setRows.forEach(function (sr, idx) {
      if (!sr.projects || sr.projects.length === 0) return;
      var labels = [];
      var vals = [];
      sr.projects.forEach(function (pr) {
        if (pr.total > 0) {
          labels.push(pr.name);
          vals.push(pr.total);
        }
      });
      var item = document.createElement('div');
      item.className = 'manpower-analysis-pie-item';
      var h4 = document.createElement('h4');
      h4.textContent = sr.name;
      var cw = document.createElement('div');
      cw.className = 'manpower-analysis-chart-wrap';
      var canvas = document.createElement('canvas');
      canvas.id = 'manpower-chart-setpie-' + idx;
      canvas.setAttribute('aria-label', sr.name + ' 子项目人力占比');
      cw.appendChild(canvas);
      item.appendChild(h4);
      item.appendChild(cw);
      grid.appendChild(item);
      if (labels.length === 0) {
        var note = document.createElement('p');
        note.className = 'manpower-analysis-empty';
        note.style.margin = '12px 0';
        note.style.fontSize = '13px';
        note.textContent = '该集下子项目人力合计为 0';
        item.appendChild(note);
        return;
      }
      var subT = vals.reduce(function (a, b) { return a + b; }, 0);
      S.manpowerAnalysisCharts.push(new ChartLib(canvas, {
        type: 'pie',
        data: {
          labels: labels,
          datasets: [{
            data: vals,
            backgroundColor: manpowerAnalysisSliceColors(labels.length),
            borderWidth: 1,
            borderColor: '#fff'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'bottom' },
            tooltip: {
              callbacks: {
                label: function (context) {
                  var num = Number(context.raw);
                  var pct = subT > 0 ? ((num / subT) * 100).toFixed(1) : '0.0';
                  return context.label + ': ' + num + '（' + pct + '%）';
                }
              }
            }
          }
        }
      }));
    });
  }

  var barCanvas = document.getElementById('manpower-chart-proj-bar');
  var barWrap = document.querySelector('#manpower-analysis-body .manpower-analysis-bar-wrap');
  if (barCanvas && barWrap && stats.allProj.length > 0) {
    var labels = stats.allProj.map(function (x) { return x.label; });
    var vals = stats.allProj.map(function (x) { return x.total; });
    var barTotal = vals.reduce(function (a, b) { return a + b; }, 0);
    var h = Math.min(560, Math.max(200, labels.length * 26));
    barWrap.style.height = h + 'px';
    S.manpowerAnalysisCharts.push(new ChartLib(barCanvas, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: '人力合计',
          data: vals,
          backgroundColor: manpowerAnalysisSliceColors(vals.length),
          borderWidth: 0
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (context) {
                var num = Number(context.raw);
                var pct = barTotal > 0 ? ((num / barTotal) * 100).toFixed(1) : '0.0';
                return '人力 ' + num + '（占当月全员合计 ' + pct + '%）';
              }
            }
          }
        },
        scales: {
          x: { beginAtZero: true, ticks: { precision: 0 } },
          y: { ticks: { autoSkip: false } }
        }
      }
    }));
  }
}

function openManpowerAnalysisModal() {
  if (S.manpowerSubView !== 'month') {
    alert('请切换到「月度」页面后查看人力分析。');
    return;
  }
  if (typeof Chart === 'undefined') {
    alert('图表组件加载失败，请检查网络后刷新页面。');
    return;
  }
  syncProjectManpowerPointerToMonth();
  var mask = document.getElementById('manpower-analysis-mask');
  var periodEl = document.getElementById('manpower-analysis-period');
  var emptyEl = document.getElementById('manpower-analysis-empty');
  var body = document.getElementById('manpower-analysis-body');
  if (!mask || !body) return;

  destroyManpowerAnalysisCharts();
  var grid = document.getElementById('manpower-analysis-set-pies-grid');
  if (grid) grid.innerHTML = '';

  if (periodEl) {
    periodEl.textContent = '统计范围：' + S.manpowerSelYear + '年' + S.manpowerSelMonth + '月（各部门人力列求和汇总）';
  }

  var stats = buildManpowerMonthAnalysisStats();
  var sections = body.querySelectorAll('.manpower-analysis-section');

  if (stats.grand <= 0) {
    if (emptyEl) {
      emptyEl.hidden = false;
      emptyEl.textContent = '当月各项目人力合计为 0，暂无分析图表。';
    }
    sections.forEach(function (sec) { sec.style.display = 'none'; });
  } else {
    if (emptyEl) emptyEl.hidden = true;
    sections.forEach(function (sec) { sec.style.display = ''; });
    renderManpowerAnalysisCharts(stats);
  }

  mask.classList.add('active');
  mask.setAttribute('aria-hidden', 'false');
  window._manpowerAnalysisOnKey = function (e) {
    if (e.key === 'Escape') {
      e.preventDefault();
      closeManpowerAnalysisModal();
    }
  };
  document.addEventListener('keydown', window._manpowerAnalysisOnKey);
  requestAnimationFrame(function () {
    var btn = document.getElementById('manpower-analysis-close');
    if (btn) btn.focus();
  });
}

function updateManpowerToolbarInputs() {
  var ym = document.getElementById('manpower-year-month');
  var ys = document.getElementById('manpower-year-season');
  var yy = document.getElementById('manpower-year-year');
  var sm = document.getElementById('manpower-month-select');
  var sq = document.getElementById('manpower-quarter-select');
  if (ym) ym.value = String(S.manpowerSelYear);
  if (ys) ys.value = String(S.manpowerSelYear);
  if (yy) yy.value = String(S.manpowerSelYear);
  if (sm) sm.value = String(S.manpowerSelMonth);
  if (sq) sq.value = String(S.manpowerSelQuarter);
}

function initManpowerTimeUi() {
  var sm = document.getElementById('manpower-month-select');
  if (sm && sm.options.length === 0) {
    for (var mo = 1; mo <= 12; mo++) {
      var o = document.createElement('option');
      o.value = String(mo);
      o.textContent = mo + '月';
      sm.appendChild(o);
    }
    sm.value = String(S.manpowerSelMonth);
  }
  var sq = document.getElementById('manpower-quarter-select');
  if (sq && sq.options.length === 0) {
    for (var qi = 0; qi < 4; qi++) {
      var qo = document.createElement('option');
      qo.value = String(qi);
      qo.textContent = QUARTER_MONTH_LABELS[qi];
      sq.appendChild(qo);
    }
    sq.value = String(S.manpowerSelQuarter);
  }
  document.querySelectorAll('.manpower-subtab').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var page = btn.getAttribute('S.data-manpower-page');
      if (!page) return;
      S.manpowerSubView = page;
      document.querySelectorAll('.manpower-subtab').forEach(function (b) {
        var on = b === btn;
        b.classList.toggle('active', on);
        b.setAttribute('aria-selected', on ? 'true' : 'false');
      });
      document.querySelectorAll('.manpower-subpage').forEach(function (el) {
        var active = el.id === 'manpower-page-' + page;
        el.classList.toggle('active', active);
        el.setAttribute('aria-hidden', active ? 'false' : 'true');
      });
      renderTable();
      scrollMainToTop();
    });
  });
  var ym = document.getElementById('manpower-year-month');
  var ys = document.getElementById('manpower-year-season');
  var yy = document.getElementById('manpower-year-year');
  if (ym) ym.addEventListener('change', function () {
    var v = parseInt(ym.value, 10);
    if (!isNaN(v) && v >= 2000 && v <= 2099) {
      S.manpowerSelYear = v;
      renderTable();
    }
  });
  if (ys) ys.addEventListener('change', function () {
    var v = parseInt(ys.value, 10);
    if (!isNaN(v) && v >= 2000 && v <= 2099) {
      S.manpowerSelYear = v;
      renderTable();
    }
  });
  if (yy) yy.addEventListener('change', function () {
    var v = parseInt(yy.value, 10);
    if (!isNaN(v) && v >= 2000 && v <= 2099) {
      S.manpowerSelYear = v;
      renderTable();
    }
  });
  if (sm) sm.addEventListener('change', function () {
    var v = parseInt(sm.value, 10);
    if (!isNaN(v) && v >= 1 && v <= 12) {
      S.manpowerSelMonth = v;
      renderTable();
    }
  });
  if (sq) sq.addEventListener('change', function () {
    var v = parseInt(sq.value, 10);
    if (!isNaN(v) && v >= 0 && v <= 3) {
      S.manpowerSelQuarter = v;
      renderTable();
    }
  });
  var btnAn = document.getElementById('btn-manpower-month-analysis');
  if (btnAn) btnAn.addEventListener('click', openManpowerAnalysisModal);
  var maskAn = document.getElementById('manpower-analysis-mask');
  var closeAn = document.getElementById('manpower-analysis-close');
  if (maskAn) {
    maskAn.addEventListener('click', function (e) {
      if (e.target === maskAn) closeManpowerAnalysisModal();
    });
  }
  if (closeAn) closeAn.addEventListener('click', closeManpowerAnalysisModal);
  updateManpowerToolbarInputs();
}

function getRegisterColCount() {
  return 2 + deptFlatCount();
}

function getRegisterColMin(colIndex) {
  if (colIndex === 0) return 100;
  if (colIndex === 1) return 120;
  return 56;
}

function loadRegisterColWidths() {
  const n = getRegisterColCount();
  const def = [];
  def[0] = 168;
  def[1] = 200;
  for (let i = 2; i < n; i++) def[i] = 96;
  const merged = def.slice();
  try {
    const raw = localStorage.getItem(STORAGE_KEY_REGISTER_COLS);
    if (raw) {
      const o = JSON.parse(raw);
      if (o && Array.isArray(o.widths)) {
        for (let j = 0; j < n && j < o.widths.length; j++) {
          const v = Number(o.widths[j]);
          if (!isNaN(v) && v >= getRegisterColMin(j)) merged[j] = v;
        }
      }
    }
  } catch (e) {}
  S.registerColWidths = merged;
}

function saveRegisterColWidths() {
  try {
    localStorage.setItem(STORAGE_KEY_REGISTER_COLS, JSON.stringify({
      widths: S.registerColWidths,
      savedAt: new Date().toISOString()
    }));
  } catch (e) {}
}

function applyRegisterColWidthsToDom() {
  const cg = document.getElementById('register-colgroup');
  if (!cg) return;
  const cols = cg.querySelectorAll('col');
  for (let i = 0; i < cols.length && i < S.registerColWidths.length; i++) {
    cols[i].style.width = S.registerColWidths[i] + 'px';
  }
}

function startRegisterColResizeDrag(colIndex, clientX) {
  S.registerColResizeDrag = {
    colIndex: colIndex,
    startX: clientX,
    startWidths: S.registerColWidths.slice()
  };
  document.body.style.userSelect = 'none';
  document.body.style.cursor = 'col-resize';

  function onMove(e) {
    if (!S.registerColResizeDrag) return;
    const idx = S.registerColResizeDrag.colIndex;
    const w = S.registerColResizeDrag.startWidths;
    const deltaRaw = e.clientX - S.registerColResizeDrag.startX;
    let delta = deltaRaw;
    if (idx < w.length - 1) {
      const minL = getRegisterColMin(idx);
      const minR = getRegisterColMin(idx + 1);
      const maxPos = w[idx + 1] - minR;
      const maxNeg = -(w[idx] - minL);
      delta = Math.max(maxNeg, Math.min(maxPos, delta));
      S.registerColWidths[idx] = w[idx] + delta;
      S.registerColWidths[idx + 1] = w[idx + 1] - delta;
    } else {
      S.registerColWidths[idx] = Math.max(getRegisterColMin(idx), Math.min(520, w[idx] + deltaRaw));
    }
    applyRegisterColWidthsToDom();
  }

  function onUp() {
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup', onUp);
    document.body.style.userSelect = '';
    document.body.style.cursor = '';
    S.registerColResizeDrag = null;
    saveRegisterColWidths();
  }

  document.addEventListener('mousemove', onMove);
  document.addEventListener('mouseup', onUp);
}

function attachRegisterColResizeHandles() {
  const thead = document.getElementById('register-thead');
  if (!thead || thead.rows.length < 2) return;
  thead.querySelectorAll('.register-col-resize-handle').forEach(function (el) {
    el.remove();
  });
  const tr1 = thead.rows[0];
  const tr2 = thead.rows[1];
  function addHandle(th, colIndex) {
    if (!th) return;
    const h = document.createElement('div');
    h.className = 'register-col-resize-handle';
    h.title = '拖动调整列宽';
    h.addEventListener('mousedown', function (e) {
      e.preventDefault();
      e.stopPropagation();
      startRegisterColResizeDrag(colIndex, e.clientX);
    });
    th.appendChild(h);
  }
  addHandle(tr1.cells[0], 0);
  addHandle(tr1.cells[1], 1);
  for (let i = 0; i < tr2.cells.length; i++) {
    addHandle(tr2.cells[i], 2 + i);
  }
}

function syncRegisterColgroup() {
  loadRegisterColWidths();
  const cg = document.getElementById('register-colgroup');
  if (!cg) return;
  cg.innerHTML = '';
  S.registerColWidths.forEach(function (w) {
    const col = document.createElement('col');
    col.style.width = w + 'px';
    cg.appendChild(col);
  });
  attachRegisterColResizeHandles();
}

function openDeleteModal() {
  const mask = document.getElementById('modal-mask');
  S.modalFocusReturn = document.activeElement;
  mask.classList.add('active');
  mask.setAttribute('aria-hidden', 'false');
  requestAnimationFrame(function () {
    const btn = document.getElementById('modal-btn-confirm');
    if (btn) btn.focus();
  });
}

async function fetchAuthMe() {
  var authAbortTid = null;
  var ctrl = null;
  try {
    ctrl = typeof AbortController !== 'undefined' ? new AbortController() : null;
    if (ctrl) {
      authAbortTid = setTimeout(function () {
        try { ctrl.abort(); } catch (abErr) {}
      }, 8000);
    }
    var r = await pmFetch('/api/v1/auth/me', { method: 'GET', signal: ctrl ? ctrl.signal : undefined });
    if (authAbortTid) clearTimeout(authAbortTid);
    if (r.status === 401) {
      window.__pmAuthRedirecting = true;
      window.location.href = 'login.html';
      return null;
    }
    if (!r.ok) {
      alert('认证服务暂时不可用（HTTP ' + r.status + '），已按普通用户权限进入（仅本地数据）。');
      return { id: 0, username: 'unknown', role: 'viewer' };
    }
    return await r.json();
  } catch (e) {
    if (authAbortTid) clearTimeout(authAbortTid);
    alert('无法连接认证后端（' + getPmApiBase() + '）。请先启动 API 服务；已按普通用户权限进入（仅本地）。');
    return { id: 0, username: 'offline', role: 'viewer' };
  }
}

function pmLogout() {
  pmFetch('/api/v1/auth/logout', { method: 'POST', body: '{}' }).catch(function () {});
  window.location.href = 'login.html';
}

async function applyMeFromServer() {
  try {
    var mr = await pmFetch('/api/v1/auth/me', { method: 'GET' });
    if (!mr.ok) return;
    var nm = await mr.json();
    window.__pmCurrentUser = nm;
    S.appUserRole = nm.role === 'admin' ? 'admin' : 'viewer';
    syncPmRoleGlobal();
    applyPermissionToAllUI();
    renderTable();
    renderRiskTable();
    renderPhaseTable();
    updateSettingsPanelRoleUi();
    var pg = document.getElementById('panel-guide');
    if (pg && pg.classList.contains('active') && typeof window.__renderGuideMenu === 'function') {
      window.__renderGuideMenu();
    }
  } catch (e) {}
}

function syncPmRoleGlobal() {
  window.pmIsAdmin = function () { return S.appUserRole === 'admin'; };
}

function canEditPanel(panel) {
  return !!(window.pmIsAdmin && window.pmIsAdmin() && S.panelEditMode[panel]);
}

function setPanelEditMode(panel, editing) {
  if (!(window.pmIsAdmin && window.pmIsAdmin())) return;
  S.panelEditMode[panel] = !!editing;
  applyPermissionToAllUI();
  if (panel === 'manpower') renderTable();
  else if (panel === 'phase') renderPhaseTable();
  else if (panel === 'risk') renderRiskTable();
}

function wirePanelEditToggleButtons() {
  [
    { id: 'btn-manpower-edit-toggle', panel: 'manpower' },
    { id: 'btn-phase-edit-toggle', panel: 'phase' },
    { id: 'btn-risk-edit-toggle', panel: 'risk' }
  ].forEach(function (cfg) {
    var btn = document.getElementById(cfg.id);
    if (!btn || btn._pmEditWired) return;
    btn._pmEditWired = true;
    btn.addEventListener('click', function () {
      if (!requireAdminOrAlert()) return;
      setPanelEditMode(cfg.panel, !S.panelEditMode[cfg.panel]);
    });
  });
}

/** 与 renderRiskTable 中控件顺序一致，供 syncRiskRowsFromDom 使用 */
const RISK_FIELD_ORDER = ['category', 'source', 'project', 'issue', 'solution', 'level', 'owner', 'regTime', 'closeTime', 'status'];

function riskLevelToNum(level) {
  var order = { '低': 1, '中': 2, '高': 3, '极高': 4 };
  var v = level != null ? String(level).trim() : '';
  return order[v] != null ? order[v] : 0;
}

function riskLevelNumToLabel(n) {
  var map = { 0: '未选/未知', 1: '低', 2: '中', 3: '高', 4: '极高' };
  return map[n] != null ? map[n] : '—';
}

function riskRowGroupKey(row) {
  var proj = row && row.project != null ? String(row.project).trim() : '';
  if (proj) return proj.length > 48 ? proj.slice(0, 48) + '…' : proj;
  var d = row && row.issue != null ? String(row.issue).trim() : '';
  if (d) {
    var line = d.split(/\r?\n/)[0].trim();
    if (!line) line = d;
    return line.length > 48 ? line.slice(0, 48) + '…' : line;
  }
  return '（未填写项目与问题）';
}

function buildRiskAnalysisStats() {
  var statusMap = {};
  var groupMap = {};
  S.riskRows.forEach(function (row) {
    var st = row.status != null ? String(row.status).trim() : '';
    if (!st) st = '（未填状态）';
    statusMap[st] = (statusMap[st] || 0) + 1;

    var gk = riskRowGroupKey(row);
    if (!groupMap[gk]) {
      groupMap[gk] = { label: gk, count: 0, maxLevel: 0 };
    }
    groupMap[gk].count += 1;
    var ln = riskLevelToNum(row.level);
    if (ln > groupMap[gk].maxLevel) groupMap[gk].maxLevel = ln;
  });
  var groups = Object.keys(groupMap).map(function (k) {
    return groupMap[k];
  });
  return { statusMap: statusMap, groups: groups };
}

function destroyRiskAnalysisCharts() {
  S.riskAnalysisCharts.forEach(function (c) {
    try { c.destroy(); } catch (e) {}
  });
  S.riskAnalysisCharts = [];
}

function destroyRiskAnalysisBarChartOnly() {
  var el = document.getElementById('risk-chart-group-bar');
  if (!el || typeof Chart === 'undefined') return;
  var c = Chart.getChart(el);
  if (c) {
    var ix = S.riskAnalysisCharts.indexOf(c);
    if (ix >= 0) S.riskAnalysisCharts.splice(ix, 1);
    try { c.destroy(); } catch (e2) {}
  }
}

function riskAnalysisSliceColors(n) {
  var pal = MANPOWER_CHART_COLORS;
  var out = [];
  for (var i = 0; i < n; i++) {
    out.push(pal[i % pal.length]);
  }
  return out;
}

function renderRiskAnalysisStatusPie(stats) {
  if (!stats || typeof Chart === 'undefined') return;
  var ctx = document.getElementById('risk-chart-status-pie');
  if (!ctx) return;
  var labels = [];
  var vals = [];
  Object.keys(stats.statusMap).forEach(function (k) {
    var v = stats.statusMap[k];
    if (v > 0) {
      labels.push(k);
      vals.push(v);
    }
  });
  var total = vals.reduce(function (a, b) { return a + b; }, 0);
  if (labels.length === 0 || total <= 0) return;
  S.riskAnalysisCharts.push(new Chart(ctx, {
    type: 'pie',
    data: {
      labels: labels,
      datasets: [{
        data: vals,
        backgroundColor: riskAnalysisSliceColors(labels.length),
        borderWidth: 1,
        borderColor: '#fff'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom' },
        tooltip: {
          callbacks: {
            label: function (context) {
              var num = Number(context.raw);
              var pct = total > 0 ? ((num / total) * 100).toFixed(1) : '0.0';
              return context.label + ': ' + num + ' 条（' + pct + '%）';
            }
          }
        }
      }
    }
  }));
}

function renderRiskAnalysisGroupBar(stats) {
  if (!stats || typeof Chart === 'undefined') return;
  var canvas = document.getElementById('risk-chart-group-bar');
  var wrap = document.getElementById('risk-group-bar-wrap');
  if (!canvas || !wrap) return;
  var sorted = stats.groups.slice();
  if (S.riskAnalysisSortMode === 'count') {
    sorted.sort(function (a, b) {
      return b.count - a.count || b.maxLevel - a.maxLevel || a.label.localeCompare(b.label, 'zh-CN');
    });
  } else {
    sorted.sort(function (a, b) {
      return b.maxLevel - a.maxLevel || b.count - a.count || a.label.localeCompare(b.label, 'zh-CN');
    });
  }
  var labels = sorted.map(function (g) {
    return g.label.length > 32 ? g.label.slice(0, 32) + '…' : g.label;
  });
  var counts = sorted.map(function (g) { return g.count; });
  var maxLv = sorted.map(function (g) { return g.maxLevel; });
  if (labels.length === 0) return;
  var h = Math.min(520, Math.max(200, labels.length * 28));
  wrap.style.height = h + 'px';
  var totalAll = counts.reduce(function (a, b) { return a + b; }, 0);
  S.riskAnalysisCharts.push(new Chart(canvas, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: '风险条数',
        data: counts,
        backgroundColor: riskAnalysisSliceColors(counts.length),
        borderWidth: 0
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: function (items) {
              var i = items[0].dataIndex;
              return sorted[i].label;
            },
            label: function (context) {
              var i = context.dataIndex;
              var cnt = counts[i];
              var pct = totalAll > 0 ? ((cnt / totalAll) * 100).toFixed(1) : '0.0';
              return [
                '条数: ' + cnt + '（占全部 ' + pct + '%）',
                '组内最高等级: ' + riskLevelNumToLabel(maxLv[i])
              ];
            }
          }
        }
      },
      scales: {
        x: { beginAtZero: true, ticks: { precision: 0 } },
        y: { ticks: { autoSkip: false } }
      }
    }
  }));
}

function redrawRiskAnalysisBarOnly() {
  if (!S.lastRiskAnalysisStats) return;
  destroyRiskAnalysisBarChartOnly();
  renderRiskAnalysisGroupBar(S.lastRiskAnalysisStats);
}

function closeRiskAnalysisModal() {
  var mask = document.getElementById('risk-analysis-mask');
  if (!mask) return;
  if (window._riskAnalysisOnKey) {
    document.removeEventListener('keydown', window._riskAnalysisOnKey);
    window._riskAnalysisOnKey = null;
  }
  destroyRiskAnalysisCharts();
  mask.classList.remove('active');
  mask.setAttribute('aria-hidden', 'true');
}

function openRiskAnalysisModal() {
  if (typeof Chart === 'undefined') {
    alert('图表组件加载失败，请检查网络后刷新页面。');
    return;
  }
  syncRiskRowsFromDom();
  var mask = document.getElementById('risk-analysis-mask');
  var noteEl = document.getElementById('risk-analysis-note');
  var emptyEl = document.getElementById('risk-analysis-empty');
  var body = document.getElementById('risk-analysis-body');
  if (!mask || !body) return;

  destroyRiskAnalysisCharts();
  S.lastRiskAnalysisStats = null;

  if (noteEl) {
    noteEl.textContent = '基于当前列表共 ' + S.riskRows.length + ' 条风险记录（含未保存的编辑内容）。';
  }

  var sections = body.querySelectorAll('.manpower-analysis-section');

  if (S.riskRows.length === 0) {
    if (emptyEl) {
      emptyEl.hidden = false;
      emptyEl.textContent = '暂无风险记录，无法生成分析。';
    }
    sections.forEach(function (sec) { sec.style.display = 'none'; });
  } else {
    if (emptyEl) emptyEl.hidden = true;
    sections.forEach(function (sec) { sec.style.display = ''; });
    S.lastRiskAnalysisStats = buildRiskAnalysisStats();
    renderRiskAnalysisStatusPie(S.lastRiskAnalysisStats);
    renderRiskAnalysisGroupBar(S.lastRiskAnalysisStats);
  }

  mask.classList.add('active');
  mask.setAttribute('aria-hidden', 'false');
  window._riskAnalysisOnKey = function (e) {
    if (e.key === 'Escape') {
      e.preventDefault();
      closeRiskAnalysisModal();
    }
  };
  document.addEventListener('keydown', window._riskAnalysisOnKey);
  requestAnimationFrame(function () {
    var btn = document.getElementById('risk-analysis-close');
    if (btn) btn.focus();
  });
}

function initRiskAnalysisUi() {
  var btn = document.getElementById('btn-risk-analysis');
  if (btn) btn.addEventListener('click', openRiskAnalysisModal);
  var mask = document.getElementById('risk-analysis-mask');
  var closeBtn = document.getElementById('risk-analysis-close');
  if (mask) {
    mask.addEventListener('click', function (e) {
      if (e.target === mask) closeRiskAnalysisModal();
    });
  }
  if (closeBtn) closeBtn.addEventListener('click', closeRiskAnalysisModal);
  document.querySelectorAll('.risk-analysis-sort-btn').forEach(function (b) {
    b.addEventListener('click', function () {
      var mode = b.getAttribute('S.data-risk-sort');
      if (!mode) return;
      S.riskAnalysisSortMode = mode;
      document.querySelectorAll('.risk-analysis-sort-btn').forEach(function (x) {
        var on = x.getAttribute('S.data-risk-sort') === mode;
        x.classList.toggle('active', on);
        x.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
      var m = document.getElementById('risk-analysis-mask');
      if (m && m.classList.contains('active') && S.lastRiskAnalysisStats) {
        redrawRiskAnalysisBarOnly();
      }
    });
  });
  document.querySelectorAll('.risk-analysis-sort-btn').forEach(function (x) {
    x.setAttribute('aria-pressed', x.classList.contains('active') ? 'true' : 'false');
  });
}

function loadAppSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_APP_SETTINGS);
    if (raw) {
      JSON.parse(raw);
    }
  } catch (e) {}
  syncPmRoleGlobal();
}

function saveAppSettings() {
  try {
    localStorage.setItem(STORAGE_KEY_APP_SETTINGS, JSON.stringify({
      savedAt: new Date().toISOString()
    }));
  } catch (e) {}
}

function requireAdminOrAlert() {
  if (!window.pmIsAdmin || !window.pmIsAdmin()) {
    alert('当前为普通用户身份，仅可查看。如需编辑或保存，请使用管理员账号登录。');
    return false;
  }
  return true;
}

function applyPermissionToAllUI() {
  const adm = window.pmIsAdmin && window.pmIsAdmin();
  if (!adm) {
    S.panelEditMode.manpower = false;
    S.panelEditMode.phase = false;
    S.panelEditMode.risk = false;
  }
  var panelConfigs = [
    { panel: 'manpower', toggleId: 'btn-manpower-edit-toggle', editSelector: '#panel-manpower .manpower-edit-only' },
    { panel: 'phase', toggleId: 'btn-phase-edit-toggle', editSelector: '#panel-phase .phase-edit-only' },
    { panel: 'risk', toggleId: 'btn-risk-edit-toggle', editSelector: '#panel-risk .risk-edit-only' }
  ];
  panelConfigs.forEach(function (cfg) {
    var toggleBtn = document.getElementById(cfg.toggleId);
    var editing = adm && !!S.panelEditMode[cfg.panel];
    if (toggleBtn) {
      toggleBtn.style.display = adm ? '' : 'none';
      toggleBtn.textContent = editing ? '完成编辑' : '编辑';
      toggleBtn.title = editing ? '退出编辑模式，回到简洁查看态' : '进入编辑模式后显示增删改与保存按钮';
    }
    document.querySelectorAll(cfg.editSelector).forEach(function (btn) {
      btn.style.display = editing ? '' : 'none';
      btn.disabled = !editing;
      if (!btn.getAttribute('S.data-orig-title') && btn.getAttribute('title')) {
        btn.setAttribute('S.data-orig-title', btn.getAttribute('title'));
      }
      if (btn.getAttribute('S.data-orig-title')) {
        btn.title = editing ? (btn.getAttribute('S.data-orig-title') || '') : '';
      }
    });
  });
}

function updateSettingsPanelRoleUi() {
  const badge = document.getElementById('settings-role-badge');
  const me = window.__pmCurrentUser || {};
  const un = me.username != null ? String(me.username) : '';
  if (badge) {
    if (S.appUserRole === 'admin') {
      badge.textContent = '当前账号「' + un + '」为管理员：可进行增删改查、保存与人员管理。';
    } else {
      badge.textContent = '当前账号「' + un + '」为普通用户：各页仅可查看，不可编辑或保存。';
    }
  }
  const navHint = document.getElementById('pm-nav-user-hint');
  if (navHint) {
    navHint.textContent = un ? (un + ' · ' + (S.appUserRole === 'admin' ? '管理员' : '普通用户')) : '';
  }
  const adminWrap = document.getElementById('settings-users-admin');
  const viewerNote = document.getElementById('settings-users-viewer-note');
  if (adminWrap && viewerNote) {
    if (window.pmIsAdmin && window.pmIsAdmin()) {
      adminWrap.style.display = '';
      viewerNote.style.display = 'none';
      refreshUsersTable();
    } else {
      adminWrap.style.display = 'none';
      viewerNote.style.display = '';
    }
  }
}

async function refreshUsersTable() {
  if (!window.pmIsAdmin || !window.pmIsAdmin()) return;
  const tb = document.getElementById('settings-users-tbody');
  if (!tb) return;
  try {
    var r = await pmFetch('/api/v1/users', { method: 'GET' });
    if (!r.ok) {
      tb.innerHTML = '<tr><td colspan="5">加载用户列表失败（HTTP ' + r.status + '）</td></tr>';
      return;
    }
    var list = await r.json();
    tb.innerHTML = '';
    list.forEach(function (u) {
      var tr = document.createElement('tr');
      var roleLabel = u.role === 'admin' ? '管理员' : '普通用户';
      var activeLabel = u.is_active ? '正常' : '已停用';
      tr.innerHTML =
        '<td>' + escapeHtml(u.username) + '</td>' +
        '<td><select class="settings-user-role-sel" S.data-user-id="' + u.id + '" aria-label="角色">' +
        '<option value="viewer"' + (u.role === 'viewer' ? ' selected' : '') + '>普通用户</option>' +
        '<option value="admin"' + (u.role === 'admin' ? ' selected' : '') + '>管理员</option></select></td>' +
        '<td>' + escapeHtml(activeLabel) + '</td>' +
        '<td>' + escapeHtml(u.auth_source || 'local') + '</td>' +
        '<td class="settings-users-actions"></td>';
      var tdAct = tr.querySelector('.settings-users-actions');
      var selR = tr.querySelector('.settings-user-role-sel');
      selR.addEventListener('change', async function () {
        try {
          var pr = await pmFetch('/api/v1/users/' + u.id, {
            method: 'PATCH',
            body: JSON.stringify({ role: selR.value })
          });
          if (!pr.ok) {
            var err = await pr.json().catch(function () { return {}; });
            alert(err.detail || '更新角色失败');
            selR.value = u.role;
            return;
          }
          if (window.__pmCurrentUser && u.id === window.__pmCurrentUser.id) {
            await applyMeFromServer();
          }
          await refreshUsersTable();
          updateSettingsPanelRoleUi();
        } catch (e) {
          alert('更新失败');
          selR.value = u.role;
        }
      });
      function addBtn(text, className, onClick) {
        var b = document.createElement('button');
        b.type = 'button';
        b.textContent = text;
        if (className) b.className = className;
        b.addEventListener('click', onClick);
        tdAct.appendChild(b);
      }
      addBtn(u.is_active ? '停用' : '启用', '', async function () {
        if (!confirm(u.is_active ? '确认停用该用户？' : '确认启用该用户？')) return;
        var pr = await pmFetch('/api/v1/users/' + u.id, {
          method: 'PATCH',
          body: JSON.stringify({ is_active: !u.is_active })
        });
        if (!pr.ok) {
          var err = await pr.json().catch(function () { return {}; });
          alert(err.detail || '操作失败');
          return;
        }
        if (window.__pmCurrentUser && u.id === window.__pmCurrentUser.id) {
          await applyMeFromServer();
        }
        await refreshUsersTable();
      });
      addBtn('重置密码', '', function () {
        var np = prompt('为「' + u.username + '」设置新密码（至少 6 位）：', '');
        if (!np || np.length < 6) {
          if (np !== null) alert('密码至少 6 位');
          return;
        }
        (async function () {
          var pr = await pmFetch('/api/v1/users/' + u.id, {
            method: 'PATCH',
            body: JSON.stringify({ password: np })
          });
          if (!pr.ok) {
            var err = await pr.json().catch(function () { return {}; });
            alert(err.detail || '重置失败');
            return;
          }
          alert('密码已更新');
        })();
      });
      addBtn('删除', 'danger', async function () {
        if (!confirm('确认删除用户「' + u.username + '」？不可恢复。')) return;
        var pr = await pmFetch('/api/v1/users/' + u.id, { method: 'DELETE' });
        if (!pr.ok) {
          var err = await pr.json().catch(function () { return {}; });
          alert(err.detail || '删除失败');
          return;
        }
        await refreshUsersTable();
      });
      tb.appendChild(tr);
    });
  } catch (e) {
    tb.innerHTML = '<tr><td colspan="5">加载失败</td></tr>';
  }
}

function bindPmLogoutButtons() {
  ['pm-btn-logout-nav', 'pm-btn-logout-settings'].forEach(function (id) {
    var el = document.getElementById(id);
    if (el && !el._pmLogoutBound) {
      el._pmLogoutBound = true;
      el.addEventListener('click', function () { pmLogout(); });
    }
  });
  var createBtn = document.getElementById('settings-btn-user-create');
  if (createBtn && !createBtn._pmBound) {
    createBtn._pmBound = true;
    createBtn.addEventListener('click', async function () {
      var nameEl = document.getElementById('settings-new-user-name');
      var passEl = document.getElementById('settings-new-user-pass');
      var roleEl = document.getElementById('settings-new-user-role');
      var username = nameEl && nameEl.value ? nameEl.value.trim() : '';
      var password = passEl ? passEl.value : '';
      var role = roleEl ? roleEl.value : 'viewer';
      if (!username) {
        alert('请填写用户名');
        return;
      }
      if (!password || password.length < 6) {
        alert('密码至少 6 位');
        return;
      }
      var r = await pmFetch('/api/v1/users', {
        method: 'POST',
        body: JSON.stringify({ username: username, password: password, role: role })
      });
      if (!r.ok) {
        var err = await r.json().catch(function () { return {}; });
        alert(err.detail || '创建失败');
        return;
      }
      if (nameEl) nameEl.value = '';
      if (passEl) passEl.value = '';
      await refreshUsersTable();
      showSaveToast('用户已创建');
    });
  }
}

function initSettingsPanelOnce() {
  const nav = document.querySelector('.settings-nav');
  if (!nav || nav._pmWired) return;
  nav._pmWired = true;
  nav.querySelectorAll('.settings-nav-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const mod = btn.getAttribute('S.data-settings-module');
      if (!mod) return;
      nav.querySelectorAll('.settings-nav-btn').forEach(function (b) {
        b.classList.toggle('active', b === btn);
      });
      document.querySelectorAll('.settings-module').forEach(function (sec) {
        sec.classList.toggle('active', sec.id === 'settings-module-' + mod);
      });
      scrollMainToTop();
    });
  });
  bindPmLogoutButtons();
  updateSettingsPanelRoleUi();
}

function escapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/"/g, '&quot;');
}

function fixManpowerInData(arr) {
  if (!Array.isArray(arr)) return;
  const need = deptFlatCount();
  arr.forEach(function (set) {
    if (!set) return;
    if (!Array.isArray(set.projectSets)) set.projectSets = [];
    set.projectSets.forEach(function (projectSet) {
      if (!projectSet) return;
      if (!Array.isArray(projectSet.subProjects)) projectSet.subProjects = [];
      projectSet.subProjects.forEach(function (p) {
        if (!p) return;
        ensureProjectHasManpowerByMonth(p);
        var mb = p.manpowerByMonth;
        var keys = Object.keys(mb);
        if (keys.length === 0 && Array.isArray(p.manpower)) {
          mb[ymKey(S.manpowerSelYear, S.manpowerSelMonth)] = p.manpower.map(function (x) {
            var n = Number(x);
            return isNaN(n) ? 0 : n;
          });
        }
        Object.keys(mb).forEach(function (k) {
          var row = Array.isArray(mb[k]) ? mb[k].slice() : [];
          row = row.map(function (x) {
            var n = Number(x);
            return isNaN(n) ? 0 : n;
          });
          while (row.length < need) row.push(0);
          if (row.length > need) row = row.slice(0, need);
          mb[k] = row;
        });
        p.manpower = getMonthSlice(p, S.manpowerSelYear, S.manpowerSelMonth);
      });
    });
  });
}

function mapRiskRowsFromStorage(arr) {
  if (!Array.isArray(arr)) return [];
  return arr.map(function (r) {
    return {
      category: r.category != null ? String(r.category) : '',
      source: r.source != null ? String(r.source) : '',
      project: r.project != null ? String(r.project) : '',
      regTime: r.regTime != null ? String(r.regTime) : '',
      issue: r.issue != null ? String(r.issue) : '',
      solution: r.solution != null ? String(r.solution) : '',
      level: r.level != null ? String(r.level) : '',
      owner: r.owner != null ? String(r.owner) : '',
      status: r.status != null ? String(r.status) : '',
      closeTime: r.closeTime != null ? String(r.closeTime) : ''
    };
  });
}

function syncRiskRowsFromDom() {
  const tb = document.getElementById('risk-table-body');
  if (!tb || S.riskRows.length === 0) return;
  const trList = tb.querySelectorAll('tr');
  let i = 0;
  trList.forEach(function (tr) {
    const tds = tr.querySelectorAll('td');
    if (tds.length < 10) return;
    const fields = tr.querySelectorAll('input, select, textarea');
    if (fields.length < RISK_FIELD_ORDER.length || !S.riskRows[i]) return;
    RISK_FIELD_ORDER.forEach(function (key, j) {
      S.riskRows[i][key] = fields[j].value;
    });
    i++;
  });
}

function loadSavedData() {
  var phaseFromStorage = false;
  try {
    const rawM = localStorage.getItem(STORAGE_KEY_MANPOWER);
    const rawR = localStorage.getItem(STORAGE_KEY_RISK);
    const rawP = localStorage.getItem(STORAGE_KEY_PHASE);
    const rawL = localStorage.getItem(STORAGE_KEY_LEGACY);

    if (!rawM && !rawR && rawL) {
      const leg = JSON.parse(rawL);
      if (leg && typeof leg === 'object') {
        if (Array.isArray(leg.data)) {
          fixManpowerInData(leg.data);
          S.data = leg.data;
        }
        if (Array.isArray(leg.riskRows)) {
          S.riskRows = mapRiskRowsFromStorage(leg.riskRows);
        }
      }
      try {
        localStorage.setItem(STORAGE_KEY_MANPOWER, JSON.stringify({ data: S.data, deptGroups: S.deptGroups, savedAt: new Date().toISOString() }));
        localStorage.setItem(STORAGE_KEY_RISK, JSON.stringify({ riskRows: S.riskRows, savedAt: new Date().toISOString() }));
        localStorage.removeItem(STORAGE_KEY_LEGACY);
      } catch (e2) {}
      fixManpowerInData(S.data);
      S.phaseData = phaseStructureNamesFromData(S.data);
      fixPhaseInData(S.phaseData);
      syncManpowerStructureFromPhase();
      return;
    }

    if (rawM) {
      const obj = JSON.parse(rawM);
      if (obj && Array.isArray(obj.data)) {
        if (Array.isArray(obj.deptGroups)) {
          S.deptGroups = normalizeDeptGroups(obj.deptGroups);
        }
        fixManpowerInData(obj.data);
        S.data = obj.data;
      }
    }
    if (rawR) {
      const obj = JSON.parse(rawR);
      if (obj && Array.isArray(obj.riskRows)) {
        S.riskRows = mapRiskRowsFromStorage(obj.riskRows);
      }
    }
    if (rawP) {
      const objP = JSON.parse(rawP);
      if (objP && Array.isArray(objP.phaseData)) {
        S.phaseData = mapPhaseDataFromStorage(objP.phaseData);
        phaseFromStorage = true;
      }
    }
  } catch (e) {
    console.warn('[PM-tool] 本地数据解析失败，已保留当前默认或已加载数据：', e);
  }
  fixManpowerInData(S.data);
  if (!phaseFromStorage) {
    S.phaseData = phaseStructureNamesFromData(S.data);
  }
  fixPhaseInData(S.phaseData);
  syncManpowerStructureFromPhase();
}

function isRegistryServerEmpty(mObj, pObj, rObj) {
  var md = (mObj && Array.isArray(mObj.data)) ? mObj.data.length : 0;
  var rd = (rObj && Array.isArray(rObj.riskRows)) ? rObj.riskRows.length : 0;
  var pd = (pObj && Array.isArray(pObj.phaseData)) ? pObj.phaseData.length : 0;
  return md === 0 && rd === 0 && pd === 0;
}

function hasLocalRegistryData() {
  try {
    var rawM = localStorage.getItem(STORAGE_KEY_MANPOWER);
    var rawR = localStorage.getItem(STORAGE_KEY_RISK);
    var rawP = localStorage.getItem(STORAGE_KEY_PHASE);
    if (rawM) {
      var o = JSON.parse(rawM);
      if (o && Array.isArray(o.data) && o.data.length > 0) return true;
    }
    if (rawR) {
      var o2 = JSON.parse(rawR);
      if (o2 && Array.isArray(o2.riskRows) && o2.riskRows.length > 0) return true;
    }
    if (rawP) {
      var o3 = JSON.parse(rawP);
      if (o3 && Array.isArray(o3.phaseData) && o3.phaseData.length > 0) return true;
    }
  } catch (e) {}
  return false;
}

function mirrorRegistryToLocalStorage(mObj, pObj, rObj) {
  try {
    if (mObj) localStorage.setItem(STORAGE_KEY_MANPOWER, JSON.stringify(mObj));
    if (pObj) localStorage.setItem(STORAGE_KEY_PHASE, JSON.stringify(pObj));
    if (rObj) localStorage.setItem(STORAGE_KEY_RISK, JSON.stringify(rObj));
  } catch (e) {}
}

function applyRegistryFromObjects(mObj, pObj, rObj) {
  var phaseFromStorage = false;
  if (mObj && Array.isArray(mObj.data)) {
    S.deptGroups = Array.isArray(mObj.deptGroups)
      ? normalizeDeptGroups(mObj.deptGroups)
      : defaultDeptGroups();
    fixManpowerInData(mObj.data);
    S.data = mObj.data;
  }
  if (rObj && Array.isArray(rObj.riskRows)) {
    S.riskRows = mapRiskRowsFromStorage(rObj.riskRows);
  }
  if (pObj && Array.isArray(pObj.phaseData)) {
    S.phaseData = mapPhaseDataFromStorage(pObj.phaseData);
    phaseFromStorage = true;
  }
  fixManpowerInData(S.data);
  if (!phaseFromStorage) {
    S.phaseData = phaseStructureNamesFromData(S.data);
  }
  fixPhaseInData(S.phaseData);
  syncManpowerStructureFromPhase();
}

async function loadRegistryData() {
  var me = window.__pmCurrentUser;
  // 仅「认证不可用/离线」时用本机缓存；正常登录与 PM_AUTH_DISABLED 下的 dev 用户仍从服务器拉取
  if (!me || me.username === 'offline' || me.username === 'unknown') {
    loadSavedData();
    return;
  }
  try {
    var results = await Promise.all([
      pmFetch('/api/v1/manpower', { method: 'GET' }),
      pmFetch('/api/v1/phase', { method: 'GET' }),
      pmFetch('/api/v1/risk', { method: 'GET' })
    ]);
    var rm = results[0];
    var rp = results[1];
    var rr = results[2];
    if (rm.status === 401 || rp.status === 401 || rr.status === 401) {
      window.__pmAuthRedirecting = true;
      window.location.href = 'login.html';
      return;
    }
    if (!rm.ok || !rp.ok || !rr.ok) {
      throw new Error('HTTP ' + rm.status + ' / ' + rp.status + ' / ' + rr.status);
    }
    var mObj = await rm.json();
    var pObj = await rp.json();
    var rObj = await rr.json();
    if (isRegistryServerEmpty(mObj, pObj, rObj) && hasLocalRegistryData()) {
      loadSavedData();
      showSaveToast('服务端暂无数据，已载入本机数据；请管理员点击保存以同步到服务器');
      return;
    }
    applyRegistryFromObjects(mObj, pObj, rObj);
    mirrorRegistryToLocalStorage(mObj, pObj, rObj);
  } catch (e) {
    console.warn('[PM-tool] 从服务器加载登记数据失败，改用本机缓存', e);
    alert('无法从服务器加载登记数据，已使用本机缓存。');
    loadSavedData();
  }
}

async function saveManpowerData() {
  if (!requireAdminOrAlert()) return;
  try {
    var r = await pmFetch('/api/v1/manpower', {
      method: 'PUT',
      body: JSON.stringify({ data: S.data, deptGroups: S.deptGroups })
    });
    if (r.status === 401) {
      window.location.href = 'login.html';
      return;
    }
    if (!r.ok) {
      var err = await r.json().catch(function () { return {}; });
      alert((err.detail != null ? err.detail : '保存失败') + '（HTTP ' + r.status + '）');
      return;
    }
    var stored = await r.json();
    mirrorRegistryToLocalStorage(stored, null, null);
    showSaveToast('人力登记已保存到服务器');
    setPanelEditMode('manpower', false);
  } catch (e) {
    alert('保存失败：无法连接服务器');
  }
}

async function saveRiskData() {
  if (!requireAdminOrAlert()) return;
  syncRiskRowsFromDom();
  try {
    var r = await pmFetch('/api/v1/risk', {
      method: 'PUT',
      body: JSON.stringify({ riskRows: S.riskRows })
    });
    if (r.status === 401) {
      window.location.href = 'login.html';
      return;
    }
    if (!r.ok) {
      var err = await r.json().catch(function () { return {}; });
      alert((err.detail != null ? err.detail : '保存失败') + '（HTTP ' + r.status + '）');
      return;
    }
    var stored = await r.json();
    mirrorRegistryToLocalStorage(null, null, stored);
    showSaveToast('风险登记已保存到服务器');
    setPanelEditMode('risk', false);
  } catch (e) {
    alert('保存失败：无法连接服务器');
  }
}

function syncPhaseFromDom() {
  var tb = document.getElementById('phase-table-body');
  if (!tb) return;
  var trs = tb.querySelectorAll('tr');
  var flat = [];
  S.phaseData.forEach(function (set) {
    getProgramProjectSets(set).forEach(function (projectSet) {
      getSubProjects(projectSet).forEach(function (p) {
        flat.push(p);
      });
    });
  });
  var ri = 0;
  trs.forEach(function (tr) {
    var p = flat[ri];
    if (!p) return;
    var slice = getPhaseMonthSlice(p, S.phaseSelYear, S.phaseSelMonth);
    var tas = tr.querySelectorAll('textarea.phase-field-input');
    if (tas.length < PHASE_FIELD_KEYS.length) return;
    PHASE_FIELD_KEYS.forEach(function (key, j) {
      slice[key] = tas[j].value;
    });
    ri++;
  });
}

function phaseDataForStorage() {
  return S.phaseData.map(function (set) {
    return {
      name: set.name,
      projectSets: getProgramProjectSets(set).map(function (projectSet) {
        return {
          name: projectSet.name,
          subProjects: getSubProjects(projectSet).map(function (p) {
            return { name: p.name, phaseByMonth: p.phaseByMonth || {} };
          })
        };
      })
    };
  });
}

async function savePhaseData() {
  if (!requireAdminOrAlert()) return;
  syncPhaseFromDom();
  try {
    var r = await pmFetch('/api/v1/phase', {
      method: 'PUT',
      body: JSON.stringify({ phaseData: phaseDataForStorage() })
    });
    if (r.status === 401) {
      window.location.href = 'login.html';
      return;
    }
    if (!r.ok) {
      var err = await r.json().catch(function () { return {}; });
      alert((err.detail != null ? err.detail : '保存失败') + '（HTTP ' + r.status + '）');
      return;
    }
    var stored = await r.json();
    mirrorRegistryToLocalStorage(null, stored, null);
    showSaveToast('阶段状态已保存到服务器');
    setPanelEditMode('phase', false);
  } catch (e) {
    alert('保存失败：无法连接服务器');
  }
}

function showSaveToast(msg) {
  const el = document.getElementById('save-toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(el._hideTimer);
  el._hideTimer = setTimeout(function () {
    el.classList.remove('show');
  }, 2200);
}

function formatRiskRegTime(d) {
  const pad = function (n) { return String(n).padStart(2, '0'); };
  return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
}

function addRiskRow() {
  if (!requireAdminOrAlert()) return;
  S.riskRows.push({
    category: '',
    source: '',
    project: '',
    issue: '',
    solution: '',
    level: '',
    owner: '',
    regTime: '',
    closeTime: '',
    status: '',
  });
  renderRiskTable();
}

function updateRisk(idx, field, value) {
  if (S.riskRows[idx]) S.riskRows[idx][field] = value;
}

function compareRiskRowsByField(a, b, key) {
  var va = a[key] != null ? String(a[key]).trim() : '';
  var vb = b[key] != null ? String(b[key]).trim() : '';
  var emptyA = !va;
  var emptyB = !vb;
  if (emptyA && emptyB) return 0;
  if (emptyA) return 1;
  if (emptyB) return -1;

  if (key === 'level') {
    var order = { '低': 1, '中': 2, '高': 3 };
    var na = order[va] != null ? order[va] : 99;
    var nb = order[vb] != null ? order[vb] : 99;
    return na - nb;
  }
  if (key === 'closeTime') {
    var da = new Date(va + 'T00:00:00').getTime();
    var db = new Date(vb + 'T00:00:00').getTime();
    if (isNaN(da)) da = 0;
    if (isNaN(db)) db = 0;
    return da - db;
  }
  if (key === 'regTime') {
    var da = new Date(va.replace(/-/g, '/')).getTime();
    var db = new Date(vb.replace(/-/g, '/')).getTime();
    if (isNaN(da)) da = 0;
    if (isNaN(db)) db = 0;
    return da - db;
  }
  if (key === 'project') {
    return va.localeCompare(vb, 'zh-CN', { numeric: true, sensitivity: 'base' });
  }
  return va.localeCompare(vb, 'zh-CN', { numeric: true, sensitivity: 'base' });
}

function applyRiskSort() {
  if (!S.riskSortState.key) return;
  var key = S.riskSortState.key;
  var mul = S.riskSortState.dir === 'asc' ? 1 : -1;
  S.riskRows.sort(function (a, b) {
    return compareRiskRowsByField(a, b, key) * mul;
  });
}

function toggleRiskSort(fieldKey) {
  if (S.riskSortState.key === fieldKey) {
    S.riskSortState.dir = S.riskSortState.dir === 'asc' ? 'desc' : 'asc';
  } else {
    S.riskSortState.key = fieldKey;
    S.riskSortState.dir = 'asc';
  }
  renderRiskTable();
}

function renderRiskThead() {
  var thead = document.getElementById('risk-thead');
  if (!thead) return;
  var headers = [
    { key: null, label: '序号', sortable: false, thClass: 'main seq' },
    { key: 'category', label: '风险类别', sortable: true },
    { key: 'source', label: '风险来源', sortable: true },
    { key: 'project', label: '项目', sortable: true },
    { key: 'issue', label: '问题&影响说明', sortable: true },
    { key: 'solution', label: '解决方案', sortable: true },
    { key: 'level', label: '风险等级', sortable: true },
    { key: 'owner', label: '跟进人', sortable: true },
    { key: 'regTime', label: '风险登记时间', sortable: true },
    { key: 'closeTime', label: '风险解除时间', sortable: true },
    { key: 'status', label: '状态', sortable: true },
    { key: null, label: '操作', sortable: false }
  ];
  var tr = document.createElement('tr');
  headers.forEach(function (h) {
    var th = document.createElement('th');
    th.className = h.thClass || 'sub';
    if (h.sortable) {
      th.classList.add('risk-th-sortable');
      var active = S.riskSortState.key === h.key;
      th.setAttribute('aria-sort', active ? (S.riskSortState.dir === 'asc' ? 'ascending' : 'descending') : 'none');
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'risk-th-sort-btn';
      btn.title = '按「' + h.label + '」排序，再次点击切换升序/降序';
      var spanLabel = document.createElement('span');
      spanLabel.textContent = h.label;
      var ind = document.createElement('span');
      ind.className = 'risk-sort-ind';
      ind.setAttribute('aria-hidden', 'true');
      ind.textContent = active ? (S.riskSortState.dir === 'asc' ? '▲' : '▼') : '↕';
      btn.appendChild(spanLabel);
      btn.appendChild(ind);
      (function (fk) {
        btn.addEventListener('click', function () { toggleRiskSort(fk); });
      })(h.key);
      th.appendChild(btn);
    } else {
      th.textContent = h.label;
    }
    tr.appendChild(th);
  });
  thead.innerHTML = '';
  thead.appendChild(tr);
}

function renderRiskTable() {
  if (S.riskSortState.key) applyRiskSort();
  renderRiskThead();
  const tb = document.getElementById('risk-table-body');
  if (!tb) return;
  const allowEdit = canEditPanel('risk');
  tb.innerHTML = '';
  if (S.riskRows.length === 0) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = 12;
    td.className = 'center-cell';
    td.style.padding = '24px';
    td.textContent = allowEdit
      ? '暂无风险记录，请点击「+ 新增风险」添加。'
      : '暂无风险记录。普通用户仅可查看；管理员可通过「+ 新增风险」添加。';
    tr.appendChild(td);
    tb.appendChild(tr);
    return;
  }
  S.riskRows.forEach(function (row, idx) {
    const tr = document.createElement('tr');

    const tdSeq = document.createElement('td');
    tdSeq.className = 'main seq';
    tdSeq.textContent = String(idx + 1);
    tr.appendChild(tdSeq);

    function tdTextInput(field, cls) {
      const td = document.createElement('td');
      td.className = 'risk-cell' + (cls ? ' ' + cls : '');
      const inp = document.createElement('input');
      inp.type = 'text';
      inp.className = 'risk-input';
      inp.value = row[field] || '';
      inp.readOnly = !allowEdit;
      inp.addEventListener('change', function () {
        if (allowEdit) updateRisk(idx, field, inp.value);
      });
      td.appendChild(inp);
      return td;
    }

    function riskSelectColorClass(field, value) {
      var v = value != null ? String(value).trim().toLowerCase() : '';
      if (!v) return '';
      if (field === 'category') {
        if (v === '进度') return 'risk-color-progress';
        if (v === '质量') return 'risk-color-quality';
        if (v === '范围') return 'risk-color-scope';
        if (v === '成本') return 'risk-color-cost';
        return '';
      }
      if (field === 'source') {
        if (v === '资源') return 'risk-color-resource';
        if (v === '技术') return 'risk-color-tech';
        return '';
      }
      if (field === 'level') {
        if (v === '高') return 'risk-color-high';
        if (v === '中') return 'risk-color-mid';
        if (v === '低') return 'risk-color-low';
        return '';
      }
      if (field === 'status') {
        if (v === 'open') return 'risk-color-open';
        if (v === 'hold') return 'risk-color-hold';
        if (v === 'close') return 'risk-color-close';
        return '';
      }
      return '';
    }

    function applyRiskSelectColor(el, field, value) {
      if (!el) return;
      el.classList.remove(
        'risk-color-progress', 'risk-color-quality', 'risk-color-scope', 'risk-color-cost',
        'risk-color-resource', 'risk-color-tech',
        'risk-color-high', 'risk-color-mid', 'risk-color-low',
        'risk-color-open', 'risk-color-hold', 'risk-color-close'
      );
      var cls = riskSelectColorClass(field, value);
      if (cls) el.classList.add(cls);
    }

    function tdSelect(field, options, cls) {
      const td = document.createElement('td');
      td.className = 'risk-cell' + (cls ? ' ' + cls : '');
      const sel = document.createElement('select');
      sel.className = 'risk-select';
      const current = row[field] != null ? String(row[field]) : '';
      [['', '请选择']].concat(options).forEach(function (opt) {
        const o = document.createElement('option');
        o.value = opt[0];
        o.textContent = opt[1];
        if (current === opt[0]) o.selected = true;
        sel.appendChild(o);
      });
      sel.disabled = !allowEdit;
      applyRiskSelectColor(sel, field, current);
      sel.addEventListener('change', function () {
        if (allowEdit) updateRisk(idx, field, sel.value);
        applyRiskSelectColor(sel, field, sel.value);
      });
      td.appendChild(sel);
      return td;
    }

    tr.appendChild(tdSelect('category', [['进度', '进度'], ['质量', '质量'], ['范围', '范围'], ['成本', '成本']]));
    tr.appendChild(tdSelect('source', [['资源', '资源'], ['技术', '技术']]));
    tr.appendChild(tdTextInput('project'));

    const tdIssue = document.createElement('td');
    tdIssue.className = 'risk-cell w-wide';
    const taIssue = document.createElement('textarea');
    taIssue.className = 'risk-input';
    taIssue.rows = 2;
    taIssue.value = row.issue || '';
    taIssue.readOnly = !allowEdit;
    taIssue.addEventListener('change', function () {
      if (allowEdit) updateRisk(idx, 'issue', taIssue.value);
    });
    tdIssue.appendChild(taIssue);
    tr.appendChild(tdIssue);

    const tdSolution = document.createElement('td');
    tdSolution.className = 'risk-cell w-wide';
    const taSolution = document.createElement('textarea');
    taSolution.className = 'risk-input';
    taSolution.rows = 2;
    taSolution.value = row.solution || '';
    taSolution.readOnly = !allowEdit;
    taSolution.addEventListener('change', function () {
      if (allowEdit) updateRisk(idx, 'solution', taSolution.value);
    });
    tdSolution.appendChild(taSolution);
    tr.appendChild(tdSolution);

    tr.appendChild(tdSelect('level', [['高', '高'], ['中', '中'], ['低', '低']]));

    tr.appendChild(tdTextInput('owner'));

    const tdRegDate = document.createElement('td');
    tdRegDate.className = 'risk-cell';
    const rin = document.createElement('input');
    rin.type = 'date';
    rin.className = 'risk-input';
    rin.value = row.regTime || '';
    rin.disabled = !allowEdit;
    rin.addEventListener('change', function () {
      if (allowEdit) updateRisk(idx, 'regTime', rin.value);
    });
    tdRegDate.appendChild(rin);
    tr.appendChild(tdRegDate);

    const tdCloseDate = document.createElement('td');
    tdCloseDate.className = 'risk-cell';
    const din = document.createElement('input');
    din.type = 'date';
    din.className = 'risk-input';
    din.value = row.closeTime || '';
    din.disabled = !allowEdit;
    din.addEventListener('change', function () {
      if (allowEdit) updateRisk(idx, 'closeTime', din.value);
    });
    tdCloseDate.appendChild(din);
    tr.appendChild(tdCloseDate);

    tr.appendChild(tdSelect('status', [['open', 'open'], ['close', 'close'], ['hold', 'hold']]));

    const tdAct = document.createElement('td');
    tdAct.className = 'center-cell';
    if (allowEdit) {
      const delBtn = document.createElement('button');
      delBtn.type = 'button';
      delBtn.className = 'delete-btn';
      delBtn.textContent = '删除';
      delBtn.onclick = function () { showRiskDeleteModal(idx); };
      tdAct.appendChild(delBtn);
    } else {
      tdAct.className = 'center-cell risk-readonly-cell';
      tdAct.textContent = '—';
    }
    tr.appendChild(tdAct);

    tb.appendChild(tr);
  });
}

function renderPhaseThead() {
  var thead = document.getElementById('phase-thead');
  if (!thead) return;
  var tr = document.createElement('tr');
  var thSet = document.createElement('th');
  thSet.className = 'main col-set';
  thSet.textContent = '项目集';
  tr.appendChild(thSet);
  var thSubSet = document.createElement('th');
  thSubSet.className = 'sub col-set';
  thSubSet.textContent = '子项目集';
  tr.appendChild(thSubSet);
  var thProj = document.createElement('th');
  thProj.className = 'sub col-proj';
  thProj.textContent = '子项目';
  tr.appendChild(thProj);
  PHASE_FIELD_KEYS.forEach(function (key) {
    var th = document.createElement('th');
    th.className = 'sub phase-field-th';
    th.textContent = PHASE_FIELD_LABELS[key];
    tr.appendChild(th);
  });
  thead.innerHTML = '';
  thead.appendChild(tr);
}

function appendPhaseRowNameCells(tr, set, setIdx, projectSet, projectSetIdx, proj, projIdx, admin) {
  if (projectSetIdx === 0 && projIdx === 0) {
    var tdSet = document.createElement('td');
    tdSet.className = 'main col-set';
    tdSet.rowSpan = countSubProjectsInSet(set) || 1;
    if (admin) {
      tdSet.innerHTML = '<div class="cell-head-inline"><span class="editable-text" onclick="editPhaseSetName(' + setIdx + ')">' + escapeHtml(set.name) + '</span><div class="actions"><button type="button" class="icon-btn" title="添加子项目集" onclick="addPhaseProjectSet(' + setIdx + ')">+</button><button type="button" class="icon-btn danger" title="删除项目集" onclick="showDeleteModal(\'set\',' + setIdx + ')">×</button></div></div>';
    } else {
      tdSet.innerHTML = '<div class="cell-head-inline"><span>' + escapeHtml(set.name) + '</span></div>';
    }
    tr.appendChild(tdSet);
  }
  if (projIdx === 0) {
    var tdSubSet = document.createElement('td');
    tdSubSet.className = 'sub col-set';
    tdSubSet.rowSpan = getSubProjects(projectSet).length || 1;
    if (admin) {
      tdSubSet.innerHTML = '<div class="cell-head-inline"><span class="editable-text" onclick="editPhaseProjectSetName(' + setIdx + ',' + projectSetIdx + ')">' + escapeHtml(projectSet.name) + '</span><div class="actions"><button type="button" class="icon-btn" title="添加子项目" onclick="addPhaseProject(' + setIdx + ',' + projectSetIdx + ')">+</button><button type="button" class="icon-btn danger" title="删除子项目集" onclick="showDeleteModal(\'projectSet\',' + setIdx + ',' + projectSetIdx + ')">×</button></div></div>';
    } else {
      tdSubSet.innerHTML = '<div class="cell-head-inline"><span>' + escapeHtml(projectSet.name) + '</span></div>';
    }
    tr.appendChild(tdSubSet);
  }
  var tdProj = document.createElement('td');
  tdProj.className = 'sub col-proj';
  if (admin) {
    tdProj.innerHTML = '<div class="cell-head-inline"><span class="editable-text" onclick="editPhaseProjectName(' + setIdx + ',' + projectSetIdx + ',' + projIdx + ')">' + escapeHtml(proj.name) + '</span><div class="actions"><button type="button" class="icon-btn danger" title="删除子项目" onclick="showDeleteModal(\'project\',' + setIdx + ',' + projectSetIdx + ',' + projIdx + ')">×</button></div></div>';
  } else {
    tdProj.innerHTML = '<div class="cell-head-inline"><span>' + escapeHtml(proj.name) + '</span></div>';
  }
  tr.appendChild(tdProj);
}

function renderPhaseTable() {
  syncPhaseRowPointer();
  renderPhaseThead();
  var tb = document.getElementById('phase-table-body');
  if (!tb) return;
  tb.innerHTML = '';
  var admin = canEditPanel('phase');
  var yearInput = document.getElementById('phase-year-input');
  var monthSel = document.getElementById('phase-month-select');
  if (yearInput) yearInput.value = String(S.phaseSelYear);
  if (monthSel) monthSel.value = String(S.phaseSelMonth);

  if (S.phaseData.length === 0) {
    var trE = document.createElement('tr');
    var tdE = document.createElement('td');
    tdE.colSpan = 3 + PHASE_FIELD_KEYS.length;
    tdE.className = 'center-cell';
    tdE.style.padding = '24px';
    tdE.textContent = admin
      ? '暂无记录，请点击「+ 新项目集」添加。'
      : '暂无记录。普通用户仅可查看；管理员可添加与编辑。';
    trE.appendChild(tdE);
    tb.appendChild(trE);
    return;
  }

  S.phaseData.forEach(function (set, setIdx) {
    getProgramProjectSets(set).forEach(function (projectSet, projectSetIdx) {
      getSubProjects(projectSet).forEach(function (proj, projIdx) {
        var tr = document.createElement('tr');
        if (setIdx % 2 === 1) tr.classList.add('manpower-set-stripe-b');
        appendPhaseRowNameCells(tr, set, setIdx, projectSet, projectSetIdx, proj, projIdx, admin);
        var slice = proj._phaseSlice || getPhaseMonthSlice(proj, S.phaseSelYear, S.phaseSelMonth);
        PHASE_FIELD_KEYS.forEach(function (key) {
          var td = document.createElement('td');
          td.className = 'phase-field-cell';
          var ta = document.createElement('textarea');
          ta.className = 'phase-field-input';
          ta.value = slice[key] || '';
          ta.readOnly = !admin;
          ta.rows = 3;
          if (admin) {
            ta.addEventListener('input', function () {
              slice[key] = ta.value;
            });
          }
          td.appendChild(ta);
          tr.appendChild(td);
        });
        tb.appendChild(tr);
      });
    });
  });
}

function addPhaseProjectSet(setIdx) {
  if (!requireAdminOrAlert()) return;
  var name = prompt(setIdx == null ? '输入新项目集的名称：' : '输入新子项目集的名称：');
  if (name && String(name).trim()) {
    var newProj = { name: '新子项目', phaseByMonth: {} };
    getPhaseMonthSlice(newProj, S.phaseSelYear, S.phaseSelMonth);
    if (setIdx == null) {
      S.phaseData.push({
        name: String(name).trim(),
        projectSets: [{ name: '默认子项目集', subProjects: [newProj] }]
      });
    } else {
      var set = S.phaseData[setIdx];
      if (!set) return;
      if (!Array.isArray(set.projectSets)) set.projectSets = [];
      set.projectSets.push({ name: String(name).trim(), subProjects: [newProj] });
    }
    fixPhaseInData(S.phaseData);
    renderPhaseTable();
    renderTable();
  }
}

function addPhaseProject(setIdx, projectSetIdx) {
  if (!requireAdminOrAlert()) return;
  var name = prompt('输入新子项目名称：');
  if (name && String(name).trim()) {
    var newProj = { name: String(name).trim(), phaseByMonth: {} };
    getPhaseMonthSlice(newProj, S.phaseSelYear, S.phaseSelMonth);
    var projectSet = S.phaseData[setIdx] && getProgramProjectSets(S.phaseData[setIdx])[projectSetIdx];
    if (!projectSet) return;
    if (!Array.isArray(projectSet.subProjects)) projectSet.subProjects = [];
    projectSet.subProjects.push(newProj);
    fixPhaseInData(S.phaseData);
    renderPhaseTable();
    renderTable();
  }
}

function editPhaseSetName(setIdx) {
  if (!requireAdminOrAlert()) return;
  var set = S.phaseData[setIdx];
  if (!set) return;
  var name = prompt('输入新的项目集名称：', set.name);
  if (name != null && String(name).trim()) {
    set.name = String(name).trim();
    renderPhaseTable();
    renderTable();
  }
}

function editPhaseProjectSetName(setIdx, projectSetIdx) {
  if (!requireAdminOrAlert()) return;
  var projectSet = S.phaseData[setIdx] && getProgramProjectSets(S.phaseData[setIdx])[projectSetIdx];
  if (!projectSet) return;
  var name = prompt('输入新的子项目集名称：', projectSet.name);
  if (name != null && String(name).trim()) {
    projectSet.name = String(name).trim();
    renderPhaseTable();
    renderTable();
  }
}

function editPhaseProjectName(setIdx, projectSetIdx, projIdx) {
  if (!requireAdminOrAlert()) return;
  var projectSet = S.phaseData[setIdx] && getProgramProjectSets(S.phaseData[setIdx])[projectSetIdx];
  var proj = projectSet && getSubProjects(projectSet)[projIdx];
  if (!proj) return;
  var name = prompt('输入新的子项目名称：', proj.name);
  if (name != null && String(name).trim()) {
    proj.name = String(name).trim();
    renderPhaseTable();
    renderTable();
  }
}

function initPhaseTimeUi() {
  var sm = document.getElementById('phase-month-select');
  if (sm && sm.options.length === 0) {
    for (var mo = 1; mo <= 12; mo++) {
      var o = document.createElement('option');
      o.value = String(mo);
      o.textContent = mo + '月';
      sm.appendChild(o);
    }
  }
  if (sm) sm.value = String(S.phaseSelMonth);
  var ym = document.getElementById('phase-year-input');
  if (ym && !ym._phaseWired) {
    ym._phaseWired = true;
    ym.addEventListener('change', function () {
      var v = parseInt(ym.value, 10);
      if (!isNaN(v) && v >= 2000 && v <= 2099) {
        S.phaseSelYear = v;
        renderPhaseTable();
      }
    });
  }
  if (sm && !sm._phaseWired) {
    sm._phaseWired = true;
    sm.addEventListener('change', function () {
      var v = parseInt(sm.value, 10);
      if (!isNaN(v) && v >= 1 && v <= 12) {
        S.phaseSelMonth = v;
        renderPhaseTable();
      }
    });
  }
  var btnPhAn = document.getElementById('btn-phase-analysis');
  var maskPh = document.getElementById('phase-analysis-mask');
  var closePh = document.getElementById('phase-analysis-close');
  if (btnPhAn) btnPhAn.addEventListener('click', openPhaseAnalysisModal);
  if (maskPh) {
    maskPh.addEventListener('click', function (e) {
      if (e.target === maskPh) closePhaseAnalysisModal();
    });
  }
  if (closePh) closePh.addEventListener('click', closePhaseAnalysisModal);
}

function openPhaseAnalysisModal() {
  var mask = document.getElementById('phase-analysis-mask');
  var per = document.getElementById('phase-analysis-period');
  if (per) per.textContent = '当前所选：' + S.phaseSelYear + ' 年 ' + S.phaseSelMonth + ' 月';
  if (mask) {
    mask.classList.add('active');
    mask.setAttribute('aria-hidden', 'false');
  }
}

function closePhaseAnalysisModal() {
  var mask = document.getElementById('phase-analysis-mask');
  if (mask) {
    mask.classList.remove('active');
    mask.setAttribute('aria-hidden', 'true');
  }
}

function showRiskDeleteModal(riskIdx) {
  if (!requireAdminOrAlert()) return;
  S.delCtx = { type: 'risk', riskIdx: riskIdx };
  document.getElementById('modal-msg').textContent = '确认删除序号为 ' + (riskIdx + 1) + ' 的风险登记？';
  openDeleteModal();
}

function renderManpowerTheadMonth() {
  const thead = document.getElementById('register-thead');
  if (!thead) return;
  const admin = canEditPanel('manpower');
  thead.innerHTML = '';

  const tr1 = document.createElement('tr');
  const thSet = document.createElement('th');
  thSet.className = 'main col-set';
  thSet.rowSpan = 2;
  thSet.textContent = '项目集';
  tr1.appendChild(thSet);
  const thSubSet = document.createElement('th');
  thSubSet.className = 'sub col-set';
  thSubSet.rowSpan = 2;
  thSubSet.textContent = '子项目集';
  tr1.appendChild(thSubSet);

  const thProj = document.createElement('th');
  thProj.className = 'sub col-proj';
  thProj.rowSpan = 2;
  thProj.textContent = '子项目';
  tr1.appendChild(thProj);

  S.deptGroups.forEach(function (g, gi) {
    const th = document.createElement('th');
    th.className = 'main dept-g-' + (gi % 2);
    th.colSpan = g.depts.length;
    const wrap = document.createElement('div');
    wrap.className = 'cell-head-inline';
    const nameSpan = document.createElement('span');
    if (admin) {
      nameSpan.className = 'editable-text';
      nameSpan.title = '点击修改分组名称';
      nameSpan.onclick = function () { editDeptGroupName(gi); };
    }
    nameSpan.textContent = g.name;
    wrap.appendChild(nameSpan);
    if (admin) {
      const act = document.createElement('div');
      act.className = 'actions inline';
      const addBtn = document.createElement('button');
      addBtn.type = 'button';
      addBtn.className = 'icon-btn';
      addBtn.textContent = '+';
      addBtn.title = '在本分组下增加一列';
      addBtn.onclick = function () { addDeptToGroup(gi); };
      act.appendChild(addBtn);
      wrap.appendChild(act);
    }
    th.appendChild(wrap);
    tr1.appendChild(th);
  });
  thead.appendChild(tr1);

  const tr2 = document.createElement('tr');
  S.deptGroups.forEach(function (g, gi) {
    g.depts.forEach(function (dname, di) {
      const th = document.createElement('th');
      th.className = 'sub dept-g-' + (gi % 2) + ' col-mp';
      const wrap = document.createElement('div');
      wrap.className = 'cell-head-inline';
      const nm = document.createElement('span');
      if (admin) {
        nm.className = 'editable-text';
        nm.title = '点击修改列名';
        nm.onclick = function () { editDeptColumnName(gi, di); };
      }
      nm.textContent = dname;
      wrap.appendChild(nm);
      if (admin) {
        const act = document.createElement('div');
        act.className = 'actions inline';
        const bEdit = document.createElement('button');
        bEdit.type = 'button';
        bEdit.className = 'text-action';
        bEdit.textContent = '改';
        bEdit.title = '改名';
        bEdit.onclick = function () { editDeptColumnName(gi, di); };
        const bDel = document.createElement('button');
        bDel.type = 'button';
        bDel.className = 'text-action danger-text';
        bDel.textContent = '删';
        bDel.title = '删列';
        bDel.onclick = function () { deleteDeptColumn(gi, di); };
        act.appendChild(bEdit);
        act.appendChild(bDel);
        wrap.appendChild(act);
      }
      th.appendChild(wrap);
      tr2.appendChild(th);
    });
  });
  thead.appendChild(tr2);
  syncRegisterColgroup();
}

function renderManpowerTheadSeason() {
  const thead = document.getElementById('register-season-thead');
  if (!thead) return;
  thead.innerHTML = '';
  const tr1 = document.createElement('tr');
  const thSet = document.createElement('th');
  thSet.className = 'main col-set';
  thSet.rowSpan = 2;
  thSet.textContent = '项目集';
  tr1.appendChild(thSet);
  const thSubSet = document.createElement('th');
  thSubSet.className = 'sub col-set';
  thSubSet.rowSpan = 2;
  thSubSet.textContent = '子项目集';
  tr1.appendChild(thSubSet);
  const thProj = document.createElement('th');
  thProj.className = 'sub col-proj';
  thProj.rowSpan = 2;
  thProj.textContent = '子项目';
  tr1.appendChild(thProj);
  S.deptGroups.forEach(function (g, gi) {
    const th = document.createElement('th');
    th.className = 'main dept-g-' + (gi % 2);
    th.colSpan = g.depts.length;
    th.textContent = g.name;
    tr1.appendChild(th);
  });
  thead.appendChild(tr1);
  const tr2 = document.createElement('tr');
  S.deptGroups.forEach(function (g, gi) {
    g.depts.forEach(function (dname) {
      const th = document.createElement('th');
      th.className = 'sub dept-g-' + (gi % 2) + ' col-mp';
      th.textContent = dname;
      tr2.appendChild(th);
    });
  });
  thead.appendChild(tr2);
}

function renderManpowerTheadYear() {
  const thead = document.getElementById('register-year-thead');
  if (!thead) return;
  thead.innerHTML = '';
  const tr1 = document.createElement('tr');
  const thSet = document.createElement('th');
  thSet.className = 'main col-set';
  thSet.rowSpan = 2;
  thSet.textContent = '项目集';
  tr1.appendChild(thSet);
  const thSubSet = document.createElement('th');
  thSubSet.className = 'sub col-set';
  thSubSet.rowSpan = 2;
  thSubSet.textContent = '子项目集';
  tr1.appendChild(thSubSet);
  const thProj = document.createElement('th');
  thProj.className = 'sub col-proj';
  thProj.rowSpan = 2;
  thProj.textContent = '子项目';
  tr1.appendChild(thProj);
  S.deptGroups.forEach(function (g, gi) {
    const th = document.createElement('th');
    th.className = 'main dept-g-' + (gi % 2);
    th.colSpan = g.depts.length;
    th.textContent = g.name;
    tr1.appendChild(th);
  });
  thead.appendChild(tr1);
  const tr2 = document.createElement('tr');
  S.deptGroups.forEach(function (g, gi) {
    g.depts.forEach(function (dname) {
      const th = document.createElement('th');
      th.className = 'sub dept-g-' + (gi % 2) + ' col-mp';
      th.textContent = dname;
      tr2.appendChild(th);
    });
  });
  thead.appendChild(tr2);
}

function editDeptGroupName(gi) {
  if (!requireManpowerMonthViewForStructure()) return;
  if (!requireAdminOrAlert()) return;
  const g = S.deptGroups[gi];
  if (!g) return;
  const name = prompt('部门分组名称：', g.name);
  if (name != null && String(name).trim()) {
    g.name = String(name).trim();
    renderTable();
  }
}

function editDeptColumnName(gi, di) {
  if (!requireManpowerMonthViewForStructure()) return;
  if (!requireAdminOrAlert()) return;
  const g = S.deptGroups[gi];
  if (!g || !g.depts[di]) return;
  const name = prompt('列名称：', g.depts[di]);
  if (name != null && String(name).trim()) {
    g.depts[di] = String(name).trim();
    renderTable();
  }
}

function addDeptGroup() {
  if (!requireManpowerMonthViewForStructure()) return;
  if (!requireAdminOrAlert()) return;
  const name = prompt('新的一级部门（分组）名称：');
  if (!name || !String(name).trim()) return;
  const subPrompt = prompt('该分组下首列（二级部门）名称：', '子部门1');
  const firstCol = (subPrompt != null && String(subPrompt).trim())
    ? String(subPrompt).trim()
    : '子部门1';
  S.deptGroups.push({ name: String(name).trim(), depts: [firstCol] });
  S.data.forEach(function (set) {
    getProgramProjectSets(set).forEach(function (projectSet) {
      getSubProjects(projectSet).forEach(function (p) {
        ensureProjectHasManpowerByMonth(p);
        if (Object.keys(p.manpowerByMonth).length === 0) {
          getMonthSlice(p, S.manpowerSelYear, S.manpowerSelMonth);
        }
        Object.keys(p.manpowerByMonth).forEach(function (k) {
          p.manpowerByMonth[k].push(0);
        });
        if (!Array.isArray(p.manpower)) p.manpower = [];
        p.manpower.push(0);
      });
    });
  });
  fixManpowerInData(S.data);
  renderTable();
}

function addDeptToGroup(gi) {
  if (!requireManpowerMonthViewForStructure()) return;
  if (!requireAdminOrAlert()) return;
  const g = S.deptGroups[gi];
  if (!g) return;
  const name = prompt('新子部门列名称：');
  if (!name || !String(name).trim()) return;
  g.depts.push(String(name).trim());
  const insertAt = flatDeptIndex(gi, g.depts.length - 1);
  S.data.forEach(function (set) {
    getProgramProjectSets(set).forEach(function (projectSet) {
      getSubProjects(projectSet).forEach(function (p) {
        ensureProjectHasManpowerByMonth(p);
        if (Object.keys(p.manpowerByMonth).length === 0) {
          getMonthSlice(p, S.manpowerSelYear, S.manpowerSelMonth);
        }
        Object.keys(p.manpowerByMonth).forEach(function (k) {
          var arr = p.manpowerByMonth[k];
          while (arr.length < insertAt) arr.push(0);
          arr.splice(insertAt, 0, 0);
        });
        if (!Array.isArray(p.manpower)) p.manpower = [];
        while (p.manpower.length < insertAt) p.manpower.push(0);
        p.manpower.splice(insertAt, 0, 0);
      });
    });
  });
  fixManpowerInData(S.data);
  renderTable();
}

function deleteDeptColumn(gi, di) {
  if (!requireManpowerMonthViewForStructure()) return;
  if (!requireAdminOrAlert()) return;
  const g = S.deptGroups[gi];
  if (!g || !g.depts[di]) return;
  if (g.depts.length <= 1) {
    alert('每组至少保留一列。');
    return;
  }
  const label = g.depts[di];
  if (!confirm('确定删除列「' + label + '」？对应人力数据列将一并删除。')) return;
  const idx = flatDeptIndex(gi, di);
  g.depts.splice(di, 1);
  S.data.forEach(function (set) {
    getProgramProjectSets(set).forEach(function (projectSet) {
      getSubProjects(projectSet).forEach(function (p) {
        ensureProjectHasManpowerByMonth(p);
        Object.keys(p.manpowerByMonth).forEach(function (k) {
          var arr = p.manpowerByMonth[k];
          if (idx < arr.length) arr.splice(idx, 1);
        });
        if (Array.isArray(p.manpower) && idx < p.manpower.length) {
          p.manpower.splice(idx, 1);
        }
      });
    });
  });
  fixManpowerInData(S.data);
  renderTable();
}

function appendManpowerRowNameCells(tr, set, setIdx, projectSet, projectSetIdx, proj, projIdx, admin, structureEditable) {
  if (projectSetIdx === 0 && projIdx === 0) {
    const tdSet = document.createElement('td');
    tdSet.className = 'main col-set';
    tdSet.rowSpan = countSubProjectsInSet(set) || 1;
    if (admin && structureEditable) {
      tdSet.innerHTML = `
          <div class="cell-head-inline">
            <span class="editable-text" onclick="editSetName(${setIdx})">${escapeHtml(set.name)}</span>
            <div class="actions">
              <button type="button" class="icon-btn" title="添加子项目集" onclick="addProjectSet(${setIdx})">+</button>
              <button type="button" class="icon-btn danger" title="删除项目集" onclick="showDeleteModal('set',${setIdx})">×</button>
            </div>
          </div>`;
    } else {
      tdSet.innerHTML = `<div class="cell-head-inline"><span>${escapeHtml(set.name)}</span></div>`;
    }
    tr.appendChild(tdSet);
  }
  if (projIdx === 0) {
    const tdSubSet = document.createElement('td');
    tdSubSet.className = 'sub col-set';
    tdSubSet.rowSpan = getSubProjects(projectSet).length || 1;
    if (admin && structureEditable) {
      tdSubSet.innerHTML = `
          <div class="cell-head-inline">
            <span class="editable-text" onclick="editProjectSetName(${setIdx},${projectSetIdx})">${escapeHtml(projectSet.name)}</span>
            <div class="actions">
              <button type="button" class="icon-btn" title="添加子项目" onclick="addProject(${setIdx},${projectSetIdx})">+</button>
              <button type="button" class="icon-btn danger" title="删除子项目集" onclick="showDeleteModal('projectSet',${setIdx},${projectSetIdx})">×</button>
            </div>
          </div>`;
    } else {
      tdSubSet.innerHTML = `<div class="cell-head-inline"><span>${escapeHtml(projectSet.name)}</span></div>`;
    }
    tr.appendChild(tdSubSet);
  }
  const tdProj = document.createElement('td');
  tdProj.className = 'sub col-proj';
  if (admin && structureEditable) {
    tdProj.innerHTML = `
        <div class="cell-head-inline">
          <span class="editable-text" onclick="editProjectName(${setIdx},${projectSetIdx},${projIdx})">${escapeHtml(proj.name)}</span>
          <div class="actions">
            <button type="button" class="icon-btn danger" title="删除子项目" onclick="showDeleteModal('project',${setIdx},${projectSetIdx},${projIdx})">×</button>
          </div>
        </div>`;
  } else {
    tdProj.innerHTML = `<div class="cell-head-inline"><span>${escapeHtml(proj.name)}</span></div>`;
  }
  tr.appendChild(tdProj);
}

function renderMonthTableBody() {
  const $body = document.getElementById('table-body');
  if (!$body) return;
  $body.innerHTML = '';
  const nCols = deptFlatCount();
  const admin = canEditPanel('manpower');
  S.data.forEach(function (set, setIdx) {
    getProgramProjectSets(set).forEach(function (projectSet, projectSetIdx) {
      getSubProjects(projectSet).forEach(function (proj, projIdx) {
        const tr = document.createElement('tr');
        if (setIdx % 2 === 1) tr.classList.add('manpower-set-stripe-b');
        appendManpowerRowNameCells(tr, set, setIdx, projectSet, projectSetIdx, proj, projIdx, admin, true);
        for (let i = 0; i < nCols; ++i) {
          const tdC = document.createElement('td');
          tdC.className = 'center-cell col-mp';
          const v = proj.manpower[i] != null ? proj.manpower[i] : 0;
          if (admin) {
            tdC.innerHTML = `
            <span id="v-${setIdx}-${projectSetIdx}-${projIdx}-${i}" ondblclick="editManpower(${setIdx},${projectSetIdx},${projIdx},${i})">${escapeHtml(String(v))}</span>
            <div class="actions inline">
              <button type="button" class="text-action" title="编辑" onclick="editManpower(${setIdx},${projectSetIdx},${projIdx},${i})">编辑</button>
            </div>`;
          } else {
            tdC.innerHTML = '<span>' + escapeHtml(String(v)) + '</span>';
          }
          tr.appendChild(tdC);
        }
        $body.appendChild(tr);
      });
    });
  });
}

function renderSeasonTableBody() {
  const $body = document.getElementById('register-season-body');
  if (!$body) return;
  $body.innerHTML = '';
  const nCols = deptFlatCount();
  const y = S.manpowerSelYear;
  const admin = canEditPanel('manpower');
  S.data.forEach(function (set, setIdx) {
    getProgramProjectSets(set).forEach(function (projectSet, projectSetIdx) {
      getSubProjects(projectSet).forEach(function (proj, projIdx) {
        const tr = document.createElement('tr');
        if (setIdx % 2 === 1) tr.classList.add('manpower-set-stripe-b');
        appendManpowerRowNameCells(tr, set, setIdx, projectSet, projectSetIdx, proj, projIdx, admin, false);
        for (let i = 0; i < nCols; ++i) {
          const tdC = document.createElement('td');
          tdC.className = 'center-cell col-mp manpower-readonly-cell';
          tdC.textContent = String(sumQuarterDept(proj, y, S.manpowerSelQuarter, i));
          tr.appendChild(tdC);
        }
        $body.appendChild(tr);
      });
    });
  });
}

function renderYearTableBody() {
  const $body = document.getElementById('register-year-body');
  if (!$body) return;
  $body.innerHTML = '';
  const nCols = deptFlatCount();
  const y = S.manpowerSelYear;
  const admin = canEditPanel('manpower');
  S.data.forEach(function (set, setIdx) {
    getProgramProjectSets(set).forEach(function (projectSet, projectSetIdx) {
      getSubProjects(projectSet).forEach(function (proj, projIdx) {
        const tr = document.createElement('tr');
        if (setIdx % 2 === 1) tr.classList.add('manpower-set-stripe-b');
        appendManpowerRowNameCells(tr, set, setIdx, projectSet, projectSetIdx, proj, projIdx, admin, false);
        for (let i = 0; i < nCols; ++i) {
          const tdC = document.createElement('td');
          tdC.className = 'center-cell col-mp manpower-readonly-cell';
          tdC.textContent = String(sumYearDept(proj, y, i));
          tr.appendChild(tdC);
        }
        $body.appendChild(tr);
      });
    });
  });
}

// 渲染表格主体
function renderTable() {
  syncManpowerStructureFromPhase();
  updateManpowerToolbarInputs();
  if (S.manpowerSubView === 'month') {
    syncProjectManpowerPointerToMonth();
    renderManpowerTheadMonth();
    renderMonthTableBody();
  } else if (S.manpowerSubView === 'season') {
    renderManpowerTheadSeason();
    renderSeasonTableBody();
  } else {
    renderManpowerTheadYear();
    renderYearTableBody();
  }
}

// 编辑项目集名称（以阶段表为准，同步到人力表）
function editSetName(setIdx) {
  if (!requireManpowerMonthViewForStructure()) return;
  if (!requireAdminOrAlert()) return;
  const set = S.phaseData[setIdx];
  if (!set) return;
  const name = prompt('输入新的项目集名称：', set.name);
  if (name && name.trim()) {
    set.name = name.trim();
    renderPhaseTable();
    renderTable();
  }
}
// 编辑项目名称（以阶段表为准，同步到人力表）
function editProjectSetName(setIdx, projectSetIdx) {
  if (!requireManpowerMonthViewForStructure()) return;
  if (!requireAdminOrAlert()) return;
  const projectSet = S.phaseData[setIdx] && getProgramProjectSets(S.phaseData[setIdx])[projectSetIdx];
  if (!projectSet) return;
  const name = prompt('输入新的子项目集名称：', projectSet.name);
  if (name && name.trim()) {
    projectSet.name = name.trim();
    renderPhaseTable();
    renderTable();
  }
}
// 编辑子项目名称（以阶段表为准，同步到人力表）
function editProjectName(setIdx, projectSetIdx, projIdx) {
  if (!requireManpowerMonthViewForStructure()) return;
  if (!requireAdminOrAlert()) return;
  const projectSet = S.phaseData[setIdx] && getProgramProjectSets(S.phaseData[setIdx])[projectSetIdx];
  const proj = projectSet && getSubProjects(projectSet)[projIdx];
  if (!proj) return;
  const name = prompt('输入新的子项目名称：', proj.name);
  if (name && name.trim()) {
    proj.name = name.trim();
    renderPhaseTable();
    renderTable();
  }
}
// 新增项目集（写入阶段表并同步人力）
function addProjectSet(setIdx) {
  if (!requireManpowerMonthViewForStructure()) return;
  if (!requireAdminOrAlert()) return;
  const name = prompt(setIdx == null ? '输入新项目集的名称：' : '输入新子项目集的名称：');
  if (name && name.trim()) {
    const newProj = { name: '新子项目', phaseByMonth: {} };
    getPhaseMonthSlice(newProj, S.phaseSelYear, S.phaseSelMonth);
    if (setIdx == null) {
      S.phaseData.push({
        name: name.trim(),
        projectSets: [{ name: '默认子项目集', subProjects: [newProj] }]
      });
    } else {
      const set = S.phaseData[setIdx];
      if (!set) return;
      if (!Array.isArray(set.projectSets)) set.projectSets = [];
      set.projectSets.push({ name: name.trim(), subProjects: [newProj] });
    }
    fixPhaseInData(S.phaseData);
    renderPhaseTable();
    renderTable();
  }
}
// 新增项目（写入阶段表并同步人力）
function addProject(setIdx, projectSetIdx) {
  if (!requireManpowerMonthViewForStructure()) return;
  if (!requireAdminOrAlert()) return;
  const name = prompt('输入新子项目名称：');
  if (name && name.trim()) {
    const newProj = { name: name.trim(), phaseByMonth: {} };
    getPhaseMonthSlice(newProj, S.phaseSelYear, S.phaseSelMonth);
    const projectSet = S.phaseData[setIdx] && getProgramProjectSets(S.phaseData[setIdx])[projectSetIdx];
    if (!projectSet) return;
    if (!Array.isArray(projectSet.subProjects)) projectSet.subProjects = [];
    projectSet.subProjects.push(newProj);
    fixPhaseInData(S.phaseData);
    renderPhaseTable();
    renderTable();
  }
}

// 编辑人力格子
function editManpower(setIdx, projectSetIdx, projIdx, col) {
  if (!requireManpowerMonthViewForStructure()) return;
  if (!requireAdminOrAlert()) return;
  const key = `v-${setIdx}-${projectSetIdx}-${projIdx}-${col}`;
  const el = document.getElementById(key);
  if (!el) return;
  const oldVal = S.data[setIdx].projectSets[projectSetIdx].subProjects[projIdx].manpower[col];
  el.innerHTML = `<input type="number" class="input-p" id="input-${key}" min="0" max="99" value="${oldVal}" 
    onblur="saveManpower(${setIdx},${projectSetIdx},${projIdx},${col}, this.value)"
    onkeydown="if(event.key==='Enter'){this.blur()}else if(event.key==='Escape'){this.parentNode.innerHTML='${oldVal}' }"
  >`;
  document.getElementById(`input-${key}`).focus();
}
function saveManpower(setIdx, projectSetIdx, projIdx, col, val) {
  if (!requireManpowerMonthViewForStructure()) return;
  if (!requireAdminOrAlert()) return;
  const v = Number(val);
  if (!isNaN(v) && v>=0 && v<100) {
    S.data[setIdx].projectSets[projectSetIdx].subProjects[projIdx].manpower[col] = v;
    renderTable();
  } else {
    alert('请输入0-99的人力人数');
    renderTable();
  }
}

// 删除弹窗
function showDeleteModal(type, setIdx, projectSetIdx=null, projIdx=null) {
  if ((type === 'set' || type === 'projectSet' || type === 'project') && !requireManpowerMonthViewForStructure()) return;
  if (!requireAdminOrAlert()) return;
  S.delCtx = {type, setIdx, projectSetIdx, projIdx};
  const msgEl = document.getElementById('modal-msg');
  if (type === 'set') {
    msgEl.textContent = '确认删除项目集 "' + (S.phaseData[setIdx] && S.phaseData[setIdx].name != null ? S.phaseData[setIdx].name : '') + '"？其下所有项目的阶段与人力记录将一并删除。';
  } else if (type === 'projectSet') {
    var ps = S.phaseData[setIdx] && getProgramProjectSets(S.phaseData[setIdx])[projectSetIdx];
    msgEl.textContent = '确认删除子项目集 "' + (ps && ps.name != null ? ps.name : '') + '"？其下子项目将一并删除。';
  } else {
    var targetSet = S.phaseData[setIdx] && getProgramProjectSets(S.phaseData[setIdx])[projectSetIdx];
    var pp = targetSet && getSubProjects(targetSet)[projIdx];
    msgEl.textContent = '确认删除子项目 "' + (pp && pp.name != null ? pp.name : '') + '"？';
  }
  openDeleteModal();
}
function closeModal() {
  S.delCtx = null;
  const mask = document.getElementById('modal-mask');
  mask.classList.remove('active');
  mask.setAttribute('aria-hidden', 'true');
  if (S.modalFocusReturn && typeof S.modalFocusReturn.focus === 'function') {
    try { S.modalFocusReturn.focus(); } catch (err) {}
  }
  S.modalFocusReturn = null;
}
function confirmDelete() {
  if (!S.delCtx) return;
  if (!requireAdminOrAlert()) {
    closeModal();
    return;
  }
  const kind = S.delCtx.type;
  if ((kind === 'set' || kind === 'projectSet' || kind === 'project') && !requireManpowerMonthViewForStructure()) {
    closeModal();
    return;
  }
  if (kind === 'set') {
    S.phaseData.splice(S.delCtx.setIdx, 1);
  }
  else if (kind === 'projectSet') {
    S.phaseData[S.delCtx.setIdx].projectSets.splice(S.delCtx.projectSetIdx, 1);
    if (S.phaseData[S.delCtx.setIdx].projectSets.length === 0) {
      S.phaseData.splice(S.delCtx.setIdx, 1);
    }
  }
  else if (kind === 'project') {
    S.phaseData[S.delCtx.setIdx].projectSets[S.delCtx.projectSetIdx].subProjects.splice(S.delCtx.projIdx, 1);
    if (S.phaseData[S.delCtx.setIdx].projectSets[S.delCtx.projectSetIdx].subProjects.length === 0) {
      S.phaseData[S.delCtx.setIdx].projectSets.splice(S.delCtx.projectSetIdx, 1);
    }
    if (S.phaseData[S.delCtx.setIdx].projectSets.length === 0) {
      S.phaseData.splice(S.delCtx.setIdx, 1);
    }
  }
  else if (kind === 'risk') {
    S.riskRows.splice(S.delCtx.riskIdx, 1);
  }
  closeModal();
  if (kind === 'risk') renderRiskTable();
  else if (kind === 'set' || kind === 'projectSet' || kind === 'project') {
    renderPhaseTable();
    renderTable();
  } else {
    renderTable();
  }
}
async function pmBootstrap() {
  var me = await fetchAuthMe();
  if (me === null) return;
  window.__pmCurrentUser = me;
  S.appUserRole = me.role === 'admin' ? 'admin' : 'viewer';
  syncPmRoleGlobal();
  bindPmLogoutButtons();
  wirePanelEditToggleButtons();

  (function initTabSwitching() {
    var tabsBar = document.querySelector('.tabs');
    if (!tabsBar) return;
    if (tabsBar._pmTabWired) return;
    tabsBar._pmTabWired = true;
    tabsBar.addEventListener('click', function (e) {
      var btn = e.target.closest('.tab');
      if (!btn || !tabsBar.contains(btn)) return;
      var target = btn.getAttribute('S.data-target');
      if (!target) return;
      tabsBar.querySelectorAll('.tab').forEach(function (b) {
        var on = b === btn;
        b.classList.toggle('active', on);
        b.setAttribute('aria-selected', on ? 'true' : 'false');
      });
      document.querySelectorAll('.tab-panel').forEach(function (p) {
        p.classList.toggle('active', p.id === target);
      });
      scrollMainToTop();
      if (target === 'panel-guide' && typeof window.__renderGuideMenu === 'function') {
        window.__renderGuideMenu();
      }
      if (target === 'panel-settings') {
        initSettingsPanelOnce();
        updateSettingsPanelRoleUi();
      }
      if (target === 'panel-phase') {
        renderPhaseTable();
      }
    });
  })();

  (function setupModalA11y() {
    var mask = document.getElementById('modal-mask');
    if (!mask) return;
    mask.addEventListener('keydown', function (e) {
      if (!mask.classList.contains('active')) return;
      if (e.key === 'Escape') {
        e.preventDefault();
        closeModal();
        return;
      }
      if (e.key !== 'Tab') return;
      var buttons = mask.querySelectorAll('.modal-box button');
      if (buttons.length === 0) return;
      var first = buttons[0];
      var last = buttons[buttons.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    });
  })();

  setTimeout(function () {
    (async function () {
      await loadRegistryData();
      loadAppSettings();
      initManpowerTimeUi();
      initPhaseTimeUi();
      initRiskAnalysisUi();
      renderTable();
      renderRiskTable();
      renderPhaseTable();
      applyPermissionToAllUI();
      initSettingsPanelOnce();
      updateSettingsPanelRoleUi();
    })();
  }, 0);
}
pmBootstrap().catch(function (err) {
  console.warn('[PM-tool] pmBootstrap failed', err);
});
