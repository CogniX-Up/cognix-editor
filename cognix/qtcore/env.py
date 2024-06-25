"""
The GUI environment that is required for setting associations between GUI types and
object types.

NodeGUI -> Node
InspectorWidget -> object
FieldWidget -> object
"""

from .nodes.gui import NodeGUI
from .inspector import InspectorWidget
from .fields.core import FieldWidget, TextField    

from typing import TypeVar, Generic
from cognixcore import InfoMsgs, Node

ToType = TypeVar('ToType')
"""The To in the From-To type relationship"""
FromType = TypeVar('FromType')
"""The From in the From-To type relationship"""

# We're intentionally omitting type hints because they don't work well
# with decorators or we have no knowledge on how to do this
class Association(Generic[FromType, ToType]):
    """
    A class for associating two types. It associates the definition of
    two types so that you can find the ToType from the FromType. This association
    also handles inheritance through MRO and registered virtual subclasses.

    The registered virtual subclasses search can be slow due to access restrictions
    for specific virtual types.
    
    The fastest approach, albeit a bit cumbersome, would be to explicitly state the
    association between the two types and not rely on inheritance. For small inheritance
    chains, however, the slowdown should be negligible.
    """
        
    def __init__(
        self, 
        parent_base_type, 
        assoc_base_type
    ):
        
        self.__from_type = parent_base_type
        self.__to_type = assoc_base_type
        self.__from_to_dict: dict = {}
        """Stores any direct associations internally."""
    
    @property
    def from_type(self):
        return self.__from_type
    
    @property
    def to_type(self):
        return self.__to_type
    
    def associate_decor(self, *from_types):
        """Returns a decorator for creating the association"""
        
        def register(to_type):
            return self.associate(to_type, *from_types)

        return register

    def associate(self, to_type, *from_types):
        """Creates a from-to association"""
        
        if not issubclass(to_type, self.__to_type):
            raise ValueError(f"To Type: {to_type} is not of type {self.__to_type}")
        
        for from_type in from_types:
            
            if not issubclass(from_type, self.__from_type):
                InfoMsgs.write(f"From Type: {from_type} is not of type {self.__from_type}")
                continue
                    
            if from_type in self.__from_to_dict:
                InfoMsgs.write(f'{from_type} has defined an explicit association {self.__from_to_dict[from_type]}')
                continue
        
            self.__from_to_dict[from_type] = to_type
            InfoMsgs.write(f"Registered association: {to_type} for {from_type}")
        
        return to_type   

    def get_assoc(self, from_type: type[FromType], check_mro=True, check_virtual=False) -> type[ToType] | None:
        """
        Retrieves an association if it exists
        
        MRO is the typical python inheritance check.
        
        """
        
        if not issubclass(from_type, self.__from_type):
            raise ValueError(f"From Type: {from_type} is not of type {self.__from_type}")
        
        # returns an immediate association, if it exists 
        if not check_mro and not check_mro:
            return self.__from_to_dict.get(from_type)
        
        # ABC checking 
        
        # Checks based on the MRO
        if check_mro:
            for t in from_type.mro():
                to_type = self.__from_to_dict.get(t)
                if to_type:
                    return to_type
        
        # At this point, all we can do is check every key and stop if we find a subclss
        if check_virtual:
            for key, value in self.__from_to_dict.items():
                if issubclass(from_type, key):
                    return value

#   Holds all information regarding a GUI environment
class GUIEnv:
    """Provides utilities for interfacing with the GUI side of various types"""
    
    def __init__(
        self,
        node_gui_assoc=Association[Node, NodeGUI](Node, NodeGUI),
        obj_insp_assoc=Association[object, InspectorWidget](object, InspectorWidget),
        obj_field_assoc=Association[object, FieldWidget](object, FieldWidget)
    ):
        super().__init__()
        self._node_gui_assoc = node_gui_assoc
        self._obj_insp_assoc = obj_insp_assoc
        self._obj_field_assoc = obj_field_assoc
    
    def get_node_gui(self, node_type: type[Node]):
        return self._node_gui_assoc.get_assoc(node_type)
    
    def get_inspector(self, obj):
        return self._obj_insp_assoc.get_assoc(obj)
    
    def get_field_widget(self, obj):
        result = self._obj_field_assoc.get_assoc(obj)
        if not result:
            result = TextField
        return result
        
    def load_env(self):
        """
        Must be called before the start of an appliction
        to register built_in types
        """
        from .fields import built_in
        # attempt to include traits configs
        try:
            from cognixcore.config.traits import (
                NodeTraitsConfig, 
                NodeTraitsGroupConfig,
            )
            from .config.traits import (
                NodeTraitsConfigInspector,
                NodeTraitsGroupConfigInspector,
            )
            self._obj_insp_assoc.associate(
                NodeTraitsConfigInspector,
                NodeTraitsConfig, 
            )
            self._obj_insp_assoc.associate(
                NodeTraitsGroupConfigInspector,
                NodeTraitsGroupConfig,
            )
        except ImportError as e:
            print("traits and traitsui aren't installed. Skipping")

_gui_env = GUIEnv()

def get_gui_env():
    """
    Retrieves the GUI environment
    
    Useful for creating custom implementation for setting the GUI of types
    """
    return _gui_env

def node_gui(*node_cls):
    """
    Shortcut decorator for registering a NodeGUI type for a Node type. Inheritance applies.
    """
    return _gui_env._node_gui_assoc.associate_decor(*node_cls)

def inspector(*obj_type):
    """
    Shortcut decorator for registering an InspectorWidget type for an object type. Inheritance applies.
    """
    return _gui_env._obj_insp_assoc.associate_decor(*obj_type)

def field_widget(*obj_type):
    """
    Shortcut decorator for registering a FieldWidget type for an object type. Inheritance applies.
    """
    
    return _gui_env._obj_field_assoc.associate_decor(*obj_type)
