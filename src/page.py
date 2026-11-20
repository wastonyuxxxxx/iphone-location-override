import argparse
import json
import math
import os
import secrets
import signal
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
ASSETS = {
    "/": ("index.html", "text/html"),
    "/style.css": ("style.css", "text/css"),
    "/app.js": ("app.js", "text/javascript"),
}


class LocationTool:
    def __init__(self):
        self.lock = threading.Lock()
        self.process = None
        self.phase = "idle"
        self.message = "连接并解锁 iPhone 后，可以先检查 USB 连接。"
        self.ios = None
        self.point = None
        self.deadline = None

    def status(self):
        with self.lock:
            remaining = None
            if self.deadline is not None:
                remaining = max(0, math.ceil(self.deadline - time.monotonic()))
            return {
                "phase": self.phase,
                "message": self.message,
                "ios": self.ios,
                "point": self.point,
                "remaining": remaining,
            }

    def run(self, action, point=None):
        with self.lock:
            if self.process is not None:
                if action == "restore" and self.phase in ("starting", "active"):
                    self.phase = "restoring"
                    self.message = "正在结束本轮模拟并恢复定位…"
                    self.process.terminate()
                    return True
                return False

            if action == "start":
                args = ["--seconds", str(point["seconds"]), "--", str(point["latitude"]), str(point["longitude"])]
                phase, message = "starting", "正在通过 USB 设置测试位置…"
            elif action == "restore":
                args = ["--clear"]
                phase, message = "restoring", "正在发送恢复定位指令…"
            else:
                args = ["--check"]
                phase, message = "checking", "正在检查 iPhone 和定位服务…"
                self.ios = None

            self.process = subprocess.Popen(
                [sys.executable, str(PACKAGE / "location.py"), "--json", *args],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding="utf-8",
                errors="replace",
                start_new_session=True,
            )
            self.phase, self.message, self.point = phase, message, point
            threading.Thread(target=self.observe, args=(self.process, action), daemon=True).start()
            return True

    def observe(self, process, action):
        result = None
        with process.stdout as output:
            for line in output:
                try:
                    event = json.loads(line)
                except ValueError:
                    if line.startswith("操作未完成（"):
                        result = line.strip()
                    continue
                if not isinstance(event, dict):
                    continue
                kind = event.get("event")
                with self.lock:
                    if kind == "active" and self.phase == "starting":
                        self.phase = "active"
                        self.deadline = time.monotonic() + self.point["seconds"]
                        self.message = "定位指令已发送。请在自用测试表单中点「获取位置」。"
                    elif kind == "cleared":
                        self.phase = "restoring"
                        self.deadline = None
                        self.message = "已发送恢复指令，正在结束连接…"
                        result = "已发送恢复指令。请在 Apple 地图中确认当前位置。"
                    elif kind == "connected":
                        self.ios = event["ios"]
                        result = f"USB 连接可用 · iOS {self.ios}"

        code = process.wait()
        with self.lock:
            self.process = self.deadline = self.point = None
            self.phase = "idle" if code == 0 and result else "error"
            if result:
                self.message = result
            elif action == "check":
                self.message = "连接检查未完成。请检查数据线、设备信任和开发者模式。"
            else:
                self.message = "定位状态未确认。请重新连接 iPhone 并点「恢复真实定位」。"

    def close(self):
        with self.lock:
            process = self.process
            if process is None:
                return
            if self.phase in ("starting", "active"):
                process.terminate()
        try:
            code = process.wait(timeout=36)
        except subprocess.TimeoutExpired:
            process.kill()
            code = process.wait()
        if code != 0:
            print("退出时未能确认定位恢复。请重新打开工具并运行「恢复真实定位」。", flush=True)


def validate_point(point):
    limits = {"latitude": (-90, 90), "longitude": (-180, 180), "seconds": (1, 180)}
    for key, (low, high) in limits.items():
        value = point.get(key)
        types = (int,) if key == "seconds" else (int, float)
        if type(value) not in types or not low <= value <= high:
            raise ValueError("请输入有效的经纬度和 1 至 180 秒的整数时长。")
    return {key: point[key] for key in limits}


def search_places(query):
    bundled_helper = PACKAGE / "search-place"
    runtime = Path(os.environ.get("IPHONE_LOCATION_RUNTIME") or PACKAGE / ".runtime")
    helper = bundled_helper if bundled_helper.is_file() else runtime / "search-place"
    source = PACKAGE / "search-place.swift"
    if helper != bundled_helper and (
        not helper.is_file() or helper.stat().st_mtime_ns < source.stat().st_mtime_ns
    ):
        runtime.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=runtime) as staging:
            build_path = Path(staging) / helper.name
            build = subprocess.run(
                ["/usr/bin/swiftc", "-module-cache-path", str(runtime / "swift-cache"), "-o", str(build_path), str(source)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=70,
            )
            if build.returncode != 0:
                raise RuntimeError("Apple 地图搜索组件未能启动。你仍可手动输入经纬度。")
            build_path.replace(helper)
    result = subprocess.run(
        [str(helper)],
        input=query + "\n",
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        encoding="utf-8",
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError("Apple 地图搜索暂不可用。你仍可手动输入经纬度。")
    return json.loads(result.stdout)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def respond(self, status, content_type, data):
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(data)

    def json_response(self, status, data):
        self.respond(status, "application/json", json.dumps(data, ensure_ascii=False).encode())

    def local_request(self):
        return self.headers.get("Host") == self.server.local_host

    def token_is_valid(self):
        given = self.headers.get("X-Local-Token", "").encode("utf-8")
        return secrets.compare_digest(given, self.server.token.encode("ascii"))

    def do_GET(self):
        if not self.local_request():
            self.json_response(403, {"error": "请从本机启动入口打开页面。"})
        elif self.path == "/api/status" and self.token_is_valid():
            self.json_response(200, self.server.tool.status())
        elif self.path in ASSETS:
            name, content_type = ASSETS[self.path]
            data = (PACKAGE / name).read_bytes()
            if self.path == "/":
                data = data.replace(b"%%LOCAL_TOKEN%%", self.server.token.encode("ascii"))
            self.respond(200, content_type, data)
        else:
            self.json_response(404, {"error": "页面不存在。"})

    def do_POST(self):
        if not (self.local_request() and self.token_is_valid() and self.headers.get("Origin") == self.server.origin):
            self.json_response(403, {"error": "请从本机启动入口打开页面。"})
            return
        action = {"/api/start": "start", "/api/restore": "restore", "/api/check": "check", "/api/search": "search"}.get(self.path)
        if action is None:
            self.json_response(404, {"error": "操作不存在。"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 1 <= size <= 512 or self.headers.get_content_type() != "application/json":
                raise ValueError("请求格式有误。")
            point = json.loads(self.rfile.read(size))
            if not isinstance(point, dict):
                raise ValueError("请求格式有误。")
            if action == "search":
                query = point.get("query")
                if not isinstance(query, str) or not 1 <= len(query.strip()) <= 100 or "\n" in query or "\r" in query:
                    raise ValueError("请输入 1 至 100 个字符的地点或地址。")
                if not self.server.search_lock.acquire(blocking=False):
                    self.json_response(409, {"error": "上一条搜索正在进行，请稍候。"})
                    return
                try:
                    results = search_places(query.strip())
                finally:
                    self.server.search_lock.release()
                self.json_response(200, {"places": results})
                return
            point = validate_point(point) if action == "start" else None
            if not self.server.tool.run(action, point):
                self.json_response(409, {"error": "当前操作尚未结束。"})
                return
        except (UnicodeError, json.JSONDecodeError, RecursionError):
            self.json_response(400, {"error": "请求格式有误。"})
            return
        except ValueError as error:
            self.json_response(400, {"error": str(error)})
            return
        except subprocess.TimeoutExpired:
            self.json_response(504, {"error": "Apple 地图搜索超时。请重试或手动输入经纬度。"})
            return
        except RuntimeError as error:
            self.json_response(503, {"error": str(error)})
            return
        except OSError:
            self.json_response(503, {"error": "定位工具暂时无法启动。"})
            return
        self.json_response(202, self.server.tool.status())


def main():
    parser = argparse.ArgumentParser(description="打开本机的 iPhone 定位测试页面。")
    parser.add_argument("--no-browser", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        server.tool = LocationTool()
        server.local_host = f"127.0.0.1:{server.server_port}"
        server.origin = f"http://{server.local_host}"
        server.token = secrets.token_urlsafe(32)
        server.search_lock = threading.Lock()

        def interrupt(_number, _frame):
            raise KeyboardInterrupt

        for number in (signal.SIGHUP, signal.SIGTERM):
            signal.signal(number, interrupt)

        print(f"已打开本机页面 {server.origin}", flush=True)
        print("请保持本终端窗口打开。按 Control+C 结束运行。", flush=True)
        if not args.no_browser:
            threading.Thread(target=webbrowser.open, args=(server.origin,), daemon=True).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.tool.close()


if __name__ == "__main__":
    main()
