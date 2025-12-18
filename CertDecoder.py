import sublime
import sublime_plugin
import re
import ssl
import base64
import tempfile
import os
from datetime import datetime
from typing import Optional

# Patterns
PEM_BLOCK_PATTERN = r"(?s)-----BEGIN (CERTIFICATE|CERTIFICATE REQUEST)-----.*?-----END \1-----"
XML_CERT_PATTERN = r"(?s)<X509Certificate>(.*?)</X509Certificate>"

def _write_text_tempfile(text: str, suffix: str = ".pem") -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as tmp:
        tmp.write(text)
        return tmp.name

def _safe_unlink(path: Optional[str]):
    if path and os.path.exists(path):
        try:
            os.unlink(path)
        except Exception:
            pass

def _der_to_pem_text(der: bytes) -> str:
    b64 = base64.b64encode(der).decode("ascii")
    lines = [b64[i:i+64] for i in range(0, len(b64), 64)]
    return "-----BEGIN CERTIFICATE-----\n" + "\n".join(lines) + "\n-----END CERTIFICATE-----\n"

def _append_cert_info(output: list, info: dict):
    try:
        subject = ", ".join(f"{k}={v}" for tup in info.get("subject", []) for k, v in tup)
        issuer = ", ".join(f"{k}={v}" for tup in info.get("issuer", []) for k, v in tup)
        output.append("Subject: " + subject)
        output.append("Issuer: " + issuer)
        output.append("Serial Number: " + str(info.get("serialNumber")))
        output.append("Valid From: " + str(info.get("notBefore")))
        output.append("Valid Until: " + str(info.get("notAfter")))
        try:
            not_after = datetime.strptime(info.get("notAfter"), "%b %d %H:%M:%S %Y %Z")
            now = datetime.utcnow()
            if not_after < now:
                output.append(f"<span style='color:red'>Expired on {not_after}</span>")
            else:
                output.append(f"<span style='color:green'>Valid until {not_after}</span>")
        except Exception:
            pass
    except Exception as e:
        output.append("Error extracting certificate fields: " + str(e))

class DecodePemSelectionCommand(sublime_plugin.TextCommand):
    """
    Decode PEM certificates and XML-wrapped X509Certificate blocks.
    """

    def run(self, edit, pem_text=None):
        if not pem_text:
            sel = self.view.sel()[0]
            pem_text = self.view.substr(sel).strip()
            if not pem_text:
                sublime.error_message("Select certificate/CSR content first or hover over it")
                return
        self.decode_and_show(pem_text)

    def decode_and_show(self, pem_text: str):
        try:
            output = []

            # XML-wrapped certificate
            m_xml = re.search(XML_CERT_PATTERN, pem_text, re.S)
            if m_xml:
                output.append("<b>🔒XML-wrapped Certificate Detected</b>")
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
                        decoded = result.decode("utf-8", errors="replace")
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
                            output.append("DER length: " + str(len(der)))
                            output.append("Raw bytes preview: " + der[:20].hex())
                            output.append("<i>Full CSR subject/SANs require OpenSSL</i>")
                        except Exception:
                            output.append("Could not base64-decode CSR body")
                    else:
                        output.append("CSR block not well-formed or OpenSSL not available")

            # PEM Certificate
            elif "BEGIN CERTIFICATE" in pem_text:
                output.append("<b>🔒Certificate Detected (PEM)</b>")
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
                output.append("Input not recognized as PEM or XML-wrapped certificate. Select the PEM block or the XML tag.")

            html = "<br>".join(output)
            self.view.show_popup(html, max_width=800)
        except Exception as e:
            sublime.error_message("Error decoding certificate: " + str(e))

class PemHoverListener(sublime_plugin.EventListener):
    """
    Hover listener for PEM and XML certificate blocks.
    """

    def on_hover(self, view, point, hover_zone):
        if hover_zone != sublime.HOVER_TEXT:
            return

        # PEM blocks
        blocks = view.find_all(PEM_BLOCK_PATTERN)
        for region in blocks:
            if region.contains(point):
                pem_text = view.substr(region)
                view.run_command("decode_pem_selection", {"pem_text": pem_text})
                return

        # XML blocks
        xml_blocks = view.find_all(XML_CERT_PATTERN)
        for region in xml_blocks:
            if region.contains(point):
                xml_text = view.substr(region)
                view.run_command("decode_pem_selection", {"pem_text": xml_text})
                return

        # Fallback: if user has a non-empty selection, decode that
        sel = view.sel()[0]
        if not sel.empty():
            selected_text = view.substr(sel)
            if selected_text.strip():
                view.run_command("decode_pem_selection", {"pem_text": selected_text})
                return
