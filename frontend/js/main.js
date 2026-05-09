/**
 * 应用入口：主逻辑 + PM 操作指引
 * Chart.js 仍由 index.html 以 UMD 全局形式加载，供 main-app 使用。
 */
import './main-app.js';
import { initGuide } from './ui/guide.js';

initGuide();
