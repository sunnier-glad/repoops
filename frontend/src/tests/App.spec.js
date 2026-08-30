import { flushPromises, mount } from '@vue/test-utils'
import { vi } from 'vitest'

import App from '../App.vue'

const qualityGate = {
  status: 'warning',
  summary: '存在发布前需要人工确认的风险',
  checks: [
    { key: 'default_branch_ci', status: 'warning', title: '主分支 CI', detail: '尚未同步到 main 分支的 CI 记录', url: null },
    { key: 'open_pull_requests', status: 'pass', title: '待处理 PR', detail: '没有待处理的开放 PR', url: null },
    { key: 'release_notes', status: 'warning', title: '发布说明', detail: '尚无 Release 记录，首次发布前需要准备发布说明', url: null },
  ],
}

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
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [{ full_name: 'octocat/demo', name: 'demo', private: false }] })
      .mockResolvedValueOnce({ ok: true, status: 201, json: async () => ({ id: 7, full_name: 'octocat/demo', webhook_configured: true }) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ pull_requests: 0, failed_workflows: 0, releases: 0 }) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => qualityGate })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).toContain('选择仓库')
    expect(wrapper.text()).toContain('octocat/demo')
    await wrapper.get('select[aria-label="选择 GitHub 仓库"]').setValue('octocat/demo')
    await wrapper.get('[data-testid="bind-repository"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('仓库已绑定')
    expect(fetchMock).toHaveBeenNthCalledWith(4, '/api/repositories', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ full_name: 'octocat/demo' }),
    }))
  })

  it('syncs the bound repository and renders live quality data', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ id: 1, github_login: 'sunnier-glad' }) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [{ full_name: 'octocat/demo', name: 'demo', private: false }] })
      .mockResolvedValueOnce({ ok: true, status: 201, json: async () => ({ id: 7, full_name: 'octocat/demo', webhook_configured: false }) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ pull_requests: 1, failed_workflows: 1, releases: 1 }) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [{ number: 3, title: 'Improve docs', state: 'open', html_url: 'https://example.test/pr/3' }] })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [{ workflow_name: 'CI', conclusion: 'failure', html_url: 'https://example.test/run/21' }] })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [{ tag_name: 'v1.0.0', name: 'First release', html_url: 'https://example.test/release/31' }] })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => qualityGate })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(App)
    await flushPromises()
    await wrapper.get('[data-testid="bind-repository"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="sync-status"]').text()).toContain('同步完成')
    expect(wrapper.get('[data-testid="metric-pr"]').text()).toContain('1')
    expect(wrapper.get('[data-testid="metric-ci"]').text()).toContain('1')
    expect(wrapper.get('[data-testid="metric-release"]').text()).toContain('1')
    expect(wrapper.text()).toContain('Improve docs')
    expect(wrapper.text()).toContain('First release')
    expect(wrapper.get('[data-testid="release-gate"]').text()).toContain('需要确认')
    expect(wrapper.get('[data-testid="gate-check-default_branch_ci"]').text()).toContain('主分支 CI')
    expect(fetchMock).toHaveBeenCalledWith('/api/repositories/7/quality-gate', expect.objectContaining({ credentials: 'include' }))
  })

  it('does not show the available-repository empty hint after a repository is bound', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ id: 1, github_login: 'sunnier-glad' }) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [{ id: 7, full_name: 'octocat/demo', webhook_configured: false }] })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ pull_requests: 0, failed_workflows: 0, releases: 0 }) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => qualityGate })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).not.toContain('当前 GitHub 账号没有可绑定的仓库。')
  })

  it('keeps an empty real repository free of demo-data controls', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ id: 1, github_login: 'sunnier-glad' }) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [{ id: 7, full_name: 'octocat/demo', webhook_configured: false }] })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ pull_requests: 0, failed_workflows: 0, releases: 0 }) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => qualityGate })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).toContain('等待 GitHub 数据')
    expect(wrapper.text()).toContain('同步仓库数据')
    expect(wrapper.text()).not.toContain('演示')
    expect(wrapper.text()).not.toContain('加载本地演示数据')
  })

  it('opens detail views from navigation and quality card actions', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ id: 1, github_login: 'sunnier-glad' }) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [{ id: 7, full_name: 'octocat/demo', webhook_configured: false }] })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ pull_requests: 1, failed_workflows: 1, releases: 1 }) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [{ number: 3, title: 'Improve docs', state: 'open', head_branch: 'docs', html_url: 'https://example.test/pr/3' }] })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [{ workflow_name: 'CI', conclusion: 'failure', branch: 'main', html_url: 'https://example.test/run/21' }] })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [{ tag_name: 'v1.0.0', name: 'First release', html_url: 'https://example.test/release/31' }] })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => qualityGate })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(App)
    await flushPromises()

    await wrapper.get('[data-testid="metric-pr"] button').trigger('click')
    expect(wrapper.get('[data-testid="detail-view"]').text()).toContain('Improve docs')
    expect(wrapper.get('[data-testid="detail-view"]').text()).toContain('开放 PR')

    const releaseNav = wrapper.findAll('button.nav-item').find(button => button.text().includes('Release 质量'))
    await releaseNav.trigger('click')
    expect(wrapper.get('[data-testid="detail-view"]').text()).toContain('First release')
    expect(wrapper.get('[data-testid="detail-view"]').text()).toContain('v1.0.0')
  })
})
