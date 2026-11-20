import argparse
import asyncio
import fcntl
import json
import signal
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from pymobiledevice3.exceptions import PyMobileDevice3Exception
from pymobiledevice3.usbmux import list_devices
from pymobiledevice3.remote.userspace_tunnel import UserspaceRsdTunnel
from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
from pymobiledevice3.services.dvt.instruments.location_simulation import LocationSimulation


@asynccontextmanager
async def location_service():
    wired = [device for device in await list_devices() if device.is_usb]
    if len(wired) != 1:
        raise RuntimeError("请通过 USB 连接且只连接一台已信任的 iPhone。")
    async with UserspaceRsdTunnel(
        serial=wired[0].serial,
        autopair=False,
        remotepairing_fallback=False,
    ) as device:
        async with DvtProvider(device) as provider, LocationSimulation(provider) as location:
            yield location, device.product_version


def report_text(message, **details):
    print(message, flush=True)


def report_json(message, **details):
    print(json.dumps({"message": message, **details}, ensure_ascii=False), flush=True)


async def check_connection(report=report_text):
    async with location_service() as (_, ios_version):
        report(f"已连接 USB iPhone（iOS {ios_version}），定位服务可用。", event="connected", ios=ios_version)


async def clear_location(report=report_text):
    async with location_service() as (location, _):
        await asyncio.wait_for(location.clear(), timeout=15)
        report("已向 iPhone 发送清除模拟定位指令。", event="cleared")


async def simulate(latitude, longitude, seconds, report=report_text):
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    signals = (signal.SIGHUP, signal.SIGINT, signal.SIGTERM)
    for signum in signals:
        loop.add_signal_handler(signum, stop.set)

    try:
        async with location_service() as (location, _):
            if stop.is_set():
                return
            try:
                await asyncio.wait_for(location.set(latitude, longitude), timeout=15)
                report(f"已设置模拟定位 {latitude}, {longitude}，持续最多 {seconds} 秒。", event="active")
                try:
                    await asyncio.wait_for(stop.wait(), timeout=seconds)
                except asyncio.TimeoutError:
                    pass
            finally:
                await asyncio.wait_for(location.clear(), timeout=15)
                report("已向 iPhone 发送清除模拟定位指令。", event="cleared")
    finally:
        for signum in signals:
            loop.remove_signal_handler(signum)


def main():
    parser = argparse.ArgumentParser(description="通过 USB 短时模拟 iPhone 定位，测试结束时清除模拟。")
    parser.add_argument("latitude", type=float, nargs="?")
    parser.add_argument("longitude", type=float, nargs="?")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--clear", action="store_true", help="清除当前模拟定位。")
    action.add_argument("--check", action="store_true", help="检查 USB 和定位服务。")
    parser.add_argument("--seconds", type=int, default=120)
    parser.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    report = report_json if args.json else report_text
    if args.clear or args.check:
        if args.latitude is not None or args.longitude is not None:
            parser.error("此操作无需输入坐标。")
        operation = clear_location if args.clear else check_connection
        asyncio.run(asyncio.wait_for(operation(report), timeout=35))
        return
    if args.latitude is None or args.longitude is None:
        parser.error("请输入纬度和经度。")
    if not -90 <= args.latitude <= 90 or not -180 <= args.longitude <= 180:
        parser.error("纬度须在 ±90 以内，经度须在 ±180 以内。")
    if not 1 <= args.seconds <= 180:
        parser.error("测试时间须在 1 至 180 秒以内。")
    lock_file = Path(tempfile.gettempdir()) / "iphone-location-test.lock"
    with lock_file.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("已有一轮定位测试正在运行。请按 Control+C 结束上一轮后再开始。")
        asyncio.run(simulate(args.latitude, args.longitude, args.seconds, report))


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, PyMobileDevice3Exception, asyncio.TimeoutError) as error:
        detail = str(error) or type(error).__name__
        raise SystemExit(
            f"操作未完成（{detail}）。请检查 USB 连接、设备信任和开发者模式。"
            "若测试中断，请重新连接后运行「恢复真实定位」，并在 Apple 地图中核对。"
        ) from None
