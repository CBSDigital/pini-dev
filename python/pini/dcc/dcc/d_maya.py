"""Tools for managing maya/pini interface."""

# pylint: disable=too-many-public-methods

import inspect
import logging

from maya import cmds

from pini.utils import single, wrap_fn, Seq, EMPTY
from maya_pini import ui, ref
from maya_pini.utils import (
    cur_file, load_scene, save_scene, render, to_clean, to_audio)

from .d_base import BaseDCC

_LOGGER = logging.getLogger(__name__)
_FPS_MAP = {
    "film": 24.0,
    "pal": 25.0,
    "palf": 50.0,
    "ntsc": 30.0,
    "ntscf": 60.0,
}


class MayaDCC(BaseDCC):
    """Manages interactions with maya."""

    NAME = 'maya'
    DEFAULT_EXTN = 'ma'
    DEFAULT_ALLOWED_RENDERERS = 'arnold'
    VALID_EXTNS = ('ma', 'mb', 'abc', 'fbx')
    REF_EXTNS = ('ma', 'mb', 'abc', 'fbx', 'vdb', 'ass', 'usd', 'gz')

    def add_menu_divider(self, parent, name):
        """Add menu divider to maya ui.

        Args:
            parent (str): parent menu
            name (str): uid for divider
        """
        _parent = ui.obtain_menu(parent)
        if cmds.menuItem(name, query=True, exists=True):
            cmds.deleteUI(name)
        cmds.menuItem(name, parent=_parent, divider=True)

    def add_menu_item(self, parent, command, image, label, name):
        """Add menu item to maya ui.

        Args:
            parent (str): parent menu
            command (func): command to call on item click
            image (str): path to item icon
            label (str): label for item
            name (str): uid for item
        """
        if cmds.menuItem(name, query=True, exists=True):
            cmds.deleteUI(name)

        _parent = ui.obtain_menu(parent)
        _cmd = command
        if inspect.isfunction(_cmd):  # Ignore args from maya
            _cmd = wrap_fn(_cmd)
        cmds.menuItem(
            name, parent=_parent, command=_cmd, image=image, label=label)

    def batch_mode(self):
        """Test whether maya is running in batch mode.

        Returns:
            (bool): batch mode
        """
        return cmds.about(batch=True)

    def clear_terminal(self):
        """Clear script editor."""
        ui.clear_script_editor()

    def create_cache_ref(
            self, cache, namespace, lookdev=None, attach_mode='Reference',
            build_plates=True, abc_mode='Auto', force=False):
        """Create a reference of the given path in the current scene.

        Args:
            cache (File): path to cache (eg. abc) to reference
            namespace (str): namespace for reference
            lookdev (CPOutput): attach this lookdev publish
            attach_mode (str): how to attach shaders (Reference/Import)
            build_plates (bool): rebuild camera plates if applicable
            abc_mode (str): how to reference abcs (Reference/aiStandIn)
            force (bool): replace existing without confirmation
        """
        from pini import pipe
        _LOGGER.debug('CREATE CACHE REF')

        # Determine abc mode
        _abc_mode = abc_mode
        if _abc_mode == 'Auto':
            _out = pipe.to_output(cache, catch=True)
            _abc_mode = 'aiStandIn' if _out.task == 'fx' else 'Reference'
        _LOGGER.debug(' - ABC MODE %s', _abc_mode)

        # Create reference
        if _abc_mode == 'Reference':
            _ref = self.create_ref(cache, namespace=namespace, force=force)
            _ref.attach_lookdev(lookdev=lookdev, mode=attach_mode)
        elif _abc_mode == 'aiStandIn':
            _ref = self._create_aistandin_ref(path=cache, namespace=namespace)
        else:
            raise ValueError(abc_mode)
        _LOGGER.debug(' - REF %s', _ref)

        # Apply cam setting
        _out = _ref.output
        if (
                build_plates and
                _abc_mode == 'Reference' and
                _out.metadata.get('type') == 'CPCacheableCam'):
            _ref.build_plates()

        return _ref

    def create_ref(self, path, namespace, force=False, group=EMPTY):
        """Create reference instance of the given path.

        Args:
            path (File): file to reference
            namespace (str): namespace reference
            force (bool): replace existing without confirmation
            group (str): override group (otherwise references are automatically
                put in a group based on the asset/output type)

        Returns:
            (CMayaPipeRef): reference
        """
        from pini import pipe
        from maya_pini import open_maya as pom
        from ..pipe_ref import pr_maya

        _LOGGER.debug('CREATE REF %s', namespace)
        _LOGGER.debug(' - PATH %s', path)

        # Bring in reference
        if path.extn == 'vdb':
            assert isinstance(path, Seq)
            cmds.loadPlugin('mtoa', quiet=True)
            _seq = path
            _shp = pom.CMDS.createNode('aiVolume', name=namespace+'Shape')
            _path = _seq[_seq.frames[0]]
            _shp.plug['filename'].set_val(_path)
            _tfm = _shp.to_parent().rename(namespace)
            _ns = str(_tfm)
            _shp.plug['useFrameExtension'].set_val(True)
            _ref = pr_maya.CMayaVdb(_tfm, path=_seq.path)
            _top_node = _ref.node

        elif path.extn in ('ass', 'usd', 'gz'):
            _ref = self._create_aistandin_ref(
                path=path, namespace=namespace)
            _top_node = _ref.node

        else:
            _ref = ref.create_ref(path, namespace=namespace, force=force)
            _ns = _ref.namespace
            _ref = self.find_pipe_ref(_ns)
            _top_node = _ref.ref.find_top_node(catch=True)
        _LOGGER.debug(' - REF %s', _ref)

        # Organise into group
        _out = _ref.output
        _LOGGER.debug(' - OUT %s', _out)
        _grp = group
        if _out and _grp is EMPTY:
            if _out.entity.name == 'camera':
                _grp = 'CAM'
            elif pipe.map_task(_out.task) == 'LOOKDEV':
                _grp = 'LOOKDEV'
            elif _out.asset_type:
                _grp = _ref.output.asset_type.upper()
            elif _out.output_type:
                _grp = _ref.output.output_type.upper()
            else:
                _grp = None
        _LOGGER.debug(' - GROUP %s -> %s', group, _grp)
        if _grp and _top_node:
            _LOGGER.debug(' - ADD TO GROUP %s %s', _top_node, _grp)
            _grp = _top_node.add_to_grp(_grp)
            _grp.solidify()

        return _ref

    def _create_aistandin_ref(self, path, namespace):
        """Create aiStandIn reference from the given path.

        Args:
            path (File|Seq): path to apply
            namespace (str): namespace to use

        Returns:
            (CMayaAiStandIn): reference
        """
        from maya_pini import open_maya as pom
        from ..pipe_ref import pr_maya

        cmds.loadPlugin('mtoa', quiet=True)
        _shp = pom.CMDS.createNode('aiStandIn', name=namespace+'Shape')
        _is_seq = isinstance(path, Seq)
        if _is_seq:
            _path = path[path.frames[0]]
        else:
            _path = path.path
        _shp.plug['dso'].set_val(_path)
        _tfm = _shp.to_parent().rename(namespace)
        _ns = str(_tfm)
        _shp.plug['useFrameExtension'].set_val(_is_seq or path.extn == 'abc')
        _ref = pr_maya.CMayaAiStandIn(_tfm, path=path)

        # Force expression update - still doesn't work for more than
        # one standin node
        if _is_seq:
            ui.raise_attribute_editor()
            cmds.refresh()

        return _ref

    def cur_file(self):
        """Get path to current scene.

        Returns:
            (str): path to current scene
        """
        return cur_file()

    def cur_frame(self):
        """Obtain current frame.

        Returns:
            (int): current frame
        """
        return int(cmds.currentTime(query=True))

    def error(self, error):
        """Raise a maya error.

        Args:
            error (str): error message
        """
        cmds.error(error)

    def _force_load(self, file_):
        """Force load the given scene.

        Args:
            file_ (str): scene to load
        """
        load_scene(file_, force=True)

    def _force_new_scene(self):
        """Force new scene."""
        cmds.file(new=True, force=True)

        # Delete unwanted node (from redshift callbacks?)
        _unknown = cmds.ls(type='unknown')
        if _unknown:
            cmds.delete(_unknown)

        cmds.file(modified=False)

    def _force_save(self, file_=None):
        """Force save the current scene without overwrite confirmation.

        Args:
            file_ (str): path to save scene to
        """
        save_scene(file_=file_, force=True)

    def get_audio(self, start=None):
        """Read scene audio.

        Args:
            start (float): override start frame

        Returns:
            (tuple): audio / offset from start frame (in secs)
        """
        return to_audio(start=start)

    def get_fps(self):
        """Get current frame rate for this dcc.

        Returns:
            (float): frame rate
        """
        _unit = cmds.currentUnit(query=True, time=True)
        if _unit.endswith('fps'):
            return float(_unit[:-3])
        if _unit not in _FPS_MAP:
            _LOGGER.info('WARNING - UNHANDLED FPS %s', _unit)
        return _FPS_MAP.get(_unit)

    def get_main_window_ptr(self):
        """Get main window pointer to main maya window.

        Returns:
            (QDialog): main window pointer
        """
        return ui.get_main_window_ptr()

    def get_next_namespace(self, base, ignore=(), mode='asset'):
        """Get next available namespace.

        Adds an 2-padded integer suffix to the given base.

        Args:
            base (str): namespace base
            ignore (str list): list of namespaces to ignore
            mode (str): how to allocate next namespace
                asset - always add a 2-padded index suffix
                cache - try to maintain namespace but otherwise
                    add an underscore and then 2-padded index suffix

        Returns:
            (str): next unused namespace of the given base
        """
        _LOGGER.debug('GET NEXT NAMESPACE base=%s mode=%s', base, mode)
        _base = base.replace('-', '_')
        _refs = ref.find_refs(unloaded=True)
        _ref_nss = [_ref.namespace for _ref in _refs]

        # Add 2-padded index suffix (eg. deadHorse -> deadHorse01)
        if mode == 'asset':
            for _idx in range(1, 1000):
                _ns = ':{}{}{:02d}'.format(
                    _base, '_' if _base[-1].isdigit() else '', _idx)
                _LOGGER.debug(' - TESTING %s', _ns)
                if (
                        not cmds.namespace(exists=_ns) and
                        not cmds.objExists(_ns) and
                        _ns.strip(':') not in _ref_nss and
                        _ns.strip(':') not in ignore):
                    return _ns
            raise RuntimeError

        # Cache mode (eg. deadHorse01) - should maintain namespace if possible
        # otherwise added _<idx> suffix (eg. deadHorse01_01)
        if mode == 'cache':
            _LOGGER.debug(' - TESTING %s', _base)
            if (
                    not cmds.namespace(exists=_base) and
                    not cmds.objExists(_base) and
                    _base.strip(':') not in _ref_nss and
                    _base.strip(':') not in ignore):
                return _base
            return self.get_next_namespace(
                _base+'_', mode='asset', ignore=ignore)

        raise ValueError(mode)

    def get_res(self):
        """Get current image resolution.

        Return:
            (tuple): width/height
        """
        return (cmds.getAttr("defaultResolution.width"),
                cmds.getAttr("defaultResolution.height"))

    def get_scene_data(self, key):
        """Retrieve data stored with this scene.

        Args:
            key (str): data to obtain

        Returns:
            (any): data which has been stored in the scene
        """
        _data = single(cmds.fileInfo(key, query=True), catch=True)
        if not _data:
            return None
        _type_key = '_TYPE_'+key
        _type = single(cmds.fileInfo(_type_key, query=True), catch=True)
        if _type == 'bool':
            _data = {'True': True, 'False': False}[_data]
        elif _type == 'float':
            _data = float(_data)
        elif _type == 'int':
            _data = int(_data)
        elif _type in ['str', 'unicode']:
            pass
        else:
            raise NotImplementedError(_type)
        return _data

    def _init_export_handlers(self):
        """Initiate export handlers."""
        if self._export_handlers is None:
            from .. import export_handler
            from pini import farm
            self._export_handlers = [
                export_handler.CMayaBasicPublish(),
                export_handler.CMayaModelPublish(),
                export_handler.CMayaLookdevPublish(),
                export_handler.CMayaLocalRender(),
                export_handler.CMayaPlayblast(),
            ]
            if farm.IS_AVAILABLE:
                self._export_handlers.append(export_handler.CMayaFarmRender())

    def _read_pipe_refs(self, selected=False):
        """Find references in the current scene.

        Args:
            selected (bool): return only selected refs

        Returns:
            (CPipeRef list): references
        """
        _LOGGER.debug('FIND PIPE REFS')
        from ..pipe_ref import pr_maya  # pylint: disable=no-name-in-module
        return pr_maya.find_pipe_refs(selected=selected)

    def refresh(self):
        """Refresh the ui."""
        cmds.refresh()

    def render(self, seq):
        """Render the current scene.

        Args:
            seq (Seq): output image sequence
        """
        render(seq)

    def select_node(self, node):
        """Select the given node.

        Args:
            node (str): node to select
        """
        cmds.select(node, noExpand=True)

    def set_fps(self, fps):
        """Set frame rate.

        Args:
            fps (float): frame rate to apply
        """
        for _name, _fps in _FPS_MAP.items():
            if _fps == fps:
                break
        else:
            _name = '{}fps'.format(fps)
        cmds.currentUnit(time=_name)

    def set_range(self, start, end):
        """Set current frame range.

        Args:
            start (float): start frame
            end (float): end frame
        """
        cmds.playbackOptions(
            edit=True, minTime=start, maxTime=end,
            animationStartTime=start, animationEndTime=end)

    def set_res(self, width, height):
        """Set current image resolution.

        Args:
            width (int): image width
            height (int): image height
        """
        cmds.setAttr("defaultResolution.width", width)
        cmds.setAttr("defaultResolution.height", height)
        cmds.setAttr("defaultResolution.deviceAspectRatio", 1.0*width/height)

    def set_scene_data(self, key, val):
        """Store data within this scene.

        Args:
            key (str): name of data to store
            val (any): value of data to store
        """
        _type = type(val).__name__
        _type_key = '_TYPE_'+key
        _LOGGER.debug('SET SCENE DATA %s %s (%s/%s)',
                      key, val, _type, _type_key)
        cmds.fileInfo(key, val)
        cmds.fileInfo(_type_key, _type)

    def t_frame(self, class_=float):
        """Obtain current frame.

        Args:
            class_ (class): override type of data to return (eg. int)

        Returns:
            (float): current frame
        """
        return class_(cmds.currentTime(query=True))

    def t_frames(self, mode='Timeline'):
        """Get list of timeline frames.

        Args:
            mode (str): where to read range from

        Returns:
            (int list): all frames in timeline
        """
        if mode == 'RenderGlobals':
            _start = int(cmds.getAttr('defaultRenderGlobals.startFrame'))
            _end = int(cmds.getAttr('defaultRenderGlobals.endFrame'))
            return list(range(_start, _end+1))
        return super(MayaDCC, self).t_frames()

    def t_start(self, class_=float):
        """Get start frame.

        Args:
            class_ (class): override result type

        Returns:
            (float): start time
        """
        return class_(cmds.playbackOptions(query=True, minTime=True))

    def t_end(self, class_=float):
        """Get end frame.

        Args:
            class_ (class): override result type

        Returns:
            (float): end time
        """
        return class_(cmds.playbackOptions(query=True, maxTime=True))

    def _read_version(self):
        """Read maya version.

        Returns:
            (tuple): major/minor version
        """
        return (int(cmds.about(majorVersion=True)),
                int(cmds.about(minorVersion=True)), None)

    def unsaved_changes(self):
        """Test whether there are currently unsaved changes.

        Returns:
            (bool): unsaved changes
        """
        _modified = cmds.file(query=True, modified=True)
        if not _modified:
            return False

        _changed_nodes = {to_clean(_node) for _node in cmds.ls(modified=True)}
        _ignorable = {
            'defaultArnoldDisplayDriver',
            'defaultArnoldDriver',
            'defaultArnoldFilter',
            'defaultArnoldRenderOptions',

            'defaultColorMgtGlobals',
            'defaultRedshiftPostEffects',
            'defaultRenderGlobals',
            'defaultResolution',

            'frontShape',
            'hardwareRenderingGlobals',
            'hyperShadePrimaryNodeEditorSavedTabsInfo',
            'perspShape',
            'redshiftOptions',
            'renderSetup',
            'sideShape',
            'time1',
            'topShape',
        }
        _relevant_changes = _changed_nodes - _ignorable
        _LOGGER.debug(' - RELEVANT CHANGES %s', sorted(_relevant_changes))
        return bool(_relevant_changes)
