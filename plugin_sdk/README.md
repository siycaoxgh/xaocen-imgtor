# drawru-imgter Plugin SDK (v1)

Plugins are optional, external capability packages. The core application only
discovers and displays plugin manifests; it does not import or execute plugin
code yet.

Install a plugin folder under the user plugin directory shown in Settings:

```text
%LOCALAPPDATA%\drawru-imgter\plugins\<plugin-id>\plugin.json
```

Minimal manifest:

```json
{
  "id": "android-motion-photo",
  "api_version": 1,
  "name": "Android Motion Photo",
  "version": "0.1.0",
  "platforms": ["windows"],
  "capabilities": ["mp4-record", "motion-photo-export", "motion-photo-crop"]
}
```

## Process protocol

The core can execute an explicitly requested plugin command in a separate
Python process. A manifest must declare a relative Python `entrypoint` and an
allow-list of `commands`:

```json
{
  "entrypoint": "plugin.py",
  "commands": ["inspect", "create"]
}
```

The host sends one JSON object on stdin and expects one JSON object on stdout:

```json
{"protocol": 1, "command": "inspect", "payload": {"input_path": "C:/example.jpg"}}
```

The response must include an `ok` boolean. Plugin code is never auto-started;
the host runs it only after an explicit user action. Plugins must keep FFmpeg
and all large media binaries inside their own folder, never in the core bundle.
