import { flushPromises, mount } from '@vue/test-utils'
import { vi } from 'vitest'

import App from '../App.vue'

const qualityGate = {
  status: 'warning',
  summary: '存在发布前需要人工确认的风险',
  checks: [
    { key: 'default_branch_ci', status: 'warning', title: '主分支 CI', detail: '尚未同步到 main 分支的 CI 记录', url: null },
    { key: 'open_pull_requests', status: 'pass', title: '待处理 PR', detail: '没有待处理的开放 PR', url: null },
    { key: 'release_notes', status: 'warning', title: '发布说明', detail: '尚未生成 Release Notes 草稿', url: null },
  ],
}

const releaseReadiness = {
  status: 'warning',
  summary: '自动检查仍有风险项，需要处理或确认',
  ready_to_release: false,
  version: null,
  automated_checks: qualityGate.checks,
  manual_checks: [
    { key: 'change_scope_confirmed', title: '变更范围已确认', detail: '已核对本次版本变更。', confirmed: false },
    { key: 'rollback_plan_confirmed', title: '回滚方案已准备', detail: '已准备回滚步骤。', confirmed: false },
    { key: 'release_window_confirmed', title: '发布窗口已确认', detail: '已确认发布时间。', confirmed: false },
  ],
  progress: { completed: 1, total: 6 },
  updated_by: null,
  updated_at: null,
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

    expect(wrapper.text()).toContain('还没有同步到事件')
    expect(wrapper.text()).toContain('同步仓库数据')
    expect(wrapper.text()).not.toContain('演示')
    expect(wrapper.text()).not.toContain('加载本地演示数据')
  })

  it('navigates from workflow steps to the matching release section', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: '未登录' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(App)
    await flushPromises()

    await wrapper.get('[data-testid="workflow-step-draft"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="detail-view"]').text()).toContain('发布说明草稿')
    expect(wrapper.get('[data-testid="release-notes-editor"]').exists()).toBe(true)
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
      .mockResolvedValueOnce({ ok: false, status: 404, json: async () => ({ detail: 'Release Notes 草稿不存在' }) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => releaseReadiness })
      .mockResolvedValueOnce({ ok: false, status: 404, json: async () => ({ detail: '尚未生成 AI 润色建议' }) })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(App)
    await flushPromises()

    await wrapper.get('[data-testid="metric-pr"] button').trigger('click')
    expect(wrapper.get('[data-testid="detail-view"]').text()).toContain('Improve docs')
    expect(wrapper.get('[data-testid="detail-view"]').text()).toContain('开放 PR')

    const releaseNav = wrapper.findAll('button.nav-item').find(button => button.text().includes('Release 质量'))
    await releaseNav.trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="detail-view"]').text()).toContain('First release')
    expect(wrapper.get('[data-testid="detail-view"]').text()).toContain('v1.0.0')
  })

  it('generates, edits, and saves a traceable release notes draft', async () => {
    const generatedDraft = {
      id: 4,
      repository_id: 7,
      version: 'v1.2.0',
      content: '# v1.2.0\n\n- [#12](https://example.test/pr/12) Improve docs',
      source_pr_count: 1,
      sources: [{ number: 12, title: 'Improve docs', author_login: 'octocat', html_url: 'https://example.test/pr/12' }],
      based_on_release: { id: 2, tag_name: 'v1.1.0', published_at: '2026-08-01T00:00:00Z' },
    }
    const readyGate = {
      ...qualityGate,
      checks: qualityGate.checks.map(check => check.key === 'release_notes'
        ? { ...check, status: 'pass', detail: 'Release Notes 草稿已准备完成' }
        : check),
    }
    const generatedReadiness = {
      ...releaseReadiness,
      version: 'v1.2.0',
      automated_checks: readyGate.checks,
      progress: { completed: 2, total: 6 },
    }
    const savedChecklist = {
      ...generatedReadiness,
      manual_checks: generatedReadiness.manual_checks.map((check, index) => ({ ...check, confirmed: index === 0 })),
      progress: { completed: 3, total: 6 },
      updated_by: 'sunnier-glad',
      updated_at: '2026-08-31T00:00:00Z',
    }
    const savedContent = '# v1.2.0\n\n## 变更内容\n\n- 完善文档'
    const polishedContent = '# v1.2.0\n\n## 变更内容\n\n- Improve docs'
    const polishSuggestion = {
      id: 9,
      status: 'succeeded',
      model: 'deepseek-chat',
      suggestion: {
        base_content: generatedDraft.content,
        summary: '统一变更表达',
        suggested_content: polishedContent,
        changes: ['统一变更表达'],
      },
    }
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ id: 1, github_login: 'sunnier-glad' }) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [{ id: 7, full_name: 'octocat/demo', webhook_configured: false }] })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ pull_requests: 0, failed_workflows: 0, releases: 0 }) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => qualityGate })
      .mockResolvedValueOnce({ ok: false, status: 404, json: async () => ({ detail: 'Release Notes 草稿不存在' }) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => releaseReadiness })
      .mockResolvedValueOnce({ ok: false, status: 404, json: async () => ({ detail: '尚未生成 AI 润色建议' }) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => generatedDraft })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => readyGate })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => generatedReadiness })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => polishSuggestion })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ ...generatedDraft, content: savedContent }) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => readyGate })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => generatedReadiness })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => savedChecklist })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(App)
    await flushPromises()
    const releaseNav = wrapper.findAll('button.nav-item').find(button => button.text().includes('Release 质量'))
    await releaseNav.trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="release-notes-editor"]').text()).toContain('尚未生成草稿')
    await wrapper.get('[data-testid="release-version"]').setValue('v1.2.0')
    await wrapper.get('[data-testid="generate-release-notes"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="release-notes-content"]').element.value).toContain('# v1.2.0')
    expect(wrapper.get('[data-testid="release-notes-editor"]').text()).toContain('1 个来源 PR')
    expect(wrapper.get('[data-testid="release-notes-editor"]').text()).toContain('Improve docs')
    expect(wrapper.get('a[href="https://example.test/pr/12"]').text()).toContain('#12')

    await wrapper.get('[data-testid="polish-release-notes"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="ai-polish-panel"]').text()).toContain('统一变更表达')
    await wrapper.get('[data-testid="adopt-polish-suggestion"]').trigger('click')
    expect(wrapper.get('[data-testid="release-notes-content"]').element.value).toBe(polishedContent)

    await wrapper.get('[data-testid="release-notes-content"]').setValue(savedContent)
    await wrapper.get('[data-testid="save-release-notes"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="release-notes-editor"]').text()).toContain('草稿已保存')
    await wrapper.get('[data-testid="manual-check-change_scope_confirmed"]').setValue(true)
    await flushPromises()

    expect(wrapper.get('[data-testid="release-checklist"]').text()).toContain('确认状态已保存')
    expect(wrapper.get('[data-testid="release-checklist"]').text()).toContain('sunnier-glad')
    expect(fetchMock).toHaveBeenNthCalledWith(11, '/api/repositories/7/release-notes/draft', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ version: 'v1.2.0' }),
    }))
    expect(fetchMock).toHaveBeenNthCalledWith(14, '/api/repositories/7/release-notes/ai-polish', expect.objectContaining({
      method: 'POST',
    }))
    expect(fetchMock).toHaveBeenNthCalledWith(15, '/api/repositories/7/release-notes/draft', expect.objectContaining({
      method: 'PUT',
      body: JSON.stringify({ content: savedContent }),
    }))
    expect(fetchMock).toHaveBeenNthCalledWith(18, '/api/repositories/7/release-readiness', expect.objectContaining({
      method: 'PUT',
      body: JSON.stringify({
        change_scope_confirmed: true,
        rollback_plan_confirmed: false,
        release_window_confirmed: false,
      }),
    }))
  })
})
