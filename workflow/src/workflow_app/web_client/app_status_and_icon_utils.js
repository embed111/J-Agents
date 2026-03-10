(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const sessionCacheKey = 'workflow.p0.session';
  const agentCacheKey = 'workflow.p0.agent';
  const showTestDataCacheKey = 'workflow.p0.settings.showTestData';
  const showSystemAgentsLegacyCacheKey = 'workflow.p0.settings.showSystemAgents';
  const layoutKeys = {
    rail: 'workflow.p0.layout.rail',
    chatLeft: 'workflow.p0.layout.chatLeft',
    trainLeft: 'workflow.p0.layout.trainLeft',
    trainRight: 'workflow.p0.layout.trainRight',
  };

  const state = {
    agents: [],
    sessionsById: {},
    sessionOrder: [],
    selectedSessionId: '',
    runningTasks: {}, // session_id -> { task_id, since_id, pending_index, started_at, status, agent_name }
    sessionTaskRuns: {}, // session_id -> task runs[]
    taskTraceCache: {}, // task_id -> { loading, data, error }
    taskTraceExpanded: {}, // task_id -> bool
    taskTraceDetailsOpen: {}, // task_id:section -> bool
    feedRenderRaf: 0,
    poller: 0,
    workflows: [],
    selectedWorkflowId: '',
    workflowPlans: {}, // workflow_id -> plan[]
    workflowEvents: {}, // workflow_id -> events[]
    workflowEventDetailOpen: {}, // workflow_id -> bool
    workflowEventDebugOpen: {}, // workflow_id:event_id -> bool
    workflowPoller: 0,
    workflowPollBusy: false,
    showTestData: true,
    queueMode: 'records', // records | training
    selectedWorkflowIds: {},
    batchRun: {
      running: false,
      action: '',
      total: 0,
      done: 0,
      success: 0,
      failed: 0,
      skipped: 0,
      results: [],
      started_at: '',
      finished_at: '',
    },
    lastBatchReport: null,
    lastFailedWorkflowIds: [],
    pendingPolicyConfirmation: null,
    agentMetaPanelOpen: false,
    agentMetaDetailsOpen: false,
    agentMetaClarityOpen: false,
    allowManualPolicyInput: true,
    policyClosureStats: {},
    sessionPolicyGateState: 'idle_unselected',
    sessionPolicyGateReason: '请先选择角色',
    sessionPolicyCacheLine: '',
    sessionPolicyGateSeq: 0,
    policyAnalyzeProgress: null, // { agent_name, gate_seq, active, failed, started_at_ms, finished_at_ms, total_ms, stages[] }
    agentPolicyProgressByName: {}, // agent_name -> ui_progress snapshot
    policyAnalyzeTicker: 0,
    agentPolicyAnalysisByName: {},
    agentPolicyAnalysisInitialized: false,
    currentAgentSearchRoot: '',
    agentSearchRootReady: false,
    agentSearchRootError: '',
    agentDropdownOpen: false,
    agentDropdownPanelWidth: 0,
    policyConfirmGateOpen: false,
    policyConfirmEvidenceOpen: false,
    policyConfirmAnalysisOpen: false,
    policyConfirmRiskOpen: true,
    policyRecommendTraceOpen: false,
    feedRenderedSessionId: '',
    tcModule: 'agents', // agents | ops
    tcAgents: [],
    tcStats: {
      agent_total: 0,
      git_available_count: 0,
      latest_release_at: '',
      training_queue_pending: 0,
    },
    tcSelectedAgentId: '',
    tcSelectedAgentName: '',
    tcSelectedAgentDetail: null,
    tcSelectedAgentContextLoading: false,
    tcSelectedAgentContextRequestSeq: 0,
    tcReleasesByAgent: {}, // agent_id -> releases[]
    tcNormalCommitsByAgent: {}, // agent_id -> normal_commits[]
    tcReleaseReviewByAgent: {}, // agent_id -> review payload
    tcReleaseReviewProgressByAgent: {}, // agent_id -> local running progress
    tcReleaseReviewErrorByAgent: {}, // agent_id -> local failed message snapshot
    tcReleaseReviewProgressTicker: 0,
    tcVersionDropdownOpen: false,
    tcQueue: [],
    tcTrainers: [],
    tcTrainerSelected: '',
  };

  function safe(value) {
    if (value === null || value === undefined) return '';
    return String(value);
  }

  function short(value, maxLen) {
    const text = safe(value);
    if (text.length <= maxLen) return text;
    return text.slice(0, maxLen) + '...';
  }

  function nowText() {
    return new Date().toLocaleTimeString();
  }

  function queryParam(name) {
    try {
      const url = new URL(window.location.href);
      return safe(url.searchParams.get(name)).trim();
    } catch (_) {
      return '';
    }
  }

  function isLayoutProbeEnabled() {
    return queryParam('layout_probe') === '1';
  }

  function isPolicyProbeEnabled() {
    return queryParam('policy_probe') === '1';
  }

  function isTrainingCenterProbeEnabled() {
    return queryParam('tc_probe') === '1';
  }

  function isTestDataToggleProbeEnabled() {
    return queryParam('td_probe') === '1';
  }

  function testDataToggleProbeCase() {
    return safe(queryParam('td_probe_case')).trim().toLowerCase() || 'ac_td_01';
  }

  function trainingCenterProbeCase() {
    return safe(queryParam('tc_probe_case')).trim().toLowerCase() || 'ac_uo_01';
  }

  function policyProbeStage() {
    const value = queryParam('policy_probe_stage').toLowerCase();
    if (['initial', 'analyzing', 'ready', 'manual'].includes(value)) return value;
    return 'initial';
  }

  function layoutProbeTab() {
    const value = queryParam('layout_probe_tab').toLowerCase();
    if (
      value === 'training' ||
      value === 'training-center' ||
      value === 'settings' ||
      value === 'chat'
    ) {
      return value;
    }
    return 'chat';
  }

  function setStatus(text) {
    $('statusLine').textContent = '[' + nowText() + '] ' + text;
  }

  function setChatError(text) {
    $('chatErr').textContent = safe(text);
  }

  function setSettingsError(text) {
    $('settingsErr').textContent = safe(text);
  }

  function setWorkflowResult(obj) {
    if (typeof obj === 'string') {
      $('workflowResult').textContent = obj;
      return;
    }
    $('workflowResult').textContent = JSON.stringify(obj || {}, null, 2);
  }

  function statusText(value) {
    const key = safe(value).toLowerCase();
    const map = {
      active: '进行中',
      running: '运行中',
      pending: '排队中',
      queued: '排队中',
      success: '成功',
      failed: '失败',
      interrupted: '已中断',
      closed: '已关闭',
      done: '已完成',
      none: '无',
      skipped: '已跳过',
      training: '训练中',
      assigned: '已指派',
      analyzing: '分析中',
      analyzed: '已分析',
      planned: '已生成任务',
      selected: '已选择执行项',
      train: '入训',
      skip: '跳过',
      need_info: '待补充',
    };
    return map[key] || safe(value);
  }

  function reasonText(value) {
    const key = safe(value).toLowerCase();
    const map = {
      no_training_value: '无训练价值',
      missing_previous_context: '上文缺失',
      missing_next_context: '下文缺失',
      all_messages_analyzed: '会话全部消息已分析',
      no_work_records: '会话无可分析消息',
      conversation_locked_by_training_plan: '会话已生成训练计划，禁止删除聊天记录',
      session_busy: '当前会话有运行中的任务',
    };
    return map[key] || safe(value);
  }

  function createSvgElement(tag, attrs) {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    const source = attrs || {};
    for (const key of Object.keys(source)) {
      node.setAttribute(key, safe(source[key]));
    }
    return node;
  }

  function createStatusIcon(kind, options) {
    const icon = safe(kind).toLowerCase();
    const opts = options || {};
    const classNames = ['status-icon'];
    if (opts.spinning) classNames.push('icon-spin');
    if (opts.compact) classNames.push('compact');
    const svg = createSvgElement('svg', {
      viewBox: '0 0 20 20',
      class: classNames.join(' '),
      'aria-hidden': 'true',
      focusable: 'false',
    });
    if (opts.spinning) {
      const cycleMs = Math.max(500, Number(opts.spinCycleMs || 1000) || 1000);
      const clockNow =
        typeof window !== 'undefined' &&
        window.performance &&
        typeof window.performance.now === 'function'
          ? window.performance.now()
          : Date.now();
      const offset = Math.floor(Math.max(0, Number(clockNow) || 0) % cycleMs);
      svg.style.setProperty('--icon-spin-duration', String(cycleMs) + 'ms');
      // Keep spin phase continuous across rerenders to avoid visible "jump back to 0deg".
      svg.style.animationDelay = '-' + String(offset) + 'ms';
    }
    const append = (tag, attrs) => {
      svg.appendChild(createSvgElement(tag, attrs));
    };
    if (icon === 'refresh') {
      append('path', { d: 'M15.4 8.2A5.9 5.9 0 1 0 16 10' });
      append('path', { d: 'M12.8 4.6H16V7.8' });
      return svg;
    }
    if (icon === 'cache') {
      append('ellipse', { cx: '10', cy: '5.5', rx: '5.8', ry: '2.2' });
      append('path', { d: 'M4.2 5.5V14.5C4.2 15.9 6.8 17 10 17C13.2 17 15.8 15.9 15.8 14.5V5.5' });
      append('path', { d: 'M4.2 10C4.2 11.4 6.8 12.5 10 12.5C13.2 12.5 15.8 11.4 15.8 10' });
      return svg;
    }
    if (icon === 'clear_one') {
      append('rect', { x: '5.4', y: '6.5', width: '9.2', height: '8.8', rx: '1.6' });
      append('path', { d: 'M4.2 6.5H15.8' });
      append('path', { d: 'M8 8.5V13.5' });
      append('path', { d: 'M12 10.9H15.9' });
      return svg;
    }
    if (icon === 'clear_all') {
      append('rect', { x: '5.4', y: '6.5', width: '9.2', height: '8.8', rx: '1.6' });
      append('path', { d: 'M4.2 6.5H15.8' });
      append('path', { d: 'M8 8.5V13.5' });
      append('path', { d: 'M12 8.5V13.5' });
      return svg;
    }
    if (icon === 'sent') {
      append('rect', { x: '3', y: '5', width: '14', height: '10', rx: '2' });
      append('path', { d: 'M3.8 6.4L10 11.2L16.2 6.4' });
      return svg;
    }
    if (icon === 'spinner') {
      append('circle', { class: 'icon-ring', cx: '10', cy: '10', r: '7.5' });
      append('path', { d: 'M10 2.5A7.5 7.5 0 0 1 17.5 10' });
      return svg;
    }
    if (icon === 'report') {
      append('rect', { x: '4.5', y: '3.2', width: '11', height: '13.6', rx: '1.6' });
      append('path', { d: 'M7 7.2H13' });
      append('path', { d: 'M7 10H13' });
      append('path', { d: 'M7 12.8H11.2' });
      return svg;
    }
    if (icon === 'flag') {
      append('path', { d: 'M6 3.4V16.6' });
      append('path', { d: 'M6.2 4.2H14.8L12.6 7.3L14.8 10.4H6.2' });
      return svg;
    }
    if (icon === 'pending') {
      append('circle', { cx: '10', cy: '10', r: '7.5' });
      append('circle', { cx: '10', cy: '10', r: '1.5', fill: 'currentColor', stroke: 'none' });
      return svg;
    }
    if (icon === 'success') {
      append('circle', { cx: '10', cy: '10', r: '7.5' });
      append('path', { d: 'M6.3 10.4L8.8 12.9L13.7 8' });
      return svg;
    }
    if (icon === 'failed') {
      append('circle', { cx: '10', cy: '10', r: '7.5' });
      append('path', { d: 'M7 7L13 13' });
      append('path', { d: 'M13 7L7 13' });
      return svg;
    }
    if (icon === 'interrupted') {
      append('circle', { cx: '10', cy: '10', r: '7.5' });
      append('path', { d: 'M6.7 10H13.3' });
      return svg;
    }
    if (icon === 'skipped') {
      append('path', { d: 'M6 6.8L10.4 10L6 13.2V6.8Z' });
      append('path', { d: 'M10.2 6.8L14.6 10L10.2 13.2V6.8Z' });
      return svg;
    }
    append('circle', { class: 'icon-ring', cx: '10', cy: '10', r: '7.5' });
    append('path', { d: 'M10 2.5A7.5 7.5 0 0 1 17.5 10' });
    return svg;
  }

  function appendIconLabel(node, label, iconKind, options) {
    const opts = options || {};
    const icon = createStatusIcon(iconKind, {
      spinning: !!opts.spinning,
      compact: !!opts.compact,
    });
    const text = document.createElement('span');
    text.className = safe(opts.labelClassName || 'chip-label');
    text.textContent = safe(label);
    node.appendChild(icon);
    node.appendChild(text);
  }

  function analysisBadgeHtml(info) {
    const item = info || {};
    return (
      "<span class='" +
      safe(item.className) +
      "' data-icon='" +
      safe(item.icon || 'pending') +
      "'" +
      (item.spinning ? " data-spin='1'" : '') +
      '>' +
      safe(item.text) +
      '</span>'
    );
  }

  function hydrateAnalysisBadges(rootNode) {
    const root = rootNode || document;
    const badges = root.querySelectorAll('.analysis-badge[data-icon]');
    for (const badge of badges) {
      if (safe(badge.getAttribute('data-icon-ready')) === '1') continue;
      const label = safe(badge.textContent);
      const icon = safe(badge.getAttribute('data-icon') || 'pending');
      const spinning = safe(badge.getAttribute('data-spin')) === '1';
      badge.textContent = '';
      appendIconLabel(badge, label, icon, {
        spinning: spinning,
        labelClassName: 'analysis-chip-label',
      });
      badge.setAttribute('data-icon-ready', '1');
    }
  }

  function createAnalysisBadgeNode(info) {
    const badge = document.createElement('span');
    const item = info || {};
    badge.className = safe(item.className || 'analysis-badge pending');
    appendIconLabel(badge, safe(item.text || ''), safe(item.icon || 'pending'), {
      spinning: !!item.spinning,
      labelClassName: 'analysis-chip-label',
    });
    return badge;
  }

  function setIconOnlyButton(buttonId, iconKind) {
    const btn = $(buttonId);
    if (!btn) return;
    const title = safe(btn.getAttribute('title')).trim();
    btn.textContent = '';
    btn.appendChild(createStatusIcon(iconKind, { compact: false }));
    if (title) {
      btn.setAttribute('aria-label', title);
    }
  }

  function setupSessionEntryToolbarIcons() {
    setIconOnlyButton('loadAgentsBtn', 'refresh');
    setIconOnlyButton('clearPolicyCacheBtn', 'clear_one');
    setIconOnlyButton('clearAllPolicyCacheBtn', 'clear_all');
    setIconOnlyButton('regeneratePolicyCacheBtn', 'cache');
  }

