import enum
import pathlib
from math import sqrt

from qtpy.QtCore import (
    QPointF, 
    QByteArray, 
    Signal,
)
from qtpy.QtGui import QStandardItem, QStandardItemModel, QIcon, QFont
from cognixcore.utils import serialize, deserialize
from cognixcore.base import Event, Identifiable, IdentifiableGroups, InfoType

from typing import Generic, Callable, TYPE_CHECKING, Any
if TYPE_CHECKING:
    from cognixcore import Node
    from .nodes.gui import NodeGUI
    from .inspector import InspectorWidget

class Location:
    PACKAGE_PATH = None

__folder_icon: QIcon = None 
def get_folder_icon() -> QIcon:
    """Gets the default folder icon"""
    global __folder_icon
    if not __folder_icon:
        __folder_icon = QIcon(f'{Location.PACKAGE_PATH}/resources/pics/cognix folder icon.png')
    return __folder_icon

__node_icon: QIcon = None
def get_node_icon() -> QIcon:
    """Gets the default node icon"""
    global __node_icon
    if not __node_icon:
        __node_icon = QIcon(f'{Location.PACKAGE_PATH}/resources/pics/cognix node.png')
    return __node_icon

__var_icon: QIcon = None
def get_var_icon() -> QIcon:
    """Gets the default variable icon"""
    global __var_icon
    if not __var_icon:
        __var_icon = QIcon(f'{Location.PACKAGE_PATH}/resources/pics/data icon.png')
    return __var_icon

text_font = QFont('Source Code Pro', 9)
text_font.setPointSizeF(text_font.pointSizeF() * 1.15)

def connect_signal_event(signal: Signal, ev: Event, callback):
    signal.connect(callback)
    ev.sub(signal.emit)
       
def generate_name(obj, name):
   return f'{name}:[{id(obj)}]' 
    
def pythagoras(a, b):
    return sqrt(a ** 2 + b ** 2)

def get_longest_line(s: str):
    lines = s.split('\n')
    lines = [line.replace('\n', '') for line in lines]
    longest_line_found = ''
    for line in lines:
        if len(line) > len(longest_line_found):
            longest_line_found = line
    return line

def shorten(s: str, max_chars: int, line_break: bool = False):
    """Ensures, that a given string does not exceed a given max length. If it would, its cut in the middle."""
    l = len(s)
    if l > max_chars:
        insert = ' . . . '
        if line_break:
            insert = '\n'+insert+'\n'
        insert_length = len(insert)
        left = s[:round((max_chars-insert_length)/2)]
        right = s[round(l-((max_chars-insert_length)/2)):]
        return left+insert+right
    else:
        return s

def create_tooltip(value, linebreak=True):
    """
    Creates a tooltip string for an object.
    
    Checks if the object has a __len__ dunder method to get a subset of it if it's too big.
    """
    
    tooltip_str = "None"
    if not isinstance(value, str):
        # if there is a __len__ function, get a subset if it's too big
        if hasattr(value, '__len__') and len(value) > 10:
            tooltip_str = str(value[:10])
            tooltip_str = f'{tooltip_str}\n. . .'
        else:
            tooltip_str = str(value)
    else:
        tooltip_str = value
    return shorten(tooltip_str, 1000, linebreak)
    
def pointF_mapped(p1, p2):
    """adds the floating part of p2 to p1"""
    p2.setX(p1.x() + p2.x()%1)
    p2.setY(p1.y() + p2.y()%1)
    return p2

def points_dist(p1, p2):
    return sqrt(abs(p1.x() - p2.x())**2 + abs(p1.y() - p2.y())**2)

def middle_point(p1, p2):
    return QPointF((p1.x() + p2.x())/2, (p1.y() + p2.y())/2)

class MovementEnum(enum.Enum):
    # this should maybe get removed later
    mouse_clicked = 1
    position_changed = 2
    mouse_released = 3

def get_resource(filepath: str):
    return pathlib.Path(Location.PACKAGE_PATH, 'resources', filepath)

def change_svg_color(filepath: str, color_hex: str):
    """Loads an SVG, changes all '#xxxxxx' occurrences to color_hex, renders it into and a pixmap and returns it"""

    # https://stackoverflow.com/questions/15123544/change-the-color-of-an-svg-in-qt

    from qtpy.QtSvg import QSvgRenderer
    from qtpy.QtGui import QPixmap, QPainter
    from qtpy.QtCore import Qt

    with open(filepath) as f:
        data = f.read()
    data = data.replace('fill:#xxxxxx', 'fill:'+color_hex)

    svg_renderer = QSvgRenderer(QByteArray(bytes(data, 'ascii')))

    pix = QPixmap(svg_renderer.defaultSize())
    pix.fill(Qt.transparent)
    pix_painter = QPainter(pix)
    svg_renderer.render(pix_painter)

    return pix
    
class IdentifiableGroupsModel(QStandardItemModel, Generic[InfoType]):
    """
    A nested model that works with identifiables.
    
    Useful for building tree views
    """
    id_added_signal = Signal(Identifiable) # Identifiable[InfoType] doesn't work correctly
    group_added_signal = Signal(str)
    
    def __init__(self, groups: IdentifiableGroups[InfoType], label = "Something", separator = '.'):
        super().__init__()
        self.setHorizontalHeaderLabels([label])
        self.groups = groups
        self.root_item = self.invisibleRootItem()
        self.separator = separator
        self.model_nodes: dict[str, QStandardItem] = {"root_item": self.root_item}
        
        # create the initial state
        for group_id, node_types in self.groups.groups.items():
            self.create_subgroups(group_id)
            for node_type in node_types.values():
                self.on_identifiable_added(node_type)
                
        connect_signal_event(self.group_added_signal, self.groups.group_added, self.create_subgroups)
        connect_signal_event(self.id_added_signal, self.groups.id_added, self.on_identifiable_added)
    
    def on_identifiable_added(self, id: Identifiable[InfoType]):
        """Adds the item to its parent"""
        if not self.has_subgroup_item(id.prefix):
            return
        parent_item = self.model_nodes[id.prefix]
        parent_item.appendRow(self.create_id_item(id))
    
    def create_id_item(self, id: Identifiable[InfoType]):
        """
        VIRTUAL
        
        Override this to create a model item for an identifiable
        """
        return QStandardItem(id.name())
    
    def has_subgroup_item(self, group_id: str):
        return group_id in self.model_nodes
             
    def create_subgroup(self, name: str, path: str) -> QStandardItem:
        """
        VIRTUAL
        Creates a subgroup item
        
        Override this to handle subgroup item creation
        """
        item = QStandardItem(name)
        item.setEditable(False)
        item.setDragEnabled(False)
        return item
    
    def create_subgroups(self, group_id: str):
        """
        Creates the various groups as QStandardItems from a group id path. 
        An optional creat_item function can be given for creation of an item.
        """
        if group_id in self.model_nodes:
            return 
        
        split_groups = group_id.split(self.separator)
        current_path = split_groups[0]
        current_root = self.root_item
        sg_len = len(split_groups)
        for i in range(sg_len):
            sg_name = split_groups[i]
            if not current_path in self.model_nodes:
                item = self.create_subgroup(sg_name, current_path)
                current_root.appendRow(item)
                self.model_nodes[current_path] = item
            current_root = self.model_nodes[current_path]
            if i != sg_len - 1:
                current_path = f"{current_path}.{split_groups[i+1]}"
        