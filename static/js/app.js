import {installPersonalControls} from './personal-feature-controls.js?v=2';
import {wakeCommand} from './sleep-state.js?v=1';
import {installCameraStyleControls} from './camera-style-controls.js?v=1';
import {installCompanionRoom} from './companion-room.js?v=wake-walk4';
import {installCompactCompanionControls} from './compact-companion-controls.js?v=mic-resize1103';
import {installStageItems} from './stage-items.js?v=scenery1028';
import { appendEvidence } from './response-evidence.js?v=medium103';
import {installChatAttachments} from './chat-attachments.js?v=context106';
import {installSystemTools} from './system-tools.js?v=live-count94';
import {installLocalModelManager,updateLocalModelChoices} from './local-model-manager.js?v=native-choice137';
installLocalModelManager();
installSystemTools();
document.getElementById('open-agent-panel')?.addEventListener('click',async()=>{
    const status=document.getElementById('agent-panel-status');
    status.textContent='Opening Agent mode in Sakura Companion…';
    window.sakuraSetAgentMode?.(true);
});
import {installCompanionToolbar} from './companion-toolbar.js?v=1';
import {updateAppBrand} from './app-branding.js?v=branding79';
import {playGameLaughter} from './game-laughter.js?v=fbx89';
import {installButtonFeedback} from './button-feedback.js?v=phone-touch73';
installButtonFeedback();
import {finishStartupPresentation} from './startup-presentation.js?v=startup106';
import {installScreenAudio} from './screen-audio.js?v=media90';
import {installSpoutControls} from './spout-output.js?v=instances152';
import {installVirtualCamera} from './virtual-camera.js?v=sakura3';
import {installMobileLink} from './mobile-link.js?v=camera-style1103';
import {installCameraPreview} from './camera-preview.js?v=1';
import CompanionCamera, {CompanionCameraModes} from './companion-camera.js?v=phone-modes108';
import {installReminders} from './assistant-reminders.js?v=calendar-context1103';
import {installExpressionEditor} from './expression-editor.js?v=emotion146';
import {installModelSettings} from './model-settings.js?v=reference-generic110';
import {installVtuberCollab} from './vtuber-collab.js?v=shared-context4';
import ModelViewer from './model-viewer.js?v=emotion140';
import AvatarTracking from './avatar-tracking.js?v=camera-style145';
import {installBroadcastCamera} from './broadcast-camera.js?v=1';
import ChatReader from './chat-reader.js?v=both1103';
import LipSync from './lip-sync.js?v=fbx89';
import RvcVoiceChanger from './rvc-voice-changer.js?v=audio-route5';
import EyeTracking from './eye-tracking.js?v=cursor-gpu6';
import ScreenShare from './screen-share.js?v=timeline63';
import ScreenMemory from './screen-memory.js?v=timeline63';
import {utilityRequest} from './utility-request.js?v=1';
import {desktopWakeControls} from './desktop-wake-controls.js?v=agent-isolation1102';
import ContinuousMic from './continuous-mic.js?v=echo-isolation1103';
import {installCompanionDefaults} from './companion-defaults.js?v=label2';
import {installCharacterVoice} from './character-voice.js?v=1';
import {installVrmSpringControls} from './vrm-spring-controls.js?v=1';
import {installBackupControls} from './backup-controls.js?v=1';
import {installHotkeyDeckControls} from './hotkey-deck-controls.js?v=1';
import {installLiveChatControls} from './live-chat-controls.js?v=both1103';
import './memory-archaeology.js?v=calendar-context1103';
import {installInitiativeControls} from './proactive-state.js?v=1';
import {createSpeechInterrupt,isSpeechInterrupt} from './speech-interrupt.js?v=interrupt105';
import { speakPhrases as runSpeechPhrases } from './speech-pipeline.js?v=latency94';
const speakPhrases=(text,generate,play,isCurrent=()=>true)=>companionSleeping?Promise.resolve():runSpeechPhrases(text,generate,play,()=>!companionSleeping&&isCurrent());
import {createVoiceRuntime} from './voice-runtime.js?v=1';

const continuousMicBtn = document.getElementById('continuous-mic-btn');
const listeningStatus = document.getElementById('listening-status');
const chatAttachments=installChatAttachments({notice:text=>addMessage(text,'sakura')});
let lastMicActivity = Date.now();
let companionSleeping=false,sleepMicTemporary=false,sleepMicEpoch=0;
function wakeCompanion(){if(!viewer?.companionRoom?.act('home'))window.dispatchEvent(new CustomEvent('sakura-companion-sleep',{detail:{sleeping:false}}));}
window.addEventListener('sakura-companion-sleep',async event=>{
    companionSleeping=event.detail?.sleeping===true;const epoch=++sleepMicEpoch;
    if(companionSleeping){
        lipSync?.stop();speechInterrupt.stop();viewer?.reactionExpressions?.clear();
        listeningStatus.textContent='Sleeping · say wake up Sakura or your wake phrase. Tasks and automations continue.';
        if(nativeWake.enabled()&&!continuousMic.enabled){
            await nativeWake.pause(true);if(epoch!==sleepMicEpoch||!companionSleeping)return;
            sleepMicTemporary=true;try{await continuousMic.start(selectedMicId);if(epoch!==sleepMicEpoch&&!companionSleeping)continuousMic.stop();}catch{sleepMicTemporary=false;listeningStatus.textContent='Sleeping · click the microphone and say wake up Sakura';}
        }
    }else{if(sleepMicTemporary){sleepMicTemporary=false;continuousMic.stop();await nativeWake.pause(companionSleeping);}listeningStatus.textContent='Awake · ready to listen';}
});
let lastDirectReplyAt = 0;
let speechRecognitionBusy = 0;
const continuousMic = new ContinuousMic(blob => {
    if(chatBusy||lipSync?.isPlaying)return;
    return sendAudioForSTT(blob, { continuous: true });
}, status => {
    if (status !== 'Listening…') lastMicActivity = Date.now();
    listeningStatus.textContent = companionSleeping?'Sleeping · say wake up Sakura or your wake phrase':status;
    continuousMicBtn.setAttribute('aria-pressed', String(continuousMic.enabled));
    continuousMicBtn.textContent = continuousMic.enabled ? '🎤 Pause mic' : '🎤 Listen';
});
window.addEventListener('pagehide', () => continuousMic.stop());
let speechInputUsed=false, interruptFollowupUntil=0, interruptFollowupTimer=null, temporaryFollowupMic=false;
const speechInterrupt=createSpeechInterrupt({
    createMic:(...args)=>new ContinuousMic(...args),
    allowed:()=>!document.body.classList.contains('agent-mode')&&!trackingOnly&&!vtuberEnabled&&!aiVtuberStarting&&(speechInputUsed||continuousMic.enabled||nativeWake.enabled()),
    wakePhrase:()=>currentSettings.wake_word||'hey sakura',
    recognize:async blob=>{
        const form=new FormData();form.append('audio',blob,'interrupt.webm');
        const response=await fetch('/api/stt',{method:'POST',body:form});
        if(!response.ok)return '';
        return (await response.json()).text||'';
    },
    interrupt:async()=>{
        if(document.body.classList.contains('agent-mode'))return;
        document.getElementById('interrupt-btn').click();
        interruptFollowupUntil=Date.now()+15000;
        listeningStatus.textContent='Paused. Ask your next question.';
        if(!continuousMic.enabled){
            if(nativeWake.enabled())await nativeWake.pause(true);
            if(document.body.classList.contains('agent-mode'))return;
            temporaryFollowupMic=true;
            try{await continuousMic.start(selectedMicId);}
            catch(error){temporaryFollowupMic=false;interruptFollowupUntil=0;await nativeWake.pause(companionSleeping);listeningStatus.textContent='Speech stopped. Click the microphone to ask your next question.';return;}
            clearTimeout(interruptFollowupTimer);
            interruptFollowupTimer=setTimeout(()=>{
                interruptFollowupUntil=0;temporaryFollowupMic=false;continuousMic.stop();void nativeWake.pause(companionSleeping);
            },15000);
        }
    },
});
window.addEventListener('pagehide',()=>{speechInterrupt.stop();clearTimeout(interruptFollowupTimer);});

async function startDesktopListening(explicit = false) {
    if(document.body.classList.contains('agent-mode'))return;
    if (trackingOnly) return;
    if (vtuberEnabled || aiVtuberStarting) return;
    if(explicit)continuousMic.userRequested=true;
    if(currentSettings.wake_word_enabled&&window.pywebview?.api?.set_wake_listener){
        await nativeWake.sync();
        if(!continuousMic.userRequested)return;
    }
    if (!explicit && !continuousMic.userRequested && !currentSettings.wake_word_enabled) {
        continuousMic.stop();
        listeningStatus.textContent='Microphone off · click Listen or enable the wake phrase';
        return;
    }
    if(document.body.classList.contains('agent-mode'))return;
    try { await continuousMic.start(selectedMicId); }
    catch (err) {
        continuousMic.stop();
        listeningStatus.textContent = `Microphone: ${err.message}. Click Listen to retry.`;
    }
}

let chatReplyGeneration = 0;
let speechFallbackShown = false;
let replyController = null;
let chatBusy = false;
let reactionsEnabled = false;
let autoGameEnabled = false;
let autoGameBusy = false;
let gameActive = false;
let detectedGameName = '';
let gameReady = false;
let gameResumeMic = false;
let gameStartedScreen = false;
let gameForeground = false;
let gamePriorReactions = false;
let lastGameSeen = 0;
let gameCloudFallbackActive = false;
let lastGameVramNotice = '';
let lastReactionText = '';
let lastGameWatch=0;
let vtuberEnabled = false;
let vtuberStartedScreen = false;
let vtuberPriorReactions = false;
let trackingOnly = false;
let avatarTracking;
let vtuberGeneration = 0;
let vtuberQueue = [];
let vtuberPollBusy = false;
let vtuberSpeaking = false;
let vtuberResumeMic = false;
let aiVtuberStarting = false;
let screenStartedMic = false;
let screenWasEnabled = false;
let lastCoHostSpeech = 0;
let lastViewerReply = '';
window.addEventListener('pagehide', () => {
    avatarTracking?.stop();
    if (rvcVoiceChanger?.active) navigator.sendBeacon('/api/voice-changer/stop');
    rvcVoiceChanger?.stop();
    if (vtuberEnabled) navigator.sendBeacon('/api/vtuber/disconnect');
});
let reactionBusy = false;
let cameraReactionController = null;
const companionCamera = new CompanionCamera(enabled => {
    const toggle=document.getElementById('companion-camera-enabled');
    if(toggle)toggle.checked=enabled;
    const status=document.getElementById('companion-camera-status');
    if(status)status.textContent=enabled?'Camera access on · images shared with your selected AI provider':'Camera access off';
    if(!enabled&&cameraReactionController){cameraReactionController.abort();lipSync?.stop();}
});
window.addEventListener('pagehide',()=>{companionCamera.stop();cameraReactionController?.abort();});
const screenReactBtn = document.getElementById('screen-react-btn');
let viewer;
let lipSync;
let rvcVoiceChanger;
const screenViewBtn = document.getElementById('screen-view-btn');
const screenViewStatus = document.getElementById('screen-view-status');
const screenShare = new ScreenShare((enabled, starting) => {
    if (enabled && !screenWasEnabled && !trackingOnly && !vtuberEnabled && !aiVtuberStarting && !continuousMic.enabled) {
        screenStartedMic = true;
        startDesktopListening().then(() => {if (!screenShare.enabled || vtuberEnabled || aiVtuberStarting) continuousMic.stop();});
    }
    screenWasEnabled = enabled;
    if (!enabled && screenStartedMic) {continuousMic.stop(); screenStartedMic = false;}
    if (!enabled) {
        reactionsEnabled = false;
        screenReactBtn.textContent = '💬 Reactions off';
        screenReactBtn.setAttribute('aria-pressed', 'false');
    }
    screenViewBtn.textContent = enabled ? '🖥️ Screen on' : starting ? 'Cancel sharing' : '🖥️ Screen off';
    screenViewBtn.setAttribute('aria-pressed', String(enabled));
    screenViewStatus.classList.toggle('sharing', enabled);
    screenViewStatus.textContent = enabled ? `Live screen + audio · AI receives recent frames via ${currentSettings.llm_provider === 'ollama' ? 'local Ollama' : currentSettings.llm_provider}`
        : starting ? 'Choose a screen or window in the browser picker' : 'Screen off · Capture stopped';
    window.dispatchEvent(new Event('sakura-screen-state'));
});
window.addEventListener('pagehide', () => screenShare.stop());
const screenAudio = installScreenAudio(() => !trackingOnly && screenShare.enabled,
    () => !!lipSync?.isPlaying || chatBusy || reactionBusy || vtuberSpeaking || companionSleeping, fetch, () => vtuberEnabled || aiVtuberStarting);
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
const ensureKokoroReady=createVoiceRuntime(()=>currentVoiceId);
let allRvcModels = [];          // from /api/voices (rvc_models)
let allPmxModels = [];          // from /api/models
let currentVoiceId = 'kokoro_af_heart';
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
const vtuberNameInput = document.getElementById('vtuber-name-input');
const avatarPresentation = document.getElementById('avatar-presentation');
const userAddress = document.getElementById('user-address');
const newsArea = document.getElementById('news-area');
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
    const gemini=local||llmProvider.value==='gemini';
    document.getElementById('cloud-connection-fields').hidden=gemini;
    geminiModel.parentElement.hidden=!gemini;
    document.getElementById('cloud-endpoint').disabled=llmProvider.value!=='compatible';
    document.getElementById('cloud-endpoint').hidden=llmProvider.value!=='compatible';
    document.querySelector('label[for="cloud-endpoint"]').hidden=llmProvider.value!=='compatible';
    document.getElementById('cloud-vision').parentElement.hidden=llmProvider.value==='auto';
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
        updateLocalModelChoices(data);
        const names=[...data.models.map(m=>m.name),...(data.native_models||[]).map(m=>m.label)];
        status.textContent = names.length ? `Available: ${names.join(', ')}` : 'No local models found.';
    } catch (error) { status.textContent = error.message; }
}

async function saveAiSettings(clearKey = false, clearBrave = false) {
    const modelButtons = ['qwen-2b-btn', 'qwen-4b-btn'].map(id => document.getElementById(id));
    if (modelButtons.some(button => button.disabled)) return;
    modelButtons.forEach(button => { button.disabled = true; });
    aiSaveStatus.textContent = 'Checking model and applying settings…';
    try {
        const payload = { llm_provider: llmProvider.value,
            gemini_model: geminiModel.value.trim() || 'gemini-flash-latest',
            ollama_model: document.getElementById('ollama-model').value.trim(),
            game_ollama_model: document.getElementById('game-ollama-model').value.trim(),
            game_cloud_auto_enabled: document.getElementById('game-cloud-auto').checked,
            ollama_models_folder: document.getElementById('ollama-models-folder').value.trim(),
            ollama_context: Number(document.getElementById('ollama-context').value),
            gemini_fallback_enabled: !clearKey && document.getElementById('gemini-fallback').checked,
            local_timeout: Number(document.getElementById('local-timeout').value) };
        if(!['ollama','gemini'].includes(llmProvider.value)){
            payload.cloud_model=document.getElementById('cloud-model').value.trim();
            payload.cloud_endpoint=document.getElementById('cloud-endpoint').value.trim();
            if(llmProvider.value!=='auto')payload.cloud_vision=document.getElementById('cloud-vision').checked;
            payload.gemini_fallback_enabled=false;
        }
        if (geminiApiKey.value.trim()) {
            if(llmProvider.value==='ollama')payload.gemini_api_key=geminiApiKey.value.trim();
            else payload.api_key = geminiApiKey.value.trim();
        }
        if (clearKey) {if(['ollama','gemini'].includes(llmProvider.value))payload.clear_gemini_key=true;else payload.clear_cloud_key=true;}
        payload.web_search_enabled = document.getElementById('web-search-enabled').checked;
        if (document.getElementById('brave-api-key').value.trim()) payload.brave_key = document.getElementById('brave-api-key').value.trim();
        if (clearBrave) payload.clear_brave_key = true;
        const response = await fetch('/api/settings', { method: 'POST',
            headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        const data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || 'Could not save AI settings.');
        geminiApiKey.value = '';
        document.getElementById('brave-api-key').value = '';
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
    button.setAttribute('aria-busy','true');
    aiSaveStatus.textContent = 'Testing saved connection…';
    try {
        if (!await saveAiSettings()) return;
        const response = await fetch('/api/llm/test', { method: 'POST' });
        const data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || 'Connection failed.');
        flashMsg(aiSaveStatus, data.message, 8000);
    } catch (err) { flashMsg(aiSaveStatus, err.message, 8000); }
    finally { button.disabled = false;button.removeAttribute('aria-busy'); }
}

async function findCloudModels(){
    const button=document.getElementById('find-cloud-models'),select=document.getElementById('available-cloud-models'),status=document.getElementById('cloud-model-status');
    const provider=llmProvider.value,key=geminiApiKey.value.trim();button.disabled=true;button.setAttribute('aria-busy','true');status.textContent='Finding models from the selected provider…';
    try{
        const response=await fetch('/api/llm/models',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider,api_key:key,model:provider==='gemini'?geminiModel.value.trim():document.getElementById('cloud-model').value.trim(),endpoint:document.getElementById('cloud-endpoint').value.trim()})});
        const data=await response.json();if(!response.ok)throw Error(data.error||'Model discovery failed.');
        if(llmProvider.value!==provider)throw Error('Provider changed. Find models again for the selected provider.');
        select.replaceChildren();const placeholder=document.createElement('option');placeholder.value='';placeholder.textContent='Choose a model';select.append(placeholder);
        for(const id of data.models||[]){const option=document.createElement('option');option.value=id;option.textContent=id;select.append(option);}
        select.dataset.provider=data.provider;status.textContent=data.models.length+' models found. Choose a model, then Test API. Your unsaved key has not been stored.';
        if(!data.models.length)status.textContent='No compatible models listed. Enter an exact model ID manually or check provider access.';
    }catch(error){status.textContent=error.message;}finally{button.disabled=false;button.removeAttribute('aria-busy');}
}

let identityDirty = false;
let identitySaving = false;
let identitySaveQueued = false;
let identityTimer = null;
let currentSettings = { assistant_name: 'Sakura', wake_word: 'hey sakura', wake_word_enabled: false };
window.addEventListener('sakura-reply-emotion',event=>{if(['auto','off','happy','concerned','amused','surprised','focused'].includes(event.detail?.value)){currentSettings.avatar_emotion=event.detail.value;viewer?.reactionExpressions?.clear();}});
let wakeCommandDeadline = 0;
const nativeWake=desktopWakeControls({continuousMic,settings:()=>currentSettings,blocked:()=>document.body.classList.contains('agent-mode')||trackingOnly||vtuberEnabled||aiVtuberStarting,
    receive:async text=>{wakeCommandDeadline=0;if(companionSleeping)wakeCompanion();chatInput.value=text;await handleSendMessage();},status:text=>{listeningStatus.textContent=text;}});


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
            window.sakuraCompanionToolbar?.positionDropdown(trigger, menu);
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
        document.getElementById('mmd-btn').classList.remove('hidden');
        document.getElementById('pmx-texture-compare').classList.remove('hidden');
    };
    if (window.pywebview) showEditorButton();
    window.addEventListener('pywebviewready', showEditorButton);
    document.getElementById('mmd-btn').addEventListener('click',async()=>{
        if(!selectedPmxPath?.toLowerCase().endsWith('.pmx')){const message='Select a PMX model to open in MikuMikuDance.';if(trackingOnly)alert(message);else addMessage(message,'sakura');return;}
        const button=document.getElementById('mmd-btn');button.disabled=true;
        try{await window.pywebview.api.open_mmd(selectedPmxPath);}
        catch(error){const message=`MikuMikuDance: ${error.message||error}`;if(trackingOnly)alert(message);else addMessage(message,'sakura');}
        finally{button.disabled=false;}
    });
    document.getElementById('rvc-runtime-setup').addEventListener('click',async()=>{
        const status=document.getElementById('rvc-runtime-status');
        try{const result=await window.pywebview?.api?.install_rvc_runtime();if(!result)throw Error('Open the Windows desktop app to install RVC.');status.textContent=result.cancelled?'Installation cancelled.':'Installer opened. Follow its progress, then select your RVC voice.';}
        catch(error){status.textContent=error.message||String(error);}
    });
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
    updateAppBrand(new URLSearchParams(window.location.search).has('tracking'));
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
    const agentFrame=document.getElementById('agent-workspace-frame');
    const agentModeButton=document.getElementById('agent-mode-toggle');
    const isAgentMode=new URLSearchParams(window.location.search).has('agent');
    let agentSpeechQueue=Promise.resolve();
    const setAgentMode=async enabled=>{
        enabled=Boolean(enabled);
        if(enabled&&trackingOnly)return;
        const active=document.body.classList.contains('agent-mode');
        if(active===enabled)return;
        document.body.classList.toggle('agent-mode',enabled);
        agentModeButton.textContent=enabled?'Companion mode':'Agent mode';
        agentModeButton.setAttribute('aria-pressed',String(enabled));
        if(enabled){
            continuousMic.stop();speechInterrupt.stop();clearTimeout(interruptFollowupTimer);
            ++chatReplyGeneration;replyController?.abort();
            if(mediaRecorder?.state==='recording')mediaRecorder.stop();
            isRecording=false;micBtn.classList.remove('recording');
            await nativeWake.sync(true);
            if(agentFrame.src==='about:blank')agentFrame.src='/agent?embedded=1';
            document.body.classList.remove('transparent-mode');document.documentElement.classList.remove('transparent-mode');
        }else{
            agentFrame.src='about:blank';
            // Agent expands the window. Return to the full Companion layout;
            // the compact desktop layout intentionally hides text chat.
            await window.applyLibraryMode?.(true);
            chatPanel.classList.remove('minimized');
            chatBubbleBtn.classList.add('hidden');
        }
        if(window.pywebview?.api?.set_library_mode){
            try{
                if(enabled){
                    // Entering Agent mode expands the floating companion into
                    // the full application window.
                    await window.pywebview.api.set_library_mode(true);
                }else{
                    // Returning to Companion changes the page layout only.
                    // Keep the full window open; the title-bar minimize button
                    // remains the explicit way to return to the floating view.
                    await window.applyLibraryMode?.(true);
                    window.updateMaximizeControl?.(true);
                    winMinBtn.title='Shrink to desktop companion';
                }
            }catch(error){console.warn('Agent window mode change failed:',error);}
        }
        requestAnimationFrame(()=>window.dispatchEvent(new Event('resize')));
    };
    window.sakuraSetAgentMode=setAgentMode;
    agentModeButton.textContent=isAgentMode?'Companion mode':'Agent mode';
    agentModeButton.setAttribute('aria-pressed',String(isAgentMode));
    if(isAgentMode)agentFrame.src='/agent?embedded=1';
    agentModeButton.addEventListener('click',()=>void setAgentMode(!document.body.classList.contains('agent-mode')));
    window.addEventListener('message',event=>{
        if(event.origin!==location.origin||event.source!==agentFrame.contentWindow)return;
        if(event.data?.type==='sakura-agent-companion-mode')void setAgentMode(false);
        if(event.data?.type==='sakura-agent-speech'&&typeof event.data.text==='string')void window.sakuraAgentSpeak?.(event.data.text);
    });
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
        document.body.classList.remove('companion-toolbar-open');
        document.getElementById('companion-toolbar-toggle').setAttribute('aria-expanded', 'false');
        document.body.classList.toggle('desktop-companion', !enabled);
        document.body.classList.toggle('native-library', enabled);
        // Keep the Sakura title bar as the window drag area in all app modes.
        setCompanionDragRegion(true);
        winMinBtn.title = enabled && !trackingOnly ? 'Shrink to desktop companion' : 'Minimize to taskbar';
        winControls.style.display = 'flex';
        continuousMicBtn.style.display = enabled ? 'none' : 'inline-flex';
        // Resize presentation immediately; microphone permission may take time.
        window.dispatchEvent(new Event('resize'));
        if (enabled) {
            continuousMic.stop();
            setTransparency(false, false);
        } else {
            setTransparency(localStorage.getItem('sakura_transparency') !== 'false', false);
            await startDesktopListening();
        }
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
        setTransparency(!isAgentMode&&localStorage.getItem('sakura_transparency') !== 'false', false);
        winControls.style.display = 'flex';
        continuousMicBtn.style.display = isAgentMode ? 'none' : 'inline-flex';
    } else {
        setTransparency(localStorage.getItem('sakura_transparency') === 'true', false);
    }
    if (isLibrary) window.applyLibraryMode(true);
    // 2. Initialize Three.js viewer and lip sync safely
    try {
        viewer  = new ModelViewer('viewer');
        installVtuberCollab({viewer, ModelViewer});
        // An explicitly chosen expression (PC editor or phone) is a manual
        // override: it pauses reactions so the pick stays visible and the
        // phone can switch away from whatever the PC had selected.
        viewer.replyEmotion=()=>currentSettings.avatar_emotion||'auto';
        viewer.areAiExpressionsAutomatic = () => currentSettings.avatar_emotion!=='off' && !trackingOnly && (!viewer.vtuberTrackingMode || !!viewer.companionTracking) && !viewer.manualExpressions?.size;
        installStageItems(viewer);
        installCompanionRoom(viewer);
        installSpoutControls(()=>viewer);
        installVirtualCamera(()=>viewer);
        window.sakuraExpressionEditor = installExpressionEditor(()=>viewer, ()=>selectedPmxPath || lastGoodModelUrl || 'none');
        window.sakuraModelSettings = installModelSettings(()=>viewer, ()=>selectedPmxPath || lastGoodModelUrl || 'none', refreshPmxTextureSelector,()=>selectedMicId,
            key=>loadModelFromUrl('/models/'+key.split('/').map(encodeURIComponent).join('/')));
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
        window.sakuraAgentSpeak=text=>{
            if(companionSleeping)return Promise.resolve();
            const safe=String(text||'').replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/gu,'').trim().slice(0,420);
            if(!safe)return Promise.resolve();
            agentSpeechQueue=agentSpeechQueue.catch(()=>{}).then(async()=>{
                if(companionSleeping)return;
                const response=await fetch('/api/tts/speak',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:safe})});
                const speech=await response.json();if(!response.ok)throw Error(speech.error||'Speech is unavailable.');
                if(speech.audio&&lipSync&&!companionSleeping)await lipSync.playWithLipSync(speech.audio);
            });
            return agentSpeechQueue;
        };
        lipSync.onAudioActive=async value=>{
            if(value)continuousMic.pauseCapture();else continuousMic.resumeCapture();
            await nativeWake.audioActive(value);
            if(value)void speechInterrupt.start(selectedMicId);
            else if(!chatBusy)speechInterrupt.stop();
        };
        rvcVoiceChanger = new RvcVoiceChanger(lipSync, message => {
            const status = document.getElementById('vtuber-rvc-changer-status');
            if (status) status.textContent = message;
        }, () => currentVoiceId);
    } catch (err) {
        console.error('Failed to initialize 3D viewer / lip sync:', err);
        const startupStatus=document.getElementById('startup-render-status');
        if(startupStatus)startupStatus.textContent='3D renderer unavailable. Companion controls remain available.';
    }
    setupEvents();
    setupAvatarTracking();
    const companionCameraModes=new CompanionCameraModes({objectCamera:companionCamera,avatarTracking,viewer});
    installCameraPreview(()=>avatarTracking,()=>viewer);
    installPersonalControls();
    installCameraStyleControls();
    installReminders(()=>!trackingOnly&&!vtuberEnabled&&!companionSleeping,()=>selectedSpeakerId);
    const cameraToggle=document.getElementById('companion-camera-enabled');
    const companionCameraMode=document.getElementById('companion-camera-mode');
    const companionFaceTrackingOptions=document.getElementById('companion-face-tracking-options');
    const updateCompanionCameraOptions=()=>{companionFaceTrackingOptions.hidden=companionCameraMode.value!=='tracking';};
    companionCameraMode.addEventListener('change',updateCompanionCameraOptions);
    updateCompanionCameraOptions();
    const setCompanionCameraMode=async enabled=>{
        const status=document.getElementById('companion-camera-status');
        if(!enabled){
            if(!trackingOnly&&!vtuberEnabled)companionCameraModes.stop();
            else companionCamera.stop();
            cameraToggle.checked=false;status.textContent='Camera access off';return;
        }
        if(trackingOnly||vtuberEnabled){companionCamera.stop();cameraToggle.checked=false;status.textContent='Stop VTuber mode before enabling Companion camera access.';return;}
        const mode=companionCameraMode.value;
        status.textContent=mode==='tracking'?'Requesting camera permission for local face tracking…':'Requesting camera permission for object recognition…';
        try{
            await companionCameraModes.start(mode,document.getElementById('settings-tracking-camera').value,
                document.getElementById('tracking-backend').value,document.getElementById('face-tracking-source').value);
            cameraToggle.checked=true;
            status.textContent=mode==='tracking'?'Face tracking on · processed locally · avatar follows you while Sakura keeps reacting':'Object recognition on · camera images are shared with your selected AI provider';
        }catch(error){companionCameraModes.stop();cameraToggle.checked=false;status.textContent=`Camera unavailable: ${error.message}. Select another camera above, close apps using it, or connect your Camo phone, then retry.`;}
    };
    cameraToggle.addEventListener('change',()=>void setCompanionCameraMode(cameraToggle.checked));
    companionCameraMode.addEventListener('change',()=>{if(cameraToggle.checked)void setCompanionCameraMode(true);});
    document.getElementById('settings-tracking-camera').addEventListener('change',()=>{
        if(cameraToggle.checked)void setCompanionCameraMode(true);
    });
    document.getElementById('companion-camera-comments').addEventListener('change',event=>{
        if(!event.target.checked&&cameraReactionController){cameraReactionController.abort();lipSync?.stop();}
    });
    const cameraTimer=setInterval(()=>reactToCamera(),60000);
    window.addEventListener('pagehide',()=>clearInterval(cameraTimer),{once:true});
    installMobileLink(()=>viewer,()=>avatarTracking,text=>addMessage(text,'sakura'),openSettingsModal);
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
            viewer?.setGlossBoost(Number(document.getElementById('gloss-boost-slider').value) / 100,
                viewer?.vrm?.scene||viewer?.model,viewer?.characterLightingTarget||null);
        };
        slider.addEventListener('input', update);
        document.getElementById(`${id}-value`).textContent = slider.value + unit;
    }
    viewer?.setLightAngles(document.getElementById('light-angle-slider').value, document.getElementById('light-elevation-slider').value);
    viewer?.setGlossBoost(Number(document.getElementById('gloss-boost-slider').value) / 100,
        viewer?.vrm?.scene||viewer?.model,viewer?.characterLightingTarget||null);

    // Load only the character on the first-paint path; optional device/voice
    // discovery must not keep the window covered (Windows enumeration can stall).
    let startupVoicesReady=Promise.resolve();
    try {
        await loadAppSettings();
        updateTransparencyShortcut();
        trackingOnly = !!currentSettings.vtuber_tracking_only;
        updateAppBrand(trackingOnly);
        document.body.classList.toggle('tracking-only', trackingOnly);
        viewer?.setVtuberTrackingMode(trackingOnly);
        await loadModelsList();
        window.sakuraCompanionDefaultsReady=true;
        window.dispatchEvent(new Event('sakura-companion-ready'));
    } catch (err) {
        console.warn('Initial data load warning:', err);
    }

    // 4. Apply saved audio output device
    if (selectedSpeakerId && lipSync) lipSync.setAudioOutput(selectedSpeakerId);

    checkStatus();
    setInterval(checkStatus, 5000);
    setInterval(async () => {
        if (identityDirty || identitySaving) return;
        try {
            const response = await fetch('/api/settings');
            if (!response.ok) return;
            const saved = await response.json();
            if (identityDirty || identitySaving) return;
            const fields = ['assistant_name', 'vtuber_name', 'avatar_presentation', 'user_address', 'news_area', 'wake_word', 'wake_word_enabled', 'computer_control_enabled'];
            if (fields.some(key => saved[key] !== currentSettings[key])) {
                for (const key of fields) currentSettings[key] = saved[key];
                wakeCommandDeadline = 0;
                applySettingsUI(currentSettings);
            }
        } catch (_) {}
    }, 5000);

    await finishStartupPresentation(viewer);
    startupVoicesReady=loadVoicesList();
    void refreshAudioDevices();

    if(!trackingOnly)try{
        await startupVoicesReady;
        const greetingGeneration=chatReplyGeneration;
        const greeting=await(await fetch('/api/assistant/greeting',{method:'POST'})).json();
        if(greeting.reply){addMessage(greeting.reply,'sakura');await ensureKokoroReady();
            const speech=await(await fetch('/api/tts/speak',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:greeting.reply})})).json();
            if(speech.audio&&greetingGeneration===chatReplyGeneration&&!trackingOnly)await lipSync.playWithLipSync(speech.audio);
        }
    }catch(error){console.warn('Startup greeting speech unavailable',error);}
    if (isDesktop && !isAgentMode) await startDesktopListening();
});

// ─────────────────────────── Tab System ───────────────────────────
function setupTabs() {
    document.querySelectorAll('#settings-modal .tab-btn[data-tab]').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            document.querySelectorAll('#settings-modal .tab-btn[data-tab]').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('#settings-modal .tab-content').forEach(c => c.classList.remove('active'));
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
    window.sakuraCompanionToolbar = installCompanionToolbar();
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
    continuousMicBtn.addEventListener('click', async () => {
        speechInterrupt.stop();clearTimeout(interruptFollowupTimer);interruptFollowupUntil=0;
        speechInputUsed=false;
        const wasTemporary=temporaryFollowupMic;
        if(wasTemporary)continuousMic.stop();
        temporaryFollowupMic=false;
        if (nativeWake.enabled()){const wasEnabled=continuousMic.enabled;wakeWordToggle.checked=false;await saveAppSettings();if(wasEnabled){sleepMicTemporary=false;continuousMic.userRequested=false;continuousMic.stop();}else await startDesktopListening(true);}
        else if (continuousMic.enabled) {continuousMic.userRequested=false;continuousMic.stop();}
        else if(!wasTemporary)startDesktopListening(true);
    });
    installCompactCompanionControls(()=>continuousMic.enabled||nativeWake.enabled());
    const gamePlayMode=document.getElementById('game-play-mode');
    gamePlayMode?.addEventListener('change',async()=>{
        const previous=currentSettings.game_play_mode||'singleplayer';
        try{const response=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({game_play_mode:gamePlayMode.value})});
            if(!response.ok){const data=await response.json();throw Error(data.error||'Could not save game type.');}currentSettings.game_play_mode=gamePlayMode.value;
            if(gameActive)listeningStatus.textContent=gamePlayMode.value==='multiplayer'?'Multiplayer · say the wake phrase to address Sakura; team/game audio is context.':'Single-player · microphone listens while enabled.';
        }catch(error){gamePlayMode.value=previous;listeningStatus.textContent=error.message;}
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

    llmProvider.addEventListener('change', () => {
        const provider=llmProvider.value;
        document.getElementById('available-cloud-models').replaceChildren();document.getElementById('cloud-model-status').textContent='Find models for the selected provider. Test API sends one small generation request.';
        document.getElementById('cloud-model').value=provider===currentSettings.llm_provider?(currentSettings.cloud_model||''):({openai:'gpt-4.1-mini',anthropic:'claude-haiku-4-5',deepseek:'deepseek-flash'}[provider]||'');
        document.getElementById('cloud-endpoint').value=provider===currentSettings.llm_provider?(currentSettings.cloud_endpoint||''):'';
        document.getElementById('cloud-vision').checked=provider===currentSettings.llm_provider?!!currentSettings.cloud_vision:['openai','anthropic'].includes(provider);
        geminiKeyStatus.textContent='A different provider needs its own key. Leave blank only to keep that provider’s saved key.';
        updateProviderFields();
    });
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
        reactionsEnabled = !reactionsEnabled;
        if(reactionsEnabled)viewer?.clearManualExpression();
        else viewer?.reactionExpressions?.clear();
        window.dispatchEvent(new Event('sakura-reactions-changed'));
        screenReactBtn.textContent = reactionsEnabled ? '💬 Reactions on' : '💬 Reactions off';
        screenReactBtn.setAttribute('aria-pressed', String(reactionsEnabled));
    });
    async function screenReactionLoop() {
        try { await reactToScreen(); }
        finally { setTimeout(screenReactionLoop, gameActive ? 1000 : 2000); }
    }
    setTimeout(screenReactionLoop, 1000);
    const screenMemory=new ScreenMemory(screenShare,()=>!trackingOnly&&!companionSleeping,
        ()=>chatBusy||reactionBusy||isRecording||!!lipSync?.isPlaying||vtuberSpeaking);
    const screenMemoryTimer=setInterval(()=>screenMemory.tick(),2000);
    window.addEventListener('pagehide',()=>{clearInterval(screenMemoryTimer);screenMemory.stop();},{once:true});
    document.getElementById('save-ai-settings').addEventListener('click', () => saveAiSettings());
    document.getElementById('test-ai-connection').addEventListener('click', testAiConnection);
    document.getElementById('find-cloud-models').addEventListener('click',findCloudModels);
    document.getElementById('available-cloud-models').addEventListener('change',event=>{
        const select=event.target;if(!select.value)return;
        if(llmProvider.value==='auto')llmProvider.value=select.dataset.provider;
        (llmProvider.value==='gemini'?geminiModel:document.getElementById('cloud-model')).value=select.value;
        updateProviderFields();document.getElementById('cloud-model-status').textContent='Selected '+select.value+'. Test API saves this selection and checks generation access.';
    });
    document.getElementById('remove-gemini-key').addEventListener('click', () => saveAiSettings(true));
    document.getElementById('remove-brave-key').addEventListener('click', () => saveAiSettings(false, true));

    // Chat
    sendBtn.addEventListener('click', handleSendMessage);
    chatInput.addEventListener('keydown', e => { if (e.key === 'Enter') handleSendMessage(); });
    clearBtn.addEventListener('click', handleClearChat);
    document.getElementById('vtuber-mode-btn').addEventListener('click', () => {
        if(trackingOnly||window.SAKURA_EDITION==='vtuber')return;
        openSettingsModal();
        const tab=document.querySelector('.tab-btn[data-tab="assistant"]');tab?.click();
        // The settings strip may be horizontally scrolled or reparented by
        // the studio shell. Explicitly activate the real assistant pane.
        document.querySelectorAll('#settings-modal .tab-content').forEach(pane=>pane.classList.toggle('active',pane.id==='tab-assistant'));
        document.querySelectorAll('#settings-modal .tab-btn').forEach(button=>button.classList.toggle('active',button===tab));
        document.getElementById('vtuber-start-btn')?.scrollIntoView({block:'center'});
    });
    document.getElementById('vtuber-start-btn').addEventListener('click', async () => {
        const status = document.getElementById('vtuber-status');
        const button = document.getElementById('vtuber-start-btn');
        button.disabled = true;
        vtuberResumeMic = continuousMic.enabled;
        aiVtuberStarting = true;
        continuousMic.stop();
        if (mediaRecorder?.state === "recording") {
            mediaRecorder.onstop = () => mediaRecorder.stream.getTracks().forEach(track => track.stop());
            mediaRecorder.stop(); isRecording = false; micBtn.classList.remove("recording");
        }
        try {
            await enableAiVtuberScreen();
            const response = await fetch('/api/vtuber/connect', {method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({service:document.getElementById('cohost-service')?.value||'youtube',twitch_link:document.getElementById('cohost-twitch-link')?.value.trim()||'',link: document.getElementById('youtube-chat-link').value.trim(),twitch_username:document.getElementById('cohost-twitch-username')?.value.trim()||'',twitch_token:document.getElementById('cohost-twitch-token')?.value||''})});
            const data = await response.json();
            if (!response.ok) throw new Error(data.error);
            ++vtuberGeneration;
            vtuberEnabled = true;
            companionCamera.stop();
            continuousMic.stop();
            document.getElementById('vtuber-chat-enabled').checked = true;
            await screenAudio.sync();
            vtuberQueue = [];
            lastViewerReply = '';
            status.textContent = ({youtube:'YouTube',twitch:'Twitch',both:'YouTube + Twitch'}[document.getElementById('cohost-service')?.value]||'YouTube')+' chat + live screen + computer audio · microphone excluded';
            document.getElementById('vtuber-mode-btn').textContent = 'AI VTuber on';
        } catch (error) {
            if(!vtuberEnabled) {aiVtuberStarting=false; restoreAiVtuberScreen(); if(vtuberResumeMic) await startDesktopListening(true);}
            status.textContent = error.message;
        }
        finally { const token=document.getElementById('cohost-twitch-token');if(token)token.value='';aiVtuberStarting = false; button.disabled = false; }
    });
    document.getElementById('vtuber-stop-btn').addEventListener('click', async () => {
        vtuberEnabled = false;
        ++vtuberGeneration;
        vtuberQueue = [];
        restoreAiVtuberScreen();
        await fetch("/api/vtuber/disconnect", {method: "POST"}).catch(console.error);
        await screenAudio.sync();
        if(vtuberResumeMic) await startDesktopListening(true);
        vtuberResumeMic = false;
        if (vtuberSpeaking) document.getElementById('interrupt-btn').click();
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
    installCompanionDefaults({blocked:()=>trackingOnly||window.SAKURA_EDITION==='vtuber',screen:screenShare,screenButton:screenViewBtn,reactionButton:screenReactBtn,gameButton,status:listeningStatus});
    installCharacterVoice({getModel:()=>selectedPmxPath,applyVoice:applyVoiceById,getVoice:()=>currentVoiceId,blocked:()=>trackingOnly||chatBusy||reactionBusy});
    installVrmSpringControls(viewer,()=>selectedPmxPath);
    installBackupControls();
    installHotkeyDeckControls();
    installLiveChatControls();
    if(window.SAKURA_EDITION!=='vtuber')window.installMemoryArchaeology?.(document.getElementById('system-tools'));
    installInitiativeControls();
    document.getElementById('clear-memory-desktop').addEventListener('click', handleClearChat);
    window.addEventListener('sakura-chat-session-ended',()=>{
        document.getElementById('interrupt-btn').click();
        cameraReactionController?.abort();
        messagesEl.innerHTML='';
        void fetch('/api/clear',{method:'POST',keepalive:true}).catch(error=>console.warn('Session reset unavailable:',error));
    });
    refreshMemoryBtn.addEventListener('click', async () => {
        refreshMemoryBtn.disabled = true;
        try {
            const response = await fetch('/api/refresh-memory', { method: 'POST' });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || 'Memory refresh failed.');
            addMessage(result.message || 'Chat lasts only for this app session and clears when you exit.', 'sakura');
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
    document.getElementById('dance-style').onchange=event=>{
        if(viewer?.dance?.active)viewer.dance.start(event.target.value);
    };
    document.getElementById('dance-stop-btn').onclick=()=>viewer?.dance?.stop();
    document.getElementById('interrupt-btn').addEventListener('click', () => {
        speechInterrupt.stop();
        viewer?.companionRoom?.stop();
        viewer?.dance?.stop();
        ++chatReplyGeneration;
        replyController?.abort();
        lipSync?.stop();
        chatBusy = false;
        removeTypingIndicator();
        hideSpeechBubble();
        viewer?.setActivity('idle');
        lastMicActivity = Date.now();
        void nativeWake.pause(companionSleeping);
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
    let companionViewChanging=false;
    window.toggleCompanionView = async () => {
        if (trackingOnly) { window.toggleStreamingControls(); return; }
        if (document.body.classList.contains('native-library')) return;
        if(companionViewChanging)return;companionViewChanging=true;
        try{
            const transparent=!document.body.classList.contains('transparent-mode');
            const characterOnly=window.pywebview?.api?.set_character_only
                ? await window.pywebview.api.set_character_only(transparent) : false;
            setTransparency(transparent);
            // Keep the title bar/recovery controls usable if the native hotkey
            // is unavailable and click-through was refused.
            document.body.classList.toggle('overlay-ui-hidden',transparent&&(!window.pywebview||characterOnly===true));
            document.body.classList.toggle('native-character-only',transparent&&characterOnly===true);
            document.querySelectorAll('.dropdown-menu').forEach(m=>m.classList.add('hidden'));
        }catch(error){console.error('Companion transparency:',error);}
        finally{companionViewChanging=false;}
    };
    bgToggleBtn.addEventListener('click', window.toggleCompanionView);
    document.getElementById('restore-companion-controls')?.addEventListener('click', window.toggleCompanionView);
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
    for (const control of [assistantNameInput, vtuberNameInput, avatarPresentation, userAddress, newsArea, wakeWordInput, wakeWordToggle, computerControlToggle]) {
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
        if (!trackingOnly && window.pywebview?.api?.set_library_mode) {
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
    screenAudio.setVisible(!trackingOnly);
    if (!trackingOnly) void screenAudio.refresh();
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
    document.getElementById('game-ollama-model').value=s.game_ollama_model||'';
    document.getElementById('game-cloud-auto').checked=s.game_cloud_auto_enabled!==false;
    if(document.getElementById('game-play-mode'))document.getElementById('game-play-mode').value=s.game_play_mode||'singleplayer';
    document.getElementById('ollama-model').value = s.ollama_model || 'qwen3-vl:2b-instruct';
    document.getElementById('ollama-models-folder').value = s.ollama_models_folder || '';
    document.getElementById('ollama-context').value = s.ollama_context || 4096;
    document.getElementById('gemini-fallback').checked = !!s.gemini_fallback_enabled;
    document.getElementById('local-timeout').value = s.local_timeout || 20;
    geminiModel.value = s.gemini_model || 'gemini-flash-latest';
    document.getElementById('cloud-model').value=s.cloud_model||'';
    document.getElementById('cloud-endpoint').value=s.cloud_endpoint||'';
    document.getElementById('cloud-vision').checked=!!s.cloud_vision;
    const keySaved=['ollama','gemini'].includes(s.llm_provider)?s.gemini_key_set:s.cloud_key_set;
    geminiKeyStatus.textContent = keySaved ? `A key is saved for ${s.llm_provider}. Leave blank to keep it.` : 'No key saved for this provider.';
    document.getElementById('remove-gemini-key').disabled = !keySaved;
    document.getElementById('web-search-enabled').checked = s.web_search_enabled !== false;
    document.getElementById('brave-key-status').textContent = s.brave_key_set
        ? 'A Brave Search key is saved. Leave blank to keep it.'
        : 'No Brave key saved; she falls back to free public sources.';
    document.getElementById('remove-brave-key').disabled = !s.brave_key_set;
    updateProviderFields();
    if (screenShare.enabled) screenShare.onChange(true, false);
    if (!identityDirty) {
        if (assistantNameInput) assistantNameInput.value = s.assistant_name || 'Sakura';
        if (vtuberNameInput) vtuberNameInput.value = s.vtuber_name || 'Sakura';
        if (avatarPresentation) avatarPresentation.value = s.avatar_presentation || 'auto';
        if (userAddress) userAddress.value=s.user_address||'sir';
        if (newsArea) newsArea.value=s.news_area||'';
        if (wakeWordInput) wakeWordInput.value = s.wake_word || 'hey sakura';
        if (wakeWordToggle) wakeWordToggle.checked = !!s.wake_word_enabled;
        if (computerControlToggle) computerControlToggle.checked = !!s.computer_control_enabled;
        for(const [id,key]of [['system-tools-permission','computer_control_enabled'],['phone-system-access','phone_system_access_enabled'],['phone-clipboard-access','phone_clipboard_enabled']]){const input=document.getElementById(id);if(input&&!input.disabled)input.checked=!!s[key];}
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


}

async function saveAppSettings() {
    clearTimeout(identityTimer);
    if (identitySaving) { identitySaveQueued = true; return; }
    identitySaving = true;
    const newName = (assistantNameInput?.value.trim()) || 'Sakura';
    const newVtuberName = (vtuberNameInput?.value.trim()) || 'Sakura';
    const newPresentation = avatarPresentation?.value || 'auto';
    const newAddress=userAddress?.value||'sir';
    const newNewsArea=newsArea?.value.trim()||'';
    const newWakeWord = (wakeWordInput?.value.trim().toLowerCase()) || 'hey sakura';
    const newWakeEnabled = wakeWordToggle?.checked || false;
    const newComputerControl = computerControlToggle?.checked || false;

    try {
        const res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                assistant_name: newName,
                vtuber_name: newVtuberName,
                avatar_presentation: newPresentation,
                user_address:newAddress,
                news_area:newNewsArea,
                wake_word: newWakeWord,
                wake_word_enabled: newWakeEnabled,
                computer_control_enabled: newComputerControl,
            }),
        });
        const data = await res.json();
        if (!res.ok || !data.ok) throw new Error(data.error || 'Could not save assistant settings.');
        const stillMatches = (assistantNameInput.value.trim() || 'Sakura') === newName && (vtuberNameInput?.value.trim() || 'Sakura') === newVtuberName && (wakeWordInput.value.trim().toLowerCase() || 'hey sakura') === newWakeWord
            && (newsArea?.value.trim()||'')===newNewsArea && (avatarPresentation?.value || 'auto') === newPresentation && (userAddress?.value||'sir')===newAddress && wakeWordToggle.checked === newWakeEnabled && computerControlToggle.checked === newComputerControl;
        if (stillMatches) identityDirty = false;
        else identitySaveQueued = true;
        wakeCommandDeadline = 0;
        currentSettings = data.settings;
        applySettingsUI(currentSettings);
        await nativeWake.sync();
        flashMsg(saveStatusMsg, newWakeEnabled ? `Saved · Say "${newWakeWord}" before a command.` : 'Saved · Wake phrase off; use Listen or the microphone button.');
    } catch (err) { flashMsg(saveStatusMsg, err.message, 8000); }
    finally {
        identitySaving = false;
        if (identitySaveQueued) { identitySaveQueued = false; saveAppSettings(); }
    }
}

// ─────────────────────────── Theme & Environment System ───────────────────────────
function setupThemeEvents() {
    themeBtn?.addEventListener('click',event=>{event.stopPropagation();themePopover?.classList.toggle('hidden');});
    closeThemePopoverBtn?.addEventListener('click',()=>themePopover?.classList.add('hidden'));
    document.addEventListener('click',event=>{if(themePopover&&!themePopover.contains(event.target)&&event.target!==themeBtn)themePopover.classList.add('hidden');});
}

// ─────────────────────────── Voice System ───────────────────────────
async function loadVoicesList() {
    try {
        const res = await fetch('/api/voices');
        const data = await res.json();
        allVoicePresets = data.presets || [];
        allRvcModels    = data.rvc_models || [];
        const current   = data.current || {};

        currentVoiceId = current.selected_voice || 'kokoro_af_heart';

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
        opt.textContent = `${p.backend==='kokoro'?'Kokoro':'Offline'} · ${p.gender || ''} · ${p.language || 'English'} · ${p.name}`;
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
        ['Kokoro · Female · English', allVoicePresets.filter(p=>p.backend==='kokoro' && p.gender==='Female' && p.language==='English')],
        ['Kokoro · Male · English', allVoicePresets.filter(p=>p.backend==='kokoro' && p.gender==='Male' && p.language==='English')],
        ['Kokoro · Hindi & Hinglish', allVoicePresets.filter(p=>p.backend==='kokoro' && ['Hindi','Hinglish'].includes(p.language))],
        ['Offline · Windows voices', allVoicePresets.filter(p=>p.backend==='system')],
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
        const name=document.createElement('div'),description=document.createElement('div');
        name.className='vc-name';name.textContent=preset.name;
        description.className='vc-desc';description.textContent=preset.desc || preset.character || '';
        card.append(name,description);
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
        status.textContent = `Off · ${selected.name} selected. Enable voice changer to convert your speech.`;
        return;
    }
    const preset = allVoicePresets.find(voice => voice.id === currentVoiceId);
    const choices = allRvcModels.map(model => model.name.replace(/^🎤\s*/, '')).join(' or ');
    status.textContent = allRvcModels.length
        ? `Off · ${preset?.name || 'A built-in voice'} selected. Enable for this voice, or choose ${choices} for RVC.`
        : `Off · ${preset?.name || 'A built-in voice'} selected. Enable voice changer to use it.`;
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
            <span class="rmi-name"></span>
            <span class="rmi-badge">${m.has_index ? '✓ Index' : 'No Index'}</span>
        `;
        item.querySelector('.rmi-name').textContent = m.name;
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
    if (currentVoiceId===id && currentSettings?.selected_voice!==id) {
        selectVoiceCard(previousVoiceId);
        rvcVoiceChanger?.resumeAfterVoiceSwitch();
        return;
    }
    if (currentVoiceId===id) speechFallbackShown=false;
    if (changerWasActive && rvcVoiceChanger?.active) {
        if (currentSettings?.selected_voice !== id) {
            currentVoiceId = previousVoiceId;
            selectVoiceCard(previousVoiceId);
            rvcVoiceChanger.resumeAfterVoiceSwitch();
            updateVtuberRvcStatus('Voice could not be saved; voice changer kept the previous voice.');
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
            updateVtuberRvcStatus('Built-in voice selected · voice changer remains on.');
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
        await ensureKokoroReady();
        const res = await fetch('/api/tts/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (data.ok && data.audio) {
            await lipSync.playWithLipSync(data.audio);
            flashMsg(voiceTestStatus, data.voice_notice || '✓ Played!');
            if(data.voice_notice)addMessage(`ℹ️ ${data.voice_notice}`, 'sakura');
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
                flashMsg(voiceSaveMsg, data.voice_notice || 'Voice applied ✓');
                if(data.voice_notice)addMessage(`ℹ️ ${data.voice_notice}`, 'sakura');
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
        if (!currentSettings.fresh_instance && !selectedPmxPath && (allPmxModels.length > 0 || live2d.length > 0)) {
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
            <div class="mc-name"></div>
            <div class="mc-file"></div>
        `;
        card.querySelector('.mc-name').textContent = m.name;
        card.querySelector('.mc-file').textContent = m.filename;
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
            lowMemory:gameActive,
            glitchFixPolicy: savedGlitchPolicy === null ? 'auto' : savedGlitchPolicy === 'true' ? 'on' : 'off',
        });
        if (!result || attempt !== modelRecoveryGeneration) return;
        if (result.notice) addMessage(result.notice, 'sakura');
        lastGoodModelUrl = url;
        selectedPmxPath = decodeURIComponent(url.replace(/^\/models\//, ''));
        window.dispatchEvent(new Event('sakura-character-loaded'));
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
        const result = await viewer.loadModel(blobUrl, {lowMemory:gameActive,glitchFixPolicy: savedGlitchPolicy === null ? 'auto' : savedGlitchPolicy === 'true' ? 'on' : 'off'});
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
            const permissionStream = await navigator.mediaDevices.getUserMedia({ audio: {autoGainControl:false} });
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
    const graphics=document.getElementById('graphics-quality');if(graphics)graphics.value=mode;
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
window.addEventListener('sakura-graphics-quality',event=>{if(['low','balanced','high'].includes(event.detail))applyModelQuality(event.detail);});

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
    window.pywebview?.api?.set_surface_transparency?.(on);
    if (persist) localStorage.setItem('sakura_transparency', String(on));
    if (bgToggleBtn) {
        bgToggleBtn.setAttribute('aria-pressed', String(on));
        bgToggleBtn.title = on
            ? 'Disable streaming transparency ('+(currentSettings.transparency_hotkey || 'Ctrl+Shift+T')+')'
            : 'Enable streaming transparency ('+(currentSettings.transparency_hotkey || 'Ctrl+Shift+T')+')';
    }
}

window.addEventListener('pywebviewready', () => {
    updateAppBrand(trackingOnly);
    window.pywebview?.api?.set_surface_transparency?.(
        document.body.classList.contains('transparent-mode'));
});

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
    const constraints = { audio: {...(selectedMicId ? {deviceId:{exact:selectedMicId}} : {}),autoGainControl:false} };
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
    if(companionSleeping){const wake=wakeCommand(chatInput.value,currentSettings.wake_word||'hey sakura');if(!wake.wake){listeningStatus.textContent='Sleeping · say wake up Sakura or your wake phrase';return;}wakeCompanion();chatInput.value=wake.command;if(!wake.command)return;}
    if(chatAttachments.busy()){listeningStatus.textContent='Wait for the file to finish loading.';return;}
    const attachedIds=chatAttachments.ids();
    const text = chatInput.value.trim()||(attachedIds.length?'What is this file? Please summarize its contents.':'');
    if (!text) return;
    clearTimeout(interruptFollowupTimer);interruptFollowupUntil=0;
    if(temporaryFollowupMic){temporaryFollowupMic=false;continuousMic.stop();}
    lastDirectReplyAt = Date.now();
    cameraReactionController?.abort();
    chatBusy = true;
    window.dispatchEvent(new CustomEvent('sakura-task-progress',{detail:{active:true}}));
    const generation = ++chatReplyGeneration;
    // Load/verify local speech while the AI generates the answer, not after.
    const voiceReady=ensureKokoroReady().then(()=>({}),error=>({error}));
    replyController?.abort();
    const controller = new AbortController();
    replyController = controller;
    lipSync?.stop();
    chatInput.value = '';
    addMessage(text, 'user');
    showTypingIndicator();
    viewer?.setActivity('thinking');

    try {
        await nativeWake.pause(true);
        await voiceSaveQueue;
        const plainGreeting = /^(?:hello|hi|hey|hii+|hiya|namaste|नमस्ते)[!.\s]*$/iu.test(text);
        const noVision=attachedIds.length>0||plainGreeting||utilityRequest(text);
        const screenImage = noVision ? null : await screenShare.snapshot();
        const appearanceQuestion = /\b(?:your|ur|hair|eyes?|clothes|outfit|avatar|appearance|that girl)\b|बाल|आँख|कपड़े/iu.test(text);
        const avatarImage = screenImage && (appearanceQuestion || currentSettings.avatar_presentation==='auto' || !currentSettings.avatar_presentation) ? viewer?.captureAvatar() : null;
        const cameraImage = !noVision && !trackingOnly && !vtuberEnabled && document.getElementById('companion-camera-mode')?.value==='objects' ? companionCamera.snapshot() : null;
        if (generation !== chatReplyGeneration) return;
        const res  = await fetch('/api/chat', {
            signal: controller.signal,
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, camera_expression:Date.now()-(window.sakuraCameraExpression?.at||0)<3000?window.sakuraCameraExpression.values:undefined,shared_context:window.sakuraSharedContext||[], game_name:gameActive?detectedGameName:null, attachments:attachedIds, ai_vtuber:vtuberEnabled, screen_frames: noVision ? [] : screenShare.recentFrames(), defer_audio: true, avatar_room:!trackingOnly?viewer?.companionRoom?.capabilities():undefined, avatar_can_dance:!!viewer?.dance?.supported(), avatar_can_greet:!!viewer?.dance?.supported()&&['chest','rightArm','rightElbow','rightWrist'].every(k=>viewer.animationBones?.[k]?.bone), avatar_can_chest_tap:!!viewer?.dance?.supported()&&['chest','rightArm','rightElbow','rightWrist'].every(k=>viewer.animationBones?.[k]?.bone), avatar_dance_style:viewer?.dance?.active?.style||null, ...(screenImage ? { screen_image: screenImage } : {}), ...(avatarImage ? { avatar_image: avatarImage } : {}), ...(cameraImage && companionCamera.enabled ? {camera_image:cameraImage} : {}) }),
        });
        const data = await res.json();
        if(generation!==chatReplyGeneration)return;
        if(data.avatar_ui_action==='check_textures'){
            document.getElementById('expression-editor-btn')?.click();
            const check=document.getElementById('model-texture-snapshot-check');
            if(check?.onclick){
                await check.onclick();
                data.reply=document.getElementById('model-texture-check-status')?.textContent||'Texture check finished. Review Model Settings > Texture remapping.';
                data.speech_reply='The texture check finished. Its results are in Model Settings, under Texture remapping.';
            }
        }
        if(data.avatar_model){
            try{await loadModelFromUrl('/models/'+data.avatar_model.split('/').map(encodeURIComponent).join('/'));if(selectedPmxPath!==data.avatar_model||!viewer?.model||viewer._displayLoading)throw Error('The requested model was not successfully loaded.');data.reply='Changed to '+data.avatar_model.split('/').at(-1).replace(/\.(pmx|vrm)$/i,'')+'.';}
            catch(error){data.reply='The outfit did not load: '+error.message;}
        }
        if(data.avatar_picker)window.dispatchEvent(new CustomEvent('sakura-open-avatar-picker',{detail:{query:data.avatar_query??(typeof data.avatar_picker==='string'?data.avatar_picker:''),cloud:!!data.avatar_cloud}}));
        if(data.avatar_expression)window.sakuraExpressionEditor?.applyByLabel?.(data.avatar_expression);
        if (data.reply) {
            let presented = false;
            const presentReply = () => {
                if (presented) return;
                presented = true;
                addMessage(data.reply, 'sakura', data);
                if (generation === chatReplyGeneration) {
                    removeTypingIndicator();
                    viewer?.setEmotionFromText(data.reply);
                    if(viewer?.areAiExpressionsAutomatic?.())viewer.reactionExpressions?.begin(data.reply,data.emotion);
                    if (!lipSync?.isPlaying) viewer?.setActivity('idle');
                    if (chatPanel.classList.contains('minimized')) showSpeechBubble(data.reply);
                }
            };
            if (generation !== chatReplyGeneration) return;
            let speechGestureStarted=false;
            const startSpeechGesture=()=>{if(!speechGestureStarted&&['chest_tap','greeting_wave'].includes(data.avatar_motion)&&generation===chatReplyGeneration){speechGestureStarted=true;viewer?.companionRoom?.stop();viewer?.dance?.start(data.avatar_motion);}};
            if(data.avatar_motion==='stop'){viewer?.dance?.stop();viewer?.companionRoom?.stop();}
            else if(['groove','step','wave','twist','disco','march','hands_both','hand_left','hand_right'].includes(data.avatar_motion)){
                viewer?.dance?.start(data.avatar_motion);
                if(['groove','step','wave','twist','disco','march'].includes(data.avatar_motion))document.getElementById('dance-style').value=data.avatar_motion;
            }
            // Text and companion expression should not wait for the first
            // local speech generation. Speech starts as soon as its first
            // short phrase arrives below.
            presentReply();
            if(typeof data.avatar_motion==='string'&&data.avatar_motion.startsWith('room:')){
                if(!viewer?.companionRoom?.act(data.avatar_motion.slice(5)))listeningStatus.textContent='Room motion could not start. Check room controls and stop tracking or dancing first.';
            }
            const indicator = document.getElementById('typing-indicator');
            if (indicator) indicator.textContent = 'Preparing voice…';
            try {
                if(['laugh','laugh_bend'].includes(data.avatar_motion)){
                    const played=await playGameLaughter(data.avatar_motion,viewer,lipSync,()=>generation===chatReplyGeneration&&!trackingOnly&&(!viewer?.vtuberTrackingMode||!!viewer?.companionTracking));
                    if(!played&&generation===chatReplyGeneration)addMessage('The laugh needs an active rigged 3D model.','sakura');
                    return;
                }
                if(data.performance_audio){await lipSync.playWithLipSync(data.performance_audio);return;}
                // Animation asset preparation must not hold up speech synthesis.
                const gestureReady=Promise.resolve().then(()=>viewer?.dance?.prepare?.(data.avatar_motion)).catch(error=>console.warn('Speech gesture unavailable',error));
                if(generation!==chatReplyGeneration)return;
                const prepared=await voiceReady;if(prepared.error)throw prepared.error;
                await speakPhrases(data.speech_reply ?? data.reply, async text => {
                    const response = await fetch('/api/tts/speak', {
                        signal: controller.signal,
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ text }),
                    });
                    const speech = await response.json();
                    if (!response.ok) throw new Error(speech.error || 'Speech is unavailable.');
                    if (generation === chatReplyGeneration) {
                        if (speech.voice_notice && !speechFallbackShown) addMessage(`ℹ️ ${speech.voice_notice}`, 'sakura');
                        speechFallbackShown = !!speech.voice_notice;
                    }
                    return speech.audio;
                }, async (audio, first) => {
                    if (audio) await lipSync.playWithLipSync(audio, first ? ()=>{presentReply();void gestureReady.then(()=>{if(generation===chatReplyGeneration&&lipSync?.isPlaying)startSpeechGesture();});} : undefined);
                    else if (first){presentReply();startSpeechGesture();}
                }, () => generation === chatReplyGeneration);
            } catch (err) {
                if (generation !== chatReplyGeneration) return;
                presentReply();
                if (generation === chatReplyGeneration)startSpeechGesture();
                if (generation === chatReplyGeneration) addMessage(`⚠️ Speech unavailable: ${err.message}`, 'sakura');
            }
            // A multi-step sequence is still running on the backend: report each
            // step as it lands instead of leaving the panel silent until the end.
            if (data.workflow?.id) void narrateWorkflow(data.workflow.id).catch(error=>console.warn('Workflow updates:',error));
            if (generation === chatReplyGeneration) hideSpeechBubble();
        } else if (data.error) {
            if (generation === chatReplyGeneration) removeTypingIndicator();
            addMessage(`⚠️ Error: ${data.error}`, 'sakura');
        }
    } catch (err) {
        removeTypingIndicator();
        if (generation === chatReplyGeneration && err.name !== 'AbortError') addMessage(`⚠️ ${err.message || 'Could not connect to the backend server.'}`, 'sakura');
    } finally {
        if (generation === chatReplyGeneration){chatBusy = false;window.dispatchEvent(new CustomEvent('sakura-task-progress',{detail:{active:false}}));speechInputUsed=false;speechInterrupt.stop();await nativeWake.pause(companionSleeping);}
        if (generation === chatReplyGeneration) lastDirectReplyAt = Date.now();
        if (generation === chatReplyGeneration && !lipSync?.isPlaying) viewer?.setActivity('idle');
        if (generation === chatReplyGeneration) viewer?.reactionExpressions?.stop();
    }
}

const workflowWatchers=new Map();
window.addEventListener('pagehide',()=>{for(const controller of workflowWatchers.values())controller.abort();workflowWatchers.clear();});
async function narrateWorkflow(id) {
    if(workflowWatchers.has(id))return;
    const controller=new AbortController();workflowWatchers.set(id,controller);
    let seen=0;const pending=[];let finished=false;
    const deadline=Date.now()+180000;
    try{
        while(!controller.signal.aborted&&Date.now()<deadline){
            if(!finished){
                const response=await fetch(`/api/assistant-tools/workflow/${encodeURIComponent(id)}`,{signal:controller.signal});
                if(!response.ok){addMessage('The action sequence is still unconfirmed. Check Recent action results.','sakura');return;}
                const state=await response.json();
                for(const step of (state.steps||[]).slice(seen)){if(step.reply){addMessage(step.reply,'sakura');pending.push(step.reply);}}
                seen=(state.steps||[]).length;finished=state.status!=='running';
                if(state.status==='failed'||state.status==='cancelled')addMessage('The remaining steps were not run.','sakura');
            }
            // New user turns take priority over progress narration. Never hold
            // chatBusy while a deterministic action runs on the server.
            if(pending.length&&!chatBusy&&!reactionBusy&&!lipSync?.isPlaying&&!trackingOnly&&!vtuberEnabled){
                const generation=chatReplyGeneration,line=pending.shift();
                await speakPhrases(line,async text=>{
                    const response=await fetch('/api/tts/speak',{signal:controller.signal,method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})});
                    if(!response.ok)return null;return (await response.json()).audio;
                },async audio=>{if(audio&&generation===chatReplyGeneration&&!chatBusy)await lipSync.playWithLipSync(audio);},()=>!controller.signal.aborted&&generation===chatReplyGeneration&&!chatBusy).catch(()=>{});
            }
            if(finished&&!pending.length)return;
            await new Promise(resolve=>setTimeout(resolve,800));
        }
    }finally{workflowWatchers.delete(id);}
}

async function setGameLocalModel(active) {
    if(currentSettings?.llm_provider!=='ollama')return;
    const response=await fetch('/api/game-mode/model',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({active})});
    const data=await response.json();if(!response.ok)throw Error(data.error||'Could not switch game model.');
    return data;
}

async function setGameCloudFallback(active, reason = '') {
    if (active === gameCloudFallbackActive) return;
    const response = await fetch('/api/game-mode/cloud-fallback', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ active }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Could not change the Game Mode AI provider.');
    gameCloudFallbackActive = !!data.active;
    if (active && data.active) {
        lastGameVramNotice = '';
        listeningStatus.textContent = `High VRAM usage${reason ? ` (${reason})` : ''} · Game Mode switched to ${data.provider} cloud AI`;
    } else if (active && data.reason) {
        const notice = `High VRAM usage · ${data.reason} Staying on local AI.`;
        if (lastGameVramNotice !== notice) listeningStatus.textContent = notice;
        lastGameVramNotice = notice;
    } else if (!active && data.provider === 'ollama') {
        listeningStatus.textContent = 'VRAM pressure cleared · Game Mode returned to local AI';
        lastGameVramNotice = '';
    }
}

async function updateGameVramFallback(game) {
    if (currentSettings?.llm_provider !== 'ollama' || currentSettings.game_cloud_auto_enabled===false) return;
    const gpus = Array.isArray(game.gpus) ? game.gpus : [];
    const measured = gpus.filter(gpu => Number.isFinite(gpu.vram_percent) && Number.isFinite(gpu.vram_total_bytes) && gpu.vram_total_bytes > 0);
    if (!measured.length) return;
    const gpu = measured.reduce((highest, item) => item.vram_percent > highest.vram_percent ? item : highest);
    const freeBytes = Number.isFinite(gpu.vram_used_bytes) ? gpu.vram_total_bytes - gpu.vram_used_bytes : null;
    const isHigh = gpu.vram_percent >= 90 || (freeBytes !== null && freeBytes < 1024 ** 3);
    const recovered = gpu.vram_percent <= 82 && (freeBytes === null || freeBytes >= 1.5 * 1024 ** 3);
    const reason = `${gpu.name || 'GPU'} at ${gpu.vram_percent}% VRAM`;
    if (!gameCloudFallbackActive && isHigh) await setGameCloudFallback(true, reason);
    else if (gameCloudFallbackActive && recovered) await setGameCloudFallback(false);
}

async function leaveGameMode() {
    const wasActive = gameActive;
    if(!wasActive)return;
    gameActive = false;
    gameReady = false;
    if (gameCloudFallbackActive) {
        try { await setGameCloudFallback(false); }
        catch (error) { listeningStatus.textContent = `Game mode ended · ${error.message}`; }
    }
    try { await setGameLocalModel(false); } catch(error) { listeningStatus.textContent=error.message; }
    reactionsEnabled = gamePriorReactions;
    screenReactBtn.textContent = reactionsEnabled?'💬 Reactions on':'💬 Reactions off';
    screenReactBtn.setAttribute('aria-pressed',String(reactionsEnabled));
    if (gameStartedScreen) screenShare.stop();
    gameStartedScreen = false;
    const resume = gameResumeMic;
    gameResumeMic = false;
    if (resume && !continuousMic.enabled) await startDesktopListening(true);
    if (!wasActive) return;
    listeningStatus.textContent = 'Game mode ended · your selected AI is unchanged';
}

async function checkGameMode() {
    if (trackingOnly || viewer?._displayLoading || viewer?._modelSwitchQueue) return;
    if (speechRecognitionBusy > 0) return;
    if (!autoGameEnabled || autoGameBusy || !window.pywebview?.api?.game_status) return;
    autoGameBusy = true;
    try {
        const game = await window.pywebview.api.game_status();
        detectedGameName=game.detected?String(game.name||'').slice(0,100):'';
        if (!autoGameEnabled) return;
        gameForeground = !!game.foreground;
        if (!game.detected) {
            if (gameActive) {
                await leaveGameMode();
            }
            return;
        }
        lastGameSeen = Date.now();
        if (gameActive && !chatBusy && !reactionBusy && !lipSync?.isPlaying) {
            try { await updateGameVramFallback(game); }
            catch (error) { listeningStatus.textContent = `Game Mode VRAM fallback: ${error.message}`; }
        }
        if (!gameActive) {
            await setGameLocalModel(true);
            gamePriorReactions=reactionsEnabled;
            gameResumeMic = continuousMic.enabled;
            gameActive = true;
            listeningStatus.textContent = `Game detected: ${game.name} · connecting your selected AI`;
        }
        if (gameReady || chatBusy || reactionBusy || lipSync?.isPlaying) return;
        if (!autoGameEnabled) return;
        if (!screenShare.enabled && window.sakuraCompanionScreenRequested!==false) { await screenShare.toggle(); gameStartedScreen = screenShare.enabled; }
        if (!screenShare.enabled) throw new Error('Screen access was not enabled.');
        if (!autoGameEnabled) return;
        // Screen reactions must not depend on microphone permission succeeding.
        reactionsEnabled = true;
        screenReactBtn.textContent = '💬 Reactions on';
        screenReactBtn.setAttribute('aria-pressed', 'true');
        screenViewBtn.textContent = '🖥️ Screen on';
        screenViewBtn.setAttribute('aria-pressed', 'true');
        if(!vtuberEnabled&&!continuousMic.enabled)await startDesktopListening(true);
        gameReady = true;
        if (!gameCloudFallbackActive) listeningStatus.textContent = `Game detected: ${game.name} · ${currentSettings.llm_provider==='ollama'?currentSettings.ollama_model:currentSettings.llm_provider} · `+
            (continuousMic.enabled||nativeWake.enabled()?(currentSettings.game_play_mode==='multiplayer'?'Multiplayer · say the wake phrase to address Sakura':'Single-player · microphone on'):'Microphone unavailable · click Listen and check microphone permission/device');
    } catch (error) { listeningStatus.textContent = `Game mode: ${error.message}`; }
    finally { autoGameBusy = false; }
}

async function enableAiVtuberScreen() {
    if(trackingOnly)throw new Error('AI VTuber is available in Gemini and Local LLM modes.');
    if(!vtuberEnabled){vtuberPriorReactions=reactionsEnabled;vtuberStartedScreen=!screenShare.enabled;}
    if(!screenShare.enabled)await screenShare.toggle();
    if(!screenShare.enabled)throw new Error('Screen sharing was not enabled. Start AI VTuber again and choose the screen to share.');
    document.getElementById('vtuber-screen-enabled').checked=true;
    reactionsEnabled=true;
    screenReactBtn.textContent='💬 Reactions on';
    screenReactBtn.setAttribute('aria-pressed','true');
    lastReactionText='';
}

function restoreAiVtuberScreen() {
    if(vtuberStartedScreen&&!gameActive)screenShare.stop();
    reactionsEnabled=vtuberPriorReactions&&screenShare.enabled;
    screenReactBtn.textContent=reactionsEnabled?'💬 Reactions on':'💬 Reactions off';
    screenReactBtn.setAttribute('aria-pressed',String(reactionsEnabled));
    vtuberStartedScreen=false;
}

async function pollVtuberChat() {
    if(companionSleeping)return;
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
                body: JSON.stringify({author: message.author, text: message.text, avatar_can_dance:!!viewer?.dance?.supported(),avatar_dance_style:viewer?.dance?.active?.style||null,screen_image: screenShare.enabled ? await screenShare.snapshot() : null, screen_frames: screenShare.recentFrames()})});
            const result = await replyResponse.json();
            if (!replyResponse.ok) throw new Error(result.error);
            if (!current() || !result.reply || /^\s*\[QUIET\]/i.test(result.reply)) return;
            addMessage(`${message.author}: ${message.text}`, 'user');
            addMessage(result.reply, 'sakura');
            resumeMic = continuousMic.enabled;
            if (resumeMic) continuousMic.stop();
            if(result.avatar_motion==='stop'){viewer?.dance?.stop();viewer?.companionRoom?.stop();}
            else if(['groove','step','wave','twist','disco','march'].includes(result.avatar_motion))viewer?.dance?.start(result.avatar_motion);
            if(result.performance_audio){
                viewer?.setEmotionFromText(result.reply);
                await lipSync.playWithLipSync(result.performance_audio);
                return;
            }
            await speakPhrases(result.reply, async text => {
                const audioResponse = await fetch('/api/tts/speak', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text})});
                const speech = await audioResponse.json();
                if (!audioResponse.ok) throw new Error(speech.error);
                return speech.audio;
            }, async audio => {
                showSpeechBubble(result.reply);
                viewer?.setEmotionFromText(result.reply);
                if(viewer?.areAiExpressionsAutomatic?.())viewer.reactionExpressions?.begin(result.reply);
                if (audio) await lipSync.playWithLipSync(audio);
            }, current);
        } finally {
            lastCoHostSpeech = Date.now();
            vtuberSpeaking = false;
            reactionBusy = false;
            viewer?.reactionExpressions?.stop();
            hideSpeechBubble();
            if (resumeMic) await startDesktopListening(true);
        }
    } catch (error) { document.getElementById('vtuber-status').textContent = error.message; }
    finally { vtuberPollBusy = false; }
}

async function reactToScreen(initialCheck = false) {
    if(companionSleeping)return;
    if (trackingOnly || viewer?._displayLoading || viewer?._modelSwitchQueue) return;
    // Human input has priority even in multiplayer. Transcription may take
    // longer than the recent-mic grace period on a cold CPU Whisper model.
    if (speechRecognitionBusy > 0 || Date.now() - lastMicActivity < 6000) return;
    const gameWatch=gameActive&&gameReady&&!initialCheck&&currentSettings.game_play_mode==='multiplayer';
    if (!gameWatch&&!initialCheck && Date.now() - lastDirectReplyAt < 30000) return;
    if(gameWatch&&Date.now()-lastGameWatch<10000)return;
    const vtuberScreens = vtuberEnabled && document.getElementById('vtuber-screen-enabled').checked;
    if (!gameWatch&&!initialCheck && Date.now() - lastCoHostSpeech < 20000) return;
    if (!initialCheck && autoGameEnabled && gameActive && !gameForeground) return;
    if ((!reactionsEnabled && !vtuberScreens && !initialCheck) || !screenShare.enabled || reactionBusy || chatBusy || isRecording ||
        lipSync?.isPlaying || (!gameWatch&&!initialCheck && Date.now() - lastMicActivity < 6000)) return;
    reactionBusy = true;
    if(gameWatch)lastGameWatch=Date.now();
    const generation = chatReplyGeneration;
    let resumeMic = false;
    let expressionStarted=false;
    try {
        const screen_image = await screenShare.snapshot();
        if (speechRecognitionBusy > 0 || chatBusy || Date.now() - lastMicActivity < 6000) return;
        const response = await fetch('/api/chat', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({text: 'Screen companion reaction', screen_image, screen_frames: screenShare.recentFrames(), screen_reaction: true, screen_check: initialCheck, game_watch:gameWatch, ai_vtuber: vtuberScreens, defer_audio: true}),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Screen viewing is unavailable.');
        if(['laugh','laugh_bend'].includes(data.game_result)&&(!viewer?.dance?.supported()||viewer.live2d))return;
        if(gameWatch&&generation===chatReplyGeneration&&screenShare.enabled&&(reactionsEnabled||vtuberScreens)&&!trackingOnly&&(!viewer?.vtuberTrackingMode||!!viewer?.companionTracking)&&['victory','defeat','laugh','laugh_bend'].includes(data.game_result)){
            if(!['laugh','laugh_bend'].includes(data.game_result))viewer?.dance?.start(data.game_result);
            viewer?.reactionExpressions?.begin(data.reply,['victory','laugh','laugh_bend'].includes(data.game_result)?'happy':'concerned');
        }
        if (!data.reply || /^\s*\[QUIET\]/i.test(data.reply) || generation !== chatReplyGeneration ||
            (!initialCheck && Date.now() - lastDirectReplyAt < 30000) ||
            (!reactionsEnabled && !vtuberScreens && !initialCheck) || !screenShare.enabled || chatBusy || speechRecognitionBusy > 0 || Date.now() - lastMicActivity < 6000) return;
        const normalizedReaction = data.reply.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '');
        if(window.sakuraProactive&&!window.sakuraProactive.consider({reply:data.reply,event:data.game_result,manual:initialCheck,busy:chatBusy||speechRecognitionBusy>0}))return;
        if (!initialCheck && normalizedReaction === lastReactionText) return;
        lastReactionText = normalizedReaction;
        if(!gameWatch&&!initialCheck&&!trackingOnly&&(!viewer?.vtuberTrackingMode||!!viewer?.companionTracking)&&
            (reactionsEnabled||vtuberScreens)&&['victory','defeat','laugh','laugh_bend'].includes(data.game_result)){
            if(!['laugh','laugh_bend'].includes(data.game_result))viewer?.dance?.start(data.game_result);
            viewer?.reactionExpressions?.begin(data.reply,['victory','laugh','laugh_bend'].includes(data.game_result)?'happy':'concerned');
        }
        listeningStatus.textContent = 'Live screen connected · recent frames analyzed';
        addMessage(data.reply, 'sakura', data);
        resumeMic = continuousMic.enabled;
        if (resumeMic) continuousMic.stop();
        if(['laugh','laugh_bend'].includes(data.game_result)){
            try{await playGameLaughter(data.game_result,viewer,lipSync,()=>generation===chatReplyGeneration&&screenShare.enabled&&(reactionsEnabled||vtuberScreens)&&!chatBusy&&!trackingOnly&&(!viewer?.vtuberTrackingMode||!!viewer?.companionTracking));}
            catch(error){viewer?.dance?.stop();console.warn('Recorded laughter unavailable:',error);}
        }
        await ensureKokoroReady();
        await speakPhrases(data.reply, async text => {
            const res = await fetch('/api/tts/speak', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text})});
            const speech = await res.json();
            if (!res.ok) throw new Error(speech.error || 'Speech unavailable.');
            return speech.audio;
        }, async audio => {
            showSpeechBubble(data.reply);
            viewer?.setEmotionFromText(data.reply);
            if(!expressionStarted&&reactionsEnabled&&!trackingOnly&&(!viewer?.vtuberTrackingMode||!!viewer?.companionTracking)){
                viewer?.reactionExpressions?.begin(data.reply,['victory','laugh','laugh_bend'].includes(data.game_result)?'happy':data.game_result==='defeat'?'concerned':null);expressionStarted=true;
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
        if (resumeMic) await startDesktopListening(true);
    }
}

async function reactToCamera() {
    if(companionSleeping)return;
    const ready=()=>companionCamera.enabled&&document.getElementById('companion-camera-mode')?.value==='objects'&&!trackingOnly&&!vtuberEnabled&&!aiVtuberStarting&&
        document.getElementById('companion-camera-comments').checked&&!chatBusy&&!isRecording&&speechRecognitionBusy===0&&
        !lipSync?.isPlaying&&Date.now()-lastDirectReplyAt>=60000&&Date.now()-lastMicActivity>=10000;
    if(!ready()||reactionBusy)return;
    const camera_image=companionCamera.snapshot();if(!camera_image)return;
    const cameraGeneration=companionCamera.generation,generation=chatReplyGeneration;
    const active=()=>ready()&&cameraGeneration===companionCamera.generation&&generation===chatReplyGeneration;
    const controller=new AbortController();cameraReactionController=controller;reactionBusy=true;
    let resumeMic=false;
    let cameraExpressionStarted=false;
    try{
        const response=await fetch('/api/chat',{method:'POST',signal:controller.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({text:'Optional camera comment',camera_image,camera_reaction:true,defer_audio:true})});
        const data=await response.json();
        if(!response.ok)throw new Error(data.error||'Camera observation unavailable.');
        if(!active()||!data.reply||/^\s*\[QUIET\]/i.test(data.reply))return;
        addMessage(data.reply,'sakura');lastDirectReplyAt=Date.now();
        viewer?.setEmotionFromText(data.reply);
        if(viewer?.areAiExpressionsAutomatic?.())cameraExpressionStarted=!!viewer.reactionExpressions?.begin(data.reply,data.emotion);
        resumeMic=continuousMic.enabled;if(resumeMic)continuousMic.stop();
        await ensureKokoroReady();
        await speakPhrases(data.reply,async text=>{
            const res=await fetch('/api/tts/speak',{method:'POST',signal:controller.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({text})});
            const speech=await res.json();if(!res.ok)throw new Error(speech.error||'Speech unavailable.');return speech.audio;
        },async audio=>{if(audio)await lipSync.playWithLipSync(audio);},()=>companionCamera.enabled&&document.getElementById('companion-camera-comments').checked&&cameraGeneration===companionCamera.generation&&generation===chatReplyGeneration&&!controller.signal.aborted&&!trackingOnly&&!vtuberEnabled);
    }catch(error){if(error.name!=='AbortError'&&companionCamera.enabled)document.getElementById('companion-camera-status').textContent=error.message;}
    finally{if(cameraExpressionStarted&&generation===chatReplyGeneration)viewer?.reactionExpressions?.stop();if(cameraReactionController===controller)cameraReactionController=null;reactionBusy=false;if(resumeMic&&!trackingOnly&&!vtuberEnabled)await startDesktopListening(true);}
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
        chatAttachments.clear();
        messagesEl.innerHTML = '';
        addMessage('🌸 Memory cleared! What would you like to talk about next?', 'sakura');
    } catch (err) { addMessage(err.message, 'sakura'); }
}

// ─────────────────────────── Voice / STT ───────────────────────────
async function handleToggleMic() {
    if(document.body.classList.contains('agent-mode'))return;
    if (vtuberEnabled || aiVtuberStarting) { listeningStatus.textContent = "AI VTuber uses computer audio and chat; microphone is excluded."; return; }
    if (!isRecording) {
        if(lipSync?.isPlaying)document.getElementById('interrupt-btn').click();
        await nativeWake.pause(true);
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {...(selectedMicId ? {deviceId:{exact:selectedMicId}} : {}),autoGainControl:false},
            });
            if(document.body.classList.contains('agent-mode')){stream.getTracks().forEach(t=>t.stop());return;}
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];
            mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };
            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                stream.getTracks().forEach(t => t.stop());
                try{await sendAudioForSTT(audioBlob);}finally{await nativeWake.pause(companionSleeping);}
            };
            mediaRecorder.start();
            isRecording = true;
            micBtn.classList.add('recording');
        } catch (err) { await nativeWake.pause(companionSleeping);alert('Could not access microphone: ' + err.message); }
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
    if(document.body.classList.contains('agent-mode'))return;
    if (trackingOnly || vtuberEnabled || aiVtuberStarting) return;
    const continuous = options.continuous === true;
    const captureGeneration = continuousMic.generation;
    if (continuous && !continuousMic.enabled) return;
    speechRecognitionBusy++;
    showTypingIndicator();
    const formData = new FormData();
    formData.append('audio', blob, 'speech.webm');
    try {
        const res  = await fetch('/api/stt', { method: 'POST', body: formData, signal:AbortSignal.timeout(90000) });
        const data = await res.json();
        if(document.body.classList.contains('agent-mode'))return;
        if (!res.ok) throw new Error(data.error || `Speech recognition failed (${res.status})`);
        removeTypingIndicator();
        if (vtuberEnabled || aiVtuberStarting) return;
        // Discard STT that completed after the user stopped the recorder.
        if (continuous && (!continuousMic.enabled || continuousMic.generation !== captureGeneration)) return;
        if (data.text?.trim()) {
            const raw = data.text.trim();
            if(companionSleeping){const wake=wakeCommand(raw,currentSettings.wake_word||'hey sakura');if(!wake.wake)return;wakeCompanion();if(wake.command){chatInput.value=wake.command;await handleSendMessage();}return;}
            if(isSpeechInterrupt(raw,currentSettings.wake_word||'hey sakura')&&(chatBusy||lipSync?.isPlaying)){
                document.getElementById('interrupt-btn').click();
                interruptFollowupUntil=Date.now()+15000;
                listeningStatus.textContent='Paused. Ask your next question.';
                return;
            }
            if(Date.now()<interruptFollowupUntil){
                interruptFollowupUntil=0;clearTimeout(interruptFollowupTimer);
                if(temporaryFollowupMic){temporaryFollowupMic=false;continuousMic.stop();}
                speechInputUsed=true;chatInput.value=raw;await handleSendMessage();return;
            }
            speechInputUsed=!continuous;
            // Speaker playback can reach the microphone despite browser echo cancellation.
            // Automatic listening needs explicit address while media audio is active.
            const mediaWake = continuous && !continuousMic.userRequested && (gameActive ? currentSettings.game_play_mode==='multiplayer' : screenAudio.playbackActive());
            if ((continuous && currentSettings.wake_word_enabled && !continuousMic.userRequested) || mediaWake) {
                const query = extractWakeCommand(raw, currentSettings.wake_word || 'hey sakura');
                if (query !== null) {
                    if (!query) {
                        wakeCommandDeadline = mediaWake ? 0 : Date.now() + 15000;
                        listeningStatus.textContent = mediaWake ? 'Say the wake phrase and your command together while video audio is on' : 'Ready—say your command';
                        return;
                    }
                    wakeCommandDeadline = 0;
                    chatInput.value = query;
                    await handleSendMessage();
                } else if (continuous && !mediaWake && Date.now() < wakeCommandDeadline) {
                    wakeCommandDeadline = 0;
                    chatInput.value = raw;
                    await handleSendMessage();
                } else if (mediaWake) {
                    wakeCommandDeadline = 0;
                    listeningStatus.textContent = `Video audio is context · say ${currentSettings.wake_word || 'hey sakura'} or use the mic button`;
                } else if (!continuous) {
                    addMessage(`*(Wake word "${currentSettings.wake_word}" not heard — say it first)*`, 'sakura');
                }
            } else {
                chatInput.value = raw;
                await handleSendMessage();
            }
        } else if (!continuous) {
            addMessage('*(I could not hear a clear phrase. Check the selected microphone, then hold the mic button while speaking.)*', 'sakura');
        } else {
            listeningStatus.textContent='No clear speech recognized. Check the selected microphone and try again.';
        }
    } catch (err) {
        removeTypingIndicator();
        listeningStatus.textContent=`Speech recognition failed: ${err.message}. Click the microphone to retry.`;
        addMessage(`⚠️ Speech recognition failed: ${err.message}`, 'sakura');
        console.error('STT failed:', err);
    } finally {
        removeTypingIndicator();
        speechRecognitionBusy = Math.max(0, speechRecognitionBusy - 1);
    }
}

// ─────────────────────────── UI Helpers ───────────────────────────
const SERVER_URL = /https?:\/\/(?:127\.0\.0\.1|localhost)(?::\d{1,5})?(?:\/[^\s<>"'`)\]]{0,200})?/g;
// An address a task actually served on this machine is the useful part of the reply, so it is
// shown as a highlighted link. Only loopback hosts are linked: an address that came out of a
// model reply or a fetched page is not trusted enough to stand out as actionable.
function appendWithServerLinks(target, text) {
    const source = String(text ?? '');
    let last = 0, match;
    SERVER_URL.lastIndex = 0;
    while ((match = SERVER_URL.exec(source))) {
        let url = match[0], tail = '';
        while (/[.,;:!?]$/.test(url)) { tail = url.slice(-1) + tail; url = url.slice(0, -1); }
        if (match.index > last) target.append(document.createTextNode(source.slice(last, match.index)));
        if (url) {
            const link = document.createElement('a');
            link.className = 'server-link'; link.href = url; link.textContent = url;
            link.target = '_blank'; link.rel = 'noopener noreferrer';
            target.append(link);
        }
        if (tail) target.append(document.createTextNode(tail));
        last = match.index + match[0].length;
    }
    if (last < source.length) target.append(document.createTextNode(source.slice(last)));
    if (!source) target.textContent = '';
}

function addMessage(text, sender, evidence = null) {
    if(sender==='sakura'&&evidence&&typeof text==='string'&&text.trim()!=='[QUIET]'){
        window.sakuraLatestReply=text;
        window.dispatchEvent(new CustomEvent('sakura-companion-reply',{detail:{text}}));
    }
    const msg = document.createElement('div');
    msg.className = `message ${sender}`;
    appendWithServerLinks(msg, text);
    // Only backend replies carry provenance. Startup notices, model loading
    // progress and UI errors are not factual AI answers and must not display
    // a misleading "Unknown" verification badge.
    if (sender === 'sakura' && evidence) appendEvidence(msg, evidence);
    if(sender==='sakura'&&evidence?.mode_guide){
        const guide=document.createElement('button');guide.type='button';guide.textContent='Show Friend / Teacher controls';
        guide.onclick=()=>{
            const event=new CustomEvent('sakura-open-conversation-mode',{cancelable:true,detail:{mode:evidence.mode_guide}});
            window.dispatchEvent(event);
            if(!event.defaultPrevented){guide.textContent='Return to Companion mode, then open the left speaker icon > Voice & speech';}
        };
        msg.appendChild(guide);
    }
    if(sender==='sakura'&&evidence?.agent_task?.id){
        const task=evidence.agent_task,card=document.createElement('section');
        const stateText=document.createElement('p'),details=document.createElement('pre'),actions=document.createElement('div');
        details.style.cssText='white-space:pre-wrap;max-height:220px;overflow:auto;font-size:12px';
        card.append(stateText,details,actions);msg.append(card);
        const endpoint='/api/companion/agent-tasks/'+encodeURIComponent(task.id);
        let stopped=false;
        const send=async(suffix,body)=>{
            const response=await fetch(endpoint+suffix,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
            const result=await response.json();if(!response.ok)throw Error(result.error||'Task operation failed.');return result;
        };
        const button=(label,handler)=>{const b=document.createElement('button');b.type='button';b.textContent=label;
            b.onclick=async()=>{for(const item of actions.children)item.disabled=true;try{await handler();}catch(error){stateText.textContent=error.message;for(const item of actions.children)item.disabled=false;}};actions.append(b);};
        const refresh=async()=>{
            if(stopped||!card.isConnected)return;
            try{
                const response=await fetch(endpoint),state=await response.json();if(!response.ok)throw Error(state.error||'Could not read task progress.');
                stateText.textContent=state.error||('Task: '+(state.planning?'planning / running':state.run.status));
                details.textContent=state.run.goal+'\nWorkspace: '+state.run.workspace+'\n'+(state.pending?state.pending.tool+'\n'+JSON.stringify(state.pending.arguments,null,2):state.run.summary||state.run.plan||'');
                actions.replaceChildren();
                if(state.pending&&!state.planning){
                    for(const [label,approved] of [['Approve step',true],['Reject step',false]])button(label,async()=>{await send('/decide',{action:state.pending.id,approved});await refresh();});
                }
                if(task.schedule_minutes&&state.run.status==='completed')button('Approve repeat every '+task.schedule_minutes+' minutes',async()=>{
                    const result=await send('/schedule',{approved:true});stopped=true;stateText.textContent='Scheduled every '+result.minutes+' minutes. Sakura must remain running.';actions.replaceChildren();
                });
                button('Open Agent mode',async()=>{document.getElementById('agent-mode-toggle')?.click();});
                if(state.planning)setTimeout(refresh,1200);
            }catch(error){stateText.textContent=error.message;}
        };
        setTimeout(refresh,0);
    }
    if(sender==='sakura'&&evidence?.command_approval){
        const actions=document.createElement('div');
        for(const [label,approved] of [['Approve & run',true],['Reject',false]]){
            const button=document.createElement('button');button.type='button';button.textContent=label;
            button.onclick=async()=>{
                for(const item of actions.children)item.disabled=true;
                const generation=chatReplyGeneration, controller=new AbortController();
                const wasBusy=chatBusy;chatBusy=true;
                try{
                    const response=await fetch('/api/commands/decide',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:evidence.command_approval,approved})});
                    const result=await response.json();
                    const line=result.reply||result.error||'The action could not be confirmed.';
                    addMessage(line,'sakura');
                    if(result.workflow?.id){
                        try{
                            await speakPhrases(line, async text=>{
                                const speech=await fetch('/api/tts/speak',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})});
                                const audio=await speech.json();
                                if(!speech.ok)throw new Error(audio.error||'Speech is unavailable.');
                                return audio.audio;
                            }, async audio=>{if(audio)await lipSync.playWithLipSync(audio);}, ()=>generation===chatReplyGeneration);
                        }catch(_){}
                        void narrateWorkflow(result.workflow.id).catch(error=>console.warn('Workflow updates:',error));
                    }
                }catch(_){addMessage('The action result could not be confirmed. Check before trying again.','sakura');}
                finally{if(!wasBusy)chatBusy=false;}
            };actions.append(button);
        }msg.append(actions);
    }

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
    const faceTrackingSource = document.getElementById('face-tracking-source');
    const companionFaceTrackingSource = document.getElementById('companion-face-tracking-source');
    const faceTrackingHelp = document.getElementById('face-tracking-source-help');
    const vbridgerStatus = document.getElementById('vbridger-status');
    const nvidiaRtxToggle = document.getElementById('settings-nvidia-rtx-toggle');
    const savedFaceSource = localStorage.getItem('sakura_face_tracking_source');
    if (['webcam','nvidia_broadcast','nvidia_ar','nvidia_expressionapp','nvidia_vts','vbridger'].includes(savedFaceSource)) faceTrackingSource.value = savedFaceSource;
    companionFaceTrackingSource.value = faceTrackingSource.value;
    const trackingBackend = document.getElementById('tracking-backend');
    const trackingBackendHelp = document.getElementById('tracking-backend-help');
    const savedBackend = localStorage.getItem('sakura_tracking_backend');
    if (['mediapipe','leap_motion','nvidia_gpu'].includes(savedBackend)) trackingBackend.value = savedBackend;
    const backendHelp = {
        mediapipe: 'MediaPipe runs locally from your webcam. It tracks face, arm pose and both hands/fingers.',
        leap_motion: 'Leap Motion uses the local Ultraleap WebSocket service for detailed finger tracking; the webcam continues tracking face and arm pose. Connect the controller and start its service first.',
        nvidia_gpu: 'Runs MediaPipe face, arm and finger landmark models with the browser GPU delegate. Chrome/WebView and Windows must expose an NVIDIA GPU; if GPU startup fails, switch back to MediaPipe.'
    };
    const graphicsRenderer = () => {
        try {
            const gl = document.createElement('canvas').getContext('webgl2') || document.createElement('canvas').getContext('webgl');
            const ext = gl?.getExtension('WEBGL_debug_renderer_info');
            return ext ? String(gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) || '') : '';
        } catch (_) { return ''; }
    };
    trackingBackend.addEventListener('change', () => {
        localStorage.setItem('sakura_tracking_backend', trackingBackend.value);
        const renderer = trackingBackend.value === 'nvidia_gpu' ? graphicsRenderer() : '';
        const detected = renderer ? ` WebGL renderer: ${renderer}.` : ' The browser does not expose its GPU renderer; it may use an integrated GPU or software rendering.';
        trackingBackendHelp.textContent = (backendHelp[trackingBackend.value] || backendHelp.mediapipe) + detected;
        if (avatarTracking.enabled) { avatarTracking.stop(); start.click(); }
        else cameraStatus.textContent = `${trackingBackend.options[trackingBackend.selectedIndex].text} selected. Press Start tracking to use it.`;
    });
    if (trackingBackend.value === 'nvidia_gpu') {
        const renderer = graphicsRenderer();
        trackingBackendHelp.textContent = backendHelp.nvidia_gpu + (renderer ? ` WebGL renderer: ${renderer}.`
            : ' The browser does not expose its GPU renderer; it may use an integrated GPU or software rendering.');
    } else trackingBackendHelp.textContent = backendHelp[trackingBackend.value] || backendHelp.mediapipe;
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
            else await ensureKokoroReady();
            await window.sakuraModelSettings?.stopMicrophone();
            await rvcVoiceChanger.start(selectedMicId);
            viewer.voiceChangerActive=true;
            viewer?.setTrackingMouthEnabled(false);
        } catch (error) {
            await stopVtuberVoiceChanger(`Could not start voice changer: ${error.message}`);
        }
    });
    const trackingDefaults = {smoothing:.25, range:1, handRange:1.3, blinkGain:1, gaze:1, linkBlinks:false, fps:15};
    let trackingOptions;
    try { trackingOptions = {...trackingDefaults, ...JSON.parse(localStorage.getItem('sakura_tracking_options') || '{}')}; }
    catch (_) { trackingOptions = {...trackingDefaults}; }
    const trackingSliders = {'tracking-smoothing':'smoothing', 'tracking-range':'range', 'tracking-hand-range':'handRange',
        'tracking-blink-gain':'blinkGain', 'tracking-gaze-strength':'gaze'};
    const applyTrackingOptions = () => {
        if (viewer) viewer.trackingOptions = trackingOptions;
        avatarTracking.frameRate = [15,24,30,60].includes(Number(trackingOptions.fps)) ? Number(trackingOptions.fps) : 15;
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
    const restartTracking = () => { if (avatarTracking.enabled) avatarTracking.start(camera.value, avatarTracking.backend).catch(error => { status.textContent=error.message; cameraStatus.textContent=error.message; }); };
    document.getElementById('tracking-fps').addEventListener('change', e => {
        trackingOptions.fps = Number(e.target.value); applyTrackingOptions(); restartTracking();
    });
    document.getElementById('tracking-reset-options').addEventListener('click', () => {
        trackingOptions = {...trackingDefaults}; applyTrackingOptions(); restartTracking();
    });
    applyTrackingOptions();
    let handsEnabled = true;
    try { handsEnabled = localStorage.getItem('sakura_hand_tracking_enabled') !== 'false'; } catch (_) {}
    handsToggle.setAttribute('aria-pressed',String(handsEnabled));
    handsToggle.classList.toggle('active',handsEnabled);
    handsToggle.textContent = `Hand tracking: ${handsEnabled ? 'On' : 'Off'}`;
    avatarTracking.setHandTracking(handsEnabled);
    window.addEventListener('sakura-physics-status-changed',()=>updatePhysicsUI(viewer?.physics?.mode));
    const reader = new ChatReader({
        onSentiment:text=>{
            if(!text){viewer?.reactionExpressions?.stop();return;}
            if(!document.getElementById('reader-sentiment')?.checked||viewer?.manualExpressions?.size)return;
            const mood=/\b(?:haha|lol|love|awesome|great|happy|congrats)\b/i.test(text)?'happy':/\b(?:sad|sorry|lost|unhappy|disappointed)\b/i.test(text)?'concerned':null;
            if(mood)viewer?.reactionExpressions?.begin(text,mood);
        },
        onEnabled: enabled => { if (viewer) viewer.chatReaderActive = enabled; },
        status: message => { status.textContent = message; },
        stopAudio: () => lipSync?.stop(),
        play: audio => lipSync.playWithLipSync(audio, null, {volume:Number(document.getElementById('reader-volume').value)/100}),
        speak: async (text, signal) => {
            await voiceSaveQueue;
            await ensureKokoroReady();
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
                body:JSON.stringify({service:document.getElementById('reader-service')?.value||'youtube',twitch_link:document.getElementById('reader-twitch-link')?.value.trim()||'',link:document.getElementById('reader-chat-link').value.trim(),twitch_username:document.getElementById('reader-twitch-username')?.value.trim()||'',twitch_token:document.getElementById('reader-twitch-token')?.value||''})});
            if(document.getElementById('reader-twitch-token'))document.getElementById('reader-twitch-token').value='';
            const data = await response.json();
            if (!response.ok) throw new Error(data.error);
            reader.start(); status.textContent='Chat Reader on · camera off · waiting for live chat';
        } catch(error) { status.textContent=error.message; }
        finally { if(document.getElementById('reader-twitch-token'))document.getElementById('reader-twitch-token').value='';switching=false; }
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
        camera.replaceChildren(new Option('Default camera', ''),new Option('Sakura Mobile · paired phone','sakura-mobile'));
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
    const faceSourceHelp = {
        webcam: 'Webcam face tracking uses the local MediaPipe tracker. Choose a hand/arm backend below independently.',
        nvidia_broadcast: 'Uses the NVIDIA Broadcast virtual camera with Sakura’s GPU-accelerated MediaPipe tracker. This is not the separate NVIDIA Broadcast Expression Tracker included with VTube Studio.',
        nvidia_ar: 'Sakura native RTX mode runs NVIDIA AR SDK Face Expressions directly on the selected camera feed.',
        nvidia_expressionapp: 'Runs the NVIDIA Broadcast Tracker ExpressionApp engine from the free ~2 GB Steam DLC. VTube Studio itself stays closed; choose the installed MXTracker/v2 folder below.',
        nvidia_vts: 'Use VTube Studio’s separate NVIDIA RTX/Broadcast Expression Tracker, connect VBridger to VTube Studio, then set VBridger VMC output to 127.0.0.1:39539. Sakura keeps webcam tracking for head pose and reads VMC facial expressions.',
        vbridger: 'Uses webcam tracking for head position and VBridger VMC packets for facial expressions. Set VBridger output to VMC at 127.0.0.1:39539, then start Sakura tracking.'
    };
    const updateFaceSource = (activate = false) => {
        // Broadcast's virtual webcam cannot replace a paired phone camera.
        // Native AR SDK consumes the phone JPEG feed without changing its source.
        const phoneCamera = camera.value === 'sakura-mobile' || avatarTracking.remoteActive;
        let source = faceTrackingSource.value;
        if (phoneCamera && ['nvidia_broadcast','nvidia_expressionapp'].includes(source)) {
            source = 'nvidia_ar';
            faceTrackingSource.value = source;
            companionFaceTrackingSource.value = source;
        }
        localStorage.setItem('sakura_face_tracking_source', source);
        const rtxSelected = source === 'nvidia_ar';
        nvidiaRtxToggle.setAttribute('aria-pressed', String(rtxSelected));
        nvidiaRtxToggle.textContent = rtxSelected ? 'Disable Sakura native RTX tracker' : 'Enable Sakura native RTX tracker';
        const expressionAppToggle=document.getElementById('settings-expressionapp-toggle');
        const expressionAppSelected=source==='nvidia_expressionapp';
        expressionAppToggle.setAttribute('aria-pressed',String(expressionAppSelected));
        expressionAppToggle.textContent=expressionAppSelected?'Disable 2 GB NVIDIA tracker':'Enable 2 GB NVIDIA tracker';
        faceTrackingHelp.textContent = faceSourceHelp[source];
        avatarTracking.setFaceSource(source);
        if (activate && phoneCamera && avatarTracking.remoteActive && source === 'nvidia_ar') {
            void fetch('/api/tracking/nvidia-ar/start',{method:'POST'}).then(async response=>{
                const data=await response.json();
                if(!response.ok)throw Error(data.error||'NVIDIA tracker could not start');
                cameraStatus.textContent='Sakura Mobile camera retained · native NVIDIA RTX expressions enabled';
            }).catch(error=>{cameraStatus.textContent='Phone tracking remains active · '+error.message;});
        }
        vbridgerStatus.hidden = !['vbridger','nvidia_vts'].includes(source);
        if (source === 'nvidia_broadcast' && activate) {
            if (trackingBackend.value !== 'nvidia_gpu') {
                trackingBackend.value = 'nvidia_gpu';
                localStorage.setItem('sakura_tracking_backend','nvidia_gpu');
                const renderer=graphicsRenderer();
                trackingBackendHelp.textContent=backendHelp.nvidia_gpu+(renderer?` WebGL renderer: ${renderer}.`:' The browser does not expose its GPU renderer; it may use an integrated GPU or software rendering.');
            }
            document.getElementById('tracking-broadcast-camera').click();
            cameraStatus.textContent = 'NVIDIA Broadcast camera selected when available. Sakura will use GPU-accelerated MediaPipe on its enhanced feed the next time tracking starts.';
        } else if (source === 'vbridger' || source === 'nvidia_vts') {
            vbridgerStatus.textContent = source === 'nvidia_vts'
                ? 'Configure VTube Studio with its NVIDIA RTX tracker; set VBridger input to VTube Studio and VMC output to 127.0.0.1:39539, then start Sakura tracking.'
                : 'Start tracking, then configure VBridger VMC output to 127.0.0.1:39539. Camera tracking supplies head pose; VBridger supplies face expression weights.';
        } else if (source === 'nvidia_ar') {
            cameraStatus.textContent = 'Sakura native RTX tracker selected. Start tracking to load NVIDIA AR SDK and begin face-expression inference.';
        } else if (source === 'nvidia_expressionapp') {
            cameraStatus.textContent = 'VTube Studio NVIDIA Broadcast Tracker engine selected. Sakura will launch ExpressionApp directly; VTube Studio does not need to run.';
        }
        if (avatarTracking.enabled) {
            cameraStatus.textContent = ['webcam','vbridger','nvidia_vts','nvidia_ar','nvidia_expressionapp'].includes(source)
                ? (source === 'nvidia_vts'
                    ? 'RTX input selected · waiting for VTube Studio → VBridger VMC data on 127.0.0.1:39539.'
                    : source === 'nvidia_expressionapp'
                        ? '2 GB NVIDIA ExpressionApp selected · waiting for tracker output on localhost.'
                    : source === 'nvidia_ar'
                        ? 'Starting Sakura’s native NVIDIA AR SDK tracker on the selected camera feed…'
                    : source === 'vbridger'
                        ? 'VBridger input selected · waiting for VMC data on 127.0.0.1:39539.'
                        : 'RTX input disabled · webcam face tracking is active.')
                : 'Face tracking source saved. Stop and restart tracking to apply the camera/backend change.';
        }
    };
    faceTrackingSource.addEventListener('change', () => {
        companionFaceTrackingSource.value = faceTrackingSource.value;
        updateFaceSource(true);
    });
    companionFaceTrackingSource.addEventListener('change', () => {
        faceTrackingSource.value = companionFaceTrackingSource.value;
        faceTrackingSource.dispatchEvent(new Event('change'));
    });
    nvidiaRtxToggle.addEventListener('click', () => {
        const enable = faceTrackingSource.value !== 'nvidia_ar';
        faceTrackingSource.value = enable ? 'nvidia_ar' : 'webcam';
        faceTrackingSource.dispatchEvent(new Event('change'));
        if (enable && !avatarTracking.enabled) {
            cameraStatus.textContent = 'Starting Sakura’s native RTX face tracking…';
            const companionCameraToggle = document.getElementById('companion-camera-enabled');
            const companionCameraMode = document.getElementById('companion-camera-mode');
            if (!trackingOnly && !vtuberEnabled) {
                companionCameraMode.value = 'tracking';
                companionCameraToggle.checked = true;
                companionCameraToggle.dispatchEvent(new Event('change'));
            } else start.click();
        } else if (!enable) {
            cameraStatus.textContent = avatarTracking.enabled
                ? 'RTX expression input disabled · Sakura is using webcam face tracking.'
                : 'RTX expression input disabled. Start tracking when ready.';
        }
    });
    document.getElementById('settings-expressionapp-toggle').addEventListener('click',()=>{
        const enable=faceTrackingSource.value!=='nvidia_expressionapp';
        faceTrackingSource.value=enable?'nvidia_expressionapp':'webcam';
        faceTrackingSource.dispatchEvent(new Event('change'));
        if(enable&&!avatarTracking.enabled){
            cameraStatus.textContent='Starting the NVIDIA ExpressionApp tracker…';
            const companionCameraToggle=document.getElementById('companion-camera-enabled');
            const companionCameraMode=document.getElementById('companion-camera-mode');
            if(!trackingOnly&&!vtuberEnabled){companionCameraMode.value='tracking';companionCameraToggle.checked=true;companionCameraToggle.dispatchEvent(new Event('change'));}
            else start.click();
        }
    });
    updateFaceSource();
    const sdkFolder=document.getElementById('nvidia-sdk-folder'),sdkStatus=document.getElementById('nvidia-sdk-status');
    sdkFolder.value=currentSettings.nvidia_ar_sdk_folder||'';
    fetch('/api/tracking/nvidia-sdk',{cache:'no-store'}).then(async response=>{
        const data=await response.json();if(!response.ok)throw Error(data.error||'SDK check failed');
        if(data.folder)sdkFolder.value=data.folder;
        const missing=Object.entries(data.features||{}).filter(([,present])=>!present).map(([name])=>name);
        sdkStatus.textContent=(data.installed?'SDK Core detected. ':'')+data.message+(data.installed&&missing.length?' Missing feature packages: '+missing.join(', ')+'.':'');
    }).catch(error=>{sdkStatus.textContent=error.message;});

    const sdkDownload=document.getElementById('nvidia-sdk-download'),sdkImport=document.getElementById('nvidia-sdk-import'),sdkArchive=document.getElementById('nvidia-sdk-archive');
    const sdkNgcKey=document.getElementById('nvidia-sdk-ngc-key'),sdkInstallFeatures=document.getElementById('nvidia-sdk-install-features');
    sdkDownload.onclick=async()=>{
        sdkDownload.disabled=true;
        try{
            const response=await fetch('/api/tracking/nvidia-sdk/download',{method:'POST'});const data=await response.json();
            if(!response.ok)throw Error(data.error||'Could not open download.');
            sdkStatus.textContent=data.ok?data.message:'Your browser did not open. Use the NVIDIA feature downloads link below, select SDK Core and the Windows x64 version.';
        }catch(error){sdkStatus.textContent=error.message;}
        finally{sdkDownload.disabled=false;}
    };
    sdkImport.onclick=()=>sdkArchive.click();
    sdkArchive.onchange=async()=>{
        const file=sdkArchive.files?.[0];if(!file)return;
        sdkImport.disabled=true;sdkDownload.disabled=true;sdkStatus.textContent='Importing SDK files… Please wait. No NVIDIA programs will be executed.';
        try{
            const body=new FormData();body.append('file',file);
            const response=await fetch('/api/tracking/nvidia-sdk/import',{method:'POST',body});const data=await response.json();
            if(!response.ok)throw Error(data.error||'SDK import failed.');
            sdkFolder.value=data.folder;currentSettings.nvidia_ar_sdk_folder=data.folder;
            const missing=Object.entries(data.features||{}).filter(([,installed])=>!installed).map(([name])=>name);
            sdkStatus.textContent=`SDK files imported. ${missing.length?'Missing feature packages: '+missing.join(', ')+'. ':''}${data.message}`;
        }catch(error){sdkStatus.textContent=error.message;}
        finally{sdkImport.disabled=false;sdkDownload.disabled=false;sdkArchive.value='';}
    };
    let sdkFeaturePoll=null;
    sdkInstallFeatures.onclick=async()=>{
        const apiKey=sdkNgcKey.value.trim();
        if(!apiKey){sdkStatus.textContent='Paste your NVIDIA NGC API key first. Sakura will use it for this install only.';sdkNgcKey.focus();return;}
        sdkInstallFeatures.disabled=true;sdkStatus.textContent='Starting NVIDIA’s face-tracking feature installer…';
        try{
            const response=await fetch('/api/tracking/nvidia-sdk/install-features',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({api_key:apiKey,folder:sdkFolder.value.trim()})});
            const data=await response.json();if(!response.ok)throw Error(data.error||'Could not start NVIDIA feature installation.');
            sdkNgcKey.value='';
            sdkStatus.textContent='NVIDIA feature installation started. Keep Sakura open while NVIDIA downloads the GPU-matched packages.';
            if(sdkFeaturePoll)clearInterval(sdkFeaturePoll);
            sdkFeaturePoll=setInterval(async()=>{
                try{
                    const statusResponse=await fetch('/api/tracking/nvidia-sdk/install-features',{cache:'no-store'}),status=await statusResponse.json();
                    const tail=(status.output||[]).slice(-3).join(' · ');
                    if(status.running){sdkStatus.textContent='Installing NVIDIA features… '+tail;return;}
                    clearInterval(sdkFeaturePoll);sdkFeaturePoll=null;sdkInstallFeatures.disabled=false;
                    const check=await fetch('/api/tracking/nvidia-sdk',{cache:'no-store'}),sdk=await check.json();
                    sdkStatus.textContent=status.returncode===0&&sdk.tracking_ready
                        ?'NVIDIA native face tracker is installed and ready. Select “NVIDIA AR SDK” as the tracking source.'
                        :(status.message||sdk.message)+(tail?' · '+tail:'');
                }catch(error){sdkStatus.textContent='Could not read NVIDIA installer status: '+error.message;}
            },1800);
        }catch(error){sdkNgcKey.value='';sdkInstallFeatures.disabled=false;sdkStatus.textContent=error.message;}
    };
    document.getElementById('nvidia-sdk-browse').onclick=async()=>{const path=await window.pywebview?.api.choose_nvidia_sdk_folder();if(path)sdkFolder.value=path;};
    document.getElementById('nvidia-sdk-check').onclick=async()=>{
        try{
            const saved=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({nvidia_ar_sdk_folder:sdkFolder.value.trim()})});if(!saved.ok)throw Error('Could not save SDK folder.');
            const response=await fetch('/api/tracking/nvidia-sdk');const data=await response.json();if(!response.ok)throw Error(data.error||'SDK check failed');sdkStatus.textContent=data.message;
        }catch(error){sdkStatus.textContent=error.message;}
    };
    const expressionFolder=document.getElementById('nvidia-expressionapp-folder');
    const expressionCamera=document.getElementById('nvidia-expressionapp-camera');
    const expressionStatus=document.getElementById('nvidia-expressionapp-status');
    const expressionDownload=document.getElementById('nvidia-expressionapp-download');
    expressionFolder.value=currentSettings.nvidia_expressionapp_folder||'';
    expressionCamera.value=currentSettings.nvidia_expressionapp_camera??0;
    document.getElementById('nvidia-expressionapp-browse').onclick=async()=>{
        const path=await window.pywebview?.api.choose_nvidia_expressionapp_folder();
        if(path)expressionFolder.value=path;
    };
    document.getElementById('nvidia-expressionapp-save').onclick=async()=>{
        try{
            const response=await fetch('/api/tracking/nvidia-expressionapp/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({folder:expressionFolder.value.trim(),camera:Number(expressionCamera.value)||0})});
            const data=await response.json();if(!response.ok)throw Error(data.error||'Could not save tracker location.');
            expressionFolder.value=data.folder;expressionCamera.value=data.camera;
            expressionStatus.textContent=data.folder?'Tracker folder is valid. Choose “Enable 2 GB NVIDIA tracker” to launch it.':'No tracker folder selected.';
        }catch(error){expressionStatus.textContent=error.message;}
    };
    let expressionInstallPoll=null;
    expressionDownload.onclick=async()=>{
        expressionDownload.disabled=true;
        try{
            const response=await fetch('/api/tracking/nvidia-expressionapp/install',{method:'POST'});
            const data=await response.json();if(!response.ok)throw Error(data.error||'Could not open the Steam installer.');
            expressionStatus.textContent=data.message;
            if(data.installed){expressionFolder.value=data.folder;return;}
            if(expressionInstallPoll)clearInterval(expressionInstallPoll);
            let checks=0;
            expressionInstallPoll=setInterval(async()=>{
                checks++;
                try{
                    const check=await fetch('/api/tracking/nvidia-expressionapp',{cache:'no-store'});
                    const status=await check.json();
                    if(status.folder){
                        clearInterval(expressionInstallPoll);expressionInstallPoll=null;
                        expressionFolder.value=status.folder;expressionCamera.value=status.camera??0;
                        expressionStatus.textContent='Tracker download detected and ready. Select “Enable 2 GB NVIDIA tracker” when you want to start camera tracking.';
                        await fetch('/api/tracking/nvidia-expressionapp/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({folder:status.folder,camera:Number(expressionCamera.value)||0})});
                    }else if(checks>=180){clearInterval(expressionInstallPoll);expressionInstallPoll=null;}
                }catch(_){if(checks>=180){clearInterval(expressionInstallPoll);expressionInstallPoll=null;}}
            },5000);
        }catch(error){expressionStatus.textContent=error.message;}
        finally{expressionDownload.disabled=false;}
    };
    fetch('/api/tracking/nvidia-expressionapp',{cache:'no-store'}).then(r=>r.json()).then(data=>{
        if(data.folder&&!expressionFolder.value)expressionFolder.value=data.folder;
        if(data.error)expressionStatus.textContent=data.error;
        else if(data.connected)expressionStatus.textContent=`ExpressionApp connected · ${data.fps} FPS.`;
        else if(data.folder)expressionStatus.textContent='Steam tracker DLC detected. Choose “Enable 2 GB NVIDIA tracker” to start it; Sakura will use its camera index below.';
    }).catch(error=>{expressionStatus.textContent=error.message;});
    settingsCamera.addEventListener('change', () => {
        camera.value = settingsCamera.value;
        camera.dispatchEvent(new Event('change'));
        cameraStatus.textContent = 'Camera selected. Press Start tracking to use it.';
        if (avatarTracking.enabled) cameraStatus.textContent = 'Camera saved. Stop and restart face tracking to use it.';
    });
    document.getElementById('settings-start-tracking').addEventListener('click', () => start.click());
    document.getElementById('settings-stop-tracking').addEventListener('click', () => { stop.click(); cameraStatus.textContent = status.textContent; });
    document.getElementById('settings-calibrate-tracking').addEventListener('click', () => { document.getElementById('tracking-calibrate').click(); cameraStatus.textContent = status.textContent; });
    const setUI = enabled => {
        trackingOnly = enabled;
        if(!enabled)window.dispatchEvent(new Event('sakura-vtuber-mode-off'));
        updateAppBrand(enabled);
        if(enabled)companionCamera.stop();
        if(enabled)viewer?.setCompanionTracking(false);
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
        const agent=document.getElementById('agent-mode-toggle');
        if(agent){agent.hidden=enabled||window.SAKURA_EDITION==='vtuber';agent.style.display=agent.hidden?'none':'';}
        document.getElementById('chat-reader-mode-btn').hidden = !enabled;
        document.getElementById('vtuber-start-btn').disabled = enabled;
    };
    window.addEventListener('sakura-phone-camera-frame',event=>companionCamera.remoteFrame(event.detail?.image));
    window.addEventListener('sakura-phone-companion-tracking',event=>{
        if(event.detail?.enabled){
        camera.value=settingsCamera.value='sakura-mobile';
        localStorage.setItem('sakura_tracking_camera','sakura-mobile');
            companionCamera.stop();
            avatarTracking.stop();
            viewer.setCompanionTracking(true);
            viewer.setVtuberTrackingMode(true);
            viewer.setUserTracking(true);
            document.getElementById('companion-camera-status').textContent='Phone face tracking on · measurements stay on the phone · Companion AI remains available';
        }else{
            viewer.setUserTracking(false);
            viewer.setVtuberTrackingMode(false);
            viewer.setCompanionTracking(false);
            document.getElementById('companion-camera-status').textContent='Phone face tracking off';
        }
    });
    window.addEventListener('sakura-phone-camera',async event=>{
        if(event.detail?.type==='camera-stop'){if(companionCamera.remote)companionCamera.stop();return;}
        if(window.SAKURA_EDITION==='vtuber')return;
        try{
            avatarTracking.stop();viewer.setUserTracking(false);
            if(trackingOnly){
                const response=await fetch('/api/tracking/mode',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:false})});
                if(!response.ok)throw Error('Restore Companion mode on the PC before sharing the phone camera.');
                viewer.setVtuberTrackingMode(false);setUI(false);
            }
            if(vtuberEnabled)throw Error('Stop AI VTuber before enabling personal camera viewing.');
            companionCamera.startRemote();
            document.getElementById('companion-camera-status').textContent='Phone camera on · object viewing only · face tracking off';
            await startDesktopListening();
        }catch(error){status.textContent=error.message;}
    });
    window.addEventListener('sakura-phone-tracking',async()=>{
        camera.value=settingsCamera.value='sakura-mobile';
        localStorage.setItem('sakura_tracking_camera','sakura-mobile');
        companionCamera.stop();
        setUI(true);continuousMic.stop();lipSync.stop();
        vtuberEnabled=false;++vtuberGeneration;vtuberQueue=[];reactionsEnabled=false;
        if(screenShare.enabled)screenShare.stop();
        try{
            const response=await fetch('/api/tracking/mode',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:true})});
            if(!response.ok)throw new Error('PC could not enter tracking mode.');
            status.textContent='Tracking from paired Android camera';
        }catch(error){status.textContent=error.message;}
    });
    mode.addEventListener('click', async () => {
        modal.classList.remove('hidden');
        if(!trackingOnly&&!switching){
            switching=true;mode.disabled=true;
            resumeMic=continuousMic.enabled;
            ++chatReplyGeneration;replyController?.abort();continuousMic.stop();lipSync?.stop();
            vtuberEnabled=false;++vtuberGeneration;vtuberQueue=[];reactionsEnabled=false;autoGameEnabled=false;
            gameActive=false;gameReady=false;
            document.getElementById('auto-game-btn').textContent='🎮 Auto game off';document.getElementById('auto-game-btn').setAttribute('aria-pressed','false');
            screenReactBtn.textContent='💬 Reactions off';screenReactBtn.setAttribute('aria-pressed','false');
            companionCamera.stop();if(screenShare.enabled)screenShare.stop();
            try{
                await stopReader();await stopVtuberVoiceChanger();
                const response=await fetch('/api/tracking/mode',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:true})});
                const data=await response.json();if(response.ok||data.tracking_only===true){setUI(true);viewer.setVtuberTrackingMode(true);}
                if(!response.ok)throw Error(data.error||'Could not switch to VTuber mode.');
                status.textContent='VTuber mode · choose camera tracking, Chat Reader or voice changer';
            }catch(error){status.textContent=error.message;}
            finally{switching=false;mode.disabled=false;}
        }
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
    handsToggle.addEventListener('click', e => {
        const enabled = e.currentTarget.getAttribute('aria-pressed') !== 'true';
        e.currentTarget.setAttribute('aria-pressed', String(enabled));
        e.currentTarget.classList.toggle('active', enabled);
        e.currentTarget.textContent = `Hand tracking: ${enabled ? 'On' : 'Off'}`;
        avatarTracking.setHandTracking(enabled);
        try { localStorage.setItem('sakura_hand_tracking_enabled', String(enabled)); } catch (_) {}
        if (avatarTracking.enabled) status.textContent = enabled
            ? 'Hand tracking on · arms and fingers follow your hands'
            : 'Hand tracking off · face, head, lean and up/down remain active';
    });
    document.getElementById('tracking-calibrate').addEventListener('click',()=> {
        if(camera.value==='sakura-mobile'){void fetch('/api/mobile/tracking-control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'calibrate'})});viewer.calibrateUserTracking();return;}
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
            avatarTracking.setFaceSource(faceTrackingSource.value);
            if(camera.value==='sakura-mobile'){avatarTracking.stop();
                if(['nvidia_ar','nvidia_expressionapp','nvidia_broadcast'].includes(avatarTracking.faceSource)){
                    const init=await fetch('/api/tracking/nvidia-ar/start',{method:'POST'}),info=await init.json();
                    if(!init.ok)throw Error(info.error||'Native NVIDIA tracker could not initialize for phone frames');
                    avatarTracking.faceSource='nvidia_ar';faceTrackingSource.value=companionFaceTrackingSource.value='nvidia_ar';localStorage.setItem('sakura_face_tracking_source','nvidia_ar');
                }
                const r=await fetch('/api/mobile/tracking-control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'start'})});const d=await r.json();if(!r.ok)throw Error(d.error);window.dispatchEvent(new CustomEvent('sakura-phone-tracking-requested',{detail:{enabled:true}}));status.textContent='Tracking requested · keep paired Sakura Mobile open';}else await avatarTracking.start(camera.value, trackingBackend.value);
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
        window.dispatchEvent(new CustomEvent('sakura-phone-tracking-requested',{detail:{enabled:false}}));
        if(camera.value==='sakura-mobile')void fetch('/api/mobile/tracking-control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'stop'})});
        status.textContent='Tracking off · AI remains paused';
    });
    document.getElementById('tracking-restore-ai').addEventListener('click',async()=> {
        if(switching) return;
        switching=true; start.disabled=true; stop.disabled=true;
        try {
            await stopVtuberVoiceChanger();avatarTracking.stop();await stopReader();
            status.textContent='Restoring assistant mode…';
            const response=await fetch('/api/tracking/mode',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:false})});
            const data=await response.json();
            if(!response.ok) throw new Error(data.error || 'Could not restore AI.');
            viewer.setVtuberTrackingMode(false);
            setUI(false); status.textContent='Tracking off · assistant restored';
            if(resumeMic && document.body.classList.contains('desktop-companion')) await startDesktopListening(true);
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
                document.getElementById('tracking-restore-ai').hidden = window.SAKURA_EDITION==='vtuber';
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




window.addEventListener('sakura-tracking-error',event=>{const el=document.getElementById('tracking-status');if(el)el.textContent='Tracking paused: '+event.detail+'. Stop and restart tracking to retry.';});
