#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tasmota Speaker Guard
---------------------
Real-time audio activity monitor (Windows, Linux, macOS) that automatically controls
one or more Tasmota smart plugs powering audio monitors or speakers:
- Instant power-on when audio playback starts (WASAPI, ASIO direct, PulseAudio, PipeWire, CoreAudio).
- Support for direct ASIO applications (Rocksmith, DAWs: Reaper, FL Studio, Ableton, amp sims...).
- Automatic power-off after X minutes of continuous silence (10 min by default).
- Guaranteed power-off on PC shutdown, reboot, or session logoff.
- Multi-plug support (concurrent HTTP requests to multiple Tasmota IPs).
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

# HTTP client
import requests

# OS detection
IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
IS_MACOS = sys.platform == "darwin"

# Windows-conditional imports
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

# Script paths
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_FILE = SCRIPT_DIR / "config.json"


# ==============================================================================
# CONFIGURATION
# ==============================================================================

def get_default_config() -> dict:
    """Returns default configuration values."""
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
    """Loads configuration from JSON file with fallback to defaults."""
    config = get_default_config()
    target_path = Path(config_path) if config_path else DEFAULT_CONFIG_FILE

    if target_path.is_file():
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                user_conf = json.load(f)
                config.update(user_conf)
        except Exception as e:
            logging.warning(f"Error reading configuration file {target_path}: {e}")

    # Backward compatibility: single tasmota_ip instead of tasmota_ips list
    if "tasmota_ip" in config and config["tasmota_ip"]:
        single_ip = config.pop("tasmota_ip")
        if single_ip not in config.get("tasmota_ips", []):
            config.setdefault("tasmota_ips", []).append(single_ip)

    if isinstance(config.get("tasmota_ips"), str):
        config["tasmota_ips"] = [ip.strip() for ip in config["tasmota_ips"].split(",") if ip.strip()]

    return config


def setup_logger(config: dict, log_level: str = "INFO"):
    """Configures console and file logging."""
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
# MULTI-PLUG TASMOTA CLIENT
# ==============================================================================

class TasmotaClient:
    """Handles HTTP REST communication with one or multiple Tasmota smart plugs."""

    def __init__(self, ips: List[str], timeout: float = 2.5):
        self.ips = [ip.strip() for ip in ips if ip.strip()]
        self.timeout = timeout

    def _query_ip_state(self, ip: str) -> Tuple[str, Optional[bool]]:
        """Queries single plug power status (True = ON, False = OFF, None on error)."""
        url = f"http://{ip}/cm?cmnd=Power"
        try:
            res = requests.get(url, timeout=self.timeout)
            if res.status_code == 200:
                data = res.json()
                power_str = data.get("POWER", "").upper()
                return ip, (power_str == "ON")
        except Exception as e:
            logging.debug(f"Unable to reach Tasmota device ({ip}): {e}")
        return ip, None

    def _send_ip_power(self, ip: str, state: bool) -> Tuple[str, bool]:
        """Sends Power ON or OFF command to a specific plug."""
        cmd = "Power ON" if state else "Power OFF"
        url = f"http://{ip}/cm?cmnd={requests.utils.quote(cmd)}"
        try:
            res = requests.get(url, timeout=self.timeout)
            if res.status_code == 200:
                return ip, True
        except Exception as e:
            logging.error(f"Failed to send '{cmd}' to Tasmota ({ip}): {e}")
        return ip, False

    def get_power_states(self) -> Dict[str, Optional[bool]]:
        """Queries all configured plugs concurrently in parallel."""
        results = {}
        if not self.ips:
            return results
        with ThreadPoolExecutor(max_workers=min(len(self.ips), 10)) as executor:
            for ip, state in executor.map(self._query_ip_state, self.ips):
                results[ip] = state
        return results

    def is_any_on(self) -> bool:
        """Returns True if at least one plug is currently turned ON."""
        states = self.get_power_states()
        return any(s is True for s in states.values())

    def set_power(self, state: bool) -> Dict[str, bool]:
        """Switches all configured plugs ON or OFF concurrently in parallel."""
        cmd_str = "ON" if state else "OFF"
        results = {}
        if not self.ips:
            return results
        with ThreadPoolExecutor(max_workers=min(len(self.ips), 10)) as executor:
            for ip, ok in executor.map(lambda ip: self._send_ip_power(ip, state), self.ips):
                results[ip] = ok
                status_txt = "SUCCESS" if ok else "FAILED"
                logging.info(f"Tasmota [{ip}] -> Power {cmd_str} ({status_txt})")
        return results


# ==============================================================================
# CROSS-PLATFORM AUDIO DETECTORS
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
    """Windows audio detector: Core Audio (WASAPI) + Peak Meter + Direct ASIO."""

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

        # 1. WASAPI sessions
        try:
            sessions = AudioUtilities.GetAllSessions()
            for s in sessions:
                if s.State == 1:
                    is_session_active = True
                    active_apps.append(s.Process.name() if s.Process else "System/Other")
        except Exception as e:
            logging.debug(f"WASAPI sessions inspection error: {e}")

        # 2. Master Peak Meter
        peak_val = 0.0
        try:
            device = AudioUtilities.GetSpeakers()
            if device and hasattr(device, "_dev") and device._dev:
                p_meter = device._dev.Activate(IAudioMeterInformation._iid_, comtypes.CLSCTX_ALL, None)
                meter = p_meter.QueryInterface(IAudioMeterInformation)
                peak_val = float(meter.GetPeakValue())
        except Exception as e:
            logging.debug(f"Master peak meter inspection error: {e}")

        # 3. Direct ASIO applications
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
    Linux audio detector:
    1. PipeWire / PulseAudio via `pactl list sinks` (State: RUNNING)
    2. Active application streams via `pactl list sink-inputs`
    3. ALSA hardware device status files (/proc/asound/card*/pcm*/sub*/status)
    """

    def __init__(self, asio_patterns: Optional[List[str]] = None):
        self.patterns = asio_patterns or []

    def get_audio_status(self) -> Tuple[bool, float, List[str]]:
        active_sources = []
        is_playing = False

        # 1. Check via pactl (PulseAudio / PipeWire)
        try:
            out = subprocess.check_output(["pactl", "list", "sinks"], stderr=subprocess.DEVNULL, text=True)
            if "State: RUNNING" in out:
                is_playing = True
                active_sources.append("PulseAudio/PipeWire Sink [RUNNING]")
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        # 2. Check active sink-inputs
        if not is_playing:
            try:
                out = subprocess.check_output(["pactl", "list", "sink-inputs"], stderr=subprocess.DEVNULL, text=True)
                if "Sink Input #" in out:
                    is_playing = True
                    active_sources.append("PulseAudio Active Stream")
            except (subprocess.SubprocessError, FileNotFoundError):
                pass

        # 3. Direct ALSA kernel status inspection (/proc/asound)
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

        # 4. Linux DAW processes
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
    macOS audio detector:
    1. System CoreAudio power assertions via `pmset -g assertions`
    2. Active DAW audio processes (Logic Pro, Reaper, Ableton...)
    """

    def __init__(self, asio_patterns: Optional[List[str]] = None):
        self.patterns = asio_patterns or []

    def get_audio_status(self) -> Tuple[bool, float, List[str]]:
        active_sources = []
        is_playing = False

        # 1. Inspect macOS power assertions
        try:
            out = subprocess.check_output(["pmset", "-g", "assertions"], stderr=subprocess.DEVNULL, text=True)
            if "coreaudiod" in out and ("PreventUserIdleDisplaySleep" in out or "PreventUserIdleSystemSleep" in out):
                is_playing = True
                active_sources.append("CoreAudio [coreaudiod active]")
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        # 2. Check DAW processes on macOS
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
    """Instantiates the appropriate audio detector for the current operating system."""
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
        raise NotImplementedError(f"Unsupported operating system: {sys.platform}")


# ==============================================================================
# SYSTEM SHUTDOWN LISTENER
# ==============================================================================

class WindowsShutdownListener:
    """Catches Windows shutdown/reboot/logoff events via a hidden top-level window."""

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
                logging.warning(f"Unable to register Win32 listener window: {e}")

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg in (win32con.WM_QUERYENDSESSION, win32con.WM_ENDSESSION):
            logging.info("Caught Windows EndSession/Shutdown signal...")
            try:
                self.on_shutdown_cb()
            except Exception as e:
                logging.error(f"Error during shutdown callback: {e}")
            return 1
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def pump(self):
        if HAS_WIN32:
            try:
                win32gui.PumpWaitingMessages()
            except Exception:
                pass


# ==============================================================================
# MAIN DAEMON
# ==============================================================================

class SpeakerGuardDaemon:
    """Main orchestration daemon for monitoring audio and switching smart plugs."""

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

        self.shutdown_listener = WindowsShutdownListener(self.handle_system_shutdown) if IS_WINDOWS else None
        self._register_signals()

    def _register_signals(self):
        atexit.register(self.handle_system_shutdown)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        if IS_WINDOWS and HAS_WIN32:
            def console_ctrl_handler(ctrl_type):
                logging.info(f"Console control signal received: {ctrl_type}")
                self.handle_system_shutdown()
                return True
            win32api.SetConsoleCtrlHandler(console_ctrl_handler, True)

    def _signal_handler(self, signum, frame):
        logging.info(f"Interrupt signal caught ({signum}).")
        self.is_running = False
        self.handle_system_shutdown()
        sys.exit(0)

    def handle_system_shutdown(self):
        """Emergency turn-off on system shutdown or process exit."""
        if not self.turn_off_on_shutdown:
            return
        logging.info("Executing safety power-off on Tasmota plugs...")
        try:
            self.tasmota.set_power(False)
        except Exception as e:
            logging.error(f"Error during shutdown power-off: {e}")

    def run(self):
        """Runs the main surveillance loop."""
        ips_str = ", ".join(self.tasmota.ips)
        logging.info("=========================================")
        logging.info("     Starting Tasmota Speaker Guard      ")
        logging.info(f"   Platform: {sys.platform}")
        logging.info(f"   Tasmota Plugs: {ips_str}")
        logging.info(f"   Silence Timeout: {self.timeout_sec}s ({self.timeout_sec / 60:.1f} min)")
        logging.info("=========================================")

        # Initial plug status sync
        self.current_power_state = self.tasmota.is_any_on()
        state_str = "AT LEAST ONE ON" if self.current_power_state else "ALL OFF"
        logging.info(f"Initial plug state: {state_str}")

        # Initial audio check
        is_playing, peak, active_sources = self.audio.get_audio_status()
        now = time.time()

        if is_playing:
            self.last_sound_time = now
            if not self.current_power_state:
                logging.info(f"Audio detected at startup ({', '.join(active_sources)}) -> Powering ON.")
                self.tasmota.set_power(True)
                self.current_power_state = True
        else:
            self.last_sound_time = now
            if self.config.get("turn_off_on_startup_if_silent", False) and self.current_power_state:
                logging.info("No audio at boot -> Turning OFF plugs.")
                self.tasmota.set_power(False)
                self.current_power_state = False

        logging.info("Audio monitoring in progress...")

        # Continuous loop
        while self.is_running:
            try:
                if self.shutdown_listener:
                    self.shutdown_listener.pump()

                now = time.time()
                is_playing, peak, active_sources = self.audio.get_audio_status()

                if is_playing:
                    self.last_sound_time = now
                    if not self.current_power_state:
                        logging.info(f"Sound detected ({', '.join(active_sources) or 'Active Stream'}) -> Powering ON speakers.")
                        self.tasmota.set_power(True)
                        self.current_power_state = True
                else:
                    if self.current_power_state:
                        elapsed = now - self.last_sound_time
                        if elapsed >= self.timeout_sec:
                            logging.info(f"Silence for {elapsed:.0f}s (threshold {self.timeout_sec:.0f}s reached) -> Turning OFF speakers.")
                            self.tasmota.set_power(False)
                            self.current_power_state = False

                time.sleep(self.poll_interval)

            except Exception as e:
                logging.error(f"Unexpected error in main monitoring loop: {e}")
                time.sleep(self.poll_interval)


# ==============================================================================
# CLI & DIAGNOSTICS
# ==============================================================================

def cli_test(config: dict):
    """Runs a complete system diagnostic."""
    print("\n--- Tasmota Speaker Guard Diagnostic ---")
    tasmota = TasmotaClient(config.get("tasmota_ips", []), timeout=config.get("http_timeout_seconds", 2.5))
    audio = create_audio_detector(config)

    print(f"Platform: {sys.platform}")
    print(f"1. Testing connection to Tasmota plug(s) ({', '.join(tasmota.ips)})...")
    states = tasmota.get_power_states()
    for ip, state in states.items():
        if state is None:
            print(f"   [{ip}] [ERROR] Unreachable")
        else:
            print(f"   [{ip}] [OK] State: {'ON' if state else 'OFF'}")

    print("\n2. Testing audio detection...")
    if IS_WINDOWS and hasattr(audio, 'installed_asio_drivers'):
        print(f"   Windows ASIO drivers detected:")
        for d in audio.installed_asio_drivers:
            print(f"     * {d['name']} ({d['desc']}) [{d['hive']}]")

    is_playing, peak, sources = audio.get_audio_status()
    print(f"   - Active audio detected : {'YES' if is_playing else 'NO'}")
    if IS_WINDOWS:
        print(f"   - WASAPI Master Peak level : {peak:.5f}")
    print(f"   - Active sound source(s) : {', '.join(sources) if sources else 'None'}")
    print("----------------------------------------\n")


def build_cli_parser() -> argparse.ArgumentParser:
    """Builds CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Smart audio-reactive power manager for Tasmota smart plugs."
    )
    parser.add_argument(
        "action",
        nargs="?",
        default="run",
        choices=["run", "test", "status", "on", "off"],
        help="Action to execute: run (default), test, status, on, off"
    )
    parser.add_argument(
        "--ips",
        nargs="+",
        help="One or more Tasmota IP addresses separated by space or comma (e.g. --ips 192.168.1.19 192.168.1.20)"
    )
    parser.add_argument(
        "--ip",
        help="Single Tasmota IP address (convenience alternative to --ips)"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        help="Silence timeout in seconds before power-off (e.g. 600)"
    )
    parser.add_argument(
        "--interval",
        type=float,
        help="Polling interval in seconds (e.g. 2.0)"
    )
    parser.add_argument(
        "--config",
        help="Path to an alternative JSON configuration file"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging detail level"
    )
    return parser


def parse_args():
    parser = build_cli_parser()
    args = parser.parse_args()

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
    config = load_config(args.config)

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
            print(f"Tasmota [{ip}]: {'ON' if state else 'OFF' if state is not None else 'UNREACHABLE'}")
    elif action == "on":
        tasmota = TasmotaClient(config.get("tasmota_ips", []))
        tasmota.set_power(True)
        print("All plugs received the Power ON command.")
    elif action == "off":
        tasmota = TasmotaClient(config.get("tasmota_ips", []))
        tasmota.set_power(False)
        print("All plugs received the Power OFF command.")


if __name__ == "__main__":
    main()
