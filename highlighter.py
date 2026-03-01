import sublime
import sublime_plugin
import re
import os
import time

REGION_NAME = 'StyleOptionsListener%d'
MAX_STYLES = 10
REGION_STORE = 'StyleOptionsRegions.sublime-settings'

# Limits
MAX_REGIONS_PER_STYLE = 500
MAX_TOKENS_PER_STYLE = 500
MAX_STORAGE_SIZE = 20 * 1024 * 1024  # 20 MB

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
    9: "diff.deleted.char",      # bright distinct
}

STYLE_FLAGS = {
    0: sublime.DRAW_NO_OUTLINE,
    1: sublime.DRAW_SOLID_UNDERLINE,
    2: sublime.DRAW_STIPPLED_UNDERLINE,
    3: sublime.DRAW_NO_OUTLINE,
    4: sublime.DRAW_NO_OUTLINE,
    5: sublime.DRAW_SOLID_UNDERLINE,
    6: sublime.DRAW_NO_OUTLINE,
    7: sublime.DRAW_NO_OUTLINE,
    8: sublime.DRAW_STIPPLED_UNDERLINE,
    9: sublime.DRAW_NO_OUTLINE,
}

# Persistent region storage


class StyleOptionsStorage:
    def __init__(self, view):
        self.view = view
        file_name = view.file_name()
        self.folder_norm = self._normalized_folder(file_name) if file_name else None
        self.scope_root = self._scope_root(file_name) if file_name else None
        self.key = self._scope_key(file_name) if file_name else str(view.id())
        self.scope_keys = self._scope_keys(file_name) if file_name else [str(view.id())]
        self.settings = sublime.load_settings(REGION_STORE)

    def _normalized_folder(self, file_name):
        folder = os.path.dirname(file_name)
        return os.path.normcase(os.path.realpath(folder))

    def _scope_key(self, file_name):
        return "folder::%s" % self._scope_root(file_name)

    def _scope_root(self, file_name):
        file_real = os.path.normcase(os.path.realpath(file_name))
        window = self.view.window()
        if window:
            candidates = []
            for folder in window.folders() or []:
                root = os.path.normcase(os.path.realpath(folder))
                if file_real == root or file_real.startswith(root + os.sep):
                    candidates.append(root)
            if candidates:
                return max(candidates, key=len)
        return self._normalized_folder(file_name)

    def _scope_keys(self, file_name):
        folder = os.path.dirname(file_name)
        normalized = self._normalized_folder(file_name)
        scope_root = self._scope_root(file_name)
        keys = [
            "folder::%s" % scope_root,
            scope_root,
            "folder::%s" % normalized,
            normalized,
            folder,
        ]
        seen = set()
        ordered = []
        for key in keys:
            if key and key not in seen:
                seen.add(key)
                ordered.append(key)
        return ordered

    def _is_within_scope(self, path_value):
        if not self.scope_root or not path_value:
            return False
        try:
            normalized = os.path.normcase(os.path.realpath(path_value))
        except Exception:
            return False
        return normalized == self.scope_root or normalized.startswith(self.scope_root + os.sep)

    def _legacy_file_keys_in_scope(self):
        if not self.scope_root:
            return []
        legacy_keys = []
        all_data = self.settings.to_dict()
        for key, value in all_data.items():
            if not isinstance(value, dict):
                continue
            candidate = key
            if key.startswith("folder::"):
                candidate = key[len("folder::"):]

            if not os.path.isabs(candidate):
                continue

            candidate_dir = os.path.dirname(candidate)
            if self._is_within_scope(candidate) or self._is_within_scope(candidate_dir):
                legacy_keys.append(key)
        return legacy_keys

    def _merged_scope_data(self, include_legacy=False):
        merged = {}
        keys = list(self.scope_keys)
        if include_legacy:
            keys += self._legacy_file_keys_in_scope()
        for key in keys:
            payload = self.settings.get(key, {})
            if isinstance(payload, dict):
                for style_key, value in payload.items():
                    if style_key not in merged:
                        merged[style_key] = value
        return merged

    def _save_scope_data(self, data, purge_legacy=False):
        if data:
            self.settings.set(self.key, data)
        else:
            self.settings.erase(self.key)

        for old_key in self.scope_keys:
            if old_key != self.key:
                self.settings.erase(old_key)

        if purge_legacy:
            for old_key in self._legacy_file_keys_in_scope():
                self.settings.erase(old_key)

        sublime.save_settings(REGION_STORE)

    def _normalize_token_entries(self, token_entries):
        normalized = []
        for entry in token_entries:
            if isinstance(entry, dict) and entry.get("p"):
                normalized.append({"p": entry["p"], "ts": entry.get("ts", 0)})
            elif isinstance(entry, str):
                normalized.append({"p": entry, "ts": 0})
        return normalized

    def _extract_tokens_from_payload(self, payload):
        if not isinstance(payload, dict):
            return []
        tokens = self._normalize_token_entries(payload.get("tokens", []))
        if tokens:
            return tokens
        # Backward compatibility with older structures
        patterns = payload.get("__patterns__", {})
        if isinstance(patterns, dict):
            legacy_tokens = []
            for values in patterns.values():
                for item in values if isinstance(values, list) else []:
                    if isinstance(item, dict) and item.get("pattern"):
                        pattern = item["pattern"]
                        if item.get("literal"):
                            pattern = re.escape(pattern)
                        legacy_tokens.append(
                            {"p": pattern, "ts": item.get("ts", 0)})
            if legacy_tokens:
                return legacy_tokens
        return []

    def _regions_from_legacy_list(self, payload):
        regions = []
        if not isinstance(payload, list):
            return regions
        for item in payload:
            if isinstance(item, dict) and "a" in item and "b" in item:
                regions.append(sublime.Region(item["a"], item["b"]))
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                regions.append(sublime.Region(item[0], item[1]))
        return regions

    def _merge_tokens(self, existing_tokens, new_patterns):
        now = time.time()
        token_map = {item["p"]: item.get("ts", 0)
                     for item in existing_tokens if item.get("p")}
        for pattern in new_patterns:
            token_map[pattern] = now
        merged = [{"p": p, "ts": ts} for p, ts in token_map.items()]
        merged = sorted(merged, key=lambda x: x.get(
            "ts", 0))[-MAX_TOKENS_PER_STYLE:]
        return merged

    def _tokens_from_regions(self, regions):
        tokens = set()
        for region in regions:
            literal = self.view.substr(region)
            if literal:
                tokens.add(re.escape(literal))
        return tokens

    def add_tokens(self, style_ind, patterns):
        style_key = REGION_NAME % style_ind
        key_data = self._merged_scope_data(include_legacy=False)
        payload = key_data.get(style_key, {})
        existing = self._extract_tokens_from_payload(payload)
        merged_tokens = self._merge_tokens(existing, patterns)
        key_data[style_key] = {"tokens": merged_tokens}
        self._save_scope_data(key_data, purge_legacy=False)

    def save(self):
        existing_data = self._merged_scope_data(include_legacy=False)
        data = {}
        for style in range(MAX_STYLES):
            style_key = REGION_NAME % style
            regions = self.view.get_regions(style_key)
            existing_tokens = self._extract_tokens_from_payload(
                existing_data.get(style_key, {}))
            region_tokens = self._tokens_from_regions(regions)
            merged_tokens = self._merge_tokens(existing_tokens, region_tokens)
            if merged_tokens:
                data[style_key] = {"tokens": merged_tokens}

        self._save_scope_data(data, purge_legacy=False)

        # Global storage cap check
        store_path = os.path.join(
            sublime.packages_path(), 'User', REGION_STORE)
        if os.path.exists(store_path) and os.path.getsize(store_path) > MAX_STORAGE_SIZE:
            self._purge_oldest_entries()

    def _purge_oldest_entries(self):
        all_data = self.settings.to_dict()
        all_tokens = []
        for file_key, styles in all_data.items():
            for style_key, regions in styles.items():
                if not isinstance(regions, dict):
                    continue
                for token in self._extract_tokens_from_payload(regions):
                    all_tokens.append((file_key, style_key, token))
        # Sort globally by timestamp
        all_tokens.sort(key=lambda x: x[2].get("ts", 0))
        # Keep only newest half
        keep = all_tokens[len(all_tokens)//2:]
        new_data = {}
        for file_key, style_key, token in keep:
            new_data.setdefault(file_key, {}).setdefault(
                style_key, {}).setdefault("tokens", []).append(token)
        # Replace settings
        for k in list(all_data.keys()):
            self.settings.erase(k)
        for k, v in new_data.items():
            self.settings.set(k, v)
        sublime.save_settings(REGION_STORE)
        sublime.status_message("Style Options: Storage pruned to reduce size.")

    def restore(self):
        data = self._merged_scope_data(include_legacy=True)
        restored = False
        for key, payload in data.items():
            try:
                style_ind = int(re.search(r'\d+', key).group())
            except Exception:
                continue
            token_entries = self._extract_tokens_from_payload(payload)
            patterns = [entry["p"]
                        for entry in token_entries if entry.get("p")]
            regions = []
            if patterns:
                seen = set()
                for pattern in patterns:
                    try:
                        found = self.view.find_all(pattern)
                    except Exception:
                        continue
                    for region in found:
                        key_tuple = (region.a, region.b)
                        if key_tuple not in seen:
                            seen.add(key_tuple)
                            regions.append(region)
            elif isinstance(payload, list):
                regions = self._regions_from_legacy_list(payload)
            self.view.add_regions(
                key,
                regions,
                get_style(style_ind),
                '',
                STYLE_FLAGS.get(style_ind, sublime.DRAW_NO_OUTLINE)
            )
            if regions:
                restored = True
        return restored

    def clear(self):
        for style in range(MAX_STYLES):
            self.view.erase_regions(REGION_NAME % style)
        self._save_scope_data({}, purge_legacy=True)

    def clear_style(self, style_ind):
        style_key = REGION_NAME % rollover(style_ind)
        self.view.erase_regions(style_key)
        key_data = self._merged_scope_data(include_legacy=False)
        if style_key in key_data:
            del key_data[style_key]
        self._save_scope_data(key_data, purge_legacy=False)


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
            '',
            STYLE_FLAGS.get(style_ind, sublime.DRAW_NO_OUTLINE)
        )
        storage = StyleOptionsStorage(view)
        storage.add_tokens(style_ind, tokens)


# Commands
class StyleOptionsCommand(sublime_plugin.TextCommand):
    def run(self, edit, style_index):
        color_selection(self.view, rollover(style_index))


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
        storage = StyleOptionsStorage(self.view)
        if style_index < 0:
            storage.clear()
            sublime.status_message("Style Options: All highlights cleared.")
        else:
            storage.clear_style(style_index)
            sublime.status_message(
                "Style Options: Cleared Style %d" % (style_index + 1))


class StyleOptionsSaveCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        StyleOptionsStorage(self.view).save()
        sublime.status_message("Style Options: Highlights saved.")


class StyleOptionsPurgeCommand(sublime_plugin.WindowCommand):
    """Manual purge command to reset storage file"""

    def run(self):
        settings = sublime.load_settings(REGION_STORE)
        for k in list(settings.to_dict().keys()):
            settings.erase(k)
        sublime.save_settings(REGION_STORE)
        sublime.status_message("Style Options: All stored highlights purged.")


# Event listener for restoration
class StyleOptionsListener(sublime_plugin.EventListener):
    def _restore_when_ready(self, view, retries=8, delay_ms=120):
        if not view or not view.file_name():
            return
        if view.is_loading() or view.size() == 0:
            if retries > 0:
                sublime.set_timeout(
                    lambda: self._restore_when_ready(view, retries - 1, delay_ms),
                    delay_ms
                )
            return
        storage = StyleOptionsStorage(view)
        restored = storage.restore()
        if not restored and retries > 0:
            sublime.set_timeout(
                lambda: self._restore_when_ready(view, retries - 1, delay_ms),
                delay_ms
            )

    def on_load(self, view):
        if view.file_name():
            sublime.set_timeout(
                lambda: self._restore_when_ready(view), 50)

    def on_activated(self, view):
        if view.file_name():
            sublime.set_timeout(
                lambda: self._restore_when_ready(view), 80)
