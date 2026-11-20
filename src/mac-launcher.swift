import AppKit

private let applicationName = "iPhone 定位测试"
private let addressPrefix = "已打开本机页面 "

final class Launcher: NSObject, NSApplicationDelegate {
    private var server: Process?
    private var output: Pipe?
    private var buffer = Data()
    private var lastOutput = ""
    private var pageURL: URL?
    private var quitting = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        let items = NSMenu()
        let reopen = NSMenuItem(title: "打开定位页面", action: #selector(openPage), keyEquivalent: "o")
        reopen.target = self
        items.addItem(reopen)
        items.addItem(.separator())
        items.addItem(NSMenuItem(title: "退出 \(applicationName)", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q"))

        let appMenu = NSMenu()
        let root = NSMenuItem()
        root.submenu = items
        appMenu.addItem(root)
        NSApp.mainMenu = appMenu
        startServer()
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows: Bool) -> Bool {
        openPage()
        return false
    }

    @objc private func openPage() {
        guard let pageURL else { return }
        if !NSWorkspace.shared.open(pageURL) {
            showMessage("无法打开默认浏览器", detail: "请在浏览器地址栏打开 \(pageURL.absoluteString)")
        }
    }

    private func startServer() {
        guard let script = Bundle.main.url(forResource: "workflow", withExtension: "py") else {
            showMessage("找不到定位工具", detail: "请从完整的工作流 ZIP 重新解压应用。")
            NSApp.terminate(nil)
            return
        }

        let process = Process()
        let pipe = Pipe()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        process.arguments = ["python3", script.path, "--web", "--no-browser"]
        var environment = ProcessInfo.processInfo.environment
        let path = environment["PATH"] ?? "/usr/bin:/bin:/usr/sbin:/sbin"
        environment["PATH"] = path + ":/opt/homebrew/bin:/usr/local/bin"
        let support = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        let runtime = support.appendingPathComponent("iPhone Location Test", isDirectory: true)
        if environment["IPHONE_LOCATION_RUNTIME"] == nil {
            environment["IPHONE_LOCATION_RUNTIME"] = runtime.path
        }
        environment["PYTHONUTF8"] = "1"
        process.environment = environment
        process.standardInput = FileHandle.nullDevice
        process.standardOutput = pipe
        process.standardError = pipe

        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let chunk = handle.availableData
            if chunk.isEmpty {
                handle.readabilityHandler = nil
            } else {
                DispatchQueue.main.async { self?.readOutput(chunk) }
            }
        }
        process.terminationHandler = { [weak self] _ in
            DispatchQueue.main.async { self?.serverStopped() }
        }

        do {
            try process.run()
            server = process
            output = pipe
        } catch {
            pipe.fileHandleForReading.readabilityHandler = nil
            showMessage("定位工具未能启动", detail: error.localizedDescription)
            NSApp.terminate(nil)
        }
    }

    private func readOutput(_ data: Data) {
        guard pageURL == nil, !quitting else { return }
        buffer.append(data)
        while let newline = buffer.firstIndex(of: 10) {
            let line = String(decoding: buffer[..<newline], as: UTF8.self)
            buffer.removeSubrange(...newline)
            if !line.isEmpty {
                lastOutput = String(line.prefix(360))
            }
            guard line.hasPrefix(addressPrefix),
                  let url = URL(string: String(line.dropFirst(addressPrefix.count))),
                  url.scheme == "http", url.host == "127.0.0.1", url.port != nil else { continue }
            pageURL = url
            buffer.removeAll()
            openPage()
            return
        }
    }

    private func serverStopped() {
        output?.fileHandleForReading.readabilityHandler = nil
        output = nil
        server = nil
        if quitting {
            NSApp.reply(toApplicationShouldTerminate: true)
            return
        }
        if pageURL == nil {
            let detail = lastOutput.isEmpty ? "请确认 Python 3.9 或更新版本可用，首次启动时连接网络。" : lastOutput
            NSLog("定位工具未能启动。%@", detail)
            showMessage("定位工具未能启动", detail: detail)
        } else {
            showMessage("定位工具已停止", detail: "如正在测试，请重新打开工具并恢复真实定位，然后在 iPhone 的 Apple 地图核对。")
        }
        NSApp.terminate(nil)
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard let server, server.isRunning else { return .terminateNow }
        if !quitting {
            quitting = true
            server.terminate()
        }
        return .terminateLater
    }

    private func showMessage(_ title: String, detail: String) {
        let alert = NSAlert()
        alert.messageText = title
        alert.informativeText = detail
        alert.addButton(withTitle: "好")
        NSApp.activate(ignoringOtherApps: true)
        alert.runModal()
    }
}

let app = NSApplication.shared
let launcher = Launcher()
app.setActivationPolicy(.regular)
app.delegate = launcher
app.run()
