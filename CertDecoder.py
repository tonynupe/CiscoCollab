import sublime
import sublime_plugin
import re
import ssl
import base64
import tempfile
import os
import subprocess
import binascii
import traceback
import time
from datetime import datetime

DEBUG_LOG = False


def _debug(msg):
    if DEBUG_LOG:
        print(msg)

# Patterns
PEM_BLOCK_PATTERN = r"(?s)-----BEGIN (CERTIFICATE|CERTIFICATE REQUEST)-----.*?-----END \1-----"
XML_CERT_PATTERN = r"(?s)<(?:ds:)?X509Certificate>\s*(.*?)\s*</(?:ds:)?X509Certificate>"
HOVER_SCAN_WINDOW = 200000
HOVER_THROTTLE_MS = 120
_HOVER_STATE = {}


def _find_enclosing_block(text, rel_point, begin_token, end_token):
    start = text.rfind(begin_token, 0, rel_point + 1)
    if start == -1:
        return None

    end = text.find(end_token, rel_point)
    if end == -1:
        return None

    end += len(end_token)
    if start <= rel_point < end:
        return (start, end)
    return None


def _extract_hover_payload(view, point):
    size = view.size()
    window_start = max(0, point - HOVER_SCAN_WINDOW)
    window_end = min(size, point + HOVER_SCAN_WINDOW)

    region = sublime.Region(window_start, window_end)
    text = view.substr(region)
    rel_point = point - window_start

    xml_pairs = [
        ("<X509Certificate>", "</X509Certificate>"),
        ("<ds:X509Certificate>", "</ds:X509Certificate>"),
    ]
    for begin_token, end_token in xml_pairs:
        bounds = _find_enclosing_block(text, rel_point, begin_token, end_token)
        if bounds:
            rel_start, rel_end = bounds
            abs_start = window_start + rel_start
            abs_end = window_start + rel_end
            return text[rel_start:rel_end], abs_start, abs_end

    pem_pairs = [
        (
            "-----BEGIN CERTIFICATE REQUEST-----",
            "-----END CERTIFICATE REQUEST-----",
        ),
        ("-----BEGIN CERTIFICATE-----", "-----END CERTIFICATE-----"),
    ]
    for begin_token, end_token in pem_pairs:
        bounds = _find_enclosing_block(text, rel_point, begin_token, end_token)
        if bounds:
            rel_start, rel_end = bounds
            abs_start = window_start + rel_start
            abs_end = window_start + rel_end
            return text[rel_start:rel_end], abs_start, abs_end

    return None


def _should_skip_hover(view, point):
    now = time.time()
    state = _HOVER_STATE.get(view.id())
    if state:
        elapsed_ms = (now - state.get("ts", 0)) * 1000.0
        if elapsed_ms < HOVER_THROTTLE_MS and abs(point - state.get("point", -999999)) < 3:
            return True
    _HOVER_STATE[view.id()] = {"ts": now, "point": point}
    return False

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
    lines = [b64[i:i+64] for i in range(0, len(b64), 64)]
    return "-----BEGIN CERTIFICATE-----\n" + "\n".join(lines) + "\n-----END CERTIFICATE-----\n"

def _append_cert_info(output_list, info):
    try:
        # Build subject and issuer strings in a Python 3.3 compatible way
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
            # ignore parse errors for notAfter
            pass

    except Exception as e:
        output_list.append("Error extracting certificate fields: " + str(e))

class DecodePemSelectionCommand(sublime_plugin.TextCommand):
    """
    Decode PEM certificates and XML-wrapped X509Certificate blocks.
    """

    def run(self, edit, pem_text=None):
        try:
            _debug("CiscoCollab: decode command invoked; pem_text provided: {}".format(bool(pem_text)))
            if not pem_text:
                sel = self.view.sel()[0]
                pem_text = self.view.substr(sel).strip()
                if not pem_text:
                    sublime.error_message("Select certificate/CSR content first or hover over it")
                    return
            self.decode_and_show(pem_text)
        except Exception as e:
            _debug("CiscoCollab: decode command exception: {}".format(e))
            traceback.print_exc()
            sublime.error_message("Error decoding certificate: " + str(e))

    def decode_and_show(self, pem_text):
        try:
            output = []

            # XML-wrapped certificate
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
                    except Exception as e:
                        output.append("Base64 decode failed: " + str(e))
                    else:
                        tmp_path = None
                        try:
                            pem_text_for_openssl = _der_to_pem_text(der)
                            tmp_path = _write_text_tempfile(pem_text_for_openssl, suffix=".pem")
                            info = ssl._ssl._test_decode_cert(tmp_path)
                            _append_cert_info(output, info)
                        except Exception as e:
                            output.append("Failed to parse XML certificate: " + str(e))
                        finally:
                            _safe_unlink(tmp_path)

            # PEM CSR
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
                            stderr=subprocess.STDOUT
                        )
                        # decode result in a py3.3-compatible way
                        try:
                            decoded = result.decode("utf-8", "replace")
                        except Exception:
                            decoded = str(result)
                        preview = "\n".join(decoded.splitlines()[:30])
                        output.append("<pre>" + preview + "</pre>")
                    finally:
                        _safe_unlink(tmp_path)
                except Exception:
                    # minimal fallback: show DER length if possible
                    m = re.search(r"(?s)-----BEGIN CERTIFICATE REQUEST-----(.*?)-----END CERTIFICATE REQUEST-----", pem_text)
                    if m:
                        b64 = "".join(m.group(1).strip().splitlines())
                        try:
                            der = base64.b64decode(b64)
                            # use binascii for hex preview for py3.3 compatibility
                            preview_hex = binascii.hexlify(der[:20]).decode("ascii")
                            output.append("DER length: " + str(len(der)))
                            output.append("Raw bytes preview: " + preview_hex)
                            output.append("<i>Full CSR subject/SANs require OpenSSL</i>")
                        except Exception:
                            output.append("Could not base64-decode CSR body")
                    else:
                        output.append("CSR block not well-formed or OpenSSL not available")

            # PEM Certificate
            elif "BEGIN CERTIFICATE" in pem_text:
                output.append("<b>Certificate Detected (PEM)</b>")
                tmp_path = None
                try:
                    tmp_path = _write_text_tempfile(pem_text, suffix=".pem")
                    info = ssl._ssl._test_decode_cert(tmp_path)
                    _append_cert_info(output, info)
                except Exception as e:
                    output.append("Failed to decode PEM certificate: " + str(e))
                finally:
                    _safe_unlink(tmp_path)

            else:
                pass

            html = "<br>".join(output)
            # show popup (guard against exceptions)
            try:
                self.view.show_popup(html, max_width=800)
            except Exception:
                # fallback to message dialog if popup fails
                sublime.message_dialog("Certificate decode result:\n\n" + "\n".join(output))
        except Exception as e:
            _debug("CiscoCollab: decode_and_show exception: {}".format(e))
            traceback.print_exc()
            sublime.error_message("Error decoding certificate: " + str(e))

class PemHoverListener(sublime_plugin.EventListener):
    """
    Hover listener for PEM and XML certificate blocks.
    """

    def on_hover(self, view, point, hover_zone):
        try:
            _debug("CiscoCollab: on_hover called; hover_zone: {}".format(hover_zone))
            if hover_zone != sublime.HOVER_TEXT:
                return

            if _should_skip_hover(view, point):
                return

            payload_data = _extract_hover_payload(view, point)
            if payload_data:
                payload, start, end = payload_data
                state = _HOVER_STATE.get(view.id(), {})
                same_block = (
                    state.get("block_start") == start and
                    state.get("block_end") == end and
                    state.get("change_count") == view.change_count()
                )
                if same_block and view.is_popup_visible():
                    return

                state.update({
                    "block_start": start,
                    "block_end": end,
                    "change_count": view.change_count(),
                })
                _HOVER_STATE[view.id()] = state
                view.run_command("decode_pem_selection", {"pem_text": payload})
                return

            # Fallback: if user has a non-empty selection, decode that
            sel = view.sel()[0]
            if not sel.empty():
                selected_text = view.substr(sel)
                if selected_text.strip():
                    view.run_command("decode_pem_selection", {"pem_text": selected_text})
                    return
        except Exception as e:
            _debug("CiscoCollab: on_hover exception: {}".format(e))
            traceback.print_exc()
