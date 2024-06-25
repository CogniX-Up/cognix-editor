from __future__ import annotations
from queue import Queue

from qtpy.QtCore import QObject, Signal
from qtpy.QtWidgets import QWidget
from qtpy.QtGui import Qt

from .base_widgets import NodeMainWidget, NodeInputWidget
from ..nodes.inspector import NodeInspectorWidget, ConfigNodeInspectorWidget
from .viewer import NodeViewerWidget, NodeViewerDefault
from .viewer import NodeViewerDefault
from ..config.abc import NodeConfigInspector
from .inspector import (
    NodeInspectorDefaultWidget, 
    InspectedChangedEvent, 
    ConfigNodeInspectorWidget
)
from ..flows.commands import DelegateCommand, undo_text_multi

from cognixcore import (
    Node,
    NodeConfig, 
    ProgressState,
    NodeAction,
)

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .item import NodeItem
    from ..session_gui import SessionGUI
    from ..flows.view import FlowView

class NodeGUI(QObject):
    """
    Interface class between nodes and their GUI representation.
    
    Both the viewer and the inspector are created when the GUI
    itself is created. This fact prevents dynamically creating
    viewers or inspectors for this node after the fact. This is
    by design.
    """

    # customizable gui attributes
    description_html: str = None
    
    main_widget_class: type[NodeMainWidget | QWidget] = None
    main_widget_pos: str = 'below ports'
    input_widget_classes: dict[str, type[NodeInputWidget | QWidget]] = {}
    inspector_widget_class: type[NodeInspectorWidget | QWidget] = ConfigNodeInspectorWidget
    wrap_inspector_in_default: bool = True
    viewer_widget_class: type[NodeViewerWidget | QWidget] = NodeViewerDefault
    
    init_input_widgets: dict = {}
    style: str = 'normal'
    color: str = '#c69a15'
    display_title: str = None
    icon: str = None

    # qt signals
    config_changed_signal = Signal(NodeConfig, NodeConfig)
    updating = Signal()
    update_error = Signal(object)
    input_added = Signal(int, object)
    output_added = Signal(int, object)
    input_removed = Signal(int, object)
    output_removed = Signal(int, object)
    input_renamed = Signal(int, object, str)
    output_renamed = Signal(int, object, str)
    update_shape_triggered = Signal()
    hide_unconnected_ports_triggered = Signal()
    show_unconnected_ports_triggered = Signal()
    progress_updated = Signal(ProgressState)
    
    def __init__(self, params: tuple[Node, SessionGUI, FlowView]):
        QObject.__init__(self)

        self.node, self.session_gui, self._flow_view = params
        self.item: NodeItem = None   # set by the node item directly after this __init__ call
        setattr(self.node, 'gui', self)

        if self.display_title is None:
            self.display_title = self.node.title

        self.input_widgets = {}     # {input: widget name}
        for i, widget_data in self.init_input_widgets.items():
            self.input_widgets[self.node._inputs[i]] = widget_data
        # using attach_input_widgets() one can buffer input widget
        # names for inputs that are about to get created
        self._next_input_widgets = Queue()

        self.error_during_update = False
        self.config_changed_func = None

        # turn ryvencore signals into Qt signals
        self.node.updating.sub(self._on_updating)
        self.node.update_error.sub(self._on_update_error)
        self.node.input_added.sub(self._on_new_input_added)
        self.node.output_added.sub(self._on_new_output_added)
        self.node.input_removed.sub(self._on_input_removed)
        self.node.output_removed.sub(self._on_output_removed)
        self.node.input_renamed.sub(self._on_input_renamed)
        self.node.output_renamed.sub(self._on_output_renamed)
        self.node.progress_updated.sub(self._on_progress_updated)
        self.config_changed_signal.connect(self._on_config_changed)

        # create the inspector widget
        self.inspector_widget = self.create_inspector()
        # create viewer widget
        self.viewer_widget = self.create_viewer()

    @property
    def gui_env(self):
        return self.flow_view.session_gui.gui_env
    
    def create_viewer(self):
        """Creates the viewer for this node."""
        
        return (
            self.viewer_widget_class((self.node, self)) 
            if self.viewer_widget_class else None
        )
        
    def create_inspector(self):
        """Creates the inspector based on settings of the GUI."""
        
        inspector_params = (self.node, self)
        if self.wrap_inspector_in_default:
            inspector_widget = NodeInspectorDefaultWidget(
                child=self.inspector_widget_class((self.node, self)),
                params=inspector_params,
            )
        else:
            inspector_widget = self.inspector_widget_class(inspector_params)
        return inspector_widget
    
    def initialized(self):
        """
        *VIRTUAL*

        Called after the node GUI has been fully initialized.
        The Node has been created already (including all ports) and loaded.
        No connections have been made to ports of the node yet.
        """
        self.apply_conf_events()
        self._init_default_actions()

    def apply_conf_events(self):
        """Creates the config changed GUI event based on config GUI class"""
        
        cognix_n = self.node
        # apply config changed event
        cognix_n.config_changed.sub(self.config_changed_signal.emit)
        
        # appl config param change events
        config = cognix_n.config
        if not config:
            return None
        
        config_gui_cls: NodeConfigInspector = self.gui_env.get_inspector(type(config))
        if not config_gui_cls:
            return None
        
        e = config_gui_cls.create_config_changed_event(cognix_n, self)
        if e:
            cognix_n.config.add_changed_event(e)
        
        self.config_changed_func = e
    
    def remove_conf_events(self):
        
        self.node.config_changed.unsub(self.config_changed_signal.emit)
        
        # config params
        if self.config_changed_func:
            self.node.config.remove_changed_event(self.config_changed_func)
            self.config_changed_func = None
    """
    slots
    """

    def _on_update_error(self, e):
        self.update_error.emit(e)

    def _on_updating(self, inp: int):
        # update input widget
        if inp != -1 and self.item.inputs[inp].widget is not None:
            o = self.node.flow.connected_output(self.node._inputs[inp])
            if o is not None:
                self.item.inputs[inp].widget.val_update_event(o.val)
        self.updating.emit()

    def _on_new_input_added(self, _, index, inp):
        if not self._next_input_widgets.empty():
            self.input_widgets[inp] = self._next_input_widgets.get()
        self.input_added.emit(index, inp)

    def _on_new_output_added(self, _, index, out):
        self.output_added.emit(index, out)

    def _on_input_removed(self, _, index, inp):
        self.input_removed.emit(index, inp)

    def _on_output_removed(self, _, index, out):
        self.output_removed.emit(index, out)
    
    def _on_input_renamed(self, _, index, inp, old_name):
        self.input_renamed.emit(index, inp, old_name)
    
    def _on_output_renamed(self, _, index, out, old_name):
        self.output_renamed.emit(index, out, old_name)

    def _on_progress_updated(self, progress: ProgressState):
        self.progress_updated.emit(progress)
    
    def _on_restored(self):
        """Called when a node is restored from being deleted"""
        self.config_changed_func = self.apply_conf_events()
    
    def _on_deleted(self):
        """Called when a node is deleted"""
        self.remove_conf_events()
        if self.inspector_widget:
            self.inspector_widget.on_node_deleted()
            
        if self.viewer_widget:
            self.viewer_widget.on_node_deleted()
            self.hide_viewer()
    
    def _on_config_changed(self, old_conf: NodeConfig, new_conf: NodeConfig):
        """Invoked when a configuration changes"""
        
        def redo_undo(old_conf: NodeConfig, new_conf: NodeConfig):
            changed_event = InspectedChangedEvent(old_conf, new_conf, False)
            insp_widget: ConfigNodeInspectorWidget = self.inspector_widget
            insp_widget.config_gui.on_insp_changed(changed_event)
            
            viewer_insp: ConfigNodeInspectorWidget = self.viewer_widget.inspector_widget
            if viewer_insp:
                viewer_insp.on_insp_changed(changed_event)
                    
        self.flow_view.push_undo(
            DelegateCommand(
                self.flow_view,
                undo_text_multi(
                    [self.node], 
                    f"Config changed: {old_conf.__class__.__name__} -> {new_conf.__class__.__name__}"
                ),
                redo_undo(new_conf, old_conf),
                redo_undo(old_conf, new_conf),
            )
        )
    """
    actions
    
    TODO: move actions to ryvencore?
    """

    def _init_default_actions(self):
        """
        Returns the default actions every node should have
        """
        node = self.node
        self.update_shape_action = node.add_generic_action(
            'update shape',
            self.update_shape
        )
        self.collapse_action = node.add_generic_action(
            'collapse ports',
            self.collapse_ports
        )
        self.uncollapse_action = node.add_generic_action(
            'uncollapse ports',
            self.uncollapse_ports
        )
        # TODO store this in the node somewhere
        self.uncollapse_action.status = NodeAction.Status.HIDDEN
        
        self.change_title_action = node.add_generic_action(
            'change title',
            self.change_title
        )
        self.toggle_viewer_action = node.add_generic_action(
            'toggle viewer',
            self.toggle_viewer
        )
        
        if self.session_gui.console:
            def console_ref():
                self.session_gui.console.add_obj_context(self.node)
                
            self.console_patch_action = node.add_generic_action(
                'console ref',
                console_ref    
            )

    """
    serialization
    """

    def data(self):
        return {
            'display title': self.display_title,
            'inspector widget': self.inspector_widget.get_state(),
        }

    def load(self, data):
        if 'display title' in data:
            self.display_title = data['display title']
        if 'inspector widget' in data:
            self.inspector_widget.set_state(data['inspector widget'])

    """
    GUI access methods
    """
    def title(self):
        return self.display_title
    
    def show_viewer(self):
        self.viewer_widget.setWindowTitle(self.title())
        self.viewer_widget.setParent(self.flow_view)
        self.viewer_widget.setWindowFlags(
            self.viewer_widget.windowFlags() |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.Dialog
        )
        self.viewer_widget.move(
            self.flow_view.mapToGlobal(
                self.item.pos()
            ).toPoint()
        )
        self.viewer_widget.show()
    
    def hide_viewer(self):
        self.viewer_widget.hide()
        
    def toggle_viewer(self):
        
        if self.viewer_widget.isHidden():
            self.show_viewer()
        else:
            self.hide_viewer()
            
    def set_display_title(self, t: str):
        self.display_title = t
        if self.viewer_widget:
            self.viewer_widget.setWindowTitle(self.display_title)
        self.update_shape()

    @property
    def flow_view(self):
        return self._flow_view

    def main_widget(self):
        """Returns the main_widget object, or None if the item doesn't exist (yet)"""

        return self.item.main_widget

    def attach_input_widgets(self, widget_names: list[str]):
        """Attaches the input widget to the next created input."""

        for w in widget_names:
            self._next_input_widgets.queue(w)

    def input_widget(self, index: int):
        """Returns a reference to the widget of the corresponding input"""

        return self.item.inputs[index].widget

    def session_stylesheet(self):
        return self.session_gui.design.global_stylesheet

    def update_shape(self):
        """Causes recompilation of the whole shape of the GUI item."""

        self.update_shape_triggered.emit()

    def collapse_ports(self):
        """Hides all ports that are not connected to anything."""

        self.collapse_action.status = NodeAction.Status.HIDDEN
        self.uncollapse_action.status = NodeAction.Status.ENABLED
        self.hide_unconnected_ports_triggered.emit()

    def uncollapse_ports(self):
        """Shows all ports that are not connected to anything."""

        self.collapse_action.status = NodeAction.Status.ENABLED
        self.uncollapse_action.status = NodeAction.Status.HIDDEN
        self.show_unconnected_ports_triggered.emit()

    def change_title(self):
        from qtpy.QtWidgets import QDialog, QVBoxLayout, QLineEdit

        class ChangeTitleDialog(QDialog):
            def __init__(self, title):
                super().__init__()
                self.new_title = None
                self.setLayout(QVBoxLayout())
                self.line_edit = QLineEdit(title)
                self.layout().addWidget(self.line_edit)
                self.line_edit.returnPressed.connect(self.return_pressed)

            def return_pressed(self):
                self.new_title = self.line_edit.text()
                self.accept()

        d = ChangeTitleDialog(self.display_title)
        d.exec()
        if d.new_title:
            self.set_display_title(d.new_title)
