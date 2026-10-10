# VUE Modern

A modern, local concept-map editor built with Python and Qt. It is a clean implementation inspired by the purpose of [Visual Understanding Environment (VUE)](https://github.com/VUE/VUE), without its legacy Java interface or a Windows installer.

## Features

- Select and move concepts with **Pointer** (`V`).
- Pan the canvas with **Hand** (`H`) and zoom with the mouse wheel.
- Create curved connections with **Connect** (`L`).
- Label a selected connection with **Label link** (`E`) or double-click its line to write the label.
- Drag a concept into another to make it visual content of the receiving concept; the container expands as children are added. **Indent** (`Tab`) and `Shift+Tab` also indent and outdent the selection.
- Edit concept titles, notes and colours in the inspector.
- Save readable `.vuemodern.json` maps, reopen them and export PNG or nested XML with explicit parent-child relationships.
- Import the concepts, notes, positions, colours and links from classic VUE `.vue` maps.
- Automatically arrange small maps.

## Run locally

Python 3.11+ is required. In PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\start.ps1
```

The project never needs a system-wide Python installation or a Windows installer.

## Classic VUE compatibility

Classic VUE maps are XML files with their own component model. The importer brings across editable nodes and links. It does not yet import resources, presentations, layers, paths or component types specific to the old application. New maps use the open `vuemodern/1` JSON format.

## License

VUE Modern is licensed under the [MIT License](LICENSE). The original VUE source is not distributed in this repository.
