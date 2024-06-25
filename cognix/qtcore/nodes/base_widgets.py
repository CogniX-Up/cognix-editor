"""The base classes for node custom widgets for nodes."""
from __future__ import annotations
from cognixcore import Node

from ..gui_base import SerializableItem

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .item import NodeItem
    from .gui import NodeGUI
    from cognixcore import NodeInput

class NodeMainWidget(SerializableItem):
    """Base class for the main widget of a node."""

    def __init__(self, params: tuple[Node, NodeItem, NodeGUI]):
        self.node, self.node_item, self.node_gui = params

    def update_node(self):
        self.node.update()

    def update_node_shape(self):
        self.node_item.update_shape()


class NodeInputWidget(SerializableItem):
    """Base class for the input widget of a node."""

    def __init__(self, params: tuple[NodeInput, Any, Node, NodeGUI, Any]):
        self.input, self.input_item, self.node, self.node_gui, self.position = params

    def val_update_event(self, val):
        """
        *VIRTUAL*

        Called when the input's value is updated through a connection.
        This can be used to represent the value in the widget.
        The widget is disabled when the port is connected.
        """
        pass

    # API methods

    def update_node_input(self, val, silent=False):
        """
        Update the input's value and update the node.
        """
        self.input.default = val
        if not silent:
            self.node.update(self.node._inputs.index(self.input))

    def update_node(self):
        self.node.update(self.node._inputs.index(self.input))

    def update_node_shape(self):
        self.node_gui.update_shape()
        