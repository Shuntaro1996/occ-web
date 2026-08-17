"""
occ_wrapper.py - occ.exe のサブプロセス呼び出しラッパー

OCC (Orlaco Camera Configurator) CLI ツールをサブプロセスとして呼び出し、
出力を解析して Python オブジェクトとして返す。
"""

import subprocess
import re
import os
import sys
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# occ.exe のパス（このファイルと同ディレクトリに配置）
OCC_EXECUTABLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "occ.exe")

# Windowsでない場合はLinuxバイナリを探す
if sys.platform != "win32":
    OCC_EXECUTABLE_LINUX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "occ")
    if os.path.exists(OCC_EXECUTABLE_LINUX):
        OCC_EXECUTABLE = OCC_EXECUTABLE_LINUX

DEFAULT_TIMEOUT = 10  # seconds


def _run_occ(args: list[str], timeout: int = DEFAULT_TIMEOUT) -> dict:
    """
    occ.exe をサブプロセスとして実行し、stdout/stderr を返す。
    """
    if not os.path.exists(OCC_EXECUTABLE):
        return {
            "success": False,
            "error": f"occ.exe が見つかりません: {OCC_EXECUTABLE}",
            "stdout": "",
            "stderr": "",
        }

    cmd = [OCC_EXECUTABLE] + args
    logger.debug(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"タイムアウト ({timeout}秒)",
            "stdout": "",
            "stderr": "",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "stdout": "",
            "stderr": "",
        }


def discover_cameras(broadcast_ip: str) -> dict:
    """
    ネットワーク上のOrlacoカメラを発見する。

    Args:
        broadcast_ip: ブロードキャストIPアドレス (例: 192.168.2.255)

    Returns:
        {
            "success": bool,
            "cameras": [
                {"index": 0, "ip": "192.168.2.10", "type": "01",
                 "service_id": "433f", "instance_id": "000a", "version": "1.0"}
            ],
            "error": str (on failure)
        }
    """
    result = _run_occ(["-d", broadcast_ip], timeout=15)

    if not result["success"] and "error" in result:
        return {"success": False, "cameras": [], "error": result["error"]}

    cameras = []
    stdout = result["stdout"] + result["stderr"]

    # 出力形式: "0: IP=192.168.2.10 Type=01 ServiceID=433f InstanceID=000a V=1.0"
    pattern = re.compile(
        r"(\d+):\s+IP=([\d.]+)\s+Type=(\w+)\s+ServiceID=(\w+)\s+InstanceID=(\w+)\s+V=([\d.]+)"
    )

    for match in pattern.finditer(stdout):
        cameras.append({
            "index": int(match.group(1)),
            "ip": match.group(2),
            "type": match.group(3),
            "service_id": match.group(4),
            "instance_id": match.group(5),
            "version": match.group(6),
        })

    # 見つからず、末尾が255でない個別IPが渡されていた場合はブロードキャストでもフォールバック検索
    if not cameras and "." in broadcast_ip and not broadcast_ip.endswith(".255"):
        ip_parts = broadcast_ip.split(".")
        if len(ip_parts) == 4:
            bcast = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.255"
            fallback_res = _run_occ(["-d", bcast], timeout=10)
            fallback_out = fallback_res["stdout"] + fallback_res["stderr"]
            for match in pattern.finditer(fallback_out):
                cameras.append({
                    "index": int(match.group(1)),
                    "ip": match.group(2),
                    "type": match.group(3),
                    "service_id": match.group(4),
                    "instance_id": match.group(5),
                    "version": match.group(6),
                })
            stdout += "\n" + fallback_out

    # "Found N devices" から台数を確認
    found_match = re.search(r"Found (\d+) devices?", stdout, re.IGNORECASE)
    num_found = int(found_match.group(1)) if found_match else len(cameras)

    return {
        "success": True,
        "cameras": cameras,
        "count": num_found,
        "raw_output": stdout,
    }


def get_registers(camera_ip: str, indices: Optional[str] = None) -> dict:
    """
    カメラのレジスタを読み込む。

    Args:
        camera_ip: カメラのIPアドレス
        indices: レジスタインデックス指定 (例: "0,1,2" または ":" で全て)

    Returns:
        {
            "success": bool,
            "registers": [
                {"index": 0, "address": "0xb00c", "hex": "0x01",
                 "decimal": 1, "ascii": "", "name": "LED Mode"}
            ]
        }
    """
    idx = indices if indices else ":"
    result = _run_occ(["-R", idx, "-i", camera_ip])

    if not result["success"] and "error" in result:
        return {"success": False, "registers": [], "error": result["error"]}

    registers = []
    stdout = result["stdout"] + result["stderr"]

    # 出力形式: "00      0xb00c  0x01      1             LED Mode"
    # ヘッダー行をスキップして各行をパース
    pattern = re.compile(
        r"^(\d+)\s+(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)\s+(\d+)\s+(.*?)\s{2,}(.+)$",
        re.MULTILINE,
    )

    for match in pattern.finditer(stdout):
        ascii_val = match.group(5).strip()
        name = match.group(6).strip()
        registers.append({
            "index": int(match.group(1)),
            "address": match.group(2),
            "hex": match.group(3),
            "decimal": int(match.group(4)),
            "ascii": ascii_val,
            "name": name,
        })

    # パターンマッチに失敗した場合、別パターンを試みる
    if not registers:
        pattern2 = re.compile(
            r"^(\d{2})\s+(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)\s+(\d+)",
            re.MULTILINE,
        )
        for match in pattern2.finditer(stdout):
            registers.append({
                "index": int(match.group(1)),
                "address": match.group(2),
                "hex": match.group(3),
                "decimal": int(match.group(4)),
                "ascii": "",
                "name": _get_register_name(match.group(2)),
            })

    return {
        "success": True,
        "registers": registers,
        "count": len(registers),
        "raw_output": stdout,
    }


def set_register(camera_ip: str, index: int, value: int) -> dict:
    """
    カメラのレジスタを書き込む。

    Args:
        camera_ip: カメラのIPアドレス
        index: レジスタインデックス
        value: 書き込む値（10進数）

    Returns:
        {"success": bool, "error": str (on failure)}
    """
    result = _run_occ(["-W", f"{index}={value}", "-i", camera_ip])
    stdout = result["stdout"] + result["stderr"]

    if "error" in result and not result["success"]:
        return {"success": False, "error": result["error"], "raw_output": stdout}

    return {"success": True, "raw_output": stdout}


def set_registers(camera_ip: str, register_map: dict[int, int]) -> dict:
    """
    複数のレジスタをまとめて書き込む。

    Args:
        camera_ip: カメラのIPアドレス
        register_map: {index: value, ...}

    Returns:
        {"success": bool, "results": [...]}
    """
    results = []
    all_success = True
    for index, value in register_map.items():
        res = set_register(camera_ip, index, value)
        results.append({"index": index, "value": value, **res})
        if not res["success"]:
            all_success = False
    return {"success": all_success, "results": results}


def get_roi(camera_ip: str, roi_index: int) -> dict:
    """
    ROI（関心領域）設定を読み込む。

    Args:
        camera_ip: カメラのIPアドレス
        roi_index: ROIインデックス (0-10)

    Returns:
        {
            "success": bool,
            "roi": {
                "index": 0,
                "p1x": 0, "p1y": 0, "p2x": 1280, "p2y": 720,
                "output_width": 1280, "output_height": 720,
                "frame_rate": 30,
                "max_bitrate": 50,
                "compression": "H.264"
            }
        }
    """
    result = _run_occ(["-g", str(roi_index), "-i", camera_ip])
    stdout = result["stdout"] + result["stderr"]

    if "error" in result and not result["success"]:
        return {"success": False, "roi": None, "error": result["error"]}

    roi = _parse_roi_output(stdout, roi_index)
    return {"success": True, "roi": roi, "raw_output": stdout}


def get_all_rois(camera_ip: str) -> dict:
    """全ROI設定を読み込む。"""
    result = _run_occ(["-G", ":", "-i", camera_ip])
    stdout = result["stdout"] + result["stderr"]

    if "error" in result and not result["success"]:
        return {"success": False, "rois": [], "error": result["error"]}

    rois = []
    for i in range(11):
        roi = _parse_roi_output(stdout, i)
        if roi:
            rois.append(roi)

    return {"success": True, "rois": rois, "raw_output": stdout}


def set_roi(
    camera_ip: str,
    roi_index: int,
    p1x: int,
    p1y: int,
    p2x: int,
    p2y: int,
    output_width: int,
    output_height: int,
    frame_rate: int,
    max_bitrate: int,
    compression: int,  # 0=None, 1=JPEG, 2=H.264
) -> dict:
    """
    ROI設定を書き込む。

    compression: 0=None, 1=JPEG, 2=H.264
    """
    args = [
        "-g",
        f"{roi_index},{p1x},{p1y},{p2x},{p2y},{output_width},{output_height},{frame_rate},{max_bitrate},{compression}",
        "-i", camera_ip,
    ]
    result = _run_occ(args)
    stdout = result["stdout"] + result["stderr"]

    if "error" in result and not result["success"]:
        return {"success": False, "error": result["error"], "raw_output": stdout}

    return {"success": True, "raw_output": stdout}


def set_camera_mode(camera_ip: str, mode: str) -> dict:
    """
    カメラモードを設定する。

    Args:
        camera_ip: カメラのIPアドレス
        mode: "start" | "stop" | "restart"
    """
    if mode not in ("start", "stop", "restart"):
        return {"success": False, "error": f"無効なモード: {mode}"}

    result = _run_occ(["-m", mode, "-i", camera_ip])
    stdout = result["stdout"] + result["stderr"]

    if "error" in result and not result["success"]:
        return {"success": False, "error": result["error"], "raw_output": stdout}

    return {"success": True, "raw_output": stdout}


def get_camera_status(camera_ip: str) -> dict:
    """カメラステータスを取得する。"""
    result = _run_occ(["-s", "-i", camera_ip])
    stdout = result["stdout"] + result["stderr"]
    return {"success": True, "raw_output": stdout}


def check_occ_available() -> dict:
    """occ.exe が利用可能かチェックする。"""
    exists = os.path.exists(OCC_EXECUTABLE)
    return {
        "available": exists,
        "path": OCC_EXECUTABLE,
        "platform": sys.platform,
    }


# --- 内部ヘルパー関数 ---

def _parse_roi_output(text: str, roi_index: int) -> Optional[dict]:
    """ROI 出力テキストをパースしてdict に変換する。"""
    # ROIセクションを探す
    section_pattern = re.compile(
        rf"ROI\s+{roi_index}[:\s]+(.*?)(?=ROI\s+\d+|$)",
        re.DOTALL | re.IGNORECASE,
    )
    section_match = section_pattern.search(text)

    if not section_match:
        return None

    section = section_match.group(1)

    def find_value(pattern, default=0):
        m = re.search(pattern, section, re.IGNORECASE)
        return int(m.group(1)) if m else default

    return {
        "index": roi_index,
        "p1x": find_value(r"P1X\s*[=:]\s*(\d+)"),
        "p1y": find_value(r"P1Y\s*[=:]\s*(\d+)"),
        "p2x": find_value(r"P2X\s*[=:]\s*(\d+)"),
        "p2y": find_value(r"P2Y\s*[=:]\s*(\d+)"),
        "output_width": find_value(r"Output Width\s*[=:]\s*(\d+)", 1280),
        "output_height": find_value(r"Output Height\s*[=:]\s*(\d+)", 720),
        "frame_rate": find_value(r"Frame Rate\s*[=:]\s*(\d+)", 30),
        "max_bitrate": find_value(r"Max Bitrate\s*[=:]\s*(\d+)", 50),
        "compression": find_value(r"Compression\s*[=:]\s*(\d+)", 2),
    }


# レジスタアドレス -> 名前マッピング
_REGISTER_NAMES = {
    "0xb00c": "LED Mode",
    "0xb041": "Stream Protocol",
    "0xb042": "Static IP Address 0",
    "0xb043": "Static IP Address 1",
    "0xb044": "Static IP Address 2",
    "0xb045": "Static IP Address 3",
    "0xb046": "Static Network Mask 0",
    "0xb047": "Static Network Mask 1",
    "0xb048": "Static Network Mask 2",
    "0xb049": "Static Network Mask 3",
    "0xb04a": "MAC Address 0",
    "0xb04b": "MAC Address 1",
    "0xb04c": "MAC Address 2",
    "0xb04d": "MAC Address 3",
    "0xb04e": "MAC Address 4",
    "0xb04f": "MAC Address 5",
    "0xb055": "VLAN ID 0",
    "0xb056": "VLAN ID 1",
    "0xb05f": "RTP Stream Dest IP 0",
    "0xb060": "RTP Stream Dest IP 1",
    "0xb061": "RTP Stream Dest IP 2",
    "0xb062": "RTP Stream Dest IP 3",
    "0xb063": "RTP Stream Dest MAC 0",
    "0xb064": "RTP Stream Dest MAC 1",
    "0xb065": "RTP Stream Dest MAC 2",
    "0xb066": "RTP Stream Dest MAC 3",
    "0xb067": "RTP Stream Dest MAC 4",
    "0xb068": "RTP Stream Dest MAC 5",
    "0xb069": "RTP Stream Dest Port 0",
    "0xb06a": "RTP Stream Dest Port 1",
    "0xb06b": "Selected ROI",
    "0xb06c": "No Stream at Boot",
    "0xb06d": "UDP Communication Port 0",
    "0xb06e": "UDP Communication Port 1",
    "0xb06f": "RTP Stream Source Port 0",
    "0xb070": "RTP Stream Source Port 1",
    "0xb071": "HDR",
    "0xb072": "Overlay",
    "0xb073": "DHCP",
    "0xb078": "Wait for MAC",
    "0xb079": "Wait for PTP Sync",
}


def _get_register_name(address: str) -> str:
    return _REGISTER_NAMES.get(address.lower(), f"Unknown ({address})")


# エイリアス関数（呼び出し互換性確保）
read_registers = get_registers
write_register = set_register
write_registers_bulk = set_registers
read_roi = get_roi
read_all_rois = get_all_rois
write_roi = set_roi

