import subprocess, psutil, logging

logger = logging.getLogger("jarvis.skills.system_control")

DANGEROUS = {"shutdown", "restart", "lock", "sleep", "hibernate", "mute"}

def execute(action: str) -> str:
    action = action.lower()
    try:
        if action == "status":
            cpu = psutil.cpu_percent(interval=0.5)
            m = psutil.virtual_memory()
            return f"Sistema: CPU {cpu}%, RAM {m.percent}%"
        elif action == "shutdown":
            subprocess.run(["shutdown", "/s", "/t", "10"], capture_output=True)
            return "Spegnimento in 10 secondi."
        elif action == "restart":
            subprocess.run(["shutdown", "/r", "/t", "10"], capture_output=True)
            return "Riavvio in 10 secondi."
        elif action == "lock":
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], capture_output=True)
            return "Workstation bloccata."
        elif action == "volume_up":
            subprocess.run(["powershell", "-NoProfile", "($obj = New-Object -ComObject WScript.Shell).SendKeys([char]175)"], capture_output=True)
            return "Volume aumentato."
        elif action == "volume_down":
            subprocess.run(["powershell", "-NoProfile", "($obj = New-Object -ComObject WScript.Shell).SendKeys([char]174)"], capture_output=True)
            return "Volume diminuito."
        elif action == "mute":
            subprocess.run(["powershell", "-NoProfile", "($obj = New-Object -ComObject WScript.Shell).SendKeys([char]173)"], capture_output=True)
            return "Volume mutato."
        else:
            return f"Azione '{action}' non riconosciuta."
    except Exception as e:
        return f"Errore esecuzione '{action}': {e}"
