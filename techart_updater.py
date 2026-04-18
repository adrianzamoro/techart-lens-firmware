#!/usr/bin/env python3
"""
TECHART Lens Adapter BLE Firmware Updater
Replicates the TECHART Update app (com.techart.updateall) from a laptop.

Supported adapters (from firmware server):
  LM-EA7, EOS-NEXplus, EOS-NEX III, TA-GA3, and others.

Requirements:
  pip install bleak requests

Usage:
  python3 techart_updater.py
  python3 techart_updater.py --firmware /path/to/local.bin  (skip download)
  python3 techart_updater.py --list                         (list available firmware)
"""

import asyncio
import sys
import time
import argparse
import struct
import requests

try:
    from bleak import BleakScanner, BleakClient
    from bleak.backends.characteristic import BleakGATTCharacteristic
except ImportError:
    print("ERROR: 'bleak' not installed. Run: pip install bleak")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────
#  Protocol constants (extracted from APK classes.dex)
# ─────────────────────────────────────────────────────────────
RESET_REMOVE    = bytes([0x01, 0xA5])   # "Prepare for update" command
UPDATE_FIREWARE = bytes([0xA5, 0xAB])   # "Apply firmware" command
REQ_CRC         = bytes([0x01, 0x80])   # "Verify CRC" request

FIRMWARE_OFFSET = 10240   # First 10 KB of binary is a boot header; skip it
PACKET_SIZE     = 16      # Bytes per BLE write packet

FIRMWARE_INDEX_URL = "http://www.techart-logic.com/g-nex3/firmware/firmware.txt"

# GATT service / characteristic UUIDs
SERVICE_UUID  = "0000fff0-0000-1000-8000-00805f9b34fb"
CHAR_CMD_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"   # mChar1: commands
CHAR_DAT_UUID = "0000fff6-0000-1000-8000-00805f9b34fb"   # mChar6: firmware data

# ─────────────────────────────────────────────────────────────
#  CRC-16 (table extracted verbatim from APK static initializer)
#  Polynomial 0x8005, reflected I/O, init 0x0000
# ─────────────────────────────────────────────────────────────
_CRC16_TABLE_RAW = (
    b'\x00\x00\x00\x00\xc1\xc0\x00\x00\x81\xc1\x00\x00\x40\x01\x00\x00'
    b'\x01\xc3\x00\x00\xc0\x03\x00\x00\x80\x02\x00\x00\x41\xc2\x00\x00'
    b'\x01\xc6\x00\x00\xc0\x06\x00\x00\x80\x07\x00\x00\x41\xc7\x00\x00'
    b'\x00\x05\x00\x00\xc1\xc5\x00\x00\x81\xc4\x00\x00\x40\x04\x00\x00'
    b'\x01\xcc\x00\x00\xc0\x0c\x00\x00\x80\r\x00\x00A\xcd\x00\x00'
    b'\x00\x0f\x00\x00\xc1\xcf\x00\x00\x81\xce\x00\x00\x40\x0e\x00\x00'
    b'\x00\x0a\x00\x00\xc1\xca\x00\x00\x81\xcb\x00\x00\x40\x0b\x00\x00'
    b'\x01\xc9\x00\x00\xc0\x09\x00\x00\x80\x08\x00\x00\x41\xc8\x00\x00'
    b'\x01\xd8\x00\x00\xc0\x18\x00\x00\x80\x19\x00\x00\x41\xd9\x00\x00'
    b'\x00\x1b\x00\x00\xc1\xdb\x00\x00\x81\xda\x00\x00\x40\x1a\x00\x00'
    b'\x00\x1e\x00\x00\xc1\xde\x00\x00\x81\xdf\x00\x00\x40\x1f\x00\x00'
    b'\x01\xdd\x00\x00\xc0\x1d\x00\x00\x80\x1c\x00\x00\x41\xdc\x00\x00'
    b'\x00\x14\x00\x00\xc1\xd4\x00\x00\x81\xd5\x00\x00\x40\x15\x00\x00'
    b'\x01\xd7\x00\x00\xc0\x17\x00\x00\x80\x16\x00\x00\x41\xd6\x00\x00'
    b'\x01\xd2\x00\x00\xc0\x12\x00\x00\x80\x13\x00\x00\x41\xd3\x00\x00'
    b'\x00\x11\x00\x00\xc1\xd1\x00\x00\x81\xd0\x00\x00\x40\x10\x00\x00'
    b'\x01\xf0\x00\x00\xc0\x30\x00\x00\x80\x31\x00\x00\x41\xf1\x00\x00'
    b'\x00\x33\x00\x00\xc1\xf3\x00\x00\x81\xf2\x00\x00\x40\x32\x00\x00'
    b'\x00\x36\x00\x00\xc1\xf6\x00\x00\x81\xf7\x00\x00\x40\x37\x00\x00'
    b'\x01\xf5\x00\x00\xc0\x35\x00\x00\x80\x34\x00\x00\x41\xf4\x00\x00'
    b'\x00\x3c\x00\x00\xc1\xfc\x00\x00\x81\xfd\x00\x00\x40\x3d\x00\x00'
    b'\x01\xff\x00\x00\xc0\x3f\x00\x00\x80\x3e\x00\x00\x41\xfe\x00\x00'
    b'\x01\xfa\x00\x00\xc0\x3a\x00\x00\x80\x3b\x00\x00\x41\xfb\x00\x00'
    b'\x00\x39\x00\x00\xc1\xf9\x00\x00\x81\xf8\x00\x00\x40\x38\x00\x00'
    b'\x00\x28\x00\x00\xc1\xe8\x00\x00\x81\xe9\x00\x00\x40\x29\x00\x00'
    b'\x01\xeb\x00\x00\xc0\x2b\x00\x00\x80\x2a\x00\x00\x41\xea\x00\x00'
    b'\x01\xee\x00\x00\xc0\x2e\x00\x00\x80\x2f\x00\x00\x41\xef\x00\x00'
    b'\x00\x2d\x00\x00\xc1\xed\x00\x00\x81\xec\x00\x00\x40\x2c\x00\x00'
    b'\x01\xe4\x00\x00\xc0\x24\x00\x00\x80\x25\x00\x00\x41\xe5\x00\x00'
    b'\x00\x27\x00\x00\xc1\xe7\x00\x00\x81\xe6\x00\x00\x40\x26\x00\x00'
    b'\x00\x22\x00\x00\xc1\xe2\x00\x00\x81\xe3\x00\x00\x40\x23\x00\x00'
    b'\x01\xe1\x00\x00\xc0\x21\x00\x00\x80\x20\x00\x00\x41\xe0\x00\x00'
    b'\x01\xa0\x00\x00\xc0\x60\x00\x00\x80\x61\x00\x00\x41\xa1\x00\x00'
    b'\x00\x63\x00\x00\xc1\xa3\x00\x00\x81\xa2\x00\x00\x40\x62\x00\x00'
    b'\x00\x66\x00\x00\xc1\xa6\x00\x00\x81\xa7\x00\x00\x40\x67\x00\x00'
    b'\x01\xa5\x00\x00\xc0\x65\x00\x00\x80\x64\x00\x00\x41\xa4\x00\x00'
    b'\x00\x6c\x00\x00\xc1\xac\x00\x00\x81\xad\x00\x00\x40\x6d\x00\x00'
    b'\x01\xaf\x00\x00\xc0\x6f\x00\x00\x80\x6e\x00\x00\x41\xae\x00\x00'
    b'\x01\xaa\x00\x00\xc0\x6a\x00\x00\x80\x6b\x00\x00\x41\xab\x00\x00'
    b'\x00\x69\x00\x00\xc1\xa9\x00\x00\x81\xa8\x00\x00\x40\x68\x00\x00'
    b'\x00\x78\x00\x00\xc1\xb8\x00\x00\x81\xb9\x00\x00\x40\x79\x00\x00'
    b'\x01\xbb\x00\x00\xc0\x7b\x00\x00\x80\x7a\x00\x00\x41\xba\x00\x00'
    b'\x01\xbe\x00\x00\xc0\x7e\x00\x00\x80\x7f\x00\x00\x41\xbf\x00\x00'
    b'\x00\x7d\x00\x00\xc1\xbd\x00\x00\x81\xbc\x00\x00\x40\x7c\x00\x00'
    b'\x01\xb4\x00\x00\xc0\x74\x00\x00\x80\x75\x00\x00\x41\xb5\x00\x00'
    b'\x00\x77\x00\x00\xc1\xb7\x00\x00\x81\xb6\x00\x00\x40\x76\x00\x00'
    b'\x00\x72\x00\x00\xc1\xb2\x00\x00\x81\xb3\x00\x00\x40\x73\x00\x00'
    b'\x01\xb1\x00\x00\xc0\x71\x00\x00\x80\x70\x00\x00\x41\xb0\x00\x00'
    b'\x00\x50\x00\x00\xc1\x90\x00\x00\x81\x91\x00\x00\x40\x51\x00\x00'
    b'\x01\x93\x00\x00\xc0\x53\x00\x00\x80\x52\x00\x00\x41\x92\x00\x00'
    b'\x01\x96\x00\x00\xc0\x56\x00\x00\x80\x57\x00\x00\x41\x97\x00\x00'
    b'\x00\x55\x00\x00\xc1\x95\x00\x00\x81\x94\x00\x00\x40\x54\x00\x00'
    b'\x01\x9c\x00\x00\xc0\x5c\x00\x00\x80\x5d\x00\x00\x41\x9d\x00\x00'
    b'\x00\x5f\x00\x00\xc1\x9f\x00\x00\x81\x9e\x00\x00\x40\x5e\x00\x00'
    b'\x00\x5a\x00\x00\xc1\x9a\x00\x00\x81\x9b\x00\x00\x40\x5b\x00\x00'
    b'\x01\x99\x00\x00\xc0\x59\x00\x00\x80\x58\x00\x00\x41\x98\x00\x00'
    b'\x01\x88\x00\x00\xc0\x48\x00\x00\x80\x49\x00\x00\x41\x89\x00\x00'
    b'\x00\x4b\x00\x00\xc1\x8b\x00\x00\x81\x8a\x00\x00\x40\x4a\x00\x00'
    b'\x00\x4e\x00\x00\xc1\x8e\x00\x00\x81\x8f\x00\x00\x40\x4f\x00\x00'
    b'\x01\x8d\x00\x00\xc0\x4d\x00\x00\x80\x4c\x00\x00\x41\x8c\x00\x00'
    b'\x00\x44\x00\x00\xc1\x84\x00\x00\x81\x85\x00\x00\x40\x45\x00\x00'
    b'\x01\x87\x00\x00\xc0\x47\x00\x00\x80\x46\x00\x00\x41\x86\x00\x00'
    b'\x01\x82\x00\x00\xc0\x42\x00\x00\x80\x43\x00\x00\x41\x83\x00\x00'
    b'\x00\x41\x00\x00\xc1\x81\x00\x00\x81\x80\x00\x00\x40\x40\x00\x00'
)
# Parse as 256 little-endian 32-bit integers
CRC16_TABLE = struct.unpack_from('<256I', _CRC16_TABLE_RAW)

def crc16_update(crc: int, byte: int) -> int:
    """Update CRC-16 with one byte, using the app's exact lookup table."""
    index = (crc ^ byte) & 0xFF
    return ((crc >> 8) ^ CRC16_TABLE[index]) & 0xFFFF

def compute_crc16(data: bytes, start: int = 0, init: int = 0) -> int:
    """Compute CRC-16 over data[start:] with given initial value."""
    crc = init
    for b in data[start:]:
        crc = crc16_update(crc, b)
    return crc

# ─────────────────────────────────────────────────────────────
#  Firmware index helpers
# ─────────────────────────────────────────────────────────────
def fetch_firmware_index(url: str = FIRMWARE_INDEX_URL) -> list[dict]:
    """Download and parse firmware.txt into a list of firmware entries."""
    print(f"Fetching firmware list from {url} ...")
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()

    entries = []
    for line in resp.text.splitlines():
        line = line.strip()
        if not line or len(line) < 10:
            continue
        parts = line.split(",", 3)
        if len(parts) < 3:
            continue
        entries.append({
            "title":       parts[0].strip(),
            "description": parts[1].strip(),
            "url":         parts[2].strip(),
        })
    return entries


def download_firmware(url: str) -> bytes:
    """Download a firmware binary."""
    print(f"Downloading firmware from {url} ...")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.content
    print(f"Downloaded {len(data)} bytes.")
    return data


# ─────────────────────────────────────────────────────────────
#  BLE updater
# ─────────────────────────────────────────────────────────────
class TechartUpdater:
    def __init__(self, firmware: bytes):
        self.firmware = firmware
        self.total    = len(firmware)
        self.pos      = FIRMWARE_OFFSET           # start after the boot header
        self.crc      = 0
        self._done_event   = asyncio.Event()
        self._write_event  = asyncio.Event()
        self._notify_queue: asyncio.Queue = asyncio.Queue()

    # ── notifications from mChar1 (fff1) ──────────────────────
    def _on_notify(self, _char: BleakGATTCharacteristic, data: bytearray):
        self._notify_queue.put_nowait(bytes(data))

    # ── write next 16-byte packet to mChar6 (with retries) ────
    async def _write_packet(self, client: BleakClient, char_dat):
        if self.pos >= self.total:
            return False                      # nothing left to send

        chunk = self.firmware[self.pos: self.pos + PACKET_SIZE]
        chunk = chunk.ljust(PACKET_SIZE, b'\x00')   # pad last packet if needed

        # update running CRC exactly like the app
        for b in chunk:
            self.crc = crc16_update(self.crc, b)

        for attempt in range(4):
            try:
                await client.write_gatt_char(char_dat, chunk, response=True)
                break
            except Exception as e:
                if attempt == 3:
                    raise
                wait = 0.5 * (attempt + 1)
                print(f"\n  Write failed ({e}), retrying in {wait:.1f}s ...")
                await asyncio.sleep(wait)

        pct = int(100 * (self.pos - FIRMWARE_OFFSET) / max(1, self.total - FIRMWARE_OFFSET))
        print(f"\r  [{pct:3d}%] sent {self.pos - FIRMWARE_OFFSET}/{self.total - FIRMWARE_OFFSET} bytes  ",
              end="", flush=True)

        self.pos += PACKET_SIZE
        return True

    # ── main update flow ──────────────────────────────────────
    async def run(self, address: str):
        print(f"\nConnecting to {address} ...")
        async with BleakClient(address, timeout=30.0) as client:
            print("Connected.")

            # ── discover GATT services ─────────────────────
            services = client.services
            char_cmd = None
            char_dat = None
            for svc in services:
                if "fff0" in str(svc.uuid):
                    for ch in svc.characteristics:
                        uid = str(ch.uuid)
                        if "fff1" in uid:
                            char_cmd = ch
                        if "fff6" in uid:
                            char_dat = ch

            if char_cmd is None or char_dat is None:
                print("ERROR: Required GATT characteristics fff1/fff6 not found.")
                print("Make sure you selected the correct device.")
                return False

            print(f"Found service fff0 | cmd=fff1 ({char_cmd.uuid}) | data=fff6 ({char_dat.uuid})")

            # ── step 1: send RESET_REMOVE to fff1 ─────────
            print("Sending RESET_REMOVE command ...")
            await client.write_gatt_char(char_cmd, RESET_REMOVE, response=True)
            await asyncio.sleep(1.0)          # give adapter time to prepare

            # ── step 2: stream firmware in 16-byte packets ─
            print(f"\nSending firmware ({self.total - FIRMWARE_OFFSET} bytes in "
                  f"{(self.total - FIRMWARE_OFFSET + 15) // 16} packets of {PACKET_SIZE} bytes) ...")

            while self.pos < self.total:
                ok = await self._write_packet(client, char_dat)
                if not ok:
                    break
                # Slightly longer inter-packet gap to avoid overwhelming the adapter.
                # The original app was callback-driven and likely ran at ~30-50ms per packet.
                await asyncio.sleep(0.05)

            print("\nAll firmware data sent.")

            # ── step 3: send UPDATE_FIREWARE command ──────
            # The adapter may disconnect immediately after this as it reboots to flash.
            # That is normal — treat a disconnection here as success.
            print("Sending UPDATE_FIREWARE command ...")
            try:
                await client.write_gatt_char(char_cmd, UPDATE_FIREWARE, response=True)
                await asyncio.sleep(0.3)
            except Exception:
                print("Adapter disconnected after UPDATE_FIREWARE — this is normal (it is rebooting).")
                print(f"\nFirmware transfer complete. CRC=0x{self.crc:04X}")
                print("Power-cycle the adapter to finish flashing.")
                return True

            # ── step 4: send REQ_CRC then read back the device's CRC ──
            print(f"Sending REQ_CRC (local CRC=0x{self.crc:04X}) ...")
            try:
                await client.write_gatt_char(char_cmd, REQ_CRC, response=True)
                await asyncio.sleep(0.3)
                response = bytes(await client.read_gatt_char(char_cmd))
                if len(response) >= 2:
                    device_crc = struct.unpack_from('<H', response)[0]
                    if device_crc == self.crc:
                        print(f"CRC verified (0x{self.crc:04X}) — update successful!")
                    else:
                        print(f"WARNING: CRC mismatch! local=0x{self.crc:04X} device=0x{device_crc:04X}")
                        print("The adapter may still have flashed correctly; try cycling power.")
                else:
                    print(f"Device response: {response.hex()} (could not parse CRC)")
            except Exception:
                print("Adapter disconnected during CRC check — it is likely rebooting to apply firmware.")

            return True


# ─────────────────────────────────────────────────────────────
#  Interactive helpers
# ─────────────────────────────────────────────────────────────
def choose(prompt: str, options: list[str]) -> int:
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    while True:
        raw = input(f"\n{prompt}: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        print(f"  Please enter a number between 1 and {len(options)}.")


async def scan_for_device(name_hint: str, timeout: float = 10.0) -> str | None:
    """Scan for a BLE device whose name contains name_hint."""
    print(f"\nScanning for BLE device matching '{name_hint}' ({timeout:.0f}s) ...")
    found = {}

    def cb(device, _adv):
        if device.name and name_hint.lower() in device.name.lower():
            found[device.address] = device.name

    scanner = BleakScanner(cb)
    await scanner.start()
    await asyncio.sleep(timeout)
    await scanner.stop()

    if not found:
        return None

    if len(found) == 1:
        addr, name = next(iter(found.items()))
        print(f"Found: {name}  ({addr})")
        return addr

    # multiple matches
    items = list(found.items())
    idx = choose("Multiple devices found — pick one",
                 [f"{n}  ({a})" for a, n in items])
    return items[idx][0]


# ─────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────
async def async_main():
    parser = argparse.ArgumentParser(description="TECHART BLE Firmware Updater")
    parser.add_argument("--list",     action="store_true",
                        help="Print available firmware versions and exit")
    parser.add_argument("--firmware", metavar="FILE",
                        help="Use a local .bin file instead of downloading")
    parser.add_argument("--address",  metavar="ADDR",
                        help="BLE address of the adapter (skip scanning)")
    args = parser.parse_args()

    # ── fetch firmware index ──────────────────────────────────
    try:
        index = fetch_firmware_index()
    except Exception as e:
        print(f"Could not reach firmware server: {e}")
        if args.firmware:
            print("Using local firmware file — adapter model selection skipped.")
            index = []
        else:
            print("Pass --firmware /path/to/file.bin to use a local file.")
            sys.exit(1)

    if args.list:
        print("\nAvailable firmware versions:")
        for e in index:
            print(f"  [{e['title']}]  {e['description']}")
        return

    # ── select target adapter model ───────────────────────────
    if args.firmware:
        print(f"Loading firmware from {args.firmware} ...")
        with open(args.firmware, "rb") as f:
            firmware_data = f.read()
        # still need to know the BT device name for scanning
        if index:
            models = sorted(set(e["title"] for e in index))
            print("\nWhich adapter model are you updating?")
            model_idx = choose("Enter number", models)
            device_name = models[model_idx]
        else:
            device_name = input("Enter the Bluetooth name of the adapter: ").strip()
    else:
        # group entries by title
        models = sorted(set(e["title"] for e in index))
        print("\nWhich adapter model are you updating?")
        model_idx = choose("Enter number", models)
        device_name = models[model_idx]

        # filter firmware versions for that model
        versions = [e for e in index if e["title"] == device_name]
        print(f"\nAvailable firmware for {device_name}:")
        ver_idx = choose("Choose firmware version",
                         [e["description"] for e in versions])
        chosen = versions[ver_idx]

        try:
            firmware_data = download_firmware(chosen["url"])
        except Exception as e:
            print(f"Download failed: {e}")
            sys.exit(1)

    if len(firmware_data) < FIRMWARE_OFFSET:
        print(f"ERROR: firmware file is too small ({len(firmware_data)} bytes); "
              f"expected at least {FIRMWARE_OFFSET} bytes.")
        sys.exit(1)

    # ── find BLE device ───────────────────────────────────────
    if args.address:
        ble_address = args.address
    else:
        ble_address = await scan_for_device(device_name)
        if ble_address is None:
            print(f"\nNo BLE device matching '{device_name}' found.")
            print("Tips:")
            print("  • Make sure the adapter is powered on and within range.")
            print("  • Some adapters only advertise when a lens is attached.")
            print("  • Try: python3 techart_updater.py --address XX:XX:XX:XX:XX:XX")
            sys.exit(1)

    # ── run the update ────────────────────────────────────────
    updater = TechartUpdater(firmware_data)
    success = await updater.run(ble_address)
    if success:
        print("\nDone. Power-cycle the adapter to load the new firmware.")
    else:
        print("\nUpdate did not complete. Check the device and try again.")


def main():
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\nAborted.")


if __name__ == "__main__":
    main()
