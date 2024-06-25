from qtpy.QtGui import (
    QFont, 
    QKeySequence,
    QColor,
    QPainter,
    QStandardItem,
    QStandardItemModel,
)

from qtpy.QtWidgets import (
    QWidget,
    QGraphicsWidget,
    QGraphicsTextItem,
    QGraphicsLayoutItem,
    QGraphicsItem,
    QStyleOptionGraphicsItem,
    QDialogButtonBox,
    QPlainTextEdit,
    QVBoxLayout,
    QMessageBox,
    QDialog,
    QShortcut,
    QTreeView,
    QLineEdit,
)

from qtpy.QtCore import (
    QPointF, 
    QSortFilterProxyModel,
    Qt,
    QModelIndex,
    QSizeF,
    QTimeLine,
    QRectF,
)

from dataclasses import dataclass, field
from numbers import Real, Integral
from re import escape

@dataclass
class TextStyle:
    """A simple config class for GraphicsTextWidget"""
    
    color: QColor = field(default_factory=lambda: QColor('#FFFFFF'))
    font: QFont = field(default_factory=QFont)


class GraphicsTextWidget(QGraphicsWidget):
    """Wraps QGraphicsTextItem as a QGraphicsWidget"""
    
    def __init__(self, parent = None) -> None:
        super().__init__(parent)
        self._text_item = QGraphicsTextItem(parent=self)
        
    def boundingRect(self):
        return self._text_item.boundingRect()
    
    def sizeHint(self, which, constraint=...):
        return self._text_item.boundingRect().size()
    
    def setGeometry(self, rect):
        self.prepareGeometryChange()
        QGraphicsLayoutItem.setGeometry(self, rect)
        self.setPos(rect.topLeft())
        
    def set_text(self, value: str):
        self._text_item.setPlainText(value)
        self.update()
        
    def set_html(self, html: str):
        self._text_item.setHtml(html)
        self.update()
        
    def set_text_width(self, width):
        self._text_item.setTextWidth(width)
        self.update()
        
    def set_default_text_color(self, color: QColor):
        self._text_item.setDefaultTextColor(color)
        self.update()
        
    def default_text_color(self):
        return self._text_item.defaultTextColor()
    
    def set_font(self, font):
        self._text_item.setFont(font)
        self.update()
        
    def set_text_style(self, style: TextStyle):
        self._text_item.setFont(style.font)
        self._text_item.setDefaultTextColor(style.color)
        self.update()


class GraphicsProgressBar(QGraphicsWidget):
    
    """A graphics progress bar for display in a Graphics View"""
    
    def __init__(self, color: QColor = QColor(0, 255, 0), height: Real = 20, parent: QGraphicsItem | None = None):
        super().__init__(parent)
        self._color = color
        self._progress: Real = 0
        self._offset: Real = 0
        self._height = 20
        self._width = 100
        self._font: QFont = None
        self._text_color: QColor = QColor(185, 185, 185)

        self.__timeline = None
    # PROPERTIES
    
    @property
    def color(self):
        return self._color
    
    @color.setter
    def color (self, color: QColor):
        self._color = color
        self.update()
    
    @property
    def progress(self):
        return self._progress

    @progress.setter
    def progress(self, value: Real):
        """Progress should be between 0 and 1"""
        self._progress = self.__clamp(value, 0, 1)
        self.update()
    
    @property
    def offset(self):
        return self._offset
    
    @offset.setter
    def offset(self, value: Real):
        self._offset = self.__clamp(value, 0, 1)
        self.update()
        
    def set_progress_values(self, progress: Real, offset: Real):
        self.progress = progress
        self.offset = offset
        self.update()
    
    @property
    def height(self):
        return self._height
    
    @height.setter
    def height(self, value: Real):
        self._height = value
        self.updateGeometry()
        self.update()
    
    @property
    def width(self):
        return self._width
    
    @width.setter
    def width(self, value: Real):
        self._width = value
        self.updateGeometry()
        self.update()
    
    def set_size(self, width: Real, height: Real):
        self._width = width
        self._height = height
        self.updateGeometry()
        self.update()
        
    @property
    def font(self):
        return self._font

    @font.setter
    def font(self, value: QFont):
        self._font = value
        self.update()
    
    @property
    def text_color(self):
        return self._text_color
    
    @text_color.setter
    def text_color(self, color: QColor):
        self._text_color = color
        if self._text_color is None:
            self._text_color = QColor(185, 185, 185)
        self.update()
    
    # ANIMATION
    
    def play_animation(
        self, percent: Integral, 
        duration: Integral = 1, 
        frames: Integral = 100 
    ):
        """
        Plays an animation that indicates indefinite loading
        
        Duration is in seconds
        """
        
        # timeline creation
        self.__timeline = QTimeLine(duration * 1000, self)
        self.__timeline.setFrameRange(0, frames)
        self.__timeline.setLoopCount(0)
        
        # progress
        self.progress = percent
        
        def update_timeline(frame):
            half_point = int(frames * 0.5)
            if frame < half_point:
                # forward
                percentage = 2 * frame / frames
            else:
                # reverse
                percentage = 2 * (1 - frame / frames)
            
            final_value = 1 - percent
            self.offset = final_value * percentage
        
        self.__timeline.frameChanged.connect(update_timeline)
        
        self.__timeline.start()

    def stop_animation(self):
        if self.__timeline:
            self.__timeline.stop()
            self.__timeline.deleteLater()
            self.__timeline = None

    # DRAWING
    
    def boundingRect(self) -> QRectF:
        return QRectF(QPointF(0, 0), self.geometry().size())
    
    def setGeometry(self, rect: QRectF):
        self.prepareGeometryChange()
        rect.setHeight(self.height)
        rect.setWidth(self.width)
        QGraphicsLayoutItem.setGeometry(self, rect)
        self.setPos(rect.topLeft())
    
    def sizeHint(self, which, constraint=...):
        return QSizeF(self._width, self._height)
        
    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = ...):
        rect = self.boundingRect()
        x, y, width, height = rect.x(), rect.y(), rect.width(), rect.height()
        
        rect_width = width - 40
        
        # Draw grey backgroundint(rect_width * self.progress)
        painter.setBrush(QColor(200, 200, 200))
        bar_rect = QRectF(x, y, rect_width, height)
        painter.drawRect(bar_rect)
        
        # Draw progress
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._color)
        p_x = int(rect_width * self.offset)
        # excess is cut automatically
        p_width = int(rect_width * self.progress)
        painter.drawRect(x + p_x, y, p_width, height)
        
        # Draw text
        text_rect = QRectF(x + rect_width, y, width - rect_width, height)
        painter.setPen(self._text_color)
        
        if self.__timeline:
            painter.drawText(text_rect, f'---%', Qt.AlignmentFlag.AlignCenter)
        else:
            painter.drawText(text_rect, f'{self.progress * 100}%', Qt.AlignmentFlag.AlignCenter)
    
    def __clamp(self, num, min_value, max_value):
        return max(min(num, max_value), min_value)


class EditVal_Dialog(QDialog):

    def __init__(self, parent, init_val):
        super(EditVal_Dialog, self).__init__(parent)

        # shortcut
        save_shortcut = QShortcut(QKeySequence.Save, self)
        save_shortcut.activated.connect(self.save_triggered)

        main_layout = QVBoxLayout()

        self.val_text_edit = QPlainTextEdit()
        val_str = ''
        try:
            val_str = str(init_val)
        except Exception as e:
            msg_box = QMessageBox(QMessageBox.Warning, 'Value parsing failed',
                                  'Couldn\'t stringify value', QMessageBox.Ok, self)
            msg_box.setDefaultButton(QMessageBox.Ok)
            msg_box.exec_()
            self.reject()

        self.val_text_edit.setPlainText(val_str)

        main_layout.addWidget(self.val_text_edit)

        button_box = QDialogButtonBox()
        button_box.setStandardButtons(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        main_layout.addWidget(button_box)

        self.setLayout(main_layout)
        self.resize(450, 300)

        self.setWindowTitle('edit val')

    def save_triggered(self):
        self.accept()


    def get_val(self):
        val = self.val_text_edit.toPlainText()
        try:
            val = eval(val)
        except Exception as e:
            pass
        return val

class FilterTreeView(QTreeView):
    """
    A tree view that uses a QSortFilterProxyModel
    
    Items that have a function set on a user role given will
    have the function invoked when clicked
    """
    
    def __init__(self, item_model: QStandardItemModel, click_user_data=1, parent: QWidget | None = None):
        super().__init__(parent)
        
        # we need qt6 for not filtering out the children if they would be filtered
        # out otherwise
        model = QSortFilterProxyModel()
        model.setRecursiveFilteringEnabled(True)
        model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.setModel(model)
        model.setSourceModel(item_model)
        self._wrapped_model = item_model
        self._proxy_model = model

        self.click_func = None
        def on_select(index: QModelIndex):
    
            source_index = self.proxy_model.mapToSource(index)
            item: QStandardItem = self.wrapped_model.itemFromIndex(source_index)
            func = item.data(Qt.UserRole + click_user_data)
            if func:
                func()
        
        self.clicked.connect(on_select)
    
    @property
    def wrapped_model(self):
        return self._wrapped_model
    
    @property
    def proxy_model(self):
        return self._proxy_model

class TreeViewSearcher(QWidget):
    
    def __init__(self, tree_view: FilterTreeView, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tree_view = tree_view
        
        self._search_bar = QLineEdit()
        self._search_bar.textChanged.connect(self.search_pkg_tree)
        
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self._search_bar)
        self.layout().addWidget(self._tree_view)
        
        self.layout().setContentsMargins(0, 0, 0, 0)
    
    @property
    def search_bar(self):
        return self._search_bar

    def search_pkg_tree(self, search: str):
        if search and search != '':
            # removes whitespace and escapes all special regex chars
            new_search = escape(search.strip())
            # regex that enforces the text starts with <new_search>
            self._tree_view.proxy_model.setFilterRegularExpression(f'^{new_search}')
            self._tree_view.expandAll()
        else:
            self._tree_view.proxy_model.setFilterRegularExpression('')
            self._tree_view.collapseAll()
        


