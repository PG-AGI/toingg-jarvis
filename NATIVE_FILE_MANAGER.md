# Native File Manager Actions

The local HTTP server exposes `POST /file_action` for native file manager
integration. It accepts JSON actions that open folders, reveal files, or open
files with the operating system default app.

## Actions

Open a directory:

```json
{ "action": "open_directory", "path": "/Users/me/Projects/Jarvis" }
```

Reveal a file:

```json
{ "action": "reveal_file", "path": "/Users/me/Downloads/report.pdf" }
```

Open a file:

```json
{ "action": "open_file", "path": "/Users/me/Documents/notes.txt" }
```

Supported actions are `open_directory`, `reveal_file`, and `open_file`.
The helper validates paths before launching native tools.

## Dry Run

Use `"dry_run": true` to preview the planned native command without opening
any OS windows:

`dry_run` must be a JSON boolean when supplied; strings such as `"false"`,
numbers, and `null` are rejected with HTTP 400. Omitting it defaults to `false`.
The `action` field must be one of the supported action strings.

```json
{
  "action": "open_file",
  "path": "/Users/me/Documents/notes.txt",
  "dry_run": true
}
```
