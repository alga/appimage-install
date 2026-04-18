# appimage-install

Install and manage AppImages on Linux.

## Installation

```
make dev
```

## Usage

```
appimage-install install MyApp-1.0-x86_64.AppImage
appimage-install list
appimage-install uninstall myapp
```

## What it does

When installing an AppImage:

- Extracts the icon and places it in `~/.local/share/icons/`
- Creates a `.desktop` file in `~/.local/share/applications/`
- Copies the AppImage to `~/.local/bin/`
- Creates a short symlink (e.g., `myapp` → `myapp.appimage`)

Installing a new version of the same app overwrites the previous installation.
