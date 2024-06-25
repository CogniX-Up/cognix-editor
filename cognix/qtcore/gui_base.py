from qtpy.QtWidgets import QGraphicsObject, QGraphicsItem
from qtpy.QtCore import QTimer

from cognixcore.base import Base

import time

class SerializableItem:
    """An interface for providing serialization / deserialization functions"""
    
    def get_state(self) -> dict:
        """
        *VIRTUAL*

        Return the state of the widget, in a (pickle) serializable format.
        """
        data = {}
        return data

    def set_state(self, data: dict):
        """
        *VIRTUAL*

        Set the state of the widget, where data corresponds to the dict
        returned by get_state().
        """
        pass
    
class GUIBase:
    """Base class for GUI items that represent specific core components"""

    # every frontend GUI object that represents some specific component from the core
    # is stored there under the the global id of the represented component.
    # used for completing data (serialization)
    FRONTEND_COMPONENT_ASSIGNMENTS = {}  # component global id : GUI object

    @staticmethod
    def get_complete_data_function(session):
        """
        generates a function that searches through generated data by the core and calls
        complete_data() on frontend components that represent them to add frontend data
        """

        def analyze(obj):
            """Searches recursively through obj and calls complete_data(obj) on associated
            frontend components (instances of GUIBase)"""

            if isinstance(obj, dict):
                GID = obj.get('GID')
                if GID is not None:
                    # find representative
                    comp = GUIBase.FRONTEND_COMPONENT_ASSIGNMENTS.get(GID)
                    if comp:
                        obj = comp.complete_data(obj)

                # look for child objects
                for key, value in obj.items():
                    obj[key] = analyze(value)

            elif isinstance(obj, list):
                for i in range(len(obj)):
                    item = obj[i]
                    item = analyze(item)
                    obj[i] = item

            return obj

        return analyze

    def __init__(self, representing_component: Base = None):
        """parameter `representing` indicates representation of a specific core component"""
        if representing_component is not None:
            GUIBase.FRONTEND_COMPONENT_ASSIGNMENTS[representing_component.global_id] = self

    # OVERRIDE
    def complete_data(self, data: dict) -> dict:
        """completes the data dict of the represented core component by adding all frontend data"""
        return data
    
    def on_move(self):
        """virtual function for when a GUI is moved in the view"""
        pass

# if the __doc__ is incorrect, this class should be removed
class QGraphicsItemAnimated(QGraphicsObject):
    """
    Serves as a proxy for animating any kind fo QGraphicsItem.
    This was created because there is no apparent way to animate
    a QGraphicsItem that isn't a QObject.
    """
    
    def __init__(self, item: QGraphicsItem, parent = None) -> None:
        super().__init__(parent)
        self.item = item
        
        # for delete purposes
        # perhaps this could be implemented in an item change where the scene
        # is none and calling a delete later 
        self.item.setParentItem(self)
        self.item.setVisible(False)
    
    def boundingRect(self):
        return self.item.boundingRect()
    
    def paint(self, painter, option, widget):
        return self.item.paint(painter, option, widget)


class AnimationTimer:
    """A simple wrapper over QTimer to aid with controlling animations"""
    
    def __init__(self, obj, interval: int, on_restart, on_timeout):
        self.timer = QTimer(obj)
        self.timer.setInterval(interval)
        self.timer.timeout.connect(self.__on_timeout_internal)
        self.on_restart = on_restart
        self.on_timeout = on_timeout
        self.is_running = False
        self.interval_ms = interval
        self._current_time = 0.0
        
    def restart(self):
        if not self.is_running:
            self.timer.start()
            self.is_running = True
            
        self.on_restart()
        self._current_time = time.perf_counter()
            
    def stop(self):
        if self.on_timeout and self.is_running:
            self.on_timeout()
            self.timer.stop()
            self.is_running = False

    # avoid calling qt functions for performance
    def __on_timeout_internal(self):
        now = time.perf_counter()
        if now - self._current_time >= self.interval_ms / 1000:
            self.on_timeout()
            self._current_time = now
            self.timer.stop()
            self.is_running = False
        