# TECHART Lens Adapter Firmware Archive

This repository preserves all firmware versions for TECHART lens adapters, along with a Python tool to flash them from a laptop over Bluetooth — no Android phone needed.

The original update app (`com.techart.updateall`) was abandoned and crashes on modern Android. The firmware server at `techart-logic.com` is still alive as of **April 2026**, but may not be forever. Everything here was archived from it. The manufacturer's support documentation has been dead for years, which is exactly why this exists.

### Status

The full update flow was tested and confirmed working on a **TA-GA3** (Contax G → Sony E) running Contax G lenses on a Sony A7C. The adapter updated successfully and autofocus works normally after flashing.

The BLE protocol is the same across all adapters in this family, so the script should work for the others too — but they haven't been tested. If you try it on an LM-EA7, EOS-NEXplus, EOS-NEX III or EOS-iNEX II and it works, feel free to open a PR updating this section.

---

## Supported Adapters

| Adapter | Mount | Latest Firmware |
|---------|-------|----------------|
| **TA-GA3** | Contax G → Sony E | Ver 2.2.0 (2015-11-16) |
| **EOS-NEX III** | Canon EF → Sony E | Ver 1.2.0 (2015-10-20) |
| **EOS-NEXplus** | Canon EF → Sony E | Ver 4.0.0 (2019-04-20) |
| **EOS-iNEX II** | Canon EF → Sony E | Ver 3.0.0 (2015-08-29) |
| **LM-EA7** | Leica M → Sony E | Ver 7.0.0 (2020-12-11) |

---

## Firmware Files

### TA-GA3
| Version | Date | File |
|---------|------|------|
| Ver 2.2.0 | 2015-11-16 | `firmware/TA-GA3/G-NEX3-2015-11-16.bin` |
| Ver 2.1.0 (A7R2) | 2015-10-07 | `firmware/TA-GA3/G-NEX3A7R2-20151007.bin` |
| Ver 1.0.5 | 2015-02-27 | `firmware/TA-GA3/G-NEX3-20150227.bin` |
| Ver 1.0.4 | 2015-01-31 | `firmware/TA-GA3/G-NEX3-20150131.bin` |
| Ver 1.0.3 | 2014-12-22 | `firmware/TA-GA3/G-NEX3-20141222.bin` |
| Ver 1.0.2 | 2014-05-25 | `firmware/TA-GA3/G-NEX3-20140525.bin` |
| Ver 1.0.0 | 2014-04-26 | `firmware/TA-GA3/G-NEX3-20140426.bin` |

### EOS-NEX III
| Version | Date | File |
|---------|------|------|
| Ver 1.2.0 | 2015-10-20 | `firmware/EOS-NEX-III/eos-nex3-20151205.bin` |
| Ver 1.1.0 | 2015-09-11 | `firmware/EOS-NEX-III/eos-nex3-20150911.bin` |

### EOS-NEXplus
| Version | Date | File |
|---------|------|------|
| Ver 4.0.0 | 2019-04-20 | `firmware/EOS-NEXplus/eos-nexplus-20190420.bin` |
| Ver 3.0.0 | 2018-06-04 | `firmware/EOS-NEXplus/eos-nexplus-20180604.bin` |
| Ver 2.0.0 | 2018-03-12 | `firmware/EOS-NEXplus/eos-nexplus-20180312.bin` |
| Ver 1.0.0 | 2018-01-05 | `firmware/EOS-NEXplus/eos-nexplus-20180105.bin` |

### EOS-iNEX II
| Version | Date | File |
|---------|------|------|
| Ver 3.0.0 | 2015-08-29 | `firmware/EOS-iNEX-II/eos-nex2-20150829.bin` |
| Ver 2.0.1 beta | 2015-02-27 | `firmware/EOS-iNEX-II/EOS-iNEX2-20150227.bin` |
| Ver 2.0.0 | 2014-02-26 | `firmware/EOS-iNEX-II/EOS-iNEX2-20140226.bin` |

### LM-EA7
| Version | Date | File |
|---------|------|------|
| Ver 7.0.0 (A7R4) | 2020-12-11 | `firmware/LM-EA7/m-nex201211.bin` |
| Ver 6.0.0 | 2018-01-05 | `firmware/LM-EA7/m-nex180105.bin` |
| Ver 5.0.0 | 2017-02-14 | `firmware/LM-EA7/m-nex170511.bin` |
| Ver 4.0.0 | 2016-09-05 | `firmware/LM-EA7/m-nex160905.bin` |
| Ver 3.0.0 | 2016-06-26 | `firmware/LM-EA7/m-nex160626.bin` |
| Ver 2.0.0 | 2016-04-15 | `firmware/LM-EA7/m-nex160415.bin` |
| Ver 1.0.0 | 2016-03-20 | `firmware/LM-EA7/m-nex160320.bin` |

---

## Flashing from a Laptop

The `techart_updater.py` script connects to the adapter over BLE and flashes any firmware file directly from macOS, Linux, or Windows — no Android required. See below how to enable pairing mode on the adaptor. 

### Requirements

```bash
python3 -m venv techart-env
source techart-env/bin/activate   # Windows: techart-env\Scripts\activate
pip install bleak requests
```

### Usage

**Interactive mode** (fetches firmware list from server, downloads and flashes):
```bash
python3 techart_updater.py
```

**Using a local firmware file** (works even if the server is down):
```bash
python3 techart_updater.py --firmware firmware/TA-GA3/G-NEX3-2015-11-16.bin
```

**If you already know the BLE address**:
```bash
python3 techart_updater.py --firmware firmware/TA-GA3/G-NEX3-2015-11-16.bin --address AA:BB:CC:DD:EE:FF
```

**List available firmware versions** (from server):
```bash
python3 techart_updater.py --list
```

### Enabling Bluetooth on the adapter

The adapter doesn't broadcast over Bluetooth by default. To enable it, switch the camera to manual mode, set the aperture to f/90, take a shot, then turn the camera off. Bluetooth will turn on automatically.

### Finding your adapter's BLE address

Once Bluetooth is on, scan for it with:

```bash
python3 -c "
import asyncio
from bleak import BleakScanner

async def scan():
    print('Scanning 10s...')
    for d in await BleakScanner.discover(timeout=10):
        print(f'  {d.address}  {d.name}')

asyncio.run(scan())
"
```

Look for a device named after your adapter model (e.g. `TA-GA3`). On macOS, addresses are UUIDs like `4CAD6BCB-8F0D-759A-B1BB-0E466250F3B6`. On Linux/Windows they look like `AA:BB:CC:DD:EE:FF`.

### Tips

- Keep the adapter within ~50 cm of your laptop during the update.
- The transfer takes about 6 minutes (118K bytes at 16 bytes/packet).
- The adapter will disconnect and reboot automatically once all data is received — this is normal.

---

## How It Works

The protocol was reverse-engineered from the original APK (`com.techart.updateall` v1.0). Key details:

- **BLE service:** `0000fff0-0000-1000-8000-00805f9b34fb`
- **Command characteristic (fff1):** write commands, read responses
- **Data characteristic (fff6):** write firmware packets (only appears after `RESET_REMOVE`)
- **Packet size:** 16 bytes
- **Firmware offset:** first 10,240 bytes of each `.bin` are a boot header and are skipped
- **Checksum:** CRC-16 (poly 0x8005, init 0x0000, reflected I/O)
- **Commands:**
  - `RESET_REMOVE` — `0x01 0xA5` — puts adapter into update mode
  - `UPDATE_FIREWARE` — `0xA5 0xAB` — triggers flash and reboot
  - `REQ_CRC` — `0x01 0x80` — requests CRC verification

---

## License

Firmware files are © TECHART. Archived here for preservation only.  
The `techart_updater.py` script is released to the public domain.
