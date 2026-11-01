# 净页 ScanPaper

Windows、macOS、Linux 中文扫描件清理与单页 PDF 排版工具。离线处理 JPG，保留黑色笔画并将背景转为透明，支持 A1–A4、横纵方向、毫米排版、拖动缩放。

[下载免安装版](https://github.com/Pazzyel/scanpaper/releases/latest) · [所有发布版本](https://github.com/Pazzyel/scanpaper/releases) · [跨平台构建状态](https://github.com/Pazzyel/scanpaper/actions/workflows/build.yml)

## 使用打包版

| 平台 | 文件 | 运行方式 |
|---|---|---|
| Windows 10 1809+ / 11 x64 | `Windows-x64.zip` | 完整解压，运行 `ScanPaper.exe` |
| macOS 14.4+，Apple Silicon | `macOS-arm64.zip` | 解压，将 `ScanPaper.app` 拖到“应用程序” |
| macOS 14.4+，Intel | `macOS-x64.zip` | 解压，将 `ScanPaper.app` 拖到“应用程序” |
| Ubuntu 22.04+ x64 / 兼容桌面系统 | `Linux-x64.tar.gz` | `tar -xzf 文件名.tar.gz`，运行 `./ScanPaper/ScanPaper` |

无需安装 Python 或 pip 依赖，中文字体已内置。Windows/Linux 必须保留整个文件夹；macOS 必须保留完整 `.app`。Linux 需要 glibc 2.35+ 和 X11 或 XWayland 桌面环境；不支持 Alpine/musl、无图形界面的服务器或 Linux ARM。

macOS 包采用临时签名，尚无 Apple Developer ID 签名或公证。首次打开可能被系统拦截，请按系统“隐私与安全性”中的提示允许打开。没有关闭 Gatekeeper 或修改系统安全设置的要求。

操作方法见 `使用说明.txt`。macOS 导入/导出使用 `⌘O` / `⌘S`；其他系统使用 `Ctrl+O` / `Ctrl+S`。

## 开发与构建

使用 Python 3.12，在目标系统原生构建。PyInstaller 不在 Windows 上交叉生成 macOS/Linux 应用。

Windows：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe main.py
.\.venv\Scripts\python.exe tools/build.py --native-smoke
```

macOS / Linux：

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-build.txt
.venv/bin/python main.py
.venv/bin/python tools/build.py --native-smoke
```

Linux 构建机需要 Qt 的 XCB 桌面库；准确的 apt 安装列表见 `.github/workflows/build.yml`。无显示器的构建机可使用 `xvfb-run -a .venv/bin/python tools/build.py --native-smoke`。这些是开发机的构建依赖；PyInstaller 会将所需 XCB 辅助库一并收集到包内。

构建脚本收集许可证、生成 ICO/ICNS 图标、执行测试和打包，再从归档解压到独立目录，在不含开发环境路径的环境中执行自检。macOS 使用 `ditto`、Linux 使用 tar.gz，保留 Qt 动态库的符号链接与执行权限。

输出位于 `release/`，文件名由应用版本、系统和架构决定；同时提供源码 ZIP、SHA256 清单和 `verification/` 下的自检报告及截图。`--skip-source` 可在矩阵构建中避免重复生成源码包。

GitHub Actions 会在推送 main、PR 或手动触发时构建四个目标。推送与应用版本一致的 `v*` 标签后，只有四个目标全部通过，才发布对应 Release。未配置 Apple Developer ID 或公证凭据，因此不会声称应用已通过 Apple 公证。

## 验证与处理边界

```sh
python -m unittest discover -s tests -v
python main.py --self-test 输出目录
```

打包版也支持 `--self-test 输出目录`；macOS 命令行入口为 `ScanPaper.app/Contents/MacOS/ScanPaper`。默认使用 Qt offscreen 平台，设置 `QT_QPA_PLATFORM=windows`、`cocoa` 或 `xcb` 可测试原生桌面插件。

导出使用原图分辨率和当前处理参数；预览使用缩略图，细节可能略有差异。默认保护黑块、细字和标点，不自动删除小连通区域。浅灰污迹与浅色笔画可能需要手动调节。原图和透明棋盘格开关只影响预览。

输入为 JPG/JPEG，单张上限 6400 万像素；输出为单页图像 PDF。不包含 OCR、多页合并、拍摄透视校正、曲面展平或颜色保留。

## 许可证与 Windows DLL 修复

应用代码为 MIT；第三方组件遵循各自许可证。内置 Noto Sans CJK SC 字体采用 SIL Open Font License 1.1。完整许可证见发布包 `licenses`，macOS 应用内位于 `Contents/Resources/licenses`。

使用仓库内的 `ScanPaper.spec` 构建。Windows 构建会排除其他软件可能提供的同名 ICU DLL，使用操作系统的 ICU 接口，避免遮蔽系统 DLL 引发 Qt 启动失败。此排除规则只用于 Windows，不删除 macOS/Linux 所需的 ICU 动态库。
