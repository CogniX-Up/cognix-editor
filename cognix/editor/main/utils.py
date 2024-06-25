"""
Core utilities for handling Ryven projects and nodes packages, and
resolving paths. Deos not depend on any Qt modules.
"""
import sys
import os
from os import environ
from os.path import normpath, join, dirname, abspath, expanduser
import pathlib
import importlib
import importlib.util
from typing import Union, Optional, Tuple
from packaging.version import Version

from cognixcore import InfoMsgs

def is_package_available(package_name:str ):
    return importlib.util.find_spec(package_name) is not None


def in_gui_mode() -> bool:
    return environ['COGNIX_MODE'] == 'gui'


def load_from_file(file: str = None, components_list: list[str] = None) -> Tuple:
    """
    Imports specified components from a python module with given file path.
    The directory of the file is added to sys.path if not already present.
    """
    if components_list is None:
        components_list = []

    dirpath, filename = os.path.split(file)
    parent_dirpath, pkg_name = os.path.split(dirpath)
    mod_name = filename.split('.')[0]
    name = f"{pkg_name}.{mod_name}"  # e.g. built_in.nodes

    # protection from re-loading for no reason
    if name in sys.modules:
        return
    
    if parent_dirpath not in sys.path:
        sys.path.append(parent_dirpath)
    
    # import the corresponding module
    try:
        mod = importlib.import_module(name, pkg_name)
        comps = tuple([getattr(mod, c) for c in components_list])
        return comps
    except ModuleNotFoundError as e:
        InfoMsgs.write_err(
            f'\n\nCould not import {name}: {e}\n'
            f'This could be due to a missing __init__.py file in the nodes package, '
            f'or your package name conflicts with another python package name '
            f'that the interpreter knows about (e.g. math).\n\n'
        )


def read_project(project_path: Union[str, pathlib.Path]) -> dict:
    """Read the project file and return its dictionary.

    :param project_path: The path to the project file.
    :return: The contents of the project file.
    """
    import io
    import json

    if isinstance(project_path, io.TextIOWrapper):
        project_dict = json.loads(project_path.read(), strict=False)
    else:
        with open(project_path) as f:
            import json
            # strict=False is needed to allow 'control characters' like '\n'
            # for newline when loading the json
            project_dict = json.load(f, strict=False)

    # backward compatibility: translate old project files to current version
    if 'cognix version' not in project_dict['general info'] or \
            Version(project_dict['general info']['cognix version']) < Version('1.0'):
        print(
            'WARNING: project was created with an older version of Cognix.',
            'Attempting to translate project to current version.'
        )
        project_dict = translate_project_v3_2_0(project_dict)

    return project_dict


def translate_project_v3_2_0(p: dict):
    def max_gid(d: dict) -> int:
        """Recursively find the maximum GID used in the project.."""
        n = 0
        for k, v in d.items():
            if isinstance(v, dict):
                n = max(n, max_gid(v))
            elif isinstance(v, list):
                for e in v:
                    if isinstance(e, dict):
                        n = max(n, max_gid(e))
            elif k == 'GID':
                n = max(n, v)
        return n

    gid_ctr = max_gid(p) + 1
    def get_gid():
        nonlocal gid_ctr
        gid_ctr += 1
        return gid_ctr

    def replace_item(obj, key, replace_value):
        # https://stackoverflow.com/questions/45335445/how-to-recursively-replace-dictionary-values-with-a-matching-key
        for k, v in obj.items():
            if isinstance(v, dict):
                obj[k] = replace_item(v, key, replace_value)
        if key in obj:
            obj[key] = replace_value
        return obj

    proj = {
        'general info': p['general info'],
        'required packages': p['required packages'],
        'GID': get_gid(),
        'version': '0.4.0',
        'flows': {},
        'addons': {},
    }

    variables = {}

    for s in p['scripts']:
        t = s['title']
        vars = s['variables']
        gid = s['flow']['GID']
        variables[(t, gid)] = vars

        proj['flows'][t] = {
            'GID': gid,
            'algorithm mode': s['flow']['algorithm mode'],
            'nodes': [
                {
                    **n_d,
                    # remove input widget data to prevent loading errors
                    # because many of the nodes have new input widget
                    # classes now
                    'inputs': [
                        replace_item(i, 'widget data', None)
                        for i in n_d['inputs']
                    ]
                } for n_d in s['flow']['nodes']
            ],
            'connections': s['flow']['connections'],
            'flow view': s['flow']['flow view'],
            'output data': [{
                # simply set every output to None
                'data': {
                    'GID': get_gid(),
                    'identifier': 'Data',
                    'serialized': 'gAROLg==',  # encoded 'None'
                },
                'dependent node outputs': [],
            }]
        }

    proj['addons']['Variables'] = {
        'GID': get_gid(),
        'version': '0.4',
        'custom state': {
            flow_id: {
                v: {
                    'GID': get_gid(),
                    'identifier': 'Data',
                    'serialized': content['serialized'],
                }
                for v, content in vars.items()
            }
            for (flow_name, flow_id), vars in variables.items()
        }
    }

    # ignoring loggers and actions

    return proj


def find_project(project_path: Union[str, pathlib.Path]) -> Optional[pathlib.Path]:
    """Resolves a possibly *~/.cognix/saves/*-relative path to a nodes package to an absolute path.

    :param project_path: The path to the project file or the subpath to :code:`cognix()/saves`.
        The file extension '.json' can be omitted.
    :return: The absolute and resolved path to the project file, or `None` if it could not be found.

    """
    project_path = pathlib.Path(project_path)

    if project_path.exists():
        return project_path.resolve()
    elif project_path.with_suffix('.json').exists():
        return project_path.with_suffix('.json').resolve()
    else:
        project_path = pathlib.Path(dir_path(), 'saves', project_path)
        if project_path.exists():
            return project_path.resolve()
        elif project_path.with_suffix('.json').exists():
            return project_path.with_suffix('.json').resolve()
        else:
            return None


def find_config_file(cfg_file_path: str) -> Optional[pathlib.Path]:
    """Resolves a possibly *~/.cognix/*-relative path of a config file to an absolute path.

    :param cfg_file_path: Either an absolute path, or relative to the *~/.cognix/* directory.
        The file extension '.cfg' can be omitted.
    :return: The full path to the config file or `None`, if it could not be found.
    """

    config_file_path = pathlib.Path(cfg_file_path)

    if config_file_path.exists():
        return config_file_path.resolve()
    else:
        config_file_path = pathlib.Path(dir_path(), cfg_file_path)
        if config_file_path.exists():
            return config_file_path.resolve()
        else:
            return None


def dir_path() -> str:
    """
    :return: absolute path to the (OS-specific) '~/.cognix/' folder
    """
    return abspath(normpath(join(expanduser('~'), '.cognix/')))


def abs_path_from_package_dir(rel_path: str):
    """
    :param rel_path: path relative to package folder (e.g. main/node_env.py)
    :return: absolute path
    """
    cognix_path = dirname(dirname(__file__))
    return abspath(join(cognix_path, rel_path))


def abs_path_from_dir(rel_path: str):
    """
    :param rel_path: path relative to '~/.cognix/' dir (e.g. saves)
    :return: absolute path
    """

    return abspath(join(dir_path(), rel_path))


def cognix_version() -> Version:
    """
    :return: the version of Cognix
    """

    # if we are in a development environment, we can't use importlib.metadata
    if (pathlib.Path(abs_path_from_package_dir('../setup.cfg'))).exists():
        # read the version from setup.cfg
        import configparser
        config = configparser.ConfigParser()
        config.read(abs_path_from_package_dir('../setup.cfg'))
        ver = Version(config['metadata']['version'])
        return ver
    else:
        # read the version from importlib.metadata
        from importlib.metadata import version
        return Version(version('cognix'))
