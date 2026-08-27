export async function request(path, options = {}) {
  if (typeof fetch !== 'function') throw new Error('浏览器请求能力不可用')
  const response = await fetch(path, {
    credentials: 'include',
    headers: { Accept: 'application/json', ...options.headers },
    ...options,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const error = new Error(body.detail || `请求失败：${response.status}`)
    error.status = response.status
    throw error
  }
  return response.status === 204 ? null : response.json()
}

export const getSession = () => request('/api/auth/me')
export const getBoundRepositories = () => request('/api/repositories')
export const getAvailableRepositories = () => request('/api/repositories/available')
export const bindRepository = (fullName) => request('/api/repositories', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ full_name: fullName }),
})
export const syncRepository = (repositoryId) => request(`/api/repositories/${repositoryId}/sync`, { method: 'POST' })
export const getPullRequests = (repositoryId) => request(`/api/repositories/${repositoryId}/pull-requests`)
export const getFailedWorkflows = (repositoryId) => request(`/api/repositories/${repositoryId}/ci/failures`)
export const getReleases = (repositoryId) => request(`/api/repositories/${repositoryId}/releases`)
