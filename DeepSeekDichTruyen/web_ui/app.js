/* ==========================================================================
   DEEPSEEK DỊCH TRUYỆN 3D STUDIO - FRONTEND JS ENGINE
   ========================================================================== */

// Global State
let appState = {
  settings: {},
  history: [],
  logs: [],
  isTranslating: false,
  isPaused: false,
  soundEnabled: true,
  mode3D: 'hero', // 'hero', 'bg', 'off'
  mouse: { x: 0, y: 0, targetX: 0, targetY: 0 },
};

// ==========================================================================
// 1. THREE.JS 3D SCENE VISUALIZER
// ==========================================================================
let scene, camera, renderer;
let bookGroup, bookCoverLeft, bookCoverRight, bookPages, magicRing, particleSystem;
let isAnimatingTranslation = false;

function init3DScene() {
  const container = document.getElementById('canvas-container');
  const canvas = document.getElementById('three-canvas');
  if (!container || !canvas || typeof THREE === 'undefined') return;

  const width = container.clientWidth;
  const height = container.clientHeight;

  scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x070a12, 0.0015);

  camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
  camera.position.set(0, 0, 25);

  renderer = new THREE.WebGLRenderer({ canvas: canvas, alpha: true, antialias: true });
  renderer.setSize(width, height);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  // Lighting
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
  scene.add(ambientLight);

  const dirLight = new THREE.DirectionalLight(0x00f2fe, 1.5);
  dirLight.position.set(10, 20, 15);
  scene.add(dirLight);

  const pointLight = new THREE.PointLight(0xa855f7, 2, 50);
  pointLight.position.set(-10, -10, 10);
  scene.add(pointLight);

  // Build 3D Book Group
  bookGroup = new THREE.Group();

  // Book Cover Left
  const coverMat = new THREE.MeshStandardMaterial({
    color: 0x0f172a,
    roughness: 0.3,
    metalness: 0.8,
  });

  const coverGeo = new THREE.BoxGeometry(6, 8.5, 0.4);
  bookCoverLeft = new THREE.Mesh(coverGeo, coverMat);
  bookCoverLeft.position.set(-3, 0, 0);

  // Book Cover Right
  bookCoverRight = new THREE.Mesh(coverGeo, coverMat);
  bookCoverRight.position.set(3, 0, 0);

  // Book Pages
  const pageMat = new THREE.MeshStandardMaterial({
    color: 0xf8fafc,
    roughness: 0.9,
  });
  const pageGeo = new THREE.BoxGeometry(5.8, 8.2, 0.8);
  bookPages = new THREE.Mesh(pageGeo, pageMat);
  bookPages.position.set(0, 0, 0.1);

  // Gold Spine Trim
  const spineMat = new THREE.MeshStandardMaterial({ color: 0xfbbf24, metalness: 0.9, roughness: 0.2 });
  const spineGeo = new THREE.CylinderGeometry(0.3, 0.3, 8.5, 16);
  const spine = new THREE.Mesh(spineGeo, spineMat);
  spine.position.set(0, 0, -0.1);

  bookGroup.add(bookCoverLeft);
  bookGroup.add(bookCoverRight);
  bookGroup.add(bookPages);
  bookGroup.add(spine);

  // Magical Orbiting Ring
  const ringGeo = new THREE.TorusGeometry(8, 0.08, 16, 100);
  const ringMat = new THREE.MeshBasicMaterial({ color: 0x00f2fe, wireframe: true });
  magicRing = new THREE.Mesh(ringGeo, ringMat);
  magicRing.rotation.x = Math.PI / 3;
  bookGroup.add(magicRing);

  // Particle Starfield Engine
  const particleCount = 250;
  const particleGeo = new THREE.BufferGeometry();
  const positions = new Float32Array(particleCount * 3);
  const colors = new Float32Array(particleCount * 3);

  for (let i = 0; i < particleCount * 3; i += 3) {
    positions[i] = (Math.random() - 0.5) * 60;
    positions[i + 1] = (Math.random() - 0.5) * 60;
    positions[i + 2] = (Math.random() - 0.5) * 60;

    colors[i] = 0;
    colors[i + 1] = 0.95;
    colors[i + 2] = 1;
  }

  particleGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  particleGeo.setAttribute('color', new THREE.BufferAttribute(colors, 3));

  const particleMat = new THREE.PointsMaterial({
    size: 0.35,
    vertexColors: true,
    transparent: true,
    opacity: 0.7,
  });

  particleSystem = new THREE.Points(particleGeo, particleMat);
  scene.add(particleSystem);

  scene.add(bookGroup);
  bookGroup.position.set(0, 2, 0);

  // Mouse tilt tracking
  window.addEventListener('mousemove', (e) => {
    appState.mouse.targetX = (e.clientX / window.innerWidth - 0.5) * 0.8;
    appState.mouse.targetY = (e.clientY / window.innerHeight - 0.5) * 0.8;
  });

  window.addEventListener('resize', onWindowResize);

  animate3D();
}

function animate3D() {
  requestAnimationFrame(animate3D);

  if (!bookGroup) return;

  // Lerp mouse interaction
  appState.mouse.x += (appState.mouse.targetX - appState.mouse.x) * 0.05;
  appState.mouse.y += (appState.mouse.targetY - appState.mouse.y) * 0.05;

  bookGroup.rotation.y = appState.mouse.x + Math.sin(Date.now() * 0.001) * 0.15;
  bookGroup.rotation.x = appState.mouse.y + Math.cos(Date.now() * 0.0012) * 0.1;

  // Floating Y oscillation
  bookGroup.position.y = 2 + Math.sin(Date.now() * 0.002) * 0.5;

  // Magic Ring rotation
  if (magicRing) {
    magicRing.rotation.z += 0.01;
    magicRing.rotation.y += 0.005;
  }

  // Particle system drift
  if (particleSystem) {
    particleSystem.rotation.y += 0.0008;
  }

  // Translation active pulse
  if (isAnimatingTranslation) {
    if (magicRing) magicRing.rotation.z += 0.03;
    bookGroup.scale.set(1.1, 1.1, 1.1);
  } else {
    bookGroup.scale.set(1, 1, 1);
  }

  renderer.render(scene, camera);
}

function onWindowResize() {
  const container = document.getElementById('canvas-container');
  if (!container || !renderer || !camera) return;
  const width = container.clientWidth;
  const height = container.clientHeight;
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  renderer.setSize(width, height);
}

// Sound Synthesizer Notifications
function playCompletionSound() {
  if (!appState.soundEnabled) return;
  try {
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(523.25, audioCtx.currentTime); // C5
    osc.frequency.exponentialRampToValueAtTime(659.25, audioCtx.currentTime + 0.15); // E5
    osc.frequency.exponentialRampToValueAtTime(783.99, audioCtx.currentTime + 0.3); // G5
    osc.frequency.exponentialRampToValueAtTime(1046.50, audioCtx.currentTime + 0.45); // C6

    gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.8);

    osc.connect(gain);
    gain.connect(audioCtx.destination);

    osc.start();
    osc.stop(audioCtx.currentTime + 0.8);
  } catch (e) {
    console.log('Audio notification fallback:', e);
  }
}

// ==========================================================================
// 2. UI INITIALIZATION & EVENT LISTENERS
// ==========================================================================
document.addEventListener('DOMContentLoaded', () => {
  init3DScene();
  setupTabNavigation();
  setupControls();
  setupDropzone();
  initPyWebviewBridge();
});

// Tab Navigation
function setupTabNavigation() {
  const tabs = document.querySelectorAll('.nav-tab');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const target = tab.getAttribute('data-tab');
      switchTab(target);
    });
  });
}

function switchTab(tabId) {
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

  const activeBtn = document.querySelector(`.nav-tab[data-tab="${tabId}"]`);
  const activeContent = document.getElementById(tabId);

  if (activeBtn) activeBtn.classList.add('active');
  if (activeContent) activeContent.classList.add('active');
}

// Form Controls & Sliders
function setupControls() {
  // Sliders
  const tempSlider = document.getElementById('slider-temp');
  const tempVal = document.getElementById('val-temp');
  tempSlider.addEventListener('input', () => {
    tempVal.textContent = tempSlider.value;
  });

  const threadsSlider = document.getElementById('slider-threads');
  const threadsVal = document.getElementById('val-threads');
  threadsSlider.addEventListener('input', () => {
    threadsVal.textContent = threadsSlider.value;
  });

  // Accordion
  const accHeader = document.getElementById('acc-header-tuning');
  const accContent = document.getElementById('acc-body-tuning');
  if (accHeader && accContent) {
    accHeader.addEventListener('click', () => {
      const isHidden = accContent.style.display === 'none';
      accContent.style.display = isHidden ? 'flex' : 'none';
    });
    accContent.style.display = 'none'; // default closed
  }

  // 3D Mode Toggle
  const btn3DToggle = document.getElementById('btn-3d-toggle');
  const val3DMode = document.getElementById('val-3d-mode');
  btn3DToggle.addEventListener('click', () => {
    if (appState.mode3D === 'hero') {
      appState.mode3D = 'bg';
      val3DMode.textContent = 'Background';
      document.getElementById('canvas-container').style.opacity = '0.35';
    } else if (appState.mode3D === 'bg') {
      appState.mode3D = 'off';
      val3DMode.textContent = 'Tắt';
      document.getElementById('canvas-container').style.display = 'none';
    } else {
      appState.mode3D = 'hero';
      val3DMode.textContent = 'Hero 3D';
      document.getElementById('canvas-container').style.display = 'block';
      document.getElementById('canvas-container').style.opacity = '1';
    }
  });

  // Sound Toggle
  const btnSound = document.getElementById('btn-sound-toggle');
  const iconSound = document.getElementById('icon-sound');
  const valSound = document.getElementById('val-sound');
  btnSound.addEventListener('click', () => {
    appState.soundEnabled = !appState.soundEnabled;
    valSound.textContent = appState.soundEnabled ? 'Bật' : 'Tắt';
    iconSound.textContent = appState.soundEnabled ? '🔊' : '🔇';
  });

  // Theme Toggle
  const btnTheme = document.getElementById('btn-theme-toggle');
  btnTheme.addEventListener('click', () => {
    document.body.classList.toggle('light-theme');
    const isLight = document.body.classList.contains('light-theme');
    btnTheme.textContent = isLight ? '☀️' : '🌙';

    if (scene && scene.fog) {
      scene.fog.color.setHex(isLight ? 0xf1f5f9 : 0x070a12);
    }
  });


  // API Key Visibility Toggle
  const btnToggleKey = document.getElementById('btn-toggle-key-visibility');
  const inputKeyVal = document.getElementById('input-api-key-value');
  btnToggleKey.addEventListener('click', () => {
    const isPass = inputKeyVal.type === 'password';
    inputKeyVal.type = isPass ? 'text' : 'password';
    btnToggleKey.textContent = isPass ? '🙈' : '👁️';
  });

  // Terminal Clear & Auto Scroll
  document.getElementById('btn-clear-logs').addEventListener('click', () => {
    document.getElementById('full-log-terminal').innerHTML = '';
    document.getElementById('log-count-badge').textContent = '0';
    appState.logs = [];
  });
}

// File Dropzone Event Listeners
function setupDropzone() {
  const dropzone = document.getElementById('dropzone');
  const btnBrowseInput = document.getElementById('btn-browse-input');
  const btnBrowseOutput = document.getElementById('btn-browse-output');

  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, preventDefaults, false);
  });

  function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
  }

  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, () => dropzone.classList.add('dragover'), false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, () => dropzone.classList.remove('dragover'), false);
  });

  dropzone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files.length > 0) {
      handleFileSelected(files[0].path || files[0].name);
    }
  });

  dropzone.addEventListener('click', () => {
    callPythonApi('select_file', 'input');
  });

  btnBrowseInput.addEventListener('click', (e) => {
    e.stopPropagation();
    callPythonApi('select_file', 'input');
  });

  btnBrowseOutput.addEventListener('click', () => {
    callPythonApi('select_file', 'output');
  });
}

function handleFileSelected(filePath) {
  if (!filePath) return;
  document.getElementById('dz-filename').textContent = filePath.split('\\').pop().split('/').pop();
  document.getElementById('dz-filesize').textContent = filePath;
  
  // Call backend to build default output path
  callPythonApi('build_output_path', filePath);
}

// ==========================================================================
// 3. PYWEBVIEW API BRIDGE INTEGRATION
// ==========================================================================
function initPyWebviewBridge() {
  window.addEventListener('pywebviewready', () => {
    console.log('PyWebview Bridge Ready!');
    fetchInitialData();
    setupActionButtons();
  });
}

function callPythonApi(funcName, ...args) {
  if (window.pywebview && window.pywebview.api && window.pywebview.api[funcName]) {
    return window.pywebview.api[funcName](...args).catch(err => {
      console.error(`Error in API call [${funcName}]:`, err);
    });
  } else {
    console.warn(`PyWebview API [${funcName}] not available yet.`);
    return Promise.reject('Bridge not ready');
  }
}

function fetchInitialData() {
  callPythonApi('get_initial_data').then(data => {
    if (!data) return;
    appState.settings = data.settings || {};
    appState.history = data.history || [];

    populateUIFromData(data);
  });
}

function populateUIFromData(data) {
  const s = data.settings || {};

  // API Keys Dropdown & Current
  const apiKeyProfiles = data.api_key_profiles || [];
  const selApiKey = document.getElementById('select-apikey-profile');
  selApiKey.innerHTML = '';
  apiKeyProfiles.forEach(p => {
    const opt = document.createElement('option');
    opt.value = p;
    opt.textContent = p;
    if (p === s.active_api_key_name) opt.selected = true;
    selApiKey.appendChild(opt);
  });

  if (s.active_api_key_value) {
    document.getElementById('input-api-key-value').value = s.active_api_key_value;
    setApiStatus(true, s.active_api_key_name || 'Đã cấu hình Key');
  } else {
    setApiStatus(false, 'Chưa nhập API Key');
  }

  // Model & Fallback
  if (s.model) document.getElementById('select-model').value = s.model;
  if (s.model_fallback_order) document.getElementById('input-fallback-order').value = s.model_fallback_order;
  if (s.thinking_level) document.getElementById('select-thinking').value = s.thinking_level;

  // Tuning Sliders
  if (s.temperature !== undefined) {
    document.getElementById('slider-temp').value = s.temperature;
    document.getElementById('val-temp').textContent = s.temperature;
  }
  if (s.thread_count) {
    document.getElementById('slider-threads').value = s.thread_count;
    document.getElementById('val-threads').textContent = s.thread_count;
  }
  if (s.chunk_size) document.getElementById('input-chunk-size').value = s.chunk_size;
  if (s.max_output_tokens) document.getElementById('input-max-tokens').value = s.max_output_tokens;
  if (s.split_mode) document.getElementById('select-split-mode').value = s.split_mode;

  // Prompts Dropdown
  const promptProfiles = data.prompt_profiles || [];
  const selPrompt = document.getElementById('select-prompt-profile');
  selPrompt.innerHTML = '';
  promptProfiles.forEach(p => {
    const opt = document.createElement('option');
    opt.value = p;
    opt.textContent = p;
    if (p === s.active_prompt_name) opt.selected = true;
    selPrompt.appendChild(opt);
  });
  if (data.active_prompt_text) {
    document.getElementById('prompt-editor-text').value = data.active_prompt_text;
  }

  // Glossary Text
  if (s.glossary !== undefined) {
    document.getElementById('glossary-editor-text').value = s.glossary;
  }

  // Google Drive Config
  if (s.drive_upload_enabled !== undefined) {
    document.getElementById('chk-drive-upload').checked = s.drive_upload_enabled;
  }
  if (s.drive_credentials_path) {
    document.getElementById('input-drive-credentials').value = s.drive_credentials_path;
  }
  if (s.drive_folder_id) {
    document.getElementById('input-drive-folder-id').value = s.drive_folder_id;
  }

  // Render History
  renderHistoryTable(appState.history);
}

function setApiStatus(isOk, text) {
  const chip = document.getElementById('api-status-chip');
  const label = document.getElementById('api-status-text');
  if (isOk) {
    chip.className = 'status-chip chip-success';
    label.textContent = `API Key: ${text}`;
  } else {
    chip.className = 'status-chip chip-warning';
    label.textContent = text;
  }
}

// Action Button Handlers
function setupActionButtons() {
  // Start Translation
  document.getElementById('btn-start-trans').addEventListener('click', () => {
    const params = getFormConfigValues();
    callPythonApi('start_translation', params).then(res => {
      if (res && res.success) {
        setTranslationRunningState(true);
      }
    });
  });

  // Pause / Resume Translation
  document.getElementById('btn-pause-trans').addEventListener('click', () => {
    callPythonApi('toggle_pause').then(paused => {
      appState.isPaused = paused;
      const btn = document.getElementById('btn-pause-trans');
      if (paused) {
        btn.innerHTML = '<span class="btn-icon">▶️</span> TIẾP TỤC';
        btn.className = 'btn btn-success btn-lg';
      } else {
        btn.innerHTML = '<span class="btn-icon">⏸️</span> TẠM DỪNG';
        btn.className = 'btn btn-warning btn-lg';
      }
    });
  });

  // Stop Translation
  document.getElementById('btn-stop-trans').addEventListener('click', () => {
    if (confirm('Bạn có chắc chắn muốn DỪNG dịch? (Tiến trình đã được lưu)')) {
      callPythonApi('stop_translation');
    }
  });

  // Quick Translate Button
  document.getElementById('btn-quick-translate').addEventListener('click', () => {
    const input = document.getElementById('quick-input-text').value.trim();
    const model = document.getElementById('quick-select-model').value;
    if (!input) {
      alert('Vui lòng nhập văn bản cần dịch!');
      return;
    }
    document.getElementById('quick-status-msg').textContent = '⏳ Đang dịch...';
    callPythonApi('translate_quick', input, model).then(res => {
      if (res && res.result) {
        document.getElementById('quick-output-text').value = res.result;
        document.getElementById('quick-status-msg').textContent = `✅ Dịch xong! Input: ${res.input_tokens} | Output: ${res.output_tokens}`;
      } else {
        document.getElementById('quick-status-msg').textContent = `❌ Lỗi: ${res.error || 'Thất bại'}`;
      }
    });
  });

  // Quick Copy
  document.getElementById('btn-quick-copy').addEventListener('click', () => {
    const out = document.getElementById('quick-output-text').value;
    if (!out) return;
    navigator.clipboard.writeText(out).then(() => {
      document.getElementById('quick-status-msg').textContent = '✅ Đã copy vào clipboard!';
    });
  });

  // Quick Paste
  document.getElementById('btn-quick-paste').addEventListener('click', () => {
    navigator.clipboard.readText().then(txt => {
      document.getElementById('quick-input-text').value = txt;
    });
  });

  // Clear Quick Input
  document.getElementById('btn-clear-quick-input').addEventListener('click', () => {
    document.getElementById('quick-input-text').value = '';
    document.getElementById('quick-output-text').value = '';
  });

  // Run Glossary Scan
  document.getElementById('btn-run-scan').addEventListener('click', () => {
    const limit = document.getElementById('input-scan-limit').value;
    const model = document.getElementById('scan-select-model').value;
    callPythonApi('run_glossary_scan', limit, model);
  });

  // Append Scanned Terms to Glossary
  document.getElementById('btn-append-scanned-glossary').addEventListener('click', () => {
    const scanned = document.getElementById('scanned-results-text').value.trim();
    if (!scanned) return;
    const current = document.getElementById('glossary-editor-text').value.trim();
    const updated = current ? current + '\n' + scanned : scanned;
    document.getElementById('glossary-editor-text').value = updated;
    callPythonApi('save_glossary', updated);
    alert('Đã thêm các thuật ngữ mới vào Glossary!');
  });

  // Test API Key
  document.getElementById('btn-test-apikey').addEventListener('click', () => {
    const key = document.getElementById('input-api-key-value').value.trim();
    const base = document.getElementById('input-api-base-url').value.trim();
    const lbl = document.getElementById('apikey-test-result');
    lbl.textContent = '⏳ Đang test...';
    lbl.className = 'test-result-label text-muted';

    callPythonApi('test_api_key', key, base).then(res => {
      if (res && res.success) {
        lbl.textContent = '✅ Kết nối API Key thành công!';
        lbl.className = 'test-result-label text-success';
        setApiStatus(true, 'Key hợp lệ');
      } else {
        lbl.textContent = `❌ Lỗi: ${res.error}`;
        lbl.className = 'test-result-label text-danger';
        setApiStatus(false, 'Lỗi kết nối Key');
      }
    });
  });
}

function getFormConfigValues() {
  return {
    input_path: document.getElementById('dz-filesize').textContent,
    output_path: document.getElementById('input-output-path').value,
    model: document.getElementById('select-model').value,
    thinking_level: document.getElementById('select-thinking').value,
    fallback_order: document.getElementById('input-fallback-order').value,
    temperature: parseFloat(document.getElementById('slider-temp').value),
    threads: parseInt(document.getElementById('slider-threads').value),
    chunk_size: parseInt(document.getElementById('input-chunk-size').value),
    max_tokens: parseInt(document.getElementById('input-max-tokens').value),
    split_mode: document.getElementById('select-split-mode').value,
    api_key: document.getElementById('input-api-key-value').value,
    prompt: document.getElementById('prompt-editor-text').value,
    glossary: document.getElementById('glossary-editor-text').value,
    drive_upload: document.getElementById('chk-drive-upload').checked,
    drive_credentials: document.getElementById('input-drive-credentials').value,
    drive_folder_id: document.getElementById('input-drive-folder-id').value,
  };
}

function setTranslationRunningState(isRunning) {
  appState.isTranslating = isRunning;
  isAnimatingTranslation = isRunning;

  document.getElementById('btn-start-trans').disabled = isRunning;
  document.getElementById('btn-pause-trans').disabled = !isRunning;
  document.getElementById('btn-stop-trans').disabled = !isRunning;

  const statusTag = document.getElementById('batch-status-tag');
  if (isRunning) {
    statusTag.className = 'status-pill pill-running';
    statusTag.textContent = '⚡ Đang dịch...';
  } else {
    statusTag.className = 'status-pill pill-idle';
    statusTag.textContent = 'Sẵn sàng';
  }
}

// ==========================================================================
// 4. EVENT CALLBACKS FROM PYTHON BACKEND
// ==========================================================================
window.onPyEvent = function(eventType, data) {
  console.log('Event from Python:', eventType, data);

  switch (eventType) {
    case 'update_progress':
      updateProgressHUD(data);
      break;

    case 'append_log':
      appendLogLine(data.message, data.level);
      break;

    case 'update_stats':
      updateStatsDisplay(data);
      break;

    case 'file_selected':
      if (data.target === 'input') {
        handleFileSelected(data.path);
      } else if (data.target === 'output') {
        document.getElementById('input-output-path').value = data.path;
      }
      break;

    case 'scan_complete':
      document.getElementById('scanned-results-text').value = data.terms || 'Không tìm thấy thuật ngữ nào.';
      break;

    case 'translation_complete':
      setTranslationRunningState(false);
      playCompletionSound();
      alert(`🎉 Hoàn tất dịch!\n${data.message}`);
      if (data.history) {
        appState.history.unshift(data.history);
        renderHistoryTable(appState.history);
      }
      break;

    case 'translation_stopped':
      setTranslationRunningState(false);
      alert('🛑 Đã dừng dịch truyện.');
      break;

    case 'translation_error':
      setTranslationRunningState(false);
      alert(`❌ Lỗi hệ thống:\n${data.error}`);
      break;
  }
};

function updateProgressHUD(data) {
  const percent = data.percent || 0;
  const done = data.done || 0;
  const total = data.total || 0;

  document.getElementById('hud-percent').textContent = `${percent}%`;
  document.getElementById('hud-chunk-counts').textContent = `${done} / ${total} đoạn`;

  // Ring SVG stroke-dashoffset (total array length = 490)
  const circle = document.getElementById('hud-progress-circle');
  const offset = 490 - (490 * percent) / 100;
  circle.style.strokeDashoffset = offset;
}

function updateStatsDisplay(data) {
  if (data.elapsed) document.getElementById('stat-elapsed-time').textContent = data.elapsed;
  if (data.speed) document.getElementById('stat-speed').textContent = `${data.speed} ký tự/s`;
  if (data.chars) document.getElementById('stat-chars-count').textContent = data.chars;
  if (data.tokens) document.getElementById('stat-tokens-count').textContent = data.tokens;
  if (data.cost_usd) {
    const usd = data.cost_usd.toFixed(4);
    const vnd = Math.round(data.cost_usd * 25400).toLocaleString('vi-VN');
    document.getElementById('stat-cost-display').textContent = `$${usd} (~ ${vnd} ₫)`;
  }
}

function appendLogLine(message, level = 'info') {
  const terminal = document.getElementById('full-log-terminal');
  const miniLog = document.getElementById('mini-log-content');

  miniLog.textContent = message;

  const div = document.createElement('div');
  div.className = `log-line log-${level}`;
  div.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;

  terminal.appendChild(div);

  const countBadge = document.getElementById('log-count-badge');
  countBadge.textContent = parseInt(countBadge.textContent || 0) + 1;

  if (document.getElementById('chk-autoscroll-logs').checked) {
    terminal.scrollTop = terminal.scrollHeight;
  }
}

// History Table Renderer
function renderHistoryTable(historyList) {
  const tbody = document.getElementById('history-tbody');
  tbody.innerHTML = '';

  if (!historyList || historyList.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted">Chưa có lịch sử dịch nào.</td></tr>';
    return;
  }

  let totalJobs = historyList.length;
  let totalInputTok = 0;
  let totalOutputTok = 0;
  let totalCostUSD = 0;

  historyList.forEach((item, index) => {
    totalInputTok += item.total_input_tokens || 0;
    totalOutputTok += item.total_output_tokens || 0;
    totalCostUSD += item.total_cost_usd || 0;

    const tr = document.createElement('tr');
    const statusClass = item.status === 'completed' ? 'pill-completed' : (item.status === 'stopped' ? 'pill-idle' : 'pill-running');

    tr.innerHTML = `
      <td><span class="status-pill ${statusClass}">${item.status || 'Done'}</span></td>
      <td>${item.start_at || '-'}</td>
      <td>${item.duration_seconds ? item.duration_seconds + 's' : '-'}</td>
      <td title="${item.input_file}">${(item.input_file || '').split('\\').pop()}</td>
      <td>${item.model || '-'}</td>
      <td>${item.chunks_done || 0}/${item.total_chunks || 0}</td>
      <td>${((item.total_input_tokens || 0) + (item.total_output_tokens || 0)).toLocaleString()}</td>
      <td class="gold-text">$${(item.total_cost_usd || 0).toFixed(4)}</td>
      <td>
        <button class="btn-icon-sm" onclick="openDiffView(${index})" title="So sánh gốc vs dịch">🔄</button>
        <button class="btn-icon-sm" onclick="openOutputFile('${item.output_file}')" title="Mở File">📂</button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  // Update KPI Bar
  document.getElementById('kpi-total-jobs').textContent = totalJobs;
  document.getElementById('kpi-input-tokens').textContent = totalInputTok.toLocaleString();
  document.getElementById('kpi-output-tokens').textContent = totalOutputTok.toLocaleString();
  document.getElementById('kpi-total-cost-usd').textContent = `$${totalCostUSD.toFixed(4)}`;
  document.getElementById('kpi-total-cost-vnd').textContent = `${Math.round(totalCostUSD * 25400).toLocaleString('vi-VN')} ₫`;
}

// Modal Handlers
function openDiffView(index) {
  const item = appState.history[index];
  if (!item) return;

  callPythonApi('get_diff_content', item.input_file, item.output_file).then(data => {
    if (data) {
      document.getElementById('diff-left-text').value = data.original || 'Không thể đọc file gốc';
      document.getElementById('diff-right-text').value = data.translated || 'Không thể đọc file dịch';
      document.getElementById('modal-diff').classList.remove('hidden');
    }
  });
}

function closeDiffModal() {
  document.getElementById('modal-diff').classList.add('hidden');
}

function openOutputFile(path) {
  if (path) callPythonApi('open_file_external', path);
}
