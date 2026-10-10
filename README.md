

[HamTech-IC7100-Windows11-Fixed-v0.6.2.zip](https://github.com/user-attachments/files/33289958/HamTech-IC7100-Windows11-Fixed-v0.6.2.zip)
# HamTech M0FXB Modification — Windows 11 IC-7100 Panel

Complete Windows edition v0.6.2 for a Windows 11 **Intel/AMD 64-bit PC** and Icom IC-7100. Includes the IC-705 source photograph, live control panel, Windows connection chooser, installers and GitHub-ready source. No previous version or Raspberry Pi is required.

## Easy installation

1. Extract the entire ZIP to a permanent folder, for example `Documents\HamTech-IC7100`. Do not run it inside the ZIP.
2. If the Icom USB driver is not already installed, disconnect the radio USB cable and install it from [Icom's official download page](https://www.icomjapan.com/support/firmware_driver/1974/). Follow [Icom's Windows 11 installation guide](https://www.icomjapan.com/support/manual/1768/). Reconnect the radio after driver installation.
3. Open the extracted `ic7100-panel` folder and double-click **INSTALL-WINDOWS.cmd**. It installs Python 3.13 if needed, installs the application's dependencies and creates a desktop shortcut. Internet access is required. Follow any Windows installer prompts.
4. Power on the radio and connect its rear USB port to the PC with a USB data cable. Keep the original control head connected. Set CI-V to **19200 baud / address 88h**.
5. Double-click **START-PANEL.cmd** or the **HamTech IC-7100 Panel** desktop shortcut.
6. Choose the radio's **CI-V COM port**, choose its **USB AUDIO CODEC** capture input, and click **START PANEL**. Your default browser opens the panel automatically.

The server console must stay open. Stop the server with **Ctrl+C in that console** before changing connections or running another copy. Closing the connection chooser does not stop the server. Settings save in `windows-settings.json` beside the launcher. Keep the extracted folder in place so the desktop shortcut continues to work.

Setup uses Windows Package Manager (WinGet) for Python and pip for Python dependencies. The ZIP includes all application files but does not contain an offline Python installer or offline package cache. Icom's driver is downloaded separately and is not redistributed in this ZIP.

If WinGet is unavailable, install **Python 3.13 64-bit**, including Tcl/Tk, from [python.org](https://www.python.org/downloads/windows/), then run INSTALL-WINDOWS.cmd again. Standard Python installations are detected from the usual per-user/system locations or the Python launcher. Windows on ARM has not been targeted by this package.

## Choose the correct COM port

The radio normally creates two serial interfaces. Choose **A / CI-V**, not B / data-GPS. The chooser displays each COM number, description and available serial number. Identify the interface in Windows Device Manager if the driver does not show A/B in its description. COM numbers depend on your PC; do not assume COM3 or COM4.

The launcher lists devices without probing or transmitting to the radio. REFRESH DEVICES updates the list after plugging in USB. Close other radio-control programs using the same port. A wrong interface or baud rate produces connection errors in the panel.

You can also launch manually from a terminal in this folder, replacing COM5 and audio index 3 with your own values:

```powershell
.\.venv\Scripts\python.exe server.py --port COM5 --baud 19200 --address 88 --audio-device 3
```

Then open **http://127.0.0.1:7100**. The server listens only on this PC's loopback interface.

## Received audio / waterfall

On the IC-7100 select **ACC/USB Output Select: AF** and a suitable AF output level. In the launcher select the IC-7100's USB AUDIO CODEC **input**, preferably the Windows WASAPI entry. The input must support mono 48 kHz capture.

Windows may list the same device under several audio APIs. Explicit selection avoids ambiguous automatic detection. If capture is denied, allow microphone access and desktop-app microphone access in **Windows Settings → Privacy & security → Microphone**. Close applications holding the input exclusively.

The waterfall is generated from real received USB audio. CI-V carries control data, not audio. Missing audio never generates demonstration signals. Radio control can still work while audio capture is unavailable. SET shows audio errors and levels.

## Controls

| Feature | Operation |
| --- | --- |
| Frequency | Click the enlarged frequency to type MHz or select a band. |
| Bands | HF/VHF/UHF starting presets and one-touch 118 MHz AM airband. Model/region restrictions apply. |
| VFO | Drag/scroll the photo dial; use tuning buttons or arrow keys. Select VFO A/B. |
| Meter | Click to select Signal, Power or SWR, using radio CI-V readings. |
| Memories | Bank A–E, channels 1–99; preview and recall existing memories. |
| Filters | FIL1/FIL2/FIL3 using the radio's stored presets. |
| NR / NB | On/off buttons and strength/level settings. |
| Repeater | Off / negative / positive shift, offset, CTCSS TX tone and RX tone squelch. |
| Audio scope | Live AF spectrum/waterfall, HOLD, span, reference, smoothing and display levels. |
| RF sweep | Separate 61-point Pi/PC-driven receiver sweep using real S-meter samples, with centre-restoration attempt. |
| Display | Real IC-705 photo, black surround, resize/fit, screen-only view and fullscreen. |
| Settings | Receiver controls, audio levels, USB reconnect and connection information. |

Power and SWR update **during transmission through the radio's own controls**. The application does not key TX. Power is an approximate meter percentage, not calibrated watts. SWR and S readings interpolate the manual's scale anchors; unavailable readings show —.

RF SWEEP retunes the receiver, changes received audio and enters VFO mode. It is separate from the IC-7100 control head's native scope and does not retrieve a native RF spectrum stream. Stop the sweep and allow centre restoration before stopping the server. If USB fails, restoration can fail and the radio may remain off-centre. Read the complete [control and protocol notes](README-LINUX.md) for metre conversions, memory-label limits and sweep behaviour. Its Linux install commands apply only to the Pi version.

Settings includes NR/NB and levels; preamp/attenuator/AGC; notch controls; filter shape; AF/RF gain/squelch; Twin PBT; CW pitch; RTTY twin-peak; dial lock; tone/tone squelch and voice squelch. Valid options depend on the radio's band and mode. There is no memory writing/deletion or PTT.

## Troubleshooting

- **Nothing installs:** read the setup console. Check internet, WinGet and Python installation. Do not double-click the Python source as a substitute for setup.
- **No COM ports:** install the Icom driver, power on the radio, reconnect USB and refresh. Check Device Manager.
- **Radio disconnected:** choose A/CI-V; match baud/address; close competing software. Use SET → RECONNECT USB after replugging.
- **Wrong audio input:** stop the server with Ctrl+C, choose another USB AUDIO CODEC input and start again.
- **Port 7100 already in use:** stop the previous server. The launcher reopens a running panel; it does not change that server's connection settings.
- **Browser does not open:** visit http://127.0.0.1:7100 in Edge, Chrome or another modern browser.
- **Desktop shortcut stops working:** restore the extracted folder to its original location or rerun setup from its new location.

## GitHub and licensing

Upload the **contents of `ic7100-panel`** to the root of your GitHub repository. Include the `web` folder, source, requirements, Windows scripts, README and licenses. Attach the complete ZIP to a GitHub Release. Do not commit `.venv`, `windows-settings.json`, shortcuts or caches; `.gitignore` excludes these.

Application code is MIT licensed. The bundled photo and its adaptations are CC BY-SA 4.0, credited to Batchman99 and VORON SPb; preserve [third-party notices](THIRD_PARTY_NOTICES.md) and [photo attribution](web/assets/ATTRIBUTION.md). This is independent software, not endorsed by Icom.

The image below is the bundled source photo, **not a runtime screenshot**:

![IC-705 source photograph used by the panel](web/assets/ic705.png)

## Status

Python compilation, JavaScript syntax, Linux-host server HTTP smoke checks and mocked CI-V meter decoding passed. **The Windows installer/chooser and radio hardware have not been tested on Windows.** This is a source-based installer package, not a compiled standalone EXE. Windows runtime, audio-device compatibility and new CI-V features await hardware confirmation.

## v0.6.2 startup fixes

Python detection now checks installed 3.12/3.13/3.14 runtimes and tolerates missing launcher versions. Setup saves `install-log.txt`. Server errors stay visible and save to `server-error.txt`. Launcher callback errors save to `launcher-error.txt`. Double-click `DIAGNOSE.cmd` to list dependencies and devices into `diagnostics.txt` without probing the radio.
