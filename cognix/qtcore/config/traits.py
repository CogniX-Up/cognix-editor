"""
Implementations for a node config based on the 
built-in traits and traitsui implementation
"""
from __future__ import annotations
from cognixcore import (
    Node,
    NodeConfig,
)

from cognixcore.config.traits import (
    NodeTraitsConfig,
    NodeTraitsGroupConfig,
)

from ..nodes.inspector import InspectedChangedEvent
from ..nodes.gui import NodeGUI
from ..flows.commands import DelegateCommand
from .abc import NodeConfigInspector

from traitsui.api import View, Group, Item, VGroup
from traits.observation.events import (
    TraitChangeEvent, 
    ListChangeEvent, 
    DictChangeEvent, 
    SetChangeEvent
)

from traits.api import (
    Button, 
    TraitListObject, 
    TraitSetObject, 
    TraitDictObject,
    List,
    Set,
    Dict,
) 
from collections.abc import Sequence, Mapping, Set as AbcSet, MutableSet
from qtpy.QtWidgets import QVBoxLayout, QWidget
from copy import copy


class NodeTraitsConfigInspector(NodeConfigInspector[NodeTraitsConfig], QWidget):
    """Basic config inspector"""
    
    _item_traits = ['style', 'enabled_when', 'visible_when', 'defined_when', 'has_focus']
    """
    These traits, while existing for an Item, aren't passed directly through 
    the Trait. Hence, we're redefining them and using them inside the GUI class.
    """
    #   CLASS
    @classmethod
    def create_config_changed_event(cls, node: Node, gui: NodeGUI):
        
        def on_trait_changed(event):
            
            gui.flow_view.setFocus()
            def undo_redo(obj, name, func, *args):
                def _undo__redo():
                    conf: NodeTraitsConfig = node.config
                    conf.block_change_events()
                    func(obj, name, *args)
                    conf.allow_change_events()
                        
                return _undo__redo
            
            def undo_redo_pair(obj, name, func, undo_args, redo_args):
                return (
                    undo_redo(obj, name, func, undo_args),
                    undo_redo(obj, name, func, redo_args)
                )
                
            node_id = node.global_id
            
            if isinstance(event, TraitChangeEvent):
                
                # this needs to get copied if it's a list otherwise
                # in redo the values from the last events (not trait change)
                # will be retained
                
                # i.e If a list had actions ["", ""] and ["xx", ""], if we
                # completely undo and then redo, we'd end up with ["xx", ""]
                # instead of ["", ""]
                
                name, obj = event.name, event.object
                if isinstance(event.new, (Sequence, Set, Mapping)):
                    new_val = copy(event.new)
                    old_val = copy(event.old)
                else:
                    new_val = event.new
                    old_val = event.old
                
                undo = undo_redo(obj, name, _trait_change, old_val)
                redo = undo_redo(obj, name, _trait_change, new_val)
                
            else:
                if isinstance(event, ListChangeEvent):
                    tlist: TraitListObject = event.object
                    obj, name = tlist.object(), tlist.name
                    new_val = getattr(obj, name)
                    old_val = copy(new_val)
                    _list_undo(old_val, event.index, event.added, event.removed)
                    
                    undo = undo_redo(
                        obj, 
                        name, 
                        _list_change,
                        event.index,
                        event.added,
                        event.removed 
                    )
                    redo = undo_redo(
                        obj,
                        name,
                        _list_change,
                        event.index,
                        event.removed,
                        event.added
                    )
                    
                elif isinstance(event, SetChangeEvent):
                    tset: TraitSetObject = event.object
                    obj, name = tset.object(), tset.name
                    new_val = getattr(obj, name)
                    old_val = copy(new_val)
                    _set_undo(old_val, event.added, event.removed)
                    undo = undo_redo(
                        obj,
                        name,
                        _set_change,
                        event.added,
                        event.removed
                    )
                    redo = undo_redo(
                        obj,
                        name,
                        _set_change,
                        event.removed,
                        event.added
                    )
                    
                elif isinstance(event, DictChangeEvent):
                    tdict: TraitDictObject = event.object
                    obj, name = tdict.object(), tdict.name
                    new_val = getattr(obj, name)
                    old_val = copy(new_val)
                    _dict_undo(old_val, event.added, event.removed)
                    undo = undo_redo(
                        obj,
                        name,
                        _dict_change,
                        event.added,
                        event.removed
                    )
                    redo = undo_redo(
                        obj,
                        name,
                        _dict_change,
                        event.removed,
                        event.added
                    )
            
            message = f'Config Change Node: {node.title}[{node_id}] {name}: {new_val}'
            # this shouldn't happen
            # I don't know if this is a bug in traits or I'm
            # doing something wrong
            # but since it's happening, lets guard against it
            if old_val == new_val:
                return
            gui.flow_view.push_undo(
                DelegateCommand(
                    gui.flow_view,
                    message,
                    undo,
                    redo,
                ), True
            )
            
        return on_trait_changed
    
    
    #   INSTANCE
    def __init__(self, params: tuple[NodeTraitsConfig, NodeGUI]):
        QWidget.__init__(self)
        
        config, _ = params
        
        self.view: View = None
        self.ui = None
        NodeConfigInspector.__init__(self, params)
    
    def inspected_label(self):
        return (
            getattr(self.inspected, 'label') 
            if hasattr(self.inspected, 'label') 
            else 'Configuration'
        )
    
    def on_insp_changed(self, change_event: InspectedChangedEvent[NodeTraitsConfig]):
        
        self.setLayout(QVBoxLayout())
        self.delete_ui()
        
        self.inspected = inspected_obj = change_event.new
        if not inspected_obj:
            return
        
        gr_label = self.inspected_label()
        
        insp_traits = inspected_obj.inspected_traits()
        custom_view = self.inspected.trait_view(
            self.inspected.default_traits_view()
        )
        if custom_view:
            self.view = custom_view
        else:
            items: list[Item] = []
            for tr in insp_traits:
                internal_tr = inspected_obj.trait(tr)
                metadata = {}
                for item_trait_name in self._item_traits:
                    item_trait = getattr(internal_tr, item_trait_name, None)
                    if item_trait:
                        metadata[item_trait_name] = item_trait
                
                t_type = internal_tr.trait_type
                if isinstance(t_type, Button):
                    item = Item(tr, **metadata, show_label=False) if metadata else Item(tr, show_label=False)
                else:
                    item = Item(tr, **metadata) if metadata else Item(tr)
                items.append(item)
                
            config_group = VGroup (
                *items,
                label=gr_label,
                scrollable=True,
                springy=True,
            )
            
            self.view = View (
                config_group
            )
        
        if not change_event.created:
            self.load()
    
    def load(self):
        
        if not self.ui:
            self.ui = self.inspected.edit_traits(parent=self, kind='subpanel', view=self.view).control
            self.ui.setVisible(False)
            self.layout().addWidget(self.ui)
            self.ui.setVisible(True)
    
    def delete_ui(self):
        if self.ui:
            self.ui.deleteLater()
            self.ui.setParent(None)
            self.ui.setVisible(False)
            self.ui = None
                          
        
class NodeTraitsGroupConfigInspector(NodeTraitsConfigInspector):
    
    traits_view = None
    
    def on_insp_changed(self, change_event: InspectedChangedEvent[NodeTraitsConfig]):
        
        inspected_obj = change_event.new
        self.delete_ui()
        
        if not inspected_obj:
            return
        
        self.inspected = inspected_obj
        
        gr_label = self.inspected_label()
        gr_layout = (
            getattr(self.inspected, 'layout') 
            if hasattr(self.inspected, 'layout') 
            else 'tabbed'
        )
        
        insp_traits = inspected_obj.serializable_traits()
        
        items: list[Item] = []
        for tr in insp_traits:
            items.append(Item(tr, style='custom', show_label=False))
        
        self.view = View(
            Group(
                *items,
                label=gr_label,
                layout=gr_layout,
                show_border=True,
                scrollable=True,
                springy=True
            )
        )
        
        if not change_event.created:
            self.load()
    

#   ------UTIL-------

def _trait_change(obj, name, value):
    setattr(obj, name, value)

def _list_change(obj: NodeTraitsConfig, name, index, added, removed): # (added, removed, index)
    li: Sequence = getattr(obj, name)
    _list_undo(li, index, added, removed)

def _list_undo(li, index, added, removed):
    # ... still don't know if it's my problem or traits
    if removed == added:
        print("nn")
        return
    li[index: (index + len(added))] = removed

# TODO Find a way for both set and undo to happen in one operation
         
def _set_change(obj, name, added, removed): # (added, removed)
    s: set = getattr(obj, name)
    _set_undo(s, added, removed)

def _set_undo(s: set, added, removed):
    if added == removed:
        return
    s.difference_update(added)
    s.update(removed)
        
def _dict_change(obj, name, added, removed): #(added, removed)
    d: dict = getattr(obj, name)
    _dict_undo(d, added, removed)

def _dict_undo(d: dict, added, removed):
    if added == removed:
        return
    for key in removed:
        del d[key]
    d.update(added)
    
# Some nice info

# What is a TraitListObject? (It was used before for the above functions)

# A validator that holds all the information Internally, this object changes for 
# a trait when the whole list changes, rather than only its items. That's why
# we have to reset the whole list for undo-redo to work correctly and not rely
# on the TraitListObject it self

# the same applies to Set and Dict Traits (TraitSetObject, TraitDictObject)

# This means that we never pass that object and change it. We should always
# use the trait itself for any undos, redos