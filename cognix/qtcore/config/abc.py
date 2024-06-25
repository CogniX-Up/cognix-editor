from __future__ import annotations
from ..nodes.inspector import InspectorWidget, InspectedChangedEvent
from cognixcore import NodeConfig, Node

from typing import TYPE_CHECKING, Callable, Any, TypeVar
if TYPE_CHECKING:
    from ..nodes.gui import NodeGUI 

ConfigType = TypeVar('ConfigType', bound=NodeConfig)

class NodeConfigInspector(InspectorWidget[ConfigType]):
    """Base class for inspecting a node config"""
    
    @classmethod
    def create_config_changed_event(cls, node: Node, gui: NodeGUI) -> Callable[[Any], None]:
        """
        VIRTUAL
        
        Override this to connect a config changed event to the gui.
        """
        pass
    
    def __init__(self, params: tuple[ConfigType, NodeGUI]):
        config, gui = params
        super().__init__(config, gui.flow_view)
    
    def on_insp_changed(self, change_event: InspectedChangedEvent[ConfigType]):
        pass
    
    def on_node_deleted(self, node: Node):
        """Callback when a node is deleted"""
        pass