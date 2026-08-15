# FFmpeg 安装说明（Windows）

视频录制插件需要一个 Windows x64 的 FFmpeg 可执行文件。核心程序和
`.xaocen-plugin` 包不内置 FFmpeg，因此不会增加核心 EXE 的体积。

## 下载

请从 FFmpeg 官方下载页进入 Windows builds：

- 官方下载页：https://ffmpeg.org/download.html
- Windows builds（官方页面列出的来源）：https://www.gyan.dev/ffmpeg/builds/

建议下载 Windows 64-bit 的 `ffmpeg-release-essentials.zip`。不要下载
source code，也不要下载 shared/dev 开发包。

## 放置文件

1. 在 XAOCEN ImgTor 设置页安装 `video_recorder_ffmpeg.xaocen-plugin`。
2. 打开插件目录。默认目录是：

   ```text
   %LOCALAPPDATA%\drawru-imgter\plugins\video-recorder-ffmpeg\
   ```

3. 从 FFmpeg 压缩包的 `bin` 目录复制：

   ```text
   ffmpeg.exe
   ffprobe.exe   （可选，但建议一起复制）
   ```

4. 推荐放置为：

   ```text
   video-recorder-ffmpeg\ffmpeg\bin\ffmpeg.exe
   video-recorder-ffmpeg\ffmpeg\bin\ffprobe.exe
   ```

   也支持直接放在插件目录的 `bin` 子目录或插件根目录。

5. 回到设置页点击“检查插件”或重启软件。

## 验证

视频录制面板显示“FFmpeg 已就绪”后即可使用。插件不会读取系统 PATH，
只使用插件目录内的 FFmpeg，这样便携版不会受其他软件安装的 FFmpeg 影响。

## 常见问题

- 显示“插件已安装，但缺少 FFmpeg”：插件目录正确，但没有找到 `ffmpeg.exe`。
- 显示“FFmpeg 无法运行”：请确认下载的是 Windows x64 可执行构建，而不是源码或开发包。
- 录制仍不可用：确认 `ffmpeg.exe` 没有被安全软件隔离，并重新点击“检查插件”。

FFmpeg 是独立的第三方开源项目，具体构建的许可证和说明以下载来源为准。
