"""CLI for AppImage installer."""

import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

import click

BIN_DIR = Path.home() / ".local" / "bin"
APPS_DIR = Path.home() / ".local" / "share" / "applications"
ICONS_DIR = Path.home() / ".local" / "share" / "icons"

DESKTOP_TEMPLATE = """\
[Desktop Entry]
Type=Application
Name={name}
Exec={exec_path}
Icon={icon_path}
Terminal=false
Categories=Utility;
"""


def get_app_name(appimage_path: Path) -> str:
    """Extract application name from AppImage filename.

    Cuts at the first '-' or '+' followed by a digit, where the version
    string typically begins.
    """
    name = appimage_path.stem
    match = re.search(r"[-+]\d", name)
    if match:
        name = name[: match.start()]
    return name


def make_executable(path: Path) -> None:
    """Add executable bit for user, group, and other."""
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def extract_appimage(appimage_path: Path, extract_dir: Path) -> Path:
    """Extract AppImage contents to a directory."""
    make_executable(appimage_path)
    subprocess.run(
        [str(appimage_path), "--appimage-extract"],
        cwd=extract_dir,
        capture_output=True,
        check=True,
    )
    return extract_dir / "squashfs-root"


def find_icon(extracted_dir: Path) -> Path | None:
    """Find the best icon in extracted AppImage."""
    # Check .DirIcon first (standard location)
    dir_icon = extracted_dir / ".DirIcon"
    if dir_icon.exists():
        return dir_icon

    # Check for PNG icons in standard locations
    icon_dirs = [
        extracted_dir / "usr" / "share" / "icons",
        extracted_dir,
    ]

    for icon_dir in icon_dirs:
        if not icon_dir.exists():
            continue
        # Look for largest PNG icon
        for icon in sorted(icon_dir.rglob("*.png"), reverse=True):
            return icon
        # Fall back to SVG
        for icon in icon_dir.rglob("*.svg"):
            return icon

    return None


def find_desktop_file(extracted_dir: Path) -> Path | None:
    """Find a .desktop file in the extracted AppImage."""
    for desktop in extracted_dir.glob("*.desktop"):
        return desktop
    for desktop in (extracted_dir / "usr" / "share" / "applications").glob("*.desktop"):
        return desktop
    return None


def parse_desktop_file(desktop_path: Path) -> dict:
    """Parse a .desktop file and return key-value pairs."""
    result = {}
    with open(desktop_path) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#") and not line.startswith("["):
                key, _, value = line.partition("=")
                result[key.strip()] = value.strip()
    return result


@click.group()
def main():
    """Install and manage AppImages."""
    pass


@main.command()
@click.argument("appimage", type=click.Path(exists=True, path_type=Path))
@click.option("--name", "-n", help="Override application name")
def install(appimage: Path, name: str | None):
    """Install an AppImage."""
    appimage = appimage.resolve()

    # Ensure directories exist
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    APPS_DIR.mkdir(parents=True, exist_ok=True)
    ICONS_DIR.mkdir(parents=True, exist_ok=True)

    # Determine app name
    app_name = name or get_app_name(appimage)
    app_name_lower = app_name.lower()

    click.echo(f"Installing {app_name}...")

    # Extract AppImage to find icon and desktop file
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        try:
            extracted = extract_appimage(appimage, tmppath)
        except subprocess.CalledProcessError as e:
            click.echo(f"Failed to extract AppImage: {e}", err=True)
            raise SystemExit(1)

        # Try to get name from desktop file
        desktop_file = find_desktop_file(extracted)
        if desktop_file and not name:
            desktop_data = parse_desktop_file(desktop_file)
            if "Name" in desktop_data:
                app_name = desktop_data["Name"]

        # Find and copy icon
        icon_src = find_icon(extracted)
        icon_dest = None
        if icon_src:
            suffix = icon_src.suffix or ".png"
            icon_dest = ICONS_DIR / f"{app_name_lower}{suffix}"
            shutil.copy2(icon_src, icon_dest)
            click.echo(f"  Icon: {icon_dest}")

    # Copy AppImage to bin directory
    dest_appimage = BIN_DIR / f"{app_name_lower}.appimage"
    shutil.copy2(appimage, dest_appimage)
    make_executable(dest_appimage)
    click.echo(f"  AppImage: {dest_appimage}")

    # Create symlink
    symlink = BIN_DIR / app_name_lower
    if symlink.exists() or symlink.is_symlink():
        symlink.unlink()
    symlink.symlink_to(dest_appimage.name)
    click.echo(f"  Symlink: {symlink}")

    # Create desktop file
    desktop_dest = APPS_DIR / f"{app_name_lower}.desktop"
    desktop_content = DESKTOP_TEMPLATE.format(
        name=app_name,
        exec_path=dest_appimage,
        icon_path=icon_dest or "",
    )
    desktop_dest.write_text(desktop_content)
    click.echo(f"  Desktop file: {desktop_dest}")

    click.echo(f"Successfully installed {app_name}")


@main.command()
@click.argument("name")
def uninstall(name: str):
    """Uninstall an AppImage by name."""
    name_lower = name.lower()

    removed = []

    # Remove AppImage
    appimage = BIN_DIR / f"{name_lower}.appimage"
    if appimage.exists():
        appimage.unlink()
        removed.append(f"AppImage: {appimage}")

    # Remove symlink
    symlink = BIN_DIR / name_lower
    if symlink.is_symlink():
        symlink.unlink()
        removed.append(f"Symlink: {symlink}")

    # Remove desktop file
    desktop = APPS_DIR / f"{name_lower}.desktop"
    if desktop.exists():
        desktop.unlink()
        removed.append(f"Desktop file: {desktop}")

    # Remove icon (try common extensions)
    for ext in [".png", ".svg", ".xpm"]:
        icon = ICONS_DIR / f"{name_lower}{ext}"
        if icon.exists():
            icon.unlink()
            removed.append(f"Icon: {icon}")

    if removed:
        click.echo(f"Uninstalled {name}:")
        for item in removed:
            click.echo(f"  {item}")
    else:
        click.echo(f"No installation found for '{name}'", err=True)
        raise SystemExit(1)


@main.command(name="list")
def list_installed():
    """List installed AppImages."""
    if not BIN_DIR.exists():
        click.echo("No AppImages installed.")
        return

    appimages = list(BIN_DIR.glob("*.appimage"))
    if not appimages:
        click.echo("No AppImages installed.")
        return

    click.echo("Installed AppImages:")
    for appimage in sorted(appimages):
        name = appimage.stem
        click.echo(f"  {name}")


if __name__ == "__main__":
    main()
