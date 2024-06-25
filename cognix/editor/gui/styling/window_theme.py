from ...main.utils import abs_path_from_package_dir
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qtpy.QtWidgets import QApplication

def hex_to_rgb(hex: str):
    if hex is None:
        return None
    else:
        return tuple(int(hex[i:i + 2], 16) for i in (1, 3, 5))


class WindowThemeType(Enum):
    PLAIN = 'plain'
    RYVEN_DARK = 'ryven-dark'
    RYVEN_LIGHT = 'ryven-light'
    QDARKSTYLE_DARK = 'qdarkstyle-dark'
    QDARKSTYLE_LIGHT = 'qdarkstyle-light'
    QDARKTHEME_DARK = 'qdarktheme-dark'
    QDARKTHEME_LIGHT = 'qdarktheme-light'
        
     
class RyvenPalette:
    """
    A class for a custom window theme. Should be combined with a corresponding
    WindowThemeType if the stylesheet is created from scratch. Otherwise, this
    is not needed.
    """
    
    name = ''
    colors = {}
    rules = {}

    def __init__(self):
        self.init_rules()

    def init_rules(self):
        self.rules = {
            # colors
            **self.colors,

            # rgb inline versions
            **{
                'rgb_inline_'+cname: str(hex_to_rgb(val))[1:-1]
                for cname, val in self.colors.items()
            },

            # additional rules
            'font_family': 'Roboto',
        }


class RyvenDarkPalette(RyvenPalette):
    name = 'dark'
    colors = {
        'primaryColor': '#448aff',
        'primaryLightColor': '#83b9ff',
        'secondaryColor': '#1E242A',
        'secondaryLightColor': '#272d32',
        'secondaryDarkColor': '#0C1116',
        'primaryTextColor': '#E9E9E9',
        'secondaryTextColor': '#9F9F9F',
        'danger': '#dc3545',
        'warning': '#ffc107',
        'success': '#17a2b8',
    }


class RyvenLightPalette(RyvenPalette):
    name = 'light'
    colors = {
        'primaryColor': '#448aff',
        'primaryLightColor': '#508AD8',
        'secondaryColor': '#FFFFFF',
        'secondaryLightColor': '#E8EAEC',
        'secondaryDarkColor': '#ECEDEF',
        'primaryTextColor': '#1A1A1A',
        'secondaryTextColor': '#6E6E6E',
        'danger': '#dc3545',
        'warning': '#ffc107',
        'success': '#17a2b8',
    }


class RyvenPlainPalette(RyvenPalette):
    name = 'plain'
    colors = {
        'primaryColor': None,
        'primaryLightColor': None,
        'secondaryColor': None,
        'secondaryLightColor': None,
        'secondaryDarkColor': None,
        'primaryTextColor': None,
        'secondaryTextColor': None,
        'danger': None,
        'warning': None,
        'success': None,
    }

__flow_theme_light = 'pure light'
__flow_theme_dark = 'pure dark'

def __apply_plain(app: 'QApplication'):
    from qtpy.QtWidgets import QApplication
    app.setStyleSheet(None)
    app.setPalette(QApplication.style().standardPalette())
    return (RyvenPlainPalette(), __flow_theme_light)

# ryven originals 

def __apply_ryven_theme(app: 'QApplication', ryven_palette: RyvenPalette, flow_theme: str) :
    from jinja2 import Template
    # path to the template stylesheet file
    template_file = abs_path_from_package_dir('resources/stylesheets/style_template.css')
    with open(template_file) as f:
        jinja_template = Template(f.read())

    stylesheet = jinja_template.render(ryven_palette.rules)
    app.setStyleSheet(stylesheet)
    return (ryven_palette, flow_theme)

def __apply_ryven_dark(app: 'QApplication'):
    return __apply_ryven_theme(app, RyvenDarkPalette(), __flow_theme_dark)

def __apply_ryven_light(app: 'QApplication'):
    return __apply_ryven_theme(app, RyvenLightPalette(), __flow_theme_light)

# qdarkstyle

def __apply_qdarkstyle(app: 'QApplication', ryven_palette: RyvenPalette, flow_theme: str, palette = None):
    from qdarkstyle import load_stylesheet
    def __apply_internal():
        if palette:
            style_sheet = load_stylesheet(palette=palette)
        else:
            style_sheet = load_stylesheet()
        app.setStyleSheet(style_sheet)
        return (ryven_palette, flow_theme)
    return __apply_internal()

def __apply_qdarkstyle_dark(app: 'QApplication'):
    return __apply_qdarkstyle(app, RyvenDarkPalette(), __flow_theme_dark)

def __apply_qdarkstyle_light(app: 'QApplication'):
    from qdarkstyle import LightPalette as l
    return __apply_qdarkstyle(app, RyvenLightPalette(), __flow_theme_light, l)
    
    
# qdarktheme

def __apply_qdarktheme(app: 'QApplication', theme: str, ryven_palette: RyvenPalette, flow_theme: str):
    from qdarktheme import setup_theme
    def __apply_internal():
        qss = """
        QToolTip {
            color: black;
        }
        """
        setup_theme(theme, additional_qss=qss)
        return (ryven_palette, flow_theme)
    return __apply_internal()

def __apply_qdarktheme_dark(app: 'QApplication'):
    return __apply_qdarktheme(app, 'dark', RyvenLightPalette(), __flow_theme_dark)

def __apply_qdarktheme_light(app: 'QApplication'):
    return __apply_qdarktheme(app, 'light', RyvenLightPalette(), __flow_theme_light)


# stores the various styles in a dictionary as tuple(style, string)
# the string indicates whether the style is light or dark (for code inspection purposes)
__style_application_dict: dict = {
    WindowThemeType.PLAIN : (__apply_plain, 'l'),
    WindowThemeType.RYVEN_DARK: (__apply_ryven_dark, 'd'),
    WindowThemeType.RYVEN_LIGHT: (__apply_ryven_light, 'l'),
    WindowThemeType.QDARKSTYLE_DARK: (__apply_qdarkstyle_dark, 'd'),
    WindowThemeType.QDARKSTYLE_LIGHT: (__apply_qdarkstyle_light, 'l'),
    WindowThemeType.QDARKTHEME_DARK: (__apply_qdarktheme_dark, 'd'),
    WindowThemeType.QDARKTHEME_LIGHT: (__apply_qdarktheme_light, 'l'),
}  

def apply_stylesheet(style: str) -> tuple[WindowThemeType, RyvenPalette, str, str]:
    """
    Applies an existing stylesheet to the Window.
    
    Returns a tuple of (WindowThemeType, RyvenPalette, <name of flow style>, 'dark'| 'light')
    """
    from qtpy.QtWidgets import QApplication
    
    # set to None if not used
    icons_dir = abs_path_from_package_dir('resources/stylesheets/icons')
    if icons_dir is not None:
        from qtpy.QtCore import QDir
        d = QDir()
        d.setSearchPaths('icon', [icons_dir])

    if not isinstance(style, WindowThemeType):
        try:
            style = WindowThemeType(style)
        except:
            style = WindowThemeType.PLAIN
    
    func, wnd_brightness = __style_application_dict[style]
    ryven_palette, flow_theme = func(QApplication.instance())
    wnd_brightness = 'dark' if wnd_brightness == 'd' else 'light' 
    return (style, ryven_palette, flow_theme, wnd_brightness)
