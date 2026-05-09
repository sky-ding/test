/** API 根地址：可被 window.PM_API_BASE 覆盖（与 login 页一致） */
export function resolveApiBase() {
  if (typeof window.PM_API_BASE === 'string' && window.PM_API_BASE) {
    return window.PM_API_BASE;
  }
  if (!window.location || !/^https?:\/\//.test(window.location.origin)) {
    return 'http://127.0.0.1:8001';
  }
  var p = Number(window.location.port || 0);
  if (p === 3000 || p === 5500 || p === 8080 || p === 5173) {
    return 'http://127.0.0.1:8001';
  }
  return window.location.origin;
}
