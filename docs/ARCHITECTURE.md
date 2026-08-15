# XAOCEN ImgTor v5 架构约定

## 目标

v5 采用 `src/xaocen_imgtor/` 核心包。源码入口、后台 worker 和 PyInstaller
都直接使用包模块；历史兼容入口只保存在 `archive/legacy-entrypoints/`，不进入运行链路。

## 目录职责

```text
根目录
├── webapp.py                         主界面入口
├── 启动.bat                           Windows 源码启动入口
├── XAOCEN-ImgTor.spec                PyInstaller 构建入口
├── src/xaocen_imgtor/                共享服务与基础模块
│   └── workers/                       后台 worker 实现
├── ui/                               HTML/CSS/JS 界面
├── plugin_examples/                  插件源码示例
├── plugin_sdk/                       插件开发说明
├── tests/                            自动化测试
├── docs/                             项目与平台文档
├── tools/                            开发/打包命令入口
└── archive/                          历史文件、运行日志和锁文件
```

## 迁移规则

- 新的共享逻辑只能放入 `src/xaocen_imgtor/`，不要再新增根目录业务模块。
- worker 实现位于 `src/xaocen_imgtor/workers/`，源码和冻结版都通过包模块启动。
- 主界面使用独立的 `.xaocen-app.lock`，截图监听使用独立的 `.xaocen-main.lock`，避免重复启动创建多个托盘图标。
- `config.json`、插件、日志、缓存和锁文件属于运行时数据，不进入源码包。
- `plugin_examples/` 不是运行时插件目录；实际插件安装位置由插件管理器决定。

## PyInstaller 规则

`XAOCEN-ImgTor.spec` 使用 `src` 作为 `pathex`，显式声明包的隐藏导入。每次移动模块后，必须运行：

```bat
python -m unittest discover -s tests -q
node --check ui/app.js
pyinstaller XAOCEN-ImgTor.spec
```

## 后续阶段

1. 统一 worker 参数解析和退出码。
2. 将插件、日志、构建和发布命令集中到明确的工具目录。
3. 发布前保持 `archive/legacy-entrypoints/` 仅作历史备份，不再进入构建链路。
