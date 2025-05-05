"""Tools for managing the houdini/pini interface."""

# pylint: disable=abstract-method

import ast
import inspect
import logging

import hou

from pini.utils import File, abs_path, check_heart, lprint
from hou_pini.utils import flipbook_frame

from .d_base import BaseDCC

if not hou.__file__:
    raise ImportError('Bad hou module')

_LOGGER = logging.getLogger(__name__)


class HouDCC(BaseDCC):
    """Manages interactions with houdini."""

    NAME = 'hou'
    if hou.licenseCategory() == hou.licenseCategoryType.Indie:
        DEFAULT_EXTN = 'hiplc'
    else:
        DEFAULT_EXTN = 'hip'
    VALID_EXTNS = (DEFAULT_EXTN, )
    REF_EXTNS = ('abc', )

    def add_menu_divider(self, parent, name, verbose=0):  # pylint: disable=unused-argument
        """Print xml to declare a separtor item in MainMenuCommon.xml file.

        Args:
            parent (str): parent menu
            name (str): uid for divider
            verbose (int): print process data
        """
        _LOGGER.debug('ADD DIVIDER')
        _xml = '\n'.join([
            '      <separatorItem/>',
            ''])
        lprint(_xml, verbose=verbose)

        return _xml

    def add_menu_item(self, parent, command, image, label, name, verbose=0):  # pylint: disable=unused-argument
        """Print xml to declare a menu item in MainMenuCommon.xml file.

        Args:
            parent (str): parent menu
            command (func): command to call on item click
            image (str): path to item icon
            label (str): label for item
            name (str): uid for item
            verbose (int): print process data
        """
        if isinstance(command, str):
            _cmd = command
        else:
            _mod = inspect.getmodule(command)
            _cmd = f'import {_mod.__name__} as _tmp\n_tmp.{command.__name__}()'

        _LOGGER.debug('ADD MENU ITEM %s', name)
        _xml = '\n'.join([
            f'      <!--Add {label}-->',
            f'      <scriptItem id="{name}">',
            f'        <label>{label}</label>',
            '          <scriptCode><![CDATA[',
            f'{_cmd}',
            ']]>',
            '         </scriptCode>',
            '      </scriptItem>',
            '',
        ])
        lprint(_xml, verbose=verbose)

        return _xml

    def batch_mode(self):
        """Check whether houdini is running in batch mode.

        Returns:
            (bool): batch mode
        """
        return not hou.isUIAvailable()

    def clear_terminal(self):
        """Clear python shell."""
        print('\n' * 5000 + '[Console cleared]')

    def create_ref(self, path, namespace, force=False):
        """Create a reference of the given path in the current scene.

        Args:
            path (File): path to reference
            namespace (str): namespace for reference
            force (bool): replace existing without confirmation
        """
        from pini import pipe
        from hou_pini import h_pipe

        _out = pipe.to_output(path)
        if _out.extn == 'abc':
            _ref = h_pipe.import_abc(abc=_out, namespace=namespace)
        else:
            raise ValueError(_out)
        _ref.node.moveToGoodPosition()

        return _ref

    def cur_file(self):
        """Get path to current scene.

        Returns:
            (str): scene path
        """
        _name = hou.hipFile.name()
        if _name == 'untitled.hip':
            return None
        _path = abs_path(_name)
        return _path

    def _force_load(self, file_):
        """Force load the given file.

        Args:
            file_ (str): file to load
        """
        hou.hipFile.load(file_, suppress_save_prompt=True)

    def _force_new_scene(self):
        """Force new scene."""
        hou.hipFile.clear(suppress_save_prompt=True)

    def _force_save(self, file_=None):
        """Force save the current scene without overwrite confirmation.

        Args:
            file_ (str): path to save scene to
        """
        _path = file_ or self.cur_file()
        if not _path:
            raise RuntimeError('Unabled to determine save path')
        _file = File(_path)
        _LOGGER.info('FORCE SAVE %s', _file.path)
        hou.hipFile.save(_file.path)

    def get_fps(self):
        """Get current frame rate for this dcc.

        Returns:
            (float): frame rate
        """
        return hou.fps()

    def get_main_window_ptr(self):
        """Get main window widget pointer.

        Returns:
            (QWidget): main window
        """
        return hou.ui.mainQtWindow()

    def get_next_namespace(self, base, ignore=(), mode='asset'):  # pylint: disable=unused-argument
        """Get next available namespace.

        Args:
            base (str): namespace base
            ignore (str list): list of namespaces to ignore
            mode (str): how to allocate next namespace
        """
        _name = 'import_' + base
        _idx = 1
        while hou.node('/obj/' + _name) or _name in ignore:
            check_heart()
            _name = f'import_{base}_{_idx:02d}'
            _idx += 1
        return _name

    def get_scene_data(self, key):
        """Retrieve data stored with this scene.

        Args:
            key (str): data to obtain
        """
        _key = f'pini_{key}'
        _data = hou.node('/').userData(_key)
        _LOGGER.debug('GET SCENE DATA %s %s', _key, _data)
        if not _data:
            _val = None
        else:
            _type, _val = _data.split(':', 1)
            if _type == 'int':
                _val = int(_val)
            elif _type == 'str':
                pass
            elif _type == 'float':
                _val = float(_val)
            elif _type in ('list', 'bool'):
                _val = ast.literal_eval(_val)
            else:
                raise ValueError(_type)
        return _val

    def _build_export_handlers(self):
        """Initiate export handlers list."""
        from .. import export
        _LOGGER.debug('INIT EXPORT HANDLERS')
        _handlers = super()._build_export_handlers()
        _handlers += [
            export.CHouFlipbook(),
        ]
        return _handlers

    def _read_pipe_refs(self, selected=False):
        """Find reference in the current dcc.

        Args:
            selected (bool): return only selected refs

        Returns:
            (CPipeRef list): list of references
        """
        from .. import pipe_ref
        return pipe_ref.find_pipe_refs(selected=selected)

    def _read_version(self):
        """Read houdini version.

        Returns:
            (int tuple): houdini version
        """
        return hou.applicationVersion()

    def select_node(self, node):
        """Select the given node.

        Args:
            node (Node): node to select
        """
        node.setSelected(True)

    def set_env(self, work):
        """Set environment to the given work file in this dcc.

        Apply $JOB to env.

        Args:
            work (CPWork): work file to apply
        """
        hou.putenv('JOB', work.job.path)

    def set_fps(self, fps):
        """Set frame rate.

        Args:
            fps (float): frame rate to apply
        """
        hou.setFps(fps)

    def set_range(self, start, end):
        """Set current frame range.

        Args:
            start (float): start frame
            end (float): end frame
        """
        hou.playbar.setFrameRange(start, end)

    def set_scene_data(self, key, val):
        """Store data within this scene.

        Args:
            key (str): name of data to store
            val (any): value of data to store
        """
        _key = f'pini_{key}'
        _type = type(val).__name__
        if _type not in ['int', 'float', 'str', 'list', 'bool']:
            raise RuntimeError(key, val, _type)
        _val = f'{_type}:{val}'
        _LOGGER.debug('SET SCENE DATA %s %s', _key, _val)
        hou.node("/").setUserData(_key, _val)

    def t_end(self, class_=float):
        """Get end frame.

        Args:
            class_ (class): override result type

        Returns:
            (float): end time
        """
        return class_(hou.playbar.frameRange()[1])

    def t_start(self, class_=float):
        """Get start frame.

        Args:
            class_ (class): override result type

        Returns:
            (float): start time
        """
        return class_(hou.playbar.frameRange()[0])

    def take_snapshot(self, file_):
        """Take snapshot of the current scene.

        Args:
            file_ (str): path to save image to
        """
        flipbook_frame(file_, force=True)

    def unsaved_changes(self):
        """Test whether there are unsaved changes in the current scene.

        Returns:
            (bool): unsaved changes
        """
        return hou.hipFile.hasUnsavedChanges()
