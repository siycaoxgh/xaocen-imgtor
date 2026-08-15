"""Shared visual tokens for native Tk overlays.

The web UI keeps the same values in ``ui/styles.css`` because CSS cannot
import Python modules.  Keeping the native values here prevents the capture
and recording overlays from drifting away from the launcher theme.
"""

PRIMARY = '#FFBD4A'
ACCENT_CYAN = '#44D9E6'
ACCENT_BLUE = '#2EB3FF'
SOFT_BLUE = '#AFCFEE'
DANGER = '#E86B75'

SURFACE_LIGHT = '#FFFFFF'
SURFACE_DARK = '#1C1E23'
CONTROL_LIGHT = '#EEF1F4'
CONTROL_DARK = '#25282E'
TEXT_LIGHT = '#17191D'
TEXT_DARK = '#EEF1F5'
MUTED_LIGHT = '#707783'
MUTED_DARK = '#969CA8'

TOOLBAR_RADIUS = 12
CONTROL_RADIUS = 9
POPUP_RADIUS = 9
TOOLBAR_TOP_GAP = 5
CONTROL_HEIGHT = 30
POPUP_ROW_HEIGHT = 28
TOOLBAR_SIDE_PAD = 12

# Native overlay controls use one width so labels never change the toolbar
# geometry when the language or output format changes.
OVERLAY_CONTROL_WIDTH = 112
