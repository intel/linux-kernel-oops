import re
import sys
import json

def parse_oops(text):
    result = {
        "type": "Unknown",
        "version": None,
        "comm": None,
        "pid": None,
        "cpu": None,
        "tainted": None,
        "rip": None,
        "rsp": None,
        "cr2": None,
        "registers": {},
        "backtrace": [],
        "modules": []
    }

    # Extract version
    version_match = re.search(r"Linux version ([\w\.\-]+)", text)
    if version_match:
        result["version"] = version_match.group(1)

    # Extract Comm, PID, CPU
    comm_match = re.search(r"CPU: (\d+) PID: (\d+) Comm: ([\w\-/]+)", text)
    if comm_match:
        result["cpu"] = comm_match.group(1)
        result["pid"] = comm_match.group(2)
        result["comm"] = comm_match.group(3)

    # Extract Tainted
    taint_match = re.search(r"Tainted: ([\w\s\(\)]+)", text)
    if taint_match:
        result["tainted"] = taint_match.group(1).strip()

    # Extract RIP
    rip_match = re.search(r"RIP: \d+:[<]([0-9a-fA-F]+)[>]", text)
    if rip_match:
        result["rip"] = rip_match.group(1)

    # Extract CR2
    cr2_match = re.search(r"BUG: unable to handle .* at ([0-9a-fA-F]+)", text)
    if cr2_match:
        result["cr2"] = cr2_match.group(1)

    # Extract Registers
    reg_lines = re.findall(r"([A-Z0-9]{2,3}): ([0-9a-fA-F]+)", text)
    for reg, val in reg_lines:
        result["registers"][reg] = val

    # Specific check for CR2 which is often on its own line or part of the BUG line
    cr2_alt = re.search(r"CR2: ([0-9a-fA-F]+)", text)
    if cr2_alt:
        result["cr2"] = cr2_alt.group(1)

    # Extract Call Trace
    trace_started = False
    for line in text.splitlines():
        if "Call Trace:" in line:
            trace_started = True
            continue
        if trace_started:
            if line.strip() == "" or "---[" in line:
                break
            # Match function name
            func_match = re.search(r"\s+[\?]?\s+([\w\.]+)\+0x", line)
            if func_match:
                result["backtrace"].append(func_match.group(1))

    return result

if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r') as f:
            print(json.dumps(parse_oops(f.read()), indent=2))
