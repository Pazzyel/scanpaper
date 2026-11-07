## 净页 ScanPaper 1.1.1

修复空白纸张预览中的导入提示偏移。反复切换 A1–A4 纸型或横纵方向时，提示会保持在纸张中心。

| 下载文件 | 适用平台 | 启动方式 |
|---|---|---|
| Windows-x64.zip | Windows 10 1809+ / 11 x64 | 完整解压，运行 ScanPaper.exe |
| macOS-arm64.zip | macOS 14.4+，Apple Silicon | 解压，将 ScanPaper.app 拖到应用程序文件夹 |
| macOS-x64.zip | macOS 14.4+，Intel | 解压，将 ScanPaper.app 拖到应用程序文件夹 |
| Linux-x64.tar.gz | Ubuntu 22.04+ x64 / 兼容 glibc 2.35+ 的桌面系统 | 用 tar -xzf 解压，运行 ScanPaper/ScanPaper |

- macOS 使用系统的 Command+O / Command+S 快捷键。
- macOS 应用仅采用临时签名，尚未使用 Apple Developer ID 签名或公证；首次打开可能需要在系统“隐私与安全性”中允许此应用。
- Linux 面向带 X11 或 XWayland 的桌面环境，不覆盖 Alpine/musl、无图形界面的服务器或其他 CPU 架构。
- macOS ZIP 和 Linux tar.gz 保留动态库符号链接及可执行权限；请完整解压，不要只复制主程序。
- 发布前会在各自系统执行核心测试、独立目录解压测试及原生 Qt 插件的窗口、排版和 PDF 导出自检；Linux 的原生窗口测试使用 Xvfb。

附源码 ZIP、第三方许可证和 SHA256 校验文件。未做 OCR、多页合并或拍摄透视校正。
