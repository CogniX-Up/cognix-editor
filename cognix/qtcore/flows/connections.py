from qtpy.QtCore import QPointF, Qt, Signal, QObject
from qtpy.QtGui import QPainter, QColor, QRadialGradient, QPainterPath, QPen
from qtpy.QtWidgets import (
    QGraphicsPathItem,
    QGraphicsItem,
    QStyleOptionGraphicsItem,
    QGraphicsEllipseItem,
)

from ..gui_base import GUIBase, AnimationTimer, QGraphicsItemAnimated
from ..utils import sqrt, pythagoras
from ..ports.item import PortItem
from ..design import Design
from ...qtcore.nodes.item import NodeItem

from qtpy.QtCore import (
    QTimeLine, 
    QPropertyAnimation, 
    QParallelAnimationGroup,
    QEasingCurve, 
)
from qtpy.QtGui import (
    QPen,
    QBrush, 
)
from qtpy.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
)

from cognixcore import NodeOutput, NodeInput, Node, ConnectionInfo
from enum import Enum

from typing import Any


class ConnectionItem(GUIBase, QGraphicsPathItem, QObject):
    """The GUI representative for a connection. The classes ExecConnectionItem and DataConnectionItem will be ready
    for reimplementation later, so users can add GUI for the enhancements of DataConnection and ExecConnection,
    like input fields for weights."""
    
    data_signal = Signal(Any) # tuple[NodeOutput, NodeInput]

    def __init__(
        self, 
        inp_node_item: NodeItem, 
        out_node_item: NodeItem, 
        connection: ConnectionInfo, 
        session_design: Design
    ):
        QGraphicsPathItem.__init__(self)
        QObject.__init__(self)

        self.setAcceptHoverEvents(True)

        self.connection = connection
        self.inp_node_item = inp_node_item
        self.out_node_item = out_node_item
        
        self.session_design = session_design
        self.session_design.flow_theme_changed.connect(self.recompute)
        self.session_design.performance_mode_changed.connect(self.recompute)

        # data signal
        self.data_signal.connect(self.__on_data_signal)
        
        # for rendering flow pictures
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        self.setFlag(QGraphicsItem.ItemIsSelectable)

        # connection animation
        diam = 12.5
        self.num_dots = 40
        self.dots = [
            QGraphicsEllipseItem(-diam / 2, -diam / 2, diam, diam, self) 
            for _ in range(self.num_dots)
        ]
        for dot in self.dots:
            dot.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
            dot.setVisible(False)

        self.items_path_animation = ConnPathItemsAnimation(self.dots, self)
        scale_dur = 350
        self.connection_animation = ConnPathItemsAnimationScaled(self.items_path_animation, duration=scale_dur)

        self._anim_timer = AnimationTimer(
            obj=self, 
            interval=250 + scale_dur, 
            on_restart=self.connection_animation.start, 
            on_timeout=self.connection_animation.stop
        )
        
        self.recompute()

    @property
    def out_item(self):
        return self.out_node_item.outputs[self.connection.out_i]
    
    @property
    def inp_item(self):
        return self.inp_node_item.inputs[self.connection.inp__i]
        
    def node(self) -> Node:
        return self.connection.node_out
        
    def __on_data_signal(self, data):
        """Called when the data signal is emitted"""
        if self.session_design.connection_animation_enabled:
            self._anim_timer.restart()
        else:
            self._anim_timer.stop()
    
    def __on_data(self, node: Node, index: int, out: NodeOutput, data):
        """Emits the data changed signal for this connection item"""
        output = self.connection.out_port
        if out == output and (self.session_design.connection_animation_enabled or self._anim_timer.is_running):
            self.data_signal.emit(data)
    
    def __str__(self):
        node_in_name = f'{self.connection.node_inp.gui.item}'
        node_in_index = self.connection.inp__i
        node_out_name = f'{self.connection.node_out.gui.item}'
        node_out_index =self.connection.out_i
        return f'{node_out_index}->{node_in_index} ({node_out_name}, {node_in_name})'

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget):
        # draw path
        painter.setBrush(self.brush())
        painter.setPen(self.pen())
        painter.drawPath(self.path())
        # return super().paint(painter, option, widget)

    def recompute(self):
        """Updates scene position and recomputes path, pen, gradient and dots"""
        # dots
        self.items_path_animation.recompute()

        # position
        self.setPos(self.out_pos())

        # path
        p1 = QPointF(self.out_item.pin.width_no_padding() * 0.5, 0)
        p2 = self.inp_pos() - self.scenePos() - QPointF(self.inp_item.pin.width_no_padding() * 0.5, 0)
        self.setPath(self.connection_path(p1, p2))

        # pen
        pen = self.get_pen()

        # brush
        self.setBrush(Qt.NoBrush)

        #   gradient
        if self.session_design.performance_mode == 'pretty':
            c = pen.color()
            w = self.path().boundingRect().width()
            h = self.path().boundingRect().height()
            gradient = QRadialGradient(
                self.boundingRect().center(), 
                pythagoras(w, h) / 2
            )

            c_r = c.red()
            c_g = c.green()
            c_b = c.blue()

            # this offset will be 1 if inp.x >> out.x and 0 if inp.x < out.x
            # hence, no fade for the gradient if the connection goes backwards
            offset_mult: float = max(
                0,
                min(
                    (self.inp_pos().x() - self.out_pos().x()) / 200,
                    1
                )
            )

            # and if the input is very far away from the output, decrease the gradient fade so the connection
            # doesn't fully disappear at the ends and stays visible
            if self.inp_pos().x() > self.out_pos().x():
                offset_mult = min(
                    offset_mult,
                    2000 / (self.dist(self.inp_pos(), self.out_pos()))
                )
                # zucker.

            gradient.setColorAt(0.0, QColor(c_r, c_g, c_b, 255))
            gradient.setColorAt(0.75, QColor(c_r, c_g, c_b, 255 - round(55 * offset_mult)))
            gradient.setColorAt(0.95, QColor(c_r, c_g, c_b, 255 - round(255 * offset_mult)))

            pen.setBrush(gradient)

        self.setPen(pen)

    def out_pos(self) -> QPointF:
        """The current global scene position of the pin of the output port"""

        return self.out_item.pin.get_scene_center_pos()

    def inp_pos(self) -> QPointF:
        """The current global scene position of the pin of the input port"""

        return self.inp_item.pin.get_scene_center_pos()

    def itemChange(self, change, value):
        # for highlights
        if change == QGraphicsItem.ItemSelectedHasChanged or (
            change == QGraphicsItem.ItemVisibleHasChanged and self.isVisible()
        ):
            self.set_highlighted(self.isSelected())
        
        # for data event
        node = self.node()
        if change == QGraphicsItem.ItemSceneChange:
            # if connection is added to the scene, subscribe to data change event
            if value:
                node.output_updated.sub(self.__on_data)
            else:
                node.output_updated.unsub(self.__on_data)
                
        return QGraphicsItem.itemChange(self, change, value)

    def set_highlighted(self, b: bool):
        pen: QPen = self.pen()

        if b:
            pen.setWidthF(self.pen_width() * 2)
        else:
            pen.setWidthF(self.pen_width())
            self.recompute()

        self.setPen(pen)

    def get_pen(self) -> QPen:
        pass

    def pen_width(self) -> int:
        pass

    def get_style_color(self):
        pass

    def flow_theme(self):
        return self.session_design.flow_theme

    def hoverEnterEvent(self, event):
        self.set_highlighted(True)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        if not self.isSelected():
            self.set_highlighted(False)
        super().hoverLeaveEvent(event)

    # uncomment to test connection animation:
    # 
    # def mouseReleaseEvent(self, event) -> None:
    #    self.connection_animation.toggle()
        
    @staticmethod
    def dist(p1: QPointF, p2: QPointF) -> float:
        """Returns the diagonal distance between the points using pythagoras"""

        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        return sqrt((dx**2) + (dy**2))

    @staticmethod
    def connection_path(p1: QPointF, p2: QPointF) -> QPainterPath:
        """Returns the painter path for drawing the connection, using the usual cubic connection path by default"""

        return default_cubic_connection_path(p1, p2)


class ExecConnectionItem(ConnectionItem):
    def pen_width(self):
        return self.flow_theme().exec_conn_width

    def get_pen(self):
        theme = self.flow_theme()
        pen = QPen(theme.exec_conn_color, theme.exec_conn_width)
        pen.setStyle(theme.exec_conn_pen_style)
        pen.setCapStyle(Qt.RoundCap)
        return pen

    def get_style_color(self):
        return self.flow_theme().exec_conn_color


class DataConnectionItem(ConnectionItem):
    def pen_width(self):
        return self.flow_theme().data_conn_width

    def get_pen(self):
        theme = self.flow_theme()
        pen = QPen(theme.data_conn_color, theme.data_conn_width)
        pen.setStyle(theme.data_conn_pen_style)
        pen.setCapStyle(Qt.RoundCap)
        return pen

    def get_style_color(self):
        return self.flow_theme().data_conn_color


def default_cubic_connection_path(p1: QPointF, p2: QPointF):
    """Returns the nice looking QPainterPath from p1 to p2"""

    path = QPainterPath()

    path.moveTo(p1)

    dx = p2.x() - p1.x()
    adx = abs(dx)
    dy = p2.y() - p1.y()
    ady = abs(dy)
    distance = sqrt((dx**2) + (dy**2))
    x1, y1 = p1.x(), p1.y()
    x2, y2 = p2.x(), p2.y()

    if ((x1 < x2 - 30) or distance < 100) and (x1 < x2):
        # STANDARD FORWARD
        path.cubicTo(x1 + ((x2 - x1) / 2), y1,
                     x1 + ((x2 - x1) / 2), y2,
                     x2, y2)
    elif x2 < x1 - 100 and adx > ady * 2:
        # STRONG BACKWARDS
        path.cubicTo(x1 + 100 + (x1 - x2) / 10, y1,
                     x1 + 100 + (x1 - x2) / 10, y1 + (dy / 2),
                     x1 + (dx / 2), y1 + (dy / 2))
        path.cubicTo(x2 - 100 - (x1 - x2) / 10, y2 - (dy / 2),
                     x2 - 100 - (x1 - x2) / 10, y2,
                     x2, y2)
    else:
        # STANDARD BACKWARDS
        path.cubicTo(x1 + 100 + (x1 - x2) / 3, y1,
                     x2 - 100 - (x1 - x2) / 3, y2,
                     x2, y2)

    return path


class ConnPathItemsAnimation(QGraphicsObject):
    """
    Animates items over the path of a connection by updating their positions.
    When the path of the connection changes, recompute() needs to be called.
    The animation can be toggled on and off.
    """

    def __init__(
        self,
        items: list[QGraphicsItem],
        connection,
        frames=100,
        between=125,
        speed=0.15,
    ):
        super().__init__()
        
        self.items: list[QGraphicsItemAnimated] = [
            QGraphicsItemAnimated(item, self) 
            for item in items
        ]
        self.connection = connection
        self.between = between
        self.speed = speed
        self.visible_items = []
        self.__visible_flag = True
        
        self.setParentItem(self.connection)
        
        self.timeline = QTimeLine()
        self.timeline.setFrameRange(0, frames)
        self.timeline.setEasingCurve(QEasingCurve.Type.Linear)
        self.timeline.valueChanged.connect(self._update_items)
        self.timeline.setLoopCount(0)

    def boundingRect(self):
        return self.connection.boundingRect()
    
    def paint(self, painter, option, widget):
        pass
    
    def toggle(self, recompute: bool = False):
        """Toggles the path animation. Returns True if toggled on, otherwise False"""

        state = self.timeline.state()
        running = False
        if state == QTimeLine.NotRunning:
            self.timeline.start()
            running = True
        elif state == QTimeLine.Paused:
            self.timeline.resume()
            running = True
        else:
            running = False
            self.timeline.setPaused(True)
        
        if recompute:
            self.recompute()
        return running
    
    def start(self, recompute: bool = True):
        self.timeline.start()
        if recompute:
            self.recompute()

    def stop(self, recompute: bool = True):
        self.timeline.stop()
        if recompute:
            self.recompute()

    def recompute(self):
        
        if self.__visible_flag:
            for item in self.items:
                item.setVisible(False)
            self.__visible_flag = False

        if self.timeline.state() == QTimeLine.State.NotRunning:
            return
        
        self.__visible_flag = True

        path_len = self.connection.path().length()
        num_points = max(3, min(self.connection.num_dots, int(path_len / self.between)))

        self.timeline.setDuration(path_len / self.speed)
        self.visible_items = []

        for i in range(1, num_points + 1):
            percent = i / num_points
            item = self.items[i - 1]
            self.visible_items.append((item, percent))
            item.setVisible(True)
            item.item.setPen(QPen(self.connection.get_style_color(), self.connection.pen_width()))
            item.item.setBrush(QBrush(self.connection.get_style_color()))

    def _update_items(self, percent):
        for item, item_percent in self.visible_items:
            p = percent + item_percent
            if p > 1:
                p = p - 1
            item.setPos(self.connection.path().pointAtPercent(p))

    def _pause(self, paused: bool, recompute: bool = True):
        self.timeline.setPaused(paused)
        if recompute:
            self.recompute()

    def _state(self):
        return self.timeline.state()
    

class ConnPathItemsAnimationScaled:
    """
    Wraps a ConnPathItemsAnimation and adds a scale animation to it.
    """

    class State(Enum):
        NOT_RUNNING = 0
        RUNNING = 1
        TO_SCALE = 2
        TO_ZERO = 3
    
    def __init__(
        self,
        items_animation: ConnPathItemsAnimation,
        duration: int = 750, 
        scale: int = 1, 
    ) -> None:
        
        self.con_items_anim = items_animation
        self.duration = duration
        self.scalar = scale
        self.to_scalar_group = QParallelAnimationGroup()
        self.to_zero_group = QParallelAnimationGroup()
        self.state = ConnPathItemsAnimationScaled.State.NOT_RUNNING
        
        for item in self.con_items_anim.items:
            item.setScale(0)
            # to scaler
            to_scalar_anim = QPropertyAnimation(item, b'scale')
            to_scalar_anim.setDuration(self.duration)
            self.to_scalar_group.addAnimation(to_scalar_anim)
            # to zero
            to_zero_anim = QPropertyAnimation(item, b'scale')
            to_zero_anim.setDuration(self.duration)
            self.to_zero_group.addAnimation(to_zero_anim)

        self.to_scalar_group.finished.connect(self._on_scalar_ended)
        self.to_zero_group.finished.connect(self._on_zero_ended)
    
    def start(self):
        if (self.state == ConnPathItemsAnimationScaled.State.NOT_RUNNING or 
            self.state == ConnPathItemsAnimationScaled.State.TO_ZERO):
            self.toggle()
    
    def stop(self):
        if (self.state == ConnPathItemsAnimationScaled.State.RUNNING or
            self.state == ConnPathItemsAnimationScaled.State.TO_SCALE):
            self.toggle()
            
    def toggle(self):
        if self.state == ConnPathItemsAnimationScaled.State.NOT_RUNNING:
            self._run_scalar()
            self.con_items_anim.start()
            self.state = ConnPathItemsAnimationScaled.State.TO_SCALE
        elif self.state == ConnPathItemsAnimationScaled.State.RUNNING:
            self._run_zero()
            self.state = ConnPathItemsAnimationScaled.State.TO_ZERO
        elif self.state == ConnPathItemsAnimationScaled.State.TO_SCALE:
            self.to_scalar_group.stop()
            self._run_zero()
            self.state = ConnPathItemsAnimationScaled.State.TO_ZERO
        else:
            self.to_zero_group.stop()
            self._run_scalar()
            self.state = ConnPathItemsAnimationScaled.State.TO_SCALE
    
    def force_stop(self):
        self.to_zero_group.stop()
        self.to_scalar_group.stop()
    
    def _run_scalar(self):
        self._run_animation(self.to_scalar_group, self.scalar)
    
    def _run_zero(self):
        self._run_animation(self.to_zero_group, 0)
        
    def _run_animation(self, group: QParallelAnimationGroup, end_value):
        for i in range(group.animationCount()):
            anim: QPropertyAnimation = group.animationAt(i)
            target: QGraphicsItem = anim.targetObject()
            anim.setKeyValues([(0, target.scale()), (1, end_value)])
        group.start()
    
    def _on_scalar_ended(self):
        self.state = ConnPathItemsAnimationScaled.State.RUNNING
    
    def _on_zero_ended(self):
        if self.state == ConnPathItemsAnimationScaled.State.TO_ZERO:
            self.con_items_anim.stop()
        self.state = ConnPathItemsAnimationScaled.State.NOT_RUNNING