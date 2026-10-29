#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tasmota Speaker Guard
---------------------
Surveille l'activité audio en temps réel (Windows, Linux, macOS) et pilote
automatiquement une ou plusieurs prises connectées Tasmota :
- Allumage instantané dès qu'un flux audio est détecté (WASAPI, ASIO direct, PulseAudio, PipeWire, CoreAudio).
- Prise en charge des applications directes ASIO (Rocksmith, DAW Reaper/FL/Ableton, plugins guitare...).
- Extinction automatique après X minutes d'inactivité continue (par défaut 10 min).
- Extinction garantie à l'arrêt/redémarrage du PC ou fermeture de session.
- Support multi-prises (liste d'adresses IP Tasmota simultanées).
"""

import os
import sys
import time
import json
import logging
import signal
import atexit
import fnmatch
import argparse
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Tuple, List, Dict, Set

# Requêtes HTTP
import requests

# Détection de l'OS
IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
IS_MACOS = sys.platform == "darwin"

# Importations conditionnelles Windows
if IS_WINDOWS:
    import winreg
    import ctypes
    import ctypes.wintypes
    import comtypes
    from pycaw.pycaw import AudioUtilities, IAudioMeterInformation

    try:
        import win32gui
        import win32con
        import win32api
        HAS_WIN32 = True
    except ImportError:
        HAS_WIN32 = False
else:
    HAS_WIN32 = False

# Répertoire du script
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_FILE = SCRIPT_DIR / "config.json"


# ==============================================================================
# CONFIGURATION
# ==============================================================================

def get_default_config() -> dict:
    """Retourne la configuration par défaut."""
    return {
        "tasmota_ips": ["192.168.1.19"],
        "timeout_seconds": 600,
        "poll_interval_seconds": 2.0,
        "turn_off_on_startup_if_silent": False,
        "turn_off_on_shutdown": True,
        "peak_audio_threshold": 0.001,
        "http_timeout_seconds": 2.5,
        "log_to_file": True,
        "log_file": "speaker_guard.log",
        "asio_detection_enabled": True,
        "asio_processes": [
            "Rocksmith2014.exe",
            "reaper*.exe",
            "FL64.exe",
            "FL.exe",
            "Ableton Live*.exe",
            "Cubase*.exe",
            "Studio One.exe",
            "Bitwig Studio.exe",
            "ProTools.exe",
            "GuitarPro*.exe",
            "AmpliTube*.exe",
            "Helix*.exe",
            "Archetype*.exe",
            "NeuralDSP*.exe",
            "Voicemeeter*.exe"
        ]
    }


def load_config(config_path: Optional[str] = None) -> dict:
    """Charge la configuration depuis un fichier JSON avec repli sur les valeurs par défaut."""
    config = get_default_config()
    target_path = Path(config_path) if config_path else DEFAULT_CONFIG_FILE

    if target_path.is_file():
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                user_conf = json.load(f)
                config.update(user_conf)
        except Exception as e:
            logging.warning(f"Erreur de lecture du fichier {target_path}: {e}")

    # Rétrocompatibilité : si "tasmota_ip" unique est fourni au lieu de "tasmota_ips"
    if "tasmota_ip" in config and config["tasmota_ip"]:
        single_ip = config.pop("tasmota_ip")
        if single_ip not in config.get("tasmota_ips", []):
            config.setdefault("tasmota_ips", []).append(single_ip)

    # Assurer que tasmota_ips est toujours une liste
    if isinstance(config.get("tasmota_ips"), str):
        config["tasmota_ips"] = [ip.strip() for ip in config["tasmota_ips"].split(",") if ip.strip()]

    return config


def setup_logger(config: dict, log_level: str = "INFO"):
    """Initialise le système de logs (console + fichier optionnel)."""
    handlers = [logging.StreamHandler(sys.stdout)]
    if config.get("log_to_file", True):
        log_path = SCRIPT_DIR / config.get("log_file", "speaker_guard.log")
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))

    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers
    )


# ==============================================================================
# CLIENT TASMOTA MULTI-PRISES
# ==============================================================================

class TasmotaClient:
    """Gestionnaire HTTP REST pour une ou plusieurs prises Tasmota simultanées."""

    def __init__(self, ips: List[str], timeout: float = 2.5):
        self.ips = [ip.strip() for ip in ips if ip.strip()]
        self.timeout = timeout

    def _query_ip_state(self, ip: str) -> Tuple[str, Optional[bool]]:
        """Récupère l'état d'alimentation d'une prise (True = ON, False = OFF, None si erreur)."""
        url = f"http://{ip}/cm?cmnd=Power"
        try:
            res = requests.get(url, timeout=self.timeout)
            if res.status_code == 200:
                data = res.json()
                power_str = data.get("POWER", "").upper()
                return ip, (power_str == "ON")
        except Exception as e:
            logging.debug(f"Impossible de joindre la prise Tasmota ({ip}): {e}")
        return ip, None

    def _send_ip_power(self, ip: str, state: bool) -> Tuple[str, bool]:
        """Envoie l'ordre ON ou OFF à une prise donnée."""
        cmd = "Power ON" if state else "Power OFF"
        url = f"http://{ip}/cm?cmnd={requests.utils.quote(cmd)}"
        try:
            res = requests.get(url, timeout=self.timeout)
            if res.status_code == 200:
                return ip, True
        except Exception as e:
            logging.error(f"Echec envoi commande '{cmd}' a Tasmota ({ip}): {e}")
        return ip, False

    def get_power_states(self) -> Dict[str, Optional[bool]]:
        """Interroge toutes les prises en parallèle."""
        results = {}
        if not self.ips:
            return results
        with ThreadPoolExecutor(max_workers=min(len(self.ips), 10)) as executor:
            for ip, state in executor.map(self._query_ip_state, self.ips):
                results[ip] = state
        return results

    def is_any_on(self) -> bool:
        """Indique si au moins une prise est allumée."""
        states = self.get_power_states()
        return any(s is True for s in states.values())

    def set_power(self, state: bool) -> Dict[str, bool]:
        """Bascule toutes les prises en parallèle sur ON ou OFF."""
        cmd_str = "ON" if state else "OFF"
        results = {}
        if not self.ips:
            return results
        with ThreadPoolExecutor(max_workers=min(len(self.ips), 10)) as executor:
            for ip, ok in executor.map(lambda ip: self._send_ip_power(ip, state), self.ips):
                results[ip] = ok
                status_txt = "SUCCES" if ok else "ECHEC"
                logging.info(f"Tasmota [{ip}] -> Power {cmd_str} ({status_txt})")
        return results


# ==============================================================================
# DÉTECTEUR AUDIO MULTI-PLATEFORME
# ==============================================================================

if IS_WINDOWS:
    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [
            ('dwSize', ctypes.wintypes.DWORD),
            ('cntUsage', ctypes.wintypes.DWORD),
            ('th32ProcessID', ctypes.wintypes.DWORD),
            ('th32DefaultHeapID', ctypes.c_size_t),
            ('th32ModuleID', ctypes.wintypes.DWORD),
            ('cntThreads', ctypes.wintypes.DWORD),
            ('th32ParentProcessID', ctypes.wintypes.DWORD),
            ('pcPriClassBase', ctypes.c_long),
            ('dwFlags', ctypes.wintypes.DWORD),
            ('szExeFile', ctypes.c_char * 260)
        ]


class WindowsAudioDetector:
    """Détecteur audio Windows : Core Audio (WASAPI) + Peak Meter + ASIO direct."""

    def __init__(self, peak_threshold: float = 0.001, asio_patterns: Optional[List[str]] = None):
        self.peak_threshold = peak_threshold
        self.asio_patterns = asio_patterns or []
        self.installed_asio_drivers = self._discover_asio_drivers()

    def _discover_asio_drivers(self) -> List[dict]:
        drivers = []
        for root, root_name in [(winreg.HKEY_LOCAL_MACHINE, 'HKLM'), (winreg.HKEY_CURRENT_USER, 'HKCU')]:
            try:
                key = winreg.OpenKey(root, r"SOFTWARE\ASIO")
                count = winreg.QueryInfoKey(key)[0]
                for i in range(count):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        sub = winreg.OpenKey(key, subkey_name)
                        desc = subkey_name
                        try:
                            desc, _ = winreg.QueryValueEx(sub, "Description")
                        except OSError:
                            pass
                        drivers.append({"name": subkey_name, "desc": desc, "hive": root_name})
                    except OSError:
                        break
            except FileNotFoundError:
                pass
        return drivers

    def _get_running_process_names(self) -> Set[str]:
        names = set()
        k32 = ctypes.windll.kernel32
        h_snap = k32.CreateToolhelp32Snapshot(0x00000002, 0)
        if h_snap == -1 or not h_snap:
            return names
        try:
            entry = PROCESSENTRY32()
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
            if k32.Process32First(h_snap, ctypes.byref(entry)):
                while True:
                    names.add(entry.szExeFile.decode('ansi', errors='ignore'))
                    if not k32.Process32Next(h_snap, ctypes.byref(entry)):
                        break
        finally:
            k32.CloseHandle(h_snap)
        return names

    def detect_active_asio_apps(self) -> List[str]:
        if not self.asio_patterns:
            return []
        running = self._get_running_process_names()
        active = []
        for p in running:
            p_low = p.lower()
            for pat in self.asio_patterns:
                if fnmatch.fnmatch(p_low, pat.lower()):
                    active.append(p)
                    break
        return active

    def get_audio_status(self) -> Tuple[bool, float, List[str]]:
        try:
            comtypes.CoInitialize()
        except Exception:
            pass

        active_apps = []
        is_session_active = False

        # 1. Sessions WASAPI Windows
        try:
            sessions = AudioUtilities.GetAllSessions()
            for s in sessions:
                if s.State == 1:
                    is_session_active = True
                    active_apps.append(s.Process.name() if s.Process else "System/Other")
        except Exception as e:
            logging.debug(f"Erreur sessions audio: {e}")

        # 2. Master Peak Meter
        peak_val = 0.0
        try:
            device = AudioUtilities.GetSpeakers()
            if device and hasattr(device, "_dev") and device._dev:
                p_meter = device._dev.Activate(IAudioMeterInformation._iid_, comtypes.CLSCTX_ALL, None)
                meter = p_meter.QueryInterface(IAudioMeterInformation)
                peak_val = float(meter.GetPeakValue())
        except Exception as e:
            logging.debug(f"Erreur peak meter: {e}")

        # 3. ASIO direct
        is_asio_active = False
        asio_apps = self.detect_active_asio_apps()
        if asio_apps:
            is_asio_active = True
            for app in asio_apps:
                active_apps.append(f"{app} [ASIO]")

        is_playing = is_session_active or (peak_val >= self.peak_threshold) or is_asio_active
        return is_playing, peak_val, active_apps


class LinuxAudioDetector:
    """
    Détecteur audio sous Linux :
    1. PipeWire / PulseAudio via `pactl list sinks` (State: RUNNING)
    2. Entrées de mixage `pactl list sink-inputs`
    3. Fichiers virtuels ALSA (/proc/asound/card*/pcm*/sub*/status)
    """

    def __init__(self, asio_patterns: Optional[List[str]] = None):
        self.patterns = asio_patterns or []

    def get_audio_status(self) -> Tuple[bool, float, List[str]]:
        active_sources = []
        is_playing = False

        # 1. Vérification via pactl (PulseAudio / PipeWire)
        try:
            out = subprocess.check_output(["pactl", "list", "sinks"], stderr=subprocess.DEVNULL, text=True)
            if "State: RUNNING" in out:
                is_playing = True
                active_sources.append("PulseAudio/PipeWire Sink [RUNNING]")
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        # 2. Vérification via les flux d'applications sink-inputs
        if not is_playing:
            try:
                out = subprocess.check_output(["pactl", "list", "sink-inputs"], stderr=subprocess.DEVNULL, text=True)
                if "Sink Input #" in out:
                    is_playing = True
                    active_sources.append("PulseAudio Active Stream")
            except (subprocess.SubprocessError, FileNotFoundError):
                pass

        # 3. Vérification directe ALSA (/proc/asound)
        if not is_playing:
            try:
                for status_file in Path("/proc/asound").glob("card*/pcm*p/sub*/status"):
                    content = status_file.read_text(errors="ignore")
                    if "state: RUNNING" in content:
                        is_playing = True
                        active_sources.append(f"ALSA [{status_file.parent.name}] RUNNING")
                        break
            except Exception:
                pass

        # 4. Processus DAW Linux (Reaper, Bitwig, Ardour, Jack...)
        try:
            for pat in self.patterns:
                clean_pat = pat.replace(".exe", "")
                try:
                    subprocess.check_output(["pgrep", "-f", clean_pat], stderr=subprocess.DEVNULL)
                    is_playing = True
                    active_sources.append(f"{clean_pat} [DAW/Process]")
                except subprocess.CalledProcessError:
                    pass
        except Exception:
            pass

        return is_playing, 1.0 if is_playing else 0.0, active_sources


class MacOSAudioDetector:
    """
    Détecteur audio sous macOS :
    1. Assertions de gestion d'alimentation CoreAudio via `pmset -g assertions`
    2. Processus audio / DAW actifs (Logic Pro, Reaper, Ableton...)
    """

    def __init__(self, asio_patterns: Optional[List[str]] = None):
        self.patterns = asio_patterns or []

    def get_audio_status(self) -> Tuple[bool, float, List[str]]:
        active_sources = []
        is_playing = False

        # 1. Inspection des assertions audio du système
        try:
            out = subprocess.check_output(["pmset", "-g", "assertions"], stderr=subprocess.DEVNULL, text=True)
            # Quand du son joue sous macOS, coreaudiod pose une assertion
            if "coreaudiod" in out and ("PreventUserIdleDisplaySleep" in out or "PreventUserIdleSystemSleep" in out):
                is_playing = True
                active_sources.append("CoreAudio [coreaudiod active]")
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        # 2. Processus DAW / Logiciels de son sous macOS
        daw_names = ["Logic Pro", "Ableton Live", "REAPER", "FL Studio", "GarageBand", "MainStage"]
        for p in self.patterns:
            clean_name = p.replace(".exe", "").replace("*", "")
            if clean_name not in daw_names:
                daw_names.append(clean_name)

        try:
            for app in daw_names:
                try:
                    subprocess.check_output(["pgrep", "-f", app], stderr=subprocess.DEVNULL)
                    is_playing = True
                    active_sources.append(f"{app} [macOS App]")
                except subprocess.CalledProcessError:
                    pass
        except Exception:
            pass

        return is_playing, 1.0 if is_playing else 0.0, active_sources


def create_audio_detector(config: dict):
    """Instancie le détecteur audio adapté au système d'exploitation."""
    patterns = config.get("asio_processes", []) if config.get("asio_detection_enabled", True) else []
    if IS_WINDOWS:
        return WindowsAudioDetector(
            peak_threshold=config.get("peak_audio_threshold", 0.001),
            asio_patterns=patterns
        )
    elif IS_LINUX:
        return LinuxAudioDetector(asio_patterns=patterns)
    elif IS_MACOS:
        return MacOSAudioDetector(asio_patterns=patterns)
    else:
        raise NotImplementedError(f"Systeme d'exploitation non supporte: {sys.platform}")


# ==============================================================================
# GESTION DES SIGNAUX & ARRÊT SYSTÈME
# ==============================================================================

class WindowsShutdownListener:
    """Interception des messages de shutdown/reboot sous Windows via fenêtre invisible."""

    def __init__(self, on_shutdown_cb):
        self.on_shutdown_cb = on_shutdown_cb
        self.hwnd = None
        self.class_atom = None
        if HAS_WIN32:
            try:
                wc = win32gui.WNDCLASS()
                wc.lpfnWndProc = self._wnd_proc
                wc.lpszClassName = "TasmotaSpeakerGuardShutdownListener"
                self.class_atom = win32gui.RegisterClass(wc)
                self.hwnd = win32gui.CreateWindow(
                    self.class_atom, "TasmotaSpeakerGuardListener",
                    0, 0, 0, 0, 0, 0, 0, 0, None
                )
            except Exception as e:
                logging.warning(f"Impossible d'enregistrer la fenetre Win32: {e}")

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg in (win32con.WM_QUERYENDSESSION, win32con.WM_ENDSESSION):
            logging.info("Interception signal Windows EndSession/Shutdown...")
            try:
                self.on_shutdown_cb()
            except Exception as e:
                logging.error(f"Erreur callback shutdown: {e}")
            return 1
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def pump(self):
        if HAS_WIN32:
            try:
                win32gui.PumpWaitingMessages()
            except Exception:
                pass


# ==============================================================================
# DAEMON PRINCIPAL
# ==============================================================================

class SpeakerGuardDaemon:
    """Boucle principale de surveillance et pilotage des enceintes."""

    def __init__(self, config: dict):
        self.config = config
        self.tasmota = TasmotaClient(
            ips=config.get("tasmota_ips", []),
            timeout=config.get("http_timeout_seconds", 2.5)
        )
        self.audio = create_audio_detector(config)
        self.timeout_sec = float(config.get("timeout_seconds", 600))
        self.poll_interval = float(config.get("poll_interval_seconds", 2.0))
        self.turn_off_on_shutdown = config.get("turn_off_on_shutdown", True)

        self.is_running = True
        self.last_sound_time = time.time()
        self.current_power_state: Optional[bool] = None

        # Gestion de l'arrêt
        self.shutdown_listener = WindowsShutdownListener(self.handle_system_shutdown) if IS_WINDOWS else None
        self._register_signals()

    def _register_signals(self):
        atexit.register(self.handle_system_shutdown)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        if IS_WINDOWS and HAS_WIN32:
            def console_ctrl_handler(ctrl_type):
                logging.info(f"Signal console recu: {ctrl_type}")
                self.handle_system_shutdown()
                return True
            win32api.SetConsoleCtrlHandler(console_ctrl_handler, True)

    def _signal_handler(self, signum, frame):
        logging.info(f"Signal d'interruption recu ({signum}).")
        self.is_running = False
        self.handle_system_shutdown()
        sys.exit(0)

    def handle_system_shutdown(self):
        """Coupe toutes les prises à l'arrêt du PC ou fermeture du script."""
        if not self.turn_off_on_shutdown:
            return
        logging.info("Extinction de securite des enceintes Tasmota...")
        try:
            self.tasmota.set_power(False)
        except Exception as e:
            logging.error(f"Erreur extinction shutdown: {e}")

    def run(self):
        """Lance la boucle continue de détection audio."""
        ips_str = ", ".join(self.tasmota.ips)
        logging.info("=========================================")
        logging.info("   Demarrage de Tasmota Speaker Guard    ")
        logging.info(f"   OS: {sys.platform}")
        logging.info(f"   Prises Tasmota: {ips_str}")
        logging.info(f"   Delai d'extinction: {self.timeout_sec}s ({self.timeout_sec / 60:.1f} min)")
        logging.info("=========================================")

        # Synchronisation de l'état initial
        self.current_power_state = self.tasmota.is_any_on()
        state_str = "AU MOINS UNE ALLUMEE" if self.current_power_state else "TOUTES ETEINTES"
        logging.info(f"Statut initial des prises: {state_str}")

        # Détection initiale
        is_playing, peak, active_sources = self.audio.get_audio_status()
        now = time.time()

        if is_playing:
            self.last_sound_time = now
            if not self.current_power_state:
                logging.info(f"Audio detecte au lancement ({', '.join(active_sources)}) -> Allumage des prises.")
                self.tasmota.set_power(True)
                self.current_power_state = True
        else:
            self.last_sound_time = now
            if self.config.get("turn_off_on_startup_if_silent", False) and self.current_power_state:
                logging.info("Aucun flux audio au boot -> Extinction par defaut.")
                self.tasmota.set_power(False)
                self.current_power_state = False

        logging.info("Surveillance audio en cours...")

        # Boucle principale
        while self.is_running:
            try:
                if self.shutdown_listener:
                    self.shutdown_listener.pump()

                now = time.time()
                is_playing, peak, active_sources = self.audio.get_audio_status()

                if is_playing:
                    self.last_sound_time = now
                    if not self.current_power_state:
                        logging.info(f"Son detecte ({', '.join(active_sources) or 'Flux actif'}) -> Allumage enceintes.")
                        self.tasmota.set_power(True)
                        self.current_power_state = True
                else:
                    if self.current_power_state:
                        elapsed = now - self.last_sound_time
                        if elapsed >= self.timeout_sec:
                            logging.info(f"Silence depuis {elapsed:.0f}s (seuil {self.timeout_sec:.0f}s atteint) -> Extinction enceintes.")
                            self.tasmota.set_power(False)
                            self.current_power_state = False

                time.sleep(self.poll_interval)

            except Exception as e:
                logging.error(f"Erreur inattendue dans la boucle principale: {e}")
                time.sleep(self.poll_interval)


# ==============================================================================
# DIAGNOSTIC & CLI
# ==============================================================================

def cli_test(config: dict):
    """Exécute un diagnostic complet du système."""
    print("\n--- Diagnostic Tasmota Speaker Guard ---")
    tasmota = TasmotaClient(config.get("tasmota_ips", []), timeout=config.get("http_timeout_seconds", 2.5))
    audio = create_audio_detector(config)

    print(f"OS detecte : {sys.platform}")
    print(f"1. Test connexion prise(s) Tasmota ({', '.join(tasmota.ips)})...")
    states = tasmota.get_power_states()
    for ip, state in states.items():
        if state is None:
            print(f"   [{ip}] [ERREUR] Inaccessible")
        else:
            print(f"   [{ip}] [OK] Etat: {'ALLUMEE (ON)' if state else 'ETEINTE (OFF)'}")

    print("\n2. Test de detection audio...")
    if IS_WINDOWS and hasattr(audio, 'installed_asio_drivers'):
        print(f"   Pilotes ASIO Windows detectes :")
        for d in audio.installed_asio_drivers:
            print(f"     * {d['name']} ({d['desc']}) [{d['hive']}]")

    is_playing, peak, sources = audio.get_audio_status()
    print(f"   - Audio actif detecte : {'OUI' if is_playing else 'NON'}")
    if IS_WINDOWS:
        print(f"   - Niveau crête Master Peak (WASAPI) : {peak:.5f}")
    print(f"   - Source(s) active(s) : {', '.join(sources) if sources else 'Aucune'}")
    print("----------------------------------------\n")


def build_cli_parser() -> argparse.ArgumentParser:
    """Construit les arguments de ligne de commande."""
    parser = argparse.ArgumentParser(
        description="Gestionnaire intelligent d'alimentation des enceintes via prises Tasmota."
    )
    parser.add_argument(
        "action",
        nargs="?",
        default="run",
        choices=["run", "test", "status", "on", "off"],
        help="Action a executer : run (defaut), test, status, on, off"
    )
    parser.add_argument(
        "--ips",
        nargs="+",
        help="Une ou plusieurs adresses IP Tasmota separees par un espace ou une virgule (ex: --ips 192.168.1.19 192.168.1.20)"
    )
    parser.add_argument(
        "--ip",
        help="Adresse IP Tasmota unique (alternative a --ips)"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        help="Delai d'inactivite en secondes avant extinction (ex: 600)"
    )
    parser.add_argument(
        "--interval",
        type=float,
        help="Intervalle de verification en secondes (ex: 2.0)"
    )
    parser.add_argument(
        "--config",
        help="Chemin vers un fichier de configuration alternatif (JSON)"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Niveau de detail des logs"
    )
    return parser


def parse_args():
    """Gere le parsing robuste des arguments, y compris quand l'action est placee apres des options."""
    parser = build_cli_parser()
    args = parser.parse_args()

    # Si l'utilisateur a passe des IPs avec des virgules ex: --ips 192.168.1.19,192.168.1.20
    if args.ips:
        flattened = []
        for item in args.ips:
            for sub in item.split(","):
                if sub.strip():
                    flattened.append(sub.strip())
        args.ips = flattened

    return args


def main():
    args = parse_args()

    # Chargement de la config
    config = load_config(args.config)

    # Surcharge via les arguments CLI
    if args.ips:
        config["tasmota_ips"] = args.ips
    elif args.ip:
        config["tasmota_ips"] = [args.ip]

    if args.timeout is not None:
        config["timeout_seconds"] = args.timeout

    if args.interval is not None:
        config["poll_interval_seconds"] = args.interval

    setup_logger(config, log_level=args.log_level)

    action = args.action.lower()

    if action == "run":
        daemon = SpeakerGuardDaemon(config)
        daemon.run()
    elif action == "test":
        cli_test(config)
    elif action == "status":
        tasmota = TasmotaClient(config.get("tasmota_ips", []))
        states = tasmota.get_power_states()
        for ip, state in states.items():
            print(f"Tasmota [{ip}]: {'ON' if state else 'OFF' if state is not None else 'INACCESSIBLE'}")
    elif action == "on":
        tasmota = TasmotaClient(config.get("tasmota_ips", []))
        tasmota.set_power(True)
        print("Toutes les prises ont recu l'ordre d'allumage.")
    elif action == "off":
        tasmota = TasmotaClient(config.get("tasmota_ips", []))
        tasmota.set_power(False)
        print("Toutes les prises ont recu l'ordre d'extinction.")


if __name__ == "__main__":
    main()
