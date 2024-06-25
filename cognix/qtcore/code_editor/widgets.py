from __future__ import annotations

from qtpy.QtGui import (
    QFont, 
    QFontMetrics, 
    QTextCursor, 
    QKeySequence,
)
from qtpy.QtWidgets import (
    QWidget,
    QTextEdit, 
    QDialog, 
    QGridLayout, 
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QHBoxLayout,
)
from qtpy.QtCore import Qt

from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import get_formatter_by_name

from .pygments.dracula import DraculaStyle
from .pygments.light import LightStyle

from .code_updater import SrcCodeUpdater
from .codes_storage import ( 
    NodeTypeCodes,
    Inspectable, 
    NodeInspectable, 
    MainWidgetInspectable, 
    CustomInputWidgetInspectable,
    SourceCodeStorage,
)

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from cognixcore import Node
    from ...qtcore import NodeGUI

class EditSrcCodeInfoDialog(QDialog):

    dont_show_again = False

    def __init__(self, parent):
        super(EditSrcCodeInfoDialog, self).__init__(parent)

        self.setLayout(QGridLayout())

        # info text edit
        info_text_edit = QTextEdit()
        info_text_edit.setHtml('''
            <h2 style="font-family: Poppins; font-size: xx-large; color: #a9d5ef;">Some info before you delete the
            universe</h2>
            <div style="font-family: Corbel; font-size: x-large;">
                <p>
                    Yes, you can change method implementations of objects.
                    This can be quite useful but since changing an instance's implementation at runtime is kinda sketchy, 
                    you should be a bit careful, it's not exactly bulletproof, and doesnt <i>always</i> work.
                    When you override a method implementation, a new function object will be created using python's ast 
                    module, which then gets bound to the object as method, which essentially shadows the old implementation. 
                    Therefore, you might need to add imports etc. you noder uses in the original nodes package. 
                    All changes are temporary and only apply on a single 
                    object.
                </p>
                <p>
                    Have fun.
                </p>
            </div>
        ''')
        info_text_edit.setReadOnly(True)
        self.layout().addWidget(info_text_edit, 0, 0, 1, 2)

        dont_show_again_button = QPushButton('Stop being annoying')
        dont_show_again_button.clicked.connect(self.close_and_dont_show_again)
        self.layout().addWidget(dont_show_again_button, 1, 0)

        ok_button = QPushButton('Got it')
        ok_button.clicked.connect(self.accept)
        self.layout().addWidget(ok_button, 1, 1)

        ok_button.setFocus()

        self.setWindowTitle('Editing Source Code Info')
        self.resize(560, 366)

    def close_and_dont_show_again(self):
        EditSrcCodeInfoDialog.dont_show_again = True
        self.accept()
  
        
class CodeEditorWidget(QTextEdit):
    
    def __init__(self, window_theme='dark', highlight=True, enabled=False):
        super(CodeEditorWidget, self).__init__()

        self.highlighting = highlight
        self.editing = enabled
        
        f = QFont('Consolas', 12)
        self.setFont(f)
        self.update_tab_stop_width()

        # also not working:
        # copy_shortcut = QShortcut(QKeySequence.Copy, self)
        # copy_shortcut.activated.connect(self.copy)
        # https://forum.qt.io/topic/121474/qshortcuts-catch-external-shortcuts-from-readonly-textedit/4

        self.textChanged.connect(self.text_changed)
        self.block_change_signal = False

        self.lexer = get_lexer_by_name('python')

        self.update_formatter(window_theme)

        if self.editing:
            self.enable_editing()
        else:
            self.disable_editing()

    def update_formatter(self, window_theme):
        if window_theme == 'dark':
            self.formatter = get_formatter_by_name('html', noclasses=True, style=DraculaStyle)
        else:
            self.formatter = get_formatter_by_name('html', noclasses=True, style=LightStyle)

    def enable_editing(self):
        self.editing = True
        self.setReadOnly(False)
        self.update_appearance()

    def disable_editing(self):
        self.editing = False
        self.setReadOnly(True)
        self.update_appearance()

    def disable_highlighting(self):
        self.highlighting = False
        # self.update_appearance()

    def enable_highlighting(self):
        self.highlighting = True
        # self.update_appearance()

    def highlight(self):
        self.enable_highlighting()
        self.update_appearance()

    def mousePressEvent(self, e) -> None:
        if not self.highlighting and not self.editing:
            self.highlight()
        else:
            return super().mousePressEvent(e)

    def wheelEvent(self, e) -> None:
        super().wheelEvent(e)
        if e.modifiers() == Qt.CTRL:  # for some reason this also catches touch pad zooming
            self.update_tab_stop_width()
            # and for some reason QTextEdit doesn't seem to zoom using zoomIn()/zoomOut(), but by changing the font size
            # so I need to update the (pixel measured) tab stop width

    def set_code(self, new_code):
        # self.highlighting = self.editing
        self.setText(new_code.replace('    ', '\t'))
        self.update_appearance()

    def get_code(self):
        return self.toPlainText().replace('\t', '    ')

    def text_changed(self):
        if not self.block_change_signal:
            self.update_appearance()

    def update_tab_stop_width(self):
        self.setTabStopWidth(QFontMetrics(self.font()).width('_')*4)

    def update_appearance(self):
        if not self.editing and not self.highlighting:
            return

        self.setUpdatesEnabled(False)  # speed up, doesnt really seem to help though

        cursor_pos = self.textCursor().position()
        scroll_pos = (self.horizontalScrollBar().sliderPosition(), self.verticalScrollBar().sliderPosition())

        self.block_change_signal = True

        highlighted = """
<style>
* {
    font-family: Consolas;
}
</style>
        """ + highlight(self.toPlainText(), self.lexer, self.formatter)

        self.setHtml(highlighted)

        self.block_change_signal = False

        if self.hasFocus():
            c = QTextCursor(self.document())
            c.setPosition(cursor_pos)
            self.setTextCursor(c)
            self.horizontalScrollBar().setSliderPosition(scroll_pos[0])
            self.verticalScrollBar().setSliderPosition(scroll_pos[1])
        else:
            self.textCursor().setPosition(0)

        self.setUpdatesEnabled(True)


class LoadSrcCodeButton(QPushButton):
    def __init__(self):
        super().__init__('load source code')
        self._node: Node = None
    
    @property
    def node(self):
        return self._node
    
    @node.setter
    def node(self, node):
        self._node = node


class LinkedRadioButton(QRadioButton):
    """Represents a button linked to one particular inspectable object."""

    def __init__(self, name, obj: Inspectable):
        super().__init__(name)
        self.representing: Inspectable = obj


class CodePreviewWidget(QWidget):
    def __init__(self, src_code_storage: SourceCodeStorage, window_theme='dark'):
        super().__init__()

        self.current_insp: Inspectable | None = None
        self.cd_storage = src_code_storage

        # widgets
        self.radio_buttons = []
        self.text_edit = CodeEditorWidget(window_theme)

        self.setup_ui()
        self._set_node(None)

    def setup_ui(self):

        secondary_layout = QHBoxLayout()

        # load source code button
        self.load_code_button = LoadSrcCodeButton()
        self.load_code_button.setProperty('class', 'small_button')
        secondary_layout.addWidget(self.load_code_button)
        self.load_code_button.hide()
        self.load_code_button.clicked.connect(self._load_code_button_clicked)

        # class radio buttons widget
        self.class_selection_layout = QHBoxLayout()  # QGridLayout()

        secondary_layout.addLayout(self.class_selection_layout)
        self.class_selection_layout.setAlignment(Qt.AlignLeft)
        # secondary_layout.setAlignment(self.class_selection_layout, Qt.AlignLeft)

        # edit source code buttons
        if self.cd_storage.edit_src_codes:
            self.edit_code_button = QPushButton('edit')
            self.edit_code_button.setProperty('class', 'small_button')
            self.edit_code_button.setMaximumWidth(100)
            self.edit_code_button.clicked.connect(self._edit_code_button_clicked)
            self.override_code_button = QPushButton('override')
            self.override_code_button.setProperty('class', 'small_button')
            self.override_code_button.setMaximumWidth(100)
            self.override_code_button.setEnabled(False)
            self.override_code_button.clicked.connect(self._override_code_button_clicked)
            self.reset_code_button = QPushButton('reset')
            self.reset_code_button.setProperty('class', 'small_button')
            self.reset_code_button.setMaximumWidth(206)
            self.reset_code_button.setEnabled(False)
            self.reset_code_button.clicked.connect(self._reset_code_button_clicked)

            edit_buttons_layout = QHBoxLayout()
            # edit_buttons_layout.addWidget(self.highlight_code_button)
            edit_buttons_layout.addWidget(self.edit_code_button)
            edit_buttons_layout.addWidget(self.override_code_button)
            edit_buttons_layout.addWidget(self.reset_code_button)
            # edit_buttons_layout.addWidget(self.highlight_code_button)

            secondary_layout.addLayout(edit_buttons_layout)
            edit_buttons_layout.setAlignment(Qt.AlignRight)

        main_layout = QVBoxLayout()
        main_layout.addLayout(secondary_layout)
        main_layout.addWidget(self.text_edit)
        self.setLayout(main_layout)

    def set_selected_nodes(self, nodes):
        if len(nodes) == 0:
            self._set_node(None)
        else:
            self._set_node(nodes[-1])

    def _set_node(self, node: Node | None):
        self.node = node

        if node is None:
            # clear view
            if self.cd_storage.edit_src_codes:
                self.edit_code_button.setEnabled(False)
                self.override_code_button.setEnabled(False)
                self.reset_code_button.setEnabled(False)
            self.text_edit.set_code('')
            self._clear_class_layout()
        else:
            if self.cd_storage.class_codes.get(node.__class__) is None:
                # source code not loaded yet
                self.load_code_button.node = node
                self.load_code_button.show()
                self._clear_class_layout()
                self._update_code(NodeInspectable(node, 'source not loaded'))
            else:
                self._process_node_src(node)

    def _process_node_src(self, node: Node):
        self._rebuild_class_selection(node)
        code = self.cd_storage.class_codes[node.__class__].node_cls
        if self.cd_storage.edit_src_codes and node in self.cd_storage.modif_codes:
            code = self.cd_storage.modif_codes[node]
        self._update_code(NodeInspectable(node, code))

    def _update_code(self, insp: Inspectable):
        if self.cd_storage.edit_src_codes:
            self._disable_editing()
            self._update_radio_buttons_edit_status()
            self.edit_code_button.setEnabled(True)
            self.reset_code_button.setEnabled(insp.obj in self.cd_storage.modif_codes)

        self.text_edit.disable_highlighting()

        self.current_insp = insp
        self.text_edit.set_code(insp.code)


    def _rebuild_class_selection(self, node: Node):
        self.load_code_button.hide()
        self._clear_class_layout()
        self.radio_buttons.clear()

        node_gui: NodeGUI = node.gui
        codes: NodeTypeCodes = self.cd_storage.class_codes[node.__class__]

        def register_rb(rb: QRadioButton):
           rb.toggled.connect(self._class_rb_toggled)
           self.class_selection_layout.addWidget(rb)
           self.radio_buttons.append(rb)

        # node radio button
        code = codes.node_cls
        code = self.cd_storage.modif_codes.get(node, code)
        register_rb(LinkedRadioButton('node', NodeInspectable(node, code)))

        # main widget radio button
        if codes.main_widget_cls is not None:
            mw = node_gui.main_widget()
            code = codes.main_widget_cls
            code = self.cd_storage.modif_codes.get(mw, code)
            register_rb(LinkedRadioButton(
                'main widget',
                MainWidgetInspectable(node, node_gui.main_widget(), code)
            ))

        # custom input widgets
        for i in range(len(node._inputs)):
            inp = node._inputs[i]
            if inp in node_gui.input_widgets:
                name = node_gui.input_widgets[inp]['name']
                widget = node_gui.item.inputs[i].widget
                code = codes.custom_input_widget_clss[name]
                code = self.cd_storage.modif_codes.get(widget, code)
                register_rb(LinkedRadioButton(
                    f'input {i}', CustomInputWidgetInspectable(node, widget, code)
                ))

        self.radio_buttons[0].setChecked(True)

    def _clear_class_layout(self):
        # clear layout
        for i in range(self.class_selection_layout.count()):
            item = self.class_selection_layout.itemAt(0)
            widget = item.widget()
            widget.hide()
            self.class_selection_layout.removeItem(item)
    
    def _load_code_button_clicked(self):
        node: Node = self.sender().node
        self.cd_storage.load_src_code(node.__class__)
        self.load_code_button.hide()
        self._process_node_src(node)

    def _update_radio_buttons_edit_status(self):
        """Draws radio buttons referring to modified objects bold."""

        for br in self.radio_buttons:
            if self.cd_storage.modif_codes.get(br.representing.obj) is not None:
                # o.setStyleSheet('color: #3B9CD9;')
                f = br.font()
                f.setBold(True)
                br.setFont(f)
            else:
                # o.setStyleSheet('color: white;')
                f = br.font()
                f.setBold(False)
                br.setFont(f)

    def _class_rb_toggled(self, checked):
        if checked:
            rb: LinkedRadioButton = self.sender()
            self._update_code(rb.representing)

    def _edit_code_button_clicked(self):
        if not EditSrcCodeInfoDialog.dont_show_again:
            info_dialog = EditSrcCodeInfoDialog(self)
            accepted = info_dialog.exec_()
            if not accepted:
                return
        self._enable_editing()

    def _enable_editing(self):
        self.text_edit.enable_editing()
        self.override_code_button.setEnabled(True)

    def _disable_editing(self):
        self.text_edit.disable_editing()
        self.override_code_button.setEnabled(False)

    def _override_code_button_clicked(self):
        new_code = self.text_edit.get_code()
        err = SrcCodeUpdater.override_code(
            obj=self.current_insp.obj,
            new_class_src=new_code,
        )
        if err is None:
            self.current_insp.code = new_code
            self.cd_storage.modif_codes[self.current_insp.obj] = new_code
            self._disable_editing()
            self.reset_code_button.setEnabled(True)
            self._update_radio_buttons_edit_status()
        else:
            # TODO: show error message
            ...

    def _reset_code_button_clicked(self):

        insp = self.current_insp
        o = insp.obj
        orig_code = ''
        if isinstance(insp, NodeInspectable):
            orig_code = self.cd_storage.class_codes[o.__class__].node_cls
        elif isinstance(insp, MainWidgetInspectable):
            orig_code = self.cd_storage.class_codes[o.__class__].main_widget_cls
        elif isinstance(insp, CustomInputWidgetInspectable):
            orig_code = self.cd_storage.class_codes[o.__class__].custom_input_widget_clss[o.__class__]

        err = SrcCodeUpdater.override_code(
            obj=self.current_insp.obj,
            new_class_src=orig_code
        )

        if err is None:
            self.current_insp.code = orig_code
            del self.cd_storage.modif_codes[self.current_insp.obj]
            self._update_code(self.current_insp)
        else:
            # TODO: show error message
            ...

