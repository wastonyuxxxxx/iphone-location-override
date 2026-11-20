# iPhone Location Override

在 Mac 上双击 **`iphone-location-override.app`**。应用会启动本机服务，并在默认浏览器打开控制页，无需启动 Codex 或打开终端。网页关掉后，可以点程序坞图标重新打开。

## 功能

| 功能 | 使用方式 |
| --- | --- |
| 检查 USB | 点「检查 USB 连接」，确认工具能打开 iPhone 的定位测试服务，并查看 iOS 版本。 |
| 选择测试地点 | 用地点名称或街道地址搜索 Apple 地图，选择结果自动填入坐标。也可以手动填写 WGS84 十进制度经纬度。 |
| 短时定位测试 | 核对坐标并确认开始。网页显示状态和剩余时间。时长默认 120 秒，可设为 1–180 秒。 |
| 恢复真实定位 | 随时点「恢复真实定位」，或等计时结束。恢复指令发出后，在 iPhone 的 Apple 地图里核对实际位置。 |
| 接龙管家拍照验证 | 在自己发布的私密测试表单中获取位置，用 iPhone 相机现场拍摄。看到照片缩略图后停在提交前。 |
| 终端备用入口 | 双击 `open-terminal.command`。菜单支持手动输入坐标、恢复定位和检查 USB。 |

## 首次运行

1. 准备一台装有 Python 3.9 或更新版本的 Mac。应用首次运行时会从 PyPI 安装依赖，放在 `~/Library/Application Support/iPhone Location Test`。以后启动会复用这套依赖。
2. 用数据线连接一台 iPhone，解锁并按提示信任这台 Mac。在 iPhone 的「设置 → 隐私与安全性 → 开发者模式」开启开发者模式，按系统提示重启并确认。
3. 双击应用，等浏览器打开，点击「检查 USB 连接」。首次安装依赖时可能需要稍等。如果应用启动失败，可以双击 `open-web.command` 打开网页备用入口并查看终端提示。若 Finder 无法直接运行脚本，在终端输入 `zsh `，将脚本拖进去后按回车。

地点搜索需要网络。点击「搜索」时，输入文字会发送给 Apple 地图。应用已内置编译好的搜索组件。若使用网页备用脚本，首次搜索可能需要本机的 Swift 编译器。搜索不可用时仍可手动填写经纬度。

## 一次完整测试

1. 在 iPhone 上打开自己已发布的私密测试签到填写页，保留「定位」和「现场拍照」两项。草稿预览模式会拦截照片上传。
2. 在网页工具选择公开测试地点，确认开始后等待「模拟中」。模拟作用于整台 iPhone，期间其他 App 也可能读到测试坐标。保持 USB 连接。
3. 在小程序点「获取位置」，对准白纸等无敏感内容现场拍摄。核对位置与照片缩略图，退出填写页。
4. 点击「恢复真实定位」或等倒计时结束。在 iPhone 的 Apple 地图点定位箭头，确认蓝点回到实际位置。

关闭浏览器标签页后，本机服务仍会继续计时。需要关闭服务时，在应用菜单里点退出应用，应用会等待服务的退出流程。如果 USB 断开、应用被强制关闭，或页面提示恢复状态未确认，请重新连接并解锁 iPhone，重新打开工具，点「恢复真实定位」，再到地图核对。

## 文件

| 文件 | 用途 |
| --- | --- |
| `iphone-location-override.app` | Finder 双击入口，自动打开网页。 |
| `open-web.command` | 网页备用入口，终端会显示启动信息。 |
| `open-terminal.command` | 终端备用入口。 |
| `workflow.py`、`requirements.txt` | 启动工具和固定 Python 依赖版本。 |
| `page.py`、`index.html`、`style.css`、`app.js` | 本机控制页及其服务。 |
| `location.py`、`search-place.swift` | USB 定位测试与 Apple 地图搜索。 |
| `mac-launcher.swift` | Finder 应用的启动器源码。 |
| `.runtime/` | 备用脚本的本机依赖和搜索组件。ZIP 不包含此目录，脚本会按需建立。 |

同一层的 `iphone-location-override.zip` 包含应用、备用入口和源码，用于备份或迁移。应用已封装网页和后端，可单独移动。通过备用脚本启动时，请保留整份源码文件夹。

## 验证记录

此前在 macOS 26.5.1 和 iOS 27.0.1 真机上，已在自用测试表单中确认测试地点和现场拍摄的照片都能显示，并在结束后确认恢复真实定位。地点名和详细地址都用 Apple 地图查询过。签到测试停在正式提交前。其他设备或 iOS 版本可先运行 USB 检查。

[Apple 开发者模式说明](https://developer.apple.com/documentation/xcode/enabling-developer-mode-on-a-device) · [pymobiledevice3 安装与连接说明](https://doronz88.github.io/pymobiledevice3/latest/installation/)
