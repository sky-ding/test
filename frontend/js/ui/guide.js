/** PM 操作指引：数据与弹层（原 index.html 第二段脚本） */

export const GUIDE_BLOCK_KEYS = ['design', 'techDesign', 'develop', 'operate'];

export let guideData = {
  design: [
    { id: 1, title: '完成需求文档撰写', body: '', link: '' },
    { id: 2, title: '绘制原型并评审', body: '', link: '' }
  ],
  techDesign: [
    { id: 1, title: '完成技术方案与接口设计', body: '', link: '' },
    { id: 2, title: '组织技术评审并落实结论', body: '', link: '' }
  ],
  develop: [
    { id: 1, title: '代码开发并提交MR', body: '', link: '' },
    { id: 2, title: '完成自测及代码Review', body: '', link: '' }
  ],
  operate: [
    { id: 1, title: '上线通知相关干系人', body: '', link: '' },
    { id: 2, title: '监控数据并反馈问题', body: '', link: '' }
  ]
};

export function saveGuideData() {
  if (window.localStorage) {
    localStorage.setItem('pmGuideData', JSON.stringify(guideData));
  }
}

export function loadGuideData() {
  if (window.localStorage) {
    var s = localStorage.getItem('pmGuideData');
    if (s) guideData = JSON.parse(s);
  }
}

function normalizeGuideItem(it) {
  var tit = it.title != null ? String(it.title).trim() : '';
  if (!tit && it.text != null) tit = String(it.text).trim();
  if (!tit) tit = '（未命名）';
  return {
    id: it.id,
    title: tit,
    body: it.body != null ? String(it.body) : '',
    link: it.link != null ? String(it.link).trim() : ''
  };
}

function normalizeGuideData() {
  GUIDE_BLOCK_KEYS.forEach(function (k) {
    var arr = guideData[k];
    if (!Array.isArray(arr)) {
      guideData[k] = [];
      return;
    }
    guideData[k] = arr.map(normalizeGuideItem);
  });
}

export function isSafeHttpUrl(s) {
  if (!s || typeof s !== 'string') return false;
  try {
    var u = new URL(s.trim());
    return u.protocol === 'http:' || u.protocol === 'https:';
  } catch (err) {
    return false;
  }
}

let guideItemModalCtx = null;

export function openGuideItemModal(blockKey, itemId) {
  if (typeof window.pmIsAdmin === 'function' && !window.pmIsAdmin()) {
    alert('当前为普通用户身份，仅可查看。请在「设置 → 权限管理」中切换为管理员后再操作。');
    return;
  }
  guideItemModalCtx = { blockKey: blockKey, itemId: itemId };
  var mask = document.getElementById('guide-item-mask');
  var heading = document.getElementById('guide-item-modal-heading');
  var t = document.getElementById('guide-item-title');
  var b = document.getElementById('guide-item-body');
  var l = document.getElementById('guide-item-link');
  if (itemId == null) {
    heading.textContent = '添加指引';
    t.value = '';
    b.value = '';
    l.value = '';
  } else {
    var arr = guideData[blockKey] || [];
    var item = arr.find(function (x) { return x.id === itemId; });
    if (!item) {
      guideItemModalCtx = null;
      return;
    }
    heading.textContent = '编辑指引';
    t.value = item.title || '';
    b.value = item.body || '';
    l.value = item.link || '';
  }
  mask.classList.add('active');
  mask.setAttribute('aria-hidden', 'false');
  requestAnimationFrame(function () {
    t.focus();
  });
}

function closeGuideItemModal() {
  guideItemModalCtx = null;
  var mask = document.getElementById('guide-item-mask');
  mask.classList.remove('active');
  mask.setAttribute('aria-hidden', 'true');
}

function saveGuideItemModal() {
  if (typeof window.pmIsAdmin === 'function' && !window.pmIsAdmin()) {
    return;
  }
  var ctx = guideItemModalCtx;
  if (!ctx) return;
  var t = document.getElementById('guide-item-title');
  var b = document.getElementById('guide-item-body');
  var l = document.getElementById('guide-item-link');
  var title = t.value.trim();
  if (!title) {
    alert('请填写标题');
    t.focus();
    return;
  }
  var body = b.value.trim();
  var link = l.value.trim();
  if (link && !isSafeHttpUrl(link)) {
    alert('链接需为以 http:// 或 https:// 开头的完整地址');
    l.focus();
    return;
  }
  var arr = guideData[ctx.blockKey];
  if (!Array.isArray(arr)) arr = guideData[ctx.blockKey] = [];
  if (ctx.itemId == null) {
    var nextId = arr.length ? Math.max.apply(null, arr.map(function (x) { return x.id; })) + 1 : 1;
    arr.push({ id: nextId, title: title, body: body, link: link });
  } else {
    var obj = arr.find(function (x) { return x.id === ctx.itemId; });
    if (obj) {
      obj.title = title;
      obj.body = body;
      obj.link = link;
    }
  }
  saveGuideData();
  closeGuideItemModal();
  renderGuideList(ctx.blockKey);
}

function openGuideDetailModal(item) {
  var mask = document.getElementById('guide-detail-mask');
  var titleEl = document.getElementById('guide-detail-title');
  var bodyEl = document.getElementById('guide-detail-body');
  var wrap = document.getElementById('guide-detail-link-wrap');
  var a = document.getElementById('guide-detail-link');
  titleEl.textContent = item.title || '';
  var bodyText = item.body ? String(item.body) : '';
  if (item.link && !isSafeHttpUrl(item.link)) {
    bodyText = bodyText ? bodyText + '\n\n链接：' + item.link : '链接：' + item.link;
  }
  bodyEl.textContent = bodyText || '暂无详细说明。';
  wrap.hidden = true;
  a.removeAttribute('href');
  mask.classList.add('active');
  mask.setAttribute('aria-hidden', 'false');
}

function closeGuideDetailModal() {
  var mask = document.getElementById('guide-detail-mask');
  mask.classList.remove('active');
  mask.setAttribute('aria-hidden', 'true');
}

function onGuideTitleClick(item) {
  if (isSafeHttpUrl(item.link)) {
    window.open(item.link.trim(), '_blank', 'noopener');
    return;
  }
  openGuideDetailModal(item);
}

function setupGuideModals() {
  var itemMask = document.getElementById('guide-item-mask');
  var detailMask = document.getElementById('guide-detail-mask');
  document.getElementById('guide-item-save').addEventListener('click', saveGuideItemModal);
  document.getElementById('guide-item-cancel').addEventListener('click', closeGuideItemModal);
  document.getElementById('guide-detail-close').addEventListener('click', closeGuideDetailModal);
  itemMask.addEventListener('click', function (e) {
    if (e.target === itemMask) closeGuideItemModal();
  });
  detailMask.addEventListener('click', function (e) {
    if (e.target === detailMask) closeGuideDetailModal();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    if (itemMask.classList.contains('active')) {
      e.preventDefault();
      closeGuideItemModal();
    } else if (detailMask.classList.contains('active')) {
      e.preventDefault();
      closeGuideDetailModal();
    }
  });
}

export function renderGuideMenu() {
  var p = document.getElementById('panel-guide');
  if (!p) return;
  var admin = typeof window.pmIsAdmin === 'function' && window.pmIsAdmin();
  var blocks = [
    { key: 'design', name: '产品设计' },
    { key: 'techDesign', name: '技术设计' },
    { key: 'develop', name: '开发 + 测试' },
    { key: 'operate', name: '运营' }
  ];
  let html = `
    <div style="padding:2em 1.5em 2em 2em;max-width:780px;">
      <div style="display: flex; gap: 2em; flex-wrap:wrap;">
  `;
  blocks.forEach(block => {
    html += `
      <div style="min-width:220px;flex:1 1 260px;background:var(--accent-soft);padding:1.1em 1em 2em 1.1em;margin-bottom:1.5em;border-radius:var(--radius-sm);">
        <div style="font-weight:bold;font-size:1.07em;margin-bottom:1em;letter-spacing:.02em;">${block.name}</div>
        <ul id="guide-list-${block.key}" style="list-style:none;padding:0;margin:0 0 1em 0;"></ul>
        ${admin ? `<button type="button" class="guide-btn-open-add" data-guide-block="${block.key}">+ 添加指引</button>` : ''}
      </div>
    `;
  });
  html += `
      </div>
      <p style="color:var(--text-muted);margin-top:2em;font-size:14px;">
        如需更多帮助请联系基础平台PMO。
      </p>
    </div>
    <style>
      .guide-btn-edit,.guide-btn-del {
        background: none; border: none; color: var(--accent); cursor: pointer; font-size: 15px; margin-left: 3px; padding:2px 4px;border-radius:3px; flex-shrink:0;
      }
      .guide-btn-del { color: var(--danger);}
      .guide-btn-edit:hover { background: #eee; }
      .guide-btn-del:hover { background: var(--danger-soft);}
    </style>
  `;
  p.innerHTML = html;

  blocks.forEach(block => renderGuideList(block.key));
  if (admin) {
    p.querySelectorAll('.guide-btn-open-add').forEach(function (btn) {
      btn.onclick = function () {
        var key = btn.getAttribute('data-guide-block');
        if (key) openGuideItemModal(key, null);
      };
    });
  }
}

function renderGuideList(blockKey) {
  var ul = document.getElementById('guide-list-' + blockKey);
  if (!ul) return;
  var admin = typeof window.pmIsAdmin === 'function' && window.pmIsAdmin();
  var arr = guideData[blockKey] || [];
  ul.innerHTML = '';
  arr.forEach(function (item) {
    var li = document.createElement('li');
    li.style.display = 'flex';
    li.style.alignItems = 'center';
    li.style.gap = '8px';
    li.style.padding = '0 0 8px 0';
    li.setAttribute('data-id', item.id);

    var titleBtn = document.createElement('button');
    titleBtn.type = 'button';
    titleBtn.className = 'guide-title-link';
    titleBtn.setAttribute('title', isSafeHttpUrl(item.link) ? '打开链接（新标签页）' : '查看指引说明');
    titleBtn.textContent = item.title || '（未命名）';
    titleBtn.addEventListener('click', function () {
      onGuideTitleClick(item);
    });

    li.appendChild(titleBtn);
    if (admin) {
      var editBtn = document.createElement('button');
      editBtn.type = 'button';
      editBtn.className = 'guide-btn-edit';
      editBtn.title = '编辑';
      editBtn.textContent = '编辑';
      editBtn.addEventListener('click', function () {
        openGuideItemModal(blockKey, item.id);
      });

      var delBtn = document.createElement('button');
      delBtn.type = 'button';
      delBtn.className = 'guide-btn-del';
      delBtn.title = '删除';
      delBtn.textContent = '删除';
      delBtn.addEventListener('click', function () {
        if (confirm('确认要删除该指引项？')) {
          var list = guideData[blockKey];
          var idx = list.findIndex(function (x) { return x.id === item.id; });
          if (idx >= 0) list.splice(idx, 1);
          saveGuideData();
          renderGuideList(blockKey);
        }
      });
      li.appendChild(editBtn);
      li.appendChild(delBtn);
    }
    ul.appendChild(li);
  });
}

/** 挂载指引：localStorage、规范化、弹层、全局 __renderGuideMenu */
export function initGuide() {
  loadGuideData();

  if (!Array.isArray(guideData.techDesign)) {
    guideData.techDesign = [
      { id: 1, title: '完成技术方案与接口设计', body: '', link: '' },
      { id: 2, title: '组织技术评审并落实结论', body: '', link: '' }
    ];
    saveGuideData();
  }

  normalizeGuideData();
  try {
    var serialized = JSON.stringify(guideData);
    if (window.localStorage && localStorage.getItem('pmGuideData') !== serialized) {
      saveGuideData();
    }
  } catch (err) {
    saveGuideData();
  }

  setupGuideModals();
  window.__renderGuideMenu = renderGuideMenu;
}
