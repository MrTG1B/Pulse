/**
 * AgentRouter Monitor & Pulse — Frontend Controller
 * Handles real-time countdown, local timezone calculation (UTC+05:30),
 * API key management, model switching, and automated health checks.
 */

(function () {
  'use strict';

  // State Management
  const state = {
    apiKey: '',
    maskedApiKey: '',
    hasApiKey: false,
    isKeyRevealed: false,
    selectedModel: 'gpt-6.1-sol',
    baseUrl: 'https://agentrouter.org',
    autoRefresh: true,
    refreshInterval: 30, // seconds
    userOffsetMinutes: 330, // Default UTC+05:30 (India Standard Time)
    nextSlotUtc: null,
    prevSlotUtc: null,
    currentSchedule: null,
    hasTriggeredChimeForSlot: false,
    lastCheckedTimestamp: null,
    isTesting: false,
    isCompact: false,
    isPinned: true,
    soundEnabled: true,
    activeModelFilter: 'all',
    provider: null,
    isSyncing: false,
    isDiscovering: false,
    accountRevision: 0,
    models: []
  };

  let autoRefreshTimer = null;
  let providerRefreshTimer = null;
  let countdownTimer = null;
  let elapsedTimer = null;

  // DOM Elements
  const el = {
    container: document.getElementById('widgetContainer'),
    mainContent: document.getElementById('mainContent'),
    headerPulseDot: document.getElementById('headerPulseDot'),
    btnPin: document.getElementById('btnPin'),
    btnCompact: document.getElementById('btnCompact'),
    btnSettings: document.getElementById('btnSettings'),
    btnHelp: document.getElementById('btnHelp'),
    btnMinimize: document.getElementById('btnMinimize'),
    btnClose: document.getElementById('btnClose'),

    // Compact View
    compactView: document.getElementById('compactView'),
    compactStatusDot: document.getElementById('compactStatusDot'),
    compactStatusText: document.getElementById('compactStatusText'),
    compactCountdown: document.getElementById('compactCountdown'),
    compactLocalTime: document.getElementById('compactLocalTime'),
    compactCenter: document.getElementById('compactCenter'),
    compactLatency: document.getElementById('compactLatency'),
    btnCompactRefresh: document.getElementById('btnCompactRefresh'),
    btnCompactExpand: document.getElementById('btnCompactExpand'),

    // API Key
    apiKeyStrip: document.getElementById('apiKeyStrip'),
    keyDisplayValue: document.getElementById('keyDisplayValue'),
    btnEditKey: document.getElementById('btnEditKey'),
    keyDrawer: document.getElementById('keyDrawer'),
    inputApiKey: document.getElementById('inputApiKey'),
    btnInputEye: document.getElementById('btnInputEye'),
    btnSaveKey: document.getElementById('btnSaveKey'),
    btnCancelEditKey: document.getElementById('btnCancelEditKey'),
    btnCloseKeyDrawer: document.getElementById('btnCloseKeyDrawer'),
    btnClearKey: document.getElementById('btnClearKey'),

    // Status Card
    statusCard: document.getElementById('statusCard'),
    statusBadge: document.getElementById('statusBadge'),
    badgeDot: document.getElementById('badgeDot'),
    badgeTitle: document.getElementById('badgeTitle'),
    latencyBadge: document.getElementById('latencyBadge'),
    latencyText: document.getElementById('latencyText'),
    statusMessage: document.getElementById('statusMessage'),
    statusActionRow: document.getElementById('statusActionRow'),
    btnSwitchRecommended: document.getElementById('btnSwitchRecommended'),

    // Countdown Card
    countdownCard: document.getElementById('countdownCard'),
    scheduleTitle: document.getElementById('scheduleTitle'),
    supplyMessage: document.getElementById('supplyMessage'),
    providerSyncStatus: document.getElementById('providerSyncStatus'),
    usedCredits: document.getElementById('usedCredits'),
    remainingKeyCredit: document.getElementById('remainingKeyCredit'),
    usageStatus: document.getElementById('usageStatus'),
    modelUsageList: document.getElementById('modelUsageList'),
    officialNoticeText: document.getElementById('officialNoticeText'),
    officialNoticeDate: document.getElementById('officialNoticeDate'),
    noticeHistory: document.getElementById('noticeHistory'),
    helpOfficialNoticeText: document.getElementById('helpOfficialNoticeText'),
    helpScheduleSummary: document.getElementById('helpScheduleSummary'),
    helpModelsList: document.getElementById('helpModelsList'),
    batchPill: document.getElementById('batchPill'),
    cntHours: document.getElementById('cntHours'),
    cntMinutes: document.getElementById('cntMinutes'),
    cntSeconds: document.getElementById('cntSeconds'),
    cycleProgressBar: document.getElementById('cycleProgressBar'),
    localTimeDisplay: document.getElementById('localTimeDisplay'),
    beijingRefTime: document.getElementById('beijingRefTime'),
    utcRefTime: document.getElementById('utcRefTime'),
    dailyScheduleTimes: document.getElementById('dailyScheduleTimes'),

    // Controls
    modelSelect: document.getElementById('modelSelect'),
    modelsCount: document.getElementById('modelsCount'),
    btnTestConnection: document.getElementById('btnTestConnection'),
    btnTestAllModels: document.getElementById('btnTestAllModels'),
    btnDiscoverModels: document.getElementById('btnDiscoverModels'),
    spinnerIcon: document.getElementById('spinnerIcon'),
    testBtnText: document.getElementById('testBtnText'),
    chkAutoRefresh: document.getElementById('chkAutoRefresh'),
    selInterval: document.getElementById('selInterval'),
    btnSoundToggle: document.getElementById('btnSoundToggle'),
    soundIcon: document.getElementById('soundIcon'),
    lastCheckedTime: document.getElementById('lastCheckedTime'),

    // Models Overview
    modelsOverviewList: document.getElementById('modelsOverviewList'),

    // Settings Modal
    settingsModal: document.getElementById('settingsModal'),
    settingApiKey: document.getElementById('settingApiKey'),
    btnModalSaveKey: document.getElementById('btnModalSaveKey'),
    settingBaseUrl: document.getElementById('settingBaseUrl'),
    settingTimezone: document.getElementById('settingTimezone'),
    settingAlwaysOnTop: document.getElementById('settingAlwaysOnTop'),
    settingChime: document.getElementById('settingChime'),
    settingSchedulerEnabled: document.getElementById('settingSchedulerEnabled'),
    settingPressEnter: document.getElementById('settingPressEnter'),
    settingGeminiKey: document.getElementById('settingGeminiKey'),
    btnSaveGeminiKey: document.getElementById('btnSaveGeminiKey'),
    btnScanWindows: document.getElementById('btnScanWindows'),
    btnManualTrigger: document.getElementById('btnManualTrigger'),
    focusTriggerResult: document.getElementById('focusTriggerResult'),
    btnCloseSettingsModal: document.getElementById('btnCloseSettingsModal'),
    btnModalClose: document.getElementById('btnModalClose'),

    // Help Modal
    helpModal: document.getElementById('helpModal'),
    btnCloseHelpModal: document.getElementById('btnCloseHelpModal'),
    btnHelpDone: document.getElementById('btnHelpDone')
  };

  // Helper: Resilient Web Audio Notification Chime with Autoplay Unlocking
  let audioCtx = null;
  function getAudioContext() {
    if (!audioCtx) {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (AudioContextClass) {
        audioCtx = new AudioContextClass();
      }
    }
    if (audioCtx && audioCtx.state === 'suspended') {
      audioCtx.resume().catch(() => {});
    }
    return audioCtx;
  }

  function playChime() {
    if (!state.soundEnabled) return;
    try {
      const ctx = getAudioContext();
      if (!ctx) return;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
      osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.15); // A5
      gain.gain.setValueAtTime(0.12, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.35);
    } catch (e) {
      console.warn('Audio play error:', e);
    }
  }

  // --- Initializer ---
  async function init() {
    try {
      setupEventListeners();
    } catch (e) {
      console.error('setupEventListeners error:', e);
    }
    try {
      if (el.btnPin) el.btnPin.classList.toggle('active', state.isPinned);
      computeLocalSchedule(); // Calculate schedule immediately for 0ms visual rendering
    } catch (e) {
      console.error('computeLocalSchedule error:', e);
    }
    try {
      startCountdownLoop();
    } catch (e) {
      console.error('startCountdownLoop error:', e);
    }
    try {
      startElapsedTimer();
      startProviderRefresh();
    } catch (e) {
      console.error('startElapsedTimer error:', e);
    }
    try {
      await loadInitialData();
    } catch (e) {
      console.error('loadInitialData error:', e);
    }
    try {
      startAutoRefresh();
    } catch (e) {
      console.error('startAutoRefresh error:', e);
    }
  }

  // --- Event Listeners ---
  function setupEventListeners() {
    // Prevent titlebar dragging when clicking window controls or buttons
    document.querySelectorAll('.no-drag, .window-controls button, .api-key-strip button, .action-buttons-row button').forEach(elem => {
      elem.addEventListener('mousedown', (e) => e.stopPropagation());
    });

    // API Key Interactions
    if (el.btnEditKey) el.btnEditKey.addEventListener('click', toggleKeyDrawer);
    const keyStripLeft = document.getElementById('keyStripLeft');
    if (keyStripLeft) keyStripLeft.addEventListener('click', toggleKeyDrawer);
    if (el.btnCloseKeyDrawer) el.btnCloseKeyDrawer.addEventListener('click', () => el.keyDrawer.style.display = 'none');
    if (el.btnCancelEditKey) el.btnCancelEditKey.addEventListener('click', () => el.keyDrawer.style.display = 'none');
    if (el.btnInputEye) el.btnInputEye.addEventListener('click', toggleInputEye);
    if (el.btnSaveKey) el.btnSaveKey.addEventListener('click', saveApiKey);
    if (el.btnClearKey) el.btnClearKey.addEventListener('click', clearApiKey);
    if (el.btnToggleKeyMask) el.btnToggleKeyMask.addEventListener('click', toggleKeyMaskDisplay);

    // Enter key to submit API keys
    if (el.inputApiKey) {
      el.inputApiKey.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') saveApiKey();
      });
    }
    if (el.settingApiKey) {
      el.settingApiKey.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') saveModalApiKey();
      });
    }

    // Testing & Discovery
    if (el.btnTestConnection) el.btnTestConnection.addEventListener('click', () => testConnection(true));
    if (el.btnTestAllModels) el.btnTestAllModels.addEventListener('click', testAllModels);
    if (el.btnDiscoverModels) el.btnDiscoverModels.addEventListener('click', discoverModels);
    if (el.btnCompactRefresh) el.btnCompactRefresh.addEventListener('click', () => testConnection(true));

    // Model Change
    if (el.modelSelect) el.modelSelect.addEventListener('change', onModelSelected);
    if (el.btnSwitchRecommended) {
      el.btnSwitchRecommended.addEventListener('click', () => {
        const targetId = el.btnSwitchRecommended.dataset.modelId;
        if (!targetId) return;
        if (el.modelSelect) el.modelSelect.value = targetId;
        onModelSelected();
      });
    }

    // Window Controls
    if (el.btnCompact) el.btnCompact.addEventListener('click', toggleCompactMode);
    if (el.btnCompactExpand) el.btnCompactExpand.addEventListener('click', toggleCompactMode);
    if (el.btnPin) {
      el.btnPin.classList.toggle('active', state.isPinned);
      el.btnPin.addEventListener('click', toggleAlwaysOnTop);
    }
    if (el.btnMinimize) el.btnMinimize.addEventListener('click', minimizeWindow);
    if (el.btnClose) el.btnClose.addEventListener('click', closeWindow);

    // Help Modal
    if (el.btnHelp) el.btnHelp.addEventListener('click', openHelpModal);
    if (el.btnCloseHelpModal) el.btnCloseHelpModal.addEventListener('click', closeHelpModal);
    if (el.btnHelpDone) el.btnHelpDone.addEventListener('click', closeHelpModal);

    // Auto-refresh & Sound
    if (el.chkAutoRefresh) {
      el.chkAutoRefresh.addEventListener('change', (e) => {
        state.autoRefresh = e.target.checked;
        restartAutoRefresh();
      });
    }
    if (el.selInterval) {
      el.selInterval.addEventListener('change', (e) => {
        state.refreshInterval = parseInt(e.target.value, 10);
        restartAutoRefresh();
      });
    }
    if (el.btnSoundToggle) {
      el.btnSoundToggle.addEventListener('click', () => {
        state.soundEnabled = !state.soundEnabled;
        if (el.soundIcon) el.soundIcon.textContent = state.soundEnabled ? '🔔' : '🔕';
        if (el.settingChime) el.settingChime.checked = state.soundEnabled;
        saveConfigToServer({ sound_alert_enabled: state.soundEnabled });
        if (state.soundEnabled) playChime();
      });
    }

    // Settings Modal
    if (el.btnSettings) el.btnSettings.addEventListener('click', openSettingsModal);
    if (el.btnCloseSettingsModal) el.btnCloseSettingsModal.addEventListener('click', closeSettingsModal);
    if (el.btnModalClose) el.btnModalClose.addEventListener('click', closeSettingsModal);
    if (el.btnModalSaveKey) el.btnModalSaveKey.addEventListener('click', saveModalApiKey);
    if (el.settingBaseUrl) {
      el.settingBaseUrl.addEventListener('change', (e) => {
        state.baseUrl = e.target.value;
        state.accountRevision += 1;
        saveConfigToServer({ base_url: state.baseUrl }).then(() => discoverModels());
      });
    }
    if (el.settingTimezone) el.settingTimezone.addEventListener('change', onTimezoneSettingChange);
    if (el.settingAlwaysOnTop) {
      el.settingAlwaysOnTop.addEventListener('change', (e) => {
        state.isPinned = e.target.checked;
        if (el.btnPin) el.btnPin.classList.toggle('active', state.isPinned);
        saveConfigToServer({ always_on_top: state.isPinned });
        if (window.pywebview && window.pywebview.api && window.pywebview.api.toggle_always_on_top) {
          window.pywebview.api.toggle_always_on_top(state.isPinned);
        }
      });
    }
    if (el.settingChime) {
      el.settingChime.addEventListener('change', (e) => {
        state.soundEnabled = e.target.checked;
        if (el.soundIcon) el.soundIcon.textContent = state.soundEnabled ? '🔔' : '🔕';
        saveConfigToServer({ sound_alert_enabled: state.soundEnabled });
        if (state.soundEnabled) playChime();
      });
    }

    // Auto-Focus Scheduler Controls
    if (el.settingSchedulerEnabled) {
      el.settingSchedulerEnabled.addEventListener('change', async (e) => {
        try {
          await fetch('/api/scheduler/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: e.target.checked })
          });
        } catch (err) {
          console.warn('Failed to toggle scheduler:', err);
        }
      });
    }

    if (el.settingPressEnter) {
      el.settingPressEnter.addEventListener('change', (e) => {
        saveConfigToServer({ scheduler_press_enter: e.target.checked });
      });
    }

    if (el.btnSaveGeminiKey) {
      el.btnSaveGeminiKey.addEventListener('click', async () => {
        const key = el.settingGeminiKey ? el.settingGeminiKey.value.trim() : '';
        if (!key) return;
        try {
          await saveConfigToServer({ gemini_api_key: key, gemini_enabled: true });
          if (el.focusTriggerResult) {
            el.focusTriggerResult.textContent = '✅ Gemini 3.8 key saved & enabled.';
          }
          if (el.settingGeminiKey) el.settingGeminiKey.value = '';
        } catch (err) {
          if (el.focusTriggerResult) {
            el.focusTriggerResult.textContent = '❌ Failed to save Gemini key.';
          }
        }
      });
    }

    if (el.btnScanWindows) {
      el.btnScanWindows.addEventListener('click', async () => {
        if (el.focusTriggerResult) el.focusTriggerResult.textContent = '🔍 Scanning for open Codex & Claude Code apps...';
        try {
          const res = await fetch('/api/focus/scan');
          const data = await res.json();
          if (data.count === 0) {
            if (el.focusTriggerResult) el.focusTriggerResult.textContent = '❌ Neither Codex nor Claude Code is currently open.';
          } else {
            const list = data.found.map(w => `${w.app === 'codex' ? '🤖 Codex' : '🧠 Claude Code'}: "${w.title}"`).join(' • ');
            if (el.focusTriggerResult) el.focusTriggerResult.textContent = `✅ Found ${data.count} app(s): ${list}`;
          }
        } catch (err) {
          if (el.focusTriggerResult) el.focusTriggerResult.textContent = '⚠️ Scan error: ' + err.message;
        }
      });
    }

    if (el.btnManualTrigger) {
      el.btnManualTrigger.addEventListener('click', async () => {
        if (el.focusTriggerResult) el.focusTriggerResult.textContent = '⚡ Focusing app and pressing Enter...';
        const pressEnter = el.settingPressEnter ? el.settingPressEnter.checked : true;
        try {
          const res = await fetch('/api/focus/trigger', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ press_enter: pressEnter })
          });
          const data = await res.json();
          const message = data.ai_message || data.message || 'Complete.';
          if (el.focusTriggerResult) el.focusTriggerResult.textContent = message;
        } catch (err) {
          if (el.focusTriggerResult) el.focusTriggerResult.textContent = '⚠️ Trigger error: ' + err.message;
        }
      });
    }

    // Modal overlay backdrop clicks to dismiss
    if (el.settingsModal) {
      el.settingsModal.addEventListener('click', (e) => {
        if (e.target === el.settingsModal) closeSettingsModal();
      });
    }
    if (el.helpModal) {
      el.helpModal.addEventListener('click', (e) => {
        if (e.target === el.helpModal) closeHelpModal();
      });
    }

    // Interactive UI components
    setupHelpTabs();
    setupModelFilterChips();
    setupKeyboardShortcuts();
    setupExternalLinks();
    setupAudioUnlocking();
    setupScrollHandling();
  }

  // --- Load Initial Data ---
  async function loadInitialData() {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);
    try {
      const res = await fetch('/api/config', { signal: controller.signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const cfg = await res.json();
      state.hasApiKey = cfg.has_api_key;
      state.maskedApiKey = cfg.masked_api_key || '';
      state.selectedModel = cfg.selected_model || state.selectedModel;
      state.refreshInterval = cfg.refresh_interval_sec || 30;
      state.autoRefresh = cfg.auto_refresh_enabled !== false;
      state.isPinned = cfg.always_on_top !== false;
      state.soundEnabled = cfg.sound_alert_enabled !== false;
      state.userOffsetMinutes = cfg.user_timezone_offset ?? 330;
      state.baseUrl = cfg.base_url || 'https://agentrouter.org';
      el.chkAutoRefresh.checked = state.autoRefresh;
      el.selInterval.value = String(state.refreshInterval);
      el.btnPin.classList.toggle('active', state.isPinned);
      if (el.soundIcon) el.soundIcon.textContent = state.soundEnabled ? '🔔' : '🔕';
      updateKeyDisplay();
      await refreshProviderData();
      await testConnection(false);
    } catch (err) {
      console.warn('Initial load error:', err);
      computeLocalSchedule();
    } finally {
      clearTimeout(timeoutId);
    }
  }

  // --- API Key Logic ---
  function updateKeyDisplay() {
    if (state.hasApiKey) {
      el.keyDisplayValue.textContent = state.maskedApiKey || 'sk-••••••••';
      el.btnEditKey.textContent = 'Edit';
      if (el.btnToggleKeyMask) el.btnToggleKeyMask.style.display = 'none';
    } else {
      el.keyDisplayValue.textContent = 'Not Set (Click to enter)';
      el.btnEditKey.textContent = 'Enter Key';
      if (el.btnToggleKeyMask) el.btnToggleKeyMask.style.display = 'none';
      state.isKeyRevealed = false;
    }
  }

  async function toggleKeyDrawer() {
    const isVisible = el.keyDrawer.style.display !== 'none';
    if (isVisible) {
      el.keyDrawer.style.display = 'none';
      return;
    }
    el.keyDrawer.style.display = 'block';
    el.inputApiKey.value = '';
    el.inputApiKey.placeholder = state.hasApiKey ? 'Enter new API key (sk-...)' : 'Paste API key (sk-...)';
    el.inputApiKey.type = 'password';
    if (el.btnInputEye) el.btnInputEye.textContent = '👁️';
    el.inputApiKey.focus();
  }

  function toggleInputEye() {
    if (el.inputApiKey.type === 'password') {
      el.inputApiKey.type = 'text';
      if (el.btnInputEye) el.btnInputEye.textContent = '🔒';
    } else {
      el.inputApiKey.type = 'password';
      if (el.btnInputEye) el.btnInputEye.textContent = '👁️';
    }
  }

  function toggleKeyMaskDisplay() {
    // Secure design: raw key remains in Python DPAPI storage
  }

  async function saveApiKey() {
    const key = el.inputApiKey.value.trim();
    if (!key) {
      alert('Please enter an API key.');
      return;
    }

    try {
      const res = await fetch('/api/config/key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: key, action: 'save' })
      });
      const data = await res.json();
      state.hasApiKey = data.has_api_key;
      state.accountRevision += 1;
      state.maskedApiKey = data.masked_api_key;
      state.apiKey = '';

      updateKeyDisplay();
      el.keyDrawer.style.display = 'none';
      el.inputApiKey.value = '';
      if (el.settingApiKey) el.settingApiKey.value = '';

      await discoverModels();
      testConnection(true);
    } catch (e) {
      alert('Failed to save API key: ' + e.message);
    }
  }

  async function saveModalApiKey() {
    const key = el.settingApiKey.value.trim();
    if (!key) return;
    el.inputApiKey.value = key;
    await saveApiKey();
    el.settingApiKey.value = '';
  }

  async function clearApiKey() {
    if (!confirm('Are you sure you want to remove the saved API key?')) return;
    try {
      const res = await fetch('/api/config/key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'clear' })
      });
      const data = await res.json();
      state.hasApiKey = false;
      state.accountRevision += 1;
      state.maskedApiKey = '';
      state.apiKey = '';
      state.isKeyRevealed = false;
      updateKeyDisplay();
      el.keyDrawer.style.display = 'none';
      el.inputApiKey.value = '';
      if (el.settingApiKey) el.settingApiKey.value = '';
      testConnection(true);
    } catch (e) {
      console.error(e);
    }
  }

  // --- Schedule & Countdown (Core Requirement) ---
  function updateScheduleData(schedule) {
    if (!schedule) return;
    state.currentSchedule = schedule;
    state.nextSlotUtc = schedule.enabled && schedule.next_slot_utc ? new Date(schedule.next_slot_utc) : null;
    state.prevSlotUtc = schedule.enabled && schedule.prev_slot_utc ? new Date(schedule.prev_slot_utc) : null;
    if (schedule.user_offset_minutes !== undefined) state.userOffsetMinutes = schedule.user_offset_minutes;
    if (el.countdownCard) el.countdownCard.classList.toggle('no-schedule', !schedule.enabled);
    if (el.scheduleTitle) el.scheduleTitle.textContent = schedule.enabled ? 'NEXT QUOTA RELEASE' : (schedule.availability_title || 'No published schedule').toUpperCase();
    if (el.supplyMessage) el.supplyMessage.textContent = schedule.schedule_message || '';
    if (el.helpScheduleSummary) el.helpScheduleSummary.textContent = schedule.enabled ? `Next quota release: ${schedule.local_display}. Daily slots: ${schedule.daily_schedule_local}.` : (schedule.schedule_message || 'No published quota schedule.');
    if (el.batchPill) el.batchPill.textContent = schedule.enabled ? `Batch ${schedule.batch_number}` : schedule.supply_status === 'unlimited' ? 'All day' : 'No timer';
    if (el.localTimeDisplay) el.localTimeDisplay.textContent = schedule.local_display || '';
    if (el.beijingRefTime) el.beijingRefTime.textContent = schedule.daily_schedule_beijing ? `Beijing: ${schedule.daily_schedule_beijing}` : '';
    if (el.utcRefTime) el.utcRefTime.textContent = schedule.daily_schedule_utc || '';
    if (el.dailyScheduleTimes) el.dailyScheduleTimes.textContent = schedule.daily_schedule_local || 'No scheduled refill';
    if (el.compactLocalTime) el.compactLocalTime.textContent = schedule.enabled ? `(${schedule.local_time} ${schedule.user_timezone || ''})` : 'No scheduled refill';
    if (!schedule.enabled) {
      if (el.compactCountdown) el.compactCountdown.textContent = schedule.supply_status === 'unlimited' ? 'ALL DAY' : 'NO TIMER';
      if (el.cycleProgressBar) el.cycleProgressBar.style.width = '0%';
      state.hasTriggeredChimeForSlot = false;
    }
    tickCountdown();
  }

  function computeLocalSchedule() {
    const model = state.models.find(m => canonicalModelKey(m.id) === canonicalModelKey(state.selectedModel));
    const slots = model && model.provider_status === 'limited' && model.available_in_account !== false ? model.release_minutes_utc || [] : [];
    if (!slots.length) {
      const status = model ? model.provider_status : 'unknown';
      const labels = { unlimited: 'Unlimited · all day', unavailable: 'Temporarily unavailable', limited: 'Release time not announced' };
      const messages = {
        unlimited: 'No scheduled quota refill is needed. Test your token to confirm access.',
        unavailable: 'AgentRouter has not announced a restoration time.',
        limited: 'Limited supply. Wait for AgentRouter to publish a release time.'
      };
      updateScheduleData({ enabled: false, supply_status: status, availability_title: labels[status] || 'No published schedule', schedule_message: messages[status] || 'No quota release schedule has been announced for this model.' });
      return;
    }
    const now = new Date();
    const candidates = [];
    for (const dayOffset of [-1, 0, 1, 2]) {
      for (const slot of slots) {
        candidates.push(new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + dayOffset, Math.floor(slot / 60), slot % 60)));
      }
    }
    candidates.sort((a, b) => a - b);
    const next = candidates.find(c => c > now);
    const previous = candidates.filter(c => c <= now).pop();
    updateScheduleData({ enabled: true, supply_status: 'limited', next_slot_utc: next.toISOString(), prev_slot_utc: previous.toISOString(), batch_number: slots.indexOf(next.getUTCHours() * 60 + next.getUTCMinutes()) + 1 });
    formatLocalTimeDisplay(next);
  }

  function formatLocalTimeDisplay(dateUtc) {
    if (!dateUtc) return;
    const offsetMs = state.userOffsetMinutes * 60 * 1000;
    const localDate = new Date(dateUtc.getTime() + offsetMs);
    const nowLocal = new Date(Date.now() + offsetMs);

    let dayStr = 'Today';
    if (localDate.getUTCDate() !== nowLocal.getUTCDate()) {
      dayStr = 'Tomorrow';
    }

    const hours = localDate.getUTCHours();
    const minutes = String(localDate.getUTCMinutes()).padStart(2, '0');
    const ampm = hours >= 12 ? 'PM' : 'AM';
    const displayHours = hours % 12 || 12;
    const tzLabel = state.userOffsetMinutes === 330 ? 'IST' : `UTC${state.userOffsetMinutes >= 0 ? '+' : '-'}${String(Math.floor(Math.abs(state.userOffsetMinutes)/60)).padStart(2,'0')}:${String(Math.abs(state.userOffsetMinutes)%60).padStart(2,'0')}`;

    if (el.localTimeDisplay) {
      el.localTimeDisplay.textContent = `${dayStr}, ${String(displayHours).padStart(2, '0')}:${minutes} ${ampm} (${tzLabel})`;
    }
    if (el.compactLocalTime) {
      el.compactLocalTime.textContent = `(${String(displayHours).padStart(2, '0')}:${minutes} ${ampm})`;
    }
    if (el.bannerLocalTarget) {
      el.bannerLocalTarget.textContent = `at ${String(displayHours).padStart(2, '0')}:${minutes} ${ampm}`;
    }
  }

  function tickCountdown() {
    if (!state.currentSchedule?.enabled || !state.nextSlotUtc) return;

    const now = Date.now();
    const target = state.nextSlotUtc.getTime();
    let diffSec = Math.max(0, Math.floor((target - now) / 1000));

    // Handle rollover safely without infinite loops
    if (diffSec <= 0) {
      if (!state.hasTriggeredChimeForSlot) {
        state.hasTriggeredChimeForSlot = true;
        playChime();
        // Reload schedule and run test connection
        setTimeout(() => {
          refreshProviderData().then(() => testConnection(false));
        }, 1500);
      }
    } else {
      state.hasTriggeredChimeForSlot = false;
    }

    const hours = Math.floor(diffSec / 3600);
    const mins = Math.floor((diffSec % 3600) / 60);
    const secs = diffSec % 60;

    const hStr = String(hours).padStart(2, '0');
    const mStr = String(mins).padStart(2, '0');
    const sStr = String(secs).padStart(2, '0');

    if (el.cntHours) el.cntHours.textContent = hStr;
    if (el.cntMinutes) el.cntMinutes.textContent = mStr;
    if (el.cntSeconds) el.cntSeconds.textContent = sStr;

    if (el.compactCountdown) el.compactCountdown.textContent = `${hStr}:${mStr}:${sStr}`;
    if (el.bannerCountdown) {
      el.bannerCountdown.textContent = `${hStr}h ${mStr}m ${sStr}s`;
    }

    // Cycle progress bar
    if (state.prevSlotUtc && el.cycleProgressBar) {
      const cycleTotal = target - state.prevSlotUtc.getTime();
      const elapsed = now - state.prevSlotUtc.getTime();
      const pct = Math.min(100, Math.max(0, (elapsed / cycleTotal) * 100));
      el.cycleProgressBar.style.width = `${pct.toFixed(1)}%`;
    }
  }

  function startCountdownLoop() {
    if (countdownTimer) clearInterval(countdownTimer);
    countdownTimer = setInterval(tickCountdown, 1000);
    tickCountdown();
  }

  // --- Connection Diagnostics ---
  async function testConnection(manual = false) {
    if (state.isTesting) return;
    const model = state.models.find(m => m.id === state.selectedModel);
    if (!state.selectedModel || (model && !modelSelectable(model))) return;
    state.isTesting = true;

    el.spinnerIcon.classList.add('spinning');
    el.testBtnText.textContent = 'Checking...';
    if (el.btnTestConnection) el.btnTestConnection.disabled = true;

    const selectedModel = el.modelSelect.value || state.selectedModel;
    const accountRevision = state.accountRevision;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 25000);

    try {
      const res = await fetch('/api/check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({
          model_id: selectedModel,
          base_url: state.baseUrl
        })
      });
      clearTimeout(timeoutId);

      const data = await res.json();
      if (selectedModel !== state.selectedModel || accountRevision !== state.accountRevision) return;
      const current = state.models.find(m => m.id === selectedModel);
      if (current && !modelSelectable(current)) return;
      applyTestResult(data);

      state.lastCheckedTimestamp = Date.now();
      updateLastCheckedDisplay();

      if (manual && state.soundEnabled && data.is_active) {
        playChime();
      }

    } catch (err) {
      clearTimeout(timeoutId);
      console.error('Test error:', err);
      const isTimeout = err.name === 'AbortError';
      applyTestResult({
        status_code: 0,
        status_type: 'offline',
        status_title: isTimeout ? 'Check Timed Out' : 'Connection Failed',
        message: isTimeout
          ? 'Diagnostic request timed out after 25s. Gateway may be busy or unreachable.'
          : 'Could not connect to local server or AgentRouter gateway: ' + (err.message || ''),
        latency_ms: 0,
        is_active: false,
        is_quota_exhausted: false,
        model_id: selectedModel
      });
    } finally {
      state.isTesting = false;
      if (el.btnTestConnection) el.btnTestConnection.disabled = false;
      el.spinnerIcon.classList.remove('spinning');
      el.testBtnText.textContent = 'Test Connection';
    }
  }

  function applyTestResult(data) {
    const card = el.statusCard;
    card.className = 'status-card'; // reset

    // Remove status classes
    const statusType = data.status_type || 'offline';
    card.classList.add(`status-${statusType}`);

    // Title & Message
    el.badgeTitle.textContent = data.status_title || 'UNKNOWN';
    el.statusMessage.textContent = data.message || '';

    // Latency
    const latency = data.latency_ms || 0;
    el.latencyText.textContent = `${latency} ms`;
    el.compactLatency.textContent = `${latency} ms`;

    // Semantic status styling:
    // Lime (#B8FF3D) = Available
    // Amber (#FFB84D) = Scheduled / waiting
    // Red (#FF4D4D) = Exhausted / error
    // Gray (#666666) = Offline / unknown
    if (data.is_active) {
      el.headerPulseDot.style.backgroundColor = 'var(--status-available)';
      el.headerPulseDot.style.boxShadow = '0 0 10px var(--status-available-glow)';
      el.compactStatusDot.style.backgroundColor = 'var(--status-available)';
      el.compactStatusText.textContent = 'AVAILABLE (200)';
      el.compactStatusText.style.color = 'var(--status-available)';
      if (el.statusActionRow) el.statusActionRow.style.display = 'none';
    } else if (data.is_quota_exhausted || data.status_code === 402) {
      el.headerPulseDot.style.backgroundColor = 'var(--status-exhausted)';
      el.headerPulseDot.style.boxShadow = '0 0 10px var(--status-exhausted-glow)';
      el.compactStatusDot.style.backgroundColor = 'var(--status-exhausted)';
      el.compactStatusText.textContent = '402 QUOTA EMPTY';
      el.compactStatusText.style.color = 'var(--status-exhausted)';
      if (el.statusActionRow) el.statusActionRow.style.display = 'flex';
    } else if (statusType === 'unavailable') {
      el.headerPulseDot.style.backgroundColor = 'var(--status-exhausted)';
      el.headerPulseDot.style.boxShadow = 'none';
      el.compactStatusDot.style.backgroundColor = 'var(--status-exhausted)';
      el.compactStatusText.textContent = 'TEMPORARILY UNAVAILABLE';
      el.compactStatusText.style.color = 'var(--status-exhausted)';
      if (el.statusActionRow) el.statusActionRow.style.display = 'flex';
    } else if (statusType === 'no_channel' || data.status_code === 503) {
      el.headerPulseDot.style.backgroundColor = 'var(--status-scheduled)';
      el.headerPulseDot.style.boxShadow = '0 0 10px var(--status-scheduled-glow)';
      el.compactStatusDot.style.backgroundColor = 'var(--status-scheduled)';
      el.compactStatusText.textContent = '503 NO CHANNEL';
      el.compactStatusText.style.color = 'var(--status-scheduled)';
      if (el.statusActionRow) el.statusActionRow.style.display = 'flex';
    } else if (statusType === 'unauthorized' || data.status_code === 401) {
      el.headerPulseDot.style.backgroundColor = 'var(--status-exhausted)';
      el.headerPulseDot.style.boxShadow = '0 0 10px var(--status-exhausted-glow)';
      el.compactStatusDot.style.backgroundColor = 'var(--status-exhausted)';
      el.compactStatusText.textContent = '401 UNAUTHORIZED';
      el.compactStatusText.style.color = 'var(--status-exhausted)';
      if (el.statusActionRow) el.statusActionRow.style.display = 'none';
    } else if (statusType === 'no_key') {
      el.headerPulseDot.style.backgroundColor = 'var(--status-scheduled)';
      el.headerPulseDot.style.boxShadow = '0 0 10px var(--status-scheduled-glow)';
      el.compactStatusDot.style.backgroundColor = 'var(--status-scheduled)';
      el.compactStatusText.textContent = 'KEY REQUIRED';
      el.compactStatusText.style.color = 'var(--status-scheduled)';
      if (el.statusActionRow) el.statusActionRow.style.display = 'none';
    } else if (data.status_code && data.status_code > 0) {
      el.headerPulseDot.style.backgroundColor = 'var(--status-exhausted)';
      el.headerPulseDot.style.boxShadow = '0 0 10px var(--status-exhausted-glow)';
      el.compactStatusDot.style.backgroundColor = 'var(--status-exhausted)';
      el.compactStatusText.textContent = `HTTP ${data.status_code}`;
      el.compactStatusText.style.color = 'var(--status-exhausted)';
      if (el.statusActionRow) el.statusActionRow.style.display = 'none';
    } else {
      el.headerPulseDot.style.backgroundColor = 'var(--status-offline)';
      el.headerPulseDot.style.boxShadow = 'none';
      el.compactStatusDot.style.backgroundColor = 'var(--status-offline)';
      el.compactStatusText.textContent = 'OFFLINE';
      el.compactStatusText.style.color = 'var(--text-secondary)';
      if (el.statusActionRow) el.statusActionRow.style.display = 'none';
    }

    updateFallbackButton();
    // Refresh model list status badge
    updateModelInOverview(data.model_id, statusType, latency);
  }

  // --- Model Overview & Selection ---
  function canonicalModelKey(id) {
    return String(id || '').toLowerCase().replace(/[^a-z0-9]/g, '');
  }

  function modelSelectable(model) {
    return model.provider_status !== 'unavailable' && model.available_in_account !== false;
  }

  async function refreshProviderData() {
    if (state.isSyncing) return;
    state.isSyncing = true;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);
    try {
      const params = new URLSearchParams({ model: state.selectedModel || '', offset: String(state.userOffsetMinutes) });
      const res = await fetch(`/api/provider?${params}`, { signal: controller.signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (data.base_url.replace(/\/$/, '') !== state.baseUrl.replace(/\/$/, '')) return;
      await applyProviderData(data);
    } catch (error) {
      if (el.providerSyncStatus) {
        el.providerSyncStatus.textContent = 'Provider sync unavailable · keeping cached data and retrying automatically';
        el.providerSyncStatus.classList.add('stale');
      }
    } finally {
      clearTimeout(timeoutId);
      state.isSyncing = false;
    }
  }

  async function applyProviderData(data) {
    state.provider = data;
    state.models = data.models || [];
    const previous = state.selectedModel;
    const current = state.models.find(m => canonicalModelKey(m.id) === canonicalModelKey(previous));
    const eligible = state.models.filter(modelSelectable);
    if (current && modelSelectable(current)) {
      state.selectedModel = current.id;
    } else if (current || !data.models_stale) {
      const preferred = eligible.find(m => m.id === data.recommended_model) || eligible[0];
      state.selectedModel = preferred ? preferred.id : '';
    }
    renderModelSelectOptions();
    renderModelsOverview();
    renderHelpModels();
    updateFallbackButton();
    renderProviderNotice(data);
    renderUsage(data.usage);
    const scheduleMatches = data.schedule && canonicalModelKey(data.schedule.model_id) === canonicalModelKey(state.selectedModel);
    if (scheduleMatches) updateScheduleData(data.schedule);
    else computeLocalSchedule();
    if (state.selectedModel && previous !== state.selectedModel) {
      await saveConfigToServer({ selected_model: state.selectedModel });
      el.badgeTitle.textContent = 'MODEL UPDATED';
      el.statusMessage.textContent = `${previous || 'The saved model'} is unavailable. Selected ${state.selectedModel} from the current catalog.`;
    }
    if (!scheduleMatches) await refreshSchedule();
  }

  async function refreshSchedule() {
    try {
      const params = new URLSearchParams({ model: state.selectedModel || '', offset: String(state.userOffsetMinutes) });
      const res = await fetch(`/api/schedule?${params}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      updateScheduleData(await res.json());
    } catch (error) {
      computeLocalSchedule();
    }
  }

  function renderProviderNotice(data) {
    const notices = data.announcements || [];
    const latest = notices[0];
    const noticeText = latest ? latest.content : 'No current announcements from AgentRouter.';
    if (el.officialNoticeText) el.officialNoticeText.textContent = noticeText;
    if (el.helpOfficialNoticeText) el.helpOfficialNoticeText.textContent = noticeText;
    if (el.officialNoticeDate) el.officialNoticeDate.textContent = latest?.published_at ? `Published ${new Date(latest.published_at).toLocaleString()}` : 'No publication date supplied';
    if (el.noticeHistory) {
      el.noticeHistory.replaceChildren();
      notices.slice(1, 6).forEach(notice => {
        const details = document.createElement('details');
        const summary = document.createElement('summary');
        summary.textContent = `Earlier announcement · ${notice.published_at ? new Date(notice.published_at).toLocaleDateString() : 'Undated'}`;
        const body = document.createElement('pre');
        body.className = 'official-notice-text';
        body.textContent = notice.content;
        details.append(summary, body);
        el.noticeHistory.appendChild(details);
      });
    }
    if (el.providerSyncStatus) {
      const stale = data.models_stale || data.notices_stale || data.pricing_stale;
      el.providerSyncStatus.classList.toggle('stale', stale);
      const synced = Math.max(data.models_updated_at || 0, data.notices_updated_at || 0);
      const prefix = data.refreshing ? 'Syncing models & notices…' : data.notice_source === 'bundled' ? 'Built-in notice · waiting for live sync' : stale ? 'Cached data · retrying automatically' : `Synced ${new Date(synced * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
      el.providerSyncStatus.textContent = `${prefix} · automatic sync every 5m`;
    }
  }

  function modelLabel(model) {
    let label = model.status_type === 'active' ? `Available (${model.latency_ms || 0}ms)` : model.tag || 'Supply policy unknown';
    const statuses = { unavailable: 'Temporarily unavailable', quota_exhausted: '402 Quota empty', unauthorized: '401 Error', no_channel: '503 No channel', offline: 'Offline' };
    if (statuses[model.status_type]) label = statuses[model.status_type];
    if (typeof model.multiplier === 'number') label += ` · ${model.multiplier}× base`;
    if (model.recommended) label += ' · Recommended';
    return label;
  }

  function renderUsage(usage) {
    if (!usage || !el.modelUsageList) return;
    const number = value => Number(value).toLocaleString(undefined, { maximumFractionDigits: 4 });
    if (el.usedCredits) el.usedCredits.textContent = usage.used_credit == null ? 'Not reported' : number(usage.used_credit);
    if (el.remainingKeyCredit) el.remainingKeyCredit.textContent = usage.unlimited_key_cap ? 'Uncapped key' : usage.remaining_key_credit == null ? 'Not reported' : number(usage.remaining_key_credit);
    if (el.usageStatus) {
      const updated = usage.updated_at ? ` · ${new Date(usage.updated_at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : '';
      el.usageStatus.textContent = `${usage.stale ? 'Cached / incomplete usage' : 'Reported API-key usage'}${updated}. ${usage.message || ''}`;
      el.usageStatus.classList.toggle('stale', usage.stale);
    }
    el.modelUsageList.replaceChildren();
    state.models.forEach(model => {
      const entry = Object.entries(usage.per_model || {}).find(([id]) => canonicalModelKey(id) === canonicalModelKey(model.id));
      const metrics = entry ? entry[1] : null;
      const row = document.createElement('div');
      row.className = 'model-usage-row';
      const name = document.createElement('strong');
      name.textContent = model.name;
      const details = document.createElement('p');
      details.textContent = metrics ? `Recent logged tokens: ${number(metrics.total_tokens)} (${number(metrics.prompt_tokens)} input / ${number(metrics.completion_tokens)} output) · ${number(metrics.requests)} requests` : 'Tokens used: not reported by AgentRouter';
      const remaining = document.createElement('p');
      remaining.textContent = 'Remaining model tokens / pool credit: not reported';
      row.append(name, details, remaining);
      el.modelUsageList.appendChild(row);
    });
  }

  function renderModelSelectOptions() {
    const sel = el.modelSelect;
    sel.replaceChildren();
    const groups = [
      ['Unlimited · all day', m => modelSelectable(m) && m.quota_limited === false],
      ['Limited supply', m => modelSelectable(m) && m.quota_limited === true],
      ['Other models · policy unknown', m => modelSelectable(m) && m.quota_limited == null],
      ['Temporarily unavailable', m => !modelSelectable(m)]
    ];
    groups.forEach(([label, predicate]) => {
      const models = state.models.filter(predicate);
      if (!models.length) return;
      const group = document.createElement('optgroup');
      group.label = label;
      models.forEach(model => {
        const option = document.createElement('option');
        option.value = model.id;
        option.textContent = `${model.name} [${modelLabel(model)}]`;
        option.disabled = !modelSelectable(model);
        group.appendChild(option);
      });
      sel.appendChild(group);
    });
    if (state.selectedModel && !state.models.some(m => m.id === state.selectedModel) && state.provider?.models_stale) {
      const saved = document.createElement('option');
      saved.value = state.selectedModel;
      saved.textContent = `${state.selectedModel} [Saved model · awaiting sync]`;
      sel.appendChild(saved);
    }
    sel.value = state.selectedModel || '';
  }

  function renderModelsOverview() {
    const list = el.modelsOverviewList;
    list.replaceChildren();
    el.modelsCount.textContent = `${state.models.length} models`;
    let filtered = state.models;
    if (state.activeModelFilter === 'active') filtered = filtered.filter(m => m.status_type === 'active' && modelSelectable(m));
    if (state.activeModelFilter === 'uninterrupted') filtered = filtered.filter(m => m.quota_limited === false && modelSelectable(m));
    if (state.activeModelFilter === 'quota') filtered = filtered.filter(m => m.quota_limited === true && modelSelectable(m));
    if (!filtered.length) {
      const empty = document.createElement('div');
      empty.className = 'overview-loading';
      empty.textContent = 'No models match this filter';
      list.appendChild(empty);
    }
    filtered.forEach(model => {
      const row = document.createElement('div');
      row.className = 'model-row-item';
      row.title = model.id;
      row.setAttribute('aria-disabled', String(!modelSelectable(model)));
      const name = document.createElement('span');
      name.className = 'model-row-name';
      name.textContent = model.name;
      name.title = model.id;
      const badge = document.createElement('span');
      const error = !modelSelectable(model) || (model.status_code && model.status_code >= 400);
      badge.className = `model-row-badge ${error ? 'badge-model-exhausted' : model.status_type === 'active' ? 'badge-model-active' : model.quota_limited === true ? 'badge-model-scheduled' : 'badge-model-unchecked'}`;
      badge.textContent = modelLabel(model);
      row.append(name, badge);
      row.addEventListener('click', () => {
        if (!modelSelectable(model)) return;
        el.modelSelect.value = model.id;
        onModelSelected();
      });
      list.appendChild(row);
    });
  }

  function renderHelpModels() {
    if (!el.helpModelsList) return;
    el.helpModelsList.replaceChildren();
    state.models.forEach(model => {
      const card = document.createElement('div');
      card.className = 'help-model-type-card';
      const name = document.createElement('strong');
      name.textContent = model.name;
      const policy = document.createElement('p');
      policy.textContent = modelLabel(model);
      card.append(name, policy);
      el.helpModelsList.appendChild(card);
    });
  }

  function updateFallbackButton() {
    if (!el.btnSwitchRecommended) return;
    const eligible = state.models.filter(m => modelSelectable(m) && m.id !== state.selectedModel);
    const target = eligible.find(m => m.id === state.provider?.recommended_model) || eligible.find(m => m.quota_limited === false) || eligible[0];
    el.btnSwitchRecommended.dataset.modelId = target ? target.id : '';
    el.btnSwitchRecommended.textContent = target ? `Switch to ${target.name}` : 'No alternate model available';
    el.btnSwitchRecommended.disabled = !target;
  }

  function startProviderRefresh() {
    if (providerRefreshTimer) clearInterval(providerRefreshTimer);
    providerRefreshTimer = setInterval(refreshProviderData, 15000);
    window.addEventListener('focus', refreshProviderData);
  }

  function updateModelInOverview(modelId, statusType, latency) {
    const m = state.models.find(x => x.id === modelId);
    if (m) {
      m.status_type = statusType;
      m.latency_ms = latency;
      renderModelSelectOptions();
      renderModelsOverview();
    }
  }

  async function onModelSelected() {
    const modelId = el.modelSelect.value;
    state.selectedModel = modelId;
    saveConfigToServer({ selected_model: modelId });
    await refreshSchedule();
    await testConnection(true);
  }

  async function testAllModels() {
    if (state.isTesting) return;
    el.btnTestAllModels.textContent = '...';
    el.btnTestAllModels.disabled = true;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 12000);
    try {
      const res = await fetch('/api/models/test-all', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({})
      });
      clearTimeout(timeoutId);
      const data = await res.json();
      if (data.models) {
        state.models = data.models;
        renderModelSelectOptions();
        renderModelsOverview();
      }
    } catch (e) {
      clearTimeout(timeoutId);
      console.error('Test all error:', e);
    } finally {
      el.btnTestAllModels.textContent = 'Test All';
      el.btnTestAllModels.disabled = false;
    }
  }

  async function discoverModels() {
    if (state.isDiscovering) return;
    state.isDiscovering = true;
    el.btnDiscoverModels.textContent = 'Syncing…';
    el.btnDiscoverModels.disabled = true;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 25000);
    try {
      const res = await fetch('/api/models/discover', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify({ base_url: state.baseUrl })
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (data.provider) await applyProviderData({ ...data.provider, models: data.models });
    } catch (error) {
      if (el.providerSyncStatus) {
        el.providerSyncStatus.textContent = 'Sync failed · keeping cached data and retrying automatically';
        el.providerSyncStatus.classList.add('stale');
      }
    } finally {
      clearTimeout(timeoutId);
      state.isDiscovering = false;
      el.btnDiscoverModels.textContent = 'Sync Now';
      el.btnDiscoverModels.disabled = false;
    }
  }

  // --- Auto Refresh Loop ---
  function startAutoRefresh() {
    if (autoRefreshTimer) clearInterval(autoRefreshTimer);
    if (!state.autoRefresh) return;

    autoRefreshTimer = setInterval(() => {
      testConnection(false);
    }, state.refreshInterval * 1000);
  }

  function restartAutoRefresh() {
    startAutoRefresh();
  }

  function startElapsedTimer() {
    if (elapsedTimer) clearInterval(elapsedTimer);
    elapsedTimer = setInterval(updateLastCheckedDisplay, 5000);
  }

  function updateLastCheckedDisplay() {
    if (!state.lastCheckedTimestamp) {
      el.lastCheckedTime.textContent = 'Never';
      return;
    }
    const elapsedSec = Math.floor((Date.now() - state.lastCheckedTimestamp) / 1000);
    if (elapsedSec < 10) {
      el.lastCheckedTime.textContent = 'Just now';
    } else if (elapsedSec < 60) {
      el.lastCheckedTime.textContent = `${elapsedSec}s ago`;
    } else {
      el.lastCheckedTime.textContent = `${Math.floor(elapsedSec / 60)}m ago`;
    }
  }

  // --- Window Controls (PyWebview Bridge) ---
  function toggleCompactMode() {
    state.isCompact = !state.isCompact;
    el.container.classList.toggle('compact-mode', state.isCompact);
    el.btnCompact.classList.toggle('active', state.isCompact);

    // Call pywebview python bridge if running as native desktop window
    if (window.pywebview && window.pywebview.api && window.pywebview.api.resize_window) {
      if (state.isCompact) {
        window.pywebview.api.resize_window(390, 100);
      } else {
        window.pywebview.api.resize_window(410, 720);
      }
    }
  }

  function toggleAlwaysOnTop() {
    state.isPinned = !state.isPinned;
    if (el.btnPin) el.btnPin.classList.toggle('active', state.isPinned);
    if (el.settingAlwaysOnTop) el.settingAlwaysOnTop.checked = state.isPinned;
    saveConfigToServer({ always_on_top: state.isPinned });

    if (window.pywebview && window.pywebview.api && window.pywebview.api.toggle_always_on_top) {
      window.pywebview.api.toggle_always_on_top(state.isPinned);
    }
  }

  function closeWindow() {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.close_window) {
      window.pywebview.api.close_window();
    } else {
      // Browser preview: minimize or hide
      el.container.style.opacity = '0.5';
    }
  }

  function minimizeWindow() {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.minimize_window) {
      window.pywebview.api.minimize_window();
    }
  }

  // --- Help Modal ---
  function openHelpModal() {
    if (el.helpModal) el.helpModal.style.display = 'flex';
  }

  function closeHelpModal() {
    if (el.helpModal) el.helpModal.style.display = 'none';
  }

  function setupHelpTabs() {
    const tabButtons = document.querySelectorAll('.help-tab-btn');
    const tabContents = document.querySelectorAll('.help-tab-content');
    tabButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        tabButtons.forEach(b => b.classList.remove('active'));
        tabContents.forEach(c => c.style.display = 'none');
        btn.classList.add('active');
        const targetId = btn.getAttribute('data-tab');
        const target = document.getElementById(targetId);
        if (target) {
          target.style.display = 'block';
        }
      });
    });
  }

  function setupModelFilterChips() {
    const chips = document.querySelectorAll('#modelsFilterBar .filter-chip');
    chips.forEach(chip => {
      chip.addEventListener('click', () => {
        chips.forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        state.activeModelFilter = chip.getAttribute('data-filter') || 'all';
        renderModelsOverview();
      });
    });
  }

  function setupKeyboardShortcuts() {
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        if (el.helpModal && el.helpModal.style.display === 'flex') {
          closeHelpModal();
        } else if (el.settingsModal && el.settingsModal.style.display === 'flex') {
          closeSettingsModal();
        } else if (el.keyDrawer && el.keyDrawer.style.display === 'block') {
          el.keyDrawer.style.display = 'none';
        }
      } else if ((e.key === 'r' || e.key === 'R') && !['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
        testConnection(true);
      }
    });
  }

  function setupExternalLinks() {
    document.addEventListener('click', (e) => {
      const link = e.target.closest('a[target="_blank"]');
      if (link && link.href) {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.open_external_url) {
          e.preventDefault();
          window.pywebview.api.open_external_url(link.href);
        }
      }
    });
  }

  function setupAudioUnlocking() {
    const unlock = () => {
      getAudioContext();
      document.removeEventListener('pointerdown', unlock);
      document.removeEventListener('keydown', unlock);
    };
    document.addEventListener('pointerdown', unlock);
    document.addEventListener('keydown', unlock);
  }

  // --- Smooth Scrolling & Interaction Controller ---
  function setupScrollHandling() {
    const main = el.mainContent || document.getElementById('mainContent');
    if (!main) return;

    // Direct wheel scrolling listener (guarantees mouse wheel scrolls main container smoothly)
    window.addEventListener('wheel', (e) => {
      // If mouse is over an inner scrollable element with its own active overflow
      const innerScrollable = (e.target && typeof e.target.closest === 'function')
        ? e.target.closest('.models-overview-content, .help-body, .modal-body')
        : null;
      if (innerScrollable && innerScrollable.scrollHeight > innerScrollable.clientHeight) {
        const atTop = innerScrollable.scrollTop <= 0 && e.deltaY < 0;
        const atBottom = (innerScrollable.scrollTop + innerScrollable.clientHeight >= innerScrollable.scrollHeight - 1) && e.deltaY > 0;
        if (!atTop && !atBottom) {
          return;
        }
      }

      if (main.scrollHeight > main.clientHeight) {
        main.scrollTop += e.deltaY;
      }
    }, { passive: true });

    // Auto-scroll into view when accordions open
    const modelsOverview = document.getElementById('modelsOverview');
    if (modelsOverview) {
      modelsOverview.addEventListener('toggle', () => {
        if (modelsOverview.open) {
          setTimeout(() => {
            modelsOverview.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          }, 60);
        }
      });
    }

    const noticeDetails = document.querySelector('.notice-details');
    if (noticeDetails) {
      noticeDetails.addEventListener('toggle', () => {
        if (noticeDetails.open) {
          setTimeout(() => {
            noticeDetails.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          }, 60);
        }
      });
    }

    // Keyboard navigation scrolling
    window.addEventListener('keydown', (e) => {
      if (['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;
      if (e.key === 'ArrowDown') {
        main.scrollTop += 45;
        e.preventDefault();
      } else if (e.key === 'ArrowUp') {
        main.scrollTop -= 45;
        e.preventDefault();
      } else if (e.key === 'PageDown' || (e.key === ' ' && !e.shiftKey)) {
        main.scrollTop += 220;
        e.preventDefault();
      } else if (e.key === 'PageUp' || (e.key === ' ' && e.shiftKey)) {
        main.scrollTop -= 220;
        e.preventDefault();
      } else if (e.key === 'Home') {
        main.scrollTop = 0;
        e.preventDefault();
      } else if (e.key === 'End') {
        main.scrollTop = main.scrollHeight;
        e.preventDefault();
      }
    });

    // Touchpad and touch drag scrolling
    let touchStartY = 0;
    let touchStartScrollTop = 0;
    main.addEventListener('touchstart', (e) => {
      if (e.touches.length === 1) {
        touchStartY = e.touches[0].clientY;
        touchStartScrollTop = main.scrollTop;
      }
    }, { passive: true });

    main.addEventListener('touchmove', (e) => {
      if (e.touches.length === 1) {
        const deltaY = touchStartY - e.touches[0].clientY;
        main.scrollTop = touchStartScrollTop + deltaY;
      }
    }, { passive: true });
  }

  // --- Settings Modal ---
  function openSettingsModal() {
    el.settingsModal.style.display = 'flex';
    el.settingBaseUrl.value = state.baseUrl;
    el.settingAlwaysOnTop.checked = state.isPinned;
    el.settingChime.checked = state.soundEnabled;
    if (el.settingTimezone) {
      el.settingTimezone.value = String(state.userOffsetMinutes);
    }
    if (el.settingApiKey) {
      el.settingApiKey.value = '';
      el.settingApiKey.placeholder = state.hasApiKey ? (state.maskedApiKey || 'Key configured') : 'Enter API Key (sk-...)';
    }

    // Load scheduler status
    fetch('/api/scheduler/status')
      .then(r => r.json())
      .then(data => {
        if (el.settingSchedulerEnabled && data.enabled !== undefined) {
          el.settingSchedulerEnabled.checked = data.enabled;
        }
        if (el.settingPressEnter && data.press_enter !== undefined) {
          el.settingPressEnter.checked = data.press_enter;
        }
        if (el.settingGeminiKey && data.has_gemini_key) {
          el.settingGeminiKey.placeholder = 'Gemini 3.8 key configured (encrypted)';
        }
      })
      .catch(console.warn);
  }

  function closeSettingsModal() {
    el.settingsModal.style.display = 'none';
  }

  function onTimezoneSettingChange(e) {
    const val = e.target.value;
    if (val === 'auto') {
      state.userOffsetMinutes = -new Date().getTimezoneOffset();
    } else {
      state.userOffsetMinutes = parseInt(val, 10);
    }
    saveConfigToServer({ user_timezone_offset: state.userOffsetMinutes }).then(refreshSchedule);
  }

  async function saveConfigToServer(updates) {
    try {
      await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
      });
    } catch (e) {
      console.warn('Error saving config:', e);
    }
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
