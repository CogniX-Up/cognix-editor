from .core import *

from qtpy.QtWidgets import (
    QLineEdit,
    QVBoxLayout,
)

from qtpy.QtGui import (
    QIntValidator, 
    QDoubleValidator,
    QValidator,
)

from ..env import field_widget

@field_widget(str)
class StrField(TextField[str]):
    
    def __init__(self, insp_widget: InspectorWidget, attr_path: str, label: str = None, validator: QValidator = None, enabled=True):
        super().__init__(insp_widget, attr_path, label, validator, enabled)
    
    def on_editing_finished(self):
        self.set_value(self.edit_field.text())

@field_widget(int)
class IntField(TextField[int]):
    
    def __init__(self, insp_widget: InspectorWidget, attr_path: str, label: str = None, enabled=True):
        super().__init__(insp_widget, attr_path, label, validator=QIntValidator(), enabled=enabled)

@field_widget(float)
class DoubleField(TextField[float]):
    
    def __init__(self, insp_widget: InspectorWidget, attr_path: str, label: str = None, enabled=True):
        super().__init__(insp_widget, attr_path, label, validator=QDoubleValidator(), enabled=enabled)