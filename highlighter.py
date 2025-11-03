import sublime, sublime_plugin
import re

REGION_NAME = 'StyleOptionsListener%d'
MAX_STYLES = 10
REGION_STORE = 'StyleOptionsRegions.sublime-settings'

# Built-in scopes that will render with distinct colors in most themes
STYLE_MAP = {
    0: "support.function",       # blue
    1: "string",                 # green
    2: "constant.numeric",       # orange
    3: "comment",                # gray
    4: "variable",               # white/light
    5: "entity.name.function",   # yellow
    6: "storage.type",           # cyan/blue-green
    7: "markup.raw.inline",      # green highlight
    8: "markup.deleted",         # red
    9: "diff.deleted.char",      # bright distinct (often bold yellow/white)
}


# Distinct draw styles for each index
STYLE_FLAGS = {
    0: sublime.DRAW_NO_OUTLINE,          # solid background
    1: sublime.DRAW_SOLID_UNDERLINE,     # underline
    2: sublime.DRAW_STIPPLED_UNDERLINE,  # dotted underline
    3: sublime.DRAW_NO_OUTLINE,             # outline only
    4: sublime.DRAW_NO_OUTLINE,          # background
    5: sublime.DRAW_SOLID_UNDERLINE,     # underline
    6: sublime.DRAW_NO_OUTLINE,          # background
    7: sublime.DRAW_NO_OUTLINE,          # background
    8: sublime.DRAW_STIPPLED_UNDERLINE,  # dotted underline
    9: sublime.DRAW_NO_OUTLINE,          # background
}

# Persistent region storage
class StyleOptionsStorage:
    def __init__(self, view):
        self.view = view
        self.key = view.file_name() or str(view.id())
        self.settings = sublime.load_settings(REGION_STORE)

    def save(self):
        data = {}
        for style in range(MAX_STYLES):
            regions = self.view.get_regions(REGION_NAME % style)
            data[REGION_NAME % style] = [(r.a, r.b) for r in regions]
        self.settings.set(self.key, data)
        sublime.save_settings(REGION_STORE)

    def restore(self):
        data = self.settings.get(self.key, {})
        for key, region_list in data.items():
            try:
                style_ind = int(re.search(r'\d+', key).group())
            except Exception:
                continue
            regions = [sublime.Region(a, b) for a, b in region_list]
            self.view.add_regions(
                key,
                regions,
                get_style(style_ind),
                '',  # no gutter icon
                STYLE_FLAGS.get(style_ind, sublime.DRAW_NO_OUTLINE)
            )

    def clear(self):
        for style in range(MAX_STYLES):
            self.view.erase_regions(REGION_NAME % style)
        self.save()

# Core logic
def rollover(style_index):
    return style_index % MAX_STYLES

def get_style(style_ind):
    return STYLE_MAP.get(style_ind, "invalid")

def get_current_regions(view, style_index):
    if style_index < 0:
        currentRegions = []
        for style in range(MAX_STYLES):
            currentRegions += view.get_regions(REGION_NAME % style)
        return sorted(currentRegions, key=lambda region: region.begin())
    else:
        return view.get_regions(REGION_NAME % rollover(style_index))

def move_selection(view, region):
    view.sel().clear()
    view.sel().add(sublime.Region(region.begin(), region.begin()))
    view.show(region)

def color_selection(view, style_ind):
    current_regions = view.get_regions(REGION_NAME % style_ind)
    tokens = set()
    for region in view.sel():
        whole_word_only = region.empty()
        if whole_word_only:
            region = view.word(region)
            if region.empty():
                continue
        literal = view.substr(region)
        escaped = re.escape(literal)
        if whole_word_only and escaped and escaped[0].isalnum():
            escaped = r'\b%s\b' % escaped
        tokens.add(escaped)

    if tokens:
        if len(tokens) == 1 and not whole_word_only:
            current_regions.extend(view.find_all(literal, sublime.LITERAL))
        else:
            current_regions.extend(view.find_all('|'.join(tokens)))
        view.add_regions(
            REGION_NAME % style_ind,
            current_regions,
            get_style(style_ind),
            '',  # no gutter icon
            STYLE_FLAGS.get(style_ind, sublime.DRAW_NO_OUTLINE)
        )
        StyleOptionsStorage(view).save()

# Commands
class StyleOptionsCommand(sublime_plugin.TextCommand):
    def run(self, edit, style_index):
        color_selection(self.view, rollover(style_index))
        StyleOptionsStorage(self.view).save()

class StyleOptionsGoCommand(sublime_plugin.TextCommand):
    def run(self, edit, style_index=-1):
        view = self.view
        current_regions = get_current_regions(view, style_index)
        if current_regions:
            selections = view.sel()
            if selections:
                pos = selections[0].end()
                for region in current_regions:
                    if region.begin() > pos:
                        move_selection(view, region)
                        return
            move_selection(view, current_regions[0])

class StyleOptionsGoBackCommand(sublime_plugin.TextCommand):
    def run(self, edit, style_index=-1):
        view = self.view
        current_regions = get_current_regions(view, style_index)
        if current_regions:
            selections = view.sel()
            if selections:
                pos = selections[0].end()
                for region in reversed(current_regions):
                    if region.begin() < pos:
                        move_selection(view, region)
                        return
            move_selection(view, current_regions[-1])

class StyleOptionsClearCommand(sublime_plugin.TextCommand):
    def run(self, edit, style_index=-1):
        if style_index < 0:
            # Clear all styles
            StyleOptionsStorage(self.view).clear()
            sublime.status_message("Style Options: All highlights cleared.")
        else:
            # Clear only the given style
            self.view.erase_regions(REGION_NAME % rollover(style_index))
            StyleOptionsStorage(self.view).save()
            sublime.status_message("Style Options: Cleared Style %d" % (style_index + 1))

class StyleOptionsSaveCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        StyleOptionsStorage(self.view).save()
        sublime.status_message("Style Options: Highlights saved.")

# Event listener for restoration
class StyleOptionsListener(sublime_plugin.EventListener):
    def on_load(self, view):
        StyleOptionsStorage(view).restore()

    def on_activated(self, view):
        if not any(view.get_regions(REGION_NAME % i) for i in range(MAX_STYLES)):
            StyleOptionsStorage(view).restore()
