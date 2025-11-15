import re
import sublime
import sublime_plugin

print(">>> cucm_dtmf_hover module loaded (py3.3 compatible, ordered by party, no title)")

CUCM_ENUMS = {
    "DTMFConfig": {1: "BestEffort", 2: "PreferOOB", 3: "Prefer2833", 4: "PreferBoth"},
    "DTMFMethod": {
        0: "NoDTMF",
        1: "OOB",
        2: "RFC2833",
        3: "OOB + RFC2833",
        4: "UnknownDTMF"
    }
}

def explain_enum(enum_type, value):
    return CUCM_ENUMS.get(enum_type, {}).get(value, "Unknown ({})".format(value))

def parse_dtmf_block(line):
    output = {}

    for m in re.finditer(r'party\d+DTMF\(', line):
        start = m.start()
        idx = m.end()
        depth = 1
        while idx < len(line) and depth > 0:
            ch = line[idx]
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            idx += 1
        if depth != 0:
            print(">>> parse_dtmf_block: paréntesis no balanceado en posición", start)
            continue
        block = line[m.start():idx]
        label_match = re.match(r'(party\d+DTMF)', block)
        label = label_match.group(1) if label_match else "partyXDTMF"

        inner = block[block.find('(')+1 : -1].strip()

        m2 = re.match(r'^\s*(\d+)\s+(\d+)\s+\(([^)]*)\)\s+(\d+)\s+(\d+)\s*$', inner)
        if m2:
            config, method, payload_raw, want_recv, provide_oob = m2.groups()
        else:
            try:
                p_open = inner.find('(')
                p_close = inner.find(')', p_open+1) if p_open != -1 else -1
                if p_open == -1 or p_close == -1:
                    raise ValueError("no payload parens")
                before = inner[:p_open].strip().split()
                payload_raw = inner[p_open+1:p_close]
                after = inner[p_close+1:].strip().split()
                if len(before) < 2 or len(after) < 2:
                    raise ValueError("estructura inesperada")
                config = before[0]
                method = before[1]
                want_recv = after[0]
                provide_oob = after[1]
            except Exception:
                print(">>> parse_dtmf_block: no match en block:", repr(block))
                continue

        payload = payload_raw.strip()
        payload_value = payload.split(":", 1)[0] if payload else None

        output["{} Config".format(label)] = explain_enum("DTMFConfig", int(config))
        output["{} Method".format(label)] = CUCM_ENUMS.get("DTMFMethod", {}).get(int(method), "Unknown ({})".format(method))
        output["{} Payload".format(label)] = payload_value if payload_value else "—"
        output["{} Wants Reception".format(label)] = "Yes" if int(want_recv) else "No"
        output["{} Provides OOB".format(label)] = "Yes" if int(provide_oob) else "No"

        print(">>> parse_dtmf_block: parsed", label, config, method, payload_raw, want_recv, provide_oob)

    return output if output else None

def format_popup(items):
    # Orden deseado de sufijos y mapeo a etiquetas mostradas
    order = [
        ("Config", "dtmf config"),
        ("Method", "dtmf method"),
        ("Payload", "payload"),
        ("Wants Reception", "wantDTMFrecepcion"),
        ("Provides OOB", "provideOOB")
    ]

    # Agrupa por partyNDTMF
    grouped = {}
    for label, value in items.items():
        key = label.split()[0]  # 'party1DTMF'
        grouped.setdefault(key, []).append((label, value))

    # ordenar keys por número de party (extraer dígito)
    def party_key(k):
        m = re.match(r'party(\d+)DTMF', k)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                return 9999
        return 9999

    sorted_groups = sorted(grouped.items(), key=lambda kv: party_key(kv[0]))

    html = "<div style='white-space: pre; font-family: monospace;'>"
    for group, entries in sorted_groups:
        # crear diccionario rápido para acceder por sufijo
        lookup = {}
        for label, value in entries:
            suf = " ".join(label.split()[1:]).strip()  # p.e. 'Config'
            lookup[suf] = value

        html += "\n🔹 <b>{}</b>\n".format(group)
        for suf, display in order:
            if suf in lookup:
                icon = "📞" if "DTMF" in group else "🔧"
                html += "   {} {}: {}\n".format(icon, display, lookup[suf])
    html += "</div>"
    return html

class CucmEnumHoverListener(sublime_plugin.EventListener):
    def on_hover(self, view, point, hover_zone):
        try:
            if hover_zone != sublime.HOVER_TEXT:
                return
            if view.is_scratch() or view.settings().get("is_widget"):
                return

            line_region = view.line(point)
            line_text = view.substr(line_region)

            # localizar regiones DTMF balanceadas dentro de la línea
            dtmf_regions = []
            for m in re.finditer(r'party\d+DTMF\(', line_text):
                rel_start = m.start()
                idx = m.end()
                depth = 1
                while idx < len(line_text) and depth > 0:
                    ch = line_text[idx]
                    if ch == '(':
                        depth += 1
                    elif ch == ')':
                        depth -= 1
                    idx += 1
                if depth == 0:
                    dtmf_regions.append((rel_start, idx))

            rel_point = point - line_region.begin()

            inside = False
            for s, e in dtmf_regions:
                if s <= rel_point < e:
                    inside = True
                    break

            if not inside:
                return

            explanation_dict = parse_dtmf_block(line_text) or {}
            if explanation_dict:
                html = format_popup(explanation_dict)
                view.show_popup(
                    html,
                    flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
                    location=point,
                    max_width=600
                )
                sublime.status_message("CUCM DTMF: información mostrada")
        except Exception as e:
            print(">>> on_hover exception:", e)
            sublime.status_message("CUCM DTMF: excepción (ver consola)")
