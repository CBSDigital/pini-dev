"""Tools for managing the houdini/pini interface."""

# pylint: disable=abstract-method

import inspect
import logging

import hou
import six

from pini.utils import File, abs_path, check_heart, lprint

from .d_base import BaseDCC

_LOGGER = logging.getLogger(__name__)

if not hou.__file__:
    raise ImportError('Bad hou module')


class HouDCC(BaseDCC):
    """Manages interactions with houdini."""

    NAME = 'hou'
    if hou.licenseCategory() == hou.licenseCategoryType.Indie:
        DEFAULT_EXTN = 'hiplc'
    else:
        DEFAULT_EXTN = 'hip'
    VALID_EXTNS = (DEFAULT_EXTN, )
    REF_EXTNS = ('abc', )

    def add_menu_divider(self, parent, name, verbose=0):
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

    def add_menu_item(self, parent, command, image, label, name, verbose=0):
        """Print xml to declare a menu item in MainMenuCommon.xml file.

        Args:
            parent (str): parent menu
            command (func): command to call on item click
            image (str): path to item icon
            label (str): label for item
            name (str): uid for item
            verbose (int): print process data
        """
        if isinstance(command, six.string_types):
            _cmd = command
        else:
            _mod = inspect.getmodule(command)
            _cmd = 'import {} as _tmp\n_tmp.{}()'.format(
                _mod.__name__, command.__name__)

        _LOGGER.debug('ADD MENU ITEM %s', name)
        _xml = '\n'.join([
            '      <!--Add {label}-->',
            '      <scriptItem id="{name}">',
            '        <label>{label}</label>',
            '          <scriptCode><![CDATA[',
            '{command}',
            ']]>',
            '         </scriptCode>',
            '      </scriptItem>',
            '',
        ]).format(command=_cmd, name=name, label=label)
        lprint(_xml, verbose=verbose)

        return _xml

    def batch_mode(self):
        """Check whether houdini is running in batch mode.

        Returns:
            (bool): batch mode
        """
        return not hou.isUIAvailable()

    def create_ref(self, path, namespace, force=False):
        """Create a reference of the given path in the current scene.

        Args:
            path (File): path to reference
            namespace (str): namespace for reference
            force (bool): replace existing without confirmation
        """
        from pini import pipe
        _out = pipe.to_output(path)
        if _out.extn == 'abc' and _out.metadata.get('type') == 'CPCacheableCam':
            _root = hou.node('/obj')
            _cam = _root.createNode('alembicarchive', namespace)
            _cam.parm('fileName').set(_out.path)
            _cam.parm('buildHierarchy').pressButton()
            _ref = self.find_pipe_ref(namespace)
            _ref.update_res()
        elif _out.extn == 'abc':
            _root = hou.node('/obj')
            _geo = _root.createNode('geo', node_name=namespace)
            _abc = _geo.createNode('alembic')
            _abc.parm('fileName').set(_out.path)
            _out = _geo.createNode('null', 'OUT')
            _out.setInput(0, _abc)
            _out.setRenderFlag(True)
            _out.setDisplayFlag(True)
            _out.setPosition((0, -1))
            _ref = self.find_pipe_ref(namespace)
        else:
            raise ValueError(_out)
        _root.moveToGoodPosition()

        return _ref

    def cur_file(self):
        """Get path to current scene.

        Returns:
            (str): scene path
        """
        _path = abs_path(hou.hipFile.name())
        _file = File(_path)
        if _file.filename == 'untitled.hip' and not _file.exists():
            return None
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

    def get_next_namespace(self, base, ignore=(), mode='asset'):
        """Get next available namespace.

        Args:
            base (str): namespace base
            ignore (str list): list of namespaces to ignore
            mode (str): how to allocate next namespace
        """
        _name = 'import_'+base
        _idx = 1
        while hou.node('/obj/'+_name) or _name in ignore:
            check_heart()
            _name = 'import_{}_{:02d}'.format(base, _idx)
            _idx += 1
        return _name

    def get_scene_data(self, key):
        """Retrieve data stored with this scene.

        Args:
            key (str): data to obtain
        """
        _key = 'pini_{}'.format(key)
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
            else:
                raise ValueError(_type)
        return _val

    def _init_export_handlers(self):
        """Initiate export handlers list."""
        if self._export_handlers is None:
            from .. import export_handler
            _LOGGER.debug('INIT EXPORT HANDLERS')
            self._export_handlers = [
                export_handler.CHouFlipbook(),
            ]

    def _read_pipe_refs(self, selected=False):
        """Find reference in the current dcc.

        Args:
            selected (bool): return only selected refs

        Returns:
            (CPipeRef list): list of references
        """
        _LOGGER.debug('READ PIPE REFS')
        from ..pipe_ref import pr_hou
        _refs = []
        for _cat, _type, _class in [
                (hou.sopNodeTypeCategory, 'alembic',
                 pr_hou.CHouAbcRef),
                (hou.objNodeTypeCategory, 'alembicarchive',
                 pr_hou.CHouAbcCamRef),
        ]:
            for _node in _cat().nodeType(_type).instances():

                _LOGGER.debug('CHECKING NODE %s', [_node])

                # Check if node references pipeline output
                try:
                    _ref = _class(_node)
                except ValueError:
                    continue

                # Check if root is selected
                if selected:
                    _root = _node
                    while _root.parent() != hou.node('/obj'):
                        check_heart()
                        _root = _root.parent()
                    _LOGGER.debug(' - ROOT %s', _root)
                    if _root not in hou.selectedNodes():
                        _LOGGER.debug(' - NOT SELECTED %s', hou.selectedNodes())
                        continue

                _refs.append(_ref)
        return _refs

    def select_node(self, node):
        """Select the given node.

        Args:
            node (Node): node to select
        """
        node.setSelected(True)

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
        _key = 'pini_{}'.format(key)
        _type = type(val).__name__
        assert _type in ['int', 'float', 'str']
        _val = '{}:{}'.format(_type, val)
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

    def _read_version(self):
        """Read houdini version.

        Returns:
            (int tuple): houdini version
        """
        return hou.applicationVersion()

    def unsaved_changes(self):
        """Test whether there are unsaved changes in the current scene.

        Returns:
            (bool): unsaved changes
        """
        return hou.hipFile.hasUnsavedChanges()
