# Third-Party Software Notices

This project (OCC-Web) uses the following open source software.
We are grateful to all authors and contributors.

---

## 1. OCC — Orlaco Camera Configurator CLI

| Item | Detail |
| :--- | :--- |
| **Repository** | https://github.com/Codemonkey1973/OCC |
| **Author** | Lee Mitchell (Codemonkey1973) |
| **License** | GNU General Public License v3.0 (GPL-3.0) |
| **Usage in this project** | `occ.exe` is used as an **external binary** invoked via subprocess. It is **not** bundled in this repository. Please download it separately from the repository above. |

> **Note**: `occ.exe` is NOT included in this repository due to its GPL-3.0 license.
> Place the binary at `system/backend/occ.exe` before running the application.

---

## 2. Flask

| Item | Detail |
| :--- | :--- |
| **Repository** | https://github.com/pallets/flask |
| **Author** | Armin Ronacher, Pallets Contributors |
| **License** | BSD-3-Clause |
| **Usage** | WSGI web application framework for the backend API server |

```
Copyright 2010 Pallets

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
...
(Full text: https://github.com/pallets/flask/blob/main/LICENSE.txt)
```

---

## 3. Flask-CORS

| Item | Detail |
| :--- | :--- |
| **Repository** | https://github.com/corydolphin/flask-cors |
| **Author** | Cory Dolphin |
| **License** | MIT License |
| **Usage** | Cross-Origin Resource Sharing (CORS) support for the Flask API |

```
Full text: https://github.com/corydolphin/flask-cors/blob/main/LICENSE
```

---

## 4. OpenCV (opencv-python-headless)

| Item | Detail |
| :--- | :--- |
| **Repository** | https://github.com/opencv/opencv |
| **Author** | OpenCV team, Intel Corporation |
| **License** | Apache License 2.0 |
| **Usage** | RTP video stream capture, H.264/MJPEG frame decoding, and MJPEG encoding for browser preview |

```
Full text: https://github.com/opencv/opencv/blob/master/LICENSE
```

---

## 5. NumPy

| Item | Detail |
| :--- | :--- |
| **Repository** | https://github.com/numpy/numpy |
| **Author** | NumPy Contributors |
| **License** | BSD-3-Clause |
| **Usage** | Array handling for video frame data |

```
Full text: https://github.com/numpy/numpy/blob/main/LICENSE.txt
```

---

## 6. Waitress

| Item | Detail |
| :--- | :--- |
| **Repository** | https://github.com/Pylons/waitress |
| **Author** | Pylons Project Contributors |
| **License** | Zope Public License 2.1 (ZPL-2.1) |
| **Usage** | Production-grade pure-Python WSGI server |

```
Full text: https://github.com/Pylons/waitress/blob/main/LICENSE.txt
```

---

## License Compatibility Summary

| Library | License | Compatible with MIT (this project) |
| :--- | :--- | :--- |
| OCC (occ.exe) | GPL-3.0 | External binary only — not bundled |
| Flask | BSD-3-Clause | Yes |
| Flask-CORS | MIT | Yes |
| OpenCV | Apache 2.0 | Yes |
| NumPy | BSD-3-Clause | Yes |
| Waitress | ZPL-2.1 | Yes |

---

*This file was last updated: 2026-08-17*
