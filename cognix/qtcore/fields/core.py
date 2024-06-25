"""
Core definitions of widgets for changing fields and attributes of an object

This is meant as a replacement for the older std_inp_widgets in Ryven.
"""
from __future__ import annotations

from qtpy.QtWidgets import (
    QWidget,
    QLineEdit,
    QHBoxLayout, 
    QVBoxLayout,
    QLabel,
)
from qtpy.QtGui import (
    QIntValidator, 
    QDoubleValidator,
    QValidator,
)


from ..inspector import InspectorWidget, InspectedChangedEvent
from cognixcore import Event

from json import dumps, loads
from types import MappingProxyType

from typing import Generic, TypeVar, TYPE_CHECKING
if TYPE_CHECKING:
    from ..flows.view import FlowView

FieldType = TypeVar('FieldType')

class FieldWidget(Generic[FieldType]):
    """The base class for creating widgets that update a field's/attribute's value"""
    
    class ValueChanged:
        def __init__(self, old: FieldType, new: FieldType):
            self.old = old
            self.new = new 
            
    def __init__(self, insp_widget: InspectorWidget, attr_path: str, label: str = None):
        self._insp_widget = insp_widget
        self._value_changed = Event[FieldWidget.ValueChanged]()
        
        # the attr path might refer to a nested attribute
        # it should be separated by dots .
        self._attr_path = attr_path.split('.')
        self.set_value(self.value, True)
        self.label = label if self.label else self._attr_path[-1]
    
    @property
    def edited_obj(self):
        """
        The object whose field/attribute is being edited
        
        Depending on the path given, this might be a nested object.
        
        It is preferable to call this property once and store it in a variable, as 
        each call may search for the edited_obj all over again.
        """
        e_obj = self.inspector_widget.inspected
        # the edited object is the object before the final destination in the path
        for i in range(len(self._attr_path)-1):
            e_obj = getattr(e_obj, self._attr_path[i])
            
        return e_obj
    
    @property 
    def value(self) -> FieldType:
        """The value of the field/attribute this widget is editting"""
        return getattr(self.edited_obj, self._attr_path[-1])
    
    @value.setter
    def value(self, val: FieldType):
        """Sets the value of the field/attribute and invokes a change event"""
        self.set_value(val)
        
    @property
    def attr_path(self):
        """
        The path to find the attribute from the inspected object to the attribute
        
        Might be a nested path.
        """
        return tuple(self._attr_path)
    
    @property
    def inspector_widget(self):
        """The inspector widget this field widget is attached to"""
        return self._insp_widget
    
    @property
    def value_changed(self):
        """
        An event emitted when a value is changed
        
        The parameters are old_value, new_value
        """
        return self._value_changed
    
    def set_value(self, val: FieldType, silent=False):
        """Sets the value of an object"""
        
        old_val = self.value
        if old_val == val:
            return False
        
        e_obj = self.edited_obj
        self.__set_value(e_obj, val)
        if not silent:
            self._value_changed.emit(old_val, val)
        
        return True
    
    def __set_value(self, obj, val: FieldType):
        setattr(obj, self.attr_path[-1], val)


class SingleLineWidget(QWidget):
    """A shortcut class for implementing single line widgets"""
    
    def __init__(self, label: str = None):
        super().__init__()
        layout = QHBoxLayout()
        self.label = QLabel(label)
        layout.addWidget(self.label)
        self.setLayout(layout)
        self.setContentsMargins(0, 0, 0, 0)

class TextField(FieldWidget[FieldType], SingleLineWidget):
    """
    A basic field for handling texts. This default version doesn't allow editing the value
    
    This widget is also the default GUI representation of any object as a field
    """
    
    def __init__(
        self, 
        insp_widget: InspectorWidget, 
        attr_path: str, 
        label: str = None,
        validator: QValidator = None,
        enabled=False
    ):
        SingleLineWidget.__init__(self, label)
        
        self.edit_field = QLineEdit()
        self.edit_field.setEnabled(enabled)
        if validator:
            self.edit_field.setValidator(validator)
        self.edit_field.editingFinished.connect(self.on_editing_finished)
        self.layout().addWidget(self.edit_field)
        
        # this should be at the bottom since it might need attributes set before
        FieldWidget.__init__(self, insp_widget, attr_path, label)
        self.edit_field.setText(str(self.value))
        
    def set_value(self, val: FieldType, silent=False):
        result = super().set_value(val, silent)
        if result:
            self.edit_field.setText(str(val))
        
        return result
    
    def on_editing_finished(self):
        # for most types, this should be ok
        val = loads(self.edit_field.text())
        self.set_value(val)

class FieldInspectorWidget(InspectorWidget, QWidget):
    """An inspector for any kind kind of value that has a FieldWidget assigned to it"""
    
    def __init__(self, inspected_obj, flow_view: FlowView, val_type: type, path: str, label: str = "value"):
        QWidget.__init__(self)
        self.path = path
        self.label = label
        self.val_type = val_type
        InspectorWidget.__init__(self, inspected_obj, flow_view)
    
    def on_insp_changed(self, change_event: InspectedChangedEvent):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        
        old_inspected, new_inspected = change_event.old, change_event.new
        field_widget_type = self.gui_env.get_field_widget(self.val_type)
        field_widget = (
            field_widget_type(self, self.path, self.label)
            if field_widget_type
            else TextField(self, self.path, self.label)
        )
        layout.addWidget(field_widget)