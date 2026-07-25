import base64
import io
import json
import shutil
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from PIL import Image

import config_manager
import plugin_manager
from plugin_host import run_plugin
import runtime_status
from helpers import canvas_rect_to_image
from dimensions import parse_dimension
from gifrecorder import (GIFRecorder, compute_constrained_size, max_record_frames,
                         outside_border_segments, parse_ratio, selection_bbox)
from overlay import compute_constrained_size as screenshot_size, image_for_save_format
from shortcuts import to_pynput, to_tk_event, validate_all, validate_pair
from webapp import API, PENDING_ITEMS
from ratio_presets import RATIO_PRESETS, is_valid_ratio
from plugin_examples.android_motion_photo.motion_photo import (
    MotionPhotoError, create_motion_photo, extract_motion_photo,
    inspect_motion_photo,
)
from plugin_examples.video_recorder_ffmpeg.video_recorder import process_request as video_plugin_request
from video_plugin_runtime import build_gdigrab_command


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original_path = config_manager.CONFIG_PATH
        config_manager.CONFIG_PATH = Path(self.temp.name) / 'config.json'

    def tearDown(self):
        config_manager.CONFIG_PATH = self.original_path
        self.temp.cleanup()

    def test_migration_and_atomic_round_trip(self):
        config_manager.CONFIG_PATH.write_text(json.dumps({
            'hotkey': 'ctrl+shift+g',
            'record_end_key': 'f9',
            'gif_ratio': '16:9',
        }), encoding='utf-8')
        config = config_manager.load_config()
        self.assertEqual(config['config_version'], config_manager.CURRENT_CONFIG_VERSION)
        self.assertEqual(config['record_stop_key'], 'f9')
        self.assertEqual(config['gif_mode'], 'ratio')
        saved = config_manager.save_config({**config, 'gif_fps': '24'})
        self.assertEqual(saved['gif_fps'], 24)
        self.assertEqual(
            json.loads(config_manager.CONFIG_PATH.read_text(encoding='utf-8'))['config_version'],
            config_manager.CURRENT_CONFIG_VERSION,
        )

    def test_gif_fixed_dimensions_have_shared_defaults(self):
        config = config_manager.normalize_config({})
        self.assertEqual(config['gif_fixed_width_str'], '400px')
        self.assertEqual(config['gif_fixed_height_str'], '320px')

    def test_free_capture_mode_is_persistable(self):
        config = config_manager.normalize_config({'default_mode': 'free'})
        self.assertEqual(config['default_mode'], 'free')

    def test_invalid_shortcut_pair_falls_back_to_safe_defaults(self):
        config = config_manager.normalize_config({
            'hotkey': 'ctrl+shift+g',
            'record_start_key': 'f9',
            'record_stop_key': 'f9',
        })
        self.assertEqual((config['record_start_key'], config['record_stop_key']), ('enter', 'f9'))

    def test_removed_native_navigation_marker_is_migrated(self):
        config = config_manager.normalize_config({
            'config_version': 2,
            'ui_panel_request': 'gif',
        })
        self.assertEqual(config['config_version'], config_manager.CURRENT_CONFIG_VERSION)
        self.assertNotIn('ui_panel_request', config)

    def test_plugin_directory_can_be_configured_without_using_bundle_paths(self):
        original_config = config_manager.CONFIG_PATH
        original_root = plugin_manager.PLUGIN_ROOT
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'portable' / 'plugins'
            try:
                config_manager.CONFIG_PATH = Path(temp) / 'config.json'
                plugin_manager.PLUGIN_ROOT = plugin_manager.DEFAULT_PLUGIN_ROOT
                config_manager.save_config({'plugin_directory': str(root)})
                self.assertEqual(plugin_manager.plugin_root(), root.resolve())
                checked, error = plugin_manager.validate_plugin_root(root)
                self.assertEqual(error, '')
                self.assertEqual(checked, root.resolve())
            finally:
                config_manager.CONFIG_PATH = original_config
                plugin_manager.PLUGIN_ROOT = original_root

    def test_native_toolbar_popup_contract(self):
        controls = (Path(config_manager.BASE_DIR) / 'rounded_controls.py').read_text(encoding='utf-8')
        self.assertIn("return 'break'", controls)
        self.assertIn('popup.lift()', controls)
        self.assertNotIn("popup.bind('<FocusOut>'", controls)
        self.assertNotIn('popup.grab_set()', controls)

    def test_webview_window_reference_stays_private(self):
        app = (Path(config_manager.BASE_DIR) / 'webapp.py').read_text(encoding='utf-8')
        self.assertIn('self._window = None', app)
        self.assertIn('api._window = window', app)
        self.assertNotIn('api.window = window', app)

    def test_tray_icon_and_recording_border_use_distinct_semantic_colours(self):
        from tray import make_icon
        recorder = (Path(config_manager.BASE_DIR) / 'gifrecorder.py').read_text(encoding='utf-8')
        tray = (Path(config_manager.BASE_DIR) / 'tray.py').read_text(encoding='utf-8')
        self.assertEqual(make_icon().size, (64, 64))
        self.assertIn('from design_tokens import ACCENT_BLUE', recorder)
        self.assertIn('fill=ACCENT_BLUE', recorder)
        self.assertIn('self.icon.run_detached(setup=self._show_icon)', tray)
        self.assertIn('icon.visible = True', tray)

    def test_crop_drop_and_global_status_contracts(self):
        app = (Path(config_manager.BASE_DIR) / 'ui' / 'app.js').read_text(encoding='utf-8')
        page = (Path(config_manager.BASE_DIR) / 'ui' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('bindCropDropTarget()', app)
        self.assertIn('isSupportedDropImage(file)', app)
        self.assertIn("id=\"cropBox\"", page)
        self.assertIn("id=\"appStatus\"", page)

    def test_native_runtime_status_is_reported_once(self):
        original_status_path = runtime_status.STATUS_PATH
        runtime_status.STATUS_PATH = Path(self.temp.name) / 'status.json'
        try:
            api = API()
            written = runtime_status.publish_status('success', 'Screenshot saved', 'C:/tmp/capture.png')
            received = api.poll_runtime_status()
            self.assertEqual(received['id'], written['id'])
            self.assertEqual(received['path'], 'C:/tmp/capture.png')
            self.assertIsNone(api.poll_runtime_status())
        finally:
            runtime_status.STATUS_PATH = original_status_path

    def test_about_stats_report_current_test_count_and_pending_items(self):
        stats = API().state()['project_stats']
        expected_tests = sum(
            1 for path in (config_manager.BASE_DIR / 'tests').glob('test_*.py')
            for line in path.read_text(encoding='utf-8').splitlines()
            if line.strip().startswith('def test_')
        )
        self.assertEqual(stats['automated_tests'], expected_tests)
        self.assertEqual(stats['pending_items'], PENDING_ITEMS)

    def test_plugin_discovery_validates_manifest_without_executing_code(self):
        original_root = plugin_manager.PLUGIN_ROOT
        with tempfile.TemporaryDirectory() as temp:
            try:
                root = Path(temp) / 'plugins'
                plugin_manager.PLUGIN_ROOT = root
                valid = root / 'android-motion-photo'
                valid.mkdir(parents=True)
                (valid / 'plugin.json').write_text(json.dumps({
                    'id': 'android-motion-photo', 'api_version': 1,
                    'name': 'Android Motion Photo', 'version': '0.1.0',
                    'platforms': [],
                    'capabilities': ['mp4-record', 'motion-photo-export'],
                }), encoding='utf-8')
                invalid = root / 'broken-plugin'
                invalid.mkdir()
                (invalid / 'plugin.json').write_text('{not json', encoding='utf-8')
                bad_version = root / 'bad-version'
                bad_version.mkdir()
                (bad_version / 'plugin.json').write_text(json.dumps({
                    'id': 'bad-version', 'api_version': 'not-a-number',
                    'capabilities': [], 'platforms': [],
                }), encoding='utf-8')

                found = plugin_manager.discover_plugins()
                self.assertEqual([item['id'] for item in found],
                                 ['android-motion-photo', 'bad-version', 'broken-plugin'])
                self.assertEqual(found[0]['status'], 'installed')
                self.assertEqual(found[1]['reason'], 'api_version_invalid')
                self.assertEqual(found[2]['status'], 'invalid')
                self.assertTrue(plugin_manager.ensure_plugin_root().is_dir())
                state = API().state()
                self.assertIn('plugins', state)
                self.assertEqual(state['plugin_root'], str(root))
            finally:
                plugin_manager.PLUGIN_ROOT = original_root

    def test_plugin_ui_contracts_are_present(self):
        app = (Path(config_manager.BASE_DIR) / 'ui' / 'app.js').read_text(encoding='utf-8')
        page = (Path(config_manager.BASE_DIR) / 'ui' / 'index.html').read_text(encoding='utf-8')
        self.assertIn("open_plugin_directory", app)
        self.assertIn("renderPlugins", app)
        self.assertIn('id="pluginList"', page)
        self.assertIn('id="openPluginDirectory"', page)

    def test_verified_single_file_plugin_package_installs_only_after_hash_check(self):
        original_root = plugin_manager.PLUGIN_ROOT
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'plugins'
            source = Path(temp) / 'source'
            source.mkdir()
            (source / 'plugin.json').write_text(json.dumps({
                'id': 'sample-plugin', 'api_version': 1, 'name': 'Sample',
                'version': '1.0.0', 'platforms': [], 'capabilities': ['sample'],
            }), encoding='utf-8')
            (source / 'runner.py').write_text('print("safe")\n', encoding='utf-8')
            package = Path(temp) / 'sample.xaocen-plugin'
            try:
                plugin_manager.PLUGIN_ROOT = root
                plugin_manager.create_plugin_package(source, package)
                checked = plugin_manager.verify_plugin_package(package)
                self.assertTrue(checked['ok'])
                installed = plugin_manager.install_plugin_package(package)
                self.assertTrue(installed['ok'])
                self.assertTrue((root / 'sample-plugin' / 'runner.py').is_file())
                self.assertEqual(plugin_manager.discover_plugins()[0]['status'], 'installed')
            finally:
                plugin_manager.PLUGIN_ROOT = original_root

    def test_plugin_package_rejects_changed_payload(self):
        import zipfile
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'source'; source.mkdir()
            (source / 'plugin.json').write_text(json.dumps({
                'id': 'tampered-plugin', 'api_version': 1, 'capabilities': [], 'platforms': [],
            }), encoding='utf-8')
            (source / 'payload.txt').write_text('original', encoding='utf-8')
            package = Path(temp) / 'tampered.xaocen-plugin'
            plugin_manager.create_plugin_package(source, package)
            replacement = Path(temp) / 'tampered-copy.xaocen-plugin'
            with zipfile.ZipFile(package) as source_zip, zipfile.ZipFile(replacement, 'w') as target_zip:
                for item in source_zip.infolist():
                    target_zip.writestr(item.filename, 'changed' if item.filename == 'payload.txt'
                                        else source_zip.read(item.filename))
            package = replacement
            self.assertEqual(plugin_manager.verify_plugin_package(package)['error'], 'plugin_package_hash_mismatch')

    def test_config_timeout_is_a_user_visible_api_result(self):
        api = API()
        with mock.patch('webapp.update_config', side_effect=TimeoutError('busy')):
            result = api.save_other_settings({'gif_fps': 15})
        self.assertFalse(result['ok'])
        self.assertEqual(result['errors']['config'], 'config_busy')


class CoreTests(unittest.TestCase):
    def test_android_motion_photo_plugin_round_trip_without_video_encoder(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            still = folder / 'still.jpg'
            video = folder / 'clip.mp4'
            output = folder / 'still_MP.jpg'
            restored_still = folder / 'restored.jpg'
            restored_video = folder / 'restored.mp4'
            Image.new('RGB', (32, 20), '#ffbd4a').save(still, format='JPEG')
            mp4 = b'\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2avc1mp41payload'
            video.write_bytes(mp4)
            create_motion_photo(still, video, output)
            info = inspect_motion_photo(output)
            self.assertTrue(info['motion_photo'])
            self.assertEqual(info['video_length'], len(mp4))
            extract_motion_photo(output, restored_still, restored_video)
            self.assertEqual(restored_video.read_bytes(), mp4)
            with Image.open(restored_still) as image:
                self.assertEqual(image.size, (32, 20))

    def test_android_motion_photo_plugin_rejects_non_mp4_input(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            still = folder / 'still.jpg'
            invalid_video = folder / 'not-video.bin'
            Image.new('RGB', (8, 8), '#44d9e6').save(still, format='JPEG')
            invalid_video.write_bytes(b'not an mp4')
            with self.assertRaises(MotionPhotoError):
                create_motion_photo(still, invalid_video, folder / 'output.jpg')

    def test_plugin_host_runs_only_manifest_allowlisted_command(self):
        original_root = plugin_manager.PLUGIN_ROOT
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            root = folder / 'plugins'
            image = folder / 'still.jpg'
            video = folder / 'clip.mp4'
            output = folder / 'still_MP.jpg'
            Image.new('RGB', (12, 10), '#2eb3ff').save(image, format='JPEG')
            video.write_bytes(b'\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2avc1mp41payload')
            shutil.copytree(config_manager.BASE_DIR / 'plugin_examples' / 'android_motion_photo',
                            root / 'android-motion-photo')
            try:
                plugin_manager.PLUGIN_ROOT = root
                created = run_plugin('android-motion-photo', 'create', {
                    'image_path': str(image), 'video_path': str(video), 'output_path': str(output),
                })
                self.assertTrue(created['ok'])
                inspected = run_plugin('android-motion-photo', 'inspect', {'input_path': str(output)})
                self.assertTrue(inspected['ok'])
                self.assertTrue(inspected['data']['motion_photo'])
                denied = run_plugin('android-motion-photo', 'delete_everything', {})
                self.assertEqual(denied['error'], 'plugin_command_unsupported')
            finally:
                plugin_manager.PLUGIN_ROOT = original_root

    def test_plugin_host_resolves_manifest_id_when_example_folder_uses_underscores(self):
        original_root = plugin_manager.PLUGIN_ROOT
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'plugins'
            try:
                shutil.copytree(config_manager.BASE_DIR / 'plugin_examples' / 'android_motion_photo',
                                root / 'android_motion_photo')
                plugin_manager.PLUGIN_ROOT = root
                resolved = plugin_manager.resolve_plugin('android-motion-photo')
                self.assertIsNotNone(resolved)
                self.assertEqual(resolved[0].name, 'android_motion_photo')
            finally:
                plugin_manager.PLUGIN_ROOT = original_root

    def test_api_exports_current_crop_through_external_motion_plugin(self):
        original_root = plugin_manager.PLUGIN_ROOT
        original_config = config_manager.CONFIG_PATH
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            root = folder / 'plugins'
            output_dir = folder / 'output'
            video = folder / 'clip.mp4'
            preview = io.BytesIO()
            Image.new('RGB', (20, 12), '#ffbd4a').save(preview, format='JPEG')
            data_url = 'data:image/jpeg;base64,' + base64.b64encode(preview.getvalue()).decode('ascii')
            video.write_bytes(b'\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2avc1mp41payload')
            shutil.copytree(config_manager.BASE_DIR / 'plugin_examples' / 'android_motion_photo',
                            root / 'android-motion-photo')
            try:
                plugin_manager.PLUGIN_ROOT = root
                config_manager.CONFIG_PATH = folder / 'config.json'
                config_manager.save_config({'save_directory': str(output_dir)})
                result = API().export_android_motion_photo(data_url, 'crop.png', str(video))
                self.assertTrue(result['ok'])
                exported = Path(result['path'])
                self.assertTrue(exported.is_file())
                self.assertTrue(inspect_motion_photo(exported)['motion_photo'])
            finally:
                plugin_manager.PLUGIN_ROOT = original_root
                config_manager.CONFIG_PATH = original_config

    def test_motion_photo_xiaomi_profile_uses_legacy_offset(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            image = folder / 'image.jpg'
            video = folder / 'clip.mp4'
            output = folder / 'xiaomi_MP.jpg'
            Image.new('RGB', (20, 12), '#ffbd4a').save(image, format='JPEG')
            video.write_bytes(b'\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2avc1mp41payload')
            create_motion_photo(image, video, output, profile='xiaomi')
            info = inspect_motion_photo(output)
            self.assertTrue(info['motion_photo'])
            self.assertEqual('xiaomi', info['profile'])
            payload = output.read_bytes()
            self.assertIn(b'GCamera:MicroVideoOffset=', payload)
            self.assertIn(b'GCamera:MicroVideoPresentationTimestampUs="0"', payload)
            self.assertEqual(b'Exif\x00\x00', payload[6:12])
            self.assertLess(payload.find(b'Exif\x00\x00'), payload.find(b'GCamera:MicroVideoOffset'))

    def test_gallery_recognizes_embedded_motion_photo_video(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            image = folder / 'image.jpg'
            video = folder / 'clip.mp4'
            output = folder / 'motion.jpg'
            Image.new('RGB', (20, 12), '#ffbd4a').save(image, format='JPEG')
            video.write_bytes(b'\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2avc1mp41payload')
            create_motion_photo(image, video, output, profile='xiaomi')
            info = API._motion_photo_info(output)
            self.assertTrue(info['motion_photo'])
            self.assertEqual(video.stat().st_size, info['video_length'])

    def test_motion_photo_export_ui_contracts_are_present(self):
        app = (Path(config_manager.BASE_DIR) / 'ui' / 'app.js').read_text(encoding='utf-8')
        page = (Path(config_manager.BASE_DIR) / 'ui' / 'index.html').read_text(encoding='utf-8')
        self.assertIn("export_android_motion_photo", app)
        self.assertIn("motionPluginInstalled", app)
        self.assertIn('id="exportMotionPhoto"', page)
        self.assertIn('id="chooseMotionVideo"', page)
        self.assertIn('id="motionProfile"', page)
        self.assertIn('id="motionClipMode"', page)
        self.assertIn('motion_video_thumbnails', app)
        self.assertIn('read_motion_video', app)
        self.assertIn('read_motion_photo_video', app)
        self.assertIn('motion_photo', app)

    def test_video_plugin_reports_missing_ffmpeg_without_using_system_path(self):
        result = video_plugin_request({'protocol': 1, 'command': 'check', 'payload': {}})
        self.assertTrue(result['ok'])
        self.assertFalse(result['data']['ready'])
        self.assertIn(result['data']['reason'], {'ffmpeg_missing', 'windows_only'})

    def test_video_plugin_ui_contracts_are_present(self):
        app = (Path(config_manager.BASE_DIR) / 'ui' / 'app.js').read_text(encoding='utf-8')
        page = (Path(config_manager.BASE_DIR) / 'ui' / 'index.html').read_text(encoding='utf-8')
        self.assertIn("video-recorder-ffmpeg", app)
        self.assertIn("checkVideoPlugin", app)
        self.assertIn('id="videoPluginCard"', page)
        self.assertIn('id="checkVideoPlugin"', page)
        self.assertIn('id="launchVideo"', page)

    def test_video_command_uses_immutable_virtual_screen_coordinates(self):
        command = build_gdigrab_command('C:/plugin/bin/ffmpeg.exe', (-1600, 20, -800, 620),
                                        24, 15, 'C:/output/video.mp4')
        self.assertEqual(command[command.index('-offset_x') + 1], '-1600')
        self.assertEqual(command[command.index('-offset_y') + 1], '20')
        self.assertEqual(command[command.index('-video_size') + 1], '800x600')
        self.assertEqual(command[command.index('-framerate') + 1], '24')

    def test_video_recorder_reuses_dpi_aware_native_selection_engine(self):
        standalone = (config_manager.BASE_DIR / 'video_recorder_standalone.py').read_text(encoding='utf-8')
        recorder = (config_manager.BASE_DIR / 'gifrecorder.py').read_text(encoding='utf-8')
        self.assertIn('set_process_dpi_awareness()', standalone)
        self.assertIn("record_kind='video'", standalone)
        self.assertIn('self._video_record_loop(record_bbox)', recorder)
        self.assertIn('build_gdigrab_command(', recorder)

    def test_ratio_presets_have_canonical_order(self):
        self.assertEqual(RATIO_PRESETS, ('1:1', '1:2', '2:1', '2:3', '3:2', '3:4', '4:3', '16:6', '9:16', '16:9', '9:18', '18:9', '21:9'))
        self.assertEqual(API().state()['ratio_presets'], list(RATIO_PRESETS))

    def test_custom_ratios_are_validated_and_persisted(self):
        self.assertTrue(is_valid_ratio(' 5 : 4 '))
        self.assertTrue(is_valid_ratio('5：4'))
        self.assertTrue(is_valid_ratio('5/4'))
        self.assertFalse(is_valid_ratio('0:4'))
        config = config_manager.normalize_config({'default_ratio': '5:4', 'gif_ratio': '7:5'})
        self.assertEqual(config['default_ratio'], '5:4')
        self.assertEqual(config['gif_ratio'], '7:5')

    def test_shortcut_conversions_and_conflicts(self):
        self.assertEqual(to_pynput('ctrl+shift+g'), '<ctrl>+<shift>+g')
        self.assertEqual(to_tk_event('f9'), '<KeyPress-F9>')
        self.assertEqual(validate_pair('enter', 'enter')[2]['record_stop_key'], 'same_as_start')
        self.assertIn('record_stop_key', validate_all('ctrl+shift+g', 'f9', 'ctrl+shift+g')[1])

    def test_dimensions_and_ratio_math(self):
        self.assertEqual(parse_dimension('400px'), 400)
        self.assertEqual(parse_ratio('16:9'), (16.0, 9.0))
        self.assertEqual(parse_ratio('16／9'), (16.0, 9.0))
        self.assertEqual(compute_constrained_size(1000, 1000, ('ratio', 16, 9)), (1000, 562))
        self.assertEqual(screenshot_size(1000, 1000, ('ratio', 16, 9)), (1000, 562))
        self.assertEqual(max_record_frames(30), 450)

    def test_crop_coordinates_are_offset_and_clamped(self):
        self.assertEqual(
            canvas_rect_to_image(150, 80, 650, 380, 100, 50, 0.5, 1000, 600),
            (100, 60, 1000, 600),
        )

    def test_api_gallery_state_and_crop_output(self):
        with tempfile.TemporaryDirectory() as temp:
            original_path = config_manager.CONFIG_PATH
            config_manager.CONFIG_PATH = Path(temp) / 'config.json'
            try:
                folder = Path(temp) / 'pictures'
                folder.mkdir()
                image_path = folder / 'sample.png'
                Image.new('RGB', (160, 90), '#44d9e6').save(image_path)
                config_manager.save_config({'save_directory': str(folder)})
                api = API()
                state = api.state()
                self.assertIn('gif_formats', state)
                self.assertIn('gif_fps', state)
                self.assertIn('free', state['selection_modes'])
                self.assertGreater(state['project_stats']['project_files'], 0)
                self.assertEqual(len(state['files']), 1)
                self.assertEqual(state['files'][0]['ratio'], '16:9')
                self.assertTrue(state['files'][0]['thumb'].startswith('data:image/'))
                self.assertFalse(api.open_file(str(folder.parent / 'outside.png'))['ok'])

                buffer = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                buffer.close()
                Image.new('RGBA', (20, 10), '#ffbd4a').save(buffer.name)
                data = 'data:image/png;base64,' + base64.b64encode(Path(buffer.name).read_bytes()).decode()
                result = api.save_crop(data, 'sample.png', False)
                self.assertTrue(result['ok'])
                self.assertTrue(Path(result['path']).exists())
                Path(buffer.name).unlink(missing_ok=True)
            finally:
                config_manager.CONFIG_PATH = original_path

    def test_overwriting_animated_gif_crop_keeps_animation(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'animated.gif'
            frames = [Image.new('RGBA', (40, 24), colour) for colour in ('#ffbd4a', '#2eb3ff')]
            frames[0].save(source, format='GIF', save_all=True, append_images=frames[1:],
                           duration=[80, 140], loop=0)
            api = API()
            api._crop_sources[str(source.resolve())] = None
            preview = io.BytesIO()
            Image.new('RGBA', (20, 12), '#44d9e6').save(preview, format='PNG')
            data = 'data:image/png;base64,' + base64.b64encode(preview.getvalue()).decode()
            result = api.save_crop(data, source.name, True, str(source),
                                   {'x': 5, 'y': 4, 'width': 20, 'height': 12})
            self.assertTrue(result['ok'])
            with Image.open(source) as cropped:
                self.assertTrue(cropped.is_animated)
                self.assertEqual(cropped.n_frames, 2)
                self.assertEqual(cropped.size, (20, 12))

    def test_overwriting_apng_and_webp_crops_keeps_animation(self):
        with tempfile.TemporaryDirectory() as temp:
            for suffix, output_format in (('.png', 'PNG'), ('.webp', 'WEBP')):
                source = Path(temp) / f'animated{suffix}'
                frames = [Image.new('RGBA', (36, 20), colour) for colour in ('#ffbd4a', '#2eb3ff')]
                frames[0].save(source, format=output_format, save_all=True,
                               append_images=frames[1:], duration=[80, 120], loop=0)
                api = API()
                api._crop_sources[str(source.resolve())] = None
                preview = io.BytesIO()
                Image.new('RGBA', (18, 10), '#44d9e6').save(preview, format='PNG')
                data = 'data:image/png;base64,' + base64.b64encode(preview.getvalue()).decode()
                result = api.save_crop(data, source.name, True, str(source),
                                       {'x': 4, 'y': 3, 'width': 18, 'height': 10})
                self.assertTrue(result['ok'])
                with Image.open(source) as cropped:
                    self.assertTrue(cropped.is_animated)
                    self.assertEqual(cropped.n_frames, 2)
                    self.assertEqual(cropped.size, (18, 10))

    def test_ico_gallery_access_and_crop_preserves_multiple_sizes(self):
        with tempfile.TemporaryDirectory() as temp:
            original_config = config_manager.CONFIG_PATH
            config_manager.CONFIG_PATH = Path(temp) / 'config.json'
            try:
                folder = Path(temp) / 'pictures'; folder.mkdir()
                source = folder / 'sample.ico'
                Image.new('RGBA', (64, 64), '#44d9e6').save(
                    source, format='ICO', sizes=[(16, 16), (32, 32), (64, 64)])
                config_manager.save_config({'save_directory': str(folder)})
                api = API()
                self.assertIsNotNone(api._gallery_target(str(source)))
                self.assertTrue(api.read_image(str(source))['ok'])
                api._crop_sources[str(source.resolve())] = None
                preview = io.BytesIO()
                Image.new('RGBA', (32, 32), '#ffbd4a').save(preview, format='PNG')
                data = 'data:image/png;base64,' + base64.b64encode(preview.getvalue()).decode()
                result = api.save_crop(data, source.name, True, str(source),
                                       {'x': 16, 'y': 16, 'width': 32, 'height': 32})
                self.assertTrue(result['ok'])
                with Image.open(source) as cropped:
                    self.assertGreaterEqual(len(cropped.ico.sizes()), 2)
            finally:
                config_manager.CONFIG_PATH = original_config

    def test_invalid_crop_payload_returns_a_ui_safe_error(self):
        result = API().save_crop('not-a-data-url', 'sample.png')
        self.assertEqual(result, {'ok': False, 'error': 'invalid_crop_data'})

    def test_large_gallery_preview_is_bounded(self):
        with tempfile.TemporaryDirectory() as temp:
            original_path = config_manager.CONFIG_PATH
            config_manager.CONFIG_PATH = Path(temp) / 'config.json'
            try:
                folder = Path(temp) / 'pictures'
                folder.mkdir()
                image_path = folder / 'large.png'
                Image.new('RGB', (4096, 3072), '#2eb3ff').save(image_path)
                config_manager.save_config({'save_directory': str(folder)})
                result = API().read_image(str(image_path))
                self.assertTrue(result['ok'])
                raw = base64.b64decode(result['data_url'].split(',', 1)[1])
                with Image.open(io.BytesIO(raw)) as preview:
                    self.assertLessEqual(max(preview.size), 2048)
            finally:
                config_manager.CONFIG_PATH = original_path

    def test_gif_output_formats(self):
        with tempfile.TemporaryDirectory() as temp:
            frame = Image.new('RGB', (24, 16), '#44d9e6')
            for fmt, extension in (('gif', '.gif'), ('apng', '.png'), ('webp', '.webp')):
                recorder = GIFRecorder({'gif_fps': 5, 'gif_format': fmt}, temp)
                recorder.frames.append(frame.copy())
                recorder.output_format = fmt
                recorder._save_output()
                self.assertTrue(any(path.suffix == extension for path in Path(temp).iterdir()))

    def test_bmp_capture_output_accepts_rgba_images(self):
        with tempfile.TemporaryDirectory() as temp:
            image = Image.new('RGBA', (24, 16), '#44d9e6')
            output = image_for_save_format(image, 'BMP')
            path = Path(temp) / 'capture.bmp'
            output.save(path, format='BMP')
            with Image.open(path) as saved:
                self.assertEqual(saved.size, (24, 16))
                self.assertIn(saved.mode, {'RGB', 'L'})

    def test_gif_ratio_is_persisted_by_web_api(self):
        with tempfile.TemporaryDirectory() as temp:
            original_path = config_manager.CONFIG_PATH
            config_manager.CONFIG_PATH = Path(temp) / 'config.json'
            try:
                config_manager.save_config({})
                result = API().save_other_settings({'gif_ratio': '4:3', 'gif_mode': 'ratio'})
                self.assertTrue(result['ok'])
                self.assertEqual(result['config']['gif_ratio'], '4:3')
                self.assertEqual(config_manager.load_config()['gif_ratio'], '4:3')
            finally:
                config_manager.CONFIG_PATH = original_path

    def test_gif_selection_snapshot_is_independent_of_live_selection(self):
        recorder = GIFRecorder({'gif_fps': 5, 'gif_format': 'gif'}, tempfile.gettempdir())
        recorder._sel_cx, recorder._sel_cy = 10, 20
        recorder._sel_cw, recorder._sel_ch = 300, 200
        snapshot = selection_bbox(
            recorder._sel_cx, recorder._sel_cy,
            recorder._sel_cw, recorder._sel_ch)
        recorder._sel_cx, recorder._sel_cy = 90, 100
        self.assertEqual(snapshot, (10, 20, 310, 220))

    def test_gif_border_never_falls_inside_capture_area(self):
        segments = outside_border_segments(0, 0, 100, 80, 500, 400)
        self.assertEqual(
            set(segments),
            {(103, 0, 103, 80), (0, 83, 100, 83)},
        )
        edge_segments = outside_border_segments(3, 4, 100, 80, 500, 400)
        for x1, y1, x2, y2 in edge_segments:
            self.assertTrue(
                x2 <= 3 or x1 >= 103 or y2 <= 4 or y1 >= 84
            )


if __name__ == '__main__':
    unittest.main()
