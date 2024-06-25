import pathlib
from .. import NodesPackage
from ..gui.styling.window_theme import WindowThemeType


class Config:
    """
    Internal representation of the configuration that the application is
    currently using.

    The args parser uses the default values of this class for the defaults
    of config arguments (or cmd line). At runtime, this class is
    instantiated and populated with the values of the config arguments.

    WHEN MODIFYING THIS CLASS, make sure to update parse_sys_args() in
    args_parser.py accordingly.
    """

    #
    # config options declaration with default values.
    # the options where the type is a union will be literals
    # initially, but will be converted to actual types
    # by the args parser.
    #

    project: pathlib.Path | None = None
    show_dialog: bool = True
    verbose: bool = False
    nodes: set[pathlib.Path] | set[NodesPackage] = []
    example: str | None = None
    window_theme: str | WindowThemeType = WindowThemeType.QDARKTHEME_DARK.value
    flow_theme: str | None = None  # None means it depends on window_theme
    performance_mode: str = 'fast'
    animations: bool = True
    window_geometry: str | None = None
    window_title: str = 'CogniX'
    qt_api: str = 'pyside6'
    src_code_edits_enabled: bool = False
    defer_code_loading: bool = True
    rest_api: bool = False
    rest_api_port: int = 7555

    @staticmethod
    def get_available_window_themes() -> list[WindowThemeType]:
        return [theme for theme in WindowThemeType]

    @staticmethod
    def get_available_flow_themes() -> set[str]:
        # TODO: expose this in ryvencore_qt without requiring Qt import, since QT_API is not set yet
        return {
            "Toy", "Tron", "Ghost", "Blender", "Simple",
            "Ueli", "pure dark", "colorful dark", "pure light",
            "colorful light", "Industrial", "Fusion"
        }

    @staticmethod
    def get_available_performance_modes() -> set[str]:
        return {'pretty', 'fast'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        global instance
        if instance is not None:
            raise RuntimeError('Config is a singleton')
        instance = self


instance: Config | None = None
