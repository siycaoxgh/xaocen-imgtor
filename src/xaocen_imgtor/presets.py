"""Shared option lists used by configuration validation and UI state APIs."""

IMAGE_FORMATS = ('png', 'jpg', 'bmp')
GIF_FORMATS = ('gif', 'apng', 'webp')
GIF_FPS = (5, 8, 10, 12, 15, 20, 24, 30)
SELECTION_MODES = ('free', 'ratio', 'fixed')
GIF_MODES = ('free', 'ratio', 'fixed')
ICO_RECOMMENDED_SIZES = (16, 24, 32, 48, 256)
ICO_ADVANCED_SIZES = (20, 40, 64, 96, 128)
ICO_ALLOWED_SIZES = ICO_RECOMMENDED_SIZES + ICO_ADVANCED_SIZES
