/**
 * ProjectGuard 项目信息模块（概要 + 编辑）
 */
(function (global) {
  'use strict';

  var PROJECT_STATUS = {
    active: { label: '进行中', cls: 'pi-tag-active' },
    archived: { label: '已归档', cls: 'pi-tag-archived' }
  };

  var TASK_STATUS = ['pending', 'in-progress', 'completed', 'overdue'];
  var TASK_STATUS_LABELS = {
    pending: '待开始',
    'in-progress': '进行中',
    completed: '已完成',
    overdue: '已延期'
  };

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
    treeLoadError: null,
    programId: null,
    subProgramId: null,
    subProjectId: null,
    data: null,
    snapshot: null,
    edit: null,
    sortables: []
  };

  function getWorkYear() {
    if (global.pmGetWorkYear) return global.pmGetWorkYear();
    return state.year;
  }

  function syncYearFromGlobal() {
    state.year = getWorkYear();
    state.period = defaultPeriod(state.year);
  }

  function isAdmin() {
    return !!(global.pmIsAdmin && global.pmIsAdmin());
  }

  function afterTreeChanged(selectIds) {
    var reload = global.pmReloadRegistryAfterProjectTreeChange;
    var chain = reload ? reload() : Promise.resolve();
    return Promise.resolve(chain).then(function () {
      return loadTree().then(function () {
        if (selectIds) {
          if (selectIds.programId != null) state.programId = selectIds.programId;
          if (selectIds.subProgramId != null) state.subProgramId = selectIds.subProgramId;
          if (selectIds.subProjectId != null) state.subProjectId = selectIds.subProjectId;
          syncTreeSelectors();
        }
        return loadProjectInfo();
      });
    });
  }

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

  function encodeYearQuery() {
    return 'year=' + encodeURIComponent(String(getWorkYear()));
  }

  function piJsonRequest(path, options) {
    return piFetch(path, options || {}).then(function (r) {
      if (r.status === 401) {
        global.location.href = 'login.html';
        throw new Error('unauthorized');
      }
      if (!r.ok) {
        return r.json().catch(function () { return {}; }).then(function (err) {
          var detail = err.detail != null ? err.detail : '请求失败';
          throw new Error(detail + '（HTTP ' + r.status + '）');
        });
      }
      if (r.status === 204) return null;
      return r.json();
    });
  }

  function createProgramWithDefaultLeaf(programName, sortOrder) {
    var y = getWorkYear();
    return piJsonRequest('/api/v1/programs', {
      method: 'POST',
      body: JSON.stringify({ year: y, name: programName, sort_order: sortOrder || 0 })
    }).then(function (program) {
      return piJsonRequest(
        '/api/v1/programs/' + encodeURIComponent(String(program.id)) + '/sub-programs?' + encodeYearQuery(),
        { method: 'POST', body: JSON.stringify({ name: '默认子项目集', sort_order: 0 }) }
      ).then(function (subProgram) {
        if (!subProgram || !subProgram.id) throw new Error('sub_program not created');
        return piJsonRequest(
          '/api/v1/programs/sub-programs/' + encodeURIComponent(String(subProgram.id)) + '/sub-projects?' + encodeYearQuery(),
          { method: 'POST', body: JSON.stringify({ name: '新子项目', sort_order: 0 }) }
        ).then(function (subProject) {
          return {
            programId: program.id,
            subProgramId: subProgram.id,
            subProjectId: subProject && subProject.id
          };
        });
      });
    });
  }

  function createSubProgramWithDefaultLeaf(programId, subProgramName, sortOrder) {
    return piJsonRequest(
      '/api/v1/programs/' + encodeURIComponent(String(programId)) + '/sub-programs?' + encodeYearQuery(),
      { method: 'POST', body: JSON.stringify({ name: subProgramName, sort_order: sortOrder || 0 }) }
    ).then(function (subProgram) {
      if (!subProgram || !subProgram.id) throw new Error('sub_program not created');
      return piJsonRequest(
        '/api/v1/programs/sub-programs/' + encodeURIComponent(String(subProgram.id)) + '/sub-projects?' + encodeYearQuery(),
        { method: 'POST', body: JSON.stringify({ name: '新子项目', sort_order: 0 }) }
      ).then(function (subProject) {
        return {
          programId: programId,
          subProgramId: subProgram.id,
          subProjectId: subProject && subProject.id
        };
      });
    });
  }

  function createSubProject(subProgramId, projectName, sortOrder) {
    return piJsonRequest(
      '/api/v1/programs/sub-programs/' + encodeURIComponent(String(subProgramId)) + '/sub-projects?' + encodeYearQuery(),
      { method: 'POST', body: JSON.stringify({ name: projectName, sort_order: sortOrder || 0 }) }
    ).then(function (subProject) {
      return { subProjectId: subProject && subProject.id };
    });
  }

  function patchProgram(programId, name) {
    return piJsonRequest(
      '/api/v1/programs/' + encodeURIComponent(String(programId)) + '?' + encodeYearQuery(),
      { method: 'PATCH', body: JSON.stringify({ name: name }) }
    );
  }

  function patchSubProgram(subProgramId, name) {
    return piJsonRequest(
      '/api/v1/programs/sub-programs/' + encodeURIComponent(String(subProgramId)) + '?' + encodeYearQuery(),
      { method: 'PATCH', body: JSON.stringify({ name: name }) }
    );
  }

  function patchSubProject(subProjectId, name) {
    return piJsonRequest(
      '/api/v1/programs/sub-projects/' + encodeURIComponent(String(subProjectId)) + '?' + encodeYearQuery(),
      { method: 'PATCH', body: JSON.stringify({ name: name }) }
    );
  }

  function deleteProgram(programId) {
    return piJsonRequest(
      '/api/v1/programs/' + encodeURIComponent(String(programId)) + '?' + encodeYearQuery(),
      { method: 'DELETE' }
    );
  }

  function deleteSubProgram(subProgramId) {
    return piJsonRequest(
      '/api/v1/programs/sub-programs/' + encodeURIComponent(String(subProgramId)) + '?' + encodeYearQuery(),
      { method: 'DELETE' }
    );
  }

  function deleteSubProject(subProjectId) {
    return piJsonRequest(
      '/api/v1/programs/sub-projects/' + encodeURIComponent(String(subProjectId)) + '?' + encodeYearQuery(),
      { method: 'DELETE' }
    );
  }

  function showTreeLoading() {
    if (state.view === 'edit') return;
    var box = document.getElementById('pi-empty-state');
    if (!box) return;
    box.classList.remove('pi-hidden');
    box.innerHTML = '<div class="pi-empty-card"><p>正在加载项目列表…</p></div>';
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

  function fmtManMonth(v) {
    var n = Number(v);
    if (isNaN(n)) return '0.0';
    return n.toFixed(1);
  }

  function saturationBadge(level, rate) {
    var pct = Math.round(Number(rate) * 100);
    var cls = level === 'over' ? 'pi-sat-over' : (level === 'normal' ? 'pi-sat-normal' : 'pi-sat-low');
    return '<span class="pi-sat ' + cls + '">' + pct + '%</span>';
  }

  function projectMonthlyTotal(members) {
    return (members || []).reduce(function (sum, m) {
      return sum + (Number(m.monthly_allocation) || 0);
    }, 0);
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
    syncYearFromGlobal();
    state.treeLoadError = null;
    showTreeLoading();
    return piFetch('/api/v1/programs/tree?year=' + state.year)
      .then(function (r) {
        if (!r.ok) throw new Error('加载项目树失败（HTTP ' + r.status + '）');
        return r.json();
      })
      .then(function (body) {
        state.tree = body.programs || [];
        syncTreeSelectors();
        updateAdminTools();
        render();
      })
      .catch(function (err) {
        state.tree = [];
        state.treeLoadError = err.message || '加载项目树失败';
        state.programId = null;
        state.subProgramId = null;
        state.subProjectId = null;
        state.data = null;
        updateAdminTools();
        render();
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
    if (isEditing()) clearEditView();
    if (!state.subProjectId) {
      state.data = null;
      render();
      return Promise.resolve();
    }
    var url = '/api/v1/project-info/' + state.subProjectId +
      '?year=' + state.year + '&period=' + encodeURIComponent(state.period);
    return piFetch(url)
      .then(function (r) {
        if (!r.ok) throw new Error('加载项目信息登记失败');
        return r.json();
      })
      .then(function (data) {
        state.data = data;
        state.period = data.period || state.period;
        state.dirty = false;
        render();
      })
      .catch(function (err) {
        alert(err.message || '加载失败');
      });
  }

  function overallProgress(tasks) {
    if (!tasks || !tasks.length) return 0;
    var completed = 0, total = 0;
    function count(list) {
      (list || []).forEach(function (t) {
        total++;
        if (t.status === 'completed') completed++;
        if (t.children && t.children.length) count(t.children);
      });
    }
    count(tasks);
    return total === 0 ? 0 : Math.round(completed / total * 100);
  }



  function buildTaskSummaryRows(tasks, depth) {
    depth = depth || 0;
    var rows = [];
    tasks.forEach(function (t) {
      var indent = depth > 0 ? '<span style="display:inline-block;width:' + (depth * 20) + 'px"></span>└ ' : '';
      var milestoneBadge = t.is_milestone ? ' <span style="font-size:10px;background:#e8f0fe;color:#1E6FFF;padding:1px 6px;border-radius:3px">里程碑</span>' : '';
      rows.push('<tr><td>' + indent + '<strong>' + esc(t.name) + '</strong>' + milestoneBadge + '</td><td>' +
        esc(TASK_STATUS_LABELS[t.status] || t.status) + '</td>' +
        '<td>' + esc(t.assignee || '—') + '</td><td>' + fmtDate(t.start_date) + '</td>' +
        '<td>' + fmtDate(t.end_date) + '</td></tr>');
      if (t.children && t.children.length) {
        rows = rows.concat(buildTaskSummaryRows(t.children, depth + 1));
      }
    });
    return rows;
  }

  function milestoneStats(ms) {
    var total = ms.length;
    var done = ms.filter(function (m) { return m.status === 'completed'; }).length;
    var prog = ms.filter(function (m) { return m.status === 'in-progress'; }).length;
    var pending = total - done - prog;
    return { total: total, done: done, prog: prog, pending: pending };
  }

  function buildMilestoneGroupedHtml(milestones) {
    if (!milestones.length) return '<span>暂无里程碑</span>';
    // 按 end_date 分组（里程碑的达成日期）
    var groups = {};
    milestones.forEach(function (m) {
      var key = m.end_date || '无日期';
      if (!groups[key]) groups[key] = [];
      groups[key].push(m);
    });
    // 按日期排序
    var keys = Object.keys(groups).sort();
    return '<div class="pi-ms-timeline">' + keys.map(function (dateKey, ki) {
      var items = groups[dateKey];
      var dateLabel = dateKey === '无日期' ? '未设置日期' : dateKey;
      var done = items.filter(function (m) { return m.status === 'completed'; }).length;
      var groupMs = items.map(function (m) {
        var color = m.status === 'completed' ? '#34a853' : (m.status === 'in-progress' ? '#1E6FFF' : '#ddd');
        return '<div class="pi-ms-item">' +
          '<div class="pi-ms-dot" style="background:' + color + '"></div>' +
          '<div class="pi-ms-item-body"><div class="pi-ms-item-name">' + esc(m.name) + '</div>' +
          '<div class="pi-ms-item-status">' + esc(TASK_STATUS_LABELS[m.status] || m.status) + '</div></div></div>';
      }).join('');
      return '<div class="pi-ms-col">' +
        (ki > 0 ? '<div class="pi-ms-arrow">→</div>' : '') +
        '<div class="pi-ms-date-card"><div class="pi-ms-date-label">' + esc(dateLabel) + '</div>' +
        '<div class="pi-ms-date-progress">' + done + '/' + items.length + ' 完成</div></div>' +
        '<div class="pi-ms-items">' + groupMs + '</div></div>';
    }).join('') + '</div>';
  }

  function renderEmptyState() {
    var box = document.getElementById('pi-empty-state');
    if (!box) return;
    if (state.view === 'edit') {
      box.classList.add('pi-hidden');
      box.innerHTML = '';
      return;
    }
    if (state.treeLoadError) {
      box.classList.remove('pi-hidden');
      box.innerHTML =
        '<div class="pi-empty-card pi-empty-error">' +
        '<h3>无法加载项目列表</h3>' +
        '<p>' + esc(state.treeLoadError) + '</p>' +
        '<p class="pi-empty-sub">请检查网络或联系管理员；若刚发版，请确认数据库迁移已执行。</p>' +
        '<button type="button" class="pi-btn pi-btn-primary" id="pi-btn-retry-tree">重试</button>' +
        '</div>';
      var retry = document.getElementById('pi-btn-retry-tree');
      if (retry) retry.addEventListener('click', function () { loadTree().then(loadProjectInfo); });
      return;
    }
    if (!state.tree || !state.tree.length) {
      box.classList.remove('pi-hidden');
      if (isAdmin()) {
        box.innerHTML =
          '<div class="pi-empty-card">' +
          '<h3>' + state.year + ' 年还没有项目</h3>' +
          '<p>年初请先创建项目结构，再填写项目信息登记与各登记页数据。</p>' +
          '<p class="pi-empty-sub">将自动创建：项目集 → 默认子项目集 → 子项目</p>' +
          '<button type="button" class="pi-btn pi-btn-primary" id="pi-btn-create-first">+ 创建第一个项目集</button>' +
          '</div>';
        var cbtn = document.getElementById('pi-btn-create-first');
        if (cbtn) cbtn.addEventListener('click', handleCreateFirstProgram);
      } else {
        box.innerHTML =
          '<div class="pi-empty-card">' +
          '<h3>' + state.year + ' 年还没有项目</h3>' +
          '<p>请联系管理员在「项目信息登记」页创建项目结构。</p>' +
          '</div>';
      }
      return;
    }
    if (!state.subProjectId) {
      box.classList.remove('pi-hidden');
      if (isAdmin()) {
        var hint = !state.programId
          ? '请先选择或创建项目集。'
          : (!state.subProgramId ? '当前项目集下还没有子项目集。' : '当前子项目集下还没有子项目。');
        box.innerHTML =
          '<div class="pi-empty-card">' +
          '<h3>尚未选择可编辑的子项目</h3>' +
          '<p>' + esc(hint) + '</p>' +
          '<div class="pi-empty-actions">' +
          (!state.programId
            ? '<button type="button" class="pi-btn pi-btn-primary" id="pi-btn-create-first">+ 创建项目集</button>'
            : (!state.subProgramId
              ? '<button type="button" class="pi-btn pi-btn-primary" id="pi-btn-add-sub-program-empty">+ 新建子项目集</button>'
              : '<button type="button" class="pi-btn pi-btn-primary" id="pi-btn-add-sub-project-empty">+ 新建子项目</button>')) +
          '</div></div>';
        var b1 = document.getElementById('pi-btn-create-first');
        if (b1) b1.addEventListener('click', handleCreateFirstProgram);
        var b2 = document.getElementById('pi-btn-add-sub-program-empty');
        if (b2) b2.addEventListener('click', handleAddSubProgram);
        var b3 = document.getElementById('pi-btn-add-sub-project-empty');
        if (b3) b3.addEventListener('click', handleAddSubProject);
      } else {
        box.innerHTML =
          '<div class="pi-empty-card"><h3>尚未选择子项目</h3><p>请从上方下拉框选择，或联系管理员创建项目。</p></div>';
      }
      return;
    }
    box.classList.add('pi-hidden');
    box.innerHTML = '';
  }

  function isEditing() {
    return state.view === 'edit';
  }

  function clearEditView() {
    state.view = 'summary';
    state.dirty = false;
    state.edit = null;
    destroySortables();
    var bar = document.getElementById('pi-bottom-bar');
    if (bar) bar.classList.add('pi-hidden');
  }

  function updateEditLockUi() {
    var locked = isEditing();
    var row = document.querySelector('#panel-project-info .pi-toolbar-row');
    if (row) row.classList.toggle('pi-toolbar-row--locked', locked);
    ['pi-sel-program', 'pi-sel-sub-program', 'pi-sel-sub-project'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.disabled = locked;
    });
    var tools = document.getElementById('pi-structure-tools');
    if (tools && !tools.hidden) {
      tools.querySelectorAll('button').forEach(function (btn) {
        btn.disabled = locked;
      });
    }
  }

  function updateAdminTools() {
    var tools = document.getElementById('pi-structure-tools');
    if (!tools) return;
    tools.hidden = !isAdmin();
  }

  function handleCreateFirstProgram() {
    if (!isAdmin()) return;
    if (isEditing()) return;
    var name = prompt('输入新项目集名称：');
    if (!name || !String(name).trim()) return;
    createProgramWithDefaultLeaf(String(name).trim(), 0)
      .then(function (ids) { return afterTreeChanged(ids); })
      .catch(function (e) { alert((e && e.message) || '创建失败'); });
  }

  function handleAddProgram() {
    if (!isAdmin()) return;
    if (isEditing()) return;
    var name = prompt('输入新项目集名称：');
    if (!name || !String(name).trim()) return;
    createProgramWithDefaultLeaf(String(name).trim(), (state.tree || []).length)
      .then(function (ids) { return afterTreeChanged(ids); })
      .catch(function (e) { alert((e && e.message) || '创建失败'); });
  }

  function handleAddSubProgram() {
    if (!isAdmin()) return;
    if (isEditing()) return;
    if (!state.programId) {
      alert('请先选择项目集。');
      return;
    }
    var prog = (state.tree || []).find(function (p) { return p.id === state.programId; });
    var name = prompt('输入新子项目集名称：');
    if (!name || !String(name).trim()) return;
    createSubProgramWithDefaultLeaf(state.programId, String(name).trim(), ((prog && prog.sub_programs) || []).length)
      .then(function (ids) { return afterTreeChanged(ids); })
      .catch(function (e) { alert((e && e.message) || '创建失败'); });
  }

  function handleAddSubProject() {
    if (!isAdmin()) return;
    if (isEditing()) return;
    if (!state.subProgramId) {
      alert('请先选择子项目集。');
      return;
    }
    var prog = (state.tree || []).find(function (p) { return p.id === state.programId; });
    var spg = prog && (prog.sub_programs || []).find(function (s) { return s.id === state.subProgramId; });
    var name = prompt('输入新子项目名称：');
    if (!name || !String(name).trim()) return;
    createSubProject(state.subProgramId, String(name).trim(), ((spg && spg.sub_projects) || []).length)
      .then(function (ids) {
        return afterTreeChanged({
          programId: state.programId,
          subProgramId: state.subProgramId,
          subProjectId: ids.subProjectId
        });
      })
      .catch(function (e) { alert((e && e.message) || '创建失败'); });
  }

  function handleRenameNode() {
    if (!isAdmin()) return;
    if (isEditing()) return;
    var prog = (state.tree || []).find(function (p) { return p.id === state.programId; });
    var spg = prog && (prog.sub_programs || []).find(function (s) { return s.id === state.subProgramId; });
    var leaf = spg && (spg.sub_projects || []).find(function (j) { return j.id === state.subProjectId; });
    if (!prog) {
      alert('请先选择项目集。');
      return;
    }
    var target = 'program';
    var currentName = prog.name;
    if (state.subProjectId && leaf) {
      target = 'sub_project';
      currentName = leaf.name;
    } else if (state.subProgramId && spg) {
      target = 'sub_program';
      currentName = spg.name;
    }
    var name = prompt('输入新名称：', currentName);
    if (name == null || !String(name).trim()) return;
    var p;
    if (target === 'program') p = patchProgram(prog.id, String(name).trim());
    else if (target === 'sub_program') p = patchSubProgram(spg.id, String(name).trim());
    else p = patchSubProject(leaf.id, String(name).trim());
    p.then(function () { return afterTreeChanged(); })
      .catch(function (e) { alert((e && e.message) || '重命名失败'); });
  }

  function handleDeleteNode() {
    if (!isAdmin()) return;
    if (isEditing()) return;
    var prog = (state.tree || []).find(function (p) { return p.id === state.programId; });
    if (!prog) {
      alert('请先选择要删除的节点。');
      return;
    }
    var spg = (prog.sub_programs || []).find(function (s) { return s.id === state.subProgramId; });
    var leaf = spg && (spg.sub_projects || []).find(function (j) { return j.id === state.subProjectId; });
    var msg = '确认删除项目集「' + prog.name + '」？其下所有登记数据将一并删除。';
    if (state.subProjectId && leaf) {
      msg = '确认删除子项目「' + leaf.name + '」？';
      if ((spg.sub_projects || []).length <= 1 && (prog.sub_programs || []).length <= 1) {
        msg = '这是最后一个子项目，删除将移除整个项目集「' + prog.name + '」。确认？';
      } else if ((spg.sub_projects || []).length <= 1) {
        msg = '这是该子项目集下最后一个子项目，删除将移除子项目集「' + spg.name + '」。确认？';
      }
    } else if (state.subProgramId && spg) {
      msg = '确认删除子项目集「' + spg.name + '」？其下子项目将一并删除。';
      if ((prog.sub_programs || []).length <= 1) {
        msg = '这是最后一个子项目集，删除将移除整个项目集「' + prog.name + '」。确认？';
      }
    }
    if (!confirm(msg)) return;
    var p;
    if (state.subProjectId && leaf) {
      if ((spg.sub_projects || []).length <= 1 && (prog.sub_programs || []).length <= 1) p = deleteProgram(prog.id);
      else if ((spg.sub_projects || []).length <= 1) p = deleteSubProgram(spg.id);
      else p = deleteSubProject(leaf.id);
    } else if (state.subProgramId && spg) {
      if ((prog.sub_programs || []).length <= 1) p = deleteProgram(prog.id);
      else p = deleteSubProgram(spg.id);
    } else {
      p = deleteProgram(prog.id);
    }
    p.then(function () { return afterTreeChanged(); })
      .catch(function (e) { alert((e && e.message) || '删除失败'); });
  }

  function renderSummary() {
    var root = document.getElementById('pi-summary');
    if (!root) return;
    renderEmptyState();
    if (!state.data || state.treeLoadError || !state.subProjectId) {
      root.innerHTML = '';
      return;
    }
    var d = state.data;
    var sp = d.sub_project;
    var ms = milestoneStats(d.milestones || []);
    var prog = overallProgress(d.tasks || []);
    var teamN = (d.team_members || []).length;
    var periodDays = daysBetween(sp.planned_start_date, sp.planned_end_date);
    var goals = d.goals || [];

    var msHtml = buildMilestoneGroupedHtml(d.milestones || []);

    var riskRows = (d.risks || []).map(function (r) {
      return '<tr><td>' + esc(r.risk_category) + '</td><td>' + esc(r.risk_source) + '</td>' +
        '<td class="pi-cell-text">' + esc(r.description || '—') + '</td>' +
        '<td class="pi-cell-text">' + esc(r.solution || '—') + '</td>' +
        '<td>' + esc(r.level) + '</td><td>' + esc(r.assignee) + '</td>' +
        '<td>' + fmtDate(r.created_at) + '</td><td>' + fmtDate(r.resolution_date) + '</td>' +
        '<td>' + esc(r.status) + '</td></tr>';
    }).join('');

    // 渲染任务（带层级展开，任务树已包含里程碑标签的任务）
    var taskRowsHtml = buildTaskSummaryRows(d.tasks || [], 0).join('');

    var teamRows = (d.team_members || []).map(function (t) {
      return '<tr><td><strong>' + esc(t.name) + '</strong></td><td>' + esc(t.team_column_name) +
        '</td><td>' + esc(t.role) + '</td><td>' + esc(t.participation) + '</td>' +
        '<td>' + fmtManMonth(t.monthly_allocation) + '</td>' +
        '<td>' + fmtManMonth(t.person_total_allocation) + '</td>' +
        '<td>' + saturationBadge(t.person_saturation_level, t.person_saturation_rate) + '</td>' +
        '<td>' + esc(t.remark || '') + '</td></tr>';
    }).join('');
    var monthTotal = fmtManMonth(d.project_monthly_total != null ? d.project_monthly_total : projectMonthlyTotal(d.team_members));

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
      '<span style="font-size:14px;font-weight:400">%</span></div></div>' +
      '<div class="pi-stat"><div class="pi-stat-lbl">本月投入</div><div class="pi-stat-val">' + monthTotal +
      '<span style="font-size:14px;font-weight:400"> 人月</span></div>' +
      '<div class="pi-stat-sub">' + esc(d.period || state.period) + '</div></div></div>' +
      '<div class="pi-card"><h3>项目概要</h3><div class="pi-meta">' +
      '<div class="pi-meta-col pi-meta-col--basic"><h4>基本信息</h4><div class="pi-meta-fields">' +
      '<div class="pi-meta-row"><span class="pi-meta-k">项目名称</span><span class="pi-meta-v">' + esc(sp.name) + '</span></div>' +
      '<div class="pi-meta-row"><span class="pi-meta-k">项目状态</span><span class="pi-meta-v">' + statusTag(sp.status) + '</span></div>' +
      '<div class="pi-meta-row pi-meta-row--full"><span class="pi-meta-k">关键目标</span><span class="pi-meta-v pi-meta-v--multiline">' + esc(sp.key_goal || '—') + '</span></div></div></div>' +
      '<div class="pi-meta-col pi-meta-col--time"><h4>时间信息</h4>' +
      '<div class="pi-meta-row"><span class="pi-meta-k">计划开始</span><span class="pi-meta-v">' + fmtDate(sp.planned_start_date) + '</span></div>' +
      '<div class="pi-meta-row"><span class="pi-meta-k">计划结束</span><span class="pi-meta-v">' + fmtDate(sp.planned_end_date) + '</span></div>' +
      '<div class="pi-meta-row"><span class="pi-meta-k">实际开始</span><span class="pi-meta-v">' + fmtDate(sp.actual_start_date) + '</span></div>' +
      '<div class="pi-meta-row"><span class="pi-meta-k">实际结束</span><span class="pi-meta-v">' + fmtDate(sp.actual_end_date) + '</span></div></div>' +
      '<div class="pi-meta-col pi-meta-col--desc"><h4>项目描述</h4><p class="pi-meta-desc">' +
      esc(sp.description || '（暂无描述）') + '</p></div></div></div>' +
      (goals.length > 0 ? '<div class="pi-card"><h3>🎯 项目目标</h3>' +
        '<div class="pi-table-wrap"><table class="pi-table pi-summary-table"><thead><tr>' +
        '<th>目标</th><th>单位</th><th>目标值</th><th>当前值</th><th>状态</th>' +
        '</tr></thead><tbody>' + goals.map(function (g) {
          var target = g.mid_term_target || g.initial_target;
          var cv = g.current_value || '-';
          var st = GOAL_STATUS_MAP[g.overall_status] || '⏳ 未开始';
          return '<tr><td>' + esc(g.name) + '</td><td>' + esc(g.metric_unit || '') +
            '</td><td>' + esc(target) + '</td><td>' + esc(cv) +
            '</td><td>' + st + '</td></tr>';
        }).join('') + '</tbody></table></div></div>' : '') +
      '<div class="pi-card"><h3>里程碑</h3><div class="pi-ms-tl">' + (msHtml || '<span>暂无里程碑</span>') + '</div></div>' +
      '<div class="pi-card"><h3>任务清单</h3><div class="pi-table-wrap"><table class="pi-table"><thead><tr>' +
      '<th>名称</th><th>状态</th><th>负责人</th><th>开始</th><th>结束</th></tr></thead><tbody>' +
      (taskRowsHtml || '<tr><td colspan="5">暂无任务</td></tr>') + '</tbody></table></div></div>' +
      '<div class="pi-card"><h3>团队与人力</h3><p class="pi-card-sub">单位：人月 · 个人容量 1.0/月 · 展示 ' + esc(d.period || state.period) + '</p>' +
      '<div class="pi-table-wrap"><table class="pi-table"><thead><tr><th>姓名</th><th>所属团队</th><th>角色</th><th>参与方式</th>' +
      '<th>本月投入</th><th>个人合计</th><th>饱和度</th><th>备注</th></tr></thead><tbody>' +
      (teamRows || '<tr><td colspan="8">暂无成员</td></tr>') + '</tbody></table></div>' +
      '<p class="pi-readonly-hint">部门人力登记页为只读汇总；成员投入请在本页编辑模式中维护。</p></div>' +
      '<div class="pi-card"><h3>风险管理</h3><div class="pi-table-wrap"><table class="pi-table"><thead><tr>' +
      '<th>类别</th><th>来源</th><th>说明</th><th>方案</th><th>等级</th><th>跟进人</th>' +
      '<th>登记时间</th><th>解除时间</th><th>状态</th></tr></thead><tbody>' +
      (riskRows || '<tr><td colspan="9">暂无风险</td></tr>') + '</tbody></table></div></div>';

    var btn = document.getElementById('pi-btn-enter-edit');
    if (btn) btn.addEventListener('click', enterEditView);
  }

  function buildEditState() {
    var d = state.data;
    state.snapshot = deepClone(d);
    // 编辑时把所有任务展平（包括里程碑任务和普通任务）
    var allTasks = [];
    function flattenTasks(tasks) {
      tasks.forEach(function (t) {
        var copy = deepClone(t);
        copy.goal_ids = copy.goal_ids || [];
        allTasks.push(copy);
        if (t.children && t.children.length) {
          flattenTasks(t.children);
        }
      });
    }
    flattenTasks(d.tasks || []);
    state.edit = {
      sub_project: deepClone(d.sub_project),
      tasks: allTasks,
      team_members: deepClone(d.team_members || []),
      risks: deepClone(d.risks || []),
      manpower: deepClone(d.manpower || { period: state.period, cells: [] }),
      goals: (d.goals || []).map(function (g) {
        return {
          id: g.id,
          name: g.name,
          metric_unit: g.metric_unit,
          initial_target: g.initial_target,
          mid_term_target: g.mid_term_target,
          current_value: g.current_value,
          direction: g.direction,
          sort_order: g.sort_order,
          overall_status: g.overall_status
        };
      })
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
    clearEditView();
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
      '<div class="pi-card"><h3>基本信息</h3><div class="pi-form-grid pi-form-grid--3col">' +
      '<div class="pi-form-group"><label>项目名称 *</label><input type="text" id="pi-f-name" value="' + esc(sp.name) + '"></div>' +
      '<div class="pi-form-group"><label>计划开始 *</label><input type="date" id="pi-f-ps" value="' + fmtDate(sp.planned_start_date) + '"></div>' +
      '<div class="pi-form-group"><label>实际开始</label><input type="date" id="pi-f-as" value="' + (sp.actual_start_date ? fmtDate(sp.actual_start_date) : '') + '"></div>' +
      '<div class="pi-form-group pi-form-group--compact"><label>项目状态 *</label><select id="pi-f-status">' +
      '<option value="active"' + (sp.status === 'active' ? ' selected' : '') + '>进行中</option>' +
      '<option value="archived"' + (sp.status === 'archived' ? ' selected' : '') + '>已归档</option></select></div>' +
      '<div class="pi-form-group"><label>计划结束 *</label><input type="date" id="pi-f-pe" value="' + fmtDate(sp.planned_end_date) + '"></div>' +
      '<div class="pi-form-group"><label>实际结束</label><input type="date" id="pi-f-ae" value="' + (sp.actual_end_date ? fmtDate(sp.actual_end_date) : '') + '"></div>' +
      '<div class="pi-form-group pi-full"><label>项目描述</label><textarea id="pi-f-desc" rows="4">' + esc(sp.description || '') + '</textarea></div>' +
      '<div class="pi-form-group pi-full"><label>关键目标</label>' +
      '<textarea id="pi-f-goal" rows="5" placeholder="每行可填写一个目标，支持多行登记">' + esc(sp.key_goal || '') + '</textarea></div></div></div>' +
      '<div class="pi-card"><h3>🎯 项目目标</h3><table class="pi-table" id="pi-tbl-goals"><thead><tr><th style="width:32px">#</th><th style="width:180px">目标名称</th><th style="width:80px">单位</th><th style="width:100px">期初目标</th><th style="width:100px">期中调整</th><th style="width:100px">当前值</th><th style="width:80px">方向</th><th style="width:80px">状态</th><th style="width:80px">操作</th></tr></thead><tbody></tbody></table>' +
      '<button type="button" class="pi-btn" id="pi-add-goal">+ 添加目标</button></div>' +
      '<div class="pi-card"><h3>任务</h3><table class="pi-table" id="pi-tbl-tasks"><thead><tr><th></th><th>名称</th><th>状态</th><th>负责人</th><th>开始</th><th>结束</th><th>里程碑</th><th>关联目标</th><th></th></tr></thead><tbody></tbody></table>' +
      '<button type="button" class="pi-btn" id="pi-add-task">+ 添加任务</button></div>' +
      '<div class="pi-card"><h3>团队与人力</h3>' +
      '<div class="pi-toolbar"><label>月份</label><select id="pi-f-month"></select>' +
      '<span id="pi-project-total" class="pi-project-total"></span></div>' +
      '<table class="pi-table" id="pi-tbl-team"><thead><tr><th></th><th>姓名</th><th>所属团队</th><th>角色</th><th>参与方式</th><th>本月投入（人月）</th><th>备注</th><th></th></tr></thead><tbody></tbody></table>' +
      '<button type="button" class="pi-btn" id="pi-add-team">+ 添加成员</button>' +
      '<p class="pi-readonly-hint">在此维护成员投入（人月，0~1）；保存后自动汇总至部门人力登记页（只读）。</p></div>' +
      '<div class="pi-card"><h3>风险管理</h3><table class="pi-table" id="pi-tbl-risks"><thead><tr><th>类别</th><th>来源</th><th>说明</th><th>方案</th><th>等级</th><th>跟进人</th><th>登记时间</th><th>解除时间</th><th>状态</th><th></th></tr></thead><tbody></tbody></table>' +
      '<button type="button" class="pi-btn" id="pi-add-risk">+ 添加风险</button></div>';

    if (bar) bar.classList.remove('pi-hidden');

    bindEditInput('#pi-f-name', function (el) { e.sub_project.name = el.value; });
    bindEditInput('#pi-f-status', function (el) { e.sub_project.status = el.value; });
    bindEditInput('#pi-f-desc', function (el) { e.sub_project.description = el.value; });
    bindEditInput('#pi-f-goal', function (el) { e.sub_project.key_goal = el.value; });
    bindEditInput('#pi-f-ps', function (el) { e.sub_project.planned_start_date = el.value || null; });
    bindEditInput('#pi-f-pe', function (el) { e.sub_project.planned_end_date = el.value || null; });
    bindEditInput('#pi-f-as', function (el) { e.sub_project.actual_start_date = el.value || null; });
    bindEditInput('#pi-f-ae', function (el) { e.sub_project.actual_end_date = el.value || null; });

    renderGoalRows();
    renderTaskRows();
    renderManpowerMonthSelect();
    renderTeamManpowerRows();
    renderRiskRows();

    wireGoalEvents();
    document.getElementById('pi-add-goal').addEventListener('click', function () {
      if (!e.goals) e.goals = [];
      e.goals.push({
        id: null, name: '', metric_unit: '', initial_target: '',
        mid_term_target: null, current_value: null, direction: 'higher_better',
        sort_order: e.goals.length, overall_status: 'not_started'
      });
      markDirty();
      renderGoalRows();
    });
    document.getElementById('pi-add-task').addEventListener('click', function () {
      e.tasks.push({
        id: null, name: '新任务', status: 'pending', assignee: '',
        start_date: state.year + '-06-01', end_date: state.year + '-06-30',
        progress: 0, is_milestone: false, parent_id: null, sort_order: e.tasks.length
      });
      markDirty();
      renderTaskRows();
    });
    document.getElementById('pi-add-team').addEventListener('click', function () {
      var colId = firstColumnId();
      e.team_members.push({
        id: null, name: '', team_column_id: colId, role: '项目负责人',
        participation: '核心成员', remark: '', sort_order: e.team_members.length,
        monthly_allocation: 0
      });
      markDirty();
      renderTeamManpowerRows();
    });
    document.getElementById('pi-add-risk').addEventListener('click', function () {
      e.risks.push({
        id: null, risk_category: '进度', risk_source: '资源', description: '',
        solution: '', level: '中', assignee: '', resolution_date: null, status: 'Open'
      });
      markDirty();
      renderRiskRows();
    });

    initSortable('pi-tbl-goals', 'goals');
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

  // ========== 项目目标 ==========

  var GOAL_DIRECTION_LABELS = {
    higher_better: '越大越好',
    lower_better: '越小越好',
    boolean: '是/否'
  };

  var GOAL_STATUS_MAP = {
    completed: '✅ 完成',
    on_track: '🟢 达标',
    at_risk: '🟡 有风险',
    behind: '🔴 落后',
    not_started: '⏳ 未开始'
  };

  function renderGoalRows() {
    var tbody = document.querySelector('#pi-tbl-goals tbody');
    if (!tbody) return;
    var e = state.edit;
    var goals = e.goals || [];
    tbody.innerHTML = '';
    goals.forEach(function (g, gi) {
      var tr = document.createElement('tr');
      tr.setAttribute('data-idx', gi);
      tr.className = 'pi-goal-row';

      // 序号 + 拖拽
      var td1 = document.createElement('td');
      td1.className = 'pi-drag';
      td1.style.cssText = 'text-align:center;color:var(--text-muted);cursor:grab';
      td1.textContent = '⠿ ' + (gi + 1);
      tr.appendChild(td1);

      // 目标名称
      var td2 = document.createElement('td');
      var inpName = document.createElement('input');
      inpName.type = 'text'; inpName.className = 'pi-input';
      inpName.value = g.name || ''; inpName.setAttribute('data-goal-field', 'name'); inpName.setAttribute('data-gi', gi);
      td2.appendChild(inpName); tr.appendChild(td2);

      // 度量单位
      var td3 = document.createElement('td');
      var inpUnit = document.createElement('input');
      inpUnit.type = 'text'; inpUnit.className = 'pi-input pi-input-sm';
      inpUnit.value = g.metric_unit || ''; inpUnit.setAttribute('data-goal-field', 'metric_unit'); inpUnit.setAttribute('data-gi', gi);
      td3.appendChild(inpUnit); tr.appendChild(td3);

      // 期初目标
      var td4 = document.createElement('td');
      var inpInit = document.createElement('input');
      inpInit.type = 'text'; inpInit.className = 'pi-input';
      inpInit.value = g.initial_target || ''; inpInit.setAttribute('data-goal-field', 'initial_target'); inpInit.setAttribute('data-gi', gi);
      td4.appendChild(inpInit); tr.appendChild(td4);

      // 期中调整
      var td5 = document.createElement('td');
      var inpMid = document.createElement('input');
      inpMid.type = 'text'; inpMid.className = 'pi-input';
      inpMid.value = g.mid_term_target || ''; inpMid.setAttribute('data-goal-field', 'mid_term_target'); inpMid.setAttribute('data-gi', gi);
      td5.appendChild(inpMid); tr.appendChild(td5);

      // 当前值（有关联时只读）
      var td6 = document.createElement('td');
      var inpCv = document.createElement('input');
      inpCv.type = 'text'; inpCv.className = 'pi-input';
      inpCv.value = g.current_value || ''; inpCv.setAttribute('data-goal-field', 'current_value'); inpCv.setAttribute('data-gi', gi);
      if (g.overall_status && g.overall_status !== 'not_started' && goals.some(function (x) { return x.id && (g.id && x.id === g.id); })) {
        // 已保存的目标，有关联时只读
      }
      td6.appendChild(inpCv); tr.appendChild(td6);

      // 方向
      var td7 = document.createElement('td');
      var selDir = document.createElement('select');
      selDir.className = 'pi-select'; selDir.setAttribute('data-goal-field', 'direction'); selDir.setAttribute('data-gi', gi);
      ['higher_better', 'lower_better', 'boolean'].forEach(function (d) {
        var opt = document.createElement('option');
        opt.value = d; opt.textContent = GOAL_DIRECTION_LABELS[d] || d;
        if (g.direction === d) opt.selected = true;
        selDir.appendChild(opt);
      });
      td7.appendChild(selDir); tr.appendChild(td7);

      // 状态（只读）
      var td8 = document.createElement('td');
      td8.className = 'pi-goal-status';
      td8.textContent = GOAL_STATUS_MAP[g.overall_status] || '⏳ 未开始';
      tr.appendChild(td8);

      // 操作列
      var td9 = document.createElement('td');
      td9.style.whiteSpace = 'nowrap';
      var delBtn = document.createElement('button');
      delBtn.type = 'button'; delBtn.className = 'pi-btn pi-btn-danger'; delBtn.setAttribute('data-goal-action', 'delete'); delBtn.setAttribute('data-gi', gi); delBtn.title = '删除';
      delBtn.textContent = '删除'; delBtn.style.cssText = 'font-size:12px;padding:4px 10px';
      td9.appendChild(delBtn);
      tr.appendChild(td9);

      tbody.appendChild(tr);
    });
  }

  function wireGoalEvents() {
    var tbody = document.querySelector('#pi-tbl-goals tbody');
    if (!tbody) return;

    // 输入变更
    tbody.addEventListener('input', function (e) {
      var el = e.target;
      var gi = parseInt(el.getAttribute('data-gi'), 10);
      var field = el.getAttribute('data-goal-field');
      if (isNaN(gi) || !field) return;
      state.edit.goals[gi][field] = el.value;
      markDirty();
    });

    // select 变更
    tbody.addEventListener('change', function (e) {
      var el = e.target;
      var gi = parseInt(el.getAttribute('data-gi'), 10);
      var field = el.getAttribute('data-goal-field');
      if (isNaN(gi) || !field) return;
      state.edit.goals[gi][field] = el.value;
      markDirty();
    });

    // 点击事件（删除）
    tbody.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-goal-action]');
      if (!btn) return;
      var action = btn.getAttribute('data-goal-action');
      var gi = parseInt(btn.getAttribute('data-gi'), 10);
      if (isNaN(gi)) return;

      if (action === 'delete') {
        if (!confirm('确认删除该目标？关联关系将同步清除。')) return;
        state.edit.goals.splice(gi, 1);
      }
      // 重新编号 sort_order
      state.edit.goals.forEach(function (g, i) { g.sort_order = i; });
      markDirty();
      renderGoalRows();
    });
  }

  function renderTaskRows() {
    var tbody = document.querySelector('#pi-tbl-tasks tbody');
    if (!tbody) return;
    var e = state.edit;
    var goals = e.goals || [];
    // 按 parent_id 排序：顶层任务在前，子任务紧跟其后（只展开2级）
    var sortedTasks = [];
    var taskMap = {};
    e.tasks.forEach(function (t, i) { t._idx = i; taskMap[t.id] = t; });
    e.tasks.forEach(function (t) {
      if (!t.parent_id || !taskMap[t.parent_id]) {
        t._depth = 0;
        sortedTasks.push(t);
        // 只展开一层子任务（最多2级）
        if (t.id != null) {
          e.tasks.forEach(function (child) {
            if (child.parent_id === t.id) {
              child._depth = 1;
              sortedTasks.push(child);
            }
          });
        }
      }
    });
    // 没有被 parent 引用的独立任务也加入
    e.tasks.forEach(function (t) {
      if (sortedTasks.indexOf(t) === -1) sortedTasks.push(t);
    });

    // 找到每个任务在 sortedTasks 中上面最近的顶层任务索引
    function findPrevParent(currentIdx) {
      for (var i = currentIdx - 1; i >= 0; i--) {
        if (!sortedTasks[i].parent_id) return sortedTasks[i];
      }
      return null;
    }

    tbody.innerHTML = sortedTasks.map(function (t, sortedIdx) {
      var idx = t._idx;
      var depth = t._depth || 0;
      var indent = depth > 0 ? '<span style="display:inline-block;width:' + (depth * 20) + 'px"></span>└ ' : '';
      // 降级/升级按钮
      var demoteBtn = '';
      if (t.parent_id == null) {
        demoteBtn = '<button type="button" class="pi-btn" data-demote="' + idx + '" style="font-size:12px;padding:4px 10px">降级</button>';
      } else {
        demoteBtn = '<button type="button" class="pi-btn" data-upgrade="' + idx + '" style="font-size:12px;padding:4px 10px">升级</button>';
      }
      return '<tr data-idx="' + idx + '"><td class="pi-drag">⠿</td>' +
        '<td style="display:flex;align-items:center;gap:4px;min-width:0">' + indent + '<input data-f="name" value="' + esc(t.name) + '" style="flex:1;min-width:0"></td>' +
        '<td><select data-f="status">' + TASK_STATUS.map(function (s) {
          return '<option value="' + s + '"' + (t.status === s ? ' selected' : '') + '>' + (TASK_STATUS_LABELS[s] || s) + '</option>';
        }).join('') + '</select></td>' +
        '<td><input data-f="assignee" value="' + esc(t.assignee || '') + '"></td>' +
        '<td><input type="date" data-f="start_date" value="' + fmtDate(t.start_date) + '"></td>' +
        '<td><input type="date" data-f="end_date" value="' + fmtDate(t.end_date) + '"></td>' +
        '<td><button type="button" class="pi-btn' + (t.is_milestone ? ' pi-btn-primary' : '') + '" data-toggle-ms="' + idx + '" style="font-size:11px;padding:2px 8px;white-space:nowrap">' + (t.is_milestone ? '是' : '否') + '</button></td>' +
        '<td><div class="pi-multi-check" data-task-goal="true" data-ti="' + idx + '"></div></td>' +
        '<td style="white-space:nowrap">' + demoteBtn + '<button type="button" class="pi-btn" data-del="task" style="font-size:12px;padding:4px 10px">删除</button></td></tr>';
    }).join('');
    wireRowInputs(tbody, e.tasks);
    // 里程碑切换按钮
    tbody.querySelectorAll('[data-toggle-ms]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var i = parseInt(btn.getAttribute('data-toggle-ms'), 10);
        e.tasks[i].is_milestone = !e.tasks[i].is_milestone;
        markDirty();
        renderTaskRows();
      });
    });
    // 降级按钮
    tbody.querySelectorAll('[data-demote]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var i = parseInt(btn.getAttribute('data-demote'), 10);
        var prevParent = findPrevParent(sortedTasks.indexOf(e.tasks[i]));
        if (!prevParent) {
          alert('已是第一个任务，上方没有可归属的父任务');
          return;
        }
        if (prevParent.id == null) {
          alert('上方任务尚未保存，请先保存后再降级');
          return;
        }
        e.tasks[i].parent_id = prevParent.id;
        markDirty();
        renderTaskRows();
      });
    });
    // 升级按钮
    tbody.querySelectorAll('[data-upgrade]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var i = parseInt(btn.getAttribute('data-upgrade'), 10);
        e.tasks[i].parent_id = null;
        markDirty();
        renderTaskRows();
      });
    });
    // 关联目标多选（自定义 checkbox 下拉）
    tbody.querySelectorAll('.pi-multi-check[data-task-goal]').forEach(function (container) {
      var ti = parseInt(container.getAttribute('data-ti'), 10);
      createMultiCheckDropdown(container, goals, e.tasks[ti].goal_ids || [], function (ids) {
        e.tasks[ti].goal_ids = ids;
        markDirty();
      });
    });
    tbody.querySelectorAll('[data-del="task"]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var idx = parseInt(btn.closest('tr').getAttribute('data-idx'), 10);
        var task = e.tasks[idx];
        // 删除该任务及其所有子任务
        var idsToDelete = {};
        idsToDelete[idx] = true;
        if (task && task.id) {
          // 找到所有 parent_id 指向该任务的行
          for (var j = e.tasks.length - 1; j >= 0; j--) {
            if (j !== idx && e.tasks[j].parent_id === task.id) {
              idsToDelete[j] = true;
            }
          }
        }
        // 从后往前删，避免索引偏移
        var sorted = Object.keys(idsToDelete).map(Number).sort(function (a, b) { return b - a; });
        sorted.forEach(function (i) { e.tasks.splice(i, 1); });
        markDirty();
        renderTaskRows();
      });
    });
  }

  function teamGroupLabel(columnId) {
    var groups = (state.edit.manpower && state.edit.manpower.dept_groups) || [];
    for (var i = 0; i < groups.length; i++) {
      var g = groups[i];
      var cols = g.columns || [];
      for (var j = 0; j < cols.length; j++) {
        if (cols[j].id === columnId) return g.name + ' / ' + cols[j].name;
      }
    }
    return '未分配团队';
  }

  function teamColumnSubtotal(members, columnId) {
    return members.filter(function (m) { return m.team_column_id === columnId; })
      .reduce(function (sum, m) { return sum + (Number(m.monthly_allocation) || 0); }, 0);
  }

  function updateProjectTotalLabel() {
    var el = document.getElementById('pi-project-total');
    if (!el || !state.edit) return;
    el.textContent = '项目本月合计：' + fmtManMonth(projectMonthlyTotal(state.edit.team_members)) + ' 人月';
  }

  function renderTeamManpowerRows() {
    var tbody = document.querySelector('#pi-tbl-team tbody');
    if (!tbody || !state.edit) return;
    var e = state.edit;
    var members = e.team_members || [];
    var seenCols = {};
    var html = '';
    members.forEach(function (t, idx) {
      if (!seenCols[t.team_column_id]) {
        seenCols[t.team_column_id] = true;
        var sub = teamColumnSubtotal(members, t.team_column_id);
        html += '<tr class="pi-group-row"><td colspan="8">' + esc(teamGroupLabel(t.team_column_id)) +
          ' · 团队小计 ' + fmtManMonth(sub) + ' 人月</td></tr>';
      }
      html += '<tr data-idx="' + idx + '"><td class="pi-drag">⠿</td><td><input data-f="name" value="' + esc(t.name) + '"></td>' +
        '<td><select data-f="team_column_id">' + columnOptions(t.team_column_id) + '</select></td>' +
        '<td><input data-f="role" value="' + esc(t.role) + '"></td>' +
        '<td><select data-f="participation">' + optHtml(PARTICIPATION, t.participation) + '</select></td>' +
        '<td><input type="number" step="0.1" min="0" max="1" data-f="monthly_allocation" value="' +
        fmtManMonth(t.monthly_allocation != null ? t.monthly_allocation : 0) + '"></td>' +
        '<td><input data-f="remark" value="' + esc(t.remark || '') + '"></td>' +
        '<td><button type="button" class="pi-btn" data-del="team">删</button></td></tr>';
    });
    tbody.innerHTML = html || '<tr><td colspan="8">暂无成员，请添加</td></tr>';
    wireRowInputs(tbody, e.team_members, function (el, row, field) {
      if (field === 'team_column_id') {
        row.team_column_id = parseInt(el.value, 10);
        renderTeamManpowerRows();
      }
      if (field === 'monthly_allocation') {
        var v = parseFloat(el.value);
        row.monthly_allocation = isNaN(v) ? 0 : Math.min(1, Math.max(0, v));
        el.value = fmtManMonth(row.monthly_allocation);
        updateProjectTotalLabel();
      }
    });
    tbody.querySelectorAll('[data-del="team"]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var idx = parseInt(btn.closest('tr').getAttribute('data-idx'), 10);
        e.team_members.splice(idx, 1);
        markDirty();
        renderTeamManpowerRows();
      });
    });
    updateProjectTotalLabel();
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
          state.edit.team_members = deepClone(data.team_members || []);
          renderTeamManpowerRows();
        });
    };
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
      if (el.tagName !== 'SELECT') el.addEventListener('input', handler);
    });
  }

  function initSortable(tableId, key) {
    if (!global.Sortable) return;
    var tbody = document.querySelector('#' + tableId + ' tbody');
    if (!tbody) return;
    var s = global.Sortable.create(tbody, {
      handle: '.pi-drag',
      draggable: 'tr[data-idx]',
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
        if (key === 'goals') renderGoalRows();
        if (key === 'tasks') renderTaskRows();
        if (key === 'team_members') renderTeamManpowerRows();
      }
    });
    state.sortables.push(s);
  }

  // 将快照的嵌套任务结构展平，用于 deletedIds 比较
  function flattenTasksForSnapshot(tasks) {
    var result = [];
    function walk(list) {
      (list || []).forEach(function (t) {
        result.push(t);
        if (t.children && t.children.length) walk(t.children);
      });
    }
    walk(tasks);
    return result;
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
      tasks: e.tasks.map(function (t) {
        return {
          id: t.id, name: t.name, status: t.status, assignee: t.assignee || null,
          start_date: t.start_date, end_date: t.end_date, progress: t.progress || 0,
          is_milestone: !!t.is_milestone, parent_id: t.parent_id || null,
          sort_order: t.sort_order, goal_ids: t.goal_ids || []
        };
      }),
      deleted_task_ids: deletedIds(flattenTasksForSnapshot(snap.tasks || []), e.tasks),
      team_members: e.team_members.map(function (t) {
        return {
          id: t.id, name: t.name, team_column_id: t.team_column_id, role: t.role,
          participation: t.participation, remark: t.remark || null, sort_order: t.sort_order,
          monthly_allocation: fmtManMonth(t.monthly_allocation != null ? t.monthly_allocation : 0)
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
        period: e.manpower.period || state.period
      },
      goals: (e.goals || []).map(function (g) {
        return {
          id: g.id,
          name: g.name,
          metric_unit: g.metric_unit || null,
          initial_target: g.initial_target,
          mid_term_target: g.mid_term_target || null,
          current_value: g.current_value || null,
          direction: g.direction,
          sort_order: g.sort_order
        };
      }),
      deleted_goal_ids: deletedIds(snap.goals || [], e.goals || [])
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
    var badAlloc = (state.edit.team_members || []).find(function (m) {
      var v = Number(m.monthly_allocation);
      return isNaN(v) || v < 0 || v > 1;
    });
    if (badAlloc) {
      alert('成员投入须为 0~1 人月');
      return;
    }
    var goals = state.edit.goals || [];
    for (var i = 0; i < goals.length; i++) {
      if (!goals[i].name || !goals[i].name.trim()) {
        alert('目标 #' + (i + 1) + ' 的名称不能为空');
        return;
      }
      if (!goals[i].initial_target || !goals[i].initial_target.trim()) {
        alert('目标 "' + goals[i].name + '" 的期初目标不能为空');
        return;
      }
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
      clearEditView();
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
    updateAdminTools();
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
    updateEditLockUi();
  }

  // ========== 自定义 checkbox 下拉多选组件 ==========
  function createMultiCheckDropdown(container, goals, selectedIds, onChange) {
    // 容器
    container.className = 'pi-multi-check';
    container.innerHTML = '';

    // 触发器：显示已选目标名称
    var trigger = document.createElement('div');
    trigger.className = 'pi-multi-check-trigger';
    trigger.tabIndex = 0;
    trigger.textContent = renderSelectedText(goals, selectedIds);
    container.appendChild(trigger);

    // 下拉面板
    var panel = document.createElement('div');
    panel.className = 'pi-multi-check-panel';
    panel.style.display = 'none';
    container.appendChild(panel);

    // 构建选项列表
    renderPanel(panel, goals, selectedIds, onChange);

    // 展开/收起
    trigger.addEventListener('click', function (e) {
      e.stopPropagation();
      togglePanel(panel);
    });

    // 点击外部关闭
    document.addEventListener('click', function closePanel(e) {
      if (!container.contains(e.target)) {
        panel.style.display = 'none';
      }
    });
  }

  function renderSelectedText(goals, selectedIds) {
    if (!selectedIds.length) return '—';
    var names = [];
    selectedIds.forEach(function (id) {
      var g = findGoal(goals, id);
      if (g) names.push(g.name);
    });
    return names.length ? names.join('、') : '—';
  }

  function findGoal(goals, id) {
    for (var i = 0; i < goals.length; i++) {
      if (goals[i].id === id) return goals[i];
    }
    return null;
  }

  function renderPanel(panel, goals, selectedIds, onChange) {
    panel.innerHTML = '';
    goals.forEach(function (g) {
      if (!g.id) return; // 跳过未保存的新目标
      var label = document.createElement('label');
      label.className = 'pi-multi-check-item';
      var cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.value = g.id;
      cb.checked = selectedIds.indexOf(g.id) !== -1;
      cb.addEventListener('change', function () {
        if (cb.checked) {
          selectedIds.push(g.id);
        } else {
          var idx = selectedIds.indexOf(g.id);
          if (idx !== -1) selectedIds.splice(idx, 1);
        }
        // 更新触发器文字
        var container = panel.parentElement;
        var trigger = container.querySelector('.pi-multi-check-trigger');
        if (trigger) trigger.textContent = renderSelectedText(goals, selectedIds);
        if (onChange) onChange(selectedIds.slice());
      });
      var span = document.createElement('span');
      span.textContent = g.name;
      label.appendChild(cb);
      label.appendChild(span);
      panel.appendChild(label);
    });
    if (!goals.some(function (g) { return !!g.id; })) {
      panel.innerHTML = '<div class="pi-multi-check-empty">暂无已保存的目标</div>';
    }
  }

  function togglePanel(panel) {
    // 关闭其他所有面板
    document.querySelectorAll('.pi-multi-check-panel').forEach(function (p) {
      if (p !== panel) p.style.display = 'none';
    });
    panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
  }

  function wireControls() {
    if (wireControls._wired) return;
    wireControls._wired = true;
    var addP = document.getElementById('pi-btn-add-program');
    var addS = document.getElementById('pi-btn-add-sub-program');
    var addJ = document.getElementById('pi-btn-add-sub-project');
    var ren = document.getElementById('pi-btn-rename-node');
    var del = document.getElementById('pi-btn-delete-node');
    if (addP) addP.addEventListener('click', handleAddProgram);
    if (addS) addS.addEventListener('click', handleAddSubProgram);
    if (addJ) addJ.addEventListener('click', handleAddSubProject);
    if (ren) ren.addEventListener('click', handleRenameNode);
    if (del) del.addEventListener('click', handleDeleteNode);
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
      if (isEditing()) {
        if (revert) revert();
        return;
      }
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
        state.subProjectId = parseInt(selJ.value, 10);
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
    if (init._done) return;
    init._done = true;
    syncYearFromGlobal();
    wireControls();
    updateAdminTools();
    updateEditLockUi();
    global.addEventListener('beforeunload', function (e) {
      if (state.dirty) {
        e.preventDefault();
        e.returnValue = '';
      }
    });
  }

  function onTabShow() {
    syncYearFromGlobal();
    loadTree().then(loadProjectInfo);
  }

  function onYearChanged(y) {
    clearEditView();
    state.year = y;
    state.period = defaultPeriod(y);
    loadTree().then(loadProjectInfo);
  }

  global.ProjectInfoModule = {
    init: init,
    onTabShow: onTabShow,
    onYearChanged: onYearChanged,
    isEditing: isEditing,
    hasDirtyChanges: function () { return !!state.dirty; },
    refreshAdminTools: function () {
      updateAdminTools();
      updateEditLockUi();
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})(window);
