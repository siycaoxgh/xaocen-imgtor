/* drawru-imgter web UI: one state store, one theme/language path, native APIs behind apiCall. */
(function () {
  'use strict';

  const APP_VERSION = '4.9.0';
  const RATIOS = ['1:1', '1:2', '2:1', '2:3', '3:2', '3:4', '4:3', '16:6', '9:16', '16:9', '9:18', '18:9', '21:9'];
  const CUSTOM_RATIO = '__custom__';
  const FPS = [5, 8, 10, 12, 15, 20, 24, 30];
  const IMAGE_FORMATS = ['png', 'jpg', 'bmp'];
  const GIF_FORMATS = ['gif', 'apng', 'webp'];
  const GIF_MODES = ['free', 'ratio', 'fixed'];
  const PANEL_META = {
    launcher: { icon:'home', nav:'nav.launcher' },
    screenshot: { icon:'capture', nav:'nav.screenshot' },
    gif: { icon:'record', nav:'nav.gif' },
    gallery: { icon:'gallery', nav:'nav.gallery' },
    crop: { icon:'crop', nav:'nav.crop' },
    settings: { icon:'settings', nav:'nav.settings' },
    about: { icon:'about', nav:'nav.about' }
  };
  const NAV = Object.entries(PANEL_META).map(([key, meta]) => [key, meta.icon]);
  const I18N = {
    zh: {
      'brand.name':'XAOCEN ImgTor', 'brand.part1':'XAOCEN', 'brand.part2':'ImgTor', 'theme.dark':'暗色模式', 'theme.light':'亮色模式',
      'nav.launcher':'启动器', 'nav.screenshot':'快速截图', 'nav.gif':'动图录制', 'nav.gallery':'图片浏览', 'nav.crop':'图片裁剪', 'nav.settings':'设置', 'nav.about':'关于',
      'panel.screenshot.kicker':'截图工作区', 'panel.gif.kicker':'录制工作区', 'panel.gif.heading':'录制设置', 'panel.gallery.kicker':'图库工作区', 'panel.gallery.heading':'图库', 'panel.crop.kicker':'编辑工作区', 'panel.crop.heading':'裁剪编辑', 'panel.settings.kicker':'偏好设置', 'panel.settings.heading':'应用设置', 'panel.about.kicker':'项目资料',
      'home.eyebrow':'轻量桌面工具', 'home.title':'XAOCEN ImgTor', 'home.subtitle':'快速截图、动图录制、图片浏览与裁剪。',
      'home.capture.title':'快速截图', 'home.capture.desc':'按快捷键框选屏幕，可使用自由大小、固定比例或固定尺寸，并自动保存图片。', 'home.record.title':'动图录制', 'home.record.desc':'框选屏幕区域，选择 FPS、输出格式和比例，最长录制 15 秒。', 'home.gallery.title':'图片浏览', 'home.gallery.desc':'查看保存目录中的图片和动图，支持原图预览、切换、打开与删除。', 'home.crop.title':'图片裁剪', 'home.crop.desc':'选择或拖入图片，在同一页面框选比例并裁剪保存。',
      'screenshot.title':'截图设置', 'screenshot.subtitle':'设置会自动保存，并应用到下一次截图。', 'screenshot.hotkey':'截图快捷键', 'screenshot.configureHotkey':'在设置中修改', 'screenshot.restart':'重启截图监听', 'screenshot.mode':'选区模式', 'screenshot.ratio':'预设比例', 'screenshot.width':'固定宽度（px / in / cm / mm）', 'screenshot.height':'固定高度（px / in / cm / mm）', 'screenshot.format':'图片格式', 'screenshot.directory':'本地保存路径', 'screenshot.other':'其他设置', 'screenshot.chooseDirectory':'选择路径', 'screenshot.autoSave':'自动保存本地', 'screenshot.autoClip':'自动复制到剪贴板',
      'ratio.custom':'自定义', 'ratio.placeholder':'例如 5:4、5：4 或 5/4', 'ratio.apply':'应用比例', 'ratio.invalid':'请输入有效比例，例如 5:4、5：4 或 5/4',
      'mode.free':'自由大小', 'mode.ratio':'固定比例', 'mode.fixed':'固定尺寸', 'common.apply':'应用截图参数', 'common.save':'保存', 'common.saved':'已保存', 'common.saving':'保存中…', 'common.cancel':'取消', 'common.invalid':'保存失败，请检查输入',
      'gif.title':'动图录制', 'gif.subtitle':'先调整选区、帧率和格式，再按开始快捷键进入 3/2/1 倒计时；最长 15 秒自动停止。', 'gif.flowTitle':'录制流程', 'gif.flow.select':'框选区域', 'gif.flow.start':'按下开始键', 'gif.flow.countdown':'3·2·1 倒计时', 'gif.flow.record':'录制中', 'gif.fps':'帧率选择', 'gif.format':'输出格式', 'gif.mode':'选区模式', 'gif.width':'固定宽度（px / in / cm / mm）', 'gif.height':'固定高度（px / in / cm / mm）', 'gif.ratio':'选区比例', 'gif.other':'其他', 'gif.free':'自由大小', 'gif.start':'开始录制', 'gif.directory':'录制保存路径', 'gif.chooseDirectory':'选择路径', 'gif.sameDirectory':'与截图使用同一个保存目录，图库会统一读取这里的文件；动图仅保存本地，不复制到剪贴板。', 'gif.configureShortcuts':'设置快捷键', 'gif.shortcuts':'设置录制快捷键', 'gif.enterStart':'回车开始', 'gif.startLabel':'开始', 'gif.stopLabel':'结束',
      'gallery.title':'图片浏览', 'gallery.all':'全部', 'gallery.images':'图片', 'gallery.motion':'动图', 'gallery.openFolder':'打开目录', 'gallery.empty':'保存目录中还没有图片。', 'gallery.emptyFirst':'还没有图片，试试先截一张图。', 'gallery.noMatch':'没有匹配的图片。', 'gallery.captureNow':'前往快速截图', 'gallery.resetFilter':'重置筛选', 'gallery.animated':'动图', 'gallery.open':'打开文件', 'gallery.delete':'删除', 'gallery.deleteTitle':'删除图片', 'gallery.play':'播放', 'gallery.pause':'暂停', 'gallery.prev':'上一张', 'gallery.next':'下一张', 'gallery.navigation':'← / → 切换图片', 'gallery.subtitle':'支持 PNG、JPG、BMP、GIF、APNG 与 Animated WebP；方向键可切换图片。',
      'crop.title':'图片裁剪', 'crop.subtitle':'选择或拖入图片，在画布中框选区域、选择比例并保存。', 'crop.open':'选择文件', 'crop.drop':'也可以将图片拖到预览区域', 'crop.hint':'拖动画框移动选区 · 拖动四角调整大小', 'crop.overwriteHint':'拖入图片无法覆盖原图，请使用“选择文件”打开原图。', 'crop.free':'自由绘制', 'crop.freeDraw':'自由绘制', 'crop.fixedRatio':'固定比例', 'crop.fixedSize':'固定大小', 'crop.ratio':'比例', 'crop.size':'尺寸', 'crop.overwrite':'替换原图', 'crop.save':'裁剪并保存', 'crop.clear':'清空图片',
      'settings.title':'设置', 'settings.subtitle':'每项设置单独占一行；快捷键保存后立即生效，其他选项直接写入配置。', 'settings.shortcutGroup':'快捷键设置', 'settings.otherGroup':'录制与应用设置', 'settings.shortcutSaveHint':'保存快捷键后立即生效', 'settings.otherSaveHint':'其他选项直接写入配置', 'settings.captureKey':'截图快捷键', 'settings.recordStart':'录制开始快捷键', 'settings.recordStop':'录制结束快捷键', 'settings.fps':'录制 FPS', 'settings.format':'录制格式', 'settings.directory':'保存目录', 'settings.chooseDirectory':'选择目录', 'settings.theme':'界面主题', 'settings.language':'界面语言', 'settings.saveShortcuts':'保存快捷键', 'settings.saveOther':'保存其他设置',
      'language.zh':'中文', 'language.en':'English', 'about.title':'关于 xaocen-imgtor', 'about.subtitle':'轻量 · 高效 · Windows 优先支持', 'about.version':'版本', 'about.featureCount':'20+', 'about.features':'已完成功能', 'about.fileCount':'20+', 'about.sourceFiles':'活跃源码文件', 'about.pendingCount':'4', 'about.pending':'待定功能', 'about.doneTitle':'✅ 已完成功能', 'about.done.core':'全局快捷键截图 — 比例约束 / 固定尺寸 / 自由大小', 'about.done.overlay':'半透明遮罩 + 十字参考线 + 四角标记 + 框内拖拽微调', 'about.done.format':'自动保存 PNG/JPG/BMP + 自动剪贴板，截图超时兜底清理', 'about.done.gif':'拖框选区 + Enter 开始 + 3/2/1 倒计时，GIF / APNG / WebP 输出', 'about.done.gallery':'缩略图网格 + 原图大图预览 + 键盘切换 + 动图播放/暂停 + 删除', 'about.done.crop':'拖放图片 + 自由绘制 / 固定比例 / 固定尺寸三种裁剪模式', 'about.done.settings':'GUI 设置面板 + 实时快捷键录入校验 + 目录选择器 + 中英双语', 'about.done.theme':'亮色 / 暗色主题 + 系统托盘后台 + 单实例锁 + 原生控件圆角', 'about.done.plugins':'可选 MP4 录制与 Android Motion Photo 插件，保持核心程序轻量', 'about.pendingTitle':'🔲 待定 / 后续', 'about.pending.mac':'macOS 适配 — 代码已预留平台分支，需实机测试', 'about.pending.exe':'PyInstaller 打包 exe — 预估 45-50 MB，后续可加', 'about.pending.motion':'Motion Photo 兼容性 — 小米等 OEM 相册仍需实机验证', 'about.excludedTitle':'🚫 已排除', 'about.excluded.live':'iOS Live Photo — Apple 私有格式，Windows 无法生成兼容文件', 'about.panels':'功能面板', 'about.dependencies':'核心依赖', 'about.supportTitle':'平台支持', 'about.support':'Windows 优先支持；macOS/Linux 已预留代码分支，尚未完成实机验证。', 'about.eyebrow':'项目资料', 'gallery.motionPhoto':'Motion 图', 'motion.previewTitle':'视频预览', 'motion.useStart':'将此位置设为起点',
      'status.running':'截图监听已启用', 'status.stopped':'截图监听未运行', 'status.restarted':'截图监听已重启', 'shortcut.empty':'请输入快捷键', 'shortcut.invalid':'快捷键格式无效', 'shortcut.modifier':'普通字符必须搭配 Ctrl / Shift / Alt', 'shortcut.reserved':'该快捷键是系统或常用编辑快捷键', 'shortcut.same':'开始和结束快捷键不能相同', 'shortcut.conflictHotkey':'与截图快捷键冲突', 'shortcut.conflictStart':'与录制开始快捷键冲突', 'shortcut.conflictStop':'与录制结束快捷键冲突', 'shortcut.pending':'待保存', 'shortcut.saved':'已保存', 'shortcut.listening':'请按下快捷键…', 'crop.needImage':'请先打开或拖入图片', 'crop.needArea':'请先框选裁剪区域', 'gallery.confirmDelete':'确定删除这张图片吗？', 'gallery.noFile':'无法打开该文件', 'crop.emptyTitle':'使用上方“选择文件”或拖入图片开始', 'crop.emptyDesc':'支持 PNG、JPG、BMP 等常见格式，拖动鼠标框选裁剪区域'
    },
    en: {
      'brand.name':'XAOCEN ImgTor', 'brand.part1':'XAOCEN', 'brand.part2':'ImgTor', 'theme.dark':'Dark mode', 'theme.light':'Light mode',
      'nav.launcher':'Launcher', 'nav.screenshot':'Quick capture', 'nav.gif':'GIF recorder', 'nav.gallery':'Image browser', 'nav.crop':'Crop image', 'nav.settings':'Settings', 'nav.about':'About',
      'panel.screenshot.kicker':'Capture workspace', 'panel.gif.kicker':'Recording workspace', 'panel.gif.heading':'Recording settings', 'panel.gallery.kicker':'Library workspace', 'panel.gallery.heading':'Library', 'panel.crop.kicker':'Editing workspace', 'panel.crop.heading':'Crop editor', 'panel.settings.kicker':'Preferences', 'panel.settings.heading':'App settings', 'panel.about.kicker':'Project information',
      'home.eyebrow':'Lightweight desktop tool', 'home.title':'XAOCEN ImgTor', 'home.subtitle':'Quick capture, motion recording, image browsing and cropping.',
      'home.capture.title':'Quick capture', 'home.capture.desc':'Frame the screen with a shortcut, then use free size, fixed ratio or fixed dimensions and save the image.', 'home.record.title':'GIF recorder', 'home.record.desc':'Frame an area, choose FPS, output format and ratio, and record for up to 15 seconds.', 'home.gallery.title':'Image browser', 'home.gallery.desc':'Browse saved images and motion files with full-size preview, navigation, opening and deletion.', 'home.crop.title':'Crop image', 'home.crop.desc':'Choose or drop an image, frame a ratio on the same page and save the crop.',
      'screenshot.title':'Screenshot settings', 'screenshot.subtitle':'Settings are saved automatically and apply to the next capture.', 'screenshot.hotkey':'Capture shortcut', 'screenshot.configureHotkey':'Edit in settings', 'screenshot.restart':'Restart capture listener', 'screenshot.mode':'Selection mode', 'screenshot.ratio':'Preset ratios', 'screenshot.width':'Fixed width (px / in / cm / mm)', 'screenshot.height':'Fixed height (px / in / cm / mm)', 'screenshot.format':'Image format', 'screenshot.directory':'Local save path', 'screenshot.other':'Other settings', 'screenshot.chooseDirectory':'Choose path', 'screenshot.autoSave':'Save locally', 'screenshot.autoClip':'Copy to clipboard',
      'ratio.custom':'Custom', 'ratio.placeholder':'e.g. 5:4, 5：4 or 5/4', 'ratio.apply':'Apply ratio', 'ratio.invalid':'Enter a valid ratio, for example 5:4, 5：4 or 5/4',
      'mode.free':'Free size', 'mode.ratio':'Fixed ratio', 'mode.fixed':'Fixed size', 'common.apply':'Apply capture settings', 'common.save':'Save', 'common.saved':'Saved', 'common.saving':'Saving…', 'common.cancel':'Cancel', 'common.invalid':'Save failed; check the input',
      'gif.title':'GIF recorder', 'gif.subtitle':'Adjust the area, FPS and format first. Start recording to begin a 3/2/1 countdown; it stops after 15 seconds.', 'gif.flowTitle':'Recording flow', 'gif.flow.select':'Frame an area', 'gif.flow.start':'Press start key', 'gif.flow.countdown':'3·2·1 countdown', 'gif.flow.record':'Recording', 'gif.fps':'FPS selection', 'gif.format':'Output format', 'gif.mode':'Selection mode', 'gif.width':'Fixed width (px / in / cm / mm)', 'gif.height':'Fixed height (px / in / cm / mm)', 'gif.ratio':'Selection ratio', 'gif.other':'Other', 'gif.free':'Free size', 'gif.start':'Start recording', 'gif.directory':'Recording save path', 'gif.chooseDirectory':'Choose path', 'gif.sameDirectory':'Uses the same directory as screenshots so the gallery stays unified. Motion files are saved locally only and are not copied to the clipboard.', 'gif.configureShortcuts':'Set shortcuts', 'gif.shortcuts':'Recording shortcuts', 'gif.enterStart':'Enter to start', 'gif.startLabel':'to start', 'gif.stopLabel':'to stop',
      'gallery.title':'Image browser', 'gallery.all':'All', 'gallery.images':'Images', 'gallery.motion':'Motion', 'gallery.openFolder':'Open folder', 'gallery.empty':'No images in the save directory.', 'gallery.emptyFirst':'No images yet. Try taking a screenshot first.', 'gallery.noMatch':'No matching images.', 'gallery.captureNow':'Go to quick capture', 'gallery.resetFilter':'Reset filter', 'gallery.animated':'Motion', 'gallery.open':'Open file', 'gallery.delete':'Delete', 'gallery.deleteTitle':'Delete image', 'gallery.play':'Play', 'gallery.pause':'Pause', 'gallery.prev':'Previous', 'gallery.next':'Next', 'gallery.navigation':'← / → to switch images', 'gallery.subtitle':'Supports PNG, JPG, BMP, GIF, APNG and Animated WebP; use the arrow keys to switch images.',
      'crop.title':'Crop image', 'crop.subtitle':'Choose or drop an image, frame the crop on the canvas and save it.', 'crop.open':'Choose file', 'crop.drop':'You can also drop an image on the preview', 'crop.hint':'Drag the frame to move it · Drag a corner to resize it', 'crop.overwriteHint':'A dropped image cannot replace the original. Use “Choose file” to open it.', 'crop.free':'Free draw', 'crop.freeDraw':'Free draw', 'crop.fixedRatio':'Fixed ratio', 'crop.fixedSize':'Fixed size', 'crop.ratio':'Ratio', 'crop.size':'Size', 'crop.overwrite':'Replace original', 'crop.save':'Crop and save', 'crop.clear':'Clear image',
      'settings.title':'Settings', 'settings.subtitle':'Each setting gets its own row. Shortcuts apply after saving; other options are written directly to the config.', 'settings.shortcutGroup':'Shortcut settings', 'settings.otherGroup':'Recording and app settings', 'settings.shortcutSaveHint':'Shortcuts apply immediately after saving', 'settings.otherSaveHint':'Other options are written to the config', 'settings.captureKey':'Capture shortcut', 'settings.recordStart':'Recording start shortcut', 'settings.recordStop':'Recording stop shortcut', 'settings.fps':'Recording FPS', 'settings.format':'Recording format', 'settings.directory':'Save directory', 'settings.chooseDirectory':'Choose directory', 'settings.theme':'Theme', 'settings.language':'Language', 'settings.saveShortcuts':'Save shortcuts', 'settings.saveOther':'Save other settings',
      'language.zh':'中文', 'language.en':'English', 'about.title':'About xaocen-imgtor', 'about.subtitle':'Lightweight · Efficient · Windows first', 'about.version':'Version', 'about.featureCount':'20+', 'about.features':'Completed', 'about.fileCount':'20+', 'about.sourceFiles':'Active source files', 'about.pendingCount':'4', 'about.pending':'Planned', 'about.doneTitle':'✅ Completed', 'about.done.core':'Global hotkey capture — ratios, fixed size, free size', 'about.done.overlay':'Translucent mask + guidelines + corner marks + drag fine-tuning', 'about.done.format':'Auto-save PNG/JPG/BMP + clipboard, capture timeout fallback', 'about.done.gif':'Drag area + Enter to start + 3/2/1 countdown, GIF / APNG / WebP', 'about.done.gallery':'Thumbnail grid + full-res preview + keyboard nav + play/pause + delete', 'about.done.crop':'Drag-and-drop image + free draw / fixed ratio / fixed size cropping', 'about.done.settings':'Settings panel + real-time shortcut recording + directory picker + i18n', 'about.done.theme':'Light/dark theme + system tray + single instance lock + rounded controls', 'about.done.plugins':'Optional MP4 recording and Android Motion Photo plugins keep the core lightweight', 'about.pendingTitle':'🔲 Planned', 'about.pending.mac':'macOS support — platform branches reserved, needs hardware testing', 'about.pending.exe':'PyInstaller .exe packaging — est. 45-50 MB, planned for later', 'about.pending.motion':'Motion Photo compatibility — OEM galleries such as Xiaomi still need hardware validation', 'about.excludedTitle':'🚫 Excluded', 'about.excluded.live':'iOS Live Photo — Apple proprietary, incompatible with Windows', 'about.panels':'Panels', 'about.dependencies':'Core deps', 'about.supportTitle':'Platform support', 'about.support':'Windows first; macOS / Linux branches are reserved but not hardware-verified.', 'about.eyebrow':'Project info', 'gallery.motionPhoto':'Motion Photo', 'motion.previewTitle':'Video preview', 'motion.useStart':'Use this position as start',
      'status.running':'Capture listener enabled', 'status.stopped':'Capture listener is not running', 'status.restarted':'Capture listener restarted', 'shortcut.empty':'Enter a shortcut', 'shortcut.invalid':'Invalid shortcut format', 'shortcut.modifier':'A normal character needs Ctrl / Shift / Alt', 'shortcut.reserved':'This is a system or common editing shortcut', 'shortcut.same':'Start and stop shortcuts must be different', 'shortcut.conflictHotkey':'Conflicts with the capture shortcut', 'shortcut.conflictStart':'Conflicts with the recording start shortcut', 'shortcut.conflictStop':'Conflicts with the recording stop shortcut', 'shortcut.pending':'Pending save', 'shortcut.saved':'Saved', 'shortcut.listening':'Press a shortcut…', 'crop.needImage':'Open or drop an image first', 'crop.needArea':'Select a crop area first', 'gallery.confirmDelete':'Delete this image?', 'gallery.noFile':'Unable to open this file', 'crop.emptyTitle':'Use “Choose file” above or drop an image', 'crop.emptyDesc':'Supports PNG, JPG, BMP and other formats — drag to select the crop area'
    }
  };
  const state = { config:{}, ratios:RATIOS, selectionModes:['free','ratio','fixed'], imageFormats:IMAGE_FORMATS, gifFormats:GIF_FORMATS, fps:FPS, gifModes:GIF_MODES, files:[], plugins:[], pluginRoot:'', motionVideo:null, motionNotice:'', videoPluginReady:false, stats:{}, current:'launcher', filter:'all', pending:{}, crop:{ image:null, name:'', path:'', mode:'free', ratio:'1:1', fixedWidth:'400px', fixedHeight:'320px', imageX:0, imageY:0, imageW:0, imageH:0, scale:1, selection:null, dragging:false, dragMode:'draw', dragStart:null, dragOffset:null }, modal:null };
  const PLUGIN_GUIDES = [
    { id:'video-recorder-ffmpeg', title:'MP4 Video Recorder (FFmpeg)', purpose:'plugins.videoPurpose', download:'https://github.com/siycaoxgh/xaocen-plugin' },
    { id:'android-motion-photo', title:'Android Motion Photo', purpose:'plugins.motionPurpose', download:'https://github.com/siycaoxgh/xaocen-plugin' }
  ];
  I18N.zh['about.done.crop'] = '页面内选择或拖入图片（拖入仅可另存）+ 自由绘制 / 固定比例 / 固定尺寸裁剪';
  I18N.en['about.done.crop'] = 'Choose or drop an image (dropped images save as a copy) + free draw / fixed ratio / fixed size cropping';
  I18N.zh['about.pending.integration'] = '官方插件签名与来源校验 — 当前已提供完整性哈希校验';
  I18N.en['about.pending.integration'] = 'Official plugin signatures and source verification — integrity hashes are available now';
  I18N.zh['about.title'] = '关于 XAOCEN ImgTor';
  I18N.zh['nav.launcher'] = '仪表盘';
  I18N.zh['about.subtitle'] = '轻量级 Windows 图像效率工具';
  I18N.zh['about.productName'] = 'XAOCEN ImgTor';
  I18N.zh['about.chineseName'] = '晓枨图像工具';
  I18N.zh['about.slogan'] = '轻量 · 高效 · 专注于图像效率';
  I18N.zh['about.description'] = '用于快速截图、动态图像录制、图片浏览、裁剪处理以及多格式导出。专注于简洁、高效的操作体验，让每一次图像处理更加流畅。';
  I18N.zh['about.descriptionLine1'] = '用于快速截图、动态图像录制、图片浏览、裁剪处理以及多格式导出。';
  I18N.zh['about.descriptionLine2'] = '专注于简洁、高效的操作体验，让每一次图像处理更加流畅。';
  I18N.zh['about.developer'] = '开发：XAOCEN STUDIO';
  I18N.zh['about.rights'] = '© 2026 XAOCEN · All Rights Reserved.';
  I18N.en['about.title'] = 'About XAOCEN ImgTor';
  I18N.en['nav.launcher'] = 'Dashboard';
  I18N.en['about.subtitle'] = 'Lightweight Windows image productivity tool';
  I18N.en['about.productName'] = 'XAOCEN ImgTor';
  I18N.en['about.chineseName'] = '晓枨图像工具';
  I18N.en['about.slogan'] = 'Lightweight · Efficient · Focused on image productivity';
  I18N.en['about.description'] = 'Fast capture, motion recording, image browsing, cropping and multi-format export. Focused on a simple, efficient workflow that keeps every image task smooth.';
  I18N.en['about.descriptionLine1'] = 'Fast capture, motion recording, image browsing, cropping and multi-format export.';
  I18N.en['about.descriptionLine2'] = 'Focused on a simple, efficient workflow that keeps every image task smooth.';
  I18N.en['about.developer'] = 'Developed by XAOCEN STUDIO';
  I18N.en['about.rights'] = '© 2026 XAOCEN · All Rights Reserved.';
  I18N.zh['crop.dropReady'] = '已载入拖入图片；拖入图片仅支持另存，无法替换原图。';
  I18N.en['crop.dropReady'] = 'Dropped image loaded. It can only be saved as a copy, not replace the original.';
  I18N.zh['crop.dropInvalid'] = '请拖入 PNG、JPG、BMP、GIF、APNG 或 WebP 图片。';
  I18N.en['crop.dropInvalid'] = 'Drop a PNG, JPG, BMP, GIF, APNG or WebP image.';
  I18N.zh['crop.invalidData'] = '裁剪数据无效，请重新选择图片后再试。';
  I18N.en['crop.invalidData'] = 'Crop data is invalid. Choose the image again and retry.';
  I18N.zh['crop.saveFailed'] = '裁剪保存失败，请检查文件格式和保存目录。';
  I18N.en['crop.saveFailed'] = 'Crop save failed. Check the image format and save directory.';
  I18N.zh['plugins.title'] = '可选插件';
  I18N.zh['plugins.subtitle'] = '插件独立安装；核心程序不包含 FFmpeg 或视频组件。插件可执行本机代码，请仅安装可信来源。';
  I18N.zh['plugins.openDirectory'] = '打开插件目录';
  I18N.zh['plugins.empty'] = '尚未安装插件。将插件文件夹放入此目录后，重新打开设置页即可识别。';
  I18N.zh['plugins.installed'] = '已安装';
  I18N.zh['plugins.incompatible'] = '当前平台不兼容';
  I18N.zh['plugins.invalid'] = '插件清单无效';
  I18N.zh['plugins.capabilities'] = '能力';
  I18N.zh['plugins.opened'] = '已打开插件目录';
  I18N.zh['plugins.openFailed'] = '无法打开插件目录';
  I18N.zh['plugins.installPackage'] = '安装插件包';
  I18N.zh['plugins.packageInstalled'] = '插件包已验证并安装';
  I18N.zh['plugins.packageHashMismatch'] = '插件包哈希校验失败，未安装';
  I18N.zh['plugins.packageFailed'] = '插件包无效或安装失败';
  I18N.en['plugins.title'] = 'Optional plugins';
  I18N.en['plugins.subtitle'] = 'Plugins are installed separately; the core does not include FFmpeg or video components. Plugins execute local code, so install only from trusted sources.';
  I18N.en['plugins.openDirectory'] = 'Open plugin folder';
  I18N.en['plugins.empty'] = 'No plugins installed. Put a plugin folder here, then reopen Settings to discover it.';
  I18N.en['plugins.installed'] = 'Installed';
  I18N.en['plugins.incompatible'] = 'Unsupported on this platform';
  I18N.en['plugins.invalid'] = 'Invalid plugin manifest';
  I18N.en['plugins.capabilities'] = 'Capabilities';
  I18N.en['plugins.opened'] = 'Plugin folder opened';
  I18N.en['plugins.openFailed'] = 'Could not open plugin folder';
  I18N.en['plugins.installPackage'] = 'Install plugin package';
  I18N.en['plugins.packageInstalled'] = 'Plugin package verified and installed';
  I18N.en['plugins.packageHashMismatch'] = 'Plugin hash verification failed; nothing was installed';
  I18N.en['plugins.packageFailed'] = 'Invalid plugin package or installation failed';
  I18N.zh['motion.title'] = 'Android Motion Photo';
  I18N.zh['motion.subtitle'] = '使用当前裁剪区域和一个 MP4 视频导出单文件动态照片。';
  I18N.zh['motion.noImage'] = '请先选择图片';
  I18N.zh['motion.noVideo'] = '尚未选择 MP4 视频';
  I18N.zh['motion.chooseVideo'] = '选择 MP4';
  I18N.zh['motion.export'] = '导出 Motion Photo';
  I18N.zh['motion.ready'] = '插件已就绪';
  I18N.zh['motion.unavailable'] = '未安装 Android Motion Photo 插件';
  I18N.zh['motion.needVideo'] = '请先选择 MP4 视频';
  I18N.zh['motion.failed'] = 'Motion Photo 导出失败';
  I18N.en['motion.title'] = 'Android Motion Photo';
  I18N.en['motion.subtitle'] = 'Export the current crop and an MP4 video as one Motion Photo file.';
  I18N.en['motion.noImage'] = 'Choose an image first';
  I18N.en['motion.noVideo'] = 'No MP4 video selected';
  I18N.en['motion.chooseVideo'] = 'Choose MP4';
  I18N.en['motion.export'] = 'Export Motion Photo';
  I18N.en['motion.ready'] = 'Plugin ready';
  I18N.en['motion.unavailable'] = 'Android Motion Photo plugin is not installed';
  I18N.en['motion.needVideo'] = 'Choose an MP4 video first';
  I18N.en['motion.failed'] = 'Motion Photo export failed';
  I18N.zh['video.title'] = '视频录制（插件）';
  I18N.zh['video.subtitle'] = 'MP4 录制使用独立 FFmpeg 插件，不增加核心程序体积。';
  I18N.zh['video.check'] = '检查插件';
  I18N.zh['video.unavailable'] = '未安装视频录制插件';
  I18N.zh['video.ready'] = 'FFmpeg 已就绪';
  I18N.zh['video.missing'] = '插件已安装，但缺少 FFmpeg';
  I18N.zh['video.unusable'] = 'FFmpeg 无法运行';
  I18N.en['video.title'] = 'Video recording (plugin)';
  I18N.en['video.subtitle'] = 'MP4 recording uses an independent FFmpeg plugin and does not enlarge the core app.';
  I18N.en['video.check'] = 'Check plugin';
  I18N.en['video.unavailable'] = 'Video recorder plugin is not installed';
  I18N.en['video.ready'] = 'FFmpeg ready';
  I18N.en['video.missing'] = 'Plugin installed, but FFmpeg is missing';
  I18N.en['video.unusable'] = 'FFmpeg cannot run';
  I18N.zh['video.start'] = '开始视频录制';
  I18N.en['video.start'] = 'Start video recording';
  I18N.zh['video.check'] = '\u5237\u65b0\u68c0\u6d4b';
  I18N.en['video.check'] = 'Refresh check';
  I18N.zh['video.subtitle'] = '\u4f7f\u7528\u52a8\u56fe\u5f55\u5236\u7684\u9009\u533a\u3001\u5e27\u7387\u4e0e\u5c3a\u5bf8\u8bbe\u7f6e\uff0c\u56fa\u5b9a\u8f93\u51fa MP4\uff1b\u4e0d\u589e\u52a0\u6838\u5fc3\u7a0b\u5e8f\u4f53\u79ef\u3002';
  I18N.en['video.subtitle'] = 'Uses the motion recorder selection, FPS and size settings; output is always MP4 and stays outside the core app.';
  I18N.zh['gallery.videos'] = '\u89c6\u9891'; I18N.en['gallery.videos'] = 'Video';
  I18N.zh['gallery.video'] = '\u89c6\u9891'; I18N.en['gallery.video'] = 'Video';
  I18N.zh['gallery.subtitle'] = '\u652f\u6301 PNG\u3001JPG\u3001BMP\u3001GIF\u3001APNG\u3001Animated WebP \u4e0e MP4\uff1b\u65b9\u5411\u952e\u53ef\u5207\u6362\u5a92\u4f53\u3002';
  I18N.en['gallery.subtitle'] = 'Supports PNG, JPG, BMP, GIF, APNG, Animated WebP and MP4; use arrow keys to switch media.';
  I18N.zh['plugins.chooseDirectory'] = '\u9009\u62e9\u63d2\u4ef6\u76ee\u5f55'; I18N.en['plugins.chooseDirectory'] = 'Choose plugin folder';
  I18N.zh['plugins.useDefault'] = '\u4f7f\u7528\u9ed8\u8ba4\u76ee\u5f55'; I18N.en['plugins.useDefault'] = 'Use default folder';
  I18N.zh['plugins.directoryHint'] = '\u53ef\u9009\u62e9\u8f6f\u4ef6\u5b89\u88c5\u76ee\u5f55\u4e0b\u7684 plugins\uff1b\u76ee\u5f55\u5fc5\u987b\u53ef\u5199\u3002'; I18N.en['plugins.directoryHint'] = 'You may choose <app>\\plugins; the directory must be writable.';
  I18N.zh['plugins.chooseDirectory'] = '\u9009\u62e9\u76ee\u5f55'; I18N.en['plugins.chooseDirectory'] = 'Choose folder';
  I18N.zh['plugins.openDirectory'] = '\u6253\u5f00\u76ee\u5f55'; I18N.en['plugins.openDirectory'] = 'Open folder';
  I18N.zh['plugins.useDefault'] = '\u6062\u590d\u9ed8\u8ba4'; I18N.en['plugins.useDefault'] = 'Reset default';
  I18N.zh['plugins.directoryFailed'] = '\u63d2\u4ef6\u76ee\u5f55\u4e0d\u53ef\u5199\uff0c\u8bf7\u9009\u62e9\u9ed8\u8ba4\u76ee\u5f55\u6216\u5176\u4ed6\u53ef\u5199\u4f4d\u7f6e\u3002'; I18N.en['plugins.directoryFailed'] = 'Plugin directory is not writable. Use the default or choose another writable location.';
  I18N.zh['motion.installHint'] = '\u8bf7\u5c06 android_motion_photo \u793a\u4f8b\u6587\u4ef6\u5939\u7684\u5185\u5bb9\u653e\u5165\u5f53\u524d\u63d2\u4ef6\u76ee\u5f55\u7684 android-motion-photo \u5b50\u6587\u4ef6\u5939\uff0c\u7136\u540e\u5237\u65b0\u8bbe\u7f6e\u9875\u3002';
  I18N.en['motion.installHint'] = 'Copy the android_motion_photo example contents into android-motion-photo under the current plugin directory, then refresh Settings.';
  I18N.zh['motion.inputHint'] = '\u6b65\u9aa4\uff1a\u5148\u5728\u4e0a\u65b9\u52a0\u8f7d\u56fe\u7247\uff08\u5f53\u524d\u88c1\u526a\u7ed3\u679c\uff09\uff0c\u518d\u9009\u62e9 MP4 \u89c6\u9891\u5408\u6210\u3002';
  I18N.en['motion.inputHint'] = 'Steps: load an image above (the current crop), then choose an MP4 video to package.';
  I18N.zh['motion.invalidMp4'] = '\u6240\u9009\u89c6\u9891\u4e0d\u662f\u6709\u6548 MP4\uff08\u7f3a\u5c11 ftyp \u6587\u4ef6\u5934\uff09\u3002'; I18N.en['motion.invalidMp4'] = 'The selected video is not a valid MP4 (the ftyp file header is missing).';
  I18N.zh['motion.errorDetail'] = '\u5408\u6210\u5931\u8d25\uff1a'; I18N.en['motion.errorDetail'] = 'Packaging failed: ';
  I18N.zh['plugins.missing'] = '\u672a\u5b89\u88c5'; I18N.en['plugins.missing'] = 'Not installed';
  I18N.zh['plugins.download'] = '\u4e0b\u8f7d\u63d2\u4ef6'; I18N.en['plugins.download'] = 'Download plugin';
  I18N.zh['plugins.downloadPending'] = '\u4e0b\u8f7d\u94fe\u63a5\u5f85\u8865\u5145'; I18N.en['plugins.downloadPending'] = 'Download link pending';
  I18N.zh['plugins.videoPurpose'] = '\u7528\u4e8e\u5f55\u5236 MP4 \u89c6\u9891\uff1b\u9700\u8981\u63d2\u4ef6\u5185\u7684 ffmpeg.exe\u3002'; I18N.en['plugins.videoPurpose'] = 'Records MP4 video; requires ffmpeg.exe inside the plugin.';
  I18N.zh['plugins.motionPurpose'] = '\u7528\u4e8e\u5c06\u5f53\u524d\u88c1\u526a\u56fe\u7247\u4e0e MP4 \u5c01\u88c5\u4e3a Google Motion Photo\uff1b\u4e0d\u9700\u8981 FFmpeg\u3002'; I18N.en['plugins.motionPurpose'] = 'Packages the current crop and an MP4 as Google Motion Photo; no FFmpeg is required.';
  I18N.zh['motion.requirementsTitle'] = '\u5408\u6210\u8981\u6c42'; I18N.en['motion.requirementsTitle'] = 'Packaging requirements';
  I18N.zh['motion.requirementImage'] = '\u56fe\u7247\uff1a\u4f7f\u7528\u5f53\u524d\u88c1\u526a\u9009\u533a\uff0c\u8f6f\u4ef6\u4f1a\u81ea\u52a8\u8f6c\u6362\u4e3a JPEG\uff1b\u8bf7\u5148\u5b8c\u6210\u6846\u9009\u3002'; I18N.en['motion.requirementImage'] = 'Image: uses the current crop and converts it to JPEG automatically; make a crop selection first.';
  I18N.zh['motion.requirementVideo'] = '\u89c6\u9891\uff1a\u5fc5\u987b\u662f\u6709\u6548 MP4\uff08\u5305\u542b ftyp \u6587\u4ef6\u5934\uff09\uff1b\u672c\u8f6f\u4ef6\u5f55\u5236\u7684 MP4 \u53ef\u76f4\u63a5\u4f7f\u7528\u3002'; I18N.en['motion.requirementVideo'] = 'Video: must be a valid MP4 with an ftyp file header; MP4s recorded by this app work directly.';
  I18N.zh['motion.requirementRecommend'] = '\u5efa\u8bae\uff1a\u56fe\u7247\u4e0e\u89c6\u9891\u4f7f\u7528\u76f8\u8fd1\u6bd4\u4f8b\uff0c\u89c6\u9891\u4e3a 1\u201315 \u79d2\uff1b\u5408\u6210\u4e0d\u4f1a\u91cd\u65b0\u7f16\u7801\u89c6\u9891\u3002'; I18N.en['motion.requirementRecommend'] = 'Recommended: match image/video aspect ratios, keep video 1–15 seconds; packaging does not re-encode video.';
  I18N.zh['motion.imageSource'] = '\u9759\u6001\u56fe\u7247'; I18N.en['motion.imageSource'] = 'Still image';
  I18N.zh['motion.videoSource'] = 'MP4 \u89c6\u9891'; I18N.en['motion.videoSource'] = 'MP4 video';
  I18N.zh['motion.openOutput'] = '\u6253\u5f00\u5bfc\u51fa\u76ee\u5f55'; I18N.en['motion.openOutput'] = 'Open output folder';
  const $ = id => document.getElementById(id);
  const q = sel => Array.from(document.querySelectorAll(sel));
  const lang = () => state.config.language === 'en' ? 'en' : 'zh';
  const t = key => (I18N[lang()][key] || I18N.zh[key] || key);
  const apiCall = (name, ...args) => window.pywebview && window.pywebview.api ? window.pywebview.api[name](...args) : Promise.reject(new Error('pywebview is not ready'));
  const displayKey = value => String(value || '').split('+').map(x => ({ctrl:'Ctrl',shift:'Shift',alt:'Alt',cmd:'Cmd',enter:'Enter',escape:'Esc',space:'Space',page_up:'PageUp',page_down:'PageDown'}[x] || x.toUpperCase())).join(' + ');
  const formatSize = bytes => bytes < 1024 ? `${bytes} B` : bytes < 1048576 ? `${(bytes/1024).toFixed(1)} KB` : `${(bytes/1048576).toFixed(1)} MB`;

  function applyI18n(root) {
    (root || document).querySelectorAll('[data-i18n]').forEach(node => { node.textContent = t(node.dataset.i18n); });
    (root || document).querySelectorAll('[data-placeholder]').forEach(node => { node.placeholder = t(node.dataset.placeholder); });
    document.documentElement.lang = lang() === 'en' ? 'en' : 'zh-CN';
    document.title = `XAOCEN ImgTor v${APP_VERSION}`;
    q('[data-version]').forEach(node => { node.textContent = `v${APP_VERSION}`; });
    renderIcons(root || document);
    applyPanelMeta(state.current);
  }
  async function setTheme(value, persist) { const theme = value === 'dark' ? 'dark' : 'light'; document.body.classList.toggle('dark', theme === 'dark'); state.config.theme = theme; if ($('themeMode')) $('themeMode').value = theme; if (persist !== false) { const result = await apiCall('save_other_settings', {theme}); if (result && result.ok !== false) setStatus(t('common.saved'), true); else setStatus(t('common.invalid'), false); } }
  async function setLanguage(value, persist) { state.config.language = value === 'en' ? 'en' : 'zh'; applyI18n(); if ($('languageMode')) $('languageMode').value = state.config.language; if (persist !== false) { const result = await apiCall('save_other_settings', {language:state.config.language}); if (result && result.ok !== false) setStatus(t('common.saved'), true); else setStatus(t('common.invalid'), false); } renderAll(); }

  function renderNav() {
    $('nav').innerHTML = NAV.map(([key, glyph]) => `<button type="button" data-nav="${key}" class="${state.current === key ? 'active' : ''}">${icon(glyph,18)}<span>${t(PANEL_META[key].nav)}</span></button>`).join('');
    q('[data-nav]').forEach(node => node.addEventListener('click', () => go(node.dataset.nav)));
  }
  function applyPanelMeta(key) {
    const meta = PANEL_META[key] || PANEL_META.launcher;
    if ($('pageTitle')) $('pageTitle').textContent = t(meta.nav);
  }
  function syncPageState(key) {
    const next = PANEL_META[key] ? key : 'launcher';
    state.current = next;
    q('.panel').forEach(panel => panel.classList.toggle('active', panel.id === next));
    q('[data-nav]').forEach(node => node.classList.toggle('active', node.dataset.nav === next));
    applyPanelMeta(next);
    const content = document.querySelector('.content');
    if (content) content.scrollTop = 0;
    $('hotkeyBadge').textContent = displayKey(state.config.hotkey);
    setTheme(state.config.theme || 'light', false);
    document.documentElement.lang = lang() === 'en' ? 'en' : 'zh-CN';
  }
  function go(key) { syncPageState(key); if (state.current === 'gallery') loadState(); if (state.current === 'settings') renderSettings(); }
  let statusTimer = null;
  function setStatus(message, state='info') {
    const kind = state === true ? 'success' : state === false ? 'error' : state;
    const node = $('appStatus'), text = $('appStatusText'), settingsNotice = $('saved');
    if (settingsNotice) { settingsNotice.textContent = message; settingsNotice.className = `notice ${kind === 'success' ? 'ok' : kind === 'error' ? 'error' : ''}`; }
    if (!node || !text) return;
    clearTimeout(statusTimer);
    text.textContent = message;
    node.hidden = false;
    node.className = `app-status is-${kind}`;
    if (kind !== 'progress') statusTimer = setTimeout(() => { node.hidden = true; }, kind === 'error' ? 7000 : 5000);
  }

  function normalizeRatioText(value) {
    const normalized = String(value || '').trim().replace(/[：／/]/g, ':');
    const match = normalized.match(/^(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)$/);
    if (!match) return null;
    const width = Number(match[1]), height = Number(match[2]);
    return Number.isFinite(width) && Number.isFinite(height) && width > 0 && height > 0 && width <= 10000 && height <= 10000 ? `${width}:${height}` : null;
  }
  function renderRatios() {
    $('ratios').innerHTML = [...state.ratios, CUSTOM_RATIO].map(value => value === CUSTOM_RATIO ? `<button class="choice" data-ratio="${CUSTOM_RATIO}" type="button" data-i18n="ratio.custom">${t('ratio.custom')}</button>` : `<button class="choice" data-ratio="${value}" type="button">${value}</button>`).join('');
    q('[data-ratio]').forEach(node => node.addEventListener('click', () => {
      if (node.dataset.ratio === CUSTOM_RATIO) {
        $('shotCustomRatioControl').hidden = false;
        q('[data-ratio]').forEach(item => item.classList.toggle('selected', item === node));
        $('shotCustomRatio').focus();
        return;
      }
      state.config.default_ratio = node.dataset.ratio;
      $('shotCustomRatioControl').hidden = true;
      q('[data-ratio]').forEach(item => item.classList.toggle('selected', item === node));
      saveCapture(false);
    }));
  }
  function setShotMode(mode, save) { state.config.default_mode = mode; $('shotModeFree').classList.toggle('active', mode === 'free'); $('shotModeRatio').classList.toggle('active', mode === 'ratio'); $('shotModeFixed').classList.toggle('active', mode === 'fixed'); $('ratioSettings').hidden = mode !== 'ratio'; $('fixedSettings').hidden = mode !== 'fixed'; if (save) saveCapture(false); }
  function renderOptionLists() {
    $('shotFormat').innerHTML = state.imageFormats.map(value => `<option value="${value}">${value.toUpperCase()}</option>`).join('');
    $('settingFps').innerHTML = state.fps.map(value => `<option value="${value}">${value}</option>`).join('');
    $('settingFormat').innerHTML = state.gifFormats.map(value => `<option value="${value}">${value === 'webp' ? 'Animated WebP' : value.toUpperCase()}</option>`).join('');
  }
  async function saveCapture(show) {
    const data = { ...state.config, default_mode:state.config.default_mode, default_ratio:state.config.default_ratio, fixed_width_str:$('fixedW').value, fixed_height_str:$('fixedH').value, file_format:$('shotFormat').value, save_directory:$('shotSaveDir').value, auto_save:$('autoSave').checked, auto_clipboard:$('autoClip').checked };
    const result = await apiCall('save_other_settings', data); if (result && result.ok !== false) { state.config = result.config || {...state.config,...data}; if (show) setStatus(t('common.saved'), true); } else setStatus(t('common.invalid'), false);
    syncConfig();
  }
  function applyShotCustomRatio() {
    const value = normalizeRatioText($('shotCustomRatio').value);
    if (!value) { setStatus(t('ratio.invalid'), false); return; }
    state.config.default_ratio = value;
    saveCapture(false);
  }
  function syncConfig() {
    $('hotkeyBadge').textContent = displayKey(state.config.hotkey); $('shotShortcut').textContent = displayKey(state.config.hotkey); $('fixedW').value = state.config.fixed_width_str || '400px'; $('fixedH').value = state.config.fixed_height_str || '320px'; $('shotFormat').value = state.config.file_format || 'png'; $('shotSaveDir').value = state.config.save_directory || ''; $('autoSave').checked = !!state.config.auto_save; $('autoClip').checked = !!state.config.auto_clipboard; setShotMode(state.config.default_mode || 'ratio', false);
    const shotRatio = state.config.default_ratio || RATIOS[0];
    const shotIsCustom = !state.ratios.includes(shotRatio);
    $('shotCustomRatio').value = shotIsCustom ? shotRatio : '';
    $('shotCustomRatioControl').hidden = !shotIsCustom;
    q('[data-ratio]').forEach(n => n.classList.toggle('selected', n.dataset.ratio === (shotIsCustom ? CUSTOM_RATIO : shotRatio)));
    const listenerStatus = $('listenerStatus'); listenerStatus.textContent = state.listener_running ? t('status.running') : t('status.stopped'); listenerStatus.className = `status-chip ${state.listener_running ? 'is-running' : 'is-stopped'}`;
  }

  function renderGifChoices() {
    $('fps').innerHTML = state.fps.map(value => `<button type="button" class="${Number(state.config.gif_fps) === value ? 'selected' : ''}" data-fps="${value}">${value}</button>`).join('');
    $('formats').innerHTML = state.gifFormats.map(value => [value, value === 'webp' ? 'Animated WebP' : value.toUpperCase()]).map(([value,label]) => `<button type="button" class="${state.config.gif_format === value ? 'selected' : ''}" data-format="${value}">${label}</button>`).join('');
    $('gifModes').innerHTML = state.gifModes.map(value => `<button type="button" class="${(state.config.gif_mode || (state.config.gif_ratio === 'free' ? 'free' : 'ratio')) === value ? 'active' : ''}" data-gif-mode="${value}">${value === 'free' ? t('gif.free') : value === 'ratio' ? t('mode.ratio') : t('mode.fixed')}</button>`).join('');
    $('gifRatioSettings').hidden = (state.config.gif_mode || (state.config.gif_ratio === 'free' ? 'free' : 'ratio')) !== 'ratio';
    $('gifFixedSettings').hidden = (state.config.gif_mode || (state.config.gif_ratio === 'free' ? 'free' : 'ratio')) !== 'fixed';
    $('gifFixedW').value = state.config.gif_fixed_width_str || '400px';
    $('gifFixedH').value = state.config.gif_fixed_height_str || '320px';
    const gifRatio = state.config.gif_ratio || state.ratios[0];
    const gifIsCustom = gifRatio !== 'free' && !state.ratios.includes(gifRatio);
    $('gifRatios').innerHTML = [...state.ratios, CUSTOM_RATIO].map(value => value === CUSTOM_RATIO ? `<button type="button" class="${gifIsCustom ? 'selected' : ''}" data-gif-ratio="${CUSTOM_RATIO}" data-i18n="gif.other">${t('gif.other')}</button>` : `<button type="button" class="${gifRatio === value ? 'selected' : ''}" data-gif-ratio="${value}">${value}</button>`).join('');
    $('gifCustomRatio').value = gifIsCustom ? gifRatio : '';
    $('gifCustomRatioControl').hidden = !gifIsCustom;
    q('[data-fps]').forEach(n => n.addEventListener('click', () => saveGif({gif_fps:Number(n.dataset.fps)})));
    q('[data-format]').forEach(n => n.addEventListener('click', () => saveGif({gif_format:n.dataset.format})));
    q('[data-gif-mode]').forEach(n => n.addEventListener('click', () => {
      const mode = n.dataset.gifMode;
      const patch = {gif_mode:mode};
      if (mode === 'free') patch.gif_ratio = 'free';
      if (mode === 'ratio' && state.config.gif_ratio === 'free') patch.gif_ratio = state.ratios[0];
      saveGif(patch);
    }));
    q('[data-gif-ratio]').forEach(n => n.addEventListener('click', () => {
      if (n.dataset.gifRatio === CUSTOM_RATIO) {
        $('gifCustomRatioControl').hidden = false;
        q('[data-gif-ratio]').forEach(item => item.classList.toggle('selected', item === n));
        $('gifCustomRatio').focus();
        return;
      }
      saveGif({gif_ratio:n.dataset.gifRatio, gif_mode:'ratio'});
    }));
    $('gifKeys').textContent = `${formatGifShortcut(state.config.record_start_key || 'enter', 'start')} · ${formatGifShortcut(state.config.record_stop_key || 'f9', 'stop')}`;
    $('gifSaveDir').value = state.config.save_directory || '';
  }
  function formatGifShortcut(value, action) {
    const key = String(value || '').toLowerCase();
    if (action === 'start' && key === 'enter') return t('gif.enterStart');
    return `${displayKey(value)} ${t(action === 'start' ? 'gif.startLabel' : 'gif.stopLabel')}`;
  }
  async function saveGif(patch) { const result = await apiCall('save_other_settings', {...patch}); if (result && result.config) { state.config = result.config; setStatus(t('common.saved'), true); } else setStatus(t('common.invalid'), false); renderGifChoices(); renderSettings(); }
  function applyGifCustomRatio() {
    const value = normalizeRatioText($('gifCustomRatio').value);
    if (!value) { setStatus(t('ratio.invalid'), false); return; }
    saveGif({gif_ratio:value, gif_mode:'ratio'});
  }

  function renderSettings() {
    $('hotkey').value = displayKey(state.config.hotkey); $('recordStart').value = displayKey(state.config.record_start_key); $('recordStop').value = displayKey(state.config.record_stop_key); $('settingFps').value = String(state.config.gif_fps || 10); $('settingFormat').value = state.config.gif_format || 'gif'; $('saveDir').value = state.config.save_directory || ''; $('themeMode').value = state.config.theme || 'light'; $('languageMode').value = state.config.language || 'zh';
  }
  function renderPlugins() {
    const list = $('pluginList'), directory = $('pluginDirectory');
    if (!list || !directory) return;
    directory.textContent = state.pluginRoot || '';
    list.replaceChildren();
    const plugins = Array.isArray(state.plugins) ? state.plugins : [];
    const known = new Set();
    for (const guide of PLUGIN_GUIDES) {
      const plugin = plugins.find(item => item.id === guide.id);
      known.add(guide.id);
      const card = document.createElement('article');
      const pluginStatus = plugin ? (plugin.status || 'invalid') : 'missing';
      card.className = `plugin-card is-${pluginStatus}`;
      const title = document.createElement('strong');
      title.textContent = plugin ? (plugin.name || guide.title) : guide.title;
      const version = document.createElement('span');
      version.className = 'plugin-version';
      version.textContent = plugin && plugin.version ? `v${plugin.version}` : '';
      const status = document.createElement('span');
      status.className = 'chip plugin-status';
      status.textContent = t(plugin ? `plugins.${pluginStatus}` : 'plugins.missing');
      const download = document.createElement('button');
      download.type = 'button'; download.className = 'secondary compact plugin-download';
      download.innerHTML = `<span>${guide.download ? t('plugins.download') : t('plugins.downloadPending')}</span>`;
      if (guide.download) {
        download.addEventListener('click', () => window.open(guide.download, '_blank', 'noopener'));
      } else {
        download.disabled = true;
        download.title = t('plugins.downloadPending');
      }
      const head = document.createElement('div');
      head.className = 'plugin-card-head';
      head.append(title, version, download, status);
      card.append(head);
      const details = document.createElement('p');
      details.textContent = t(guide.purpose);
      card.append(details);
      list.append(card);
    }
    for (const plugin of plugins.filter(item => !known.has(item.id))) {
      const card = document.createElement('article'); card.className = `plugin-card is-${plugin.status || 'invalid'}`;
      card.innerHTML = `<div class="plugin-card-head"><strong>${plugin.name || plugin.id}</strong><span class="plugin-version">${plugin.version ? `v${plugin.version}` : ''}</span><span class="chip plugin-status">${t(`plugins.${plugin.status || 'invalid'}`)}</span></div>`;
      list.append(card);
    }
  }
  async function openPluginDirectory() {
    try {
      const result = await apiCall('open_plugin_directory');
      if (result && result.ok) {
        state.pluginRoot = result.path || state.pluginRoot;
        renderPlugins(); setStatus(t('plugins.opened'), true);
      } else setStatus(t('plugins.openFailed'), false);
    } catch (_) { setStatus(t('plugins.openFailed'), false); }
  }
  async function refreshPlugins() {
    const result = await apiCall('plugins_state');
    if (!result) return false;
    state.plugins = result.plugins || [];
    state.pluginRoot = result.plugin_root || state.pluginRoot;
    renderPlugins(); renderMotionPhotoExport(); renderVideoPlugin();
    return true;
  }
  async function choosePluginDirectory() {
    try {
      const result = await apiCall('choose_plugin_directory');
      if (!result) return;
      if (!result.ok) { setStatus(t('plugins.directoryFailed'), false); return; }
      state.config = result.config || state.config; state.plugins = result.plugins || [];
      state.pluginRoot = result.path || state.pluginRoot;
      renderPlugins(); renderMotionPhotoExport(); renderVideoPlugin();
      setStatus(t('common.saved'), true);
    } catch (_) { setStatus(t('plugins.directoryFailed'), false); }
  }
  async function resetPluginDirectory() {
    try {
      const result = await apiCall('reset_plugin_directory');
      if (!result || !result.ok) { setStatus((result && result.message) || t('plugins.directoryFailed'), false); return; }
      state.config = result.config || state.config; state.plugins = result.plugins || [];
      state.pluginRoot = result.path || state.pluginRoot;
      renderPlugins(); renderMotionPhotoExport(); renderVideoPlugin(); setStatus(t('common.saved'), true);
    } catch (_) { setStatus(t('plugins.directoryFailed'), false); }
  }
  async function installPluginPackage() {
    try {
      setStatus(t('common.saving'), 'progress');
      const result = await apiCall('install_plugin_package');
      if (!result || result.error === 'cancelled') return;
      if (!result.ok) {
        setStatus(result.error === 'plugin_package_hash_mismatch' ? t('plugins.packageHashMismatch') : t('plugins.packageFailed'), false);
        return;
      }
      state.plugins = result.plugins || state.plugins;
      state.pluginRoot = result.plugin_root || state.pluginRoot;
      renderPlugins(); renderMotionPhotoExport(); renderVideoPlugin();
      setStatus(`${t('plugins.packageInstalled')}: ${result.name || result.id}`, true);
    } catch (_) { setStatus(t('plugins.packageFailed'), false); }
  }
  function renderAboutStats() { const stats=state.stats||{}; $('aboutFeatureCount').textContent=stats.completed_items ?? '—'; $('aboutFileCount').textContent=stats.project_files ?? '—'; $('aboutPendingCount').textContent=stats.pending_items ?? '—'; }

  async function chooseSaveDirectory(targetId) {
    const result = await apiCall('choose_save_directory');
    if (!result || !result.path) return;
    state.config = result.config || {...state.config, save_directory:result.path};
    $(targetId).value = result.path;
    syncConfig();
    renderSettings();
    setStatus(t('common.saved'), true);
  }
  function canonicalKey(event) {
    const mods = []; if (event.ctrlKey) mods.push('ctrl'); if (event.shiftKey) mods.push('shift'); if (event.altKey) mods.push('alt'); if (event.metaKey) mods.push('cmd');
    const names = {Control:'ctrl',Shift:'shift',Alt:'alt',Meta:'cmd',Enter:'enter',Escape:'escape',Esc:'escape',Space:'space',Tab:'tab',Backspace:'backspace',Delete:'delete',Insert:'insert',Home:'home',End:'end',PageUp:'page_up',PageDown:'page_down',ArrowUp:'up',ArrowDown:'down',ArrowLeft:'left',ArrowRight:'right'};
    let key = names[event.key] || (/^F\d+$/.test(event.key) ? event.key.toLowerCase() : event.key.length === 1 ? event.key.toLowerCase() : '');
    if (!key || ['ctrl','shift','alt','cmd'].includes(key)) return '';
    return [...new Set(mods), key].join('+');
  }
  function shortcutError(field, value, proposed) {
    if (!proposed) return 'shortcut.empty';
    const parts = proposed.split('+'), key = parts[parts.length - 1];
    if (!key || (key.length === 1 && parts.length === 1)) return field === 'hotkey' ? 'shortcut.modifier' : 'shortcut.invalid';
    if (['ctrl+c','ctrl+v','ctrl+x','ctrl+a','ctrl+z','ctrl+y','ctrl+s','ctrl+w','alt+f4','alt+tab','ctrl+alt+delete'].includes(proposed)) return 'shortcut.reserved';
    const all = {...state.config,...state.pending,[field]:proposed};
    if (field === 'record_start_key' && proposed === all.record_stop_key) return 'shortcut.same';
    if (field === 'record_stop_key' && proposed === all.record_start_key) return 'shortcut.same';
    if (field !== 'hotkey' && proposed === all.hotkey) return 'shortcut.conflictHotkey';
    if (field === 'hotkey' && proposed === all.record_start_key) return 'shortcut.conflictStart';
    if (field === 'hotkey' && proposed === all.record_stop_key) return 'shortcut.conflictStop';
    if (field === 'record_start_key' && proposed === all.record_stop_key) return 'shortcut.same';
    return '';
  }
  function setupKeyCapture(id, field) {
    const input = $(id), status = input.parentElement.querySelector('.shortcut-status');
    input.addEventListener('focus', () => { input.value = ''; status.textContent = t('shortcut.listening'); apiCall('set_shortcut_capture', true).catch(()=>{}); });
    input.addEventListener('keydown', event => { event.preventDefault(); event.stopPropagation(); const value = canonicalKey(event); if (!value) return; const error = shortcutError(field, value, value); if (error) { status.textContent = t(error); status.className = 'shortcut-status error'; return; } state.pending[field] = value; input.value = displayKey(value); status.textContent = t('shortcut.pending'); status.className = 'shortcut-status'; input.blur(); apiCall('set_shortcut_capture', false).catch(()=>{}); });
    input.addEventListener('blur', () => { if (!state.pending[field]) status.textContent = ''; });
  }
  async function applyShortcuts() {
    const data = {...state.config, ...state.pending}; setStatus(t('common.saving'), 'progress'); const result = await apiCall('save_settings', data);
    if (!result || !result.ok) { const errors = result && result.errors ? Object.values(result.errors).filter(Boolean) : []; const error = errors[0] || ''; const message = result && result.message ? result.message : (error === 'config_busy' ? '设置正被另一进程写入，请稍后重试。' : (error.startsWith('conflict_') ? (error.includes('record_start') ? t('shortcut.conflictStart') : error.includes('record_stop') ? t('shortcut.conflictStop') : t('shortcut.conflictHotkey')) : t(`shortcut.${error}`))); setStatus(message || t('shortcut.invalid'), false); return; }
    state.config = result.config; state.pending = {}; q('.shortcut-status').forEach(n => { n.textContent = t('shortcut.saved'); n.className = 'shortcut-status ok'; }); syncConfig(); renderSettings(); setStatus(t('common.saved'), true);
  }

  function galleryMatches(item) {
    if (state.filter === 'all') return true;
    if (state.filter === 'video') return !!item.video;
    if (state.filter === 'motion') return !item.video && (!!item.animated || !!item.motion_photo);
    return !item.video && !item.animated && !item.motion_photo;
  }
  function renderGallery() {
    const items = state.files.filter(galleryMatches); const grid = $('galleryGrid'); if (!items.length) { const firstUse = state.files.length === 0; grid.innerHTML = `<div class="gallery-empty"><strong>${t(firstUse ? 'gallery.emptyFirst' : 'gallery.noMatch')}</strong><span>${firstUse ? t('gallery.subtitle') : t('gallery.resetFilter')}</span><button type="button" class="secondary compact" data-empty-action>${icon(firstUse ? 'capture' : 'refresh',17)}<span>${t(firstUse ? 'gallery.captureNow' : 'gallery.resetFilter')}</span></button></div>`; const action=grid.querySelector('[data-empty-action]'); if(action) action.addEventListener('click',()=>firstUse?go('screenshot'):(state.filter='all',q('[data-filter]').forEach(n=>n.classList.toggle('active',n.dataset.filter==='all')),renderGallery())); return; }
    grid.innerHTML = items.map((item, index) => `<button type="button" class="gallery-card" data-gallery-index="${state.files.indexOf(item)}"><span class="thumb">${item.thumb ? `<img src="${item.thumb}" alt="">` : `<span class="ph"${item.video ? ` data-video-thumb="${state.files.indexOf(item)}"` : ''}>${item.format || 'IMG'}</span>`}${item.video ? `<span class="video-badge">${t('gallery.video')}</span>` : item.motion_photo ? `<span class="motion-badge motion-photo-badge">${t('gallery.motionPhoto')}</span>` : item.animated ? `<span class="motion-badge">${t('gallery.animated')}</span>` : ''}</span><span class="gallery-meta"><strong title="${item.name}">${item.name}</strong><small>${item.ratio || '—'} · ${formatSize(item.size || 0)}</small></span></button>`).join('');
    q('[data-video-thumb]').slice(0,12).forEach(node=>{const item=state.files[Number(node.dataset.videoThumb)];if(!item)return;apiCall('video_thumbnail',item.path).then(result=>{if(result&&result.ok&&node.isConnected){const image=document.createElement('img');image.src=result.data_url;image.alt='';node.replaceWith(image);}}).catch(()=>{});});
    q('[data-gallery-index]').forEach(node => { node.addEventListener('click', () => openGallery(Number(node.dataset.galleryIndex))); });
  }
  function showConfirmDialog(message) {
    return new Promise(resolve => {
      const backdrop = document.createElement('div');
      backdrop.className = 'app-confirm-backdrop';
      backdrop.innerHTML = `<div class="app-confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="confirmTitle"><div class="confirm-head"><span class="confirm-icon">${icon('trash',20)}</span><div class="confirm-copy"><h3 id="confirmTitle">${t('gallery.deleteTitle')}</h3><p>${message}</p></div></div><div class="confirm-actions"><button type="button" class="secondary" data-confirm-cancel>${t('common.cancel')}</button><button type="button" class="primary danger" data-confirm-ok>${t('gallery.delete')}</button></div></div>`;
      document.body.appendChild(backdrop);
      const close = result => { document.removeEventListener('keydown', onKey, true); backdrop.remove(); resolve(result); };
      const onKey = event => { if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(false); } if (event.key === 'Enter') { event.preventDefault(); event.stopPropagation(); close(true); } };
      backdrop.addEventListener('click', event => { if (event.target === backdrop) close(false); });
      backdrop.querySelector('[data-confirm-cancel]').addEventListener('click', () => close(false));
      backdrop.querySelector('[data-confirm-ok]').addEventListener('click', () => close(true));
      document.addEventListener('keydown', onKey, true);
      backdrop.querySelector('[data-confirm-cancel]').focus();
    });
  }
  function bindGalleryZoom(modal, media) {
    const viewport=modal.querySelector('.gallery-image-viewport'); if(!viewport||!media)return;
    let zoom=1;
    const apply=()=>{const width=media.videoWidth||media.naturalWidth,height=media.videoHeight||media.naturalHeight;if(!width||!height)return;const base=Math.min(viewport.clientWidth/width,viewport.clientHeight/height,1);media.style.maxWidth='none';media.style.maxHeight='none';media.style.width=`${Math.max(1,Math.round(width*base*zoom))}px`;media.style.height='auto';};
    const ready=media.tagName==='VIDEO'?'loadedmetadata':'load';media.addEventListener(ready,apply,{once:true});
    viewport.addEventListener('wheel',event=>{event.preventDefault();zoom=Math.max(.25,Math.min(5,zoom*(event.deltaY<0?1.12:1/1.12)));apply();},{passive:false});
  }
  function openGallery(index) {
    const item = state.files[index]; if (!item) return;
    state.modal = {index, playing:true, full:''};
    const modal = document.createElement('div'); modal.className='gallery-modal';
    const info = `${item.width || 0} × ${item.height || 0} · ${item.ratio || '—'} · ${formatSize(item.size || 0)} · ${item.format || ''}`;
    const isVideo = item.video || item.motion_photo;
    const viewer = isVideo ? `<video class="modal-video" controls preload="metadata"></video>` : `<img class="modal-image" src="${item.thumb || item.poster || ''}" alt="${item.name}">`;
    modal.innerHTML = `<div class="gallery-dialog" role="dialog"><div class="modal-top"><div class="gallery-title-block"><strong title="${item.name}">${item.name}</strong><small>${info}</small><span class="gallery-nav-hint">${t('gallery.navigation')} · 滚轮缩放</span></div><div class="modal-actions modal-actions-top">${item.animated ? `<button class="secondary" data-play>${icon('pause',17)}<span>${t('gallery.pause')}</span></button>` : ''}<button class="secondary" data-prev>${icon('arrowLeft',17)}<span>${t('gallery.prev')}</span></button><button class="secondary" data-next><span>${t('gallery.next')}</span>${icon('arrow',17)}</button><button class="secondary" data-open>${icon('folder',17)}<span>${t('gallery.open')}</span></button><button class="secondary" data-delete>${icon('trash',17)}<span>${t('gallery.delete')}</span></button><button class="icon-button" data-close aria-label="Close">${icon('close',20)}</button></div></div><div class="gallery-image-viewport">${viewer}</div></div>`;
    document.body.appendChild(modal); state.modal.node=modal;
    const openRelative = delta => { const items=state.files.filter(galleryMatches); const current=items.indexOf(item); const next=items[(current+delta+items.length)%items.length]; if(next){closeGallery();openGallery(state.files.indexOf(next));} };
    modal.querySelector('[data-close]').addEventListener('click', closeGallery); modal.addEventListener('click', e => { if (e.target === modal) closeGallery(); }); modal.querySelector('[data-prev]').addEventListener('click', () => openRelative(-1)); modal.querySelector('[data-next]').addEventListener('click', () => openRelative(1)); modal.querySelector('[data-open]').addEventListener('click', () => apiCall('open_file', item.path)); modal.querySelector('[data-delete]').addEventListener('click', async () => { if (!await showConfirmDialog(t('gallery.confirmDelete'))) return; const result=await apiCall('delete_file',item.path); if(result && result.ok){closeGallery();loadState();} });
    const play = modal.querySelector('[data-play]'); if (play) play.addEventListener('click', () => { state.modal.playing=!state.modal.playing; const img=modal.querySelector('.modal-image'); img.src=state.modal.playing ? (state.modal.full || item.thumb) : item.poster; play.innerHTML=icon(state.modal.playing?'pause':'play',17)+`<span>${t(state.modal.playing?'gallery.pause':'gallery.play')}</span>`; });
    const previewMedia=modal.querySelector(isVideo ? '.modal-video' : '.modal-image');bindGalleryZoom(modal,previewMedia);
    apiCall(item.motion_photo ? 'read_motion_photo_video' : (item.video ? 'read_video' : 'read_image'), item.path).then(result => { if(result && result.ok && state.modal && state.modal.node===modal){ state.modal.full=result.data_url; const media=modal.querySelector(isVideo ? '.modal-video' : '.modal-image'); if (media && (isVideo || state.modal.playing)) media.src=result.data_url; } }).catch(()=>{});
  }
  function closeGallery() { if (state.modal && state.modal.node) state.modal.node.remove(); state.modal=null; }
  function setupGallery() { q('[data-filter]').forEach(node => node.addEventListener('click', () => { state.filter=node.dataset.filter; q('[data-filter]').forEach(n=>n.classList.toggle('active',n===node)); renderGallery(); })); $('openFolder').addEventListener('click',()=>apiCall('open_folder')); document.addEventListener('keydown', e => { if (state.current!=='gallery'||!state.modal) return; if(e.key==='Escape') closeGallery(); if(e.key==='ArrowLeft'||e.key==='ArrowRight'){const items=state.files.filter(galleryMatches),current=items.indexOf(state.files[state.modal.index]); const next=items[(current+(e.key==='ArrowRight'?1:-1)+items.length)%items.length]; if(next) {closeGallery();openGallery(state.files.indexOf(next));}} if(e.key==='Delete'){const button=state.modal.node.querySelector('[data-delete]');if(button)button.click();} if(e.code==='Space' && state.files[state.modal.index] && state.files[state.modal.index].animated){e.preventDefault();const button=state.modal.node.querySelector('[data-play]');if(button)button.click();} }); }

  function cropCanvasPoint(event) { const rect=$('cropCanvas').getBoundingClientRect(); return {x:(event.clientX-rect.left)*$('cropCanvas').width/rect.width,y:(event.clientY-rect.top)*$('cropCanvas').height/rect.height}; }
  function parseCropDimension(value, fallback) { const match=String(value || '').trim().match(/^([\d.]+)\s*(px)?$/i); const parsed=match ? Number(match[1]) : NaN; return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback; }
  function cropRatioValue() { const parts=String(state.crop.ratio || '1:1').split(':').map(Number); return parts[0] > 0 && parts[1] > 0 ? parts[0] / parts[1] : 1; }
  function clampCropSelection(sel) {
    const c=state.crop, right=c.imageX+c.imageW, bottom=c.imageY+c.imageH;
    let w=Math.max(3,Number(sel.w)||3), h=Math.max(3,Number(sel.h)||3), x=Number(sel.x)||c.imageX, y=Number(sel.y)||c.imageY;
    if(c.mode==='ratio'){ const target=cropRatioValue(); if(w/h>target) w=h*target; else h=w/target; }
    if(c.mode==='fixed'){ w=Math.min(c.imageW,parseCropDimension(c.fixedWidth,400)*c.scale); h=Math.min(c.imageH,parseCropDimension(c.fixedHeight,320)*c.scale); }
    w=Math.min(w,c.imageW); h=Math.min(h,c.imageH); x=Math.max(c.imageX,Math.min(x,right-w)); y=Math.max(c.imageY,Math.min(y,bottom-h));
    if(c.mode==='ratio'){ const target=cropRatioValue(); if(w/h>target) w=h*target; else h=w/target; w=Math.min(w,right-x);h=Math.min(h,bottom-y); }
    return {x,y,w:Math.max(3,w),h:Math.max(3,h)};
  }
  function updateCropInfo() { const c=state.crop, info=$('cropInfo'); if(!info)return; if(!c.image){info.textContent='';return;} info.textContent=`${c.name} · ${c.image.naturalWidth} × ${c.image.naturalHeight} px · ${c.mode==='free'?t('crop.freeDraw'):c.mode==='ratio'?`${t('crop.fixedRatio')} ${c.ratio}`:`${t('crop.fixedSize')} ${c.fixedWidth} × ${c.fixedHeight}`}`; }
  function motionPluginInstalled() { return state.plugins.some(plugin => plugin.id === 'android-motion-photo' && plugin.status === 'installed'); }
  function renderMotionPhotoExport() {
    const box=$('motionPhotoExport'), stateChip=$('motionPluginState'), image=$('motionPhotoImage'), video=$('motionPhotoVideo'), choose=$('chooseMotionVideo'), exportButton=$('exportMotionPhoto'), tools=$('motionVideoTools');
    if(!box) return;
    const installed=motionPluginInstalled(), crop=state.crop, hasImage=!!crop.image, hasVideo=!!state.motionVideo;
    image.textContent=hasImage ? crop.name : t('motion.noImage');
    video.textContent=hasVideo ? state.motionVideo.name : t('motion.noVideo');
    stateChip.textContent=installed ? t('motion.ready') : t('motion.unavailable');
    box.classList.toggle('is-unavailable',!installed);
    choose.disabled=!installed;
    exportButton.disabled=!installed || !hasImage || !hasVideo;
    if(tools) tools.hidden=!hasVideo;
    const mode=$('motionClipMode'), start=$('motionClipStart'), duration=$('motionClipDuration'), meta=$('motionVideoMeta');
    if(hasVideo && mode && start && duration){
      const isFull=mode.value==='full', videoDuration=Number(state.motionVideo.duration||0), requested=Number(duration.value)||4.8;
      if(mode.value==='social') duration.value='4.8';
      start.disabled=isFull; duration.disabled=isFull;
      start.max=Math.max(0,videoDuration-(Number(duration.value)||requested)).toFixed(1);
      if(Number(start.value)>Number(start.max))start.value=start.max;
      if(meta)meta.textContent=videoDuration>0?`视频时长 ${videoDuration.toFixed(1)} 秒 · ${isFull?'将保留完整视频':'将精确裁切所选片段'}`:'正在读取视频信息…';
      const thumbs=$('motionThumbnails'); if(thumbs){thumbs.innerHTML=(state.motionVideo.thumbnails||[]).map(item=>`<button type="button" class="motion-thumbnail" data-motion-time="${item.timestamp}" title="预览 ${item.timestamp.toFixed(1)} 秒"><img src="${item.data_url}" alt="${item.timestamp.toFixed(1)} 秒"><small>${item.timestamp.toFixed(1)}s · 点击预览</small></button>`).join('');}
    }
    const status=$('motionPhotoStatus'); if(status) status.textContent=state.motionNotice || (installed ? t('motion.inputHint') : t('motion.installHint'));
  }
  function cropDataUrl(type='image/png', quality) {
    const c=state.crop;
    if(!c.image || !c.selection) return '';
    const s=c.selection, cropRect={x:(s.x-c.imageX)/c.scale,y:(s.y-c.imageY)/c.scale,width:s.w/c.scale,height:s.h/c.scale};
    const out=document.createElement('canvas'); out.width=Math.max(1,Math.round(cropRect.width));out.height=Math.max(1,Math.round(cropRect.height));
    out.getContext('2d').drawImage(c.image,cropRect.x,cropRect.y,cropRect.width,cropRect.height,0,0,out.width,out.height);
    return out.toDataURL(type,quality);
  }
  async function chooseMotionVideo() {
    const result=await apiCall('choose_motion_video');
    if(result && result.ok){
      state.motionVideo={path:result.path,name:result.name,duration:0,thumbnails:[]};state.motionNotice='正在读取视频时长…';renderMotionPhotoExport();
      const probe=await apiCall('inspect_motion_video',result.path);
      if(probe&&probe.ok&&probe.data&&Number(probe.data.duration_seconds)>0){
        state.motionVideo.duration=Number(probe.data.duration_seconds);state.motionNotice='';renderMotionPhotoExport();
        const thumbs=await apiCall('motion_video_thumbnails',result.path,state.motionVideo.duration);
        if(thumbs&&thumbs.ok)state.motionVideo.thumbnails=thumbs.data?.thumbnails||[];
      }else state.motionNotice='无法读取视频时长；仍可按完整视频导出。';
      renderMotionPhotoExport();
    }
    else if(result && result.error)setStatus(t('motion.failed'),false);
  }
  async function openMotionFrame(timestamp) {
    if(!state.motionVideo) return;
    const backdrop=document.createElement('div');backdrop.className='gallery-modal motion-frame-modal';
    backdrop.innerHTML=`<div class="motion-preview-dialog" role="dialog" aria-modal="true"><div class="motion-preview-head"><strong>${t('motion.previewTitle')} · ${Number(timestamp).toFixed(1)} s</strong><button type="button" class="icon-button" data-motion-close aria-label="Close">${icon('close',20)}</button></div><video controls preload="metadata"></video><div class="motion-preview-actions"><button type="button" class="secondary" data-motion-use>${t('motion.useStart')}</button></div></div>`;
    document.body.appendChild(backdrop);const close=()=>backdrop.remove(),video=backdrop.querySelector('video');
    backdrop.querySelector('[data-motion-close]').addEventListener('click',close);backdrop.addEventListener('click',event=>{if(event.target===backdrop)close();});
    backdrop.querySelector('[data-motion-use]').addEventListener('click',()=>{$('motionClipStart').value=Number(timestamp).toFixed(1);$('motionClipMode').value='custom';renderMotionPhotoExport();close();});
    try { const result=await apiCall('read_motion_video',state.motionVideo.path); if(result&&result.ok){video.src=result.data_url;video.addEventListener('loadedmetadata',()=>{video.currentTime=Math.min(Number(timestamp)||0,Math.max(0,video.duration-.05));},{once:true});} else { setStatus(result&&result.error==='video_too_large'?'视频超过 100 MB，无法在应用内预览。':'无法加载视频预览。',false);close(); } } catch (_) { setStatus('无法加载视频预览。',false);close(); }
  }
  function motionErrorMessage(result) {
    if (!result) return t('motion.failed');
    if (result.error === 'plugin_unavailable') return t('motion.unavailable');
    if (result.error === 'motion_video_invalid') return t('motion.invalidMp4');
    if (result.error === 'motion_video_duration_invalid') return '小米兼容仅支持 1–15 秒 MP4，请使用选段后再导出。';
    const detail = String(result.detail || '');
    if (/ftyp|MP4 file/i.test(detail)) return t('motion.invalidMp4');
    return `${t('motion.errorDetail')}${detail || t('motion.failed')}`;
  }
  async function exportMotionPhoto() {
    if(!motionPluginInstalled()){setStatus(t('motion.unavailable'),false);return;}
    if(!state.crop.image){setStatus(t('crop.needImage'),false);return;}
    if(!state.motionVideo){setStatus(t('motion.needVideo'),false);return;}
    const status=$('motionPhotoStatus'), mode=$('motionClipMode').value, start=Number($('motionClipStart').value)||0, duration=mode==='full'?0:(Number($('motionClipDuration').value)||4.8), profile=$('motionProfile').value;
    state.motionNotice=t('common.saving');status.textContent=state.motionNotice;setStatus(t('common.saving'),'progress');
    try{const result=await apiCall('export_android_motion_photo',cropDataUrl('image/jpeg',.95),state.crop.name,state.motionVideo.path,profile,start,duration);if(result&&result.ok){const message=`${t('common.saved')}: ${result.path}`;state.motionNotice=message;status.textContent=message;setStatus(message,true);loadState();}else{const message=motionErrorMessage(result);state.motionNotice=message;status.textContent=message;setStatus(message,false);}}catch(error){const message=`${t('motion.errorDetail')}${error && error.message ? error.message : t('motion.failed')}`;state.motionNotice=message;status.textContent=message;setStatus(message,false);}
  }
  function videoPluginInstalled() { return state.plugins.some(plugin => plugin.id === 'video-recorder-ffmpeg' && plugin.status === 'installed'); }
  function renderVideoPlugin() {
    const button=$('checkVideoPlugin'), chip=$('videoPluginState'), detail=$('videoPluginDetail'), start=$('launchVideo');
    if(!button || !chip || !detail || !start) return;
    const installed=videoPluginInstalled();
    button.disabled=!installed; start.disabled=!installed || !state.videoPluginReady; chip.textContent=state.videoPluginReady ? t('video.ready') : (installed ? t('video.missing') : t('video.unavailable'));
    if(!installed){detail.textContent='';state.videoPluginReady=false;}
  }
  async function checkVideoPlugin() {
    await refreshPlugins();
    if(!videoPluginInstalled()) { setStatus(t('video.unavailable'), false); return; }
    const detail=$('videoPluginDetail');detail.textContent=t('common.saving');
    try { const result=await apiCall('run_plugin','video-recorder-ffmpeg','check',{}); const data=result&&result.data;
      if(result&&result.ok&&data&&data.ready){state.videoPluginReady=true;$('videoPluginState').textContent=t('video.ready');detail.textContent=data.version||'';renderVideoPlugin();setStatus(t('video.ready'),true);}
      else {state.videoPluginReady=false;const message=data&&data.reason==='ffmpeg_missing'?t('video.missing'):t('video.unusable');$('videoPluginState').textContent=message;detail.textContent='';renderVideoPlugin();setStatus(message,false);}
    } catch (_) { state.videoPluginReady=false;$('videoPluginState').textContent=t('video.unusable');detail.textContent='';renderVideoPlugin();setStatus(t('video.unusable'),false); }
  }
  function setCropMode(mode) { const c=state.crop;c.mode=mode;q('[data-crop-mode]').forEach(n=>n.classList.toggle('active',n.dataset.cropMode===mode));$('cropRatioControl').hidden=mode!=='ratio';$('cropCustomRatioControl').hidden=mode!=='ratio' || state.ratios.includes(c.ratio);$('cropFixedControl').hidden=mode!=='fixed';if(c.selection)c.selection=clampCropSelection(c.selection);updateCropInfo();drawCrop(); }
  function drawCrop() { const c=state.crop, canvas=$('cropCanvas'), ctx=canvas.getContext('2d'); ctx.clearRect(0,0,canvas.width,canvas.height); const empty=$('cropEmpty'), actionHint=$('cropHint'), preview=document.querySelector('.crop-preview-row'), info=$('cropInfo'), actions=document.querySelector('.crop-actions'), clear=$('clearCrop'); if(!c.image){if(canvas)canvas.style.display='none';if(empty)empty.style.display='';if(actionHint)actionHint.style.display='none';if(preview)preview.style.display='none';if(info)info.style.display='none';if(actions)actions.style.display='none';if(clear)clear.hidden=true;renderMotionPhotoExport();return;} if(canvas)canvas.style.display='';if(empty)empty.style.display='none';if(actionHint)actionHint.style.display=c.selection?'':'none';if(preview)preview.style.display='';if(info)info.style.display='';if(actions)actions.style.display='';if(clear)clear.hidden=false;ctx.fillStyle='#aeb7bd';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(c.image,c.imageX,c.imageY,c.imageW,c.imageH);if(!c.selection)c.selection={x:c.imageX,y:c.imageY,w:c.imageW,h:c.imageH};const s=c.selection;ctx.fillStyle='rgba(10,16,20,.56)';ctx.fillRect(c.imageX,c.imageY,c.imageW,c.imageH);ctx.clearRect(s.x,s.y,s.w,s.h);ctx.drawImage(c.image,(s.x-c.imageX)/c.scale,(s.y-c.imageY)/c.scale,s.w/c.scale,s.h/c.scale,s.x,s.y,s.w,s.h);if(c.mode==='fixed'){ctx.fillStyle='rgba(255,189,74,.08)';ctx.fillRect(s.x,s.y,s.w,s.h);}ctx.strokeStyle='#44d9e6';ctx.lineWidth=2;ctx.setLineDash(c.mode==='free'?[7,4]:[]);ctx.strokeRect(s.x,s.y,s.w,s.h);ctx.setLineDash([]);ctx.fillStyle='#ffbd4a';[[s.x,s.y],[s.x+s.w,s.y],[s.x,s.y+s.h],[s.x+s.w,s.y+s.h]].forEach(([x,y])=>ctx.fillRect(x-4,y-4,8,8));renderMotionPhotoExport(); }
  function setCropSource(data,name,path,fromPicker=false,dropped=false,sourceSize=null) { const image=new Image(); image.onload=()=>{ const c=state.crop, canvas=$('cropCanvas'), overwrite=$('overwriteCrop'); c.image=image;c.name=name||'image.png';c.path=fromPicker?(path||''):'';c.sourceScaleX=sourceSize&&sourceSize.width?sourceSize.width/image.width:1;c.sourceScaleY=sourceSize&&sourceSize.height?sourceSize.height/image.height:1;c.scale=Math.min((canvas.width-24)/image.width,(canvas.height-24)/image.height,1);c.imageW=image.width*c.scale;c.imageH=image.height*c.scale;c.imageX=(canvas.width-c.imageW)/2;c.imageY=(canvas.height-c.imageH)/2;c.selection={x:c.imageX,y:c.imageY,w:c.imageW,h:c.imageH};overwrite.checked=false;overwrite.disabled=!c.path;overwrite.closest('.switch').classList.toggle('is-disabled',!c.path);$('cropStatus').textContent=dropped?t('crop.dropReady'):'';if(dropped)setStatus(t('crop.dropReady'),'info');updateCropInfo();drawCrop(); }; image.onerror=()=>setStatus(t('crop.dropInvalid'),false); image.src=data; }
  function isSupportedDropImage(file) { const name=String(file&&file.name||'').toLowerCase(); return !!file && (String(file.type||'').startsWith('image/') || /\.(png|jpe?g|bmp|gif|apng|webp|ico|tiff?)$/.test(name)); }
  function loadDroppedCropFile(file) { if(!isSupportedDropImage(file)){setStatus(t('crop.dropInvalid'),false);return;} if(file.size>64*1024*1024){setStatus('图片过大，请使用“选择文件”加载。',false);return;} const reader=new FileReader();reader.onload=()=>setCropSource(reader.result,file.name,'',false,true);reader.onerror=()=>setStatus(t('crop.dropInvalid'),false);reader.readAsDataURL(file); }
  function bindCropDropTarget() { const box=$('cropBox');let depth=0;const hasFiles=event=>Array.from(event.dataTransfer?.types||[]).includes('Files');box.addEventListener('dragenter',event=>{if(!hasFiles(event))return;event.preventDefault();depth+=1;box.classList.add('is-dragging');});box.addEventListener('dragover',event=>{if(!hasFiles(event))return;event.preventDefault();event.dataTransfer.dropEffect='copy';box.classList.add('is-dragging');});box.addEventListener('dragleave',event=>{if(!hasFiles(event))return;depth=Math.max(0,depth-1);if(!depth)box.classList.remove('is-dragging');});box.addEventListener('drop',event=>{event.preventDefault();depth=0;box.classList.remove('is-dragging');loadDroppedCropFile(event.dataTransfer.files&&event.dataTransfer.files[0]);}); }
  function setupCrop() {
    $('cropFile').addEventListener('change',e=>{const file=e.target.files[0];if(!file)return;loadDroppedCropFile(file);});
    $('chooseCrop').addEventListener('click',async()=>{const result=await apiCall('choose_crop_image');if(result&&result.ok!==false)setCropSource(result.data_url,result.name,result.path,true,false,result.source_size);else if(result)setStatus(result.error==='crop_source_too_large'?'图片过大，暂不支持载入。':t('crop.dropInvalid'),false);});
    const canvas=$('cropCanvas'); bindCropDropTarget();
    canvas.addEventListener('pointerdown',e=>{if(!state.crop.image)return;const c=state.crop,p=cropCanvasPoint(e);c.dragging=true;c.dragStart=p;if(c.selection&&p.x>=c.selection.x&&p.x<=c.selection.x+c.selection.w&&p.y>=c.selection.y&&p.y<=c.selection.y+c.selection.h){c.dragMode='move';c.dragOffset={x:p.x-c.selection.x,y:p.y-c.selection.y};}else{c.dragMode='draw';c.selection={x:p.x,y:p.y,w:1,h:1};}canvas.setPointerCapture(e.pointerId);});
    canvas.addEventListener('pointermove',e=>{const c=state.crop;if(!c.dragging)return;const p=cropCanvasPoint(e);if(c.dragMode==='move'){c.selection=clampCropSelection({x:p.x-c.dragOffset.x,y:p.y-c.dragOffset.y,w:c.selection.w,h:c.selection.h});}else{const start=c.dragStart;c.selection=clampCropSelection({x:Math.min(start.x,p.x),y:Math.min(start.y,p.y),w:Math.abs(p.x-start.x),h:Math.abs(p.y-start.y)});}drawCrop();});
    const stopDrag=()=>{state.crop.dragging=false;state.crop.dragMode='draw';}; canvas.addEventListener('pointerup',stopDrag);canvas.addEventListener('pointercancel',stopDrag);
    q('[data-crop-mode]').forEach(node=>node.addEventListener('click',()=>setCropMode(node.dataset.cropMode))); $('clearCrop').addEventListener('click',()=>{state.crop.image=null;state.crop.name='';state.crop.path='';state.crop.selection=null;$('cropFile').value='';$('cropStatus').textContent='';drawCrop();}); $('cropRatioSelect').addEventListener('change',e=>{if(e.target.value===CUSTOM_RATIO){$('cropCustomRatioControl').hidden=false;$('cropCustomRatio').focus();return;}state.crop.ratio=e.target.value;$('cropCustomRatioControl').hidden=true;if(state.crop.selection)state.crop.selection=clampCropSelection(state.crop.selection);updateCropInfo();drawCrop();}); $('applyCropCustomRatio').addEventListener('click',()=>{const value=normalizeRatioText($('cropCustomRatio').value);if(!value){setStatus(t('ratio.invalid'),false);return;}state.crop.ratio=value;$('cropRatioSelect').value=CUSTOM_RATIO;$('cropCustomRatioControl').hidden=false;if(state.crop.selection)state.crop.selection=clampCropSelection(state.crop.selection);updateCropInfo();drawCrop();}); $('cropFixedW').addEventListener('change',e=>{state.crop.fixedWidth=e.target.value;if(state.crop.selection)state.crop.selection=clampCropSelection(state.crop.selection);updateCropInfo();drawCrop();}); $('cropFixedH').addEventListener('change',e=>{state.crop.fixedHeight=e.target.value;if(state.crop.selection)state.crop.selection=clampCropSelection(state.crop.selection);updateCropInfo();drawCrop();}); $('saveCrop').addEventListener('click',saveCrop);$('chooseMotionVideo').addEventListener('click',chooseMotionVideo);$('exportMotionPhoto').addEventListener('click',exportMotionPhoto);setCropMode('free');
    $('motionClipMode').addEventListener('change',()=>renderMotionPhotoExport());$('motionClipStart').addEventListener('change',()=>renderMotionPhotoExport());$('motionClipDuration').addEventListener('change',()=>renderMotionPhotoExport());$('motionProfile').addEventListener('change',()=>renderMotionPhotoExport());$('motionThumbnails').addEventListener('click',event=>{const button=event.target.closest('[data-motion-time]');if(!button)return;openMotionFrame(button.dataset.motionTime);});
  }
  async function saveCrop() { const c=state.crop;if(!c.image){setStatus(t('crop.needImage'),false);return;}if(!c.selection||c.selection.w<3||c.selection.h<3){setStatus(t('crop.needArea'),false);return;}const s=c.selection,cropRect={x:(s.x-c.imageX)/c.scale,y:(s.y-c.imageY)/c.scale,width:s.w/c.scale,height:s.h/c.scale},sourceRect={x:cropRect.x*(c.sourceScaleX||1),y:cropRect.y*(c.sourceScaleY||1),width:cropRect.width*(c.sourceScaleX||1),height:cropRect.height*(c.sourceScaleY||1)},out=document.createElement('canvas');out.width=Math.max(1,Math.round(cropRect.width));out.height=Math.max(1,Math.round(cropRect.height));out.getContext('2d').drawImage(c.image,cropRect.x,cropRect.y,cropRect.width,cropRect.height,0,0,out.width,out.height);const overwrite=$('overwriteCrop').checked;if(overwrite&&!c.path){setStatus(t('crop.overwriteHint'),false);return;}$('cropStatus').textContent=t('common.saving');setStatus(t('common.saving'),'progress');try{const result=await apiCall('save_crop',out.toDataURL('image/png'),c.name,overwrite,c.path,sourceRect);if(result&&result.ok){const message=`${t('common.saved')}: ${result.path}`;$('cropStatus').textContent=message;setStatus(message,true);loadState();}else{const message=result&&result.error==='invalid_crop_data'?t('crop.invalidData'):t('crop.saveFailed');$('cropStatus').textContent=message;setStatus(message,false);}}catch(_){const message=t('crop.saveFailed');$('cropStatus').textContent=message;setStatus(message,false);} }

  async function loadState() { try { const result=await apiCall('state'); state.config=result.config||{};state.ratios=Array.isArray(result.ratio_presets)&&result.ratio_presets.length ? result.ratio_presets : RATIOS;state.selectionModes=result.selection_modes||state.selectionModes;state.imageFormats=result.image_formats||IMAGE_FORMATS;state.gifFormats=result.gif_formats||GIF_FORMATS;state.fps=result.gif_fps||FPS;state.gifModes=result.gif_modes||GIF_MODES;state.files=result.files||[];state.plugins=result.plugins||[];state.pluginRoot=result.plugin_root||'';state.stats=result.project_stats||state.stats;state.listener_running=result.listener_running; await setTheme(state.config.theme || 'light', false); applyI18n();renderAll(); } catch (error) { console.error(error); } }
  async function pollRuntimeStatus() { try { const event = await apiCall('poll_runtime_status'); if (event && event.message) { setStatus(event.message, event.level || 'info'); if (state.current === 'gallery') loadState(); } } catch (_) {} }
  function renderAll() { renderNav();syncPageState(state.current);renderRatios();renderOptionLists();syncConfig();renderGifChoices();renderGallery();renderSettings();renderPlugins();renderMotionPhotoExport();renderVideoPlugin();renderAboutStats(); }
  function setSidebarCollapsed(collapsed) {
    document.body.classList.toggle('sidebar-collapsed', collapsed);
    const button = $('collapseSidebar');
    if (button) {
      button.innerHTML = icon(collapsed ? 'chevronRight' : 'chevronLeft', 18);
      button.setAttribute('aria-label', collapsed ? 'Expand sidebar' : 'Collapse sidebar');
      button.title = collapsed ? '展开侧栏' : '折叠侧栏';
    }
  }
  let bound = false;
  function bind() {
    if (bound) return;
    bound = true;
    setSidebarCollapsed(localStorage.getItem('xaocen-sidebar-collapsed') === '1'); document.addEventListener('click',event=>{const button=event.target.closest('#collapseSidebar');if(button){event.preventDefault();event.stopPropagation();const next=!document.body.classList.contains('sidebar-collapsed');setSidebarCollapsed(next);localStorage.setItem('xaocen-sidebar-collapsed',next?'1':'0');return;}const brand=event.target.closest('#brand');if(brand&&document.body.classList.contains('sidebar-collapsed')){setSidebarCollapsed(false);localStorage.setItem('xaocen-sidebar-collapsed','0');}}); q('[data-go]').forEach(node=>node.addEventListener('click',()=>go(node.dataset.go))); $('openPluginDirectory').addEventListener('click',openPluginDirectory); $('choosePluginDirectory').addEventListener('click',choosePluginDirectory); $('resetPluginDirectory').addEventListener('click',resetPluginDirectory); $('installPluginPackage').addEventListener('click',installPluginPackage); $('themeMode').addEventListener('change',e=>setTheme(e.target.value)); $('languageMode').addEventListener('change',e=>setLanguage(e.target.value)); $('shotModeFree').addEventListener('click',()=>setShotMode('free',true)); $('shotModeRatio').addEventListener('click',()=>setShotMode('ratio',true));$('shotModeFixed').addEventListener('click',()=>setShotMode('fixed',true));$('chooseShotDir').addEventListener('click',()=>chooseSaveDirectory('shotSaveDir'));$('chooseGifDir').addEventListener('click',()=>chooseSaveDirectory('gifSaveDir'));$('chooseSaveDir').addEventListener('click',()=>chooseSaveDirectory('saveDir'));$('applyShotCustomRatio').addEventListener('click',applyShotCustomRatio);$('shotCustomRatio').addEventListener('keydown',e=>{if(e.key==='Enter')applyShotCustomRatio();});$('applyGifCustomRatio').addEventListener('click',applyGifCustomRatio);$('gifCustomRatio').addEventListener('keydown',e=>{if(e.key==='Enter')applyGifCustomRatio();});$('saveShot').addEventListener('click',()=>saveCapture(true));$('restartListener').addEventListener('click',async()=>{await apiCall('restart_screenshot');state.listener_running=true;syncConfig();$('listenerStatus').textContent=t('status.restarted');});$('launchGif').addEventListener('click',()=>apiCall('launch','gif'));$('settingFps').addEventListener('change',e=>saveGif({gif_fps:Number(e.target.value)}));$('settingFormat').addEventListener('change',e=>saveGif({gif_format:e.target.value}));$('gifFixedW').addEventListener('change',e=>saveGif({gif_fixed_width_str:e.target.value}));$('gifFixedH').addEventListener('change',e=>saveGif({gif_fixed_height_str:e.target.value}));$('saveShortcuts').addEventListener('click',applyShortcuts);$('saveOther').addEventListener('click',async()=>{const data={gif_fps:Number($('settingFps').value),gif_format:$('settingFormat').value,gif_fixed_width_str:$('gifFixedW').value,gif_fixed_height_str:$('gifFixedH').value,save_directory:$('saveDir').value,theme:$('themeMode').value,language:$('languageMode').value};const result=await apiCall('save_other_settings',data);if(result&&result.config){state.config=result.config;applyI18n();renderAll();setStatus(t('common.saved'),true);}else setStatus((result&&result.message)||'设置保存失败，请稍后重试。',false);});
    $('checkVideoPlugin').addEventListener('click',checkVideoPlugin); $('launchVideo').addEventListener('click',()=>apiCall('launch','video')); $('openMotionOutput').addEventListener('click',()=>apiCall('open_folder'));
    setupKeyCapture('hotkey','hotkey');setupKeyCapture('recordStart','record_start_key');setupKeyCapture('recordStop','record_stop_key');setupGallery();setupCrop();
  }
  window.addEventListener('pywebviewready',()=>{ bind();loadState(); });
  if (window.pywebview) { bind(); loadState(); }
  setInterval(pollRuntimeStatus, 500);
  applyI18n(); renderNav();
})();
