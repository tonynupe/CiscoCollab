# CiscoCollab
Simple complement for Sublime text, provides automated highlight of keywords in Cisco Collaboration products for ease of guidance and troubleshooting.


## ✨ Features

- Custom keyword highlighting for protocols, config keys, and diagnostic terms
- Inverted color scheme for high-contrast visibility
- Optimized for YAML, SIP, and Cisco-style syntax
- Modular design for easy extension and reuse
- Mouse binding for quick bookmarking

## 🔧 Installation

### Manual
1. Clone or download this repository.
2. Move the contents into your Sublime Text `Packages/User` directory:
   - `Preferences > Browse Packages`

### Package Control (optional)
To make this installable via Package Control, submit it to the [Package Control Channel](https://github.com/wbond/package_control_channel) with a semantic version tag.

## 🎨 Color Scheme Variants

### Cisco Collab (DARK MODE: Mariana)
Add the following inside your `.sublime-color-scheme` file under `"rules"`:

```json
{
    "scope": "keyword.custom.highlightBlack",
    "foreground": "var(black)",
    "font_style": "bold",
    "background": "hsla(0, 0%, 100%, 1)"
}


Cisco Collab (LIGHT MODE: Sixteen)
Add the following inside "rules":

{
    "scope": "keyword.custom.highlightBlack",
    "foreground": "white",
    "font_style": "bold",
    "background": "black"
}

Mouse Key Binding for Bookmarks
To toggle a bookmark with Ctrl + Left Click, add this to your Default (Windows).sublime-mousemap (or platform-specific variant):

[
  {
    "button": "button1",
    "count": 1,
    "modifiers": ["ctrl"],
    "press_command": "toggle_bookmark"
  }
]

Theme Auto-Switching
Set your theme preferences to auto-switch based on system appearance:

auto > light = Sixteen; dark = Mariana
