from __future__ import annotations
from qtpy.QtWidgets import (
    QWidget, 
    QHBoxLayout,
    QVBoxLayout, 
    QLabel, 
    QMenu, 
    QAction,
    QLineEdit,
    QScrollArea,
    QMessageBox,
)
from qtpy.QtGui import QIcon, QImage
from qtpy.QtCore import Qt, QEvent, QBuffer, Signal

from ..utils import Location, connect_signal_event
from cognixcore import Flow

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..session_gui import SessionGUI
    
    
class FlowsListItemWidget(QWidget):
    """A QWidget representing a single Flow for the FlowsListWidget."""

    def __init__(self, flows_list_widget: FlowsListWidget, session_gui: SessionGUI, flow: Flow):
        super().__init__()

        self.session_gui = session_gui
        self.flow = flow
        self.flow_view = self.session_gui.flow_views[flow]
        self.flows_list_widget = flows_list_widget
        self.previous_flow_title = ''
        self._thumbnail_source = ''
        self.ignore_title_line_edit_signal = False


        # UI

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        #   create icon

        # TODO: change this icon
        flow_icon = QIcon(Location.PACKAGE_PATH + '/resources/pics/script_picture.png')

        icon_label = QLabel()
        icon_label.setFixedSize(20, 20)
        icon_label.setStyleSheet('border:none;')
        icon_label.setPixmap(flow_icon.pixmap(20, 20))
        main_layout.addWidget(icon_label)

        #   title line edit

        self.title_line_edit = QLineEdit(flow.title, self)
        self.title_line_edit.setPlaceholderText('title')
        self.title_line_edit.setEnabled(False)
        self.title_line_edit.editingFinished.connect(self.title_line_edit_editing_finished)

        main_layout.addWidget(self.title_line_edit)

        self.setLayout(main_layout)



    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.title_line_edit.geometry().contains(event.pos()):
                self.title_line_edit_double_clicked()
                return


    def event(self, event):
        if event.type() == QEvent.ToolTip:

            # generate preview img as QImage
            img: QImage = self.flow_view.get_viewport_img().scaledToHeight(200)

            # store the img data in QBuffer to load it directly from memory
            buffer = QBuffer()
            img.save(buffer, 'PNG')

            # generate html from data in memory
            html = f"<img src='data:image/png;base64, { bytes( buffer.data().toBase64() ).decode() }'>"

            # show tooltip
            self.setToolTip(html)

        return QWidget.event(self, event)


    def contextMenuEvent(self, event):
        menu: QMenu = QMenu(self)

        delete_action = QAction('delete')
        delete_action.triggered.connect(self.action_delete_triggered)

        actions = [delete_action]
        for a in actions:
            menu.addAction(a)

        menu.exec_(event.globalPos())


    def action_delete_triggered(self):
        self.flows_list_widget.del_flow(self.flow, self)


    def title_line_edit_double_clicked(self):
        self.title_line_edit.setEnabled(True)
        self.title_line_edit.setFocus()
        self.title_line_edit.selectAll()

        self.previous_flow_title = self.title_line_edit.text()


    def title_line_edit_editing_finished(self):
        if self.ignore_title_line_edit_signal:
            return

        title = self.title_line_edit.text()

        self.ignore_title_line_edit_signal = True

        if self.session_gui.core_session.new_flow_title_valid(title):
            self.session_gui.core_session.rename_flow(flow=self.flow, title=title)
        else:
            self.title_line_edit.setText(self.previous_flow_title)

        self.title_line_edit.setEnabled(False)
        self.ignore_title_line_edit_signal = False


class FlowsListWidget(QWidget):
    """Convenience class for a QWidget to easily manage the flows of a session."""

    _flow_deleted_signal = Signal(Flow)
    _flow_renamed_signal = Signal(Flow, str)
    
    def __init__(self, session_gui: SessionGUI):
        super().__init__()

        self.session_gui = session_gui
        self.flow_items: dict[Flow, FlowsListItemWidget] = {}
        self.ignore_name_line_edit_signal = False  # because disabling causes firing twice otherwise

        self.setup_UI()

        self.session_gui.flow_view_created.connect(self._on_flow_created)
        
        s = self.session_gui.core_session
        connect_signal_event(
            self._flow_deleted_signal,
            s.flow_deleted,
            self._on_flow_deleted
        )
        connect_signal_event(
            self._flow_renamed_signal,
            s.flow_renamed,
            self._on_flow_renamed
        )

    def setup_UI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignTop)
        self.setLayout(main_layout)

        # list scroll area

        self.list_scroll_area = QScrollArea(self)
        self.list_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.list_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.list_scroll_area.setWidgetResizable(True)
        self.list_scroll_area.setContentsMargins(0, 0, 0, 0)

        self.scroll_area_widget = QWidget()
        self.scroll_area_widget.setContentsMargins(0, 0, 0, 0)
        self.list_scroll_area.setWidget(self.scroll_area_widget)

        self.list_layout = QVBoxLayout()
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setAlignment(Qt.AlignTop)
        self.scroll_area_widget.setLayout(self.list_layout)

        self.layout().addWidget(self.list_scroll_area)

        # line edit

        self.new_flow_title_lineedit = QLineEdit()
        self.new_flow_title_lineedit.setPlaceholderText('new flow\'s title')
        self.new_flow_title_lineedit.returnPressed.connect(self.create_flow)

        main_layout.addWidget(self.new_flow_title_lineedit)

    def create_flow(self):
        title = self.new_flow_title_lineedit.text()

        if self.session_gui.core_session.new_flow_title_valid(title):
            self.session_gui.core_session.create_flow(title=title)

    def _on_flow_created(self, flow, flow_view):
        new_widget = FlowsListItemWidget(self, self.session_gui, flow)
        self.list_layout.addWidget(new_widget)
        self.flow_items[flow] = new_widget
    
    def _on_flow_deleted(self, flow: Flow):
        flow_item = self.flow_items[flow]
        del self.flow_items[flow]
        self.list_layout.removeWidget(flow_item)
    
    def _on_flow_renamed(self, flow: Flow, name: str):
        flow_item = self.flow_items[flow]
        flow_item.title_line_edit.setText(flow.title)

    def del_flow(self, flow, flow_widget):
        msg_box = QMessageBox(QMessageBox.Warning, 'sure about deleting flow?',
                              'You are about to delete a flow. This cannot be undone, all content will be lost. '
                              'Do you want to continue?', QMessageBox.Cancel | QMessageBox.Yes, self)
        msg_box.setDefaultButton(QMessageBox.Cancel)
        ret = msg_box.exec()
        if ret != QMessageBox.Yes:
            return
        
        self.session_gui.core_session.delete_flow(flow)
        # self.recreate_list()
