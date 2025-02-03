"""Tools for managing maya/pini interface."""

# pylint: disable=too-many-public-methods

import inspect
import logging

from maya import cmds

from pini.utils import single, wrap_fn, EMPTY, Path, abs_path

from maya_pini import ui, ref
from maya_pini.utils import (
    cur_file, load_scene, save_scene, render, to_clean, to_audio, blast_frame)

from .d_base import BaseDCC

_LOGGER = logging.getLogger(__name__)
_FPS_MAP = {
    "29.97df": 30,
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
    REF_EXTNS = ('ma', 'mb', 'abc', 'fbx', 'vdb', 'ass', 'usd', 'gz', 'rs')

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
        from pini.tools import release
        release.apply_deprecation('22/01/25', 'Use pipe_ref.create_abc_ref')

        from pini import pipe
        from pini.dcc import pipe_ref
        _LOGGER.debug('CREATE CACHE REF')

        # Determine abc mode
        _abc_mode = abc_mode
        if _abc_mode == 'Auto':
            _out = pipe.to_output(cache, catch=True)
            if 'arnold' in self.allowed_renderers() and _out.task == 'fx':
                _abc_mode = 'aiStandIn'
            else:
                _abc_mode = 'Reference'
        _LOGGER.debug(' - ABC MODE %s', _abc_mode)

        # Create reference
        if _abc_mode == 'Reference':
            _ref = self.create_ref(cache, namespace=namespace, force=force)
            _ref.attach_shaders(lookdev, mode=attach_mode)
        elif _abc_mode == 'aiStandIn':
            _ref = pipe_ref.create_ai_standin(path=cache, namespace=namespace)
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
        from maya_pini import open_maya as pom
        from .. import pipe_ref

        _LOGGER.debug('CREATE REF %s', namespace)

        _path = path
        if isinstance(_path, str):
            _path = Path(abs_path(_path))
        _LOGGER.debug(' - PATH %s', path)

        # Bring in reference
        if _path.extn == 'vdb':
            _ref = pipe_ref.create_ai_vol(
                _path, namespace=namespace, group=group)
        elif _path.extn in ('ass', 'usd', 'gz'):
            _ref = pipe_ref.create_ai_standin(
                path=_path, namespace=namespace, group=group)
        elif _path.extn in ('rs', ):
            _ref = pipe_ref.create_rs_pxy(
                _path, namespace=namespace, group=group)
        else:
            _pom_ref = pom.create_ref(_path, namespace=namespace, force=force)
            _ns = _pom_ref.namespace
            _ref = self.find_pipe_ref(_ns, catch=True)
            if _ref.top_node:
                pipe_ref.apply_grouping(
                    top_node=_ref.top_node, output=_ref.output, group=group)
            pipe_ref.lock_cams(_pom_ref)

        _LOGGER.debug(' - REF %s', _ref)

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
                _score = '_' if _base[-1].isdigit() else ''
                _ns = f':{_base}{_score}{_idx:02d}'
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
            from .. import export
            from pini import farm
            self._export_handlers = [
                export.CMayaBasicPublish(),
                export.CMayaModelPublish(),
                export.CMayaLookdevPublish(),
                export.CMayaLocalRender(),
                export.CMayaPlayblast(),
            ]
            if farm.IS_AVAILABLE:
                self._export_handlers.append(export.CMayaFarmRender())

    def _read_pipe_refs(self, selected=False):
        """Find references in the current scene.

        Args:
            selected (bool): return only selected refs

        Returns:
            (CPipeRef list): references
        """
        _LOGGER.debug('FIND PIPE REFS')
        from .. import pipe_ref
        return pipe_ref.find_pipe_refs(selected=selected)

    def _read_version(self):
        """Read maya version.

        Returns:
            (tuple): major/minor version
        """
        return (int(cmds.about(majorVersion=True)),
                int(cmds.about(minorVersion=True)), None)

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

    def set_env(self, work):
        """Set environment to the given work file in this dcc.

        Set arnold snapshots dir.

        Args:
            work (CPWork): work file to apply
        """
        if cmds.pluginInfo('mtoa', query=True, loaded=True):
            _dir = work.work_dir.to_subdir('workspace/snapshots')
            _dir.mkdir()
            cmds.arnoldRenderView(opt=("Snapshots Folder", _dir.path))

    def set_fps(self, fps):
        """Set frame rate.

        Args:
            fps (float): frame rate to apply
        """
        for _name, _fps in _FPS_MAP.items():
            if _fps == fps:
                break
        else:
            _name = f'{fps}fps'
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
            _step = int(cmds.getAttr('defaultRenderGlobals.byFrameStep'))
            return list(range(_start, _end+1, _step))
        return super().t_frames()

    def t_start(self, class_=float):
        """Get timeline start frame.

        Args:
            class_ (class): override result type

        Returns:
            (float): start time
        """
        return class_(cmds.playbackOptions(query=True, minTime=True))

    def t_end(self, class_=float):
        """Get timeline end frame.

        Args:
            class_ (class): override result type

        Returns:
            (float): end time
        """
        return class_(cmds.playbackOptions(query=True, maxTime=True))

    def take_snapshot(self, file_):
        """Take snapshot of the current scene.

        Args:
            file_ (str): path to save image to
        """
        blast_frame(file_, force=True)

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
