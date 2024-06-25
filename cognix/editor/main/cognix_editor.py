from __future__ import annotations
import os
import sys

from .packages import nodes_package
from . import utils
from .config import Config
from .args_parser import process_args
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..gui.main_window import MainWindow

def run(*args_,
        qt_app=None, gui_parent=None, use_sysargs=True,
        **kwargs) -> None | MainWindow:
    """Start the CogniX Editor window.

    The `*args_` and `**kwargs` arguments correspond to their positional and
    optional command line equivalents, respectively (see `parse_args()`).
    Optional keyword arguments are specified without the leading double hyphens
    '--'. As a name, the corresponding 'dest' value of `add_argument` has to
    be used. E.g. the command line:
        cognix --window-theme=light --nodes=std --nodes=linalg myproject.json
    becomes:
        run('myproject.json', window_theme='light', nodes=['std', 'linalg'])

    Note 1
    ------
    The `*args_` and `**kwargs` takes predecence and overwrites the values
    specified on the command line (or the default values, if
    `use_sysargs=False` is given). The exception are lists, which are appended,
    e.g. in the example from above, the two nodes 'std' and 'linalg' are added
    at the end of the nodes supplied at the command line.

    Note 2
    ------
    The positional command line argument to specify the project file also
    checks `utils.dir_path()/saves`, if it can find the project file.
    The `*args_` does not perform this check. This is up to the developer
    calling `run()`. The developer can always use `utils.find_project()` to
    find projects in this additional directory.

    Parameters
    ----------
    qt_app : QApplication, optional
        The `QApplication` to be used. If `None` a `QApplication` is generated.
        The default is `None`.
    gui_parent : QWidget, optional
        The parent `QWidget`.
        The default is `None`.
    use_sysargs : bool, optional
        Whether the command line arguments should be used.
        The default is `True`.
    *args_ : str
        Corresponding to the positional command line argument(s).
    **kwargs : any
        Corresponding to the keyword command line arguments.

    Raises
    ------
    TypeError
        Raised, if keyword argument is not specified by the argument parser or
        the wrong number of positional arguments are specified.

    Returns
    -------
    None|Main Window
    """
    # Process command line and method's arguments
    conf: Config = process_args(use_sysargs, *args_, **kwargs)

    #
    # Qt application setup
    #
    # Init environment
    os.environ['COGNIX_MODE'] = 'gui'
    os.environ['QT_API'] = conf.qt_api
    from ..node_env import init_node_env
    init_node_env()
    
    # Import GUI sources (must come after setting `os.environ['QT_API']`)
    from ...qtcore.console import Console
    from ..gui.main_window import MainWindow
    from ..gui.styling.window_theme import apply_stylesheet
    # Init Qt application
    if qt_app is None:
        from qtpy.QtWidgets import QApplication
        if conf.window_geometry:
            # Pass '--geometry' argument to Qt
            qt_args = [sys.argv[0], '-geometry', conf.window_geometry]
        else:
            qt_args = [sys.argv[0]]
        
        # TODO figure out what's creating the instance
        app = QApplication.instance() or QApplication(qt_args)
    else:
        app = qt_app

    # Register fonts
    from qtpy.QtGui import QFontDatabase
    db = QFontDatabase()
    db.addApplicationFont(
        utils.abs_path_from_package_dir('resources/fonts/poppins/Poppins-Medium.ttf'))
    db.addApplicationFont(
        utils.abs_path_from_package_dir('resources/fonts/source_code_pro/SourceCodePro-Regular.ttf'))
    db.addApplicationFont(
        utils.abs_path_from_package_dir('resources/fonts/asap/Asap-Regular.ttf'))

    #
    # Editor configuration
    #

    # editor_config = {}

    # Startup dialog
    if conf.show_dialog:
        from ..gui.startup import StartupDialog

        # Get packages and project file interactively and update arguments accordingly

        sw = StartupDialog(config=conf, parent=gui_parent)
        # Exit if dialog couldn't initialize or is exited
        if sw.exec() <= 0:
            sys.exit('Start-up screen dismissed')

    # Replace node directories with `NodePackage` instances
    if conf.nodes:
        conf.nodes, pkgs_not_found, _ = nodes_package.process_nodes_packages(list(conf.nodes))
        if pkgs_not_found:
            sys.exit(
                f'Error: Nodes packages not found: {", ".join([str(p) for p in pkgs_not_found])}')

        # editor_config['requested packages'] = conf.nodes

    # Store WindowThemeType object
    conf.window_theme, ryven_palette, flow_theme, wnd_light_type = apply_stylesheet(conf.window_theme)

    # Adjust flow theme if not set
    if conf.flow_theme is None:
        conf.flow_theme = flow_theme

    # Note:
    #   At this point, the Config is fully populated with exact types
    #   (e.g. `conf.nodes` is a list of `NodePackage` instances, and
    #   not a list of `str` anymore).

    # Get packages required by the project
    built_in = MainWindow.built_in_packages()
    if conf.project:
        pkgs, pkgs_not_found, project_dict = nodes_package.process_nodes_packages(
            conf.project, requested_packages=list(conf.nodes))

        # TODO do this more elegantly somewhere else
        pkgs = {pkg for pkg in pkgs if pkg.name not in built_in}
        pkgs_not_found = {pkg for pkg in pkgs_not_found if pkg.name not in built_in}
        
        if pkgs_not_found:
            str_missing_pkgs = ', '.join([str(p.name) for p in pkgs_not_found])
            plural = len(pkgs_not_found) > 1
            sys.exit(
                f'The package{"s" if plural else ""} {str_missing_pkgs} '
                f'{"were" if plural else "was"} requested, '
                f'but {"they are" if plural else "it is"} not available.\n'
                f'Update the project file or supply the missing package{"s" if plural else ""} '
                f'{str_missing_pkgs} on the command line with the "-n" switch.')

        requested_packages = conf.nodes
        required_packages = pkgs
        project_content = project_dict

    else:
        requested_packages = conf.nodes
        required_packages = None
        project_content = None

    #
    # Launch editor
    #

    # Init main console
    console = Console(ryven_palette)
    console_stdout_redirect, console_errout_redirect = console.redirect_output()

    # Init main window
    editor = MainWindow(
        config=conf,
        requested_packages=requested_packages,
        required_packages=required_packages,
        project_content=project_content,
        parent=gui_parent,
        wnd_light_type=wnd_light_type,
        console=console
    )
    
    # Start application
    if qt_app is None:
        if conf.verbose:
            # Run application
            editor.print_info()
            editor.load()
            sys.exit(app.exec())

        else:
            # Redirect console output
            import contextlib

            with (contextlib.redirect_stdout(console_stdout_redirect),
                    contextlib.redirect_stderr(console_errout_redirect)):
                # Run application
                editor.print_info()
                editor.load()
                sys.exit(app.exec())

    else:
        return editor


if __name__ == '__main__':

    run()
