<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  bindRepository,
  getBoundRepositories,
  getAvailableRepositories,
  getFailedWorkflows,
  getPullRequests,
  getReleases,
  getSession,
  syncRepository,
} from './api/client'

const session = ref(null)
const sessionLoading = ref(true)
const activeView = ref('overview')
const availableRepositories = ref([])
const selectedRepository = ref('')
const boundRepository = ref(null)
const repositoryLoading = ref(false)
const repositoryBinding = ref(false)
const repositoryError = ref('')
const syncStatus = ref('')
const syncError = ref('')
const pullRequests = ref([])
const failedWorkflows = ref([])
const releases = ref([])

const navItems = [
  { id: 'overview', label: '质量总览', icon: '⌁' },
  { id: 'pull-requests', label: 'PR 协作', icon: '↗' },
  { id: 'releases', label: 'Release 质量', icon: '◈' },
]

const qualityCards = computed(() => [
  { id: 'metric-ci', label: 'CI 失败', value: String(failedWorkflows.value.length), hint: '当前失败任务', tone: 'danger', action: '查看失败任务' },
  { id: 'metric-pr', label: 'PR 协作', value: String(pullRequests.value.filter(item => item.state === 'open').length), hint: '开放请求', tone: 'accent', action: '查看开放 PR' },
  { id: 'metric-release', label: 'Release 质量', value: String(releases.value.length), hint: '发布记录', tone: 'success', action: '查看发布记录' },
])

const activities = computed(() => [
  ...pullRequests.value.slice(0, 5).map(item => ({
    label: 'PR',
    title: `#${item.number} ${item.title}`,
    detail: item.state === 'open' ? '开放 PR' : `PR ${item.state}`,
    url: item.html_url,
  })),
  ...failedWorkflows.value.slice(0, 5).map(item => ({
    label: 'CI',
    title: item.workflow_name,
    detail: `${item.branch || '未知分支'} · 失败`,
    url: item.html_url,
  })),
  ...releases.value.slice(0, 5).map(item => ({
    label: 'Release',
    title: item.name || item.tag_name,
    detail: item.tag_name,
    url: item.html_url,
  })),
])

async function loadRepositories() {
  repositoryLoading.value = true
  repositoryError.value = ''
  try {
    availableRepositories.value = await getAvailableRepositories()
    if (!selectedRepository.value && availableRepositories.value.length) {
      selectedRepository.value = availableRepositories.value[0].full_name
    }
  } catch (error) {
    repositoryError.value = error.message
  } finally {
    repositoryLoading.value = false
  }
}

async function handleBindRepository() {
  if (!selectedRepository.value) return
  repositoryBinding.value = true
  repositoryError.value = ''
  try {
    boundRepository.value = await bindRepository(selectedRepository.value)
    await loadQualityData()
  } catch (error) {
    repositoryError.value = error.message
  } finally {
    repositoryBinding.value = false
  }
}

async function loadQualityData() {
  if (!boundRepository.value) return
  syncStatus.value = '正在同步…'
  syncError.value = ''
  try {
    await syncRepository(boundRepository.value.id)
    const [pullRequestData, workflowData, releaseData] = await Promise.all([
      getPullRequests(boundRepository.value.id),
      getFailedWorkflows(boundRepository.value.id),
      getReleases(boundRepository.value.id),
    ])
    pullRequests.value = pullRequestData
    failedWorkflows.value = workflowData
    releases.value = releaseData
    syncStatus.value = '同步完成'
  } catch (error) {
    syncStatus.value = '同步失败'
    syncError.value = error.message
  }
}

onMounted(async () => {
  if (typeof fetch !== 'function') {
    sessionLoading.value = false
    return
  }
  try {
    session.value = await getSession()
    const boundRepositories = await getBoundRepositories()
    if (boundRepositories.length) {
      boundRepository.value = boundRepositories[0]
      await loadQualityData()
    } else {
      await loadRepositories()
    }
  } catch {
    // The shell remains usable when the API is not started locally.
  } finally {
    sessionLoading.value = false
  }
})
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand-block">
        <div class="brand-mark">R</div>
        <div><strong>RepoOps</strong><span>release quality</span></div>
      </div>
      <nav class="primary-nav" aria-label="主导航">
        <button v-for="item in navItems" :key="item.id" class="nav-item" :class="{ active: activeView === item.id }" type="button" @click="activeView = item.id">
          <span class="nav-icon">{{ item.icon }}</span>{{ item.label }}
        </button>
      </nav>
      <div class="sidebar-note"><span class="eyebrow">工作流</span><p>从 GitHub 事件到发布结论，集中查看每一次变更的质量信号。</p></div>
      <div class="sidebar-footer"><span class="status-dot"></span><span>Webhook 服务在线</span></div>
    </aside>

    <main class="main-content">
      <header class="topbar">
        <div>
          <p class="eyebrow">PROJECT CONTROL ROOM</p>
          <h1>RepoOps · 发布质量工作台</h1>
          <p class="page-subtitle">GitHub 项目协作与发布质量平台</p>
        </div>
        <div class="topbar-actions">
          <span class="version-pill">v0.1.0 · MVP</span>
          <a v-if="!session" class="login-button" href="/api/auth/github">GitHub 登录 <span>↗</span></a>
          <span v-else class="user-pill">{{ session.github_login }}</span>
        </div>
      </header>

      <section class="workspace-banner">
        <div>
          <span class="eyebrow">当前工作区</span>
          <h2>{{ boundRepository ? boundRepository.full_name : session ? `${session.github_login} 的项目空间` : '连接 GitHub，开始管理项目质量' }}</h2>
          <p v-if="sessionLoading">正在恢复登录状态…</p>
          <p v-else-if="!session">登录后绑定仓库，接收 CI、PR 和 Release 的实时信号。</p>
          <p v-else-if="boundRepository">仓库已绑定，可同步当前 PR、CI 和 Release 数据。</p>
          <p v-else>选择一个仓库，查看变更、失败任务和发布风险。</p>
        </div>
        <div class="workspace-orbit" aria-hidden="true"><span class="orbit-core">RO</span><span class="orbit-ring ring-one"></span><span class="orbit-ring ring-two"></span></div>
      </section>

      <section v-if="session" id="repository-panel" class="repository-panel" aria-label="仓库接入">
        <div class="panel-heading"><div><span class="eyebrow">REPOSITORY ACCESS</span><h2>选择工作仓库</h2></div><span v-if="boundRepository" class="repository-status">已连接</span></div>
        <div v-if="boundRepository" class="repository-bound-state">
          <strong>{{ boundRepository.full_name }}</strong>
          <span>{{ boundRepository.webhook_configured ? 'Webhook 已配置' : 'Webhook 配置待完成' }}</span>
        </div>
        <div v-if="boundRepository" class="sync-toolbar">
          <span data-testid="sync-status">{{ syncStatus || '尚未同步' }}</span>
          <button class="text-button" type="button" :disabled="syncStatus === '正在同步…'" @click="loadQualityData">同步仓库数据 ↻</button>
        </div>
        <div v-else class="repository-picker">
          <select v-model="selectedRepository" aria-label="选择 GitHub 仓库" :disabled="repositoryLoading || !availableRepositories.length">
            <option value="" disabled>{{ repositoryLoading ? '正在加载仓库…' : '请选择一个仓库' }}</option>
            <option v-for="repository in availableRepositories" :key="repository.full_name" :value="repository.full_name">
              {{ repository.full_name }}{{ repository.private ? ' · Private' : '' }}
            </option>
          </select>
          <button data-testid="bind-repository" type="button" :disabled="!selectedRepository || repositoryBinding" @click="handleBindRepository">
            {{ repositoryBinding ? '绑定中…' : '绑定仓库' }}
          </button>
        </div>
        <p v-if="!repositoryLoading && !availableRepositories.length && !repositoryError" class="repository-hint">当前 GitHub 账号没有可绑定的仓库。</p>
        <p v-if="repositoryError" class="repository-error" role="alert">{{ repositoryError }}</p>
        <button v-if="!boundRepository" class="text-button repository-refresh" type="button" @click="loadRepositories">重新加载仓库 ↻</button>
      </section>

      <section class="section-heading"><div><span class="eyebrow">QUALITY SIGNALS</span><h2>今天的发布状态</h2></div><span class="updated-label"><span class="status-dot"></span>数据实时同步</span></section>
      <section class="quality-grid" aria-label="质量指标">
        <article v-for="card in qualityCards" :key="card.label" class="quality-card" :class="card.tone" :data-testid="card.id">
          <div class="card-topline"><span>{{ card.label }}</span><span class="card-arrow">↗</span></div>
          <strong class="card-value">{{ card.value }}</strong>
          <div class="card-footer"><span>{{ card.hint }}</span><span>{{ card.action }}</span></div>
        </article>
      </section>

      <section class="lower-grid">
        <article class="panel activity-panel">
          <div class="panel-heading"><div><span class="eyebrow">EVENT STREAM</span><h2>最近活动</h2></div><button class="text-button" type="button" :disabled="!boundRepository || syncStatus === '正在同步…'" @click="loadQualityData">刷新 ↻</button></div>
          <div v-if="activities.length" class="activity-list">
            <a v-for="activity in activities" :key="`${activity.label}-${activity.title}`" class="activity-row" :href="activity.url || '#'" target="_blank" rel="noreferrer">
              <span class="activity-label">{{ activity.label }}</span><span class="activity-title">{{ activity.title }}</span><span class="activity-detail">{{ activity.detail }}</span><span>↗</span>
            </a>
          </div>
          <div v-else class="empty-state"><div class="empty-icon">⌁</div><strong>{{ boundRepository ? '暂无仓库数据' : '还没有 GitHub 事件' }}</strong><p>{{ boundRepository ? '点击同步仓库数据，加载当前 PR、CI 和 Release。' : '先选择并绑定一个仓库，再接收 push、PR、CI 和 release。' }}</p><button class="empty-link" type="button" @click="boundRepository ? loadQualityData() : document.getElementById('repository-panel')?.scrollIntoView({ behavior: 'smooth' })">{{ boundRepository ? '同步仓库数据' : '选择仓库' }} <span>↗</span></button></div>
          <p v-if="syncError" class="repository-error" role="alert">{{ syncError }}</p>
        </article>
        <article class="panel playbook-panel">
          <div class="panel-heading"><div><span class="eyebrow">HOW IT WORKS</span><h2>质量闭环</h2></div></div>
          <ol class="playbook-list">
            <li><span>01</span><div><strong>接收事件</strong><p>Webhook 原始入库，校验签名与 delivery。</p></div></li>
            <li><span>02</span><div><strong>更新状态</strong><p>PR、CI、Release 进入统一质量模型。</p></div></li>
            <li><span>03</span><div><strong>辅助判断</strong><p>AI 生成摘要与草稿，结果可追溯、可编辑。</p></div></li>
          </ol>
        </article>
      </section>
    </main>
  </div>
</template>

<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');
:root { color: #e9f1ef; background: #0a1113; font-family: 'Manrope', 'Segoe UI', sans-serif; font-synthesis: none; text-rendering: optimizeLegibility; }
* { box-sizing: border-box; } body { margin: 0; min-width: 320px; background: #0a1113; } button, a { font: inherit; } button { color: inherit; } a { color: inherit; text-decoration: none; }
.app-shell { display: flex; min-height: 100vh; background: radial-gradient(circle at 80% 0%, #173237 0, #0a1113 35rem); }
.sidebar { width: 246px; padding: 30px 18px 24px; border-right: 1px solid #233335; display: flex; flex-direction: column; background: rgba(8, 16, 18, .74); }
.brand-block { display: flex; align-items: center; gap: 11px; padding: 0 12px 42px; }.brand-mark { width: 34px; height: 34px; display: grid; place-items: center; border: 1px solid #7fe5c4; color: #071313; background: #8debc9; font-weight: 800; border-radius: 9px; }.brand-block strong { display: block; font-size: 17px; letter-spacing: .02em; }.brand-block span, .eyebrow { color: #77918e; font: 500 10px 'DM Mono', monospace; letter-spacing: .14em; text-transform: uppercase; }
.primary-nav { display: grid; gap: 5px; }.nav-item { display: flex; gap: 12px; align-items: center; border: 0; border-radius: 9px; padding: 12px; background: transparent; color: #8ba09e; text-align: left; cursor: pointer; transition: .2s ease; }.nav-item:hover, .nav-item.active { background: #182b2d; color: #e9f1ef; }.nav-item.active { box-shadow: inset 3px 0 #8debc9; }.nav-icon { width: 19px; color: #8debc9; font-size: 19px; }
.sidebar-note { margin: auto 12px 25px; padding: 17px 0; border-top: 1px solid #233335; border-bottom: 1px solid #233335; }.sidebar-note p { color: #829795; font-size: 12px; line-height: 1.8; margin: 12px 0 0; }.sidebar-footer, .updated-label { display: flex; gap: 8px; align-items: center; color: #76908d; font-size: 11px; }.status-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: #8debc9; box-shadow: 0 0 0 4px rgba(141, 235, 201, .1); }
.main-content { flex: 1; max-width: 1430px; padding: 42px clamp(24px, 5vw, 76px) 60px; margin: 0 auto; }.topbar { display: flex; justify-content: space-between; gap: 30px; align-items: flex-start; } h1, h2, p { margin-top: 0; } h1 { margin: 9px 0 8px; font-size: clamp(27px, 3.2vw, 44px); letter-spacing: -.055em; line-height: 1.1; } h2 { margin: 8px 0 0; font-size: 19px; letter-spacing: -.03em; }.page-subtitle { color: #849a98; font-size: 13px; }.topbar-actions { display: flex; align-items: center; gap: 12px; padding-top: 16px; }.version-pill, .user-pill { border: 1px solid #2b4141; border-radius: 99px; color: #8ca09e; padding: 8px 12px; font: 10px 'DM Mono', monospace; }.login-button { border: 1px solid #8debc9; border-radius: 8px; padding: 10px 15px; color: #071313; background: #8debc9; font-size: 12px; font-weight: 800; }.login-button span, .empty-state a span { margin-left: 9px; }.user-pill { color: #8debc9; }
.workspace-banner { position: relative; overflow: hidden; display: flex; justify-content: space-between; align-items: center; min-height: 194px; margin-top: 48px; padding: 30px 34px; border: 1px solid #294345; border-radius: 15px; background: linear-gradient(110deg, #14292b, #122124 60%, #18383a); }.workspace-banner h2 { font-size: 24px; max-width: 480px; }.workspace-banner p { color: #94aaa7; font-size: 13px; margin: 13px 0 0; }.workspace-orbit { position: relative; width: 160px; height: 130px; margin-right: 45px; }.orbit-core { position: absolute; z-index: 2; inset: 45px 55px; display: grid; place-items: center; border-radius: 50%; background: #8debc9; color: #081314; font: 700 13px 'DM Mono', monospace; }.orbit-ring { position: absolute; border: 1px solid rgba(141, 235, 201, .4); border-radius: 50%; transform: rotate(-20deg); }.ring-one { width: 150px; height: 58px; top: 33px; left: 5px; }.ring-two { width: 130px; height: 85px; top: 20px; left: 15px; transform: rotate(52deg); }
.repository-panel { margin-top: 15px; padding: 22px 24px; border: 1px solid #294345; border-radius: 13px; background: #101c1e; }.repository-status { color: #8debc9; font: 11px 'DM Mono', monospace; }.repository-picker { display: flex; gap: 12px; margin-top: 20px; }.repository-picker select { flex: 1; min-width: 0; border: 1px solid #345153; border-radius: 8px; padding: 12px 14px; color: #dcebe7; background: #0b1517; }.repository-picker button { border: 0; border-radius: 8px; padding: 0 18px; color: #071313; background: #8debc9; font-size: 12px; font-weight: 800; cursor: pointer; }.repository-picker button:disabled { cursor: not-allowed; opacity: .45; }.repository-bound-state { display: flex; justify-content: space-between; gap: 16px; margin-top: 20px; color: #8debc9; font-size: 13px; }.repository-bound-state span, .repository-hint, .repository-error { color: #819997; font-size: 12px; }.repository-error { color: #fb9b8a; }.repository-refresh { margin-top: 15px; padding: 0; }.sync-toolbar { display: flex; justify-content: space-between; gap: 16px; align-items: center; margin-top: 15px; color: #8debc9; font-size: 11px; }.sync-toolbar button:disabled { opacity: .5; cursor: not-allowed; }.empty-link { border: 0; color: #8debc9; background: transparent; cursor: pointer; font-size: 12px; font-weight: 700; }
.section-heading, .panel-heading { display: flex; justify-content: space-between; align-items: flex-end; gap: 20px; }.section-heading { margin: 46px 0 17px; }.quality-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; }.quality-card { min-height: 176px; display: flex; flex-direction: column; padding: 20px; border: 1px solid #263b3d; border-radius: 13px; background: #101c1e; }.quality-card.danger { border-top: 2px solid #fb8c78; }.quality-card.accent { border-top: 2px solid #8dbae9; }.quality-card.success { border-top: 2px solid #8debc9; }.card-topline, .card-footer { display: flex; justify-content: space-between; color: #839997; font-size: 12px; }.card-arrow { color: #8debc9; }.card-value { margin: 25px 0 auto; color: #eff9f5; font-size: 43px; letter-spacing: -.08em; }.card-footer { padding-top: 14px; border-top: 1px solid #233335; font-size: 10px; }.card-footer span:last-child { color: #aac0bc; }
.lower-grid { display: grid; grid-template-columns: 1.35fr 1fr; gap: 15px; margin-top: 15px; }.panel { min-height: 320px; padding: 23px; border: 1px solid #263b3d; border-radius: 13px; background: #101a1c; }.text-button { border: 0; color: #8debc9; background: transparent; cursor: pointer; font-size: 11px; }.empty-state { min-height: 240px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; }.empty-icon { display: grid; place-items: center; width: 41px; height: 41px; margin-bottom: 15px; border: 1px solid #426462; border-radius: 50%; color: #8debc9; font-size: 23px; }.empty-state strong { font-size: 14px; }.empty-state p { max-width: 320px; margin: 8px 0 18px; color: #78908d; font-size: 12px; line-height: 1.7; }.empty-state a { color: #8debc9; font-size: 12px; font-weight: 700; }.activity-list { display: grid; gap: 0; margin-top: 18px; }.activity-row { display: grid; grid-template-columns: 68px minmax(0, 1fr) auto 18px; align-items: center; gap: 10px; padding: 13px 0; border-bottom: 1px solid #243638; color: #dcebe7; font-size: 12px; }.activity-label { color: #8debc9; font: 10px 'DM Mono', monospace; }.activity-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.activity-detail { color: #78908d; font-size: 11px; }.playbook-list { padding: 6px 0 0; margin: 0; list-style: none; }.playbook-list li { display: flex; gap: 16px; padding: 17px 0; border-bottom: 1px solid #243638; }.playbook-list li:last-child { border-bottom: 0; }.playbook-list li > span { color: #5e7b77; font: 11px 'DM Mono', monospace; }.playbook-list strong { font-size: 12px; }.playbook-list p { margin: 5px 0 0; color: #78908d; font-size: 11px; line-height: 1.6; }
@media (max-width: 900px) { .sidebar { width: 190px; }.workspace-orbit { margin-right: 0; transform: scale(.8); }.lower-grid { grid-template-columns: 1fr; } }
@media (max-width: 680px) { .app-shell { display: block; }.sidebar { width: auto; padding: 16px; border-right: 0; border-bottom: 1px solid #233335; }.brand-block { padding: 0 5px 15px; }.primary-nav { grid-template-columns: repeat(3, 1fr); }.nav-item { justify-content: center; padding: 8px 4px; font-size: 11px; }.nav-icon, .sidebar-note, .sidebar-footer { display: none; }.main-content { padding: 28px 16px 40px; }.topbar { display: block; }.topbar-actions { padding-top: 14px; }.workspace-banner { min-height: 170px; margin-top: 28px; padding: 23px; }.workspace-orbit { display: none; }.repository-picker { display: grid; }.repository-picker button { min-height: 42px; }.repository-bound-state { display: grid; gap: 6px; }.quality-grid { grid-template-columns: 1fr; }.quality-card { min-height: 145px; }.section-heading { margin-top: 32px; } }
</style>
