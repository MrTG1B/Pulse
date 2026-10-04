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
    selectedModel: 'deepseek-v4-flash',
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
    models: []
  };

  let autoRefreshTimer = null;
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
    btnSwitchDeepSeek: document.getElementById('btnSwitchDeepSeek'),

    // Countdown Card
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
    if (el.btnSwitchDeepSeek) {
      el.btnSwitchDeepSeek.addEventListener('click', () => {
        const targetId = 'deepseek-v4-flash';
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
        saveConfigToServer({ base_url: state.baseUrl });
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
    try {
      // 1. Fetch initial status & schedule with timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 6000);
      const res = await fetch('/api/status', { signal: controller.signal });
      clearTimeout(timeoutId);
      const data = await res.json();

      if (data.config) {
        state.hasApiKey = data.config.has_api_key;
        state.maskedApiKey = data.config.masked_api_key || '';
        state.selectedModel = data.config.selected_model || state.selectedModel;
        state.refreshInterval = data.config.refresh_interval_sec || 30;
        state.autoRefresh = data.config.auto_refresh_enabled !== false;
        state.isPinned = data.config.always_on_top !== false;
        state.baseUrl = data.config.base_url || 'https://agentrouter.org';

        el.chkAutoRefresh.checked = state.autoRefresh;
        el.selInterval.value = String(state.refreshInterval);
        el.btnPin.classList.toggle('active', state.isPinned);
        updateKeyDisplay();
      }

      // Verify masked API key metadata
      if (state.hasApiKey) {
        try {
          const kr = await fetch('/api/config/key');
          const kd = await kr.json();
          if (kd.masked_api_key) state.maskedApiKey = kd.masked_api_key;
        } catch (e) {}
      }

      if (data.schedule) {
        updateScheduleData(data.schedule);
      }

      // 2. Fetch models & discover user's active channel models
      await fetchModels();
      if (state.hasApiKey) {
        try {
          await discoverModels();
        } catch (e) {}
      }

      // If default model is claude-3-5-sonnet-20241022 (no channel) but deepseek-v4-flash is discovered, use it
      if (state.models.some(m => m.id === 'deepseek-v4-flash') && (!state.selectedModel || state.selectedModel === 'claude-3-5-sonnet-20241022')) {
        state.selectedModel = 'deepseek-v4-flash';
        el.modelSelect.value = 'deepseek-v4-flash';
      }

      // 3. Run initial test
      await testConnection(false);

    } catch (err) {
      console.warn('Initial load error:', err);
      // Fallback local schedule computation
      computeLocalSchedule();
      await fetchModels();
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
      state.maskedApiKey = data.masked_api_key;
      state.apiKey = '';

      updateKeyDisplay();
      el.keyDrawer.style.display = 'none';
      el.inputApiKey.value = '';
      if (el.settingApiKey) el.settingApiKey.value = '';

      // Test connection immediately with new key
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
    state.nextSlotUtc = new Date(schedule.next_slot_utc);
    state.prevSlotUtc = new Date(schedule.prev_slot_utc);
    if (schedule.user_offset_minutes !== undefined) {
      state.userOffsetMinutes = schedule.user_offset_minutes;
    }

    if (el.batchPill && schedule.batch_number) {
      el.batchPill.textContent = `Batch ${schedule.batch_number}`;
    }
    if (el.localTimeDisplay && schedule.local_display) {
      el.localTimeDisplay.textContent = schedule.local_display;
    }
    if (el.beijingRefTime && schedule.daily_schedule_beijing) {
      el.beijingRefTime.textContent = `Beijing: ${schedule.daily_schedule_beijing}`;
    }
    if (el.utcRefTime && schedule.daily_schedule_utc) {
      el.utcRefTime.textContent = schedule.daily_schedule_utc;
    }
    if (el.dailyScheduleTimes && schedule.daily_schedule_local) {
      el.dailyScheduleTimes.textContent = schedule.daily_schedule_local;
    }

    if (el.compactLocalTime && schedule.local_time) {
      const tz = schedule.user_timezone || 'IST';
      el.compactLocalTime.textContent = `(${schedule.local_time} ${tz})`;
    }

    tickCountdown();
  }

  function computeLocalSchedule() {
    // Pure frontend calculation fallback
    const now = new Date();
    const candidateHoursUtc = [2, 11];
    let candidates = [];

    for (let dayOffset of [-1, 0, 1, 2]) {
      for (let h of candidateHoursUtc) {
        const d = new Date(Date.UTC(
          now.getUTCFullYear(),
          now.getUTCMonth(),
          now.getUTCDate() + dayOffset,
          h, 0, 0
        ));
        candidates.push(d);
      }
    }
    candidates.sort((a, b) => a - b);

    const nextSlot = candidates.find(c => c > now) || new Date(now.getTime() + 4 * 3600 * 1000);
    const pastSlots = candidates.filter(c => c <= now);
    const prevSlot = pastSlots[pastSlots.length - 1] || new Date(nextSlot.getTime() - 9 * 3600 * 1000);

    state.nextSlotUtc = nextSlot;
    state.prevSlotUtc = prevSlot;

    if (el.batchPill) {
      const isMorning = nextSlot.getUTCHours() === 2;
      el.batchPill.textContent = isMorning ? 'Batch 1' : 'Batch 2';
    }
    if (el.beijingRefTime) el.beijingRefTime.textContent = 'Beijing: 10:00 & 19:00 (Beijing Time / UTC+8)';
    if (el.utcRefTime) el.utcRefTime.textContent = '02:00 & 11:00 UTC';
    if (el.dailyScheduleTimes) el.dailyScheduleTimes.textContent = '07:30 AM & 04:30 PM (IST)';

    // Format local time for user's timezone (UTC+05:30)
    formatLocalTimeDisplay(nextSlot);
    tickCountdown();
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
    if (!state.nextSlotUtc) return;

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
          loadInitialData();
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
    state.isTesting = true;

    el.spinnerIcon.classList.add('spinning');
    el.testBtnText.textContent = 'Checking...';
    if (el.btnTestConnection) el.btnTestConnection.disabled = true;

    const selectedModel = el.modelSelect.value || state.selectedModel;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 8000);

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
          ? 'Diagnostic request timed out after 8s. Gateway may be busy or unreachable.'
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

    // Refresh model list status badge
    updateModelInOverview(data.model_id, statusType, latency);
  }

  // --- Model Overview & Selection ---
  async function fetchModels() {
    try {
      const res = await fetch('/api/models');
      const data = await res.json();
      state.models = data.models || [];
      renderModelSelectOptions();
      renderModelsOverview();
    } catch (e) {
      console.warn('Failed to load models:', e);
    }
  }

  function renderModelSelectOptions() {
    const sel = el.modelSelect;
    const currentVal = sel.value || state.selectedModel;
    sel.innerHTML = '';

    const uninterrupted = state.models.filter(m => !m.quota_limited);
    const quotaLimited = state.models.filter(m => m.quota_limited && !m.discovered);
    const discovered = state.models.filter(m => m.discovered);

    function createOpt(m) {
      const opt = document.createElement('option');
      opt.value = m.id;
      let statusPrefix = '';
      let statusSuffix = '';

      if (m.status_type === 'active') {
        statusPrefix = '🟢 ';
        statusSuffix = m.latency_ms ? ` [Active · ${m.latency_ms}ms]` : ' [Active]';
      } else if (m.status_type === 'quota_exhausted') {
        statusPrefix = '🔴 ';
        statusSuffix = ' [402 Quota Empty]';
      } else if (m.status_type === 'unauthorized') {
        statusPrefix = '🔴 ';
        statusSuffix = ' [401 Error]';
      } else if (m.status_type === 'no_channel') {
        statusPrefix = '🔴 ';
        statusSuffix = ' [503 No Channel]';
      } else if (m.status_type === 'offline') {
        statusPrefix = '⚪ ';
        statusSuffix = ' [Offline]';
      } else if (!m.quota_limited) {
        statusPrefix = '⚡ ';
        statusSuffix = ' [Always Active]';
      } else {
        statusPrefix = '⏱️ ';
        statusSuffix = ' [Quota Pool]';
      }

      opt.textContent = `${statusPrefix}${m.name}${statusSuffix}`;
      return opt;
    }

    if (uninterrupted.length > 0) {
      const grp = document.createElement('optgroup');
      grp.label = '⚡ Uninterrupted Models (Always Active - No Quota Lock)';
      uninterrupted.forEach(m => grp.appendChild(createOpt(m)));
      sel.appendChild(grp);
    }

    if (quotaLimited.length > 0) {
      const grp = document.createElement('optgroup');
      grp.label = '⏱️ Claude & GPT Quota Pool (10:00 & 19:00 Releases)';
      quotaLimited.forEach(m => grp.appendChild(createOpt(m)));
      sel.appendChild(grp);
    }

    if (discovered.length > 0) {
      const grp = document.createElement('optgroup');
      grp.label = '🔍 Discovered from AgentRouter';
      discovered.forEach(m => grp.appendChild(createOpt(m)));
      sel.appendChild(grp);
    }

    // Restore selected value if present, otherwise default
    if ([...sel.options].some(o => o.value === currentVal)) {
      sel.value = currentVal;
    } else if (sel.options.length > 0) {
      sel.value = sel.options[0].value;
      state.selectedModel = sel.value;
    }
  }

  function renderModelsOverview() {
    const list = el.modelsOverviewList;
    list.innerHTML = '';

    if (!state.models || state.models.length === 0) {
      list.innerHTML = '<div class="overview-loading">No models catalog available</div>';
      return;
    }

    el.modelsCount.textContent = `${state.models.length} models`;

    let filtered = state.models;
    if (state.activeModelFilter === 'active') {
      filtered = state.models.filter(m => m.status_type === 'active');
    } else if (state.activeModelFilter === 'uninterrupted') {
      filtered = state.models.filter(m => !m.quota_limited);
    } else if (state.activeModelFilter === 'quota') {
      filtered = state.models.filter(m => m.quota_limited);
    }

    if (filtered.length === 0) {
      list.innerHTML = `<div class="overview-loading">No models matching '${state.activeModelFilter}'</div>`;
      return;
    }

    filtered.forEach(m => {
      const row = document.createElement('div');
      row.className = 'model-row-item';
      row.style.cursor = 'pointer';
      row.title = `Click to test ${m.name} (${m.id})`;

      const isAvailable = m.status_type === 'active';
      const isExhaustedOrError = m.status_type === 'quota_exhausted' || m.status_type === 'unauthorized' || m.status_type === 'no_channel' || (m.status_code && m.status_code >= 400);

      // Semantic status class: Available (Lime), Quota Pool Scheduled (Amber), Exhausted/Error (Red), Unchecked Uninterrupted (Active/Lime)
      const typeClass = isAvailable ? 'badge-model-active'
        : isExhaustedOrError ? 'badge-model-exhausted'
        : m.quota_limited ? 'badge-model-scheduled'
        : 'badge-model-active';

      let statusLabel = m.quota_limited ? '⏱️ Scheduled' : '⚡ Uninterrupted';
      if (m.status_type === 'active') {
        statusLabel = `Available (${m.latency_ms || 0}ms)`;
      } else if (m.status_type === 'quota_exhausted') {
        statusLabel = '402 Quota Empty';
      } else if (m.status_type === 'unauthorized') {
        statusLabel = '401 Error';
      } else if (m.status_type === 'no_channel') {
        statusLabel = '503 No Channel';
      } else if (m.status_type === 'offline') {
        statusLabel = 'Offline';
      }

      row.innerHTML = `
        <span class="model-row-name" title="${m.id}">${m.name}</span>
        <span class="model-row-badge ${typeClass}">${statusLabel}</span>
      `;

      row.addEventListener('click', () => {
        el.modelSelect.value = m.id;
        onModelSelected();
      });

      list.appendChild(row);
    });
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
    if (!el.btnDiscoverModels || state.isTesting) return;
    el.btnDiscoverModels.textContent = '...';
    el.btnDiscoverModels.disabled = true;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);
    try {
      const res = await fetch('/api/models/discover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({ base_url: state.baseUrl })
      });
      clearTimeout(timeoutId);
      const data = await res.json();
      if (data.models && data.models.length > 0) {
        state.models = data.models;
        renderModelSelectOptions();
        renderModelsOverview();
      }
      if (data.count > 0) {
        el.statusMessage.textContent = `Discovered ${data.count} models from AgentRouter.`;
      }
    } catch (e) {
      clearTimeout(timeoutId);
      console.warn('Discovery error:', e);
    } finally {
      el.btnDiscoverModels.textContent = 'Discover';
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
    fetch(`/api/schedule?offset=${state.userOffsetMinutes}`)
      .then(r => r.json())
      .then(updateScheduleData)
      .catch(console.error);
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
