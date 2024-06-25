from __future__ import annotations

import traceback

from qtpy.QtWidgets import (
    QGraphicsItem, 
    QGraphicsObject, 
    QMenu, 
    QGraphicsDropShadowEffect,
    QGraphicsWidget,
    QGraphicsLinearLayout,
    QSizePolicy,
    QAction,
    QGraphicsLayoutItem,
    QGraphicsPixmapItem,
)
from qtpy.QtCore import (
    Qt, 
    QRectF, 
    QObject, 
    QPointF, 
    Signal,
    QSizeF, 
    QSize,
    QPropertyAnimation,
    QParallelAnimationGroup,
    Property,
)
from qtpy.QtGui import (
    QFont, 
    QPixmap,
    QImage,
    QColor,
)

from .gui import NodeGUI
from ..gui_base import GUIBase

from cognixcore import (
    Node,
    NodeInput,
    NodeOutput,
    ProgressState,
    IdentifiableGroups,
    NodeAction,
)

from ..utils import (
    serialize, 
    deserialize, 
    MovementEnum, 
    generate_name, 
    change_svg_color, 
    get_resource
)

from ..ports.item import InputPortItem, OutputPortItem
from ..util_widgets import GraphicsProgressBar, GraphicsTextWidget
from ..design import Design
from ..flows.widget_proxies import FlowViewProxyWidget

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..flows.view import FlowView


class NodeErrorIndicator(GUIBase, QGraphicsPixmapItem):

    def __init__(self, node_item):
        GUIBase.__init__(self)
        QGraphicsPixmapItem.__init__(self, parent=node_item)

        self.node = node_item
        self.pix = QPixmap(str(get_resource('pics/warning.png')))
        self.setPixmap(self.pix)
        self.setScale(0.1)
        self.setOffset(-self.boundingRect().width()/2, -self.boundingRect().width()/2)

    def set_error(self, e):
        error_msg = ''.join([
            f'<p>{line}</p>'
            for line in traceback.format_exc().splitlines()
        ])

        self.setToolTip(
            f'<html><head/><body>'
            f'{error_msg}'
            f'</body></html>'
        )

class NodeItem_CollapseButton(QGraphicsWidget):
    def __init__(self, node_gui: 'NodeGUI', node_item: 'NodeItem'):
        super().__init__(parent=node_item)

        self.node_gui = node_gui
        self.node_item = node_item

        self.icon_size = QSizeF(14, 7)

        self.setGraphicsItem(self)
        self.setCursor(Qt.PointingHandCursor)


        self.collapse_pixmap = change_svg_color(
            get_resource('node_collapse_icon.svg'),
            self.node_gui.color
        )
        self.expand_pixmap = change_svg_color(
            get_resource('node_expand_icon.svg'),
            self.node_gui.color
        )


    def boundingRect(self):
        return QRectF(QPointF(0, 0), self.icon_size)

    def setGeometry(self, rect):
        self.prepareGeometryChange()
        QGraphicsLayoutItem.setGeometry(self, rect)
        self.setPos(rect.topLeft())

    def sizeHint(self, which, constraint=...):
        return QSizeF(self.icon_size.width(), self.icon_size.height())

    def mousePressEvent(self, event):
        event.accept()  # make sure the event doesn't get passed on
        self.node_item.flow_view.mouse_event_taken = True

        if self.node_item.collapsed:
            self.node_item.expand()
        else:
            self.node_item.collapse()

    # def hoverEnterEvent(self, event):

    def paint(self, painter, option, widget=None):

        # doesn't work: ...
        # painter.setRenderHint(QPainter.Antialiasing, True)
        # painter.setRenderHint(QPainter.HighQualityAntialiasing, True)
        # painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        if not self.node_item.hovered:
            return

        if self.node_item.collapsed:
            pixmap = self.expand_pixmap
        else:
            pixmap = self.collapse_pixmap

        painter.drawPixmap(
            0, 0,
            self.icon_size.width(), self.icon_size.height(),
            pixmap
        )
        
        
class NodeItem_Icon(QGraphicsWidget):
    def __init__(self, node_gui: 'NodeGUI', node_item: 'NodeItem'):
        super().__init__(parent=node_item)

        self.icon_size = QSize(20, 20) if node_gui.style == 'normal' else QSize(50, 50)

        image = QImage(node_gui.icon)
        self.pixmap = QPixmap.fromImage(image)
        # self.pixmap = change_svg_color(node.icon, node.color)


    def boundingRect(self):
        return QRectF(QPointF(0, 0), self.icon_size)

    def setGeometry(self, rect):
        self.prepareGeometryChange()
        QGraphicsLayoutItem.setGeometry(self, rect)
        self.setPos(rect.topLeft())

    def sizeHint(self, which, constraint=...):
        return QSizeF(self.icon_size.width(), self.icon_size.height())

    def paint(self, painter, option, widget=None):

        # TODO: anti aliasing for node icons
        
        # this doesn't work: ...
        # painter.setRenderHint(QPainter.Antialiasing, True)
        # painter.setRenderHint(QPainter.HighQualityAntialiasing, True)
        # painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        painter.drawPixmap(
            0, 0,
            self.icon_size.width(), self.icon_size.height(),
            self.pixmap
        )
    
    
class NodeItemWidget(QGraphicsWidget):
    """The QGraphicsWidget managing all GUI components of a NodeItem in widgets and layouts."""

    def __init__(self, node_gui: 'NodeGUI', node_item: 'NodeItem'):
        super().__init__(parent=node_item)

        self.node_gui = node_gui
        self.node_item = node_item
        self.flow_view = self.node_item.flow_view
        self.flow = self.flow_view.flow

        self.body_padding = 6
        self.header_padding = (0, 0, 0, 0)  # theme dependent and hence updated in setup_layout()!

        self.icon = NodeItem_Icon(node_gui, node_item) if node_gui.icon else None
        self.collapse_button = NodeItem_CollapseButton(node_gui, node_item)
        
        # title
        self.title_label = GraphicsTextWidget()
        self.title_label.set_font(
            QFont('Poppins', 15) if self.node_gui.style == 'normal' else
            QFont('K2D', 20, QFont.Bold, True)
        )
        
        self.max_title_length_normal = 30
        self.max_title_length_small = 12
        
        self.main_widget_proxy: FlowViewProxyWidget = None
        if self.node_item.main_widget:
            self.main_widget_proxy = FlowViewProxyWidget(self.flow_view)
            self.main_widget_proxy.setWidget(self.node_item.main_widget)
        self.header_layout: QGraphicsWidget = None
        self.header_widget: QGraphicsWidget = None
        self.body_layout: QGraphicsLinearLayout = None
        self.body_widget: QGraphicsWidget = None
        self.inputs_layout: QGraphicsLinearLayout = None
        self.outputs_layout: QGraphicsLinearLayout = None
        
        # layout
        self.min_size = QSize(150, 30) if node_gui.style == 'normal' else QSize(115, 40)
        self.setLayout(self.setup_layout())

    def setup_layout(self) -> QGraphicsLinearLayout:

        self.header_padding = self.node_item.session_design.flow_theme.header_padding

        #   main layout
        layout = QGraphicsLinearLayout(Qt.Vertical)
        layout.setMinimumSize(self.min_size)
        layout.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header_widget = QGraphicsWidget()
        self.header_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.header_layout = QGraphicsLinearLayout(Qt.Horizontal)
        self.header_widget.setLayout(self.header_layout)
        
        self.header_layout.setSpacing(5)
        self.header_layout.setContentsMargins(
            *self.header_padding
        )
        
        if self.icon:
            self.header_layout.addItem(self.icon)
            self.header_layout.setAlignment(
                self.icon, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
            )

        self.header_layout.addItem(self.title_label)
        
        self.header_layout.addItem(self.collapse_button)
        self.header_layout.setAlignment(
            self.collapse_button, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
        )
        
        layout.addItem(self.header_widget)
        layout.setAlignment(self.header_widget, Qt.AlignmentFlag.AlignHCenter)
            
        #   inputs
        self.inputs_layout = QGraphicsLinearLayout(Qt.Vertical)
        self.inputs_layout.setSpacing(2)

        #   outputs
        self.outputs_layout = QGraphicsLinearLayout(Qt.Vertical)
        self.outputs_layout.setSpacing(2)

        #   body
        self.body_widget = QGraphicsWidget()
        self.body_layout = QGraphicsLinearLayout(Qt.Horizontal)
        self.body_layout.setContentsMargins(
            self.body_padding,
            self.body_padding,
            self.body_padding,
            self.body_padding
        )

        self.body_layout.setSpacing(4)
        self.body_layout.addItem(self.inputs_layout)
        self.body_layout.setAlignment(self.inputs_layout, Qt.AlignVCenter | Qt.AlignLeft)
        self.body_layout.addStretch()
        self.body_layout.addItem(self.outputs_layout)
        self.body_layout.setAlignment(self.outputs_layout, Qt.AlignVCenter | Qt.AlignRight)

        self.body_widget.setLayout(self.body_layout)

        layout.addItem(self.body_widget)

        return layout

    def rebuild_ui(self):
        """Due to some really strange and annoying behaviour of these QGraphicsWidgets, they don't want to shrink
        automatically when content is removed, they just stay large, even with a Minimum SizePolicy. I didn't find a
        way around that yet, so for now I have to recreate the whole layout and make sure the widget uses the smallest
        size possible."""

        self.setLayout(self.setup_layout())
        
        if self.node_item.collapsed:
            return

        for inp_item in self.node_item.inputs:
            self.add_input_to_layout(inp_item)
        for out_item in self.node_item.outputs:
            self.add_output_to_layout(out_item)

        if self.node_item.main_widget:
            self.add_main_widget_to_layout()

    def update_shape(self):
        
        for inp in self.node_item.inputs:
            inp.update()
        
        for out in self.node_item.outputs:
            out.update()
        
        # truncate the title if it's too big
        display_title = title = self.node_gui.title()
        max_title_length = (
            self.max_title_length_normal 
            if self.node_gui.style == 'normal' 
            else self.max_title_length_small
        )
        if len(display_title) > max_title_length:
            display_title = f'{title[0:max_title_length]}...'
        
        self.title_label.setToolTip(title)
            
        self.node_item.session_design.flow_theme.setup_NI_title_label(
            self.title_label,
            self.isSelected(),
            self.node_item.hovered,
            self.node_gui.style,
            display_title,
            self.node_item.color,
        )

        # makes extended node items shrink according to resizing input widgets
        if not self.node_item.initializing:
            self.rebuild_ui()
            
        mw = self.node_item.main_widget
        if mw is not None:  # maybe the main_widget got resized
            
            self.main_widget_proxy.setMaximumSize(QSizeF(mw.size()))
            self.main_widget_proxy.setMinimumSize(QSizeF(mw.size()))

        self.adjustSize()

        self.body_layout.invalidate()
        self.layout().invalidate()
        self.layout().activate()
        # very essential; repositions everything in case content has changed (inputs/outputs/widget)

        w = self.boundingRect().width()
        h = self.boundingRect().height()
        rect = QRectF(QPointF(-w / 2, -h / 2),
                      QPointF(w / 2, h / 2))
        self.setPos(rect.left(), rect.top())

    def add_main_widget_to_layout(self):
        if self.node_gui.main_widget_pos == 'between ports':
            self.body_layout.insertItem(1, self.main_widget_proxy)
            self.body_layout.insertStretch(2)

        elif self.node_gui.main_widget_pos == 'below ports':
            self.layout().addItem(self.main_widget_proxy)
            self.layout().setAlignment(self.main_widget_proxy, Qt.AlignHCenter)

    def add_input_to_layout(self, inp: InputPortItem):
        if self.inputs_layout.count() > 0:
            self.inputs_layout.addStretch()
        self.inputs_layout.addItem(inp)
        self.inputs_layout.setAlignment(inp, Qt.AlignLeft)

    def insert_input_into_layout(self, index: int, inp: InputPortItem):
        self.inputs_layout.insertItem(index * 2 + 1, inp)  # *2 bcs of the stretches
        self.inputs_layout.setAlignment(inp, Qt.AlignLeft)
        if len(self.node_gui.node._inputs) > 1:
            self.inputs_layout.insertStretch(index * 2 + 1)  # *2+1 because of the stretches, too

    def remove_input_from_layout(self, inp: InputPortItem):
        self.inputs_layout.removeItem(inp)

        # just a temporary workaround for the issues discussed here:
        # https://forum.qt.io/topic/116268/qgraphicslayout-not-properly-resizing-to-change-of-content
        self.rebuild_ui()

    def add_output_to_layout(self, out: OutputPortItem):
        if self.outputs_layout.count() > 0:
            self.outputs_layout.addStretch()
        self.outputs_layout.addItem(out)
        self.outputs_layout.setAlignment(out, Qt.AlignRight)

    def insert_output_into_layout(self, index: int, out: OutputPortItem):
        self.outputs_layout.insertItem(index * 2 + 1, out)  # *2 because of the stretches
        self.outputs_layout.setAlignment(out, Qt.AlignRight)
        if len(self.node_gui.node._outputs) > 1:
            self.outputs_layout.insertStretch(index * 2 + 1)  # *2+1 because of the stretches, too

    def remove_output_from_layout(self, out: OutputPortItem):
        self.outputs_layout.removeItem(out)

        # just a temporary workaround for the issues discussed here:
        # https://forum.qt.io/topic/116268/qgraphicslayout-not-properly-resizing-to-change-of-content
        self.rebuild_ui()

    def collapse(self):
        self.body_widget.hide()
        if self.main_widget_proxy:
            self.main_widget_proxy.hide()

    def expand(self):
        self.body_widget.show()
        if self.main_widget_proxy:
            self.main_widget_proxy.show()

    def has_hidden_ports(self):
        for inp in self.node_item.inputs:
            if inp.isVisible():
                return False
        for out in self.node_item.outputs:
            if out.isVisible():
                return False
        return True
    
    def hide_unconnected_ports(self):
        for inp in self.node_item.inputs:
            if self.flow.connected_output(inp.port) is None:
                inp.hide()
        for out in self.node_item.outputs:
            if len(self.flow.connected_inputs(out.port)) == 0:
                out.hide()

    def show_unconnected_ports(self):
        for inp in self.node_item.inputs:
            inp.show()
        for out in self.node_item.outputs:
            out.show()
            

class NodeItemAnimator(QObject):

    def __init__(self, node_item: NodeItem):
        super(NodeItemAnimator, self).__init__()

        self.node_item = node_item
        self.animation_running = False

        # title color
        self.title_activation_animation = QPropertyAnimation(self, b"p_title_color")
        self.title_activation_animation.setDuration(700)
        # body color
        self.body_activation_animation = QPropertyAnimation(self, b"p_body_color")
        self.body_activation_animation.setDuration(700)
        # transform
        self.scale_animation = QPropertyAnimation(self.node_item, b'scale')
        self.scale_animation.setDuration(700)
        self.scalar = 1.05
        
        self.animation = QParallelAnimationGroup()
        self.animation.addAnimation(self.title_activation_animation)
        self.animation.addAnimation(self.body_activation_animation)
        self.animation.addAnimation(self.scale_animation)
        self.animation.finished.connect(self.finished)

    def start(self):
        self.animation_running = True
        self.animation.start()

    def stop(self):
        # reset color values. it would just freeze without
        self.title_activation_animation.setCurrentTime(self.title_activation_animation.duration())
        self.body_activation_animation.setCurrentTime(self.body_activation_animation.duration())
        self.scale_animation.setCurrentTime(self.scale_animation.duration())
        
        self.animation.stop()

    def finished(self):
        self.animation_running = False

    def running(self):
        return self.animation_running

    def reload_values(self):
        self.stop()

        # self.node_item.title_label.update_design()
        self.title_activation_animation.setKeyValueAt(0, self.get_title_color())
        self.title_activation_animation.setKeyValueAt(0.3, self.get_body_color().lighter().lighter())
        self.title_activation_animation.setKeyValueAt(1, self.get_title_color())

        self.body_activation_animation.setKeyValueAt(0, self.get_body_color())
        self.body_activation_animation.setKeyValueAt(0.3, self.get_body_color().lighter())
        self.body_activation_animation.setKeyValueAt(1, self.get_body_color())
        
        self.scale_animation.setKeyValueAt(0, 1)
        self.scale_animation.setKeyValueAt(0.3, self.scalar)
        self.scale_animation.setKeyValueAt(1, 1)

    def fading_out(self):
        return self.title_activation_animation.currentTime()/self.title_activation_animation.duration() >= 0.3

    def set_animation_max(self):
        self.title_activation_animation.setCurrentTime(0.3*self.title_activation_animation.duration())
        self.body_activation_animation.setCurrentTime(0.3*self.body_activation_animation.duration())

    # BODY COLOR
    def get_body_color(self):
        return self.node_item.color

    def set_body_color(self, val):
        self.node_item.color = val
        QGraphicsItem.update(self.node_item)

    p_body_color = Property(QColor, get_body_color, set_body_color)

    # TITLE COLOR
    def get_title_color(self):
        return self.node_item.widget.title_label.default_text_color()
        
    def set_title_color(self, val):
        self.node_item.widget.title_label.set_default_text_color(val)
        
    p_title_color = Property(QColor, get_title_color, set_title_color)
    
           
class NodeItem(GUIBase, QGraphicsObject):  # QGraphicsItem, QObject):
    """The GUI representative for nodes. Unlike the Node class, this class is not subclassed individually and works
    the same for every node."""

    def __init__(self, node: Node, node_gui: NodeGUI, flow_view: FlowView, design: Design):
        GUIBase.__init__(self, representing_component=node)
        QGraphicsObject.__init__(self)

        self.node = node
        self.node_gui = node_gui
        self.node_gui.item = self
        self.flow_view: FlowView = flow_view
        self.session_design = design
        self.movement_state = None
        self.movement_pos_from = None
        self.painted_once = False
        self.inputs: list[InputPortItem] = []
        self.outputs: list[OutputPortItem] = []
        self.color = QColor(self.node_gui.color)  # manipulated by self.animator
        self.progress_state: ProgressState = None

        self.collapsed = False
        self.hovered = False
        self.hiding_unconnected_ports = False
        self.displaying_error = False

        self.personal_logs = []

        # 'initializing' will be set to False below. It's needed for the ports setup, to prevent shape updating stuff
        self.initializing = True

        # self.temp_state_data = None
        self.init_data = self.node.load_data

        # CONNECT TO NODE
        self.node_gui.updating.connect(self.node_updating)
        self.node_gui.update_shape_triggered.connect(self.update_shape)
        self.node_gui.hide_unconnected_ports_triggered.connect(self.hide_unconnected_ports_triggered)
        self.node_gui.show_unconnected_ports_triggered.connect(self.show_unconnected_ports_triggered)
        self.node_gui.input_added.connect(self.on_node_input_added)
        self.node_gui.output_added.connect(self.on_node_output_added)
        self.node_gui.input_removed.connect(self.on_node_input_removed)
        self.node_gui.output_removed.connect(self.on_node_output_removed)
        self.node_gui.input_renamed.connect(self.on_node_input_renamed)
        self.node_gui.output_renamed.connect(self.on_node_output_renamed)

        # FLAGS
        self.setFlags(
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemSendsScenePositionChanges
        )

        self.setAcceptHoverEvents(True)
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)

        # Progress Bar and Message
        self.top_section_widget = QGraphicsWidget(parent=self)
        self.top_section_widget.setVisible(False)
        top_section_layout = QGraphicsLinearLayout(Qt.Vertical)
        top_section_layout.setContentsMargins(0, 0, 0 , 0)
        self.top_section_widget.setLayout(top_section_layout)
        
        self.message = GraphicsTextWidget()
        self.message.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        top_section_layout.addItem(self.message)
        
        self.progress_bar = GraphicsProgressBar()
        top_section_layout.addItem(self.progress_bar)
        
        self.node_gui.progress_updated.connect(self._on_progress_updated)
        
        # Node UI
        self.shadow_effect = None
        self.main_widget = None
        if self.node_gui.main_widget_class is not None:
            self.main_widget = self.node_gui.main_widget_class((self.node, self, self.node_gui))
        self.widget = NodeItemWidget(self.node_gui, self)  # QGraphicsWidget(self)
        self.animator = NodeItemAnimator(self)  # needs self.title_label
        self.error_indicator = NodeErrorIndicator(self)
        self.error_indicator.hide()

        # TOOLTIP
        self.tooltip_descr_html_content = \
            self.node_gui.description_html \
            if self.node_gui.description_html is not None \
            else \
            f'<p>{self.node.__doc__}</p>'

        self.setToolTip(f'<html><head/><body>{self.tooltip_descr_html_content}</body></html>')

        # DESIGN THEME
        self.session_design.flow_theme_changed.connect(self.update_design)
        self.session_design.performance_mode_changed.connect(self.update_design)

    def initialize(self):
        """All ports and the main widget get finally created here."""

        # LOADING DATA
        if self.init_data is not None:
            if self.main_widget:
                try:
                    self.main_widget.set_state(deserialize(self.init_data['main widget data']))
                except Exception as e:
                    print('Exception while setting data in', self.node.title, 'Node\'s main widget:', e,
                          ' (was this intended?)')

        # catch up on init ports
        for inp in self.node._inputs:
            self.add_new_input(inp)

        for out in self.node._outputs:
            self.add_new_output(out)

        if self.init_data is not None:
            if self.init_data.get('unconnected ports hidden'):
                self.hide_unconnected_ports_triggered()
            if self.init_data.get('collapsed'):
                self.collapse()

        if self.init_data is not None:
            self.node_gui.load(self.init_data)

        self.node_gui.initialized()

        self.initializing = False

        # No self.update_shape() here because for some reason, the bounding rect hasn't been initialized yet, so
        # self.update_shape() gets called when the item is being drawn the first time (see paint event in NI painter)
        # https://forum.qt.io/topic/117179/force-qgraphicsitem-to-update-immediately-wait-for-update-event

        self.update_design()  # load current design, update QGraphicsItem

        self.update()  # ... not sure if I need that

    def __str__(self):
        name = self.node.__class__.title if self.node else f'{NodeItem.__name__}'
        obj = self.node if self.node else self
        return generate_name(obj, name)
    
    def has_hidden_ports(self):
        for inp in self.inputs:
            if not inp.isVisible():
                return False
        for out in self.outputs:
            if not out.isVisible():
                return False
        return True
    
    # EVENTS
    
    def _on_progress_updated(self, p_state: ProgressState):
        self.progress_state = p_state
        self.top_section_widget.setVisible(p_state is not None)
        
        if not p_state:
            # stop any potential animations
            self.progress_bar.stop_animation()
            return
        
        # message
        message = self.progress_state.message
        if message is not None and message != '':
            self.message.setVisible(True)
            self.message.set_text(message)
        else:
            self.message.setVisible(False)
            
        # progress
        self.progress_bar.setVisible(self.session_design.flow_theme.use_progress_bar and self.progress_state is not None)
        if not self.progress_state.is_indefinite():
            self.progress_bar.set_progress_values(self.progress_state.percentage(), 0)
        else:
            self.progress_bar.play_animation(1/3, 2, 50)
        
        self.update()
    
    # UI STUFF

    def node_updating(self):
        if self.session_design.node_animation_enabled:
            if not self.animator.running():
                self.animator.start()
            elif self.animator.fading_out():
                self.animator.set_animation_max()
            
            self.update()

    def display_error(self, e):
        self.error_indicator.set_error(e)
        self.error_indicator.show()
        self.displaying_error = True

    def remove_error_message(self):
        self.error_indicator.hide()
        self.setToolTip(f'<html><head/><body>{self.tooltip_descr_html_content}</body></html>')

    def set_tooltip(self, error_msg=None):

        if error_msg is not None:
            err = f'<p style="background: red; color: white">{error_msg}</p>'
        else:
            err = ''

        if self.node.description_html:
            html = self.node.description_html + f'<html><head/><body>{err}</body></html>'
        elif self.node.__doc__:
            html = f'<html><head/><body><p>{self.node.__doc__}</p>{err}</body></html>'

        self.setToolTip(html)
        self.setCursor(Qt.SizeAllCursor)

    def on_node_input_added(self, index, inp: NodeInput):
        insert = index if index == len(self.node._inputs) - 1 else None
        self.add_new_input(inp, insert)

    def add_new_input(self, inp: NodeInput, insert: int = None):

        if inp in self.node_gui.input_widgets:
            widget_name = self.node_gui.input_widgets[inp]['name']
            widget_class = self.node_gui.input_widget_classes[widget_name]
            widget_pos = self.node_gui.input_widgets[inp]['pos']
            widget = (widget_class, widget_pos)
        else:
            widget = None

        # create item
        item = InputPortItem(self.node_gui, self, inp, input_widget=widget)

        if insert is not None:
            self.inputs.insert(insert, item)
            self.widget.insert_input_into_layout(insert, item)
        else:
            self.inputs.append(item)
            self.widget.add_input_to_layout(item)

        if not self.initializing:
            self.update_shape()
            self.update()

    def on_node_input_removed(self, index, inp: NodeInput):
        self.remove_input(index, inp)

    def on_node_input_renamed(self, index: int, inp: NodeInput, old_name: str):
        self.inputs[index].update()
        self.update()
        
    def remove_input(self, index: int, inp: NodeInput):
        item = self.inputs[index]
        
        # for some reason, I have to remove all widget items manually from the scene too. setting the items to
        # ownedByLayout(True) does not work, I don't know why.
        self.scene().removeItem(item.pin)
        self.scene().removeItem(item.label)
        if item.proxy is not None:
            self.scene().removeItem(item.proxy)

        self.inputs.remove(item)
        self.widget.remove_input_from_layout(item)

        if not self.initializing:
            self.update_shape()
            self.update()

    def on_node_output_added(self, index, out: NodeOutput):
        insert = index if index == len(self.node._outputs) - 1 else None
        self.add_new_output(out, insert)

    def add_new_output(self, out: NodeOutput, insert: int = None):

        # create item
        # out.item = OutputPortItem(out.node, self, out)
        item = OutputPortItem(self.node_gui, self, out)

        if insert is not None:
            self.outputs.insert(insert, item)
            self.widget.insert_output_into_layout(insert, item)
        else:
            self.outputs.append(item)
            self.widget.add_output_to_layout(item)

        if not self.initializing:
            self.update_shape()
            self.update()

    def on_node_output_removed(self, index, out: NodeOutput):
        self.remove_output(index, out)
    
    def on_node_output_renamed(self, index: int, out: NodeOutput, old_name: str):
        self.outputs[index].update()
        self.update_shape()

    def remove_output(self, index: int, out: NodeOutput):
        item = self.outputs[index]
        
        # see remove_input() for info!
        self.scene().removeItem(item.pin)
        self.scene().removeItem(item.label)

        self.outputs.remove(item)
        self.widget.remove_output_from_layout(item)

        if not self.initializing:
            self.update_shape()
            self.update()

    def update_shape(self):
        self.widget.update_shape()
        self.update_conn_pos()
        self.flow_view.viewport().update()
        
    def update_design(self):
        """Loads the shadow effect option and causes redraw with active theme."""
        self.progress_bar.setVisible(
            self.session_design.flow_theme.use_progress_bar
        )
        
        t_color = (
            QColor(185, 185, 185)
            if self.session_design.flow_theme.type_ == "dark"
            else QColor(40, 40, 40)
        )
        self.progress_bar.text_color = t_color
        self.message.set_default_text_color(t_color)
        
        if self.session_design.node_item_shadows_enabled:
            self.shadow_effect = QGraphicsDropShadowEffect()
            self.shadow_effect.setXOffset(12)
            self.shadow_effect.setYOffset(12)
            self.shadow_effect.setBlurRadius(20)
            self.shadow_effect.setColor(self.session_design.flow_theme.node_item_shadow_color)
            self.setGraphicsEffect(self.shadow_effect)
        else:
            self.setGraphicsEffect(None)

        self.widget.update_shape()
        self.animator.reload_values()

        QGraphicsItem.update(self)

    def boundingRect(self):
        # remember: (0, 0) shall be the NI's center!
        rect = QRectF()
        w = self.widget.layout().geometry().width()
        h = self.widget.layout().geometry().height()
        rect.setLeft(-w / 2)
        rect.setTop(-h / 2)
        rect.setWidth(w)
        rect.setHeight(h)
        return rect

    def get_left_body_header_vertex_scene_pos(self):
        return self.mapToScene(
            QPointF(
                -self.boundingRect().width() / 2,
                -self.boundingRect().height() / 2 + self.widget.header_widget.rect().height()
            )
        )

    def get_right_body_header_vertex_scene_pos(self):
        return self.mapToScene(
            QPointF(
                +self.boundingRect().width() / 2,
                -self.boundingRect().height() / 2 + self.widget.header_widget.rect().height()
            )
        )

    def hide_unconnected_ports_triggered(self):
        self.widget.hide_unconnected_ports()
        self.hiding_unconnected_ports = True
        self.update_shape()

    def show_unconnected_ports_triggered(self):
        self.widget.show_unconnected_ports()
        self.hiding_unconnected_ports = False
        self.update_shape()

    def expand(self):
        self.collapsed = False
        self.widget.expand()
        self.update_shape()

    def collapse(self):
        self.collapsed = True
        self.widget.collapse()
        self.update_shape()

    #   PAINTING
        
    def paint(self, painter, option, widget=None):
        """All painting is done by NodeItemPainter"""
        
        b_rect = self.boundingRect()
        # in order to access a meaningful geometry of GraphicsWidget contents in update_shape(), the paint event
        # has to be called once.
        # https://forum.qt.io/topic/117179/force-qgraphicsitem-to-update-immediately-wait-for-update-event/4
        if not self.painted_once:
            # Since I am using a NodeItemWidget, calling self.update_design() here (again)
            # leads to a QT crash without error, which is strange. In principle, calling update_design multiple times
            # shouldn't be a problem. It's not necessary anymore, so I removed it.
            # self.update_design()

            self.update_shape()
            self.update_conn_pos()
            self.error_indicator.setPos(b_rect.bottomRight())
        
        # Progress and message drawing
        if self.message.isVisible():
            self.message.set_text_width(b_rect.width() + 50)
            
        if self.progress_bar.isVisible():
            self.progress_bar.set_size(b_rect.width(), 20)
            h = self.top_section_widget.size().height()
            self.top_section_widget.setPos(-b_rect.width() / 2, -b_rect.height() / 2 - h - 5)       
            
        # I think calling this here is not well thought, because some functions in FlowTheme DO NOT take into
        # account potential expansions of NodeItemWidget, like the get_header... ones. Ideally, I think 
        # this should be called inside NodeItemWidget.
        n_rect = b_rect
        
        self.session_design.flow_theme.paint_NI(
            node_gui=self.node_gui,
            selected=self.isSelected(),
            hovered=self.hovered,
            node_style=self.node_gui.style,
            painter=painter,
            option=option,
            color=self.color,
            w=n_rect.width(),
            h=n_rect.height(),
            bounding_rect=n_rect,
            title_rect=self.widget.header_widget.boundingRect()
            if self.widget.header_widget
            else self.widget.title_label.boundingRect()
        )

        self.painted_once = True

    # MOUSE INTERACTION

    def mouseDoubleClickEvent(self, event):
        self.node_gui.show_viewer()
        QGraphicsObject.mouseDoubleClickEvent(self, event)
        
    def get_context_menu(self):
        menu = QMenu(self.flow_view)
        
        def add_action(name: str, menu: QMenu, action: NodeAction):
            action.update()
            if action.status == NodeAction.Status.HIDDEN:
                return
            
            menu_action = QAction(name, self)
            if action.status == NodeAction.Status.DISABLED:
                menu_action.setEnabled(False)
                
            menu_action.triggered.connect(action.invoke)
            #menu.addAction(menu_action)
            menu.addAction(menu_action)
            
                
        actions = self.node.actions
        submenu_dict: dict[str, QMenu] = {}
        submenu_dict[IdentifiableGroups.NO_PREFIX_ROOT] = menu
        
        for group, id_dict in actions.groups.items():
            if group not in submenu_dict:    
                subgroups = group.split('.')
                subgroup_name = ''
                for sub in subgroups:
                    if sub not in submenu_dict:
                        continue
                    subgroup_name = f"{subgroup_name}.{sub}" if subgroup_name else sub
                    submenu = menu.addMenu(title=sub)
                    submenu_dict[subgroup_name] = submenu
                    menu.addMenu(submenu)
            
            for name, id_action in id_dict.items():
                prefix = id_action.prefix if id_action.prefix else IdentifiableGroups.NO_PREFIX_ROOT
                action = id_action.info
                submenu = submenu_dict[prefix]
                add_action(name, submenu, action)
        
        return menu

    def itemChange(self, change, value):
        """Ensures that all connections, selection borders etc. that get drawn in the FlowView get
        constantly redrawn during a drag of the item"""

        if change == QGraphicsItem.ItemPositionChange:
            if self.session_design.performance_mode == 'pretty':
                self.flow_view.viewport().update()
            if self.movement_state == MovementEnum.mouse_clicked:
                self.movement_state = MovementEnum.position_changed

            self.update_conn_pos()

        return QGraphicsItem.itemChange(self, change, value)
    
    def on_move(self):
        self.update_conn_pos()
    
    def update_conn_pos(self):
        """Updates the scene positions of connections"""
        
        for o in self.node._outputs:
            for i in self.node.flow.connected_inputs(o):
                c_info = self.flow_view.flow.connection_info((o, i))
                if c_info not in self.flow_view.connection_items:
                    # it can happen that the connection item hasn't been
                    # created yet
                    continue

                item = self.flow_view.connection_items[c_info]
                item.recompute()
                
        for i in self.node._inputs:
            o = self.node.flow.connected_output(i)
            if not o:
                continue
            c_info = self.flow_view.flow.connection_info((o, i))
            if c_info not in self.flow_view.connection_items:
                # it can happen that the connection item hasn't been
                # created yet
                continue

            item = self.flow_view.connection_items[c_info]
            item.recompute()
            
        
    def hoverEnterEvent(self, event):
        self.hovered = True
        self.widget.update_shape()
        QGraphicsItem.hoverEnterEvent(self, event)

    def hoverLeaveEvent(self, event):
        self.hovered = False
        self.widget.update_shape()
        QGraphicsItem.hoverLeaveEvent(self, event)

    def mousePressEvent(self, event):
        """Used for Moving-Commands in FlowView - may be replaced later by a nicer determination of a moving action."""

        self.flow_view.mouse_event_taken = True

        if event.button() == Qt.LeftButton:
            self.movement_state = MovementEnum.mouse_clicked
            self.movement_pos_from = self.pos()
        return QGraphicsItem.mousePressEvent(self, event)

    def mouseReleaseEvent(self, event):
        """Used for Moving-Commands in FlowView - may be replaced later by a nicer determination of a moving action."""

        self.flow_view.mouse_event_taken = True

        if self.movement_state == MovementEnum.position_changed:
            self.flow_view._move_selected_copmonents__cmd(
                pos_diff=self.pos() - self.movement_pos_from,
                already_moved=True,
            )
        self.movement_state = None
        return QGraphicsItem.mouseReleaseEvent(self, event)

    # DATA

    def complete_data(self, data: dict) -> dict:
        """completes the node's data by adding all frontend info"""

        data['pos x'] = self.pos().x()
        data['pos y'] = self.pos().y()
        if self.main_widget:
            data['main widget data'] = serialize(self.main_widget.get_state())

        data['unconnected ports hidden'] = self.hiding_unconnected_ports
        data['collapsed'] = self.collapsed

        data = {**data, **self.node_gui.data()}

        return data
