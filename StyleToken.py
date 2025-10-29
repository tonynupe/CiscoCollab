import sublime, sublime_plugin
import re

REGION_NAME = 'StyleTokenListener%d'
MAX_STYLES = 10
REGION_STORE = 'StyleTokenRegions.sublime-settings'
cs_settings = None

# Load plugin settings
def plugin_loaded():
    global cs_settings
    cs_settings = sublime.load_settings('StyleToken.sublime-settings')

# Helper class for persistent region storage
class StyleTokenStorage:
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
            except:
                continue
            regions = [sublime.Region(a, b) for a, b in region_list]
            self.view.add_regions(key, regions, str(get_style(style_ind)), '')

    def clear(self):
        for style in range(MAX_STYLES):
            self.view.erase_regions(REGION_NAME % style)
        self.save()

# Core logic
def rollover(style_index):
    return style_index % MAX_STYLES

def get_style(style_ind):
    return cs_settings.get('styletoken_style%d' % (style_ind + 1), 'invalid')

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
        if whole_word_only and escaped[0].isalnum():
            escaped = r'\b%s\b' % escaped
        tokens.add(escaped)

    if tokens:
        if len(tokens) == 1 and not whole_word_only:
            current_regions.extend(view.find_all(literal, sublime.LITERAL))
        else:
            current_regions.extend(view.find_all('|'.join(tokens)))
        view.add_regions(REGION_NAME % style_ind, current_regions, str(get_style(style_ind)), '')
        StyleTokenStorage(view).save()

# Commands
class TokenStyleCommand(sublime_plugin.TextCommand):
    def run(self, edit, style_index):
        color_selection(self.view, rollover(style_index))
        StyleTokenStorage(self.view).save()

class TokenStyleGoCommand(sublime_plugin.TextCommand):
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

class TokenStyleGoBackCommand(sublime_plugin.TextCommand):
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

class TokenStyleClearCommand(sublime_plugin.TextCommand):
    def run(self, edit, style_index=-1):
        if style_index < 0:
            StyleTokenStorage(self.view).clear()
        else:
            self.view.erase_regions(REGION_NAME % rollover(style_index))
            StyleTokenStorage(self.view).save()

class TokenStyleSaveCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        StyleTokenStorage(self.view).save()
        sublime.status_message("StyleToken: Highlights saved.")

# Event listener for restoration
class StyleTokenListener(sublime_plugin.EventListener):
    def on_load(self, view):
        StyleTokenStorage(view).restore()

    def on_activated(self, view):
        # Restore only if regions are missing
        if not any(view.get_regions(REGION_NAME % i) for i in range(MAX_STYLES)):
            StyleTokenStorage(view).restore()
