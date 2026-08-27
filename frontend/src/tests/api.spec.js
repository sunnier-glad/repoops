import { afterEach, describe, expect, it, vi } from 'vitest'

import { bindRepository, getAvailableRepositories, request } from '../api/client'

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
})
