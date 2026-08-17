"""
net_utils.py - ネットワークインターフェース情報取得ユーティリティ

Windows 上のアダプター一覧（有線LAN、Wi-Fi等）から、
IPアドレス、サブネットマスク、ブロードキャストアドレスを抽出する。
"""

import socket
import subprocess
import re
import ipaddress
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


def get_network_interfaces() -> List[Dict[str, str]]:
    """
    ローカル PC のネットワークインターフェース（IPv4）一覧を取得する。

    Returns:
        List of dict: [
            {
                "name": "イーサネット",
                "ip": "192.168.2.100",
                "mask": "255.255.255.0",
                "broadcast": "192.168.2.255"
            }, ...
        ]
    """
    interfaces = []
    
    # 1. ipconfig /all の出力をパース (Windows 専用の高信頼性取得)
    try:
        proc = subprocess.run(
            ["ipconfig", "/all"],
            capture_output=True,
            text=True,
            encoding="cp932",
            errors="ignore",
            timeout=3
        )
        
        current_adapter = None
        current_ip = None
        current_mask = None
        
        for line in proc.stdout.splitlines():
            line_str = line.strip()
            
            # アダプター見出し (例: "イーサネット アダプター イーサネット:" or "Ethernet adapter Ethernet:")
            adapter_match = re.match(r"^(.+?アダプター|.+?adapter)\s+(.+?):$", line_str, re.IGNORECASE)
            if adapter_match:
                # 前のアダプターを保存
                if current_adapter and current_ip:
                    bcast = _calc_broadcast(current_ip, current_mask or "255.255.255.0")
                    interfaces.append({
                        "name": current_adapter,
                        "ip": current_ip,
                        "mask": current_mask or "255.255.255.0",
                        "broadcast": bcast
                    })
                current_adapter = adapter_match.group(2).strip()
                current_ip = None
                current_mask = None
                continue
                
            # IPv4 アドレス
            ip_match = re.search(r"IPv4\s*(アドレス|Address)[.\s]*:\s*([0-9.]+)", line_str, re.IGNORECASE)
            if ip_match:
                ip_val = ip_match.group(2).replace("(優先)", "").replace("(Preferred)", "").strip()
                if not ip_val.startswith("127.") and not ip_val.startswith("169.254."):
                    current_ip = ip_val
                    
            # サブネットマスク
            mask_match = re.search(r"(サブネット\s*マスク|Subnet\s*Mask)[.\s]*:\s*([0-9.]+)", line_str, re.IGNORECASE)
            if mask_match:
                current_mask = mask_match.group(2).strip()
                
        # 最後のブロックを保存
        if current_adapter and current_ip:
            bcast = _calc_broadcast(current_ip, current_mask or "255.255.255.0")
            interfaces.append({
                "name": current_adapter,
                "ip": current_ip,
                "mask": current_mask or "255.255.255.0",
                "broadcast": bcast
            })
            
    except Exception as e:
        logger.warning(f"Failed to parse ipconfig: {e}")

    # フォールバック: socket.gethostbyname_ex
    if not interfaces:
        try:
            hostname = socket.gethostname()
            _, _, ips = socket.gethostbyname_ex(hostname)
            for i, ip in enumerate(ips):
                if not ip.startswith("127.") and not ip.startswith("169.254."):
                    bcast = _calc_broadcast(ip, "255.255.255.0")
                    interfaces.append({
                        "name": f"ネットワーク アダプター {i+1}",
                        "ip": ip,
                        "mask": "255.255.255.0",
                        "broadcast": bcast
                    })
        except Exception:
            pass

    return interfaces


def _calc_broadcast(ip_str: str, mask_str: str) -> str:
    """IP アドレスとサブネットマスクからブロードキャスト IP を計算する。"""
    try:
        network = ipaddress.IPv4Network(f"{ip_str}/{mask_str}", strict=False)
        return str(network.broadcast_address)
    except Exception:
        pass

    # フォールバック (Cクラス想定)
    parts = ip_str.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.{parts[2]}.255"
    return "255.255.255.255"
