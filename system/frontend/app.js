/**
 * app.js - Orlaco EMOS Camera Configurator GUI
 * フロントエンドアプリケーションロジック (v1.2 - SE & デザイナー統合版)
 *
 * - マルチ NIC アダプター自動検出 & ヘッダーバッジ表示
 * - 産業用 OSD & リアルタイム映像プレビュー
 * - カメラ誤設定による文鎮化（通信不能）防止ガード
 * - 設定プリセットの JSON エクスポート / インポート
 * - 設定反映の自動再起動催促モーダル
 */

'use strict';

// =========================================================================
// 定数 & 設定
// =========================================================================

const API_BASE = '';  // 同一オリジン
const COMPRESSION_LABELS = { 0: '非圧縮', 1: 'JPEG', 2: 'H.264' };
const PRESET_STORAGE_KEY = 'occ-web-presets';

// =========================================================================
// アプリケーション状態
// =========================================================================

const state = {
  selectedCamera: null,     // { ip, type, service_id, instance_id, version }
  cameras: [],
  interfaces: [],           // [ { name, ip, mask, broadcast }, ... ]
  selectedInterface: null,  // 選択中の NIC 情報
  activePresetName: null,   // 現在適用中のプリセット名
  previewRunning: false,    // プレビュー受信中フラグ
  previewPollTimer: null,   // ステータス監視タイマー
  osdTimer: null,           // OSD タイムコード更新タイマー
  pendingNetworkApply: null,// 警告確認待ちの設定ペイロード
};

// =========================================================================
// DOM 参照
// =========================================================================

const $ = (id) => document.getElementById(id);

const els = {
  // ヘッダーステータス
  headerServerStatus:     $('header-server-status'),
  headerServerStatusLabel:$('header-server-status-label'),
  headerNicBadge:         $('header-nic-badge'),
  headerNicName:          $('header-nic-name'),

  // 発見
  broadcastIp:          $('broadcast-ip'),
  btnDiscover:          $('btn-discover'),
  cameraList:           $('camera-list'),
  cameraCount:          $('camera-count'),

  // カメラ動作制御
  controlPanel:         $('control-panel'),
  btnStart:             $('btn-start'),
  btnStop:              $('btn-stop'),
  btnRestart:           $('btn-restart'),

  // プリセット & JSON入出力
  presetPanel:          $('preset-panel'),
  presetCount:          $('preset-count'),
  presetNameInput:      $('preset-name-input'),
  btnSavePreset:        $('btn-save-preset'),
  btnExportPresets:     $('btn-export-presets'),
  presetFileInput:      $('preset-file-input'),
  presetList:           $('preset-list'),
  presetActiveBar:      $('preset-active-bar'),
  presetActiveName:     $('preset-active-name'),
  btnClearPreset:       $('btn-clear-preset'),

  // 選択バー & プレースホルダー
  selectedCameraBar:    $('selected-camera-bar'),
  selectedCameraLabel:  $('selected-camera-label'),
  cameraMeta:           $('camera-meta'),
  noCameraPlaceholder:  $('no-camera-placeholder'),
  tabContainer:         $('tab-container'),

  // タブ
  tabBtns:              document.querySelectorAll('.tab-btn'),
  tabPanels:            document.querySelectorAll('.tab-panel'),

  // リアルタイム映像プレビュー & OSD
  previewLiveStatus:    $('preview-live-status'),
  previewStatusText:    $('preview-status-text'),
  statResolution:       $('stat-resolution'),
  statFps:              $('stat-fps'),
  statPort:             $('stat-port'),
  previewScreenContainer: $('preview-screen-container'),
  cameraPreviewImg:     $('camera-preview-img'),
  btnPreviewToggle:     $('btn-preview-toggle'),
  btnPreviewSnapshot:   $('btn-preview-snapshot'),
  btnPreviewFullscreen: $('btn-preview-fullscreen'),
  previewPortInput:     $('preview-port-input'),
  previewCodecSelect:   $('preview-codec-select'),
  osdCamIp:             $('osd-cam-ip'),
  osdTime:              $('osd-time'),
  osdCodecInfo:         $('osd-codec-info'),
  osdResInfo:           $('osd-res-info'),

  // 映像設定 (ROI)
  roiIndexSelect:       $('roi-index-select'),
  btnLoadRoi:           $('btn-load-roi'),
  outputWidth:          $('output-width'),
  outputHeight:         $('output-height'),
  frameRate:            $('frame-rate'),
  frameRateValue:       $('frame-rate-value'),
  maxBitrate:           $('max-bitrate'),
  maxBitrateValue:      $('max-bitrate-value'),
  p1x:                  $('p1x'),
  p1y:                  $('p1y'),
  p2x:                  $('p2x'),
  p2y:                  $('p2y'),
  btnApplyRoi:          $('btn-apply-roi'),

  // ネットワーク
  btnLoadNetwork:       $('btn-load-network'),
  dhcpEnabled:          $('dhcp-enabled'),
  staticIpFields:       $('static-ip-fields'),
  staticIp:             $('static-ip'),
  subnetMask:           $('subnet-mask'),
  rtpDestIp:            $('rtp-dest-ip'),
  rtpDestPort:          $('rtp-dest-port'),
  btnFillPcIp:          $('btn-fill-pc-ip'),
  hdrEnabled:           $('hdr-enabled'),
  overlayEnabled:       $('overlay-enabled'),
  ledEnabled:           $('led-enabled'),
  btnApplyNetwork:      $('btn-apply-network'),

  // レジスタ
  btnLoadRegisters:     $('btn-load-registers'),
  registersContainer:   $('registers-container'),

  // 再起動催促モーダル
  restartModal:         $('restart-modal'),
  modalCountdown:       $('modal-countdown'),
  countdownFill:        $('countdown-fill'),
  countdownText:        $('countdown-text'),
  btnModalRestart:      $('btn-modal-restart'),
  btnModalClose:        $('btn-modal-close'),

  // 文鎮化警告モーダル
  warningModal:         $('warning-modal'),
  warningModalDesc:     $('warning-modal-desc'),
  btnWarningConfirm:    $('btn-warning-confirm'),
  btnWarningCancel:     $('btn-warning-cancel'),

  // ユーティリティ
  toastContainer:       $('toast-container'),
  loadingOverlay:       $('loading-overlay'),
  loadingMessage:       $('loading-message'),
};

// =========================================================================
// API ユーティリティ
// =========================================================================

async function apiFetch(method, path, body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body) opts.body = JSON.stringify(body);

  try {
    const res = await fetch(API_BASE + path, opts);
    const data = await res.json();
    return data;
  } catch (err) {
    console.error(`API Error [${method} ${path}]:`, err);
    return { success: false, error: `通信エラー: ${err.message}` };
  }
}

// =========================================================================
// ローディング & トースト通知
// =========================================================================

function showLoading(message = '処理中...') {
  els.loadingMessage.textContent = message;
  els.loadingOverlay.style.display = 'flex';
}

function hideLoading() {
  els.loadingOverlay.style.display = 'none';
}

function showToast(type, title, message = '', duration = 4500) {
  const icons = {
    success: '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
    error:   '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
    warning: '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
    info:    '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
  };

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    ${icons[type] || icons.info}
    <div class="toast-body">
      <div class="toast-title">${escapeHtml(title)}</div>
      ${message ? `<div class="toast-message">${escapeHtml(message)}</div>` : ''}
    </div>
  `;

  els.toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('fade-out');
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// =========================================================================
// 起動チェック & ネットワークインターフェース自動取得
// =========================================================================

async function checkServerStatus() {
  try {
    const data = await apiFetch('GET', '/api/status');
    if (data.server === 'ok') {
      els.headerServerStatus.className = 'status-indicator ok';
      els.headerServerStatusLabel.textContent = `稼働中 (v${data.version || '1.2.0'})`;
    }
    if (!data.occ || !data.occ.available) {
      showToast('warning', 'occ.exe が未配置です', 'system/backend/ フォルダに occ.exe を配置してください（Codemonkey1973/OCC より入手）。', 10000);
    }
  } catch {
    els.headerServerStatus.className = 'status-indicator error';
    els.headerServerStatusLabel.textContent = 'オフライン';
    showToast('warning', 'バックエンドに接続できません', 'start.bat を実行してサーバーを起動してください。', 8000);
  }

}

async function loadNetworkInterfaces() {
  const data = await apiFetch('GET', '/api/interfaces');
  if (!data.success || !data.interfaces || data.interfaces.length === 0) {
    return;
  }

  state.interfaces = data.interfaces;
  // イーサネット/有線LANを優先して選択、なければ1番目
  const ethIdx = data.interfaces.findIndex(i => 
    i.name.toLowerCase().includes('ethernet') || 
    i.name.includes('イーサネット') || 
    i.name.toLowerCase().includes('lan')
  );
  const targetIdx = ethIdx >= 0 ? ethIdx : 0;
  selectInterface(targetIdx);
}

function selectInterface(idx) {
  const iface = state.interfaces[idx];
  if (!iface) return;

  state.selectedInterface = iface;
  
  // ヘッダーバッジ更新
  els.headerNicBadge.style.display = 'flex';
  els.headerNicName.textContent = `${iface.name} (${iface.ip})`;

  // 未入力の場合のみセット
  if (!els.broadcastIp.value) {
    els.broadcastIp.value = iface.broadcast || '192.168.2.10';
  }
}

function fillPcIpToRtp() {
  if (state.selectedInterface) {
    els.rtpDestIp.value = state.selectedInterface.ip;
    showToast('info', 'PC の IP アドレスを設定しました', state.selectedInterface.ip);
  } else if (state.interfaces.length > 0) {
    els.rtpDestIp.value = state.interfaces[0].ip;
    showToast('info', 'PC の IP アドレスを設定しました', state.interfaces[0].ip);
  } else {
    showToast('warning', 'PC の IP アドレスが取得できませんでした');
  }
}

// =========================================================================
// カメラ発見
// =========================================================================

async function discoverCameras() {
  const broadcastIp = els.broadcastIp.value.trim();
  if (!broadcastIp) {
    showToast('warning', 'IPアドレスを入力してください');
    return;
  }

  showLoading('カメラをスキャン中...');
  els.btnDiscover.disabled = true;

  const data = await apiFetch('POST', '/api/discover', { broadcast_ip: broadcastIp });
  hideLoading();
  els.btnDiscover.disabled = false;

  if (!data.success) {
    showToast('error', 'スキャン失敗', data.error || '不明なエラー');
    return;
  }

  state.cameras = data.cameras || [];
  renderCameraList(state.cameras);

  if (state.cameras.length === 0) {
    showToast('info', 'カメラが見つかりません', `${broadcastIp} のネットワークにカメラが検出されませんでした。LANケーブルの接続やPCのアダプター設定を確認してください。`);
  } else {
    showToast('success', `${state.cameras.length} 台のカメラを発見`, '');
    if (state.cameras.length === 1) {
      selectCamera(state.cameras[0].ip);
    }
  }
}

function renderCameraList(cameras) {
  els.cameraCount.textContent = cameras.length;

  if (cameras.length === 0) {
    els.cameraList.innerHTML = `
      <div class="empty-state">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
          <path d="M15 10l4.553-2.069A1 1 0 0121 8.847v6.306a1 1 0 01-1.447.894L15 14M3 8a2 2 0 012-2h10a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V8z" stroke-dasharray="4 2"/>
        </svg>
        <p>カメラが見つかりませんでした</p>
      </div>`;
    return;
  }

  els.cameraList.innerHTML = cameras.map((cam) => `
    <div class="camera-item${state.selectedCamera?.ip === cam.ip ? ' selected' : ''}"
         data-ip="${cam.ip}" data-index="${cam.index}">
      <span class="camera-ip">${cam.ip}</span>
      <span class="camera-meta-small">SVC: ${cam.service_id} · INST: ${cam.instance_id} · v${cam.version}</span>
    </div>
  `).join('');

  els.cameraList.querySelectorAll('.camera-item').forEach((item) => {
    item.addEventListener('click', () => selectCamera(item.dataset.ip));
  });
}

function selectCamera(ip) {
  const cam = state.cameras.find((c) => c.ip === ip);
  if (!cam) return;

  state.selectedCamera = cam;

  els.cameraList.querySelectorAll('.camera-item').forEach((item) => {
    item.classList.toggle('selected', item.dataset.ip === ip);
  });

  els.selectedCameraBar.style.display = 'flex';
  els.selectedCameraLabel.textContent = `カメラ: ${ip}`;
  els.cameraMeta.innerHTML = `
    <span>ServiceID: ${cam.service_id}</span>
    <span>InstanceID: ${cam.instance_id}</span>
    <span>v${cam.version}</span>
  `;

  els.noCameraPlaceholder.style.display = 'none';
  els.tabContainer.style.display = 'flex';

  els.controlPanel.style.display = 'block';
  initPresetPanel();

  // OSD 更新
  if (els.osdCamIp) els.osdCamIp.textContent = `CAM: ${ip}`;

  startPreview();
  showToast('info', 'カメラを選択しました', ip);
}

// =========================================================================
// カメラ動作制御 (Start / Stop / Restart)
// =========================================================================

async function setCameraMode(mode) {
  if (!state.selectedCamera) return;

  const modeLabels = {
    start: '映像配信開始',
    stop: '映像配信停止',
    restart: 'カメラ再起動'
  };

  showLoading(`カメラを${modeLabels[mode]}中...`);

  const data = await apiFetch('POST', '/api/mode', {
    ip: state.selectedCamera.ip,
    mode,
  });
  hideLoading();

  if (data.success) {
    showToast('success', `${modeLabels[mode]}を実行しました`);
    if (mode === 'start') {
      startPreview();
    }
  } else {
    showToast('error', `${modeLabels[mode]}に失敗しました`, data.error);
  }
}

// =========================================================================
// リアルタイム映像プレビュー & 産業用 OSD
// =========================================================================

async function startPreview() {
  const port = parseInt(els.previewPortInput.value) || 5004;
  const codec = els.previewCodecSelect.value || 'h264';

  const res = await apiFetch('POST', '/api/preview/start', { port, codec });
  if (res.success) {
    state.previewRunning = true;
    els.btnPreviewToggle.innerHTML = `
      <svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12"/></svg>
      プレビュー停止
    `;
    els.btnPreviewToggle.className = 'btn btn-danger';
    els.cameraPreviewImg.src = `/api/video_feed?t=${Date.now()}`;
    startPreviewPolling();
    startOsdTimer();
  }
}

async function stopPreview() {
  await apiFetch('POST', '/api/preview/stop');
  state.previewRunning = false;
  els.btnPreviewToggle.innerHTML = `
    <svg viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
    プレビュー受信開始
  `;
  els.btnPreviewToggle.className = 'btn btn-primary';
  stopPreviewPolling();
  stopOsdTimer();
  updatePreviewUi({ running: false, connected: false, fps: 0, resolution: '-', status_message: '停止中' });
}

function togglePreview() {
  if (state.previewRunning) {
    stopPreview();
  } else {
    startPreview();
  }
}

function startPreviewPolling() {
  stopPreviewPolling();
  state.previewPollTimer = setInterval(async () => {
    if (!state.previewRunning) return;
    try {
      const res = await apiFetch('GET', '/api/preview/status');
      if (res.success && res.status) {
        updatePreviewUi(res.status);
      }
    } catch (e) {
      console.warn('Preview status check failed:', e);
    }
  }, 1000);
}

function stopPreviewPolling() {
  if (state.previewPollTimer) {
    clearInterval(state.previewPollTimer);
    state.previewPollTimer = null;
  }
}

function startOsdTimer() {
  stopOsdTimer();
  const updateTime = () => {
    const now = new Date();
    if (els.osdTime) {
      els.osdTime.textContent = now.toTimeString().split(' ')[0];
    }
  };
  updateTime();
  state.osdTimer = setInterval(updateTime, 1000);
}

function stopOsdTimer() {
  if (state.osdTimer) {
    clearInterval(state.osdTimer);
    state.osdTimer = null;
  }
}

function updatePreviewUi(status) {
  if (status.connected) {
    els.previewLiveStatus.className = 'preview-live-indicator live';
    els.previewStatusText.textContent = 'LIVE (受信中)';
  } else if (status.running) {
    els.previewLiveStatus.className = 'preview-live-indicator waiting';
    els.previewStatusText.textContent = '待機中...';
  } else {
    els.previewLiveStatus.className = 'preview-live-indicator';
    els.previewStatusText.textContent = '停止中';
  }

  els.statResolution.textContent = status.resolution || '-';
  const fpsStr = (status.fps !== undefined) ? status.fps.toFixed(1) : '0.0';
  els.statFps.textContent = fpsStr;
  els.statPort.textContent = `${status.port || 5004} UDP`;

  // OSD 更新
  if (els.osdCodecInfo) {
    els.osdCodecInfo.textContent = `${(status.codec || 'H.264').toUpperCase()} / UDP:${status.port || 5004}`;
  }
  if (els.osdResInfo) {
    els.osdResInfo.textContent = `${status.resolution || '1280x720'} @ ${fpsStr}fps`;
  }
}

function captureSnapshot() {
  const img = els.cameraPreviewImg;
  const canvas = document.createElement('canvas');
  canvas.width = img.naturalWidth || 1280;
  canvas.height = img.naturalHeight || 720;
  const ctx = canvas.getContext('2d');
  
  try {
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    const link = document.createElement('a');
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    link.download = `emos_snapshot_${timestamp}.jpg`;
    link.href = canvas.toDataURL('image/jpeg', 0.95);
    link.click();
    showToast('success', 'スナップショットを保存しました');
  } catch (e) {
    showToast('warning', 'キャプチャ失敗', 'ブラウザセキュリティの制約により画像取得できませんでした。');
  }
}

function toggleFullscreen() {
  const container = els.previewScreenContainer;
  if (!document.fullscreenElement) {
    container.requestFullscreen?.() || container.webkitRequestFullscreen?.();
  } else {
    document.exitFullscreen?.() || document.webkitExitFullscreen?.();
  }
}

// =========================================================================
// 再起動催促モーダル & 文鎮化警告モーダル
// =========================================================================

function showRestartModal() {
  els.restartModal.style.display = 'flex';
  els.modalCountdown.style.display = 'none';
  els.btnModalRestart.disabled = false;
}

function hideRestartModal() {
  els.restartModal.style.display = 'none';
}

async function executeModalRestart() {
  if (!state.selectedCamera) return;

  els.btnModalRestart.disabled = true;
  els.modalCountdown.style.display = 'flex';
  els.countdownFill.style.width = '0%';
  els.countdownText.textContent = '再起動コマンドを送信中...';

  const res = await apiFetch('POST', '/api/mode', {
    ip: state.selectedCamera.ip,
    mode: 'restart',
  });

  if (res.success) {
    els.countdownText.textContent = 'カメラ起動待機中... (約8秒)';
    els.countdownFill.style.transition = 'width 8s linear';
    setTimeout(() => { els.countdownFill.style.width = '100%'; }, 50);

    setTimeout(() => {
      hideRestartModal();
      showToast('success', 'カメラの再起動が完了しました', '新しい設定が有効化されました。');
      apiFetch('POST', '/api/mode', { ip: state.selectedCamera.ip, mode: 'start' });
    }, 8200);
  } else {
    els.countdownText.textContent = `再起動エラー: ${res.error || '失敗'}`;
    els.btnModalRestart.disabled = false;
  }
}

function showWarningModal(desc, onConfirm) {
  els.warningModalDesc.innerHTML = desc;
  els.warningModal.style.display = 'flex';
  state.pendingNetworkApply = onConfirm;
}

function hideWarningModal() {
  els.warningModal.style.display = 'none';
  state.pendingNetworkApply = null;
}

function confirmWarningModal() {
  if (state.pendingNetworkApply) {
    const callback = state.pendingNetworkApply;
    hideWarningModal();
    callback();
  }
}

// =========================================================================
// ROI 映像設定
// =========================================================================

async function loadRoi() {
  if (!state.selectedCamera) return;

  const roiIndex = parseInt(els.roiIndexSelect.value);
  showLoading(`ROI ${roiIndex} を読み込み中...`);

  const data = await apiFetch('GET', `/api/roi/${roiIndex}?ip=${encodeURIComponent(state.selectedCamera.ip)}`);
  hideLoading();

  if (!data.success) {
    showToast('error', 'ROI 読み込み失敗', data.error || '');
    return;
  }

  const roi = data.roi;
  if (!roi) {
    showToast('warning', 'ROI データが取得できませんでした');
    return;
  }

  els.outputWidth.value      = roi.output_width  ?? 1280;
  els.outputHeight.value     = roi.output_height ?? 720;
  els.frameRate.value        = roi.frame_rate    ?? 30;
  els.frameRateValue.value   = roi.frame_rate    ?? 30;
  els.maxBitrate.value       = roi.max_bitrate   ?? 50;
  els.maxBitrateValue.value  = roi.max_bitrate   ?? 50;
  els.p1x.value              = roi.p1x  ?? 0;
  els.p1y.value              = roi.p1y  ?? 0;
  els.p2x.value              = roi.p2x  ?? 1280;
  els.p2y.value              = roi.p2y  ?? 720;

  const compressionVal = roi.compression ?? 2;
  document.querySelectorAll('input[name="compression"]').forEach((r) => {
    r.checked = parseInt(r.value) === compressionVal;
  });

  showToast('success', `ROI ${roiIndex} を読み込みました`);
}

async function applyRoi() {
  if (!state.selectedCamera) return;

  const compression = parseInt(
    document.querySelector('input[name="compression"]:checked')?.value ?? '2'
  );

  const payload = {
    ip:            state.selectedCamera.ip,
    roi_index:     parseInt(els.roiIndexSelect.value),
    p1x:           parseInt(els.p1x.value),
    p1y:           parseInt(els.p1y.value),
    p2x:           parseInt(els.p2x.value),
    p2y:           parseInt(els.p2y.value),
    output_width:  parseInt(els.outputWidth.value),
    output_height: parseInt(els.outputHeight.value),
    frame_rate:    parseInt(els.frameRate.value),
    max_bitrate:   parseInt(els.maxBitrate.value),
    compression,
  };

  if (!validateRoiPayload(payload)) return;

  showLoading('映像設定を適用中...');
  const data = await apiFetch('POST', '/api/roi', payload);
  hideLoading();

  if (data.success) {
    showToast('success', '映像設定を送信しました',
      `ROI ${payload.roi_index}: ${payload.output_width}×${payload.output_height} @ ${payload.frame_rate}fps`);
    showRestartModal();
  } else {
    showToast('error', '映像設定の適用に失敗しました', data.error || '');
  }
}

function validateRoiPayload(p) {
  if (p.p2x <= p.p1x || p.p2y <= p.p1y) {
    showToast('warning', '座標エラー', 'P2X > P1X、P2Y > P1Y になるよう設定してください。');
    return false;
  }
  if (p.output_width < 1 || p.output_height < 1) {
    showToast('warning', '解像度エラー', '幅・高さは 1px 以上を指定してください。');
    return false;
  }
  if (p.frame_rate < 1 || p.frame_rate > 60) {
    showToast('warning', 'FPS エラー', 'フレームレートは 1〜60 fps の範囲で指定してください。');
    return false;
  }
  return true;
}

// =========================================================================
// ネットワーク設定 & 文鎮化ガード
// =========================================================================

const REGISTER_IDX = {
  LED_MODE:       0,
  STREAM_PROTOCOL: 1,
  STATIC_IP_0:    2,
  STATIC_IP_1:    3,
  STATIC_IP_2:    4,
  STATIC_IP_3:    5,
  MASK_0:         6,
  MASK_1:         7,
  MASK_2:         8,
  MASK_3:         9,
  RTP_DEST_IP_0:  28,
  RTP_DEST_IP_1:  29,
  RTP_DEST_IP_2:  30,
  RTP_DEST_IP_3:  31,
  RTP_DEST_PORT_0: 38,
  RTP_DEST_PORT_1: 39,
  HDR:            48,
  OVERLAY:        49,
  DHCP:           50,
};

async function loadNetworkSettings() {
  if (!state.selectedCamera) return;

  showLoading('ネットワーク設定を読み込み中...');
  const data = await apiFetch('GET', `/api/registers?ip=${encodeURIComponent(state.selectedCamera.ip)}`);
  hideLoading();

  if (!data.success || !data.registers) {
    showToast('error', '設定の読み込みに失敗しました', data.error || '');
    return;
  }

  const regs = {};
  data.registers.forEach((r) => { regs[r.index] = r.decimal; });

  if ([2,3,4,5].every((i) => regs[i] !== undefined)) {
    els.staticIp.value = `${regs[2]}.${regs[3]}.${regs[4]}.${regs[5]}`;
  }
  if ([6,7,8,9].every((i) => regs[i] !== undefined)) {
    els.subnetMask.value = `${regs[6]}.${regs[7]}.${regs[8]}.${regs[9]}`;
  }
  if ([28,29,30,31].every((i) => regs[i] !== undefined)) {
    els.rtpDestIp.value = `${regs[28]}.${regs[29]}.${regs[30]}.${regs[31]}`;
  }
  if (regs[38] !== undefined && regs[39] !== undefined) {
    els.rtpDestPort.value = (regs[38] << 8) | regs[39];
  }

  if (regs[50] !== undefined) els.dhcpEnabled.checked    = regs[50] === 1;
  if (regs[48] !== undefined) els.hdrEnabled.checked     = regs[48] === 1;
  if (regs[49] !== undefined) els.overlayEnabled.checked = regs[49] === 1;
  if (regs[0]  !== undefined) els.ledEnabled.checked     = regs[0]  === 1;

  if (regs[1] !== undefined) {
    document.querySelectorAll('input[name="stream-protocol"]').forEach((r) => {
      r.checked = parseInt(r.value) === regs[1];
    });
  }

  updateStaticIpVisibility();
  showToast('success', 'ネットワーク設定を読み込みました');
}

async function applyNetworkSettings() {
  if (!state.selectedCamera) return;

  const newStaticIp = els.staticIp.value.trim();
  const isDhcp = els.dhcpEnabled.checked;

  // 文鎮化チェック: 静的IPの場合、現在のPCのIPとセグメントが一致するか検証
  if (!isDhcp && state.selectedInterface && newStaticIp) {
    const pcIpParts = state.selectedInterface.ip.split('.').map(Number);
    const camIpParts = newStaticIp.split('.').map(Number);
    if (camIpParts.length === 4 && (pcIpParts[0] !== camIpParts[0] || pcIpParts[1] !== camIpParts[1] || pcIpParts[2] !== camIpParts[2])) {
      const desc = `設定しようとしているカメラの静的IP (<strong>${escapeHtml(newStaticIp)}</strong>) は、現在接続中のPCのIP (<strong>${state.selectedInterface.ip}</strong>) と異なるネットワークセグメントです。<br><br>このまま適用してカメラを再起動すると、<strong>PC側のIPアドレスを変更するまでカメラと通信できなくなります</strong>が、本当に適用しますか？`;
      showWarningModal(desc, () => doSendNetworkSettings());
      return;
    }
  }

  doSendNetworkSettings();
}

async function doSendNetworkSettings() {
  const registers = {};
  registers[REGISTER_IDX.DHCP] = els.dhcpEnabled.checked ? 1 : 0;

  if (!els.dhcpEnabled.checked) {
    const ipParts = parseIPv4(els.staticIp.value);
    if (!ipParts) { showToast('warning', '静的IPアドレスの形式が正しくありません'); return; }
    registers[REGISTER_IDX.STATIC_IP_0] = ipParts[0];
    registers[REGISTER_IDX.STATIC_IP_1] = ipParts[1];
    registers[REGISTER_IDX.STATIC_IP_2] = ipParts[2];
    registers[REGISTER_IDX.STATIC_IP_3] = ipParts[3];

    const maskParts = parseIPv4(els.subnetMask.value);
    if (maskParts) {
      registers[REGISTER_IDX.MASK_0] = maskParts[0];
      registers[REGISTER_IDX.MASK_1] = maskParts[1];
      registers[REGISTER_IDX.MASK_2] = maskParts[2];
      registers[REGISTER_IDX.MASK_3] = maskParts[3];
    }
  }

  const rtpParts = parseIPv4(els.rtpDestIp.value);
  if (rtpParts) {
    registers[REGISTER_IDX.RTP_DEST_IP_0] = rtpParts[0];
    registers[REGISTER_IDX.RTP_DEST_IP_1] = rtpParts[1];
    registers[REGISTER_IDX.RTP_DEST_IP_2] = rtpParts[2];
    registers[REGISTER_IDX.RTP_DEST_IP_3] = rtpParts[3];
  }

  const port = parseInt(els.rtpDestPort.value);
  if (!isNaN(port) && port > 0) {
    registers[REGISTER_IDX.RTP_DEST_PORT_0] = (port >> 8) & 0xFF;
    registers[REGISTER_IDX.RTP_DEST_PORT_1] = port & 0xFF;
  }

  registers[REGISTER_IDX.HDR]              = els.hdrEnabled.checked     ? 1 : 0;
  registers[REGISTER_IDX.OVERLAY]          = els.overlayEnabled.checked ? 1 : 0;
  registers[REGISTER_IDX.LED_MODE]         = els.ledEnabled.checked     ? 1 : 0;
  registers[REGISTER_IDX.STREAM_PROTOCOL]  = parseInt(
    document.querySelector('input[name="stream-protocol"]:checked')?.value ?? '0'
  );

  showLoading('ネットワーク設定を適用中...');
  const data = await apiFetch('POST', '/api/registers/bulk', {
    ip: state.selectedCamera.ip,
    registers,
  });
  hideLoading();

  if (data.success) {
    showToast('success', 'ネットワーク設定を送信しました');
    showRestartModal();
  } else {
    showToast('error', '設定の適用に失敗しました', data.error || '');
  }
}

function parseIPv4(str) {
  if (!str) return null;
  const parts = str.trim().split('.').map(Number);
  if (parts.length !== 4) return null;
  if (parts.some((p) => isNaN(p) || p < 0 || p > 255)) return null;
  return parts;
}

// =========================================================================
// 詳細レジスタ
// =========================================================================

async function loadRegisters() {
  if (!state.selectedCamera) return;

  showLoading('全レジスタを読み込み中...');
  const data = await apiFetch('GET', `/api/registers?ip=${encodeURIComponent(state.selectedCamera.ip)}`);
  hideLoading();

  if (!data.success || !data.registers) {
    showToast('error', 'レジスタ読み込み失敗', data.error || '');
    return;
  }

  renderRegistersTable(data.registers);
  showToast('success', `${data.registers.length} 件のレジスタを読み込みました`);
}

function renderRegistersTable(registers) {
  if (!registers || registers.length === 0) {
    els.registersContainer.innerHTML = `
      <div class="empty-state">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
          <path d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18"/>
        </svg>
        <p>レジスタが取得できませんでした</p>
      </div>`;
    return;
  }

  const rows = registers.map((reg) => `
    <tr>
      <td class="reg-index">${String(reg.index).padStart(2, '0')}</td>
      <td class="reg-address">${reg.address}</td>
      <td class="reg-hex">${reg.hex}</td>
      <td class="reg-dec">${reg.decimal}</td>
      <td class="reg-name">${escapeHtml(reg.name || '')}</td>
      <td>
        <div class="reg-edit">
          <input type="number" class="input input-reg" id="reg-val-${reg.index}"
                 value="${reg.decimal}" min="0" max="255">
          <button class="btn-reg-write" data-reg-index="${reg.index}">書込</button>
        </div>
      </td>
    </tr>
  `).join('');

  els.registersContainer.innerHTML = `
    <div class="registers-table-wrapper">
      <table class="registers-table">
        <thead>
          <tr>
            <th class="reg-index">#</th>
            <th class="reg-address">アドレス</th>
            <th class="reg-hex">Hex</th>
            <th class="reg-dec">Dec</th>
            <th class="reg-name">名称</th>
            <th>書き込み</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;

  els.registersContainer.querySelectorAll('.btn-reg-write').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const idx = parseInt(btn.dataset.regIndex);
      const valInput = $(`reg-val-${idx}`);
      const value = parseInt(valInput.value);

      if (isNaN(value) || value < 0 || value > 255) {
        showToast('warning', '無効な値', '0〜255 の範囲で指定してください。');
        return;
      }

      btn.textContent = '...';
      btn.disabled = true;

      const data = await apiFetch('POST', '/api/register', {
        ip: state.selectedCamera.ip,
        index: idx,
        value,
      });

      btn.textContent = '書込';
      btn.disabled = false;

      if (data.success) {
        showToast('success', `レジスタ ${idx} を書き込みました`, `値: ${value}`);
        const row = btn.closest('tr');
        row.querySelector('.reg-dec').textContent = value;
        row.querySelector('.reg-hex').textContent = '0x' + value.toString(16).padStart(2,'0').toUpperCase();
        showRestartModal();
      } else {
        showToast('error', 'レジスタ書き込み失敗', data.error || '');
      }
    });
  });
}

// =========================================================================
// 設定プリセット管理 & JSON エクスポート / インポート
// =========================================================================

function loadPresetsFromStorage() {
  try {
    const raw = localStorage.getItem(PRESET_STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function savePresetsToStorage(presets) {
  localStorage.setItem(PRESET_STORAGE_KEY, JSON.stringify(presets));
}

function captureCurrentSettings() {
  return {
    roi_index:     parseInt(els.roiIndexSelect.value),
    output_width:  parseInt(els.outputWidth.value),
    output_height: parseInt(els.outputHeight.value),
    frame_rate:    parseInt(els.frameRate.value),
    max_bitrate:   parseInt(els.maxBitrate.value),
    compression:   parseInt(
      document.querySelector('input[name="compression"]:checked')?.value ?? '2'
    ),
    p1x: parseInt(els.p1x.value),
    p1y: parseInt(els.p1y.value),
    p2x: parseInt(els.p2x.value),
    p2y: parseInt(els.p2y.value),
    dhcp:             els.dhcpEnabled.checked,
    static_ip:        els.staticIp.value,
    subnet_mask:      els.subnetMask.value,
    rtp_dest_ip:      els.rtpDestIp.value,
    rtp_dest_port:    els.rtpDestPort.value,
    stream_protocol:  parseInt(
      document.querySelector('input[name="stream-protocol"]:checked')?.value ?? '0'
    ),
    hdr:              els.hdrEnabled.checked,
    overlay:          els.overlayEnabled.checked,
    led:              els.ledEnabled.checked,
  };
}

function applySettingsToForm(settings) {
  if (settings.roi_index     !== undefined) els.roiIndexSelect.value    = settings.roi_index;
  if (settings.output_width  !== undefined) els.outputWidth.value       = settings.output_width;
  if (settings.output_height !== undefined) els.outputHeight.value      = settings.output_height;
  if (settings.frame_rate    !== undefined) {
    els.frameRate.value      = settings.frame_rate;
    els.frameRateValue.value = settings.frame_rate;
    updateFpsPresets(settings.frame_rate);
  }
  if (settings.max_bitrate   !== undefined) {
    els.maxBitrate.value      = settings.max_bitrate;
    els.maxBitrateValue.value = settings.max_bitrate;
  }
  if (settings.compression   !== undefined) {
    document.querySelectorAll('input[name="compression"]').forEach((r) => {
      r.checked = parseInt(r.value) === settings.compression;
    });
  }
  if (settings.p1x !== undefined) els.p1x.value = settings.p1x;
  if (settings.p1y !== undefined) els.p1y.value = settings.p1y;
  if (settings.p2x !== undefined) els.p2x.value = settings.p2x;
  if (settings.p2y !== undefined) els.p2y.value = settings.p2y;

  if (settings.dhcp !== undefined) {
    els.dhcpEnabled.checked = settings.dhcp;
    updateStaticIpVisibility();
  }
  if (settings.static_ip     !== undefined) els.staticIp.value       = settings.static_ip;
  if (settings.subnet_mask   !== undefined) els.subnetMask.value     = settings.subnet_mask;
  if (settings.rtp_dest_ip   !== undefined) els.rtpDestIp.value      = settings.rtp_dest_ip;
  if (settings.rtp_dest_port !== undefined) els.rtpDestPort.value    = settings.rtp_dest_port;
  if (settings.stream_protocol !== undefined) {
    document.querySelectorAll('input[name="stream-protocol"]').forEach((r) => {
      r.checked = parseInt(r.value) === settings.stream_protocol;
    });
  }
  if (settings.hdr     !== undefined) els.hdrEnabled.checked     = settings.hdr;
  if (settings.overlay !== undefined) els.overlayEnabled.checked = settings.overlay;
  if (settings.led     !== undefined) els.ledEnabled.checked     = settings.led;
}

function savePreset() {
  const name = els.presetNameInput.value.trim();
  if (!name) {
    showToast('warning', 'プリセット名を入力してください');
    els.presetNameInput.focus();
    return;
  }

  const presets = loadPresetsFromStorage();
  const existing = presets.findIndex((p) => p.name === name);
  const entry = {
    name,
    settings: captureCurrentSettings(),
    savedAt: new Date().toLocaleString('ja-JP', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }),
  };

  if (existing >= 0) {
    presets[existing] = entry;
    showToast('success', `プリセット「${name}」を上書き保存しました`);
  } else {
    presets.push(entry);
    showToast('success', `プリセット「${name}」を保存しました`);
  }

  savePresetsToStorage(presets);
  els.presetNameInput.value = '';
  renderPresetList();
  setActivePreset(name);
}

function loadPreset(name) {
  const presets = loadPresetsFromStorage();
  const preset = presets.find((p) => p.name === name);
  if (!preset) {
    showToast('error', `プリセット「${name}」が見つかりません`);
    return;
  }

  applySettingsToForm(preset.settings);
  setActivePreset(name);
  showToast('success', `プリセット「${name}」を読み込みました`,
    '設定をカメラに反映するには「適用」ボタンを押してください。');
}

function deletePreset(name) {
  const presets = loadPresetsFromStorage().filter((p) => p.name !== name);
  savePresetsToStorage(presets);
  if (state.activePresetName === name) clearActivePreset();
  renderPresetList();
  showToast('info', `プリセット「${name}」を削除しました`);
}

function exportPresetsToJson() {
  const presets = loadPresetsFromStorage();
  if (presets.length === 0) {
    showToast('warning', 'エクスポートするプリセットがありません');
    return;
  }
  const jsonStr = JSON.stringify(presets, null, 2);
  const blob = new Blob([jsonStr], { type: 'application/json' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = `emos_presets_${new Date().toISOString().slice(0,10)}.json`;
  link.click();
  showToast('success', 'プリセットを JSON ファイルとして保存しました');
}

function importPresetsFromJson(file) {
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    try {
      const imported = JSON.parse(e.target.result);
      if (!Array.isArray(imported)) throw new Error('フォーマットが不正です');
      
      const current = loadPresetsFromStorage();
      const map = new Map();
      current.forEach(p => map.set(p.name, p));
      imported.forEach(p => {
        if (p.name && p.settings) map.set(p.name, p);
      });
      
      const merged = Array.from(map.values());
      savePresetsToStorage(merged);
      renderPresetList();
      showToast('success', `${imported.length} 件のプリセットをインポートしました`);
    } catch (err) {
      showToast('error', 'インポート失敗', '有効な JSON ファイルではありません。');
    }
  };
  reader.readAsText(file);
}

function setActivePreset(name) {
  state.activePresetName = name;
  els.presetActiveName.textContent = name;
  els.presetActiveBar.style.display = 'flex';
  renderPresetList();
}

function clearActivePreset() {
  state.activePresetName = null;
  els.presetActiveBar.style.display = 'none';
  renderPresetList();
}

function renderPresetList() {
  const presets = loadPresetsFromStorage();
  els.presetCount.textContent = presets.length;

  if (presets.length === 0) {
    els.presetList.innerHTML = `
      <div class="empty-state">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
          <path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z" stroke-dasharray="4 2"/>
        </svg>
        <p>保存済みプリセットなし</p>
      </div>`;
    return;
  }

  els.presetList.innerHTML = presets.map((p) => `
    <div class="preset-item${state.activePresetName === p.name ? ' active-preset' : ''}">
      <span class="preset-item-name" title="クリックして読み込む" data-name="${escapeHtml(p.name)}">${escapeHtml(p.name)}</span>
      <span class="preset-item-meta">${p.savedAt}</span>
      <button class="btn-preset-load" data-name="${escapeHtml(p.name)}">読込</button>
      <button class="btn-preset-delete" data-name="${escapeHtml(p.name)}" title="削除">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="3 6 5 6 21 6"/>
          <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/>
          <path d="M10 11v6M14 11v6"/>
          <path d="M9 6V4h6v2"/>
        </svg>
      </button>
    </div>
  `).join('');

  els.presetList.querySelectorAll('.preset-item-name').forEach((el) => {
    el.addEventListener('click', () => loadPreset(el.dataset.name));
  });
  els.presetList.querySelectorAll('.btn-preset-load').forEach((btn) => {
    btn.addEventListener('click', () => loadPreset(btn.dataset.name));
  });
  els.presetList.querySelectorAll('.btn-preset-delete').forEach((btn) => {
    btn.addEventListener('click', () => {
      if (confirm(`プリセット「${btn.dataset.name}」を削除しますか？`)) {
        deletePreset(btn.dataset.name);
      }
    });
  });
}

function initPresetPanel() {
  els.presetPanel.style.display = 'block';
  renderPresetList();
}

// =========================================================================
// タブ切り替え & スライダー
// =========================================================================

function switchTab(tabName) {
  els.tabBtns.forEach((btn) => btn.classList.toggle('active', btn.dataset.tab === tabName));
  els.tabPanels.forEach((panel) => panel.classList.toggle('active', panel.id === `tab-${tabName}`));
}

function syncSliders() {
  els.frameRate.addEventListener('input', () => {
    els.frameRateValue.value = els.frameRate.value;
    updateFpsPresets(parseInt(els.frameRate.value));
  });
  els.frameRateValue.addEventListener('input', () => {
    els.frameRate.value = els.frameRateValue.value;
    updateFpsPresets(parseInt(els.frameRateValue.value));
  });

  els.maxBitrate.addEventListener('input', () => { els.maxBitrateValue.value = els.maxBitrate.value; });
  els.maxBitrateValue.addEventListener('input', () => { els.maxBitrate.value = els.maxBitrateValue.value; });
}

function updateFpsPresets(fps) {
  document.querySelectorAll('.preset-btn[data-fps]').forEach((btn) => {
    btn.classList.toggle('active', parseInt(btn.dataset.fps) === fps);
  });
}

function initPresets() {
  document.querySelectorAll('.preset-btn[data-w]').forEach((btn) => {
    btn.addEventListener('click', () => {
      els.outputWidth.value  = btn.dataset.w;
      els.outputHeight.value = btn.dataset.h;
      els.p2x.value          = btn.dataset.w;
      els.p2y.value          = btn.dataset.h;
    });
  });

  document.querySelectorAll('.preset-btn[data-fps]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const fps = parseInt(btn.dataset.fps);
      els.frameRate.value      = fps;
      els.frameRateValue.value = fps;
      updateFpsPresets(fps);
    });
  });
}

function updateStaticIpVisibility() {
  if (els.dhcpEnabled.checked) {
    els.staticIpFields.classList.add('hidden');
  } else {
    els.staticIpFields.classList.remove('hidden');
  }
}

// =========================================================================
// イベントリスナー登録
// =========================================================================

function initEventListeners() {
  els.btnFillPcIp.addEventListener('click', fillPcIpToRtp);

  // カメラ発見
  els.btnDiscover.addEventListener('click', discoverCameras);
  els.broadcastIp.addEventListener('keydown', (e) => { if (e.key === 'Enter') discoverCameras(); });

  // カメラ動作制御
  els.btnStart.addEventListener('click',   () => setCameraMode('start'));
  els.btnStop.addEventListener('click',    () => setCameraMode('stop'));
  els.btnRestart.addEventListener('click', () => setCameraMode('restart'));

  // リアルタイム映像プレビュー
  els.btnPreviewToggle.addEventListener('click', togglePreview);
  els.btnPreviewSnapshot.addEventListener('click', captureSnapshot);
  els.btnPreviewFullscreen.addEventListener('click', toggleFullscreen);

  // 再起動催促モーダル
  els.btnModalRestart.addEventListener('click', executeModalRestart);
  els.btnModalClose.addEventListener('click',   hideRestartModal);

  // 文鎮化警告モーダル
  els.btnWarningConfirm.addEventListener('click', confirmWarningModal);
  els.btnWarningCancel.addEventListener('click',  hideWarningModal);

  // タブ切り替え
  els.tabBtns.forEach((btn) => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  // 映像設定 (ROI)
  els.btnLoadRoi.addEventListener('click',   loadRoi);
  els.btnApplyRoi.addEventListener('click',  applyRoi);

  // ネットワーク設定
  els.btnLoadNetwork.addEventListener('click',   loadNetworkSettings);
  els.btnApplyNetwork.addEventListener('click',  applyNetworkSettings);
  els.dhcpEnabled.addEventListener('change', updateStaticIpVisibility);

  // 詳細レジスタ
  els.btnLoadRegisters.addEventListener('click', loadRegisters);

  // プリセット & JSON入出力
  els.btnSavePreset.addEventListener('click', savePreset);
  els.btnClearPreset.addEventListener('click', clearActivePreset);
  els.presetNameInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') savePreset(); });
  els.btnExportPresets.addEventListener('click', exportPresetsToJson);
  els.presetFileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files[0]) {
      importPresetsFromJson(e.target.files[0]);
      e.target.value = '';
    }
  });

  // スライダー & プリセット初期化
  syncSliders();
  initPresets();

  // ブラウザ終了時の自動サーバーシャットダウン
  initAutoShutdown();
}

// =========================================================================
// 自動シャットダウン（ブラウザ終了検知）
// =========================================================================

function initAutoShutdown() {
  const sendPing = () => {
    fetch(API_BASE + '/api/heartbeat', { method: 'POST', keepalive: true }).catch(() => {});
  };

  // 1. 即時送信 & 定期ハートビート（1.5秒おき）
  sendPing();
  setInterval(sendPing, 1500);

  // 2. タブへのフォーカス復帰時にも即座に送信
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') sendPing();
  });

  // 3. ブラウザを閉じた瞬間に即座にシャットダウンリクエスト
  window.addEventListener('beforeunload', () => {
    if (navigator.sendBeacon) {
      navigator.sendBeacon(API_BASE + '/api/shutdown');
    } else {
      fetch(API_BASE + '/api/shutdown', { method: 'POST', keepalive: true }).catch(() => {});
    }
  });
}

// =========================================================================
// 初期化
// =========================================================================

async function init() {
  initEventListeners();
  await checkServerStatus();
  await loadNetworkInterfaces();
}

document.addEventListener('DOMContentLoaded', init);
