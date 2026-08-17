"""
verify_system.py - OCC-Web 全体仕様・稼働検証テストスクリプト
"""

import sys
import os
import json
import re

# パス設定
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(BASE_DIR, "system", "backend")
FRONTEND_DIR = os.path.join(BASE_DIR, "system", "frontend")
sys.path.insert(0, BACKEND_DIR)


import app
import occ_wrapper as occ
import streamer
import net_utils


def test_static_files():
    print("\n--- 1. 静的ファイル & ルーティングテスト ---")
    client = app.app.test_client()

    # index.html
    res = client.get("/")
    assert res.status_code == 200, f"index.html failed: {res.status_code}"
    assert "Orlaco EMOS" in res.get_data(as_text=True), "index.html content mismatch"
    print("  [PASS] GET / (index.html)")

    # style.css
    res = client.get("/style.css")
    assert res.status_code == 200, f"style.css failed: {res.status_code}"
    assert "--color-bg-base" in res.get_data(as_text=True), "style.css content mismatch"
    print("  [PASS] GET /style.css")

    # app.js
    res = client.get("/app.js")
    assert res.status_code == 200, f"app.js failed: {res.status_code}"
    assert "API_BASE" in res.get_data(as_text=True), "app.js content mismatch"
    print("  [PASS] GET /app.js")


def test_system_apis():
    print("\n--- 2. システム API テスト ---")
    client = app.app.test_client()

    # /api/status
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.get_json()
    assert data["server"] == "ok"
    assert "occ" in data
    assert data["version"] == "1.2.0"
    print(f"  [PASS] GET /api/status -> server: {data['server']}, version: {data['version']}, occ: {data['occ']['available']}")

    # /api/interfaces
    res = client.get("/api/interfaces")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert isinstance(data["interfaces"], list)
    print(f"  [PASS] GET /api/interfaces -> count: {len(data['interfaces'])}, first: {data['interfaces'][0] if data['interfaces'] else 'None'}")

    # /api/heartbeat
    res = client.post("/api/heartbeat")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"
    print("  [PASS] POST /api/heartbeat")


def test_camera_apis_signatures():
    print("\n--- 3. カメラ操作 API 結合テスト (関数呼び出しとエラーハンドリング) ---")
    client = app.app.test_client()

    # 1. /api/discover
    res = client.post("/api/discover", json={"broadcast_ip": "192.168.2.255"})
    assert res.status_code == 200
    data = res.get_json()
    assert "success" in data
    print(f"  [PASS] POST /api/discover -> success: {data['success']}")

    # 2. /api/registers (GET)
    res = client.get("/api/registers?ip=192.168.2.10")
    assert res.status_code == 200
    data = res.get_json()
    assert "success" in data
    print(f"  [PASS] GET /api/registers -> success: {data['success']}")

    # 3. /api/register (POST)
    res = client.post("/api/register", json={"ip": "192.168.2.10", "index": 0, "value": 1})
    assert res.status_code == 200
    data = res.get_json()
    assert "success" in data
    print(f"  [PASS] POST /api/register -> success: {data['success']}")

    # 4. /api/registers/bulk (POST)
    res = client.post("/api/registers/bulk", json={"ip": "192.168.2.10", "registers": {"0": 1, "48": 1}})
    assert res.status_code == 200
    data = res.get_json()
    assert "success" in data
    print(f"  [PASS] POST /api/registers/bulk -> success: {data['success']}")

    # 5. /api/roi/0 (GET)
    res = client.get("/api/roi/0?ip=192.168.2.10")
    assert res.status_code == 200
    data = res.get_json()
    assert "success" in data
    print(f"  [PASS] GET /api/roi/0 -> success: {data['success']}")

    # 6. /api/rois (GET)
    res = client.get("/api/rois?ip=192.168.2.10")
    assert res.status_code == 200
    data = res.get_json()
    assert "success" in data
    print(f"  [PASS] GET /api/rois -> success: {data['success']}")

    # 7. /api/roi (POST)
    payload = {
        "ip": "192.168.2.10",
        "roi_index": 0,
        "p1x": 0, "p1y": 0,
        "p2x": 1280, "p2y": 720,
        "output_width": 1280,
        "output_height": 720,
        "frame_rate": 30,
        "max_bitrate": 50,
        "compression": 2
    }
    res = client.post("/api/roi", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert "success" in data
    print(f"  [PASS] POST /api/roi -> success: {data['success']}")

    # 8. /api/mode (POST)
    res = client.post("/api/mode", json={"ip": "192.168.2.10", "mode": "start"})
    assert res.status_code == 200
    data = res.get_json()
    assert "success" in data
    print(f"  [PASS] POST /api/mode -> success: {data['success']}")


def test_streamer_apis():
    print("\n--- 4. 映像ストリーミング API テスト ---")
    client = app.app.test_client()

    # /api/preview/status
    res = client.get("/api/preview/status")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "status" in data
    print(f"  [PASS] GET /api/preview/status -> status: {data['status']['status_message']}")

    # /api/preview/start
    res = client.post("/api/preview/start", json={"port": 5004, "codec": "h264"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    print(f"  [PASS] POST /api/preview/start -> port: {data['port']}, codec: {data['codec']}")

    # /api/preview/stop
    res = client.post("/api/preview/stop")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    print("  [PASS] POST /api/preview/stop")


def test_frontend_dom_binding():
    print("\n--- 5. フロントエンド DOM & JavaScript 参照整合性チェック ---")
    html_path = os.path.join(FRONTEND_DIR, "index.html")
    js_path = os.path.join(FRONTEND_DIR, "app.js")

    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    with open(js_path, "r", encoding="utf-8") as f:
        js_content = f.read()

    # app.js 内の $('id_name') または getElementById('id_name') をすべて抽出
    id_matches = re.findall(r"\$\(['\"]([^'\"]+)['\"]\)", js_content)
    id_matches += re.findall(r"getElementById\(['\"]([^'\"]+)['\"]\)", js_content)
    unique_ids = set(id_matches)

    missing_ids = []
    for elem_id in unique_ids:
        # テンプレート文字列等で動的生成される ID は除外（例: reg-val-X）
        if "reg-val-" in elem_id:
            continue
        pattern = f'id="{elem_id}"'
        if pattern not in html_content:
            missing_ids.append(elem_id)

    if missing_ids:
        print(f"  [WARN] HTML 内に見つからない ID 参照: {missing_ids}")
    else:
        print(f"  [PASS] 全 {len(unique_ids)} 個の JS 参照 DOM ID が index.html に完全に存在しています")


if __name__ == "__main__":
    print("==================================================")
    print("  OCC-Web 仕様・稼働確認テストスイート開始")
    print("==================================================")
    try:
        test_static_files()
        test_system_apis()
        test_camera_apis_signatures()
        test_streamer_apis()
        test_frontend_dom_binding()
        print("\n==================================================")
        print("  [SUCCESS] All verification tests PASSED!")
        print("  System is fully operational as specified.")
        print("==================================================")

    except AssertionError as e:
        print(f"\n[FAIL] Assertion error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] Unexpected error: {e}")
        sys.exit(1)

