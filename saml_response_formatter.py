import os
import re
from xml.dom import minidom

import sublime
import sublime_plugin

START_TAG = "<saml2p:Response"
END_TAG = "</saml2p:Response>"
SETTINGS_FILE = "SamlResponseFormatter.sublime-settings"


def _settings():
    return sublime.load_settings(SETTINGS_FILE)


def _should_auto_format(view):
    settings = _settings()
    if not settings.get("saml_auto_format_on_open", False):
        return False

    file_path = view.file_name()
    if not file_path:
        return False

    extensions = settings.get("saml_auto_format_extensions", ["log"]) or ["log"]
    ext = os.path.splitext(file_path)[1].lstrip(".").lower()
    normalized = [str(item).lstrip(".").lower() for item in extensions]
    if normalized and ext not in normalized:
        return False

    max_bytes = settings.get("saml_auto_format_max_bytes", 5000000)
    if isinstance(max_bytes, int) and max_bytes > 0:
        try:
            if os.path.getsize(file_path) > max_bytes:
                return False
        except OSError:
            return False

    return view.find(START_TAG, 0) is not None


def _collapse_x509_certificate(text):
    def replacer(match):
        inner = re.sub(r"\s+", "", match.group(2))
        return "{}{}{}".format(match.group(1), inner, match.group(3))

    return re.sub(
        r"(<(?:ds:)?X509Certificate>)([\s\S]*?)(</(?:ds:)?X509Certificate>)",
        replacer,
        text,
    )


def pretty_xml(xml_text, indent="  "):
    doc = minidom.parseString(xml_text)
    pretty = doc.toprettyxml(indent=indent)
    lines = [line for line in pretty.splitlines() if line.strip()]
    if lines and lines[0].startswith("<?xml"):
        lines = lines[1:]
    formatted = "\n".join(lines)
    return _collapse_x509_certificate(formatted)


def format_saml_blocks(text):
    out_parts = []
    pos = 0
    formatted = 0
    failed = 0

    while True:
        start = text.find(START_TAG, pos)
        if start == -1:
            out_parts.append(text[pos:])
            break

        end = text.find(END_TAG, start)
        if end == -1:
            out_parts.append(text[pos:])
            break

        end += len(END_TAG)
        out_parts.append(text[pos:start])
        block = text[start:end]

        try:
            formatted_block = pretty_xml(block)
            out_parts.append(formatted_block)
            formatted += 1
        except Exception:
            out_parts.append(block)
            failed += 1

        pos = end

    return "".join(out_parts), formatted, failed


class SamlFormatResponseCommand(sublime_plugin.TextCommand):
    def run(self, edit, scope="all"):
        if scope != "all":
            scope = "all"

        regions = self.view.sel()
        targets = []

        if scope == "selection" and regions and not regions[0].empty():
            targets = list(regions)
        else:
            targets = [sublime.Region(0, self.view.size())]

        total_formatted = 0
        total_failed = 0

        for region in reversed(targets):
            text = self.view.substr(region)
            new_text, formatted, failed = format_saml_blocks(text)
            if new_text != text:
                self.view.replace(edit, region, new_text)
            total_formatted += formatted
            total_failed += failed

        status = "SAML Response formatted: {} ok, {} failed".format(
            total_formatted, total_failed
        )
        sublime.status_message(status)


class SamlAutoFormatOnLoadListener(sublime_plugin.EventListener):
    def on_load(self, view):
        if not _should_auto_format(view):
            return

        sublime.set_timeout(lambda: view.run_command("saml_format_response"), 0)
