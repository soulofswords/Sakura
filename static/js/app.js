import {installSpoutControls} from './spout-output.js?v=miu-expression-manager6';
import {installExpressionEditor} from './expression-editor.js?v=auto1-custom-expression5';
import {installModelSettings} from './model-settings.js?v=live2d-speed28';
import ModelViewer from './model-viewer.js?v=live2d-speed28';
import AvatarTracking from './avatar-tracking.js?v=distance6';
import {installBroadcastCamera} from './broadcast-camera.js?v=1';
import ChatReader from './chat-reader.js?v=lean1';
import LipSync from './lip-sync.js?v=reader-audio6';
import RvcVoiceChanger from './rvc-voice-changer.js?v=mouth-controls4';
import EyeTracking from './eye-tracking.js?v=vtuber-eyes1';
import ScreenShare from './screen-share.js?v=capture2';
import ContinuousMic from './continuous-mic.js';
import { speakPhrases } from './speech-pipeline.js';

const continuousMicBtn = document.getElementById('continuous-mic-btn');
const listeningStatus = document.getElementById('listening-status');
let lastMicActivity = Date.now();
const continuousMic = new ContinuousMic(blob => sendAudioForSTT(blob, { continuous: true }), status => {
    if (status !== 'Listening…') lastMicActivity = Date.now();
    listeningStatus.textContent = status;
    continuousMicBtn.setAttribute('aria-pressed', String(continuousMic.enabled));
    continuousMicBtn.textContent = continuousMic.enabled ? '🎤 Pause mic' : '🎤 Listen';
});
window.addEventListener('pagehide', () => continuousMic.stop());

async function startDesktopListening() {
    if (trackingOnly) return;
    if (gameActive && autoGameEnabled) return;
    try { await continuousMic.start(selectedMicId); }
    catch (err) {
        continuousMic.stop();
        listeningStatus.textContent = `Microphone: ${err.message}. Click Listen to retry.`;
    }
}

let chatReplyGeneration = 0;
let replyController = null;
let chatBusy = false;
let reactionsEnabled = false;
let autoGameEnabled = false;
let autoGameBusy = false;
let gameActive = false;
let gameReady = false;
let gameResumeMic = false;
let gameStartedScreen = false;
let gameForeground = false;
let lastGameSeen = 0;
let lastReactionText = '';
let vtuberEnabled = false;
let trackingOnly = false;
let avatarTracking;
let vtuberGeneration = 0;
let vtuberQueue = [];
let vtuberPollBusy = false;
let vtuberSpeaking = false;
let lastCoHostSpeech = 0;
let lastViewerReply = '';
window.addEventListener('pagehide', () => {
    avatarTracking?.stop();
    if (rvcVoiceChanger?.active) navigator.sendBeacon('/api/voice-changer/stop');
    rvcVoiceChanger?.stop();
    if (vtuberEnabled) navigator.sendBeacon('/api/vtuber/disconnect');
});
let reactionBusy = false;
const screenReactBtn = document.getElementById('screen-react-btn');
let viewer;
let lipSync;
let rvcVoiceChanger;
const screenViewBtn = document.getElementById('screen-view-btn');
const screenViewStatus = document.getElementById('screen-view-status');
const screenShare = new ScreenShare((enabled, starting) => {
    if (!enabled) {
        reactionsEnabled = false;
        screenReactBtn.textContent = '💬 Reactions off';
        screenReactBtn.setAttribute('aria-pressed', 'false');
    }
    screenViewBtn.textContent = enabled ? '🖥️ Screen on' : starting ? 'Cancel sharing' : '🖥️ Screen off';
    screenViewBtn.setAttribute('aria-pressed', String(enabled));
    screenViewStatus.classList.toggle('sharing', enabled);
    screenViewStatus.textContent = enabled ? `Screen on · Each message sends a snapshot to ${currentSettings.llm_provider === 'gemini' ? 'Google Gemini' : 'local Ollama'}`
        : starting ? 'Choose a screen or window in the browser picker' : 'Screen off · No snapshots sent';
});
window.addEventListener('pagehide', () => screenShare.stop());
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;

// Audio Device State
let selectedMicId = localStorage.getItem('sakura_mic_id') || '';
let selectedSpeakerId = localStorage.getItem('sakura_speaker_id') || '';
let micMonitorStream = null;
let micMonitorInterval = null;
let micMonitorContext = null;
let micMonitorGeneration = 0;

// Voice / Model state
let allVoicePresets = [];       // from /api/voices
let allRvcModels = [];          // from /api/voices (rvc_models)
let allPmxModels = [];          // from /api/models
let currentVoiceId = 'sakura_ava';
let voiceSaveQueue = Promise.resolve();
let voiceSelectionGeneration = 0;
let selectedPmxPath = '';
let glitchModelKey = '';

// DOM — Top Bar
const modelSelect      = document.getElementById('model-select');
const voiceQuickSelect = document.getElementById('voice-quick-select');
const refreshModelsBtn = document.getElementById('refresh-models');
const loadFileBtn      = document.getElementById('load-file-btn');
const pmxFileInput     = document.getElementById('pmx-file-input');
const statusDot        = document.getElementById('status-indicator');
const bgToggleBtn      = document.getElementById('bg-toggle-btn');
const refreshAudioDevicesBtn = document.getElementById('refresh-audio-devices-btn');
const settingsBtn      = document.getElementById('settings-btn');
const winControls      = document.getElementById('win-controls');
const winMinBtn        = document.getElementById('win-min-btn');
const winCloseBtn      = document.getElementById('win-close-btn');
const brandTitle       = document.getElementById('brand-title');

// DOM — Chat Panel
const messagesEl         = document.getElementById('messages');
const chatInput          = document.getElementById('chat-input');
const sendBtn            = document.getElementById('send-btn');
const micBtn             = document.getElementById('mic-btn');
const clearBtn           = document.getElementById('clear-btn');
const refreshMemoryBtn   = document.getElementById('refresh-memory-btn');
const chatPanel          = document.getElementById('chat-panel');
const toggleChatPanelBtn = document.getElementById('toggle-chat-panel');
const chatBubbleBtn      = document.getElementById('chat-bubble-btn');
const speechBubble       = document.getElementById('floating-speech-bubble');
const speechBubbleText   = document.getElementById('speech-bubble-text');
const panelTitleText     = document.getElementById('panel-title-text');

// DOM — Settings Modal
const settingsModal  = document.getElementById('settings-modal');
const closeSettingsBtn = document.getElementById('close-settings-btn');

// DOM — Voice Tab
const voicePresetGrid   = document.getElementById('voice-preset-grid');
const rvcModelsList     = document.getElementById('rvc-models-list');
const rvcCharNameInput  = document.getElementById('rvc-char-name');
const rvcPthInput       = document.getElementById('rvc-pth-input');
const rvcIndexInput     = document.getElementById('rvc-index-input');
const rvcPthLabel       = document.getElementById('rvc-pth-label');
const rvcIndexLabel     = document.getElementById('rvc-index-label');
const rvcUploadBtn      = document.getElementById('rvc-upload-btn');
const rvcUploadStatus   = document.getElementById('rvc-upload-status');
const rvcControls       = document.getElementById('rvc-controls');
const rvcPitchSlider    = document.getElementById('rvc-pitch-slider');
const rvcPitchVal       = document.getElementById('rvc-pitch-val');
const rvcIndexRateSlider = document.getElementById('rvc-index-rate-slider');
const rvcIndexRateVal   = document.getElementById('rvc-index-rate-val');
const testVoiceBtn      = document.getElementById('test-voice-btn');
const voiceTestStatus   = document.getElementById('voice-test-status');
const saveVoiceBtn      = document.getElementById('save-voice-btn');
const voiceSaveMsg      = document.getElementById('voice-save-msg');

// DOM — Theme & Environment
const themeBtn                = document.getElementById('theme-btn');
const themePopover            = document.getElementById('theme-popover');
const closeThemePopoverBtn    = document.getElementById('close-theme-popover');
const envColorPicker          = document.getElementById('env-color-picker');
const envColorHex             = document.getElementById('env-color-hex');
const envColorPickerModal     = document.getElementById('env-color-picker-modal');
const envColorHexModal        = document.getElementById('env-color-hex-modal');
const envIntensitySlider      = document.getElementById('env-intensity-slider');
const envIntensityVal         = document.getElementById('env-intensity-val');
const envIntensitySliderModal = document.getElementById('env-intensity-slider-modal');
const envIntensityValModal    = document.getElementById('env-intensity-val-modal');
const envRgbToggle            = document.getElementById('env-rgb-toggle');
const envRgbToggleModal       = document.getElementById('env-rgb-toggle-modal');
const saveThemeBtn            = document.getElementById('save-theme-btn');
const themeSaveMsg            = document.getElementById('theme-save-msg');

let currentEnvColor = localStorage.getItem('sakura_env_color') || '#ff6ea7';
let currentEnvIntensity = parseFloat(localStorage.getItem('sakura_env_intensity') || '1.0');
let currentRgbBreathing = localStorage.getItem('sakura_env_rgb') === 'true';

// DOM — Models Tab
const modelCardGrid      = document.getElementById('model-card-grid');
const refreshModelsModal = document.getElementById('refresh-models-modal');
const loadFileModal      = document.getElementById('load-file-modal');

// DOM — Audio Tab
const micSelect     = document.getElementById('mic-select');
const speakerSelect = document.getElementById('speaker-select');
const micMeterFill  = document.getElementById('mic-meter-fill');
const testAudioBtn  = document.getElementById('test-audio-btn');

// DOM — Assistant Tab
const assistantNameInput = document.getElementById('assistant-name-input');
const wakeWordInput      = document.getElementById('wake-word-input');
const wakeWordToggle     = document.getElementById('wake-word-toggle');
const computerControlToggle = document.getElementById('computer-control-toggle');
const saveSettingsBtn    = document.getElementById('save-settings-btn');
const saveStatusMsg      = document.getElementById('save-status-msg');

// DOM — Morph Overlay
const morphToggleBtn = document.getElementById('morph-toggle-btn');
const morphOverlay   = document.getElementById('morph-overlay');
const detectedMorphsEl = document.getElementById('detected-morphs');

const llmProvider = document.getElementById('llm-provider');
const geminiModel = document.getElementById('gemini-model');
const geminiApiKey = document.getElementById('gemini-api-key');
const geminiKeyStatus = document.getElementById('gemini-key-status');
const aiSaveStatus = document.getElementById('ai-save-status');

function updateProviderFields() {
    const local = llmProvider.value === 'ollama';
    document.getElementById('local-llm-settings').classList.toggle('hidden', !local);
    document.getElementById('gemini-settings').classList.toggle('hidden', local && !document.getElementById('gemini-fallback').checked);
    document.getElementById('browse-ollama-folder').style.display = window.pywebview ? '' : 'none';
}

async function scanLocalModels() {
    const status = document.getElementById('ollama-scan-status');
    status.textContent = 'Reading local models…';
    try {
        const response = await fetch('/api/ollama/models', { method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder: document.getElementById('ollama-models-folder').value.trim() }) });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error);
        const options = document.getElementById('ollama-model-options');
        options.replaceChildren();
        data.models.forEach(model => {
            const option = document.createElement('option');
            option.value = model.name;
            options.appendChild(option);
        });
        status.textContent = data.models.length ? `Available: ${data.models.map(m => m.name).join(', ')}` : 'No local models found.';
    } catch (error) { status.textContent = error.message; }
}

async function saveAiSettings(clearKey = false) {
    const modelButtons = ['qwen-2b-btn', 'qwen-4b-btn'].map(id => document.getElementById(id));
    if (modelButtons.some(button => button.disabled)) return;
    modelButtons.forEach(button => { button.disabled = true; });
    aiSaveStatus.textContent = 'Checking model and applying settings…';
    try {
        const payload = { llm_provider: llmProvider.value,
            gemini_model: geminiModel.value.trim() || 'gemini-flash-latest',
            ollama_model: document.getElementById('ollama-model').value.trim(),
            ollama_models_folder: document.getElementById('ollama-models-folder').value.trim(),
            ollama_context: Number(document.getElementById('ollama-context').value),
            gemini_fallback_enabled: !clearKey && document.getElementById('gemini-fallback').checked,
            local_timeout: Number(document.getElementById('local-timeout').value) };
        if (geminiApiKey.value.trim()) payload.gemini_api_key = geminiApiKey.value.trim();
        if (clearKey) payload.clear_gemini_key = true;
        const response = await fetch('/api/settings', { method: 'POST',
            headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        const data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || 'Could not save AI settings.');
        geminiApiKey.value = '';
        currentSettings = data.settings;
        applySettingsUI(currentSettings);
        flashMsg(aiSaveStatus, clearKey ? 'Saved key removed.' : 'AI settings saved.');
        await checkStatus();
        return true;
    } catch (err) { flashMsg(aiSaveStatus, err.message, 8000); return false; }
    finally { modelButtons.forEach(button => { button.disabled = false; }); }
}

async function testAiConnection() {
    const button = document.getElementById('test-ai-connection');
    button.disabled = true;
    aiSaveStatus.textContent = 'Testing saved connection…';
    try {
        if (!await saveAiSettings()) return;
        const response = await fetch('/api/llm/test', { method: 'POST' });
        const data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || 'Connection failed.');
        flashMsg(aiSaveStatus, data.message, 8000);
    } catch (err) { flashMsg(aiSaveStatus, err.message, 8000); }
    finally { button.disabled = false; }
}

let identityDirty = false;
let identitySaving = false;
let identitySaveQueued = false;
let identityTimer = null;
let currentSettings = { assistant_name: 'Sakura', wake_word: 'hey sakura', wake_word_enabled: false };
let wakeCommandDeadline = 0;

// ─────────────────────────── Custom Dropdown System ───────────────────────────
function initCustomDropdown(dropdownId, selectEl) {
    const dropdown = document.getElementById(dropdownId);
    if (!dropdown) return;
    const trigger = dropdown.querySelector('.dropdown-trigger');
    const menu = dropdown.querySelector('.dropdown-menu');
    if (!trigger || !menu) return;

    trigger.addEventListener('click', (e) => {
        e.stopPropagation();
        // Close other dropdowns & popovers
        document.querySelectorAll('.dropdown-menu').forEach(m => {
            if (m !== menu) m.classList.add('hidden');
        });
        document.querySelectorAll('.custom-dropdown').forEach(d => {
            if (d !== dropdown) d.classList.remove('open');
        });
        if (themePopover) themePopover.classList.add('hidden');

        const isOpen = !menu.classList.contains('hidden');
        if (isOpen) {
            menu.classList.add('hidden');
            dropdown.classList.remove('open');
        } else {
            menu.classList.remove('hidden');
            dropdown.classList.add('open');
        }
    });
}

let pmxFolderPath = [];
function renderPmxFolders(selectEl) {
    const menu = document.querySelector('#model-dropdown .dropdown-menu');
    menu.replaceChildren();
    const models = allPmxModels.filter(m => m.path.toLowerCase().endsWith('.pmx'));
    const foldersOf = m => m.folders || m.path.split('/').slice(1, -1);
    const within = m => pmxFolderPath.every((part, i) => foldersOf(m)[i] === part);
    if (!models.some(within)) pmxFolderPath = [];
    const add = (text, action, disabled = false) => {
        const item = document.createElement('button');
        item.type = 'button'; item.className = 'dropdown-item pmx-folder-item';
        item.textContent = text; item.disabled = disabled;
        item.addEventListener('click', e => { e.stopPropagation(); action(); });
        menu.appendChild(item);
    };
    const heading = document.createElement('div');
    heading.className = 'dropdown-group-heading';
    heading.textContent = ['PMX', ...pmxFolderPath].join(' / ');
    menu.appendChild(heading);
    if (pmxFolderPath.length) add('← Back', () => { pmxFolderPath.pop(); renderPmxFolders(selectEl); });
    const matches = models.filter(within);
    const folders = [...new Set(matches.map(m => foldersOf(m)[pmxFolderPath.length]).filter(Boolean))].sort((a,b) => a.localeCompare(b));
    for (const folder of folders) add('📁 ' + folder + ' ›', () => { pmxFolderPath.push(folder); renderPmxFolders(selectEl); });
    for (const model of matches.filter(m => foldersOf(m).length === pmxFolderPath.length)) {
        add((model.path === selectedPmxPath ? '✓ ' : '') + model.filename + (model.error ? ' — ' + model.error : ''), () => {
            selectEl.value = model.path;
            menu.classList.add('hidden');
            document.getElementById('model-dropdown').classList.remove('open');
            selectEl.dispatchEvent(new Event('change'));
        }, Boolean(model.error));
    }
    if (!matches.length) add('No PMX models found', () => {}, true);
}

function syncCustomDropdown(dropdownId, selectEl, onSelect) {
    // PMX libraries are commonly arranged as game / character / files.  Keep
    // that hierarchy everywhere, including the maximized model library.
    if (dropdownId === 'model-dropdown') {
        renderPmxFolders(selectEl); return;
    }
    const dropdown = document.getElementById(dropdownId);
    if (!dropdown || !selectEl) return;
    const label = dropdown.querySelector('.dropdown-label');
    const menu = dropdown.querySelector('.dropdown-menu');
    if (!label || !menu) return;

    menu.innerHTML = '';
    const options = Array.from(selectEl.options);
    if (options.length === 0) {
        menu.innerHTML = '<div class="dropdown-empty">None available</div>';
        return;
    }

    options.forEach(opt => {
        const item = document.createElement('div');
        item.className = `dropdown-item${opt.value === selectEl.value ? ' active' : ''}`;
        item.dataset.value = opt.value;
        if (opt.disabled) {
            item.className = opt.dataset.heading ? 'dropdown-group-heading' : 'dropdown-empty';
            item.textContent = opt.textContent;
            item.setAttribute('aria-disabled', 'true');
            menu.appendChild(item);
            return;
        }
        item.textContent = opt.textContent;
        item.addEventListener('click', (e) => {
            e.stopPropagation();
            selectEl.value = opt.value;
            label.textContent = opt.textContent;
            menu.querySelectorAll('.dropdown-item').forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            menu.classList.add('hidden');
            dropdown.classList.remove('open');
            selectEl.dispatchEvent(new Event('change'));
            if (onSelect) onSelect(opt.value);
        });
        menu.appendChild(item);
    });

    const activeOpt = selectEl.options[selectEl.selectedIndex];
    if (activeOpt && activeOpt.value) {
        label.textContent = activeOpt.textContent;
    }
}

function updateCustomDropdownLabel(dropdownId, text, value) {
    const dropdown = document.getElementById(dropdownId);
    if (!dropdown) return;
    const label = dropdown.querySelector('.dropdown-label');
    const menu = dropdown.querySelector('.dropdown-menu');
    if (label && text) label.textContent = text;
    if (menu && value !== undefined) {
        menu.querySelectorAll('.dropdown-item').forEach(item => {
            item.classList.toggle('active', item.dataset.value === value);
        });
    }
}

// ─────────────────────────── Init ───────────────────────────
window.addEventListener('sakura-model-render-error', event => {
    addMessage(`Model stopped to prevent repeated rendering errors: ${event.detail}. Select another character or try Low quality.`, 'sakura');
});

window.addEventListener('DOMContentLoaded', async () => {
    const nativeSurface = !!window.pywebview || /(?:desktop|library|upload)=1/.test(window.location.search);
    if (nativeSurface) document.body.classList.add('native-renderer');
    window.addEventListener('pywebviewready', () => document.body.classList.add('native-renderer'));
    const editorButton = document.getElementById('pmx-editor-btn');
    const showEditorButton = async () => {
        if (window.pywebview?.api?.platform_capabilities) {
            try {
                if (!(await window.pywebview.api.platform_capabilities()).pmx_editor) return;
            } catch (error) { console.warn('Native capabilities:', error); return; }
        }
        editorButton.classList.remove('hidden');
        document.getElementById('pmx-texture-compare').classList.remove('hidden');
    };
    if (window.pywebview) showEditorButton();
    window.addEventListener('pywebviewready', showEditorButton);
    editorButton.addEventListener('click', async () => {
        if (!selectedPmxPath?.toLowerCase().endsWith('.pmx')) {
            addMessage('Select a PMX model to open in PMX Editor.', 'sakura');
            return;
        }
        try {
            await window.pywebview.api.open_pmx_editor(selectedPmxPath);
        } catch (error) {
            addMessage(`PMX Editor: ${error.message || error}`, 'sakura');
            if (trackingOnly) alert(`PMX Editor: ${error.message || error}`);
        }
    });
    document.getElementById('pmx-texture-compare').addEventListener('click', () => editorButton.click());
    const referenceToggle = document.getElementById('pmx-reference-mode');
    referenceToggle.checked = localStorage.getItem('sakura_pmx_reference') === 'true';
    referenceToggle.addEventListener('change', async () => {
        localStorage.setItem('sakura_pmx_reference', String(referenceToggle.checked));
        save_setting_silent({pmx_texture_reference:referenceToggle.checked});
        if (lastGoodModelUrl && selectedPmxPath?.toLowerCase().endsWith('.pmx')) await loadModelFromUrl(lastGoodModelUrl);
    });
    document.getElementById('full-model-btn').addEventListener('click', event => {
        if (!viewer) return;
        viewer.fullModelView = !viewer.fullModelView;
        event.currentTarget.setAttribute('aria-pressed', String(viewer.fullModelView));
        event.currentTarget.textContent = viewer.fullModelView ? 'Portrait view' : 'Full model';
        if (viewer.model) viewer._autoFrame(viewer.model);
    });
    const uploadSplash = document.getElementById('model-upload-splash');
    if (new URLSearchParams(window.location.search).has('upload') && uploadSplash) {
        uploadSplash.classList.remove('hidden');
        const closeSplash = () => uploadSplash.classList.add('hidden');
        document.getElementById('skip-upload-splash')?.addEventListener('click', closeSplash);
        window.setTimeout(closeSplash, 3600);
    }
    const companionSplash = document.getElementById('desktop-companion-splash');
    if (new URLSearchParams(window.location.search).has('companion') && companionSplash) {
        companionSplash.classList.remove('hidden');
        const closeSplash = () => companionSplash.classList.add('hidden');
        document.getElementById('skip-companion-splash')?.addEventListener('click', closeSplash);
        window.setTimeout(closeSplash, 3000);
    }
    const isLibrary = new URLSearchParams(window.location.search).has('library');
    const isDesktop = !isLibrary && (new URLSearchParams(window.location.search).has('desktop') || !!window.pywebview);
    const setCompanionDragRegion = enabled => {
        const titlebar = document.getElementById('top-bar');
        const dragTargets = [titlebar, ...document.querySelectorAll('#top-bar .brand, #top-bar .logo, #top-bar .title, #top-bar .badge')];
        for (const target of dragTargets) {
            if (!target) continue;
            target.classList.toggle('pywebview-drag-region', Boolean(enabled));
        }
        if (titlebar) titlebar.title = enabled ? 'Drag anywhere on this bar to move Sakura Companion' : '';
        const flower = document.querySelector('#top-bar .logo');
        if (flower) flower.removeAttribute('title');
    };
    window.applyLibraryMode = async enabled => {
        document.body.classList.remove('overlay-ui-hidden', 'native-character-only');
        document.body.classList.toggle('desktop-companion', !enabled);
        document.body.classList.toggle('native-library', enabled);
        // Keep the Sakura title bar as the window drag area in all app modes.
        setCompanionDragRegion(true);
        winMinBtn.title = enabled && !trackingOnly ? 'Shrink to desktop companion' : 'Minimize to taskbar';
        winControls.style.display = 'flex';
        continuousMicBtn.style.display = enabled ? 'none' : 'inline-flex';
        if (enabled) {
            continuousMic.stop();
            setTransparency(false, false);
        } else {
            setTransparency(localStorage.getItem('sakura_transparency') !== 'false', false);
            await startDesktopListening();
        }
        window.dispatchEvent(new Event('resize'));
    };
    if (isDesktop || isLibrary) {
        setCompanionDragRegion(true);
        for (const edge of ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw']) {
            const handle = document.createElement('div');
            handle.className = `window-resize-handle resize-${edge}`;
            handle.title = 'Drag to resize companion window';
            handle.addEventListener('pointerdown', event => {
                if (event.button !== 0) return;
                event.preventDefault();
                event.stopPropagation();
                const api = window.pywebview?.api;
                if (!api?.start_window_resize) return;
                // Let Qt/the window manager own the drag, just like a normal
                // desktop window. Pointer capture and JS geometry updates
                // interfere with native edge resizing and cause lag/jumps.
                api.start_window_resize(edge).catch(error =>
                    console.warn('Window resize failed:', error));
            });
            document.body.appendChild(handle);
        }
        document.body.classList.add('desktop-companion');
        setTransparency(localStorage.getItem('sakura_transparency') !== 'false', false);
        winControls.style.display = 'flex';
        continuousMicBtn.style.display = 'inline-flex';
    } else {
        setTransparency(localStorage.getItem('sakura_transparency') === 'true', false);
    }
    if (isLibrary) window.applyLibraryMode(true);
    // 2. Initialize Three.js viewer and lip sync safely
    try {
        viewer  = new ModelViewer('viewer');
        installSpoutControls(()=>viewer);
        window.sakuraExpressionEditor = installExpressionEditor(()=>viewer, ()=>selectedPmxPath || lastGoodModelUrl || 'none');
        window.sakuraModelSettings = installModelSettings(()=>viewer, ()=>selectedPmxPath || lastGoodModelUrl || 'none', refreshPmxTextureSelector,()=>selectedMicId);
        updateQualityUI(viewer.quality);
        const savedStrength = localStorage.getItem('sakura_physics_boost');
        const migrated = {off:0,subtle:.55,normal:1,lively:1.5}[localStorage.getItem('sakura_physics_mode')] ?? 1;
        const previousStrength = Number(localStorage.getItem('sakura_physics_strength') ?? migrated);
        viewer.physicsEnabled = localStorage.getItem('sakura_physics_enabled') !== 'false';
        applyPhysicsStrength(savedStrength === null ? Math.max(0,(previousStrength-1)*3) : Number(savedStrength), false);
        viewer.setWindStrength(Number(localStorage.getItem('sakura_physics_wind') || 0));
        updatePhysicsUI(viewer.physics.mode);
        updateGlitchFixUI();
        lipSync = new LipSync(viewer);
        rvcVoiceChanger = new RvcVoiceChanger(lipSync, message => {
            const status = document.getElementById('vtuber-rvc-changer-status');
            if (status) status.textContent = message;
        }, () => currentVoiceId);
    } catch (err) {
        console.error('Failed to initialize 3D viewer / lip sync:', err);
    }
    setupEvents();
    setupAvatarTracking();
    const glowSlider = document.getElementById('character-glow-slider');
    glowSlider.value = Math.round(Number(localStorage.getItem('sakura_character_glow') || 0) * 100);
    const applyGlow = () => {
        viewer?.setCharacterGlow(Number(glowSlider.value) / 100);
        localStorage.setItem('sakura_character_glow', String(Number(glowSlider.value) / 100));
        document.getElementById('character-glow-value').textContent = `${glowSlider.value}%`;
    };
    glowSlider.addEventListener('input', applyGlow);
    applyGlow();
    for (const [id, key, fallback, unit] of [
        ['light-angle', 'sakura_light_angle', 35, '°'],
        ['light-elevation', 'sakura_light_elevation', 30, '°'],
        ['gloss-boost', 'sakura_gloss_boost', 0, '%']]) {
        const slider = document.getElementById(`${id}-slider`);
        slider.value = Number(localStorage.getItem(key) ?? fallback) * (id === 'gloss-boost' ? 100 : 1);
        const update = () => {
            localStorage.setItem(key, String(Number(slider.value) / (id === 'gloss-boost' ? 100 : 1)));
            document.getElementById(`${id}-value`).textContent = slider.value + unit;
            viewer?.setLightAngles(document.getElementById('light-angle-slider').value, document.getElementById('light-elevation-slider').value);
            viewer?.setGlossBoost(Number(document.getElementById('gloss-boost-slider').value) / 100);
        };
        slider.addEventListener('input', update);
        document.getElementById(`${id}-value`).textContent = slider.value + unit;
    }
    viewer?.setLightAngles(document.getElementById('light-angle-slider').value, document.getElementById('light-elevation-slider').value);
    viewer?.setGlossBoost(Number(document.getElementById('gloss-boost-slider').value) / 100);

    // Read the saved character before the models list chooses an initial model.
    try {
        await loadAppSettings();
        updateTransparencyShortcut();
        trackingOnly = !!currentSettings.vtuber_tracking_only;
        document.body.classList.toggle('tracking-only', trackingOnly);
        viewer?.setVtuberTrackingMode(trackingOnly);
        await Promise.all([
            loadVoicesList(),
            loadModelsList(),
            refreshAudioDevices(),
        ]);
    } catch (err) {
        console.warn('Initial data load warning:', err);
    }

    // 4. Apply saved audio output device
    if (selectedSpeakerId && lipSync) lipSync.setAudioOutput(selectedSpeakerId);

    // 5. Apply saved Environment Color & Aura
    applyEnvironmentTheme(currentEnvColor, currentEnvIntensity);
    if (currentRgbBreathing) {
        setRgbBreathingMode(true);
    }


    checkStatus();
    setInterval(checkStatus, 5000);
    setInterval(async () => {
        if (identityDirty || identitySaving) return;
        try {
            const response = await fetch('/api/settings');
            if (!response.ok) return;
            const saved = await response.json();
            if (identityDirty || identitySaving) return;
            const fields = ['assistant_name', 'wake_word', 'wake_word_enabled', 'computer_control_enabled'];
            if (fields.some(key => saved[key] !== currentSettings[key])) {
                for (const key of fields) currentSettings[key] = saved[key];
                wakeCommandDeadline = 0;
                applySettingsUI(currentSettings);
            }
        } catch (_) {}
    }, 5000);

    addMessage(`🌸 Konnichiwa! I am ${currentSettings.assistant_name || 'Sakura'}, your desktop companion! Use ⚙️ Settings to pick your voice and 3D character model~`, 'sakura');
    if (isDesktop) await startDesktopListening();
});

// ─────────────────────────── Tab System ───────────────────────────
function setupTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(`tab-${tab}`).classList.add('active');

            // Side effects when switching tabs
            if (tab === 'audio') startMicLevelMonitor();
            else stopMicLevelMonitor();
        });
    });
}

// ─────────────────────────── Events ───────────────────────────
function transparencyShortcut(event) {
    const key = event.key?.toUpperCase();
    if (!/^(?:[A-Z0-9]|F(?:[1-9]|1[0-2]))$/.test(key || '')) return '';
    return [event.ctrlKey?'Ctrl':'',event.altKey?'Alt':'',event.shiftKey?'Shift':'',event.metaKey?'Meta':'',key].filter(Boolean).join('+');
}
function updateTransparencyShortcut() {
    const shortcut=currentSettings.transparency_hotkey || 'Ctrl+Shift+T';
    document.getElementById('transparency-shortcut-label').textContent=shortcut;
    bgToggleBtn.title='Toggle streaming transparency ('+shortcut+')';
}

function setupEvents() {
    const hotkeyInput=document.getElementById('transparency-hotkey');
    hotkeyInput.addEventListener('keydown',event=>{
        event.preventDefault();event.stopPropagation();
        if(event.key==='Backspace'||event.key==='Delete'){hotkeyInput.value='';return;}
        const shortcut=transparencyShortcut(event);
        if(shortcut && (event.ctrlKey || event.altKey || event.metaKey))hotkeyInput.value=shortcut;
    });
    document.getElementById('reset-transparency-hotkey').onclick=()=>{hotkeyInput.value='';};
    document.getElementById('save-general-settings').addEventListener('click',async()=> {
        const status=document.getElementById('general-save-status');
        try {
            const shortcut=hotkeyInput.value || 'Ctrl+Shift+T';
            if(window.pywebview?.api?.set_transparency_hotkey){
                const result=await window.pywebview.api.set_transparency_hotkey(shortcut);
                if(!result.ok)throw new Error(result.error);
            }
            const response=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},
                body:JSON.stringify({transparency_hotkey:shortcut,preserve_configuration_on_reinstall:document.getElementById('preserve-configuration').checked})});
            const data=await response.json();
            if(!response.ok)throw new Error(data.error || 'Settings could not be saved.');
            currentSettings=data.settings;updateTransparencyShortcut();status.textContent='General settings saved. Transparency: '+(currentSettings.transparency_hotkey || 'Ctrl+Shift+T');
        }catch(error){status.textContent=error.message;}
    });
    document.querySelectorAll('[data-quality]').forEach(button => {
        button.addEventListener('click', () => applyModelQuality(button.dataset.quality));
    });
    document.querySelectorAll('[data-physics]').forEach(button => {
        button.addEventListener('click', () => applyPhysicsMode(button.dataset.physics));
    });
    document.getElementById('physics-strength').addEventListener('input', event => applyPhysicsStrength(Number(event.target.value)/100));
    document.getElementById('physics-enabled').addEventListener('change', event => {
        viewer.physicsEnabled = event.target.checked;
        localStorage.setItem('sakura_physics_enabled',String(event.target.checked));
        save_setting_silent({physics_enabled:event.target.checked});
        applyPhysicsStrength(viewer.physicsBoost ?? 0,false);
    });
    document.getElementById('physics-wind').addEventListener('input', event => {
        const value = Number(event.target.value)/100;
        viewer?.setWindStrength(value);
        localStorage.setItem('sakura_physics_wind',String(value));
        save_setting_silent({physics_wind:value});
        updatePhysicsUI(viewer?.physics?.mode);
    });
    document.getElementById('physics-repair-btn')?.addEventListener('click', () => {
        if (!viewer?.model || viewer.vrm) return;
        localStorage.setItem(glitchFixStorageKey(glitchModelKey || selectedPmxPath), 'true');
        viewer.repairPhysics();
        updateGlitchFixUI();
        updatePhysicsUI(viewer?.physics?.mode);
    });
    document.getElementById('glitch-fix-btn')?.addEventListener('click', () => {
        if (!viewer?.model) return;
        localStorage.setItem(glitchFixStorageKey(glitchModelKey || selectedPmxPath), 'true');
        viewer.setGlitchFix(true);
        updateGlitchFixUI();
        updatePhysicsUI(viewer?.physics?.mode);
    });
    document.getElementById('glitch-restore-btn')?.addEventListener('click', () => {
        if (!viewer?.model) return;
        localStorage.setItem(glitchFixStorageKey(glitchModelKey || selectedPmxPath), 'false');
        viewer.setGlitchFix(false);
        updateGlitchFixUI();
        updatePhysicsUI(viewer?.physics?.mode);
    });
    document.getElementById('quality-btn').addEventListener('click', () => {
        const modes = ['low', 'balanced', 'high'];
        applyModelQuality(modes[(modes.indexOf(viewer?.quality || 'balanced') + 1) % modes.length]);
    });
    continuousMicBtn.addEventListener('click', () => {
        if (continuousMic.enabled) continuousMic.stop();
        else startDesktopListening();
    });
    setupTabs();

    // Custom dropdown triggers
    initCustomDropdown('model-dropdown', modelSelect);
    initCustomDropdown('vrm-dropdown', document.getElementById('vrm-select'));
    initCustomDropdown('live2d-dropdown', document.getElementById('live2d-select'));
    document.getElementById('live2d-select').addEventListener('change',e=>{if(e.target.value)loadModelFromUrl('/models/'+e.target.value.split('/').map(encodeURIComponent).join('/'));});
    initCustomDropdown('voice-dropdown', voiceQuickSelect);
    initCustomDropdown('mic-dropdown', micSelect);
    initCustomDropdown('speaker-dropdown', speakerSelect);

    // Close open dropdowns when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.custom-dropdown')) {
            document.querySelectorAll('.dropdown-menu').forEach(m => m.classList.add('hidden'));
            document.querySelectorAll('.custom-dropdown').forEach(d => d.classList.remove('open'));
        }
    });

    // Screen access is always off on page load and requires the browser picker.
    screenViewBtn.addEventListener('click', async () => {
        try {
            await screenShare.toggle();
            if (!screenShare.enabled) return;
            listeningStatus.textContent = 'Checking screen vision…';
            const response = await fetch('/api/screen/status');
            const status = await response.json();
            if (!response.ok || !status.ready) throw new Error(status.message || 'Screen vision is unavailable.');
            if (!screenShare.enabled) return;
            listeningStatus.textContent = `Screen captured · ${status.model}. Ask “What can you see?”`;
            await reactToScreen(true);
        } catch (err) {
            screenShare.stop();
            listeningStatus.textContent = `Screen: ${err.message}`;
            addMessage(`⚠️ ${err.message}`, 'sakura');
        }
    });

    llmProvider.addEventListener('change', updateProviderFields);
    document.getElementById('gemini-fallback').addEventListener('change', updateProviderFields);
    document.getElementById('scan-ollama-models').addEventListener('click', scanLocalModels);
    for (const [id, model] of [['qwen-2b-btn', 'qwen3-vl:2b-instruct'], ['qwen-4b-btn', 'qwen3-vl:4b-instruct']]) {
        document.getElementById(id).addEventListener('click', async () => {
            if (chatBusy || reactionBusy) {
                flashMsg(aiSaveStatus, 'Wait for the current reply to finish before switching models.', 6000);
                return;
            }
            llmProvider.value = 'ollama';
            document.getElementById('ollama-model').value = model;
            await saveAiSettings();
        });
    }
    document.getElementById('browse-ollama-folder').addEventListener('click', async () => {
        try {
            const folder = await window.pywebview?.api.choose_ollama_folder();
            if (folder) {
                document.getElementById('ollama-models-folder').value = folder;
                await scanLocalModels();
            }
        } catch (error) { document.getElementById('ollama-scan-status').textContent = error.message; }
    });
    screenReactBtn.addEventListener('click', () => {
        if (!screenShare.enabled) {
            listeningStatus.textContent = 'Turn Screen on first, then enable reactions.';
            return;
        }
        reactionsEnabled = !reactionsEnabled;
        if(!reactionsEnabled)viewer?.reactionExpressions?.stop();
        screenReactBtn.textContent = reactionsEnabled ? '💬 Reactions on' : '💬 Reactions off';
        screenReactBtn.setAttribute('aria-pressed', String(reactionsEnabled));
    });
    async function screenReactionLoop() {
        try { await reactToScreen(); }
        finally { setTimeout(screenReactionLoop, gameActive ? 1000 : 2000); }
    }
    setTimeout(screenReactionLoop, 1000);
    document.getElementById('save-ai-settings').addEventListener('click', () => saveAiSettings());
    document.getElementById('test-ai-connection').addEventListener('click', testAiConnection);
    document.getElementById('remove-gemini-key').addEventListener('click', () => saveAiSettings(true));

    // Chat
    sendBtn.addEventListener('click', handleSendMessage);
    chatInput.addEventListener('keydown', e => { if (e.key === 'Enter') handleSendMessage(); });
    clearBtn.addEventListener('click', handleClearChat);
    document.getElementById('vtuber-mode-btn').addEventListener('click', () => {
        openSettingsModal();
        document.querySelector('.tab-btn[data-tab="assistant"]')?.click();
    });
    document.getElementById('vtuber-start-btn').addEventListener('click', async () => {
        const status = document.getElementById('vtuber-status');
        const button = document.getElementById('vtuber-start-btn');
        button.disabled = true;
        try {
            const response = await fetch('/api/vtuber/connect', {method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({link: document.getElementById('youtube-chat-link').value.trim()})});
            const data = await response.json();
            if (!response.ok) throw new Error(data.error);
            ++vtuberGeneration;
            vtuberEnabled = true;
            vtuberQueue = [];
            lastViewerReply = '';
            status.textContent = 'Connecting to YouTube live chat…';
            document.getElementById('vtuber-mode-btn').textContent = 'AI VTuber on';
        } catch (error) { status.textContent = error.message; }
        finally { button.disabled = false; }
    });
    document.getElementById('vtuber-stop-btn').addEventListener('click', async () => {
        vtuberEnabled = false;
        ++vtuberGeneration;
        vtuberQueue = [];
        if (vtuberSpeaking) document.getElementById('interrupt-btn').click();
        await fetch('/api/vtuber/disconnect', {method: 'POST'}).catch(console.error);
        document.getElementById('vtuber-status').textContent = 'Off';
        document.getElementById('vtuber-mode-btn').textContent = 'AI VTuber';
    });
    setInterval(pollVtuberChat, 3000);
    const gameButton = document.getElementById('auto-game-btn');
    gameButton.style.display = '';
    gameButton.addEventListener('click', async () => {
        autoGameEnabled = !autoGameEnabled;
        gameButton.textContent = autoGameEnabled ? '🎮 Auto game on' : '🎮 Auto game off';
        gameButton.setAttribute('aria-pressed', String(autoGameEnabled));
        if (!autoGameEnabled) { document.getElementById('interrupt-btn').click(); await leaveGameMode(); }
        else checkGameMode();
    });
    setInterval(checkGameMode, 2000);
    document.getElementById('clear-memory-desktop').addEventListener('click', handleClearChat);
    refreshMemoryBtn.addEventListener('click', async () => {
        refreshMemoryBtn.disabled = true;
        try {
            const response = await fetch('/api/refresh-memory', { method: 'POST' });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || 'Memory refresh failed.');
            addMessage('Memory refreshed. I will address you as Master now.', 'sakura');
        } catch (error) {
            addMessage(`⚠️ ${error.message}`, 'sakura');
        } finally { refreshMemoryBtn.disabled = false; }
    });
    micBtn.addEventListener('click', handleToggleMic);

    // Top-bar quick model & voice selectors
    refreshModelsBtn.addEventListener('click', loadModelsList);
    // Rescan when opening the library: folders copied manually appear without a restart.
    document.getElementById('model-dropdown-trigger').addEventListener('click', () => {
        if (document.getElementById('model-dropdown').classList.contains('open')) loadModelsList();
    });
    for (const select of [modelSelect, document.getElementById('vrm-select')]) select.addEventListener('change', async e => {
        const path = e.target.value;
        if (!path) return;
        selectedPmxPath = path;
        syncModelSelectors();
        highlightActiveModelCard(path);
        await loadModelFromUrl(`/models/${path.split('/').map(encodeURIComponent).join('/')}`);
    });
    voiceQuickSelect.addEventListener('change', async e => {
        const id = e.target.value;
        if (!id) return;
        await applyVoiceById(id);
    });

    // File pickers
    loadFileBtn.addEventListener('click', () => pmxFileInput.click());
    pmxFileInput.addEventListener('change', handleLocalFileSelect);
    const eyeButton = document.getElementById('eye-tracking-btn');
    const eyeTracking = new EyeTracking(viewer, enabled => {
        eyeButton.textContent = enabled ? '👀 Eyes on' : '👀 Eyes off';
        eyeButton.setAttribute('aria-pressed', String(enabled));
    });
    eyeButton.addEventListener('click', () => {
        if (eyeTracking.enabled) eyeTracking.stop(); else eyeTracking.start();
        localStorage.setItem('sakura_eye_tracking', String(eyeTracking.enabled));
    });
    if (localStorage.getItem('sakura_eye_tracking') === 'true') eyeTracking.start();
    window.addEventListener('pagehide', () => eyeTracking.stop());
    const sizeSlider = document.getElementById('model-size');
    const savedSize = Number(localStorage.getItem('sakura_model_size') || 100);
    sizeSlider.value = Number.isFinite(savedSize) ? Math.max(40, Math.min(180, savedSize)) : 100;
    const applySize = () => {
        viewer?.setDisplaySize(sizeSlider.value);
        document.getElementById('model-size-value').textContent = `${sizeSlider.value}%`;
    };
    sizeSlider.addEventListener('input', applySize);
    applySize();
    document.getElementById('dance-btn').onclick=()=>{
        if(!viewer?.dance?.start(document.getElementById('dance-style').value))listeningStatus.textContent='Choose a rigged PMX or VRM in Companion mode to dance.';
    };
    document.getElementById('dance-stop-btn').onclick=()=>viewer?.dance?.stop();
    document.getElementById('interrupt-btn').addEventListener('click', () => {
        viewer?.dance?.stop();
        ++chatReplyGeneration;
        replyController?.abort();
        lipSync?.stop();
        chatBusy = false;
        removeTypingIndicator();
        hideSpeechBubble();
        viewer?.setActivity('idle');
        lastMicActivity = Date.now();
    });
    const chooseModelPackage=async(input,kind)=>{
        if(!window.pywebview?.api.import_model_package){document.getElementById(input).click();return;}
        try{
            const data=await window.pywebview.api.import_model_package(kind);
            if(data.cancelled)return;
            if(data.error)throw Error(data.error);
            await loadModelsList();
            if(data.models?.length)await loadModelFromUrl('/models/'+data.models[0].split('/').map(encodeURIComponent).join('/'));
            addMessage(data.message||'Model imported.','sakura');
        }catch(error){addMessage(error.message,'sakura');}
    };
    document.getElementById('rig-analysis-reset').onclick=()=>{viewer?.rigMonitor?.reset();updatePhysicsUI(viewer?.physics.mode);};
    document.getElementById('rig-analysis-image').onclick=()=>{
        const blob=viewer?.rigDiagnosticImage;
        if(!blob){document.getElementById('rig-analysis-status').textContent='Wait eight seconds after loading a PMX model for its diagnostic image.';return;}
        const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='Sakura-model-diagnosis.png';link.click();setTimeout(()=>URL.revokeObjectURL(url),5000);
    };
    window.addEventListener('sakura-rig-analysis',()=>updatePhysicsUI(viewer?.physics.mode));
    for (const [button, input,kind] of [['upload-pmx-toolbar', 'pmx-folder-input','pmx'], ['upload-vrm-toolbar', 'vrm-file-input','vrm'], ['upload-live2d-toolbar', 'live2d-folder-input','live2d']]) {
        document.getElementById(button).addEventListener('click', () => chooseModelPackage(input,kind));
    }
    document.getElementById('import-model-folder').addEventListener('click', () => chooseModelPackage('pmx-folder-input','pmx'));
    document.getElementById('pmx-folder-input').addEventListener('change', handleLocalFileSelect);
    for (const [button, input] of [['import-vrm', 'vrm-file-input'], ['import-live2d', 'live2d-folder-input']]) {
        document.getElementById(button).addEventListener('click', () => chooseModelPackage(input,input==='vrm-file-input'?'vrm':'live2d'));
        document.getElementById(input).addEventListener('change', handleLocalFileSelect);
    }
    window.addEventListener('dragover', e => e.preventDefault());
    window.addEventListener('drop', handleFileDrop);

    // Settings Modal
    settingsBtn.addEventListener('click', openSettingsModal);
    closeSettingsBtn.addEventListener('click', closeSettingsModal);
    settingsModal.addEventListener('click', e => { if (e.target === settingsModal) closeSettingsModal(); });
    window.toggleStreamingControls = () => {
        const hide = !document.body.classList.contains('overlay-ui-hidden');
        document.body.classList.toggle('overlay-ui-hidden', hide);
        document.getElementById('overlay-ui-btn').setAttribute('aria-pressed', String(hide));
        document.querySelectorAll('.dropdown-menu').forEach(m => m.classList.add('hidden'));
    };
    window.toggleCompanionView = () => {
        if (trackingOnly) { window.toggleStreamingControls(); return; }
        if (document.body.classList.contains('native-library')) return;
        const hide = !document.body.classList.contains('overlay-ui-hidden');
        setTransparency(hide);
        document.body.classList.toggle('overlay-ui-hidden', hide);
        document.body.classList.toggle('native-character-only', hide && !!window.pywebview);
        window.pywebview?.api.set_character_only(hide).catch(console.error);
        document.querySelectorAll('.dropdown-menu').forEach(m => m.classList.add('hidden'));
    };
    bgToggleBtn.addEventListener('click', window.toggleCompanionView);
    document.getElementById('restore-companion-controls').addEventListener('click', window.toggleCompanionView);
    document.getElementById('overlay-ui-btn').addEventListener('click', () => {
        if (trackingOnly || document.body.classList.contains('native-library')) window.toggleStreamingControls();
        else window.toggleCompanionView();
    });
    document.getElementById('viewer').addEventListener('dblclick', () => {
        if (document.body.classList.contains('overlay-ui-hidden') && !document.body.classList.contains('native-character-only')) window.toggleStreamingControls();
    });
    window.addEventListener('keydown', e => {
        if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'h') {
            e.preventDefault();
            if (trackingOnly || document.body.classList.contains('native-library')) window.toggleStreamingControls();
            else window.toggleCompanionView();
        }
        if (!e.repeat && !e.target.closest?.('input,textarea,select,[contenteditable="true"]') && transparencyShortcut(e) === (currentSettings.transparency_hotkey || 'Ctrl+Shift+T')) {
            e.preventDefault();
            if (!window.pywebview) window.toggleCompanionView();
            else window.pywebview.api.hotkey_status().then(registered => {
                if (!registered) window.toggleCompanionView();
            }).catch(() => window.toggleCompanionView());
        }
    });

    // Audio tab
    micSelect.addEventListener('change', e => {
        selectedMicId = e.target.value;
        localStorage.setItem('sakura_mic_id', selectedMicId);
        startMicLevelMonitor();
        if (continuousMic.enabled) startDesktopListening();
        if (rvcVoiceChanger?.active) rvcVoiceChanger.start(selectedMicId).catch(error => {
            void stopVtuberVoiceChanger(`Could not open microphone: ${error.message}`);
        });
    });
    speakerSelect.addEventListener('change', e => {
        selectedSpeakerId = e.target.value;
        localStorage.setItem('sakura_speaker_id', selectedSpeakerId);
        lipSync.setAudioOutput(selectedSpeakerId);
    });
    testAudioBtn.addEventListener('click', playTestAudioTone);
    refreshAudioDevicesBtn?.addEventListener('click', () => refreshAudioDevices({ requestPermission: true }));
    navigator.mediaDevices?.addEventListener?.('devicechange', () => refreshAudioDevices());

    // Assistant tab
    if (saveSettingsBtn) saveSettingsBtn.addEventListener('click', saveAppSettings);
    for (const control of [assistantNameInput, wakeWordInput, wakeWordToggle, computerControlToggle]) {
        control?.addEventListener(control.type === 'checkbox' ? 'change' : 'input', () => {
            identityDirty = true;
            clearTimeout(identityTimer);
            identityTimer = setTimeout(saveAppSettings, 700);
        });
    }

    // Voice tab — RVC sliders
    rvcPitchSlider.addEventListener('input', () => {
        rvcPitchVal.textContent = `${rvcPitchSlider.value} st`;
    });
    rvcIndexRateSlider.addEventListener('input', () => {
        rvcIndexRateVal.textContent = parseFloat(rvcIndexRateSlider.value).toFixed(2);
    });

    // RVC file pickers
    rvcPthInput.addEventListener('change', () => {
        rvcPthLabel.textContent = rvcPthInput.files[0]?.name || 'No file';
    });
    rvcIndexInput.addEventListener('change', () => {
        rvcIndexLabel.textContent = rvcIndexInput.files[0]?.name || 'Optional';
    });
    rvcUploadBtn.addEventListener('click', uploadRvcModel);

    // Voice test & save
    testVoiceBtn.addEventListener('click', testCurrentVoice);
    saveVoiceBtn.addEventListener('click', saveVoiceSettings);

    // Models tab buttons
    refreshModelsModal.addEventListener('click', loadModelsList);
    document.getElementById('pmx-material-slot').addEventListener('change', updatePmxTextureChoice);
    document.getElementById('pmx-texture-refresh').addEventListener('click', refreshPmxTextureSelector);
    document.getElementById('pmx-texture-apply').addEventListener('click', () => savePmxTextureChoice(false));
    document.getElementById('pmx-texture-reset').addEventListener('click', () => savePmxTextureChoice(true));
    loadFileModal.addEventListener('click', () => pmxFileInput.click());

    // Chat panel minimize / restore
    toggleChatPanelBtn.addEventListener('click', () => {
        chatPanel.classList.add('minimized');
        chatBubbleBtn.classList.remove('hidden');
    });
    chatBubbleBtn.addEventListener('click', () => {
        chatPanel.classList.remove('minimized');
        chatBubbleBtn.classList.add('hidden');
    });

    // Morph Overlay
    morphToggleBtn.addEventListener('click', () => morphOverlay.classList.toggle('collapsed'));

    // Desktop Window Controls
    winCloseBtn.addEventListener('click', () => {
        if (window.pywebview?.api) window.pywebview.api.close();
        else window.close();
    });
    winMinBtn.addEventListener('click', () => {
        if (!trackingOnly && document.body.classList.contains('native-library') && window.pywebview?.api?.set_library_mode) {
            window.pywebview.api.set_library_mode(false);
        } else if (window.pywebview?.api) window.pywebview.api.minimize();
    });
    const maximizeButton = document.getElementById('win-max-btn');
    window.updateMaximizeControl = maximized => {
        document.body.classList.toggle('window-maximized', maximized);
        maximizeButton.textContent = maximized ? '❐' : '□';
        maximizeButton.title = maximized ? 'Restore window' : 'Maximize / open model library';
        maximizeButton.setAttribute('aria-label', maximized ? 'Restore window' : 'Maximize');
    };
    maximizeButton.addEventListener('click', () => {
        window.pywebview?.api?.toggle_maximize().catch(error => console.error('Window sizing:', error));
    });
    window.updateMaximizeControl(document.body.classList.contains('native-library'));

    // 🎨 Theme & Environment Color Wheel
    setupThemeEvents();
}

// ─────────────────────────── Settings Modal ───────────────────────────
function openSettingsModal() {
    settingsModal.classList.remove('hidden');
    if (trackingOnly) document.getElementById('settings-refresh-cameras')?.click();
    if (document.getElementById('tab-audio').classList.contains('active')) startMicLevelMonitor();
}
function closeSettingsModal() {
    settingsModal.classList.add('hidden');
    stopMicLevelMonitor();
}

// ─────────────────────────── App Settings ───────────────────────────
async function loadAppSettings() {
    try {
        const res = await fetch('/api/settings');
        const data = await res.json();
        currentSettings = data;
        applySettingsUI(data);
        restoreRenderingPreferences(data);
    } catch (err) { console.error('Failed to load settings:', err); }
}

function applySettingsUI(s) {
    document.getElementById('preserve-configuration').checked=s.preserve_configuration_on_reinstall !== false;
    document.getElementById('transparency-hotkey').value=s.transparency_hotkey || '';
    updateTransparencyShortcut();
    llmProvider.value = s.llm_provider || 'ollama';
    document.getElementById('ollama-model').value = s.ollama_model || 'qwen3-vl:2b-instruct';
    document.getElementById('ollama-models-folder').value = s.ollama_models_folder || '';
    document.getElementById('ollama-context').value = s.ollama_context || 4096;
    document.getElementById('gemini-fallback').checked = !!s.gemini_fallback_enabled;
    document.getElementById('local-timeout').value = s.local_timeout || 20;
    geminiModel.value = s.gemini_model || 'gemini-flash-latest';
    geminiKeyStatus.textContent = s.gemini_key_set ? 'A key is saved. Enter a new key to replace it.' : 'No key saved yet.';
    document.getElementById('remove-gemini-key').disabled = !s.gemini_key_set;
    updateProviderFields();
    if (screenShare.enabled) screenShare.onChange(true, false);
    if (!identityDirty) {
        if (assistantNameInput) assistantNameInput.value = s.assistant_name || 'Sakura';
        if (wakeWordInput) wakeWordInput.value = s.wake_word || 'hey sakura';
        if (wakeWordToggle) wakeWordToggle.checked = !!s.wake_word_enabled;
        if (computerControlToggle) computerControlToggle.checked = !!s.computer_control_enabled;
    }
    if (brandTitle)         brandTitle.textContent = s.assistant_name || 'Sakura';
    if (panelTitleText)     panelTitleText.textContent = `💬 Chat with ${s.assistant_name || 'Sakura'}`;

    // Apply saved voice
    if (s.selected_voice) {
        currentVoiceId = s.selected_voice;
        if (voiceQuickSelect) voiceQuickSelect.value = s.selected_voice;
    }
    // Apply RVC sliders
    if (rvcPitchSlider) {
        rvcPitchSlider.value = s.rvc_pitch ?? 0;
        rvcPitchVal.textContent = `${rvcPitchSlider.value} st`;
    }
    if (rvcIndexRateSlider) {
        rvcIndexRateSlider.value = s.rvc_index_rate ?? 0.75;
        rvcIndexRateVal.textContent = parseFloat(rvcIndexRateSlider.value).toFixed(2);
    }

    // Apply saved Environment Color & Aura
    if (s.env_color) currentEnvColor = s.env_color;
    if (s.env_intensity !== undefined) currentEnvIntensity = s.env_intensity;
    if (s.env_rgb_breathing !== undefined) currentRgbBreathing = s.env_rgb_breathing;
    applyEnvironmentTheme(currentEnvColor, currentEnvIntensity);
    if (currentRgbBreathing) setRgbBreathingMode(true);
}

async function saveAppSettings() {
    clearTimeout(identityTimer);
    if (identitySaving) { identitySaveQueued = true; return; }
    identitySaving = true;
    const newName = (assistantNameInput?.value.trim()) || 'Sakura';
    const newWakeWord = (wakeWordInput?.value.trim().toLowerCase()) || 'hey sakura';
    const newWakeEnabled = wakeWordToggle?.checked || false;
    const newComputerControl = computerControlToggle?.checked || false;

    try {
        const res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                assistant_name: newName,
                wake_word: newWakeWord,
                wake_word_enabled: newWakeEnabled,
                computer_control_enabled: newComputerControl,
            }),
        });
        const data = await res.json();
        if (!res.ok || !data.ok) throw new Error(data.error || 'Could not save assistant settings.');
        const stillMatches = (assistantNameInput.value.trim() || 'Sakura') === newName && (wakeWordInput.value.trim().toLowerCase() || 'hey sakura') === newWakeWord
            && wakeWordToggle.checked === newWakeEnabled && computerControlToggle.checked === newComputerControl;
        if (stillMatches) identityDirty = false;
        else identitySaveQueued = true;
        wakeCommandDeadline = 0;
        currentSettings = data.settings;
        applySettingsUI(currentSettings);
        flashMsg(saveStatusMsg, newWakeEnabled ? `Saved · Say "${newWakeWord}" before a command.` : 'Saved · Wake phrase is off; all speech is accepted.');
    } catch (err) { flashMsg(saveStatusMsg, err.message, 8000); }
    finally {
        identitySaving = false;
        if (identitySaveQueued) { identitySaveQueued = false; saveAppSettings(); }
    }
}

// ─────────────────────────── Theme & Environment System ───────────────────────────
function hexToRgb(hex) {
    let clean = (hex || '#ff6ea7').replace('#', '');
    if (clean.length === 3) clean = clean.split('').map(c => c + c).join('');
    const num = parseInt(clean, 16) || 0;
    return {
        r: (num >> 16) & 255,
        g: (num >> 8) & 255,
        b: num & 255,
    };
}

function rgbToHsl(r, g, b) {
    r /= 255; g /= 255; b /= 255;
    const max = Math.max(r, g, b), min = Math.min(r, g, b);
    let h = 0, s = 0, l = (max + min) / 2;
    if (max !== min) {
        const d = max - min;
        s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
        switch (max) {
            case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
            case g: h = ((b - r) / d + 2) / 6; break;
            case b: h = ((r - g) / d + 4) / 6; break;
        }
    }
    return { h: Math.round(h * 360), s: Math.round(s * 100), l: Math.round(l * 100) };
}

function applyEnvironmentTheme(hex, intensity = 1.0, isRgbCycle = false) {
    if (!hex) return;
    const { r, g, b } = hexToRgb(hex);
    const { h, s, l } = rgbToHsl(r, g, b);

    // CSS variables
    const root = document.documentElement.style;
    root.setProperty('--sakura-pink', hex);
    root.setProperty('--sakura-glow', `rgba(${r}, ${g}, ${b}, ${(0.45 * intensity).toFixed(2)})`);
    root.setProperty('--panel-border', `rgba(${r}, ${g}, ${b}, ${(0.28 * intensity).toFixed(2)})`);
    root.setProperty('--sakura-bubble', `rgba(${r}, ${g}, ${b}, ${(0.22 * intensity).toFixed(2)})`);

    // Ambient background gradient
    const bg1 = `hsl(${h}, ${Math.min(s, 40)}%, ${Math.max(8, Math.round(l * 0.22))}%)`;
    const bg2 = `hsl(${h}, ${Math.min(s, 50)}%, 4%)`;
    const userBubble = `hsl(${h}, ${Math.min(s, 30)}%, 14%)`;
    root.setProperty('--bg-grad-1', bg1);
    root.setProperty('--bg-grad-2', bg2);
    root.setProperty('--user-bubble', userBubble);

    // 3D Scene lighting
    if (viewer && typeof viewer.setEnvironmentColor === 'function') {
        viewer.setEnvironmentColor(hex, intensity);
    }

    if (!isRgbCycle) {
        currentEnvColor = hex;
        currentEnvIntensity = intensity;
        localStorage.setItem('sakura_env_color', hex);
        localStorage.setItem('sakura_env_intensity', intensity.toString());

        // Sync inputs
        if (envColorPicker) envColorPicker.value = hex;
        if (envColorHex) envColorHex.textContent = hex;
        if (envColorPickerModal) envColorPickerModal.value = hex;
        if (envColorHexModal) envColorHexModal.textContent = hex;

        const pct = Math.round(intensity * 100);
        if (envIntensitySlider) envIntensitySlider.value = pct;
        if (envIntensityVal) envIntensityVal.textContent = `${pct}%`;
        if (envIntensitySliderModal) envIntensitySliderModal.value = pct;
        if (envIntensityValModal) envIntensityValModal.textContent = `${pct}%`;

        // Highlight matching preset chips
        document.querySelectorAll('.aura-chip').forEach(chip => {
            const chipColor = chip.dataset.color?.toLowerCase();
            chip.classList.toggle('active', chipColor === hex.toLowerCase());
        });
    }
}

function setRgbBreathingMode(enabled) {
    currentRgbBreathing = !!enabled;
    localStorage.setItem('sakura_env_rgb', currentRgbBreathing ? 'true' : 'false');
    if (envRgbToggle) envRgbToggle.checked = currentRgbBreathing;
    if (envRgbToggleModal) envRgbToggleModal.checked = currentRgbBreathing;

    if (viewer && typeof viewer.setRgbBreathing === 'function') {
        viewer.setRgbBreathing(currentRgbBreathing, (cycleHex) => {
            applyEnvironmentTheme(cycleHex, currentEnvIntensity, true);
        });
    }

    if (!currentRgbBreathing) {
        applyEnvironmentTheme(currentEnvColor, currentEnvIntensity, false);
    }
}

function setupThemeEvents() {
    // Popover open / close
    if (themeBtn) {
        themeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (themePopover) themePopover.classList.toggle('hidden');
        });
    }
    if (closeThemePopoverBtn) {
        closeThemePopoverBtn.addEventListener('click', () => {
            if (themePopover) themePopover.classList.add('hidden');
        });
    }
    document.addEventListener('click', (e) => {
        if (themePopover && !themePopover.classList.contains('hidden')) {
            if (!themePopover.contains(e.target) && e.target !== themeBtn) {
                themePopover.classList.add('hidden');
            }
        }
    });

    // Real-time Color Wheel Input
    const onColorPick = (e) => {
        const hex = e.target.value;
        if (currentRgbBreathing) setRgbBreathingMode(false);
        applyEnvironmentTheme(hex, currentEnvIntensity, false);
        save_setting_silent({ env_color: hex, env_rgb_breathing: false });
    };
    if (envColorPicker) envColorPicker.addEventListener('input', onColorPick);
    if (envColorPickerModal) envColorPickerModal.addEventListener('input', onColorPick);

    // Intensity Slider
    const onIntensityChange = (e) => {
        const intensity = parseFloat(e.target.value) / 100.0;
        currentEnvIntensity = intensity;
        applyEnvironmentTheme(currentEnvColor, currentEnvIntensity, false);
        save_setting_silent({ env_intensity: intensity });
    };
    if (envIntensitySlider) envIntensitySlider.addEventListener('input', onIntensityChange);
    if (envIntensitySliderModal) envIntensitySliderModal.addEventListener('input', onIntensityChange);

    // RGB Breathing Toggles
    if (envRgbToggle) {
        envRgbToggle.addEventListener('change', (e) => {
            setRgbBreathingMode(e.target.checked);
            save_setting_silent({ env_rgb_breathing: e.target.checked });
        });
    }
    if (envRgbToggleModal) {
        envRgbToggleModal.addEventListener('change', (e) => {
            setRgbBreathingMode(e.target.checked);
            save_setting_silent({ env_rgb_breathing: e.target.checked });
        });
    }

    // Preset Chips
    document.querySelectorAll('.aura-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const color = chip.dataset.color;
            if (color) {
                if (currentRgbBreathing) setRgbBreathingMode(false);
                applyEnvironmentTheme(color, currentEnvIntensity, false);
                save_setting_silent({ env_color: color, env_rgb_breathing: false });
            }
        });
    });

    // Save Theme in Modal
    if (saveThemeBtn) {
        saveThemeBtn.addEventListener('click', async () => {
            await save_setting_silent({
                env_color: currentEnvColor,
                env_intensity: currentEnvIntensity,
                env_rgb_breathing: currentRgbBreathing,
            });
            flashMsg(themeSaveMsg, 'Theme saved! ✓');
        });
    }
}

// ─────────────────────────── Voice System ───────────────────────────
async function loadVoicesList() {
    try {
        const res = await fetch('/api/voices');
        const data = await res.json();
        allVoicePresets = data.presets || [];
        allRvcModels    = data.rvc_models || [];
        const current   = data.current || {};

        currentVoiceId = current.selected_voice || 'sakura_ava';

        renderVoiceGrid();
        renderRvcModelsList();
        populateVoiceQuickSelect();

        // Apply saved slider values
        if (rvcPitchSlider) {
            rvcPitchSlider.value = current.rvc_pitch ?? 0;
            rvcPitchVal.textContent = `${rvcPitchSlider.value} st`;
        }
        if (rvcIndexRateSlider) {
            rvcIndexRateSlider.value = current.rvc_index_rate ?? 0.75;
            rvcIndexRateVal.textContent = parseFloat(rvcIndexRateSlider.value).toFixed(2);
        }

        // Show RVC controls if current voice is RVC
        updateRvcControlsVisibility(currentVoiceId);
        updateVtuberRvcStatus();
    } catch (err) { console.error('Failed to load voices:', err); }
}

function populateVoiceQuickSelect() {
    if (!voiceQuickSelect) return;
    voiceQuickSelect.innerHTML = '<option value="">🎵 Voice...</option>';

    // Add built-in presets (skip the placeholder rvc_custom)
    allVoicePresets.filter(p => p.voice !== 'rvc').forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = `${p.gender || ''} · ${p.language || 'English'} · ${p.name}`;
        if (p.id === currentVoiceId) opt.selected = true;
        voiceQuickSelect.appendChild(opt);
    });

    // Add discovered RVC models
    allRvcModels.forEach(m => {
        const opt = document.createElement('option');
        opt.value = m.id;
        opt.textContent = m.name;
        if (m.id === currentVoiceId) opt.selected = true;
        voiceQuickSelect.appendChild(opt);
    });

    syncCustomDropdown('voice-dropdown', voiceQuickSelect);
    const readerChoice=document.getElementById('reader-voice');
    if(readerChoice){readerChoice.replaceChildren(...Array.from(voiceQuickSelect.options,o=>new Option(o.text,o.value)));readerChoice.value=currentVoiceId;}
}

function renderVoiceGrid() {
    if (!voicePresetGrid) return;
    voicePresetGrid.innerHTML = '';

    const groups = [
        ['Female · English', allVoicePresets.filter(p=>p.voice!=='rvc' && p.gender==='Female' && p.language==='English')],
        ['Male · English', allVoicePresets.filter(p=>p.voice!=='rvc' && p.gender==='Male' && p.language==='English')],
        ['Hindi & Hinglish', allVoicePresets.filter(p=>['Hindi','Hinglish'].includes(p.language))],
        ['Custom RVC', allRvcModels],
    ];
    for (const [title,presets] of groups) {
        if (!presets.length) continue;
        const heading=document.createElement('div'); heading.className='voice-group-heading'; heading.textContent=title;
        voicePresetGrid.appendChild(heading);
        presets.forEach(preset => {
        const card = document.createElement('div');
        card.className = `voice-card${preset.id === currentVoiceId ? ' active' : ''}`;
        card.dataset.id = preset.id;
        card.innerHTML = `
            <div class="vc-name">${preset.name}</div>
            <div class="vc-desc">${preset.desc || preset.character || ''}</div>
        `;
        card.addEventListener('click', () => applyVoiceById(preset.id));
        voicePresetGrid.appendChild(card);
        });
    }
}

function selectVoiceCard(id) {
    currentVoiceId = id;
    document.querySelectorAll('.voice-card').forEach(c => {
        c.classList.toggle('active', c.dataset.id === id);
    });
    if (voiceQuickSelect) voiceQuickSelect.value = id;
    const match = allVoicePresets.find(p => p.id === id) || allRvcModels.find(m => m.id === id);
    if (match) {
        updateCustomDropdownLabel('voice-dropdown', match.name, id);
    }
    updateRvcControlsVisibility(id);
    updateVtuberRvcStatus();
}

function updateVtuberRvcStatus(message = '') {
    const status = document.getElementById('vtuber-rvc-changer-status');
    if (!status) return;
    if (message) {
        status.textContent = message;
        return;
    }
    if (rvcVoiceChanger?.active) return;
    const selected = allRvcModels.find(model => model.id === currentVoiceId);
    if (selected) {
        status.textContent = `Off · ${selected.name} selected. Enable microphone voice mode to convert your speech.`;
        return;
    }
    const preset = allVoicePresets.find(voice => voice.id === currentVoiceId);
    const choices = allRvcModels.map(model => model.name.replace(/^🎤\s*/, '')).join(' or ');
    status.textContent = allRvcModels.length
        ? `Off · ${preset?.name || 'A built-in voice'} selected. Enable for this voice, or choose ${choices} for RVC.`
        : `Off · ${preset?.name || 'A built-in voice'} selected. Enable microphone voice mode to use it.`;
}

function updateRvcControlsVisibility(id) {
    const isRvc = id.startsWith('rvc_') || allRvcModels.some(m => m.id === id);
    if (rvcControls) rvcControls.style.display = isRvc ? 'flex' : 'none';
}

function renderRvcModelsList() {
    if (!rvcModelsList) return;
    rvcModelsList.innerHTML = '';

    if (allRvcModels.length === 0) {
        rvcModelsList.innerHTML = '<div class="rvc-empty">No custom voice models found in <code>voices/</code> folder</div>';
        return;
    }

    allRvcModels.forEach(m => {
        const item = document.createElement('div');
        item.className = `rvc-model-item${m.id === currentVoiceId ? ' active' : ''}`;
        item.dataset.id = m.id;
        item.innerHTML = `
            <span class="rmi-name">${m.name}</span>
            <span class="rmi-badge">${m.has_index ? '✓ Index' : 'No Index'}</span>
        `;
        item.addEventListener('click', () => applyVoiceById(m.id));
        rvcModelsList.appendChild(item);
    });
}

async function applyVoiceById(id) {
    if (!id) return;
    if (chatBusy || reactionBusy || lipSync?.isPlaying) {
        selectVoiceCard(currentVoiceId);
        flashMsg(voiceSaveMsg, 'Wait for the current reply to finish before changing voice or language.');
        return;
    }
    const previousVoiceId = currentVoiceId;
    const changerWasActive = typeof rvcVoiceChanger !== 'undefined' && rvcVoiceChanger?.active;
    if (changerWasActive) rvcVoiceChanger.pauseForVoiceSwitch();
    currentVoiceId = id;
    selectVoiceCard(id);
    ++chatReplyGeneration;
    lipSync?.stop();
    await saveVoiceSettings();
    if (changerWasActive && rvcVoiceChanger?.active) {
        if (currentSettings?.selected_voice !== id) {
            currentVoiceId = previousVoiceId;
            selectVoiceCard(previousVoiceId);
            rvcVoiceChanger.resumeAfterVoiceSwitch();
            updateVtuberRvcStatus('Voice could not be saved; microphone voice mode kept the previous voice.');
            return;
        }
        if (allRvcModels.some(model => model.id === id)) {
            try {
                if (currentSettings?.rvc_model !== allRvcModels.find(model => model.id === id)?.pth)
                    throw new Error('The selected RVC model was not saved.');
                await prepareVtuberRvcVoice();
                rvcVoiceChanger.resumeAfterVoiceSwitch();
            }
            catch (error) { await stopVtuberVoiceChanger(`Could not load RVC voice: ${error.message}`); }
        } else {
            rvcVoiceChanger.resumeAfterVoiceSwitch();
            updateVtuberRvcStatus('Built-in voice selected · microphone voice mode remains on.');
        }
    }
}

async function prepareVtuberRvcVoice() {
    const model = allRvcModels.find(item => item.id === currentVoiceId);
    if (!model) throw new Error('Select an installed [RVC] voice first.');
    const modal = document.getElementById('rvc-loading-modal');
    const message = document.getElementById('rvc-loading-message');
    const error = document.getElementById('rvc-loading-error');
    const close = document.getElementById('rvc-loading-close');
    if (message) message.textContent = `Loading ${model.name}. This can take a little while the first time.`;
    if (error) error.textContent = '';
    if (close) close.classList.add('hidden');
    modal?.classList.remove('hidden');
    try {
        const response = await fetch('/api/voice-changer/prepare', {method: 'POST'});
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || `Could not load RVC (${response.status}).`);
        if (message) message.textContent = `${model.name} is ready.`;
        await new Promise(resolve => setTimeout(resolve, 350));
        modal?.classList.add('hidden');
    } catch (exception) {
        if (error) error.textContent = exception.message;
        if (message) message.textContent = 'RVC could not be loaded.';
        if (close) close.classList.remove('hidden');
        throw exception;
    }
}

async function stopVtuberVoiceChanger(message = 'Off') {
    const toggle = document.getElementById('vtuber-rvc-changer-toggle');
    if (toggle) toggle.checked = false;
    const wasActive = Boolean(rvcVoiceChanger?.active);
    await rvcVoiceChanger?.stop();
    if (wasActive) await fetch('/api/voice-changer/stop', {method: 'POST'}).catch(() => {});
    if(viewer)viewer.voiceChangerActive=false;
    viewer?.setTrackingMouthEnabled(!viewer?.mouthOptions||['webcam','both'].includes(viewer.mouthOptions.source));
    const status = document.getElementById('vtuber-rvc-changer-status');
    if (status) {
        if (message === 'Off') updateVtuberRvcStatus();
        else status.textContent = message;
    }
}

async function testCurrentVoice() {
    if (!testVoiceBtn) return;
    if (chatBusy || reactionBusy || lipSync?.isPlaying) return;
    testVoiceBtn.disabled = true;
    flashMsg(voiceTestStatus, '⏳ Generating preview...');

    // Gather current config
    const payload = buildVoicePayload();
    const language=allVoicePresets.find(p=>p.id===currentVoiceId)?.language || 'English';
    payload.text = language==='Hindi' ? 'नमस्ते! मेरी आवाज़ ऐसी है। क्या आपको पसंद आई?'
        : language==='Hinglish' ? 'Hello! Meri voice aisi hai. Aapko kaisi lagi?'
        : 'Hello! This is how I sound. Do you like this voice?';

    try {
        const res = await fetch('/api/tts/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (data.ok && data.audio) {
            await lipSync.playWithLipSync(data.audio);
            flashMsg(voiceTestStatus, '✓ Played!');
        } else {
            flashMsg(voiceTestStatus, `⚠️ ${data.error || 'Error'}`);
        }
    } catch (err) {
        flashMsg(voiceTestStatus, '⚠️ Failed');
    } finally {
        testVoiceBtn.disabled = false;
    }
}

async function saveVoiceSettings() {
    if (chatBusy || reactionBusy || lipSync?.isPlaying) {
        flashMsg(voiceSaveMsg, 'Wait for the current reply to finish before changing voice or language.');
        return;
    }
    const payload = buildVoicePayload();
    const save = async () => {
        try {
            const res = await fetch('/api/settings', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (!res.ok || !data.ok) throw new Error(data.error || 'Voice could not be applied.');
            ++voiceSelectionGeneration;
            if (currentVoiceId === payload.selected_voice) {
                currentSettings = data.settings;
                flashMsg(voiceSaveMsg, 'Voice applied ✓');
            }
        } catch (err) {
            flashMsg(voiceSaveMsg, `⚠️ ${err.message}`);
            addMessage(`⚠️ ${err.message}`, 'sakura');
        }
    };
    // Apply rapid selections in order, so the newest choice stays active.
    voiceSaveQueue = voiceSaveQueue.then(save, save);
    return voiceSaveQueue;
}

function buildVoicePayload() {
    const rvcModel = allRvcModels.find(m => m.id === currentVoiceId);
    const preset = allVoicePresets.find(p => p.id === currentVoiceId);
    return {
        selected_voice:  currentVoiceId,
        tts_pitch:       preset?.pitch || '+0Hz',
        tts_rate:        preset?.rate || '+0%',
        rvc_model:       rvcModel ? rvcModel.pth : '',
        rvc_index:       rvcModel ? (rvcModel.index || '') : '',
        rvc_pitch:       rvcPitchSlider ? parseInt(rvcPitchSlider.value) : 0,
        rvc_index_rate:  rvcIndexRateSlider ? parseFloat(rvcIndexRateSlider.value) : 0.75,
        voice:           currentVoiceId,
        pitch:           preset?.pitch || '+0Hz',
        rate:            preset?.rate || '+0%',
    };
}

// ── RVC Upload ────────────────────────────────────────────────
async function uploadRvcModel() {
    if (chatBusy || reactionBusy || lipSync?.isPlaying) {
        flashMsg(rvcUploadStatus, 'Wait for the current reply to finish before activating an RVC voice.');
        return;
    }
    if (document.body.classList.contains('desktop-companion')) return;
    const charName = rvcCharNameInput?.value.trim();
    const pthFile  = rvcPthInput?.files[0];

    if (!charName) { flashMsg(rvcUploadStatus, '⚠️ Enter a character name!'); return; }
    if (!pthFile)  { flashMsg(rvcUploadStatus, '⚠️ Select a .pth model file!'); return; }

    rvcUploadBtn.disabled = true;
    flashMsg(rvcUploadStatus, '⏳ Uploading...');

    const formData = new FormData();
    formData.append('character_name', charName);
    formData.append('pth_file', pthFile);
    if (rvcIndexInput?.files[0]) formData.append('index_file', rvcIndexInput.files[0]);

    try {
        const res = await fetch('/api/voices/upload', { method: 'POST', body: formData });
        const data = await res.json();
        if (data.ok) {
            flashMsg(rvcUploadStatus, `✅ "${charName}" uploaded & activated!`);
            rvcCharNameInput.value = '';
            rvcPthInput.value = '';
            rvcIndexInput.value = '';
            rvcPthLabel.textContent = 'No file';
            rvcIndexLabel.textContent = 'Optional';
            await loadVoicesList();
        } else {
            flashMsg(rvcUploadStatus, `⚠️ ${data.error}`);
        }
    } catch (err) {
        flashMsg(rvcUploadStatus, `⚠️ Upload failed: ${err.message}`);
    } finally {
        rvcUploadBtn.disabled = false;
    }
}

// ─────────────────────────── 3D Model Loading ───────────────────────────
function syncModelSelectors() {
    for (const [id, select, label] of [['model-dropdown', modelSelect, 'PMX'], ['vrm-dropdown', document.getElementById('vrm-select'), 'VRM'], ['live2d-dropdown', document.getElementById('live2d-select'), 'Live2D']]) {
        select.value = Array.from(select.options).some(o => o.value === selectedPmxPath) ? selectedPmxPath : '';
        syncCustomDropdown(id, select);
        const selected = select.options[select.selectedIndex];
        updateCustomDropdownLabel(id, selected?.value ? `${label} · ${selected.textContent}` : label, select.value);
    }
}

async function loadModelsList() {
    try {
        const res = await fetch('/api/models');
        const data = await res.json();
        allPmxModels = data.models || [];

        for (const [select, extension, label] of [[modelSelect, '.pmx', 'PMX'], [document.getElementById('vrm-select'), '.vrm', 'VRM']]) {
            select.innerHTML = '';
            const placeholder = new Option(label, '');
            placeholder.disabled = true;
            select.appendChild(placeholder);
            for (const model of allPmxModels.filter(m => m.path.toLowerCase().endsWith(extension))) {
                const option = new Option(model.name + (model.error ? ' — ' + model.error : ''), model.path);
                option.disabled = Boolean(model.error);
                select.appendChild(option);
            }
        }
        syncModelSelectors();

        const live2dSelect = document.getElementById('live2d-select');
        live2dSelect.innerHTML = '<option value="">Live2D</option>';
        const live2d = data.live2d_models || [];
        for (const model of live2d.length ? live2d : [{name: 'No Live2D models imported'}]) {
            const option = document.createElement('option');
            option.disabled = !model.path;
            option.value=model.path || '';
            option.textContent = model.name;
            live2dSelect.appendChild(option);
        }
        syncCustomDropdown('live2d-dropdown', live2dSelect);

        // Render model cards in Settings > Models tab
        renderModelCards();

        syncModelSelectors();

        // Auto-load first model if none selected
        if (!selectedPmxPath && (allPmxModels.length > 0 || live2d.length > 0)) {
            const available = [...allPmxModels.filter(m => !m.error), ...live2d.filter(m=>m.path)];
            const savedName = (currentSettings.selected_model || '').split('/').pop();
            const relocated = available.filter(m => m.filename === savedName);
            selectedPmxPath = available.find(m => m.path === currentSettings.selected_model)?.path
                || (relocated.length === 1 ? relocated[0].path : available[0]?.path);
            if (!selectedPmxPath) return;
            syncModelSelectors();
            highlightActiveModelCard(selectedPmxPath);
            await loadModelFromUrl(`/models/${selectedPmxPath.split('/').map(encodeURIComponent).join('/')}`);
        }
    } catch (err) { console.error('Failed to fetch models list:', err); }
}

function renderModelCards() {
    if (!modelCardGrid) return;
    modelCardGrid.innerHTML = '';

    if (allPmxModels.length === 0) {
        modelCardGrid.innerHTML = '<div style="font-size:0.8rem;color:var(--text-muted);grid-column:1/-1;text-align:center;padding:20px">No .pmx models found in <code>models/</code></div>';
        return;
    }

    allPmxModels.forEach(m => {
        const card = document.createElement('div');
        card.className = `model-card${m.path === selectedPmxPath ? ' active' : ''}`;
        card.dataset.path = m.path;

        // Pick a fun icon by character name heuristics
        const icons = { evelyn: '🧝', miku: '🎵', sakura: '🌸', hutao: '🔥', rem: '💙', emilia: '⚡', nami: '🌊' };
        const icon = icons[m.name.toLowerCase()] || '🎎';
        card.innerHTML = `
            <div class="mc-icon">${icon}</div>
            <div class="mc-name">${m.name}</div>
            <div class="mc-file">${m.filename}</div>
        `;
        if (m.error) { card.title = m.error; card.classList.add('invalid-model'); }
        card.addEventListener('click', async () => {
            if (m.error) { addMessage(m.error, 'sakura'); return; }
            selectedPmxPath = m.path;
            syncModelSelectors();
            highlightActiveModelCard(m.path);
            closeSettingsModal();
            await loadModelFromUrl(`/models/${m.path.split('/').map(encodeURIComponent).join('/')}`);
        });
        modelCardGrid.appendChild(card);
    });
}

function highlightActiveModelCard(path) {
    document.querySelectorAll('.model-card').forEach(c => {
        c.classList.toggle('active', c.dataset.path === path);
    });
}

async function refreshPmxTextureSelector() {
    const panel = document.getElementById('pmx-texture-selector');
    const model = selectedPmxPath;
    const enabled = !!model?.toLowerCase().endsWith('.pmx') && !!viewer.pmxTextureSlots?.length;
    panel.hidden = !enabled;
    if (!enabled) return;
    const select = document.getElementById('pmx-material-slot');
    const previous = select.value;
    select.replaceChildren();
    viewer.pmxTextureSlots.forEach((slot, i) => select.add(new Option(`${slot.material + 1}. ${slot.name} — ${slot.slot}`, String(i))));
    if ([...select.options].some(o => o.value === previous)) select.value = previous;
    try {
        const response = await fetch('/api/models/texture-options?model=' + encodeURIComponent(model), {cache:'no-store'});
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Could not list texture files.');
        if (model !== selectedPmxPath) return;
        const choice = document.getElementById('pmx-texture-choice');
        choice.replaceChildren();
        for (const file of data.textures) choice.add(new Option(file, file));
        updatePmxTextureChoice();
    } catch (err) {
        document.getElementById('pmx-texture-selector-status').textContent = err.message;
    }
}

function updatePmxTextureChoice() {
    const slot = viewer.pmxTextureSlots?.[Number(document.getElementById('pmx-material-slot').value)];
    if (!slot) return;
    document.getElementById('pmx-original-texture').textContent = `Original: ${slot.original}. Current override: ${slot.chosen || 'none'}.`;
    const choice = document.getElementById('pmx-texture-choice');
    const target = slot.chosen || slot.original.replace(/\\/g, '/');
    choice.value = [...choice.options].some(o => o.value === target) ? target : '';
}

async function savePmxTextureChoice(reset) {
    const model = selectedPmxPath;
    const slot = viewer.pmxTextureSlots?.[Number(document.getElementById('pmx-material-slot').value)];
    const texture = document.getElementById('pmx-texture-choice').value;
    const status = document.getElementById('pmx-texture-selector-status');
    if (!slot || (!reset && !texture)) {status.textContent = 'Choose a material and replacement image first.'; return;}
    const buttons = ['pmx-texture-apply','pmx-texture-reset'].map(id=>document.getElementById(id));
    buttons.forEach(b=>b.disabled=true);
    try {
        const response = await fetch('/api/models/texture-material', {method:'POST',headers:{'Content-Type':'application/json'},
            body:JSON.stringify({model,material:slot.material,slot:slot.slot,texture:reset ? null : texture})});
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Could not save texture.');
        if (model === selectedPmxPath) await loadModelFromUrl('/models/' + model.split('/').map(encodeURIComponent).join('/'));
        status.textContent = reset ? 'Original PMX reference restored.' : 'Texture saved and model reloaded. Original PMX is unchanged.';
    } catch (err) {status.textContent=err.message;}
    finally {buttons.forEach(b=>b.disabled=false);}
}

let lastGoodModelUrl = null;
let modelRecoveryGeneration = 0;
async function loadModelFromUrl(url, recovering = false) {
    const attempt = ++modelRecoveryGeneration;
    if (detectedMorphsEl) detectedMorphsEl.textContent = '';
    addMessage(`⏳ Loading 3D model: ${url.split('/').pop()}...`, 'sakura');
    try {
        viewer.preferPmxReference = localStorage.getItem('sakura_pmx_reference') === 'true';
        const modelKey = decodeURIComponent(url.replace(/^\/models\//, '').split(/[?#]/, 1)[0]);
        const savedGlitchPolicy = localStorage.getItem(glitchFixStorageKey(modelKey));
        const result = await viewer.loadModel(url, {
            glitchFixPolicy: savedGlitchPolicy === null ? 'auto' : savedGlitchPolicy === 'true' ? 'on' : 'off',
        });
        if (!result || attempt !== modelRecoveryGeneration) return;
        if (result.notice) addMessage(result.notice, 'sakura');
        lastGoodModelUrl = url;
        selectedPmxPath = decodeURIComponent(url.replace(/^\/models\//, ''));
        window.sakuraExpressionEditor?.refresh();
        await window.sakuraModelSettings?.refresh();
        glitchModelKey = selectedPmxPath;
        syncModelSelectors();
        save_setting_silent({ selected_model: selectedPmxPath });
        addMessage(`✨ Model loaded! (${result.morphs.length} morph targets detected)`, 'sakura');
        console.info('Character physics:', result.physics || 'unavailable');
        updateGlitchFixUI();
        updatePhysicsUI(localStorage.getItem('sakura_physics_mode') || 'normal');
        const textureStatus = document.getElementById('pmx-texture-status');
        refreshPmxTextureSelector();
        if (textureStatus) {
            const review=viewer.textureReview;
            const required=review?.required_missing ?? review?.missing ?? [];
            const optional=review?.optional_missing ?? [];
            textureStatus.textContent = required.length
                ? `Missing diffuse textures (${required.length}): ${required.map(p=>p.split('/').pop()).join(', ')}. Use Check textures in PMX Editor to inspect them.`
                : optional.length ? `Diffuse textures found. ${optional.length} optional shine maps are missing; neutral fallbacks are used. PMX Editor opens only when requested.`
                : review ? 'Texture references checked: no missing files.' : 'Texture check unavailable. You can compare manually in PMX Editor.';
        }
        if (detectedMorphsEl) {
            detectedMorphsEl.textContent = result.morphs.slice(0, 15).join(', ') + (result.morphs.length > 15 ? '...' : '');
        }
    } catch (err) {
        if (attempt !== modelRecoveryGeneration) return;
        addMessage(`⚠️ This model could not load: ${err.message || err}. Check that its complete folder was copied, or re-export the PMX.`, 'sakura');
        if (!recovering && lastGoodModelUrl && lastGoodModelUrl !== url) {
            addMessage('Restoring the last working character…', 'sakura');
            await loadModelFromUrl(lastGoodModelUrl, true);
        }
    }
}

async function handleLocalFileSelect(e) {
    if (document.body.classList.contains('desktop-companion')) { e.target.value = ''; return; }
    const files = Array.from(e.target.files);
    if (!files.length) return;
    const form = new FormData();
    if (e.target.dataset.modelFormat) form.append('model_format', e.target.dataset.modelFormat);
    files.forEach(file => form.append('files', file, file.webkitRelativePath || file.name));
    addMessage('Importing model and textures…', 'sakura');
    try {
        const response = await fetch('/api/models/import', { method: 'POST', body: form });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Import failed');
        await loadModelsList();
        if (data.renderable !== false) await loadModelFromUrl('/models/' + data.models[0].split('/').map(encodeURIComponent).join('/'));
        addMessage(data.message || 'Model saved in your library.', 'sakura');
    } catch (error) { addMessage(error.message, 'sakura'); }
    finally { e.target.value = ''; }
}

function handleFileDrop(e) {
    e.preventDefault();
    if (document.body.classList.contains('desktop-companion')) return;
    if (e.dataTransfer.files.length > 0) {
        const file = e.dataTransfer.files[0];
        if (file.name.toLowerCase().endsWith('.pmx') || file.name.toLowerCase().endsWith('.pmd')) {
            loadLocalPmx(file);
        }
    }
}

async function loadLocalPmx(file) {
    if (detectedMorphsEl) detectedMorphsEl.textContent = '';
    addMessage(`⏳ Loading local file: ${file.name}...`, 'sakura');
    const blobUrl = URL.createObjectURL(file);
    try {
        glitchModelKey = `local/${file.webkitRelativePath || file.name}:${file.size}:${file.lastModified}`;
        const savedGlitchPolicy = localStorage.getItem(glitchFixStorageKey(glitchModelKey));
        const result = await viewer.loadModel(blobUrl, {glitchFixPolicy: savedGlitchPolicy === null ? 'auto' : savedGlitchPolicy === 'true' ? 'on' : 'off'});
        if (!result) return;
        addMessage(`✨ Loaded ${file.name}! Note: Put model folder in anime-assistant/models/ for full textures.`, 'sakura');
        updateGlitchFixUI();
        updatePhysicsUI(localStorage.getItem('sakura_physics_mode') || 'normal');
        if (detectedMorphsEl) {
            detectedMorphsEl.textContent = result.morphs.slice(0, 15).join(', ') + (result.morphs.length > 15 ? '...' : '');
        }
    } catch (err) {
        addMessage(`⚠️ Error loading PMX: ${err.message || err}`, 'sakura');
    } finally {
        URL.revokeObjectURL(blobUrl);
    }
}

// ─────────────────────────── Audio Devices ───────────────────────────
async function refreshAudioDevices({ requestPermission = false } = {}) {
    if (!navigator.mediaDevices?.enumerateDevices) return;
    try {
        if (requestPermission && !continuousMic.enabled && navigator.mediaDevices.getUserMedia) {
            const permissionStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            permissionStream.getTracks().forEach(track => track.stop());
        }
        const devices = await navigator.mediaDevices.enumerateDevices();
        const audioInputs  = devices.filter(d => d.kind === 'audioinput');
        const audioOutputs = devices.filter(d => d.kind === 'audiooutput');

        micSelect.innerHTML = '<option value="">Default Microphone</option>';
        audioInputs.forEach((dev, i) => {
            const opt = document.createElement('option');
            opt.value = dev.deviceId;
            opt.textContent = dev.label || `Microphone ${i + 1}`;
            if (dev.deviceId === selectedMicId) opt.selected = true;
            micSelect.appendChild(opt);
        });

        speakerSelect.innerHTML = '<option value="">Default Audio Output</option>';
        audioOutputs.forEach((dev, i) => {
            const opt = document.createElement('option');
            opt.value = dev.deviceId;
            opt.textContent = dev.label || `Speaker ${i + 1}`;
            if (dev.deviceId === selectedSpeakerId) opt.selected = true;
            speakerSelect.appendChild(opt);
        });

        syncCustomDropdown('mic-dropdown', micSelect);

        syncCustomDropdown('speaker-dropdown', speakerSelect, (val) => {
            selectedSpeakerId = val;
            localStorage.setItem('sakura_speaker_id', selectedSpeakerId);
            if (lipSync) lipSync.setAudioOutput(selectedSpeakerId);
        });
    } catch (err) {
        console.warn('Audio device enumeration failed:', err);
        if (refreshAudioDevicesBtn) refreshAudioDevicesBtn.title = 'Microphone permission is required';
    }
}

function updateQualityUI(mode) {
    const names = { low: 'Low', balanced: 'Balanced', high: 'High' };
    document.getElementById('quality-btn').textContent = names[mode];
    document.querySelectorAll('[data-quality]').forEach(button => {
        const selected = button.dataset.quality === mode;
        button.classList.toggle('active', selected);
        button.setAttribute('aria-pressed', String(selected));
    });
}
function applyModelQuality(mode) {
    if (!viewer) return;
    viewer.setQuality(mode);
    updateQualityUI(viewer.quality);
    save_setting_silent({model_quality:viewer.quality});
}

function applyPhysicsMode(mode, persist = true) {
    const value = ['off', 'subtle', 'normal', 'lively'].includes(mode) ? mode : 'normal';
    if (persist) localStorage.setItem('sakura_physics_mode', value);
    if (persist) save_setting_silent({physics_mode:value,physics_enabled:value !== 'off'});
    if (viewer) viewer.setPhysicsMode(value);
    updatePhysicsUI(value);
}

function applyPhysicsStrength(strength, persist = true) {
    const value = Number.isFinite(strength) ? Math.max(0,Math.min(1.5,strength)) : 0;
    if(persist) localStorage.setItem('sakura_physics_boost',String(value));
    if(persist) save_setting_silent({physics_boost:value,physics_mode:viewer?.physicsEnabled === false?'off':'custom'});
    if(viewer) {
        viewer.physicsBoost = value;
        viewer.setPhysicsStrength(viewer.physicsEnabled === false ? 0 : 1 + value/3);
    }
    updatePhysicsUI(viewer?.physics?.mode);
}

function restoreRenderingPreferences(settings) {
    // Move older browser-only preferences into config so upgrades can reuse
    // them even when the renderer/profile changes. Existing config wins.
    const mapping={model_quality:'sakura_render_quality',physics_mode:'sakura_physics_mode',
        physics_boost:'sakura_physics_boost',physics_enabled:'sakura_physics_enabled',
        physics_wind:'sakura_physics_wind',pmx_texture_reference:'sakura_pmx_reference'};
    const migration={};
    for(const [field,key] of Object.entries(mapping)) {
        if(settings[field] !== undefined)localStorage.setItem(key,String(settings[field]));
        else if(localStorage.getItem(key)!==null) {
            const raw=localStorage.getItem(key);
            migration[field]=['physics_enabled','pmx_texture_reference'].includes(field)?raw==='true':
                ['physics_boost','physics_wind'].includes(field)?Number(raw):raw;
        }
    }
    if(Object.keys(migration).length)save_setting_silent(migration);
    const reference=document.getElementById('pmx-reference-mode');
    if(reference)reference.checked=localStorage.getItem('sakura_pmx_reference')==='true';
    if(!viewer)return;
    const quality=localStorage.getItem('sakura_render_quality');
    if(quality){viewer.setQuality(quality);updateQualityUI(viewer.quality);}
    viewer.physicsEnabled=localStorage.getItem('sakura_physics_enabled')!=='false';
    applyPhysicsStrength(Number(localStorage.getItem('sakura_physics_boost')||0),false);
    viewer.setWindStrength(Number(localStorage.getItem('sakura_physics_wind')||0));
    updatePhysicsUI(viewer.physics.mode);
}

function glitchFixStorageKey(modelPath) {
    return 'sakura_glitch_fix::' + (modelPath || 'local-file');
}

function updateGlitchFixUI() {
    const fixBtn = document.getElementById('glitch-fix-btn');
    const restoreBtn = document.getElementById('glitch-restore-btn');
    const status = document.getElementById('glitch-fix-status');
    if (!fixBtn || !restoreBtn) return;
    const glitch = viewer?.physicsInfo?.glitch;
    if (!viewer?.model || !glitch) {
        fixBtn.classList.add('hidden');
        restoreBtn.classList.add('hidden');
        if (status) status.textContent = '';
        return;
    }
    const active = Boolean(glitch.active);
    restoreBtn.classList.toggle('hidden', !active);
    fixBtn.classList.toggle('hidden', active);
    fixBtn.disabled = !active && !glitch.detected;
    fixBtn.textContent = glitch.detected ? `🧩 Exclude ${glitch.detected} pivots` : '🧩 No extra physics pivots';
    if (active) {
        const groups = glitch.groups || [];
        const summary = groups.length
            ? `${glitch.removed} duplicate-chain bones (${groups.slice(0, 3).map(g => `${g.name}×${g.removed + 1}`).join(', ')}${groups.length > 3 ? '…' : ''})` + (glitch.zeroLength ? ` and ${glitch.zeroLength} zero-length bones` : '')
            : `${glitch.removed} problem bones`;
        if (status) status.textContent = `Automatically excluded ${summary} from simulation on every load. Source bones and mesh stay intact; other physics keeps running.`;
        fixBtn.classList.add('hidden');
    } else if (glitch.detected) {
        if (status) status.textContent = `Detected ${glitch.detected} coincident duplicate physics pivots. They are excluded automatically on load; distinct hair/skirt chains remain active.`;
        fixBtn.classList.remove('hidden');
    } else {
        if (status) status.textContent = 'No coincident duplicate physics pivots detected in this model; all authored hair and skirt chains stay enabled.';
    }
}

function updatePhysicsUI(mode) {
    const diagnosis=document.getElementById('rig-analysis-status');
    if(diagnosis)diagnosis.textContent=viewer?.rigAnalysis?.status||'PMX physics is checked for eight seconds after loading. Diagnostic images stay on this device.';
    const repairBtn = document.getElementById('physics-repair-btn');
    if (repairBtn) repairBtn.disabled = !viewer?.model || !!viewer.vrm || !viewer.physicsInfo?.bones;
    mode = viewer?.physics?.mode || mode;
    document.querySelectorAll('[data-physics]').forEach(button => {
        const selected = button.dataset.physics === mode;
        button.classList.toggle('active', selected);
        button.setAttribute('aria-pressed', String(selected));
    });
    const status = document.getElementById('physics-status');
    if (!status) return;
    const info = viewer?.physicsInfo;
    const names = {off: 'Off', subtle: 'Subtle', normal: 'Normal', lively: 'Lively'};
    const strength = viewer?.physics?.strength ?? {off:0,subtle:.55,normal:1,lively:1.5}[mode] ?? 1;
    const boost = viewer?.physicsBoost ?? Math.max(0,(strength-1)*3);
    const wind = viewer?.physics?.windStrength || 0;
    const humanoidLabel = viewer?.humanoidInfo ? 'Humanoid rig verified · ' : '';
    const slider = document.getElementById('physics-strength');
    if(slider) {slider.value = Math.round(boost*100);slider.disabled = mode === 'off';}
    const enabled = document.getElementById('physics-enabled');
    if(enabled) enabled.checked = mode !== 'off';
    const windSlider = document.getElementById('physics-wind');
    if(windSlider) windSlider.value = Math.round(wind*100);
    const valueText = document.getElementById('physics-strength-value');
    if(valueText) valueText.textContent = mode === 'off' ? 'Off' : boost === 0 ? 'Natural (0%)' : `${Math.round(boost*100)}%`;
    const windText = document.getElementById('physics-wind-value');
    if(windText) windText.textContent = `${Math.round(wind*100)}%`;
    const label = mode === 'custom' ? boost === 0 ? 'Natural (0% boost)' : `Natural + ${Math.round(boost*100)}% boost` : names[mode] || 'Normal';
    if (info?.source === 'Live2D authored physics') {
        const authored = mode === 'off' ? 'Simulation paused' : 'Authored physics active';
        status.textContent = `${humanoidLabel}${authored} · ${info.chains} physics chains, ${info.bones} physics points · Cubism Physics · Mode: ${names[mode] || 'Normal'}`;
    } else if (!info || !info.bones || info.source === 'none') {
        status.textContent = `${humanoidLabel}No physics available · Strength: ${label} · 0 chains, 0 bones`;
    } else {
        const parts = Object.entries(info.categories || {})
            .sort((a, b) => b[1] - a[1]).map(([type, count]) => `${count} ${type}`).join(', ');
        status.textContent = `${humanoidLabel}Strength: ${label} · Wind: ${Math.round(wind*100)}% · ${info.engine || info.source} · ${info.rigidBodies || 0} rigid bodies, ${info.joints || 0} joints · ${info.chains} chains, ${info.bones} bones (${parts || 'unsorted'})${mode === 'off' ? ' · Simulation paused' : ''}${info.warning ? ' · '+info.warning : ''}`;
    }
}

function setTransparency(enabled, persist = true) {
    const on = Boolean(enabled);
    document.body.classList.toggle('transparent-mode', on);
    document.documentElement.classList.toggle('transparent-mode', on);
    if (persist) localStorage.setItem('sakura_transparency', String(on));
    if (bgToggleBtn) {
        bgToggleBtn.setAttribute('aria-pressed', String(on));
        bgToggleBtn.title = on
            ? 'Disable streaming transparency ('+(currentSettings.transparency_hotkey || 'Ctrl+Shift+T')+')'
            : 'Enable streaming transparency ('+(currentSettings.transparency_hotkey || 'Ctrl+Shift+T')+')';
    }
}

function startMicLevelMonitor() {
    stopMicLevelMonitor();
    const generation = micMonitorGeneration;
    // Desktop listening already owns the microphone. Reopening it from the
    // Settings meter can crash Qt WebEngine's media permission/capture path.
    if (document.body.classList.contains('desktop-companion')) {
        micMonitorInterval = setInterval(() => {
            const analyser = continuousMic.enabled ? continuousMic.analyser : null;
            let pct = 0;
            if (analyser) {
                const samples = new Float32Array(analyser.fftSize);
                analyser.getFloatTimeDomainData(samples);
                const rms = Math.sqrt(samples.reduce((sum, n) => sum + n * n, 0) / samples.length);
                pct = Math.min(100, Math.round(rms * 600));
            }
            if (micMeterFill) micMeterFill.style.width = `${pct}%`;
        }, 50);
        return;
    }
    if (!navigator.mediaDevices?.getUserMedia) return;
    const constraints = { audio: selectedMicId ? { deviceId: { exact: selectedMicId } } : true };
    navigator.mediaDevices.getUserMedia(constraints).then(stream => {
        if (generation !== micMonitorGeneration) { stream.getTracks().forEach(t => t.stop()); return; }
        micMonitorStream = stream;
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        micMonitorContext = audioCtx;
        const source = audioCtx.createMediaStreamSource(stream);
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 256;
        source.connect(analyser);
        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        micMonitorInterval = setInterval(() => {
            analyser.getByteFrequencyData(dataArray);
            const avg = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
            const pct = Math.min(Math.round((avg / 128) * 100), 100);
            if (micMeterFill) micMeterFill.style.width = `${pct}%`;
        }, 50);
    }).catch(() => {});
}

function stopMicLevelMonitor() {
    ++micMonitorGeneration;
    if (micMonitorInterval) { clearInterval(micMonitorInterval); micMonitorInterval = null; }
    if (micMonitorStream)   { micMonitorStream.getTracks().forEach(t => t.stop()); micMonitorStream = null; }
    if (micMonitorContext) { micMonitorContext.close().catch(() => {}); micMonitorContext = null; }
    if (micMeterFill)       micMeterFill.style.width = '0%';
}

async function playTestAudioTone() {
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (selectedSpeakerId && typeof audioCtx.setSinkId === 'function') {
        try { await audioCtx.setSinkId(selectedSpeakerId); } catch (_) {}
    }
    const osc  = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(523.25, audioCtx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(880.00, audioCtx.currentTime + 0.15);
    gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.5);
    osc.connect(gain); gain.connect(audioCtx.destination);
    osc.start(); osc.stop(audioCtx.currentTime + 0.5);
}

// ─────────────────────────── Chat & AI ───────────────────────────
async function handleSendMessage() {
    if (trackingOnly) return;
    const text = chatInput.value.trim();
    if (!text) return;
    chatBusy = true;
    await voiceSaveQueue;
    const generation = ++chatReplyGeneration;
    replyController?.abort();
    const controller = new AbortController();
    replyController = controller;
    lipSync?.stop();
    chatInput.value = '';
    addMessage(text, 'user');
    showTypingIndicator();
    viewer?.setActivity('thinking');

    try {
        const screenImage = await screenShare.snapshot();
        const appearanceQuestion = /\b(?:your|ur|hair|eyes?|clothes|outfit|avatar|appearance|that girl)\b|बाल|आँख|कपड़े/iu.test(text);
        const avatarImage = screenImage && appearanceQuestion ? viewer?.captureAvatar() : null;
        if (generation !== chatReplyGeneration) return;
        const res  = await fetch('/api/chat', {
            signal: controller.signal,
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, defer_audio: true, avatar_can_dance:!!viewer?.dance?.supported(), ...(screenImage ? { screen_image: screenImage } : {}), ...(avatarImage ? { avatar_image: avatarImage } : {}) }),
        });
        const data = await res.json();
        if (data.reply) {
            let presented = false;
            const presentReply = () => {
                if (presented) return;
                presented = true;
                addMessage(data.reply, 'sakura');
                if (generation === chatReplyGeneration) {
                    removeTypingIndicator();
                    viewer?.setEmotionFromText(data.reply);
                    if (!lipSync?.isPlaying) viewer?.setActivity('idle');
                    if (chatPanel.classList.contains('minimized')) showSpeechBubble(data.reply);
                }
            };
            if (generation !== chatReplyGeneration) return;
            if(data.avatar_motion==='stop')viewer?.dance?.stop();
            else if(['groove','step','wave'].includes(data.avatar_motion))viewer?.dance?.start(data.avatar_motion);
            // Text and companion expression should not wait for the first
            // Edge-TTS network response. Speech starts as soon as its first
            // short phrase arrives below.
            presentReply();
            const indicator = document.getElementById('typing-indicator');
            if (indicator) indicator.textContent = 'Preparing voice…';
            try {
                await speakPhrases(data.reply, async text => {
                    const response = await fetch('/api/tts/speak', {
                        signal: controller.signal,
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ text }),
                    });
                    const speech = await response.json();
                    if (!response.ok) throw new Error(speech.error || 'Speech is unavailable.');
                    return speech.audio;
                }, async (audio, first) => {
                    if (audio) await lipSync.playWithLipSync(audio, first ? presentReply : undefined);
                    else if (first) presentReply();
                }, () => generation === chatReplyGeneration);
            } catch (err) {
                if (generation !== chatReplyGeneration) return;
                presentReply();
                if (generation === chatReplyGeneration) addMessage(`⚠️ Speech unavailable: ${err.message}`, 'sakura');
            }
            if (generation === chatReplyGeneration) hideSpeechBubble();
        } else if (data.error) {
            if (generation === chatReplyGeneration) removeTypingIndicator();
            addMessage(`⚠️ Error: ${data.error}`, 'sakura');
        }
    } catch (err) {
        removeTypingIndicator();
        if (generation === chatReplyGeneration && err.name !== 'AbortError') addMessage(`⚠️ ${err.message || 'Could not connect to the backend server.'}`, 'sakura');
    } finally {
        if (generation === chatReplyGeneration) chatBusy = false;
        if (generation === chatReplyGeneration && !lipSync?.isPlaying) viewer?.setActivity('idle');
    }
}

async function leaveGameMode() {
    const wasActive = gameActive;
    gameActive = false;
    gameReady = false;
    reactionsEnabled = false;
    screenReactBtn.textContent = '💬 Reactions off';
    screenReactBtn.setAttribute('aria-pressed', 'false');
    if (gameStartedScreen) screenShare.stop();
    gameStartedScreen = false;
    const resume = gameResumeMic;
    gameResumeMic = false;
    if (resume) await startDesktopListening();
    if (!wasActive) return;
    try {
        const response = await fetch('/api/settings', {method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({llm_provider: 'ollama', ollama_model: 'qwen3-vl:4b-instruct',
                ollama_models_folder: currentSettings.ollama_models_folder || 'llm-models', ollama_context: 2048})});
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Could not restore Qwen 4B.');
        currentSettings = data.settings;
        applySettingsUI(currentSettings);
        listeningStatus.textContent = 'Game mode ended · Qwen 4B restored';
    } catch (error) { listeningStatus.textContent = `Game mode: ${error.message}`; }
}

async function checkGameMode() {
    if (trackingOnly) return;
    if (!autoGameEnabled || autoGameBusy || !window.pywebview?.api?.game_status) return;
    autoGameBusy = true;
    try {
        const game = await window.pywebview.api.game_status();
        if (!autoGameEnabled) return;
        gameForeground = !!game.foreground;
        if (!game.detected) {
            if (gameActive) {
                await leaveGameMode();
            }
            return;
        }
        lastGameSeen = Date.now();
        if (!gameActive) {
            gameResumeMic = continuousMic.enabled;
            gameActive = true;
            continuousMic.stop();
            lastMicActivity = 0;
            listeningStatus.textContent = `Game detected: ${game.name} · mic paused · preparing Qwen 2B`;
        }
        if (gameReady || chatBusy || reactionBusy || lipSync?.isPlaying) return;
        const response = await fetch('/api/settings', { method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({llm_provider: 'ollama', ollama_model: 'qwen3-vl:2b-instruct', ollama_models_folder: currentSettings.ollama_models_folder || 'llm-models', ollama_context: 2048}) });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Could not select Qwen 2B.');
        currentSettings = data.settings;
        applySettingsUI(currentSettings);
        if (!autoGameEnabled) return;
        if (!screenShare.enabled) { await screenShare.toggle(); gameStartedScreen = screenShare.enabled; }
        if (!screenShare.enabled) throw new Error('Screen access was not enabled.');
        if (!autoGameEnabled) return;
        gameReady = true;
        reactionsEnabled = true;
        screenReactBtn.textContent = '💬 Reactions on';
        screenReactBtn.setAttribute('aria-pressed', 'true');
        listeningStatus.textContent = `Game detected: ${game.name} · Qwen 2B · mic paused · live frame checks`;
    } catch (error) { listeningStatus.textContent = `Game mode: ${error.message}`; }
    finally { autoGameBusy = false; }
}

async function pollVtuberChat() {
    if (trackingOnly) return;
    if (!vtuberEnabled || vtuberPollBusy) return;
    vtuberPollBusy = true;
    const session = vtuberGeneration;
    try {
        const response = await fetch('/api/vtuber/messages');
        const data = await response.json();
        if (!response.ok || !vtuberEnabled || session !== vtuberGeneration) return;
        document.getElementById('vtuber-status').textContent = data.status;
        vtuberQueue.push(...(data.messages || []));
        vtuberQueue = vtuberQueue.filter(item => Date.now() - item.timestamp < 90000).slice(-20);
        if (!document.getElementById('vtuber-chat-enabled').checked || chatBusy || reactionBusy || isRecording || lipSync?.isPlaying || Date.now() - lastMicActivity < 6000 || Date.now() - lastCoHostSpeech < 20000) return;
        const index = vtuberQueue.findIndex(item => /sakura|\?|？/i.test(item.text));
        const message = index >= 0 ? vtuberQueue.splice(index, 1)[0] : vtuberQueue.pop();
        if (!message || message.text.toLowerCase().trim() === lastViewerReply) return;
        lastViewerReply = message.text.toLowerCase().trim();
        reactionBusy = true;
        vtuberSpeaking = true;
        const replyGeneration = chatReplyGeneration;
        const current = () => vtuberEnabled && session === vtuberGeneration && replyGeneration === chatReplyGeneration;
        let resumeMic = false;
        try {
            const replyResponse = await fetch('/api/vtuber/reply', {method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({author: message.author, text: message.text})});
            const result = await replyResponse.json();
            if (!replyResponse.ok) throw new Error(result.error);
            if (!current() || !result.reply || result.reply.trim() === '[QUIET]') return;
            addMessage(`${message.author}: ${message.text}`, 'user');
            addMessage(result.reply, 'sakura');
            resumeMic = continuousMic.enabled;
            if (resumeMic) continuousMic.stop();
            await speakPhrases(result.reply, async text => {
                const audioResponse = await fetch('/api/tts/speak', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text})});
                const speech = await audioResponse.json();
                if (!audioResponse.ok) throw new Error(speech.error);
                return speech.audio;
            }, async audio => {
                showSpeechBubble(result.reply);
                viewer?.setEmotionFromText(result.reply);
                if (audio) await lipSync.playWithLipSync(audio);
            }, current);
        } finally {
            lastCoHostSpeech = Date.now();
            vtuberSpeaking = false;
            reactionBusy = false;
            hideSpeechBubble();
            if (resumeMic) await startDesktopListening();
        }
    } catch (error) { document.getElementById('vtuber-status').textContent = error.message; }
    finally { vtuberPollBusy = false; }
}

async function reactToScreen(initialCheck = false) {
    if (trackingOnly) return;
    const vtuberScreens = vtuberEnabled && document.getElementById('vtuber-screen-enabled').checked;
    if (!initialCheck && Date.now() - lastCoHostSpeech < (gameActive ? 30000 : 20000)) return;
    if (!initialCheck && autoGameEnabled && gameActive && !gameForeground) return;
    if ((!reactionsEnabled && !vtuberScreens && !initialCheck) || !screenShare.enabled || reactionBusy || chatBusy || isRecording ||
        lipSync?.isPlaying || (!initialCheck && Date.now() - lastMicActivity < 6000)) return;
    reactionBusy = true;
    const generation = chatReplyGeneration;
    let resumeMic = false;
    let expressionStarted=false;
    try {
        const screen_image = await screenShare.snapshot();
        const response = await fetch('/api/chat', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({text: 'Screen companion reaction', screen_image, screen_reaction: true, screen_check: initialCheck, ai_vtuber: vtuberScreens, defer_audio: true}),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Screen viewing is unavailable.');
        if (!data.reply || data.reply.trim() === '[QUIET]' || generation !== chatReplyGeneration ||
            (!reactionsEnabled && !vtuberScreens && !initialCheck) || !screenShare.enabled || chatBusy || (!initialCheck && Date.now() - lastMicActivity < 6000)) return;
        const normalizedReaction = data.reply.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '');
        if (!initialCheck && normalizedReaction === lastReactionText) return;
        lastReactionText = normalizedReaction;
        listeningStatus.textContent = 'Screen vision connected · snapshot understood';
        addMessage(data.reply, 'sakura');
        resumeMic = continuousMic.enabled;
        if (resumeMic) continuousMic.stop();
        await speakPhrases(data.reply, async text => {
            const res = await fetch('/api/tts/speak', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text})});
            const speech = await res.json();
            if (!res.ok) throw new Error(speech.error || 'Speech unavailable.');
            return speech.audio;
        }, async audio => {
            showSpeechBubble(data.reply);
            viewer?.setEmotionFromText(data.reply);
            if(!expressionStarted&&reactionsEnabled&&!trackingOnly&&!viewer?.vtuberTrackingMode){
                viewer?.reactionExpressions?.begin(data.reply);expressionStarted=true;
            }
            if (audio) await lipSync.playWithLipSync(audio);
        }, () => (reactionsEnabled || (vtuberEnabled && document.getElementById('vtuber-screen-enabled').checked) || initialCheck) && screenShare.enabled && generation === chatReplyGeneration);
    } catch (err) {
        listeningStatus.textContent = `Screen reactions: ${err.message}`;
    } finally {
        reactionBusy = false;
        if(expressionStarted)viewer?.reactionExpressions?.stop();
        lastCoHostSpeech = Date.now();
        hideSpeechBubble();
        if (resumeMic) await startDesktopListening();
    }
}

function showSpeechBubble(text) {
    speechBubbleText.textContent = text;
    speechBubble.classList.remove('hidden');
}
function hideSpeechBubble() { speechBubble.classList.add('hidden'); }

async function handleClearChat() {
    try {
        document.getElementById('interrupt-btn').click();
        const response = await fetch('/api/clear', { method: 'POST' });
        if (!response.ok) throw new Error('Could not clear memory. Please try again.');
        messagesEl.innerHTML = '';
        addMessage('🌸 Memory cleared! What would you like to talk about next?', 'sakura');
    } catch (err) { addMessage(err.message, 'sakura'); }
}

// ─────────────────────────── Voice / STT ───────────────────────────
async function handleToggleMic() {
    if (!isRecording) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: selectedMicId ? { deviceId: { exact: selectedMicId } } : true,
            });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];
            mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };
            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                stream.getTracks().forEach(t => t.stop());
                await sendAudioForSTT(audioBlob);
            };
            mediaRecorder.start();
            isRecording = true;
            micBtn.classList.add('recording');
        } catch (err) { alert('Could not access microphone: ' + err.message); }
    } else {
        if (mediaRecorder?.state !== 'inactive') mediaRecorder.stop();
        isRecording = false;
        micBtn.classList.remove('recording');
    }
}

function extractWakeCommand(raw, phrase) {
    const words = phrase.trim().split(/[^\p{L}\p{N}]+/u).filter(Boolean);
    if (!words.length) return null;
    const escape = text => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const pattern = new RegExp('(?:^|[^\\p{L}\\p{N}])' + words.map(escape).join('[^\\p{L}\\p{N}]+') + '(?=$|[^\\p{L}\\p{N}])', 'iu');
    const match = pattern.exec(raw);
    return match ? raw.slice(match.index + match[0].length).replace(/^[,\s.!?]+/, '').trim() : null;
}

async function sendAudioForSTT(blob, options = {}) {
    if (trackingOnly) return;
    const continuous = options.continuous === true;
    showTypingIndicator();
    const formData = new FormData();
    formData.append('audio', blob, 'speech.webm');
    try {
        const res  = await fetch('/api/stt', { method: 'POST', body: formData });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || `Speech recognition failed (${res.status})`);
        removeTypingIndicator();
        if (data.text?.trim()) {
            const raw = data.text.trim();
            if (currentSettings.wake_word_enabled) {
                const query = extractWakeCommand(raw, currentSettings.wake_word || '');
                if (query !== null) {
                    if (!query) {
                        wakeCommandDeadline = Date.now() + 15000;
                        listeningStatus.textContent = 'Ready—say your command';
                        return;
                    }
                    wakeCommandDeadline = 0;
                    chatInput.value = query;
                    await handleSendMessage();
                } else if (continuous && Date.now() < wakeCommandDeadline) {
                    wakeCommandDeadline = 0;
                    chatInput.value = raw;
                    await handleSendMessage();
                } else if (!continuous) {
                    addMessage(`*(Wake word "${currentSettings.wake_word}" not heard — say it first)*`, 'sakura');
                }
            } else {
                chatInput.value = raw;
                await handleSendMessage();
            }
        } else if (!continuous) {
            addMessage('*(I could not hear a clear phrase. Check the selected microphone, then hold the mic button while speaking.)*', 'sakura');
        }
    } catch (err) {
        removeTypingIndicator();
        addMessage(`⚠️ Speech recognition failed: ${err.message}`, 'sakura');
        console.error('STT failed:', err);
    }
}

// ─────────────────────────── UI Helpers ───────────────────────────
function addMessage(text, sender) {
    const msg = document.createElement('div');
    msg.className = `message ${sender}`;
    msg.textContent = text;
    messagesEl.appendChild(msg);
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

function showTypingIndicator() {
    removeTypingIndicator();
    const typing = document.createElement('div');
    typing.id = 'typing-indicator';
    typing.className = 'message sakura typing';
    typing.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';
    messagesEl.appendChild(typing);
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

function removeTypingIndicator() {
    document.getElementById('typing-indicator')?.remove();
}

async function checkStatus() {
    try {
        const res  = await fetch('/api/status');
        const data = await res.json();
        if (data.ok) {
            statusDot.classList.remove('offline');
            statusDot.title = `${data.provider === 'gemini' ? 'Gemini configured' : 'Ollama online'} (${data.model})`;
        } else {
            statusDot.classList.add('offline');
            statusDot.title = data.provider === 'gemini' ? 'Gemini key is missing' : 'Ollama or model offline';
        }
    } catch (_) {
        statusDot.classList.add('offline');
        statusDot.title = 'Backend Offline';
    }
}

function flashMsg(el, msg, durationMs = 3000) {
    if (!el) return;
    el.textContent = msg;
    setTimeout(() => { if (el) el.textContent = ''; }, durationMs);
}

function setupAvatarTracking() {
    const modal = document.getElementById('tracking-modal');
    const status = document.getElementById('tracking-status');
    const start = document.getElementById('tracking-start');
    const stop = document.getElementById('tracking-stop');
    const camera = document.getElementById('tracking-camera');
    const settingsCamera = document.getElementById('settings-tracking-camera');
    const cameraStatus = document.getElementById('settings-camera-status');
    const bgEnabled = document.getElementById('obs-background-enabled');
    const bgColor = document.getElementById('obs-background-color');
    bgEnabled.checked = localStorage.getItem('sakura_obs_background_enabled') === 'true';
    const storedColor = localStorage.getItem('sakura_obs_background_color');
    if (/^#[0-9a-f]{6}$/i.test(storedColor || '')) bgColor.value = storedColor;
    const applyObsBackground = () => {
        document.body.classList.toggle('obs-solid-background', bgEnabled.checked);
        document.body.style.setProperty('--obs-background-color', bgColor.value);
        document.getElementById('obs-background-value').textContent = bgColor.value;
        localStorage.setItem('sakura_obs_background_enabled', String(bgEnabled.checked));
        localStorage.setItem('sakura_obs_background_color', bgColor.value);
    };
    bgEnabled.addEventListener('change', applyObsBackground);
    bgColor.addEventListener('input', applyObsBackground);
    document.getElementById('obs-green-screen').addEventListener('click', () => {
        bgColor.value = '#00ff00'; bgEnabled.checked = true; applyObsBackground();
    });
    applyObsBackground();
    const handsToggle = document.getElementById('tracking-hands-enabled');
    const mode = document.getElementById('tracking-mode-btn');
    const aiControls = ['vtuber-mode-btn', 'auto-game-btn', 'screen-view-btn', 'screen-react-btn',
        'continuous-mic-btn', 'mic-btn', 'send-btn'];
    let switching = false, resumeMic = false;
    avatarTracking = new AvatarTracking(viewer, message => { status.textContent = message; cameraStatus.textContent = message; });
    const voiceChangerToggle = document.getElementById('vtuber-rvc-changer-toggle');
    const voiceChangerStatus = document.getElementById('vtuber-rvc-changer-status');
    document.getElementById('rvc-loading-close')?.addEventListener('click', () => {
        document.getElementById('rvc-loading-modal')?.classList.add('hidden');
    });
    voiceChangerToggle.checked = false;
    voiceChangerToggle.addEventListener('change', async () => {
        if (!voiceChangerToggle.checked) {
            await stopVtuberVoiceChanger();
            return;
        }
        if (!trackingOnly) {
            await stopVtuberVoiceChanger('Enter VTuber mode before enabling the RVC voice changer.');
            return;
        }
        const selectedRvc = allRvcModels.find(model => model.id === currentVoiceId);
        const selectedBuiltin = allVoicePresets.find(voice => voice.id === currentVoiceId);
        if (!selectedRvc && !selectedBuiltin) {
            await stopVtuberVoiceChanger('Select a built-in or [RVC] voice from the top voice selector first.');
            return;
        }
        voiceChangerStatus.textContent = selectedRvc ? 'Preparing RVC microphone voice…' : 'Starting built-in microphone voice…';
        try {
            await voiceSaveQueue;
            if (currentSettings?.selected_voice !== currentVoiceId ||
                    (selectedRvc && currentSettings?.rvc_model !== selectedRvc.pth)) {
                await stopVtuberVoiceChanger('Voice selection was not saved. Check the voice error, select the voice again, and retry.');
                return;
            }
            if (selectedRvc) await prepareVtuberRvcVoice();
            await window.sakuraModelSettings?.stopMicrophone();
            await rvcVoiceChanger.start(selectedMicId);
            viewer.voiceChangerActive=true;
            viewer?.setTrackingMouthEnabled(false);
        } catch (error) {
            await stopVtuberVoiceChanger(`Could not start microphone voice mode: ${error.message}`);
        }
    });
    const trackingDefaults = {smoothing:.25, range:1, handRange:1.3, blinkGain:1, gaze:1, linkBlinks:false, fps:15};
    let trackingOptions;
    try { trackingOptions = {...trackingDefaults, ...JSON.parse(localStorage.getItem('sakura_tracking_options') || '{}')}; }
    catch (_) { trackingOptions = {...trackingDefaults}; }
    const trackingSliders = {'tracking-smoothing':'smoothing', 'tracking-range':'range', 'tracking-hand-range':'handRange',
        'tracking-blink-gain':'blinkGain', 'tracking-gaze-strength':'gaze'};
    const applyTrackingOptions = () => {
        viewer.trackingOptions = trackingOptions;
        avatarTracking.frameRate = [15,24,30].includes(Number(trackingOptions.fps)) ? Number(trackingOptions.fps) : 15;
        for (const [id,key] of Object.entries(trackingSliders)) {
            const control = document.getElementById(id);
            control.value = Number(trackingOptions[key])*100;
            control.title = `${control.value}%`;
        }
        document.getElementById('tracking-link-blinks').checked = !!trackingOptions.linkBlinks;
        document.getElementById('tracking-glasses').checked=!!trackingOptions.glasses;
        document.getElementById('tracking-fps').value = avatarTracking.frameRate;
        document.getElementById('tracking-hand-range-value').textContent = `${Math.round(trackingOptions.handRange*100)}%`;
        localStorage.setItem('sakura_tracking_options', JSON.stringify(trackingOptions));
    };
    for (const [id,key] of Object.entries(trackingSliders)) {
        document.getElementById(id).addEventListener('input', e => {
            trackingOptions[key] = Number(e.target.value)/100; applyTrackingOptions();
        });
    }
    document.getElementById('tracking-link-blinks').addEventListener('change', e => {
        trackingOptions.linkBlinks = e.target.checked; applyTrackingOptions();
    });
    document.getElementById('tracking-glasses').addEventListener('change',e=>{
        trackingOptions.glasses=e.target.checked;applyTrackingOptions();avatarTracking.calibrate();
    });
    const restartTracking = () => { if (avatarTracking.enabled) { avatarTracking.stop(); start.click(); } };
    document.getElementById('tracking-fps').addEventListener('change', e => {
        trackingOptions.fps = Number(e.target.value); applyTrackingOptions(); restartTracking();
    });
    document.getElementById('tracking-reset-options').addEventListener('click', () => {
        trackingOptions = {...trackingDefaults}; applyTrackingOptions(); restartTracking();
    });
    applyTrackingOptions();
    try { handsToggle.checked = localStorage.getItem('sakura_hand_tracking_enabled') !== 'false'; } catch (_) {}
    avatarTracking.setHandTracking(handsToggle.checked);
    window.addEventListener('sakura-physics-status-changed',()=>updatePhysicsUI(viewer?.physics?.mode));
    const reader = new ChatReader({
        onEnabled: enabled => { if (viewer) viewer.chatReaderActive = enabled; },
        status: message => { status.textContent = message; },
        stopAudio: () => lipSync?.stop(),
        play: audio => lipSync.playWithLipSync(audio, null, {volume:Number(document.getElementById('reader-volume').value)/100}),
        speak: async (text, signal) => {
            await voiceSaveQueue;
            const readerVoiceKey=currentVoiceId+':'+voiceSelectionGeneration;
            if (currentVoiceId.startsWith('rvc_') && readerRvcVoice !== readerVoiceKey) {
                await prepareVtuberRvcVoice();
                readerRvcVoice = readerVoiceKey;
            }
            if (signal.aborted) return null;
            const response = await fetch('/api/chat-reader/speak', {method:'POST', signal,
                headers:{'Content-Type':'application/json'}, body:JSON.stringify({text})});
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Speech is unavailable.');
            return data.audio;
        },
    });
    let readerRvcVoice = '';
    const readerVolume=document.getElementById('reader-volume');
    readerVolume.value=localStorage.getItem('sakura_reader_volume')??100;
    const volumeLabel=()=>document.getElementById('reader-volume-value').textContent=readerVolume.value+'%';
    volumeLabel();
    readerVolume.oninput=()=>{volumeLabel();localStorage.setItem('sakura_reader_volume',readerVolume.value);if(reader.enabled)lipSync?.setPlaybackVolume(Number(readerVolume.value)/100);};
    const readerVoice=document.getElementById('reader-voice');
    readerVoice.onchange=async()=>{
        await applyVoiceById(readerVoice.value);readerVoice.value=currentVoiceId;
        if(reader.enabled&&currentVoiceId.startsWith('rvc_')){try{await prepareVtuberRvcVoice();readerRvcVoice=currentVoiceId+':'+voiceSelectionGeneration;}catch(error){status.textContent=error.message;}}
    };
    let readerPolling = false;
    const stopReader = async () => {
        reader.stop();
        readerRvcVoice='';
        await fetch('/api/vtuber/disconnect', {method:'POST'}).catch(()=>{});
    };
    document.getElementById('chat-reader-start').addEventListener('click', async () => {
        if (switching) return;
        switching = true;
        try {
            await stopVtuberVoiceChanger();
            avatarTracking.stop(); await stopReader();
            viewer.setVtuberTrackingMode(true);
            continuousMic.stop(); setUI(true);
            ++chatReplyGeneration; replyController?.abort();
            vtuberEnabled=false; ++vtuberGeneration; vtuberQueue=[];
            reactionsEnabled=false; autoGameEnabled=false;
            if (screenShare.enabled) await screenShare.toggle();
            const paused = await fetch('/api/tracking/mode', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:true})});
            const pauseData = await paused.json();
            if (!paused.ok) throw new Error(pauseData.error);
            const response = await fetch('/api/chat-reader/connect', {method:'POST', headers:{'Content-Type':'application/json'},
                body:JSON.stringify({link:document.getElementById('reader-chat-link').value.trim()})});
            const data = await response.json();
            if (!response.ok) throw new Error(data.error);
            reader.start(); status.textContent='Chat Reader on · camera off · waiting for YouTube chat';
        } catch(error) { status.textContent=error.message; }
        finally { switching=false; }
    });
    document.getElementById('chat-reader-stop').addEventListener('click', async () => {
        await stopReader(); status.textContent='Chat Reader off · AI remains paused';
    });
    const readerTimer = setInterval(async () => {
        if (!reader.enabled || readerPolling) return;
        readerPolling=true; const generation=reader.generation;
        try {
            const response=await fetch('/api/vtuber/messages'); const data=await response.json();
            if (generation !== reader.generation || !reader.enabled) return;
            if (!response.ok) throw new Error(data.error || 'Chat disconnected.');
            if (!reader.queue.length && reader.running == null) status.textContent=data.status;
            reader.enqueue(data.messages || []);
        } catch(error) { if (generation===reader.generation) status.textContent=error.message; }
        finally { readerPolling=false; }
    }, 2500);
    window.addEventListener('pagehide',()=> {clearInterval(readerTimer); reader.stop(); avatarTracking.stop();});
    const refreshCameras = async () => {
        const selected = camera.value || localStorage.getItem('sakura_tracking_camera') || '';
        const devices = await navigator.mediaDevices?.enumerateDevices() || [];
        camera.replaceChildren(new Option('Default camera', ''));
        devices.filter(d=>d.kind==='videoinput').forEach((d,i)=>camera.add(new Option(d.label || `Camera ${i+1}`,d.deviceId)));
        camera.value = selected;
        settingsCamera.replaceChildren(...Array.from(camera.options, option => new Option(option.text, option.value)));
        settingsCamera.value = camera.value;
        if (camera.value) try { localStorage.setItem('sakura_tracking_camera', camera.value); } catch (_) {}
    };
    document.getElementById('settings-refresh-cameras').addEventListener('click', () => {
        refreshCameras().catch(error => { cameraStatus.textContent = error.message; });
    });
    installBroadcastCamera({refresh:refreshCameras,select:settingsCamera,status:cameraStatus,open:()=>window.pywebview?.api.open_nvidia_broadcast()});
    const sdkFolder=document.getElementById('nvidia-sdk-folder'),sdkStatus=document.getElementById('nvidia-sdk-status');
    sdkFolder.value=currentSettings.nvidia_ar_sdk_folder||'';
    document.getElementById('nvidia-sdk-browse').onclick=async()=>{const path=await window.pywebview?.api.choose_nvidia_sdk_folder();if(path)sdkFolder.value=path;};
    document.getElementById('nvidia-sdk-check').onclick=async()=>{
        try{
            const saved=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({nvidia_ar_sdk_folder:sdkFolder.value.trim()})});if(!saved.ok)throw Error('Could not save SDK folder.');
            const response=await fetch('/api/tracking/nvidia-sdk');const data=await response.json();if(!response.ok)throw Error(data.error||'SDK check failed');sdkStatus.textContent=data.message;
        }catch(error){sdkStatus.textContent=error.message;}
    };
    settingsCamera.addEventListener('change', () => {
        camera.value = settingsCamera.value;
        camera.dispatchEvent(new Event('change'));
        cameraStatus.textContent = 'Camera selected. Press Start tracking to use it.';
        if (avatarTracking.enabled) { avatarTracking.stop(); start.click(); }
    });
    document.getElementById('settings-start-tracking').addEventListener('click', () => start.click());
    document.getElementById('settings-stop-tracking').addEventListener('click', () => { stop.click(); cameraStatus.textContent = status.textContent; });
    document.getElementById('settings-calibrate-tracking').addEventListener('click', () => { document.getElementById('tracking-calibrate').click(); cameraStatus.textContent = status.textContent; });
    const setUI = enabled => {
        trackingOnly = enabled;
        document.body.classList.toggle('tracking-only', enabled);
        if (!enabled && rvcVoiceChanger?.active) void stopVtuberVoiceChanger();
        document.querySelector('.brand .badge').textContent = enabled ? 'VTuber' : 'Companion';
        winMinBtn.title = enabled ? 'Minimize to taskbar' : document.body.classList.contains('native-library') ? 'Shrink to desktop companion' : 'Minimize to taskbar';
        if (enabled && window.pywebview?.api?.set_library_mode) {
            window.pywebview.api.set_library_mode(true).catch(error => console.warn('VTuber window mode:', error));
        }
        mode.textContent = enabled ? 'VTuber on' : 'VTuber';
        for (const id of aiControls) document.getElementById(id).disabled = enabled;
        document.getElementById('vtuber-mode-btn').hidden = enabled;
        document.getElementById('chat-reader-mode-btn').hidden = !enabled;
        document.getElementById('vtuber-start-btn').disabled = enabled;
    };
    mode.addEventListener('click', async () => {
        modal.classList.remove('hidden');
        try { await refreshCameras(); } catch (error) { status.textContent = error.message; }
    });
    document.getElementById('chat-reader-mode-btn').addEventListener('click',()=> {
        readerVoice.replaceChildren(...Array.from(voiceQuickSelect.options,option=>new Option(option.text,option.value)));
        readerVoice.value=currentVoiceId;
        modal.classList.remove('hidden'); document.getElementById('reader-chat-link').focus();
    });
    document.getElementById('close-tracking-modal').addEventListener('click',()=>modal.classList.add('hidden'));
    document.getElementById('tracking-mirror').addEventListener('change',e=>{ viewer.userTrackingMirror=e.target.checked; });
    camera.addEventListener('change',e=>{ settingsCamera.value = e.target.value; try { localStorage.setItem('sakura_tracking_camera', e.target.value); } catch (_) {} });
    handsToggle.addEventListener('change', e => {
        const enabled = e.target.checked;
        avatarTracking.setHandTracking(enabled);
        try { localStorage.setItem('sakura_hand_tracking_enabled', String(enabled)); } catch (_) {}
        if (avatarTracking.enabled) status.textContent = enabled
            ? 'Body tracking on · shoulders, arms, hands and fingers follow you'
            : 'Body tracking off · face and head tracking remain on';
    });
    document.getElementById('tracking-calibrate').addEventListener('click',()=> {
        if (!avatarTracking.enabled) { status.textContent = 'Start tracking before calibration.'; return; }
        avatarTracking.calibrate();
        status.textContent = 'Neutral head and hand pose calibrated.';
    });
    start.addEventListener('click',async()=> {
        if(switching || avatarTracking.enabled) return;
        if(!viewer?.model || (!viewer.animationBones.head && !viewer.vrm && !viewer.live2d)) {
            status.textContent = 'Choose a Live2D model or rigged PMX/VRM character first.'; return;
        }
        switching=true; start.disabled=true; stop.disabled=true;
        resumeMic=continuousMic.enabled;
        viewer.setVtuberTrackingMode(true);
        setUI(true);
        ++chatReplyGeneration; replyController?.abort(); lipSync?.stop();
        continuousMic.stop();
        vtuberEnabled=false; ++vtuberGeneration; vtuberQueue=[];
        reactionsEnabled=false; autoGameEnabled=false; gameActive=false; gameReady=false;
        document.getElementById('vtuber-mode-btn').textContent='AI VTuber';
        document.getElementById('auto-game-btn').textContent='🎮 Auto game off';
        screenReactBtn.textContent='💬 Reactions off';
        if(screenShare.enabled) await screenShare.toggle();
        status.textContent='Unloading chat AI and speech models…';
        try {
            await stopReader();
            const response=await fetch('/api/tracking/mode',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:true})});
            const data=await response.json();
            if(!response.ok) throw new Error(data.error);
            viewer.userTrackingMirror=document.getElementById('tracking-mirror').checked;
            await avatarTracking.start(camera.value);
            await refreshCameras();
        } catch(error) {
            // Stay AI-paused when camera initialization fails. The user can
            // retry or explicitly restore AI; never silently reload Qwen.
            status.textContent=error.message;
        } finally { switching=false; start.disabled=false; stop.disabled=false; }
    });
    stop.addEventListener('click',()=> {
        if(switching) return;
        avatarTracking.stop();
        status.textContent='Tracking off · AI remains paused';
    });
    document.getElementById('tracking-restore-ai').addEventListener('click',async()=> {
        if(switching) return;
        switching=true; start.disabled=true; stop.disabled=true;
        await stopVtuberVoiceChanger();
        avatarTracking.stop();
        await stopReader();
        status.textContent='Restoring assistant mode…';
        try {
            const response=await fetch('/api/tracking/mode',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:false})});
            const data=await response.json();
            if(!response.ok) throw new Error(data.error || 'Could not restore AI.');
            viewer.setVtuberTrackingMode(false);
            setUI(false); status.textContent='Tracking off · assistant restored';
            if(resumeMic && document.body.classList.contains('desktop-companion')) await startDesktopListening();
        } catch(error) { status.textContent=error.message; }
        finally { switching=false; start.disabled=false; stop.disabled=false; }
    });
    // A second window must honor the backend's AI-free mode too.
    fetch('/api/tracking/mode').then(r=>r.json()).then(data=> {
        if(data.tracking_only) {
            continuousMic.stop(); setUI(true);
            reactionsEnabled=false; autoGameEnabled=false; vtuberEnabled=false;
            status.textContent='AI paused · choose your camera and start face, shoulder and arm tracking';
            if(data.startup_mode === 'vtuber') {
                viewer.setVtuberTrackingMode(true);
                document.getElementById('tracking-restore-ai').hidden = true;
                modal.classList.remove('hidden');
                refreshCameras().catch(error=>{status.textContent=error.message;});
            }
        }
    }).catch(()=>{});
}

async function save_setting_silent(data) {
    try {
        await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
    } catch (_) {}
}



