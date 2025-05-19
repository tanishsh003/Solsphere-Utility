import platform
import os
import subprocess
import json
import time
import logging
import requests
import signal
from datetime import datetime

API_ENDPOINT = "http://localhost:3000/api/sysutil"
CHECK_INTERVAL_MIN = 15
STATE_FILE = "system_monitor_last_state.json"
LOG_FILE = "system_monitor.log"
MAX_SLEEP_MINUTES = 10

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s %(message)s')

def run_command(cmd, shell=True, timeout=30):
    try:
        result = subprocess.run(cmd, shell=shell, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", -1

def check_disk_encryption():
    os_type = platform.system()
    if os_type == "Darwin":
        out, _, _ = run_command("fdesetup status")
        return "Enabled" if "On" in out else "Disabled"
    elif os_type == "Windows":
        cmd = "(Get-BitLockerVolume -MountPoint $env:SystemDrive).ProtectionStatus"
        out, _, _ = run_command(f"powershell -Command \"{cmd}\"")
        return "Enabled" if out.strip() == "1" else "Disabled"
    elif os_type == "Linux":
        out, _, code = run_command("lsblk | grep crypt")
        return "Enabled" if code == 0 else "Disabled"
    return "Unknown"

def check_os_update_status():
    os_type = platform.system()
    if os_type == "Darwin":
        out, _, _ = run_command("softwareupdate -l")
        return "Up-to-date" if "No new software" in out else "Updates available"
    elif os_type == "Windows":
        cmd = "Get-WindowsUpdateLog"
        out, _, _ = run_command(f"powershell -Command \"{cmd}\"")
        return "Updates available" if "update" in out.lower() else "Likely up-to-date"
    elif os_type == "Linux":
        out, _, _ = run_command("apt list --upgradable 2>/dev/null | grep -v Listing | wc -l")
        return "Up-to-date" if out.strip() == "0" else f"Updates available ({out.strip()} packages)"
    return "Unknown"

def check_antivirus_status():
    os_type = platform.system()
    if os_type == "Windows":
        cmd = "Get-CimInstance -Namespace root\\SecurityCenter2 -ClassName AntivirusProduct | Select-Object displayName"
        out, _, _ = run_command(f"powershell -Command \"{cmd}\"")
        return {"presence": "Detected", "details": out.strip()} if out else {"presence": "Not found", "details": "None detected"}
    elif os_type == "Darwin":
        out, _, _ = run_command("ps aux | grep -E 'Sophos|Avast|Malwarebytes|ESET|Bitdefender' | grep -v grep")
        return {"presence": "Detected", "details": out.split('\n')[0]} if out else {"presence": "Not found", "details": "None detected"}
    elif os_type == "Linux":
        out, _, _ = run_command("ps aux | grep -E 'clamd|clamav|sophos' | grep -v grep")
        return {"presence": "Detected", "details": out.split('\n')[0]} if out else {"presence": "Not found", "details": "None detected"}
    return {"presence": "Unknown", "details": "Platform not supported"}

def check_sleep_settings():
    os_type = platform.system()
    minutes = -1
    if os_type == "Darwin":
        out, _, _ = run_command("pmset -g | grep displaysleep")
        parts = out.split()
        if len(parts) > 1:
            minutes = int(parts[1])
    elif os_type == "Windows":
        cmd = "(powercfg /q | Select-String -Pattern 'VIDEOIDLE' -Context 0,1)"
        out, _, _ = run_command(f"powershell -Command \"{cmd}\"")
        if out:
            try:
                minutes = int(out.strip(), 16) // 60
            except Exception:
                pass
    elif os_type == "Linux":
        out, _, _ = run_command("gsettings get org.gnome.settings-daemon.plugins.power sleep-inactive-ac-timeout")
        if out.isdigit():
            minutes = int(out.strip()) // 60
    compliance = "Compliant" if 0 < minutes <= MAX_SLEEP_MINUTES else "Non-compliant"
    return {"compliance_status": compliance, "configured_minutes": minutes}

def get_system_state():
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "os_type": platform.system(),
        "hostname": platform.node(),
        "disk_encryption": check_disk_encryption(),
        "os_update_status": check_os_update_status(),
        "antivirus_info": check_antivirus_status(),
        "inactivity_sleep_settings": check_sleep_settings()
    }

def states_are_equal(s1, s2):
    def scrub(state):
        return {k: v for k, v in state.items() if k not in ["timestamp", "hostname"]}
    return scrub(s1) == scrub(s2)

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except:
        return None

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def send_to_api(data):
    try:
        response = requests.post(API_ENDPOINT, json=data, timeout=20)
        logging.info(f"Sent to API, response: {response.status_code}")
        return 200 <= response.status_code < 300
    except Exception as e:
        logging.error(f"API send error: {e}")
        return False

def main():
    logging.info("System utility started.")
    should_exit = False

    def signal_handler(sig, frame):
        nonlocal should_exit
        should_exit = True
        logging.info("Received shutdown signal.")
        print("Exiting...")

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    previous_state = load_state()

    while not should_exit:
        current_state = get_system_state()
        if previous_state is None or not states_are_equal(previous_state, current_state):
            logging.info("System state changed or first run.")
            if send_to_api(current_state):
                save_state(current_state)
                previous_state = current_state
        else:
            logging.info("No system state change detected.")
        for _ in range(CHECK_INTERVAL_MIN * 60):
            if should_exit:
                break
            time.sleep(1)

if __name__ == "__main__":
    main()
