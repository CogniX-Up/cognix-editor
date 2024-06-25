from __future__ import annotations

from qtpy.QtWidgets import QGraphicsGridLayout, QGraphicsWidget, QGraphicsLayoutItem
from qtpy.QtCore import Qt, QRectF, QPointF, QSizeF
from qtpy.QtGui import QFont

from ..gui_base import GUIBase
from ..utils import shorten, create_tooltip
from ..flows.widget_proxies import FlowViewProxyWidget
from ..util_widgets import GraphicsTextWidget

from enum import IntEnum

from cognixcore import (
    NodePort,
    NodeInput,
    NodeOutput,
    serialize,
    deserialize,
)

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..nodes.gui import NodeGUI
    from ..nodes.item import NodeItem
    from ..flows.view import FlowView
    
# utils


def is_connected(port: NodePort):
    if isinstance(port, NodeOutput):
        is_connected = len(port.node.flow.connected_inputs(port)) > 0
    else:
        is_connected = port.node.flow.connected_output(port) is not None
    return is_connected


def val(port: NodePort):
    if isinstance(port, NodeOutput):
        return port.val
    else:
        conn_out = port.node.flow.connected_output(port)
        if conn_out:
            return conn_out.val
        else:
            return None


def connections(port: NodePort):
    f = port.node.flow
    if isinstance(port, NodeOutput):
        return [
            f.connection_info((port, i)) 
            for i in port.node.flow.connected_inputs(port)
        ]
    else:
        conn_out = port.node.flow.connected_output(port)
        if conn_out:
            return [
                f.connection_info(
                    (port.node.flow.connected_output(port), port)
                )
            ]
        else:
            return []


# main classes


class PortItem(GUIBase, QGraphicsWidget):
    """The GUI representative for ports of nodes, also handling mouse events for connections."""

    def __init__(
        self, 
        node_gui: NodeGUI, 
        node_item: NodeItem, 
        port: NodePort, 
        flow_view: FlowView
    ):
        GUIBase.__init__(self, representing_component=port)
        QGraphicsWidget.__init__(self)

        self.setGraphicsItem(self)

        self.node_gui = node_gui
        self.node = self.node_gui.node
        self.node_item = node_item
        self._is_input = isinstance(port, NodeInput)
        self._port_list = self.node._inputs if self._is_input else self.node._outputs
        self._port_index = self._port_list.index(port)
        self.flow_view = flow_view

        self.pin = PortItemPin(
            self._port_list,
            self._port_index,
            self,
            self.node_gui, 
            self.node_item
        )

        self.label = GraphicsTextWidget(self)
        self.label.set_font(QFont("Source Code Pro", 10, QFont.Bold))
        
        self._layout = QGraphicsGridLayout()
        self._layout.setSpacing(0)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self._layout)

    @property
    def port(self):
        if len(self._port_list) <= self._port_index:
            return None
        return self._port_list[self._port_index]
    
    # >>> interaction boilerplate >>>
    def boundingRect(self):
        return QRectF(QPointF(0, 0), self.geometry().size())

    def setGeometry(self, rect):
        self.prepareGeometryChange()
        QGraphicsLayoutItem.setGeometry(self, rect)
        self.setPos(rect.topLeft())
    # <<< interaction boilerplate <<<

    def update(self):
        if self.port is None:
            return
        self.node_item.session_design.flow_theme.setup_PI_label(
            self.label,
            self.port.type_,
            self.pin.state,
            self.port.label_str,
            self.node_gui.color,
        )
        super().update()
        
    def setup_ui(self):
        pass

    def port_connected(self):
        self.pin.state = PinState.CONNECTED
        self.update()

    def port_disconnected(self):
        self.pin.state = PinState.DISCONNECTED
        self.update()


class InputPortItem(PortItem):
    def __init__(self, node_gui: NodeGUI, node_item: NodeItem, port: NodePort, input_widget: tuple[type, str] = None):
        super().__init__(node_gui, node_item, port, node_gui.flow_view)

        self.proxy = None  # widget proxy
        self.widget = None  # widget
        if input_widget is not None:
            self.create_widget(input_widget[0], input_widget[1])

        self.update_widget_value = (
            self.widget is not None
        )  # modified by FlowView when performance mode changes

        # catch up to missed connections
        if self.port.node.flow.connected_output(self.port) is not None:
            self.port_connected()

        if (
            self.port.type_ == 'data'
            and self.port.load_data is not None
            and self.port.load_data['has widget']
        ):
            c_d = self.port.load_data['widget data']
            if c_d is not None:
                self.widget.set_state(deserialize(c_d))
            else:
                # this is a little feature that lets us prevent loading of input widgets
                # which is occasionally useful, e.g. when changing an input widget class:
                # to prevent loading of the input widget, 'widget data' must be None
                pass

        self.setup_ui()

    def setup_ui(self):
        l = self._layout

        # l.setSpacing(0)
        l.addItem(self.pin, 0, 0)
        l.setAlignment(self.pin, Qt.AlignVCenter | Qt.AlignLeft)
        l.addItem(self.label, 0, 1)
        l.setAlignment(self.label, Qt.AlignVCenter | Qt.AlignLeft)
        if self.widget:
            if self.widget.position == 'below':
                l.addItem(self.proxy, 1, 0, 1, 2)
            elif self.widget.position == 'besides':
                l.addItem(self.proxy, 0, 2)
            else:
                print('Unknown input widget position:', self.widget.position)

            l.setAlignment(self.proxy, Qt.AlignCenter)

    def create_widget(self, widget_class, widget_pos):
        if widget_class is None:
            return

        if self.port.type_ != 'data':
            # TODO: how about input widgets for exec inputs?
            return

        params = (self.port, self, self.node_gui.node, self.node_gui, widget_pos)

        # custom input widget
        self.widget = widget_class(params)
        self.proxy = FlowViewProxyWidget(self.flow_view, parent=self.node_item)
        self.proxy.setWidget(self.widget)

    def port_connected(self):
        """Disables the widget"""
        if self.widget:
            self.widget.setEnabled(False)
        super().port_connected()

        # https://github.com/leon-thomm/Ryven/pull/137#issuecomment-1433783052
        # if self.port.type_ == 'data':
        #     self.port.connections[0].activated.connect(self._port_val_updated)
        #
        # self._port_val_updated(self.port.val)

    def port_disconnected(self):
        """Enables the widget again"""
        if self.widget:
            self.widget.setEnabled(True)
        super().port_disconnected()

    def complete_data(self, data: dict) -> dict:
        if self.port.type_ == 'data':
            if self.widget:
                data['has widget'] = True
                data['widget name'] = self.node_gui.input_widgets[self.port]['name']
                data['widget pos'] = self.node_gui.input_widgets[self.port]['pos']
                data['widget data'] = serialize(self.widget.get_state())
            else:
                data['has widget'] = False

        return data


class OutputPortItem(PortItem):
    def __init__(self, node_gui: 'NodeGUI', node_item: 'NodeItem', port: NodePort):
        super().__init__(node_gui, node_item, port, node_gui.flow_view)

        self.setup_ui()

    def setup_ui(self):
        l = self._layout

        # l.setSpacing(5)
        l.addItem(self.label, 0, 0)
        l.setAlignment(self.label, Qt.AlignVCenter | Qt.AlignRight)
        l.addItem(self.pin, 0, 1)

        l.setAlignment(self.pin, Qt.AlignVCenter | Qt.AlignRight)


# contents

class PinState(IntEnum):
    DISCONNECTED = 1
    CONNECTED = 2
    VALID = 3
    INVALID = 4
        
        
class PortItemPin(QGraphicsWidget):
    
    def __init__(self, port_list: list[NodePort], port_index: int, port_item, node_gui: NodeGUI, node_item: NodeItem):
        super(PortItemPin, self).__init__(node_item)
        
        self._port_list = port_list
        self.port_index = port_index
        self.port_item = port_item
        self.node_gui = node_gui
        self.node_item = node_item
        self.flow_view = self.node_item.flow_view
        
        self._state = PinState.DISCONNECTED

        self.setGraphicsItem(self)
        self.setAcceptHoverEvents(True)
        self.hovered = False
        self.setCursor(Qt.CrossCursor)
        self.tool_tip_pos = None

        self.padding = 2
        self.width = 17
        self.height = 17
        self.port_local_pos = None

    @property
    def port(self):
        if len(self._port_list) <= self.port_index:
            return None
        return self._port_list[self.port_index]
    
    @property
    def state(self):
        """Returns the pin state, regardless of whether it's connected"""
        return self._state
    
    @state.setter
    def state(self, value: PinState):
        """Sets the pin state. Protects if pin is connected"""
        self.set_state(value)
    
    def set_state(self, value: PinState, protect_connection = True):
        """
        Sets the pin state.
        
        If protect_connection and port is connected, state is set to PinState.CONNECTED
        """
        self._state = (
            value 
            if not (is_connected(self.port) and protect_connection) 
            else PinState.CONNECTED
        )
        self.update
        
    def boundingRect(self):
        return QRectF(QPointF(0, 0), self.geometry().size())

    def setGeometry(self, rect):
        self.prepareGeometryChange()
        QGraphicsLayoutItem.setGeometry(self, rect)
        self.setPos(rect.topLeft())

    def sizeHint(self, which, constraint=...):
        return QSizeF(self.width, self.height)

    def paint(self, painter, option, widget=None):
        port = self.port
        if not port:
            return
        
        self.node_item.session_design.flow_theme.paint_PI(
            node_gui=self.node_gui,
            painter=painter,
            option=option,
            node_color=self.node_gui.color,
            type_=port.type_,
            pin_state=self._state,
            rect=QRectF(
                self.padding, self.padding, self.width_no_padding(), self.height_no_padding()
            ),
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:  # DRAG NEW CONNECTION
            self.flow_view.mouse_event_taken = True
            self.flow_view._selected_pin = self
            self.flow_view._dragging_connection = True
            event.accept()  # don't pass the ev ent to anything below
        else:
            return QGraphicsWidget.mousePressEvent(self, event)

    def hoverEnterEvent(self, event):
        if self.port.type_ == 'data':
            self.setToolTip(create_tooltip(val(self.port)))

        # highlight connections
        items = self.flow_view.connection_items
        for c in connections(self.port):
            items[c].set_highlighted(True)

        self.hovered = True

        QGraphicsWidget.hoverEnterEvent(self, event)

    def hoverLeaveEvent(self, event):
        # un-highlight connections
        items = self.flow_view.connection_items
        for c in connections(self.port):
            items[c].set_highlighted(False)

        self.hovered = False

        QGraphicsWidget.hoverLeaveEvent(self, event)

    def width_no_padding(self):
        """The width without the padding"""
        return self.width - 2 * self.padding

    def height_no_padding(self):
        """The height without the padding"""
        return self.height - 2 * self.padding

    def get_scene_center_pos(self):
        if not self.node_item.collapsed:
            return QPointF(
                self.scenePos().x() + self.boundingRect().width() / 2,
                self.scenePos().y() + self.boundingRect().height() / 2,
            )
        else:
            if isinstance(self.port_item, InputPortItem):
                return self.node_item.get_left_body_header_vertex_scene_pos()
            else:
                return self.node_item.get_right_body_header_vertex_scene_pos()