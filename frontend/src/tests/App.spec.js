import { mount } from '@vue/test-utils'

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
})
