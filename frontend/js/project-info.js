/**
 * ProjectGuard 项目信息模块（概要 + 编辑）
 */
(function (global) {
  'use strict';

  var PROJECT_STATUS = {
    active: { label: '进行中', cls: 'pi-tag-active' },
    archived: { label: '已归档', cls: 'pi-tag-archived' }
  };

  var MILESTONE_STATUS = ['pending', 'in-progress', 'completed', 'overdue'];
  var MILESTONE_LABELS = {
    pending: '待开始',
    'in-progress': '进行中',
    completed: '已完成',
    overdue: '已延期'
  };

  var TASK_PHASES = ['需求与设计', '开发实施', '测试验证', '部署上线'];
  var PARTICIPATION = ['核心成员', '兼职参与', '外部协作'];
  var RISK_CATEGORIES = ['质量', '进度', '成本', '范围'];
  var RISK_SOURCES = ['技术', '资源', '管理', '外部'];
  var RISK_LEVELS = ['高', '中', '低'];

  var state = {
    year: new Date().getFullYear(),
    period: '',
    view: 'summary',
    dirty: false,
    tree: null,
    programId: null,
    subProgramId: null,
    subProjectId: null,
    data: null,
    snapshot: null,
    edit: null,
    sortables: []
  };

  function piApi(path) {
    var base = (typeof global.PM_API_BASE !== 'undefined' ? global.PM_API_BASE : (global.PM_API_BASE || ''));
    base = String(base || '').replace(/\/$/, '');
    return base + (path.charAt(0) === '/' ? path : '/' + path);
  }

  function piFetch(path, options) {
    if (global.pmFetch) return global.pmFetch(path, options);
    var opts = options || {};
    var h = Object.assign({}, opts.headers || {});
    if (opts.body && typeof opts.body === 'string' && !h['Content-Type']) {
      h['Content-Type'] = 'application/json';
    }
    return fetch(piApi(path), Object.assign({}, opts, { credentials: 'include', headers: h }));
  }

  function defaultPeriod(year) {
    var now = new Date();
    if (year === now.getFullYear()) {
      return year + '-' + String(now.getMonth() + 1).padStart(2, '0');
    }
    return year < now.getFullYear() ? year + '-12' : year + '-01';
  }

  function esc(s) {
    if (s == null) return '';
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function fmtDate(d) {
    if (!d) return '—';
    return String(d).slice(0, 10);
  }

  function daysBetween(a, b) {
    if (!a || !b) return 0;
    var t0 = new Date(a).getTime();
    var t1 = new Date(b).getTime();
    return Math.max(0, Math.round((t1 - t0) / 86400000));
  }

  function destroySortables() {
    state.sortables.forEach(function (s) {
      try { s.destroy(); } catch (e) {}
    });
    state.sortables = [];
  }

  function markDirty() {
    state.dirty = true;
  }

  function deepClone(obj) {
    return JSON.parse(JSON.stringify(obj));
  }

  function statusTag(status) {
    var m = PROJECT_STATUS[status] || { label: status, cls: '' };
    return '<span class="pi-tag ' + m.cls + '">' + esc(m.label) + '</span>';
  }

  function loadTree() {
    return piFetch('/api/v1/programs/tree?year=' + state.year)
      .then(function (r) {
        if (!r.ok) throw new Error('加载项目树失败');
        return r.json();
      })
      .then(function (body) {
        state.tree = body.programs || [];
        syncTreeSelectors();
      });
  }

  function syncTreeSelectors() {
    var selP = document.getElementById('pi-sel-program');
    var selS = document.getElementById('pi-sel-sub-program');
    var selJ = document.getElementById('pi-sel-sub-project');
    if (!selP || !selS || !selJ) return;

    selP.innerHTML = '';
    state.tree.forEach(function (p) {
      var o = document.createElement('option');
      o.value = p.id;
      o.textContent = p.name;
      selP.appendChild(o);
    });

    if (!state.tree.length) {
      selS.innerHTML = '';
      selJ.innerHTML = '';
      state.programId = null;
      state.subProgramId = null;
      state.subProjectId = null;
      return;
    }

    if (!state.programId || !state.tree.some(function (p) { return p.id === state.programId; })) {
      state.programId = state.tree[0].id;
    }
    selP.value = String(state.programId);

    var prog = state.tree.find(function (p) { return p.id === state.programId; });
    var subs = (prog && prog.sub_programs) || [];
    selS.innerHTML = '';
    subs.forEach(function (s) {
      var o = document.createElement('option');
      o.value = s.id;
      o.textContent = s.name;
      selS.appendChild(o);
    });
    if (!subs.length) {
      selJ.innerHTML = '';
      state.subProgramId = null;
      state.subProjectId = null;
      return;
    }
    if (!state.subProgramId || !subs.some(function (s) { return s.id === state.subProgramId; })) {
      state.subProgramId = subs[0].id;
    }
    selS.value = String(state.subProgramId);

    var spg = subs.find(function (s) { return s.id === state.subProgramId; });
    var leaves = (spg && spg.sub_projects) || [];
    selJ.innerHTML = '';
    leaves.forEach(function (j) {
      var o = document.createElement('option');
      o.value = j.id;
      o.textContent = j.name;
      selJ.appendChild(o);
    });
    if (!leaves.length) {
      state.subProjectId = null;
      return;
    }
    if (!state.subProjectId || !leaves.some(function (j) { return j.id === state.subProjectId; })) {
      state.subProjectId = leaves[0].id;
    }
    selJ.value = String(state.subProjectId);
  }

  function loadProjectInfo() {
    if (!state.subProjectId) {
      state.data = null;
      render();
      return Promise.resolve();
    }
    var url = '/api/v1/project-info/' + state.subProjectId +
      '?year=' + state.year + '&period=' + encodeURIComponent(state.period);
    return piFetch(url)
      .then(function (r) {
        if (!r.ok) throw new Error('加载项目信息失败');
        return r.json();
      })
      .then(function (data) {
        state.data = data;
        state.dirty = false;
        render();
      })
      .catch(function (err) {
        alert(err.message || '加载失败');
      });
  }

  function overallProgress(tasks) {
    if (!tasks || !tasks.length) return 0;
    var sum = tasks.reduce(function (a, t) { return a + (Number(t.progress) || 0); }, 0);
    return Math.round(sum / tasks.length);
  }

  function milestoneStats(ms) {
    var total = ms.length;
    var done = ms.filter(function (m) { return m.status === 'completed'; }).length;
    var prog = ms.filter(function (m) { return m.status === 'in-progress'; }).length;
    var pending = total - done - prog;
    return { total: total, done: done, prog: prog, pending: pending };
  }

  function renderSummary() {
    var root = document.getElementById('pi-summary');
    if (!root) return;
    if (!state.data) {
      root.innerHTML = '<p class="pi-readonly-hint">请选择项目集 / 子项目集 / 子项目</p>';
      return;
    }
    var d = state.data;
    var sp = d.sub_project;
    var ms = milestoneStats(d.milestones || []);
    var prog = overallProgress(d.tasks || []);
    var teamN = (d.team_members || []).length;
    var periodDays = daysBetween(sp.planned_start_date, sp.planned_end_date);

    var msHtml = (d.milestones || []).map(function (m) {
      var color = m.status === 'completed' ? '#34a853' : (m.status === 'in-progress' ? '#1E6FFF' : '#ddd');
      return '<div class="pi-ms-item"><div class="pi-ms-dot" style="background:' + color + '"></div>' +
        '<div><strong>' + esc(m.name) + '</strong></div><div>' + fmtDate(m.planned_date) + '</div>' +
        '<div>' + esc(MILESTONE_LABELS[m.status] || m.status) + '</div></div>';
    }).join('');

    var riskRows = (d.risks || []).slice(0, 6).map(function (r) {
      return '<tr><td>' + esc(r.risk_category) + '</td><td>' + esc(r.risk_source) + '</td><td>' +
        esc(r.level) + '</td><td>' + esc(r.assignee) + '</td><td>' + esc(r.status) + '</td></tr>';
    }).join('');

    var teamRows = (d.team_members || []).map(function (t) {
      return '<tr><td><strong>' + esc(t.name) + '</strong></td><td>' + esc(t.team_column_name) +
        '</td><td>' + esc(t.role) + '</td><td>' + esc(t.participation) + '</td><td>' + esc(t.remark || '') + '</td></tr>';
    }).join('');

    var editBtn = (global.pmIsAdmin && global.pmIsAdmin())
      ? '<button type="button" class="pi-btn pi-btn-primary" id="pi-btn-enter-edit">编辑项目</button>'
      : '';

    root.innerHTML =
      '<div class="pi-toolbar"><span></span>' + editBtn + '</div>' +
      '<div class="pi-cards">' +
      '<div class="pi-stat"><div class="pi-stat-lbl">项目周期</div><div class="pi-stat-val">' + periodDays +
      '<span style="font-size:14px;font-weight:400"> 天</span></div><div class="pi-stat-sub">' +
      fmtDate(sp.planned_start_date) + ' → ' + fmtDate(sp.planned_end_date) + '</div></div>' +
      '<div class="pi-stat"><div class="pi-stat-lbl">团队规模</div><div class="pi-stat-val">' + teamN +
      '<span style="font-size:14px;font-weight:400"> 人</span></div></div>' +
      '<div class="pi-stat"><div class="pi-stat-lbl">里程碑进度</div><div class="pi-stat-val">' + ms.done + ' / ' + ms.total +
      '</div><div class="pi-stat-sub">完成 ' + ms.done + ' · 进行 ' + ms.prog + ' · 待开始 ' + ms.pending + '</div></div>' +
      '<div class="pi-stat"><div class="pi-stat-lbl">整体进度</div><div class="pi-stat-val">' + prog +
      '<span style="font-size:14px;font-weight:400">%</span></div></div></div>' +
      '<div class="pi-card"><h3>项目概要</h3><div class="pi-meta">' +
      '<div class="pi-meta-col"><h4>基本信息</h4>' +
      '<div class="pi-meta-row"><span class="pi-meta-k">项目名称</span><span class="pi-meta-v">' + esc(sp.name) + '</span></div>' +
      '<div class="pi-meta-row"><span class="pi-meta-k">项目状态</span><span class="pi-meta-v">' + statusTag(sp.status) + '</span></div>' +
      '<div class="pi-meta-row"><span class="pi-meta-k">关键目标</span><span class="pi-meta-v">' + esc(sp.key_goal || '—') + '</span></div>' +
      '<div class="pi-meta-row"><span class="pi-meta-k">自动化率</span><span class="pi-meta-v">' + esc(sp.automation_rate_goal || '—') + '</span></div></div>' +
      '<div class="pi-meta-col"><h4>时间信息</h4>' +
      '<div class="pi-meta-row"><span class="pi-meta-k">计划开始</span><span class="pi-meta-v">' + fmtDate(sp.planned_start_date) + '</span></div>' +
      '<div class="pi-meta-row"><span class="pi-meta-k">计划结束</span><span class="pi-meta-v">' + fmtDate(sp.planned_end_date) + '</span></div>' +
      '<div class="pi-meta-row"><span class="pi-meta-k">实际开始</span><span class="pi-meta-v">' + fmtDate(sp.actual_start_date) + '</span></div>' +
      '<div class="pi-meta-row"><span class="pi-meta-k">实际结束</span><span class="pi-meta-v">' + fmtDate(sp.actual_end_date) + '</span></div></div>' +
      '<div class="pi-meta-col"><h4>项目描述</h4><p style="font-size:13px;color:#5f6368;line-height:1.7">' +
      esc(sp.description || '（暂无描述）') + '</p></div></div></div>' +
      '<div class="pi-card"><h3>里程碑</h3><div class="pi-ms-tl">' + (msHtml || '<span>暂无里程碑</span>') + '</div></div>' +
      '<div class="pi-card"><h3>近期风险</h3><table class="pi-table"><thead><tr><th>类别</th><th>来源</th><th>等级</th><th>跟进人</th><th>状态</th></tr></thead><tbody>' +
      (riskRows || '<tr><td colspan="5">暂无风险</td></tr>') + '</tbody></table></div>' +
      '<div class="pi-card"><h3>项目团队</h3><table class="pi-table"><thead><tr><th>姓名</th><th>所属团队</th><th>角色</th><th>参与方式</th><th>备注</th></tr></thead><tbody>' +
      (teamRows || '<tr><td colspan="5">暂无成员</td></tr>') + '</tbody></table></div>';

    var btn = document.getElementById('pi-btn-enter-edit');
    if (btn) btn.addEventListener('click', enterEditView);
  }

  function buildEditState() {
    var d = state.data;
    state.snapshot = deepClone(d);
    state.edit = {
      sub_project: deepClone(d.sub_project),
      milestones: deepClone(d.milestones || []),
      tasks: deepClone(d.tasks || []),
      team_members: deepClone(d.team_members || []),
      risks: deepClone(d.risks || []),
      manpower: deepClone(d.manpower || { period: state.period, cells: [] })
    };
  }

  function enterEditView() {
    if (!(global.pmIsAdmin && global.pmIsAdmin())) return;
    if (!state.data) return;
    buildEditState();
    state.view = 'edit';
    state.dirty = false;
    render();
  }

  function exitEditView() {
    if (state.dirty && !confirm('有未保存的更改，确定离开？')) return;
    state.view = 'summary';
    state.dirty = false;
    state.edit = null;
    destroySortables();
    render();
  }

  function optHtml(values, selected) {
    return values.map(function (v) {
      return '<option value="' + esc(v) + '"' + (v === selected ? ' selected' : '') + '>' + esc(v) + '</option>';
    }).join('');
  }

  function columnOptions(selectedId) {
    var groups = (state.edit.manpower && state.edit.manpower.dept_groups) || [];
    var html = '';
    groups.forEach(function (g) {
      (g.columns || []).forEach(function (c) {
        html += '<option value="' + c.id + '"' + (c.id === selectedId ? ' selected' : '') + '>' +
          esc(g.name) + ' / ' + esc(c.name) + '</option>';
      });
    });
    return html;
  }

  function bindEditInput(sel, fn) {
    document.querySelectorAll(sel).forEach(function (el) {
      el.addEventListener('change', function () { fn(el); markDirty(); });
      el.addEventListener('input', function () { fn(el); markDirty(); });
    });
  }

  function renderEdit() {
    var root = document.getElementById('pi-edit');
    var bar = document.getElementById('pi-bottom-bar');
    if (!root || !state.edit) return;
    var e = state.edit;
    var sp = e.sub_project;

    root.innerHTML =
      '<div class="pi-card"><h3>基本信息</h3><div class="pi-form-grid">' +
      '<div class="pi-form-group"><label>项目名称 *</label><input type="text" id="pi-f-name" value="' + esc(sp.name) + '"></div>' +
      '<div class="pi-form-group"><label>项目状态 *</label><select id="pi-f-status">' +
      '<option value="active"' + (sp.status === 'active' ? ' selected' : '') + '>进行中</option>' +
      '<option value="archived"' + (sp.status === 'archived' ? ' selected' : '') + '>已归档</option></select></div>' +
      '<div class="pi-form-group pi-full"><label>项目描述</label><textarea id="pi-f-desc" rows="3">' + esc(sp.description || '') + '</textarea></div>' +
      '<div class="pi-form-group"><label>关键目标</label><input type="text" id="pi-f-goal" value="' + esc(sp.key_goal || '') + '"></div>' +
      '<div class="pi-form-group"><label>自动化率目标</label><input type="text" id="pi-f-auto" value="' + esc(sp.automation_rate_goal || '') + '"></div></div></div>' +
      '<div class="pi-card"><h3>时间信息</h3><div class="pi-form-grid">' +
      '<div class="pi-form-group"><label>计划开始 *</label><input type="date" id="pi-f-ps" value="' + fmtDate(sp.planned_start_date) + '"></div>' +
      '<div class="pi-form-group"><label>计划结束 *</label><input type="date" id="pi-f-pe" value="' + fmtDate(sp.planned_end_date) + '"></div>' +
      '<div class="pi-form-group"><label>实际开始</label><input type="date" id="pi-f-as" value="' + (sp.actual_start_date ? fmtDate(sp.actual_start_date) : '') + '"></div>' +
      '<div class="pi-form-group"><label>实际结束</label><input type="date" id="pi-f-ae" value="' + (sp.actual_end_date ? fmtDate(sp.actual_end_date) : '') + '"></div></div></div>' +
      '<div class="pi-card"><h3>里程碑</h3><table class="pi-table" id="pi-tbl-milestones"><thead><tr><th></th><th>名称</th><th>计划日期</th><th>状态</th><th>描述</th><th></th></tr></thead><tbody></tbody></table>' +
      '<button type="button" class="pi-btn" id="pi-add-milestone">+ 添加里程碑</button></div>' +
      '<div class="pi-card"><h3>任务</h3><table class="pi-table" id="pi-tbl-tasks"><thead><tr><th></th><th>名称</th><th>阶段</th><th>负责人</th><th>开始</th><th>结束</th><th>进度</th><th></th></tr></thead><tbody></tbody></table>' +
      '<button type="button" class="pi-btn" id="pi-add-task">+ 添加任务</button></div>' +
      '<div class="pi-card"><h3>项目团队</h3><table class="pi-table" id="pi-tbl-team"><thead><tr><th></th><th>姓名</th><th>所属团队</th><th>角色</th><th>参与方式</th><th>备注</th><th></th></tr></thead><tbody></tbody></table>' +
      '<button type="button" class="pi-btn" id="pi-add-team">+ 添加成员</button></div>' +
      '<div class="pi-card"><h3>人力投入</h3><div class="pi-toolbar"><label>月份</label><select id="pi-f-month"></select></div>' +
      '<table class="pi-table" id="pi-tbl-manpower"><thead><tr><th>部门列</th><th>投入（人天）</th></tr></thead><tbody></tbody></table></div>' +
      '<div class="pi-card"><h3>风险管理</h3><table class="pi-table" id="pi-tbl-risks"><thead><tr><th>类别</th><th>来源</th><th>说明</th><th>方案</th><th>等级</th><th>跟进人</th><th>登记时间</th><th>解除时间</th><th>状态</th><th></th></tr></thead><tbody></tbody></table>' +
      '<button type="button" class="pi-btn" id="pi-add-risk">+ 添加风险</button></div>';

    if (bar) bar.classList.remove('pi-hidden');

    bindEditInput('#pi-f-name', function (el) { e.sub_project.name = el.value; });
    bindEditInput('#pi-f-status', function (el) { e.sub_project.status = el.value; });
    bindEditInput('#pi-f-desc', function (el) { e.sub_project.description = el.value; });
    bindEditInput('#pi-f-goal', function (el) { e.sub_project.key_goal = el.value; });
    bindEditInput('#pi-f-auto', function (el) { e.sub_project.automation_rate_goal = el.value; });
    bindEditInput('#pi-f-ps', function (el) { e.sub_project.planned_start_date = el.value || null; });
    bindEditInput('#pi-f-pe', function (el) { e.sub_project.planned_end_date = el.value || null; });
    bindEditInput('#pi-f-as', function (el) { e.sub_project.actual_start_date = el.value || null; });
    bindEditInput('#pi-f-ae', function (el) { e.sub_project.actual_end_date = el.value || null; });

    renderMilestoneRows();
    renderTaskRows();
    renderTeamRows();
    renderManpowerMonthSelect();
    renderManpowerRows();
    renderRiskRows();

    document.getElementById('pi-add-milestone').addEventListener('click', function () {
      e.milestones.push({
        id: null, name: '新里程碑', planned_date: state.year + '-06-01',
        status: 'pending', description: '', sort_order: e.milestones.length
      });
      markDirty();
      renderMilestoneRows();
    });
    document.getElementById('pi-add-task').addEventListener('click', function () {
      e.tasks.push({
        id: null, name: '新任务', phase: TASK_PHASES[0], assignee: '',
        start_date: state.year + '-06-01', end_date: state.year + '-06-30',
        progress: 0, sort_order: e.tasks.length
      });
      markDirty();
      renderTaskRows();
    });
    document.getElementById('pi-add-team').addEventListener('click', function () {
      var colId = firstColumnId();
      e.team_members.push({
        id: null, name: '', team_column_id: colId, role: '项目负责人',
        participation: '核心成员', remark: '', sort_order: e.team_members.length
      });
      markDirty();
      renderTeamRows();
    });
    document.getElementById('pi-add-risk').addEventListener('click', function () {
      e.risks.push({
        id: null, risk_category: '进度', risk_source: '资源', description: '',
        solution: '', level: '中', assignee: '', resolution_date: null, status: 'Open'
      });
      markDirty();
      renderRiskRows();
    });

    initSortable('pi-tbl-milestones', 'milestones');
    initSortable('pi-tbl-tasks', 'tasks');
    initSortable('pi-tbl-team', 'team_members');
  }

  function firstColumnId() {
    var groups = (state.edit.manpower && state.edit.manpower.dept_groups) || [];
    for (var i = 0; i < groups.length; i++) {
      var cols = groups[i].columns || [];
      if (cols.length) return cols[0].id;
    }
    return 0;
  }

  function renderMilestoneRows() {
    var tbody = document.querySelector('#pi-tbl-milestones tbody');
    if (!tbody) return;
    var e = state.edit;
    tbody.innerHTML = e.milestones.map(function (m, idx) {
      return '<tr data-idx="' + idx + '"><td class="pi-drag">⠿</td><td><input data-f="name" value="' + esc(m.name) + '"></td>' +
        '<td><input type="date" data-f="planned_date" value="' + fmtDate(m.planned_date) + '"></td>' +
        '<td><select data-f="status">' + MILESTONE_STATUS.map(function (s) {
          return '<option value="' + s + '"' + (m.status === s ? ' selected' : '') + '>' + (MILESTONE_LABELS[s] || s) + '</option>';
        }).join('') + '</select></td>' +
        '<td><input data-f="description" value="' + esc(m.description || '') + '"></td>' +
        '<td><button type="button" class="pi-btn" data-del="ms">删</button></td></tr>';
    }).join('');
    wireRowInputs(tbody, e.milestones);
    tbody.querySelectorAll('[data-del="ms"]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var idx = parseInt(btn.closest('tr').getAttribute('data-idx'), 10);
        e.milestones.splice(idx, 1);
        markDirty();
        renderMilestoneRows();
      });
    });
  }

  function renderTaskRows() {
    var tbody = document.querySelector('#pi-tbl-tasks tbody');
    if (!tbody) return;
    var e = state.edit;
    tbody.innerHTML = e.tasks.map(function (t, idx) {
      return '<tr data-idx="' + idx + '"><td class="pi-drag">⠿</td><td><input data-f="name" value="' + esc(t.name) + '"></td>' +
        '<td><select data-f="phase">' + optHtml(TASK_PHASES, t.phase) + '</select></td>' +
        '<td><input data-f="assignee" value="' + esc(t.assignee || '') + '"></td>' +
        '<td><input type="date" data-f="start_date" value="' + fmtDate(t.start_date) + '"></td>' +
        '<td><input type="date" data-f="end_date" value="' + fmtDate(t.end_date) + '"></td>' +
        '<td><input type="range" min="0" max="100" data-f="progress" value="' + (t.progress || 0) + '"> ' +
        (t.progress || 0) + '%</td>' +
        '<td><button type="button" class="pi-btn" data-del="task">删</button></td></tr>';
    }).join('');
    wireRowInputs(tbody, e.tasks);
    tbody.querySelectorAll('input[data-f="progress"]').forEach(function (el) {
      el.addEventListener('input', function () {
        var idx = parseInt(el.closest('tr').getAttribute('data-idx'), 10);
        e.tasks[idx].progress = parseInt(el.value, 10) || 0;
        el.nextSibling.textContent = e.tasks[idx].progress + '%';
        markDirty();
      });
    });
    tbody.querySelectorAll('[data-del="task"]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var idx = parseInt(btn.closest('tr').getAttribute('data-idx'), 10);
        e.tasks.splice(idx, 1);
        markDirty();
        renderTaskRows();
      });
    });
  }

  function renderTeamRows() {
    var tbody = document.querySelector('#pi-tbl-team tbody');
    if (!tbody) return;
    var e = state.edit;
    tbody.innerHTML = e.team_members.map(function (t, idx) {
      return '<tr data-idx="' + idx + '"><td class="pi-drag">⠿</td><td><input data-f="name" value="' + esc(t.name) + '"></td>' +
        '<td><select data-f="team_column_id">' + columnOptions(t.team_column_id) + '</select></td>' +
        '<td><input data-f="role" value="' + esc(t.role) + '"></td>' +
        '<td><select data-f="participation">' + optHtml(PARTICIPATION, t.participation) + '</select></td>' +
        '<td><input data-f="remark" value="' + esc(t.remark || '') + '"></td>' +
        '<td><button type="button" class="pi-btn" data-del="team">删</button></td></tr>';
    }).join('');
    wireRowInputs(tbody, e.team_members, function (el, row, field) {
      if (field === 'team_column_id') row.team_column_id = parseInt(el.value, 10);
    });
    tbody.querySelectorAll('[data-del="team"]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var idx = parseInt(btn.closest('tr').getAttribute('data-idx'), 10);
        e.team_members.splice(idx, 1);
        markDirty();
        renderTeamRows();
      });
    });
  }

  function renderManpowerMonthSelect() {
    var sel = document.getElementById('pi-f-month');
    if (!sel) return;
    sel.innerHTML = '';
    for (var m = 1; m <= 12; m++) {
      var p = state.year + '-' + String(m).padStart(2, '0');
      var o = document.createElement('option');
      o.value = p;
      o.textContent = m + '月';
      sel.appendChild(o);
    }
    sel.value = state.edit.manpower.period || state.period;
    sel.onchange = function () {
      var newPeriod = sel.value;
      piFetch('/api/v1/project-info/' + state.subProjectId + '?year=' + state.year + '&period=' + encodeURIComponent(newPeriod))
        .then(function (r) { return r.json(); })
        .then(function (data) {
          state.edit.manpower.period = data.manpower.period;
          state.edit.manpower.cells = data.manpower.cells || [];
          state.edit.manpower.dept_groups = data.manpower.dept_groups;
          renderManpowerRows();
        });
    };
  }

  function cellAllocation(columnId) {
    var cells = state.edit.manpower.cells || [];
    var c = cells.find(function (x) { return x.column_id === columnId; });
    return c ? c.allocation : 0;
  }

  function setCellAllocation(columnId, val) {
    var cells = state.edit.manpower.cells || [];
    var c = cells.find(function (x) { return x.column_id === columnId; });
    if (c) c.allocation = val;
    else cells.push({ column_id: columnId, allocation: val });
    state.edit.manpower.cells = cells;
  }

  function renderManpowerRows() {
    var tbody = document.querySelector('#pi-tbl-manpower tbody');
    if (!tbody) return;
    var groups = state.edit.manpower.dept_groups || [];
    var rows = '';
    groups.forEach(function (g) {
      (g.columns || []).forEach(function (col) {
        var val = cellAllocation(col.id);
        rows += '<tr><td>' + esc(g.name) + ' / ' + esc(col.name) + '</td>' +
          '<td><input type="number" step="0.5" min="0" data-col="' + col.id + '" value="' + val + '"></td></tr>';
      });
    });
    tbody.innerHTML = rows || '<tr><td colspan="2">请先在设置中配置人力表头</td></tr>';
    tbody.querySelectorAll('input[data-col]').forEach(function (el) {
      el.addEventListener('change', function () {
        setCellAllocation(parseInt(el.getAttribute('data-col'), 10), parseFloat(el.value) || 0);
        markDirty();
      });
    });
  }

  function renderRiskRows() {
    var tbody = document.querySelector('#pi-tbl-risks tbody');
    if (!tbody) return;
    var e = state.edit;
    tbody.innerHTML = e.risks.map(function (r, idx) {
      return '<tr data-idx="' + idx + '">' +
        '<td><select data-f="risk_category">' + optHtml(RISK_CATEGORIES, r.risk_category) + '</select></td>' +
        '<td><select data-f="risk_source">' + optHtml(RISK_SOURCES, r.risk_source) + '</select></td>' +
        '<td><textarea data-f="description">' + esc(r.description || '') + '</textarea></td>' +
        '<td><textarea data-f="solution">' + esc(r.solution || '') + '</textarea></td>' +
        '<td><select data-f="level">' + optHtml(RISK_LEVELS, r.level) + '</select></td>' +
        '<td><input data-f="assignee" value="' + esc(r.assignee || '') + '"></td>' +
        '<td style="color:#9aa0a6;font-size:12px">' + (r.created_at ? fmtDate(r.created_at) : '（新建）') + '</td>' +
        '<td><input type="date" data-f="resolution_date" value="' + (r.resolution_date ? fmtDate(r.resolution_date) : '') + '"></td>' +
        '<td><select data-f="status"><option value="Open"' + (r.status === 'Open' ? ' selected' : '') + '>Open</option>' +
        '<option value="Close"' + (r.status === 'Close' ? ' selected' : '') + '>Close</option></select></td>' +
        '<td><button type="button" class="pi-btn" data-del="risk">删</button></td></tr>';
    }).join('');
    wireRowInputs(tbody, e.risks, function (el, row, field) {
      if (field === 'resolution_date') row.resolution_date = el.value || null;
    });
    tbody.querySelectorAll('[data-del="risk"]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var idx = parseInt(btn.closest('tr').getAttribute('data-idx'), 10);
        e.risks.splice(idx, 1);
        markDirty();
        renderRiskRows();
      });
    });
  }

  function wireRowInputs(tbody, arr, extra) {
    tbody.querySelectorAll('[data-f]').forEach(function (el) {
      var field = el.getAttribute('data-f');
      var handler = function () {
        var idx = parseInt(el.closest('tr').getAttribute('data-idx'), 10);
        arr[idx][field] = el.value;
        if (extra) extra(el, arr[idx], field);
        markDirty();
      };
      el.addEventListener('change', handler);
      el.addEventListener('input', handler);
    });
  }

  function initSortable(tableId, key) {
    if (!global.Sortable) return;
    var tbody = document.querySelector('#' + tableId + ' tbody');
    if (!tbody) return;
    var s = global.Sortable.create(tbody, {
      handle: '.pi-drag',
      animation: 120,
      onEnd: function () {
        var order = [];
        tbody.querySelectorAll('tr[data-idx]').forEach(function (tr, i) {
          var idx = parseInt(tr.getAttribute('data-idx'), 10);
          order.push(state.edit[key][idx]);
        });
        order.forEach(function (item, i) { item.sort_order = i; });
        state.edit[key] = order;
        markDirty();
        if (key === 'milestones') renderMilestoneRows();
        if (key === 'tasks') renderTaskRows();
        if (key === 'team_members') renderTeamRows();
      }
    });
    state.sortables.push(s);
  }

  function deletedIds(snapshotList, currentList) {
    var curIds = {};
    currentList.forEach(function (r) { if (r.id) curIds[r.id] = true; });
    return snapshotList.filter(function (r) { return r.id && !curIds[r.id]; }).map(function (r) { return r.id; });
  }

  function buildPutPayload() {
    var e = state.edit;
    var snap = state.snapshot;
    return {
      sub_project: {
        name: e.sub_project.name,
        status: e.sub_project.status,
        description: e.sub_project.description || null,
        key_goal: e.sub_project.key_goal || null,
        automation_rate_goal: e.sub_project.automation_rate_goal || null,
        planned_start_date: e.sub_project.planned_start_date,
        planned_end_date: e.sub_project.planned_end_date,
        actual_start_date: e.sub_project.actual_start_date || null,
        actual_end_date: e.sub_project.actual_end_date || null
      },
      milestones: e.milestones.map(function (m) {
        return {
          id: m.id, name: m.name, planned_date: m.planned_date,
          status: m.status, description: m.description || null, sort_order: m.sort_order
        };
      }),
      deleted_milestone_ids: deletedIds(snap.milestones || [], e.milestones),
      tasks: e.tasks.map(function (t) {
        return {
          id: t.id, name: t.name, phase: t.phase, assignee: t.assignee || null,
          start_date: t.start_date, end_date: t.end_date, progress: t.progress || 0, sort_order: t.sort_order
        };
      }),
      deleted_task_ids: deletedIds(snap.tasks || [], e.tasks),
      team_members: e.team_members.map(function (t) {
        return {
          id: t.id, name: t.name, team_column_id: t.team_column_id, role: t.role,
          participation: t.participation, remark: t.remark || null, sort_order: t.sort_order
        };
      }),
      deleted_team_member_ids: deletedIds(snap.team_members || [], e.team_members),
      risks: e.risks.map(function (r) {
        return {
          id: r.id, risk_category: r.risk_category, risk_source: r.risk_source,
          description: r.description, solution: r.solution || null, level: r.level,
          assignee: r.assignee, resolution_date: r.resolution_date || null, status: r.status
        };
      }),
      deleted_risk_ids: deletedIds(snap.risks || [], e.risks),
      manpower: {
        period: e.manpower.period || state.period,
        cells: (e.manpower.cells || []).map(function (c) {
          return { column_id: c.column_id, allocation: String(c.allocation) };
        })
      }
    };
  }

  function saveEdit() {
    if (!state.edit || !state.subProjectId) return;
    var sp = state.edit.sub_project;
    if (!sp.name || !sp.planned_start_date || !sp.planned_end_date) {
      alert('请填写项目名称与计划日期');
      return;
    }
    if (sp.planned_end_date < sp.planned_start_date) {
      alert('计划结束日期不能早于开始日期');
      return;
    }
    var payload = buildPutPayload();
    piFetch('/api/v1/project-info/' + state.subProjectId + '?year=' + state.year, {
      method: 'PUT',
      body: JSON.stringify(payload)
    }).then(function (r) {
      if (!r.ok) {
        return r.json().then(function (j) {
          throw new Error((j && j.detail) ? (typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)) : '保存失败');
        });
      }
      return r.json();
    }).then(function (data) {
      state.data = data;
      state.period = data.period;
      state.view = 'summary';
      state.dirty = false;
      state.edit = null;
      destroySortables();
      render();
      alert('保存成功');
    }).catch(function (err) {
      alert(err.message || '保存失败');
    });
  }

  function render() {
    var summary = document.getElementById('pi-summary');
    var edit = document.getElementById('pi-edit');
    var bar = document.getElementById('pi-bottom-bar');
    if (state.view === 'edit') {
      if (summary) summary.classList.add('pi-hidden');
      if (edit) edit.classList.remove('pi-hidden');
      renderEdit();
    } else {
      if (summary) summary.classList.remove('pi-hidden');
      if (edit) edit.classList.add('pi-hidden');
      if (bar) bar.classList.add('pi-hidden');
      destroySortables();
      renderSummary();
    }
  }

  function wireControls() {
    var yearSel = document.getElementById('pi-year');
    if (yearSel) {
      yearSel.value = String(state.year);
      yearSel.addEventListener('change', function () {
        if (state.dirty && !confirm('切换年度将丢失未保存更改，是否继续？')) {
          yearSel.value = String(state.year);
          return;
        }
        state.year = parseInt(yearSel.value, 10);
        state.period = defaultPeriod(state.year);
        state.dirty = false;
        loadTree().then(loadProjectInfo);
      });
    }
    var selP = document.getElementById('pi-sel-program');
    var selS = document.getElementById('pi-sel-sub-program');
    var selJ = document.getElementById('pi-sel-sub-project');
    function applySelectionFromDom() {
      if (selP && selP.value) state.programId = parseInt(selP.value, 10);
      syncTreeSelectors();
      if (selS && selS.value) state.subProgramId = parseInt(selS.value, 10);
      if (selJ && selJ.value) state.subProjectId = parseInt(selJ.value, 10);
    }
    function onProjectSelectionChange(revert) {
      if (state.dirty && !confirm('切换项目将丢失未保存更改，是否继续？')) {
        if (revert) revert();
        return;
      }
      applySelectionFromDom();
      state.dirty = false;
      loadProjectInfo();
    }
    if (selP) {
      selP.addEventListener('change', function () {
        var prev = { p: state.programId, s: state.subProgramId, j: state.subProjectId };
        state.programId = parseInt(selP.value, 10);
        onProjectSelectionChange(function () {
          state.programId = prev.p;
          state.subProgramId = prev.s;
          state.subProjectId = prev.j;
          syncTreeSelectors();
        });
      });
    }
    if (selS) {
      selS.addEventListener('change', function () {
        var prev = { s: state.subProgramId, j: state.subProjectId };
        state.programId = parseInt(selP.value, 10);
        state.subProgramId = parseInt(selS.value, 10);
        onProjectSelectionChange(function () {
          state.subProgramId = prev.s;
          state.subProjectId = prev.j;
          syncTreeSelectors();
        });
      });
    }
    if (selJ) {
      selJ.addEventListener('change', function () {
        var prev = state.subProjectId;
        applySelectionFromDom();
        onProjectSelectionChange(function () {
          state.subProjectId = prev;
          syncTreeSelectors();
        });
      });
    }
    var cancelBtn = document.getElementById('pi-btn-cancel');
    var saveBtn = document.getElementById('pi-btn-save');
    if (cancelBtn) cancelBtn.addEventListener('click', exitEditView);
    if (saveBtn) saveBtn.addEventListener('click', saveEdit);
  }

  function init() {
    state.period = defaultPeriod(state.year);
    wireControls();
    global.addEventListener('beforeunload', function (e) {
      if (state.dirty) {
        e.preventDefault();
        e.returnValue = '';
      }
    });
  }

  function onTabShow() {
    state.period = defaultPeriod(state.year);
    loadTree().then(loadProjectInfo);
  }

  global.ProjectInfoModule = {
    init: init,
    onTabShow: onTabShow
  };
})(window);
