# 🔊 Tasmota Speaker Guard

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-green.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tasmota](https://img.shields.io/badge/Compatible-Tasmota%20HTTP%20REST-orange.svg)](https://tasmota.github.io/docs/Commands/)

> **Gestionnaire intelligent et multiplateforme d'alimentation d'enceintes connectées via prises Tasmota.**  
> Détecte en temps réel l'activité audio du système (Windows WASAPI/ASIO, Linux PipeWire/PulseAudio/ALSA, macOS CoreAudio) et pilote automatiquement l'allumage et l'extinction de vos prises Tasmota.

---

## ✨ Points forts

- 🟢 **Allumage instantané** dès qu'un son est émis par le système (musique, vidéo, jeu, DAW, appel...).
- ⏳ **Extinction temporisée (10 min par défaut)** : coupure automatique après une période de silence prolongé.
- 🎛️ **Support ASIO direct** : ne coupe plus vos enceintes de monitoring lors de l'utilisation d'interfaces audio directes et logiciels comme **Rocksmith**, **Reaper**, **FL Studio**, **Ableton Live**, **Cubase**, ou des simulateurs d'amplis (Helix, Neural DSP, Amplitube...).
- 🔌 **Multi-prises Tasmota** : pilotez une ou plusieurs prises simultanément en parallèle (enceintes gauche/droite indépendantes, caisson de basse, etc.).
- 💻 **Multiplateforme natif** :
  - **Windows** : Windows Core Audio (WASAPI) + Peak Meter + ASIO + arrêt propre via fenêtre invisible `WM_QUERYENDSESSION`.
  - **Linux** : PipeWire, PulseAudio (`pactl`) et ALSA direct (`/proc/asound`) + service `systemd` utilisateur.
  - **macOS** : CoreAudio assertions (`pmset`) + détection DAW + agent `launchd`.
- 🔴 **Extinction garantie à l'arrêt du PC** : extinction systématique des prises lors de l'arrêt, redémarrage ou déconnexion.
- ⚡ **CPU ~ 0%** : le script dort entre chaque vérification et lit directement les variables en mémoire sans traitement audio lourd.

---

## 📁 Structure du projet

```text
tasmota-speaker-guard/
│
├── config.json              # Configuration active (IPs, délais, processus)
├── config.example.json      # Exemple de configuration par défaut
├── requirements.txt         # Dépendances Python (PEP 508 multi-OS)
├── LICENSE                  # Licence MIT
│
├── speaker_guard.py         # Moteur principal multiplateforme & CLI
├── speaker_guard.pyw        # Lanceur silencieux en arrière-plan (Windows)
│
├── install_windows.ps1      # Installation démarrage automatique (Windows)
├── uninstall_windows.ps1    # Désinstallation (Windows)
│
├── install_linux.sh         # Installation service systemd (Linux)
├── uninstall_linux.sh       # Désinstallation (Linux)
│
├── install_macos.sh         # Installation LaunchAgent launchd (macOS)
├── uninstall_macos.sh       # Désinstallation (macOS)
│
├── start.bat / stop.bat     # Contrôles rapides (Windows)
└── test.bat                 # Diagnostic rapide (Windows)
```

---

## ⚙️ Configuration (`config.json`)

Le fichier `config.json` permet de paramétrer le service :

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

### Options de configuration :

| Paramètre | Description |
| :--- | :--- |
| `tasmota_ips` | Liste des adresses IP des prises Tasmota à contrôler en parallèle. |
| `timeout_seconds` | Délai de silence en secondes avant extinction automatique (`600` = 10 minutes). |
| `poll_interval_seconds` | Intervalle de scrutation en secondes (`2.0` recommandé). |
| `turn_off_on_startup_if_silent` | Si `true`, éteint d'office la prise au démarrage si aucun son n'est joué. |
| `turn_off_on_shutdown` | Si `true`, force l'extinction des enceintes lors de l'arrêt du PC. |
| `peak_audio_threshold` | Seuil crête WASAPI pour ignorer les micro-bruits de fond. |
| `asio_detection_enabled` | Active la surveillance des applications et DAW en mode direct ASIO. |
| `asio_processes` | Liste des masques de noms d'exécutables considérés comme sources audio actives. |

---

## 🚀 Installation & Démarrage automatique

### 🪟 Sous Windows

1. Installez les dépendances :
   ```powershell
   pip install -r requirements.txt
   ```
2. Installez le démarrage automatique en tâche de fond (Tâche planifiée) :
   ```powershell
   .\install_windows.ps1
   ```
   *(Pour désinstaller : `.\uninstall_windows.ps1`)*

### 🐧 Sous Linux (Ubuntu, Debian, Arch, Fedora)

1. Rendez les scripts exécutables et installez le service `systemd` utilisateur :
   ```bash
   chmod +x *.sh
   ./install_linux.sh
   ```
2. Le service tourne sous votre session et démarre au boot :
   ```bash
   systemctl --user status tasmota-speaker-guard.service
   ```
   *(Pour désinstaller : `./uninstall_linux.sh`)*

### 🍏 Sous macOS

1. Rendez les scripts exécutables et installez le `LaunchAgent` :
   ```bash
   chmod +x *.sh
   ./install_macos.sh
   ```
2. Le service est pris en charge par `launchd` :
   ```bash
   launchctl list | grep tasmotaspeakerguard
   ```
   *(Pour désinstaller : `./uninstall_macos.sh`)*

---

## 🧪 Diagnostic & Ligne de commande (CLI)

Toutes les options peuvent être surchargées en ligne de commande :

```text
usage: speaker_guard.py [-h] [--ips IPS [IPS ...]] [--ip IP] [--timeout TIMEOUT]
                        [--interval INTERVAL] [--config CONFIG]
                        [--log-level {DEBUG,INFO,WARNING,ERROR}]
                        {run,test,status,on,off}
```

### Exemples :

- **Tester la détection audio et la connectivité des prises :**
  ```bash
  python speaker_guard.py test
  ```
- **Tester avec des IPs spécifiques :**
  ```bash
  python speaker_guard.py test --ips 192.168.1.19 192.168.1.20
  ```
- **Afficher le statut actuel des prises :**
  ```bash
  python speaker_guard.py status
  ```
- **Allumer manuellement toutes les prises :**
  ```bash
  python speaker_guard.py on
  ```
- **Éteindre manuellement toutes les prises :**
  ```bash
  python speaker_guard.py off
  ```
- **Lancer avec un délai de 5 minutes (300 secondes) :**
  ```bash
  python speaker_guard.py run --timeout 300
  ```

---

## 📜 Licence

Ce projet est sous licence [MIT](LICENSE).
