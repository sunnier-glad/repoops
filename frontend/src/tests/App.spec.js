import { flushPromises, mount } from '@vue/test-utils'
import { vi } from 'vitest'

import App from '../App.vue'

describe('RepoOps app shell', () => {
  it('renders the product name and purpose', () => {
    const wrapper = mount(App)

    expect(wrapper.get('h1').text()).toBe('RepoOps · 发布质量工作台')
    expect(wrapper.text()).toContain('GitHub 项目协作与发布质量平台')
    expect(wrapper.text()).toContain('CI 失败')
    expect(wrapper.text()).toContain('PR 协作')
    expect(wrapper.text()).toContain('Release 质量')
    expect(wrapper.get('a[href="/api/auth/github"]').text()).toContain('GitHub 登录')
  })

  it('loads available repositories and binds the selected repository', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ id: 1, github_login: 'sunnier-glad' }) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [{ full_name: 'octocat/demo', name: 'demo', private: false }] })
      .mockResolvedValueOnce({ ok: true, status: 201, json: async () => ({ id: 7, full_name: 'octocat/demo', webhook_configured: true }) })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).toContain('选择仓库')
    expect(wrapper.text()).toContain('octocat/demo')
    await wrapper.get('select[aria-label="选择 GitHub 仓库"]').setValue('octocat/demo')
    await wrapper.get('[data-testid="bind-repository"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('仓库已绑定')
    expect(fetchMock).toHaveBeenLastCalledWith('/api/repositories', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ full_name: 'octocat/demo' }),
    }))
  })
})
