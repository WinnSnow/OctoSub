export function getApiErrorMessage(error, fallback = '请求失败') {
  return error?.response?.data?.detail || error?.message || fallback;
}
