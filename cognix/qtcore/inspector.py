from __future__ import annotations
from .gui_base import SerializableItem
from typing import Generic, TypeVar
from .flows.commands import DelegateCommand

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    # this is kinda bad as a structure
    from .flows.view import FlowView

InspectType = TypeVar('InspectType')
"""A type representing an inspectable object"""

class InspectedChangedEvent(Generic[InspectType]):
    
    def __init__(self, old: InspectType, new: InspectType, created: bool):
        self._old = old
        self._new = new
        self._created = created
    
    @property
    def old(self):
        return self._old
    
    @property
    def new(self):
        return self._new
    
    @property
    def created(self):
        return self._created
    
class InspectorWidget(SerializableItem, Generic[InspectType]):
    """Base class representing an inspector to view and alter the state of an object"""
    
    def __init__(self, inspected_obj: InspectType, flow_view: FlowView):
        self.flow_view = flow_view
        self._inspected = None
        self._set_inspected(inspected_obj, True)
    
    @property
    def gui_env(self):
        return self.flow_view.session_gui.gui_env
    
    @property
    def inspected(self):
        return self._inspected
    
    @inspected.setter
    def inspected(self, val: InspectType):
        self._set_inspected(val, False)

    def _set_inspected(self, val: InspectType, created: bool):
        if self._inspected == val:
            return
        old = self._inspected
        self._inspected = val
        self.on_insp_changed(InspectedChangedEvent(old, val, created))
        
    def on_insp_changed(self, change_event: InspectedChangedEvent[InspectType]):
        """
        VIRTUAL
        
        This needs to be overriden, otherwise it will throw an exception.
        Allows for dynamic reseting of an editor with a different inspectable
        """
        raise NotImplementedError(f"Inspector {self.__class__} does not allow reseting the inspectable")

    def load(self):
        """Called when the inspector is loaded in any kind of gui"""
    
    def unload(self):
        """Called when the inspector is removed from its parent gui"""
        
    def push_undo(self, text: str, undo_fn, redo_fn, silent=False):
        """
        Push an undo function to the undo stack of the flow.
        
        If silent, the redo is not invoked upon pushing.
        """
        self.flow_view.push_undo(
            DelegateCommand(
                self.flow_view,
                text=text,
                on_undo=undo_fn,
                on_redo=redo_fn,
            ),
            silent
        )