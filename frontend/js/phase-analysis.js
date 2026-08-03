// ===== 项目阶段健康度分析（按需懒加载）=====

var PHASE_WEAKNESS_KW = [
  { regex: /延期|延迟|滞后|赶不上/, signal: '进度风险', weight: 2 },
  { regex: /人力|人手不足|缺人|资源/, signal: '资源问题', weight: 2 },
  { regex: /阻塞|停滞|卡住|受阻/, signal: '阻塞', weight: 3 },
  { regex: /沟通|协作|配合|对接/, signal: '协作问题', weight: 1 },
  { regex: /技术|架构|重构|改造/, signal: '技术挑战', weight: 1 },
  { regex: /需求|变更|范围|调整/, signal: '需求变化', weight: 1 },
  { regex: /风险|隐患|安全问题/, signal: '安全风险', weight: 2 },
  { regex: /质量|缺陷|bug/i, signal: '质量问题', weight: 1 }
];

function assessPlanMatch(text) {
  if (!text || !text.trim()) return null;
  var txt = text.trim();
  if (/按计划|按时|如期|提前|已完成|达到预期|符合预期/.test(txt)) return 3;
  if (/基本|大部分|接近/.test(txt)) return 2;
  if (/严重|停滞|阻塞|无法|大量|未开始|未启动/.test(txt)) return 0;
  if (/延期|延迟|推迟|滞后|落后/.test(txt)) return 1;
  if (/进行中|在推进|正常/.test(txt)) return 2;
  return null;
}

function extractWeaknessSignals(text) {
  if (!text || !text.trim()) return [];
  var signals = [];
  PHASE_WEAKNESS_KW.forEach(function(rule) {
    if (rule.regex.test(text)) {
      signals.push({ signal: rule.signal, weight: rule.weight });
    }
  });
  return signals;
}

function assessHealthLevel(slice) {
  var hasData = false;
  PHASE_FIELD_KEYS.forEach(function(k) {
    if (slice[k] && slice[k].trim()) hasData = true;
  });
  if (!hasData) return 'grey';
  var planScore = assessPlanMatch(slice.planMatch);
  var signals = extractWeaknessSignals(slice.weakness);
  var maxWeight = 0;
  signals.forEach(function(s) { if (s.weight > maxWeight) maxWeight = s.weight; });
  if (planScore === 0 || maxWeight >= 3) return 'red';
  if (planScore === 1 || maxWeight >= 2) return 'yellow';
  if (planScore === 2) return 'yellow';
  if (planScore === 3 && maxWeight < 2) return 'green';
  return 'green';
}

function buildPhaseHealthStats() {
  var stats = { total: 0, health: 0, attention: 0, risk: 0, noData: 0, projects: [] };
  var riskMap = {};
  riskRows.forEach(function(r) {
    if (!r._subProjectId) return;
    if (!riskMap[r._subProjectId]) riskMap[r._subProjectId] = { total: 0, unresolved: 0, high: 0 };
    riskMap[r._subProjectId].total++;
    if (r.status !== 'close' && r.status !== 'closed') {
      riskMap[r._subProjectId].unresolved++;
      if (r.level === '高') riskMap[r._subProjectId].high++;
    }
  });
  phaseData.forEach(function(set) {
    getProgramProjectSets(set).forEach(function(ps) {
      getSubProjects(ps).forEach(function(p) {
        var slice = p._phaseSlice || { goal: '', deliver: '', planMatch: '', highlight: '', weakness: '', nextNote: '' };
        var level = assessHealthLevel(slice);
        var risks = riskMap[p._subProjectId] || { total: 0, unresolved: 0, high: 0 };
        var info = {
          name: p.name || '',
          setName: set.name || '',
          projectSetName: ps.name || '',
          subProjectId: p._subProjectId,
          health: level,
          planMatch: slice.planMatch || '',
          weakness: slice.weakness || '',
          highlight: slice.highlight || '',
          planScore: assessPlanMatch(slice.planMatch),
          weaknessSignals: extractWeaknessSignals(slice.weakness),
          unresolvedRisks: risks.unresolved,
          highRisks: risks.high
        };
        stats.projects.push(info);
        stats.total++;
        if (level === 'green') stats.health++;
        else if (level === 'yellow') stats.attention++;
        else if (level === 'red') stats.risk++;
        else stats.noData++;
      });
    });
  });
  var signalCounts = {};
  stats.projects.forEach(function(p) {
    p.weaknessSignals.forEach(function(s) {
      if (!signalCounts[s.signal]) signalCounts[s.signal] = { count: 0, projects: [], examples: [] };
      signalCounts[s.signal].count++;
      if (signalCounts[s.signal].projects.indexOf(p.name) === -1) {
        signalCounts[s.signal].projects.push(p.name);
      }
    });
    if (p.weakness && p.weakness.trim()) {
      var txt = p.weakness.trim();
      PHASE_WEAKNESS_KW.forEach(function(rule) {
        if (rule.regex.test(txt)) {
          if (signalCounts[rule.signal]) {
            var short = txt.length > 30 ? txt.slice(0, 30) + '...' : txt;
            if (signalCounts[rule.signal].examples.indexOf(short) === -1) {
              signalCounts[rule.signal].examples.push(short);
            }
          }
        }
      });
    }
  });
  stats.commonIssues = signalCounts;
  stats.maxCommonCount = 0;
  Object.keys(signalCounts).forEach(function(k) {
    if (signalCounts[k].count > stats.maxCommonCount) stats.maxCommonCount = signalCounts[k].count;
  });
  return stats;
}

function renderPhaseHealthCards(stats) {
  var el = document.getElementById('phase-health-cards');
  if (!el) return;
  el.innerHTML =
    '<div class="phase-health-card phase-hc-green">' +
      '<div class="phase-hc-count">' + stats.health + '</div>' +
      '<div class="phase-hc-label">健康</div>' +
    '</div>' +
    '<div class="phase-health-card phase-hc-yellow">' +
      '<div class="phase-hc-count">' + stats.attention + '</div>' +
      '<div class="phase-hc-label">关注</div>' +
    '</div>' +
    '<div class="phase-health-card phase-hc-red">' +
      '<div class="phase-hc-count">' + stats.risk + '</div>' +
      '<div class="phase-hc-label">风险</div>' +
    '</div>' +
    '<div class="phase-health-card phase-hc-grey">' +
      '<div class="phase-hc-count">' + stats.noData + '</div>' +
      '<div class="phase-hc-label">无数据</div>' +
    '</div>';
}

function renderPhaseHealthGrid(stats) {
  var el = document.getElementById('phase-health-grid');
  if (!el) return;

  // Determine flat sets: if every project-set under a set has only 1 sub-project,
  // merge them into a single row grouped by set name.
  var setAnalysis = {};
  stats.projects.forEach(function(p) {
    if (!setAnalysis[p.setName]) setAnalysis[p.setName] = { total: 0, psetNames: {} };
    setAnalysis[p.setName].total++;
    setAnalysis[p.setName].psetNames[p.projectSetName] = true;
  });
  var flatSets = {};
  Object.keys(setAnalysis).forEach(function(sn) {
    var sa = setAnalysis[sn];
    if (sa.total === Object.keys(sa.psetNames).length) flatSets[sn] = true;
  });

  var groups = {};
  stats.projects.forEach(function(p) {
    var key, isFlat = !!flatSets[p.setName];
    if (isFlat) {
      key = p.setName;
      if (!groups[key]) groups[key] = { setName: p.setName, isFlat: true, projects: [] };
    } else {
      key = p.setName + '|' + p.projectSetName;
      if (!groups[key]) groups[key] = { setName: p.setName, projectSetName: p.projectSetName, isFlat: false, projects: [] };
    }
    groups[key].projects.push(p);
  });
  var html = '';
  Object.keys(groups).forEach(function(key) {
    var g = groups[key];
    var dots = g.projects.map(function(p) {
      var dotCls = p.health === 'green' ? 'g' : p.health === 'yellow' ? 'y' : p.health === 'red' ? 'r' : 'gr';
      var itemCls = p.health;
      return '<span class="phase-hg-item ' + itemCls + '"><span class="phase-hg-dot ' + dotCls + '"></span>' + escapeHtml(p.name) + '</span>';
    });
    var title = g.isFlat ? g.setName : (g.setName + ' · ' + g.projectSetName);
    html += '<div class="phase-hg-group">' +
      '<div class="phase-hg-group-title">' + escapeHtml(title) + '</div>' +
      '<div class="phase-hg-row">' + dots.join('') + '</div>' +
    '</div>';
  });
  el.innerHTML = html;
}

function renderPhaseAttentionList(stats) {
  var el = document.getElementById('phase-attention-list');
  if (!el) return;
  var items = stats.projects.filter(function(p) { return p.health === 'red' || p.health === 'yellow'; });
  items.sort(function(a, b) {
    if (a.health === 'red' && b.health !== 'red') return -1;
    if (a.health !== 'red' && b.health === 'red') return 1;
    return 0;
  });
  if (items.length === 0) {
    el.innerHTML = '<div class="phase-empty-muted">暂无需要关注的项目</div>';
    return;
  }
  var html = '';
  items.forEach(function(p) {
    var isRed = p.health === 'red';
    var cls = isRed ? 'red' : 'yellow';
    var taCls = isRed ? 'red' : 'orange';
    var taLabel = isRed ? '风险' : '关注';
    var riskHtml = '';
    if (p.unresolvedRisks > 0) {
      var riskColor = isRed ? 'color:#c62828;' : 'color:#e65100;';
      var desc = '⚠ 关联 ' + p.unresolvedRisks + ' 条未解决风险';
      if (p.highRisks > 0) desc += ' · ' + p.highRisks + ' 条高危';
      riskHtml = '<div class="phase-attn-meta" style="' + riskColor + '">' + desc + '</div>';
    }
    html += '<div class="phase-attn-item ' + cls + '">' +
      '<div class="phase-attn-icon">' + (isRed ? '🔴' : '🟡') + '</div>' +
      '<div class="phase-attn-body">' +
        '<div class="phase-attn-title">' +
          escapeHtml(p.name) +
          '<span class="phase-attn-tag ' + taCls + '">' + taLabel + '</span>' +
          '<span style="font-size:11px;color:#6B7280;font-weight:400;">' + escapeHtml(p.setName + ' · ' + p.projectSetName) + '</span>' +
        '</div>' +
        '<div class="phase-attn-meta">计划匹配度：' + escapeHtml(p.planMatch || '未填写') + ' ｜ 不足：' + escapeHtml(p.weakness || '未填写') + '</div>' +
        riskHtml +
      '</div>' +
    '</div>';
  });
  el.innerHTML = html;
}

function renderPhaseCommonIssues(stats) {
  var el = document.getElementById('phase-common-issues');
  if (!el) return;
  var issues = [];
  Object.keys(stats.commonIssues).forEach(function(k) {
    issues.push({ signal: k, count: stats.commonIssues[k].count, examples: stats.commonIssues[k].examples });
  });
  issues.sort(function(a, b) { return b.count - a.count; });
  if (issues.length === 0) {
    el.innerHTML = '<div class="phase-empty-muted">本月无明显共性问题</div>';
    return;
  }
  var colors = { '资源问题': '#e65100', '进度风险': '#c62828', '阻塞': '#c62828', '协作问题': '#1565c0', '技术挑战': '#6B7280', '需求变化': '#8e24aa', '安全风险': '#c62828', '质量问题': '#e65100' };
  var html = '';
  issues.forEach(function(issue) {
    var pct = stats.maxCommonCount > 0 ? Math.round(issue.count / stats.maxCommonCount * 100) : 100;
    var color = colors[issue.signal] || '#6B7280';
    var examplesText = issue.examples.slice(0, 3).join('、');
    html += '<div class="phase-ci-row">' +
      '<span class="phase-ci-signal" style="color:' + color + ';">' + issue.signal + '</span>' +
      '<div class="phase-ci-bar-bg"><div class="phase-ci-bar-fill" style="width:' + pct + '%;background:' + color + ';"></div></div>' +
      '<span class="phase-ci-count">' + issue.count + ' 项</span>' +
      '<span class="phase-ci-examples">' + escapeHtml(examplesText) + '</span>' +
    '</div>';
  });
  el.innerHTML = html;
}

function renderPhaseInsights(stats) {
  var el = document.getElementById('phase-insights');
  if (!el) return;
  var insights = [];
  var redProjects = stats.projects.filter(function(p) { return p.health === 'red'; });
  redProjects.forEach(function(p) {
    var parts = [];
    if (p.planScore === 0) parts.push('严重延期');
    if (p.unresolvedRisks > 0) parts.push(p.unresolvedRisks + ' 条未解决风险');
    if (p.highRisks > 0) parts.push('含高危风险');
    var reason = parts.length > 0 ? parts.join('、') : '存在明显问题';
    insights.push(p.name + ' 同时存在「' + reason + '」，项目阶段健康亮红灯，建议安排专项跟进。');
  });
  var setGroups = {};
  stats.projects.forEach(function(p) {
    var key = p.setName + '|' + p.projectSetName;
    if (!setGroups[key]) setGroups[key] = { total: 0, noData: 0, projectSetName: p.projectSetName };
    setGroups[key].total++;
    if (p.health === 'grey') setGroups[key].noData++;
  });
  Object.keys(setGroups).forEach(function(k) {
    var g = setGroups[k];
    if (g.total >= 3 && g.noData >= 2) {
      var pct = Math.round(g.noData / g.total * 100);
      insights.push(g.projectSetName + ' 方向下属 ' + g.total + ' 个子项目中有 ' + g.noData + ' 个未填复盘（占 ' + pct + '%），需关注管理覆盖是否到位。');
    }
  });
  var topIssue = null;
  var topCount = 0;
  Object.keys(stats.commonIssues).forEach(function(k) {
    if (stats.commonIssues[k].count > topCount) { topCount = stats.commonIssues[k].count; topIssue = k; }
  });
  if (topIssue && topCount >= 3) {
    insights.push('本月共性问题以「' + topIssue + '」为主（' + topCount + ' 项提及），建议在 PMO 层面统一协调。');
  }
  if (insights.length === 0) { el.innerHTML = ''; return; }
  var html = '<div class="phase-section-title">💡 关注点</div>';
  insights.forEach(function(item) {
    html += '<div class="phase-insight-item"><span style="flex-shrink:0;">🔍</span><span>' + escapeHtml(item) + '</span></div>';
  });
  el.innerHTML = html;
}

function renderPhaseReviewContent() {
  syncPhaseRowPointer();
  var stats = buildPhaseHealthStats();
  renderPhaseHealthCards(stats);
  renderPhaseHealthGrid(stats);
  renderPhaseAttentionList(stats);
  renderPhaseCommonIssues(stats);
  renderPhaseInsights(stats);
}
