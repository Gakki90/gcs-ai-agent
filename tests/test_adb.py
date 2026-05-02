from autoglm_phone_controller.adb import AdbDevice, parse_adb_devices


def test_parse_adb_devices_with_descriptions() -> None:
    output = """List of devices attached
R5CT123ABC	device usb:336592896X product:o1qxxx model:SM_G9910 device:o1q transport_id:1
emulator-5554	offline

"""

    assert parse_adb_devices(output) == [
        AdbDevice(
            serial="R5CT123ABC",
            state="device",
            description="usb:336592896X product:o1qxxx model:SM_G9910 device:o1q transport_id:1",
        ),
        AdbDevice(serial="emulator-5554", state="offline", description=""),
    ]


def test_parse_adb_devices_empty() -> None:
    assert parse_adb_devices("List of devices attached\n\n") == []
