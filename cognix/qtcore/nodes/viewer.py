from __future__ import annotations
from typing import TYPE_CHECKING
from qtpy.QtGui import QCloseEvent, QHideEvent, QShowEvent
from qtpy.QtWidgets import QTabWidget, QVBoxLayout, QDialog, QSplitter
from qtpy.QtCore import Qt

from ..code_editor.widgets import CodePreviewWidget
from ..addons.logging import LogWidget

from cognixcore import Node

if TYPE_CHECKING:
    from .gui import NodeGUI

class NodeViewerWidget:
    """
    Base class for the view widget of a node.
    
    A view is a detached window for interacting with the node other than the inspector.
    """

    def __init__(self, params: tuple[Node, NodeGUI]):
        self.node, self.node_gui = params
        self._inspector_widget = None
    
    @property
    def inspector_widget(self):
        """A Node Inspector for the viewer, if it was attached"""
        return self._inspector_widget
    
    def on_before_shown(self):
        """
        VIRTUAL
        
        Called before the viewer is shown
        """
        pass
    
    def on_after_shown(self):
        """
        VIRTUAL
        
        Called after the viewer is shown
        """
        pass
    
    def on_before_hidden(self):
        """
        VIRTUAL
        
        Called before the viewer is hidden.
        """
    
    def on_after_hidden(self):
        """
        VIRTUAL
        
        Called after the viewer is hidden.
        """
        
    def on_before_closed(self):
        """
        VIRTUAL
        
        Called before the viewer is closed
        """
        pass

    def on_after_closed(self):
        """
        VIRTUAL
        
        Called after the viewer is closed
        """
    
    def on_node_update(self, data):
        """
        VIRTUAL
        
        Called when a node is updated (the updated event).
        The developer can pass any kind of data and update the view.
        """
        pass

    def on_node_deleted(self):
        """
        VIRTUAL
        
        Called when a node is deleted
        """
        pass
    
    
class NodeViewerDefault(NodeViewerWidget, QDialog):
    """
    The default class for creating a view window for a node.
    
    Attaches a horizontal splitter as self.content. The inspector
    is also attached to the splitter.
    
    It is adviced to utilize this class for any potential overrides, as
    it connects to other qt events.
    """
    
    attach_inspect_widgets = True
    
    def __init__(self, params: tuple[Node, NodeGUI], parent=None):
        NodeViewerWidget.__init__(self, params)
        QDialog.__init__(self, parent)
        
        node, _ = params
        self.setLayout(QVBoxLayout())
        self.setWindowFlag(Qt.Widget)
    
        self.content = QSplitter()
        self.content.setOrientation(Qt.Orientation.Horizontal)
        self.layout().addWidget(self.content)
        self._inspector_widget = None
        
        if self.attach_inspect_widgets:
            
            self.inspect_tab_widget = QTabWidget()
            
            # inspector
            self._inspector_widget = self.node_gui.create_inspector()
            self.inspect_tab_widget.addTab(self._inspector_widget, 'Inspector')
            
            # logger
            self.logger = LogWidget(node.logger, node)
            self.inspect_tab_widget.addTab(self.logger, 'Logger')
            # code preview
            self.code_preview_widget = CodePreviewWidget(
                self.node_gui.session_gui.cd_storage,
            )
            self.inspect_tab_widget.addTab(self.code_preview_widget, 'Source Code')
            
            self.content.addWidget(self.inspect_tab_widget)
        
        self.setWindowTitle(f'{self.node_gui.display_title} Viewer @GID{self.node.global_id}')
        self.setMinimumHeight(650)
        
    # Connect Viewer functons to QT events
    
    def showEvent(self, show_event: QShowEvent):
        
        if self.code_preview_widget:
            self.code_preview_widget.text_edit.update_formatter(self.node_gui.session_gui.wnd_light_type)
            self.code_preview_widget._set_node(self.node)
        
        self.on_before_shown()
        
        if self.attach_inspect_widgets:
            self._inspector_widget.load()
            
        super().showEvent(show_event)
        self.on_after_shown()
    
    def hideEvent(self, hide_event: QHideEvent):
        self.on_before_hidden()
        super().hideEvent(hide_event)
        if self.attach_inspect_widgets:
            self._inspector_widget.unload()
        self.on_after_hidden()
    
    def on_node_deleted(self):
        if self.attach_inspect_widgets:
            self._inspector_widget.on_node_deleted()
    
    def closeEvent(self, close_event: QCloseEvent):
        self.on_before_closed()
        super().closeEvent(close_event)
        self.on_after_closed()
    
    
     