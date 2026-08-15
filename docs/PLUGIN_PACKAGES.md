# xaocen-imgtor 插件包

`.xaocen-plugin` 是可直接读取的 ZIP 插件包，便于分发和安装。

## 安装

在“设置 → 可选插件”中点击“安装插件包”，选择一个 `.xaocen-plugin` 文件；也可以直接把包复制到当前插件目录，程序刷新时会自动校验并安装。
程序会先校验包内 `integrity.json` 所列文件的 SHA-256，再解包到当前插件目录。校验失败时不会安装任何文件。

## 打包可信插件

```powershell
python tools\package_plugin.py .\plugin_examples\android_motion_photo
python tools\package_plugin.py .\plugin_examples\video_recorder_ffmpeg .\video-recorder-ffmpeg.xaocen-plugin
```

包内仍是普通的 `plugin.json` 与插件源码；安装后插件以文件夹形式运行，方便升级和排查问题。

> 哈希校验验证包内容是否被损坏或意外篡改，不证明发布者身份。只安装可信来源的插件；未来官方分发将再增加签名与来源校验。
