# 🎥 OCC-Web — Orlaco EMOS Camera Configurator GUI & Dashboard

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Dashboard-Streamlit-FF4B4B.svg?logo=streamlit)](https://streamlit.io/)
[![Flask](https://img.shields.io/badge/Framework-Flask%20%2F%20Waitress-black.svg?logo=flask)](https://flask.palletsprojects.com/)
[![OpenCV](https://img.shields.io/badge/Video-OpenCV-5C3EE8.svg?logo=opencv)](https://opencv.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%2F%20Cloud-0078D6.svg?logo=windows)](https://www.microsoft.com/windows)

**産業用 [Orlaco EMOS IP カメラ](https://github.com/Codemonkey1973/OCC) の設定変更およびリアルタイム映像プレビューを、Webブラウザから直感的に行える高信頼性ポータブルGUI & Streamlit ダッシュボードシステムです。**

---

### 🚀 Live Demo (オンライン即時起動)

インストール不要でブラウザから直接ダッシュボードを起動・体験できます：

👉 **Live Demo: [https://net-ops-toolkit.streamlit.app](https://net-ops-toolkit.streamlit.app/)**

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://net-ops-toolkit.streamlit.app/)

---


## 🌟 主な機能 (Key Features)

| 機能 | 詳細 |
| :--- | :--- |
| 📊 **2つのUIモード** | **① Flask + Vanilla JS 本番用GUI** (`start.bat`) / **② Streamlit インタラクティブダッシュボード** (`start_streamlit.bat`) |
| 🎮 **デモ / シミュレーション搭載** | 実機カメラがない環境や [Streamlit Community Cloud](https://share.streamlit.io/) でも、仮想テスト映像・OSD・レジスタ変更を完全体験・提示可能。 |
| 🎥 **リアルタイム映像プレビュー & 産業用 OSD** | カメラからの RTP ストリーム（H.264 / MJPEG）を超低遅延表示。ファインダー風レティクル枠線、LIVEバッジ、タイムコード、全画面・静止画キャプチャ対応。 |
| 💓 **省電力ハートビート & クリーンアップ** | プレビュー非表示時はストリームデコードを自動停止し、ブラウザ終了時は一時ファイル削除と安全な Graceful Shutdown を実行。 |
| 🌐 **マルチNIC自動検出 & ヘッダーバッジ** | 有線LANとWi-Fiが混在する現場PCでも、カメラ接続用のLANアダプターを選択するだけでIP・ブロードキャストIPを自動補完。 |
| 🛡️ **文鎮化防止ガード** | PCのIPと異なるサブネットへの変更時に警告ダイアログを表示し、誤設定による通信不能を未然に防止。 |
| 💾 **設定プリセット & JSON入出力** | ブラウザ内保存に加え、設定一式を `.json` ファイルとしてエクスポート/インポート可能。チーム内共有やバックアップを支援。 |
| 🔍 **カメラ自動発見** | ブロードキャストスキャンでネットワーク上のカメラを自動検出。 |
| ⚙️ **映像設定 (ROI)** | 解像度・FPS・コーデック・ビットレート・センサー切り取り範囲（ROI）をフォームとスライダーで調整。 |
| 🔄 **設定反映 & 自動再起動催促** | 設定送信後、自動的に再起動を催促し、ワンクリックで再起動コマンドを実行。 |
| 📋 **詳細レジスタ編集** | 全レジスタ一覧の確認・検索および1バイト単位の直接書き込み。 |
| 🚀 **完全ポータブル仕様** | フォルダごと別PCにコピーしてバッチをダブルクリックするだけで、仮想環境作成からブラウザ起動まで自動完了。 |

---

## 🏗️ システム構成 (Architecture)

```mermaid
graph TD
    subgraph UI Options
        User1([ブラウザ - Flask Web GUI]) <-->|Port 5000| App[Flask / Waitress WSGI Server]
        User2([ブラウザ - Streamlit Dashboard]) <-->|Port 8501| StreamlitApp[streamlit_app.py]
    end
    
    App <-->|Subprocess Control| OCC[occ.exe Backend Driver]
    StreamlitApp <-->|Subprocess / Wrapper| OCC
    
    App <-->|RTP Stream / OpenCV| Camera[Orlaco EMOS IP Camera]
    StreamlitApp <-->|RTP Stream or Sim Frame| Camera
```

---

## 📁 ディレクトリ構成 (Directory Structure)

```
occ-web/
├── start.bat                   # Flask 版 Web GUI 起動バッチ (Port 5000)
├── start_streamlit.bat         # Streamlit 版 ダッシュボード起動バッチ (Port 8501)
├── streamlit_app.py            # Streamlit アプリケーション本体 (Cloud対応)
├── requirements.txt            # Streamlit / 依存ライブラリ一覧
├── LICENSE                     # MIT License
├── THIRD_PARTY_LICENSES.md     # オープンソース使用表示
├── README.md                   # 本ドキュメント
└── system/                     # システム内部フォルダ
    ├── README.md               # 詳細解説書
    ├── STRUCTURE_AND_CUSTOMIZE.md # システム構成・カスタマイズ解説
    ├── backend/                # Python バックエンド (Flask + Waitress + OpenCV)
    │   ├── app.py              # API サーバー & WSGI エントリポイント
    │   ├── occ_wrapper.py      # occ.exe ラッパー
    │   ├── streamer.py         # RTP 映像受信 & 配信（省電力ハートビート付）
    │   ├── net_utils.py        # NIC 検出 & IP 計算ユーティリティ
    │   └── occ.exe             # 通信バイナリ ※別途ダウンロード必要 (GPL-3.0)
    └── frontend/               # Web フロントエンド

        ├── index.html          # HTML 構造
        ├── style.css           # UI スタイル
        └── app.js              # フロントエンド制御ロジック
```

---

## 🚀 クイックスタート (Quick Start)

### 1. 🌐 オンラインで即座に起動（おすすめ）

インストールやセットアップ不要で、ブラウザから直接アプリを起動・体験できます：

👉 **Live Demo: [https://net-ops-toolkit.streamlit.app](https://net-ops-toolkit.streamlit.app/)**

---

### 2. 💻 ローカル環境での起動（実機接続・オフライン運用）

#### A. Streamlit 版ダッシュボード (Port 8501)
```bash
streamlit run streamlit_app.py
```
*または `start_streamlit.bat` をダブルクリック*

#### B. Flask + Vanilla JS 版 Web GUI (Port 5000)
1. `system/backend/` に `occ.exe` を配置（[Codemonkey1973/OCC](https://github.com/Codemonkey1973/OCC) から入手）
2. `start.bat` をダブルクリック（または `python system/backend/app.py`）


---

### 起動方法 B: Flask + Vanilla JS 版 Web GUI（本番・現場運用向け）

1. **`occ.exe` を別途入手し配置します。**
   * [Codemonkey1973/OCC](https://github.com/Codemonkey1973/OCC) の Releases からダウンロードし、`system/backend/occ.exe` に配置してください。
2. **`start.bat`** をダブルクリックします。
3. 自動的にブラウザが立ち上がり、操作画面（`http://localhost:5000`）が表示されます。

---

## 💡 カメラ動作ボタンの仕様

| ボタン | コマンド | 説明 |
| :--- | :--- | :--- |
| **▶ 配信開始** | `-m start` | カメラからの RTP 映像配信（ストリーミング）を開始します。 |
| **⏹ 配信停止** | `-m stop` | 映像配信を停止し、カメラをスタンバイ状態にします。 |
| **🔄 再起動** | `-m restart` | カメラ本体のマイコンをソフトリブートします。**設定変更を反映させるために必須です。** |

---

## 📖 ドキュメント (Documentation)

* **システム構造・カスタマイズ詳細**: [system/STRUCTURE_AND_CUSTOMIZE.md](system/STRUCTURE_AND_CUSTOMIZE.md)
* **内部仕様書**: [system/README.md](system/README.md)
* **オープンソース使用表示**: [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)

---

## 👤 作成者 (Author)

* **GitHub**: [@Shuntaro1996](https://github.com/Shuntaro1996)

---

## 📄 ライセンス (License)

本プロジェクトのコード（バックエンド・フロントエンド・Streamlit）は [MIT License](LICENSE) のもとで公開されています。

本プロジェクトが使用するオープンソースソフトウェアについては [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) をご覧ください。

> **Note**: 本リポジトリに `occ.exe` は含まれていません。[Codemonkey1973/OCC](https://github.com/Codemonkey1973/OCC)（GPL-3.0）から別途入手してください。
