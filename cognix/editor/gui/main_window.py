import sys
import os
import os.path

from PySide6.QtCore import QObject
from qtpy.QtGui import QIcon, QKeySequence
from qtpy.QtWidgets import (
    QMainWindow,
    QFileDialog,
    QShortcut,
    QAction,
    QActionGroup,
    QMenu,
    QMessageBox,
    QTabWidget,
    QDockWidget,
    QProgressDialog,
    QDialog,
)
from qtpy.QtCore import Qt, QByteArray, Signal

from ..gui.flow_ui import FlowUI, FlowView
from ..main.config import Config
from ..main.packages.nodes_package import NodesPackage
from ..gui.uic.ui_main_window import Ui_MainWindow
from ..main.utils import (
    abs_path_from_package_dir,
    abs_path_from_dir,
    cognix_version,
)
from .. import import_nodes_package
from ..gui.dialogs import GetTextDialog, ChooseFlowDialog

from ...qtcore import SessionGUI, NodeGUI
from ...qtcore.console import Console
from ...qtcore.flows.list_widget import FlowsListWidget
from ...qtcore.nodes.list_widget import NodeListWidget
from ...qtcore.addons.variables import VarTypeDialogue
from ...qtcore.utils import connect_signal_event

from cognixcore import InfoMsgs, Flow, NodeAction
from threading import Thread
        
class MainWindow(QMainWindow):

    __built_in_packages = ['built_in', 'cognix_library']
    __session_gui_instance = None
    
    _dialog_label_signal = Signal(str)
    _loading_finished_signal = Signal()
    _module_error = Signal(Exception)
    _node_types_updated = Signal(list)
    _flow_deleted_signal = Signal(Flow)
    _flow_renamed_signal = Signal(Flow, str)
    
    @classmethod
    def built_in_packages(cls):
        return list(cls.__built_in_packages)
    
    @classmethod
    def get_session_gui_instance(cls) -> SessionGUI:
        return cls.__session_gui_instance
        
    def __init__(
        self,
        config: Config,
        requested_packages: set = (),
        required_packages: set = None,  # only valid when project_content is provided
        project_content: dict = None,
        parent=None,
        wnd_light_type = 'dark',
        console: Console = None
    ):
        super().__init__(parent)

        self.console = console
        self._requested_packages = requested_packages
        self._required_packages = required_packages
        self._project_content = project_content if project_content else None
        
        self.config = config
        self.session_gui, self.core_session = None, None
        self.theme = config.window_theme
        self.node_packages = {}  # {Node: str}
        self.flow_UIs: dict[Flow, FlowUI] = {}
        self.flow_ui_template: dict[str, QByteArray | dict] = None
        self.wnd_light_type = wnd_light_type
        
        # Init Session GUI

        self.session_gui = SessionGUI(self)
        MainWindow.__session_gui_instance = self.session_gui

        self.session_gui.cd_storage.edit_src_codes = self.config.src_code_edits_enabled
        self.session_gui.wnd_light_type = wnd_light_type
        
        self.core_session = self.session_gui.core_session
        if self.config.verbose:
            self.core_session._info_messenger().enable(traceback=True)
        else:
            self.core_session._info_messenger().disable()

        # this didn't even need to be signal
        self.session_gui.flow_view_created.connect(self.flow_created)
        
        connect_signal_event(
            self._flow_renamed_signal, 
            self.core_session.flow_renamed, 
            self.flow_renamed
            )
        
        connect_signal_event(
            self._flow_deleted_signal,
            self.core_session.flow_deleted,
            self.flow_deleted
        )
        
        # Create data type dialogue
        self.type_dialog = VarTypeDialogue(parent=self)

        # unused; default flow theme etc. are defined by Config
        # self.session_gui.design.load_from_config(abs_path_from_package_dir('gui/styling/design_config.json'))

        self.session_gui.design.set_flow_theme(name=self.config.flow_theme)
        self.session_gui.design.set_animations_enabled(self.config.animations)

        # Assemble Window UI

        self.setup_ui()

        self.flow_view_theme_actions = []
        self.setup_menu_actions()

        self.setWindowTitle(self.config.window_title)
        self.setWindowIcon(QIcon(abs_path_from_package_dir('resources/pics/cognix/cognix_icon_small.png')))
        self.ui.flows_tab_widget.removeTab(0)  # remove placeholder tab

        # Configure window-wide Shortcuts

        save_shortcut = QShortcut(QKeySequence.Save, self)
        save_shortcut.activated.connect(self.on_save_project_triggered)
        import_nodes_shortcut = QShortcut(QKeySequence('Ctrl+i'), self)
        import_nodes_shortcut.activated.connect(self.on_import_nodes_triggered)

        # Setup Main Console

        self.console.session = self.session_gui
        self.console.reset_interpreter()

        if config.verbose and self.console:
            self.console.writeoutput(
                '''Editor is in Verbose mode. 
All output will be printed in the terminal, not the editor console.
The editor console can still be used for commands.
              '''
            )
            # hide the console in verbose mode
            self.ui.consoleDock.hide()

        # Setup ryvencore Session and load project

        # Requested packages take precedence over other packages
        self.progress_dial = QProgressDialog(":D", None, 0, 0)
        self.progress_dial.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.progress_dial.hide()
        
        # signals
        self._dialog_label_signal.connect(self.progress_dial.setLabelText)
        def _on_loaded_project():
            
            if self._project_content:
                # load the flow_ui_template if it exists
                self.set_flow_ui_template(self._project_content.get('flow_ui_template'))
                # After everything has loaded, load previous UI geometry and state
                self.load_qt_window(self._project_content)
                for flow_ui in self.flow_UIs.values():
                    self.load_flow_ui(flow_ui)
            
            self.progress_dial.close()
            self.show()
        
        self._loading_finished_signal.connect(_on_loaded_project)
        
        def _on_module_error(e: Exception):
            import traceback
            traceback.print_exc()
            msg_box = QMessageBox(
                QMessageBox.Warning,
                'Missing Python module',
                str(e),
                QMessageBox.Ok,
                self,
            )
            msg_box.exec()
            sys.exit(e)
            
        self._module_error.connect(_on_module_error)
        
        self._node_types_updated.connect(self.nodes_list_widget.update_list)
        self.resize(1500, 800)  # FIXME: this renders the --geometry argument useless, no?
        # self.showMaximized()
    
    def load(self):
        """Loads the project, displaying a dialogue. It then shows it."""
        # this function essentially separates the logic loading and the gui
        # loading by attaching the logic behind a thread
        
        self.progress_dial.show()
        
        def change_dial_label(label: str):
            self._dialog_label_signal.emit(label)
            
        def _load():
            change_dial_label('Importing Cognix Library...')
            self.import_nodes(path=abs_path_from_package_dir('main/packages/cognix_library/'))
            
            if self._requested_packages:
                change_dial_label('Importing requested packages...')
                self.import_packages(self._requested_packages)
            
            if self._project_content:
                
                if self._required_packages:
                    change_dial_label('Importing required packages...')
                    self.import_packages(self._required_packages)
                
                change_dial_label('Loading Project...')
                self.core_session.load(self._project_content)
            else:
                self.core_session.create_flow(title='hello world')
            
            if self.config.rest_api:
                from logging import getLogger, INFO, ERROR, DEBUG
                change_dial_label('REST API port validity check...')
                session = self.core_session
                port = self.config.rest_api_port
                
                # set up custom handlers for uvicorn to avoid
                # weird behaviour 
                s_handlers = session.logger.handlers
                uvicorn_logger = getLogger('uvicorn')
                uvicorn_logger.handlers = s_handlers
                uvicorn_logger.setLevel(DEBUG)
                
                uvicorn_error_logger = getLogger('uvicorn.error')
                uvicorn_error_logger.setLevel(ERROR)
                
                uvicorn_access_logger = getLogger('uvicorn.access')
                uvicorn_access_logger.setLevel(INFO)
                
                try:
                    session.rest_api.run(
                        port=port, 
                        on_other_thread=True, 
                        wait_time_if_thread= 1.25,
                        bypass_uvicorn_log=True,
                    )
                except Exception as e:
                    change_dial_label(f'Port {port} taken! Searching...')
                    from socket import socket, AF_INET, SOCK_STREAM
                    from errno import EADDRINUSE
                    for port in range(7555, 65500):
                        with socket(AF_INET, SOCK_STREAM) as s:
                            try:
                                s.bind(('127.0.0.1', port))
                                break
                            except:
                                continue
                    change_dial_label(f'Starting REST API @ {port}')
                    session.rest_api.run(
                        port=port,
                        on_other_thread=True
                    )
            self._loading_finished_signal.emit()
            
        # start the loading
        t = Thread(target=_load)
        t.start()
            
    def closeEvent(self, event):
        for flow_ui in self.flow_UIs.values():
            flow_ui.unload()
        self.session_gui.core_session.shutdown()
        
        # at this point
        
    def print_info(self):
        print('''
CONTROLS
    nodes dialog: right mouse in scene
    place nodes: drag and drop from left
        or hit enter in scene dialog
    select: left mouse
    pan / navigating scene: right mouse
    save: ctrl+s
    import: ctrl+i
        ''')

    # UI

    def setup_ui(self):
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.statusBar.hide()

        # actions for setting / unsetting a flow ui template
        self.focused_flow: FlowUI = None

        def unset_flow_template():
            self.set_flow_ui_template(None)

        def set_flow_template():
            flow_ui = self.flow_UIs.get(self.get_current_flow())
            if not flow_ui:
                return
            template = {
                'geometry': flow_ui.saveGeometry().toHex().data().decode(),
                'state': flow_ui.saveState().toHex().data().decode(),
                'view': flow_ui.flow_view.save_state()
            }
            self.set_flow_ui_template(template)

        self.flow_ui_template_menu = QMenu()
        self.flow_ui_template_menu.setTitle('Flow Template')

        restore_default = QAction('Restore Default', self)
        restore_default.triggered.connect(unset_flow_template)
        save_current = QAction('Save Current', self)
        save_current.triggered.connect(set_flow_template)

        self.flow_ui_template_menu.addAction(save_current)
        self.flow_ui_template_menu.addAction(restore_default)

        # set tabs to be on top
        self.setTabPosition(Qt.AllDockWidgetAreas, QTabWidget.North)

        # main console
        if self.console:
            self.ui.consoleDock.setWidget(self.console)
            self.ui.console_placeholder_widget.setParent(None)

        # splitter sizes
        self.ui.main_vertical_splitter.setSizes([700, 0])

        self.flows_list_widget = FlowsListWidget(self.session_gui)
        self.ui.flows_dock.setWidget(self.flows_list_widget)

        self.nodes_list_widget = NodeListWidget(self.session_gui, True)
        self.ui.nodes_dock.setWidget(self.nodes_list_widget)

        self.ui.main_horizontal_splitter.setSizes([120, 800 - 120])

        # add widget actions to menu
        all_dock_widgets: list[QDockWidget] = [d for d in self.findChildren(QDockWidget)]
        open_all_docks = QAction('Open All', self)
        open_all_docks.triggered.connect(self.open_docks)
        close_all_docks = QAction('Close All Tabs', self)
        close_all_docks.triggered.connect(self.close_docks)
        self.ui.menuDocks.addActions([open_all_docks, close_all_docks])
        self.ui.menuDocks.addActions([w.toggleViewAction() for w in all_dock_widgets])
        # tabify all left tabs at a fresh project
        left_widgets = [
            d for d in all_dock_widgets if self.dockWidgetArea(d) == Qt.LeftDockWidgetArea
        ]
        for i in range(1, len(left_widgets)):
            self.tabifyDockWidget(left_widgets[i - 1], left_widgets[i])

    def open_docks(self):
        for dock in self.findChildren(QDockWidget):
            dock.show()
    
    def close_docks(self):
        for dock in self.findChildren(QDockWidget):
            if not dock.isFloating():
                dock.close()
            
    def setup_menu_actions(self):
        # flow designs
        light_themes_menu = QMenu('light')
        for d in self.session_gui.design.flow_themes:
            design_action = QAction(d.name, self)
            if d.type_ == 'dark':
                self.ui.menuFlow_Design_Style.addAction(design_action)
            else:
                light_themes_menu.addAction(design_action)

            design_action.triggered.connect(self.on_design_action_triggered)
            self.flow_view_theme_actions.append(design_action)

        self.ui.menuFlow_Design_Style.addMenu(light_themes_menu)

        self.ui.actionImport_Nodes.triggered.connect(self.on_import_nodes_triggered)
        self.ui.actionImport_Example_Nodes.triggered.connect(self.on_import_example_nodes_triggered)
        self.ui.actionSave_Project.triggered.connect(self.on_save_project_triggered)
        # TODO: rename occurences of "Script" to "Flow" in the UI
        self.ui.actionNew_Flow.triggered.connect(self.on_new_flow_triggered)
        self.ui.actionRename_Flow.triggered.connect(self.on_rename_flow_triggered)
        self.ui.actionDelete_Flow.triggered.connect(self.on_delete_flow_triggered)
        self.ui.actionEnableInfoMessages.triggered.connect(self.on_enable_info_msgs_triggered)
        self.ui.actionDisableInfoMessages.triggered.connect(self.on_disable_info_msgs_triggered)
        self.ui.actionSave_Pic_Viewport.triggered.connect(self.on_save_scene_pic_viewport_triggered)
        self.ui.actionSave_Pic_Whole_Scene_scaled.triggered.connect(
            self.on_save_scene_pic_whole_triggered
        )

        # performance mode
        self.session_gui.design.performance_mode_changed.connect(
            self.on_performance_mode_value_changed
        )

        self.ac_perf_mode_fast = QAction('Fast', self)
        self.ac_perf_mode_fast.setCheckable(True)

        self.ac_perf_mode_pretty = QAction('Pretty', self)
        self.ac_perf_mode_pretty.setCheckable(True)

        perf_mode_ag = QActionGroup(self)
        perf_mode_ag.addAction(self.ac_perf_mode_fast)
        perf_mode_ag.addAction(self.ac_perf_mode_pretty)

        self.ac_perf_mode_fast.setChecked(self.config.performance_mode == 'fast')
        self.ac_perf_mode_pretty.setChecked(self.config.performance_mode == 'pretty')

        perf_mode_ag.triggered.connect(self.on_performance_mode_changed)

        perf_menu = QMenu('Performance Mode', self)
        perf_menu.addAction(self.ac_perf_mode_fast)
        perf_menu.addAction(self.ac_perf_mode_pretty)

        self.ui.menuView.addMenu(perf_menu)
        
        # APIs
        self.api_menu = QMenu('APIs', self)
        self.ui.menuBar.addMenu(self.api_menu)
        
        self.rest_api_action = QAction('REST', self)
        self.api_menu.addAction(self.rest_api_action)
        self.rest_api_msg = QMessageBox(
                None,
                'Rest API',
                'Nothing yet',
                QMessageBox.Ok,
                self,
            )
        
        self.rest_api_msg.hide()
        def on_rest_api_action():
            rest = self.core_session.rest_api
            if rest.running:
                self.rest_api_msg.setText(f'REST running @{rest.port}!')
            else:
                self.rest_api_msg.setText(f'REST inactive!')
            self.rest_api_msg.show()
        self.rest_api_action.triggered.connect(on_rest_api_action)
        
        self.session_gui.design.set_performance_mode(self.config.performance_mode)

        # animations
        design = self.session_gui.design
        self.ac_anims_active = QAction('Enable All', self)
        self.ac_anims_inactive = QAction('Disable All', self)
        
        self.scale_animation_action = QAction('Node Scale', self)
        self.scale_animation_action.setCheckable(True)
        self.scale_animation_action.setChecked(design.node_animation_enabled)
        def on_scale_check(check):
            design.node_animation_enabled = check
        self.scale_animation_action.triggered.connect(on_scale_check)
        
        self.connection_animation_action = QAction('Connection Path', self)
        self.connection_animation_action.setCheckable(True)
        self.connection_animation_action.setChecked(design.connection_animation_enabled)
        def on_conn_check(check):
            design.connection_animation_enabled = check
        self.connection_animation_action.triggered.connect(on_conn_check)
        
        # for individual settings
        self._animation_specific_actions = [self.scale_animation_action, self.connection_animation_action] 
        def enable_animations(enable: bool):
            def _enable_animations():
                for ac in self._animation_specific_actions:
                    # trigger is as if the user clicks it, hence the not
                    ac.setChecked(not enable)
                    ac.trigger()
            return _enable_animations
                    
        self.ac_anims_active.triggered.connect(enable_animations(True))
        self.ac_anims_inactive.triggered.connect(enable_animations(False))
        
        animations_menu = QMenu('Animations', self)
        animations_menu.addAction(self.ac_anims_active)
        animations_menu.addAction(self.ac_anims_inactive)
        animations_menu.addAction(self.scale_animation_action)
        animations_menu.addAction(self.connection_animation_action)

        self.ui.menuView.addMenu(animations_menu)

    def load_stylesheet(self, ss):
        ss_content = ''
        try:
            f = open(abs_path_from_package_dir('resources/stylesheets/' + ss + '.txt'))
            ss_content = f.read()
            f.close()
        finally:
            self.session_gui.set_stylesheet(ss_content)
            self.setStyleSheet(ss_content)

    # necessary for proper flow view loading
    def showEvent(self, event):
        for flow_ui in self.flow_UIs.values():
            flow_ui.flow_view.reload()
        
    # events
    
    def on_performance_mode_value_changed(self, mode: str):
        if mode == 'fast':
            self.setDockOptions(self.dockOptions() & ~QMainWindow.AnimatedDocks)
        else:
            self.setDockOptions(self.dockOptions() | QMainWindow.AnimatedDocks)

    # slots

    def on_import_nodes_triggered(self):
        file_path = QFileDialog.getOpenFileName(
            self,
            'select nodes file',
            abs_path_from_dir('nodes'),
            'Python File (*.py)',
        )[0]
        if file_path != '':
            self.import_nodes(path=os.path.dirname(file_path))

    def on_import_example_nodes_triggered(self):
        file_path = QFileDialog.getOpenFileName(
            self,
            'select nodes file',
            abs_path_from_package_dir('example_nodes'),
            'Python File (*.py)',
        )[0]
        if file_path != '':
            self.import_nodes(path=os.path.dirname(file_path))

    def on_performance_mode_changed(self, action):
        if action == self.ac_perf_mode_fast:
            self.session_gui.design.set_performance_mode('fast')
        else:
            self.session_gui.design.set_performance_mode('pretty')

    def on_design_action_triggered(self):
        index = self.flow_view_theme_actions.index(self.sender())
        self.session_gui.design.set_flow_theme(self.session_gui.design.flow_themes[index])

    def on_enable_info_msgs_triggered(self):
        InfoMsgs.enable()

    def on_disable_info_msgs_triggered(self):
        InfoMsgs.disable()

    def on_save_scene_pic_viewport_triggered(self):
        """Saves a picture of the currently visible viewport."""
        if len(self.core_session.flows) == 0:
            return

        file_path = QFileDialog.getSaveFileName(self, 'select file', '', 'PNG(*.png)')[0]
        flow = self.ui.flows_tab_widget.currentWidget().flow
        view = self.session_gui.flow_views[flow]
        img = view.get_viewport_img()
        img.save(file_path)

    def on_save_scene_pic_whole_triggered(self):
        """Saves a picture of the whole currently visible scene."""
        if len(self.core_session.flows) == 0:
            return

        file_path = QFileDialog.getSaveFileName(self, 'select file', '', 'PNG(*.png)')[0]
        flow = self.ui.flows_tab_widget.currentWidget().flow
        view = self.session_gui.flow_views[flow]
        img = view.get_whole_scene_img()
        img.save(file_path)

    def on_save_project_triggered(self):
        file_name = QFileDialog.getSaveFileName(
            self,
            'select location and give file name',
            abs_path_from_dir('saves'),
            'JSON(*.json)',
        )[0]
        if not file_name.endswith('.json'):
            file_name += '.json'

        if file_name != '':
            self.save_project(file_name)

    def on_new_flow_triggered(self):
        new_flow_title = GetTextDialog('choose unique title', '', 'new flow title', self).get_text()

        if self.core_session.new_flow_title_valid(new_flow_title):
            self.core_session.create_flow(new_flow_title)
        else:
            flow = [f for f in self.core_session.flows if f.title == new_flow_title][0]
            self.focus_on_flow(flow)

    def on_rename_flow_triggered(self):
        flow = ChooseFlowDialog('choose flow', self.core_session.flows, self).get_flow()
        new_title = GetTextDialog('new title', flow.title, 'new flow title', self).get_text()

        if self.core_session.new_flow_title_valid(new_title):
            self.core_session.rename_flow(flow, new_title)

    def on_delete_flow_triggered(self):
        flow = ChooseFlowDialog('choose flow', self.core_session.flows, self).get_flow()

        msg_box = QMessageBox(
            QMessageBox.Warning,
            'sure about deleting flow?',
            'You are about to delete a flow. This cannot be undone, all content will be gone. '
            'Do you want to continue?',
            QMessageBox.Cancel | QMessageBox.Yes,
            self,
        )
        msg_box.setDefaultButton(QMessageBox.Cancel)
        ret = msg_box.exec_()
        if ret != QMessageBox.Yes:
            return

        self.core_session.delete_flow(flow)

    # session

    def flow_created(self, flow: Flow, flow_view: FlowView):
        flow_widget = FlowUI(self, flow, flow_view)
        self.flow_UIs[flow] = flow_widget
        self.ui.flows_tab_widget.addTab(flow_widget, flow.title)
        flow_view.menu().addMenu(self.flow_ui_template_menu)
        if self.flow_ui_template:
            flow_widget.load_directly(self.flow_ui_template)

        self.focus_on_flow(flow)

    def flow_renamed(self, flow: Flow, name: str):
        i = self.ui.flows_tab_widget.indexOf(self.flow_UIs[flow])
        self.ui.flows_tab_widget.setTabText(i, flow.title)

    def flow_deleted(self, flow: Flow):
        i = self.ui.flows_tab_widget.indexOf(self.flow_UIs[flow])
        self.ui.flows_tab_widget.removeTab(i)
        self.flow_UIs[flow].unload()
        del self.flow_UIs[flow]

    def get_current_flow(self):
        return self.core_session.flows[self.ui.flows_tab_widget.currentIndex()]

    def focus_on_flow(self, flow: Flow):
        self.ui.flows_tab_widget.setCurrentWidget(self.flow_UIs[flow])

    def import_packages(self, packages_list: list[NodesPackage]):
        for p in packages_list:
            self.import_nodes(p)

    def import_nodes(self, package: NodesPackage = None, path: str = None):
        
        if package is not None:
            p = package
        else:
            p = NodesPackage(path)

        if p in self.node_packages.values():
            # never import package twice!
            # different packages with same name are forbidden
            print('package with this name already exists')
            return

        try:
            node_types = import_nodes_package(p)
        except ModuleNotFoundError as e:
            self._module_error.emit(e)

        self.core_session.register_node_types(node_types)

        for n in node_types:
            self.node_packages[n] = p

        self._node_types_updated.emit(list(self.core_session.node_types))

    def set_flow_ui_template(self, template: dict[str, str | QByteArray | dict] | None):
        if template is None:
            self.flow_ui_template = None
            return
        save = (
            lambda key: template[key]
            if type(template[key]) is QByteArray
            else bytes.fromhex(template[key])
        )
        self.flow_ui_template = {
            'geometry': save('geometry'), 
            'state': save('state'),
            'view': template['view']
        }

    def load_qt_window(self, project_dict):
        """
        Loads the main windows previous geometry and state, if they were saved.
        """
        if 'geometry' in project_dict:
            self.restoreGeometry(bytes.fromhex(project_dict['geometry']))
        if 'state' in project_dict:
            self.restoreState(bytes.fromhex(project_dict['state']))

    def load_flow_ui(self, flow_ui: FlowUI):
        """
        Loads a flow uis previous geometry and state based on the previous flow id.
        """
        if self._project_content is None:
            return
        try:
            flow_ui.load(self._project_content['flow_uis'])
        except Exception as e:
            # print(f'Could not load previous UI state for flow with previous id: {flow_ui.flow.prev_global_id}')
            pass

    def save_project(self, file_name):
        import json

        file = None
        try:
            if os.path.exists(file_name):
                os.remove(file_name)
            file = open(file_name, 'w')
        except FileNotFoundError:
            InfoMsgs.write('couldn\'t open file')
            return

        general_project_info_dict = {
            'type': 'Cognix project file',
            'cognix version': str(cognix_version()),
        }

        flows_data = self.core_session.serialize()

        required_packages = set()
        for node in self.core_session.all_node_objects():
            if (
                node.__class__ not in self.node_packages.keys()
                or self.node_packages[node.__class__] is None
                or self.node_packages[node.__class__].name in self.__built_in_packages
            ):
                continue
            required_packages.add(self.node_packages[node.__class__])

        # Serialization of the main window
        geometry = self.saveGeometry().toHex().data().decode()
        state = self.saveState().toHex().data().decode()

        # Serialization of the flow views
        # should be dict[str, dict[str, str | dict]] in 3.9+
        flow_uis_ser: dict = {}
        for flow, flow_ui in self.flow_UIs.items():
            flow_uis_ser[str(flow.global_id)] = flow_ui.save_state()

        whole_project_dict = {
            'general info': general_project_info_dict,
            'required packages': [p.config_data() for p in required_packages],
            **flows_data,
            'geometry': geometry,
            'state': state,
            'flow_uis': flow_uis_ser,
        }

        # flow ui template
        if self.flow_ui_template:
            whole_project_dict['flow_ui_template'] = {
                'geometry': QByteArray(self.flow_ui_template['geometry']).toHex().data().decode(),
                'state': QByteArray(self.flow_ui_template['state']).toHex().data().decode(),
                'view': self.flow_ui_template['view']
            }

        data = json.dumps(whole_project_dict, indent=4)
        InfoMsgs.write("project saved!")
        # InfoMsgs.write(data)

        file.write(data)
        file.close()
