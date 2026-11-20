import fcntl
import os
import subprocess
import sys
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
REQUIREMENTS = PACKAGE / "requirements.txt"


def prepare_runtime():
    runtime = Path(os.environ.get("IPHONE_LOCATION_RUNTIME") or PACKAGE / ".runtime")
    runtime.mkdir(parents=True, exist_ok=True)
    python = runtime / "venv" / "bin" / "python"
    installed_requirements = runtime / "installed-requirements.txt"
    current_requirements = REQUIREMENTS.read_bytes()

    with (runtime / "setup.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if python.is_file() and installed_requirements.is_file():
            if installed_requirements.read_bytes() == current_requirements:
                return python

        print("首次运行将从 PyPI 下载依赖，安装在本机的工具运行目录内。", flush=True)
        subprocess.run([sys.executable, "-m", "venv", str(python.parent.parent)], check=True)
        subprocess.run(
            [str(python), "-m", "pip", "--isolated", "--disable-pip-version-check", "install",
             "--index-url", "https://pypi.org/simple", "--no-cache-dir", "--timeout", "20",
             "--retries", "2", "-r", str(REQUIREMENTS)],
            check=True,
        )
        subprocess.run([str(python), "-m", "pip", "--disable-pip-version-check", "check"], check=True)
        installed_requirements.write_bytes(current_requirements)
        return python


def main():
    if sys.version_info < (3, 9):
        raise SystemExit("此工具需要 Python 3.9 或更新版本。")

    if sys.argv[1:2] == ["--web"]:
        python = prepare_runtime()
        os.execv(str(python), [str(python), str(PACKAGE / "page.py"), *sys.argv[2:]])

    print("iPhone 定位测试\n1  设置短时测试定位\n2  恢复真实定位\n3  检查 USB 连接\n0  退出")
    choice = input("请选择 0–3 ").strip()
    if choice == "0":
        return
    if choice == "1":
        latitude = float(input("纬度（-90 至 90） "))
        longitude = float(input("经度（-180 至 180） "))
        seconds = int(input("持续秒数（1 至 180，直接回车为 120） ").strip() or "120")
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180 or not 1 <= seconds <= 180:
            raise ValueError("经纬度或持续时间超出范围。")
        print(f"测试点 {latitude}, {longitude}，最长 {seconds} 秒。期间其他 App 也可能读到测试位置。")
        if input("确认开始请输入 Y ").strip().lower() != "y":
            return
        args = ["--seconds", str(seconds), "--", str(latitude), str(longitude)]
    elif choice == "2":
        args = ["--clear"]
    elif choice == "3":
        args = ["--check"]
    else:
        raise ValueError("请选择 0、1、2 或 3。")

    python = prepare_runtime()
    os.execv(str(python), [str(python), str(PACKAGE / "location.py"), *args])


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        raise SystemExit("已取消。") from None
    except ValueError as error:
        raise SystemExit(f"输入有误。{error}") from None
    except (OSError, subprocess.CalledProcessError):
        raise SystemExit("工具未能启动。请检查当前目录可写、Python 3 可用，并在首次安装时连接网络。") from None
