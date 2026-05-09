/**
 * 项目集 / 子项目集 / 子项目 树访问与阶段按月切片（无 DOM、不依赖 S）
 */
import { PHASE_FIELD_KEYS } from '../state.js';

export function ymKey(y, m) {
  return String(y) + '-' + String(m).padStart(2, '0');
}

export function getProgramProjectSets(set) {
  return (set && Array.isArray(set.projectSets)) ? set.projectSets : [];
}

export function getSubProjects(projectSet) {
  return (projectSet && Array.isArray(projectSet.subProjects)) ? projectSet.subProjects : [];
}

export function countSubProjectsInSet(set) {
  var n = 0;
  getProgramProjectSets(set).forEach(function (ps) {
    n += getSubProjects(ps).length;
  });
  return n;
}

export function newPhaseMonthRow() {
  return { goal: '', deliver: '', highlight: '', weakness: '', nextNote: '' };
}

export function ensurePhaseByMonth(p) {
  if (!p.phaseByMonth || typeof p.phaseByMonth !== 'object') p.phaseByMonth = {};
}

export function getPhaseMonthSlice(p, y, m) {
  ensurePhaseByMonth(p);
  var k = ymKey(y, m);
  if (!p.phaseByMonth[k] || typeof p.phaseByMonth[k] !== 'object') {
    p.phaseByMonth[k] = newPhaseMonthRow();
  }
  var row = p.phaseByMonth[k];
  PHASE_FIELD_KEYS.forEach(function (key) {
    if (row[key] == null) row[key] = '';
    else row[key] = String(row[key]);
  });
  return row;
}
