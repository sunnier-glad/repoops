<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import {
  bindRepository,
  generateReleaseNoteDraft,
  getBoundRepositories,
  getAvailableRepositories,
  getFailedWorkflows,
  getPullRequests,
  getQualityGate,
  getReleaseNoteDraft,
  getLatestReleaseNotesPolish,
  getReleaseReadiness,
  polishReleaseNotes,
  getReleases,
  getSession,
  saveReleaseChecklist,
  saveReleaseNoteDraft,
  syncRepository,
} from './api/client'

const session = ref(null)
const sessionLoading = ref(true)
const activeView = ref('overview')
const availableRepositories = ref([])
const boundRepositories = ref([])
const selectedRepository = ref('')
const boundRepository = ref(null)
const boundRepositoryId = ref('')
const repositoryPickerOpen = ref(false)
const repositoryLoading = ref(false)
const repositoryBinding = ref(false)
const repositoryError = ref('')
const syncStatus = ref('')
const syncError = ref('')
const pullRequests = ref([])
const failedWorkflows = ref([])
const releases = ref([])
const qualityGate = ref(null)
const releaseNoteDraft = ref(null)
const releaseVersion = ref('v0.1.0')
const releaseContent = ref('')
const releaseDraftLoading = ref(false)
const releaseDraftSaving = ref(false)
const releaseDraftStatus = ref('')
const releaseDraftError = ref('')
const releaseReadiness = ref(null)
const releaseChecklistLoading = ref(false)
const releaseChecklistSaving = ref(false)
const releaseChecklistStatus = ref('')
const releaseChecklistError = ref('')
const releasePolishSuggestion = ref(null)
const releasePolishLoading = ref(false)
const releasePolishStatus = ref('')
const releasePolishError = ref('')

const navItems = [
  { id: 'overview', label: '质量总览', icon: '⌁' },
  { id: 'pull-requests', label: 'PR 协作', icon: '↗' },
  { id: 'releases', label: 'Release 质量', icon: '◈' },
]

const qualityCards = computed(() => [
  { id: 'metric-ci', label: 'CI 失败', description: '自动化检查未通过的任务', value: String(failedWorkflows.value.length), hint: '当前失败任务', tone: 'danger', action: '查看失败任务', target: 'ci' },
  { id: 'metric-pr', label: 'PR 协作', description: '等待处理的代码合并请求', value: String(pullRequests.value.filter(item => item.state === 'open').length), hint: '开放请求', tone: 'accent', action: '查看开放 PR', target: 'pull-requests' },
  { id: 'metric-release', label: 'Release 质量', description: 'GitHub 上已经发布的版本', value: String(releases.value.length), hint: '发布记录', tone: 'success', action: '查看发布记录', target: 'releases' },
])

const hasReleaseDraft = computed(() => Boolean(
  releaseNoteDraft.value
  || qualityGate.value?.checks?.some(check => check.key === 'release_notes' && check.status === 'pass'),
))

const bindableRepositories = computed(() => {
  const boundNames = new Set(boundRepositories.value.map(repository => repository.full_name))
  return availableRepositories.value.filter(repository => !boundNames.has(repository.full_name))
})

const workflowSteps = computed(() => {
  const syncDone = syncStatus.value === '同步完成'
  return [
    { key: 'connect', number: '01', label: '连接仓库', detail: boundRepository.value ? '已连接真实仓库' : session.value ? '等待选择仓库' : '需要先登录', status: boundRepository.value ? 'done' : session.value ? 'current' : 'locked' },
    { key: 'sync', number: '02', label: '同步数据', detail: syncDone ? 'PR、CI、Release 已更新' : '从 GitHub 拉取最新记录', status: !boundRepository.value ? 'locked' : syncDone ? 'done' : 'current' },
    { key: 'draft', number: '03', label: '准备发布说明', detail: hasReleaseDraft.value ? '已有可编辑草稿' : '生成版本变更摘要', status: !syncDone ? 'locked' : hasReleaseDraft.value ? 'done' : 'current' },
    { key: 'review', number: '04', label: '检查并确认', detail: releaseReadiness.value?.status === 'ready' ? '检查单已完成' : '人工确认发布风险', status: !hasReleaseDraft.value ? 'locked' : releaseReadiness.value?.status === 'ready' ? 'done' : 'current' },
  ]
})

const nextAction = computed(() => {
  if (sessionLoading.value) return { eyebrow: 'WORKSPACE STATUS', title: '正在恢复工作区', description: '正在读取登录状态和已绑定仓库，请稍候。', action: 'none', label: '读取中…' }
  if (!session.value) return { eyebrow: 'START HERE', title: '先连接你的 GitHub 项目', description: '登录后选择一个有权限访问的仓库，RepoOps 才能读取真实的 PR、CI 和版本记录。', action: 'login', label: 'GitHub 登录' }
  if (!boundRepository.value) return { eyebrow: 'NEXT STEP', title: '绑定一个工作仓库', description: '从你的 GitHub 仓库列表中选择项目，绑定后即可开始同步质量数据。', action: 'bind', label: '选择仓库' }
  if (syncStatus.value !== '同步完成') return { eyebrow: 'NEXT STEP', title: '同步一次 GitHub 数据', description: '先拉取最新的 PR、CI 和 Release，下面的质量判断才会有依据。', action: 'sync', label: syncStatus.value === '正在同步…' ? '同步中…' : '同步仓库数据' }
  if (!hasReleaseDraft.value) return { eyebrow: 'RELEASE QUALITY', title: '生成本次版本的发布说明', description: '系统会根据已同步的合并 PR 生成草稿，你可以编辑内容，也可以让 AI 提供可审阅的润色建议。', action: 'release', label: '去生成草稿' }
  return { eyebrow: 'RELEASE QUALITY', title: '检查并确认发布准备状态', description: '草稿已经准备好。请核对变更范围、回滚方案和发布时间，再查看是否还有自动风险。', action: 'release', label: '查看发布质量' }
})

const releaseWorkflowSteps = computed(() => [
  { key: 'sync', number: '01', label: '同步数据', detail: '获取真实 GitHub 记录', status: syncStatus.value === '同步完成' ? 'done' : 'current' },
  { key: 'draft', number: '02', label: '生成草稿', detail: '整理合并 PR 变更', status: releaseNoteDraft.value ? 'done' : 'current' },
  { key: 'review', number: '03', label: '审阅保存', detail: '人工编辑或采用 AI 建议', status: releaseNoteDraft.value && releaseDraftStatus.value === '草稿已保存' ? 'done' : releaseNoteDraft.value ? 'current' : 'locked' },
  { key: 'checklist', number: '04', label: '发布前检查', detail: '确认自动风险和人工事项', status: releaseReadiness.value?.status === 'ready' ? 'done' : releaseReadiness.value ? 'current' : 'locked' },
])

const qualityGateLabel = computed(() => ({
  blocked: '阻塞发布',
  warning: '需要确认',
  ready: '可以发布',
}[qualityGate.value?.status] || '等待评估'))

const qualityCheckLabel = (status) => ({
  fail: '未通过',
  warning: '需确认',
  pass: '已通过',
}[status] || status)

const formatTimestamp = (value) => value
  ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
  : ''

const releaseReadinessLabel = computed(() => ({
  blocked: '阻塞发布',
  warning: '存在风险',
  pending: '等待人工确认',
  ready: '准备完成',
}[releaseReadiness.value?.status] || '等待检查'))

const releaseReadinessProgress = computed(() => {
  const progress = releaseReadiness.value?.progress
  if (!progress?.total) return 0
  return Math.round((progress.completed / progress.total) * 100)
})

const detailConfig = computed(() => {
  const configs = {
    ci: { eyebrow: 'CI FAILURE QUEUE', title: '失败任务', description: '集中查看最近同步到的失败工作流，定位分支和失败入口。' },
    'pull-requests': { eyebrow: 'PR COLLABORATION', title: '开放 PR', description: '查看待处理变更、来源分支和 GitHub 原始链接。' },
    releases: { eyebrow: 'RELEASE QUALITY', title: '发布记录', description: '按仓库查看已同步的版本、标签和发布入口。' },
  }
  return configs[activeView.value]
})

const detailItems = computed(() => {
  if (activeView.value === 'ci') return failedWorkflows.value
  if (activeView.value === 'pull-requests') return pullRequests.value.filter(item => item.state === 'open')
  if (activeView.value === 'releases') return releases.value
  return []
})

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

let qualityLoadSequence = 0

async function loadRepositories() {
  repositoryLoading.value = true
  repositoryError.value = ''
  try {
    availableRepositories.value = await getAvailableRepositories()
    if (!bindableRepositories.value.some(repository => repository.full_name === selectedRepository.value)) {
      selectedRepository.value = bindableRepositories.value[0]?.full_name || ''
    }
  } catch (error) {
    repositoryError.value = error.message
  } finally {
    repositoryLoading.value = false
  }
}

async function toggleRepositoryPicker() {
  repositoryPickerOpen.value = !repositoryPickerOpen.value
  if (repositoryPickerOpen.value) await loadRepositories()
}

function resetRepositoryData() {
  qualityLoadSequence += 1
  pullRequests.value = []
  failedWorkflows.value = []
  releases.value = []
  qualityGate.value = null
  releaseNoteDraft.value = null
  releaseVersion.value = 'v0.1.0'
  releaseContent.value = ''
  releaseReadiness.value = null
  releasePolishSuggestion.value = null
  syncStatus.value = ''
  syncError.value = ''
  releaseDraftStatus.value = ''
  releaseDraftError.value = ''
  releaseChecklistStatus.value = ''
  releaseChecklistError.value = ''
  releasePolishStatus.value = ''
  releasePolishError.value = ''
}

function setBoundRepository(repository) {
  boundRepository.value = repository
  boundRepositoryId.value = repository?.id ?? ''
  resetRepositoryData()
}

async function handleBindRepository() {
  if (!selectedRepository.value) return
  repositoryBinding.value = true
  repositoryError.value = ''
  try {
    const repository = await bindRepository(selectedRepository.value)
    boundRepositories.value = [...boundRepositories.value, repository]
    setBoundRepository(repository)
    repositoryPickerOpen.value = false
    await loadQualityData()
  } catch (error) {
    repositoryError.value = error.message
  } finally {
    repositoryBinding.value = false
  }
}

async function handleRepositorySwitch() {
  const repository = boundRepositories.value.find(item => String(item.id) === String(boundRepositoryId.value))
  if (!repository || repository.id === boundRepository.value?.id) return
  setBoundRepository(repository)
  await loadQualityData()
  if (activeView.value === 'releases') await loadReleaseWorkspace()
}

async function loadQualityData() {
  if (!boundRepository.value) return
  const repositoryId = boundRepository.value.id
  const sequence = ++qualityLoadSequence
  syncStatus.value = '正在同步…'
  syncError.value = ''
  try {
    await syncRepository(repositoryId)
    const [pullRequestData, workflowData, releaseData, qualityGateData] = await Promise.all([
      getPullRequests(repositoryId),
      getFailedWorkflows(repositoryId),
      getReleases(repositoryId),
      getQualityGate(repositoryId),
    ])
    if (sequence !== qualityLoadSequence || boundRepository.value?.id !== repositoryId) return
    pullRequests.value = pullRequestData
    failedWorkflows.value = workflowData
    releases.value = releaseData
    qualityGate.value = qualityGateData
    syncStatus.value = '同步完成'
  } catch (error) {
    if (sequence !== qualityLoadSequence || boundRepository.value?.id !== repositoryId) return
    syncStatus.value = '同步失败'
    syncError.value = error.message
  }
}

function handleNextAction() {
  if (nextAction.value.action === 'bind') {
    document.getElementById('repository-panel')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  } else if (nextAction.value.action === 'sync') {
    loadQualityData()
  } else if (nextAction.value.action === 'release') {
    activeView.value = 'releases'
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
}

function scrollToStepTarget(selector) {
  nextTick(() => {
    document.querySelector(selector)?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
  })
}

function handleWorkflowStep(step) {
  if (step.key === 'connect' || step.key === 'sync') {
    if (step.key === 'sync' && boundRepository.value && syncStatus.value !== '正在同步…') {
      loadQualityData()
    }
    document.getElementById('repository-panel')?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
    return
  }

  activeView.value = 'releases'
  scrollToStepTarget(step.key === 'draft'
    ? '[data-testid="release-notes-editor"]'
    : '[data-testid="release-checklist"]')
}

function applyReleaseNoteDraft(draft) {
  releaseNoteDraft.value = draft
  releaseVersion.value = draft.version
  releaseContent.value = draft.content
}

async function loadReleaseNoteDraft() {
  if (!boundRepository.value) return
  releaseDraftLoading.value = true
  releaseDraftError.value = ''
  releaseDraftStatus.value = ''
  try {
    applyReleaseNoteDraft(await getReleaseNoteDraft(boundRepository.value.id))
  } catch (error) {
    if (error.status === 404) {
      releaseNoteDraft.value = null
      releaseContent.value = ''
    } else {
      releaseDraftError.value = error.message
    }
  } finally {
    releaseDraftLoading.value = false
  }
}

async function loadReleaseReadiness() {
  if (!boundRepository.value) return
  releaseChecklistLoading.value = true
  releaseChecklistError.value = ''
  try {
    releaseReadiness.value = await getReleaseReadiness(boundRepository.value.id)
  } catch (error) {
    releaseChecklistError.value = error.message
  } finally {
    releaseChecklistLoading.value = false
  }
}

async function loadReleaseWorkspace() {
  await Promise.all([loadReleaseNoteDraft(), loadReleaseReadiness(), loadLatestReleaseNotesPolish()])
}

async function loadLatestReleaseNotesPolish() {
  if (!boundRepository.value) return
  releasePolishError.value = ''
  try {
    const result = await getLatestReleaseNotesPolish(boundRepository.value.id)
    if (result.status === 'succeeded' && result.suggestion) {
      releasePolishSuggestion.value = result
    } else {
      releasePolishSuggestion.value = null
      releasePolishError.value = result.error || '上一次 AI 润色未生成可审阅建议'
    }
  } catch (error) {
    if (error.status === 404) {
      releasePolishSuggestion.value = null
    } else {
      releasePolishError.value = error.message
    }
  }
}

async function handleGenerateReleaseNoteDraft() {
  const version = releaseVersion.value.trim()
  if (!boundRepository.value || !version) return
  releaseDraftSaving.value = true
  releaseDraftError.value = ''
  releaseDraftStatus.value = '正在生成草稿…'
  try {
    applyReleaseNoteDraft(await generateReleaseNoteDraft(boundRepository.value.id, version))
    const [qualityGateData, readinessData] = await Promise.all([
      getQualityGate(boundRepository.value.id),
      getReleaseReadiness(boundRepository.value.id),
    ])
    qualityGate.value = qualityGateData
    releaseReadiness.value = readinessData
    releasePolishSuggestion.value = null
    releasePolishStatus.value = ''
    releaseDraftStatus.value = '草稿已生成，发布门禁已更新'
  } catch (error) {
    releaseDraftStatus.value = ''
    releaseDraftError.value = error.message
  } finally {
    releaseDraftSaving.value = false
  }
}

async function handleSaveReleaseNoteDraft() {
  if (!boundRepository.value || !releaseNoteDraft.value || !releaseContent.value.trim()) return
  releaseDraftSaving.value = true
  releaseDraftError.value = ''
  releaseDraftStatus.value = '正在保存草稿…'
  try {
    applyReleaseNoteDraft(await saveReleaseNoteDraft(boundRepository.value.id, releaseContent.value))
    const [qualityGateData, readinessData] = await Promise.all([
      getQualityGate(boundRepository.value.id),
      getReleaseReadiness(boundRepository.value.id),
    ])
    qualityGate.value = qualityGateData
    releaseReadiness.value = readinessData
    releasePolishSuggestion.value = null
    releasePolishStatus.value = ''
    releaseDraftStatus.value = '草稿已保存'
  } catch (error) {
    releaseDraftStatus.value = ''
    releaseDraftError.value = error.message
  } finally {
    releaseDraftSaving.value = false
  }
}

async function handlePolishReleaseNotes() {
  if (!boundRepository.value || !releaseNoteDraft.value || releasePolishLoading.value) return
  releasePolishLoading.value = true
  releasePolishError.value = ''
  releasePolishStatus.value = '正在生成润色建议…'
  try {
    const result = await polishReleaseNotes(boundRepository.value.id)
    if (result.status !== 'succeeded' || !result.suggestion) {
      releasePolishSuggestion.value = null
      releasePolishStatus.value = ''
      releasePolishError.value = result.error || 'AI 未返回可审阅的建议'
    } else {
      releasePolishSuggestion.value = result
      releasePolishStatus.value = '建议已生成，请审阅后手动采用'
    }
  } catch (error) {
    releasePolishStatus.value = ''
    releasePolishError.value = error.message
  } finally {
    releasePolishLoading.value = false
  }
}

function adoptReleaseNotesSuggestion() {
  const suggestedContent = releasePolishSuggestion.value?.suggestion?.suggested_content
  if (!suggestedContent) return
  releaseContent.value = suggestedContent
  releasePolishStatus.value = '建议已载入编辑区，请检查内容后保存'
}

async function handleChecklistChange(key, confirmed) {
  if (!boundRepository.value || !releaseReadiness.value || releaseChecklistSaving.value) return
  const confirmations = Object.fromEntries(
    releaseReadiness.value.manual_checks.map(item => [item.key, item.confirmed]),
  )
  confirmations[key] = confirmed
  releaseChecklistSaving.value = true
  releaseChecklistError.value = ''
  releaseChecklistStatus.value = '正在保存确认状态…'
  try {
    releaseReadiness.value = await saveReleaseChecklist(boundRepository.value.id, confirmations)
    releaseChecklistStatus.value = '确认状态已保存'
  } catch (error) {
    releaseChecklistStatus.value = ''
    releaseChecklistError.value = error.message
  } finally {
    releaseChecklistSaving.value = false
  }
}

watch(activeView, (view) => {
  if (view === 'releases' && boundRepository.value) loadReleaseWorkspace()
})

onMounted(async () => {
  if (typeof fetch !== 'function') {
    sessionLoading.value = false
    return
  }
  try {
    session.value = await getSession()
    boundRepositories.value = await getBoundRepositories()
    if (boundRepositories.value.length) {
      setBoundRepository(boundRepositories.value[0])
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

      <section v-if="activeView === 'overview'" class="next-action-card" :class="nextAction.action" data-testid="next-action" aria-label="下一步操作">
        <div class="next-action-copy">
          <span class="eyebrow">{{ nextAction.eyebrow }}</span>
          <h2>{{ nextAction.title }}</h2>
          <p>{{ nextAction.description }}</p>
        </div>
        <div class="next-action-cta">
          <span>推荐下一步</span>
          <a v-if="nextAction.action === 'login'" class="primary-action" href="/api/auth/github">{{ nextAction.label }} <span>↗</span></a>
          <button v-else class="primary-action" type="button" :disabled="nextAction.action === 'none' || syncStatus === '正在同步…'" @click="handleNextAction">{{ nextAction.label }} <span>→</span></button>
        </div>
      </section>

      <section v-if="activeView === 'overview'" class="workflow-strip" data-testid="workflow-guide" aria-label="使用流程">
        <div class="workflow-intro"><span class="eyebrow">HOW TO USE</span><strong>四步完成一次发布检查</strong><small>先连接和同步，再生成说明，最后确认风险。</small></div>
        <ol class="workflow-steps">
          <li v-for="step in workflowSteps" :key="step.key" :class="step.status" :data-testid="`workflow-step-${step.key}`" role="button" tabindex="0" @click="handleWorkflowStep(step)" @keydown.enter="handleWorkflowStep(step)" @keydown.space.prevent="handleWorkflowStep(step)">
            <span class="workflow-number">{{ step.number }}</span>
            <div><strong>{{ step.label }}</strong><small>{{ step.detail }}</small></div>
            <span class="workflow-status">{{ step.status === 'done' ? '完成' : step.status === 'current' ? '当前' : '待开始' }}</span>
          </li>
        </ol>
      </section>

      <section v-if="session" id="repository-panel" class="repository-panel" aria-label="仓库接入">
        <div class="panel-heading"><div><span class="eyebrow">REPOSITORY ACCESS</span><h2>{{ boundRepository ? '当前工作仓库' : '选择工作仓库' }}</h2><p class="panel-helper">{{ boundRepository ? '切换仓库可查看独立的 PR、CI、Release 和发布检查。' : '只会显示当前 GitHub 账号有权限访问的仓库。' }}</p></div><span v-if="boundRepository" class="repository-status">已连接 {{ boundRepositories.length }} 个</span></div>
        <div v-if="boundRepository" class="repository-bound-state">
          <label class="repository-selection">
            <span>当前查看仓库</span>
            <select v-model="boundRepositoryId" data-testid="bound-repository-switcher" aria-label="切换已绑定仓库" :disabled="syncStatus === '正在同步…'" @change="handleRepositorySwitch">
              <option v-for="repository in boundRepositories" :key="repository.id" :value="repository.id">{{ repository.full_name }}</option>
            </select>
            <small>{{ boundRepository.webhook_configured ? 'Webhook 已配置' : '本地模式：通过同步按钮获取 GitHub 数据' }}</small>
          </label>
          <button class="text-button repository-switch-button" data-testid="bind-new-repository" type="button" @click="toggleRepositoryPicker">{{ repositoryPickerOpen ? '收起绑定面板' : '绑定新仓库' }}</button>
        </div>
        <div v-if="boundRepository" class="sync-toolbar">
          <span data-testid="sync-status">{{ syncStatus || '尚未同步' }}</span>
          <button class="text-button" type="button" :disabled="syncStatus === '正在同步…'" @click="loadQualityData">同步仓库数据 ↻</button>
        </div>
        <div v-if="repositoryPickerOpen || !boundRepository" class="repository-picker">
          <select v-model="selectedRepository" aria-label="选择 GitHub 仓库" :disabled="repositoryLoading || !bindableRepositories.length">
            <option value="" disabled>{{ repositoryLoading ? '正在加载仓库…' : bindableRepositories.length ? '请选择一个未绑定仓库' : '没有新的可绑定仓库' }}</option>
            <option v-for="repository in bindableRepositories" :key="repository.full_name" :value="repository.full_name">
              {{ repository.full_name }}{{ repository.private ? ' · Private' : '' }}
            </option>
          </select>
          <button data-testid="bind-repository" type="button" :disabled="!selectedRepository || repositoryBinding" @click="handleBindRepository">
            {{ repositoryBinding ? '绑定中…' : '绑定仓库' }}
          </button>
        </div>
        <p v-if="(repositoryPickerOpen || !boundRepository) && !repositoryLoading && !bindableRepositories.length && !repositoryError" class="repository-hint">当前 GitHub 账号没有尚未绑定的仓库。</p>
        <p v-if="repositoryError" class="repository-error" role="alert">{{ repositoryError }}</p>
        <button v-if="repositoryPickerOpen || !boundRepository" class="text-button repository-refresh" type="button" @click="loadRepositories">重新加载仓库 ↻</button>
      </section>

      <template v-if="activeView === 'overview'">
        <section class="section-heading"><div><span class="eyebrow">QUALITY SIGNALS</span><h2>当前质量状态</h2><p class="section-helper">用下面的门禁和指标判断：现在是否适合准备下一次发布。</p></div><span class="updated-label"><span class="status-dot"></span>数据实时同步</span></section>
        <section v-if="boundRepository" class="release-gate" :class="qualityGate?.status || 'loading'" data-testid="release-gate" aria-label="发布质量门禁">
          <div class="gate-summary">
            <div>
              <span class="eyebrow">RELEASE GATE</span>
              <h2>发布质量门禁</h2>
            </div>
            <span class="gate-badge">{{ qualityGateLabel }}</span>
            <p>{{ qualityGate?.summary || '正在根据真实 GitHub 数据评估发布风险…' }}</p>
            <span class="gate-help">怎么看：红色代表需要先处理，黄色代表需要人工确认，绿色代表当前检查通过。</span>
          </div>
          <div v-if="qualityGate" class="gate-checks">
            <article v-for="check in qualityGate.checks" :key="check.key" class="gate-check" :class="check.status" :data-testid="`gate-check-${check.key}`">
              <div class="gate-check-heading"><strong>{{ check.title }}</strong><span>{{ qualityCheckLabel(check.status) }}</span></div>
              <p>{{ check.detail }}</p>
              <a v-if="check.url" :href="check.url" target="_blank" rel="noreferrer">查看 GitHub 证据 ↗</a>
            </article>
          </div>
        </section>
        <section class="quality-grid" aria-label="质量指标">
          <article v-for="card in qualityCards" :key="card.label" class="quality-card" :class="card.tone" :data-testid="card.id">
            <div class="card-topline"><span>{{ card.label }}</span><span class="card-arrow">↗</span></div>
            <strong class="card-value">{{ card.value }}</strong>
            <p class="card-description">{{ card.description }}</p>
            <div class="card-footer"><span>{{ card.hint }}</span><button class="card-action" type="button" @click="activeView = card.target">{{ card.action }}</button></div>
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
            <div v-else class="empty-state"><div class="empty-icon">⌁</div><strong>{{ boundRepository ? '还没有同步到事件' : '还没有 GitHub 事件' }}</strong><p>{{ boundRepository ? '当前仓库还没有 PR、CI 或 Release；先点击同步，之后在 GitHub 产生真实事件再同步一次。' : '先选择并绑定一个仓库，再接收 push、PR、CI 和 release。' }}</p><button v-if="boundRepository" class="empty-link" type="button" :disabled="syncStatus === '正在同步…'" @click="loadQualityData">同步仓库数据 <span>↻</span></button><button v-else class="empty-link" type="button" @click="document.getElementById('repository-panel')?.scrollIntoView({ behavior: 'smooth' })">选择工作仓库 <span>↗</span></button></div>
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
      </template>

      <section v-else class="detail-view" data-testid="detail-view">
        <div class="section-heading detail-heading">
          <div><span class="eyebrow">{{ detailConfig.eyebrow }}</span><h2>{{ detailConfig.title }}</h2><p>{{ detailConfig.description }}</p></div>
          <button class="text-button" type="button" @click="activeView = 'overview'">返回总览 ↩</button>
        </div>
        <section v-if="activeView === 'releases'" class="release-flow-guide" data-testid="release-flow-guide" aria-label="Release 质量使用步骤">
          <div class="release-flow-heading"><div><span class="eyebrow">RELEASE FLOW</span><h2>按顺序完成，不容易漏步骤</h2></div><small>草稿和建议都不会自动发布</small></div>
          <ol class="release-flow-steps">
            <li v-for="step in releaseWorkflowSteps" :key="step.key" :class="step.status" :data-testid="`release-step-${step.key}`" role="button" tabindex="0" @click="handleWorkflowStep(step)" @keydown.enter="handleWorkflowStep(step)" @keydown.space.prevent="handleWorkflowStep(step)"><span>{{ step.number }}</span><div><strong>{{ step.label }}</strong><small>{{ step.detail }}</small></div><b>{{ step.status === 'done' ? '✓' : step.status === 'current' ? '进行中' : '待开始' }}</b></li>
          </ol>
        </section>
        <article v-if="activeView === 'releases'" class="panel release-checklist" :class="releaseReadiness?.status || 'loading'" data-testid="release-checklist">
          <div class="checklist-heading">
            <div>
              <span class="eyebrow">RELEASE READINESS</span>
              <h2>发布前检查单</h2>
              <p>{{ releaseReadiness?.summary || '正在汇总自动检查和人工确认状态…' }}</p>
            </div>
            <div class="checklist-result">
              <span class="checklist-badge">{{ releaseReadinessLabel }}</span>
              <strong>{{ releaseReadiness?.progress.completed || 0 }}/{{ releaseReadiness?.progress.total || 6 }}</strong>
              <small>检查完成</small>
            </div>
          </div>
          <div class="progress-track" aria-label="检查进度">
            <span :style="{ width: `${releaseReadinessProgress}%` }"></span>
          </div>

          <div v-if="releaseReadiness" class="checklist-grid">
            <section class="checklist-group" aria-label="自动检查">
              <div class="checklist-group-heading"><span>自动检查</span><small>来自真实 GitHub 数据</small></div>
              <a v-for="check in releaseReadiness.automated_checks" :key="check.key" class="checklist-row automated" :class="check.status" :href="check.url || undefined" :target="check.url ? '_blank' : undefined" rel="noreferrer">
                <span class="check-indicator">{{ check.status === 'pass' ? '✓' : check.status === 'fail' ? '×' : '!' }}</span>
                <div><strong>{{ check.title }}</strong><p>{{ check.detail }}</p></div>
                <small>{{ qualityCheckLabel(check.status) }}{{ check.url ? ' ↗' : '' }}</small>
              </a>
            </section>
            <section class="checklist-group" aria-label="人工确认">
              <div class="checklist-group-heading"><span>人工确认</span><small>{{ releaseReadiness.version || '等待草稿版本' }}</small></div>
              <label v-for="check in releaseReadiness.manual_checks" :key="check.key" class="checklist-row manual" :class="{ confirmed: check.confirmed }">
                <input type="checkbox" :data-testid="`manual-check-${check.key}`" :checked="check.confirmed" :disabled="!releaseNoteDraft || releaseChecklistSaving" @change="handleChecklistChange(check.key, $event.target.checked)">
                <span class="manual-checkbox">✓</span>
                <div><strong>{{ check.title }}</strong><p>{{ check.detail }}</p></div>
              </label>
            </section>
          </div>
          <p v-if="releaseChecklistLoading" class="draft-message">正在读取检查单…</p>
          <p v-if="releaseChecklistStatus" class="draft-message success" role="status">{{ releaseChecklistStatus }}</p>
          <p v-if="releaseChecklistError" class="draft-message error" role="alert">{{ releaseChecklistError }}</p>
          <div v-if="releaseReadiness?.updated_at" class="checklist-audit">
            最近确认：{{ releaseReadiness.updated_by || '未知用户' }} · {{ formatTimestamp(releaseReadiness.updated_at) }}
          </div>
        </article>
        <article v-if="activeView === 'releases'" class="panel release-editor" data-testid="release-notes-editor">
          <div class="release-editor-heading">
            <div>
              <span class="eyebrow">RELEASE NOTES DRAFT</span>
              <h2>发布说明草稿</h2>
              <p>根据上次发布后合并到默认分支的真实 PR 生成，支持人工编辑和保存。</p>
            </div>
            <span class="draft-safety-badge">仅保存草稿 · 不自动发布</span>
          </div>

          <div class="release-editor-toolbar">
            <label class="version-field">
              <span>目标版本</span>
              <input v-model="releaseVersion" data-testid="release-version" type="text" maxlength="100" placeholder="例如 v1.2.0" :disabled="!boundRepository || releaseDraftLoading || releaseDraftSaving">
            </label>
            <button class="editor-primary-button" data-testid="generate-release-notes" type="button" :disabled="!boundRepository || !releaseVersion.trim() || releaseDraftLoading || releaseDraftSaving" @click="handleGenerateReleaseNoteDraft">
              {{ releaseDraftSaving ? '处理中…' : releaseNoteDraft ? '重新生成草稿' : '生成草稿' }}
            </button>
            <button class="editor-secondary-button" data-testid="save-release-notes" type="button" :disabled="!releaseNoteDraft || !releaseContent.trim() || releaseDraftLoading || releaseDraftSaving" @click="handleSaveReleaseNoteDraft">保存修改</button>
            <button class="editor-ai-button" data-testid="polish-release-notes" type="button" :disabled="!releaseNoteDraft || releaseDraftSaving || releasePolishLoading" @click="handlePolishReleaseNotes">{{ releasePolishLoading ? '分析中…' : 'AI 润色建议' }}</button>
          </div>

          <p class="editor-hint"><span>使用提示</span>先生成草稿，再编辑或获取 AI 建议；AI 只提供建议，确认后仍需手动保存。</p>

          <p v-if="releaseDraftLoading" class="draft-message">正在读取草稿…</p>
          <p v-else-if="!boundRepository" class="draft-message">请先绑定 GitHub 仓库，再生成发布说明。</p>
          <p v-else-if="!releaseNoteDraft" class="draft-message">尚未生成草稿。填写目标版本后，系统会从已同步的合并 PR 中提取变更。</p>
          <p v-if="releaseDraftStatus" class="draft-message success" role="status">{{ releaseDraftStatus }}</p>
          <p v-if="releaseDraftError" class="draft-message error" role="alert">{{ releaseDraftError }}</p>
          <p v-if="releasePolishStatus" class="draft-message success" role="status">{{ releasePolishStatus }}</p>
          <p v-if="releasePolishError" class="draft-message error" role="alert">{{ releasePolishError }}</p>

          <div class="release-editor-grid">
            <label class="markdown-editor">
              <span>Markdown 内容</span>
              <textarea v-model="releaseContent" data-testid="release-notes-content" rows="15" placeholder="生成草稿后可在这里编辑…" :disabled="!releaseNoteDraft || releaseDraftLoading || releaseDraftSaving"></textarea>
            </label>
            <aside class="release-sources" aria-label="草稿来源">
              <div class="source-summary">
                <span class="eyebrow">TRACEABLE SOURCES</span>
                <strong>{{ releaseNoteDraft?.source_pr_count || 0 }} 个来源 PR</strong>
                <p>{{ releaseNoteDraft?.based_on_release ? `基于 ${releaseNoteDraft.based_on_release.tag_name} 之后的变更` : '基于仓库开始记录以来的变更' }}</p>
              </div>
              <div v-if="releaseNoteDraft?.sources?.length" class="source-list">
                <a v-for="source in releaseNoteDraft.sources" :key="source.number" :href="source.html_url || '#'" target="_blank" rel="noreferrer">
                  <span>#{{ source.number }}</span>
                  <strong>{{ source.title }}</strong>
                  <small>{{ source.author_login ? `@${source.author_login}` : '未知作者' }} ↗</small>
                </a>
              </div>
              <p v-else class="source-empty">当前没有符合条件的已合并 PR。草稿仍可生成和手动编辑，但不会伪造变更内容。</p>
            </aside>
          </div>
          <section v-if="releasePolishSuggestion?.suggestion" class="ai-polish-panel" data-testid="ai-polish-panel">
            <div class="ai-polish-heading">
              <div><span class="eyebrow">REVIEWABLE SUGGESTION</span><h3>AI 润色建议</h3><p>{{ releasePolishSuggestion.suggestion.summary }}</p></div>
              <button class="editor-secondary-button" data-testid="adopt-polish-suggestion" type="button" @click="adoptReleaseNotesSuggestion">载入建议到编辑区</button>
            </div>
            <ul v-if="releasePolishSuggestion.suggestion.changes?.length" class="ai-change-list">
              <li v-for="change in releasePolishSuggestion.suggestion.changes" :key="change">{{ change }}</li>
            </ul>
            <div class="ai-compare-grid">
              <div><span>当前草稿</span><pre>{{ releasePolishSuggestion.suggestion.base_content }}</pre></div>
              <div><span>建议版本</span><pre>{{ releasePolishSuggestion.suggestion.suggested_content }}</pre></div>
            </div>
            <small class="ai-model-note">模型：{{ releasePolishSuggestion.model }} · 建议已保存为独立分析记录</small>
          </section>
        </article>
        <article class="panel detail-panel">
          <div v-if="detailItems.length" class="detail-list">
            <a v-for="item in detailItems" :key="item.id || item.number || item.tag_name" class="detail-row" :href="item.html_url || '#'" target="_blank" rel="noreferrer">
              <span v-if="activeView === 'pull-requests'" class="detail-kicker">#{{ item.number }}</span>
              <span v-else-if="activeView === 'ci'" class="detail-kicker">CI</span>
              <span v-else class="detail-kicker">{{ item.tag_name }}</span>
              <div class="detail-main">
                <strong v-if="activeView === 'pull-requests'">{{ item.title }}</strong>
                <strong v-else-if="activeView === 'ci'">{{ item.workflow_name }}</strong>
                <strong v-else>{{ item.name || item.tag_name }}</strong>
                <p v-if="activeView === 'pull-requests'">{{ item.head_branch || '默认分支' }} · GitHub 同步</p>
                <p v-else-if="activeView === 'ci'">{{ item.branch || '未知分支' }} · {{ item.conclusion || '失败' }} · GitHub 同步</p>
                <p v-else>{{ item.tag_name }} · GitHub 同步</p>
              </div>
              <span class="detail-status">{{ activeView === 'pull-requests' ? '开放 PR' : activeView === 'ci' ? '失败' : '发布记录' }} ↗</span>
            </a>
          </div>
          <div v-else class="empty-state"><div class="empty-icon">⌁</div><strong>暂无{{ detailConfig.title }}</strong><p>{{ boundRepository ? '当前仓库还没有对应 GitHub 数据，请先在 GitHub 产生对应事件，再同步仓库。' : '先绑定一个 GitHub 仓库，再查看质量详情。' }}</p><button v-if="boundRepository" class="empty-link" type="button" @click="activeView = 'overview'">返回总览 <span>↩</span></button></div>
        </article>
      </section>
    </main>
  </div>
</template>

<style>
/* Keep the dashboard usable offline and let each platform use its native system font. */
:root { color: #162b46; background: #f4f8fe; font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Segoe UI", sans-serif; font-synthesis: none; text-rendering: optimizeLegibility; }
* { box-sizing: border-box; } body { margin: 0; min-width: 320px; background: #0a1113; } button, a { font: inherit; } button { color: inherit; } a { color: inherit; text-decoration: none; }
.app-shell { display: flex; min-height: 100vh; background: radial-gradient(circle at 80% 0%, #173237 0, #0a1113 35rem); }
.sidebar { width: 246px; padding: 30px 18px 24px; border-right: 1px solid #233335; display: flex; flex-direction: column; background: rgba(8, 16, 18, .74); }
.brand-block { display: flex; align-items: center; gap: 11px; padding: 0 12px 42px; }.brand-mark { width: 34px; height: 34px; display: grid; place-items: center; border: 1px solid #7fe5c4; color: #071313; background: #8debc9; font-weight: 800; border-radius: 9px; }.brand-block strong { display: block; font-size: 17px; letter-spacing: .02em; }.brand-block span, .eyebrow { color: #77918e; font: 500 10px 'DM Mono', monospace; letter-spacing: .14em; text-transform: uppercase; }
.primary-nav { display: grid; gap: 5px; }.nav-item { display: flex; gap: 12px; align-items: center; border: 0; border-radius: 9px; padding: 12px; background: transparent; color: #8ba09e; text-align: left; cursor: pointer; transition: .2s ease; }.nav-item:hover, .nav-item.active { background: #182b2d; color: #e9f1ef; }.nav-item.active { box-shadow: inset 3px 0 #8debc9; }.nav-icon { width: 19px; color: #8debc9; font-size: 19px; }
.sidebar-note { margin: auto 12px 25px; padding: 17px 0; border-top: 1px solid #233335; border-bottom: 1px solid #233335; }.sidebar-note p { color: #829795; font-size: 12px; line-height: 1.8; margin: 12px 0 0; }.sidebar-footer, .updated-label { display: flex; gap: 8px; align-items: center; color: #76908d; font-size: 11px; }.status-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: #8debc9; box-shadow: 0 0 0 4px rgba(141, 235, 201, .1); }
.main-content { flex: 1; max-width: 1430px; padding: 42px clamp(24px, 5vw, 76px) 60px; margin: 0 auto; }.topbar { display: flex; justify-content: space-between; gap: 30px; align-items: flex-start; } h1, h2, p { margin-top: 0; } h1 { margin: 9px 0 8px; font-size: clamp(27px, 3.2vw, 44px); letter-spacing: -.055em; line-height: 1.1; } h2 { margin: 8px 0 0; font-size: 19px; letter-spacing: -.03em; }.page-subtitle { color: #849a98; font-size: 13px; }.topbar-actions { display: flex; align-items: center; gap: 12px; padding-top: 16px; }.version-pill, .user-pill { border: 1px solid #2b4141; border-radius: 99px; color: #8ca09e; padding: 8px 12px; font: 10px 'DM Mono', monospace; }.login-button { border: 1px solid #8debc9; border-radius: 8px; padding: 10px 15px; color: #071313; background: #8debc9; font-size: 12px; font-weight: 800; }.login-button span, .empty-state a span { margin-left: 9px; }.user-pill { color: #8debc9; }
.workspace-banner { position: relative; overflow: hidden; display: flex; justify-content: space-between; align-items: center; min-height: 194px; margin-top: 48px; padding: 30px 34px; border: 1px solid #294345; border-radius: 15px; background: linear-gradient(110deg, #14292b, #122124 60%, #18383a); }.workspace-banner h2 { font-size: 24px; max-width: 480px; }.workspace-banner p { color: #94aaa7; font-size: 13px; margin: 13px 0 0; }.workspace-orbit { position: relative; width: 160px; height: 130px; margin-right: 45px; }.orbit-core { position: absolute; z-index: 2; inset: 45px 55px; display: grid; place-items: center; border-radius: 50%; background: #8debc9; color: #081314; font: 700 13px 'DM Mono', monospace; }.orbit-ring { position: absolute; border: 1px solid rgba(141, 235, 201, .4); border-radius: 50%; transform: rotate(-20deg); }.ring-one { width: 150px; height: 58px; top: 33px; left: 5px; }.ring-two { width: 130px; height: 85px; top: 20px; left: 15px; transform: rotate(52deg); }
.repository-panel { margin-top: 15px; padding: 22px 24px; border: 1px solid #294345; border-radius: 13px; background: #101c1e; }.repository-status { color: #8debc9; font: 11px 'DM Mono', monospace; }.repository-picker { display: flex; gap: 12px; margin-top: 20px; }.repository-picker select { flex: 1; min-width: 0; border: 1px solid #345153; border-radius: 8px; padding: 12px 14px; color: #dcebe7; background: #0b1517; }.repository-picker button { border: 0; border-radius: 8px; padding: 0 18px; color: #071313; background: #8debc9; font-size: 12px; font-weight: 800; cursor: pointer; }.repository-picker button:disabled { cursor: not-allowed; opacity: .45; }.repository-bound-state { display: flex; justify-content: space-between; gap: 16px; margin-top: 20px; color: #8debc9; font-size: 13px; }.repository-bound-state span, .repository-hint, .repository-error { color: #819997; font-size: 12px; }.repository-error { color: #fb9b8a; }.repository-refresh { margin-top: 15px; padding: 0; }.sync-toolbar { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 12px; align-items: center; margin-top: 15px; color: #8debc9; font-size: 11px; }.sync-toolbar > span:first-child { margin-right: auto; }.sync-toolbar button:disabled { opacity: .5; cursor: not-allowed; }.empty-link { border: 0; color: #8debc9; background: transparent; cursor: pointer; font-size: 12px; font-weight: 700; }
.section-heading, .panel-heading { display: flex; justify-content: space-between; align-items: flex-end; gap: 20px; }.section-heading { margin: 46px 0 17px; }.quality-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; }.quality-card { min-height: 176px; display: flex; flex-direction: column; padding: 20px; border: 1px solid #263b3d; border-radius: 13px; background: #101c1e; }.quality-card.danger { border-top: 2px solid #fb8c78; }.quality-card.accent { border-top: 2px solid #8dbae9; }.quality-card.success { border-top: 2px solid #8debc9; }.card-topline, .card-footer { display: flex; justify-content: space-between; color: #839997; font-size: 12px; }.card-arrow { color: #8debc9; }.card-value { margin: 25px 0 auto; color: #eff9f5; font-size: 43px; letter-spacing: -.08em; }.card-footer { padding-top: 14px; border-top: 1px solid #233335; font-size: 10px; }.card-footer span:last-child { color: #aac0bc; }.card-action { border: 0; padding: 0; color: #aac0bc; background: transparent; cursor: pointer; font-size: 10px; }.card-action:hover { color: #8debc9; }
.release-gate { display: grid; grid-template-columns: minmax(220px, .7fr) 1.5fr; gap: 24px; margin-bottom: 15px; padding: 23px; border: 1px solid #304547; border-left: 3px solid #6c8582; border-radius: 13px; background: linear-gradient(115deg, #111f21, #101a1c); }.release-gate.blocked { border-left-color: #fb8c78; }.release-gate.warning { border-left-color: #e3ba72; }.release-gate.ready { border-left-color: #8debc9; }.gate-summary { display: grid; align-content: start; }.gate-summary h2 { margin-bottom: 16px; }.gate-summary p { margin: 17px 0 0; color: #9aafac; font-size: 12px; line-height: 1.7; }.gate-badge { width: fit-content; border: 1px solid #405557; border-radius: 99px; padding: 7px 10px; color: #bacac7; font: 500 10px 'DM Mono', monospace; }.blocked .gate-badge { border-color: rgba(251, 140, 120, .5); color: #fb9b8a; }.warning .gate-badge { border-color: rgba(227, 186, 114, .5); color: #e3ba72; }.ready .gate-badge { border-color: rgba(141, 235, 201, .5); color: #8debc9; }.gate-checks { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }.gate-check { min-width: 0; padding: 16px; border: 1px solid #2a3e40; border-radius: 10px; background: rgba(7, 17, 19, .45); }.gate-check-heading { display: flex; justify-content: space-between; gap: 10px; align-items: center; }.gate-check-heading strong { font-size: 12px; }.gate-check-heading span { color: #829795; font: 500 9px 'DM Mono', monospace; }.gate-check.fail .gate-check-heading span { color: #fb9b8a; }.gate-check.warning .gate-check-heading span { color: #e3ba72; }.gate-check.pass .gate-check-heading span { color: #8debc9; }.gate-check p { min-height: 44px; margin: 11px 0 0; color: #78908d; font-size: 11px; line-height: 1.65; }.gate-check a { display: inline-block; margin-top: 12px; color: #8debc9; font-size: 10px; }
.lower-grid { display: grid; grid-template-columns: 1.35fr 1fr; gap: 15px; margin-top: 15px; }.panel { min-height: 320px; padding: 23px; border: 1px solid #263b3d; border-radius: 13px; background: #101a1c; }.text-button { border: 0; color: #8debc9; background: transparent; cursor: pointer; font-size: 11px; }.empty-state { min-height: 240px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; }.empty-icon { display: grid; place-items: center; width: 41px; height: 41px; margin-bottom: 15px; border: 1px solid #426462; border-radius: 50%; color: #8debc9; font-size: 23px; }.empty-state strong { font-size: 14px; }.empty-state p { max-width: 320px; margin: 8px 0 18px; color: #78908d; font-size: 12px; line-height: 1.7; }.empty-state a { color: #8debc9; font-size: 12px; font-weight: 700; }.activity-list { display: grid; gap: 0; margin-top: 18px; }.activity-row { display: grid; grid-template-columns: 68px minmax(0, 1fr) auto 18px; align-items: center; gap: 10px; padding: 13px 0; border-bottom: 1px solid #243638; color: #dcebe7; font-size: 12px; }.activity-label { color: #8debc9; font: 10px 'DM Mono', monospace; }.activity-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.activity-detail { color: #78908d; font-size: 11px; }.playbook-list { padding: 6px 0 0; margin: 0; list-style: none; }.playbook-list li { display: flex; gap: 16px; padding: 17px 0; border-bottom: 1px solid #243638; }.playbook-list li:last-child { border-bottom: 0; }.playbook-list li > span { color: #5e7b77; font: 11px 'DM Mono', monospace; }.playbook-list strong { font-size: 12px; }.playbook-list p { margin: 5px 0 0; color: #78908d; font-size: 11px; line-height: 1.6; }.detail-heading { align-items: flex-start; }.detail-heading p { max-width: 560px; margin: 8px 0 0; color: #78908d; font-size: 12px; line-height: 1.7; }.detail-panel { min-height: 320px; }.detail-list { display: grid; }.detail-row { display: grid; grid-template-columns: 78px minmax(0, 1fr) auto; align-items: center; gap: 18px; padding: 20px 0; border-bottom: 1px solid #243638; }.detail-row:last-child { border-bottom: 0; }.detail-kicker { color: #8debc9; font: 11px 'DM Mono', monospace; }.detail-main { min-width: 0; }.detail-main strong { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; }.detail-main p { margin: 6px 0 0; color: #78908d; font-size: 11px; }.detail-status { color: #aac0bc; font-size: 11px; white-space: nowrap; }
.release-checklist { min-height: auto; margin-bottom: 15px; border-left: 3px solid #647c79; }
.release-checklist.blocked { border-left-color: #fb8c78; }
.release-checklist.warning, .release-checklist.pending { border-left-color: #e3ba72; }
.release-checklist.ready { border-left-color: #8debc9; }
.checklist-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; }
.checklist-heading h2 { margin: 8px 0 7px; }
.checklist-heading p { max-width: 650px; margin: 0; color: #829795; font-size: 12px; line-height: 1.7; }
.checklist-result { display: grid; grid-template-columns: auto auto; align-items: center; gap: 3px 12px; text-align: right; }
.checklist-result strong { font: 700 20px 'DM Mono', monospace; }
.checklist-result small { grid-column: 2; color: #78908d; font-size: 9px; }
.checklist-badge { grid-row: 1 / span 2; border: 1px solid #405557; border-radius: 99px; padding: 7px 10px; color: #bacac7; font: 500 9px 'DM Mono', monospace; }
.blocked .checklist-badge { border-color: rgba(251, 140, 120, .5); color: #fb9b8a; }
.warning .checklist-badge, .pending .checklist-badge { border-color: rgba(227, 186, 114, .5); color: #e3ba72; }
.ready .checklist-badge { border-color: rgba(141, 235, 201, .5); color: #8debc9; }
.progress-track { height: 4px; margin: 20px 0; overflow: hidden; border-radius: 99px; background: #243638; }
.progress-track span { display: block; height: 100%; border-radius: inherit; background: #8debc9; transition: width .25s ease; }
.checklist-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.checklist-group { overflow: hidden; border: 1px solid #293e40; border-radius: 10px; background: rgba(7, 17, 19, .36); }
.checklist-group-heading { display: flex; justify-content: space-between; gap: 12px; padding: 13px 15px; border-bottom: 1px solid #293e40; color: #dcebe7; font-size: 11px; font-weight: 700; }
.checklist-group-heading small { color: #78908d; font-size: 9px; font-weight: 500; }
.checklist-row { position: relative; display: grid; grid-template-columns: 28px minmax(0, 1fr) auto; align-items: center; gap: 9px; min-height: 76px; padding: 12px 14px; border-bottom: 1px solid #243638; }
.checklist-row:last-child { border-bottom: 0; }
.checklist-row strong { display: block; font-size: 11px; }
.checklist-row p { margin: 5px 0 0; color: #78908d; font-size: 9px; line-height: 1.55; }
.checklist-row > small { color: #829795; font: 9px 'DM Mono', monospace; }
.check-indicator, .manual-checkbox { display: grid; place-items: center; width: 24px; height: 24px; border: 1px solid #405557; border-radius: 50%; color: #829795; font: 700 11px 'DM Mono', monospace; }
.checklist-row.pass .check-indicator { border-color: rgba(141, 235, 201, .5); color: #8debc9; }
.checklist-row.warning .check-indicator { border-color: rgba(227, 186, 114, .5); color: #e3ba72; }
.checklist-row.fail .check-indicator { border-color: rgba(251, 140, 120, .5); color: #fb9b8a; }
.checklist-row.manual { grid-template-columns: 28px minmax(0, 1fr); cursor: pointer; }
.checklist-row.manual input { position: absolute; width: 1px; height: 1px; opacity: 0; }
.checklist-row.manual input:focus-visible + .manual-checkbox { outline: 2px solid #8debc9; outline-offset: 2px; }
.checklist-row.manual input:disabled + .manual-checkbox { opacity: .45; }
.checklist-row.manual.confirmed .manual-checkbox { border-color: #8debc9; color: #071313; background: #8debc9; }
.checklist-audit { margin-top: 14px; padding-top: 12px; border-top: 1px solid #243638; color: #78908d; font: 9px 'DM Mono', monospace; }
.release-editor { min-height: auto; margin-bottom: 15px; }
.release-editor-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; }
.release-editor-heading h2 { margin: 8px 0 7px; }
.release-editor-heading p { max-width: 620px; margin: 0; color: #78908d; font-size: 12px; line-height: 1.7; }
.draft-safety-badge { flex: none; border: 1px solid rgba(141, 235, 201, .35); border-radius: 99px; padding: 7px 10px; color: #8debc9; font: 500 9px 'DM Mono', monospace; }
.release-editor-toolbar { display: grid; grid-template-columns: minmax(190px, 1fr) repeat(3, auto); align-items: end; gap: 10px; margin: 24px 0 16px; }
.version-field, .markdown-editor { display: grid; gap: 8px; color: #91a6a3; font-size: 11px; }
.version-field input, .markdown-editor textarea { width: 100%; border: 1px solid #304547; border-radius: 9px; outline: none; color: #e9f1ef; background: #0b1517; }
.version-field input { min-height: 42px; padding: 0 13px; }
.markdown-editor textarea { min-height: 330px; padding: 15px; resize: vertical; font: 12px/1.75 'DM Mono', monospace; }
.version-field input:focus, .markdown-editor textarea:focus { border-color: #8debc9; box-shadow: 0 0 0 3px rgba(141, 235, 201, .08); }
.version-field input:disabled, .markdown-editor textarea:disabled { opacity: .55; cursor: not-allowed; }
.editor-primary-button, .editor-secondary-button { min-height: 42px; border-radius: 9px; padding: 0 16px; cursor: pointer; font-size: 11px; font-weight: 700; }
.editor-primary-button { border: 1px solid #8debc9; color: #071313; background: #8debc9; }
.editor-secondary-button { border: 1px solid #3b5153; color: #c8d8d4; background: transparent; }
.editor-ai-button { min-height: 42px; border: 1px solid #8dbae9; border-radius: 9px; padding: 0 16px; color: #c9ddf3; background: rgba(141, 186, 233, .08); cursor: pointer; font-size: 11px; font-weight: 700; }
.editor-primary-button:disabled, .editor-secondary-button:disabled, .editor-ai-button:disabled { opacity: .45; cursor: not-allowed; }
.draft-message { margin: 8px 0 15px; color: #91a6a3; font-size: 11px; }
.draft-message.success { color: #8debc9; }
.draft-message.error { color: #fb9b8a; }
.release-editor-grid { display: grid; grid-template-columns: minmax(0, 1.55fr) minmax(250px, .75fr); gap: 15px; }
.release-sources { min-width: 0; border: 1px solid #293e40; border-radius: 10px; padding: 17px; background: rgba(7, 17, 19, .45); }
.source-summary { padding-bottom: 14px; border-bottom: 1px solid #243638; }
.source-summary strong { display: block; margin-top: 9px; font-size: 14px; }
.source-summary p, .source-empty { margin: 7px 0 0; color: #78908d; font-size: 10px; line-height: 1.7; }
.source-list { display: grid; }
.source-list a { display: grid; grid-template-columns: 38px minmax(0, 1fr); gap: 5px 8px; padding: 13px 0; border-bottom: 1px solid #243638; }
.source-list a:last-child { border-bottom: 0; }
.source-list span { grid-row: 1 / span 2; color: #8debc9; font: 10px 'DM Mono', monospace; }
.source-list strong { overflow: hidden; color: #dcebe7; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.source-list small { color: #78908d; font-size: 9px; }
.ai-polish-panel { margin-top: 15px; border: 1px solid #3b5262; border-radius: 10px; padding: 18px; background: linear-gradient(120deg, rgba(24, 42, 54, .68), rgba(12, 25, 29, .6)); }
.ai-polish-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; }
.ai-polish-heading h3 { margin: 8px 0 6px; font-size: 14px; }
.ai-polish-heading p { margin: 0; color: #a6bdc9; font-size: 11px; line-height: 1.6; }
.ai-change-list { display: flex; flex-wrap: wrap; gap: 7px; padding: 0; margin: 16px 0; list-style: none; }
.ai-change-list li { border: 1px solid #385263; border-radius: 99px; padding: 6px 9px; color: #b8d1e3; font-size: 9px; }
.ai-compare-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.ai-compare-grid > div { min-width: 0; }
.ai-compare-grid > div > span { display: block; margin-bottom: 7px; color: #8faab9; font: 500 9px 'DM Mono', monospace; text-transform: uppercase; }
.ai-compare-grid pre { min-height: 170px; max-height: 310px; overflow: auto; margin: 0; border: 1px solid #304752; border-radius: 8px; padding: 12px; color: #d2e0e5; background: rgba(5, 13, 16, .58); white-space: pre-wrap; word-break: break-word; font: 10px/1.7 'DM Mono', monospace; }
.ai-model-note { display: block; margin-top: 12px; color: #718b96; font-size: 9px; }
@media (max-width: 900px) { .sidebar { width: 190px; }.workspace-orbit { margin-right: 0; transform: scale(.8); }.release-gate { grid-template-columns: 1fr; }.lower-grid, .release-editor-grid, .checklist-grid { grid-template-columns: 1fr; }.markdown-editor textarea { min-height: 280px; } }
@media (max-width: 680px) { .app-shell { display: block; }.sidebar { width: auto; padding: 16px; border-right: 0; border-bottom: 1px solid #233335; }.brand-block { padding: 0 5px 15px; }.primary-nav { grid-template-columns: repeat(3, 1fr); }.nav-item { justify-content: center; padding: 8px 4px; font-size: 11px; }.nav-icon, .sidebar-note, .sidebar-footer { display: none; }.main-content { padding: 28px 16px 40px; }.topbar { display: block; }.topbar-actions { padding-top: 14px; }.workspace-banner { min-height: 170px; margin-top: 28px; padding: 23px; }.workspace-orbit { display: none; }.repository-picker { display: grid; }.repository-picker button { min-height: 42px; }.repository-bound-state { display: grid; gap: 6px; }.gate-checks, .quality-grid { grid-template-columns: 1fr; }.quality-card { min-height: 145px; }.section-heading { margin-top: 32px; }.detail-heading { display: block; }.detail-heading .text-button { margin-top: 18px; }.detail-row { grid-template-columns: 48px minmax(0, 1fr); gap: 10px; }.detail-status { grid-column: 2; }.detail-main strong { white-space: normal; }.release-editor-heading, .checklist-heading { display: grid; }.checklist-result { width: fit-content; text-align: left; }.draft-safety-badge { width: fit-content; }.release-editor-toolbar { grid-template-columns: 1fr 1fr; }.version-field { grid-column: 1 / -1; }.editor-primary-button, .editor-secondary-button, .editor-ai-button { padding: 0 10px; }.markdown-editor textarea { min-height: 240px; }.ai-polish-heading { display: grid; }.ai-compare-grid { grid-template-columns: 1fr; } }
/* Guided workflow layer: keep the existing visual language, but make the next action obvious. */
.next-action-card { display: flex; justify-content: space-between; align-items: center; gap: 28px; margin-top: 15px; padding: 22px 24px; border: 1px solid #365759; border-radius: 14px; background: linear-gradient(105deg, rgba(28, 57, 57, .92), rgba(14, 27, 30, .96)); box-shadow: 0 18px 45px rgba(0, 0, 0, .12); }
.next-action-card.login { border-color: #507a77; }
.next-action-card.bind, .next-action-card.sync, .next-action-card.release { border-color: #416c68; }
.next-action-copy { min-width: 0; }
.next-action-copy h2 { margin: 8px 0 7px; color: #f2faf6; font-size: 18px; }
.next-action-copy p { max-width: 690px; margin: 0; color: #a6beb8; font-size: 12px; line-height: 1.75; }
.next-action-cta { display: grid; flex: none; justify-items: end; gap: 9px; }
.next-action-cta > span { color: #75928d; font: 9px 'DM Mono', monospace; letter-spacing: .12em; text-transform: uppercase; }
.primary-action { display: inline-flex; align-items: center; gap: 12px; min-height: 42px; border: 1px solid #8debc9; border-radius: 9px; padding: 0 15px; color: #071313; background: #8debc9; font-size: 11px; font-weight: 800; cursor: pointer; box-shadow: 0 8px 20px rgba(141, 235, 201, .12); }
.primary-action span { font-size: 16px; line-height: 1; }
.primary-action:hover { background: #b3f5dd; transform: translateY(-1px); }
.primary-action:disabled { cursor: wait; opacity: .55; transform: none; }
.workflow-strip { display: grid; grid-template-columns: minmax(190px, .7fr) minmax(0, 1.8fr); gap: 20px; margin-top: 15px; padding: 17px 20px; border: 1px solid #263e40; border-radius: 13px; background: rgba(13, 26, 28, .78); }
.workflow-intro { display: grid; align-content: center; gap: 7px; padding-right: 12px; border-right: 1px solid #263e40; }
.workflow-intro strong { color: #dcebe7; font-size: 13px; }
.workflow-intro small { color: #78908d; font-size: 10px; line-height: 1.6; }
.workflow-steps { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; padding: 0; margin: 0; list-style: none; }
.workflow-steps li { position: relative; display: grid; grid-template-columns: 27px minmax(0, 1fr); gap: 8px; min-width: 0; padding: 3px 7px; }
.workflow-steps li + li::before { position: absolute; top: 13px; left: -4px; width: 7px; height: 1px; content: ''; background: #355052; }
.workflow-number { display: grid; place-items: center; width: 26px; height: 26px; border: 1px solid #3d5859; border-radius: 50%; color: #87a6a0; font: 10px 'DM Mono', monospace; }
.workflow-steps li div { min-width: 0; }
.workflow-steps strong { display: block; overflow: hidden; color: #a9bfba; font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
.workflow-steps small { display: block; overflow: hidden; margin-top: 4px; color: #637d79; font-size: 9px; line-height: 1.45; text-overflow: ellipsis; white-space: nowrap; }
.workflow-status { grid-column: 2; color: #637d79; font: 8px 'DM Mono', monospace; }
.workflow-steps li.done .workflow-number { border-color: #8debc9; color: #071313; background: #8debc9; }
.workflow-steps li.done strong, .workflow-steps li.done .workflow-status { color: #8debc9; }
.workflow-steps li.current .workflow-number { border-color: #8dbae9; color: #c9ddf3; box-shadow: 0 0 0 4px rgba(141, 186, 233, .08); }
.workflow-steps li.current strong, .workflow-steps li.current .workflow-status { color: #c9ddf3; }
.workflow-steps li.locked { opacity: .58; }
.panel-helper { margin: 8px 0 0; color: #78908d; font-size: 10px; line-height: 1.6; }
.section-helper { margin: 7px 0 0; color: #78908d; font-size: 11px; line-height: 1.6; }
.gate-help { display: block; margin-top: 13px; color: #78908d; font-size: 10px; line-height: 1.6; }
.card-description { min-height: 30px; margin: 4px 0 12px; color: #78908d; font-size: 10px; line-height: 1.5; }
.quality-card:hover { border-color: #3f5b5c; background: #122123; transform: translateY(-2px); transition: .2s ease; }
.quality-card:focus-within, .panel:focus-within { border-color: #4f706f; }
.text-button:hover, .empty-link:hover { color: #c0f8e4; }
.repository-panel, .panel, .release-gate { box-shadow: 0 14px 34px rgba(0, 0, 0, .08); }
.release-flow-guide { margin-bottom: 15px; padding: 19px 22px; border: 1px solid #2c484a; border-radius: 13px; background: linear-gradient(105deg, rgba(19, 39, 41, .92), rgba(13, 26, 29, .88)); }
.release-flow-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; }
.release-flow-heading h2 { margin: 8px 0 0; font-size: 16px; }
.release-flow-heading small { color: #78908d; font-size: 10px; }
.release-flow-steps { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0; padding: 0; margin: 20px 0 0; list-style: none; }
.release-flow-steps li { position: relative; display: grid; grid-template-columns: 29px minmax(0, 1fr) auto; align-items: center; gap: 9px; min-width: 0; padding: 0 13px; }
.release-flow-steps li:first-child { padding-left: 0; }
.release-flow-steps li:last-child { padding-right: 0; }
.release-flow-steps li:not(:last-child)::after { position: absolute; top: 14px; right: -2px; width: 15px; height: 1px; content: ''; background: #355052; }
.release-flow-steps li > span { display: grid; place-items: center; width: 28px; height: 28px; border: 1px solid #3d5859; border-radius: 50%; color: #89a6a0; font: 10px 'DM Mono', monospace; }
.release-flow-steps li > div { min-width: 0; }
.release-flow-steps strong { display: block; color: #b6c9c4; font-size: 10px; }
.release-flow-steps small { display: block; overflow: hidden; margin-top: 4px; color: #68827e; font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }
.release-flow-steps b { color: #68827e; font: 8px 'DM Mono', monospace; white-space: nowrap; }
.release-flow-steps li.done > span { border-color: #8debc9; color: #071313; background: #8debc9; }
.release-flow-steps li.done strong, .release-flow-steps li.done b { color: #8debc9; }
.release-flow-steps li.current > span { border-color: #8dbae9; color: #c9ddf3; box-shadow: 0 0 0 4px rgba(141, 186, 233, .08); }
.release-flow-steps li.current strong, .release-flow-steps li.current b { color: #c9ddf3; }
.release-flow-steps li.locked { opacity: .55; }
.editor-hint { margin: 0 0 15px; padding: 10px 12px; border-left: 2px solid #4b6c6c; color: #78908d; background: rgba(32, 54, 55, .35); font-size: 10px; line-height: 1.65; }
.editor-hint span { margin-right: 9px; color: #b8d1c9; font-weight: 700; }
.version-field input::placeholder, .markdown-editor textarea::placeholder { color: #4f6967; }
.editor-primary-button:hover:not(:disabled), .editor-secondary-button:hover:not(:disabled), .editor-ai-button:hover:not(:disabled) { transform: translateY(-1px); transition: .18s ease; }
@media (max-width: 900px) { .workflow-strip { grid-template-columns: 1fr; }.workflow-intro { padding-right: 0; padding-bottom: 12px; border-right: 0; border-bottom: 1px solid #263e40; }.release-flow-steps { grid-template-columns: repeat(2, 1fr); gap: 17px 0; }.release-flow-steps li:nth-child(2)::after { display: none; }.release-flow-steps li:nth-child(3) { padding-left: 0; }.release-flow-steps li:nth-child(4) { padding-right: 0; } }
@media (max-width: 680px) { .next-action-card { display: grid; gap: 18px; padding: 19px; }.next-action-cta { justify-items: stretch; }.primary-action { justify-content: center; }.workflow-steps { grid-template-columns: repeat(2, 1fr); gap: 15px 5px; }.workflow-steps li + li::before { display: none; }.workflow-steps li { padding: 0 3px; }.release-flow-guide { padding: 17px; }.release-flow-heading { display: grid; gap: 8px; }.release-flow-steps { grid-template-columns: 1fr; gap: 12px; }.release-flow-steps li, .release-flow-steps li:nth-child(3) { padding: 0; }.release-flow-steps li:not(:last-child)::after { top: auto; right: auto; bottom: -9px; left: 14px; width: 1px; height: 7px; }.release-flow-steps li:nth-child(2)::after { display: block; }.card-description { min-height: 0; } }
/* Apple-inspired light system: high whitespace, calm surfaces and one clear system-blue action. */
:root {
  --ios-blue: #007aff;
  --ios-blue-dark: #0066d6;
  --ios-blue-soft: #eaf4ff;
  --ios-sky: #d9edff;
  --ios-ink: #162b46;
  --ios-muted: #66809d;
  --ios-faint: #8fa5bd;
  --ios-border: #d9e6f3;
  --ios-surface: rgba(255, 255, 255, .86);
  --ios-shadow: 0 18px 45px rgba(39, 93, 145, .10);
}

html { background: #f4f8fe; }
body { min-width: 320px; color: var(--ios-ink); background: #f4f8fe; }
button, input, select, textarea { font-family: inherit; }
button, a { -webkit-tap-highlight-color: transparent; }
a { color: inherit; }
:focus-visible { outline: 3px solid rgba(0, 122, 255, .28); outline-offset: 3px; }

.app-shell {
  min-height: 100vh;
  background:
    radial-gradient(circle at 83% -8%, rgba(190, 225, 255, .70), transparent 31rem),
    linear-gradient(135deg, #f7fbff 0%, #f1f6fd 48%, #eef5fd 100%);
}

.sidebar {
  position: sticky;
  top: 0;
  z-index: 5;
  width: 252px;
  min-height: 100vh;
  padding: 28px 16px 22px;
  border-right: 1px solid rgba(199, 217, 234, .85);
  background: rgba(250, 253, 255, .78);
  box-shadow: 10px 0 35px rgba(58, 111, 160, .04);
  backdrop-filter: blur(24px);
}
.brand-block { gap: 12px; padding: 0 12px 42px; }
.brand-mark {
  width: 38px;
  height: 38px;
  border: 0;
  border-radius: 12px;
  color: #fff;
  background: linear-gradient(145deg, #54b7ff, #007aff);
  box-shadow: 0 8px 18px rgba(0, 122, 255, .22);
  font-size: 17px;
}
.brand-block strong { color: var(--ios-ink); font-size: 17px; letter-spacing: -.02em; }
.brand-block span, .eyebrow {
  color: #7894b0;
  font-family: inherit;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: .14em;
}
.primary-nav { gap: 7px; }
.nav-item {
  min-height: 45px;
  gap: 12px;
  border: 1px solid transparent;
  border-radius: 13px;
  padding: 11px 13px;
  color: #6d86a1;
  font-size: 13px;
  font-weight: 600;
}
.nav-item:hover { color: var(--ios-blue); background: rgba(226, 241, 255, .72); }
.nav-item.active {
  color: var(--ios-blue);
  background: #e5f2ff;
  border-color: #cfe6fb;
  box-shadow: none;
}
.nav-icon {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: 8px;
  color: var(--ios-blue);
  background: rgba(0, 122, 255, .09);
  font-size: 16px;
}
.sidebar-note { margin: auto 12px 25px; padding: 17px 0; border-color: #dbe8f4; }
.sidebar-note p { color: var(--ios-muted); font-size: 11px; line-height: 1.75; }
.sidebar-footer, .updated-label { color: #7893ae; font-size: 10px; }
.status-dot { width: 7px; height: 7px; background: #34c759; box-shadow: 0 0 0 4px rgba(52, 199, 89, .12); }

.main-content { max-width: 1510px; padding: 38px clamp(24px, 5vw, 76px) 68px; }
.topbar { gap: 30px; }
h1 { margin: 10px 0 8px; color: #102844; font-size: clamp(29px, 3.15vw, 46px); font-weight: 750; letter-spacing: -.065em; }
h2 { color: #1a3451; font-size: 20px; font-weight: 720; letter-spacing: -.04em; }
.page-subtitle { color: #7690ab; font-size: 13px; }
.topbar-actions { gap: 10px; padding-top: 13px; }
.version-pill, .user-pill {
  border: 1px solid #d6e4f2;
  border-radius: 99px;
  padding: 8px 12px;
  color: #6d87a3;
  background: rgba(255, 255, 255, .67);
  font-family: inherit;
  font-size: 10px;
  font-weight: 650;
}
.user-pill { color: var(--ios-blue); background: #e8f4ff; border-color: #cde5fb; }
.login-button {
  border: 0;
  border-radius: 11px;
  padding: 11px 16px;
  color: #fff;
  background: var(--ios-blue);
  box-shadow: 0 8px 18px rgba(0, 122, 255, .18);
  font-size: 12px;
  font-weight: 720;
}
.login-button:hover { background: var(--ios-blue-dark); transform: translateY(-1px); }

.workspace-banner {
  min-height: 200px;
  margin-top: 44px;
  padding: 33px 36px;
  border: 1px solid #cfe4f7;
  border-radius: 24px;
  background:
    radial-gradient(circle at 92% 45%, rgba(255, 255, 255, .70), transparent 12rem),
    linear-gradient(118deg, #e9f5ff 0%, #d8edff 57%, #c7e6ff 100%);
  box-shadow: var(--ios-shadow);
}
.workspace-banner h2 { max-width: 600px; margin-top: 10px; color: #123253; font-size: clamp(22px, 2.25vw, 31px); }
.workspace-banner p { margin-top: 13px; color: #5d7a98; font-size: 13px; }
.workspace-orbit { margin-right: 43px; }
.orbit-core { inset: 43px 51px; width: 58px; height: 58px; color: #fff; background: linear-gradient(145deg, #55b9ff, #007aff); box-shadow: 0 10px 24px rgba(0, 122, 255, .24); font-family: inherit; font-size: 14px; }
.orbit-ring { border-color: rgba(0, 122, 255, .22); }

.repository-panel, .panel, .release-gate {
  border-color: var(--ios-border);
  border-radius: 20px;
  background: var(--ios-surface);
  box-shadow: var(--ios-shadow);
  backdrop-filter: blur(18px);
}
.repository-panel { margin-top: 15px; padding: 24px 26px; }
.panel-heading h2 { color: #1b3652; }
.panel-helper, .section-helper, .detail-heading p, .gate-help { color: var(--ios-muted); }
.repository-status { color: #279a51; font-family: inherit; font-size: 11px; font-weight: 700; }
.repository-bound-state { gap: 14px; padding: 16px 0 0; align-items: flex-end; }
.repository-selection { display: grid; flex: 1; min-width: 0; gap: 6px; }
.repository-selection > span { color: #6e89a4; font-size: 11px; }
.repository-selection select { width: min(100%, 620px); padding: 13px 14px; border: 1px solid #cfe0ef; border-radius: 13px; color: #244461; background: rgba(255, 255, 255, .92); box-shadow: inset 0 1px 2px rgba(36, 75, 112, .03); font-weight: 650; }
.repository-selection select:focus, .repository-picker select:focus { outline: 3px solid rgba(0, 122, 255, .16); outline-offset: 1px; }
.repository-selection small { color: #6e89a4; font-size: 11px; }
.repository-switch-button { flex: 0 0 auto; padding: 0 0 3px; white-space: nowrap; }
.sync-toolbar { margin-top: 16px; padding-top: 14px; border-top-color: #e3edf6; }
.sync-toolbar > span { color: #6e89a4; font-size: 11px; }
.text-button, .empty-link, .card-action { color: var(--ios-blue); font-weight: 650; }
.text-button:hover, .empty-link:hover, .card-action:hover { color: var(--ios-blue-dark); }
.repository-picker { margin-top: 20px; }
.repository-picker select, .version-field input, .markdown-editor textarea {
  border: 1px solid #cfe0ef;
  border-radius: 13px;
  color: #244461;
  background: rgba(255, 255, 255, .92);
  box-shadow: inset 0 1px 2px rgba(36, 75, 112, .03);
}
.repository-picker select { padding: 13px 14px; }
.repository-picker button {
  min-height: 44px;
  border: 0;
  border-radius: 12px;
  padding: 0 19px;
  color: #fff;
  background: var(--ios-blue);
  box-shadow: 0 7px 15px rgba(0, 122, 255, .16);
  font-size: 12px;
  font-weight: 720;
}
.repository-picker button:hover:not(:disabled) { background: var(--ios-blue-dark); transform: translateY(-1px); }
.repository-picker button:disabled, .text-button:disabled, .empty-link:disabled { opacity: .48; cursor: not-allowed; }
.repository-hint, .repository-error { color: #6e89a4; font-size: 11px; }
.repository-error, .draft-message.error { color: #d94d57; }

.next-action-card {
  margin-top: 15px;
  padding: 25px 27px;
  border: 1px solid #bedfff;
  border-radius: 20px;
  background: linear-gradient(110deg, rgba(231, 245, 255, .96), rgba(248, 252, 255, .95));
  box-shadow: var(--ios-shadow);
}
.next-action-card.login { border-color: #bedfff; }
.next-action-copy h2 { color: #123457; font-size: 20px; }
.next-action-copy p { color: #5c7896; }
.next-action-cta > span { color: #7390ad; font-family: inherit; font-size: 9px; font-weight: 700; letter-spacing: .12em; }
.primary-action {
  min-height: 44px;
  border: 0;
  border-radius: 12px;
  padding: 0 17px;
  color: #fff;
  background: var(--ios-blue);
  box-shadow: 0 8px 18px rgba(0, 122, 255, .18);
}
.primary-action:hover { color: #fff; background: var(--ios-blue-dark); }

.workflow-strip, .release-flow-guide {
  border: 1px solid var(--ios-border);
  border-radius: 18px;
  background: rgba(255, 255, 255, .74);
  box-shadow: 0 12px 30px rgba(40, 91, 141, .06);
}
.workflow-strip { margin-top: 15px; padding: 18px 20px; }
.workflow-intro { border-color: #e1ebf4; }
.workflow-intro strong { color: #274664; }
.workflow-intro small { color: #7892ac; }
.workflow-steps li + li::before { background: #cddcea; }
.workflow-number { border-color: #c8d9e9; color: #7893ae; }
.workflow-steps strong { color: #52718f; }
.workflow-steps small, .workflow-status { color: #8aa0b8; }
.workflow-steps li.done .workflow-number { border-color: #34c759; color: #fff; background: #34c759; }
.workflow-steps li.done strong, .workflow-steps li.done .workflow-status { color: #26954a; }
.workflow-steps li.current .workflow-number { border-color: var(--ios-blue); color: var(--ios-blue); background: #edf6ff; box-shadow: 0 0 0 4px rgba(0, 122, 255, .10); }
.workflow-steps li.current strong, .workflow-steps li.current .workflow-status { color: var(--ios-blue); }

.section-heading { margin-top: 37px; }
.updated-label { color: #7691ab; }
.release-gate { grid-template-columns: minmax(230px, .72fr) minmax(0, 1.4fr); padding: 23px 25px; }
.release-gate.blocked { border-color: #f3cbd0; background: rgba(255, 250, 250, .88); }
.release-gate.warning { border-color: #f2dfb9; background: rgba(255, 253, 247, .90); }
.release-gate.ready { border-color: #bee8cb; background: rgba(249, 255, 251, .90); }
.gate-summary { padding-right: 22px; border-color: #e0eaf3; }
.gate-summary h2 { color: #1b3652; }
.gate-summary p, .gate-help { color: #6b849e; }
.gate-badge, .checklist-badge { border-color: #c8d9e8; color: #6c86a1; background: rgba(255, 255, 255, .6); font-family: inherit; font-size: 10px; font-weight: 700; }
.blocked .gate-badge, .blocked .checklist-badge { border-color: #efb9bf; color: #c94754; }
.warning .gate-badge, .warning .checklist-badge { border-color: #e9cc8e; color: #ad7510; }
.ready .gate-badge, .ready .checklist-badge { border-color: #a9ddba; color: #238b45; }
.gate-checks { gap: 10px; }
.gate-check { border-color: #e0eaf3; border-radius: 14px; padding: 14px 15px; background: rgba(255, 255, 255, .64); }
.gate-check-heading strong { color: #365672; }
.gate-check-heading span { font-family: inherit; font-size: 10px; font-weight: 700; }
.gate-check p { color: #6e89a4; }
.gate-check a { color: var(--ios-blue); }
.gate-check.pass { border-color: #ccebd5; background: #f7fdf9; }
.gate-check.pass .gate-check-heading span { color: #26954a; }
.gate-check.warning { border-color: #f1e1be; background: #fffdf8; }
.gate-check.warning .gate-check-heading span { color: #ad7510; }
.gate-check.fail { border-color: #f3cbd0; background: #fff9fa; }
.gate-check.fail .gate-check-heading span { color: #c94754; }

.quality-grid { gap: 15px; }
.quality-card {
  min-height: 170px;
  border: 1px solid var(--ios-border);
  border-top: 3px solid #bed8f1;
  border-radius: 18px;
  padding: 21px 22px 17px;
  background: rgba(255, 255, 255, .88);
  box-shadow: var(--ios-shadow);
}
.quality-card.danger { border-top-color: #ff8c94; }
.quality-card.accent { border-top-color: #70b7ff; }
.quality-card.success { border-top-color: #65d68a; }
.quality-card:hover { border-color: #b5d5f1; border-top-color: #70b7ff; background: #fff; transform: translateY(-3px); }
.card-topline span:first-child { color: #61809d; font-size: 12px; font-weight: 650; }
.card-arrow { color: var(--ios-blue); }
.card-value { color: #173654; font-size: 47px; font-weight: 720; letter-spacing: -.08em; }
.card-description { color: #7892ad; }
.card-footer { border-color: #e4edf5; color: #8aa0b7; }
.card-action { font-size: 10px; }

.lower-grid { gap: 15px; }
.panel { padding: 23px 26px; }
.activity-row { border-color: #e4edf5; color: #365570; }
.activity-row:hover { background: #f4f9ff; }
.activity-label { color: var(--ios-blue); font-family: inherit; font-size: 10px; font-weight: 750; }
.activity-detail, .playbook-list p { color: #7892ad; }
.playbook-list li { border-color: #e4edf5; }
.playbook-list li > span { color: #8aa2ba; font-family: inherit; font-size: 11px; font-weight: 700; }
.playbook-list strong { color: #385774; }
.empty-icon { border-color: #c9e0f4; color: var(--ios-blue); background: #edf7ff; }
.empty-state strong { color: #41617e; }
.empty-state p { color: #7892ad; }

.detail-heading { margin-top: 37px; }
.detail-panel { min-height: 320px; }
.detail-row { border-color: #e4edf5; }
.detail-row:hover { background: #f6faff; }
.detail-kicker { color: var(--ios-blue); font-family: inherit; font-size: 11px; font-weight: 750; }
.detail-main strong { color: #365570; }
.detail-main p, .detail-status { color: #7892ad; }

.release-flow-guide { margin-bottom: 15px; padding: 21px 24px; background: linear-gradient(110deg, #f2f8ff, #fff); }
.release-flow-heading h2 { color: #254967; }
.release-flow-heading small { color: #7892ad; }
.release-flow-steps li:not(:last-child)::after { background: #cbdbea; }
.release-flow-steps li > span { border-color: #c6d9ea; color: #7893ae; background: #fff; }
.release-flow-steps strong { color: #52718e; }
.release-flow-steps small, .release-flow-steps b { color: #8aa1b8; font-family: inherit; }
.release-flow-steps li.done > span { border-color: #34c759; color: #fff; background: #34c759; }
.release-flow-steps li.done strong, .release-flow-steps li.done b { color: #26954a; }
.release-flow-steps li.current > span { border-color: var(--ios-blue); color: var(--ios-blue); background: #edf6ff; box-shadow: 0 0 0 4px rgba(0, 122, 255, .10); }
.release-flow-steps li.current strong, .release-flow-steps li.current b { color: var(--ios-blue); }

.release-checklist { border-left: 3px solid #c4d9eb; }
.release-checklist.blocked { border-left-color: #ff8c94; }
.release-checklist.warning, .release-checklist.pending { border-left-color: #e8bd67; }
.release-checklist.ready { border-left-color: #65d68a; }
.checklist-heading p, .checklist-result small { color: #7892ad; }
.checklist-result strong { color: #264663; font-family: inherit; }
.progress-track { background: #e6eef6; }
.progress-track span { background: linear-gradient(90deg, #6fc1ff, var(--ios-blue)); }
.checklist-group { border-color: #dce8f2; border-radius: 14px; background: rgba(249, 252, 255, .75); }
.checklist-group-heading { border-color: #e1ebf4; color: #3e5c78; }
.checklist-group-heading small { color: #829ab2; }
.checklist-row { border-color: #e5edf5; }
.checklist-row strong { color: #3c5a77; }
.checklist-row p, .checklist-row > small { color: #7892ad; }
.check-indicator, .manual-checkbox { border-color: #c6d9e9; color: #7f98b0; background: #fff; }
.checklist-row.pass .check-indicator { border-color: #9bd9ae; color: #26954a; background: #f5fdf7; }
.checklist-row.warning .check-indicator { border-color: #e7c87e; color: #b37812; background: #fffaf0; }
.checklist-row.fail .check-indicator { border-color: #efb7be; color: #c94754; background: #fff7f8; }
.checklist-row.manual.confirmed .manual-checkbox { border-color: var(--ios-blue); color: #fff; background: var(--ios-blue); }
.checklist-row.manual input:focus-visible + .manual-checkbox { outline-color: rgba(0, 122, 255, .45); }
.checklist-audit { border-color: #e4edf5; color: #829ab1; font-family: inherit; font-size: 10px; }

.release-editor-heading p, .draft-message { color: #7892ad; }
.draft-safety-badge { border-color: #b9ddf7; color: var(--ios-blue); background: #f0f8ff; font-family: inherit; font-size: 10px; font-weight: 700; }
.release-editor-toolbar { margin: 24px 0 16px; }
.version-field, .markdown-editor { color: #5f7b98; font-size: 11px; font-weight: 650; }
.version-field input, .markdown-editor textarea { color: #274764; }
.version-field input:focus, .markdown-editor textarea:focus { border-color: #74baff; box-shadow: 0 0 0 4px rgba(0, 122, 255, .11); }
.version-field input::placeholder, .markdown-editor textarea::placeholder { color: #a2b5c9; }
.editor-primary-button, .editor-secondary-button, .editor-ai-button { min-height: 44px; border-radius: 12px; font-size: 11px; font-weight: 720; }
.editor-primary-button { border-color: var(--ios-blue); color: #fff; background: var(--ios-blue); box-shadow: 0 7px 15px rgba(0, 122, 255, .15); }
.editor-primary-button:hover:not(:disabled) { border-color: var(--ios-blue-dark); background: var(--ios-blue-dark); }
.editor-secondary-button { border-color: #cbddec; color: #52718e; background: #fff; }
.editor-secondary-button:hover:not(:disabled) { border-color: #91c5f1; color: var(--ios-blue); background: #f4f9ff; }
.editor-ai-button { border-color: #99c9f3; color: #0871d6; background: #edf7ff; }
.editor-ai-button:hover:not(:disabled) { border-color: #5eaff1; background: #e3f2ff; }
.editor-primary-button:disabled, .editor-secondary-button:disabled, .editor-ai-button:disabled { opacity: .48; }
.editor-hint { border-left-color: #80bff1; color: #6d88a4; background: #f1f8ff; }
.editor-hint span { color: #3a6c96; }
.draft-message.success { color: #279a51; }
.release-sources { border-color: #dce8f2; border-radius: 14px; background: #f8fbff; }
.source-summary { border-color: #e2ebf4; }
.source-summary strong { color: #31516e; }
.source-summary p, .source-empty { color: #7892ad; }
.source-list a { border-color: #e4edf5; }
.source-list a:hover { background: #eef7ff; }
.source-list span { color: var(--ios-blue); font-family: inherit; font-size: 10px; font-weight: 750; }
.source-list strong { color: #3b5b78; }
.source-list small { color: #7892ad; }
.ai-polish-panel { border-color: #c7e3fa; border-radius: 16px; background: linear-gradient(120deg, #f0f8ff, #fbfdff); }
.ai-polish-heading h3 { color: #2d4d6a; }
.ai-polish-heading p { color: #6d88a4; }
.ai-change-list li { border-color: #c7e3fa; color: #3d6c95; background: #f7fbff; }
.ai-compare-grid > div > span { color: #6f8aa5; font-family: inherit; font-size: 9px; font-weight: 750; }
.ai-compare-grid pre { border-color: #d8e7f3; color: #486783; background: #fff; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.ai-model-note { color: #8aa1b8; }

@media (max-width: 1080px) {
  .sidebar { width: 220px; }
  .main-content { padding-right: 35px; padding-left: 35px; }
}
@media (max-width: 720px) {
  .app-shell { display: block; }
  .sidebar { position: static; width: auto; min-height: 0; padding: 16px; border-right: 0; border-bottom: 1px solid #dbe8f4; box-shadow: 0 8px 25px rgba(58, 111, 160, .05); }
  .brand-block { padding: 0 5px 15px; }
  .primary-nav { grid-template-columns: repeat(3, 1fr); }
  .nav-item { justify-content: center; min-height: 43px; padding: 8px 4px; font-size: 11px; }
  .nav-icon, .sidebar-note, .sidebar-footer { display: none; }
  .main-content { padding: 27px 16px 42px; }
  .topbar { display: block; }
  .topbar-actions { padding-top: 15px; }
  .workspace-banner { min-height: 174px; margin-top: 27px; padding: 24px; border-radius: 20px; }
  .workspace-orbit { display: none; }
  .repository-picker { display: grid; }
  .repository-picker button { min-height: 44px; }
  .repository-bound-state { display: grid; }
  .gate-checks, .quality-grid { grid-template-columns: 1fr; }
  .section-heading { margin-top: 31px; }
  .detail-heading { display: block; }
  .detail-heading .text-button { margin-top: 18px; }
  .release-editor-heading, .checklist-heading { display: grid; }
  .checklist-result { width: fit-content; text-align: left; }
  .draft-safety-badge { width: fit-content; }
  .release-editor-toolbar { grid-template-columns: 1fr 1fr; }
  .version-field { grid-column: 1 / -1; }
  .editor-primary-button, .editor-secondary-button, .editor-ai-button { padding: 0 10px; }
  .ai-polish-heading, .ai-compare-grid { grid-template-columns: 1fr; }
  .ai-polish-heading { display: grid; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; animation-duration: .01ms !important; }
}
/* Typography comfort pass: make supporting copy readable without losing the iOS hierarchy. */
body { font-size: 14px; line-height: 1.55; }
.brand-block span { font-size: 10px; }
.nav-item { font-size: 14px; }
.page-subtitle { font-size: 14px; line-height: 1.6; }
.workspace-banner p { font-size: 14px; line-height: 1.7; }
.panel-helper { font-size: 12px; line-height: 1.7; }
.repository-bound-state strong { font-size: 15px; }
.repository-bound-state span, .sync-toolbar > span { font-size: 12px; }
.repository-hint, .repository-error { font-size: 12px; line-height: 1.65; }
.next-action-copy h2 { font-size: 22px; }
.next-action-copy p { font-size: 14px; line-height: 1.75; }
.workflow-intro strong { font-size: 14px; }
.workflow-intro small { font-size: 11px; line-height: 1.7; }
.workflow-steps strong { font-size: 12px; }
.workflow-steps small { font-size: 10px; line-height: 1.55; }
.workflow-status { font-size: 10px; }
.section-helper { font-size: 12px; line-height: 1.7; }
.gate-summary p { font-size: 13px; line-height: 1.7; }
.gate-help { font-size: 11px; line-height: 1.7; }
.gate-check-heading strong { font-size: 13px; }
.gate-check-heading span { font-size: 11px; }
.gate-check p { font-size: 12px; line-height: 1.65; }
.gate-check a { font-size: 11px; }
.card-topline span:first-child { font-size: 13px; }
.card-description { min-height: 34px; font-size: 12px; line-height: 1.6; }
.card-footer { font-size: 11px; }
.card-action { font-size: 11px; }
.activity-row { font-size: 13px; }
.activity-detail { font-size: 12px; }
.playbook-list strong { font-size: 13px; }
.playbook-list p { font-size: 12px; line-height: 1.7; }
.detail-heading p { font-size: 13px; line-height: 1.75; }
.detail-main strong { font-size: 14px; }
.detail-main p, .detail-status { font-size: 12px; }
.release-flow-heading h2 { font-size: 18px; }
.release-flow-heading small { font-size: 11px; }
.release-flow-steps strong { font-size: 12px; }
.release-flow-steps small { font-size: 10px; line-height: 1.55; }
.release-flow-steps b { font-size: 10px; }
.checklist-heading p, .release-editor-heading p { font-size: 13px; line-height: 1.75; }
.checklist-result small { font-size: 10px; }
.checklist-group-heading { font-size: 12px; }
.checklist-group-heading small { font-size: 10px; }
.checklist-row strong { font-size: 12px; }
.checklist-row p { font-size: 11px; line-height: 1.65; }
.checklist-row > small { font-size: 10px; }
.checklist-audit { font-size: 11px; }
.version-field, .markdown-editor { font-size: 12px; }
.version-field input { font-size: 13px; }
.markdown-editor textarea { font-size: 13px; line-height: 1.8; }
.editor-primary-button, .editor-secondary-button, .editor-ai-button { font-size: 12px; }
.editor-hint { font-size: 12px; line-height: 1.75; }
.draft-message { font-size: 12px; line-height: 1.7; }
.source-summary strong { font-size: 15px; }
.source-summary p, .source-empty { font-size: 11px; line-height: 1.7; }
.source-list strong { font-size: 12px; }
.source-list small { font-size: 10px; }
.ai-polish-heading h3 { font-size: 15px; }
.ai-polish-heading p { font-size: 12px; line-height: 1.7; }
.ai-change-list li { font-size: 10px; }
.ai-compare-grid > div > span { font-size: 10px; }
.ai-compare-grid pre { font-size: 11px; line-height: 1.75; }
.ai-model-note { font-size: 10px; }
@media (max-width: 720px) {
  .page-subtitle { font-size: 13px; }
  .workspace-banner p, .next-action-copy p { font-size: 13px; }
  .next-action-copy h2 { font-size: 20px; }
  .card-description { min-height: 0; }
  .workflow-steps strong { font-size: 11px; }
  .workflow-steps small { font-size: 10px; }
}
.workflow-steps li, .release-flow-steps li {
  cursor: pointer;
  border-radius: 13px;
  transition: background-color .18s ease, transform .18s ease;
}
.workflow-steps li:hover, .release-flow-steps li:hover {
  background: rgba(227, 242, 255, .72);
  transform: translateY(-1px);
}
.workflow-steps li:focus-visible, .release-flow-steps li:focus-visible {
  outline: 3px solid rgba(0, 122, 255, .25);
  outline-offset: 2px;
}
.workflow-steps li.locked, .release-flow-steps li.locked { cursor: pointer; }
.app-shell { display: block; }
.sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  height: 100vh;
  min-height: 100vh;
  overflow-y: auto;
  overscroll-behavior: contain;
}
.main-content {
  width: calc(100% - 252px);
  min-width: 0;
  margin-left: 252px;
}
@media (max-width: 1080px) {
  .main-content { width: calc(100% - 220px); margin-left: 220px; }
}
@media (max-width: 720px) {
  .sidebar {
    position: static;
    inset: auto;
    width: auto;
    height: auto;
    min-height: 0;
    overflow: visible;
  }
  .main-content { width: auto; margin-left: 0; }
}
@media (max-width: 680px) {
  .repository-bound-state { align-items: stretch; }
  .repository-selection select { width: 100%; }
  .repository-switch-button { padding: 0; text-align: left; }
}
</style>
