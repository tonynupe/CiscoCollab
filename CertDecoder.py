import sublime
import sublime_plugin
import re
import ssl
import base64
import tempfile
import subprocess
import os
from datetime import datetime

# Regex to capture PEM blocks
PEM_BLOCK_PATTERN = r"(?s)-----BEGIN (CERTIFICATE|CERTIFICATE REQUEST)-----.*?-----END \1-----"

class DecodePemSelectionCommand(sublime_plugin.TextCommand):
    """
    Decode CSR/Certificate from provided pem_text (or selection) using stdlib,
    with optional OpenSSL fallback for CSRs.
    """

    def run(self, edit, pem_text=None):
        # Allow both: explicit pem_text (from hover) or current selection
        if not pem_text:
            sel = self.view.substr(self.view.sel()[0])
            if not sel.strip():
                sublime.error_message("Select PEM content first")
                return
            pem_text = sel

        self.decode_and_show(pem_text)

    def decode_and_show(self, pem_text: str):
        try:
            output = []

            if "BEGIN CERTIFICATE REQUEST" in pem_text:
                # CSR handling
                output.append("<b>CSR Detected</b>")

                # Try OpenSSL if available
                try:
                    with tempfile.NamedTemporaryFile(mode="w", suffix=".csr", delete=False) as tmp:
                        tmp.write(pem_text)
                        tmp_path = tmp.name
                    try:
                        result = subprocess.check_output(
                            ["openssl", "req", "-in", tmp_path, "-noout", "-text"],
                            stderr=subprocess.STDOUT
                        )
                        decoded = result.decode("utf-8")
                        # Show first ~30 lines for readability
                        preview = "\n".join(decoded.splitlines()[:30])
                        output.append("<pre>" + preview + "</pre>")
                    finally:
                        os.unlink(tmp_path)
                except Exception:
                    # Fallback: minimal decode
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
                        output.append("CSR block not well-formed")

            else:
                # Certificate handling
                output.append("<b>🔒Certificate Detected</b>")
                with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as tmp:
                    tmp.write(pem_text)
                    tmp_path = tmp.name

                try:
                    info = ssl._ssl._test_decode_cert(tmp_path)  # expects a file path
                    subject = ", ".join(f"{k}={v}" for tup in info.get("subject", []) for k, v in tup)
                    issuer = ", ".join(f"{k}={v}" for tup in info.get("issuer", []) for k, v in tup)
                    output.append("Subject: " + subject)
                    output.append("Issuer: " + issuer)
                    output.append("Serial Number: " + str(info.get("serialNumber")))
                    output.append("Valid From: " + str(info.get("notBefore")))
                    output.append("Valid Until: " + str(info.get("notAfter")))

                    # Expiry check
                    try:
                        not_after = datetime.strptime(info.get("notAfter"), "%b %d %H:%M:%S %Y %Z")
                        now = datetime.utcnow()
                        if not_after < now:
                            validity_html = f"<span style='color:red'>Expired on {not_after}</span>"
                        else:
                            validity_html = f"<span style='color:green'>Valid until {not_after}</span>"
                        output.append(validity_html)
                    except Exception:
                        pass
                finally:
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass

            html = "<br>".join(output)
            self.view.show_popup(html, max_width=800)
        except Exception as e:
            sublime.error_message("Error decoding PEM: " + str(e))


class PemHoverListener(sublime_plugin.EventListener):
    """
    Show popup when hovering over PEM CSR/Certificate blocks.
    """

    def on_hover(self, view, point, hover_zone):
        if hover_zone != sublime.HOVER_TEXT:
            return

        blocks = view.find_all(PEM_BLOCK_PATTERN)
        for region in blocks:
            if region.contains(point):
                pem_text = view.substr(region)
                view.run_command("decode_pem_selection", {"pem_text": pem_text})
                break
