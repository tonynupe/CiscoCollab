import re

def explain_enum(category, value):
    enums = {
        "DTMFConfig": {
            1: "BestEffort",
            2: "Prefer OOB",
            3: "Prefer RFC2833",
            4: "Prefer Both"
        },
        "DTMFMethod": {
            0: "No DTMF",
            1: "OOB",
            2: "RFC2833",
            3: "OOB + RFC2833",
            4: "Unknown"
        },
        "ReconnectCauseCode": {
            0: "Unknown",
            1: "Zero Cap Count",
            2: "Mismatch Capabilities",
            3: "DTMF Mismatch",
            4: "Deallocate MTP for Early Offer",
            5: "Modified Capabilities",
            6: "Agent Change"
        },
        "SsRejectionCause": {
            0: "No Cause",
            1: "Destination Not Available",
            2: "Destination In Use",
            3: "Not Enough Bandwidth",
            4: "Precedence Call Blocked",
            5: "Device Not Preemptable",
            6: "Unallocated Number",
            7: "No Answer From User"
        },
        "InsertMediaError": {
            0: "No Error",
            1: "Protocol Error",
            2: "Unknown Destination",
            3: "Unrecognized Manager",
            4: "Destination Busy",
            5: "Destination Out of Order",
            6: "Media Already Connected",
            7: "Unable to Allocate Resource",
            8: "Media Connection Error",
            9: "Media Disconnect Error",
            10: "Suppress MOH",
            11: "Unknown Media Error",
            12: "Unknown Party",
            13: "Pending Transaction",
            14: "Incompatible State",
            15: "Party Is Holding",
            16: "Unknown Media Type"
        },
        "BATJobStatus": {
            1: "Pending",
            2: "Stop Requested",
            3: "Processing",
            4: "Completed",
            5: "Incomplete",
            6: "Hold"
        },
        "StationConnectionError": {
            0: "Device Initiated Reset",
            1: "SCCP Device Throttling",
            2: "KeepAlive Timeout",
            3: "DB Change Notify",
            4: "Registration Superseded",
            5: "Deep Sleep",
            6: "Registration Sequence Error",
            7: "Invalid Capabilities",
            8: "Socket Broken",
            9: "Unspecified"
        },
        "AllocateMtpResourceErr": {
            1: "Mismatch Device Capabilities",
            2: "Not Enough Resources",
            4: "Codec Mismatch",
            8: "No RSVP Capability",
            16: "No Passthru Capability",
            32: "Codec Mismatch A",
            64: "Codec Mismatch B"
        },
        "MTPInsertionReason": {
            0: "None",
            1: "Capability Mismatch",
            2: "Configured to Insert",
            3: "Saved Connection",
            4: "Provide OOB Set",
            5: "RSVP with Xcoder"
        },
        "EarlyOfferType": {
            0: "None",
            1: "G.Clear",
            2: "Voice + Video",
            3: "G.Clear + Voice + Video",
            4: "Best Effort Voice + Video",
            5: "Best Effort + G.Clear + Voice + Video"
        },
        "MediaRequirements": {
            0: "No Requirements",
            1: "Requires MTP",
            2: "Requires RFC2833 MTP",
            3: "Requires MTP + TRP",
            4: "Requires RFC2833 MTP + TRP",
            5: "Requires RFC2833 + TRP",
            6: "Use TRP",
            7: "Disable Audio Passthru"
        },
        "MediaResourceType": {
            1: "MTP",
            2: "Transcoder",
            3: "Conference Bridge",
            4: "Music On Hold",
            5: "Monitor Bridge",
            6: "Recorder",
            7: "Annunciator",
            8: "Built-in Bridge",
            9: "RSVP Agent"
        }
    }
    return enums.get(category, {}).get(value, f"{value} (no definido)")

def parse_dtmf_block(line):
    output = {}
    blocks = re.findall(r'party\dDTMF\((?:[^\(\)]|\([^\(\)]*\))*\)', line)
    for block in blocks:
        label_match = re.match(r'(party\dDTMF)', block)
        label = label_match.group(1) if label_match else "partyXDTMF"
        match = re.search(r'party\dDTMF\((\d+)\s+(\d+)\s+\(([^)]*)\)\s+(\d+)\s+(\d+)\)', block)
        if match:
            config, method, payload_raw, want_recv, provide_oob = match.groups()
            payload = payload_raw.strip()
            payload_value = payload.split(":")[0] if payload else None
            output[f"{label} Config"] = explain_enum("DTMFConfig", int(config))
            output[f"{label} Method"] = explain_enum("DTMFMethod", int(method))
            output[f"{label} Payload"] = payload_value if payload_value else "—"
            output[f"{label} Wants Reception"] = "Yes" if int(want_recv) else "No"
            output[f"{label} Provides OOB"] = "Yes" if int(provide_oob) else "No"
    return output if output else None

def parse_mtp_block(line):
    matches = re.findall(r'MTP\((\d+),(\d+)\)', line)
    output = {}
    for i, (a, b) in enumerate(matches):
        output[f"MTP Side A [{i}]"] = explain_enum("MediaRequirements", int(a))
        output[f"MTP Side B [{i}]"] = explain_enum("MediaRequirements", int(b))
    return output if output else None

def parse_xfermode_block(line):
    matches = re.findall(r'xferMode\((\d+),(\d+)\)', line)
    output = {}
    for i, (a, b) in enumerate(matches):
        output[f"xferMode Side A [{i}]"] = explain_enum("EarlyOfferType", int(a))
        output[f"xferMode Side B [{i}]"] = explain_enum("EarlyOfferType", int(b))
    return output if output else None

def format_popup(title, items):
    grouped = {}
    for label, value in items.items():
        key = label.split()[0]
        grouped.setdefault(key, []).append((label, value))

    html = f"<b>{''}</b><br><div style='white-space: pre; font-family: monospace;'>"
    for group, entries in grouped.items():
        html += f"\n🔹 <b>{group}</b>\n"
        for label, value in entries:
            icon = "📞" if "DTMF" in label else "🔧"
            html += f"   {icon} {label.split(':')[0].replace(group, '').strip()}: {value}\n"
    return html
