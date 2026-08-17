"""
streamer.py - Orlaco EMOS RTP 映像ストリーム受信＆MJPEG配信モジュール

カメラから送信される RTP (H.264 / MJPEG) UDP パケットを受信し、
Web ブラウザで表示可能な MJPEG ストリームに変換して配信する。
クライアント非接続時の自動アイドル・省電力機能およびイベント駆動配信を搭載。
"""

import os
import sys
import time
import atexit
import tempfile
import threading
import logging
from typing import Optional, Generator

logger = logging.getLogger(__name__)

# OpenCV のインポート試行（headless 対応）
try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    logger.warning("OpenCV is not installed. Video preview will use placeholder generator.")


class VideoStreamer:
    """
    RTP ストリームの受信とフレームキャッシュを管理するシングルトンクラス。
    Condition 変数を用いてイベント駆動型で低遅延 MJPEG 配信を行う。
    """
    def __init__(self):
        self.running = False
        self.current_port = 5004
        self.codec = "h264"  # "h264" or "mjpeg"
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        self.frame_condition = threading.Condition(self.lock)
        
        self.latest_frame: Optional[bytes] = None
        self.frame_count = 0
        self.fps = 0.0
        self.resolution = (0, 0)
        self.status_message = "停止中"
        self.last_frame_time = 0.0
        self.last_client_access = 0.0
        self.active_clients = 0
        self.is_connected = False
        self._sdp_path: Optional[str] = None

        # プロセス終了時のクリーンアップ登録
        atexit.register(self.cleanup)

    def cleanup(self):
        """プロセス終了時のリソースクリーンアップ。"""
        self.stop()
        if self._sdp_path and os.path.exists(self._sdp_path):
            try:
                os.remove(self._sdp_path)
            except Exception:
                pass
            self._sdp_path = None

    def _create_sdp_file(self, port: int, codec: str) -> str:
        """OpenCV / FFmpeg 用の SDP ファイルを作成する。"""
        temp_dir = tempfile.gettempdir()
        sdp_path = os.path.join(temp_dir, f"emos_stream_{port}.sdp")
        
        if codec.lower() in ("mjpeg", "jpeg"):
            sdp_content = (
                "v=0\n"
                "o=- 0 0 IN IP4 127.0.0.1\n"
                "s=Orlaco EMOS MJPEG\n"
                "c=IN IP4 0.0.0.0\n"
                "t=0 0\n"
                f"m=video {port} RTP/AVP 26\n"
                "a=rtpmap:26 JPEG/90000\n"
            )
        else:
            sdp_content = (
                "v=0\n"
                "o=- 0 0 IN IP4 127.0.0.1\n"
                "s=Orlaco EMOS H264\n"
                "c=IN IP4 0.0.0.0\n"
                "t=0 0\n"
                f"m=video {port} RTP/AVP 96\n"
                "a=rtpmap:96 H264/90000\n"
            )
            
        with open(sdp_path, "w", encoding="utf-8") as f:
            f.write(sdp_content)
            
        return sdp_path

    def start(self, port: int = 5004, codec: str = "h264") -> dict:
        """ストリーム受信を開始する。"""
        if self.running:
            if self.current_port == port and self.codec == codec:
                return {"success": True, "message": "既にストリーミング受信中です"}
            self.stop()

        self.current_port = port
        self.codec = codec
        self.running = True
        self.status_message = f"ポート {port} で受信待機中..."
        self.is_connected = False
        self.last_client_access = time.time()
        
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        
        logger.info(f"Started video streamer on port {port} (codec={codec})")
        return {"success": True, "port": port, "codec": codec}

    def stop(self) -> dict:
        """ストリーム受信を停止する。"""
        self.running = False
        with self.frame_condition:
            self.frame_condition.notify_all()

        if self.thread and self.thread.is_alive() and threading.current_thread() != self.thread:
            self.thread.join(timeout=1.0)
            
        self.is_connected = False
        self.status_message = "停止しました"
        
        if self._sdp_path and os.path.exists(self._sdp_path):
            try:
                os.remove(self._sdp_path)
            except Exception:
                pass
            self._sdp_path = None
            
        logger.info("Stopped video streamer")
        return {"success": True}

    def get_status(self) -> dict:
        """現在のストリーミングステータスを返す。"""
        with self.lock:
            connected = self.is_connected and (time.time() - self.last_frame_time < 3.0)
            return {
                "running": self.running,
                "connected": connected,
                "port": self.current_port,
                "codec": self.codec,
                "fps": round(self.fps, 1),
                "resolution": f"{self.resolution[0]}x{self.resolution[1]}" if connected else "-",
                "frame_count": self.frame_count,
                "status_message": self.status_message,
                "active_clients": self.active_clients,
                "opencv_available": OPENCV_AVAILABLE,
            }

    def _generate_placeholder_frame(self, text: str, subtext: str = "") -> bytes:
        """待機中やエラー時に表示するグラフィックフレームを生成。"""
        if not OPENCV_AVAILABLE:
            return b""
            
        w, h = 640, 360
        img = np.zeros((h, w, 3), dtype=np.uint8)
        img[:] = (23, 26, 34)  # #171a22 ダークブルーグレー

        # グリッド線描画
        for y in range(0, h, 40):
            cv2.line(img, (0, y), (w, y), (30, 34, 48), 1)
        for x in range(0, w, 40):
            cv2.line(img, (x, 0), (x, h), (30, 34, 48), 1)

        # カメラアイコン
        cv2.rectangle(img, (270, 110), (370, 190), (59, 130, 246), 2)
        cv2.circle(img, (320, 150), 22, (59, 130, 246), 2)
        cv2.fillPoly(img, [np.array([[370, 130], [395, 115], [395, 185], [370, 170]])], (59, 130, 246))

        # テキスト描画
        font = cv2.FONT_HERSHEY_SIMPLEX
        text_size = cv2.getTextSize(text, font, 0.65, 2)[0]
        text_x = (w - text_size[0]) // 2
        cv2.putText(img, text, (text_x, 240), font, 0.65, (230, 235, 245), 2, cv2.LINE_AA)

        if subtext:
            sub_size = cv2.getTextSize(subtext, font, 0.45, 1)[0]
            sub_x = (w - sub_size[0]) // 2
            cv2.putText(img, subtext, (sub_x, 275), font, 0.45, (139, 144, 160), 1, cv2.LINE_AA)

        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(img, f"Port: {self.current_port} UDP | {now_str}", (15, 340), font, 0.38, (85, 89, 104), 1, cv2.LINE_AA)

        _, jpeg = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        return jpeg.tobytes()

    def _capture_loop(self):
        """バックグラウンドスレッドで RTP ストリームを受信・デコードするループ。"""
        if not OPENCV_AVAILABLE:
            while self.running:
                frame = self._generate_placeholder_frame(
                    "OpenCV がインストールされていません",
                    "pip install opencv-python-headless を実行してください"
                )
                with self.frame_condition:
                    self.latest_frame = frame
                    self.frame_condition.notify_all()
                time.sleep(0.5)
            return

        self._sdp_path = self._create_sdp_file(self.current_port, self.codec)
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "protocol_whitelist;file,rtp,udp,crypto,data|timeout;2000000|buffer_size;1024000"

        cap = None
        fps_timer = time.time()
        fps_frames = 0

        while self.running:
            try:
                # クライアントが10秒以上アクセスしていない場合はアイドルスリープ（CPU消費抑制）
                if self.active_clients == 0 and (time.time() - self.last_client_access > 10.0):
                    if cap is not None:
                        cap.release()
                        cap = None
                    time.sleep(0.5)
                    continue

                if cap is None or not cap.isOpened():
                    self.status_message = f"UDP ポート {self.current_port} からのパケット受信待機中..."
                    self.is_connected = False
                    
                    with self.frame_condition:
                        self.latest_frame = self._generate_placeholder_frame(
                            "カメラからの映像信号を受信待機中...",
                            f"カメラ側設定: RTP 送信先 IP=(このPCのIP), ポート={self.current_port}"
                        )
                        self.frame_condition.notify_all()
                    
                    cap = cv2.VideoCapture(self._sdp_path, cv2.CAP_FFMPEG)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    time.sleep(0.5)
                    continue

                ret, frame = cap.read()
                if not ret or frame is None:
                    time.sleep(0.02)
                    if time.time() - self.last_frame_time > 3.0:
                        self.is_connected = False
                        self.status_message = "映像信号が途絶えました（再接続試行中...）"
                        with self.frame_condition:
                            self.latest_frame = self._generate_placeholder_frame(
                                "映像信号が途絶えました",
                                "カメラの電源、IP設定、LANケーブル接続を確認してください"
                            )
                            self.frame_condition.notify_all()
                        cap.release()
                        cap = None
                    continue

                now = time.time()
                self.last_frame_time = now
                self.is_connected = True
                self.frame_count += 1
                fps_frames += 1

                if now - fps_timer >= 1.0:
                    self.fps = fps_frames / (now - fps_timer)
                    fps_frames = 0
                    fps_timer = now

                h, w = frame.shape[:2]
                self.resolution = (w, h)
                self.status_message = f"受信中 ({w}x{h} @ {self.fps:.1f} fps)"

                _, jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                jpeg_bytes = jpeg.tobytes()

                with self.frame_condition:
                    self.latest_frame = jpeg_bytes
                    self.frame_condition.notify_all()

                time.sleep(0.002)

            except Exception as e:
                logger.error(f"Stream capture exception: {e}")
                self.status_message = f"エラー: {str(e)}"
                self.is_connected = False
                if cap:
                    cap.release()
                    cap = None
                time.sleep(1.0)

        if cap:
            cap.release()

    def generate_frames(self) -> Generator[bytes, None, None]:
        """Flask の Response 用 MJPEG ジェネレータ関数 (イベント駆動)。"""
        self.active_clients += 1
        self.last_client_access = time.time()

        if self.latest_frame is None:
            self.latest_frame = self._generate_placeholder_frame("映像プレビュー停止中", "「プレビュー開始」ボタンを押してください")

        try:
            last_sent_frame = None
            while True:
                self.last_client_access = time.time()
                with self.frame_condition:
                    # 新しいフレームが来るか、最大100ms待機
                    self.frame_condition.wait(timeout=0.1)
                    frame = self.latest_frame

                if frame and frame is not last_sent_frame:
                    last_sent_frame = frame
                    yield (b"--frame\r\n"
                           b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
        finally:
            self.active_clients = max(0, self.active_clients - 1)


# グローバルな Streamer インスタンス
streamer = VideoStreamer()
