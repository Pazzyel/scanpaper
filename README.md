# 净页 ScanPaper

Windows 中文扫描件清理与单页 PDF 排版工具。离线处理 JPG，保留黑色笔画并将背景转为透明，支持 A1–A4、横纵方向、毫米排版、拖动缩放。

## 使用打包版

[下载 Windows 免安装版](https://github.com/Pazzyel/scanpaper/releases/latest) · [所有发布版本](https://github.com/Pazzyel/scanpaper/releases)

完整解压发布 ZIP，运行 `ScanPaper.exe`。无需安装运行环境。操作方法见 `使用说明.txt`。所有 `_internal` 文件必须与 EXE 一起保留。

## 开发与构建

在 Windows x64、Python 3.12 环境中执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe main.py
.\.venv\Scripts\python.exe tools/build.py
```

构建脚本收集许可证、生成图标、运行测试、生成 EXE、在精简环境中运行打包自检，然后输出 `release/ScanPaper-1.0.0-Windows-x64.zip` 和源码 ZIP、SHA256 文件。
仅开发和重新构建需要下载依赖；终端用户不需要联网或安装依赖。

单独自检：`ScanPaper.exe --self-test 输出目录`，输出合成扫描样例、导出 PDF、界面截图与 `self-test.json`。自检用 Qt offscreen 平台；正常启动用 Windows 桌面平台。

## 结构与处理

`scanpaper/processing.py` 处理亮度校正和软透明度；`scanpaper/model.py` 记录毫米坐标；`scanpaper/canvas.py` 提供拖动和等比例缩放；`scanpaper/pdf.py` 负责裁切、透明遮罩与原子保存；`scanpaper/app.py` 管理界面和后台任务。

处理保留原始分辨率，预览使用缩略图。背景估计在固定的工作尺度上进行，再映射回输入分辨率；缩略图和原图在细节处可能略有差异。导出总是使用原图和当前参数。原图与棋盘格开关不影响导出。

默认保护暗色笔画和黑块，不做小连通区域删除。浅灰污迹和浅灰笔画可能需要手动调节。应用不含 OCR、多页合并或透视校正。

## 许可证

应用代码为 MIT；第三方组件遵循其各自许可证。PySide6 / Qt 为独立动态库，允许按适用许可证替换和调试。详见发布包 `licenses` 及 `licenses/THIRD-PARTY.txt`。

## Windows DLL 打包修复

使用仓库内的 `ScanPaper.spec` 构建，不要用会重写该文件的 PyInstaller 命令行生成方式。
Qt 使用 Windows 系统 ICU C 接口。构建机的其他软件（例如 Poppler）可能提供同名但导出函数不同的 `icuuc.dll`；配置会排除这些非系统副本，避免遮蔽操作系统 DLL。构建后检查发布目录，并在只有系统目录的 PATH 下执行解压包自检。
