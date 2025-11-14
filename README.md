# CiscoCollab
Custom syntax with automated and manual highlight of keywords in Cisco Collaboration products for ease of guidance and troubleshooting.


## ✨ Features

- Custom keyword highlighting for protocols, config keys, and diagnostic terms
- Inverted color scheme for high-contrast visibility
- Optimized for YAML, SIP, and Cisco-style syntax
- Modular design for easy extension and reuse
- Mouse binding for quick bookmarking (to be added manually)
- Extraction tool for nested files supporting ".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".tar.gz" (removed support for .7z and .rar to prevent external dependencies) 
- The Extract tool has been added to the side bar menu, When selecting a compressed file, right click on the file and select "Extract"
- Persistent highlights introduced to the plugin, this will preserved highlighted words upon closure of the app\

v1.2.0 Nov 3, 2025
- Feature added to clear specific styles instead of only "clear all", malfunction corrections on the extraction tool and remove dependancies from other files

- v1.3.0 Nov 14, 2025
- CUCM dictionary values added as hover over popups for ease of understanding of what some values might mean; First stage: DTMF
- Added syntax for EOL (end of line) process of CSF devices. 

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
