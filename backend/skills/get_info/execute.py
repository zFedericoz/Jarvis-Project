import psutil, platform, logging

logger = logging.getLogger("jarvis.skills.get_info")

def execute(type: str = "all") -> str:
    try:
        if type == "cpu":
            return f"CPU: {psutil.cpu_percent(interval=0.5)}% ({psutil.cpu_count()} core)"
        elif type == "ram":
            m = psutil.virtual_memory()
            return f"RAM: {m.percent}% ({m.used//1024**3}GB/{m.total//1024**3}GB)"
        elif type == "disk":
            d = psutil.disk_usage("/")
            return f"DISK: {d.percent}% ({d.used//1024**3}GB/{d.total//1024**3}GB)"
        elif type == "processes":
            procs = sorted(psutil.process_iter(["pid","name","cpu_percent"]), key=lambda p: p.info.get("cpu_percent",0) or 0, reverse=True)[:5]
            return "\n".join(f"  {p.info['pid']} {p.info['name']} CPU:{p.info.get('cpu_percent',0)}%" for p in procs)
        else:
            cpu = psutil.cpu_percent(interval=0.3)
            m = psutil.virtual_memory()
            d = psutil.disk_usage("/")
            return f"Sistema: {platform.system()} {platform.release()}\nCPU: {cpu}%\nRAM: {m.percent}%\nDISK: {d.percent}%"
    except Exception as e:
        logger.warning(f"get_info fallito: {e}")
        return f"Errore: {e}"
