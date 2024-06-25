from __future__ import annotations
from qtpy.QtGui import (
    QIcon, 
    QDrag, 
    QMouseEvent, 
    QStandardItem
)
from qtpy.QtCore import (
    QMimeData, 
    Qt,
    QEvent,
    QByteArray,
    Signal,
)
from qtpy.QtWidgets import (
    QWidget, 
    QHBoxLayout, 
    QVBoxLayout,
    QLabel, 
    QMenu, 
    QAction,
    QFrame,
    QLineEdit,
    QScrollArea,
    QDialog,
    QTreeView,
    QPushButton,
)

from cognixcore.base import IdentifiableGroups, Identifiable
from cognixcore.addons.variables import VarsAddon, Variable, VarSubscriber
from cognixcore.addons.variables.builtin import VarType, variable_groups

from ..utils import (
    create_tooltip, 
    connect_signal_event, 
    Location, 
    IdentifiableGroupsModel,
    text_font,
    get_folder_icon,
    get_var_icon,
)
from ..util_widgets import EditVal_Dialog, FilterTreeView, TreeViewSearcher
from ..flows.commands import DelegateCommand
from ..fields.core import FieldInspectorWidget

from json import dumps

from typing import TYPE_CHECKING, Callable, Any
if TYPE_CHECKING:
    from ..flows.view import FlowView

class VariableGroupsModel(IdentifiableGroupsModel[VarType]):
    
    item_clicked_signal = Signal(type)
    
    def __init__(self, groups: IdentifiableGroups[VarType], label="Variable Types", separator='.'):
        super().__init__(groups, label, separator)
        self._selected: type[Any] = None
    
    @property
    def selected(self):
        return self._selected
    
    def create_subgroup(self, name: str, path: str) -> QStandardItem:
        result = IdentifiableGroupsModel[VarType].create_subgroup(self, name, path)
        result.setFont(text_font)
        result.setIcon(get_folder_icon())
        return result
        
    def create_id_item(self, id: Identifiable[VarType]):
        item = QStandardItem(id.name)
        item.setFont(text_font)
        item.setEditable(False)
        item.setDragEnabled(False)
        item.setIcon(get_var_icon())
        
        def on_click():
            self._selected = id.info.val_type
            self.item_clicked_signal.emit(id.info.val_type)
            
        item.setData(on_click, Qt.UserRole + 1)
        return item

class VarTypeDialogue(QDialog):
    
    confirmed = Signal(type)
    
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setLayout(QVBoxLayout())
        self.setWindowTitle("Variable Types")
        
        # use the built in variable types for now
        self.data_model = VariableGroupsModel(variable_groups)
        
        # create tree view and model
        self.tree_view = FilterTreeView(self.data_model)
        self.tree_searcher = TreeViewSearcher(self.tree_view)
        self.tree_searcher.search_bar.setPlaceholderText('search variable types...')
        self.layout().addWidget(self.tree_searcher)
        
        # button
        self.button = QPushButton("Change Data")
        def on_click():
            if self.data_model._selected:
                self.confirmed.emit(self.data_model.selected)
                self.data_model._selected = None
            
            self.close()
            
        self.button.clicked.connect(on_click)
        self.layout().addWidget(self.button)
        
        self.confirm_func = None
    
    def set_confirm_func(self, func: Callable[[type[Any]], None]):
        if self.confirm_func:
            self.confirmed.disconnect(self.confirm_func)
        self.confirmed.connect(func)
        self.confirm_func = func
      
class VarsItemWidget(QWidget):
    """A QWidget representing a single script variable for the VariablesListWidget."""
    
    class VarIcon(QLabel):
        
        fold_changed = Signal(bool)
        FOLDED = True
        
        def __init__(self, parent: QWidget | None = None):
            super().__init__(parent)

            self.icon_right = QIcon(Location.PACKAGE_PATH+'/resources/pics/variable_picture_right.png')
            self.icon_right_pix = self.icon_right.pixmap(15, 15)
            self.icon_down = QIcon(Location.PACKAGE_PATH+'/resources/pics/variable_picture_down.png')
            self.icon_down_pix = self.icon_down.pixmap(15, 15)
            
            self.setFixedSize(15, 15)
            self.setStyleSheet('border:none;')
            self._folded = True
            self.setPixmap(self.icon_right_pix)
        
        @property
        def folded(self):
            return self._folded
        
        @folded.setter
        def folded(self, val: bool):
            if val == self._folded:
                return
            self._folded = val
            self.setPixmap(self.icon_right_pix if self.folded else self.icon_down_pix)
            self.fold_changed.emit(self._folded)
            
        def mousePressEvent(self, event: QMouseEvent):
            if event.button() == Qt.LeftButton:
                self.folded = not self.folded
            QLabel.mousePressEvent(self, event)
            
        
    def __init__(self, vars_list_widget: VariablesListWidget, var: Variable):
        super().__init__()

        self.vars_addon = var.addon
        self.flow = var.flow
        self.var = var
        self.vars_list_widget = vars_list_widget
        self.previous_var_name = ''  # for editing

        self.ignore_name_line_edit_signal = False
        # UI

        self.main_layout = main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(main_layout)
        # create icon

        # content-layout
        self.content_widget = QFrame()
        self.content_widget.setFrameStyle(QFrame.StyledPanel | QFrame.Plain)
        self.content_widget.setLineWidth(1)
        self.content_widget.setLayout(QVBoxLayout())
        self.content_widget.layout().setContentsMargins(1, 1, 1, 1)
        main_layout.addWidget(self.content_widget)
        
        #   name line edit and type and icon

        self.name_type_widget = QWidget()
        self.name_type_widget.setLayout(QHBoxLayout())
        
        # icon
        self.icon_label = VarsItemWidget.VarIcon()
        self.name_type_widget.layout().addWidget(self.icon_label)
                
        # name edit
        self.name_line_edit = QLineEdit(self.var.name, self)
        self.name_line_edit.setPlaceholderText('name')
        self.name_line_edit.setEnabled(False)
        self.name_line_edit.editingFinished.connect(self.name_line_edit_editing_finished)
        self.name_type_widget.layout().addWidget(self.name_line_edit)
        
        # type edit
        self.type_button = QPushButton(text=str(var.var_type.name))
        self.type_button.setFixedWidth(125)
        def on_open_type_dial():
            # TODO adjust position here
            def on_confirm(val_type):
                self.var.set_type(val_type)
                
            self.type_dial.set_confirm_func(on_confirm)
            self.type_dial.exec()
            
        self.type_button.clicked.connect(on_open_type_dial)
        self.name_type_widget.layout().addWidget(self.type_button)
        
        self.content_widget.layout().addWidget(self.name_type_widget)
        
        # Data options
        self.value_container = QWidget()
        self.value_container.setLayout(QVBoxLayout())
        self.value_container.setVisible(False)
        self.content_widget.layout().addWidget(self.value_container)
        
        # connect config container to label
        def toggle_config(folded: bool):
            self.value_container.setVisible(not folded)
        self.icon_label.fold_changed.connect(toggle_config)
        
        self.field_inspector = None
        self.build_inspector()
        
    @property
    def type_dial(self):
        return self.vars_list_widget.type_dial
    
    def build_inspector(self):
        if self.field_inspector:
            self.value_container.layout().removeWidget(self.field_inspector)
        
        session_gui = self.vars_list_widget.flow_view.session_gui
        self.field_inspector = FieldInspectorWidget(
            self.var,
            self.vars_list_widget.flow_view,
            self.var.var_type.val_type,
            '_value'
        )
        self.value_container.layout().addWidget(self.field_inspector)
        self.value_container.layout().setContentsMargins(0, 0, 0, 0)
        
    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            if self.name_line_edit.geometry().contains(event.pos()):
                self.name_line_edit_double_clicked()
                return

    # TODO make it draggable to the view
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            #Fold
            #self.icon_label.mouseReleaseEvent(event)
            
            # Drag
            drag = QDrag(self)
            mime_data = QMimeData()
            data_text = self.get_drag_data()
            data = QByteArray(bytes(data_text, 'utf-8'))
            mime_data.setData('text/plain', data)
            drag.setMimeData(mime_data)
            drop_action = drag.exec_()
            return

    def event(self, event):
        if event.type() == QEvent.ToolTip:
            try:
                tooltip_str = create_tooltip(self.var.value)
                tooltip_str = f"val:type {str(type(self.var.value))}\n{tooltip_str}"
            except Exception as e:
                tooltip_str = "couldn't stringify value"
            self.setToolTip(tooltip_str)

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
        self.vars_list_widget.del_var(self.var)

    def action_edit_val_triggered(self):
        edit_var_val_dialog = EditVal_Dialog(self, self.var.get())
        accepted = edit_var_val_dialog.exec_()
        if accepted:
            self.var.set(edit_var_val_dialog.get_val())
            # self.vars_addon.create_var(self.flow, self.var.name, edit_var_val_dialog.get_val())

    def name_line_edit_double_clicked(self):
        self.name_line_edit.setEnabled(True)
        self.name_line_edit.setFocus()
        self.name_line_edit.selectAll()

        self.previous_var_name = self.name_line_edit.text()

    def get_drag_data(self):
        data = {'type': 'variable',
                'name': self.var.name,
                'value': self.var.value}  # value is probably unnecessary
        data_text = dumps(data)
        return data_text

    def name_line_edit_editing_finished(self):
        if self.ignore_name_line_edit_signal:
            return

        new_name = self.name_line_edit.text()

        self.ignore_name_line_edit_signal = True
        
        rename_result = self.vars_addon.rename_var(self.flow, self.var.name, new_name)
        if not rename_result:
            self.name_line_edit.setText(self.previous_var_name)

        self.name_line_edit.setEnabled(False)
        self.ignore_name_line_edit_signal = False
    
    def set_name_text(self, name: str):
        self.ignore_name_line_edit_signal = True
        self.name_line_edit.setText(name)
        self.ignore_name_line_edit_signal = False


class VariablesListWidget(QWidget):
    """Convenience class for a QWidget to easily manage script variables of a script."""

    var_created_signal = Signal(Variable)
    var_deleted_signal = Signal(Variable, VarSubscriber)
    var_renamed_signal = Signal(Variable, str)
    var_value_changed_signal = Signal(Variable, Any)
    var_type_changed_signal = Signal(Variable, Any)
    
    def __init__(
        self, 
        vars_addon: VarsAddon, 
        flow_view: FlowView,
        data_type_dial: VarTypeDialogue,         
    ):
        
        super(VariablesListWidget, self).__init__()

        self.vars_addon = vars_addon
        self.flow_view = flow_view
        self.flow = self.flow_view.flow
        self.type_dial = data_type_dial
        
        # signals and events
        connect_signal_event(self.var_created_signal, self.vars_addon.var_created, self.on_var_created)
        connect_signal_event(self.var_deleted_signal, self.vars_addon.var_deleted, self.on_var_deleted)
        connect_signal_event(self.var_renamed_signal, self.vars_addon.var_renamed, self.on_var_renamed)
        connect_signal_event(self.var_value_changed_signal, self.vars_addon.var_value_changed, self.on_var_value_changed)
        connect_signal_event(self.var_type_changed_signal, self.vars_addon.var_type_changed, self.on_var_type_changed)
        
        self.widgets: dict[str, VarsItemWidget] = {}
        # to recreate the vars
        self.deleted_vars: dict[str, VarSubscriber] = {}        
        
        self.setup_UI()
        
    def setup_UI(self):
        main_layout = QVBoxLayout()

        self.list_layout = QVBoxLayout()
        self.list_layout.setAlignment(Qt.AlignTop)

        # list scroll area

        self.list_scroll_area = QScrollArea()
        self.list_scroll_area.setWidgetResizable(True)
        self.list_scroll_area.setContentsMargins(0, 0, 0, 0)

        w = QWidget()
        w.setContentsMargins(0, 0, 0, 0)
        w.setLayout(self.list_layout)

        self.list_scroll_area.setWidget(w)

        main_layout.addWidget(self.list_scroll_area)

        # controls

        self.new_var_name_lineedit = QLineEdit()
        self.new_var_name_lineedit.setPlaceholderText('new var\'s title')
        self.new_var_name_lineedit.returnPressed.connect(self.new_var_LE_return_pressed)

        main_layout.addWidget(self.new_var_name_lineedit)

        self.setContentsMargins(0, 0, 0, 0)
        self.setLayout(main_layout)

        self.recreate_list()

    def push_undo(self, text: str, on_undo, on_redo):
        self.flow_view.push_undo(
            DelegateCommand(
                self.flow_view,
                text,
                on_undo,
                on_redo
            )
        )
        
    def on_var_created(self, var: Variable):
        if var.flow == self.flow:
            v_sub = var.subscriber
            def redo():
                w = VarsItemWidget(self, var)
                self.widgets[var.name] = w
                self.list_layout.addWidget(w)
                self.vars_addon.add_var(self.flow, v_sub)
                
            def undo():
                w = self.widgets[var.name]
                del self.widgets[var.name]
                w.setParent(None)
                # forcibly remove the var
                var.addon.remove_var(self.flow, var)
            
            self.push_undo(
                f"Created Variable: {var.name} : {var.value}",
                undo,
                redo
            )
                

    def on_var_deleted(self, var: Variable, var_sub: VarSubscriber):
        if var.name in self.widgets:
            w = self.widgets[var.name]
            def redo():
                w.setParent(None)
                del self.widgets[var.name]
                self.vars_addon.remove_var(self.flow, var)
                
            def undo():
                self.widgets[var.name] = w
                self.list_layout.addWidget(w)
                # forcibly add the var
                self.vars_addon.add_var(self.flow, var_sub)
            
            self.push_undo(
                f"Deleted Variable: {var.name}",
                undo,
                redo
            )      

    def on_var_renamed(self, var: Variable, old_name: str):
        
        new_name = var.name
        def undo_redo(new_name: str, old_name: str):
            def _undo_redo():
                w = self.widgets[old_name]
                del self.widgets[old_name]
                self.widgets[new_name] = w
                w.set_name_text(new_name)
                self.vars_addon.rename_var(self.flow, old_name, new_name, True)
            return _undo_redo
        
        self.push_undo(
            f"Renamed Variable: {old_name} -> {new_name}",
            undo_redo(old_name, new_name),
            undo_redo(new_name, old_name)
        )
    
    def on_var_value_changed(self, var: Variable, old_value: Any):
        new_value = var.value
        
        def undo_redo(val):
            def _undo_redo():
                var.set(val, True)
                w = self.widgets[var.name]
                w.value_field.value = val
            return _undo_redo
        
        self.push_undo(
            f"Variable {var.name} Value Change: {old_value} -> {new_value}",
            undo_redo(old_value),
            undo_redo(new_value)
        )
    
    def on_var_type_changed(self, var: Variable, old_type: VarType):
        new_val_type = var.var_type.val_type
        
        def undo_redo(val_type):
            def _undo_redo():
                
                var.set_type(val_type, silent=True)
                widget = self.widgets[var.name]
                widget.type_button.setText(var.var_type.val_type.__name__)
                widget.build_inspector()
            
            return _undo_redo

        self.push_undo(
            f"Variable {var.name} Type Change: {old_type} -> {new_val_type}",
            undo_redo(old_type.val_type),
            undo_redo(new_val_type),
        )
       
    def recreate_list(self):
        for w in self.widgets.values():
            w.setParent(None)
            del w

        self.widgets.clear()

        for var_name, var_sub in self.vars_addon.flow_variables[self.flow].items():
            new_widget = VarsItemWidget(self, var_sub.variable)
            self.widgets[var_name] = new_widget

        self.rebuild_list()

    def rebuild_list(self):
        for w in self.widgets.values():
            w.setParent(None)

        for w in self.widgets.values():
            self.list_layout.addWidget(w)

    def new_var_LE_return_pressed(self):
        name = self.new_var_name_lineedit.text()
        if not self.vars_addon.var_name_valid(self.flow, name=name):
            return
        v = self.vars_addon.create_var(self.flow, name=name)

    def del_var(self, var):
        self.vars_addon.delete_var(self.flow, var.name)
