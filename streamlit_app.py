"""
streamlit_app.py - OCC-Web (Orlaco EMOS Camera Configurator) Streamlit Dashboard
Streamlit 上でカメラ設定、リアルタイム映像プレビュー（OSD付き）、レジスタ操作、プリセット管理を実行・提示できるダッシュボード。
実機カメラ接続モードと、Streamlit Cloud やデモ提示に対応するシミュレーションモードを搭載。
"""

import sys
import os
import time
import json
import io
import datetime
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import streamlit as st

# バックエンドモジュールパスの追加
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "system", "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

try:
    import net_utils
    import occ_wrapper as occ
    import streamer
except ImportError:
    net_utils = None
    occ = None
    streamer = None

# ==========================================
# ページ初期設定 & カスタムスタイル
# ==========================================
st.set_page_config(
    page_title="OCC-Web Dashboard — Orlaco EMOS Camera GUI",
    page_icon="🎥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 産業用ダークテーマ CSS
st.markdown("""
<style>
    /* 全体フォント・カラー調整 */
    .stApp {
        background-color: #0d1117;
        color: #c9d1d9;
    }
    
    /* ヘッダーバッジスタイル */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.85rem;
        font-weight: 600;
        background: rgba(35, 134, 54, 0.2);
        color: #3fb950;
        border: 1px solid rgba(63, 185, 80, 0.4);
    }
    .status-badge.demo {
        background: rgba(56, 139, 253, 0.2);
        color: #58a6ff;
        border: 1px solid rgba(88, 166, 255, 0.4);
    }
    
    /* カード風コンテナ */
    .metric-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
    
    /* ボタンのホバーエフェクト */
    .stButton > button {
        border-radius: 6px;
        font-weight: 500;
        transition: all 0.15s ease;
    }
    
    /* レジスタテーブル用等幅フォント */
    .mono-text {
        font-family: 'JetBrains Mono', 'Consolas', monospace;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# セッションステート初期化
# ==========================================
if "app_mode" not in st.session_state:
    st.session_state.app_mode = "demo"  # 'hardware' or 'demo'

if "camera_ip" not in st.session_state:
    st.session_state.camera_ip = "192.168.2.10"

if "broadcast_ip" not in st.session_state:
    st.session_state.broadcast_ip = "192.168.2.255"

if "is_streaming" not in st.session_state:
    st.session_state.is_streaming = False

if "discovered_cameras" not in st.session_state:
    st.session_state.discovered_cameras = []

if "current_roi" not in st.session_state:
    st.session_state.current_roi = {
        "roi_index": 0,
        "p1x": 0, "p1y": 0,
        "p2x": 1280, "p2y": 720,
        "output_width": 1280,
        "output_height": 720,
        "frame_rate": 30,
        "max_bitrate": 50,
        "compression": 2  # 2: H.264, 3: MJPEG
    }

if "registers_cache" not in st.session_state:
    # デフォルトのレジスタモックデータ
    st.session_state.registers_cache = {
        "0": {"name": "Video Mode (0:Stop, 1:Start)", "value": 1, "writable": True},
        "1": {"name": "Encoder Status", "value": 0, "writable": False},
        "2": {"name": "Target Bitrate (Mbps)", "value": 50, "writable": True},
        "3": {"name": "Sensor FPS Cap", "value": 30, "writable": True},
        "4": {"name": "Exposure Mode", "value": 1, "writable": True},
        "5": {"name": "White Balance Preset", "value": 2, "writable": True},
        "6": {"name": "Gain Control", "value": 12, "writable": True},
        "7": {"name": "Horizontal Mirror", "value": 0, "writable": True},
        "8": {"name": "Vertical Flip", "value": 0, "writable": True},
        "48": {"name": "ROI 0 Enable", "value": 1, "writable": True},
        "49": {"name": "ROI 0 Compression Format", "value": 2, "writable": True},
        "50": {"name": "ROI 0 Framerate", "value": 30, "writable": True},
        "51": {"name": "ROI 0 P1X (MSB)", "value": 0, "writable": True},
        "52": {"name": "ROI 0 P1X (LSB)", "value": 0, "writable": True},
        "53": {"name": "ROI 0 P1Y (MSB)", "value": 0, "writable": True},
        "54": {"name": "ROI 0 P1Y (LSB)", "value": 0, "writable": True},
        "55": {"name": "ROI 0 P2X (MSB)", "value": 5, "writable": True},
        "56": {"name": "ROI 0 P2X (LSB)", "value": 0, "writable": True},
        "57": {"name": "ROI 0 P2Y (MSB)", "value": 2, "writable": True},
        "58": {"name": "ROI 0 P2Y (LSB)", "value": 208, "writable": True},
    }

# プリセット定義
DEFAULT_PRESETS = {
    "HD 720p @ 30fps (標準 / 推奨)": {
        "output_width": 1280, "output_height": 720, "frame_rate": 30, "max_bitrate": 50, "compression": 2,
        "p1x": 0, "p1y": 0, "p2x": 1280, "p2y": 720
    },
    "Full HD 1080p @ 30fps (高精細)": {
        "output_width": 1920, "output_height": 1080, "frame_rate": 30, "max_bitrate": 80, "compression": 2,
        "p1x": 0, "p1y": 0, "p2x": 1920, "p2y": 1080
    },
    "WVGA 480p @ 60fps (高速応答)": {
        "output_width": 800, "output_height": 480, "frame_rate": 60, "max_bitrate": 30, "compression": 2,
        "p1x": 0, "p1y": 0, "p2x": 800, "p2y": 480
    },
    "Low Bandwidth MJPEG @ 15fps": {
        "output_width": 640, "output_height": 360, "frame_rate": 15, "max_bitrate": 15, "compression": 3,
        "p1x": 0, "p1y": 0, "p2x": 640, "p2y": 360
    }
}


# ==========================================
# ヘルパー関数: 仮想テストフレーム & 産業用 OSD 生成
# ==========================================
def generate_osd_frame(width=1280, height=720, ip="192.168.2.10", fps=30, bitrate=50, codec="H.264", is_live=True):
    """産業用カメラファインダー風のテスト映像 & OSD を生成"""
    img = Image.new("RGB", (width, height), color=(18, 22, 28))
    draw = ImageDraw.Draw(img)

    # カラーバー / グリッド背景の描画
    bar_width = width // 8
    colors = [
        (200, 200, 200), (200, 200, 0), (0, 200, 200), (0, 200, 0),
        (200, 0, 200), (200, 0, 0), (0, 0, 200), (30, 30, 30)
    ]
    for i, col in enumerate(colors):
        draw.rectangle([i * bar_width, 0, (i + 1) * bar_width, height // 2], fill=col)

    # グラデーション・チェッカーボード下部
    draw.rectangle([0, height // 2, width, height], fill=(28, 33, 40))
    for x in range(0, width, 40):
        draw.line([(x, height // 2), (x, height)], fill=(40, 48, 58), width=1)
    for y in range(height // 2, height, 40):
        draw.line([(0, y), (width, y)], fill=(40, 48, 58), width=1)

    # 中央ターゲット・レティクル (十字線 & 円)
    cx, cy = width // 2, height // 2
    draw.line([(cx - 40, cy), (cx + 40, cy)], fill=(0, 255, 200), width=2)
    draw.line([(cx, cy - 40), (cx, cy + 40)], fill=(0, 255, 200), width=2)
    draw.ellipse([cx - 25, cy - 25, cx + 25, cy + 25], outline=(0, 255, 200), width=2)

    # コーナーレティクル (ファインダー枠線)
    cw, cl = 30, 4  # コーナー幅、線太さ
    margin = 25
    # 左上
    draw.line([(margin, margin), (margin + cw, margin)], fill=(0, 255, 200), width=cl)
    draw.line([(margin, margin), (margin, margin + cw)], fill=(0, 255, 200), width=cl)
    # 右上
    draw.line([(width - margin - cw, margin), (width - margin, margin)], fill=(0, 255, 200), width=cl)
    draw.line([(width - margin, margin), (width - margin, margin + cw)], fill=(0, 255, 200), width=cl)
    # 左下
    draw.line([(margin, height - margin), (margin + cw, height - margin)], fill=(0, 255, 200), width=cl)
    draw.line([(margin, height - margin - cw), (margin, height - margin)], fill=(0, 255, 200), width=cl)
    # 右下
    draw.line([(width - margin - cw, height - margin), (width - margin, height - margin)], fill=(0, 255, 200), width=cl)
    draw.line([(width - margin, height - margin - cw), (width - margin, height - margin)], fill=(0, 255, 200), width=cl)

    # 産業用 OSD 情報（左上: LIVEバッジ & IP, 右上: タイムコード, 左下: 解像度/FPS/コーデック）
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-4]
    
    # 左上 OSD バナー
    draw.rectangle([margin, margin + 8, margin + 220, margin + 45], fill=(0, 0, 0, 180), outline=(50, 60, 75))
    status_text = "● LIVE (RTP)" if is_live else "■ STOPPED"
    status_color = (63, 185, 80) if is_live else (248, 81, 73)
    draw.text((margin + 12, margin + 14), status_text, fill=status_color)
    draw.text((margin + 120, margin + 14), f"{ip}", fill=(200, 200, 200))

    # 右上 OSD (タイムコード)
    draw.rectangle([width - margin - 240, margin + 8, width - margin, margin + 45], fill=(0, 0, 0, 180), outline=(50, 60, 75))
    draw.text((width - margin - 225, margin + 14), f"TIME: {now_str}", fill=(255, 255, 255))

    # 左下 OSD (解像度・FPS・ビットレート)
    draw.rectangle([margin, height - margin - 50, margin + 360, height - margin - 8], fill=(0, 0, 0, 180), outline=(50, 60, 75))
    info_text = f"RES: {width}x{height} | {fps} FPS | {codec} | {bitrate}Mbps"
    draw.text((margin + 12, height - margin - 38), info_text, fill=(88, 166, 255))

    return img


# ==========================================
# サイドバー: ネットワーク & 接続設定
# ==========================================
with st.sidebar:
    st.image("https://img.shields.io/badge/ORLACO%20EMOS-Camera%20Configurator-0078D6?style=for-the-badge&logo=cameraui", use_container_width=True)
    st.title("OCC-Web Settings")

    # 動作モード切替
    st.subheader("🛠️ 動作モード (Mode)")
    mode_selection = st.radio(
        "接続モードを選択:",
        ["🎮 デモ / シミュレーション", "⚡ 実機カメラ接続 (occ.exe)"],
        index=0 if st.session_state.app_mode == "demo" else 1,
        help="実機が手元にない場合やCloudデモでは「デモ / シミュレーション」を選択してください。"
    )
    st.session_state.app_mode = "hardware" if "実機" in mode_selection else "demo"

    if st.session_state.app_mode == "demo":
        st.markdown('<div class="status-badge demo">● DEMO MODE ACTIVE</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="status-badge">● HARDWARE MODE ACTIVE</div>', unsafe_allow_html=True)

    st.markdown("---")

    # NIC / ネットワーク設定
    st.subheader("🌐 ネットワーク接続 (NIC)")
    
    # NIC リスト取得
    interfaces = []
    if net_utils:
        try:
            interfaces = net_utils.get_network_interfaces()
        except Exception:
            pass

    if interfaces:
        nic_options = [f"{nic['name']} ({nic['ip']})" for nic in interfaces]
        selected_nic_idx = st.selectbox("使用するアダプター (NIC):", range(len(nic_options)), format_func=lambda x: nic_options[x])
        selected_nic = interfaces[selected_nic_idx]
        st.session_state.broadcast_ip = selected_nic.get("broadcast", "192.168.2.255")
        st.caption(f"サブネットマスク: `{selected_nic.get('mask', '255.255.255.0')}` | ブロードキャスト: `{st.session_state.broadcast_ip}`")
    else:
        st.info("NIC 自動検出: デフォルト値を使用中")

    camera_ip_input = st.text_input("カメラ IP アドレス:", value=st.session_state.camera_ip)
    st.session_state.camera_ip = camera_ip_input

    bcast_ip_input = st.text_input("ブロードキャスト IP:", value=st.session_state.broadcast_ip)
    st.session_state.broadcast_ip = bcast_ip_input

    # カメラ探索ボタン
    if st.button("🔍 ネットワーク探索 (Discover)", use_container_width=True):
        with st.spinner("カメラをスキャン中..."):
            if st.session_state.app_mode == "hardware" and occ:
                res = occ.discover(broadcast_ip=st.session_state.broadcast_ip)
                if res.get("success"):
                    st.session_state.discovered_cameras = res.get("cameras", [])
                    st.success(f"{len(st.session_state.discovered_cameras)} 台のカメラを発見しました！")
                else:
                    st.warning(f"検出失敗: {res.get('error', '応答なし')}")
            else:
                time.sleep(0.8)
                st.session_state.discovered_cameras = [
                    {"ip": st.session_state.camera_ip, "model": "EMOS HD 180°", "firmware": "v2.4.1", "status": "Ready"}
                ]
                st.success(f"1 台のカメラをシミュレーション検出しました (IP: {st.session_state.camera_ip})")

    st.markdown("---")
    st.caption("OCC-Web Streamlit Dashboard v1.2.0\nMIT License | © 2026 Shuntaro1996")


# ==========================================
# メイン画面ヘッダー
# ==========================================
col_title, col_stat = st.columns([3, 1])
with col_title:
    st.title("🎥 Orlaco EMOS Camera Dashboard")
    st.markdown("**産業用カメラ設定 & リアルタイム映像監視 Web インターフェース**")

with col_stat:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.session_state.app_mode == "hardware":
        st.markdown(f'<div class="status-badge">⚡ HARDWARE: {st.session_state.camera_ip}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="status-badge demo">🎮 SIMULATION: {st.session_state.camera_ip}</div>', unsafe_allow_html=True)


# ==========================================
# タブレイアウト
# ==========================================
tab_live, tab_roi, tab_registers, tab_presets = st.tabs([
    "🎥 ライブプレビュー & OSD",
    "⚙️ 映像設定 & ROI",
    "📋 レジスタ一覧 (Data Table)",
    "💾 プリセット管理 & JSON"
])

# ----------------------------------------------------
# TAB 1: ライブプレビュー & 産業用 OSD
# ----------------------------------------------------
with tab_live:
    col_view, col_ctrl = st.columns([3, 1])

    with col_view:
        st.subheader("📹 リアルタイム映像モニター (Industrial OSD)")
        
        # プレビュー画像の生成・表示
        codec_name = "H.264" if st.session_state.current_roi["compression"] == 2 else "MJPEG"
        preview_img = generate_osd_frame(
            width=st.session_state.current_roi["output_width"],
            height=st.session_state.current_roi["output_height"],
            ip=st.session_state.camera_ip,
            fps=st.session_state.current_roi["frame_rate"],
            bitrate=st.session_state.current_roi["max_bitrate"],
            codec=codec_name,
            is_live=st.session_state.is_streaming
        )

        st.image(preview_img, use_container_width=True, caption=f"RTP 映像ストリーム ({codec_name} @ {st.session_state.current_roi['output_width']}x{st.session_state.current_roi['output_height']})")

    with col_ctrl:
        st.subheader("🎮 配信制御")

        # 配信開始 / 停止トグル
        if not st.session_state.is_streaming:
            if st.button("▶ 配信開始 (Start Stream)", type="primary", use_container_width=True):
                st.session_state.is_streaming = True
                if st.session_state.app_mode == "hardware" and streamer and occ:
                    occ.set_camera_mode(st.session_state.camera_ip, "start")
                    streamer.streamer.start(port=5004, codec="h264" if st.session_state.current_roi["compression"] == 2 else "mjpeg")
                st.success("映像ストリーミングを開始しました")
                st.rerun()
        else:
            if st.button("⏹ 配信停止 (Stop Stream)", type="secondary", use_container_width=True):
                st.session_state.is_streaming = False
                if st.session_state.app_mode == "hardware" and streamer and occ:
                    streamer.streamer.stop()
                    occ.set_camera_mode(st.session_state.camera_ip, "stop")
                st.info("映像ストリーミングを停止しました")
                st.rerun()

        # カメラ再起動ボタン
        if st.button("🔄 カメラ再起動 (Restart)", use_container_width=True):
            with st.spinner("カメラをリブート中..."):
                if st.session_state.app_mode == "hardware" and occ:
                    occ.set_camera_mode(st.session_state.camera_ip, "restart")
                else:
                    time.sleep(1.0)
                st.success("再起動コマンドを送信しました（設定が反映されます）")

        st.markdown("---")
        st.subheader("📊 ストリームメトリクス")
        st.metric("解像度", f"{st.session_state.current_roi['output_width']} x {st.session_state.current_roi['output_height']}")
        st.metric("フレームレート", f"{st.session_state.current_roi['frame_rate']} FPS")
        st.metric("ビットレート", f"{st.session_state.current_roi['max_bitrate']} Mbps")
        st.metric("コーデック", codec_name)

        # スナップショットダウンロード
        img_byte_arr = io.BytesIO()
        preview_img.save(img_byte_arr, format='PNG')
        st.download_button(
            label="📸 スナップショット保存",
            data=img_byte_arr.getvalue(),
            file_name=f"snapshot_{st.session_state.camera_ip}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
            mime="image/png",
            use_container_width=True
        )


# ----------------------------------------------------
# TAB 2: 映像設定 & ROI エディタ
# ----------------------------------------------------
with tab_roi:
    st.subheader("⚙️ 映像出力 & センサー切り取り設定 (ROI 0)")

    # プリセットクイック適用
    preset_col1, preset_col2 = st.columns([3, 1])
    with preset_col1:
        selected_preset = st.selectbox("📋 クイックプリセット選択:", list(DEFAULT_PRESETS.keys()))
    with preset_col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("プリセットを適用", use_container_width=True):
            st.session_state.current_roi.update(DEFAULT_PRESETS[selected_preset])
            st.success(f"「{selected_preset}」の設定をロードしました")
            st.rerun()

    st.markdown("---")

    col_form, col_canvas = st.columns([1, 1])

    with col_form:
        st.markdown("#### 1. エンコーダー設定")
        out_res = st.selectbox(
            "出力解像度 (Width x Height):",
            ["1920x1080", "1280x720", "800x480", "640x360"],
            index=["1920x1080", "1280x720", "800x480", "640x360"].index(f"{st.session_state.current_roi['output_width']}x{st.session_state.current_roi['output_height']}") if f"{st.session_state.current_roi['output_width']}x{st.session_state.current_roi['output_height']}" in ["1920x1080", "1280x720", "800x480", "640x360"] else 1
        )
        w_val, h_val = map(int, out_res.split("x"))
        st.session_state.current_roi["output_width"] = w_val
        st.session_state.current_roi["output_height"] = h_val

        fps_val = st.slider("フレームレート (FPS):", min_value=5, max_value=60, value=st.session_state.current_roi["frame_rate"], step=5)
        st.session_state.current_roi["frame_rate"] = fps_val

        bitrate_val = st.slider("最大ビットレート (Mbps):", min_value=5, max_value=100, value=st.session_state.current_roi["max_bitrate"], step=5)
        st.session_state.current_roi["max_bitrate"] = bitrate_val

        comp_val = st.radio(
            "圧縮フォーマット (Codec):",
            ["H.264 (推奨・高圧縮)", "MJPEG (低遅延)"],
            index=0 if st.session_state.current_roi["compression"] == 2 else 1
        )
        st.session_state.current_roi["compression"] = 2 if "H.264" in comp_val else 3

        st.markdown("#### 2. センサー切り取り範囲 (ROI Coordinates)")
        c_p1, c_p2 = st.columns(2)
        with c_p1:
            p1x = st.number_input("始点 X (P1X):", min_value=0, max_value=1920, value=st.session_state.current_roi["p1x"], step=10)
            p1y = st.number_input("始点 Y (P1Y):", min_value=0, max_value=1080, value=st.session_state.current_roi["p1y"], step=10)
            st.session_state.current_roi["p1x"] = p1x
            st.session_state.current_roi["p1y"] = p1y
        with c_p2:
            p2x = st.number_input("終点 X (P2X):", min_value=0, max_value=1920, value=st.session_state.current_roi["p2x"], step=10)
            p2y = st.number_input("終点 Y (P2Y):", min_value=0, max_value=1080, value=st.session_state.current_roi["p2y"], step=10)
            st.session_state.current_roi["p2x"] = p2x
            st.session_state.current_roi["p2y"] = p2y

    with col_canvas:
        st.markdown("#### 3. センサー切り取り範囲プレビュー")
        
        # センサーキャンバス (1920x1080 センサー上の ROI 矩形可視化)
        sensor_canvas = Image.new("RGB", (480, 270), color=(22, 27, 34))
        cdraw = ImageDraw.Draw(sensor_canvas)
        
        # センサー全体枠
        cdraw.rectangle([0, 0, 479, 269], outline=(48, 54, 61), width=2)
        cdraw.text((10, 10), "Full Sensor: 1920 x 1080", fill=(139, 148, 158))
        
        # ROI 矩形 (スケール縮小描画: 1920x1080 -> 480x270)
        sx1, sy1 = int(p1x * (480 / 1920)), int(p1y * (270 / 1080))
        sx2, sy2 = int(p2x * (480 / 1920)), int(p2y * (270 / 1080))
        
        cdraw.rectangle([sx1, sy1, sx2, sy2], fill=(56, 139, 253, 60), outline=(88, 166, 255), width=2)
        cdraw.text((sx1 + 8, sy1 + 8), f"ROI ({p2x - p1x}x{p2y - p1y})", fill=(255, 255, 255))
        
        st.image(sensor_canvas, caption="CMOS センサー切り取りイメージ (水色枠が送信範囲)", use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📤 カメラへ設定を書き込む (Write ROI)", type="primary", use_container_width=True):
            with st.spinner("設定を送信中..."):
                if st.session_state.app_mode == "hardware" and occ:
                    res = occ.set_roi(
                        ip=st.session_state.camera_ip,
                        roi_index=0,
                        p1x=p1x, p1y=p1y, p2x=p2x, p2y=p2y,
                        output_width=w_val, output_height=h_val,
                        frame_rate=fps_val, max_bitrate=bitrate_val,
                        compression=st.session_state.current_roi["compression"]
                    )
                    if res.get("success"):
                        st.success("✅ 設定をカメラへ正常に書き込みました！反映のため再起動を行ってください。")
                    else:
                        st.error(f"書き込みエラー: {res.get('error')}")
                else:
                    time.sleep(0.6)
                    st.success("✅ [デモ] 設定をシミュレーション書き込みしました！")


# ----------------------------------------------------
# TAB 3: レジスタ一覧 & 編集
# ----------------------------------------------------
with tab_registers:
    st.subheader("📋 カメラ内部レジスタ一覧 (Direct Register Table)")
    
    col_reg_btn, col_reg_search = st.columns([1, 2])
    with col_reg_btn:
        if st.button("🔄 レジスタ再読込 (Read All)", use_container_width=True):
            with st.spinner("全レジスタを取得中..."):
                if st.session_state.app_mode == "hardware" and occ:
                    res = occ.get_registers(st.session_state.camera_ip)
                    if res.get("success"):
                        for k, v in res.get("registers", {}).items():
                            if k in st.session_state.registers_cache:
                                st.session_state.registers_cache[k]["value"] = v
                            else:
                                st.session_state.registers_cache[k] = {"name": f"Register {k}", "value": v, "writable": True}
                        st.success("レジスタを読み込みました")
                    else:
                        st.warning(f"取得失敗: {res.get('error')}")
                else:
                    time.sleep(0.5)
                    st.success("[デモ] レジスタ値を更新しました")

    with col_reg_search:
        search_query = st.text_input("🔍 レジスタ検索 (Index / Name):", "")

    # DataFrame 変換
    reg_rows = []
    for k, info in sorted(st.session_state.registers_cache.items(), key=lambda x: int(x[0])):
        if search_query.lower() in str(k) or search_query.lower() in info["name"].lower():
            reg_rows.append({
                "Index": int(k),
                "Name / Description": info["name"],
                "Value (Hex)": f"0x{info['value']:02X}",
                "Value (Dec)": info["value"],
                "Writable": "✅ Yes" if info["writable"] else "🔒 ReadOnly"
            })

    df_regs = pd.DataFrame(reg_rows)
    st.dataframe(df_regs, use_container_width=True, height=360)

    # 直接書き込みフォーム
    st.markdown("---")
    st.markdown("#### ✍️ 1バイト直接書き込み (Write Register)")
    c_w1, c_w2, c_w3 = st.columns([1, 1, 1])
    with c_w1:
        target_idx = st.number_input("レジスタ Index (0-255):", min_value=0, max_value=255, value=0)
    with c_w2:
        target_val = st.number_input("設定値 (0-255):", min_value=0, max_value=255, value=1)
    with c_w3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("書き込み実行 (Set Register)", use_container_width=True):
            if st.session_state.app_mode == "hardware" and occ:
                res = occ.set_register(st.session_state.camera_ip, int(target_idx), int(target_val))
                if res.get("success"):
                    st.success(f"Register {target_idx} を {target_val} に設定しました")
                else:
                    st.error(f"エラー: {res.get('error')}")
            else:
                st.session_state.registers_cache[str(target_idx)] = {
                    "name": f"Custom Reg {target_idx}", "value": int(target_val), "writable": True
                }
                st.success(f"[デモ] Register {target_idx} を {target_val} (0x{target_val:02X}) に設定しました")
                st.rerun()


# ----------------------------------------------------
# TAB 4: プリセット管理 & JSON
# ----------------------------------------------------
with tab_presets:
    st.subheader("💾 プリセット設定のエクスポート & インポート")
    st.markdown("チーム間での設定共有や、カメラ交換時のバックアップ用として JSON ファイルの入出力が可能です。")

    col_exp, col_imp = st.columns(2)

    with col_exp:
        st.markdown("#### 📤 現在の設定をエクスポート")
        export_data = {
            "version": "1.2.0",
            "camera_ip": st.session_state.camera_ip,
            "export_time": datetime.datetime.now().isoformat(),
            "roi_settings": st.session_state.current_roi,
            "registers": {k: v["value"] for k, v in st.session_state.registers_cache.items()}
        }
        json_str = json.dumps(export_data, indent=2, ensure_ascii=False)
        st.download_button(
            label="💾 設定を JSON としてダウンロード",
            data=json_str,
            file_name=f"occ_preset_{st.session_state.camera_ip}_{datetime.datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json",
            use_container_width=True
        )
        st.json(export_data, expanded=False)

    with col_imp:
        st.markdown("#### 📥 JSON 設定をインポート")
        uploaded_file = st.file_uploader("JSON プリセットファイルをアップロード:", type=["json"])
        if uploaded_file is not None:
            try:
                imp_data = json.load(uploaded_file)
                if "roi_settings" in imp_data:
                    st.session_state.current_roi.update(imp_data["roi_settings"])
                if "camera_ip" in imp_data:
                    st.session_state.camera_ip = imp_data["camera_ip"]
                st.success("プリセット設定を正常にインポートしました！")
                st.rerun()
            except Exception as e:
                st.error(f"JSON 解析エラー: {e}")
