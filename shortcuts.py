#!/usr/bin/env python3
"""Canonical shortcut parsing, validation, display and toolkit conversion."""

MODIFIERS = ('ctrl', 'shift', 'alt', 'cmd')
MODIFIER_ALIASES = {'control': 'ctrl', 'command': 'cmd', 'meta': 'cmd', 'win': 'cmd'}
KEY_ALIASES = {
    'return': 'enter', 'esc': 'escape', 'del': 'delete', 'spacebar': 'space',
    'pageup': 'page_up', 'pagedown': 'page_down',
}
SPECIAL_KEYS = {
    'enter', 'escape', 'space', 'tab', 'backspace', 'delete', 'insert',
    'home', 'end', 'page_up', 'page_down', 'up', 'down', 'left', 'right',
} | {f'f{i}' for i in range(1, 13)}

RESERVED = {
    'alt+f4', 'ctrl+alt+delete', 'ctrl+alt+del', 'cmd+l', 'cmd+d',
    'cmd+tab', 'alt+tab', 'alt+space', 'ctrl+shift+escape',
    'ctrl+c', 'ctrl+v', 'ctrl+x', 'ctrl+a', 'ctrl+z', 'ctrl+y',
    'ctrl+s', 'ctrl+shift+s', 'ctrl+w', 'ctrl+f', 'ctrl+insert',
    'shift+insert', 'shift+delete',
}


def normalize(value):
    """Return the canonical form, e.g. ctrl+shift+x or enter."""
    if value is None:
        return ''
    parts = [part.strip().lower() for part in str(value).replace('-', '+').split('+') if part.strip()]
    modifiers = []
    key = None
    for part in parts:
        part = MODIFIER_ALIASES.get(part, part)
        part = KEY_ALIASES.get(part, part)
        if part in MODIFIERS:
            if part not in modifiers:
                modifiers.append(part)
        elif key is None:
            key = part
        else:
            raise ValueError(f'multiple keys in shortcut: {value}')
    if key is None:
        return ''
    ordered = [mod for mod in MODIFIERS if mod in modifiers]
    return '+'.join(ordered + [key])


def is_valid_key(key):
    return len(key) == 1 or key in SPECIAL_KEYS or (key.startswith('f') and key[1:].isdigit())


def validate(value, *, require_modifier=False):
    """Return (canonical_value, error_code). error_code is None when valid."""
    try:
        canonical = normalize(value)
    except ValueError:
        return '', 'invalid_format'
    if not canonical:
        return '', 'empty'
    parts = canonical.split('+')
    key = parts[-1]
    modifiers = parts[:-1]
    if not is_valid_key(key):
        return '', 'invalid_key'
    if len(key) == 1 and not modifiers:
        return '', 'modifier_required' if require_modifier else 'modifier_required'
    if require_modifier and not modifiers:
        return '', 'modifier_required'
    if canonical in RESERVED:
        return '', 'reserved'
    return canonical, None


def validate_pair(start, stop):
    start_value, start_error = validate(start)
    stop_value, stop_error = validate(stop)
    errors = {'record_start_key': start_error, 'record_stop_key': stop_error}
    if not start_error and not stop_error and start_value == stop_value:
        errors['record_stop_key'] = 'same_as_start'
    return start_value, stop_value, {key: value for key, value in errors.items() if value}


def validate_all(hotkey, start, stop):
    """Validate the complete application shortcut set with one rule set."""
    shot_value, shot_error = validate(hotkey, require_modifier=True)
    start_value, stop_value, errors = validate_pair(start, stop)
    if shot_error:
        errors['hotkey'] = shot_error
    values = {
        'hotkey': shot_value,
        'record_start_key': start_value,
        'record_stop_key': stop_value,
    }
    valid_values = {key: value for key, value in values.items() if not errors.get(key)}
    seen = {}
    for name, value in valid_values.items():
        if value in seen:
            errors[name] = 'conflict_' + seen[value]
        else:
            seen[value] = name
    return values, errors


def display(value):
    canonical = normalize(value)
    labels = {'ctrl': 'Ctrl', 'shift': 'Shift', 'alt': 'Alt', 'cmd': 'Cmd',
              'enter': 'Enter', 'escape': 'Esc', 'space': 'Space',
              'page_up': 'PageUp', 'page_down': 'PageDown'}
    return ' + '.join(labels.get(part, part.upper() if part.startswith('f') else part.upper() if len(part) == 1 else part.title()) for part in canonical.split('+'))


def to_pynput(value, *, require_modifier=True):
    """Convert a canonical shortcut to pynput syntax.

    Screenshot hotkeys require a modifier; recording start/stop keys may also
    be a single key such as Enter or F9.
    """
    canonical, error = validate(value, require_modifier=require_modifier)
    if error:
        raise ValueError(error)
    parts = canonical.split('+')
    return '+'.join(f'<{part}>' if part in MODIFIERS or part in SPECIAL_KEYS or part.startswith('f') else part for part in parts)


def to_tk_event(value):
    canonical, error = validate(value)
    if error:
        raise ValueError(error)
    parts = canonical.split('+')
    key = parts[-1]
    tk_key = {
        'enter': 'Return', 'escape': 'Escape', 'space': 'space',
        'page_up': 'Prior', 'page_down': 'Next',
    }.get(key, key.upper() if key.startswith('f') else key)
    modifier_names = {'ctrl': 'Control', 'shift': 'Shift', 'alt': 'Alt', 'cmd': 'Command'}
    modifiers = '-'.join(modifier_names[part] for part in parts[:-1])
    return f'<{modifiers}-KeyPress-{tk_key}>' if modifiers else f'<KeyPress-{tk_key}>'
