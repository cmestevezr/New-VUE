# VUE Modern

A modern, local concept-map editor built with Python and Qt. It is a clean implementation inspired by the purpose of [Visual Understanding Environment (VUE)](https://github.com/VUE/VUE), without its legacy Java interface or a Windows installer.

The **Studio Paper** interface includes a bundled warm paper canvas, translucent surfaces, consistent native icons, high-contrast input states and the open-source Inter typeface. The included font is licensed under the SIL Open Font License; see [`assets/OFL-Inter.txt`](assets/OFL-Inter.txt).

## Features

- Select and move concepts with **Pointer** (`V`).
- Pan the canvas with **Hand** (`H`) and zoom with the mouse wheel.
- Use visible **Zoom in**, **Zoom out**, **100 %**, **Centre nodes** and **Fit view** controls; the zoom percentage stays visible in the toolbar.
- Create curved connections with **Connect** (`L`).
- Label a selected connection with **Label link** (`E`) or double-click its line to write the label.
- Drag a concept into another to make it visual content of the receiving concept; the container expands as children are added. **Indent** (`Tab`) and `Shift+Tab` also indent and outdent the selection.
- Attach PNG or GIF images to concepts; VUE Modern shows a thumbnail and expands the concept as needed.
- Add a URL to a concept and click its underlined address to open it in your default browser.
- Add up to 256 characters of underlined text and edit it from **Edit text**, the inspector, or right-clicking the displayed text.
- Edit concept titles, notes and colours in the inspector.
- Save readable `.vuemodern.json` maps, reopen them and export PNG or nested XML with explicit parent-child relationships.
- Import the concepts, notes, positions, colours and links from classic VUE `.vue` maps.
- Automatically arrange small maps.

## Install on Windows

The release package is self-contained and installs only for the current Windows user. It does not require administrator permissions or a system-wide Python installation.

1. Extract `VUE-Modern-<version>-windows.zip`.
2. Run `Install-VUE-Modern.cmd`.
3. Open **VUE Modern** from the Start menu.

To build the ZIP package locally, install the build dependency once and run:

```powershell
%USERPROFILE%\VUE-Modern\runtime\Scripts\python.exe -m pip install pyinstaller
.\build-installer.ps1 -Version 0.1.0
```

The ZIP is written to `installer-output/`. Run `Uninstall-VUE-Modern.ps1` from the extracted package to remove the per-user installation.

## Run from source

Python 3.11+ is required. In PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\start.ps1
```

The project never needs a system-wide Python installation.

## Classic VUE compatibility

Classic VUE maps are XML files with their own component model. The importer brings across editable nodes and links. It does not yet import resources, presentations, layers, paths or component types specific to the old application. New maps use the open `vuemodern/1` JSON format.

## License

VUE Modern is licensed under the [MIT License](LICENSE). The original VUE source is not distributed in this repository.
