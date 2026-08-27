import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  bindRepository,
  getAvailableRepositories,
  getFailedWorkflows,
  getPullRequests,
  getReleases,
  getBoundRepositories,
  request,
  syncRepository,
} from '../api/client'

describe('api client', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('sends cookies and parses available repositories', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [{ full_name: 'octocat/demo' }],
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(getAvailableRepositories()).resolves.toEqual([{ full_name: 'octocat/demo' }])
    expect(fetchMock).toHaveBeenCalledWith('/api/repositories/available', expect.objectContaining({ credentials: 'include' }))
  })

  it('exposes the API detail and status for non-2xx responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: '无权访问' }),
    }))

    await expect(request('/api/private')).rejects.toMatchObject({ message: '无权访问', status: 403 })
  })

  it('binds a selected repository with a JSON request', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ id: 1, full_name: 'octocat/demo' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(bindRepository('octocat/demo')).resolves.toEqual({ id: 1, full_name: 'octocat/demo' })
    expect(fetchMock).toHaveBeenCalledWith('/api/repositories', expect.objectContaining({
      method: 'POST',
      credentials: 'include',
      headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ full_name: 'octocat/demo' }),
    }))
  })

  it('loads and syncs repository quality data', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ pull_requests: 1 }) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [{ number: 3 }] })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [{ workflow_name: 'CI' }] })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [{ tag_name: 'v1.0.0' }] })
    vi.stubGlobal('fetch', fetchMock)

    await expect(syncRepository(1)).resolves.toEqual({ pull_requests: 1 })
    await expect(getPullRequests(1)).resolves.toEqual([{ number: 3 }])
    await expect(getFailedWorkflows(1)).resolves.toEqual([{ workflow_name: 'CI' }])
    await expect(getReleases(1)).resolves.toEqual([{ tag_name: 'v1.0.0' }])

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/repositories/1/sync', expect.objectContaining({ method: 'POST' }))
  })

  it('loads repositories already bound to the current account', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [{ id: 1, full_name: 'octocat/demo' }],
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(getBoundRepositories()).resolves.toEqual([{ id: 1, full_name: 'octocat/demo' }])
    expect(fetchMock).toHaveBeenCalledWith('/api/repositories', expect.objectContaining({ credentials: 'include' }))
  })
})
