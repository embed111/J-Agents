  function switchTab(name) {
    document.querySelectorAll('.tab').forEach((node) => {
      node.classList.toggle('active', safe(node.getAttribute('data-tab')) === name);
    });
    document.querySelectorAll('.pane').forEach((node) => {
      node.classList.toggle('active', safe(node.id) === 'pane-' + name);
    });
    if (name === 'training-center') {
      refreshTrainingCenterAgents()
        .then(() => refreshTrainingCenterQueue(false))
        .catch((err) => {
          setTrainingCenterError(err.message || String(err));
        });
    }
  }

  function bindEvents() {
    $('agentSelect').onchange = () => {
      const agent = selectedAgent();
      if (agent) localStorage.setItem(agentCacheKey, agent);
      state.agentMetaPanelOpen = false;
      state.agentMetaDetailsOpen = false;
      state.agentMetaClarityOpen = false;
      startPolicyAnalysisForSelection();
    };
    $('agentSelectTrigger').onclick = (event) => {
      event.preventDefault();
      if ($('agentSelectTrigger').disabled) return;
      const willOpen = !state.agentDropdownOpen;
      if (willOpen) {
        const search = $('agentSelectSearch');
        if (search) {
          search.value = '';
        }
        renderAgentStatusList(visibleAgents());
      }
      setAgentDropdownOpen(willOpen);
    };
    $('agentSelectSearch').addEventListener('input', () => {
      renderAgentStatusList(visibleAgents());
    });
    $('agentSelectSearch').addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        setAgentDropdownOpen(false);
      }
    });
    $('loadAgentsBtn').onclick = async () => {
      try {
        await withButtonLock('loadAgentsBtn', async () => {
          setStatus('正在刷新角色...');
          await refreshAgents(true);
          await refreshDashboard();
          setStatus('就绪');
        });
      } catch (err) {
        setChatError(err.message || String(err));
      }
    };
    $('clearPolicyCacheBtn').onclick = async () => {
      try {
        await withButtonLock('clearPolicyCacheBtn', async () => {
          await clearPolicyCache('selected');
        });
      } catch (err) {
        setChatError(err.message || String(err));
      }
    };
    $('clearAllPolicyCacheBtn').onclick = async () => {
      try {
        await withButtonLock('clearAllPolicyCacheBtn', async () => {
          await clearPolicyCache('all');
        });
      } catch (err) {
        setChatError(err.message || String(err));
      }
    };
    $('regeneratePolicyCacheBtn').onclick = async () => {
      try {
        await withButtonLock('regeneratePolicyCacheBtn', async () => {
          regenerateSelectedPolicyCache();
        });
      } catch (err) {
        setChatError(err.message || String(err));
      }
    };
    $('newSessionBtn').onclick = async () => {
      try {
        await withButtonLock('newSessionBtn', async () => {
          setStatus('正在创建会话...');
          const created = await createSession();
          await refreshSessions();
          if (created) {
            setStatus('就绪');
          }
        });
      } catch (err) {
        setChatError(err.message || String(err));
      }
    };
    $('policyGateBtn').onclick = async () => {
      try {
        await withButtonLock('policyGateBtn', async () => {
          openPolicyConfirmForSelectedAgent();
        });
      } catch (err) {
        setChatError(err.message || String(err));
      }
    };
    $('reloadSessionsBtn').onclick = async () => {
      try {
        await withButtonLock('reloadSessionsBtn', async () => {
          await refreshSessions();
          setStatus('会话列表已刷新');
        });
      } catch (err) {
        setChatError(err.message || String(err));
      }
    };
    $('deleteSessionBtn').onclick = async () => {
      try {
        await withButtonLock('deleteSessionBtn', async () => {
          await deleteCurrentSession();
        });
      } catch (err) {
        setChatError(err.message || String(err));
      }
    };
    $('sendBtn').onclick = async () => {
      try {
        await runTask(false);
      } catch (err) {
        setChatError(err.message || String(err));
      }
    };
    $('retryBtn').onclick = async () => {
      try {
        await runTask(true);
      } catch (err) {
        setChatError(err.message || String(err));
      }
    };
    $('stopBtn').onclick = async () => {
      try {
        await interruptCurrentTask();
      } catch (err) {
        setChatError(err.message || String(err));
      }
    };
    $('msg').addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        $('sendBtn').click();
      }
    });
    $('feed').addEventListener('click', (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      const btn = target.closest('button.trace-toggle');
      if (!btn) return;
      const taskId = safe(btn.getAttribute('data-task-id'));
      if (!taskId) return;
      const expanded = !!state.taskTraceExpanded[taskId];
      if (expanded) {
        delete state.taskTraceExpanded[taskId];
        renderFeed();
        return;
      }
      state.taskTraceExpanded[taskId] = true;
      ensureTaskTrace(taskId).catch((err) => {
        setChatError(err.message || String(err));
      });
    });
    $('refreshWorkflowBtn').onclick = async () => {
      try {
        await withButtonLock('refreshWorkflowBtn', async () => {
          await refreshWorkflows();
        });
      } catch (err) {
        setWorkflowResult(err.message || String(err));
      }
    };
    $('workflowDialogue').addEventListener('click', (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      const btn = target.closest('button.workflow-delete-msg');
      if (!btn) return;
      event.stopPropagation();
      const sid = safe(btn.getAttribute('data-session-id'));
      const mid = safe(btn.getAttribute('data-message-id'));
      deleteSessionMessage(sid, mid, btn).catch((err) => {
        setWorkflowResult(err.message || String(err));
      });
    });
    $('workflowSelectionToggleCheck').onclick = (event) => {
      event.stopPropagation();
      toggleWorkflowSelectionState();
    };
    $('queueModeRecordsBtn').onclick = () => {
      setWorkflowQueueMode('records');
    };
    $('queueModeTrainingBtn').onclick = () => {
      setWorkflowQueueMode('training');
    };
    $('batchAnalystInput').addEventListener('change', () => {
      const value = safe($('batchAnalystInput').value).trim();
      if (value) $('analystInput').value = value;
      updateBatchActionState();
    });
    $('analystInput').addEventListener('change', () => {
      const value = safe($('analystInput').value).trim();
      if (value) $('batchAnalystInput').value = value;
      updateBatchActionState();
    });
    $('batchAnalyzeBtn').onclick = async () => {
      try {
        await batchAnalyzeRecords();
      } catch (err) {
        setWorkflowResult(err.message || String(err));
      }
    };
    $('batchDeleteRecordsBtn').onclick = async () => {
      try {
        await batchDeleteRecords();
      } catch (err) {
        setWorkflowResult(err.message || String(err));
      }
    };
    $('assignBtn').onclick = async () => {
      try {
        await withButtonLock('assignBtn', async () => {
          await assignAnalyst();
        });
      } catch (err) {
        setWorkflowResult(err.message || String(err));
      }
    };
    $('generatePlanBtn').onclick = async () => {
      try {
        await withButtonLock('generatePlanBtn', async () => {
          await generateWorkflowPlan();
        });
      } catch (err) {
        setWorkflowResult(err.message || String(err));
      }
    };
    $('executePlanBtn').onclick = async () => {
      try {
        await withButtonLock('executePlanBtn', async () => {
          await executeWorkflowPlan();
        });
      } catch (err) {
        setWorkflowResult(err.message || String(err));
      }
    };
    $('deleteWorkflowBtn').onclick = async () => {
      try {
        await withButtonLock('deleteWorkflowBtn', async () => {
          await deleteSelectedWorkflow();
        });
      } catch (err) {
        setWorkflowResult(err.message || String(err));
      }
    };
    $('refreshEventsBtn').onclick = async () => {
      try {
        await refreshWorkflowEvents(state.selectedWorkflowId);
      } catch (err) {
        setWorkflowResult(err.message || String(err));
      }
    };
    $('tcTabAgentsBtn').onclick = () => {
      setTrainingCenterModule('agents');
    };
    $('tcTabOpsBtn').onclick = () => {
      setTrainingCenterModule('ops');
    };
    $('tcEnterOpsBtn').onclick = () => {
      setTrainingCenterModule('ops');
    };
    $('tcAgentSearchInput').addEventListener('input', () => {
      renderTrainingCenterAgentList();
    });
    $('tcPlanTargetAgentSelect').addEventListener('change', () => {
      const agentId = safe($('tcPlanTargetAgentSelect').value).trim();
      state.tcSelectedAgentId = agentId;
      const matched =
        agentId && state.tcAgents.find((item) => safe(item.agent_id).trim() === agentId);
      if (matched) {
        state.tcSelectedAgentDetail = matched;
        state.tcSelectedAgentName = safe(matched.agent_name || '');
      }
      updateTrainingCenterSelectedMeta();
      renderTrainingCenterAgentList();
      renderTrainingCenterAgentDetail();
      if (agentId) {
        refreshTrainingCenterReleases(agentId).catch((err) => {
          setTrainingCenterDetailError(err.message || String(err));
        });
      }
      applyGateState();
    });
    $('tcRefreshAgentsBtn').onclick = async () => {
      try {
        await withButtonLock('tcRefreshAgentsBtn', async () => {
          await refreshTrainingCenterAgents();
          await refreshTrainingCenterQueue();
          setTrainingCenterDetailError('');
          setTrainingCenterError('');
        });
      } catch (err) {
        setTrainingCenterDetailError(err.message || String(err));
      }
    };
    $('tcSearchTrainerBtn').onclick = async () => {
      try {
        await withButtonLock('tcSearchTrainerBtn', async () => {
          await searchTrainingCenterTrainers();
          setTrainingCenterError('');
        });
      } catch (err) {
        setTrainingCenterError(err.message || String(err));
      }
    };
    $('tcEnqueueManualBtn').onclick = async () => {
      try {
        await withButtonLock('tcEnqueueManualBtn', async () => {
          await enqueueTrainingCenterPlan('manual');
        });
      } catch (err) {
        setTrainingCenterError(err.message || String(err));
      }
    };
    $('tcEnqueueAutoBtn').onclick = async () => {
      try {
        await withButtonLock('tcEnqueueAutoBtn', async () => {
          await enqueueTrainingCenterPlan('auto_analysis');
        });
      } catch (err) {
        setTrainingCenterError(err.message || String(err));
      }
    };
    $('tcRefreshQueueBtn').onclick = async () => {
      try {
        await withButtonLock('tcRefreshQueueBtn', async () => {
          await refreshTrainingCenterQueue();
          setTrainingCenterError('');
        });
      } catch (err) {
        setTrainingCenterError(err.message || String(err));
      }
    };
    $('tcDispatchNextBtn').onclick = async () => {
      try {
        await withButtonLock('tcDispatchNextBtn', async () => {
          await dispatchNextTrainingCenterQueue();
        });
      } catch (err) {
        setTrainingCenterError(err.message || String(err));
      }
    };
    $('tcSwitchVersionTrigger').onclick = (event) => {
      event.preventDefault();
      const trigger = $('tcSwitchVersionTrigger');
      if (!trigger || trigger.disabled) return;
      setTrainingCenterVersionDropdownOpen(!state.tcVersionDropdownOpen);
    };
    $('tcSwitchVersionOptions').onclick = (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      const option = target.closest('.tc-version-option');
      if (!option) return;
      const version = safe(option.getAttribute('data-version')).trim();
      const select = $('tcSwitchVersionSelect');
      if (!version || !select) return;
      if (version === safe(select.value).trim()) {
        setTrainingCenterVersionDropdownOpen(false);
        return;
      }
      select.value = version;
      setTrainingCenterVersionDropdownOpen(false);
      select.dispatchEvent(new Event('change', { bubbles: true }));
    };
    $('tcSwitchVersionSelect').onchange = async () => {
      const select = $('tcSwitchVersionSelect');
      const trigger = $('tcSwitchVersionTrigger');
      const previous = currentTrainingCenterDisplayedVersion(state.tcSelectedAgentDetail || {});
      const next = safe(select ? select.value : '').trim();
      if (!next || next === previous) {
        return;
      }
      try {
        if (select) select.disabled = true;
        if (trigger) trigger.disabled = true;
        await switchTrainingCenterAgentVersion();
      } catch (err) {
        if (select) {
          select.value = previous;
        }
        setTrainingCenterDetailError(err.message || String(err));
      } finally {
        if (select) select.disabled = false;
        if (trigger) trigger.disabled = false;
      }
    };
    $('tcCloneAgentBtn').onclick = async () => {
      try {
        await withButtonLock('tcCloneAgentBtn', async () => {
          await cloneTrainingCenterAgentFromCurrent();
        });
      } catch (err) {
        setTrainingCenterDetailError(err.message || String(err));
      }
    };
    $('tcSetAvatarBtn').onclick = async () => {
      const fileInput = $('tcAvatarFileInput');
      if (!safe(state.tcSelectedAgentId).trim()) {
        setTrainingCenterDetailError('请先选择角色');
        return;
      }
      if (fileInput) {
        fileInput.value = '';
        fileInput.click();
      }
    };
    $('tcAvatarFileInput').addEventListener('change', async () => {
      const fileInput = $('tcAvatarFileInput');
      const hasFile = !!(fileInput && fileInput.files && fileInput.files[0]);
      if (!hasFile) return;
      try {
        await withButtonLock('tcSetAvatarBtn', async () => {
          await setTrainingCenterAgentAvatar();
        });
      } catch (err) {
        setTrainingCenterDetailError(err.message || String(err));
      }
    });
    $('tcDiscardPreReleaseBtn').onclick = async () => {
      try {
        await withButtonLock('tcDiscardPreReleaseBtn', async () => {
          await discardTrainingCenterPreRelease();
        });
      } catch (err) {
        setTrainingCenterDetailError(err.message || String(err));
      }
    };
    $('tcEnterReleaseReviewBtn').onclick = async () => {
      try {
        await withButtonLock('tcEnterReleaseReviewBtn', async () => {
          await enterTrainingCenterReleaseReview();
        });
      } catch (err) {
        const agentId = typeof selectedTrainingCenterAgentId === 'function' ? selectedTrainingCenterAgentId() : '';
        const review = agentId && typeof currentTrainingCenterReleaseReview === 'function'
          ? currentTrainingCenterReleaseReview(agentId)
          : {};
        const localError = agentId && typeof currentTrainingCenterReleaseReviewError === 'function'
          ? currentTrainingCenterReleaseReviewError(agentId)
          : null;
        const hasStructuredError = !!(
          safe(review && review.report_error).trim() ||
          safe(review && review.publish_error).trim() ||
          (localError && safe(localError.error_message).trim())
        );
        if (agentId && typeof renderTrainingCenterReleaseReview === 'function') {
          setTrainingCenterDetailError(hasStructuredError ? '' : err.message || String(err));
          renderTrainingCenterReleaseReview(agentId);
        } else {
          setTrainingCenterDetailError(err.message || String(err));
        }
      }
    };
    $('tcSubmitEvalBtn').onclick = async () => {
      try {
        await withButtonLock('tcSubmitEvalBtn', async () => {
          await submitTrainingCenterManualEvaluation();
        });
      } catch (err) {
        setTrainingCenterDetailError(err.message || String(err));
      }
    };
    $('tcConfirmReleaseReviewBtn').onclick = async () => {
      try {
        await withButtonLock('tcConfirmReleaseReviewBtn', async () => {
          await confirmTrainingCenterReleaseReview();
        });
      } catch (err) {
        const agentId = typeof selectedTrainingCenterAgentId === 'function' ? selectedTrainingCenterAgentId() : '';
        const review = agentId && typeof currentTrainingCenterReleaseReview === 'function'
          ? currentTrainingCenterReleaseReview(agentId)
          : {};
        const localError = agentId && typeof currentTrainingCenterReleaseReviewError === 'function'
          ? currentTrainingCenterReleaseReviewError(agentId)
          : null;
        const hasStructuredError = !!(
          safe(review && review.report_error).trim() ||
          safe(review && review.publish_error).trim() ||
          (localError && safe(localError.error_message).trim())
        );
        if (agentId && typeof renderTrainingCenterReleaseReview === 'function') {
          setTrainingCenterDetailError(hasStructuredError ? '' : err.message || String(err));
          renderTrainingCenterReleaseReview(agentId);
        } else {
          setTrainingCenterDetailError(err.message || String(err));
        }
      }
    };
    $('showTestDataCheck').onchange = async () => {
      const node = $('showTestDataCheck');
      const previous = !!state.showTestData;
      const checked = !!$('showTestDataCheck').checked;
      try {
        setSettingsError('');
        const payload = {
          show_test_data: checked,
        };
        if (queryParam('td_probe_force_write_fail') === '1') {
          payload.force_fail = true;
        }
        const saved = await postJSON('/api/config/show-test-data', payload);
        state.showTestData = !!saved.show_test_data;
        node.checked = state.showTestData;
        localStorage.setItem(showTestDataCacheKey, state.showTestData ? '1' : '0');
        cleanupLegacyShowSystemAgentsCache();
        updateShowTestDataMeta();
        await refreshAgents(true, { autoAnalyze: false });
        await refreshSessions();
        await refreshWorkflows();
        await refreshTrainingCenterAgents();
        await refreshTrainingCenterQueue(false);
        await refreshDashboard();
        setStatus(state.showTestData ? '已开启测试数据展示' : '已隐藏测试数据');
      } catch (err) {
        state.showTestData = previous;
        node.checked = previous;
        localStorage.setItem(showTestDataCacheKey, previous ? '1' : '0');
        updateShowTestDataMeta();
        setSettingsError(err.message || String(err));
        setStatus('测试数据开关更新失败');
      }
    };
    $('allowManualPolicyInputCheck').onchange = async () => {
      const checked = !!$('allowManualPolicyInputCheck').checked;
      try {
        const data = await postJSON('/api/config/manual-policy-input', {
          allow_manual_policy_input: checked,
        });
        state.allowManualPolicyInput = !!data.allow_manual_policy_input;
        $('allowManualPolicyInputCheck').checked = state.allowManualPolicyInput;
        updateManualPolicyInputMeta();
        startPolicyAnalysisForSelection();
        setStatus(state.allowManualPolicyInput ? '已开启手动角色与职责兜底' : '已关闭手动角色与职责兜底');
      } catch (err) {
        $('allowManualPolicyInputCheck').checked = state.allowManualPolicyInput;
        updateManualPolicyInputMeta();
        setSettingsError(err.message || String(err));
      }
    };
    $('switchRootBtn').onclick = async () => {
      try {
        setSettingsError('');
        await withButtonLock('switchRootBtn', async () => {
          await switchAgentSearchRoot();
        });
      } catch (err) {
        setSettingsError(err.message || String(err));
      }
    };
    $('refreshSettingsBtn').onclick = async () => {
      try {
        await withButtonLock('refreshSettingsBtn', async () => {
          await refreshAgents(true);
          await refreshSessions();
          await refreshWorkflows();
          await refreshDashboard();
          setStatus('设置已刷新');
        });
      } catch (err) {
        setSettingsError(err.message || String(err));
      }
    };
    $('cleanupHistoryBtn').onclick = async () => {
      try {
        setSettingsError('');
        await withButtonLock('cleanupHistoryBtn', async () => {
          await cleanupHistory();
        });
      } catch (err) {
        setSettingsError(err.message || String(err));
      }
    };
    $('policyConfirmUseBtn').onclick = async () => {
      try {
        await withButtonLock('policyConfirmUseBtn', async () => {
          await submitPolicyConfirmation('confirm');
          await refreshAgents(true);
          await refreshSessions();
          await refreshDashboard();
          setStatus('角色与职责确认成功，已创建会话');
        });
      } catch (err) {
        setPolicyConfirmError(err.message || String(err));
      }
    };
    $('policyEditUseBtn').onclick = async () => {
      try {
        await withButtonLock('policyEditUseBtn', async () => {
          await submitPolicyConfirmation('edit');
          await refreshAgents(true);
          await refreshSessions();
          await refreshDashboard();
          setStatus('角色与职责编辑确认成功，已创建会话');
        });
      } catch (err) {
        setPolicyConfirmError(err.message || String(err));
      }
    };
    $('policyRescoreBtn').onclick = async () => {
      try {
        await withButtonLock('policyRescoreBtn', async () => {
          await rescoreEditedPolicy();
        });
      } catch (err) {
        setPolicyConfirmError(err.message || String(err));
      }
    };
    $('policyCancelBtn').onclick = () => {
      closePolicyConfirmModal();
      setStatus('已取消角色与职责确认/兜底');
    };
    $('policyConfirmMask').onclick = (event) => {
      if (event.target === $('policyConfirmMask')) {
        closePolicyConfirmModal();
      }
    };
    document.addEventListener('click', (event) => {
      const target = event.target;
      if (!(target instanceof Node)) return;
      if (state.agentDropdownOpen) {
        const host = $('agentDropdown');
        if (host && !host.contains(target)) {
          setAgentDropdownOpen(false);
        }
      }
      if (state.tcVersionDropdownOpen) {
        const versionHost = $('tcVersionDropdown');
        if (versionHost && !versionHost.contains(target)) {
          setTrainingCenterVersionDropdownOpen(false);
        }
      }
    });
    document.addEventListener('keydown', (event) => {
      if (event.key !== 'Escape') return;
      if (!$('policyConfirmMask').classList.contains('hidden')) {
        closePolicyConfirmModal();
        return;
      }
      if (state.tcVersionDropdownOpen) {
        setTrainingCenterVersionDropdownOpen(false);
        return;
      }
      if (state.agentDropdownOpen) {
        setAgentDropdownOpen(false);
      }
    });
    window.addEventListener('resize', handleAgentDropdownViewportChange);
    window.addEventListener('scroll', handleAgentDropdownViewportChange, true);
    $('policyRecommendBtn').onclick = async () => {
      try {
        await withButtonLock('policyRecommendBtn', async () => {
          await recommendPolicyDraft();
        });
      } catch (err) {
        setPolicyConfirmError(err.message || String(err));
      }
    };
    const handlePolicyEditInput = () => {
      const pending = state.pendingPolicyConfirmation;
      if (!pending || !pending.rescore_fingerprint) return;
      if (pending.rescore_fingerprint === policyEditFingerprint()) return;
      clearPolicyEditScorePreview('内容已变更，请点击“重新评分并对比”。');
    };
    ['policyEditRole', 'policyEditGoal', 'policyEditDuty'].forEach((id) => {
      const node = $(id);
      if (!node) return;
      node.addEventListener('input', handlePolicyEditInput);
    });
    $('policyCopyBtn').onclick = async () => {
      try {
        const result = await withButtonLock('policyCopyBtn', async () => {
          return copyPolicyConfirmHtmlView();
        });
        setPolicyConfirmError('');
        if (result && result.mode === 'html') {
          setStatus('已复制网页富文本视图到剪贴板');
        } else {
          setStatus('复制完成');
        }
      } catch (err) {
        setPolicyConfirmError('复制失败：' + safe(err.message || String(err)));
      }
    };
    document.querySelectorAll('.tab').forEach((node) => {
      node.onclick = () => switchTab(safe(node.getAttribute('data-tab')));
    });
  }

  function findTrainingCenterProbeAgent(options) {
    const opts = options || {};
    const rows = Array.isArray(state.tcAgents) ? state.tcAgents : [];
    if (!rows.length) return null;
    const expected = safe(queryParam('tc_probe_agent')).trim().toLowerCase();
    if (expected) {
      const matched = rows.find((row) => {
        const byName = safe(row && row.agent_name).trim().toLowerCase();
        const byId = safe(row && row.agent_id).trim().toLowerCase();
        return byName === expected || byId === expected;
      });
      if (matched) return matched;
    }
    if (opts.nonGitFirst) {
      const nonGit = rows.find((row) => !row.git_available);
      if (nonGit) return nonGit;
    }
    return rows[0] || null;
  }

  async function selectTrainingCenterProbeAgent(options) {
    const selected = findTrainingCenterProbeAgent(options);
    if (!selected) return null;
    const agentId = safe(selected.agent_id).trim();
    if (!agentId) return null;
    state.tcSelectedAgentId = agentId;
    state.tcSelectedAgentName = safe(selected.agent_name || '');
    state.tcSelectedAgentDetail = selected;
    syncTrainingCenterPlanAgentOptions();
    updateTrainingCenterSelectedMeta();
    renderTrainingCenterAgentList();
    renderTrainingCenterAgentDetail();
    await refreshTrainingCenterReleases(agentId);
    return selected;
  }

  function fillTrainingCenterProbePlan(agentId, suffix, priority) {
    const sid = safe(suffix).trim() || String(Date.now());
    const target = safe(agentId).trim();
    if ($('tcPlanTargetAgentSelect')) $('tcPlanTargetAgentSelect').value = target;
    if ($('tcPlanGoalInput')) $('tcPlanGoalInput').value = 'probe capability ' + sid;
    if ($('tcPlanTasksInput')) $('tcPlanTasksInput').value = 'probe task ' + sid + '\nverify traceability ' + sid;
    if ($('tcPlanAcceptanceInput')) $('tcPlanAcceptanceInput').value = 'probe acceptance ' + sid;
    if ($('tcPlanPrioritySelect')) $('tcPlanPrioritySelect').value = safe(priority).trim();
    if ($('tcTrainerQueryInput')) $('tcTrainerQueryInput').value = 'trainer-probe';
    state.tcTrainerSelected = 'trainer-probe';
    state.tcSelectedAgentId = target;
    const matched = Array.isArray(state.tcAgents)
      ? state.tcAgents.find((item) => safe(item.agent_id).trim() === target)
      : null;
    if (matched) {
      state.tcSelectedAgentDetail = matched;
      state.tcSelectedAgentName = safe(matched.agent_name || '');
    }
    updateTrainingCenterSelectedMeta();
    renderTrainingCenterAgentList();
    renderTrainingCenterAgentDetail();
  }

  function ensureTrainingCenterProbeOutputNode() {
    let node = $('trainingCenterProbeOutput');
    if (node) return node;
    node = document.createElement('pre');
    node.id = 'trainingCenterProbeOutput';
    node.style.display = 'none';
    document.body.appendChild(node);
    return node;
  }


  function ensureTestDataToggleProbeOutputNode() {
    let node = $('testDataToggleProbeOutput');
    if (node) return node;
    node = document.createElement('pre');
    node.id = 'testDataToggleProbeOutput';
    node.style.display = 'none';
    document.body.appendChild(node);
    return node;
  }

  async function runTestDataToggleProbe() {
    const output = {
      ts: new Date().toISOString(),
      case: testDataToggleProbeCase(),
      pass: false,
      error: '',
      total_agents: 0,
      visible_when_off: 0,
      visible_when_on: 0,
      tc_agents_off: 0,
      tc_agents_on: 0,
      tc_queue_off: 0,
      tc_queue_on: 0,
      error_text: '',
      retry_ok: false,
      session_toggle_exists: false,
      settings_toggle_exists: false,
      dashboard_off: {},
      dashboard_on: {},
    };
    const waitMs = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));
    try {
      const probeCase = output.case;
      const refreshAll = async () => {
        await refreshAgents(true, { autoAnalyze: false });
        await refreshSessions();
        await refreshWorkflows();
        await refreshDashboard();
        await refreshTrainingCenterAgents();
        await refreshTrainingCenterQueue(true);
      };
      if (probeCase === 'ac_td_01') {
        switchTab('chat');
        output.session_toggle_exists = !!$('showSystemAgentsCheck');
        switchTab('settings');
        output.settings_toggle_exists = !!$('showTestDataCheck');
        output.pass = !output.session_toggle_exists && output.settings_toggle_exists;
      } else if (probeCase === 'ac_td_02') {
        switchTab('settings');
        await postJSON('/api/config/show-test-data', { show_test_data: false });
        await refreshAll();
        output.server_value_after_set = !!state.showTestData;
        localStorage.setItem(showTestDataCacheKey, '1');
        await refreshAgents(true, { autoAnalyze: false });
        output.server_value_after_reload = !!state.showTestData;
        output.pass = !output.server_value_after_set && !output.server_value_after_reload;
      } else if (probeCase === 'ac_td_03') {
        switchTab('chat');
        await postJSON('/api/config/show-test-data', { show_test_data: false });
        await refreshAgents(true, { autoAnalyze: false });
        output.total_agents = Array.isArray(state.agents) ? state.agents.length : 0;
        output.visible_when_off = visibleAgents().length;
        await postJSON('/api/config/show-test-data', { show_test_data: true });
        await refreshAgents(true, { autoAnalyze: false });
        output.visible_when_on = visibleAgents().length;
        setAgentDropdownOpen(true);
        output.pass =
          output.total_agents >= output.visible_when_off &&
          output.visible_when_on >= output.visible_when_off &&
          output.visible_when_on === output.total_agents &&
          output.visible_when_on > output.visible_when_off;
      } else if (probeCase === 'ac_td_04') {
        switchTab('training');
        await postJSON('/api/config/show-test-data', { show_test_data: false });
        await refreshDashboard();
        output.dashboard_off = await getJSON('/api/dashboard');
        await postJSON('/api/config/show-test-data', { show_test_data: true });
        await refreshDashboard();
        output.dashboard_on = await getJSON('/api/dashboard');
        const changed =
          Number(output.dashboard_off.new_sessions_24h || 0) !== Number(output.dashboard_on.new_sessions_24h || 0) ||
          Number(output.dashboard_off.pending_analysis || 0) !== Number(output.dashboard_on.pending_analysis || 0) ||
          Number(output.dashboard_off.pending_training || 0) !== Number(output.dashboard_on.pending_training || 0);
        output.pass = !!changed;
      } else if (probeCase === 'ac_td_05') {
        switchTab('training-center');
        setTrainingCenterModule('ops');
        await postJSON('/api/config/show-test-data', { show_test_data: false });
        await refreshTrainingCenterAgents();
        await refreshTrainingCenterQueue(true);
        output.tc_agents_off = Array.isArray(state.tcAgents) ? state.tcAgents.length : 0;
        output.tc_queue_off = Array.isArray(state.tcQueue) ? state.tcQueue.length : 0;
        await postJSON('/api/config/show-test-data', { show_test_data: true });
        await refreshTrainingCenterAgents();
        await refreshTrainingCenterQueue(true);
        output.tc_agents_on = Array.isArray(state.tcAgents) ? state.tcAgents.length : 0;
        output.tc_queue_on = Array.isArray(state.tcQueue) ? state.tcQueue.length : 0;
        output.pass =
          output.tc_agents_on >= output.tc_agents_off &&
          output.tc_queue_on >= output.tc_queue_off &&
          (output.tc_agents_on > output.tc_agents_off || output.tc_queue_on > output.tc_queue_off);
      } else if (probeCase === 'ac_td_06') {
        switchTab('settings');
        await refreshAgents(true, { autoAnalyze: false });
        const check = $('showTestDataCheck');
        const before = !!state.showTestData;
        if (!check) throw new Error('showTestDataCheck not found');
        check.checked = !before;
        check.dispatchEvent(new Event('change', { bubbles: true }));
        await waitMs(240);
        output.before_state = before;
        output.after_state = !!state.showTestData;
        output.after_checked = !!check.checked;
        output.error_text = safe($('settingsErr') ? $('settingsErr').textContent : '').trim();
        output.pass =
          output.after_state === before &&
          output.after_checked === before &&
          !!output.error_text;
      } else if (probeCase === 'ac_td_07') {
        switchTab('settings');
        let failed = false;
        try {
          await refreshAgents(true, {
            autoAnalyze: false,
            agentsPath: '/api/agents?force_show_test_data_read_fail=1',
          });
        } catch (err) {
          failed = true;
          setSettingsError(err.message || String(err));
        }
        output.error_text = safe($('settingsErr') ? $('settingsErr').textContent : '').trim();
        await refreshAgents(true, { autoAnalyze: false });
        output.retry_ok = !!state.agentSearchRootReady;
        output.pass = failed && !!output.error_text && output.retry_ok;
      } else if (probeCase === 'ac_td_08') {
        switchTab('settings');
        await postJSON('/api/config/show-test-data', { show_test_data: false });
        await refreshAgents(true, { autoAnalyze: false });
        localStorage.setItem('workflow.p0.settings.showSystemAgents', '1');
        localStorage.setItem(showTestDataCacheKey, '1');
        await refreshAgents(true, { autoAnalyze: false });
        const legacyValue = safe(localStorage.getItem('workflow.p0.settings.showSystemAgents')).trim();
        output.legacy_key_after_refresh = legacyValue;
        output.server_state = !!state.showTestData;
        output.pass = !output.server_state && !legacyValue;
      } else {
        output.pass = true;
      }
    } catch (err) {
      output.error = safe(err && err.message ? err.message : err);
    }
    const node = ensureTestDataToggleProbeOutputNode();
    node.textContent = JSON.stringify(output);
    node.setAttribute('data-pass', output.pass ? '1' : '0');
  }

  async function bootstrap() {
    initSplitters();
    bindEvents();
    setupSessionEntryToolbarIcons();
    setTrainingCenterModule('agents');
    renderTrainingCenterAgentStats();
    renderTrainingCenterAgentList();
    renderTrainingCenterAgentDetail();
    renderTrainingCenterQueue();
    renderTrainingCenterTrainerList();
    syncTrainingCenterPlanAgentOptions();
    updateTrainingCenterSelectedMeta();
    const cachedShowTestData = localStorage.getItem(showTestDataCacheKey);
    if (cachedShowTestData === '0' || cachedShowTestData === '1') {
      state.showTestData = cachedShowTestData === '1';
    }
    cleanupLegacyShowSystemAgentsCache();
    $('showTestDataCheck').checked = state.showTestData;
    updateShowTestDataMeta();
    updateClearPolicyCacheButton();
    setWorkflowQueueMode('records');
    await refreshAgents(false);
    await refreshSessions();
    await refreshWorkflows();
    await refreshDashboard();
    const cachedSession = localStorage.getItem(sessionCacheKey) || '';
    if (cachedSession && state.sessionsById[cachedSession]) {
      await selectSession(cachedSession);
    } else {
      renderFeed();
    }
    applyGateState();
    startWorkflowPoller();
    setStatus(state.agentSearchRootReady ? '就绪' : '等待设置角色搜索根路径');
    if (isLayoutProbeEnabled()) {
      await runLayoutProbe();
    }
    if (isPolicyProbeEnabled()) {
      await runPolicyProbe();
    }
    if (isTrainingCenterProbeEnabled()) {
      await runTrainingCenterProbe();
    }
    if (isTestDataToggleProbeEnabled()) {
      await runTestDataToggleProbe();
    }
  }

  bootstrap().catch((err) => {
    setChatError(err.message || String(err));
    setStatus('失败');
  });
})();
