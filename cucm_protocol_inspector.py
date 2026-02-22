import re
import sublime
import sublime_plugin

DEBUG_LOG = False


def _debug(msg):
    if DEBUG_LOG:
        print(msg)


_debug(">>> cucm_dtmf_hover module loaded (py3.3 compatible, ordered by party, no title)")

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

Q850_CAUSES = {
    1: ("Unallocated Number", "Destination cannot be reached because the number is unassigned."),
    2: ("No Route To Transit Network", "Call asked to route through an unrecognized intermediate network."),
    3: ("No Route To Destination", "Called party cannot be reached via the selected network path."),
    4: ("Send Special Information Tone", "Long-term condition; SIT tone should be returned."),
    5: ("Misdialed Trunk Prefix", "Called number contains an erroneous trunk prefix."),
    6: ("Channel Unacceptable", "Identified channel is not acceptable for this call."),
    7: ("Call Delivered In Established Channel", "Call delivered using an already-established channel."),
    8: ("Preemption", "Call was preempted (typically emergency priority)."),
    9: ("Preemption, Circuit Reserved", "Call preempted and circuit reserved for reuse."),
    16: ("Normal Call Clearing", "Call cleared normally because one party ended the call."),
    17: ("User Busy", "Called party cannot accept another call (busy)."),
    18: ("No User Responding", "No alerting/connect response within allowed time."),
    19: ("No Answer (User Alerted)", "User was alerted but did not answer in time."),
    20: ("Subscriber Absent", "User not reachable (logged off, out of range, or unavailable)."),
    21: ("Call Rejected", "Called side/network rejected the call despite compatibility."),
    22: ("Number Changed", "Dialed number is no longer assigned."),
    23: ("Redirection To New Destination", "Call is redirected/forwarded to another destination."),
    25: ("Exchange Routing Error", "Intermediate exchange released call (routing/hop issue)."),
    26: ("Nonselected User Clearing", "Called number was not awarded the incoming call."),
    27: ("Destination Out Of Order", "Destination interface/signaling path not functioning correctly."),
    28: ("Invalid Number Format", "Called number format is invalid or incomplete."),
    29: ("Facility Rejected", "Requested supplementary service cannot be provided."),
    30: ("Response To STATUS ENQUIRY", "STATUS cause associated to prior STATUS ENQUIRY."),
    31: ("Normal, Unspecified", "Normal event with no more specific normal-class cause."),
    34: ("No Circuit/Channel Available", "No suitable circuit/channel currently available."),
    38: ("Network Out Of Order", "Network failure expected to persist for some period."),
    39: ("Permanent Frame Connection Out Of Service", "Permanent frame-mode connection is out of service."),
    40: ("Permanent Frame Connection Operational", "Permanent frame-mode connection is operational."),
    41: ("Temporary Failure", "Temporary network failure likely to clear soon."),
    42: ("Switching Equipment Congestion", "Switching node is experiencing congestion/high traffic."),
    43: ("Access Information Discarded", "Network could not deliver requested access information."),
    44: ("Requested Circuit/Channel Not Available", "Requested circuit/channel cannot be provided."),
    46: ("Precedence Call Blocked", "No preemptive circuits available or equal/higher precedence active."),
    47: ("Resource Unavailable", "Internal resource allocation failure (e.g., memory/socket)."),
    49: ("QoS Unavailable", "Requested quality of service cannot be provided."),
    50: ("Facility Not Subscribed", "Caller requested a service not authorized/subscribed."),
    53: ("Outgoing Calls Barred In CUG", "Outgoing CUG calls are barred for this member."),
    55: ("Incoming Calls Barred In CUG", "Incoming CUG calls are barred for this member."),
    57: ("Bearer Capability Not Authorized", "Bearer capability exists but is not authorized."),
    58: ("Bearer Capability Not Available", "Bearer capability exists but is currently unavailable."),
    62: ("Outgoing Access/Subclass Inconsistency", "Inconsistency in outgoing access info and subscriber class."),
    63: ("Service/Option Not Available, Unspecified", "Service not available and no specific cause applies."),
    65: ("Bearer Capability Not Implemented", "Requested media/bearer capability is not supported."),
    66: ("Channel Type Not Implemented", "Requested channel type is not supported."),
    69: ("Requested Facility Not Implemented", "Requested supplementary service is unsupported."),
    70: ("Restricted Digital Info Bearer Only", "Only restricted bearer available for requested service."),
    79: ("Service/Option Not Implemented, Unspecified", "Service unsupported and no specific cause applies."),
    81: ("Invalid Call Reference", "Message received with call reference not currently in use."),
    82: ("Identified Channel Does Not Exist", "Call attempted on a channel not configured/available."),
    83: ("Suspended Call Exists, Identity Does Not", "Resume attempted with mismatched suspended-call identity."),
    84: ("Call Identity In Use", "Suspended call identity already in use."),
    85: ("No Call Suspended", "Resume requested but no suspended call matches identity."),
    86: ("Call Cleared", "Suspended call identity points to call already cleared."),
    87: ("User Not Member Of CUG", "Called user not member of specified closed user group."),
    88: ("Incompatible Destination", "Destination cannot support requested call compatibility attributes."),
    90: ("Nonexistent CUG", "Specified closed user group does not exist."),
    91: ("Invalid Transit Network Selection", "Transit network identification format is invalid."),
    95: ("Invalid Message", "Protocol entity received an invalid message."),
    96: ("Mandatory IE Missing", "Message is missing required information element(s)."),
    97: ("Message Type Nonexistent/Not Implemented", "Received unsupported or invalid message type."),
    98: ("Message Not Compatible With Call State", "Received message not valid for current call state."),
    99: ("IE/Parameter Nonexistent Or Not Implemented", "Message contains undefined/unsupported IE or parameter."),
    100: ("Invalid IE Contents", "Received IE exists but contents are invalid/unsupported."),
    101: ("Message In Invalid Call State", "Message incompatible with call processing state."),
    102: ("Recovery On Timer Expiry", "Call setup/protocol timer expired during procedures."),
    103: ("Parameter Not Implemented", "Message passed with undefined/unsupported parameter."),
    110: ("Unrecognized Parameter Discarded", "Message discarded due to unrecognized parameter."),
    111: ("Protocol Error, Unspecified", "Protocol error with no more specific cause."),
    127: ("Interworking, Unspecified", "Internal/interworking failure; exact cause cannot be ascertained."),
}

Q850_PATTERNS = [
    re.compile(r'(?i)\breason\s*:\s*q\.?\s*850\s*;\s*cause\s*=\s*(\d{1,3})\b'),
]

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
            _debug(">>> parse_dtmf_block: paréntesis no balanceado en posición {}".format(start))
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
                _debug(">>> parse_dtmf_block: no match en block: {}".format(repr(block)))
                continue

        payload = payload_raw.strip()
        payload_value = payload.split(":", 1)[0] if payload else None

        output["{} Config".format(label)] = explain_enum("DTMFConfig", int(config))
        output["{} Method".format(label)] = CUCM_ENUMS.get("DTMFMethod", {}).get(int(method), "Unknown ({})".format(method))
        output["{} Payload".format(label)] = payload_value if payload_value else "—"
        output["{} Wants Reception".format(label)] = "Yes" if int(want_recv) else "No"
        output["{} Provides OOB".format(label)] = "Yes" if int(provide_oob) else "No"

        _debug(">>> parse_dtmf_block: parsed {} {} {} {} {} {}".format(label, config, method, payload_raw, want_recv, provide_oob))

    return output if output else None


def find_q850_in_line(line_text):
    matches = []
    seen = set()

    for regex in Q850_PATTERNS:
        for m in regex.finditer(line_text):
            try:
                code_text = m.group(1)
                code = int(code_text)
            except Exception:
                continue

            key = (m.start(1), m.end(1), code)
            if key in seen:
                continue

            seen.add(key)
            matches.append({
                "start": m.start(1),
                "end": m.end(1),
                "code": code,
            })

    return matches


def format_q850_popup(code):
    title, description = Q850_CAUSES.get(
        code,
        ("Unknown / Not Mapped", "No description available in bundled Q.850 map."),
    )

    html = "<div style='white-space: pre-wrap; font-family: monospace;'>"
    html += "🔹 <b>Q.850 Cause {}</b>\n".format(code)
    html += "   📌 <b>{}</b>\n".format(title)
    html += "   📝 {}".format(description)
    html += "</div>"
    return html

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
            rel_point = point - line_region.begin()

            q850_matches = find_q850_in_line(line_text)
            for match in q850_matches:
                if match["start"] <= rel_point < match["end"]:
                    html = format_q850_popup(match["code"])
                    view.show_popup(
                        html,
                        flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
                        location=point,
                        max_width=700,
                    )
                    sublime.status_message("CUCM Q.850: información mostrada")
                    return

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
            _debug(">>> on_hover exception: {}".format(e))
            sublime.status_message("CUCM DTMF: excepción (ver consola)")
