"""Pair the FZ Bridge with Windows using the PIN shown on the Flipper."""
import asyncio
import sys

from bleak import BleakScanner
from winrt.windows.devices.bluetooth import BluetoothLEDevice
from winrt.windows.devices.enumeration import (
    DeviceInformation,
    DevicePairingKinds,
    DevicePairingProtectionLevel,
)

sys.path.insert(0, ".")
from host.fibp_host.bluetooth_transport import bridge_advertisement  # noqa: E402


async def main():
    print("Open Bluetooth mode in the bridge app on the Flipper...", flush=True)
    device = await BleakScanner.find_device_by_filter(bridge_advertisement, timeout=30)
    if device is None:
        print("FZ Bridge not found.")
        return 1
    print(f"Found {device.name} ({device.address})", flush=True)
    address = int(device.address.replace(":", ""), 16)
    ble = await BluetoothLEDevice.from_bluetooth_address_async(address)
    info = await DeviceInformation.create_from_id_async(ble.device_id)
    if info.pairing.is_paired:
        print("Already paired with Windows. Unpairing for a clean bond...", flush=True)
        await info.pairing.unpair_async()
        info = await DeviceInformation.create_from_id_async(ble.device_id)

    loop = asyncio.get_running_loop()
    custom = info.pairing.custom

    def handler(_sender, args):
        deferral = args.get_deferral()
        kind = args.pairing_kind
        print(f"Windows pairing request: {kind.name}", flush=True)
        if kind == DevicePairingKinds.PROVIDE_PIN:
            pin = input("Enter the PIN shown on the Flipper: ").strip()
            args.accept(pin)
        else:
            if args.pin:
                print(f"Confirm this PIN matches the Flipper: {args.pin}", flush=True)
            args.accept()
        deferral.complete()

    token = custom.add_pairing_requested(handler)
    try:
        kinds = (DevicePairingKinds.PROVIDE_PIN | DevicePairingKinds.CONFIRM_PIN_MATCH |
                 DevicePairingKinds.DISPLAY_PIN | DevicePairingKinds.CONFIRM_ONLY)
        result = await custom.pair_async(
            kinds, DevicePairingProtectionLevel.ENCRYPTION_AND_AUTHENTICATION)
        print("Authenticated pairing:", result.status.name, flush=True)
        if result.status.name not in ("PAIRED", "ALREADY_PAIRED"):
            result = await custom.pair_async(kinds, DevicePairingProtectionLevel.DEFAULT)
            print("Default pairing:", result.status.name, flush=True)
    finally:
        custom.remove_pairing_requested(token)
    print("Pairing result:", result.status.name, flush=True)
    ble.close()
    return 0 if result.status.name in ("PAIRED", "ALREADY_PAIRED") else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
