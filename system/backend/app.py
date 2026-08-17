"""
app.py - Orlaco Camera Configurator Web GUI
Flask REST API バックエンドサーバー (Waitress WSGI 本番対応)

occ.exe をサブプロセスとして呼び出し、カメラ設定・リアルタイム映像プレビュー・
ネットワークインターフェース情報を提供する。
"""

import logging
import os
import sys
import time
import threading
import ipaddress
from flask import Flask, jsonify, request, send_from_directory, Response
from flask_cors import CORS

import occ_wrapper as occ
import streamer
import net_utils

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Flask アプリ初期化
app = Flask(__name__)
CORS(app)  # CORS許可

# フロントエンドの静的ファイルパス
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")


# =========================================================================
# 静的ファイル配信（フロントエンド）
# =========================================================================

@app.route("/")
def index():
    """フロントエンドのHTMLを返す。"""
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    """CSS・JS などの静的ファイルを返す。"""
    return send_from_directory(FRONTEND_DIR, filename)


# =========================================================================
# ライフサイクル管理（ハートビート & Graceful Shutdown）
# =========================================================================

_heartbeat_lock = threading.Lock()
_last_heartbeat = time.time()
_has_connected = False
_server_start_time = time.time()


def _graceful_shutdown():
    """リソースを解放してサーバーを安全に終了する。"""
    logger.info("Performing graceful shutdown...")
    try:
        streamer.streamer.cleanup()
    except Exception as e:
        logger.warning(f"Error during streamer cleanup: {e}")
    time.sleep(0.3)
    os._exit(0)


def _heartbeat_watcher():
    """
    ブラウザ画面が閉じられた場合に自動終了する監視スレッド。
    起動猶予期間（30秒）と安全マージン（25秒）を設ける。
    """
    global _last_heartbeat, _has_connected
    while True:
        time.sleep(2.0)
        with _heartbeat_lock:
            if time.time() - _server_start_time < 30.0:
                continue

            if _has_connected:
                if time.time() - _last_heartbeat > 25.0:
                    logger.info("Browser closed (heartbeat lost for >25s). Shutting down...")
                    _graceful_shutdown()


# 監視スレッド開始
threading.Thread(target=_heartbeat_watcher, daemon=True).start()


@app.route("/api/heartbeat", methods=["GET", "POST"])
def api_heartbeat():
    """ブラウザからのハートビートを受信し、最終アクセス時刻を更新する。"""
    global _last_heartbeat, _has_connected
    with _heartbeat_lock:
        _last_heartbeat = time.time()
        _has_connected = True
    return jsonify({"status": "ok"})


@app.route("/api/shutdown", methods=["POST"])
def api_shutdown():
    """ブラウザ終了時 (beforeunload / sendBeacon) に即座にサーバーを終了する。"""
    logger.info("Shutdown requested from browser beforeunload.")
    threading.Thread(target=_graceful_shutdown, daemon=True).start()
    return jsonify({"success": True, "message": "Server shutting down"})


# =========================================================================
# システム系 API & ネットワークインターフェース
# =========================================================================

@app.route("/api/status", methods=["GET"])
def api_status():
    """サーバーステータスと occ.exe の利用可否を返す。"""
    global _last_heartbeat, _has_connected
    with _heartbeat_lock:
        _last_heartbeat = time.time()
        _has_connected = True
    occ_status = occ.check_occ_available()
    return jsonify({
        "server": "ok",
        "occ": occ_status,
        "version": "1.2.0",
    })


@app.route("/api/interfaces", methods=["GET"])
def api_get_interfaces():
    """
    ローカル PC のネットワークアダプター一覧（IP、サブネット、ブロードキャスト）を返す。
    マルチ NIC 環境でカメラ接続用 NIC を選択する際に使用。
    """
    interfaces = net_utils.get_network_interfaces()
    return jsonify({
        "success": True,
        "interfaces": interfaces
    })


# =========================================================================
# カメラ発見 API
# =========================================================================

@app.route("/api/discover", methods=["POST"])
def api_discover():
    """
    ネットワーク上のOrlacoカメラを発見する。
    """
    data = request.get_json()
    if not data or "broadcast_ip" not in data:
        return jsonify({"success": False, "error": "broadcast_ip が必要です"}), 400

    broadcast_ip = str(data["broadcast_ip"]).strip()
    if not broadcast_ip:
        return jsonify({"success": False, "error": "broadcast_ip が空です"}), 400

    logger.info(f"Camera discovery: broadcast={broadcast_ip}")
    result = occ.discover_cameras(broadcast_ip)
    return jsonify(result)


# =========================================================================
# レジスタ API
# =========================================================================

@app.route("/api/registers", methods=["GET"])
def api_get_registers():
    """カメラの全レジスタを読み込む。"""
    camera_ip = request.args.get("ip")
    if not camera_ip:
        return jsonify({"success": False, "error": "クエリパラメータ 'ip' が必要です"}), 400

    logger.info(f"Read all registers: ip={camera_ip}")
    result = occ.get_registers(camera_ip)
    return jsonify(result)


@app.route("/api/register", methods=["POST"])
def api_write_register():
    """単一レジスタに値を書き込む。"""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "JSONボディが必要です"}), 400

    camera_ip = data.get("ip")
    reg_index = data.get("index")
    value = data.get("value")

    if not camera_ip:
        return jsonify({"success": False, "error": "ip が必要です"}), 400
    if reg_index is None:
        return jsonify({"success": False, "error": "index が必要です"}), 400
    if value is None:
        return jsonify({"success": False, "error": "value が必要です"}), 400

    try:
        reg_index = int(reg_index)
        value = int(value)
    except ValueError:
        return jsonify({"success": False, "error": "index と value は整数である必要があります"}), 400

    logger.info(f"Write register: ip={camera_ip}, index={reg_index}, value={value}")
    result = occ.set_register(camera_ip, reg_index, value)
    return jsonify(result)


@app.route("/api/registers/bulk", methods=["POST"])
def api_write_registers_bulk():
    """複数レジスタを一括書き込みする。"""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "JSONボディが必要です"}), 400

    camera_ip = data.get("ip")
    reg_dict = data.get("registers")

    if not camera_ip:
        return jsonify({"success": False, "error": "ip が必要です"}), 400
    if not reg_dict or not isinstance(reg_dict, dict):
        return jsonify({"success": False, "error": "registers (辞書) が必要です"}), 400

    try:
        converted = {int(k): int(v) for k, v in reg_dict.items()}
    except ValueError:
        return jsonify({"success": False, "error": "レジスタのインデックスと値は整数である必要があります"}), 400

    logger.info(f"Bulk write registers: ip={camera_ip}, count={len(converted)}")
    result = occ.set_registers(camera_ip, converted)
    return jsonify(result)


# =========================================================================
# ROI 設定 API
# =========================================================================

@app.route("/api/roi/<int:roi_index>", methods=["GET"])
def api_get_roi(roi_index):
    """指定したROIインデックスの設定を読み込む。"""
    camera_ip = request.args.get("ip")
    if not camera_ip:
        return jsonify({"success": False, "error": "クエリパラメータ 'ip' が必要です"}), 400

    if not (0 <= roi_index <= 10):
        return jsonify({"success": False, "error": "roi_index は 0〜10 の範囲です"}), 400

    logger.info(f"Read ROI: ip={camera_ip}, index={roi_index}")
    result = occ.get_roi(camera_ip, roi_index)
    return jsonify(result)


@app.route("/api/rois", methods=["GET"])
def api_get_all_rois():
    """カメラの全ROI設定 (0〜10) を読み込む。"""
    camera_ip = request.args.get("ip")
    if not camera_ip:
        return jsonify({"success": False, "error": "クエリパラメータ 'ip' が必要です"}), 400

    logger.info(f"Read all ROIs: ip={camera_ip}")
    result = occ.get_all_rois(camera_ip)
    return jsonify(result)


@app.route("/api/roi", methods=["POST"])
def api_write_roi():
    """ROI設定を書き込む。"""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "JSONボディが必要です"}), 400

    required_fields = ["ip", "roi_index", "p1x", "p1y", "p2x", "p2y",
                       "output_width", "output_height", "frame_rate", "max_bitrate", "compression"]
    for field in required_fields:
        if field not in data:
            return jsonify({"success": False, "error": f"必須フィールド '{field}' がありません"}), 400

    try:
        camera_ip     = str(data["ip"]).strip()
        roi_index     = int(data["roi_index"])
        p1x           = int(data["p1x"])
        p1y           = int(data["p1y"])
        p2x           = int(data["p2x"])
        p2y           = int(data["p2y"])
        output_width  = int(data["output_width"])
        output_height = int(data["output_height"])
        frame_rate    = int(data["frame_rate"])
        max_bitrate   = int(data["max_bitrate"])
        compression   = int(data["compression"])
    except ValueError:
        return jsonify({"success": False, "error": "パラメータの数値変換に失敗しました"}), 400

    if not (0 <= roi_index <= 10):
        return jsonify({"success": False, "error": "roi_index は 0〜10 の範囲です"}), 400
    if not (0 <= compression <= 2):
        return jsonify({"success": False, "error": "compression は 0, 1, 2 のいずれかです"}), 400

    logger.info(f"Write ROI: ip={camera_ip}, index={roi_index}, res={output_width}x{output_height}@{frame_rate}fps")
    result = occ.set_roi(
        camera_ip, roi_index,
        p1x, p1y, p2x, p2y,
        output_width, output_height,
        frame_rate, max_bitrate, compression
    )
    return jsonify(result)


# =========================================================================
# カメラ動作制御 API (Start / Stop / Restart)
# =========================================================================

@app.route("/api/mode", methods=["POST"])
def api_set_mode():
    """カメラの動作モードを変更する。"""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "JSONボディが必要です"}), 400

    camera_ip = data.get("ip")
    mode = data.get("mode")

    if not camera_ip or not mode:
        return jsonify({"success": False, "error": "ip と mode が必要です"}), 400

    valid_modes = ["start", "stop", "restart"]
    if mode not in valid_modes:
        return jsonify({"success": False, "error": f"mode は {valid_modes} のいずれかです"}), 400

    logger.info(f"Set camera mode: ip={camera_ip}, mode={mode}")
    result = occ.set_camera_mode(camera_ip, mode)
    return jsonify(result)


@app.route("/api/camera/status", methods=["GET"])
def api_get_camera_status():
    """カメラの動作ステータスを取得する。"""
    camera_ip = request.args.get("ip")
    if not camera_ip:
        return jsonify({"success": False, "error": "クエリパラメータ 'ip' が必要です"}), 400

    logger.info(f"Get camera status: ip={camera_ip}")
    result = occ.get_camera_status(camera_ip)
    return jsonify(result)


# =========================================================================
# リアルタイム映像プレビュー API
# =========================================================================

@app.route("/api/video_feed")
def video_feed():
    """ブラウザ用 MJPEG リアルタイム映像ストリーム。"""
    return Response(
        streamer.streamer.generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/api/preview/start", methods=["POST"])
def api_preview_start():
    """RTP ストリームの受信を開始する。"""
    data = request.get_json() or {}
    port = int(data.get("port", 5004))
    codec = str(data.get("codec", "h264")).strip()
    logger.info(f"Start preview on port={port}, codec={codec}")
    res = streamer.streamer.start(port=port, codec=codec)
    return jsonify(res)


@app.route("/api/preview/stop", methods=["POST"])
def api_preview_stop():
    """RTP ストリームの受信を停止する。"""
    logger.info("Stop preview")
    res = streamer.streamer.stop()
    return jsonify(res)


@app.route("/api/preview/status", methods=["GET"])
def api_preview_status():
    """ストリーム受信状況を返す。"""
    status = streamer.streamer.get_status()
    return jsonify({"success": True, "status": status})


# =========================================================================
# エラーハンドラ
# =========================================================================

@app.errorhandler(404)
def not_found(e):
    return jsonify({"success": False, "error": "エンドポイントが見つかりません"}), 404


@app.errorhandler(500)
def server_error(e):
    logger.error(f"Internal server error: {e}")
    return jsonify({"success": False, "error": "サーバー内部エラー"}), 500


# =========================================================================
# エントリポイント (Waitress WSGI サーバー)
# =========================================================================

if __name__ == "__main__":
    # Windows コンソールの文字コード問題を回避
    if sys.stdout.encoding and sys.stdout.encoding.lower() in ('cp932', 'cp1252', 'ascii'):
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

    print("=" * 60)
    print("  OCC-Web - Orlaco Camera Configurator GUI")
    print("  Production WSGI Server (Waitress)")
    print("=" * 60)

    # occ.exe チェック
    occ_status = occ.check_occ_available()
    if occ_status["available"]:
        print(f"  [OK] occ.exe: {occ_status['path']}")
    else:
        print(f"  [!!] occ.exe not found: {occ_status['path']}")
        print("       backend/ フォルダに occ.exe を配置してください。")

    print(f"  Frontend: {FRONTEND_DIR}")
    print("")
    print("  ブラウザで開いてください: http://localhost:5000")
    print("=" * 60)

    # 本番用 WSGI サーバー Waitress で起動
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=5000, threads=8)
    except ImportError:
        logger.warning("Waitress not installed. Falling back to Flask dev server.")
        app.run(host="0.0.0.0", port=5000, debug=False)
