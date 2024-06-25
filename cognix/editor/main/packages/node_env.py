"""
This module automatically imports all requirements for custom nodes.
"""
from __future__ import annotations
import os
from ...main.utils import in_gui_mode
from cognixcore import Node
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...main.packages.nodes_package import NodesPackage

def init_node_env():
    if os.environ['COGNIX_MODE'] == 'gui':
        from .... import qtcore
        
class NodesEnvRegistry:
    """
    Statically stores custom `cognixcore.Node` subclasses
    exported via export_nodes on import of a nodes package.
    After running the imported nodes.py module (which needs to call
    `export_nodes()` to run), the exported types from this class
    are available for retrieval.
    """

    exported_package_metadata: dict[str, list[type[Node]]] = {}
    """Stores, for each nodes package or subpackage a list of exported node types"""
    
    last_exported_package: list[list[type[Node]]] = []
    """The last exported package to be consumed for loading"""
    
    current_package: NodesPackage = None
    """Stores the package that is currently being imported. Set by the nodes package"""
    
    @classmethod
    def current_package_id(cls):
        if cls.current_package is None:
            raise Exception(
                f'Unexpected nodes export. '
                f'Nodes export is only allowed when the nodes package is imported. '
            )
        return cls.current_package.name

    @classmethod
    def consume_last_exported_package(cls) -> list[type[Node]]:
        """Consumes the last exported package"""
        result: list[type[Node]] = []
        for nodes in cls.last_exported_package:
            result.extend(nodes)
        cls.last_exported_package.clear()
        return result


def export_nodes(
    node_types: list[type[Node]],
    sub_pkg_name: str = None
):
    """
    Exports/exposes the specified nodes for use in flows. Nodes will have the same identifier, since they come as a package.
    This function will fail if the NodesEnvRegistry package is not set.
    """

    pkg_name = NodesEnvRegistry.current_package_id()
    if sub_pkg_name is not None:
        pkg_name = f"{pkg_name}.{sub_pkg_name}"
    
    # extend identifiers of node types to include the package name
    for n_cls in node_types:
        # store the package id as identifier prefix, which will be added
        # by ryvencore when registering the node type
        n_cls.id_prefix = pkg_name

        # also add the identifier without the prefix as fallback for older versions
        n_cls.legacy_ids = [
            *n_cls.legacy_ids,
            n_cls.id_name if n_cls.id_name else n_cls.__name__,
        ]
        
    metadata = NodesEnvRegistry.exported_package_metadata
    metadata[pkg_name] = node_types
    NodesEnvRegistry.last_exported_package.append(node_types)


__gui_loaders: list = []


def on_gui_load(func):
    """
    Use this decorator to register a function which imports all gui
    modules of the nodes package.
    Do not import any gui modules outside of this function.
    When Ryven is running in headless mode, this function will not
    be called, and your nodes package should function without any.

    Example:
    `nodes.py`:
    ```
    from cognix.node_env import *

    # <node types> definitions

    export_nodes(<node types>)

    @on_gui_load
    def load_guis():
        import .gui
    ```
    """
    __gui_loaders.append(func)


def load_current_guis():
    """
    Calls the functions registered via `~cognix.main.gui_env.on_gui_load`.
    """
    if not in_gui_mode():
        return
    for func in __gui_loaders:
        func()
    __gui_loaders.clear()
