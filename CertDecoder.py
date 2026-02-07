import base64
import binascii
import os
import re
import ssl
import subprocess
import tempfile
import traceback
from datetime import datetime
from xml.dom import minidom

import sublime
import sublime_plugin

START_TAG = "<saml2p:Response"
END_TAG = "</saml2p:Response>"
PEM_BLOCK_PATTERN = r"(?s)-----BEGIN (CERTIFICATE|CERTIFICATE REQUEST)-----.*?-----END \1-----"
XML_CERT_PATTERN = r"(?s)<(?:ds:)?X509Certificate>\s*(.*?)\s*</(?:ds:)?X509Certificate>"

SETTINGS_FILE = "SamlResponseFormatter.sublime-settings"


def _write_text_tempfile(text, suffix=".pem"):
    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as tmp:
        tmp.write(text)
        return tmp.name


def _safe_unlink(path):
    if path and os.path.exists(path):
        try:
            os.unlink(path)
        except Exception:
            pass


def _der_to_pem_text(der):
    b64 = base64.b64encode(der).decode("ascii")
    lines = [b64[i:i + 64] for i in range(0, len(b64), 64)]
    return "-----BEGIN CERTIFICATE-----\n" + "\n".join(lines) + "\n-----END CERTIFICATE-----\n"


def _append_cert_info(output_list, info):
    try:
        subject_parts = []
        for tup in info.get("subject", []):
            for k, v in tup:
                subject_parts.append("{}={}".format(k, v))
        subject = ", ".join(subject_parts)

        issuer_parts = []
        for tup in info.get("issuer", []):
            for k, v in tup:
                issuer_parts.append("{}={}".format(k, v))
        issuer = ", ".join(issuer_parts)

        output_list.append("Subject: " + subject)
        output_list.append("Issuer: " + issuer)
        output_list.append("Serial Number: " + str(info.get("serialNumber")))
        output_list.append("Valid From: " + str(info.get("notBefore")))
        output_list.append("Valid Until: " + str(info.get("notAfter")))

        try:
            not_after = datetime.strptime(info.get("notAfter"), "%b %d %H:%M:%S %Y %Z")
            now = datetime.utcnow()
            if not_after < now:
                validity_html = "<span style='color:red'>Expired on {}</span>".format(not_after)
            else:
                validity_html = "<span style='color:green'>Valid until {}</span>".format(not_after)
            output_list.append(validity_html)
        except Exception:
            pass

    except Exception as exc:
        output_list.append("Error extracting certificate fields: " + str(exc))


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

    max_bytes = settings.get("saml_auto_format_max_bytes", 5_000_000)
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


class DecodePemSelectionCommand(sublime_plugin.TextCommand):
    def run(self, edit, pem_text=None):
        try:
            if not pem_text:
                sel = self.view.sel()[0]
                pem_text = self.view.substr(sel).strip()
                if not pem_text:
                    sublime.error_message("Select certificate/CSR content first or hover over it")
                    return
            self.decode_and_show(pem_text)
        except Exception as exc:
            traceback.print_exc()
            sublime.error_message("Error decoding certificate: " + str(exc))

    def decode_and_show(self, pem_text):
        try:
            output = []

            m_xml = re.search(XML_CERT_PATTERN, pem_text, re.S)
            if m_xml:
                output.append("<b>XML-wrapped Certificate Detected</b>")
                b64 = m_xml.group(1) or ""
                b64_clean = "".join(b64.split())
                if not b64_clean:
                    output.append("Could not extract Base64 content from <X509Certificate>")
                else:
                    try:
                        der = base64.b64decode(b64_clean)
                    except Exception as exc:
                        output.append("Base64 decode failed: " + str(exc))
                    else:
                        tmp_path = None
                        try:
                            pem_text_for_openssl = _der_to_pem_text(der)
                            tmp_path = _write_text_tempfile(pem_text_for_openssl, suffix=".pem")
                            info = ssl._ssl._test_decode_cert(tmp_path)
                            _append_cert_info(output, info)
                        except Exception as exc:
                            output.append("Failed to parse XML certificate: " + str(exc))
                        finally:
                            _safe_unlink(tmp_path)

            elif "BEGIN CERTIFICATE REQUEST" in pem_text:
                output.append("<b>CSR Detected</b>")
                tmp_path = None
                try:
                    with tempfile.NamedTemporaryFile(mode="w", suffix=".csr", delete=False) as tmp:
                        tmp.write(pem_text)
                        tmp_path = tmp.name
                    try:
                        result = subprocess.check_output(
                            ["openssl", "req", "-in", tmp_path, "-noout", "-text"],
                            stderr=subprocess.STDOUT,
                        )
                        try:
                            decoded = result.decode("utf-8", "replace")
                        except Exception:
                            decoded = str(result)
                        preview = "\n".join(decoded.splitlines()[:30])
                        output.append("<pre>" + preview + "</pre>")
                    finally:
                        _safe_unlink(tmp_path)
                except Exception:
                    m = re.search(
                        r"(?s)-----BEGIN CERTIFICATE REQUEST-----(.*?)-----END CERTIFICATE REQUEST-----",
                        pem_text,
                    )
                    if m:
                        b64 = "".join(m.group(1).strip().splitlines())
                        try:
                            der = base64.b64decode(b64)
                            preview_hex = binascii.hexlify(der[:20]).decode("ascii")
                            output.append("DER length: " + str(len(der)))
                            output.append("Raw bytes preview: " + preview_hex)
                            output.append("<i>Full CSR subject/SANs require OpenSSL</i>")
                        except Exception:
                            output.append("Could not base64-decode CSR body")
                    else:
                        output.append("CSR block not well-formed or OpenSSL not available")

            elif "BEGIN CERTIFICATE" in pem_text:
                output.append("<b>Certificate Detected (PEM)</b>")
                tmp_path = None
                try:
                    tmp_path = _write_text_tempfile(pem_text, suffix=".pem")
                    info = ssl._ssl._test_decode_cert(tmp_path)
                    _append_cert_info(output, info)
                except Exception as exc:
                    output.append("Failed to decode PEM certificate: " + str(exc))
                finally:
                    _safe_unlink(tmp_path)

            html = "<br>".join(output)
            try:
                self.view.show_popup(html, max_width=800)
            except Exception:
                sublime.message_dialog("Certificate decode result:\n\n" + "\n".join(output))
        except Exception as exc:
            traceback.print_exc()
            sublime.error_message("Error decoding certificate: " + str(exc))


class PemHoverListener(sublime_plugin.EventListener):
    def on_hover(self, view, point, hover_zone):
        try:
            if hover_zone != sublime.HOVER_TEXT:
                return

            blocks = view.find_all(PEM_BLOCK_PATTERN)
            for region in blocks:
                if region.contains(point):
                    pem_text = view.substr(region)
                    view.run_command("decode_pem_selection", {"pem_text": pem_text})
                    return

            xml_blocks = view.find_all(XML_CERT_PATTERN)
            for region in xml_blocks:
                if region.contains(point):
                    xml_text = view.substr(region)
                    view.run_command("decode_pem_selection", {"pem_text": xml_text})
                    return

            sel = view.sel()[0]
            if not sel.empty():
                selected_text = view.substr(sel)
                if selected_text.strip():
                    view.run_command("decode_pem_selection", {"pem_text": selected_text})
        except Exception:
            traceback.print_exc()


class SamlAutoFormatOnLoadListener(sublime_plugin.EventListener):
    def on_load(self, view):
        if not _should_auto_format(view):
            return

        sublime.set_timeout(lambda: view.run_command("saml_format_response"), 0)
