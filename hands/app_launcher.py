"""
hands/app_launcher.py
App launching logic for Seven v4.0.

Launch priority:
  1. URL detection (http/https/domain)
  2. Special Windows apps (camera, settings, control panel, etc.)
  3. Fast launch table (common apps, hardcoded)
  4. Unified Web Service Registry (200+ canonical cloud services)
  5. App Discovery index (Start Menu + Registry + UWP + PATH + Desktop)
  6. Direct path/exe fallback
  7. AppOpener (last resort, async)

No aliases. Discovery is authoritative.
Public API:
  open_app(app_name) -> bool
  focus_target_window(target, delay) -> None
"""

import os
import re
import threading
import subprocess
import webbrowser
import time
from colorama import Fore
from memory.command_log import command_log
from memory.mood import mood_engine

_CREATE_NO_WINDOW = 0x08000000

# ── Unified Web Service Registry (200+ Popular Services) ─────────────────────
# Canonical sources to handle direct-to-web transitions instantly
WEB_SERVICES = {
    # AI & ML
    "chatgpt": "https://chat.openai.com",
    "claude": "https://claude.ai",
    "gemini": "https://gemini.google.com",
    "perplexity": "https://perplexity.ai",
    "copilot": "https://copilot.microsoft.com",
    "midjourney": "https://midjourney.com",
    "huggingface": "https://huggingface.co",
    "deepseek": "https://deepseek.com",
    "groq": "https://groq.com",
    "mistral": "https://mistral.ai",
    "replicate": "https://replicate.com",
    "openrouter": "https://openrouter.ai",
    "together": "https://together.ai",
    "fireworks": "https://fireworks.ai",
    "cohere": "https://cohere.com",
    "anthropic": "https://anthropic.com",
    "openai": "https://openai.com",
    "ollama": "https://ollama.com",
    "v0": "https://v0.dev",
    "bolt": "https://bolt.new",
    "lovable": "https://lovable.dev",
    "phind": "https://phind.com",
    "poe": "https://poe.com",

    # Design & Creative
    "canva": "https://canva.com",
    "figma": "https://figma.com",
    "dribbble": "https://dribbble.com",
    "behance": "https://behance.net",
    "photopea": "https://photopea.com",
    "unsplash": "https://unsplash.com",
    "pexels": "https://pexels.com",
    "pixabay": "https://pixabay.com",
    "freepik": "https://freepik.com",
    "pinterest": "https://pinterest.com",
    "lottiefiles": "https://lottiefiles.com",
    "removebg": "https://remove.bg",
    "photoroom": "https://photoroom.com",
    "spline": "https://spline.design",
    "sketch": "https://sketch.com",
    "invision": "https://invisionapp.com",
    "adobespark": "https://spark.adobe.com",
    "creativecloud": "https://creativecloud.adobe.com",

    # Developer Platforms & Hosting
    "github": "https://github.com",
    "gitlab": "https://gitlab.com",
    "bitbucket": "https://bitbucket.org",
    "vercel": "https://vercel.com",
    "netlify": "https://netlify.com",
    "render": "https://render.com",
    "supabase": "https://supabase.com",
    "firebase": "https://firebase.google.com",
    "heroku": "https://heroku.com",
    "railway": "https://railway.app",
    "fly": "https://fly.io",
    "digitalocean": "https://digitalocean.com",
    "linode": "https://linode.com",
    "cloudflare": "https://cloudflare.com",
    "aws": "https://aws.amazon.com",
    "azure": "https://portal.azure.com",
    "gcp": "https://console.cloud.google.com",
    "datadog": "https://datadoghq.com",
    "sentry": "https://sentry.io",
    "logrocket": "https://logrocket.com",
    "postman": "https://postman.com",
    "hoppscotch": "https://hoppscotch.io",
    "ngrok": "https://ngrok.com",
    "tailscale": "https://tailscale.com",
    "auth0": "https://auth0.com",
    "clerk": "https://clerk.com",
    "mongodb": "https://mongodb.com",
    "planetscale": "https://planetscale.com",
    "neon": "https://neon.tech",
    "upstash": "https://upstash.com",
    "redis": "https://redis.com",
    "hasura": "https://hasura.io",
    "prisma": "https://prisma.io",
    "docker": "https://docker.com",
    "kubernetes": "https://kubernetes.io",
    "npm": "https://npmjs.com",
    "pypi": "https://pypi.org",
    "crates": "https://crates.io",
    "godaddy": "https://godaddy.com",
    "namecheap": "https://namecheap.com",

    # Communication & Collaboration
    "slack": "https://slack.com",
    "discord": "https://discord.com",
    "telegram": "https://web.telegram.org",
    "whatsapp": "https://web.whatsapp.com",
    "teams": "https://teams.microsoft.com",
    "zoom": "https://zoom.us",
    "meet": "https://meet.google.com",
    "skype": "https://skype.com",
    "webex": "https://webex.com",
    "gather": "https://gather.town",
    "loom": "https://loom.com",

    # Productivity, Docs & SaaS
    "notion": "https://notion.so",
    "trello": "https://trello.com",
    "asana": "https://asana.com",
    "monday": "https://monday.com",
    "clickup": "https://clickup.com",
    "jira": "https://jira.atlassian.com",
    "confluence": "https://confluence.atlassian.com",
    "linear": "https://linear.app",
    "todoist": "https://todoist.com",
    "ticktick": "https://ticktick.com",
    "basecamp": "https://basecamp.com",
    "evernote": "https://evernote.com",
    "obsidian": "https://obsidian.md",
    "dropbox": "https://dropbox.com",
    "onedrive": "https://onedrive.live.com",
    "box": "https://box.com",
    "google-drive": "https://drive.google.com",
    "google-docs": "https://docs.google.com",
    "google-sheets": "https://sheets.google.com",
    "google-slides": "https://slides.google.com",
    "google-calendar": "https://calendar.google.com",
    "google-mail": "https://mail.google.com",
    "gmail": "https://mail.google.com",
    "outlook": "https://outlook.live.com",
    "protonmail": "https://proton.me",
    "zoho": "https://zoho.com",
    "superhuman": "https://superhuman.com",
    "miro": "https://miro.com",
    "mural": "https://mural.co",
    "lucidchart": "https://lucidchart.com",
    "typeform": "https://typeform.com",
    "tally": "https://tally.so",
    "surveymonkey": "https://surveymonkey.com",
    "docusign": "https://docusign.com",
    "pandadoc": "https://pandadoc.com",
    "notion-so": "https://notion.so",

    # Social & Media Platforms
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "linkedin": "https://linkedin.com",
    "facebook": "https://facebook.com",
    "instagram": "https://instagram.com",
    "threads": "https://threads.net",
    "reddit": "https://reddit.com",
    "youtube": "https://youtube.com",
    "twitch": "https://twitch.tv",
    "vimeo": "https://vimeo.com",
    "tiktok": "https://tiktok.com",
    "pinterest": "https://pinterest.com",
    "tumblr": "https://tumblr.com",
    "medium": "https://medium.com",
    "substack": "https://substack.com",
    "devto": "https://dev.to",
    "hashnode": "https://hashnode.com",
    "quora": "https://quora.com",
    "bluesky": "https://bsky.app",
    "mastodon": "https://joinmastodon.org",

    # Entertainment & Streaming
    "netflix": "https://netflix.com",
    "primevideo": "https://primevideo.com",
    "disneyplus": "https://disneyplus.com",
    "hulu": "https://hulu.com",
    "hbo": "https://max.com",
    "max": "https://max.com",
    "peacock": "https://peacocktv.com",
    "crunchyroll": "https://crunchyroll.com",
    "spotify": "https://open.spotify.com",
    "soundcloud": "https://soundcloud.com",
    "bandcamp": "https://bandcamp.com",
    "deezer": "https://deezer.com",
    "tidal": "https://tidal.com",
    "applemusic": "https://music.apple.com",
    "youtubemusic": "https://music.youtube.com",
    "steam": "https://store.steampowered.com",
    "epicgames": "https://epicgames.com",
    "gog": "https://gog.com",
    "itch": "https://itch.io",
    "chess": "https://chess.com",
    "lichess": "https://lichess.org",

    # Finance, Commerce & Billing
    "stripe": "https://stripe.com",
    "razorpay": "https://razorpay.com",
    "paypal": "https://paypal.com",
    "amazon": "https://amazon.com",
    "ebay": "https://ebay.com",
    "shopify": "https://shopify.com",
    "aliexpress": "https://aliexpress.com",
    "etsy": "https://etsy.com",
    "target": "https://target.com",
    "walmart": "https://walmart.com",
    "bestbuy": "https://bestbuy.com",
    "gumroad": "https://gumroad.com",
    "lemonsqueezy": "https://lemonsqueezy.com",
    "kofi": "https://ko-fi.com",
    "patreon": "https://patreon.com",
    "buymeacoffee": "https://buymeacoffee.com",
    "stripe-dashboard": "https://dashboard.stripe.com",

    # Reference & Tools
    "wikipedia": "https://wikipedia.org",
    "wolframalpha": "https://wolframalpha.com",
    "google": "https://google.com",
    "bing": "https://bing.com",
    "duckduckgo": "https://duckduckgo.com",
    "yahoo": "https://yahoo.com",
    "maps": "https://maps.google.com",
    "translate": "https://translate.google.com",
    "weather": "https://weather.com",
    "speedtest": "https://speedtest.net",
    "archive": "https://archive.org",
    "github-gist": "https://gist.github.com",
    "stackoverflow": "https://stackoverflow.com",
}


# ── Fast launch table ─────────────────────────────────────────────────
_FAST_LAUNCH = {
    "chrome":       ("exe", "chrome"),
    "firefox":      ("exe", "firefox"),
    "edge":         ("uri", "microsoft-edge:"),
    "notepad":      ("exe", "notepad"),
    "notepad++":    ("exe", "notepad++"),
    "vlc":          ("exe", "vlc"),
    "spotify":      ("uri", "spotify:"),
    "telegram":     ("exe", "telegram"),
    "discord":      ("exe", "discord"),
    "steam":        ("exe", "steam"),
    "vs code":      ("exe", "code"),
    "vscode":       ("exe", "code"),
    "code":         ("exe", "code"),
    "word":         ("exe", "winword"),
    "excel":        ("exe", "excel"),
    "powerpoint":   ("exe", "powerpnt"),
    "paint":        ("exe", "mspaint"),
    "cmd":          ("exe", "cmd"),
    "terminal":     ("exe", "wt"),
    "powershell":   ("exe", "powershell"),
    "task manager": ("exe", "taskmgr"),
    "obs":          ("exe", "obs64"),
    "zoom":         ("exe", "zoom"),
    "teams":        ("uri", "msteams:"),
    "outlook":      ("exe", "outlook"),
    "file manager": ("exe", "explorer"),
    "files":        ("exe", "explorer"),
}

# -- Special Windows folder shortcuts --
_SPECIAL_FOLDERS = {}


def _init_special_folders():
    """Build folder shortcuts from real user profile paths."""
    home = os.path.expanduser("~")
    mapping = {
        "downloads":       os.path.join(home, "Downloads"),
        "download":        os.path.join(home, "Downloads"),
        "documents":       os.path.join(home, "Documents"),
        "document":        os.path.join(home, "Documents"),
        "pictures":        os.path.join(home, "Pictures"),
        "picture":         os.path.join(home, "Pictures"),
        "photos":          os.path.join(home, "Pictures"),
        "videos":          os.path.join(home, "Videos"),
        "video":           os.path.join(home, "Videos"),
        "music":           os.path.join(home, "Music"),
        "desktop":         os.path.join(home, "Desktop"),
        "screenshots":     os.path.join(home, "Pictures", "Screenshots"),
        "screenshot":      os.path.join(home, "Pictures", "Screenshots"),
        "recordings":      os.path.join(home, "Videos", "Recordings"),
        "captures":        os.path.join(home, "Videos", "Captures"),
        "onedrive":        os.path.join(home, "OneDrive"),
        "recent":          "shell:recent",
        "startup":         "shell:startup",
        "appdata":         os.path.join(home, "AppData"),
        "local appdata":   os.path.join(home, "AppData", "Local"),
        "roaming":         os.path.join(home, "AppData", "Roaming"),
        "temp":            os.path.join(home, "AppData", "Local", "Temp"),
    }
    for key, path in mapping.items():
        if path.startswith("shell:"):
            _SPECIAL_FOLDERS[key] = path
        elif os.path.exists(path):
            _SPECIAL_FOLDERS[key] = path


_init_special_folders()


def focus_target_window(target, delay=0.5):
    """
    Spawns a background worker thread to pull the target process window,
    file viewer, folder container, or web browser window to the foreground.
    Strictly filters out Seven's own processes and windows.
    """
    t = threading.Thread(target=_focus_worker, args=(target, delay), daemon=True)
    t.start()


def _focus_worker(target, delay):
    import time
    try:
        import win32gui
        import win32process
        import win32con
        import psutil
    except ImportError:
        return

    time.sleep(delay)

    # 1. Gather all running PIDs for Seven's own processes to filter them out
    seven_pids = set()
    current_pid = os.getpid()
    seven_pids.add(current_pid)
    for p in psutil.process_iter(['pid', 'name']):
        try:
            p_name = p.info['name'].lower()
            if "seven" in p_name or "electron" in p_name:
                seven_pids.add(p.info['pid'])
        except Exception:
            pass

    # 2. Enumerate visible windows
    hwnds = []
    def enum_cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
            hwnds.append(hwnd)
        return True

    try:
        win32gui.EnumWindows(enum_cb, None)
    except Exception:
        return

    target_hwnd = None

    # Case A: target is a Popen object
    if hasattr(target, 'pid'):
        target_pid = target.pid
        for hwnd in hwnds:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid == target_pid:
                if pid not in seven_pids:
                    target_hwnd = hwnd
                    break

    # Case B: target is a local file or folder path
    elif isinstance(target, str) and (os.path.exists(target) or "\\" in target or "/" in target):
        filename = os.path.basename(target).lower()
        name_no_ext = os.path.splitext(filename)[0]

        for hwnd in hwnds:
            title = win32gui.GetWindowText(hwnd).lower()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid in seven_pids:
                continue
            if filename in title or (len(name_no_ext) > 3 and name_no_ext in title):
                target_hwnd = hwnd
                break

    # Case C: target is a web link or domain
    elif isinstance(target, str) and (target.startswith("http") or "://" in target or any(target.endswith(ext) for ext in [".com", ".org", ".net", ".io", ".dev", ".app"])):
        browser_proc_names = {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe"}
        for hwnd in hwnds:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid in seven_pids:
                continue
            try:
                p = psutil.Process(pid)
                if p.name().lower() in browser_proc_names:
                    target_hwnd = hwnd
                    break
            except Exception:
                pass

    # Fallback Case D: Focus the most recently active non-Seven window if specific target matches failed
    if not target_hwnd:
        for hwnd in hwnds:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid in seven_pids:
                continue
            title = win32gui.GetWindowText(hwnd).lower()
            if "seven" in title or "vite" in title or "electron" in title:
                continue
            target_hwnd = hwnd
            break

    # Attempt to force the window into the foreground using thread inputs
    if target_hwnd:
        try:
            if win32gui.IsIconic(target_hwnd):
                win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
            else:
                win32gui.ShowWindow(target_hwnd, win32con.SW_SHOW)

            win32gui.BringWindowToTop(target_hwnd)

            import win32thread
            fore_hwnd = win32gui.GetForegroundWindow()
            if fore_hwnd != target_hwnd:
                fore_thread = win32process.GetWindowThreadProcessId(fore_hwnd)[0]
                curr_thread = win32thread.GetCurrentThreadId()
                if fore_thread != curr_thread and fore_thread != 0:
                    try:
                        win32thread.AttachThreadInput(curr_thread, fore_thread, True)
                        win32gui.SetForegroundWindow(target_hwnd)
                        win32thread.AttachThreadInput(curr_thread, fore_thread, False)
                    except Exception:
                        win32gui.SetForegroundWindow(target_hwnd)
                else:
                    win32gui.SetForegroundWindow(target_hwnd)
            print(Fore.GREEN + f"[FOCUS] Successfully activated target window: {win32gui.GetWindowText(target_hwnd)}")
        except Exception as e:
            print(Fore.YELLOW + f"[FOCUS] Window force activation error: {e}")


def _fast_launch(app_name: str) -> bool:
    """Try fast launch table. Returns True if launched."""
    clean = app_name.lower().strip()
    entry = _FAST_LAUNCH.get(clean)
    if not entry:
        for key, val in _FAST_LAUNCH.items():
            if key in clean or clean in key:
                entry = val
                break
    if not entry:
        return False

    launch_type, target = entry
    try:
        if launch_type == "uri":
            os.startfile(target)
            focus_target_window(target)
        else:
            try:
                os.startfile(target)
                focus_target_window(target)
            except FileNotFoundError:
                proc = subprocess.Popen(target, creationflags=_CREATE_NO_WINDOW)
                focus_target_window(proc)
        print(Fore.GREEN + f"   -> Fast launch: {target}")
        return True
    except Exception as e:
        print(Fore.YELLOW + f"   -> Fast launch failed: {e}")
        return False


def _launch_via_discovery(app_name: str) -> bool:
    """Query app_discovery index and launch the best match."""
    try:
        from hands.app_discovery import search_apps
        hits = search_apps(app_name, limit=3)
        if not hits:
            return False

        best = hits[0]
        launch_cmd = best["launch"]
        display = best["name"]

        print(Fore.CYAN + f"   -> Discovery match: '{display}' ({best['source']})")

        if launch_cmd.startswith("explorer.exe shell:AppsFolder"):
            proc = subprocess.Popen(launch_cmd, shell=True, creationflags=_CREATE_NO_WINDOW)
            focus_target_window(proc)
        elif launch_cmd.endswith(".lnk"):
            os.startfile(launch_cmd)
            focus_target_window(launch_cmd)
        else:
            proc = subprocess.Popen(launch_cmd, shell=True, creationflags=_CREATE_NO_WINDOW)
            focus_target_window(proc)

        print(Fore.GREEN + f"   -> Launched via discovery: {display}")
        return True

    except Exception as e:
        print(Fore.YELLOW + f"   -> Discovery launch failed: {e}")
        return False


def open_app(app_name: str) -> bool:
    """
    Launch an application by name.

    Priority:
      1. URL detection
      2. Special Windows apps (camera, settings, etc.)
      3. Fast launch table
      4. Unified Web Service Registry (Canva, Figma, etc.)
      5. App Discovery index
      6. Direct path/exe
      7. AppOpener (last resort, async)

    Returns True if launch was initiated.
    """
    original = app_name.lower().strip()
    clean = original.replace("activated", "").replace("!", "").strip()

    # Suffix browser force checks
    force_browser = False
    if "in browser" in clean:
        force_browser = True
        clean = clean.replace("in browser", "").strip()

    # ── 1. URL detection ────────────────────────────────────────
    if (any(clean.startswith(p) for p in ['http://', 'https://'])
            or any(clean.endswith(d) for d in
                   ['.com', '.org', '.net', '.io', '.dev', '.app', '.co'])):
        url = clean if clean.startswith('http') else f'https://{clean}'
        webbrowser.open(url)
        focus_target_window(url)
        command_log.log_command("OPEN", clean, True, f"URL: {url}")
        mood_engine.on_command_result(True)
        return True

    # ── 1b. Drive open (e.g. "open disk M", "open drive D") ─────
    drive_match = re.match(r'^(?:disk|drive)\s+([a-z])$', clean)
    if drive_match:
        drive_letter = drive_match.group(1).upper()
        drive_path = f"{drive_letter}:\\"
        if os.path.exists(drive_path):
            proc = subprocess.Popen(f'explorer "{drive_path}"', shell=True)
            focus_target_window(drive_path)
            command_log.log_command("OPEN", clean, True, f"Drive: {drive_path}")
            mood_engine.on_command_result(True)
            return True

    # ── 1c. Special folder shortcuts ────────────────────────────
    _folder_clean = clean.replace(" folder", "").replace(" directory", "").strip()
    if _folder_clean in _SPECIAL_FOLDERS:
        _fpath = _SPECIAL_FOLDERS[_folder_clean]
        try:
            if _fpath.startswith("shell:"):
                proc = subprocess.Popen(f'explorer {_fpath}', shell=True)
                focus_target_window(_fpath)
            else:
                proc = subprocess.Popen(f'explorer "{_fpath}"', shell=True)
                focus_target_window(_fpath)
            command_log.log_command("OPEN", clean, True, f"Folder: {_fpath}")
            mood_engine.on_command_result(True)
            print(Fore.GREEN + f"   -> Opened folder: {_fpath}")
            return True
        except Exception as e:
            print(Fore.YELLOW + f"   -> Folder open failed: {e}")
    print(Fore.CYAN + f"HANDS: Opening '{clean}'...")

    try:
        # ── 2. Special Windows apps ─────────────────────────────
        if "camera" in clean:
            subprocess.Popen(
                'start microsoft.windows.camera:',
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            def _focus_camera():
                time.sleep(2.0)
                focus_target_window("camera")
            threading.Thread(target=_focus_camera, daemon=True).start()
            command_log.log_command("OPEN", "camera", True, "Windows URI")
            mood_engine.on_command_result(True)
            return True

        if "control panel" in clean:
            proc = subprocess.Popen("control", shell=True)
            focus_target_window(proc)
            command_log.log_command("OPEN", "control panel", True, "Direct")
            mood_engine.on_command_result(True)
            return True

        if "settings" in clean:
            subprocess.Popen(
                ["explorer.exe", "ms-settings:"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            def _focus_settings():
                time.sleep(1.5)
                focus_target_window("settings")
            threading.Thread(target=_focus_settings, daemon=True).start()
            command_log.log_command("OPEN", "settings", True, "Windows URI")
            mood_engine.on_command_result(True)
            return True

        if "calculator" in clean:
            proc = subprocess.Popen("calc", shell=True,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            focus_target_window(proc)
            command_log.log_command("OPEN", "calculator", True, "Direct")
            mood_engine.on_command_result(True)
            return True

        if "notepad" in clean:
            os.startfile("notepad")
            focus_target_window("notepad")
            command_log.log_command("OPEN", "notepad", True, "os.startfile")
            mood_engine.on_command_result(True)
            return True

        if any(x in clean for x in ["explorer", "file explorer", "file manager"]):
            proc = subprocess.Popen("explorer.exe", shell=False)
            focus_target_window(proc)
            command_log.log_command("OPEN", "explorer", True, "subprocess")
            mood_engine.on_command_result(True)
            return True

        if "whatsapp" in clean:
            subprocess.Popen(
                ["explorer.exe", "whatsapp:"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            def _focus_whatsapp():
                time.sleep(1.5)
                focus_target_window("whatsapp")
            threading.Thread(target=_focus_whatsapp, daemon=True).start()
            command_log.log_command("OPEN", "whatsapp", True, "Windows URI")
            mood_engine.on_command_result(True)
            return True

        # ── 3. Fast launch table ────────────────────────────────
        if _fast_launch(clean):
            command_log.log_command("OPEN", clean, True, "FastLaunch")
            mood_engine.on_command_result(True)
            return True

        # ── 4. Unified Web Service Registry (High-Priority Match) ──
        if clean in WEB_SERVICES:
            url = WEB_SERVICES[clean]
            webbrowser.open(url)
            focus_target_window(url)
            command_log.log_command("OPEN", clean, True, f"Web: {url}")
            mood_engine.on_command_result(True)
            return True

        # ── 5. App Discovery index ──────────────────────────────
        if _launch_via_discovery(clean):
            command_log.log_command("OPEN", clean, True, "Discovery")
            mood_engine.on_command_result(True)
            return True

        # ── 6. Direct path/exe ──────────────────────────────────
        if clean.endswith('.exe') or '\\' in clean or '/' in clean:
            try:
                os.startfile(clean)
                focus_target_window(clean)
                command_log.log_command("OPEN", clean, True, "Direct path")
                mood_engine.on_command_result(True)
                return True
            except Exception:
                pass

        # ── 7. AppOpener (last resort, async) ───────────────────
        print(Fore.YELLOW + f"   -> Falling back to AppOpener for '{clean}'...")
        appopener_worked = threading.Event()
        try:
            from AppOpener import open as app_opener

            def _async_appopener():
                try:
                    app_opener(clean, match_closest=True, throw_error=True)
                    focus_target_window(clean)
                    command_log.log_command("OPEN", clean, True, "AppOpener")
                    mood_engine.on_command_result(True)
                    appopener_worked.set()
                except Exception as err:
                    print(Fore.YELLOW + f"   -> AppOpener failed: {err}")

            t = threading.Thread(target=_async_appopener, daemon=True)
            t.start()
            t.join(timeout=3.0)

            if appopener_worked.is_set():
                return True
        except ImportError:
            pass

        # ── 8. Universal URL fallback ───────────────────────────
        if ' ' not in clean and len(clean) >= 3 and clean.isalnum():
            _guess_url = f"https://{clean}.com"
            print(Fore.CYAN + f"   -> Trying universal URL: {_guess_url}")
            webbrowser.open(_guess_url)
            focus_target_window(_guess_url)
            command_log.log_command("OPEN", clean, True, f"Universal URL: {_guess_url}")
            mood_engine.on_command_result(True)
            return True

        print(Fore.RED + f"   -> Cannot find '{clean}' anywhere.")
        command_log.log_command("OPEN", clean, False, "Not found in any source")
        mood_engine.on_command_result(False)
        return False

    except Exception as e:
        print(Fore.RED + f"HANDS: Failed to open '{clean}': {e}")
        command_log.log_command("OPEN", clean, False, str(e))
        mood_engine.on_command_result(False)
        return False