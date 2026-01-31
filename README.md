# CiscoCollab
A productivity toolkit for Cisco Collaboration log analysis.
CiscoCollab is a Sublime Text package designed to streamline the analysis of Cisco Collaboration logs. It provides automated highlighting, syntax detection, extraction utilities, and contextual decoding tools that make navigating large or complex log files significantly easier.

## ✨ Features

- Custom keyword highlighting for protocols, config keys, and diagnostic terms
- Optimized for YAML, SIP, and Cisco-style syntax
- Mouse binding for quick bookmarking (to be added manually)
- Extraction tool for nested files supporting ".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".tar.gz" (removed support for .7z and .rar to prevent external dependencies) 
- Persistent highlights introduced to the plugin, this will preserved highlighted words upon closure of the app

v1.2.0 Nov 3, 2025
- Feature added to clear specific styles instead of only "clear all", malfunction corrections on the extraction tool and remove dependancies from other files

- v1.3.0 Nov 14, 2025
- CUCM dictionary values added as hover over popups for ease of understanding of what some values might mean; First stage: DTMF
- Added syntax for EOL (end of line) process of CSF devices.

- 🔐 Certificate Decoder
Hover over Base64‑encoded certificates to view decoded X.509 details.
Supports PEM and XML‑wrapped certificates, including SSO logs.

## Create a new file with the name "Default (OSX).sublime-mousemap" for Mac and save it into this User/ folder; use "Default (Windows).sublime-mousemap" for Windows
## Content:
```
[
  {
    "button": "button1",
    "count": 1,
    "modifiers": ["ctrl"],
    "press_command": "toggle_bookmark"
  }
]
```
## 🔧 Installation

### Manual
1. Clone or download this repository.
2. Move the contents into your Sublime Text `Packages/User` directory:
   - `Preferences > Browse Packages`
