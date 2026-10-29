# 🔊 Tasmota Speaker Guard

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-green.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tasmota](https://img.shields.io/badge/Compatible-Tasmota%20HTTP%20REST-orange.svg)](https://tasmota.github.io/docs/Commands/)

> **Smart, lightweight, cross-platform audio-reactive power manager for studio monitors and speakers connected via Tasmota smart plugs.**  
> Monitors real-time system audio activity (Windows WASAPI/ASIO, Linux PipeWire/PulseAudio/ALSA, macOS CoreAudio) and automatically switches your Tasmota plug(s) ON when audio starts, and OFF after prolonged silence or on system shutdown.

---

## ✨ Features

- 🟢 **Instant Power-On**: Turns your speakers ON immediately when any audio stream is detected (music, video, gaming, DAW, calls...).
- ⏳ **Configurable Idle Timeout**: Turns plugs OFF automatically after a period of continuous silence (10 minutes by default).
- 🎛️ **Direct ASIO Support**: Keeps studio monitors ON during direct ASIO sessions, preventing cutoff when playing through low-latency audio interfaces (**Rocksmith**, **Reaper**, **FL Studio**, **Ableton Live**, **Cubase**, amp simulators like Helix, Neural DSP, Amplitube...).
- 🔌 **Multi-Plug Support**: Control multiple Tasmota smart plugs simultaneously in parallel (e.g. separate left/right studio monitors, subwoofers).
- 💻 **Cross-Platform Native Support**:
  - **Windows**: Core Audio (WASAPI) + Master Peak Meter + ASIO process matching + graceful shutdown via invisible `WM_QUERYENDSESSION` window handler.
  - **Linux**: PipeWire, PulseAudio (`pactl`), and direct ALSA hardware states (`/proc/asound`) + `systemd` user service.
  - **macOS**: CoreAudio power assertions (`pmset`) + DAW process tracking + `launchd` LaunchAgent.
- 🔴 **Guaranteed Shutdown Safety**: Intercepts OS shutdown, reboot, and logout events to ensure plugs are turned OFF before the computer powers down.
- ⚡ **~0.0% CPU Overhead**: Sleeps between polling intervals and reads memory-mapped audio registers without heavy digital signal processing or FFT calculations.

---

## 📁 Repository Structure

```text
tasmota-speaker-guard/
│
├── config.json              # Active configuration file (IPs, timeouts, processes)
├── config.example.json      # Template configuration
├── requirements.txt         # Python dependencies (with PEP 508 multi-OS markers)
├── LICENSE                  # MIT License
│
├── speaker_guard.py         # Main cross-platform daemon & CLI tool
├── speaker_guard.pyw        # Silent background launcher (Windows, no console window)
│
├── install_windows.ps1      # Windows autostart installer (Scheduled Task)
├── uninstall_windows.ps1    # Windows uninstaller
│
├── install_linux.sh         # Linux autostart installer (systemd user service)
├── uninstall_linux.sh       # Linux uninstaller
│
├── install_macos.sh         # macOS autostart installer (launchd LaunchAgent)
├── uninstall_macos.sh       # macOS uninstaller
│
├── start.bat / stop.bat     # Windows quick start / stop scripts
└── test.bat                 # Windows quick diagnostic script
```

---

## ⚙️ Configuration (`config.json`)

Adjust behavior easily through `config.json` without modifying any code:

```json
{
  "tasmota_ips": [
    "192.168.1.19"
  ],
  "timeout_seconds": 600,
  "poll_interval_seconds": 2.0,
  "turn_off_on_startup_if_silent": false,
  "turn_off_on_shutdown": true,
  "peak_audio_threshold": 0.001,
  "http_timeout_seconds": 2.5,
  "log_to_file": true,
  "log_file": "speaker_guard.log",
  "asio_detection_enabled": true,
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
```

### Options Reference:

| Key | Description | Default |
| :--- | :--- | :--- |
| `tasmota_ips` | List of target Tasmota plug IP addresses to control in parallel. | `["192.168.1.19"]` |
| `timeout_seconds` | Silence duration in seconds before turning plugs OFF. | `600` (10 min) |
| `poll_interval_seconds` | Audio polling frequency in seconds. | `2.0` |
| `turn_off_on_startup_if_silent` | If `true`, turns plugs OFF immediately at startup if no audio is playing. | `false` |
| `turn_off_on_shutdown` | If `true`, sends `Power OFF` when the computer shuts down or logs off. | `true` |
| `peak_audio_threshold` | Peak amplitude threshold to filter out micro-noise and background hiss. | `0.001` |
| `asio_detection_enabled` | Enables process surveillance for direct ASIO-exclusive applications. | `true` |
| `asio_processes` | Executable patterns (case-insensitive wildcards) treated as active audio sources. | *(DAWs & games)* |

---

## 🚀 Installation & Autostart

### 🪟 Windows Setup

1. Install requirements:
   ```powershell
   pip install -r requirements.txt
   ```
2. Register the silent background Scheduled Task:
   ```powershell
   .\install_windows.ps1
   ```
   *(To uninstall: `.\uninstall_windows.ps1`)*

### 🐧 Linux Setup (Ubuntu, Debian, Arch, Fedora)

1. Make scripts executable and install the `systemd` user service:
   ```bash
   chmod +x *.sh
   ./install_linux.sh
   ```
2. The service starts automatically with your user session:
   ```bash
   systemctl --user status tasmota-speaker-guard.service
   ```
   *(To uninstall: `./uninstall_linux.sh`)*

### 🍏 macOS Setup

1. Make scripts executable and load the `launchd` LaunchAgent:
   ```bash
   chmod +x *.sh
   ./install_macos.sh
   ```
2. Verify the agent is active:
   ```bash
   launchctl list | grep tasmotaspeakerguard
   ```
   *(To uninstall: `./uninstall_macos.sh`)*

---

## 🧪 Diagnostic & CLI Usage

All configuration values can be overridden via command-line arguments:

```text
usage: speaker_guard.py [-h] [--ips IPS [IPS ...]] [--ip IP] [--timeout TIMEOUT]
                        [--interval INTERVAL] [--config CONFIG]
                        [--log-level {DEBUG,INFO,WARNING,ERROR}]
                        {run,test,status,on,off}
```

### Examples:

- **Run system and audio diagnostics:**
  ```bash
  python speaker_guard.py test
  ```
- **Test with custom IP addresses:**
  ```bash
  python speaker_guard.py test --ips 192.168.1.19 192.168.1.20
  ```
- **Check current power state of all plugs:**
  ```bash
  python speaker_guard.py status
  ```
- **Manually switch all plugs ON:**
  ```bash
  python speaker_guard.py on
  ```
- **Manually switch all plugs OFF:**
  ```bash
  python speaker_guard.py off
  ```
- **Run daemon with a 5-minute timeout (300 seconds):**
  ```bash
  python speaker_guard.py run --timeout 300
  ```

---

## 🛠️ How It Works Under the Hood

### Windows WASAPI & ASIO
Under Windows, standard applications output sound through the Windows Audio Engine (WASAPI). The script queries active session states and reads the master audio endpoint's peak meter.  
When an application uses direct **ASIO** (such as Rocksmith or DAWs communicating with hardware interfaces like Line 6, Focusrite, RME, etc.), the Windows audio mixer is completely bypassed. The script uses an ultra-fast Win32 toolhelp snapshot (< 10 ms) to track configured ASIO processes and keep the plugs active.

### Linux PipeWire, PulseAudio & ALSA
The Linux engine inspects audio sink states using `pactl list sinks` (`State: RUNNING`), checks active application streams via `sink-inputs`, and inspects kernel ALSA device status files (`/proc/asound/card*/pcm*p/sub*/status`).

### macOS CoreAudio & Power Assertions
On macOS, active playback creates system-level power assertions (`pmset -g assertions`) under `coreaudiod`. The daemon monitors these assertions alongside active digital audio workstation processes.

### Shutdown Safety
On Windows, a hidden top-level window catches `WM_QUERYENDSESSION` and `WM_ENDSESSION` before the OS terminates processes. On Linux and macOS, standard POSIX termination signals (`SIGTERM`, `SIGINT`) trigger the power-off callback prior to system halt.

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).
