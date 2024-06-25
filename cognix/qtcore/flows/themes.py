#
#   notice: available themes are hardcoded in Ryven for CLI; make sure to update those
#   in case of changes affecting it
#

from qtpy.QtCore import (
    Qt, 
    QPointF, 
    QPoint, 
    QRectF, 
    QMarginsF
)
from qtpy.QtGui import (
    QColor, 
    QPainter, 
    QBrush, 
    QRadialGradient, 
    QLinearGradient, 
    QPen, QPainterPath, 
    QFont, 
    QPolygon
)
from qtpy.QtWidgets import QStyleOption

from ..ports.item import PinState
from ..util_widgets import GraphicsTextWidget, TextStyle
from ..utils import pythagoras

from dataclasses import dataclass, field

def _get_color(color: str, alpha=255):
    def __get_color():
        result = QColor(color)
        result.setAlpha(alpha)
        return result
    return __get_color
    
@dataclass
class PinStyle:
    pen_width: int = 2
    
    valid_color: QColor = field(default_factory=_get_color('#0dff05', 125))
    invalid_color: QColor = field(default_factory=_get_color('#ff2605', 125))
    connected_color: QColor = field(default_factory=lambda: QColor('#c69a15'))
    disconnected_color: QColor = None
    
    margin_cut: int = 0

    __pin_colors = None
    
    @property
    def pin_colors(self) -> dict[PinState, QColor]:
        if not self.__pin_colors:
            self.__pin_colors = {
                PinState.VALID: self.valid_color,
                PinState.INVALID: self.invalid_color,
                PinState.CONNECTED: self.connected_color,
                PinState.DISCONNECTED: self.disconnected_color,
            }
        return self.__pin_colors
    
@dataclass
class DataPinStyle(PinStyle):
    """Default values for Data"""
    pen_width: int = 2
    margin_cut: int = 0


@dataclass
class ExecPinStyle(PinStyle):
    """Default values for Exec"""
    connected_color: QColor = field(default_factory=lambda: QColor("#FFFFFF"))
    pen_width: int = 0
    margin_cut: int = 0
    
    
class FlowTheme:

    name = ''
    type_ = 'dark'

    node_selection_stylesheet__base = '''
QScrollArea {
    border: 0px solid grey;
    border-radius: 0px;
}
NodeWidget {

}
'''
    use_progress_bar = True
    node_selection_stylesheet = ''

    header_padding = (10, 2, 10, 2)  # (left, top, right, botton)

    exec_conn_color = QColor('#ffffff')
    exec_conn_width = 1.5
    exec_conn_pen_style = Qt.SolidLine

    data_conn_color = QColor('#ffffff')
    data_conn_width = 1.5
    data_conn_pen_style = Qt.DashLine

    flow_background_brush = QBrush(QColor('#333333'))
    flow_background_grid = None
    flow_highlight_pen_color = QColor('#245d75')

    node_item_shadow_color = QColor('#2b2b2b')
    
    # Setting for pins
    pin_style_data = DataPinStyle()
    pin_style_exec = ExecPinStyle()
    
    # Setting for title label
    title_label_styles: dict[str, TextStyle] = {
        'normal': TextStyle(),
        'small': TextStyle(),
    }
    
    EXPORT = []

    def __init__(self):
        pass

    def load(self, data: dict):
        if data and self.name in data.keys():
            imported = {}
            for k, v in data[self.name].items():
                if v != 'default':
                    imported[k] = v
            self._load(imported)

    def _load(self, imported: dict):
        for k, v in imported.items():

            if k == 'exec connection color':
                self.exec_conn_color = self.hex_to_col(v)
            elif k == 'exec connection width':
                self.exec_conn_width = v
            elif k == 'exec connection pen style':
                self.exec_conn_pen_style = self._parse_pen_style(v)

            elif k == 'data connection color':
                self.data_conn_color = self.hex_to_col(v)
            elif k == 'data connection width':
                self.data_conn_width = v
            elif k == 'data connection pen style':
                self.data_conn_pen_style = self._parse_pen_style(v)

            elif k == 'flow background color':
                self.flow_background_brush.setColor(self.hex_to_col(v))

    def build_node_selection_stylesheet(self):
        return self.node_selection_stylesheet__base + '\n' + self.node_selection_stylesheet
    
    def setup_NI_title_label(self, text_graphic: GraphicsTextWidget, selected: bool, hovering: bool, node_style: str, 
                             node_title: str, node_color: QColor):
        pass
    
    def setup_PI_label(self, text_graphic: GraphicsTextWidget, type_: str, pin_state: PinState, 
                       label_str: str, node_color: QColor):
        
        self.setup_label(
            text_graphic,
            label_str,
            TextStyle(
                QColor('#FFFFFF') if type_ == 'exec' else node_color,
                QFont("Source Code Pro", 10, QFont.Bold)
            )
        )

    def paint_PI(self, node_gui, painter: QPainter, option: QStyleOption, node_color: QColor, type_: str, pin_state: PinState,
                 rect: QRectF):  # padding, w, h):
        self.paint_PI_default(self, node_gui, painter, option, node_color, type_, pin_state, rect)

    def paint_NI(self, node_gui,
                 selected: bool, hovered: bool, node_style: str,
                 painter: QPainter, option: QStyleOption,
                 color: QColor, w, h, bounding_rect, title_rect):

        painter.setRenderHint(QPainter.Antialiasing)

        if node_style == 'normal':
            self.draw_NI_normal(node_gui, selected, hovered, painter, color, w, h, bounding_rect, title_rect)
        elif node_style == 'small':
            self.draw_NI_small(node_gui, selected, hovered, painter, color, w, h, bounding_rect, title_rect)

    def draw_NI_normal(self, node_gui, selected: bool, hovered: bool,
                       painter: QPainter, c: QColor, w, h, bounding_rect: QRectF, title_rect: QRectF):
        pass

    def draw_NI_small(self, node_gui, selected: bool, hovered: bool,
                      painter: QPainter, c: QColor, w, h, bounding_rect: QRectF, title_rect: QRectF):
        pass

    def paint_NI_selection_border(self, ni, painter: QPainter, color: QColor, w, h, bounding_rect):
        pen = QPen(self.flow_highlight_pen_color)
        pen.setWidth(3)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        size_factor = 1.2

        rect = QRectF(bounding_rect)
        rect.setWidth(w*size_factor)
        rect.setHeight(h*size_factor)
        rect.setX(rect.x() - w*size_factor/2)
        rect.setY(rect.y() - h*size_factor/2)

        painter.drawRoundedRect(rect, 10, 10)

    @staticmethod
    def setup_label(text_item: GraphicsTextWidget, title: str, text_style: TextStyle):
        
        text_item._text_item.setPlainText(title)
        text_item.set_text_style(text_style)

    @staticmethod
    def paint_PI_label_default(painter: QPainter, label_str: str, color: QColor, font: QFont, bounding_rect: QRectF):
        painter.setBrush(Qt.NoBrush)
        pen = QPen(color)
        painter.setPen(pen)
        painter.setFont(font)
        painter.drawText(bounding_rect, Qt.AlignCenter, label_str)

    @staticmethod
    def paint_PI_default(theme, node_gui, painter: QPainter, option: QStyleOption, node_color: QColor, type_: str, pin_state: PinState,
                 rect: QRectF, use_node_color = True):
        
        theme: FlowTheme = theme
        
        pin_style = theme.pin_style_exec if type_ == 'exec' else theme.pin_style_data
        brush_color = pin_style.pin_colors.get(pin_state)
        pen_color = pin_style.connected_color
        
        # ignore the pin style's connected color and use the
        # node guis
        if type_ == 'data' and use_node_color:
            pen_color = node_color
            
            if pin_state == PinState.CONNECTED:
                brush_color = QColor(pen_color)
                brush_color.setAlpha(100)
        
        brush = QBrush(brush_color) if brush_color else Qt.NoBrush
        
        pen = (
            QPen(pen_color) 
            if pin_style.pen_width > 0
            else Qt.NoPen 
        )
        
        painter.setBrush(brush)
        painter.setPen(pen)
        
        c = pin_style.margin_cut
        draw_rect = rect.marginsRemoved(QMarginsF(c, c, c, c)) if c > 0 else rect
        painter.drawEllipse(draw_rect)
        
    @staticmethod
    def get_header_rect(node_width, node_height, title_rect):
        header_height = 1.0 * title_rect.height()  # 35 * (self.parent_node.title.count('\n')+1)

        header_rect = QRectF()
        header_rect.setTopLeft(QPointF(-node_width / 2, -node_height / 2))
        header_rect.setWidth(node_width)
        header_rect.setHeight(header_height)
        return header_rect
    
    @staticmethod
    def get_rect_no_header(node_width, node_height, bounding_rect, title_rect):
        return QRectF(
            QPointF(
                bounding_rect.left(), 
                bounding_rect.top() + FlowTheme.get_header_rect(
                    node_width,
                    node_height,
                    title_rect
                ).height()
            ),
            bounding_rect.bottomRight()
        )

    @staticmethod
    def interpolate_color(c1, c2, val):
        r1 = c1.red()
        g1 = c1.green()
        b1 = c2.blue()
        a1 = c1.alpha()

        r2 = c2.red()
        g2 = c2.green()
        b2 = c2.blue()
        a2 = c2.alpha()

        r = (r2 - r1) * val + r1
        g = (g2 - g1) * val + g1
        b = (b2 - b1) * val + b1
        a = (a2 - a1) * val + a1

        return QColor(r, g, b, a)

    @staticmethod
    def hex_to_col(hex_str: str) -> QColor:
        """Converts a hex value in format '#xxxxxx[xx]' to QColor using alpha value if [xx] is used."""

        h = hex_str.lstrip('#')

        if len(h) == 6:
            r, g, b = tuple(
                int(h[i:i + 2], 16) for i in (0, 2, 4)
            )
            return QColor(r, g, b)
        elif len(h) == 8:
            r, g, b, a = tuple(
                int(h[i:i + 2], 16) for i in (0, 2, 4, 6)
            )
            return QColor(r, g, b, a)

        return None

    @staticmethod
    def col(c: QColor, alpha=255):
        return QColor(c.red(), c.green(), c.blue(), alpha)

    @staticmethod
    def _parse_pen_style(s: str):
        if s == 'solid line':
            return Qt.SolidLine
        elif s == 'dash line':
            return Qt.DashLine
        elif s == 'dash dot line':
            return Qt.DashDotLine
        elif s == 'dash dot dot line':
            return Qt.DashDotDotLine
        elif s == 'dot line':
            return Qt.DotLine


class FlowTheme_Toy(FlowTheme):
    name = 'Toy'

    node_selection_stylesheet = ''

    header_padding = (12, 5, 10, 2)

    exec_conn_color = QColor(188, 187, 242)
    exec_conn_width = 5
    exec_conn_pen_style = Qt.SolidLine

    data_conn_color = QColor(188, 187, 242)
    data_conn_width = 5
    data_conn_pen_style = Qt.DashLine

    flow_background_brush = QBrush(QColor('#333333'))
    
    pin_style_data = DataPinStyle(
        pen_width=0,
        valid_color=QColor('#2E688C'),
        margin_cut=3,
        disconnected_color=QColor('#c69a15'),
    )
    
    pin_style_exec = ExecPinStyle(
        valid_color=QColor('#3880ad'),
    )
    
    def setup_NI_title_label(self, text_graphic: GraphicsTextWidget, selected: bool, hovering: bool, node_style: str, node_title: str, node_color: QColor):
        
        if node_style == 'normal':
            text_style = TextStyle(
                color = QColor(30, 43, 48) if not hovering else node_color.lighter(),
                font=QFont('Poppins', 15)
            )
        else:
            text_style = TextStyle(
                color = node_color if not hovering else node_color.lighter(),
                font=QFont('K2D', 15, QFont.Bold, True)
            )
        
        self.setup_label(text_graphic, node_title, text_style)
        
    def setup_PI_label(self, text_graphic: GraphicsTextWidget, type_: str, pin_state: PinState, 
                       label_str: str, node_color: QColor):
        
        self.setup_label(
            text_graphic,
            label_str,
            TextStyle(
                QColor('#FFFFFF'),
                QFont("Source Code Pro", 10, QFont.Bold)
            )
        )
        
    def draw_NI_normal(self, node_gui, selected: bool, hovered: bool,
                       painter: QPainter, c: QColor, w, h, bounding_rect, title_rect):

        # main rect
        header_color = QColor(c.red() / 10 + 100, c.green() / 10 + 100, c.blue() / 10 + 100)
        if selected:
            header_color = header_color.lighter()
        body_gradient = QRadialGradient(bounding_rect.topLeft(), pythagoras(h, w))
        body_gradient.setColorAt(0, self.col(header_color, alpha=200))
        body_gradient.setColorAt(1, self.col(header_color, alpha=0))

        painter.setBrush(body_gradient)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(bounding_rect, 12, 12)

        header_gradient = QLinearGradient(FlowTheme_Toy.get_header_rect(w, h, title_rect).topRight(),
                                          FlowTheme_Toy.get_header_rect(w, h, title_rect).bottomLeft())
        header_gradient.setColorAt(0, QColor(c.red(), c.green(), c.blue(), 255))
        header_gradient.setColorAt(1, QColor(c.red(), c.green(), c.blue(), 0))
        painter.setBrush(header_gradient)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(FlowTheme_Toy.get_header_rect(w, h, title_rect), 12, 12)

    def draw_NI_small(self, node_gui, selected: bool, hovered: bool,
                      painter: QPainter, c: QColor, w, h, bounding_rect, title_rect):

        path = QPainterPath()
        th = title_rect.height()
        path.moveTo(-w / 2, 0)

        body_rect = self.get_rect_no_header(w, h, bounding_rect, title_rect)
        bh = body_rect.height()
        
        pw, ph = w * 0.5, bh * 0.5
        
        path.cubicTo(-pw, -ph,
                     -pw, -ph,
                     0, -ph)
        path.cubicTo(+pw, -ph,
                     +pw, -ph,
                     +pw, 0)
        path.cubicTo(+pw, +ph,
                     +pw, +ph,
                     0, +ph)
        path.cubicTo(-pw, +ph,
                     -pw, +ph,
                     -pw, 0)
        path.closeSubpath()
        path.translate(0, th * 0.5)
        
        body_gradient = QLinearGradient(body_rect.bottomLeft(),
                                        body_rect.topRight())
        body_gradient.setColorAt(0, QColor(c.red(), c.green(), c.blue(), 150))
        body_gradient.setColorAt(1, QColor(c.red(), c.green(), c.blue(), 80))

        painter.setBrush(body_gradient)
        painter.setPen(QPen(QColor(30, 43, 48)))

        painter.drawPath(path)


class FlowTheme_DarkTron(FlowTheme):
    name = 'Tron'

    node_selection_stylesheet = ''

    header_padding = (12, 5, 10, 2)

    exec_conn_color = QColor(0, 120, 180)
    exec_conn_width = 4
    exec_conn_pen_style = Qt.SolidLine

    data_conn_color = QColor(0, 120, 180)
    data_conn_width = 4
    data_conn_pen_style = Qt.DashLine

    flow_background_brush = QBrush(QColor('#333333'))


    def setup_NI_title_label(self, text_graphic: GraphicsTextWidget, selected: bool, hovering: bool, node_style: str, 
                             node_title: str, node_color: QColor):
        
        if node_style == 'normal':
            text_style = TextStyle(
                color = node_color if not (hovering or selected) else node_color.lighter().lighter(),
                font = QFont('Poppins', 15),
            )
        else:
            text_style = TextStyle(
                color = node_color,
                font = QFont('K2D', 15, QFont.Bold, True),
            )
        
        self.setup_label(text_graphic, node_title, text_style)

    def draw_NI_normal(self, node_gui, selected: bool, hovered: bool,
                       painter, c: QColor, w: int, h: int, bounding_rect, title_rect):

        background_color = QColor('#212224')
        painter.setBrush(background_color)
        pen = QPen(c if not selected else c.lighter())
        pen.setWidth(2)
        painter.setPen(pen)
        body_path = self.get_extended_body_path(w, h)
        painter.drawPath(body_path)

        header_gradient = QLinearGradient(self.get_header_rect(w, h, title_rect).topRight(),
                                          self.get_header_rect(w, h, title_rect).bottomLeft())
        header_gradient.setColorAt(0, QColor(c.red(), c.green(), c.blue(), 255))
        header_gradient.setColorAt(0.5, QColor(c.red(), c.green(), c.blue(), 100))
        header_gradient.setColorAt(1, QColor(c.red(), c.green(), c.blue(), 0))
        painter.setBrush(header_gradient)
        header_path = self.get_extended_header_path(w, h, title_rect)
        painter.drawPath(header_path)

    @staticmethod
    def get_extended_body_path(w, h):

        c_s = 10  # corner size

        path = QPainterPath()
        path.moveTo(+w * 0.5, -h * 0.5 + c_s)
        path.lineTo(+w * 0.5 - c_s, -h * 0.5)
        path.lineTo(-w * 0.5 + c_s, -h * 0.5)
        path.lineTo(-w * 0.5, -h * 0.5 + c_s)
        path.lineTo(-w * 0.5, +h * 0.5 - c_s)
        path.lineTo(-w * 0.5 + c_s, +h * 0.5)
        path.lineTo(+w * 0.5 - c_s, +h * 0.5)
        path.lineTo(+w * 0.5, +h * 0.5 - c_s)
        path.closeSubpath()
        return path

    def get_extended_header_path(self, w, h, title_rect):

        c_s = 10  # corner size

        header_height = self.get_header_rect(w, h, title_rect).height()
        header_bottom = -h * 0.5 + header_height
        path = QPainterPath()
        path.moveTo(+w * 0.5, -h * 0.5 + c_s)
        path.lineTo(+w * 0.5 - c_s, -h * 0.5)
        path.lineTo(-w * 0.5 + c_s, -h * 0.5)
        path.lineTo(-w * 0.5, -h * 0.5 + c_s)
        path.lineTo(-w * 0.5, header_bottom - c_s)
        path.lineTo(-w * 0.5 + c_s, header_bottom)
        path.lineTo(+w * 0.5 - c_s, header_bottom)
        path.lineTo(+w * 0.5, header_bottom - c_s)
        path.closeSubpath()
        return path

    def draw_NI_small(self, node_gui, selected: bool, hovered: bool,
                      painter: QPainter, c: QColor, w, h, bounding_rect, title_rect):

        if hovered:
            background_color = c.darker()
        else:
            background_color = QColor('#212429')

        c_s = 10  # corner size
        
        body_rect = self.get_rect_no_header(w, h, bounding_rect, title_rect)
        bh = body_rect.height()
        
        path = QPainterPath()
        path.moveTo(-w / 2, 0)
        
        path.lineTo(-w / 2 + c_s / 2, -bh / 2 + c_s / 2)
        path.lineTo(0, -bh / 2)
        path.lineTo(+w / 2 - c_s / 2, -bh / 2 + c_s / 2)
        path.lineTo(+w / 2, 0)
        path.lineTo(+w / 2 - c_s / 2, +bh / 2 - c_s / 2)
        path.lineTo(0, +bh / 2)
        path.lineTo(-w / 2 + c_s / 2, +bh / 2 - c_s / 2)
        path.closeSubpath()

        path.translate(0, +title_rect.height() * 0.5)
        
        painter.setBrush(background_color)
        pen = QPen(c)
        pen.setWidth(2)
        painter.setPen(pen)

        painter.drawPath(path)


class FlowTheme_Ghost(FlowTheme):
    name = 'Ghost'
    type_ = 'dark'

    node_selection_stylesheet = ''

    header_padding = (12, 6, 10, 2)

    exec_conn_color = QColor(0, 17, 25)
    exec_conn_width = 2
    exec_conn_pen_style = Qt.SolidLine

    data_conn_color = QColor(0, 17, 25)
    data_conn_width = 2
    data_conn_pen_style = Qt.DashLine

    flow_background_color = QColor('#333333')
    flow_background_brush = QBrush(flow_background_color)

    node_color = QColor(28, 28, 28, 170)
    node_small_color = QColor('#212429')

    pin_style_data = DataPinStyle(margin_cut=3, pen_width=1)
    pin_style_exec = ExecPinStyle(pen_width=1)
    
    EXPORT = [
        'nodes color',
        'small nodes color',
        'flow background color'
    ]

    def _load(self, imported: dict):
        super()._load(imported)

        for k, v in imported.items():
            if k == 'nodes color':
                self.node_color = self.hex_to_col(v)
            elif k == 'small nodes color':
                self.node_small_color = self.hex_to_col(v)
            elif k == 'flow background color':
                self.flow_background_color = self.hex_to_col(v)
                self.flow_background_brush = QBrush(self.flow_background_color)

    def setup_NI_title_label(self, text_graphic: GraphicsTextWidget, selected: bool, hovering: bool, node_style: str, 
                             node_title: str, node_color: QColor):
        
        if node_style == 'normal':
            text_style = TextStyle(
                color = node_color if not hovering else node_color.lighter().lighter(),
                font = QFont('Poppins', 15),
            )
        else:
            text_style = TextStyle(
                color = node_color,
                font = QFont('K2D', 15, QFont.Bold, True),
            )
        
        self.setup_label(text_graphic, node_title, text_style)

    def draw_NI_normal(self, node_gui, selected: bool, hovered: bool,
                       painter, c, w, h, bounding_rect, title_rect):

        background_color = self.node_color
        painter.setBrush(background_color)
        pen = QPen(c.darker())
        pen.setWidth(1 if not selected else 5)
        painter.setPen(pen)
        body_path = self.get_extended_body_path(5, w, h)
        painter.drawPath(body_path)

    @staticmethod
    def get_extended_body_path(c_s, w, h):

        path = QPainterPath()
        path.moveTo(+w / 2, -h / 2 + c_s)
        path.lineTo(+w / 2 - c_s, -h / 2)
        path.lineTo(-w / 2 + c_s, -h / 2)
        path.lineTo(-w / 2, -h / 2 + c_s)
        path.lineTo(-w / 2, +h / 2 - c_s)
        path.lineTo(-w / 2 + c_s, +h / 2)
        path.lineTo(+w / 2 - c_s, +h / 2)
        path.lineTo(+w / 2, +h / 2 - c_s)
        path.closeSubpath()
        return path

    def draw_NI_small(self, node_gui, selected: bool, hovered: bool,
                      painter, c, w, h, bounding_rect, title_rect):

        background_color = self.node_small_color
        c_s = 10  # corner size

        bh = self.get_rect_no_header(w, h, bounding_rect, title_rect).height()
        path = self.get_extended_body_path(c_s, w, bh)  # equals the small in this case
        path.translate(0, title_rect.height() * 0.5)
        
        painter.setBrush(background_color)
        painter.setPen(Qt.NoPen)
        painter.drawPath(path)


class FlowTheme_Blender(FlowTheme):
    name = 'Blender'

    node_selection_stylesheet = ''

    header_padding = (5, 0, 0, 0)

    exec_conn_color = QColor(0, 17, 25)
    exec_conn_width = 3
    exec_conn_pen_style = Qt.SolidLine

    data_conn_color = QColor(200, 200, 200)
    data_conn_width = 2.5
    data_conn_pen_style = Qt.SolidLine

    flow_background_color = QColor('#232323')
    flow_background_brush = QBrush(flow_background_color)

    node_color = QColor('#3f3f3f')
    corner_radius_normal = 5
    corner_radius_small = 10

    pin_style_data = DataPinStyle(margin_cut=3, pen_width=1)
    pin_style_exec= ExecPinStyle(pen_width=1)
    
    EXPORT = [
        'nodes color',
        'flow background color'
    ]

    def _load(self, imported: dict):
        super()._load(imported)

        for k, v in imported.items():
            if k == 'nodes color':
                self.node_color = self.hex_to_col(v)
            elif k == 'flow background color':
                self.flow_background_color = self.hex_to_col(v)
                self.flow_background_brush = QBrush(self.flow_background_color)

    def setup_NI_title_label(self, text_graphic: GraphicsTextWidget, selected: bool, hovering: bool, node_style: str, 
                             node_title: str, node_color: QColor):
        
        if node_style == 'normal':
            text_style = TextStyle(
                color = QColor('#FFFFFF'),
                font = QFont('Segoe UI', 11),
            )
        else:
            text_style = TextStyle(
                color = node_color,
                font = QFont('Segoe UI', 11, QFont.Bold, True),
            )
        
        self.setup_label(text_graphic, node_title, text_style)

    def draw_NI_normal(self, node_gui, selected: bool, hovered: bool,
                       painter, c, w, h, bounding_rect, title_rect):

        background_color = self.node_color
        header_color = QColor(c.red(), c.green(), c.blue(), 180)
        if selected:
            header_color = header_color.lighter()


        rel_header_height = self.get_header_rect(w, h, title_rect).height() / h
        gradient = QLinearGradient(bounding_rect.topLeft(), bounding_rect.bottomLeft())
        gradient.setColorAt(0, header_color)
        gradient.setColorAt(rel_header_height, header_color)
        gradient.setColorAt(rel_header_height + 0.0001, background_color)
        gradient.setColorAt(1, background_color)

        painter.setBrush(gradient)
        painter.setPen(
            Qt.NoPen
            if not selected else
            QPen(QColor(200, 200, 200))
        )
        painter.drawRoundedRect(bounding_rect, self.corner_radius_normal, self.corner_radius_normal)

    def draw_NI_small(self, node_gui, selected: bool, hovered: bool,
                      painter, c, w, h, bounding_rect, title_rect):

        background_color = QColor('#212429')
        painter.setBrush(self.interpolate_color(c, background_color, 0.97))
        painter.setPen(
            QPen(c)
            if not selected else
            QPen(QColor(200, 200, 200))
        )
        
        painter.drawRoundedRect(
            self.get_rect_no_header(w, h, bounding_rect, title_rect), 
            self.corner_radius_small, 
            self.corner_radius_small
        )


class FlowTheme_Simple(FlowTheme):
    name = 'Simple'
    type_ = 'dark'

    node_selection_stylesheet = ''

    header_padding = (10, 2, 10, 2)

    exec_conn_color = QColor('#989c9f')
    exec_conn_width = 2
    exec_conn_pen_style = Qt.SolidLine

    data_conn_color = QColor('#989c9f')
    data_conn_width = 2
    data_conn_pen_style = Qt.DashLine

    flow_background_color = QColor('#3f4044')
    flow_background_brush = QBrush(flow_background_color)

    node_background_color = QColor('#212429')
    node_small_background_color = QColor('#212429')

    pin_style_data = DataPinStyle(
        margin_cut=2,
        disconnected_color=QColor('#53585c'),
        pen_width=0
    )
    pin_style_exec = ExecPinStyle(
        margin_cut=2,
        valid_color=QColor('#dddddd')
    )
    
    EXPORT = [
        'nodes background color',
        'small nodes background color',
        'flow background color'
    ]

    def _load(self, imported: dict):
        super()._load(imported)

        for k, v in imported.items():
            if k == 'nodes background color':
                self.node_background_color = self.hex_to_col(v)
            elif k == 'small nodes background color':
                self.node_small_background_color = self.hex_to_col(v)
            elif k == 'flow background color':
                self.flow_background_color = self.hex_to_col(v)
                self.flow_background_brush = QBrush(self.flow_background_color)

    def setup_NI_title_label(self, text_graphic: GraphicsTextWidget, selected: bool, hovering: bool, node_style: str, 
                             node_title: str, node_color: QColor):
        
        if node_style == 'normal':
            text_style = TextStyle(
                color = QColor('#312b29'),
                font = QFont('ASAP', 13, QFont.Bold),
            )
        else:
            text_style = TextStyle(
                color = node_color,
                font = QFont('Poppins', 13, QFont.Thin),
            )
        
        self.setup_label(text_graphic, node_title, text_style)

    def setup_PI_label(self, text_graphic: GraphicsTextWidget, type_: str, pin_state: PinState, 
                       label_str: str, node_color: QColor):
        
        if pin_state != PinState.CONNECTED:
            c = QColor('#53585c')
        else:
            if type_ == 'exec':
                c = QColor('#cccccc')
            else:
                c = node_color
                
        self.setup_label(
            text_graphic,
            label_str,
            TextStyle(
                c,
                QFont("Courier New", 10, QFont.Bold)
            )
        )
        
    def draw_NI_normal(self, node_gui, selected: bool, hovered: bool,
                       painter, c, w, h, bounding_rect, title_rect):

        background_color = self.node_background_color

        if selected:
            header_color = c.lighter()
        else:
            header_color = c

        rel_header_height = self.get_header_rect(w, h, title_rect).height() / h
        gradient = QLinearGradient(bounding_rect.topLeft(), bounding_rect.bottomLeft())
        gradient.setColorAt(0, header_color)
        gradient.setColorAt(rel_header_height, header_color)
        gradient.setColorAt(rel_header_height + 0.0001, background_color)
        gradient.setColorAt(1, background_color)

        painter.setBrush(gradient)
        painter.setPen(Qt.NoPen)  # QPen(c.darker()))
        painter.drawRoundedRect(bounding_rect, 9, 9)

    def draw_NI_small(self, node_gui, selected: bool, hovered: bool,
                      painter, c, w, h, bounding_rect, title_rect):

        background_color = self.node_small_background_color
        c_s = 10
        painter.setBrush(self.interpolate_color(c, background_color, 0.97))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.get_rect_no_header(w, h, bounding_rect, title_rect), c_s, c_s)


class FlowTheme_Ueli(FlowTheme):
    name = 'Ueli'

    node_selection_stylesheet = ''

    header_padding = (5, 2, 10, 0)

    exec_conn_color = QColor('#989c9f')
    exec_conn_width = 2
    exec_conn_pen_style = Qt.SolidLine

    data_conn_color = QColor('#989c9f')
    data_conn_width = 2
    data_conn_pen_style = Qt.DashLine

    flow_background_color = QColor('#3f4044')
    flow_background_brush = QBrush(flow_background_color)

    nodes_background_color = QColor('#212429')
    small_nodes_background_color = nodes_background_color

    pin_style_data = DataPinStyle(
        pen_width=0,
        disconnected_color=QColor('#53585c'),
        margin_cut=2
    )
    pin_style_exec = ExecPinStyle(
        pen_width=0,
        valid_color=QColor('#dddddd')
    )
    
    EXPORT = [
        'nodes background color',
        'small nodes background color',
        'flow background color'
    ]

    def _load(self, imported: dict):
        super()._load(imported)

        for k, v in imported.items():
            if k == 'nodes background color':
                c = self.hex_to_col(v)
                self.nodes_background_color = c
            elif k == 'small nodes background color':
                self.small_nodes_background_color = self.hex_to_col(v)
            elif k == 'flow background color':
                self.flow_background_color = self.hex_to_col(v)
                self.flow_background_brush = QBrush(self.flow_background_color)

    def setup_NI_title_label(self, text_graphic: GraphicsTextWidget, selected: bool, hovering: bool, node_style: str, 
                             node_title: str, node_color: QColor):
        
        if node_style == 'normal':
            text_style = TextStyle(
                color = node_color,
                font = QFont('Poppins', 13),
            )
        else:
            text_style = TextStyle(
                color = node_color,
                font = QFont('Poppins', 13, QFont.Thin),
            )
        
        self.setup_label(text_graphic, node_title, text_style)

    def setup_PI_label(self, text_graphic: GraphicsTextWidget, type_: str, pin_state: PinState, 
                       label_str: str, node_color: QColor):
        
        if pin_state != PinState.CONNECTED:
            c = QColor('#53585c')
        else:
            if type_ == 'exec':
                c = QColor('#cccccc')
            else:
                c = node_color
                
        self.setup_label(
            text_graphic,
            label_str,
            TextStyle(
                c,
                QFont("Courier New", 10, QFont.Bold)
            )
        )

    def draw_NI_normal(self, node_gui, selected: bool, hovered: bool,
                       painter, c, w, h, bounding_rect: QRectF, title_rect):

        if selected:
            background_color = self.interpolate_color(self.nodes_background_color, c.darker(), 0.18)
        else:
            background_color = self.nodes_background_color

        header_color = c

        header_height = self.get_header_rect(w, h, title_rect).height()
        rel_header_height = header_height / h
        gradient = QLinearGradient(bounding_rect.topLeft(), bounding_rect.bottomLeft())
        gradient.setColorAt(0, header_color)
        gradient.setColorAt(rel_header_height, header_color)
        gradient.setColorAt(rel_header_height + 0.0001, background_color)
        gradient.setColorAt(1, background_color)

        painter.setBrush(QBrush(background_color))
        painter.setPen(Qt.NoPen)  # QPen(c.darker()))
        painter.drawRoundedRect(QRectF(
            QPointF(bounding_rect.left(), bounding_rect.top() + header_height),
            bounding_rect.bottomRight()
        ), 6, 6)

    def draw_NI_small(self, node_gui, selected: bool, hovered: bool,
                      painter, c, w, h, bounding_rect, title_rect):
        background_color = self.small_nodes_background_color
        c_s = 10  # corner size
        painter.setBrush(self.interpolate_color(c, background_color, 0.97))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.get_rect_no_header(w, h, bounding_rect, title_rect), c_s, c_s)


class FlowTheme_PureDark(FlowTheme):
    name = 'pure dark'

    node_selection_stylesheet = ''

    header_padding = (4, 2, 2, 2)

    exec_conn_color = QColor('#ffffff')
    exec_conn_width = 1.5
    exec_conn_pen_style = Qt.SolidLine

    data_conn_color = QColor('#ffffff')
    data_conn_width = 1.5
    data_conn_pen_style = Qt.DashLine

    flow_background_brush = QBrush(QColor('#1E242A'))
    flow_background_grid = ('points', flow_background_brush.color().lighter(), 2, 50, 50)

    node_item_shadow_color = QColor('#101010')

    node_normal_bg_col = QColor('#0C1116')
    node_small_bg_col = QColor('#363c41')
    node_title_color = QColor('#ffffff')
    port_pin_pen_color = QColor('#ffffff')
    
    EXPORT = [
        'extended node background color',
        'small node background color',
        'node title color',
        'port pin pen color'
    ]

    def _load(self, imported: dict):
        super()._load(imported)

        for k, v in imported.items():
            if k == 'extended node background color':
                self.node_normal_bg_col = self.hex_to_col(v)
            elif k == 'small node background color':
                self.node_small_bg_col = self.hex_to_col(v)
            elif k == 'node title color':
                self.node_title_color = self.hex_to_col(v)
            elif k == 'port pin pen color':
                self.port_pin_pen_color = self.hex_to_col(v)

    def setup_NI_title_label(self, text_graphic: GraphicsTextWidget, selected: bool, hovering: bool, node_style: str, 
                             node_title: str, node_color: QColor):
        
        text_style = TextStyle(
            color = self.node_title_color,
            font = QFont('Segoe UI', 12)
        )
        
        self.setup_label(text_graphic, node_title, text_style)

    def setup_PI_label(self, text_graphic: GraphicsTextWidget, type_: str, pin_state: PinState, 
                       label_str: str, node_color: QColor):
        
        if pin_state != PinState.CONNECTED:
            c = QColor('#53585c')
        else:
            if type_ == 'exec':
                c = QColor('#cccccc')
            else:
                c = node_color
                
        self.setup_label(
            text_graphic,
            label_str,
            TextStyle(
                c,
                QFont("Segoe UI", 10, QFont.Bold)
            )
        )

    def paint_PI(self, node_gui, painter, option, node_color, type_, pin_state, rect):
        
        pin_style = self.pin_style_exec if type_ == 'exec' else self.pin_style_data
        brush_color = pin_style.pin_colors.get(pin_state)
        
        if pin_state == PinState.CONNECTED:
            brush_color = QColor('#508AD8')
            painter.setPen(Qt.NoPen)
        else:
            pen = QPen(self.port_pin_pen_color)
            pen.setWidthF(1.1)
            painter.setPen(pen)
        
        brush = QBrush(brush_color) if brush_color else QBrush(Qt.NoBrush)
        painter.setBrush(brush)

        if type_ == 'exec':
            painter.setBrush(QBrush(QColor('white')))
        
        painter.drawEllipse(rect.marginsRemoved(QMarginsF(2, 2, 2, 2)))

    def draw_NI_normal(self, node_gui, selected: bool, hovered: bool,
                       painter, c, w, h, bounding_rect: QRectF, title_rect):

        if selected:
            background_color = self.interpolate_color(self.node_normal_bg_col, c.darker(), 0.18)
        else:
            background_color = self.node_normal_bg_col

        header_height = self.get_header_rect(w, h, title_rect).height()

        painter.setBrush(QBrush(background_color))
        painter.setPen(Qt.NoPen)  # QPen(c.darker()))
        painter.drawRoundedRect(QRectF(
            QPointF(bounding_rect.left(), bounding_rect.top() + header_height),
            bounding_rect.bottomRight()
        ), 3, 3)

        p = QPen(c)
        p.setWidthF(2.3)
        painter.setPen(p)
        painter.drawLine(
            QPointF(bounding_rect.left(), bounding_rect.top() + header_height),
            QPointF(bounding_rect.right(), bounding_rect.top() + header_height)
        )

    def draw_NI_small(self, node_gui, selected: bool, hovered: bool,
                      painter, c, w, h, bounding_rect, title_rect):

        painter.setBrush(QBrush(self.node_small_bg_col))
        painter.setPen(Qt.NoPen)
        
        painter.drawRoundedRect(self.get_rect_no_header(w, h, bounding_rect, title_rect), 4, 4)


class FlowTheme_PureLight(FlowTheme_PureDark):
    name = 'pure light'
    type_ = 'light'

    header_padding = (2, 2, 2, 2)

    node_selection_stylesheet = '''
NodeSelectionWidget {
    background-color: white;
}
NodeWidget {
    background-color: white;
}
    '''

    exec_conn_color = QColor('#1f1f1f')

    data_conn_color = QColor('#1f1f1f')

    flow_background_brush = QBrush(QColor('#ffffff'))
    flow_background_grid = ('points', QColor('#dddddd'), 2, 20, 20)

    node_normal_bg_col = QColor('#cdcfd1')
    node_small_bg_col = QColor('#bebfc1')
    node_title_color = QColor('#1f1f1f')
    port_pin_pen_color = QColor('#1f1f1f')

    node_item_shadow_color = QColor('#cccccc')


class FlowTheme_Colorful(FlowTheme):
    name = 'colorful dark'

    header_padding = (12, 0, 2, 2)

    exec_conn_color = QColor('#ffffff')
    exec_conn_width = 1.5
    exec_conn_pen_style = Qt.SolidLine

    data_conn_color = QColor('#ffffff')
    data_conn_width = 1.5
    data_conn_pen_style = Qt.DashLine

    flow_background_brush = QBrush(QColor('#1E242A'))
    flow_background_grid = ('points', flow_background_brush.color().lighter(), 2, 50, 50)

    node_ext_background_color = QColor('#0C1116')
    node_small_background_color = QColor('#363c41')
    node_title_color = QColor('#ffffff')
    port_pin_pen_color = QColor('#ffffff')

    EXPORT = [
        'node title color',
        'port pin pen color'
    ]

    def _load(self, imported: dict):
        super()._load(imported)

        for k, v in imported.items():
            if k == 'node title color':
                self.node_title_color = self.hex_to_col(v)
            elif k == 'port pin pen color':
                self.port_pin_pen_color = self.hex_to_col(v)

    def setup_NI_title_label(self, text_graphic: GraphicsTextWidget, selected: bool, hovering: bool, node_style: str, 
                             node_title: str, node_color: QColor):
        
        text_style = TextStyle(
            color = self.node_title_color,
            font = QFont('Segoe UI', 12)
        )
        
        self.setup_label(text_graphic, node_title, text_style)

    def setup_PI_label(self, text_graphic: GraphicsTextWidget, type_: str, pin_state: PinState, 
                       label_str: str, node_color: QColor):
        
        if pin_state != PinState.CONNECTED:
            c = QColor('#dddddd')
        else:
            if type_ == 'exec':
                c = QColor('#cccccc')
            else:
                c = node_color
                
        self.setup_label(
            text_graphic,
            label_str,
            TextStyle(
                c,
                QFont("Segoe UI", 10, QFont.Bold)
            )
        )

    def paint_PI(self, node_gui, painter, option, node_color, type_, pin_state, rect):
        
        FlowTheme_PureDark.paint_PI(self, node_gui, painter, option, node_color, type_, pin_state, rect)

    def draw_NI_normal(self, node_gui, selected: bool, hovered: bool,
                       painter, c, w, h, bounding_rect: QRectF, title_rect):

        background_color = c
        background_color.setAlpha(150)

        if selected:
            header_color = QColor(c.red(), c.green(), c.blue(), 130)
        else:
            header_color = QColor(c.red(), c.green(), c.blue(), 130).darker()

        rel_header_height = self.get_header_rect(w, h, title_rect).height() / h
        gradient = QLinearGradient(bounding_rect.topLeft(), bounding_rect.bottomLeft())
        gradient.setColorAt(0, header_color)
        gradient.setColorAt(rel_header_height, header_color)
        gradient.setColorAt(rel_header_height + 0.0001, background_color)
        gradient.setColorAt(1, background_color)

        painter.setBrush(gradient)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(bounding_rect, 7, 7)

    def draw_NI_small(self, node_gui, selected: bool, hovered: bool,
                      painter, c, w, h, bounding_rect, title_rect):

        painter.setBrush(QBrush(QColor(c.red(), c.green(), c.blue(), 150)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.get_rect_no_header(w, h, bounding_rect, title_rect), 8, 8)


class FlowTheme_ColorfulLight(FlowTheme_Colorful):
    name = 'colorful light'
    type_ = 'light'

    header_padding = (12, 0, 2, 2)

    exec_conn_color = QColor('#1f1f1f')

    data_conn_color = QColor('#1f1f1f')

    flow_background_brush = QBrush(QColor('#ffffff'))
    flow_background_grid = ('points', QColor('#dddddd'), 2, 20, 20)

    node_title_color = QColor('#1f1f1f')
    port_pin_pen_color = QColor('#1f1f1f')

    node_item_shadow_color = QColor('#cccccc')

    def setup_PI_label(self, text_graphic: GraphicsTextWidget, type_: str, pin_state: PinState, 
                       label_str: str, node_color: QColor):
        
        if pin_state != PinState.CONNECTED:
            c = QColor('#1f1f1f')
        else:
            if type_ == 'exec':
                c = QColor('#cccccc')
            else:
                c = node_color
                
        self.setup_label(
            text_graphic,
            label_str,
            TextStyle(
                c,
                QFont("Segoe UI", 10, QFont.Bold)
            )
        )

    def draw_NI_normal(self, node_gui, selected: bool, hovered: bool, painter, c, w, h, bounding_rect: QRectF, title_rect):

        background_color = c.lighter()
        background_color.setAlpha(150)

        header_color = QColor(c.red(), c.green(), c.blue(), 130).darker()

        rel_header_height = self.get_header_rect(w, h, title_rect).height() / h
        gradient = QLinearGradient(bounding_rect.topLeft(), bounding_rect.bottomLeft())
        gradient.setColorAt(0, header_color)
        gradient.setColorAt(rel_header_height, header_color)
        gradient.setColorAt(rel_header_height + 0.0001, background_color)
        gradient.setColorAt(1, background_color)

        painter.setBrush(gradient)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(bounding_rect, 7, 7)

    def draw_NI_small(self, node_gui, selected: bool, hovered: bool,
                      painter, c, w, h, bounding_rect, title_rect):

        painter.setBrush(QBrush(QColor(c.red(), c.green(), c.blue(), 150)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.get_rect_no_header(w, h, bounding_rect, title_rect), 8, 8)


class FlowTheme_Industrial(FlowTheme):
    name = 'Industrial'

    header_padding = (8, 0, 8, 0)  # (8, 6, 10, 2)

    exec_conn_color = QColor(255, 255, 255)
    exec_conn_width = 2
    exec_conn_pen_style = Qt.SolidLine

    data_conn_color = QColor(255, 194, 45)
    data_conn_width = 2
    data_conn_pen_style = Qt.DashLine

    flow_background_brush = QBrush(QColor(19, 19, 19))
    flow_background_grid = ('points', QColor(80, 80, 80), 2, 30, 30)

    node_color = QColor(10, 10, 10, 250)
    node_item_shadow_color = QColor(0, 0, 0)

    def setup_NI_title_label(self, text_graphic: GraphicsTextWidget, selected: bool, hovering: bool, node_style: str, 
                             node_title: str, node_color: QColor):
        
        if node_style == 'normal':    
            text_style = TextStyle(
                color = QColor(200, 200, 200),
                font = QFont('Segoe UI', 11, QFont.Normal if not (hovering or selected) else QFont.Bold)
            )
        else:
            text_style = TextStyle(
                color = node_color,
                font = QFont('Segoe UI', 12, QFont.Bold)
            )
        
        self.setup_label(text_graphic, node_title, text_style)

    def setup_PI_label(self, text_graphic: GraphicsTextWidget, type_: str, pin_state: PinState, 
                       label_str: str, node_color: QColor):
        
        self.setup_label(
            text_graphic,
            label_str,
            TextStyle(
                QColor('#FFFFFF'),
                QFont("Segoe UI", 8, QFont.Normal)
            )
        )

    def paint_PI(self, node_gui, painter, option, node_color, type_, pin_state, rect):

        color = QColor('#FFFFFF') if type_ == 'exec' else QColor(node_color)

        # add = 2
        # padd = padding + add
        outer_ellipse_rect = rect.marginsRemoved(QMarginsF(2, 2, 2, 2))  # QRectF(padd, padd, w - 2*padd, h - 2*padd)
        # add = 4
        # padd = padding + add
        inner_ellipse_rect = rect.marginsRemoved(QMarginsF(4, 4, 4, 4))  # QRectF(padd, padd, w - 2*padd, h - 2*padd)

        if type_ == 'exec':
            
            pin_style = self.pin_style_exec
            brush_color = pin_style.pin_colors.get(pin_state)
            
            if pin_state == PinState.CONNECTED:
                brush_color = QBrush(QColor(255, 255, 255, 200))
            
            brush = QBrush(brush_color) if brush_color else Qt.NoBrush    
            painter.setBrush(brush)

            rect_ = rect.marginsRemoved(QMarginsF(2, 2, 2, 2))

            painter.setPen(QPen(QColor(255, 255, 255)))

            painter.drawPolygon(QPolygon([
                rect_.topLeft().toPoint(),
                QPoint(rect_.right(), rect_.center().toPoint().y()),
                rect_.bottomLeft().toPoint(),
            ]))

        elif type_ == 'data':

            pin_style = self.pin_style_data
            
            pen = QPen(color)
            pen.setWidth(1)
            painter.setPen(pen)

            if pin_state != PinState.DISCONNECTED:
                # draw inner ellipse
                brush_color = pin_style.pin_colors[pin_state]
                if pin_state == PinState.CONNECTED:
                    brush_color = color
                    
                brush_color = QColor(brush_color)
                brush_color.setAlpha(200)
                painter.setBrush(brush_color)
                painter.drawEllipse(inner_ellipse_rect)

            # draw outer ellipse
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(outer_ellipse_rect)

    def draw_NI_normal(self, node_gui, selected: bool, hovered: bool,
                       painter, c, w, h, bounding_rect, title_rect):

        background_color = QColor(14, 14, 14)
        header_color = QColor(105, 105, 105, 150)

        rel_header_height = self.get_header_rect(w, h, title_rect).height() / h
        gradient = QLinearGradient(bounding_rect.topLeft(), bounding_rect.bottomLeft())
        gradient.setColorAt(0, header_color)
        gradient.setColorAt(rel_header_height, header_color)
        gradient.setColorAt(rel_header_height + 0.0001, background_color)
        gradient.setColorAt(1, background_color)

        painter.setBrush(gradient)
        painter.setPen(Qt.NoPen)  # QPen(c.darker())
        painter.drawRoundedRect(bounding_rect, 2, 2)

    def draw_NI_small(self, node_gui, selected: bool, hovered: bool,
                      painter, c, w, h, bounding_rect, title_rect):

        background_color = QColor(217, 217, 217, 50)
        c_s = 2
        painter.setBrush(self.interpolate_color(c, background_color, 0.97))
        pen = QPen(QColor(130, 130, 130))
        painter.setPen(pen)
        painter.drawRoundedRect(self.get_rect_no_header(w, h, bounding_rect, title_rect), c_s, c_s)


class FlowTheme_Fusion(FlowTheme):
    name = 'Fusion'
    type_ = 'light'

    node_selection_stylesheet = '''
    NodeSelectionWidget {
        background-color: white;
    }
    NodeWidget {
        background-color: white;
    }
        '''

    exec_conn_color = QColor('#1f1f1f')
    exec_conn_width = 2

    data_conn_color = QColor('#1f1f1f')
    data_conn_width = 2

    flow_background_brush = QBrush(QColor('#ffffff'))

    node_normal_bg_col = QColor('#ebeced')
    node_small_bg_col = QColor('#cccdcf')
    node_title_color = QColor('#1f1f1f')
    port_pin_pen_color = QColor('#1f1f1f')

    node_item_shadow_color = QColor('#cccccc')

    def setup_NI_title_label(self, text_graphic: GraphicsTextWidget, selected: bool, hovering: bool, node_style: str, 
                             node_title: str, node_color: QColor):
        
        text_style = TextStyle(
            color = self.node_title_color,
            font = QFont('Segoe UI', 11)
        )
        
        self.setup_label(text_graphic, node_title, text_style)

    def setup_PI_label(self, text_graphic: GraphicsTextWidget, type_: str, pin_state: PinState, 
                       label_str: str, node_color: QColor):
        
        self.setup_label(
            text_graphic,
            label_str,
            TextStyle(
                QColor(0, 0, 0),
                QFont("Segoe UI", 8)
            )
        )
        
    def paint_PI_label(self, node_gui, painter, option, type_, pin_state, label_str, node_color, bounding_rect):
        pen = QPen(QColor('#000000'))
        pen.setWidthF(1.2)
        painter.setPen(pen)

        self.paint_PI_label_default(painter, label_str, QColor(0, 0, 0), QFont("Segoe UI", 8), bounding_rect)


    def paint_PI(self, node_gui, painter, option, node_color, type_, pin_state, rect):

        painter.setBrush(QColor('#000000'))
        painter.setPen(Qt.NoPen)

        if type_ == 'data':
            painter.drawEllipse(rect.marginsRemoved(QMarginsF(3, 3, 3, 3)))
        else:
            draw_rect = rect.marginsRemoved(QMarginsF(3, 3, 3, 3))
            path = QPainterPath(draw_rect.topLeft())
            path.lineTo(QPointF(draw_rect.right(), draw_rect.center().y()))
            path.lineTo(draw_rect.bottomLeft())
            path.closeSubpath()

            painter.drawPath(path)


    def draw_NI_normal(self, node_gui, selected: bool, hovered: bool,
                       painter, c, w, h, bounding_rect: QRectF, title_rect):

        pen = QPen(c)
        col_top = self.node_normal_bg_col.lighter(105)
        col_bottom = self.node_normal_bg_col

        if not selected:
            pen.setWidthF(1)
        else:
            pen.setWidthF(2.5)
            col_bottom = QColor(255, 255, 255)

        header_height = self.get_header_rect(w, h, title_rect).height()
        header_fraction = header_height / bounding_rect.height()

        gradient = QLinearGradient(bounding_rect.topLeft(), bounding_rect.bottomLeft())
        gradient.setColorAt(0, col_top)
        gradient.setColorAt(header_fraction, self.interpolate_color(col_top, col_bottom, 0.7))
        gradient.setColorAt(1, col_bottom)

        painter.setBrush(QBrush(gradient))
        painter.setPen(pen)
        painter.drawRoundedRect(bounding_rect, 3, 3)


    def draw_NI_small(self, node_gui, selected: bool, hovered: bool,
                      painter, c, w, h, bounding_rect, title_rect):

        painter.setBrush(QBrush(self.node_small_bg_col))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.get_rect_no_header(w, h, bounding_rect, title_rect), 4, 4)


flow_themes = [
    FlowTheme_Toy(),
    FlowTheme_DarkTron(),
    FlowTheme_Ghost(),
    FlowTheme_Blender(),
    FlowTheme_Simple(),
    FlowTheme_Ueli(),
    FlowTheme_PureDark(),
    FlowTheme_Colorful(),
    FlowTheme_PureLight(),
    FlowTheme_ColorfulLight(),
    FlowTheme_Industrial(),
    FlowTheme_Fusion(),
]
