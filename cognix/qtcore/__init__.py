# set package path (for resources etc.)
import os
from .utils import Location
Location.PACKAGE_PATH = os.path.normpath(os.path.dirname(__file__))

os.environ['RC_MODE'] = 'gui'  # set ryvencore gui mode
os.environ['QT_ENABLE_HIGHDPI_SCALING'] = '1'

# expose ryvencore
import cognixcore

#expose gui env and load it
from .env import *
from .session_gui import SessionGUI
from .nodes.gui import NodeGUI
from .nodes.base_widgets import NodeMainWidget, NodeInputWidget
from .nodes.inspector import NodeInspectorWidget
# customer base classes
from cognixcore import Node

# gui classes
from .addons import *
from .flows.themes import flow_themes
