from __future__ import annotations

from qtpy.QtCore import QObject, Signal, Qt
from qtpy.QtWidgets import QWidget, QApplication

from .flows.view import FlowView
from .design import Design
from .gui_base import GUIBase
from .code_editor.codes_storage import SourceCodeStorage
from ..qtcore.utils import connect_signal_event

from cognixcore import (
    set_complete_data_func,
    Flow,
    Session,
)

from logging import (
    DEBUG, 
    INFO, 
    NOTSET, 
    Handler, 
    LogRecord, 
    Formatter
)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .env import GUIEnv
    from .console import Console

class SessionLogHandler(Handler):
    
    def __init__(self, level: int | str = 0, formatter: Formatter = None):
        super().__init__(level)
        if formatter:
            self.setFormatter(formatter)
        else:
            self.setFormatter(Formatter('%(levelname)s: %(name)s: %(message)s'))
        
    def emit(self, record: LogRecord):
        # somehow this prints it twice, I can't tell why
        print(self.format(record))
        
class SessionGUI(GUIBase, QObject):
    """
    Session wrapper class, implementing the GUI.
    Any session with a GUI must be created through this class.
    Access the ryvencore session through the :code:`session`
    attribute, and the GUI from the ryvencore session through the
    :code:`gui` attribute. Once instantiated, you can simply use
    the :code:`session` directly to create, rename, delete flows,
    register nodes, etc.
    """
    
    __flow_created_signal = Signal(object)
    __flow_deleted_signal = Signal(object)
    
    flow_view_created = Signal(object, object)

    def __init__(
        self, 
        gui_parent: QWidget, 
        gui_env: GUIEnv=None, 
        log_level=DEBUG,
        console: Console = None
    ):
        GUIBase.__init__(self)
        QObject.__init__(self)

        if gui_env:
            self.__gui_env = gui_env
        else:
            from .env import get_gui_env # global gui env
            self.__gui_env = get_gui_env()
        
        self.__gui_env.load_env()
        self.console = console
            
        self.core_session = Session(gui=True, load_optional_addons=True)
        self.core_session.logg_addon.log_level = log_level
        # We're setting a simple handler to just print the output
        # It will be either the terminal or the gui console
        self.core_session.logger.addHandler(SessionLogHandler(level=NOTSET))
        # We're explicitly passing INFO here as this logger is tied
        # to the rest api and the console
        setattr(self.core_session, 'gui', self)

        self.gui_parent = gui_parent

        # code storage
        self.wnd_light_type = 'dark'
        self.cd_storage = SourceCodeStorage(self.__gui_env)
        # flow views
        self.flow_views: dict[Flow, FlowView] = {}

        # register complete_data function
        set_complete_data_func(self.get_complete_data_function(self))

        # load design
        app = QApplication.instance()
        app.setAttribute(Qt.AA_UseHighDpiPixmaps)
        Design.register_fonts()
        self.design = Design()

        # connect to session
        s = self.core_session
        connect_signal_event(self.__flow_created_signal, s.flow_created, self._flow_created)
        connect_signal_event(self.__flow_deleted_signal, s.flow_deleted, self._flow_deleted)
        
    @property
    def gui_env(self):
        """Utility property for accessing the global GUI environment."""
        return self.__gui_env
    
    def _flow_created(self, flow: Flow):
        """
        Builds the flow view for a newly created flow, saves it in
        self.flow_views, and emits the flow_view_created signal.
        """
        self.flow_views[flow] = FlowView(
            session_gui=self,
            flow=flow,
            parent=self.gui_parent,
        )
        self.flow_view_created.emit(flow, self.flow_views[flow])

        return flow

    def _flow_deleted(self, flow: Flow):
        """
        Removes the flow view for a deleted flow from self.flow_views.
        """
        self.flow_views.pop(flow)