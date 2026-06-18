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

IPADDR_PATTERNS = [
    re.compile(r'(?i)\bIpAddr\s*=\s*([0-9a-f]{1,8})\b'),
    re.compile(r"(?i)\bip\s*'([0-9a-f]{8})'h\b"),
]

Q931_MESSAGE_TYPES = {
    0x01: "ALERTING",
    0x02: "CALL PROCEEDING",
    0x03: "PROGRESS",
    0x05: "SETUP",
    0x07: "CONNECT",
    0x0F: "CONNECT ACK",
    0x45: "DISCONNECT",
    0x4D: "RELEASE",
    0x5A: "RELEASE COMPLETE",
    0x62: "FACILITY",
    0x75: "STATUS",
    0x79: "STATUS ENQUIRY",
    0x7B: "INFORMATION",
    0x7D: "NOTIFY",
}

Q931_IE_TYPES = {
    0x04: "Bearer Capability",
    0x08: "Cause",
    0x18: "Channel Identification",
    0x1E: "Progress Indicator",
    0x28: "Display",
    0x34: "Signal",
    0x4C: "Connected Number",
    0x6C: "Calling Party Number",
    0x70: "Called Party Number",
    0x7D: "High Layer Compatibility",
    0x7E: "User-User",
}

HEX_CANDIDATE_PATTERNS = [
    re.compile(r'(?i)(?:0x)?[0-9a-f]{2}(?:[\s:-]+(?:0x)?[0-9a-f]{2}){4,}'),
    re.compile(r'(?i)\b(?:0x)?[0-9a-f]{12,}\b'),
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


def _hex_to_ipv4_pairs(hex_text):
    normalized = (hex_text or "").strip().lower().replace("0x", "")
    if not re.match(r'^[0-9a-f]{1,8}$', normalized):
        return None

    normalized = normalized.zfill(8)
    octets = [int(normalized[i:i + 2], 16) for i in range(0, 8, 2)]
    be_ip = "{}.{}.{}.{}".format(octets[0], octets[1], octets[2], octets[3])
    le_ip = "{}.{}.{}.{}".format(octets[3], octets[2], octets[1], octets[0])

    return {
        "hex": normalized.upper(),
        "be_ip": be_ip,
        "le_ip": le_ip,
    }


def find_hex_ip_at_point(line_text, rel_point):
    for regex in IPADDR_PATTERNS:
        for m in regex.finditer(line_text):
            if m.start() <= rel_point < m.end():
                parsed = _hex_to_ipv4_pairs(m.group(1))
                if parsed:
                    return {
                        "start": m.start(1),
                        "end": m.end(1),
                        "parsed": parsed,
                        "is_ipaddr_field": "IpAddr" in m.group(0),
                    }
    return None


def format_hex_ip_popup(found):
    parsed = found["parsed"]
    primary = parsed["le_ip"] if found.get("is_ipaddr_field") else parsed["be_ip"]
    alternate = parsed["be_ip"] if found.get("is_ipaddr_field") else parsed["le_ip"]
    primary_label = "Little-endian" if found.get("is_ipaddr_field") else "Network order"
    alt_label = "Network order" if found.get("is_ipaddr_field") else "Little-endian"
    network_order = parsed["be_ip"]

    html = "<div style='white-space: pre-wrap; font-family: monospace;'>"
    html += "<b>HEX to IPv4</b>\n"
    html += "HEX: <b>{}</b>\n".format(parsed["hex"])
    html += "OUTPUT ({}) : <span style='color: #1f7a1f;'><b>{}</b></span>\n".format(primary_label, primary)
    html += "Network order: <span style='color: #0b4f9c;'><b>{}</b></span>\n".format(network_order)
    if alt_label.lower() != "network order":
        html += "{}: {}".format(alt_label, alternate)
    html += "</div>"
    return html


def _normalize_hex_bytes(raw_text):
    if not raw_text:
        return []

    # Evita falsos positivos con números decimales largos.
    if not re.search(r'(?i)[a-f]|0x|[\s:-]', raw_text):
        return []

    parts = re.findall(r'(?i)(?:0x)?([0-9a-f]{2})', raw_text)
    output = []
    for p in parts:
        try:
            output.append(int(p, 16))
        except Exception:
            return []
    return output


def find_hex_blob_at_point(line_text, rel_point):
    for regex in HEX_CANDIDATE_PATTERNS:
        for m in regex.finditer(line_text):
            if m.start() <= rel_point < m.end():
                raw = m.group(0)
                data = _normalize_hex_bytes(raw)
                if len(data) >= 5:
                    return {
                        "start": m.start(),
                        "end": m.end(),
                        "raw": raw,
                        "bytes": data,
                    }
    return None


def find_first_hex_blob_in_line(line_text):
    for regex in HEX_CANDIDATE_PATTERNS:
        for m in regex.finditer(line_text):
            raw = m.group(0)
            data = _normalize_hex_bytes(raw)
            if len(data) >= 5:
                return {
                    "start": m.start(),
                    "end": m.end(),
                    "raw": raw,
                    "bytes": data,
                }
    return None


def find_iedata_hex_blob_at_point(line_text, rel_point):
    if "IEData=" not in line_text:
        return None

    m = re.search(r'IEData\s*=\s*(.+)$', line_text)
    if not m:
        return None

    start = m.start(1)
    end = m.end(1)
    # UX: para líneas IEData activamos aunque el cursor esté en cualquier parte de la línea.
    _ = rel_point

    raw = m.group(1).strip()
    data = _normalize_hex_bytes(raw)
    if len(data) < 2:
        return None

    return {
        "start": start,
        "end": end,
        "raw": raw,
        "bytes": data,
    }


def _decode_q931_number_digits(value_bytes):
    # En estos logs CUCM suele venir IA5/ASCII; conservamos bytes imprimibles.
    out = []
    for b in value_bytes:
        if 32 <= b <= 126:
            out.append(chr(b))
    return "".join(out).strip()


def _decode_q931_party_number(value_bytes):
    if not value_bytes:
        return ""

    # Q.931 Party Number IE:
    # - octeto 3 (tipo/plan) siempre presente
    # - octeto 3a (presentation/screening) opcional cuando ext bit del octeto 3 = 0
    start = 1
    if len(value_bytes) >= 2 and (value_bytes[0] & 0x80) == 0:
        start = 2

    return _decode_q931_number_digits(value_bytes[start:])


def decode_q931_ie_hex(byte_list):
    if not byte_list or len(byte_list) < 2:
        return None

    ie_id = byte_list[0]
    ie_len = byte_list[1]
    value = byte_list[2:2 + ie_len]
    if len(value) < ie_len:
        value = byte_list[2:]

    result = {
        "ie_id": ie_id,
        "ie_len": ie_len,
        "ie_label": Q931_IE_TYPES.get(ie_id, "Unknown IE"),
        "text": None,
        "q850_cause": None,
    }

    if ie_id == 0x28 and value:
        # Display IE: texto IA5.
        result["text"] = "".join([chr(b) if 32 <= b <= 126 else "." for b in value])
    elif ie_id in (0x6C, 0x70) and len(value) >= 1:
        result["text"] = _decode_q931_party_number(value)
    elif ie_id == 0x08 and len(value) >= 2:
        cause_code = value[1] & 0x7F
        cause_title, cause_desc = Q850_CAUSES.get(
            cause_code,
            ("Unknown / Not Mapped", "No description available in bundled Q.850 map."),
        )
        result["q850_cause"] = {
            "code": cause_code,
            "title": cause_title,
            "description": cause_desc,
        }

    return result


def decode_h323_q931_hex(byte_list):
    if not byte_list or len(byte_list) < 3:
        return None

    protocol_discriminator = byte_list[0]
    call_ref_len = byte_list[1] & 0x0F
    msg_index = 2 + call_ref_len

    if msg_index >= len(byte_list):
        return None

    call_ref_dir = "Unknown"
    call_ref_value = None
    if call_ref_len > 0:
        first_call_ref_octet = byte_list[2]
        call_ref_dir = "To originating side" if (first_call_ref_octet & 0x80) else "To destination side"
        value = first_call_ref_octet & 0x7F
        idx = 3
        while idx < (2 + call_ref_len) and idx < len(byte_list):
            value = (value << 8) | byte_list[idx]
            idx += 1
        call_ref_value = value

    msg_type = byte_list[msg_index]
    result = {
        "protocol_discriminator": protocol_discriminator,
        "protocol_label": "Q.931 Call Control" if protocol_discriminator == 0x08 else "Unknown",
        "call_ref_len": call_ref_len,
        "call_ref_dir": call_ref_dir,
        "call_ref_value": call_ref_value,
        "msg_type": msg_type,
        "msg_label": Q931_MESSAGE_TYPES.get(msg_type, "Unknown"),
        "q850_cause": None,
    }

    i = msg_index + 1
    while i < len(byte_list):
        ie_id = byte_list[i]

        # Single-octet IEs (bit 8 = 1) no incluyen campo de longitud.
        if ie_id & 0x80:
            i += 1
            continue

        if i + 1 >= len(byte_list):
            break

        ie_len = byte_list[i + 1]
        value_start = i + 2
        value_end = value_start + ie_len
        if value_end > len(byte_list):
            break

        # Cause IE (Q.931 IEI 0x08) contiene causa Q.850 en el segundo octeto.
        if ie_id == 0x08 and ie_len >= 2:
            cause_code = byte_list[value_start + 1] & 0x7F
            cause_title, cause_desc = Q850_CAUSES.get(
                cause_code,
                ("Unknown / Not Mapped", "No description available in bundled Q.850 map."),
            )
            result["q850_cause"] = {
                "code": cause_code,
                "title": cause_title,
                "description": cause_desc,
            }

        i = value_end

    return result


def format_h323_popup(decoded, byte_list):
    byte_preview = " ".join(["{:02X}".format(b) for b in byte_list[:48]])
    if len(byte_list) > 48:
        byte_preview += " ..."

    html = "<div style='white-space: pre-wrap; font-family: monospace;'>"
    html += "<b>H.323 / Q.931 HEX</b>\n"
    html += "Bytes: {}\n".format(len(byte_list))
    html += "PD: 0x{:02X} ({})\n".format(decoded["protocol_discriminator"], decoded["protocol_label"])
    html += "CallRefLen: {}\n".format(decoded["call_ref_len"])

    if decoded["call_ref_value"] is not None:
        html += "CallRef: {} ({})\n".format(decoded["call_ref_value"], decoded["call_ref_dir"])

    html += "MsgType: 0x{:02X} ({})\n".format(decoded["msg_type"], decoded["msg_label"])

    cause = decoded.get("q850_cause")
    if cause:
        html += "\nQ.850 Cause {}: {}\n".format(cause["code"], cause["title"])
        html += "{}\n".format(cause["description"])

    html += "\nHEX: {}".format(byte_preview)
    html += "</div>"
    return html


def format_q931_ie_popup(decoded, byte_list, ie_name_hint=None):
    byte_preview = " ".join(["{:02X}".format(b) for b in byte_list[:48]])
    if len(byte_list) > 48:
        byte_preview += " ..."

    html = "<div style='white-space: pre-wrap; font-family: monospace;'>"
    html += "<b>Q.931 IE HEX</b>\n"
    if ie_name_hint:
        html += "Line IE: {}\n".format(ie_name_hint)
    html += "IEI: 0x{:02X} ({})\n".format(decoded["ie_id"], decoded["ie_label"])
    html += "Length: {}\n".format(decoded["ie_len"])

    if decoded.get("text"):
        text_label = "Decoded text"
        if decoded.get("ie_id") == 0x6C:
            text_label = "Calling number"
        elif decoded.get("ie_id") == 0x70:
            text_label = "Called number"
        elif decoded.get("ie_id") == 0x28:
            text_label = "Display text"

        html += "{}: <span style='color: #1f7a1f;'><b>{}</b></span>\n".format(text_label, decoded["text"])

    cause = decoded.get("q850_cause")
    if cause:
        html += "\nQ.850 Cause {}: {}\n".format(cause["code"], cause["title"])
        html += "{}\n".format(cause["description"])

    html += "\nHEX: {}".format(byte_preview)
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

            ip_hit = find_hex_ip_at_point(line_text, rel_point)
            if ip_hit:
                html = format_hex_ip_popup(ip_hit)
                view.show_popup(
                    html,
                    flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
                    location=point,
                    max_width=600,
                )
                sublime.status_message("CUCM HEX IP: información mostrada")
                return

            hex_blob = find_hex_blob_at_point(line_text, rel_point)
            if (not hex_blob) and ("IsdnMsgData" in line_text):
                hex_blob = find_first_hex_blob_in_line(line_text)
            if hex_blob:
                decoded = decode_h323_q931_hex(hex_blob["bytes"])
                if decoded and decoded["protocol_discriminator"] == 0x08:
                    html = format_h323_popup(decoded, hex_blob["bytes"])
                    view.show_popup(
                        html,
                        flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
                        location=point,
                        max_width=760,
                    )
                    sublime.status_message("CUCM H.323 HEX: información mostrada")
                    return

            ie_blob = find_iedata_hex_blob_at_point(line_text, rel_point)
            if ie_blob:
                ie_name_match = re.search(r'\bIe\s*-\s*([^\-]+?)\s*--', line_text)
                ie_name = ie_name_match.group(1).strip() if ie_name_match else None
                ie_decoded = decode_q931_ie_hex(ie_blob["bytes"])
                if ie_decoded:
                    html = format_q931_ie_popup(ie_decoded, ie_blob["bytes"], ie_name)
                    view.show_popup(
                        html,
                        flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
                        location=point,
                        max_width=760,
                    )
                    sublime.status_message("CUCM Q.931 IE: información mostrada")
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
