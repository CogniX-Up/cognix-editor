import os
import pathlib

from qtpy.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QFileDialog,
    QRadioButton,
    QButtonGroup,
    QLabel,
    QFormLayout,
    QComboBox,
    QDialogButtonBox,
    QCheckBox,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QStyleOptionFrame,
    QStyle,
    QLineEdit,
    QWidget,
    QLineEdit,
)
from qtpy.QtCore import Qt, QSize
from qtpy.QtGui import QIcon, QPainter, QIntValidator

from ..main.args_parser import unparse_sys_args
from ..main.config import Config
from ..main.utils import (
    abs_path_from_package_dir,
    abs_path_from_dir,
    dir_path,
    is_package_available,
)
from ..main.packages.nodes_package import process_nodes_packages
from ..gui.main_window import MainWindow
from ..gui.styling.window_theme import apply_stylesheet


LBL_CREATE_PROJECT = '<create new project>'
LBL_DEFAULT_FLOW_THEME = '<default>'


class ElideLabel(QLabel):
    """A QLabel with ellipsis, if the text is too long to be fully displayed.

    See:
        https://stackoverflow.com/questions/68092087/one-line-elideable-qlabel#answer-68092991

    Copyright (C) 2021  https://github.com/MaurizioB/
    """

    _elideMode = Qt.ElideMiddle

    def setText(self, label, *args, **kwargs):
        """Sets text and tooltip."""
        s = str(label)
        super().setText(s, *args, **kwargs)
        self.setToolTip(s)

    def elideMode(self):
        return self._elideMode

    def setElideMode(self, mode):
        if self._elideMode != mode and mode != Qt.ElideNone:
            self._elideMode = mode
            self.updateGeometry()

    def minimumSizeHint(self):
        return self.sizeHint()

    def sizeHint(self):
        hint = self.fontMetrics().boundingRect(self.text()).size()
        c_margins = self.contentsMargins()
        l, t, r, b = c_margins.left(), c_margins.top(), c_margins.right(), c_margins.bottom()
        margin = self.margin() * 2
        return QSize(
            min(100, hint.width()) + l + r + margin,
            min(self.fontMetrics().height(), hint.height()) + t + b + margin,
        )

    def paintEvent(self, event):
        qp = QPainter(self)
        opt = QStyleOptionFrame()
        self.initStyleOption(opt)
        self.style().drawControl(QStyle.CE_ShapedFrame, opt, qp, self)
        c_margins = self.contentsMargins()
        l, t, r, b = c_margins.left(), c_margins.top(), c_margins.right(), c_margins.bottom()
        margin = self.margin()
        try:
            # since Qt >= 5.11
            m = self.fontMetrics().horizontalAdvance('x') / 2 - margin
        except:
            m = self.fontMetrics().width('x') / 2 - margin
        r = self.contentsRect().adjusted(margin + m, margin, -(margin + m), -margin)
        qp.drawText(
            r,
            self.alignment(),
            self.fontMetrics().elidedText(self.text(), self.elideMode(), r.width()),
        )


class ShowCommandDialog(QDialog):
    def __init__(self, command, config, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout()
        command_lineedit = QLineEdit(command)
        layout.addWidget(command_lineedit)
        self.config_text_edit = QTextEdit()
        self.config_text_edit.setText(config)
        layout.addWidget(self.config_text_edit)

        buttons_layout = QHBoxLayout()
        save_config_button = QPushButton('save config')
        save_config_button.clicked.connect(self.on_save_config_clicked)
        buttons_layout.addWidget(save_config_button)
        close_button = QPushButton('close')
        close_button.clicked.connect(self.accept)
        buttons_layout.addWidget(close_button)
        layout.addLayout(buttons_layout)

        self.setLayout(layout)

    def on_save_config_clicked(self):
        config = self.config_text_edit.toPlainText()

        file = QFileDialog.getSaveFileName(
            self,
            'select config file',
            dir_path(),
            'cognix config files (*.cfg)',
        )[0]

        if file != '':
            p = pathlib.Path(file)
            with open(p, 'w') as f:
                f.write(config)


class StartupDialog(QDialog):
    """The welcome dialog.

    The user can choose between creating a new project and loading a saved or
    example project. When a project is loaded, it scans for validity of all
    the required packages for the project, and in case some paths are invalid,
    they are shown in the dialog. The user than can autodiscover those missing
    packages or cherry-pick by choosing paths manually.

    The user can also set some common configuration options, and can generate
    an analogous command and config file and save the configuration in it.
    """

    def __init__(self, config: Config, parent=None):
        """Initialize the `StartupDialog` class.

        Parameters
        ----------
        config : Config
            The global configuration, parsed from command line or run() function
            interface.
            Notice that this class operates on args directly, so all values
            are either of primitive type (including strings), except paths
            which are pathlib.Path objects. Translation to NodePackage objects,
            WindowTheme objects etc. will happen at a later stage, not here.
        parent : QWidget, optional
            The parent `QWidget`.
            The default is `None`.

        Returns
        -------
        None.

        """
        super().__init__(parent)

        self.conf = config

        #
        # Layout the contents of the dialog
        #

        layout = QVBoxLayout()

        info_widget = QWidget()
        info_widget.setLayout(QHBoxLayout())
        layout.addWidget(info_widget)
        
        # qt api availability
        qt_api = config.qt_api
        qt_available = f'Qt API: {qt_api}. Available in your system: [ '
        for api_string in ['PySide6', 'PyQt6']:
            if is_package_available(api_string):
                qt_available += f'{api_string.lower()} '
        qt_available += ' ]. Restart with arg --qt-api <your_api> if you need another API.'
        
        # Top info text edit
        info_text_edit = QTextEdit()
        info_text_edit.setHtml(f'''
            <div style="font-family: Corbel; font-size: large;">
                CogniX Editor is not a stable piece of software, it's experimental, and nothing is
                guaranteed to work as expected. Make sure to save frequently. 
                If you spot an issue, please report it on the 
                <a href="">GitHub page [to be added]</a>.
                <br><br>
                CogniX comes with built-in libraries tailored for signal processing,
                mainly for EEG and Eye Gaze. Currently it's at an early development stage.
                <br><br>
                {qt_available}
            <div>
        ''')
        info_text_edit.setReadOnly(True)
        icon_label = QLabel(f'''
            <img style="float:right;" height=100 src="{abs_path_from_package_dir('resources/pics/cognix/cognix_icon.png')}">
                ''')
        
        info_widget.layout().addWidget(icon_label)
        info_widget.layout().addWidget(info_text_edit)

        # The form with the configuration options
        fbox = QFormLayout()

        # Project
        project_label = QLabel('Project:')

        project_layout = QVBoxLayout()

        self.project_name = ElideLabel()
        if self.conf.project is not None:
            self.project_name.setText(str(config.project))
        else:
            self.project_name.setText(LBL_CREATE_PROJECT)
        project_layout.addWidget(self.project_name)

        project_buttons_widget = QDialogButtonBox()

        self.create_project_button = QPushButton('New')
        self.create_project_button.setToolTip('Create a new project')
        self.create_project_button.setDefault(True)
        self.create_project_button.clicked.connect(self.on_create_project_button_clicked)
        project_buttons_widget.addButton(self.create_project_button, QDialogButtonBox.ActionRole)

        load_project_button = QPushButton('Load')
        load_project_button.setToolTip('Load an existing project')
        load_project_button.clicked.connect(self.on_load_project_button_clicked)
        project_buttons_widget.addButton(load_project_button, QDialogButtonBox.ActionRole)

        load_example_project_button = QPushButton('Example')
        load_example_project_button.setToolTip('Load a CogniX example')
        load_example_project_button.clicked.connect(self.on_load_example_project_button_clicked)
        project_buttons_widget.addButton(load_example_project_button, QDialogButtonBox.ActionRole)

        project_layout.addWidget(project_buttons_widget)

        fbox.addRow(project_label, project_layout)

        # Nodes packages
        packages_label = QLabel('Nodes packages:')

        packages_layout = QVBoxLayout()
        packages_sublayout = QHBoxLayout()

        # FIXME: The three following columns should have half their default size!
        # ???: How is that achieved?
        packages_imported_layout = QVBoxLayout()
        label_imported = QLabel('Imported:')
        label_imported.setToolTip(
            'Nodes packages which are required by the project and are found'
        )
        label_imported.setAlignment(Qt.AlignCenter)
        packages_imported_layout.addWidget(label_imported)
        self.imported_list_widget = QListWidget()
        packages_imported_layout.addWidget(self.imported_list_widget)
        packages_sublayout.addLayout(packages_imported_layout)

        packages_missing_layout = QVBoxLayout()
        label_missing = QLabel('Missing:')
        label_missing.setToolTip(
            'Nodes packages which are required by the project but could not be found'
        )
        label_missing.setAlignment(Qt.AlignCenter)
        packages_missing_layout.addWidget(label_missing)
        self.missing_list_widget = QListWidget()
        packages_missing_layout.addWidget(self.missing_list_widget)
        packages_sublayout.addLayout(packages_missing_layout)

        packages_manually_layout = QVBoxLayout()
        label_manually = QLabel('Manually imported:')
        label_manually.setToolTip(
            '''Nodes packages which are manually imported
            They will override the packages required by the project
            Additional packages can be imported later.'''
        )
        label_manually.setAlignment(Qt.AlignCenter)
        packages_manually_layout.addWidget(label_manually)

        self.manually_list_widget = QListWidget()
        self.manually_list_widget.setSelectionMode(QListWidget.MultiSelection)
        self.manually_list_widget.itemSelectionChanged.connect(self.on_packages_manually_selection)
        packages_manually_layout.addWidget(self.manually_list_widget)
        packages_sublayout.addLayout(packages_manually_layout)

        packages_layout.addLayout(packages_sublayout)

        packages_buttons_widget = QDialogButtonBox()
        self.autodiscover_packages_button = QPushButton('Find')
        self.autodiscover_packages_button.setToolTip(
            'Automatically find and import missing packages'
        )
        self.autodiscover_packages_button.clicked.connect(self.on_autodiscover_package_clicked)
        packages_buttons_widget.addButton(self.autodiscover_packages_button, QDialogButtonBox.ActionRole)
        self.autodiscover_packages_button.setEnabled(False)
        
        import_package_button = QPushButton('Import')
        import_package_button.setToolTip('Manually load a nodes package')
        import_package_button.clicked.connect(self.on_import_package_clicked)
        packages_buttons_widget.addButton(import_package_button, QDialogButtonBox.ActionRole)

        self.remove_packages_button = QPushButton('Remove')
        self.remove_packages_button.setToolTip(
            'Remove manually imported nodes packages'
        )
        self.remove_packages_button.clicked.connect(self.on_remove_packages_clicked)
        self.remove_packages_button.setEnabled(False)
        packages_buttons_widget.addButton(self.remove_packages_button, QDialogButtonBox.ActionRole)

        self.clear_packages_button = QPushButton('Clear')
        self.clear_packages_button.setToolTip(
            'Clear the list of manually imported nodes packages '
        )
        self.clear_packages_button.clicked.connect(self.on_clear_packages_clicked)
        self.clear_packages_button.setEnabled(False)
        packages_buttons_widget.addButton(self.clear_packages_button, QDialogButtonBox.ActionRole)
        packages_layout.addWidget(packages_buttons_widget)

        fbox.addRow(packages_label, packages_layout)
        
        # Window theme
        windowtheme_label = QLabel('Window theme:')
        windowtheme_widget = QComboBox()
        windowtheme_widget.setToolTip(
            'Select the main CogniX theme.'
        )
        windowtheme_widget.addItems([theme.value for theme in self.conf.get_available_window_themes()])
        windowtheme_widget.currentTextChanged.connect(self.on_window_theme_toggled)
        fbox.addRow(windowtheme_label, windowtheme_widget)

        # Flow theme
        flowtheme_label = QLabel('Flow theme:')
        flowtheme_widget = QComboBox()
        flowtheme_widget.setToolTip(
            'Select the theme of the flow display\nCan also be changed later …'
        )
        flowtheme_widget.addItems(
            [LBL_DEFAULT_FLOW_THEME] + list(self.conf.get_available_flow_themes())
        )
        flowtheme_widget.insertSeparator(1)
        flowtheme_widget.currentTextChanged.connect(self.on_flow_theme_selected)
        fbox.addRow(flowtheme_label, flowtheme_widget)

        # Performance mode
        performance_label = QLabel('Performance mode:')
        performance_layout = QHBoxLayout()
        performance_button_group = QButtonGroup(performance_layout)
        self.perf_mode_rbs = {
            mode: QRadioButton(mode)
            for mode in self.conf.get_available_performance_modes()
        }
        for rb in self.perf_mode_rbs.values():
            performance_button_group.addButton(rb)
            performance_layout.addWidget(rb)
        performance_button_group.buttonToggled.connect(self.on_performance_toggled)
        fbox.addRow(performance_label, performance_layout)

        # Animations
        animations_label = QLabel('Animations:')
        animations_cb = QCheckBox('Animations')
        animations_cb.toggled.connect(self.on_animations_toggled)
        fbox.addRow(animations_label, animations_cb)

        # Title
        title_label = QLabel('Window title:')
        self.title_lineedit = QLineEdit()
        self.title_lineedit.textChanged.connect(self.on_title_changed)
        fbox.addRow(title_label, self.title_lineedit)

        # Verbose
        verbose_output_label = QLabel('Verbose:')
        verbose_output_cb = QCheckBox('Enable verbose output')
        verbose_output_cb.setToolTip(
            f'''Choose whether verbose output should be displayed. 
            Verbose output prevents stdout and stderr from being
            displayed in the in-editor console, that usually means
            all output goes to the terminal from which CogniX Editor was
            launched. Also, it causes lots of debug info to be 
            printed.'''
        )
        verbose_output_cb.toggled.connect(self.on_verbose_toggled)
        fbox.addRow(verbose_output_label, verbose_output_cb)

        # Defer source code loading
        defer_code_label = QLabel('Defer SCL:')
        defer_code_cb = QCheckBox('Enable defer source code loading')
        defer_code_cb.setToolTip(
            f'''Choose whether source code will be loaded on package
            import or when the user manually attempt to inspect the
            source on a specific node. Helps reduce package import
            time.'''
        )
        defer_code_cb.toggled.connect(self.on_defer_toggled)
        fbox.addRow(defer_code_label, defer_code_cb)
        
        # Rest API
        rest_api_widget = QWidget()
        rest_api_widget.setLayout(QHBoxLayout())
        
        rest_api_label = QLabel('RESTful API:')
        rest_api_cb = QCheckBox('Enabled')
        rest_api_cb.setToolTip(
            f'''Choose whether you want to start a RESTful service to connect
            to the CogniX Session. If the given port is not available, a random
            free port will be chosen.
            '''
        )
        
        # check box
        
        rest_api_cb.toggled.connect(self.on_rest_api_toggled)
        rest_api_cb.setChecked(self.conf.rest_api)
        rest_api_widget.layout().addWidget(rest_api_cb)
        
        # port
        self.rest_api_port = QLineEdit(str(self.conf.rest_api_port))
        self.rest_api_port.setValidator(QIntValidator())
        self.rest_api_port.editingFinished.connect(self.on_rest_port_edited)
        rest_api_widget.layout().addWidget(self.rest_api_port)
        
        fbox.addRow(rest_api_label, rest_api_widget)
        
        layout.addLayout(fbox)

        # Buttons
        buttons_layout = QHBoxLayout()
        gen_config_button = QPushButton('generate / save config')
        gen_config_button.clicked.connect(self.gen_config_clicked)
        buttons_layout.addWidget(gen_config_button)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.ok_button = buttons.button(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons_layout.addWidget(buttons)
        layout.addLayout(buttons_layout)

        self.setLayout(layout)

        #
        # Populate/set the widgets
        #

        # Set project
        self.load_project(self.conf.project)

        # Set requested nodes
        self.update_packages_lists()

        # Set window theme
        windowtheme_widget.setCurrentText(self.conf.window_theme)

        # Set performance mode
        for mode, rb in self.perf_mode_rbs.items():
            rb.setChecked(self.conf.performance_mode == mode)

        # Set animations
        animations_cb.setChecked(self.conf.animations)

        # Set title
        self.title_lineedit.setText(self.conf.window_title)

        # Set flow theme
        if self.conf.flow_theme is not None:
            idx = flowtheme_widget.findText(self.conf.flow_theme)
        else:
            idx = flowtheme_widget.findText(LBL_DEFAULT_FLOW_THEME)
        flowtheme_widget.setCurrentIndex(idx)

        # Set verbose output
        verbose_output_cb.setChecked(self.conf.verbose)

        # Set defer code loading
        defer_code_cb.setChecked(self.conf.defer_code_loading)
        
        # Set window title and icon
        self.setWindowTitle('CogniX')
        self.setWindowIcon(
            QIcon(abs_path_from_package_dir('resources/pics/cognix/cognix_icon_small.png'))
        )

    #
    # Call-back methods
    #

    # Project

    def on_create_project_button_clicked(self):
        """Call-back method, whenever the 'New' button was clicked."""
        # Create a new project
        self.load_project(None)

    def on_load_project_button_clicked(self):
        """Call-back method, whenever the 'Load' button was clicked."""
        # Load a saved project, starting in the user's cognix directory
        project_path = self.get_project(abs_path_from_dir('saves'))

        if project_path is not None:
            self.load_project(project_path)

    def on_load_example_project_button_clicked(self):
        """Call-back method, whenever the 'Example' button was clicked."""
        # Load an example project, starting in the cognix's example directory
        project_path = self.get_project(
            abs_path_from_package_dir('examples_projects'), title='Select CogniX example'
        )

        if project_path is not None:
            self.load_project(project_path)

    # Nodes packages

    def on_packages_manually_selection(self):
        """Call-back method, whenever a package in the manual list was selected."""
        # En/Disable the 'Remove' button
        if self.manually_list_widget.selectedItems():
            self.remove_packages_button.setEnabled(True)
        else:
            self.remove_packages_button.setEnabled(False)

    def on_autodiscover_package_clicked(self):
        """Call-back method, whenever the 'Find' button was clicked."""
        # Search in user packages
        self.auto_discover(pathlib.Path(dir_path(), 'nodes'))
        self.update_packages_lists()

        # Search in example packages
        self.auto_discover(pathlib.Path(abs_path_from_package_dir('example_nodes')))
        self.update_packages_lists()

    def on_import_package_clicked(self):
        """Call-back method, whenever the 'Import' button was clicked."""
        # Import a nodes package, starting in the user's cognix directory
        file_name = QFileDialog.getOpenFileName(
            self,
            'Select',
            abs_path_from_dir('packages'),
            'ryven nodes package (nodes.py)',
        )[0]

        if file_name:
            file_path = pathlib.Path(file_name)
            if file_path.exists():
                self.conf.nodes.add(file_path.parent)
                self.update_packages_lists()

    def on_remove_packages_clicked(self):
        """Call-back method, whenever the 'Remove' button was clicked."""
        # Remove packages selected in the manual imported list
        for item in self.manually_list_widget.selectedItems():
            package_name = item.text()
            for pkg_path in self.conf.nodes:
                if pkg_path.stem == package_name:
                    self.conf.nodes.remove(pkg_path)
                    break

        self.update_packages_lists()

    def on_clear_packages_clicked(self):
        """Call-back method, for when the 'Clear' button was clicked."""
        # Clear the manual imported list
        self.conf.nodes.clear()

        self.update_packages_lists()

    # Window theme

    def on_window_theme_toggled(self, theme):
        """Call-back method, whenever a window theme radio button was toggled."""
        # Apply the selected window theme
        self.conf.window_theme = theme            
        # Set the StartupDialog to the selected theme
        apply_stylesheet(self.conf.window_theme)

    # Flow theme

    def on_flow_theme_selected(self, theme):
        """Call-back method, whenever a new flow theme was selected."""
        # "Apply" the selected flow theme
        if theme == LBL_DEFAULT_FLOW_THEME:
            self.conf.flow_theme = Config.flow_theme
        else:
            self.conf.flow_theme = theme

    # Performance mode

    def on_performance_toggled(self):
        """Call-back method, whenever a new performance mode was selected"""
        for mode, rb in self.perf_mode_rbs.items():
            if rb.isChecked():
                self.conf.performance_mode = mode
                break

    # Animations

    def on_animations_toggled(self, check):
        """Call-back method, whenever animations are enabled/disabled"""
        self.conf.animations = check

    # Title

    def on_title_changed(self, t):
        """Call-back method, whenever the title was changed"""
        self.conf.window_title = t

    # Verbose output

    def on_verbose_toggled(self, check):
        """Call-back method, whenever the verbose checkbox was toggled."""
        # "Apply" the verbose option
        self.conf.verbose = check

    # Defer Source Code Loading
    def on_defer_toggled(self, check):
        """Call-back method, whenever the defer source code loading checkbox was toggled"""
        self.conf.defer_code_loading = check
    #
    
    def on_rest_api_toggled(self, check):
        """Call-back method, whenever the rest api checkbox was toggled"""
        self.conf.rest_api = check
        
    def on_rest_port_edited(self):
        """Call-back method, whenever the rest api port was changed"""
        self.conf.rest_api_port = int(self.rest_api_port.text())
        
    # Helper/Working methods
    #

    def get_project(
        self, base_dir: str, title='Select project file'
    ) -> pathlib.Path | None:
        """
        Get a project file from the user.

        Parameters
        ----------
        base_dir : str|pathlib.Path
            The initial directory shown in the file dialog.
        title : str, optional
            The title of the file dialog.
            The default is 'Select project file'.

        Returns
        -------
        file_path : pathlib.Path|None
            The path of the selected file.

        """
        # Get the file from the user
        file_name = QFileDialog.getOpenFileName(
            self, title, str(base_dir), 'JSON (*.json)'
        )[0]

        if file_name:
            file_path = pathlib.Path(file_name)
            if file_path.exists():
                return file_path

        return None

    def load_project(self, project_path: pathlib.Path | None):
        """
        Load a project file.

        It opens the project file and scans for all required node packages.
        These are displayed in the imported packages list. All packages which
        could not be found are displayed in the missing packages list.

        Parameters
        ----------
        project_path : pathlib.Path
            The project's file name to be loaded.

        Returns
        -------
        None.

        """

        self.imported_list_widget.clear()
        self.missing_list_widget.clear()
        # TODO avoid including the basic cognix library in the missing list
        built_in = MainWindow.built_in_packages()
        
        if project_path is None:
            self.conf.project = None
            self.project_name.setText(LBL_CREATE_PROJECT)
            self.create_project_button.setEnabled(False)

        else:
            self.conf.project = project_path
            self.project_name.setText(project_path)
            self.create_project_button.setEnabled(True)

            required_nodes, missing_nodes, _ = process_nodes_packages(project_path)
            item_flags = ~Qt.ItemIsSelectable & ~Qt.ItemIsEditable
            for node in sorted(required_nodes, key=lambda n: n.name):
                if node.name in built_in:
                    continue
                node_item = QListWidgetItem(node.name)
                node_item.setToolTip(node.directory)
                node_item.setFlags(item_flags)
                self.imported_list_widget.addItem(node_item)
            for node_path in sorted(missing_nodes, key=lambda p: p.name):
                if node_path.name in built_in:
                    continue
                node_item = QListWidgetItem(node_path.name)
                node_item.setToolTip(str(node_path))
                node_item.setFlags(item_flags)
                self.missing_list_widget.addItem(node_item)

        self.update_packages_lists()

    def auto_discover(self, packages_dir):
        """Automatically find and import missing packages.

        Parameters
        ----------
        packages_dir : str|pathlib.Path
            The directory under which packages should be searched.

        Returns
        -------
        None.

        """
        # List of packages which are missing
        missing_packages = [
            self.missing_list_widget.item(i).text()
            for i in range(self.missing_list_widget.count())
        ]

        # Search for missing packages under `package_dir`
        for entry in filter(lambda e: e.is_dir(), os.scandir(packages_dir)):
            path = pathlib.Path(entry.path)
            if path.name in missing_packages:
                node_path = path.joinpath('nodes.py')
                if node_path.exists():
                    self.conf.nodes.add(path)

    def update_packages_lists(self):
        """Update the packages lists and buttons.

        1. Mark all imported packages, if they were manually imported.
        2. Mark all missing packages, if they were manually imported.
        3. Repopulate the list with manually imported packages.
        4. En/Disable 'Ok', 'Find' and 'Clear' buttons.
        """
        # Mark all imported packages, if they were manually imported
        built_in = MainWindow.built_in_packages()
        for i in range(self.imported_list_widget.count()):
            node_item = self.imported_list_widget.item(i)
            font = node_item.font()
            for pkg_path in self.conf.nodes:
                n_text = node_item.text()
                if n_text == pkg_path.stem or n_text in built_in:
                    # Required package is overwritten by manually imported package
                    font.setStrikeOut(True)
                    break
            else:
                font.setStrikeOut(False)
            node_item.setFont(font)

        # Mark all missing packages, if they were manually imported
        missing_packages = False  # Track, if we have to enable the 'Find' button
        for i in range(self.missing_list_widget.count()):
            node_item = self.missing_list_widget.item(i)
            font = node_item.font()
            for pkg_path in self.conf.nodes:
                n_text = node_item.text()
                if n_text == pkg_path.stem or n_text in built_in:
                    # Missing package is provided by manually imported package
                    font.setStrikeOut(True)
                    break
            else:
                font.setStrikeOut(False)
                missing_packages = True
            node_item.setFont(font)

        # Repopulate the list with manually imported packages
        self.manually_list_widget.clear()
        for pkg_path in sorted(self.conf.nodes):
            node_item = QListWidgetItem(pkg_path.stem)
            node_item.setToolTip(str(pkg_path))
            node_item.setFlags(~Qt.ItemIsEditable)
            self.manually_list_widget.addItem(node_item)

        # Update the buttons
        if missing_packages:
            # There are still packages missing
            self.ok_button.setEnabled(False)
            self.ok_button.setToolTip('Import all missing packages first')
            self.autodiscover_packages_button.setEnabled(True)
        else:
            # No missing packages
            self.ok_button.setEnabled(True)
            self.ok_button.setToolTip(None)
            self.autodiscover_packages_button.setEnabled(False)
        self.clear_packages_button.setEnabled(bool(self.conf.nodes))

    def gen_config_clicked(self):
        """Generates the command analogous to the specified settings
        as well as the according config file content.
        Opens a dialog with option to save to config file.
        """

        # Convert configuration dictionary to command line argument and
        # configuration file contents
        command, config = unparse_sys_args(self.conf)

        d = ShowCommandDialog(command, config)
        d.exec()
