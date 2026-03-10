  function setTrainingCenterModule(moduleName) {
    const next = safe(moduleName).toLowerCase() === 'ops' ? 'ops' : 'agents';
    state.tcModule = next;
    const tabAgentsBtn = $('tcTabAgentsBtn');
    const tabOpsBtn = $('tcTabOpsBtn');
    if (tabAgentsBtn) tabAgentsBtn.classList.toggle('active', next === 'agents');
    if (tabOpsBtn) tabOpsBtn.classList.toggle('active', next === 'ops');
    const moduleAgents = $('tcModuleAgents');
    const moduleOps = $('tcModuleOps');
    if (moduleAgents) moduleAgents.classList.toggle('active', next === 'agents');
    if (moduleOps) moduleOps.classList.toggle('active', next === 'ops');
  }

  function setTrainingCenterError(text) {
    const node = $('tcOpsErr');
    if (node) node.textContent = safe(text);
  }

  function setTrainingCenterDetailError(text) {
    const node = $('tcAgentDetailErr');
    if (node) node.textContent = safe(text);
  }

  function setTrainingCenterAgentActionResult(value) {
    const node = $('tcAgentActionResult');
    if (!node) return;
    if (typeof value === 'string') {
      node.textContent = value;
      return;
    }
    node.textContent = JSON.stringify(value || {}, null, 2);
  }

  function trainingLifecycleText(value) {
    const key = safe(value).toLowerCase();
    if (key === 'pre_release') return '预发布';
    if (key === 'unknown') return '不可判定';
    return '已发布';
  }

  function trainingGateText(value) {
    const key = safe(value).toLowerCase();
    if (key === 'frozen_switched') return '已切换（禁训）';
    return '可训练';
  }

  function trainingStatusTagText(value) {
    const key = safe(value).toLowerCase();
    if (key === 'published_ready') return '已发布';
    if (key === 'git_unavailable') return 'Git不可用（按预发布处理）';
    if (key === 'pre_release') return '预发布';
    if (key === 'pre_release_unknown') return '预发布不可判定';
    if (key === 'frozen_switched') return '已切换';
    if (key === 'cloned') return '克隆角色';
    if (key === 'normal_commit_present') return '含普通提交';
    return safe(value);
  }

  function visibleTrainingStatusTags(tags) {
    if (!Array.isArray(tags)) return [];
    return tags
      .map((tag) => safe(tag).trim())
      .filter((tag) => !!tag)
      .filter((tag) => {
        const key = tag.toLowerCase();
        return key !== 'git_unavailable' && key !== 'normal_commit_present';
      });
  }

  function trainingCenterVersionText(versionLabel) {
    const value = safe(versionLabel).trim();
    return value || '未发布';
  }

  function renderTrainingCenterVersionPill(versionLabel) {
    const value = safe(versionLabel).trim();
    return (
      "<div class='tc-card-version'>" +
      "<span class='tc-card-version-k'>当前版本</span>" +
      "<span class='tc-card-version-v" +
      (value ? '' : ' empty') +
      "'>" +
      trainingCenterVersionText(value) +
      '</span>' +
      '</div>'
    );
  }

  function trainingCenterAgentDetailById(agentId) {
    const key = safe(agentId).trim();
    if (!key) return {};
    if (safe(state.tcSelectedAgentId).trim() === key && state.tcSelectedAgentDetail) {
      return state.tcSelectedAgentDetail || {};
    }
    const rows = Array.isArray(state.tcAgents) ? state.tcAgents : [];
    return rows.find((item) => safe(item && item.agent_id).trim() === key) || {};
  }

  function defaultTrainingCenterReleaseReview(agentLike) {
    const detail = agentLike && typeof agentLike === 'object' ? agentLike : {};
    const lifecycleState = safe(detail.lifecycle_state || 'released').trim().toLowerCase() || 'released';
    return {
      review_id: '',
      agent_id: safe(detail.agent_id).trim(),
      agent_name: safe(detail.agent_name).trim(),
      release_review_state: 'idle',
      target_version: '',
      current_workspace_ref: safe(detail.current_version).trim(),
      prompt_version: '',
      analysis_chain: {},
      report: {},
      report_error: '',
      report_error_code: '',
      report_missing_fields: [],
      required_report_fields: [],
      review_decision: '',
      reviewer: '',
      review_comment: '',
      reviewed_at: '',
      publish_version: '',
      publish_status: '',
      publish_error: '',
      execution_logs: [],
      fallback: {},
      created_at: '',
      updated_at: '',
      can_enter: lifecycleState === 'pre_release',
      can_discard: false,
      can_review: false,
      can_confirm: false,
      publish_succeeded: false,
      lifecycle_state: lifecycleState,
    };
  }

  function normalizeTrainingCenterReleaseReviewPayload(agentId, payload) {
    const detail = trainingCenterAgentDetailById(agentId);
    const rawReview =
      payload && payload.review && typeof payload.review === 'object'
        ? payload.review
        : payload && typeof payload === 'object'
          ? payload
          : {};
    const review = Object.assign({}, defaultTrainingCenterReleaseReview(detail), rawReview || {});
    review.analysis_chain =
      rawReview && rawReview.analysis_chain && typeof rawReview.analysis_chain === 'object'
        ? rawReview.analysis_chain
        : {};
    review.report =
      rawReview && rawReview.report && typeof rawReview.report === 'object'
        ? rawReview.report
        : {};
    review.report_error_code = safe(rawReview && rawReview.report_error_code).trim();
    review.report_missing_fields =
      rawReview && Array.isArray(rawReview.report_missing_fields)
        ? rawReview.report_missing_fields.map((item) => safe(item).trim()).filter(Boolean)
        : [];
    review.required_report_fields =
      rawReview && Array.isArray(rawReview.required_report_fields)
        ? rawReview.required_report_fields.map((item) => safe(item).trim()).filter(Boolean)
        : [];
    review.execution_logs =
      rawReview && Array.isArray(rawReview.execution_logs)
        ? rawReview.execution_logs
        : [];
    review.fallback =
      rawReview && rawReview.fallback && typeof rawReview.fallback === 'object'
        ? rawReview.fallback
        : {};
    review.agent_id = safe(review.agent_id || agentId).trim();
    review.agent_name = safe(review.agent_name || detail.agent_name).trim();
    review.release_review_state = safe(review.release_review_state || 'idle').trim() || 'idle';
    review.review_decision = safe(review.review_decision).trim();
    review.publish_status = safe(review.publish_status).trim();
    review.lifecycle_state = safe(review.lifecycle_state || detail.lifecycle_state || 'released').trim().toLowerCase() || 'released';
    review.can_enter = !!review.can_enter;
    review.can_discard = !!review.can_discard;
    review.can_review = !!review.can_review;
    review.can_confirm = !!review.can_confirm;
    review.publish_succeeded = !!review.publish_succeeded;
    return review;
  }

  function currentTrainingCenterReleaseReview(agentId) {
    const key = safe(agentId).trim();
    const store =
      state.tcReleaseReviewByAgent && typeof state.tcReleaseReviewByAgent === 'object'
        ? state.tcReleaseReviewByAgent
        : {};
    if (key && store[key] && typeof store[key] === 'object') {
      return normalizeTrainingCenterReleaseReviewPayload(key, store[key]);
    }
    return normalizeTrainingCenterReleaseReviewPayload(key, {});
  }

  function trainingCenterReleaseReviewIsActive(review) {
    const node = review && typeof review === 'object' ? review : {};
    const reviewId = safe(node.review_id).trim();
    const stateKey = safe(node.release_review_state).trim().toLowerCase();
    if (!reviewId) return false;
    return stateKey !== 'idle' && stateKey !== 'review_discarded';
  }

  function trainingCenterReleaseReviewProgressTemplates(mode) {
    const key = safe(mode).trim().toLowerCase();
    if (key === 'confirm') {
      return [
        {
          key: 'prepare',
          label: '准备发布',
          detail: '正在整理目标版本、release note 与工作区上下文',
          handoff_after_ms: 800,
        },
        {
          key: 'git_execute',
          label: 'Git / release note',
          detail: '正在执行 Git 提交、打标签与 release note 处理',
          handoff_after_ms: 3200,
        },
        {
          key: 'verify',
          label: '发布后校验',
          detail: '正在按当前版本识别规则回读并校验发布结果',
          handoff_after_ms: 0,
        },
      ];
    }
    return [
      {
        key: 'enter',
        label: '创建评审记录',
        detail: '正在进入发布评审并创建评审记录',
        handoff_after_ms: 700,
      },
      {
        key: 'codex',
        label: 'Codex 生成报告',
        detail: '正在委派工作区 agent 生成结构化发布报告，并在完成后回填分析链路与报告结果',
        handoff_after_ms: 0,
      },
    ];
  }

  function currentTrainingCenterReleaseReviewProgress(agentId) {
    const key = safe(agentId).trim();
    const store =
      state.tcReleaseReviewProgressByAgent && typeof state.tcReleaseReviewProgressByAgent === 'object'
        ? state.tcReleaseReviewProgressByAgent
        : {};
    const progress = key && store[key] && typeof store[key] === 'object' ? store[key] : null;
    return progress || null;
  }

  function currentTrainingCenterReleaseReviewError(agentId) {
    const key = safe(agentId).trim();
    const store =
      state.tcReleaseReviewErrorByAgent && typeof state.tcReleaseReviewErrorByAgent === 'object'
        ? state.tcReleaseReviewErrorByAgent
        : {};
    const item = key && store[key] && typeof store[key] === 'object' ? store[key] : null;
    return item || null;
  }

  function clearTrainingCenterReleaseReviewError(agentId) {
    const key = safe(agentId).trim();
    if (!key) return;
    const store =
      state.tcReleaseReviewErrorByAgent && typeof state.tcReleaseReviewErrorByAgent === 'object'
        ? state.tcReleaseReviewErrorByAgent
        : {};
    if (store[key]) {
      delete store[key];
    }
  }

  function clearTrainingCenterReleaseReviewProgressTickerIfIdle() {
    const store =
      state.tcReleaseReviewProgressByAgent && typeof state.tcReleaseReviewProgressByAgent === 'object'
        ? state.tcReleaseReviewProgressByAgent
        : {};
    const hasRunning = Object.keys(store).some((agentId) => {
      const item = store[agentId];
      return !!(item && item.active);
    });
    if (!hasRunning && state.tcReleaseReviewProgressTicker) {
      window.clearInterval(state.tcReleaseReviewProgressTicker);
      state.tcReleaseReviewProgressTicker = 0;
    }
  }

  function ensureTrainingCenterReleaseReviewProgressTicker() {
    if (state.tcReleaseReviewProgressTicker) return;
    state.tcReleaseReviewProgressTicker = window.setInterval(() => {
      const selectedAgentId = safe(state.tcSelectedAgentId).trim();
      if (selectedAgentId && currentTrainingCenterReleaseReviewProgress(selectedAgentId)) {
        renderTrainingCenterReleaseReview(selectedAgentId);
      }
      clearTrainingCenterReleaseReviewProgressTickerIfIdle();
    }, 480);
  }

  function startTrainingCenterReleaseReviewProgress(agentId, mode) {
    const key = safe(agentId).trim();
    if (!key) return null;
    if (!state.tcReleaseReviewProgressByAgent || typeof state.tcReleaseReviewProgressByAgent !== 'object') {
      state.tcReleaseReviewProgressByAgent = {};
    }
    if (!state.tcReleaseReviewErrorByAgent || typeof state.tcReleaseReviewErrorByAgent !== 'object') {
      state.tcReleaseReviewErrorByAgent = {};
    }
    clearTrainingCenterReleaseReviewError(key);
    const progress = {
      agent_id: key,
      mode: safe(mode).trim().toLowerCase() || 'enter',
      active: true,
      failed: false,
      error_message: '',
      started_at_ms: Date.now(),
      finished_at_ms: 0,
      stages: trainingCenterReleaseReviewProgressTemplates(mode),
    };
    state.tcReleaseReviewProgressByAgent[key] = progress;
    ensureTrainingCenterReleaseReviewProgressTicker();
    if (safe(state.tcSelectedAgentId).trim() === key) {
      renderTrainingCenterReleaseReview(key);
    }
    return progress;
  }

  function finishTrainingCenterReleaseReviewProgress(agentId) {
    const key = safe(agentId).trim();
    if (!key) return;
    clearTrainingCenterReleaseReviewError(key);
    const store =
      state.tcReleaseReviewProgressByAgent && typeof state.tcReleaseReviewProgressByAgent === 'object'
        ? state.tcReleaseReviewProgressByAgent
        : {};
    if (store[key]) {
      delete store[key];
    }
    if (safe(state.tcSelectedAgentId).trim() === key) {
      renderTrainingCenterReleaseReview(key);
    }
    clearTrainingCenterReleaseReviewProgressTickerIfIdle();
  }

  function failTrainingCenterReleaseReviewProgress(agentId, errorLike) {
    const key = safe(agentId).trim();
    if (!key) return;
    const current = currentTrainingCenterReleaseReviewProgress(key);
    if (!current) return;
    if (!state.tcReleaseReviewErrorByAgent || typeof state.tcReleaseReviewErrorByAgent !== 'object') {
      state.tcReleaseReviewErrorByAgent = {};
    }
    const data = errorLike && errorLike.data && typeof errorLike.data === 'object' ? errorLike.data : {};
    const message = safe(errorLike && errorLike.message ? errorLike.message : errorLike).trim();
    current.active = false;
    current.failed = true;
    current.error_message = message;
    current.finished_at_ms = Date.now();
    state.tcReleaseReviewErrorByAgent[key] = {
      mode: safe(current.mode).trim().toLowerCase(),
      error_message: safe(current.error_message).trim(),
      error_code: safe(errorLike && errorLike.code).trim().toLowerCase(),
      error_reason: safe(data.reason).trim(),
      error_status: Number(errorLike && errorLike.status) || 0,
      error_data: data,
      failed_at_ms: current.finished_at_ms,
    };
    if (safe(state.tcSelectedAgentId).trim() === key) {
      renderTrainingCenterReleaseReview(key);
    }
    window.setTimeout(() => {
      const latest = currentTrainingCenterReleaseReviewProgress(key);
      if (latest !== current) return;
      finishTrainingCenterReleaseReviewProgress(key);
    }, 2600);
    clearTrainingCenterReleaseReviewProgressTickerIfIdle();
  }

  function describeTrainingCenterReleaseReviewProgress(progress) {
    const node = progress && typeof progress === 'object' ? progress : {};
    const stages = Array.isArray(node.stages) ? node.stages : [];
    if (!stages.length) {
      return {
        active: !!node.active,
        failed: !!node.failed,
        elapsed_ms: 0,
        headline: '',
        detail: '',
        items: [],
      };
    }
    const nowMs = Date.now();
    const startedAtMs = Number(node.started_at_ms || nowMs);
    const finishedAtMs = Number(node.finished_at_ms || 0);
    const elapsedMs = node.active
      ? Math.max(0, nowMs - startedAtMs)
      : Math.max(0, (finishedAtMs || nowMs) - startedAtMs);
    let currentIndex = 0;
    let cursorMs = 0;
    for (let i = 0; i < stages.length - 1; i += 1) {
      cursorMs += Math.max(0, Number(stages[i] && stages[i].handoff_after_ms) || 0);
      if (elapsedMs < cursorMs) {
        currentIndex = i;
        break;
      }
      currentIndex = i + 1;
    }
    const items = stages.map((stage, index) => {
      let status = 'pending';
      if (node.failed) {
        status = index < currentIndex ? 'done' : index === currentIndex ? 'failed' : 'pending';
      } else if (node.active) {
        status = index < currentIndex ? 'done' : index === currentIndex ? 'running' : 'pending';
      } else {
        status = 'done';
      }
      return {
        key: safe(stage && stage.key).trim(),
        label: safe(stage && stage.label).trim(),
        detail: safe(stage && stage.detail).trim(),
        status: status,
      };
    });
    const currentStage = items[currentIndex] || items[0];
    const modeText = safe(node.mode).trim().toLowerCase() === 'confirm' ? '确认发布' : '进入发布评审';
    const headline = node.failed
      ? modeText + '失败'
      : currentStage && currentStage.status === 'running'
        ? modeText + '运行中'
        : modeText + '处理中';
    const detail = node.failed
      ? safe(node.error_message).trim() || '执行失败，请稍后重试'
      : safe(currentStage && currentStage.detail).trim();
    return {
      active: !!node.active,
      failed: !!node.failed,
      elapsed_ms: elapsedMs,
      headline: headline,
      detail: detail,
      items: items,
    };
  }

  function renderTrainingCenterReleaseReviewProgress(host, progress) {
    if (!host) return;
    host.innerHTML = '';
    host.classList.remove('active');
    host.classList.remove('failed');
    if (!progress) return;
    const snapshot = describeTrainingCenterReleaseReviewProgress(progress);
    host.classList.add('active');
    if (snapshot.failed) host.classList.add('failed');

    const head = document.createElement('div');
    head.className = 'tc-release-review-progress-head';
    const title = document.createElement('div');
    title.className = 'tc-release-review-progress-title';
    const titleIcon = createStatusIcon(snapshot.failed ? 'failed' : 'spinner', {
      compact: true,
      spinning: !snapshot.failed,
    });
    title.appendChild(titleIcon);
    const titleText = document.createElement('span');
    titleText.textContent =
      snapshot.headline +
      ' · 已耗时 ' +
      (typeof formatDurationMs === 'function' ? formatDurationMs(snapshot.elapsed_ms) : Math.floor(snapshot.elapsed_ms / 1000) + 's');
    title.appendChild(titleText);
    head.appendChild(title);
    host.appendChild(head);

    const detail = document.createElement('div');
    detail.className = 'tc-release-review-progress-detail';
    detail.textContent = snapshot.detail || '请稍候...';
    host.appendChild(detail);

    const stageWrap = document.createElement('div');
    stageWrap.className = 'tc-release-review-progress-stages';
    snapshot.items.forEach((item) => {
      const node = document.createElement('div');
      node.className = 'tc-release-review-progress-stage ' + safe(item.status).trim();
      const iconBox = document.createElement('span');
      iconBox.className = 'tc-release-review-progress-stage-icon';
      iconBox.appendChild(
        createStatusIcon(
          item.status === 'done' ? 'success' : item.status === 'failed' ? 'failed' : item.status === 'running' ? 'spinner' : 'pending',
          {
            compact: true,
            spinning: item.status === 'running',
          }
        )
      );
      node.appendChild(iconBox);
      const textBox = document.createElement('span');
      textBox.className = 'tc-release-review-progress-stage-text';
      textBox.textContent = safe(item.label);
      node.appendChild(textBox);
      stageWrap.appendChild(node);
    });
    host.appendChild(stageWrap);
  }

  function trainingCenterReleaseReviewFieldLabel(fieldName) {
    const key = safe(fieldName).trim().toLowerCase();
    if (key === 'target_version') return '目标版本';
    if (key === 'current_workspace_ref') return '工作区基线';
    if (key === 'first_person_summary') return '第一人称摘要';
    if (key === 'full_capability_inventory') return '全量能力清单';
    if (key === 'knowledge_scope') return '知识范围';
    if (key === 'agent_skills') return 'Agent Skills';
    if (key === 'applicable_scenarios') return '适用场景';
    if (key === 'change_summary') return '变更摘要';
    if (key === 'release_recommendation') return '发布建议';
    if (key === 'next_action_suggestion') return '下一步建议';
    return safe(fieldName).trim() || '未知字段';
  }

  function trainingCenterReleaseReviewFieldPresent(value) {
    if (Array.isArray(value)) {
      return value.some((item) => !!safe(item).trim());
    }
    if (value && typeof value === 'object') {
      return Object.keys(value).length > 0;
    }
    return !!safe(value).trim();
  }

  function trainingCenterReleaseReviewMissingReportFields(review) {
    const reviewNode = review && typeof review === 'object' ? review : {};
    const node = reviewNode.report && typeof reviewNode.report === 'object' ? reviewNode.report : {};
    const requiredFields = Array.isArray(reviewNode.required_report_fields) ? reviewNode.required_report_fields : [];
    return requiredFields
      .filter((fieldName) => !trainingCenterReleaseReviewFieldPresent(node[fieldName]))
      .map((fieldName) => trainingCenterReleaseReviewFieldLabel(fieldName));
  }

  function describeTrainingCenterReleaseReportFailure(review, localError) {
    const reviewNode = review && typeof review === 'object' ? review : {};
    const localNode = localError && typeof localError === 'object' ? localError : {};
    const chain = reviewNode.analysis_chain && typeof reviewNode.analysis_chain === 'object' ? reviewNode.analysis_chain : {};
    const rawMessage = safe(reviewNode.report_error).trim() || (safe(localNode.mode).trim().toLowerCase() === 'enter' ? safe(localNode.error_message).trim() : '');
    const errorCode = safe(reviewNode.report_error_code || chain.report_error_code || localNode.error_code).trim().toLowerCase();
    const missingFields = errorCode === 'release_review_report_incomplete' ? trainingCenterReleaseReviewMissingReportFields(reviewNode) : [];
    const chainError = safe(chain.error || localNode.error_reason || localNode.error_code).trim().toLowerCase();
    const exitCode = Number(chain.codex_summary && chain.codex_summary.exit_code);
    let summary = rawMessage;
    if (!summary || safe(summary).trim().toLowerCase() === 'release review report failed') {
      if (errorCode === 'release_review_report_incomplete' && missingFields.length) {
        summary = '生成发布报告失败：结构化报告缺少关键字段（' + missingFields.join(' / ') + '）。';
      } else if (chainError === 'codex_command_not_found') {
        summary = '生成发布报告失败：当前环境未找到 codex 命令。';
      } else if (chainError === 'codex_exec_timeout') {
        summary = '生成发布报告失败：Codex 执行超时。';
      } else if (chainError.startsWith('codex_exec_failed_exit_')) {
        summary = '生成发布报告失败：Codex 执行异常退出（exit=' + chainError.slice('codex_exec_failed_exit_'.length) + '）。';
      } else if (chainError === 'codex_result_missing') {
        summary = '生成发布报告失败：Codex 已执行，但没有产出可解析的结构化 JSON 报告。';
      } else if (Number.isFinite(exitCode) && exitCode > 0) {
        summary = '生成发布报告失败：Codex 执行异常退出（exit=' + String(exitCode) + '）。';
      }
    }
    if (!summary) return null;

    let suggestion = '';
    if (!/请先|建议|重新进入发布评审/.test(summary)) {
      if (errorCode === 'release_review_report_incomplete' && missingFields.length) {
        suggestion = '建议先检查报告文件是否缺少 ' + missingFields.join(' / ') + '，修正后点击“重新进入发布评审”。';
      } else if (safe(chain.stderr_path).trim() || safe(chain.stdout_path).trim() || safe(chain.report_path).trim()) {
        suggestion = '建议先查看分析链路里的 stderr / stdout / 报告文件，定位原因后点击“重新进入发布评审”。';
      } else {
        suggestion = '建议先处理环境或工作区问题，再点击“重新进入发布评审”。';
      }
    } else if (errorCode === 'release_review_report_incomplete' && missingFields.length && !/stderr|stdout|报告文件/.test(summary)) {
      suggestion = '建议先检查报告文件是否缺少 ' + missingFields.join(' / ') + '，修正后点击“重新进入发布评审”。';
    }

    const inspectParts = [];
    if (safe(chain.stderr_path).trim()) inspectParts.push('stderr');
    if (safe(chain.stdout_path).trim()) inspectParts.push('stdout');
    if (safe(chain.report_path).trim()) inspectParts.push('报告文件');
    return {
      summary: summary,
      suggestion: suggestion,
      inspect_hint: inspectParts.length ? '优先排查：' + inspectParts.join(' / ') : '',
    };
  }

  function findTrainingCenterReleaseFailedLog(review) {
    const logs = Array.isArray(review && review.execution_logs) ? review.execution_logs : [];
    return logs.find((item) => safe(item && item.status).trim().toLowerCase() === 'failed') || null;
  }

  function describeTrainingCenterReleasePublishFailure(review, localError) {
    const reviewNode = review && typeof review === 'object' ? review : {};
    const localNode = localError && typeof localError === 'object' ? localError : {};
    const fallback = reviewNode.fallback && typeof reviewNode.fallback === 'object' ? reviewNode.fallback : {};
    const failedLog = findTrainingCenterReleaseFailedLog(reviewNode);
    const message = safe(reviewNode.publish_error).trim() || (safe(localNode.mode).trim().toLowerCase() === 'confirm' ? safe(localNode.error_message).trim() : '');
    if (!message && !failedLog && !safe(fallback.failure_reason || fallback.error).trim()) return null;

    const phase = safe(failedLog && failedLog.phase).trim().toLowerCase();
    let suggestion = safe(fallback.next_action_suggestion).trim();
    if (!suggestion) {
      if (phase === 'git_execute') {
        suggestion = reviewNode.can_confirm
          ? '建议先检查 Git 标签/提交是否可写、是否存在冲突；修复后可直接点击“重试发布”。'
          : '建议先检查 Git 标签/提交是否可写、是否存在冲突，然后重新点击“确认发布”。';
      } else if (phase === 'release_note') {
        suggestion = reviewNode.can_confirm
          ? '建议先检查 release note 是否成功写入并符合当前版本识别规则；修正后可直接点击“重试发布”。'
          : '建议先检查 release note 是否成功写入并符合当前版本识别规则，修正后重新点击“确认发布”。';
      } else if (phase === 'verify') {
        suggestion = reviewNode.can_confirm
          ? '建议先检查 Git 标签和 release note 是否都已落盘并可被当前版本规则识别；修复后可直接点击“重试发布”。'
          : '建议先检查 Git 标签和 release note 是否都已落盘并可被当前版本规则识别，再重新点击“确认发布”。';
      } else if (safe(fallback.status).trim()) {
        suggestion = reviewNode.can_confirm
          ? '自动兜底已执行但仍未完成；请根据兜底结果修复问题后直接点击“重试发布”，若报告本身需要变化再重新进入发布评审。'
          : '自动兜底已执行但仍未完成，请根据兜底结果人工处理后再重试。';
      } else {
        suggestion = reviewNode.can_confirm
          ? '建议先查看执行日志中的失败阶段，修复后可直接点击“重试发布”。'
          : '建议先查看执行日志中的失败阶段，修复后再重新点击“确认发布”。';
      }
    }

    const detailText =
      safe(failedLog && failedLog.message).trim() ||
      safe(fallback.repair_summary).trim() ||
      safe(fallback.failure_reason || fallback.error).trim() ||
      message;
    return {
      summary: message || detailText,
      suggestion: suggestion,
      inspect_hint: phase ? '失败阶段：' + phase : '',
    };
  }

  function applyTrainingCenterReleaseReviewProgress(review, progress) {
    if (!progress) return review;
    const next = Object.assign({}, review || {});
    const mode = safe(progress.mode).trim().toLowerCase();
    if (mode === 'confirm') {
      next.release_review_state = progress.failed ? 'publish_failed' : 'publish_running';
      next.can_discard = false;
      if (progress.active) next.can_confirm = false;
      if (progress.failed && !safe(next.publish_error).trim()) {
        next.publish_error = safe(progress.error_message).trim();
      }
    } else {
      next.release_review_state = progress.failed ? 'report_failed' : 'report_generating';
      next.analysis_chain = {};
      next.report = {};
      next.report_error_code = '';
      next.report_missing_fields = [];
      next.review_decision = '';
      next.reviewer = '';
      next.review_comment = '';
      next.reviewed_at = '';
      next.publish_version = '';
      next.publish_status = '';
      next.publish_error = '';
      next.execution_logs = [];
      next.fallback = {};
      next.can_discard = false;
      if (progress.active) {
        next.can_enter = false;
        next.can_review = false;
      }
      if (progress.failed && !safe(next.report_error).trim()) {
        next.report_error = safe(progress.error_message).trim();
      }
    }
    if (!safe(next.review_id).trim()) {
      next.review_id = '__local_progress__';
    }
    return next;
  }

  function trainingCenterReleaseReviewStateText(value) {
    const key = safe(value).trim().toLowerCase();
    if (key === 'report_generating') return '生成发布报告中';
    if (key === 'report_ready') return '发布报告已就绪';
    if (key === 'review_approved') return '人工审核已通过';
    if (key === 'review_rejected') return '人工审核未通过';
    if (key === 'review_discarded') return '当前评审已废弃';
    if (key === 'publish_running') return '确认发布执行中';
    if (key === 'publish_failed') return '确认发布失败';
    if (key === 'report_failed') return '发布报告生成失败';
    return '待进入发布评审';
  }

  function trainingCenterReleaseReviewDecisionText(value) {
    const key = safe(value).trim().toLowerCase();
    if (key === 'approve_publish') return '通过并进入确认发布';
    if (key === 'reject_continue_training') return '不通过：继续训练';
    if (key === 'reject_discard_pre_release') return '不通过：舍弃预发布';
    if (key === 'discard_review') return '已废弃当前评审记录';
    return key ? safe(value) : '未提交';
  }

  function trainingCenterReleaseLogStatus(logs, phase) {
    const rows = Array.isArray(logs) ? logs.filter((item) => safe(item && item.phase).trim() === phase) : [];
    if (!rows.length) return 'pending';
    for (let index = rows.length - 1; index >= 0; index -= 1) {
      const status = safe(rows[index] && rows[index].status).trim().toLowerCase();
      if (status === 'failed') return 'failed';
      if (status === 'running') return 'current';
      if (status === 'done') return 'done';
    }
    return 'pending';
  }

  function trainingCenterReleaseSubstepLabel(kind, status) {
    const key = safe(kind).trim().toLowerCase();
    const phaseStatus = safe(status).trim().toLowerCase();
    if (key === 'git') {
      if (phaseStatus === 'done') return 'Git 发布完成';
      if (phaseStatus === 'failed') return 'Git 发布失败';
      if (phaseStatus === 'current') return 'Git 发布中';
      return 'Git 发布待执行';
    }
    if (key === 'release_note') {
      if (phaseStatus === 'done') return 'release note 已完成';
      if (phaseStatus === 'failed') return 'release note 失败';
      if (phaseStatus === 'current') return 'release note 处理中';
      return 'release note 待处理';
    }
    if (key === 'verify') {
      if (phaseStatus === 'done') return '成功校验通过';
      if (phaseStatus === 'failed') return '成功校验失败';
      if (phaseStatus === 'current') return '成功校验中';
      return '成功校验待执行';
    }
    return safe(kind).trim();
  }

  function trainingCenterReleaseReviewSteps(review) {
    const stateKey = safe(review && review.release_review_state).trim().toLowerCase();
    const publishSuccess = safe(review && review.publish_status).trim().toLowerCase() === 'success';
    return [
      {
        label: '进入发布评审',
        status: safe(review && review.review_id).trim() ? 'done' : 'current',
      },
      {
        label: '生成发布报告',
        status:
          stateKey === 'report_failed'
            ? 'failed'
            : stateKey === 'report_generating'
              ? 'current'
              : safe(review && review.review_id).trim()
                ? 'done'
                : 'pending',
      },
      {
        label: '人工审核',
        status:
          stateKey === 'review_rejected'
            || stateKey === 'review_discarded'
            ? 'failed'
            : stateKey === 'report_ready'
              ? 'current'
              : stateKey === 'review_approved' || stateKey === 'publish_running' || stateKey === 'publish_failed' || publishSuccess
                ? 'done'
                : safe(review && review.review_id).trim()
                  ? 'pending'
                  : 'pending',
      },
      {
        label: '确认发布',
        status:
          publishSuccess
            ? 'done'
            : stateKey === 'publish_failed'
              ? 'failed'
              : stateKey === 'review_approved' || stateKey === 'publish_running'
                ? 'current'
                : 'pending',
      },
    ];
  }

  function trainingCenterReleaseReviewSubsteps(review) {
    const logs = Array.isArray(review && review.execution_logs) ? review.execution_logs : [];
    const stateKey = safe(review && review.release_review_state).trim().toLowerCase();
    const publishSuccess = safe(review && review.publish_status).trim().toLowerCase() === 'success';
    const gitStatus = trainingCenterReleaseLogStatus(logs, 'git_execute');
    const releaseNoteStatus = trainingCenterReleaseLogStatus(logs, 'release_note');
    const verifyStatus = trainingCenterReleaseLogStatus(logs, 'verify');
    const hasPublishTrace =
      stateKey === 'publish_running' ||
      stateKey === 'publish_failed' ||
      publishSuccess ||
      logs.some((item) => ['prepare', 'git_execute', 'release_note', 'verify'].includes(safe(item && item.phase).trim()));
    if (!hasPublishTrace) return [];
    const finalStatus = publishSuccess ? 'done' : stateKey === 'publish_failed' ? 'failed' : stateKey === 'publish_running' ? 'current' : 'pending';
    return [
      {
        label: trainingCenterReleaseSubstepLabel('git', gitStatus === 'pending' && stateKey === 'publish_running' ? 'current' : gitStatus),
        status: gitStatus === 'pending' && stateKey === 'publish_running' ? 'current' : gitStatus,
      },
      {
        label: trainingCenterReleaseSubstepLabel('release_note', releaseNoteStatus === 'pending' && stateKey === 'publish_running' ? 'current' : releaseNoteStatus),
        status: releaseNoteStatus === 'pending' && stateKey === 'publish_running' ? 'current' : releaseNoteStatus,
      },
      {
        label: trainingCenterReleaseSubstepLabel('verify', verifyStatus === 'pending' && stateKey === 'publish_running' ? 'current' : verifyStatus),
        status: verifyStatus === 'pending' && stateKey === 'publish_running' ? 'current' : verifyStatus,
      },
      {
        label: publishSuccess ? '发布完成' : stateKey === 'publish_failed' ? '发布失败' : '完成 / 失败',
        status: finalStatus,
      },
    ];
  }

  function trainingCenterReleaseFallbackSteps(review) {
    const fallback = review && review.fallback && typeof review.fallback === 'object' ? review.fallback : {};
    const status = safe(fallback.status).trim().toLowerCase();
    if (!status) return [];
    return [
      {
        label: '兜底中',
        status: status === 'fallback_done' || status === 'fallback_failed' ? 'done' : 'current',
      },
      {
        label: '兜底完成',
        status: status === 'fallback_done' ? 'done' : 'pending',
      },
      {
        label: '兜底失败',
        status: status === 'fallback_failed' ? 'failed' : 'pending',
      },
    ];
  }

  function renderTrainingCenterReleaseReviewSteps(host, items, emptyText) {
    if (!host) return;
    host.innerHTML = '';
    if (!Array.isArray(items) || !items.length) {
      const empty = document.createElement('div');
      empty.className = 'tc-empty';
      empty.textContent = safe(emptyText || '暂无阶段信息');
      host.appendChild(empty);
      return;
    }
    items.forEach((item, index) => {
      const node = document.createElement('div');
      node.className = 'tc-release-review-step ' + safe(item && item.status).trim();
      const indexNode = document.createElement('span');
      indexNode.className = 'tc-release-review-step-index';
      indexNode.textContent = String(index + 1);
      const labelNode = document.createElement('span');
      labelNode.className = 'tc-release-review-step-label';
      labelNode.textContent = safe(item && item.label);
      node.appendChild(indexNode);
      node.appendChild(labelNode);
      host.appendChild(node);
    });
  }

  function renderTrainingCenterReleaseReviewPills(host, items, emptyText) {
    if (!host) return;
    host.innerHTML = '';
    if (!Array.isArray(items) || !items.length) {
      const empty = document.createElement('div');
      empty.className = 'tc-empty';
      empty.textContent = safe(emptyText || '暂无子阶段信息');
      host.appendChild(empty);
      return;
    }
    items.forEach((item) => {
      const badge = document.createElement('span');
      badge.className = 'tc-release-review-pill ' + safe(item && item.status).trim();
      badge.textContent = safe(item && item.label);
      host.appendChild(badge);
    });
  }

  function createTrainingCenterReleaseReportModule(title, description) {
    const section = document.createElement('section');
    section.className = 'tc-release-report-module';
    const head = document.createElement('div');
    head.className = 'tc-release-report-module-head';
    const titleNode = document.createElement('div');
    titleNode.className = 'tc-release-report-module-title';
    titleNode.textContent = safe(title);
    head.appendChild(titleNode);
    const descText = safe(description).trim();
    if (descText) {
      const descNode = document.createElement('div');
      descNode.className = 'tc-release-report-module-desc';
      descNode.textContent = descText;
      head.appendChild(descNode);
    }
    const body = document.createElement('div');
    body.className = 'tc-release-report-module-body';
    section.appendChild(head);
    section.appendChild(body);
    return {
      section,
      body,
    };
  }

  function createTrainingCenterReleaseReportCard(label, value, options) {
    const card = document.createElement('section');
    card.className = 'tc-release-report-card';
    const labelNode = document.createElement('div');
    labelNode.className = 'tc-release-report-card-label';
    labelNode.textContent = safe(label);
    const valueNode = document.createElement('div');
    const classes = ['tc-release-report-card-value'];
    if (options && options.code) classes.push('code');
    if (options && options.tag) classes.push('tag');
    if (options && options.strong) classes.push('strong');
    valueNode.className = classes.join(' ');
    valueNode.textContent = safe(value).trim() || safe(options && options.emptyText).trim() || '—';
    card.appendChild(labelNode);
    card.appendChild(valueNode);
    return card;
  }

  function createTrainingCenterReleaseReportList(items, tone) {
    const values = (Array.isArray(items) ? items : []).map((item) => safe(item).trim()).filter(Boolean);
    if (!values.length) return null;
    const list = document.createElement('ul');
    list.className = 'tc-release-report-list' + (safe(tone).trim() ? ' ' + safe(tone).trim() : '');
    values.forEach((text) => {
      const item = document.createElement('li');
      item.className = 'tc-release-report-list-item';
      item.textContent = text;
      list.appendChild(item);
    });
    return list;
  }

  function renderTrainingCenterReleaseReport(host, effectiveReview, progress, reportFailure) {
    if (!host) return;
    host.innerHTML = '';
    const stack = document.createElement('div');
    stack.className = 'tc-release-report-stack';
    host.appendChild(stack);

    if (reportFailure) {
      const alert = document.createElement('section');
      alert.className = 'tc-release-report-alert danger';
      const titleNode = document.createElement('div');
      titleNode.className = 'tc-release-report-alert-title';
      titleNode.textContent = '生成发布报告失败';
      alert.appendChild(titleNode);
      [reportFailure.summary, reportFailure.suggestion, reportFailure.inspect_hint]
        .map((item) => safe(item).trim())
        .filter(Boolean)
        .forEach((text, index) => {
          const line = document.createElement('div');
          line.className = 'tc-release-report-alert-line' + (index === 0 ? ' strong' : '');
          line.textContent = text;
          alert.appendChild(line);
        });
      stack.appendChild(alert);
    }

    const report = effectiveReview && effectiveReview.report && typeof effectiveReview.report === 'object'
      ? effectiveReview.report
      : {};
    let moduleCount = 0;
    const coreEntries = [
      {
        label: '目标版本',
        value: safe(report.target_version).trim(),
        options: {
          tag: true,
        },
      },
      {
        label: '工作区基线',
        value: safe(report.current_workspace_ref).trim(),
        options: {
          code: true,
        },
      },
      {
        label: '上一正式版本',
        value: safe(report.previous_release_version).trim(),
        options: {
          tag: true,
        },
      },
      {
        label: '发布建议',
        value: safe(report.release_recommendation).trim(),
        options: {
          strong: true,
        },
      },
      {
        label: '下一步建议',
        value: safe(report.next_action_suggestion).trim(),
      },
    ].filter((entry) => !!entry.value);
    if (coreEntries.length) {
      const module = createTrainingCenterReleaseReportModule('核心信息', '先看版本、基线与发布结论');
      const grid = document.createElement('div');
      grid.className = 'tc-release-report-core-grid';
      coreEntries.forEach((entry) => {
        grid.appendChild(createTrainingCenterReleaseReportCard(entry.label, entry.value, entry.options));
      });
      module.body.appendChild(grid);
      stack.appendChild(module.section);
      moduleCount += 1;
    }

    const firstPersonSummary = safe(report.first_person_summary).trim();
    const fullCapabilityInventory = Array.isArray(report.full_capability_inventory) ? report.full_capability_inventory : [];
    const knowledgeScope = safe(report.knowledge_scope).trim();
    const agentSkills = Array.isArray(report.agent_skills) ? report.agent_skills : [];
    const applicableScenarios = Array.isArray(report.applicable_scenarios) ? report.applicable_scenarios : [];
    const roleProfilePreviewParts = [];
    if (firstPersonSummary) {
      const summaryNode = document.createElement('div');
      summaryNode.className = 'tc-release-report-text';
      summaryNode.textContent = firstPersonSummary;
      roleProfilePreviewParts.push(summaryNode);
    }
    const inventoryList = createTrainingCenterReleaseReportList(fullCapabilityInventory, 'capability');
    if (inventoryList) {
      roleProfilePreviewParts.push(inventoryList);
    }
    const previewFacts = [
      ['角色知识范围', knowledgeScope],
      ['Agent Skills', agentSkills.join('、')],
      ['适用场景', applicableScenarios.join('、')],
    ].filter((entry) => !!safe(entry[1]).trim());
    if (previewFacts.length) {
      const previewGrid = document.createElement('div');
      previewGrid.className = 'tc-release-report-core-grid';
      previewFacts.forEach((entry) => {
        previewGrid.appendChild(createTrainingCenterReleaseReportCard(entry[0], entry[1], {}));
      });
      roleProfilePreviewParts.push(previewGrid);
    }
    if (roleProfilePreviewParts.length) {
      const module = createTrainingCenterReleaseReportModule('正式发布角色介绍预览', '确认发布成功后，角色详情页优先展示这里的第一人称全量介绍');
      roleProfilePreviewParts.forEach((node) => module.body.appendChild(node));
      stack.appendChild(module.section);
      moduleCount += 1;
    }

    const changeSummary = safe(report.change_summary).trim();
    const capabilityDeltaList = createTrainingCenterReleaseReportList(report.capability_delta, 'capability');
    if (changeSummary || capabilityDeltaList) {
      const module = createTrainingCenterReleaseReportModule('功能差异报告', '重点说明相对上一正式发布版本的变化');
      const text = document.createElement('div');
      text.className = 'tc-release-report-text';
      text.textContent = changeSummary || '当前未补充结构化变更摘要。';
      module.body.appendChild(text);
      if (capabilityDeltaList) {
        module.body.appendChild(capabilityDeltaList);
      }
      stack.appendChild(module.section);
      moduleCount += 1;
    }

    [
      ['风险清单', report.risk_list, 'risk', '发布前需要继续确认或补齐的风险点'],
      ['验证证据', report.validation_evidence, 'evidence', '报告中引用的验证动作与结果'],
      ['补充提示', report.warnings, 'warning', '非阻断但建议关注的附加说明'],
    ].forEach((entry) => {
      const title = entry[0];
      const values = entry[1];
      const tone = entry[2];
      const description = entry[3];
      const list = createTrainingCenterReleaseReportList(values, tone);
      if (!list) return;
      const module = createTrainingCenterReleaseReportModule(title, description);
      module.body.appendChild(list);
      stack.appendChild(module.section);
      moduleCount += 1;
    });

    if (!moduleCount) {
      const empty = document.createElement('section');
      empty.className = 'tc-release-report-empty';
      const titleNode = document.createElement('div');
      titleNode.className = 'tc-release-report-empty-title';
      titleNode.textContent = '结构化发布报告';
      const bodyNode = document.createElement('div');
      bodyNode.className = 'tc-release-report-empty-text';
      bodyNode.textContent = progress && safe(progress.mode).trim().toLowerCase() === 'enter'
        ? '正在生成发布报告，请稍候...'
        : safe(effectiveReview && effectiveReview.report_error).trim()
          ? '请先处理报告失败原因，再重新进入发布评审'
          : '进入发布评审后，这里会按模块展示结构化发布报告';
      empty.appendChild(titleNode);
      empty.appendChild(bodyNode);
      stack.appendChild(empty);
    }
  }

  async function fetchTrainingCenterJsonRef(refPath) {
    const path = safe(refPath).trim();
    if (!path) {
      throw new Error('当前发布版本未绑定发布报告文件。');
    }
    const requestUrl = /^https?:\/\//i.test(path)
      ? path
      : '/api/runtime-file?path=' + encodeURIComponent(path);
    const resp = await fetch(requestUrl, { cache: 'no-store' });
    const text = await resp.text();
    if (!resp.ok) {
      throw new Error('读取发布报告失败：' + path);
    }
    let payload = {};
    try {
      payload = JSON.parse(text || '{}');
    } catch (_) {
      throw new Error('发布报告文件不是有效 JSON：' + path);
    }
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
      throw new Error('发布报告文件格式不正确：' + path);
    }
    return payload;
  }

  function ensureTrainingCenterPublishedReleaseReportDialog() {
    let dialog = $('tcPublishedReleaseReportDialog');
    if (!dialog) {
      dialog = document.createElement('dialog');
      dialog.id = 'tcPublishedReleaseReportDialog';
      dialog.className = 'tc-report-dialog';

      const shell = document.createElement('div');
      shell.className = 'tc-report-dialog-shell';

      const head = document.createElement('div');
      head.className = 'tc-report-dialog-head';
      const titleWrap = document.createElement('div');
      titleWrap.className = 'tc-report-dialog-title-wrap';
      const titleNode = document.createElement('div');
      titleNode.className = 'tc-report-dialog-title';
      const metaNode = document.createElement('div');
      metaNode.className = 'tc-report-dialog-meta';
      titleWrap.appendChild(titleNode);
      titleWrap.appendChild(metaNode);
      const closeBtn = document.createElement('button');
      closeBtn.type = 'button';
      closeBtn.className = 'alt';
      closeBtn.textContent = '关闭';
      closeBtn.onclick = () => dialog.close();
      head.appendChild(titleWrap);
      head.appendChild(closeBtn);

      const errorNode = document.createElement('div');
      errorNode.className = 'tc-report-dialog-error';

      const bodyNode = document.createElement('div');
      bodyNode.className = 'tc-report-dialog-body';

      shell.appendChild(head);
      shell.appendChild(errorNode);
      shell.appendChild(bodyNode);
      dialog.appendChild(shell);
      dialog.addEventListener('click', (event) => {
        if (event.target !== dialog) return;
        const rect = dialog.getBoundingClientRect();
        const inside =
          event.clientX >= rect.left &&
          event.clientX <= rect.right &&
          event.clientY >= rect.top &&
          event.clientY <= rect.bottom;
        if (!inside) dialog.close();
      });
      document.body.appendChild(dialog);
    }
    return {
      dialog: dialog,
      titleNode: dialog.querySelector('.tc-report-dialog-title'),
      metaNode: dialog.querySelector('.tc-report-dialog-meta'),
      errorNode: dialog.querySelector('.tc-report-dialog-error'),
      bodyNode: dialog.querySelector('.tc-report-dialog-body'),
    };
  }

  async function openTrainingCenterPublishedReleaseReport(agentId, releaseRow) {
    const release = releaseRow && typeof releaseRow === 'object' ? releaseRow : {};
    const detail = trainingCenterAgentDetailById(agentId);
    const reportRef = safe(release.release_source_ref).trim() || safe(release.capability_snapshot_ref).trim();
    const reportRefType = safe(release.release_source_ref).trim() ? '发布报告' : '能力快照';
    const refs = ensureTrainingCenterPublishedReleaseReportDialog();
    if (refs.titleNode) {
      refs.titleNode.textContent = safe(release.version_label).trim()
        ? safe(release.version_label).trim() + ' 发布报告'
        : '发布报告';
    }
    if (refs.metaNode) {
      const metaParts = [];
      if (safe(release.released_at).trim()) metaParts.push('发布时间：' + safe(release.released_at).trim());
      if (safe(reportRefType).trim() && safe(reportRef).trim()) metaParts.push(reportRefType + '：' + safe(reportRef).trim());
      refs.metaNode.textContent = metaParts.join(' · ');
    }
    if (refs.errorNode) refs.errorNode.textContent = '';
    if (refs.bodyNode) {
      refs.bodyNode.innerHTML = '';
      const loading = document.createElement('div');
      loading.className = 'tc-empty';
      loading.textContent = '正在读取发布报告...';
      refs.bodyNode.appendChild(loading);
    }
    if (refs.dialog && !refs.dialog.open && typeof refs.dialog.showModal === 'function') {
      refs.dialog.showModal();
    }
    if (refs.dialog) {
      refs.dialog.dataset.releaseVersion = safe(release.version_label).trim();
      refs.dialog.dataset.agentId = safe(detail.agent_id || release.agent_id).trim();
    }
    const report = await fetchTrainingCenterJsonRef(reportRef);
    const review = defaultTrainingCenterReleaseReview(detail);
    review.review_id = safe(release.release_id).trim();
    review.agent_id = safe(detail.agent_id || release.agent_id).trim();
    review.agent_name = safe(detail.agent_name || release.agent_id).trim();
    review.target_version = safe(release.version_label).trim();
    review.publish_version = safe(release.version_label).trim();
    review.current_workspace_ref = safe(report.current_workspace_ref).trim();
    review.publish_status = 'success';
    review.publish_succeeded = true;
    review.report = report;
    review.analysis_chain = {
      report_path: safe(release.release_source_ref).trim(),
    };
    review.public_profile_markdown_path = safe(release.public_profile_ref).trim();
    review.capability_snapshot_json_path = safe(release.capability_snapshot_ref).trim();
    if (refs.bodyNode) {
      refs.bodyNode.innerHTML = '';
      const host = document.createElement('div');
      refs.bodyNode.appendChild(host);
      renderTrainingCenterReleaseReport(host, review, null, null);
    }
  }

  function renderTrainingCenterReleaseReview(agentId) {
    const reviewCard = $('tcReleaseReviewCard');
    const hintNode = $('tcReleaseReviewHint');
    const stepperNode = $('tcReleaseReviewStepper');
    const progressNode = $('tcReleaseReviewProgress');
    const substageNode = $('tcReleaseReviewSubstage');
    const reportNode = $('tcReleaseReviewReport');
    const chainNode = $('tcReleaseReviewChain');
    const manualMetaNode = $('tcReleaseReviewManualMeta');
    const logsNode = $('tcReleaseReviewLogs');
    const fallbackNode = $('tcReleaseReviewFallback');
    const enterBtn = $('tcEnterReleaseReviewBtn');
    const discardBtn = $('tcDiscardReleaseReviewBtn');
    const confirmBtn = $('tcConfirmReleaseReviewBtn');
    const decisionSelect = $('tcEvalDecisionSelect');
    const reviewerInput = $('tcEvalReviewerInput');
    const summaryInput = $('tcEvalSummaryInput');
    const submitBtn = $('tcSubmitEvalBtn');
    const reviewGrids = reviewCard ? Array.from(reviewCard.querySelectorAll('.tc-release-review-grid')) : [];
    if (!reviewCard) return;

    const key = safe(agentId).trim();
    const detail = trainingCenterAgentDetailById(key);
    const review = currentTrainingCenterReleaseReview(key);
    const progress = currentTrainingCenterReleaseReviewProgress(key);
    const localError = currentTrainingCenterReleaseReviewError(key);
    const progressMode = progress ? safe(progress.mode).trim().toLowerCase() : '';
    const effectiveReview = applyTrainingCenterReleaseReviewProgress(review, progress);
    const reportFailure = describeTrainingCenterReleaseReportFailure(effectiveReview, localError);
    const publishFailure = describeTrainingCenterReleasePublishFailure(effectiveReview, localError);
    const hasAgent = !!key;
    const hasPublishedRelease = !!currentTrainingCenterPublishedRelease(detail);
    const canReview = !!effectiveReview.can_review && !progress;
    const hasActiveReview = trainingCenterReleaseReviewIsActive(effectiveReview);
    const contextLoading =
      !!state.tcSelectedAgentContextLoading &&
      safe(state.tcSelectedAgentId).trim() === key;

    reviewCard.dataset.reviewMode = hasActiveReview ? 'active' : 'inactive';
    [stepperNode, progressNode, substageNode].forEach((node) => {
      if (node) node.hidden = !hasActiveReview;
    });
    reviewGrids.forEach((node) => {
      node.hidden = !hasActiveReview;
    });

    reviewCard.classList.toggle('disabled', !hasAgent);
    if (!hasAgent) {
      reviewCard.dataset.reviewMode = 'inactive';
      if (hintNode) hintNode.textContent = '请选择左侧角色后查看发布评审链路';
      renderTrainingCenterReleaseReviewProgress(progressNode, null);
      renderTrainingCenterReleaseReviewSteps(stepperNode, [], '未选择角色');
      renderTrainingCenterReleaseReviewPills(substageNode, [], '发布后子阶段会显示在这里');
      [reportNode, chainNode, manualMetaNode, logsNode, fallbackNode].forEach((node) => {
        if (!node) return;
        node.innerHTML = '';
        const empty = document.createElement('div');
        empty.className = 'tc-empty';
        empty.textContent = '暂无内容';
        node.appendChild(empty);
      });
      if (enterBtn) enterBtn.disabled = true;
      if (discardBtn) discardBtn.disabled = true;
      if (confirmBtn) confirmBtn.disabled = true;
      if (decisionSelect) decisionSelect.disabled = true;
      if (reviewerInput) reviewerInput.disabled = true;
      if (summaryInput) summaryInput.disabled = true;
      if (submitBtn) submitBtn.disabled = true;
      return;
    }

    if (hintNode) {
      if (contextLoading && !safe(review.review_id).trim() && !progress) {
        hintNode.textContent = '正在同步发布版本与评审上下文...';
      } else if (!hasActiveReview) {
        const stateKey = safe(effectiveReview.release_review_state).trim().toLowerCase();
        if (stateKey === 'review_discarded') {
          hintNode.textContent = '当前没有进行中的发布评审；上一条评审已废弃，如需继续请重新进入发布评审。历史正式发布记录请从“发布版本”列表点击“查看发布报告”查看。';
        } else if (safe(effectiveReview.publish_status).trim().toLowerCase() === 'success') {
          hintNode.textContent = '当前没有进行中的发布评审；本次发布已完成。历史正式发布记录请从“发布版本”列表点击“查看发布报告”查看。';
        } else if (effectiveReview.can_enter) {
          hintNode.textContent = '当前还没有进行中的发布评审；点击“进入发布评审”后，这里会展示完整评审链路。';
        } else {
          hintNode.textContent = '当前没有进行中的发布评审；历史正式发布记录请从“发布版本”列表点击“查看发布报告”查看。';
        }
      } else if (progress) {
        const snapshot = describeTrainingCenterReleaseReviewProgress(progress);
        hintNode.textContent = snapshot.headline + ' · ' + (snapshot.detail || '请稍候...');
      } else {
        const targetVersion = safe(effectiveReview.target_version).trim();
        const workspaceRef = safe(effectiveReview.current_workspace_ref).trim();
        const stateText = trainingCenterReleaseReviewStateText(effectiveReview.release_review_state);
        hintNode.textContent =
          stateText +
          (targetVersion ? ' · 目标版本 ' + targetVersion : '') +
          (workspaceRef ? ' · 工作区基线 ' + workspaceRef : '');
      }
    }

    renderTrainingCenterReleaseReviewProgress(progressNode, progress);
    renderTrainingCenterReleaseReviewSteps(stepperNode, trainingCenterReleaseReviewSteps(effectiveReview), '待进入发布评审');
    const substeps = trainingCenterReleaseReviewSubsteps(effectiveReview);
    const fallbackSteps = trainingCenterReleaseFallbackSteps(effectiveReview);
    renderTrainingCenterReleaseReviewPills(
      substageNode,
      substeps.concat(fallbackSteps),
      '确认发布后会持续展示 Git / release note / 校验 / 兜底阶段'
    );

    if (enterBtn) {
      enterBtn.disabled = !!progress || !effectiveReview.can_enter;
      enterBtn.textContent =
        progressMode === 'enter'
          ? '进入中...'
          : safe(review.review_id).trim()
            ? '重新进入发布评审'
            : '进入发布评审';
    }
    if (discardBtn) {
      discardBtn.disabled = !!progress || !effectiveReview.can_discard;
      discardBtn.textContent = '废弃当前评审';
      discardBtn.hidden = !hasActiveReview;
    }
    if (confirmBtn) {
      confirmBtn.disabled = !!progress || !effectiveReview.can_confirm;
      confirmBtn.textContent =
        progressMode === 'confirm'
          ? '发布中...'
          : safe(review.publish_status).trim().toLowerCase() === 'success'
            ? '已发布成功'
            : safe(effectiveReview.release_review_state).trim() === 'publish_failed'
              ? '重试发布'
              : '确认发布';
      confirmBtn.hidden = !hasActiveReview;
    }
    if (decisionSelect) {
      const rejectDiscardOption = Array.from(decisionSelect.options || []).find(
        (option) => safe(option && option.value).trim() === 'reject_discard_pre_release'
      );
      if (rejectDiscardOption) rejectDiscardOption.disabled = !hasPublishedRelease;
      decisionSelect.disabled = !canReview;
      decisionSelect.value = safe(effectiveReview.review_decision).trim() || (hasPublishedRelease ? 'approve_publish' : 'reject_continue_training');
      if (!hasPublishedRelease && safe(decisionSelect.value).trim() === 'reject_discard_pre_release') {
        decisionSelect.value = 'reject_continue_training';
      }
    }
    if (reviewerInput) {
      reviewerInput.disabled = !canReview;
      reviewerInput.value = safe(effectiveReview.reviewer).trim() || '';
    }
    if (summaryInput) {
      summaryInput.disabled = !canReview;
      summaryInput.value = safe(effectiveReview.review_comment).trim() || '';
    }
    if (submitBtn) {
      submitBtn.disabled = !canReview;
      submitBtn.textContent = progressMode === 'enter'
        ? '报告生成中...'
        : progressMode === 'confirm'
          ? '发布执行中...'
          : canReview
            ? '提交审核结论'
            : '等待发布报告完成';
    }

    if (!hasActiveReview) {
      const emptyStateText =
        contextLoading && !safe(review.review_id).trim() && !progress
          ? '正在同步发布评审链路'
          : '当前没有进行中的发布评审';
      const emptyHintText =
        contextLoading && !safe(review.review_id).trim() && !progress
          ? '正在同步历史发布版本与评审上下文，请稍候...'
          : '历史正式发布记录请从“发布版本”列表点击“查看发布报告”查看';
      renderTrainingCenterReleaseReviewProgress(progressNode, null);
      renderTrainingCenterReleaseReviewSteps(stepperNode, [], emptyStateText);
      renderTrainingCenterReleaseReviewPills(substageNode, [], emptyHintText);
      [reportNode, chainNode, manualMetaNode, logsNode, fallbackNode].forEach((node) => {
        if (!node) return;
        node.innerHTML = '';
        if (contextLoading && !safe(review.review_id).trim() && !progress) {
          const empty = document.createElement('div');
          empty.className = 'tc-empty';
          empty.textContent = '正在同步发布评审链路...';
          node.appendChild(empty);
        }
      });
      return;
    }

    renderTrainingCenterReleaseReport(reportNode, effectiveReview, progress, reportFailure);

    if (chainNode) {
      chainNode.innerHTML = '';
      const analysisChain = effectiveReview.analysis_chain && typeof effectiveReview.analysis_chain === 'object' ? effectiveReview.analysis_chain : {};
      const codexSummary = analysisChain.codex_summary && typeof analysisChain.codex_summary === 'object' ? analysisChain.codex_summary : {};
      const chainRows = [
        ['提示词版本', safe(analysisChain.prompt_version || review.prompt_version).trim()],
        ['提示词文件', safe(analysisChain.prompt_path).trim()],
        ['报告文件', safe(analysisChain.report_path).trim()],
        ['公开介绍快照', safe(effectiveReview.public_profile_markdown_path || analysisChain.public_profile_markdown_path).trim()],
        ['能力快照', safe(effectiveReview.capability_snapshot_json_path || analysisChain.capability_snapshot_json_path).trim()],
        ['stdout', safe(analysisChain.stdout_path).trim()],
        ['stderr', safe(analysisChain.stderr_path).trim()],
        ['trace 目录', safe(analysisChain.trace_dir).trim()],
        ['执行摘要', safe(analysisChain.command_summary).trim()],
      ].filter((entry) => !!entry[1]);
      chainRows.forEach((entry) => {
        const row = document.createElement('div');
        row.className = 'tc-release-review-row';
        const labelNode = document.createElement('span');
        labelNode.className = 'tc-release-review-row-label';
        labelNode.textContent = entry[0];
        const valueNode = document.createElement('span');
        valueNode.className = 'tc-release-review-row-value code';
        valueNode.textContent = entry[1];
        row.appendChild(labelNode);
        row.appendChild(valueNode);
        chainNode.appendChild(row);
      });
      if (Object.keys(codexSummary).length) {
        const summaryNode = document.createElement('div');
        summaryNode.className = 'tc-release-review-note';
        summaryNode.textContent =
          'Codex 摘要：exit=' +
          safe(codexSummary.exit_code) +
          ' · events=' +
          safe(codexSummary.event_count) +
          ' · duration_ms=' +
          safe(codexSummary.duration_ms);
        chainNode.appendChild(summaryNode);
      }
      const promptText = safe(analysisChain.prompt_text).trim();
      if (promptText) {
        const promptPre = document.createElement('pre');
        promptPre.className = 'tc-release-review-pre';
        promptPre.textContent = promptText;
        chainNode.appendChild(promptPre);
      }
      if (!chainRows.length && !promptText) {
        const empty = document.createElement('div');
        empty.className = 'tc-empty';
        empty.textContent = progress && safe(progress.mode).trim().toLowerCase() === 'enter'
          ? '正在委派 Codex 分析，完成后会展示提示词、stdout/stderr 与报告路径'
          : '生成发布报告后，这里会展示提示词、Codex 摘要以及 stdout/stderr/report 路径';
        chainNode.appendChild(empty);
      }
    }

    if (manualMetaNode) {
      manualMetaNode.innerHTML = '';
      const statusNode = document.createElement('div');
      statusNode.className = 'tc-release-review-note';
      statusNode.textContent = '当前状态：' + trainingCenterReleaseReviewStateText(effectiveReview.release_review_state);
      manualMetaNode.appendChild(statusNode);
      if (safe(effectiveReview.release_review_state).trim().toLowerCase() === 'review_discarded') {
        const discardedNode = document.createElement('div');
        discardedNode.className = 'tc-release-review-note';
        discardedNode.textContent = '当前评审记录已废弃；如需继续，请重新进入发布评审。';
        manualMetaNode.appendChild(discardedNode);
      }
      if (safe(effectiveReview.review_decision).trim()) {
        [
          ['审核结论', trainingCenterReleaseReviewDecisionText(effectiveReview.review_decision)],
          ['审核人', safe(effectiveReview.reviewer).trim() || '-'],
          ['审核时间', safe(effectiveReview.reviewed_at).trim() || '-'],
          ['审核意见', safe(effectiveReview.review_comment).trim() || '-'],
        ].forEach((entry) => {
          const row = document.createElement('div');
          row.className = 'tc-release-review-row';
          const labelNode = document.createElement('span');
          labelNode.className = 'tc-release-review-row-label';
          labelNode.textContent = entry[0];
          const valueNode = document.createElement('span');
          valueNode.className = 'tc-release-review-row-value';
          valueNode.textContent = entry[1];
          row.appendChild(labelNode);
          row.appendChild(valueNode);
          manualMetaNode.appendChild(row);
        });
      } else if (!canReview) {
        const empty = document.createElement('div');
        empty.className = 'tc-empty';
        empty.textContent = progressMode === 'enter'
          ? '发布报告生成中，人工审核入口暂不可用'
          : progressMode === 'confirm'
            ? '确认发布执行中，人工审核结论已锁定'
            : '发布报告完成后，才允许提交人工审核结论';
        manualMetaNode.appendChild(empty);
      }
    }

    if (logsNode) {
      logsNode.innerHTML = '';
      const logs = Array.isArray(effectiveReview.execution_logs) ? effectiveReview.execution_logs : [];
      if (publishFailure) {
        const errorNode = document.createElement('div');
        errorNode.className = 'tc-release-review-note danger';
        errorNode.textContent = publishFailure.summary;
        logsNode.appendChild(errorNode);
        const suggestionNode = document.createElement('div');
        suggestionNode.className = 'tc-release-review-note';
        suggestionNode.textContent = publishFailure.suggestion;
        logsNode.appendChild(suggestionNode);
        if (safe(publishFailure.inspect_hint).trim()) {
          const inspectNode = document.createElement('div');
          inspectNode.className = 'tc-release-review-note';
          inspectNode.textContent = publishFailure.inspect_hint;
          logsNode.appendChild(inspectNode);
        }
      }
      if (!logs.length) {
        const empty = document.createElement('div');
        empty.className = 'tc-empty';
        empty.textContent = progress && safe(progress.mode).trim().toLowerCase() === 'confirm'
          ? '确认发布运行中，执行日志返回后会持续展示 prepare / git_execute / release_note / verify / fallback 摘要'
          : '确认发布后，这里会持续显示 prepare / git_execute / release_note / verify / fallback 摘要';
        logsNode.appendChild(empty);
      } else {
        logs.forEach((log) => {
          const item = document.createElement('div');
          item.className = 'tc-release-review-log-item';
          const head = document.createElement('div');
          head.className = 'tc-release-review-log-head';
          const phase = document.createElement('span');
          phase.className = 'tc-release-review-log-phase';
          phase.textContent = safe(log && log.phase).trim() || 'unknown';
          const status = document.createElement('span');
          status.className = 'tc-release-review-pill ' + (safe(log && log.status).trim() || 'pending');
          status.textContent = safe(log && log.status).trim() || 'pending';
          head.appendChild(phase);
          head.appendChild(status);
          item.appendChild(head);
          const message = document.createElement('div');
          message.className = 'tc-release-review-log-message';
          message.textContent = safe(log && log.message).trim() || '-';
          item.appendChild(message);
          const meta = [];
          if (safe(log && log.path).trim()) meta.push('path=' + safe(log.path).trim());
          if (safe(log && log.ts).trim()) meta.push('ts=' + safe(log.ts).trim());
          if (meta.length) {
            const metaNode = document.createElement('div');
            metaNode.className = 'tc-release-review-log-meta';
            metaNode.textContent = meta.join(' · ');
            item.appendChild(metaNode);
          }
          if (log && log.details && typeof log.details === 'object' && Object.keys(log.details).length) {
            const detailsNode = document.createElement('pre');
            detailsNode.className = 'tc-release-review-pre compact';
            detailsNode.textContent = JSON.stringify(log.details, null, 2);
            item.appendChild(detailsNode);
          }
          logsNode.appendChild(item);
        });
      }
    }

    if (fallbackNode) {
      fallbackNode.innerHTML = '';
      const fallback = effectiveReview.fallback && typeof effectiveReview.fallback === 'object' ? effectiveReview.fallback : {};
      if (!safe(fallback.status).trim()) {
        const empty = document.createElement('div');
        empty.className = 'tc-empty';
        empty.textContent = '发布失败时，这里会展示失败原因、自动重试结果与下一步建议';
        fallbackNode.appendChild(empty);
      } else {
        [
          ['兜底状态', safe(fallback.status).trim()],
          ['失败原因', safe(fallback.failure_reason || fallback.error).trim() || '-'],
          ['修复摘要', safe(fallback.repair_summary).trim() || '-'],
          ['下一步建议', safe(fallback.next_action_suggestion).trim() || '-'],
        ].forEach((entry) => {
          const row = document.createElement('div');
          row.className = 'tc-release-review-row';
          const labelNode = document.createElement('span');
          labelNode.className = 'tc-release-review-row-label';
          labelNode.textContent = entry[0];
          const valueNode = document.createElement('span');
          valueNode.className = 'tc-release-review-row-value';
          valueNode.textContent = entry[1];
          row.appendChild(labelNode);
          row.appendChild(valueNode);
          fallbackNode.appendChild(row);
        });
        const repairActions = Array.isArray(fallback.repair_actions) ? fallback.repair_actions.filter((item) => safe(item).trim()) : [];
        if (repairActions.length) {
          const actionsPre = document.createElement('pre');
          actionsPre.className = 'tc-release-review-pre compact';
          actionsPre.textContent = repairActions.join('\n');
          fallbackNode.appendChild(actionsPre);
        }
        const retryResult = fallback.retry_result && typeof fallback.retry_result === 'object' ? fallback.retry_result : {};
        if (Object.keys(retryResult).length) {
          const retryPre = document.createElement('pre');
          retryPre.className = 'tc-release-review-pre compact';
          retryPre.textContent = JSON.stringify(retryResult, null, 2);
          fallbackNode.appendChild(retryPre);
        }
      }
    }
  }

  function syncTrainingCenterSwitchVersionOptions(agentId) {
    const select = $('tcSwitchVersionSelect');
    const trigger = $('tcSwitchVersionTrigger');
    const triggerText = $('tcSwitchVersionTriggerText');
    const triggerSub = $('tcSwitchVersionTriggerSub');
    const optionsNode = $('tcSwitchVersionOptions');
    if (!select || !trigger || !triggerText || !triggerSub || !optionsNode) return;
    const key = safe(agentId).trim();
    const hasSelectedAgent = !!key;
    const releases = Array.isArray(state.tcReleasesByAgent[key]) ? state.tcReleasesByAgent[key] : [];
    const detail = hasSelectedAgent ? state.tcSelectedAgentDetail || {} : {};
    const currentVersion = currentTrainingCenterDisplayedVersion(detail, releases);
    const currentRelease = releases.find((row) => safe(row && row.version_label).trim() === currentVersion) || releases[0] || null;
    select.innerHTML = '';
    optionsNode.innerHTML = '';
    if (!releases.length) {
      const empty = document.createElement('option');
      empty.value = '';
      empty.textContent = '无可切换版本';
      select.appendChild(empty);
      select.value = '';
      triggerText.textContent = hasSelectedAgent ? '无可切换版本' : '请选择角色';
      triggerSub.textContent = hasSelectedAgent ? '当前角色暂无已发布版本' : '选择角色后查看已发布版本';
      const emptyNode = document.createElement('div');
      emptyNode.className = 'tc-version-option-empty';
      emptyNode.textContent = hasSelectedAgent ? '暂无符合发布格式的版本' : '请先从左侧选择角色';
      optionsNode.appendChild(emptyNode);
      trigger.disabled = true;
      setTrainingCenterVersionDropdownOpen(false);
      return;
    }
    for (const rel of releases) {
      const version = safe(rel && rel.version_label).trim();
      if (!version) continue;
      const opt = document.createElement('option');
      opt.value = version;
      const releasedAt = safe(rel && rel.released_at).trim();
      opt.textContent = version + (releasedAt ? ' · ' + releasedAt : '');
      select.appendChild(opt);

      const optionBtn = document.createElement('button');
      optionBtn.type = 'button';
      optionBtn.className = 'tc-version-option' + (version === currentVersion ? ' active' : '');
      optionBtn.dataset.version = version;
      optionBtn.setAttribute('role', 'option');
      optionBtn.setAttribute('aria-selected', version === currentVersion ? 'true' : 'false');
      const main = document.createElement('span');
      main.className = 'tc-version-option-main';
      const name = document.createElement('span');
      name.className = 'tc-version-option-name';
      name.textContent = version;
      const sub = document.createElement('span');
      sub.className = 'tc-version-option-sub';
      sub.textContent = releasedAt ? '发布时间：' + releasedAt : '选择后立即切换';
      main.appendChild(name);
      main.appendChild(sub);
      optionBtn.appendChild(main);
      optionsNode.appendChild(optionBtn);
    }
    if (currentVersion) {
      select.value = currentVersion;
    } else if (select.options.length) {
      select.selectedIndex = 0;
    }
    triggerText.textContent = trainingCenterVersionText(currentVersion || safe(select.value).trim());
    triggerSub.textContent =
      currentRelease && safe(currentRelease.released_at).trim()
        ? '发布时间：' + safe(currentRelease.released_at).trim()
        : '选择其他发布版本后立即切换';
    trigger.disabled = false;
  }

  function updateTrainingCenterOpsGateState() {
    const detail = state.tcSelectedAgentDetail || {};
    const frozen = safe(detail.training_gate_state).toLowerCase() === 'frozen_switched';
    ['tcEnqueueManualBtn', 'tcEnqueueAutoBtn'].forEach((id) => {
      const node = $(id);
      if (node) node.disabled = frozen || !state.agentSearchRootReady;
    });
    const hint = '当前角色已冻结训练，请切回最新发布版本后再训练';
    if (frozen) {
      setTrainingCenterError(hint);
    } else if (safe($('tcOpsErr') ? $('tcOpsErr').textContent : '').includes('冻结训练')) {
      setTrainingCenterError('');
    }
  }

  function updateTrainingCenterSelectedMeta() {
    const node = $('tcSelectedAgentMeta');
    if (!node) return;
    if (!state.tcSelectedAgentId) {
      node.textContent = '未选择角色';
      return;
    }
    const name = safe(state.tcSelectedAgentName).trim() || safe(state.tcSelectedAgentId).trim();
    node.textContent = '当前角色：' + name;
  }

  function renderTrainingCenterAgentStats() {
    const stats = state.tcStats || {};
    const node = $('tcAgentStats');
    if (!node) return;
    node.textContent =
      '角色总数=' +
      safe(stats.agent_total || 0) +
      ' · Git可用=' +
      safe(stats.git_available_count || 0) +
      ' · 最新发布时间=' +
      (safe(stats.latest_release_at) || '-') +
      ' · 队列待处理=' +
      safe(stats.training_queue_pending || 0);
  }

  function filteredTrainingCenterAgents() {
    const keyword = safe($('tcAgentSearchInput') ? $('tcAgentSearchInput').value : '').trim().toLowerCase();
    const rows = Array.isArray(state.tcAgents) ? state.tcAgents : [];
    if (!keyword) return rows;
    return rows.filter((row) => {
      const name = safe(row && row.agent_name).toLowerCase();
      const caps = safe(row && row.core_capabilities).toLowerCase();
      const capability = safe(row && row.capability_summary).toLowerCase();
      const knowledge = safe(row && row.knowledge_scope).toLowerCase();
      const scenarios = safe(row && row.applicable_scenarios).toLowerCase();
      const skills = trainingCenterPortraitSkills(row && row.agent_skills).join(' ').toLowerCase();
      return (
        name.includes(keyword) ||
        caps.includes(keyword) ||
        capability.includes(keyword) ||
        knowledge.includes(keyword) ||
        scenarios.includes(keyword) ||
        skills.includes(keyword)
      );
    });
  }

  function syncTrainingCenterPlanAgentOptions() {
    const select = $('tcPlanTargetAgentSelect');
    if (!select) return;
    const current = safe(select.value).trim();
    const rows = Array.isArray(state.tcAgents) ? state.tcAgents : [];
    select.innerHTML = '';
    const first = document.createElement('option');
    first.value = '';
    first.textContent = '请选择目标角色';
    select.appendChild(first);
    for (const row of rows) {
      const agentId = safe(row && row.agent_id).trim();
      if (!agentId) continue;
      const name = safe(row && row.agent_name).trim();
      const gate = safe(row && row.training_gate_state).trim().toLowerCase();
      const visibleVersion = safe((row && (row.bound_release_version || row.latest_release_version)) || '').trim();
      const opt = document.createElement('option');
      opt.value = agentId;
      const segments = [name || agentId];
      if (visibleVersion) {
        segments.push(visibleVersion);
      }
      if (gate === 'frozen_switched') {
        segments.push('禁训');
      }
      opt.textContent = segments.join(' · ');
      select.appendChild(opt);
    }
    const prefer = safe(state.tcSelectedAgentId).trim() || current;
    if (prefer) select.value = prefer;
  }

  function trainingCenterAvatarSeed(text) {
    const raw = safe(text);
    let hash = 0;
    for (let i = 0; i < raw.length; i += 1) {
      hash = (hash * 131 + raw.charCodeAt(i)) >>> 0;
    }
    return hash >>> 0;
  }

  function trainingCenterAvatarSvg(seedText) {
    const seed = trainingCenterAvatarSeed(seedText);
    const palettes = [
      ['#e6f4ff', '#1677ff', '#073b7a'],
      ['#fff7e6', '#fa8c16', '#7a3c00'],
      ['#f6ffed', '#52c41a', '#245d0c'],
      ['#fff0f6', '#eb2f96', '#7a1450'],
      ['#f9f0ff', '#722ed1', '#3a1572'],
      ['#e6fffb', '#13c2c2', '#0d5959'],
    ];
    const tone = palettes[seed % palettes.length];
    const bg = tone[0];
    const accent = tone[1];
    const deep = tone[2];
    const shoulder = ['#f5d7c0', '#eec39f', '#d9a37e', '#f2c4a4'][seed % 4];
    const hair = ['#2f2a26', '#4b3a2a', '#1e1f26', '#3d2d4f'][seed % 4];
    return (
      "<svg class='tc-avatar-svg' viewBox='0 0 48 48' aria-hidden='true' focusable='false'>" +
      "<rect x='1.5' y='1.5' width='45' height='45' rx='12' fill='" +
      bg +
      "' stroke='" +
      accent +
      "' stroke-width='2'></rect>" +
      "<circle cx='24' cy='18' r='8.3' fill='" +
      shoulder +
      "'></circle>" +
      "<path d='M16 18.3c0-5.4 3.2-9.2 8-9.2s8 3.8 8 9.2c-2.2-1.2-4.6-1.8-8-1.8s-5.8.6-8 1.8z' fill='" +
      hair +
      "'></path>" +
      "<path d='M11 40c0-6.9 5.8-12.4 13-12.4S37 33.1 37 40' fill='" +
      accent +
      "' opacity='0.9'></path>" +
      "<path d='M16 40c0-4.2 3.6-7.6 8-7.6s8 3.4 8 7.6' fill='" +
      deep +
      "' opacity='0.9'></path>" +
      "</svg>"
    );
  }

  function isTrainingCenterSkillPlaceholder(entry) {
    const text = safe(entry).trim();
    if (!text) return true;
    const normalized = text.replace(/[\s\[\]\(\)\{\}'"`,\\]+/g, '').toLowerCase();
    return !normalized || normalized === 'null' || normalized === 'none';
  }

  function trainingCenterPortraitSkills(value) {
    if (Array.isArray(value)) {
      return value.map((item) => safe(item).trim()).filter((item) => !!item && !isTrainingCenterSkillPlaceholder(item));
    }
    const text = safe(value).trim();
    if (!text) return [];
    return text
      .split(/[\r\n,，、;；|/]+/)
      .map((item) => safe(item).trim())
      .filter((item) => !!item && !isTrainingCenterSkillPlaceholder(item));
  }

  function normalizeTrainingCenterSkillKey(value) {
    return safe(value)
      .trim()
      .toLowerCase()
      .replace(/[\s_-]+/g, '');
  }

  function trainingCenterPublishedSkillProfiles(value) {
    if (!Array.isArray(value)) return [];
    const rows = [];
    for (const item of value) {
      if (!item || typeof item !== 'object') continue;
      const name = safe(item.name).trim();
      if (!name || isTrainingCenterSkillPlaceholder(name)) continue;
      rows.push({
        name: name,
        summary: safe(item.summary).trim(),
        details: safe(item.details).trim(),
      });
    }
    return rows;
  }

  function trainingCenterPublishedSkillMap(release, fallbackSkills) {
    const map = Object.create(null);
    const profiles = trainingCenterPublishedSkillProfiles(release && release.skill_profiles);
    for (const profile of profiles) {
      const key = normalizeTrainingCenterSkillKey(profile.name);
      if (!key) continue;
      if (!map[key]) {
        map[key] = profile;
        continue;
      }
      if (!safe(map[key].summary).trim() && safe(profile.summary).trim()) {
        map[key].summary = profile.summary;
      }
      if (!safe(map[key].details).trim() && safe(profile.details).trim()) {
        map[key].details = profile.details;
      }
    }
    const names = trainingCenterPortraitSkills(release && release.skills);
    for (const name of names) {
      const key = normalizeTrainingCenterSkillKey(name);
      if (!key || map[key]) continue;
      map[key] = { name: name, summary: '', details: '' };
    }
    if (!Object.keys(map).length && safe(release && release.version_label).trim()) {
      const fallbackNames = trainingCenterPortraitSkills(fallbackSkills);
      for (const name of fallbackNames) {
        const key = normalizeTrainingCenterSkillKey(name);
        if (!key || map[key]) continue;
        map[key] = {
          name: name,
          summary: '',
          details: '',
          inferred: true,
        };
      }
    }
    return map;
  }

  function trainingCenterSkillSummaryText(profile) {
    const summary = safe(profile && profile.summary).trim();
    if (summary) return summary;
    const details = safe(profile && profile.details).trim();
    if (details) return '已发布，展开查看详情';
    if (profile && profile.inferred) return '已发布，当前版本未单独记录技能详情';
    return '未发布';
  }

  function trainingCenterSkillStateText(isPublished) {
    return isPublished ? '已发布' : '未发布';
  }

  function renderTrainingCenterSkillCards(localSkills, publishedRelease, fallbackPublishedSkills) {
    const skills = trainingCenterPortraitSkills(localSkills);
    if (!skills.length) {
      return '当前工作区未发现本地 Agent Skills';
    }
    const publishedSkillMap = trainingCenterPublishedSkillMap(publishedRelease || {}, fallbackPublishedSkills);
    return (
      "<div class='tc-agent-skill-cards'>" +
      skills
        .map((skillName) => {
          const key = normalizeTrainingCenterSkillKey(skillName);
          const isPublished = !!(key && Object.prototype.hasOwnProperty.call(publishedSkillMap, key));
          const profile = publishedSkillMap[key] || { name: skillName, summary: '', details: '' };
          const summaryText = trainingCenterSkillSummaryText(profile);
          const detailsText = safe(profile && profile.details).trim();
          return (
            "<div class='tc-agent-skill-card'>" +
            "<div class='tc-agent-skill-head'>" +
            "<div class='tc-agent-skill-name'>" +
            safe(skillName) +
            '</div>' +
            "<span class='tc-agent-skill-state " +
            (isPublished ? 'published' : 'unpublished') +
            "'>" +
            trainingCenterSkillStateText(isPublished) +
            '</span>' +
            '</div>' +
            "<div class='tc-agent-skill-summary'>" +
            safe(summaryText) +
            '</div>' +
            (detailsText
              ? "<details class='tc-agent-skill-detail'>" +
                "<summary>查看详情</summary>" +
                "<div class='tc-agent-skill-detail-body'>" +
                safe(detailsText) +
                '</div>' +
                '</details>'
              : '') +
            '</div>'
          );
        })
        .join('') +
      '</div>'
    );
  }

  function trainingCenterRolePositionText(value, maxLen) {
    const text = safe(value).trim();
    if (!text) return '未确定';
    const size = Math.max(1, Number(maxLen) || 50);
    if (text.length <= size) return text;
    if (size <= 3) return text.slice(0, size);
    return text.slice(0, size - 3).trimEnd() + '...';
  }

  function trainingCenterProfileTextItems(value, limit) {
    const rows = safe(value)
      .split(/[\r\n,，、;；|/]+/)
      .map((item) => safe(item).trim())
      .filter((item) => !!item);
    return rows.slice(0, Math.max(1, Number(limit) || 6));
  }

  function trainingCenterRoleProfile(detail) {
    const raw = detail && detail.role_profile && typeof detail.role_profile === 'object'
      ? detail.role_profile
      : {};
    const normalizeItems = (value, limit) => {
      if (Array.isArray(value)) {
        return value.map((item) => safe(item).trim()).filter(Boolean).slice(0, Math.max(1, Number(limit) || 6));
      }
      return trainingCenterProfileTextItems(value, limit);
    };
    return {
      profile_source: safe(raw.profile_source).trim(),
      fallback_reason: safe(raw.fallback_reason).trim(),
      source_release_id: safe(raw.source_release_id).trim(),
      source_release_version: safe(raw.source_release_version).trim(),
      source_ref: safe(raw.source_ref).trim(),
      first_person_summary: safe(raw.first_person_summary).trim(),
      what_i_can_do: normalizeItems(raw.what_i_can_do, 5),
      full_capability_inventory: normalizeItems(raw.full_capability_inventory, 12),
      knowledge_scope: safe(raw.knowledge_scope).trim(),
      agent_skills: normalizeItems(raw.agent_skills, 12),
      applicable_scenarios: normalizeItems(raw.applicable_scenarios, 6),
      version_notes: safe(raw.version_notes).trim(),
      public_profile_ref: safe(raw.public_profile_ref).trim(),
      capability_snapshot_ref: safe(raw.capability_snapshot_ref).trim(),
    };
  }

  function trainingCenterRoleProfileSourceText(source) {
    const key = safe(source).trim().toLowerCase();
    if (key === 'latest_release_report') return '最新正式发布报告';
    if (key === 'structured_fields_fallback') return '结构化字段回退';
    return '未绑定';
  }

  function trainingCenterRoleProfileFallbackReasonText(reason) {
    const key = safe(reason).trim().toLowerCase();
    if (key === 'latest_release_report_missing') return '正式发布报告快照缺失';
    if (key === 'latest_release_report_invalid') return '正式发布报告快照解析失败';
    if (key === 'no_released_profile') return '当前还没有可用的正式发布画像';
    return safe(reason).trim();
  }

  function trainingCenterPortraitIntroText(detail, publishedRelease, highlights) {
    const roleProfile = trainingCenterRoleProfile(detail);
    if (roleProfile.first_person_summary) return roleProfile.first_person_summary;
    const intro =
      safe((publishedRelease && (publishedRelease.capability_summary || publishedRelease.change_summary)) || '').trim() ||
      safe(detail && (detail.capability_summary || detail.core_capabilities)).trim();
    if (intro) return intro;
    if (Array.isArray(highlights) && highlights.length) return highlights.join('；');
    return safe((publishedRelease && publishedRelease.knowledge_scope) || detail.knowledge_scope).trim() || '当前暂无已发布角色简介。';
  }

  function trainingCenterWhatICanDoLines(item) {
    const detail = item || {};
    const roleProfile = trainingCenterRoleProfile(detail);
    if (roleProfile.what_i_can_do.length) {
      return roleProfile.what_i_can_do.slice(0, 5);
    }
    const candidateLines = [];
    const pushLines = (text) => {
      const rows = safe(text)
        .split(/[\r\n|；;。!?！？]+/)
        .map((line) => safe(line).replace(/^(能力|知识|技能|场景)\s*[:：]/, '').trim())
        .filter((line) => !!line);
      for (const line of rows) {
        if (!candidateLines.includes(line)) {
          candidateLines.push(line);
        }
      }
    };
    pushLines(detail.capability_summary);
    pushLines(detail.core_capabilities);
    return candidateLines.slice(0, 5);
  }

  function currentTrainingCenterPublishedRelease(item) {
    const detail = item || {};
    const agentId = safe(detail.agent_id).trim();
    if (!agentId) return null;
    const releases = Array.isArray(state.tcReleasesByAgent[agentId]) ? state.tcReleasesByAgent[agentId] : [];
    if (!releases.length) return null;
    const preferredVersion = safe(detail.bound_release_version || detail.latest_release_version).trim();
    if (preferredVersion) {
      const matched = releases.find((row) => safe(row && row.version_label).trim() === preferredVersion);
      if (matched) {
        return matched;
      }
    }
    return releases[0] || null;
  }

  function currentTrainingCenterDisplayedVersion(item, releaseRows) {
    const detail = item || {};
    const agentId = safe(detail.agent_id).trim();
    const releases = Array.isArray(releaseRows)
      ? releaseRows
      : agentId && Array.isArray(state.tcReleasesByAgent[agentId])
        ? state.tcReleasesByAgent[agentId]
        : [];
    const versionSet = new Set(
      releases
        .map((row) => safe(row && row.version_label).trim())
        .filter((value) => !!value)
    );
    const candidates = [
      safe(detail.bound_release_version).trim(),
      safe(detail.current_version).trim(),
      safe(detail.latest_release_version).trim(),
    ];
    for (const value of candidates) {
      if (!value) continue;
      if (!versionSet.size || versionSet.has(value)) {
        return value;
      }
    }
    return releases.length ? safe(releases[0] && releases[0].version_label).trim() : '';
  }

  function setTrainingCenterVersionDropdownOpen(nextOpen) {
    const host = $('tcVersionDropdown');
    const trigger = $('tcSwitchVersionTrigger');
    const panel = $('tcSwitchVersionPanel');
    const options = $('tcSwitchVersionOptions');
    const hasOptions =
      !!options &&
      Array.from(options.children || []).some((node) => node instanceof HTMLElement && node.classList.contains('tc-version-option'));
    const canOpen = !!host && !!trigger && !!panel && !trigger.disabled && hasOptions;
    const open = !!nextOpen && canOpen;
    state.tcVersionDropdownOpen = open;
    if (host) host.classList.toggle('open', open);
    if (trigger) trigger.setAttribute('aria-expanded', open ? 'true' : 'false');
  }

  function hasTrainingCenterPublishedRelease(item) {
    return !!currentTrainingCenterPublishedRelease(item);
  }

  function renderTrainingCenterAvatarPreview(item, forceDefault) {
    const previewNode = $('tcAvatarPreview');
    if (!previewNode) return;
    if (forceDefault) {
      previewNode.innerHTML = trainingCenterAvatarSvg('default-avatar');
      return;
    }
    const seed = safe((item && item.vector_icon) || (item && item.agent_name) || (item && item.agent_id) || '');
    const avatarUri = safe(item && item.avatar_uri).trim();
    previewNode.innerHTML = '';
    if (!avatarUri) {
      previewNode.innerHTML = trainingCenterAvatarSvg(seed || 'default-avatar');
      return;
    }
    const image = document.createElement('img');
    image.className = 'tc-avatar-image';
    image.alt = '角色头像';
    image.src = avatarUri;
    image.onerror = () => {
      previewNode.innerHTML = trainingCenterAvatarSvg(seed || 'default-avatar');
    };
    previewNode.appendChild(image);
  }

  function renderTrainingCenterPortrait(item) {
    const portraitNode = $('tcPortraitFields');
    if (!portraitNode) return;
    const portraitCard = $('tcPortraitCard');
    if (portraitCard) {
      portraitCard.style.maxHeight = 'none';
      portraitCard.style.overflow = 'visible';
      portraitCard.style.overscrollBehavior = 'auto';
    }
    portraitNode.style.maxHeight = 'none';
    portraitNode.style.overflow = 'visible';
    portraitNode.style.paddingRight = '0';
    const detail = item || {};
    const detailIdentity = safe(detail.agent_id || detail.agent_name).trim();
    if (!detailIdentity) {
      portraitNode.style.display = '';
      portraitNode.innerHTML =
        "<div class='tc-empty-detail'>" +
        "<div class='tc-empty-detail-title'>从左侧选择角色</div>" +
        "<div class='tc-empty-detail-desc'>选择后可查看角色介绍、发布模板信息、本地 Agent Skills 与版本切换入口。</div>" +
        "<div class='tc-empty-detail-pills'>" +
        "<span class='tc-badge'>角色介绍</span>" +
        "<span class='tc-badge'>发布模板</span>" +
        "<span class='tc-badge'>Agent Skills</span>" +
        "<span class='tc-badge'>版本切换</span>" +
        '</div>' +
        '</div>';
      renderTrainingCenterAvatarPreview(null, true);
      return;
    }
    const publishedRelease = currentTrainingCenterPublishedRelease(detail);
    const roleProfile = trainingCenterRoleProfile(detail);
    const localAgentSkills = trainingCenterPortraitSkills(detail.agent_skills);
    const publishedSkillMap = trainingCenterPublishedSkillMap(publishedRelease || {}, localAgentSkills);
    const publishedSkillRows = Object.keys(publishedSkillMap).map((key) => publishedSkillMap[key]).filter((row) => !!row);
    const introText = trainingCenterPortraitIntroText(detail, publishedRelease, roleProfile.what_i_can_do);
    const whatICanDo = roleProfile.what_i_can_do.length ? roleProfile.what_i_can_do : trainingCenterWhatICanDoLines(detail);
    const fullCapabilityInventory = roleProfile.full_capability_inventory.length
      ? roleProfile.full_capability_inventory
      : whatICanDo;
    const knowledgeScope = roleProfile.knowledge_scope || safe(publishedRelease && publishedRelease.knowledge_scope).trim();
    const scenarioItems = roleProfile.applicable_scenarios.length
      ? roleProfile.applicable_scenarios
      : trainingCenterProfileTextItems(safe(publishedRelease && publishedRelease.applicable_scenarios).trim(), 6);
    const skillItems = roleProfile.agent_skills.length
      ? roleProfile.agent_skills
      : (
        publishedSkillRows.length
          ? publishedSkillRows.map((row) => safe(row.name).trim()).filter((row) => !!row)
          : localAgentSkills
      );
    const versionNotes = roleProfile.version_notes || safe(publishedRelease && publishedRelease.version_notes).trim();
    const skillHint = roleProfile.profile_source === 'structured_fields_fallback'
      ? '当前角色详情来自结构化字段回退；正式发布报告补齐后会优先替换。'
      : (
        publishedRelease && !publishedSkillRows.some((skill) => safe(skill.summary || skill.details).trim())
          ? '当前版本仅同步到技能标签，未单独补充技能说明。'
          : ''
      );
    const sourceText = trainingCenterRoleProfileSourceText(roleProfile.profile_source);
    const sourceDetail = sourceText +
      (roleProfile.source_release_version ? ' · 来源版本=' + roleProfile.source_release_version : '') +
      (roleProfile.fallback_reason ? ' · 原因=' + trainingCenterRoleProfileFallbackReasonText(roleProfile.fallback_reason) : '');
    const portraitSections = [];
    const addTextSection = (label, value) => {
      const text = safe(value).trim();
      if (!text) return;
      portraitSections.push(
        "<section class='tc-portrait-item'>" +
          "<div class='tc-portrait-k'>" + safe(label) + '</div>' +
          "<div class='tc-portrait-v'>" + safe(text) + '</div>' +
        '</section>'
      );
    };
    const addListSection = (label, rows, extraTip) => {
      const list = Array.isArray(rows) ? rows.map((row) => safe(row).trim()).filter((row) => !!row) : [];
      if (!list.length) return;
      portraitSections.push(
        "<section class='tc-portrait-item'>" +
          "<div class='tc-portrait-k'>" + safe(label) + '</div>' +
          "<ul class='tc-portrait-v tc-portrait-list'>" +
            list.map((row) => '<li>' + safe(row) + '</li>').join('') +
          '</ul>' +
          (extraTip ? "<div class='tc-portrait-v'>" + safe(extraTip) + '</div>' : '') +
        '</section>'
      );
    };
    addTextSection('角色详情来源', sourceDetail);
    addTextSection('我是', introText);
    addListSection('我当前能做什么', whatICanDo);
    addListSection('全量能力清单', fullCapabilityInventory);
    addTextSection('角色知识范围', knowledgeScope);
    addListSection('适用场景', scenarioItems);
    addListSection('Agent Skills', skillItems, skillHint);
    addTextSection('版本备注', versionNotes);
    portraitNode.style.display = '';
    portraitNode.innerHTML = portraitSections.length
      ? portraitSections.join('')
      : (
        "<section class='tc-portrait-item'>" +
          "<div class='tc-portrait-k'>发布状态</div>" +
          "<div class='tc-portrait-v'>" + safe(publishedRelease ? '当前版本尚未补充角色简介详情。' : '当前还没有可用的发布简介。') + '</div>' +
        '</section>'
      );
    renderTrainingCenterAvatarPreview(detail);
  }

  function renderTrainingCenterCardTags(tags) {
    const visibleTags = visibleTrainingStatusTags(tags);
    if (!visibleTags.length) {
      return "<span class='tc-badge'>已发布</span>";
    }
    return visibleTags.map((tag) => "<span class='tc-badge'>" + trainingStatusTagText(tag) + '</span>').join('');
  }

  function renderTrainingCenterAgentList() {
    const box = $('tcAgentList');
    if (!box) return;
    box.innerHTML = '';
    const rows = filteredTrainingCenterAgents();
    if (!rows.length) {
      const empty = document.createElement('div');
      empty.className = 'tc-empty';
      empty.textContent = state.agentSearchRootReady ? '暂无角色资产数据' : '根路径未就绪，功能已锁定';
      box.appendChild(empty);
      return;
    }
    for (const row of rows) {
      const agentId = safe(row && row.agent_id).trim();
      if (!agentId) continue;
      const node = document.createElement('div');
      node.className = 'tc-item tc-agent-card' + (safe(state.tcSelectedAgentId) === agentId ? ' active' : '');
      const tags = visibleTrainingStatusTags(row.status_tags);
      const iconSeed = safe(row.vector_icon || row.agent_name || agentId);
      const cardTitle = safe(row.agent_name || agentId);
      const releaseLine = safe(row.last_release_at).trim();
      const visibleVersion = safe(row.bound_release_version || row.latest_release_version).trim();
      const capabilitySummary = safe(row.capability_summary || row.core_capabilities).trim();
      const knowledgeScope = safe(row.knowledge_scope).trim();
      const rolePosition = visibleVersion
        ? trainingCenterRolePositionText(capabilitySummary || knowledgeScope, 50)
        : '未确定';
      const cardMetaRows = [];
      cardMetaRows.push("<div class='tc-item-sub tc-card-line'>角色定位：" + rolePosition + '</div>');
      if (releaseLine) {
        cardMetaRows.push("<div class='tc-item-sub tc-card-line'>最近发布时间：" + releaseLine + '</div>');
      }
      node.innerHTML =
        "<div class='tc-card-head'>" +
        "<span class='tc-vector-icon'>" +
        trainingCenterAvatarSvg(iconSeed) +
        '</span>' +
        "<div class='tc-card-title-wrap'>" +
        "<div class='tc-item-title'>" +
        cardTitle +
        '</div>' +
        renderTrainingCenterVersionPill(visibleVersion) +
        '</div>' +
        "<span class='tc-card-chip'>工牌</span>" +
        '</div>' +
        cardMetaRows.join('') +
        "<div class='tc-card-tags'>" +
        renderTrainingCenterCardTags(tags) +
        '</div>';
      node.onclick = () => {
        setTrainingCenterVersionDropdownOpen(false);
        state.tcSelectedAgentId = agentId;
        state.tcSelectedAgentName = safe(row.agent_name || '');
        state.tcSelectedAgentDetail = row;
        syncTrainingCenterPlanAgentOptions();
        updateTrainingCenterSelectedMeta();
        renderTrainingCenterAgentList();
        refreshTrainingCenterSelectedAgentContext(agentId).catch((err) => {
          setTrainingCenterDetailError(err.message || String(err));
        });
        applyGateState();
      };
      box.appendChild(node);
    }
  }

  function renderTrainingCenterReleases(agentId) {
    const box = $('tcReleaseList');
    if (!box) return;
    box.innerHTML = '';
    const key = safe(agentId).trim();
    const releases = state.tcReleasesByAgent[key] || [];
    syncTrainingCenterSwitchVersionOptions(key);
    if (!releases.length) {
      const empty = document.createElement('div');
      empty.className = 'tc-empty';
      empty.textContent =
        state.tcSelectedAgentContextLoading && safe(state.tcSelectedAgentId).trim() === key
          ? '正在同步发布版本...'
          : '暂无符合发布格式的版本';
      box.appendChild(empty);
      return;
    }
    for (const row of releases) {
      const node = document.createElement('div');
      node.className = 'tc-item';
      const titleNode = document.createElement('div');
      titleNode.className = 'tc-item-title';
      titleNode.textContent = safe(row.version_label || '-');
      const badgeNode = document.createElement('span');
      badgeNode.className = 'tc-badge ok';
      badgeNode.textContent = '发布版本';
      titleNode.appendChild(document.createTextNode(' '));
      titleNode.appendChild(badgeNode);
      node.appendChild(titleNode);

      const timeNode = document.createElement('div');
      timeNode.className = 'tc-item-sub';
      timeNode.textContent = '发布时间：' + safe(row.released_at || '-');
      node.appendChild(timeNode);

      const summaryNode = document.createElement('div');
      summaryNode.className = 'tc-item-sub';
      summaryNode.textContent = '发布说明：' + safe(row.version_notes || row.change_summary || '-');
      node.appendChild(summaryNode);
      node.dataset.releaseVersion = safe(row.version_label || '').trim();

      const reportRef = safe(row.release_source_ref || row.capability_snapshot_ref).trim();
      if (reportRef) {
        const actionsNode = document.createElement('div');
        actionsNode.className = 'tc-release-row';
        const reportBtn = document.createElement('button');
        reportBtn.type = 'button';
        reportBtn.className = 'alt';
        reportBtn.textContent = '查看发布报告';
        reportBtn.dataset.releaseVersion = safe(row.version_label || '').trim();
        reportBtn.onclick = async () => {
          try {
            reportBtn.disabled = true;
            await openTrainingCenterPublishedReleaseReport(key, row);
          } catch (err) {
            const refs = ensureTrainingCenterPublishedReleaseReportDialog();
            if (refs.errorNode) refs.errorNode.textContent = safe(err && err.message ? err.message : err);
            if (refs.bodyNode) {
              refs.bodyNode.innerHTML = '';
              const empty = document.createElement('div');
              empty.className = 'tc-empty';
              empty.textContent = '当前发布报告暂不可展示。';
              refs.bodyNode.appendChild(empty);
            }
            if (refs.dialog && !refs.dialog.open && typeof refs.dialog.showModal === 'function') {
              refs.dialog.showModal();
            }
          } finally {
            reportBtn.disabled = false;
          }
        };
        actionsNode.appendChild(reportBtn);
        node.appendChild(actionsNode);
      } else {
        const hintNode = document.createElement('div');
        hintNode.className = 'tc-item-sub';
        hintNode.textContent = '发布报告：当前版本未绑定可展示的发布报告文件';
        hintNode.dataset.releaseVersion = safe(row.version_label || '').trim();
        node.appendChild(hintNode);
      }
      box.appendChild(node);
    }
  }

  function renderTrainingCenterNormalCommits(agentId) {
    const box = $('tcNormalCommitList');
    const detailsNode = $('tcNormalCommitDetails');
    const summaryTextNode = $('tcNormalCommitSummaryText');
    const countNode = $('tcNormalCommitCount');
    if (!box) return;
    box.innerHTML = '';
    const key = safe(agentId).trim();
    const rows = state.tcNormalCommitsByAgent && state.tcNormalCommitsByAgent[key]
      ? state.tcNormalCommitsByAgent[key]
      : [];
    if (summaryTextNode) {
      summaryTextNode.textContent = rows.length ? '查看 Git 提交记录详情' : '暂无 Git 提交记录';
    }
    if (countNode) {
      countNode.textContent = rows.length ? String(rows.length) : '';
    }
    if (detailsNode) {
      detailsNode.hidden = !rows.length;
      if (!rows.length) detailsNode.open = false;
    }
    if (!rows.length) {
      return;
    }
    for (const row of rows) {
      const reasons = Array.isArray(row.invalid_reasons) ? row.invalid_reasons.filter((v) => !!safe(v).trim()) : [];
      const node = document.createElement('div');
      node.className = 'tc-item';
      node.innerHTML =
        "<div class='tc-item-title'>" +
        safe(row.version_label || '-') +
        " <span class='tc-badge warn'>普通提交</span>" +
        '</div>' +
        "<div class='tc-item-sub'>发布时间：" +
        safe(row.released_at || '-') +
        '</div>' +
        "<div class='tc-item-sub'>说明：" +
        safe(row.version_notes || row.change_summary || '-') +
        '</div>' +
        "<div class='tc-item-sub'>未通过原因：" +
        (reasons.length ? reasons.join(', ') : '发布字段不完整') +
        '</div>';
      box.appendChild(node);
    }
  }

  function renderTrainingCenterAgentDetail() {
    const titleNode = $('tcAgentDetailTitle');
    const subtitleNode = $('tcAgentDetailSubtitle');
    const metaNode = $('tcAgentDetailMeta');
    const stateNode = $('tcAgentLifecycleMeta');
    const detailBody = $('tcAgentDetailBody');
    const detailNode = document.querySelector('#tcModuleAgents .tc-detail');
    const enterOpsBtn = $('tcEnterOpsBtn');
    const avatarBtn = $('tcSetAvatarBtn');
    const switchSelect = $('tcSwitchVersionSelect');
    const switchTrigger = $('tcSwitchVersionTrigger');
    const switchTriggerText = $('tcSwitchVersionTriggerText');
    const switchTriggerSub = $('tcSwitchVersionTriggerSub');
    const discardBtn = $('tcDiscardPreReleaseBtn');
    const evalDecisionSelect = $('tcEvalDecisionSelect');
    const item = state.tcSelectedAgentDetail || null;
    const contextLoading =
      !!item &&
      !!state.tcSelectedAgentContextLoading &&
      safe(state.tcSelectedAgentId).trim() === safe(item.agent_id).trim();
    if (detailNode instanceof HTMLElement) {
      detailNode.style.minWidth = '0';
      detailNode.style.maxWidth = '100%';
      detailNode.style.overflowX = 'hidden';
      detailNode.style.overflowY = 'auto';
      detailNode.style.overscrollBehavior = 'contain';
    }
    if (metaNode instanceof HTMLElement) {
      metaNode.style.display = 'block';
      metaNode.style.minWidth = '0';
      metaNode.style.maxWidth = '100%';
      metaNode.style.overflow = 'visible';
      metaNode.style.whiteSpace = 'normal';
      metaNode.style.overflowWrap = 'anywhere';
      metaNode.style.wordBreak = 'break-word';
      metaNode.style.lineHeight = '1.45';
    }
    if (stateNode instanceof HTMLElement) {
      stateNode.style.display = 'flex';
      stateNode.style.flexWrap = 'wrap';
      stateNode.style.gap = '6px';
      stateNode.style.minWidth = '0';
      stateNode.style.maxWidth = '100%';
      stateNode.style.overflow = 'visible';
      stateNode.style.whiteSpace = 'normal';
      stateNode.style.overflowWrap = 'anywhere';
      stateNode.style.wordBreak = 'break-word';
    }
    if (!item) {
      setTrainingCenterVersionDropdownOpen(false);
      if (titleNode) titleNode.textContent = '角色详情';
      if (subtitleNode) subtitleNode.textContent = '请选择左侧角色工卡';
      if (metaNode) metaNode.textContent = '路径/版本信息将在这里展示';
      if (stateNode) stateNode.innerHTML = '';
      if (detailBody instanceof HTMLElement) detailBody.style.display = 'none';
      if (enterOpsBtn) enterOpsBtn.disabled = true;
      if (avatarBtn) avatarBtn.disabled = true;
      if (switchSelect) {
        switchSelect.value = '';
        switchSelect.disabled = true;
      }
      if (switchTrigger) switchTrigger.disabled = true;
      if (switchTriggerText) switchTriggerText.textContent = trainingCenterVersionText('');
      if (switchTriggerSub) switchTriggerSub.textContent = '请选择左侧角色工卡';
      if (discardBtn) discardBtn.disabled = true;
      if (evalDecisionSelect) {
        const rejectDiscardOption = Array.from(evalDecisionSelect.options || []).find(
          (option) => safe(option && option.value).trim() === 'reject_discard_pre_release'
        );
        if (rejectDiscardOption) rejectDiscardOption.disabled = true;
        if (safe(evalDecisionSelect.value).trim() === 'reject_discard_pre_release') {
          evalDecisionSelect.value = 'reject_continue_training';
        }
      }
      setTrainingCenterAgentActionResult('等待发布管理操作...');
      renderTrainingCenterPortrait(null);
      renderTrainingCenterReleases('');
      renderTrainingCenterNormalCommits('');
      renderTrainingCenterReleaseReview('');
      updateTrainingCenterOpsGateState();
      return;
    }
    const publishedRelease = currentTrainingCenterPublishedRelease(item);
    const hasPublishedRelease = !!publishedRelease;
    const roleProfile = trainingCenterRoleProfile(item);
    const roleSubtitle = trainingCenterRolePositionText(
      safe(roleProfile.first_person_summary || (publishedRelease && (publishedRelease.capability_summary || publishedRelease.knowledge_scope)) || '').trim(),
      50
    );
    if (titleNode) {
      titleNode.textContent = '角色详情 · ' + safe(item.agent_name || item.agent_id || '');
    }
    if (subtitleNode) {
      subtitleNode.textContent = '角色介绍：' + roleSubtitle + ' · 来源=' + trainingCenterRoleProfileSourceText(roleProfile.profile_source || '');
    }
    if (detailBody instanceof HTMLElement) detailBody.style.display = '';
    if (avatarBtn) avatarBtn.disabled = false;
    if (switchSelect) {
      const releaseRows = Array.isArray(state.tcReleasesByAgent[safe(item.agent_id).trim()]) ? state.tcReleasesByAgent[safe(item.agent_id).trim()] : [];
      switchSelect.disabled = !releaseRows.length;
      if (switchTrigger) switchTrigger.disabled = !releaseRows.length;
    }
    if (evalDecisionSelect) {
      const rejectDiscardOption = Array.from(evalDecisionSelect.options || []).find(
        (option) => safe(option && option.value).trim() === 'reject_discard_pre_release'
      );
      if (rejectDiscardOption) rejectDiscardOption.disabled = !hasPublishedRelease;
      if (!hasPublishedRelease && safe(evalDecisionSelect.value).trim() === 'reject_discard_pre_release') {
        evalDecisionSelect.value = 'reject_continue_training';
      }
    }
    if (metaNode) {
      const tags = visibleTrainingStatusTags(item.status_tags);
      const preState = safe(item.pre_release_state || item.lifecycle_state || '').toLowerCase();
      const preReason = safe(item.pre_release_reason || '').trim();
      const preCheckedAt = safe(item.pre_release_checked_at || '').trim();
      const workspacePath = safe(item.workspace_path).trim();
      const currentVersion = safe(item.current_version).trim();
      const boundReleaseVersion = safe(item.bound_release_version).trim();
      const latestReleaseVersion = safe(item.latest_release_version).trim();
      const lastReleaseAt = safe(item.last_release_at).trim();
      const lines = [
        '工作区路径=' + (workspacePath || '-'),
        '发布状态=' + (publishedRelease ? '已发布' : '未发布'),
        '预发布判定=' + trainingLifecycleText(preState || 'unknown'),
      ];
      if (currentVersion && (boundReleaseVersion || latestReleaseVersion)) {
        lines.push('当前版本=' + currentVersion);
      }
      if (boundReleaseVersion) {
        lines.push('绑定发布版本=' + boundReleaseVersion);
      }
      if (latestReleaseVersion) {
        lines.push('最新发布版本=' + latestReleaseVersion);
      }
      if (lastReleaseAt) {
        lines.push('最近发布时间=' + lastReleaseAt);
      }
      lines.push('角色详情来源=' + trainingCenterRoleProfileSourceText(roleProfile.profile_source || ''));
      if (roleProfile.source_release_version) {
        lines.push('画像来源版本=' + roleProfile.source_release_version);
      }
      if (tags.length) {
        lines.push('状态标签=' + tags.map((tag) => trainingStatusTagText(tag)).join(','));
      }
      if (preReason) {
        lines.push('预发布原因=' + preReason);
      }
      if (preCheckedAt) {
        lines.push('预发布判定时间=' + preCheckedAt);
      }
      if (contextLoading) {
        lines.push('上下文同步=正在刷新发布版本与评审信息');
      }
      metaNode.innerHTML = '';
      for (const lineText of lines) {
        const lineNode = document.createElement('div');
        lineNode.textContent = safe(lineText);
        lineNode.style.whiteSpace = 'normal';
        lineNode.style.overflowWrap = 'anywhere';
        lineNode.style.wordBreak = 'break-word';
        lineNode.style.lineHeight = '1.45';
        metaNode.appendChild(lineNode);
      }
    }
    if (stateNode) {
      const lifecycle = safe(item.lifecycle_state || 'released').toLowerCase();
      const gate = safe(item.training_gate_state || 'trainable').toLowerCase();
      const parent = safe(item.parent_agent_id || '').trim();
      const lifecycleCls = lifecycle === 'released' ? 'ok' : 'warn';
      const gateCls = gate === 'frozen_switched' ? 'warn' : 'ok';
      stateNode.innerHTML = '';
      const badgeRows = [
        { cls: lifecycleCls, text: '生命周期：' + trainingLifecycleText(lifecycle) },
        { cls: gateCls, text: '训练门禁：' + trainingGateText(gate) },
      ];
      if (parent) {
        badgeRows.push({ cls: '', text: '克隆来源：' + parent });
      }
      for (const row of badgeRows) {
        const badge = document.createElement('span');
        badge.className = row.cls ? 'tc-badge ' + row.cls : 'tc-badge';
        badge.textContent = safe(row.text);
        badge.style.maxWidth = '100%';
        badge.style.whiteSpace = 'normal';
        badge.style.overflowWrap = 'anywhere';
        badge.style.wordBreak = 'break-word';
        stateNode.appendChild(badge);
      }
    }
    if (enterOpsBtn) enterOpsBtn.disabled = !state.agentSearchRootReady;
    if (discardBtn) {
      discardBtn.disabled = safe(item.lifecycle_state).toLowerCase() !== 'pre_release' || !hasPublishedRelease;
    }
    renderTrainingCenterPortrait(item);
    renderTrainingCenterReleases(safe(item.agent_id));
    renderTrainingCenterNormalCommits(safe(item.agent_id));
    renderTrainingCenterReleaseReview(safe(item.agent_id));
    updateTrainingCenterOpsGateState();
  }

  function beginTrainingCenterSelectedAgentContext(agentId) {
    const key = safe(agentId).trim();
    if (!key || safe(state.tcSelectedAgentId).trim() !== key) {
      state.tcSelectedAgentContextLoading = false;
      return 0;
    }
    const nextSeq = Number(state.tcSelectedAgentContextRequestSeq || 0) + 1;
    state.tcSelectedAgentContextRequestSeq = nextSeq;
    state.tcSelectedAgentContextLoading = true;
    return nextSeq;
  }

  function isTrainingCenterSelectedAgentContextCurrent(agentId, requestSeq) {
    const key = safe(agentId).trim();
    if (!key || safe(state.tcSelectedAgentId).trim() !== key) {
      return false;
    }
    const seq = Number(requestSeq || 0);
    if (!seq) {
      return true;
    }
    return Number(state.tcSelectedAgentContextRequestSeq || 0) === seq;
  }

  function syncTrainingCenterSelectedAgentFromPayload(agentId, agentPayload) {
    const key = safe(agentId).trim();
    if (!key || safe(state.tcSelectedAgentId).trim() !== key || !agentPayload || typeof agentPayload !== 'object') {
      return;
    }
    state.tcSelectedAgentDetail = Object.assign({}, state.tcSelectedAgentDetail || {}, agentPayload);
    state.tcSelectedAgentId = safe(agentPayload.agent_id || key);
    state.tcSelectedAgentName = safe(agentPayload.agent_name || state.tcSelectedAgentName);
    updateTrainingCenterSelectedMeta();
  }

  async function refreshTrainingCenterReleases(agentId, options) {
    const key = safe(agentId).trim();
    const opts = options && typeof options === 'object' ? options : {};
    if (!key) {
      if (!opts.skipRender) {
        renderTrainingCenterAgentDetail();
      }
      return;
    }
    const data = await getJSON('/api/training/agents/' + encodeURIComponent(key) + '/releases?page=1&page_size=120');
    if (opts.requestSeq && !isTrainingCenterSelectedAgentContextCurrent(key, opts.requestSeq)) {
      return data;
    }
    if (!state.tcNormalCommitsByAgent || typeof state.tcNormalCommitsByAgent !== 'object') {
      state.tcNormalCommitsByAgent = {};
    }
    state.tcReleasesByAgent[key] = Array.isArray(data.releases) ? data.releases : [];
    state.tcNormalCommitsByAgent[key] = Array.isArray(data.normal_commits) ? data.normal_commits : [];
    if (data.agent && typeof data.agent === 'object') {
      syncTrainingCenterSelectedAgentFromPayload(key, data.agent);
    }
    if (!opts.skipRender && safe(state.tcSelectedAgentId).trim() === key) {
      renderTrainingCenterAgentDetail();
    }
    return data;
  }

  async function refreshTrainingCenterReleaseReview(agentId, options) {
    const key = safe(agentId).trim();
    const opts = options && typeof options === 'object' ? options : {};
    if (!key) {
      if (!opts.skipRender) {
        renderTrainingCenterReleaseReview('');
      }
      return;
    }
    const data = await getJSON('/api/training/agents/' + encodeURIComponent(key) + '/release-review');
    if (opts.requestSeq && !isTrainingCenterSelectedAgentContextCurrent(key, opts.requestSeq)) {
      return data;
    }
    if (!state.tcReleaseReviewByAgent || typeof state.tcReleaseReviewByAgent !== 'object') {
      state.tcReleaseReviewByAgent = {};
    }
    state.tcReleaseReviewByAgent[key] = normalizeTrainingCenterReleaseReviewPayload(key, data);
    if (!opts.skipRender && safe(state.tcSelectedAgentId).trim() === key) {
      renderTrainingCenterReleaseReview(key);
    }
    return data;
  }

  async function refreshTrainingCenterSelectedAgentContext(agentId, options) {
    const key = safe(agentId).trim();
    const opts = options && typeof options === 'object' ? options : {};
    if (!key) {
      state.tcSelectedAgentContextLoading = false;
      renderTrainingCenterAgentDetail();
      return;
    }
    const requestSeq = beginTrainingCenterSelectedAgentContext(key);
    if (!opts.skipRender && safe(state.tcSelectedAgentId).trim() === key) {
      renderTrainingCenterAgentDetail();
    }
    const results = await Promise.allSettled([
      refreshTrainingCenterReleases(key, { skipRender: true, requestSeq: requestSeq }),
      refreshTrainingCenterReleaseReview(key, { skipRender: true, requestSeq: requestSeq }),
    ]);
    if (requestSeq && !isTrainingCenterSelectedAgentContextCurrent(key, requestSeq)) {
      return results;
    }
    if (requestSeq) {
      state.tcSelectedAgentContextLoading = false;
    }
    if (!opts.skipRender && safe(state.tcSelectedAgentId).trim() === key) {
      renderTrainingCenterAgentDetail();
    }
    const rejected = results.find((entry) => entry && entry.status === 'rejected');
    if (rejected && rejected.reason) {
      throw rejected.reason;
    }
    return results;
  }

  async function refreshTrainingCenterAgents() {
    const data = await getJSON('/api/training/agents');
    state.tcAgents = Array.isArray(data.items) ? data.items : [];
    const knownAgentIds = new Set(
      state.tcAgents
        .map((item) => safe(item && item.agent_id).trim())
        .filter((item) => !!item)
    );
    const nextReleasesByAgent = {};
    const nextNormalCommitsByAgent = {};
    const nextReleaseReviewByAgent = {};
    const releasesByAgent = state.tcReleasesByAgent && typeof state.tcReleasesByAgent === 'object'
      ? state.tcReleasesByAgent
      : {};
    const normalCommitsByAgent = state.tcNormalCommitsByAgent && typeof state.tcNormalCommitsByAgent === 'object'
      ? state.tcNormalCommitsByAgent
      : {};
    const releaseReviewByAgent = state.tcReleaseReviewByAgent && typeof state.tcReleaseReviewByAgent === 'object'
      ? state.tcReleaseReviewByAgent
      : {};
    Object.keys(releasesByAgent).forEach((agentId) => {
      if (!knownAgentIds.has(agentId)) return;
      nextReleasesByAgent[agentId] = Array.isArray(releasesByAgent[agentId]) ? releasesByAgent[agentId] : [];
    });
    Object.keys(normalCommitsByAgent).forEach((agentId) => {
      if (!knownAgentIds.has(agentId)) return;
      nextNormalCommitsByAgent[agentId] = Array.isArray(normalCommitsByAgent[agentId]) ? normalCommitsByAgent[agentId] : [];
    });
    Object.keys(releaseReviewByAgent).forEach((agentId) => {
      if (!knownAgentIds.has(agentId)) return;
      nextReleaseReviewByAgent[agentId] = releaseReviewByAgent[agentId];
    });
    state.tcReleasesByAgent = nextReleasesByAgent;
    state.tcNormalCommitsByAgent = nextNormalCommitsByAgent;
    state.tcReleaseReviewByAgent = nextReleaseReviewByAgent;
    state.tcStats =
      data.stats && typeof data.stats === 'object'
        ? data.stats
        : {
            agent_total: 0,
            git_available_count: 0,
            latest_release_at: '',
            training_queue_pending: 0,
          };
    renderTrainingCenterAgentStats();
    const selected = safe(state.tcSelectedAgentId).trim();
    const matched =
      selected && state.tcAgents.find((item) => safe(item.agent_id).trim() === selected);
    if (!matched) {
      state.tcSelectedAgentId = '';
      state.tcSelectedAgentName = '';
      state.tcSelectedAgentDetail = null;
      state.tcSelectedAgentContextLoading = false;
    } else {
      state.tcSelectedAgentDetail = matched;
      state.tcSelectedAgentName = safe(matched.agent_name || '');
    }
    syncTrainingCenterPlanAgentOptions();
    updateTrainingCenterSelectedMeta();
    renderTrainingCenterAgentList();
    if (state.tcSelectedAgentId) {
      await refreshTrainingCenterSelectedAgentContext(state.tcSelectedAgentId);
      return;
    }
    renderTrainingCenterAgentDetail();
  }

  function renderTrainingCenterTrainerList() {
    const box = $('tcTrainerList');
    if (!box) return;
    box.innerHTML = '';
    const rows = Array.isArray(state.tcTrainers) ? state.tcTrainers : [];
    if (!rows.length) {
      const empty = document.createElement('div');
      empty.className = 'tc-empty';
      empty.textContent = '暂无训练师匹配结果';
      box.appendChild(empty);
      return;
    }
    for (const row of rows) {
      const trainerName = safe(row && row.trainer_name).trim();
      if (!trainerName) continue;
      const node = document.createElement('div');
      node.className = 'tc-item' + (safe(state.tcTrainerSelected) === trainerName ? ' active' : '');
      node.innerHTML =
        "<div class='tc-item-title'>" +
        trainerName +
        '</div>' +
        "<div class='tc-item-sub'>" +
        safe(row.path || '-') +
        ' · 来源=' +
        safe(row.source || '-') +
        '</div>';
      node.onclick = () => {
        state.tcTrainerSelected = trainerName;
        if ($('tcTrainerQueryInput')) $('tcTrainerQueryInput').value = trainerName;
        renderTrainingCenterTrainerList();
      };
      box.appendChild(node);
    }
  }

  async function searchTrainingCenterTrainers() {
    const keyword = safe($('tcTrainerQueryInput') ? $('tcTrainerQueryInput').value : '').trim();
    const data = await getJSON('/api/training/trainers?query=' + encodeURIComponent(keyword));
    state.tcTrainers = Array.isArray(data.items) ? data.items : [];
    if (state.tcTrainerSelected) {
      const matched = state.tcTrainers.find((row) => safe(row.trainer_name) === state.tcTrainerSelected);
      if (!matched) state.tcTrainerSelected = '';
    }
    renderTrainingCenterTrainerList();
  }

  function trainingCenterSelectedTargetAgent() {
    const select = $('tcPlanTargetAgentSelect');
    const fromSelect = safe(select ? select.value : '').trim();
    if (fromSelect) return fromSelect;
    return safe(state.tcSelectedAgentId).trim();
  }

  function parseTrainingTasksInput() {
    const text = safe($('tcPlanTasksInput') ? $('tcPlanTasksInput').value : '').trim();
    if (!text) return [];
    return text
      .split(/\r?\n/)
      .map((line) => safe(line).trim())
      .filter((line) => !!line);
  }

  function setTrainingCenterRunResult(value) {
    const node = $('tcRunResult');
    if (!node) return;
    if (typeof value === 'string') {
      node.textContent = value;
      return;
    }
    node.textContent = JSON.stringify(value || {}, null, 2);
  }

  function renderTrainingCenterQueue() {
    const box = $('tcQueueList');
    if (!box) return;
    box.innerHTML = '';
    const rows = Array.isArray(state.tcQueue) ? state.tcQueue : [];
    if (!rows.length) {
      const empty = document.createElement('div');
      empty.className = 'tc-empty';
      empty.textContent = '训练队列为空';
      box.appendChild(empty);
      return;
    }
    for (const row of rows) {
      const queueTaskId = safe(row && row.queue_task_id).trim();
      if (!queueTaskId) continue;
      const node = document.createElement('div');
      node.className = 'tc-queue-item';
      const rowStatus = safe(row.status).toLowerCase();

      const header = document.createElement('div');
      header.className = 'row between';
      const title = document.createElement('div');
      const similarFlag = !!row.similar_flag;
      title.innerHTML =
        "<span class='tc-item-title'>" +
        safe(row.agent_name || row.target_agent_id || '-') +
        '</span>' +
        (similarFlag ? " <span class='tc-badge similar'>相似计划</span>" : '') +
        " <span class='tc-badge'>" +
        safe(row.priority || '-') +
        '</span>';
      header.appendChild(title);
      const ops = document.createElement('div');
      ops.className = 'row';
      const removeBtn = document.createElement('button');
      removeBtn.className = 'bad';
      removeBtn.type = 'button';
      removeBtn.textContent = '移除';
      removeBtn.title = '风险提示：移除后不可自动恢复';
      removeBtn.disabled = rowStatus === 'removed';
      removeBtn.onclick = () => {
        removeTrainingCenterQueueTask(queueTaskId).catch((err) => {
          setTrainingCenterError(err.message || String(err));
        });
      };
      ops.appendChild(removeBtn);

      const executeBtn = document.createElement('button');
      executeBtn.type = 'button';
      executeBtn.textContent = '执行';
      executeBtn.disabled = !row.can_execute || rowStatus !== 'queued';
      executeBtn.onclick = () => {
        executeTrainingCenterQueueTask(queueTaskId).catch((err) => {
          setTrainingCenterError(err.message || String(err));
        });
      };
      ops.appendChild(executeBtn);

      header.appendChild(ops);
      node.appendChild(header);

      const sub = document.createElement('div');
      sub.className = 'tc-item-sub';
      sub.textContent =
        '来源=' +
        safe(row.source || '-') +
        ' | 状态=' +
        statusText(row.status || '-') +
        ' | 入队时间=' +
        safe(row.enqueued_at || '-') +
        ' | 训练师=' +
        safe(row.trainer_match || '-');
      node.appendChild(sub);

      const goal = document.createElement('div');
      goal.className = 'tc-item-sub';
      goal.textContent = '能力目标=' + safe(row.capability_goal || '-');
      node.appendChild(goal);

      if (safe(row.latest_run_id)) {
        const run = document.createElement('div');
        run.className = 'tc-item-sub';
        run.textContent =
          '执行ID=' +
          safe(row.latest_run_id) +
          ' | 执行状态=' +
          statusText(row.latest_run_status || '-') +
          ' | 更新时间=' +
          safe(row.latest_run_updated_at || '-');
        node.appendChild(run);
      }
      box.appendChild(node);
    }
  }

  async function refreshTrainingCenterQueue(includeRemoved) {
    const includeRemovedFlag = includeRemoved === true;
    const queueUrl = '/api/training/queue?include_removed=' + (includeRemovedFlag ? '1' : '0');
    const data = await getJSON(queueUrl);
    state.tcQueue = Array.isArray(data.items) ? data.items : [];
    renderTrainingCenterQueue();
  }

  function trainingCenterPlanPayload() {
    return {
      target_agent_id: trainingCenterSelectedTargetAgent(),
      capability_goal: safe($('tcPlanGoalInput') ? $('tcPlanGoalInput').value : '').trim(),
      training_tasks: parseTrainingTasksInput(),
      acceptance_criteria: safe($('tcPlanAcceptanceInput') ? $('tcPlanAcceptanceInput').value : '').trim(),
      priority: safe($('tcPlanPrioritySelect') ? $('tcPlanPrioritySelect').value : '').trim(),
      trainer_query: safe($('tcTrainerQueryInput') ? $('tcTrainerQueryInput').value : '').trim(),
      trainer_match: safe(state.tcTrainerSelected).trim(),
      operator: 'web-user',
      created_by: 'web-user',
    };
  }

  async function enqueueTrainingCenterPlan(source) {
    const mode = safe(source).toLowerCase() === 'auto_analysis' ? 'auto_analysis' : 'manual';
    const payload = trainingCenterPlanPayload();
    const endpoint = mode === 'manual' ? '/api/training/plans/manual' : '/api/training/plans/auto';
    const data = await postJSON(endpoint, payload);
    setTrainingCenterError('');
    setTrainingCenterRunResult(data);
    await refreshTrainingCenterQueue();
    await refreshTrainingCenterAgents();
  }

  async function removeTrainingCenterQueueTask(queueTaskId) {
    const data = await postJSON('/api/training/queue/' + encodeURIComponent(queueTaskId) + '/remove', {
      operator: 'web-user',
      reason: 'manual_remove_from_ui',
    });
    setTrainingCenterError('');
    setTrainingCenterRunResult(data);
    await refreshTrainingCenterQueue(false);
    await refreshTrainingCenterAgents();
  }

  async function executeTrainingCenterQueueTask(queueTaskId) {
    const data = await postJSON('/api/training/queue/' + encodeURIComponent(queueTaskId) + '/execute', {
      operator: 'web-user',
    });
    setTrainingCenterError('');
    setTrainingCenterRunResult(data);
    if (safe(data.run_id)) {
      const run = await getJSON('/api/training/runs/' + encodeURIComponent(safe(data.run_id)));
      setTrainingCenterRunResult(run);
    }
    await refreshTrainingCenterQueue(false);
    await refreshTrainingCenterAgents();
  }

  async function dispatchNextTrainingCenterQueue() {
    const data = await postJSON('/api/training/queue/dispatch-next', {
      operator: 'web-user',
    });
    setTrainingCenterError('');
    setTrainingCenterRunResult(data);
    await refreshTrainingCenterQueue(false);
    await refreshTrainingCenterAgents();
  }

  function selectedTrainingCenterAgentId() {
    const fromState = safe(state.tcSelectedAgentId).trim();
    if (fromState) return fromState;
    return safe(trainingCenterSelectedTargetAgent()).trim();
  }

  async function switchTrainingCenterAgentVersion() {
    const agentId = selectedTrainingCenterAgentId();
    if (!agentId) throw new Error('请先选择角色');
    const versionLabel = safe($('tcSwitchVersionSelect') ? $('tcSwitchVersionSelect').value : '').trim();
    if (!versionLabel) throw new Error('请选择已发布版本');
    const currentVersion = currentTrainingCenterDisplayedVersion(state.tcSelectedAgentDetail || {});
    if (versionLabel === currentVersion) {
      return null;
    }
    const data = await postJSON('/api/training/agents/' + encodeURIComponent(agentId) + '/switch', {
      version_label: versionLabel,
      operator: 'web-user',
    });
    setTrainingCenterDetailError('');
    setTrainingCenterAgentActionResult(data);
    setTrainingCenterRunResult(data);
    await refreshTrainingCenterAgents();
    await refreshTrainingCenterQueue(false);
  }

  async function cloneTrainingCenterAgentFromCurrent() {
    const agentId = selectedTrainingCenterAgentId();
    if (!agentId) throw new Error('请先选择角色');
    const newAgentName = safe($('tcCloneAgentNameInput') ? $('tcCloneAgentNameInput').value : '').trim();
    if (!newAgentName) throw new Error('克隆角色名称必填');
    const data = await postJSON('/api/training/agents/' + encodeURIComponent(agentId) + '/clone', {
      new_agent_name: newAgentName,
      operator: 'web-user',
    });
    state.tcSelectedAgentId = safe(data.agent_id || '').trim();
    state.tcSelectedAgentName = safe(data.agent_name || '').trim();
    setTrainingCenterDetailError('');
    setTrainingCenterAgentActionResult(data);
    setTrainingCenterRunResult(data);
    await refreshTrainingCenterAgents();
    await refreshTrainingCenterQueue(false);
  }

  async function setTrainingCenterAgentAvatar() {
    const agentId = selectedTrainingCenterAgentId();
    if (!agentId) throw new Error('请先选择角色');
    const fileInput = $('tcAvatarFileInput');
    const file = fileInput && fileInput.files && fileInput.files[0] ? fileInput.files[0] : null;
    if (!file) throw new Error('请选择本地头像文件');
    const name = safe(file.name).trim();
    const ext = name.includes('.') ? safe(name.split('.').pop()).toLowerCase() : '';
    if (!['png', 'jpg', 'jpeg', 'webp'].includes(ext)) {
      throw new Error('头像格式仅支持 png/jpg/webp');
    }
    const size = Number(file.size) || 0;
    if (size <= 0) {
      throw new Error('头像文件内容为空');
    }
    if (size > 2 * 1024 * 1024) {
      throw new Error('头像文件超过 2MB 限制');
    }
    const dataUrl = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(safe(reader.result));
      reader.onerror = () => reject(new Error('头像文件读取失败'));
      reader.readAsDataURL(file);
    });
    const rawUrl = safe(dataUrl).trim();
    const splitIndex = rawUrl.indexOf(',');
    if (splitIndex <= 0) {
      throw new Error('头像文件读取失败');
    }
    const meta = rawUrl.slice(0, splitIndex);
    const payloadBase64 = rawUrl.slice(splitIndex + 1);
    const contentType = meta.replace(/^data:/i, '').replace(/;base64$/i, '').trim();
    try {
      const data = await postJSON('/api/training/agents/' + encodeURIComponent(agentId) + '/avatar', {
        upload_name: name,
        upload_content_type: contentType || safe(file.type),
        upload_base64: payloadBase64,
        operator: 'web-user',
      });
      if (fileInput) {
        fileInput.value = '';
      }
      setTrainingCenterDetailError('');
      setTrainingCenterAgentActionResult(data);
      setTrainingCenterRunResult(data);
      await refreshTrainingCenterAgents();
    } catch (err) {
      renderTrainingCenterAvatarPreview(state.tcSelectedAgentDetail || {});
      throw err;
    }
  }

  async function discardTrainingCenterPreRelease() {
    const agentId = selectedTrainingCenterAgentId();
    if (!agentId) throw new Error('请先选择角色');
    if (!hasTrainingCenterPublishedRelease(state.tcSelectedAgentDetail || {})) {
      throw new Error('没有首个发布版本，不能舍弃修改');
    }
    const data = await postJSON(
      '/api/training/agents/' + encodeURIComponent(agentId) + '/pre-release/discard',
      {
        operator: 'web-user',
      }
    );
    setTrainingCenterDetailError('');
    setTrainingCenterAgentActionResult(data);
    setTrainingCenterRunResult(data);
    await refreshTrainingCenterAgents();
    await refreshTrainingCenterQueue(false);
  }

  async function enterTrainingCenterReleaseReview() {
    const agentId = selectedTrainingCenterAgentId();
    if (!agentId) throw new Error('请先选择角色');
    startTrainingCenterReleaseReviewProgress(agentId, 'enter');
    try {
      const data = await postJSON(
        '/api/training/agents/' + encodeURIComponent(agentId) + '/release-review/enter',
        {
          operator: 'web-user',
        }
      );
      if (!state.tcReleaseReviewByAgent || typeof state.tcReleaseReviewByAgent !== 'object') {
        state.tcReleaseReviewByAgent = {};
      }
      state.tcReleaseReviewByAgent[agentId] = normalizeTrainingCenterReleaseReviewPayload(agentId, data);
      finishTrainingCenterReleaseReviewProgress(agentId);
      setTrainingCenterDetailError('');
      setTrainingCenterAgentActionResult(data);
      setTrainingCenterRunResult(data);
      renderTrainingCenterReleaseReview(agentId);
      await refreshTrainingCenterAgents();
    } catch (err) {
      failTrainingCenterReleaseReviewProgress(agentId, err);
      throw err;
    }
  }

  async function discardTrainingCenterReleaseReview() {
    const agentId = selectedTrainingCenterAgentId();
    if (!agentId) throw new Error('请先选择角色');
    const reason = safe($('tcEvalSummaryInput') ? $('tcEvalSummaryInput').value : '').trim();
    const data = await postJSON(
      '/api/training/agents/' + encodeURIComponent(agentId) + '/release-review/discard',
      {
        operator: 'web-user',
        reason: reason,
      }
    );
    if (!state.tcReleaseReviewByAgent || typeof state.tcReleaseReviewByAgent !== 'object') {
      state.tcReleaseReviewByAgent = {};
    }
    state.tcReleaseReviewByAgent[agentId] = normalizeTrainingCenterReleaseReviewPayload(agentId, data);
    setTrainingCenterDetailError('');
    setTrainingCenterAgentActionResult(data);
    setTrainingCenterRunResult(data);
    renderTrainingCenterReleaseReview(agentId);
    await refreshTrainingCenterAgents();
  }

  async function submitTrainingCenterManualEvaluation() {
    const agentId = selectedTrainingCenterAgentId();
    if (!agentId) throw new Error('请先选择角色');
    const decision = safe($('tcEvalDecisionSelect') ? $('tcEvalDecisionSelect').value : '').trim();
    const reviewer = safe($('tcEvalReviewerInput') ? $('tcEvalReviewerInput').value : '').trim();
    const summary = safe($('tcEvalSummaryInput') ? $('tcEvalSummaryInput').value : '').trim();
    if (decision === 'reject_discard_pre_release' && !hasTrainingCenterPublishedRelease(state.tcSelectedAgentDetail || {})) {
      throw new Error('没有首个发布版本，不能舍弃修改');
    }
    const data = await postJSON(
      '/api/training/agents/' + encodeURIComponent(agentId) + '/release-review/manual',
      {
        decision: decision,
        reviewer: reviewer,
        review_comment: summary,
        operator: 'web-user',
      }
    );
    if (!state.tcReleaseReviewByAgent || typeof state.tcReleaseReviewByAgent !== 'object') {
      state.tcReleaseReviewByAgent = {};
    }
    state.tcReleaseReviewByAgent[agentId] = normalizeTrainingCenterReleaseReviewPayload(agentId, data);
    setTrainingCenterDetailError('');
    setTrainingCenterAgentActionResult(data);
    setTrainingCenterRunResult(data);
    renderTrainingCenterReleaseReview(agentId);
    await refreshTrainingCenterAgents();
  }

  async function confirmTrainingCenterReleaseReview() {
    const agentId = selectedTrainingCenterAgentId();
    if (!agentId) throw new Error('请先选择角色');
    startTrainingCenterReleaseReviewProgress(agentId, 'confirm');
    try {
      const data = await postJSON(
        '/api/training/agents/' + encodeURIComponent(agentId) + '/release-review/confirm',
        {
          operator: 'web-user',
        }
      );
      if (!state.tcReleaseReviewByAgent || typeof state.tcReleaseReviewByAgent !== 'object') {
        state.tcReleaseReviewByAgent = {};
      }
      state.tcReleaseReviewByAgent[agentId] = normalizeTrainingCenterReleaseReviewPayload(agentId, data);
      finishTrainingCenterReleaseReviewProgress(agentId);
      setTrainingCenterDetailError('');
      setTrainingCenterAgentActionResult(data);
      setTrainingCenterRunResult(data);
      renderTrainingCenterReleaseReview(agentId);
      await refreshTrainingCenterAgents();
    } catch (err) {
      failTrainingCenterReleaseReviewProgress(agentId, err);
      throw err;
    }
  }

  async function runTrainingCenterProbe() {
    const output = {
      ts: new Date().toISOString(),
      case: trainingCenterProbeCase(),
      pass: false,
      error: '',
      error_code: '',
      module: '',
      agent_count: 0,
      selected_agent_id: '',
      selected_agent_name: '',
      release_count: 0,
      release_versions: [],
      release_has_commit_ref: false,
      lifecycle_state: '',
      training_gate_state: '',
      queue_count: 0,
      queue_removed_count: 0,
      queue_sources: [],
      clone_agent_id: '',
      risk_tip: '',
      run_status: '',
      api_result: {},
      review_state: '',
      review_decision: '',
      review_reviewer: '',
      review_can_review: false,
      review_can_confirm: false,
      review_error: '',
      publish_status: '',
      publish_error: '',
      fallback_status: '',
      release_review_card_mode: '',
      release_review_visible_grid_count: 0,
      release_report_ref_count: 0,
      release_report_button_count: 0,
      release_report_button_versions: [],
      release_report_unavailable_count: 0,
      release_report_unavailable_versions: [],
      release_report_dialog_open: false,
      release_report_dialog_title: '',
      release_report_dialog_version: '',
      release_report_dialog_text: '',
      release_review_current_pills: [],
      report_first_person_summary: '',
      report_change_summary: '',
      report_has_inventory: false,
      report_has_delta: false,
      analysis_chain_paths: {},
      execution_log_phases: [],
      role_profile_source: '',
      role_profile_source_release_id: '',
      role_profile_first_person_summary: '',
      active_role_profile_ref: '',
    };
    const errorPayload = (err) => ({
      ok: false,
      error: safe(err && err.message ? err.message : err),
      code: safe(err && err.code),
      status: Number(err && err.status) || 0,
      data: err && err.data ? err.data : {},
    });
    try {
      switchTab('training-center');
      setTrainingCenterModule('agents');
      await refreshTrainingCenterAgents();
      await refreshTrainingCenterQueue();
      const rows = Array.isArray(state.tcAgents) ? state.tcAgents : [];
      output.agent_count = rows.length;
      const probeCase = output.case;
      const requestedAgent = safe(queryParam('tc_probe_agent')).trim().toLowerCase();
      let selected = await selectTrainingCenterProbeAgent({ nonGitFirst: probeCase === 'ac_uo_04' });
      if (!selected) {
        selected = findTrainingCenterProbeAgent({});
      }
      const pickAgentBy = async (matcher) => {
        const list = Array.isArray(state.tcAgents) ? state.tcAgents : [];
        for (const row of list) {
          const aid = safe(row && row.agent_id).trim();
          if (!aid) continue;
          state.tcSelectedAgentId = aid;
          state.tcSelectedAgentName = safe(row.agent_name || '');
          state.tcSelectedAgentDetail = row;
          syncTrainingCenterPlanAgentOptions();
          updateTrainingCenterSelectedMeta();
          renderTrainingCenterAgentList();
          await refreshTrainingCenterSelectedAgentContext(aid);
          const detail = state.tcSelectedAgentDetail || {};
          const releases = Array.isArray(state.tcReleasesByAgent[aid]) ? state.tcReleasesByAgent[aid] : [];
          if (matcher(detail, releases)) {
            return row;
          }
        }
        return null;
      };

      if (requestedAgent) {
        const explicit = await pickAgentBy((detail) => {
          const agentId = safe(detail && detail.agent_id).trim().toLowerCase();
          const agentName = safe(detail && detail.agent_name).trim().toLowerCase();
          return requestedAgent === agentId || requestedAgent === agentName;
        });
        if (explicit) selected = explicit;
      }
      if (probeCase.startsWith('ac_ar_') && !requestedAgent) {
        const preferred = await pickAgentBy((detail, releases) => {
          return !!detail.git_available && releases.length >= 2;
        });
        if (preferred) selected = preferred;
      }
      const selectedId = safe(selected && selected.agent_id).trim();
      const selectedName = safe(selected && selected.agent_name).trim();
      output.selected_agent_id = selectedId;
      output.selected_agent_name = selectedName;

      if (probeCase === 'ac_uo_01') {
        setTrainingCenterModule('agents');
      } else if (probeCase === 'ac_uo_02' || probeCase === 'ac_uo_03' || probeCase === 'ac_uo_04') {
        setTrainingCenterModule('agents');
      } else if (probeCase === 'ac_uo_05_before') {
        setTrainingCenterModule('ops');
        fillTrainingCenterProbePlan(selectedId, 'before', 'P1');
      } else if (probeCase === 'ac_uo_05_after') {
        setTrainingCenterModule('ops');
        fillTrainingCenterProbePlan(selectedId, 'after', 'P1');
        output.api_result = await postJSON('/api/training/plans/manual', trainingCenterPlanPayload());
        await refreshTrainingCenterQueue();
      } else if (probeCase === 'ac_uo_06') {
        setTrainingCenterModule('ops');
        fillTrainingCenterProbePlan(selectedId, 'priority-missing', '');
        try {
          await postJSON('/api/training/plans/manual', trainingCenterPlanPayload());
        } catch (err) {
          setTrainingCenterError(err.message || String(err));
        }
      } else if (probeCase === 'ac_uo_07') {
        setTrainingCenterModule('ops');
        fillTrainingCenterProbePlan(selectedId, 'dispatch-p2', 'P2');
        await postJSON('/api/training/plans/manual', trainingCenterPlanPayload());
        fillTrainingCenterProbePlan(selectedId, 'dispatch-p0', 'P0');
        await postJSON('/api/training/plans/manual', trainingCenterPlanPayload());
        fillTrainingCenterProbePlan(selectedId, 'dispatch-p1', 'P1');
        await postJSON('/api/training/plans/manual', trainingCenterPlanPayload());
        await refreshTrainingCenterQueue();
      } else if (probeCase === 'ac_uo_08') {
        setTrainingCenterModule('ops');
        fillTrainingCenterProbePlan(selectedId, 'similarity', 'P2');
        if ($('tcPlanGoalInput')) $('tcPlanGoalInput').value = 'similarity-case';
        if ($('tcPlanTasksInput')) $('tcPlanTasksInput').value = 'normalize output\nstabilize retry';
        if ($('tcPlanAcceptanceInput')) $('tcPlanAcceptanceInput').value = 'shape stable';
        await postJSON('/api/training/plans/manual', trainingCenterPlanPayload());
        await postJSON('/api/training/plans/manual', trainingCenterPlanPayload());
        await refreshTrainingCenterQueue();
      } else if (probeCase === 'ac_uo_09_before') {
        setTrainingCenterModule('ops');
        fillTrainingCenterProbePlan(selectedId, 'remove-before', 'P1');
        await postJSON('/api/training/plans/manual', trainingCenterPlanPayload());
        await refreshTrainingCenterQueue();
      } else if (probeCase === 'ac_uo_09_after') {
        setTrainingCenterModule('ops');
        fillTrainingCenterProbePlan(selectedId, 'remove-after', 'P1');
        await postJSON('/api/training/plans/manual', trainingCenterPlanPayload());
        await refreshTrainingCenterQueue();
        const toRemove = (state.tcQueue || []).find((row) => safe(row.status).toLowerCase() === 'queued');
        if (toRemove && safe(toRemove.queue_task_id).trim()) {
          output.api_result = await postJSON(
            '/api/training/queue/' + encodeURIComponent(safe(toRemove.queue_task_id)) + '/remove',
            { operator: 'probe-user', reason: 'tc_probe_remove' }
          );
        }
        // Probe for AC-UO-09 needs to validate removed item state from queue payload.
        await refreshTrainingCenterQueue(true);
      } else if (probeCase === 'ac_uo_10') {
        setTrainingCenterModule('ops');
        fillTrainingCenterProbePlan(selectedId, 'manual-source', 'P2');
        await postJSON('/api/training/plans/manual', trainingCenterPlanPayload());
        fillTrainingCenterProbePlan(selectedId, 'auto-source', 'P2');
        await postJSON('/api/training/plans/auto', trainingCenterPlanPayload());
        await refreshTrainingCenterQueue();
      } else if (probeCase === 'ac_uo_11') {
        setTrainingCenterModule('ops');
        fillTrainingCenterProbePlan(selectedId, 'execute', 'P2');
        const created = await postJSON('/api/training/plans/manual', trainingCenterPlanPayload());
        const queueTaskId = safe(created && created.queue_task_id).trim();
        if (queueTaskId) {
          output.api_result = await postJSON('/api/training/queue/' + encodeURIComponent(queueTaskId) + '/execute', {
            operator: 'probe-user',
          });
        }
        await refreshTrainingCenterQueue();
      } else if (probeCase === 'ac_ar_01') {
        setTrainingCenterModule('agents');
      } else if (probeCase === 'ac_ar_02') {
        setTrainingCenterModule('agents');
      } else if (probeCase === 'ac_ar_03') {
        setTrainingCenterModule('agents');
        try {
          output.api_result = await postJSON('/api/training/agents/' + encodeURIComponent(selectedId) + '/switch', {
            version_label: 'deadbeef-not-release',
            operator: 'probe-user',
          });
        } catch (err) {
          output.api_result = errorPayload(err);
          output.error_code = safe(err && err.code);
        }
      } else if (probeCase === 'ac_ar_04') {
        setTrainingCenterModule('ops');
        const releases = Array.isArray(state.tcReleasesByAgent[selectedId]) ? state.tcReleasesByAgent[selectedId] : [];
        const latest = safe((releases[0] || {}).version_label).trim();
        const older = safe((releases[1] || {}).version_label).trim();
        if (older && latest && older !== latest) {
          await postJSON('/api/training/agents/' + encodeURIComponent(selectedId) + '/switch', {
            version_label: older,
            operator: 'probe-user',
          });
        }
        await refreshTrainingCenterAgents();
        await refreshTrainingCenterSelectedAgentContext(selectedId);
        fillTrainingCenterProbePlan(selectedId, 'ar04-frozen-enqueue', 'P1');
        try {
          output.api_result = await postJSON('/api/training/plans/manual', trainingCenterPlanPayload());
        } catch (err) {
          output.api_result = errorPayload(err);
          output.error_code = safe(err && err.code);
        }
      } else if (probeCase === 'ac_ar_05') {
        setTrainingCenterModule('ops');
        const releases = Array.isArray(state.tcReleasesByAgent[selectedId]) ? state.tcReleasesByAgent[selectedId] : [];
        const latest = safe((releases[0] || {}).version_label).trim();
        if (latest) {
          await postJSON('/api/training/agents/' + encodeURIComponent(selectedId) + '/switch', {
            version_label: latest,
            operator: 'probe-user',
          });
        }
        await refreshTrainingCenterAgents();
        await refreshTrainingCenterSelectedAgentContext(selectedId);
        fillTrainingCenterProbePlan(selectedId, 'ar05-unfreeze-enqueue', 'P1');
        output.api_result = await postJSON('/api/training/plans/manual', trainingCenterPlanPayload());
        await refreshTrainingCenterQueue();
      } else if (probeCase === 'ac_ar_06') {
        setTrainingCenterModule('ops');
        const releases = Array.isArray(state.tcReleasesByAgent[selectedId]) ? state.tcReleasesByAgent[selectedId] : [];
        const latest = safe((releases[0] || {}).version_label).trim();
        const older = safe((releases[1] || {}).version_label).trim();
        if (older && latest && older !== latest) {
          await postJSON('/api/training/agents/' + encodeURIComponent(selectedId) + '/switch', {
            version_label: older,
            operator: 'probe-user',
          });
        }
        const cloneName = safe(selectedId || 'probe-agent')
          .replace(/[^0-9A-Za-z._:-]/g, '')
          .slice(0, 72) + '-clone-' + String(Date.now()).slice(-5);
        const cloneResp = await postJSON('/api/training/agents/' + encodeURIComponent(selectedId) + '/clone', {
          new_agent_name: cloneName,
          operator: 'probe-user',
        });
        output.clone_agent_id = safe(cloneResp.agent_id || '').trim();
        await refreshTrainingCenterAgents();
        state.tcSelectedAgentId = output.clone_agent_id;
        await refreshTrainingCenterSelectedAgentContext(output.clone_agent_id);
        fillTrainingCenterProbePlan(output.clone_agent_id, 'ar06-clone-enqueue', 'P1');
        output.api_result = await postJSON('/api/training/plans/manual', trainingCenterPlanPayload());
        await refreshTrainingCenterQueue();
      } else if (probeCase === 'ac_ar_07') {
        setTrainingCenterModule('ops');
        const trainable = await pickAgentBy((detail) => safe(detail.training_gate_state).toLowerCase() !== 'frozen_switched');
        const trainableId = safe((trainable || {}).agent_id || state.tcSelectedAgentId).trim();
        fillTrainingCenterProbePlan(trainableId, 'ar07-train', 'P1');
        const created = await postJSON('/api/training/plans/manual', trainingCenterPlanPayload());
        const queueTaskId = safe(created.queue_task_id).trim();
        if (queueTaskId) {
          output.api_result = await postJSON('/api/training/queue/' + encodeURIComponent(queueTaskId) + '/execute', {
            operator: 'probe-user',
          });
        }
        await refreshTrainingCenterAgents();
        await refreshTrainingCenterSelectedAgentContext(trainableId);
        await refreshTrainingCenterQueue();
      } else if (probeCase === 'ac_ar_08') {
        setTrainingCenterModule('agents');
        let preRelease = await pickAgentBy((detail) => safe(detail.lifecycle_state).toLowerCase() === 'pre_release');
        if (!preRelease) {
          const trainable = await pickAgentBy((detail) => safe(detail.training_gate_state).toLowerCase() !== 'frozen_switched');
          const aid = safe((trainable || {}).agent_id || state.tcSelectedAgentId).trim();
          setTrainingCenterModule('ops');
          fillTrainingCenterProbePlan(aid, 'ar08-train-to-pre', 'P1');
          const created = await postJSON('/api/training/plans/manual', trainingCenterPlanPayload());
          const queueTaskId = safe(created.queue_task_id).trim();
          if (queueTaskId) {
            await postJSON('/api/training/queue/' + encodeURIComponent(queueTaskId) + '/execute', {
              operator: 'probe-user',
            });
          }
          await refreshTrainingCenterAgents();
          preRelease = await pickAgentBy((detail) => safe(detail.lifecycle_state).toLowerCase() === 'pre_release');
        }
        const discardAgentId = safe((preRelease || {}).agent_id || state.tcSelectedAgentId).trim();
        output.api_result = await postJSON(
          '/api/training/agents/' + encodeURIComponent(discardAgentId) + '/pre-release/discard',
          { operator: 'probe-user' }
        );
        await refreshTrainingCenterAgents();
        await refreshTrainingCenterSelectedAgentContext(discardAgentId);
      } else if (probeCase === 'ac_ar_09') {
        setTrainingCenterModule('agents');
        let preRelease = await pickAgentBy((detail) => safe(detail.lifecycle_state).toLowerCase() === 'pre_release');
        if (!preRelease) {
          const trainable = await pickAgentBy((detail) => safe(detail.training_gate_state).toLowerCase() !== 'frozen_switched');
          const aid = safe((trainable || {}).agent_id || state.tcSelectedAgentId).trim();
          setTrainingCenterModule('ops');
          fillTrainingCenterProbePlan(aid, 'ar09-train-to-pre', 'P1');
          const created = await postJSON('/api/training/plans/manual', trainingCenterPlanPayload());
          const queueTaskId = safe(created.queue_task_id).trim();
          if (queueTaskId) {
            await postJSON('/api/training/queue/' + encodeURIComponent(queueTaskId) + '/execute', {
              operator: 'probe-user',
            });
          }
          await refreshTrainingCenterAgents();
          preRelease = await pickAgentBy((detail) => safe(detail.lifecycle_state).toLowerCase() === 'pre_release');
        }
        const evalAgentId = safe((preRelease || {}).agent_id || state.tcSelectedAgentId).trim();
        output.api_result = await postJSON(
          '/api/training/agents/' + encodeURIComponent(evalAgentId) + '/release-evaluations/manual',
          {
            decision: 'approve',
            reviewer: 'probe-reviewer',
            summary: 'manual evaluation approve in probe',
            operator: 'probe-user',
          }
        );
        await refreshTrainingCenterAgents();
        await refreshTrainingCenterSelectedAgentContext(evalAgentId);
      } else if (probeCase === 'ac_ar_10') {
        setTrainingCenterModule('agents');
      } else if (
        probeCase === 'ac_ar_rr_09' ||
        probeCase === 'ac_ar_rr_10' ||
        probeCase === 'ac_ar_rr_11' ||
        probeCase === 'ac_ar_rr_12' ||
        probeCase === 'ac_ar_rr_13' ||
        probeCase === 'ac_ar_rr_14' ||
        probeCase === 'ac_ar_rr_15' ||
        probeCase === 'ac_ar_rr_16'
      ) {
        setTrainingCenterModule('agents');
        if (selectedId) {
          await refreshTrainingCenterSelectedAgentContext(selectedId);
        }
      } else {
        setTrainingCenterModule('ops');
        await refreshTrainingCenterQueue();
      }

      const selectedDetail = state.tcSelectedAgentDetail || {};
      const roleProfile = trainingCenterRoleProfile(selectedDetail);
      const currentReview = currentTrainingCenterReleaseReview(safe(state.tcSelectedAgentId).trim());
      const releases = state.tcReleasesByAgent[safe(state.tcSelectedAgentId)] || [];
      const queueItems = Array.isArray(state.tcQueue) ? state.tcQueue : [];
      output.module = safe(state.tcModule);
      output.selected_agent_id = safe(state.tcSelectedAgentId);
      output.selected_agent_name = safe(state.tcSelectedAgentName || selectedName);
      output.release_count = releases.length;
      output.release_versions = releases.map((row) => safe(row.version_label)).filter(Boolean);
      output.release_has_commit_ref = releases.some((row) => Object.prototype.hasOwnProperty.call(row || {}, 'commit_ref'));
      output.queue_count = queueItems.length;
      output.queue_removed_count = queueItems.filter((row) => safe(row.status).toLowerCase() === 'removed').length;
      output.queue_sources = Array.from(
        new Set(queueItems.map((row) => safe(row.source).toLowerCase()).filter(Boolean))
      );
      output.risk_tip = safe((output.api_result && output.api_result.risk_tip) || $('tcOpsRisk').textContent);
      output.run_status = safe((output.api_result && output.api_result.status) || '');
      output.git_available = !!selectedDetail.git_available;
      output.status_tags = Array.isArray(selectedDetail.status_tags) ? selectedDetail.status_tags : [];
      output.lifecycle_state = safe(selectedDetail.lifecycle_state || '').toLowerCase();
      output.training_gate_state = safe(selectedDetail.training_gate_state || '').toLowerCase();
      output.review_state = safe(currentReview.release_review_state || '').toLowerCase();
      output.review_decision = safe(currentReview.review_decision || '').trim();
      output.review_reviewer = safe(currentReview.reviewer || '').trim();
      output.review_can_enter = !!currentReview.can_enter;
      output.review_can_discard = !!currentReview.can_discard;
      output.review_can_review = !!currentReview.can_review;
      output.review_can_confirm = !!currentReview.can_confirm;
      output.review_error = safe(currentReview.report_error || '').trim();
      output.review_report_error_code = safe(currentReview.report_error_code || '').trim().toLowerCase();
      output.review_report_missing_fields = Array.isArray(currentReview.report_missing_fields) ? currentReview.report_missing_fields : [];
      output.review_required_report_fields = Array.isArray(currentReview.required_report_fields) ? currentReview.required_report_fields : [];
      output.publish_status = safe(currentReview.publish_status || '').toLowerCase();
      output.publish_error = safe(currentReview.publish_error || '').trim();
      output.fallback_status = safe(currentReview.fallback && currentReview.fallback.status).toLowerCase();
      const releaseReviewCard = $('tcReleaseReviewCard');
      output.release_review_card_mode = safe(releaseReviewCard && releaseReviewCard.dataset && releaseReviewCard.dataset.reviewMode).trim().toLowerCase();
      output.release_review_visible_grid_count = Array.from(document.querySelectorAll('#tcReleaseReviewCard .tc-release-review-grid'))
        .filter((node) => !!node && !node.hidden)
        .length;
      const releaseReportButtons = Array.from(document.querySelectorAll('#tcReleaseList button'))
        .filter((node) => safe(node && node.textContent).trim() === '查看发布报告');
      const releaseReportUnavailableNodes = Array.from(document.querySelectorAll('#tcReleaseList .tc-item-sub'))
        .filter((node) => /未绑定可展示的发布报告文件/.test(safe(node && node.textContent).trim()));
      output.release_report_ref_count = releases.filter((row) => !!safe((row && (row.release_source_ref || row.capability_snapshot_ref)) || '').trim()).length;
      output.release_report_button_count = releaseReportButtons.length;
      output.release_report_button_versions = releaseReportButtons
        .map((node) => safe(node && node.dataset && node.dataset.releaseVersion).trim())
        .filter(Boolean);
      output.release_report_unavailable_count = releaseReportUnavailableNodes.length;
      output.release_report_unavailable_versions = releaseReportUnavailableNodes
        .map((node) => safe(node && node.dataset && node.dataset.releaseVersion).trim())
        .filter(Boolean);
      output.release_review_current_pills = Array.from(document.querySelectorAll('#tcReleaseReviewSubstage .tc-release-review-pill.current'))
        .map((node) => safe(node && node.textContent).trim())
        .filter(Boolean);
      output.report_previous_release_version = safe(currentReview.report && currentReview.report.previous_release_version).trim();
      output.report_first_person_summary = safe(currentReview.report && currentReview.report.first_person_summary).trim();
      output.report_change_summary = safe(currentReview.report && currentReview.report.change_summary).trim();
      output.report_release_recommendation = safe(currentReview.report && currentReview.report.release_recommendation).trim().toLowerCase();
      output.report_has_inventory =
        !!(currentReview.report && Array.isArray(currentReview.report.full_capability_inventory) && currentReview.report.full_capability_inventory.length);
      output.report_has_delta =
        !!(currentReview.report && Array.isArray(currentReview.report.capability_delta) && currentReview.report.capability_delta.length);
      output.report_has_knowledge_scope = !!safe(currentReview.report && currentReview.report.knowledge_scope).trim();
      output.report_agent_skill_count =
        currentReview.report && Array.isArray(currentReview.report.agent_skills) ? currentReview.report.agent_skills.length : 0;
      output.report_applicable_scenario_count =
        currentReview.report && Array.isArray(currentReview.report.applicable_scenarios) ? currentReview.report.applicable_scenarios.length : 0;
      output.report_warning_count =
        currentReview.report && Array.isArray(currentReview.report.warnings) ? currentReview.report.warnings.length : 0;
      output.report_has_failure_skeleton =
        !!safe(currentReview.report && currentReview.report.target_version).trim() &&
        !!safe(currentReview.report && currentReview.report.current_workspace_ref).trim() &&
        !!safe(currentReview.report && currentReview.report.change_summary).trim() &&
        !!safe(currentReview.report && currentReview.report.release_recommendation).trim() &&
        !!safe(currentReview.report && currentReview.report.next_action_suggestion).trim();
      output.analysis_chain_paths = {
        prompt_path: safe(currentReview.analysis_chain && currentReview.analysis_chain.prompt_path).trim(),
        stdout_path: safe(currentReview.analysis_chain && currentReview.analysis_chain.stdout_path).trim(),
        stderr_path: safe(currentReview.analysis_chain && currentReview.analysis_chain.stderr_path).trim(),
        report_path: safe(currentReview.analysis_chain && currentReview.analysis_chain.report_path).trim(),
        public_profile_markdown_path: safe(currentReview.public_profile_markdown_path).trim(),
        capability_snapshot_json_path: safe(currentReview.capability_snapshot_json_path).trim(),
      };
      output.execution_log_phases = Array.from(
        new Set(
          (Array.isArray(currentReview.execution_logs) ? currentReview.execution_logs : [])
            .map((row) => safe(row && row.phase).trim().toLowerCase())
            .filter(Boolean)
        )
      );
      output.role_profile_source = safe(roleProfile.profile_source).trim();
      output.role_profile_source_release_id = safe(roleProfile.source_release_id).trim();
      output.role_profile_first_person_summary = safe(roleProfile.first_person_summary).trim();
      output.active_role_profile_ref = safe(selectedDetail.active_role_profile_ref || '').trim();
      if ((probeCase === 'ac_ar_rr_12' || probeCase === 'ac_ar_rr_19') && output.release_report_button_count >= 1) {
        const requestedReleaseVersion = safe(queryParam('tc_probe_release_version')).trim();
        const releaseReportBtn = Array.from(document.querySelectorAll('#tcReleaseList button'))
          .find((node) => {
            if (safe(node && node.textContent).trim() !== '查看发布报告') return false;
            if (!requestedReleaseVersion) return true;
            return safe(node && node.dataset && node.dataset.releaseVersion).trim() === requestedReleaseVersion;
          });
        if (releaseReportBtn) {
          releaseReportBtn.click();
          await new Promise((resolve) => window.setTimeout(resolve, 250));
          const reportDialog = $('tcPublishedReleaseReportDialog');
          output.release_report_dialog_open = !!(reportDialog && reportDialog.open);
          const reportTitleNode = reportDialog ? reportDialog.querySelector('.tc-report-dialog-title') : null;
          const reportBodyNode = reportDialog ? reportDialog.querySelector('.tc-report-dialog-body') : null;
          output.release_report_dialog_title = safe(reportTitleNode && reportTitleNode.textContent).trim();
          output.release_report_dialog_version = safe(reportDialog && reportDialog.dataset && reportDialog.dataset.releaseVersion).trim();
          output.release_report_dialog_text = safe(reportBodyNode && reportBodyNode.textContent).trim().slice(0, 1600);
          if (probeCase !== 'ac_ar_rr_19' && reportDialog && reportDialog.open && typeof reportDialog.close === 'function') {
            reportDialog.close();
          }
        }
      }
      if (!output.error_code) {
        output.error_code = safe((output.api_result && output.api_result.code) || '').toLowerCase();
      }

      output.pass =
        output.agent_count >= 0 &&
        (probeCase === 'ac_uo_01'
          ? output.agent_count >= 1
          : probeCase === 'ac_uo_02' || probeCase === 'ac_uo_03'
            ? output.release_count >= 1
            : probeCase === 'ac_uo_04'
              ? output.status_tags.includes('git_unavailable')
              : probeCase === 'ac_uo_06'
                ? !!safe($('tcOpsErr').textContent)
              : probeCase === 'ac_uo_09_after'
                  ? output.queue_removed_count >= 1
                  : probeCase === 'ac_uo_10'
                    ? output.queue_sources.includes('manual') && output.queue_sources.includes('auto_analysis')
                    : probeCase === 'ac_ar_01'
                      ? output.agent_count >= 1
                      : probeCase === 'ac_ar_02'
                        ? output.release_count >= 1 && !output.release_has_commit_ref
                        : probeCase === 'ac_ar_03'
                          ? output.error_code === 'version_not_released'
                          : probeCase === 'ac_ar_04'
                            ? output.error_code === 'training_frozen_after_switch' || output.training_gate_state === 'frozen_switched'
                            : probeCase === 'ac_ar_05'
                              ? safe(output.api_result && output.api_result.queue_task_id) && output.training_gate_state !== 'frozen_switched'
                              : probeCase === 'ac_ar_06'
                                ? safe(output.clone_agent_id) && safe(output.api_result && output.api_result.queue_task_id)
                                : probeCase === 'ac_ar_07'
                                  ? safe(output.api_result && output.api_result.status).toLowerCase() === 'done' && output.lifecycle_state === 'pre_release'
                                  : probeCase === 'ac_ar_08'
                                    ? !!(output.api_result && output.api_result.discarded) && output.lifecycle_state === 'released'
                                    : probeCase === 'ac_ar_09'
                                      ? !!safe(output.api_result && output.api_result.evaluation_id) && safe(output.api_result && output.api_result.decision) === 'approve'
                                      : probeCase === 'ac_ar_10'
                                        ? true
                                        : probeCase === 'ac_ar_rr_09'
                                          ? output.review_state === 'report_generating'
                                            : probeCase === 'ac_ar_rr_10'
                                              ? output.review_state === 'report_ready' &&
                                                output.report_has_inventory &&
                                                output.report_has_delta &&
                                                output.report_has_knowledge_scope &&
                                                output.report_agent_skill_count >= 1 &&
                                                output.report_applicable_scenario_count >= 1 &&
                                                !!safe(output.analysis_chain_paths.prompt_path) &&
                                                !!safe(output.analysis_chain_paths.stdout_path) &&
                                                !!safe(output.analysis_chain_paths.stderr_path) &&
                                                !!safe(output.analysis_chain_paths.report_path) &&
                                                /^我/.test(output.report_first_person_summary)
                                            : probeCase === 'ac_ar_rr_11'
                                              ? output.review_state === 'review_approved' &&
                                                output.review_decision === 'approve_publish' &&
                                                !!output.review_reviewer
                                            : probeCase === 'ac_ar_rr_12'
                                                ? output.publish_status === 'success' &&
                                                  output.release_review_card_mode === 'inactive' &&
                                                  output.release_review_visible_grid_count === 0 &&
                                                  output.role_profile_source === 'latest_release_report' &&
                                                  !!output.active_role_profile_ref &&
                                                  output.release_report_ref_count >= 1 &&
                                                  output.release_report_button_count >= 1 &&
                                                  output.release_report_dialog_open &&
                                                  /发布报告/.test(output.release_report_dialog_title) &&
                                                  output.release_review_current_pills.length === 0 &&
                                                  /^我/.test(output.role_profile_first_person_summary)
                                                : probeCase === 'ac_ar_rr_19'
                                                  ? output.publish_status === 'success' &&
                                                    output.release_report_button_count >= 1 &&
                                                    output.release_report_dialog_open &&
                                                    /发布报告/.test(output.release_report_dialog_title) &&
                                                    (!safe(queryParam('tc_probe_release_version')).trim() ||
                                                      output.release_report_button_versions.includes(safe(queryParam('tc_probe_release_version')).trim())) &&
                                                    (!safe(queryParam('tc_probe_release_version')).trim() ||
                                                      output.release_report_dialog_version === safe(queryParam('tc_probe_release_version')).trim()) &&
                                                    (!safe(queryParam('tc_probe_release_version')).trim() ||
                                                      output.release_report_dialog_text.includes(safe(queryParam('tc_probe_release_version')).trim()))
                                                : probeCase === 'ac_ar_rr_20'
                                                  ? output.release_report_unavailable_count >= 1 &&
                                                    !output.release_report_dialog_open &&
                                                    (!safe(queryParam('tc_probe_release_version')).trim() ||
                                                      output.release_report_unavailable_versions.includes(safe(queryParam('tc_probe_release_version')).trim())) &&
                                                    (!safe(queryParam('tc_probe_release_version')).trim() ||
                                                      !output.release_report_button_versions.includes(safe(queryParam('tc_probe_release_version')).trim()))
                                                : probeCase === 'ac_ar_rr_13'
                                                  ? output.execution_log_phases.includes('prepare') &&
                                                    output.execution_log_phases.includes('git_execute') &&
                                                    output.execution_log_phases.includes('release_note') &&
                                                    output.execution_log_phases.includes('verify')
                                                  : probeCase === 'ac_ar_rr_14'
                                                    ? output.review_state === 'publish_failed' &&
                                                      !!output.fallback_status &&
                                                      output.execution_log_phases.includes('fallback_trigger') &&
                                                      output.execution_log_phases.includes('fallback_result')
                                                  : probeCase === 'ac_ar_rr_15'
                                                    ? output.review_state === 'report_failed' &&
                                                      !!output.review_error &&
                                                      !!output.review_report_error_code &&
                                                      output.report_has_failure_skeleton &&
                                                      !output.review_can_confirm
                                                    : probeCase === 'ac_ar_rr_16'
                                                      ? output.review_state === 'review_discarded' &&
                                                        output.review_can_enter &&
                                                        !output.review_can_confirm
                                         : true);
    } catch (err) {
      output.error = safe(err && err.message ? err.message : err);
      output.error_code = safe(err && err.code ? err.code : output.error_code);
    }
    const node = ensureTrainingCenterProbeOutputNode();
    node.textContent = JSON.stringify(output);
    node.setAttribute('data-pass', output.pass ? '1' : '0');
  }

