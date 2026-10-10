"""VUE Modern: a local, modern concept-map editor built with Qt for Python."""

from __future__ import annotations

import json
import sys
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QBrush,
    QColor,
    QFont,
    QFontDatabase,
    QImage,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QDesktopServices,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsPathItem,
    QGraphicsDropShadowEffect,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStyle,
    QToolBar,
    QVBoxLayout,
    QWidget,
)


APP_NAME = "VUE Modern"
DEFAULT_NODE_COLOUR = "#E8F0FE"
PALETTE = ("#DCE8F8", "#E1EFE2", "#F9E2D7", "#E8E1F5", "#F5E9C8", "#E7ECEF")
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
PAPER_TEXTURE = ASSETS_DIR / "studio-paper-canvas.png"
APP_FONT = "Inter"


@dataclass
class NodeData:
    id: str
    label: str
    x: float
    y: float
    colour: str = DEFAULT_NODE_COLOUR
    notes: str = ""
    parent_id: str | None = None
    image_path: str = ""
    url: str = ""
    text: str = ""


@dataclass
class LinkData:
    id: str
    source: str
    target: str
    label: str = ""


class MapLink(QGraphicsPathItem):
    """A curved visual connection which follows two MapNode instances."""

    def __init__(self, source: "MapNode", target: "MapNode", label: str = "") -> None:
        super().__init__()
        self.id = uuid.uuid4().hex
        self.source = source
        self.target = target
        self.label = label
        self.setZValue(-1)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setToolTip("Doble clic para escribir una etiqueta")
        self.refresh_path()

    def refresh_path(self) -> None:
        start = self.source.sceneBoundingRect().center()
        end = self.target.sceneBoundingRect().center()
        distance = end.x() - start.x()
        path = QPainterPath(start)
        path.cubicTo(
            QPointF(start.x() + distance * 0.45, start.y()),
            QPointF(end.x() - distance * 0.45, end.y()),
            end,
        )
        self.setPath(path)
        self.setPen(QPen(QColor("#81756A"), 2.0, Qt.PenStyle.SolidLine))

    def shape(self) -> QPainterPath:  # type: ignore[override]
        """Give the narrow painted line a comfortable target for mouse input."""
        stroker = QPainterPathStroker()
        stroker.setWidth(18.0)
        return stroker.createStroke(self.path())

    def paint(self, painter: QPainter, option, widget=None) -> None:  # type: ignore[override]
        pen = QPen(QColor("#356BCE") if self.isSelected() else QColor("#81756A"), 3.0 if self.isSelected() else 2.0)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self.path())
        if self.label.strip():
            center = self.path().pointAtPercent(0.5)
            font = QFont("Segoe UI", 9)
            font.setWeight(QFont.Weight.DemiBold)
            painter.setFont(font)
            text_rect = QRectF(painter.fontMetrics().boundingRect(self.label)).adjusted(-8, -4, 8, 4)
            text_rect.moveCenter(center)
            painter.fillRect(text_rect, QColor("#FFFCF7"))
            painter.setPen(QColor("#4F453C"))
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self.label)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        label, accepted = QInputDialog.getText(None, "Etiquetar enlace", "Etiqueta del enlace:", text=self.label)
        if accepted:
            self.label = label.strip()
            self.update()
            if isinstance(self.scene(), MapScene):
                self.scene().changed.emit()
        event.accept()


class MapNode(QGraphicsObject):
    """An editable, movable map concept."""

    changed = Signal()
    WIDTH = 190.0
    HEIGHT = 86.0
    HEADER_HEIGHT = 42.0
    CONTENT_PADDING = 18.0
    CONTENT_GAP = 12.0
    THUMBNAIL_MAX_WIDTH = 150
    THUMBNAIL_MAX_HEIGHT = 96
    TEXT_HEIGHT = 48.0

    def __init__(self, data: NodeData) -> None:
        super().__init__()
        self.data = data
        self.links: list[MapLink] = []
        self._drag_origin: QPointF | None = None
        self._width = self.WIDTH
        self._height = self.HEIGHT
        self._contains_children = False
        self._thumbnail_path = ""
        self._thumbnail = QPixmap()
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(74, 60, 46, 40))
        self.setGraphicsEffect(shadow)
        self.setPos(data.x, data.y)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setToolTip("Doble clic para editar")

    def boundingRect(self) -> QRectF:  # type: ignore[override]
        return QRectF(0, 0, self._width, self._height)

    @property
    def node_width(self) -> float:
        return self._width

    @property
    def node_height(self) -> float:
        return self._height

    def set_container_size(self, width: float, height: float, contains_children: bool) -> None:
        width, height = max(self.WIDTH, width), max(self.HEIGHT, height)
        if (self._width, self._height, self._contains_children) == (width, height, contains_children):
            return
        self.prepareGeometryChange()
        self._width = width
        self._height = height
        self._contains_children = contains_children
        self.update()

    def thumbnail(self) -> QPixmap:
        """Return a small, static preview for either a PNG or the first GIF frame."""
        if self.data.image_path != self._thumbnail_path:
            self._thumbnail_path = self.data.image_path
            image = QPixmap(self.data.image_path) if self.data.image_path else QPixmap()
            self._thumbnail = image.scaled(
                self.THUMBNAIL_MAX_WIDTH,
                self.THUMBNAIL_MAX_HEIGHT,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ) if not image.isNull() else QPixmap()
        return self._thumbnail

    def detail_height(self) -> float:
        parts: list[float] = []
        preview = self.thumbnail()
        if not preview.isNull():
            parts.append(float(preview.height()))
        elif self.data.image_path:
            parts.append(22.0)
        if self.data.url.strip():
            parts.append(20.0)
        if self.data.text.strip():
            parts.append(self.TEXT_HEIGHT)
        return sum(parts) + self.CONTENT_GAP * max(0, len(parts) - 1)

    def intrinsic_width(self) -> float:
        preview = self.thumbnail()
        image_width = float(preview.width()) if not preview.isNull() else (150.0 if self.data.image_path else 0.0)
        return max(self.WIDTH, image_width + self.CONTENT_PADDING * 2)

    def has_details(self) -> bool:
        return bool(self.data.image_path or self.data.url.strip() or self.data.text.strip())

    def detail_layout(self) -> tuple[QRectF | None, QRectF | None, QRectF | None]:
        """Return local rectangles for the image, URL and short text."""
        if not (self._contains_children or self.has_details()):
            return None, None, None
        y = self.HEADER_HEIGHT + self.CONTENT_PADDING
        image_rect: QRectF | None = None
        url_rect: QRectF | None = None
        text_rect: QRectF | None = None
        preview = self.thumbnail()
        if not preview.isNull():
            image_rect = QRectF((self._width - preview.width()) / 2, y, preview.width(), preview.height())
            y += preview.height() + self.CONTENT_GAP
        elif self.data.image_path:
            image_rect = QRectF(self.CONTENT_PADDING, y, self._width - self.CONTENT_PADDING * 2, 22)
            y += 22 + self.CONTENT_GAP
        if self.data.url.strip():
            url_rect = QRectF(self.CONTENT_PADDING, y, self._width - self.CONTENT_PADDING * 2, 20)
            y += 20 + self.CONTENT_GAP
        if self.data.text.strip():
            text_rect = QRectF(self.CONTENT_PADDING, y, self._width - self.CONTENT_PADDING * 2, self.TEXT_HEIGHT)
        return image_rect, url_rect, text_rect

    def paint(self, painter: QPainter, option, widget=None) -> None:  # type: ignore[override]
        rect = self.boundingRect()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        fill = QColor(self.data.colour)
        fill.setAlpha(238)
        border = QColor("#356BCE") if self.isSelected() else QColor("#B9AB9A")
        painter.setPen(QPen(border, 3.0 if self.isSelected() else 1.25))
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, 18, 18)

        painter.setPen(QColor("#2F2B27"))
        font = QFont(APP_FONT, 10)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        if self._contains_children or self.has_details():
            title_rect = QRectF(rect.left() + 14, rect.top() + 6, rect.width() - 28, self.HEADER_HEIGHT - 10)
            painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.data.label)
            painter.setPen(QPen(QColor("#CFC2B3"), 1.0))
            painter.drawLine(rect.left() + 12, self.HEADER_HEIGHT, rect.right() - 12, self.HEADER_HEIGHT)
        else:
            painter.drawText(rect.adjusted(14, 12, -14, -12), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.data.label)

        image_rect, url_rect, text_rect = self.detail_layout()
        if image_rect:
            preview = self.thumbnail()
            if preview.isNull():
                painter.setPen(QColor("#B45309"))
                painter.drawText(image_rect, Qt.AlignmentFlag.AlignCenter, "Imagen no disponible")
            else:
                painter.drawPixmap(image_rect.toRect(), preview)
        if url_rect:
            url_font = QFont(APP_FONT, 8)
            url_font.setUnderline(True)
            painter.setFont(url_font)
            painter.setPen(QColor("#315DAA"))
            painter.drawText(url_rect, Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextSingleLine, self.data.url)
        if text_rect:
            text_font = QFont(APP_FONT, 8)
            text_font.setUnderline(True)
            painter.setFont(text_font)
            painter.setPen(QColor("#4F453C"))
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, self.data.text)

    def itemChange(self, change, value):  # type: ignore[override]
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.data.x = self.pos().x()
            self.data.y = self.pos().y()
            for link in self.links:
                link.refresh_path()
            self.changed.emit()
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        label, accepted = QInputDialog.getText(None, "Editar concepto", "Texto del concepto:", text=self.data.label)
        if accepted and label.strip():
            self.data.label = label.strip()
            self.update()
            self.changed.emit()
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = QPointF(self.pos())
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        super().mouseReleaseEvent(event)
        origin, self._drag_origin = self._drag_origin, None
        if origin is None:
            return
        if (self.pos() - origin).manhattanLength() < 8:
            _, url_rect, _ = self.detail_layout()
            if event.button() == Qt.MouseButton.LeftButton and url_rect and url_rect.contains(event.pos()) and self.data.url.strip():
                QDesktopServices.openUrl(QUrl.fromUserInput(self.data.url.strip()))
                event.accept()
            return
        scene = self.scene()
        if not isinstance(scene, MapScene):
            return
        center = self.sceneBoundingRect().center()
        parent = next(
            (
                item
                for item in scene.items(center)
                if isinstance(item, MapNode) and item is not self and item.sceneBoundingRect().contains(center)
            ),
            None,
        )
        if parent and scene.indent_node(self, parent):
            self.setSelected(True)
        elif scene.move_descendants(self, self.pos() - origin):
            self.setSelected(True)

    def contextMenuEvent(self, event) -> None:  # type: ignore[override]
        _, _, text_rect = self.detail_layout()
        if text_rect and text_rect.contains(event.pos()):
            text, accepted = QInputDialog.getText(
                None,
                "Editar texto del concepto",
                "Texto breve (máx. 256 caracteres):",
                text=self.data.text,
            )
            if accepted:
                self.data.text = text.strip()[:256]
                scene = self.scene()
                if isinstance(scene, MapScene):
                    scene.reflow_hierarchy()
                    scene.changed.emit()
                self.update()
            event.accept()
            return
        super().contextMenuEvent(event)


class MapScene(QGraphicsScene):
    changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSceneRect(-2400, -1800, 4800, 3600)

    def add_node(self, label: str, position: QPointF, colour: str = DEFAULT_NODE_COLOUR, notes: str = "") -> MapNode:
        node = MapNode(NodeData(uuid.uuid4().hex, label, position.x(), position.y(), colour, notes))
        node.changed.connect(self.changed)
        self.addItem(node)
        self.changed.emit()
        return node

    def add_link(self, source: MapNode, target: MapNode, label: str = "") -> MapLink | None:
        if source is target or any(link.target is target or link.source is target for link in source.links):
            return None
        link = MapLink(source, target, label)
        source.links.append(link)
        target.links.append(link)
        self.addItem(link)
        self.changed.emit()
        return link

    def indent_node(self, node: MapNode, parent: MapNode) -> bool:
        """Place ``node`` inside ``parent`` and preserve the hierarchy in the model."""
        if node is parent or self._would_create_cycle(node, parent):
            return False
        node.data.parent_id = parent.data.id
        if not any(link.source is parent and link.target is node for link in parent.links):
            self.add_link(parent, node)
        self.reflow_hierarchy()
        self.changed.emit()
        return True

    def outdent_node(self, node: MapNode) -> bool:
        """Remove a node from its visual container while retaining its map position."""
        if not node.data.parent_id:
            return False
        parent = next(
            (item for item in self.items() if isinstance(item, MapNode) and item.data.id == node.data.parent_id),
            None,
        )
        node.data.parent_id = None
        if parent:
            node.setPos(parent.pos() + QPointF(parent.node_width + 60, MapNode.HEADER_HEIGHT))
        self.reflow_hierarchy()
        self.changed.emit()
        return True

    def move_descendants(self, node: MapNode, delta: QPointF) -> bool:
        """Keep visible contents together when a container itself is moved."""
        if delta.manhattanLength() < 1:
            return False
        if not self._children_by_parent().get(node.data.id, []):
            return False

        def move_branch(parent: MapNode) -> None:
            for child in self._children_by_parent().get(parent.data.id, []):
                child.moveBy(delta.x(), delta.y())
                move_branch(child)

        move_branch(node)
        self.changed.emit()
        return True

    def reflow_hierarchy(self) -> None:
        """Size containers from their contents and lay every child out inside its parent."""
        children_by_parent = self._children_by_parent()

        def measure(node: MapNode) -> tuple[float, float]:
            children = children_by_parent.get(node.data.id, [])
            child_sizes = [measure(child) for child in children]
            detail_height = node.detail_height()
            if not children:
                node.set_container_size(
                    node.intrinsic_width(),
                    max(MapNode.HEIGHT, MapNode.HEADER_HEIGHT + detail_height + MapNode.CONTENT_PADDING * 2),
                    False,
                )
                return node.node_width, node.node_height
            content_width = max(width for width, _ in child_sizes)
            content_height = sum(height for _, height in child_sizes) + MapNode.CONTENT_GAP * (len(children) - 1)
            node.set_container_size(
                max(node.intrinsic_width(), content_width + MapNode.CONTENT_PADDING * 2),
                MapNode.HEADER_HEIGHT + detail_height + content_height + MapNode.CONTENT_PADDING * 2
                + (MapNode.CONTENT_GAP if detail_height else 0),
                True,
            )
            return node.node_width, node.node_height

        all_nodes = [item for item in self.items() if isinstance(item, MapNode)]
        roots = [node for node in all_nodes if not node.data.parent_id or node.data.parent_id not in children_by_parent]
        for root in roots:
            measure(root)

        def place_children(parent: MapNode, depth: int) -> None:
            parent.setZValue(depth)
            children = children_by_parent.get(parent.data.id, [])
            current_y = parent.pos().y() + MapNode.HEADER_HEIGHT + MapNode.CONTENT_PADDING + parent.detail_height()
            if children and parent.detail_height():
                current_y += MapNode.CONTENT_GAP
            for child in children:
                child.setPos(parent.pos().x() + (parent.node_width - child.node_width) / 2, current_y)
                current_y += child.node_height + MapNode.CONTENT_GAP
                place_children(child, depth + 1)

        for root in roots:
            place_children(root, 0)
        for link in (item for item in self.items() if isinstance(item, MapLink)):
            link.refresh_path()

    def _children_by_parent(self) -> dict[str, list[MapNode]]:
        nodes = [item for item in self.items() if isinstance(item, MapNode)]
        ids = {node.data.id for node in nodes}
        children: dict[str, list[MapNode]] = {}
        for node in nodes:
            if node.data.parent_id in ids:
                children.setdefault(node.data.parent_id, []).append(node)
        for siblings in children.values():
            siblings.sort(key=lambda item: (item.pos().y(), item.pos().x(), item.data.id))
        return children

    def _would_create_cycle(self, node: MapNode, parent: MapNode) -> bool:
        lookup = {item.data.id: item for item in self.items() if isinstance(item, MapNode)}
        ancestor: MapNode | None = parent
        while ancestor:
            if ancestor is node:
                return True
            ancestor = lookup.get(ancestor.data.parent_id or "")
        return False

    def remove_node(self, node: MapNode) -> None:
        for link in list(node.links):
            self.remove_link(link)
        self.removeItem(node)
        self.changed.emit()

    def remove_link(self, link: MapLink) -> None:
        if link in link.source.links:
            link.source.links.remove(link)
        if link in link.target.links:
            link.target.links.remove(link)
        self.removeItem(link)
        self.changed.emit()

    def clear_map(self) -> None:
        self.clear()
        self.changed.emit()

    def to_document(self) -> dict:
        nodes = [item for item in self.items() if isinstance(item, MapNode)]
        links = [item for item in self.items() if isinstance(item, MapLink)]
        return {
            "format": "vue-modern/1",
            "nodes": [
                {
                    "id": node.data.id,
                    "label": node.data.label,
                    "x": node.pos().x(),
                    "y": node.pos().y(),
                    "colour": node.data.colour,
                    "notes": node.data.notes,
                    "parent_id": node.data.parent_id,
                    "image_path": node.data.image_path,
                    "url": node.data.url,
                    "text": node.data.text,
                }
                for node in nodes
            ],
            "links": [
                {"id": link.id, "source": link.source.data.id, "target": link.target.data.id, "label": link.label}
                for link in links
            ],
        }

    def load_document(self, document: dict) -> None:
        if document.get("format") != "vue-modern/1":
            raise ValueError("El archivo no tiene el formato VUE Modern.")
        self.clear()
        lookup: dict[str, MapNode] = {}
        for raw in document.get("nodes", []):
            data = NodeData(
                str(raw["id"]),
                str(raw.get("label", "Sin título")),
                float(raw.get("x", 0)),
                float(raw.get("y", 0)),
                str(raw.get("colour", DEFAULT_NODE_COLOUR)),
                str(raw.get("notes", "")),
                raw.get("parent_id"),
                str(raw.get("image_path", "")),
                str(raw.get("url", "")),
                str(raw.get("text", ""))[:256],
            )
            node = MapNode(data)
            node.changed.connect(self.changed)
            self.addItem(node)
            lookup[data.id] = node
        for raw in document.get("links", []):
            source, target = lookup.get(str(raw.get("source"))), lookup.get(str(raw.get("target")))
            if source and target:
                link = self.add_link(source, target, str(raw.get("label", "")))
                if link:
                    link.id = str(raw.get("id", link.id))
        self.reflow_hierarchy()
        self.changed.emit()

    def export_xml(self, path: Path) -> None:
        """Write an interoperable, indented XML representation of the map."""
        document = self.to_document()
        root = ET.Element("vue-modern", {"version": "1"})
        nodes_element = ET.SubElement(root, "nodes")
        nodes_by_id = {node["id"]: node for node in document["nodes"]}
        children_by_parent: dict[str, list[dict]] = {}
        for node in document["nodes"]:
            if node.get("parent_id") in nodes_by_id:
                children_by_parent.setdefault(str(node["parent_id"]), []).append(node)

        def write_node(node: dict, parent_element: ET.Element) -> None:
            attributes = {
                "id": node["id"],
                "label": node["label"],
                "x": str(node["x"]),
                "y": str(node["y"]),
                "colour": node["colour"],
            }
            if node.get("parent_id"):
                attributes["parent_id"] = str(node["parent_id"])
            element = ET.SubElement(parent_element, "node", attributes)
            ET.SubElement(element, "notes").text = node["notes"]
            if node.get("image_path"):
                ET.SubElement(element, "image", {"path": str(node["image_path"])})
            if node.get("url"):
                ET.SubElement(element, "url").text = str(node["url"])
            if node.get("text"):
                ET.SubElement(element, "text").text = str(node["text"])
            descendants = children_by_parent.get(node["id"], [])
            if descendants:
                children_element = ET.SubElement(element, "children")
                for child in descendants:
                    write_node(child, children_element)

        for node in document["nodes"]:
            if node.get("parent_id") not in nodes_by_id:
                write_node(node, nodes_element)
        links_element = ET.SubElement(root, "links")
        for link in document["links"]:
            ET.SubElement(
                links_element,
                "link",
                {"id": link["id"], "source": link["source"], "target": link["target"], "label": link["label"]},
            )
        ET.indent(root, space="  ")
        ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)

    def load_legacy_vue(self, path: Path) -> tuple[int, int]:
        """Import the core node/link structure of a classic VUE ``.vue`` map.

        VUE maps also contain resources, presentation paths, metadata and several
        old UI-specific component types. This importer intentionally preserves the
        editable concepts and their connections, while leaving those legacy-only
        features out of the new, smaller document model.
        """
        try:
            # Some VUE 3.x maps put preservation comments before their XML
            # declaration. XML parsers correctly reject that shape, though VUE
            # itself tolerated it, so start at the declaration when present.
            source = path.read_text(encoding="utf-8", errors="replace")
            declaration = source.find("<?xml")
            root = ET.fromstring(source[declaration:] if declaration >= 0 else source)
        except ET.ParseError as error:
            raise ValueError(f"El archivo .vue no es XML válido: {error}") from error
        if root.tag.rsplit("}", 1)[-1] != "LW-MAP":
            raise ValueError("El archivo no parece ser un mapa VUE clásico.")

        def type_of(element: ET.Element) -> str:
            return next((value for key, value in element.attrib.items() if key.rsplit("}", 1)[-1] == "type"), "")

        def child_text(element: ET.Element, name: str) -> str:
            return next((child.text or "" for child in element if child.tag.rsplit("}", 1)[-1] == name), "")

        self.clear()
        lookup: dict[str, MapNode] = {}
        raw_links: list[ET.Element] = []
        for child in root:
            if child.tag.rsplit("}", 1)[-1] != "child":
                continue
            component_type = type_of(child)
            if component_type == "link":
                raw_links.append(child)
                continue
            if component_type != "node":
                continue
            node_id = child.get("ID", uuid.uuid4().hex)
            node = MapNode(
                NodeData(
                    node_id,
                    child.get("label", "Sin título").replace("\\n", " "),
                    float(child.get("x", "0")),
                    float(child.get("y", "0")),
                    child_text(child, "fillColor") or DEFAULT_NODE_COLOUR,
                    child_text(child, "notes").strip(),
                )
            )
            node.changed.connect(self.changed)
            self.addItem(node)
            lookup[node_id] = node

        imported_links = 0
        for legacy_link in raw_links:
            source_id, target_id = child_text(legacy_link, "ID1"), child_text(legacy_link, "ID2")
            source, target = lookup.get(source_id), lookup.get(target_id)
            if source and target and self.add_link(source, target, legacy_link.get("label", "")):
                imported_links += 1
        self.changed.emit()
        return len(lookup), imported_links


class MapCanvas(QGraphicsView):
    node_selected = Signal(object)
    link_ready = Signal(object, object)
    zoom_changed = Signal(int)
    MIN_ZOOM = 0.2
    MAX_ZOOM = 3.0

    def __init__(self, scene: MapScene, parent=None) -> None:
        super().__init__(scene, parent)
        self.connect_mode = False
        self._source: MapNode | None = None
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        texture = QPixmap(str(PAPER_TEXTURE))
        self.setBackgroundBrush(QBrush(texture) if not texture.isNull() else QBrush(QColor("#F7F2E9")))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if self.connect_mode and event.button() == Qt.MouseButton.LeftButton:
            clicked = self.itemAt(event.position().toPoint())
            while clicked and not isinstance(clicked, MapNode):
                clicked = clicked.parentItem()
            if isinstance(clicked, MapNode):
                if self._source is None:
                    self._source = clicked
                    clicked.setSelected(True)
                elif clicked is not self._source:
                    self.link_ready.emit(self._source, clicked)
                    self._source = None
                return
        super().mousePressEvent(event)

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.zoom_by(factor)

    def zoom_by(self, factor: float) -> None:
        current = self.transform().m11()
        target = min(self.MAX_ZOOM, max(self.MIN_ZOOM, current * factor))
        if abs(target - current) < 0.0001:
            return
        self.scale(target / current, target / current)
        self.zoom_changed.emit(round(target * 100))

    def reset_zoom(self) -> None:
        self.resetTransform()
        self.zoom_changed.emit(100)

    def report_zoom(self) -> None:
        self.zoom_changed.emit(round(self.transform().m11() * 100))


class Inspector(QWidget):
    """A small, live editing pane for the selected concept."""

    changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.node: MapNode | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        title = QLabel("Inspector")
        title.setObjectName("panelTitle")
        layout.addWidget(title)
        self.hint = QLabel("Selecciona un concepto para editarlo.")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

        form = QFormLayout()
        self.title_edit = QLineEdit()
        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setPlaceholderText("Notas privadas del concepto…")
        self.notes_edit.setFixedHeight(130)
        self.image_path_edit = QLineEdit()
        self.image_path_edit.setReadOnly(True)
        self.image_path_edit.setPlaceholderText("Sin imagen adjunta")
        self.attach_image_button = QPushButton("Adjuntar…")
        self.remove_image_button = QPushButton("Quitar")
        image_row = QWidget()
        image_layout = QHBoxLayout(image_row)
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.addWidget(self.image_path_edit, 1)
        image_layout.addWidget(self.attach_image_button)
        image_layout.addWidget(self.remove_image_button)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://…")
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("Texto breve, máximo 256 caracteres…")
        self.text_edit.setFixedHeight(70)
        self.colour_button = QPushButton("Color")
        self.apply_button = QPushButton("Aplicar cambios")
        self.apply_button.setObjectName("primaryButton")
        form.addRow("Título", self.title_edit)
        form.addRow("Notas", self.notes_edit)
        form.addRow("Imagen", image_row)
        form.addRow("URL", self.url_edit)
        form.addRow("Texto", self.text_edit)
        form.addRow("Estilo", self.colour_button)
        layout.addLayout(form)
        layout.addWidget(self.apply_button)
        layout.addStretch(1)
        self.apply_button.clicked.connect(self.apply)
        self.colour_button.clicked.connect(self.choose_colour)
        self.attach_image_button.clicked.connect(self.attach_image)
        self.remove_image_button.clicked.connect(self.remove_image)
        self.set_enabled(False)

    def set_enabled(self, enabled: bool) -> None:
        self.title_edit.setEnabled(enabled)
        self.notes_edit.setEnabled(enabled)
        self.image_path_edit.setEnabled(enabled)
        self.attach_image_button.setEnabled(enabled)
        self.remove_image_button.setEnabled(enabled)
        self.url_edit.setEnabled(enabled)
        self.text_edit.setEnabled(enabled)
        self.colour_button.setEnabled(enabled)
        self.apply_button.setEnabled(enabled)

    def inspect(self, node: MapNode | None) -> None:
        self.node = node
        self.set_enabled(node is not None)
        if not node:
            self.hint.setText("Selecciona un concepto para editarlo.")
            self.title_edit.clear()
            self.notes_edit.clear()
            self.image_path_edit.clear()
            self.url_edit.clear()
            self.text_edit.clear()
            return
        self.hint.setText("Los cambios se guardan con el mapa.")
        self.title_edit.setText(node.data.label)
        self.notes_edit.setPlainText(node.data.notes)
        self.image_path_edit.setText(node.data.image_path)
        self.url_edit.setText(node.data.url)
        self.text_edit.setPlainText(node.data.text)
        self.colour_button.setStyleSheet(f"background: {node.data.colour};")

    def apply(self) -> None:
        if not self.node:
            return
        label = self.title_edit.text().strip()
        if label:
            self.node.data.label = label
        self.node.data.notes = self.notes_edit.toPlainText().strip()
        self.node.data.url = self.url_edit.text().strip()
        self.node.data.text = self.text_edit.toPlainText().strip()[:256]
        self.node.update()
        scene = self.node.scene()
        if isinstance(scene, MapScene):
            scene.reflow_hierarchy()
        self.node.changed.emit()
        self.changed.emit()

    def attach_image(self) -> None:
        if not self.node:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Adjuntar imagen", "", "Imágenes (*.png *.gif)")
        if not path:
            return
        self.node.data.image_path = path
        self.image_path_edit.setText(path)
        self.node._thumbnail_path = ""
        scene = self.node.scene()
        if isinstance(scene, MapScene):
            scene.reflow_hierarchy()
        self.node.update()
        self.node.changed.emit()
        self.changed.emit()

    def remove_image(self) -> None:
        if not self.node or not self.node.data.image_path:
            return
        self.node.data.image_path = ""
        self.node._thumbnail_path = ""
        self.image_path_edit.clear()
        scene = self.node.scene()
        if isinstance(scene, MapScene):
            scene.reflow_hierarchy()
        self.node.update()
        self.node.changed.emit()
        self.changed.emit()

    def choose_colour(self) -> None:
        if not self.node:
            return
        colour = QColorDialog.getColor(QColor(self.node.data.colour), self, "Color del concepto")
        if colour.isValid():
            self.node.data.colour = colour.name()
            self.colour_button.setStyleSheet(f"background: {colour.name()};")
            self.node.update()
            self.node.changed.emit()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1360, 860)
        self.file_path: Path | None = None
        self.dirty = False
        self.scene = MapScene(self)
        self.canvas = MapCanvas(self.scene)
        self.inspector = Inspector()
        self.scene.selectionChanged.connect(self.selection_changed)
        self.scene.changed.connect(self.mark_dirty)
        self.canvas.link_ready.connect(self.create_link)
        self.canvas.zoom_changed.connect(self.update_zoom_label)
        self.inspector.changed.connect(self.mark_dirty)
        self.setCentralWidget(self.make_workspace())
        self.make_actions()
        self.make_toolbar()
        self.statusBar().showMessage("Listo. Crea ideas y conéctalas.")
        self.new_map(seed=True)
        QTimer.singleShot(0, self.zoom_fit)

    def make_workspace(self) -> QWidget:
        splitter = QSplitter()
        splitter.addWidget(self.canvas)
        panel = QFrame()
        panel.setObjectName("inspectorPanel")
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        panel.setMinimumWidth(270)
        panel.setMaximumWidth(350)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.addWidget(self.inspector)
        splitter.addWidget(panel)
        splitter.setStretchFactor(0, 1)
        splitter.setSizes([1060, 300])
        return splitter

    def make_actions(self) -> None:
        self.new_action = QAction("Nuevo", self, shortcut=QKeySequence.StandardKey.New, triggered=self.new_map)
        self.open_action = QAction("Abrir", self, shortcut=QKeySequence.StandardKey.Open, triggered=self.open_map)
        self.save_action = QAction("Guardar", self, shortcut=QKeySequence.StandardKey.Save, triggered=self.save_map)
        self.save_as_action = QAction("Guardar como…", self, shortcut=QKeySequence.StandardKey.SaveAs, triggered=lambda: self.save_map(save_as=True))
        self.export_action = QAction("Exportar PNG", self, triggered=self.export_png)
        self.export_xml_action = QAction("Exportar XML", self, triggered=self.export_xml)
        self.add_node_action = QAction("Nuevo concepto", self, shortcut="N", triggered=self.add_node)
        self.select_action = QAction("Puntero", self, checkable=True, shortcut="V")
        self.pan_action = QAction("Mano", self, checkable=True, shortcut="H")
        self.connect_action = QAction("Conectar", self, checkable=True, shortcut="L")
        self.delete_action = QAction("Eliminar", self, shortcut=QKeySequence.StandardKey.Delete, triggered=self.delete_selection)
        self.indent_action = QAction("Indentar…", self, shortcut="Tab", triggered=self.indent_selected_node)
        self.outdent_action = QAction("Desindentar", self, shortcut="Shift+Tab", triggered=self.outdent_selected_node)
        self.label_link_action = QAction("Etiquetar enlace…", self, shortcut="E", triggered=self.label_selected_link)
        self.edit_text_action = QAction("Editar texto del concepto…", self, triggered=self.edit_selected_node_text)
        self.layout_action = QAction("Ordenar", self, triggered=self.auto_layout)
        self.zoom_in_action = QAction("Acercar", self, shortcut="Ctrl++", triggered=lambda: self.canvas.zoom_by(1.2))
        self.zoom_out_action = QAction("Alejar", self, shortcut="Ctrl+-", triggered=lambda: self.canvas.zoom_by(1 / 1.2))
        self.zoom_reset_action = QAction("100 %", self, shortcut="Ctrl+0", triggered=self.canvas.reset_zoom)
        self.center_action = QAction("Centrar nodos", self, shortcut="C", triggered=self.center_nodes)
        self.zoom_fit_action = QAction("Ajustar vista", self, shortcut="F", triggered=self.zoom_fit)

        def icon(action: QAction, glyph: QStyle.StandardPixmap) -> None:
            action.setIcon(self.style().standardIcon(glyph))

        icon(self.new_action, QStyle.StandardPixmap.SP_FileIcon)
        icon(self.open_action, QStyle.StandardPixmap.SP_DirOpenIcon)
        icon(self.save_action, QStyle.StandardPixmap.SP_DialogSaveButton)
        icon(self.export_action, QStyle.StandardPixmap.SP_FileIcon)
        icon(self.export_xml_action, QStyle.StandardPixmap.SP_FileIcon)
        icon(self.add_node_action, QStyle.StandardPixmap.SP_FileDialogNewFolder)
        icon(self.select_action, QStyle.StandardPixmap.SP_ArrowForward)
        icon(self.pan_action, QStyle.StandardPixmap.SP_BrowserReload)
        icon(self.connect_action, QStyle.StandardPixmap.SP_CommandLink)
        icon(self.delete_action, QStyle.StandardPixmap.SP_TrashIcon)
        icon(self.indent_action, QStyle.StandardPixmap.SP_ArrowRight)
        icon(self.outdent_action, QStyle.StandardPixmap.SP_ArrowLeft)
        icon(self.label_link_action, QStyle.StandardPixmap.SP_MessageBoxInformation)
        icon(self.edit_text_action, QStyle.StandardPixmap.SP_FileDialogDetailedView)
        icon(self.layout_action, QStyle.StandardPixmap.SP_DesktopIcon)
        icon(self.zoom_in_action, QStyle.StandardPixmap.SP_ArrowUp)
        icon(self.zoom_out_action, QStyle.StandardPixmap.SP_ArrowDown)
        icon(self.zoom_reset_action, QStyle.StandardPixmap.SP_BrowserStop)
        icon(self.center_action, QStyle.StandardPixmap.SP_DialogApplyButton)
        icon(self.zoom_fit_action, QStyle.StandardPixmap.SP_TitleBarMaxButton)

        self.tool_group = QActionGroup(self)
        self.tool_group.setExclusive(True)
        for action in (self.select_action, self.pan_action, self.connect_action):
            self.tool_group.addAction(action)
        self.select_action.triggered.connect(self.activate_pointer)
        self.pan_action.triggered.connect(self.activate_hand)
        self.connect_action.triggered.connect(self.toggle_connect)
        self.select_action.setChecked(True)
        for action in self.findChildren(QAction):
            action.setToolTip(action.text())

        menu = self.menuBar()
        file_menu = menu.addMenu("Archivo")
        file_menu.addActions([self.new_action, self.open_action, self.save_action, self.save_as_action])
        file_menu.addSeparator()
        file_menu.addActions([self.export_action, self.export_xml_action])
        edit_menu = menu.addMenu("Editar")
        edit_menu.addActions(
            [
                self.add_node_action,
                self.indent_action,
                self.outdent_action,
                self.label_link_action,
                self.edit_text_action,
                self.delete_action,
                self.layout_action,
            ]
        )
        tools_menu = menu.addMenu("Herramientas")
        tools_menu.addActions([self.select_action, self.pan_action, self.connect_action])
        view_menu = menu.addMenu("Vista")
        view_menu.addActions([self.zoom_in_action, self.zoom_out_action, self.zoom_reset_action])
        view_menu.addSeparator()
        view_menu.addActions([self.center_action, self.zoom_fit_action])

    def make_toolbar(self) -> None:
        toolbar = QToolBar("Mapa")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(22, 22))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        brand = QLabel("VUE Modern")
        brand.setObjectName("brandLabel")
        toolbar.addWidget(brand)
        toolbar.addSeparator()
        toolbar.addActions([self.new_action, self.open_action, self.save_action])
        toolbar.addSeparator()
        toolbar.addActions([self.select_action, self.pan_action, self.connect_action])
        toolbar.addSeparator()
        toolbar.addActions([self.add_node_action, self.indent_action, self.outdent_action, self.label_link_action, self.edit_text_action, self.delete_action])
        toolbar.addSeparator()
        toolbar.addActions([self.layout_action, self.zoom_out_action, self.zoom_in_action, self.zoom_reset_action, self.center_action, self.zoom_fit_action])
        self.zoom_label = QLabel("100 %")
        self.zoom_label.setObjectName("zoomLabel")
        self.zoom_label.setMinimumWidth(52)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toolbar.addWidget(self.zoom_label)
        toolbar.addSeparator()
        toolbar.addActions([self.export_action, self.export_xml_action])
        self.addToolBar(toolbar)

    def new_map(self, checked=False, seed: bool = False) -> None:
        if not seed and not self.confirm_unsaved():
            return
        self.scene.blockSignals(True)
        self.scene.clear_map()
        if seed:
            central = self.scene.add_node("Mi mapa", QPointF(-95, -43), "#DBEAFE", "Punto de partida")
            for label, point, colour in (
                ("Pregunta", QPointF(-390, -180), "#FEF3C7"),
                ("Evidencia", QPointF(230, -180), "#DCFCE7"),
                ("Próximo paso", QPointF(230, 160), "#EDE9FE"),
            ):
                node = self.scene.add_node(label, point, colour)
                self.scene.add_link(central, node)
        self.scene.blockSignals(False)
        self.file_path = None
        self.dirty = False
        self.update_title()
        self.zoom_fit()

    def add_node(self) -> None:
        label, accepted = QInputDialog.getText(self, "Nuevo concepto", "Texto del concepto:", text="Nueva idea")
        if not accepted or not label.strip():
            return
        point = self.canvas.mapToScene(self.canvas.viewport().rect().center())
        node = self.scene.add_node(label.strip(), point - QPointF(MapNode.WIDTH / 2, MapNode.HEIGHT / 2), PALETTE[len(self.scene.items()) % len(PALETTE)])
        self.scene.clearSelection()
        node.setSelected(True)
        self.inspector.inspect(node)

    def set_interaction_mode(self, mode: str) -> None:
        self.canvas._source = None
        self.canvas.connect_mode = mode == "connect"
        if mode == "pan":
            self.canvas.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.canvas.setCursor(Qt.CursorShape.OpenHandCursor)
            self.statusBar().showMessage("Modo mano: arrastra el lienzo para desplazarte.")
        elif mode == "connect":
            self.canvas.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.canvas.setCursor(Qt.CursorShape.CrossCursor)
            self.statusBar().showMessage("Modo conectar: haz clic en el origen y luego en el destino.")
        else:
            self.canvas.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            self.canvas.setCursor(Qt.CursorShape.ArrowCursor)
            self.statusBar().showMessage("Modo puntero: selecciona y arrastra conceptos.")

    def activate_pointer(self, checked: bool = True) -> None:
        if checked:
            self.set_interaction_mode("select")

    def activate_hand(self, checked: bool = True) -> None:
        if checked:
            self.set_interaction_mode("pan")

    def toggle_connect(self, enabled: bool) -> None:
        if enabled:
            self.set_interaction_mode("connect")
        else:
            self.select_action.setChecked(True)
            self.set_interaction_mode("select")

    def create_link(self, source: MapNode, target: MapNode) -> None:
        if self.scene.add_link(source, target):
            self.statusBar().showMessage("Conexión creada.", 2500)
        else:
            self.statusBar().showMessage("Esos conceptos ya están conectados.", 2500)

    def selected_node(self) -> MapNode | None:
        return next((item for item in self.scene.selectedItems() if isinstance(item, MapNode)), None)

    def indent_selected_node(self) -> None:
        node = self.selected_node()
        if not node:
            QMessageBox.information(self, "Indentar", "Selecciona un concepto para indentar.")
            return
        candidates = [item for item in self.scene.items() if isinstance(item, MapNode) and item is not node]
        if not candidates:
            return
        choices = {f"{candidate.data.label}  ·  {candidate.data.id[:6]}": candidate for candidate in candidates}
        choice, accepted = QInputDialog.getItem(self, "Indentar concepto", "Concepto padre:", list(choices), 0, False)
        if not accepted:
            return
        parent = choices[choice]
        if not self.scene.indent_node(node, parent):
            QMessageBox.warning(self, "Indentar", "No puedes crear una jerarquía circular.")
            return
        self.mark_dirty()
        self.statusBar().showMessage(f"{node.data.label} quedó indentado bajo {parent.data.label}.", 3500)

    def outdent_selected_node(self) -> None:
        node = self.selected_node()
        if not node or not self.scene.outdent_node(node):
            return
        self.mark_dirty()
        self.statusBar().showMessage("Concepto desindentado.", 2500)

    def label_selected_link(self) -> None:
        link = next((item for item in self.scene.selectedItems() if isinstance(item, MapLink)), None)
        if not link:
            QMessageBox.information(self, "Etiquetar enlace", "Selecciona un enlace o haz doble clic sobre él.")
            return
        label, accepted = QInputDialog.getText(self, "Etiquetar enlace", "Etiqueta del enlace:", text=link.label)
        if accepted:
            link.label = label.strip()
            link.update()
            self.mark_dirty()

    def edit_selected_node_text(self) -> None:
        node = self.selected_node()
        if not node:
            QMessageBox.information(self, "Editar texto", "Selecciona un concepto para editar su texto.")
            return
        text, accepted = QInputDialog.getText(
            self,
            "Editar texto del concepto",
            "Texto breve (máx. 256 caracteres):",
            text=node.data.text,
        )
        if not accepted:
            return
        node.data.text = text.strip()[:256]
        self.scene.reflow_hierarchy()
        node.update()
        self.inspector.inspect(node)
        self.mark_dirty()

    def delete_selection(self) -> None:
        selected = list(self.scene.selectedItems())
        if not selected:
            return
        for item in selected:
            if isinstance(item, MapNode):
                self.scene.remove_node(item)
            elif isinstance(item, MapLink):
                self.scene.remove_link(item)
        self.inspector.inspect(None)

    def auto_layout(self) -> None:
        nodes = [item for item in self.scene.items() if isinstance(item, MapNode)]
        if not nodes:
            return
        columns = max(1, round(len(nodes) ** 0.5))
        for index, node in enumerate(reversed(nodes)):
            row, column = divmod(index, columns)
            node.setPos(column * 280 - (columns - 1) * 140, row * 175)
        self.zoom_fit()
        self.mark_dirty()

    def selection_changed(self) -> None:
        selected = self.scene.selectedItems()
        node = next((item for item in selected if isinstance(item, MapNode)), None)
        self.inspector.inspect(node)

    def mark_dirty(self) -> None:
        self.dirty = True
        self.update_title()

    def update_title(self) -> None:
        name = self.file_path.stem if self.file_path else "Mapa sin título"
        self.setWindowTitle(f"{'● ' if self.dirty else ''}{name} — {APP_NAME}")

    def confirm_unsaved(self) -> bool:
        if not self.dirty:
            return True
        result = QMessageBox.question(self, "Cambios sin guardar", "¿Quieres guardar tus cambios antes de continuar?", QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        if result == QMessageBox.StandardButton.Save:
            return self.save_map()
        return result == QMessageBox.StandardButton.Discard

    def open_map(self) -> None:
        if not self.confirm_unsaved():
            return
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir mapa",
            str(Path.home() / "Documents"),
            "Mapas VUE Modern (*.vuemodern.json);;Mapas VUE clásicos (*.vue)",
        )
        if not file_name:
            return
        try:
            self.scene.blockSignals(True)
            selected_path = Path(file_name)
            if selected_path.suffix.lower() == ".vue":
                nodes, links = self.scene.load_legacy_vue(selected_path)
                self.file_path = None
                self.statusBar().showMessage(f"Mapa VUE importado: {nodes} conceptos y {links} conexiones. Guárdalo como VUE Modern.", 7000)
            else:
                document = json.loads(selected_path.read_text(encoding="utf-8"))
                self.scene.load_document(document)
                self.file_path = selected_path
            self.scene.blockSignals(False)
            self.dirty = False
            self.update_title()
            self.zoom_fit()
        except (OSError, ValueError, json.JSONDecodeError) as error:
            QMessageBox.critical(self, "No se pudo abrir", str(error))

    def save_map(self, checked=False, save_as: bool = False) -> bool:
        if not self.file_path or save_as:
            file_name, _ = QFileDialog.getSaveFileName(self, "Guardar mapa", str(Path.home() / "Documents" / "mi-mapa.vuemodern.json"), "Mapas VUE Modern (*.vuemodern.json)")
            if not file_name:
                return False
            self.file_path = Path(file_name)
            if self.file_path.suffix != ".json":
                self.file_path = self.file_path.with_suffix(".vuemodern.json")
        try:
            self.file_path.write_text(json.dumps(self.scene.to_document(), ensure_ascii=False, indent=2), encoding="utf-8")
            self.dirty = False
            self.update_title()
            self.statusBar().showMessage(f"Mapa guardado: {self.file_path.name}", 3500)
            return True
        except OSError as error:
            QMessageBox.critical(self, "No se pudo guardar", str(error))
            return False

    def export_png(self) -> None:
        file_name, _ = QFileDialog.getSaveFileName(self, "Exportar PNG", str(Path.home() / "Documents" / "mi-mapa.png"), "Imagen PNG (*.png)")
        if not file_name:
            return
        rect = self.scene.itemsBoundingRect().adjusted(-60, -60, 60, 60)
        if rect.isEmpty():
            return
        image = QImage(int(rect.width()), int(rect.height()), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor("#F8FAFC"))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.scene.render(painter, target=QRectF(image.rect()), source=rect)
        painter.end()
        if image.save(file_name):
            self.statusBar().showMessage("PNG exportado.", 3000)

    def export_xml(self) -> None:
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar XML",
            str(Path.home() / "Documents" / "mi-mapa.xml"),
            "XML (*.xml)",
        )
        if not file_name:
            return
        export_path = Path(file_name)
        if export_path.suffix.lower() != ".xml":
            export_path = export_path.with_suffix(".xml")
        try:
            self.scene.export_xml(export_path)
            self.statusBar().showMessage(f"XML exportado: {export_path.name}", 3500)
        except OSError as error:
            QMessageBox.critical(self, "No se pudo exportar XML", str(error))

    def update_zoom_label(self, percent: int) -> None:
        self.zoom_label.setText(f"{percent} %")

    def center_nodes(self) -> None:
        bounds = self.scene.itemsBoundingRect()
        if bounds.isEmpty():
            return
        self.canvas.centerOn(bounds.center())
        self.statusBar().showMessage("Vista centrada en los nodos.", 2500)

    def zoom_fit(self) -> None:
        bounds = self.scene.itemsBoundingRect()
        if not bounds.isEmpty():
            self.canvas.fitInView(bounds.adjusted(-90, -90, 90, 90), Qt.AspectRatioMode.KeepAspectRatio)
            self.canvas.report_zoom()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self.confirm_unsaved():
            event.accept()
        else:
            event.ignore()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("VUE Modern")
    font_id = QFontDatabase.addApplicationFont(str(ASSETS_DIR / "Inter-Variable.ttf"))
    if font_id >= 0:
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app.setFont(QFont(families[0], 10))
    app.setStyle("Fusion")
    app.setStyleSheet(
        """
        QMainWindow { background: #EDE7DD; }
        QMenuBar {
            background: rgba(255, 253, 248, 238); color: #322D27;
            border-bottom: 1px solid #D8CEC0; padding: 5px 14px; font: 10pt "Inter";
        }
        QMenuBar::item { padding: 8px 12px; margin: 0 2px; border-radius: 8px; background: transparent; }
        QMenuBar::item:selected { background: #EAE3D7; color: #245BBB; }
        QToolBar {
            background: rgba(255, 253, 248, 230); border: 1px solid #DED4C6;
            border-radius: 14px; margin: 7px 12px 9px 12px; padding: 6px 10px; spacing: 5px;
        }
        QToolButton {
            min-width: 34px; min-height: 34px; border: 1px solid transparent; border-radius: 10px;
            padding: 5px; color: #3E352D; font: 8.5pt "Inter";
        }
        QToolButton:hover { background: rgba(235, 226, 213, 220); border-color: #D2C5B4; color: #245BBB; }
        QToolButton:checked { background: #E4EDF9; border-color: #9BBCEB; color: #245BBB; }
        QLabel#brandLabel { color: #2F2B27; font: 700 16px "Inter"; padding: 0 12px 0 5px; }
        QLabel#zoomLabel { color: #675B4E; font-weight: 600; padding: 0 8px; }
        QMenu { background: #FFFCF7; color: #3E352D; border: 1px solid #D8CEC0; border-radius: 10px; padding: 6px; }
        QMenu::item { padding: 8px 30px 8px 30px; border-radius: 7px; }
        QMenu::item:selected { background: #EEE7DC; color: #245BBB; }
        QMenu::separator { height: 1px; background: #E4DCD1; margin: 5px 10px; }
        QSplitter::handle { background: transparent; width: 7px; }
        QSplitter::handle:hover { background: #DAD0C2; }
        #inspectorPanel {
            background: rgba(255, 253, 248, 238); border: 1px solid #DED4C6;
            border-radius: 16px; margin: 0 12px 12px 0;
        }
        #inspectorPanel QLabel { color: #4F453C; background: transparent; }
        #panelTitle { font: 600 20px "Inter"; color: #2F2B27; padding-bottom: 4px; }
        QLineEdit, QPlainTextEdit {
            border: 1px solid #D6CCBE; border-radius: 9px; padding: 8px; background: rgba(255, 255, 255, 210);
            color: #2F2B27; selection-background-color: #B9D0F3;
        }
        QLineEdit:focus, QPlainTextEdit:focus { border: 2px solid #6F9ADD; background: #FFFFFF; }
        QPushButton { border: 1px solid #D2C6B6; border-radius: 9px; padding: 8px 11px; background: rgba(255, 255, 255, 200); color: #3E352D; }
        QPushButton:hover { background: #EEE7DC; border-color: #BDAF9E; }
        #primaryButton { background: #285EBC; color: white; border-color: #285EBC; font-weight: 600; }
        #primaryButton:hover { background: #1D4D9D; }
        QDialog, QMessageBox { background: #FFFCF7; color: #2F2B27; }
        QDialog QLabel, QMessageBox QLabel { background: transparent; color: #2F2B27; }
        QDialog QPushButton, QMessageBox QPushButton { background: #FFFFFF; color: #3E352D; border: 1px solid #C8BAA9; min-width: 76px; }
        QDialog QPushButton:hover, QMessageBox QPushButton:hover { background: #EEE7DC; }
        QStatusBar { background: rgba(255, 253, 248, 235); border-top: 1px solid #DED4C6; color: #675B4E; padding-left: 12px; }
        """
    )
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
