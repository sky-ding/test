/** 可变应用状态（原 index.html 顶层 let），各模块 import { S } 使用同一引用 */

export function defaultDeptGroups() {
  return [
    { name: '技术部', depts: ['前端', '后端'] },
    { name: '市场部', depts: ['销售', '策划'] }
  ];
}

export function createDefaultData() {
  return [
    {
      name: '项目集A',
      projectSets: [
        {
          name: '子项目集A-1',
          subProjects: [
            { name: '子项目A-1', manpower: [2, 3, 0, 1] },
            { name: '子项目A-2', manpower: [1, 0, 0, 1] }
          ]
        }
      ]
    },
    {
      name: '项目集B',
      projectSets: [
        {
          name: '子项目集B-1',
          subProjects: [{ name: '子项目B-1', manpower: [0, 2, 3, 0] }]
        }
      ]
    }
  ];
}

export function createDefaultPhaseData() {
  return [
    {
      name: '项目集A',
      projectSets: [
        {
          name: '子项目集A-1',
          subProjects: [
            { name: '子项目A-1', phaseByMonth: {} },
            { name: '子项目A-2', phaseByMonth: {} }
          ]
        }
      ]
    },
    {
      name: '项目集B',
      projectSets: [
        {
          name: '子项目集B-1',
          subProjects: [{ name: '子项目B-1', phaseByMonth: {} }]
        }
      ]
    }
  ];
}

export const QUARTER_MONTH_LABELS = ['一季度', '二季度', '三季度', '四季度'];
export const QUARTER_MONTHS = [[1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12]];

export const PHASE_FIELD_KEYS = ['goal', 'deliver', 'highlight', 'weakness', 'nextNote'];
export const PHASE_FIELD_LABELS = {
  goal: '阶段交付目标',
  deliver: '实际交付评估',
  highlight: '执行过程分析',
  weakness: '问题分析',
  nextNote: '改进计划'
};

export const STORAGE_KEY_MANPOWER = 'PM-tool-manpower-v1';
export const STORAGE_KEY_REGISTER_COLS = 'PM-tool-register-colwidths-v1';
export const STORAGE_KEY_RISK = 'PM-tool-risk-v1';
export const STORAGE_KEY_PHASE = 'PM-tool-phase-v1';
export const STORAGE_KEY_LEGACY = 'PM-tool-data-v1';
export const STORAGE_KEY_APP_SETTINGS = 'PM-tool-app-settings-v1';

const now = new Date();
export const S = {
  data: createDefaultData(),
  phaseData: createDefaultPhaseData(),
  deptGroups: defaultDeptGroups(),
  manpowerSubView: 'month',
  manpowerSelYear: now.getFullYear(),
  manpowerSelMonth: now.getMonth() + 1,
  manpowerSelQuarter: Math.floor(now.getMonth() / 3),
  phaseSelYear: now.getFullYear(),
  phaseSelMonth: now.getMonth() + 1,
  manpowerAnalysisCharts: [],
  registerColWidths: [],
  registerColResizeDrag: null,
  delCtx: null,
  modalFocusReturn: null,
  riskRows: [],
  riskSortState: { key: null, dir: 'asc' },
  appUserRole: 'viewer',
  panelEditMode: { manpower: false, phase: false, risk: false },
  riskAnalysisCharts: [],
  lastRiskAnalysisStats: null,
  riskAnalysisSortMode: 'count'
};
