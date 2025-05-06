"""Tools for managing the base dcc object."""

# pylint: disable=too-many-public-methods

import copy
import logging
import os
import sys

from pini import icons
from pini.utils import File, single, passes_filter, is_pascal

_LOGGER = logging.getLogger(__name__)


class BaseDCC:
    """Base class managing interaction with any dcc."""

    DEFAULT_EXTN = None
    DEFAULT_ALLOWED_RENDERERS = ''
    HELPER_AVAILABLE = True
    NAME = None
    REF_EXTNS = ()
    VALID_EXTNS = ()

    _export_handlers = None

    def add_menu_divider(self, parent, name):
        """Add menu divider to maya ui.

        Args:
            parent (str): parent menu
            name (str): uid for divider
        """

    def add_menu_item(self, parent, command, image, label, name):
        """Add menu item to maya ui.

        Args:
            parent (str): parent menu
            command (func): command to call on item click
            image (str): path to item icon
            label (str): label for item
            name (str): uid for item
        """

    def add_export_handler(self, handler):
        """Add an export handler to the current list.

        This will replace any export handlers with the same action - ie. only
        one export handler for each action can exist.

        Args:
            handler (CRenderHandler): render handler to add.
        """
        _LOGGER.debug('ADD RENDER HANDLER %s', handler)
        self._check_export_handlers()

        # Flush existing
        for _exp in copy.copy(self._export_handlers):
            if _exp.ACTION == handler.ACTION:
                self._export_handlers.remove(_exp)

        self._export_handlers.insert(0, handler)
        _LOGGER.debug(' - RENDER HANDLERS %s', self._export_handlers)

    def allowed_renderers(self):
        """List allowed renderers for the current dcc pipeline.

        Returns:
            (str list): allowed renderers
        """
        _val = os.environ.get(
            'PINI_ALLOWED_RENDERERS', self.DEFAULT_ALLOWED_RENDERERS)
        return _val.split(',')

    def batch_mode(self):
        """Test whether we are in a dcc running in batch mode.

        Returns:
            (bool): batch mode
        """
        return False

    def can_reference_output(self, output):
        """Test whether the dcc can reference the given output.

        Args:
            output (CPOutput): output to reference

        Returns:
            (bool): whether output can be referenced
        """
        return output.extn in self.REF_EXTNS

    def clear_terminal(self):
        """Clear current terminal or script editor (if applicable)."""

    def create_cache_ref(  # pylint: disable=unused-argument
            self, cache, namespace, lookdev=None, attach_mode='Reference',
            build_plates=True, abc_mode='Auto', force=False):
        """Create a reference of the given path in the current scene.

        Args:
            cache (str): path to cache (eg. abc) to reference
            namespace (str): namespace for reference
            lookdev (CPOutput): attach this lookdev publish
            attach_mode (str): how to attach shaders (Reference/Import)
            build_plates (bool): rebuild camera plates if applicable
            abc_mode (str): how to reference abcs (Reference/aiStandIn)
            force (bool): replace existing without confirmation
        """
        from pini.tools import release
        release.apply_deprecation('22/01/25', 'Use pipe_ref.create_abc_ref')
        raise NotImplementedError

    def create_ref(self, path, namespace, force=False):
        """Create a reference of the given path in the current scene.

        Args:
            path (File): path to reference
            namespace (str): namespace for reference
            force (bool): replace existing without confirmation
        """
        raise NotImplementedError

    def cur_file(self):
        """Get path to current file.

        Returns:
            (str|None): current file (if any)
        """
        return None

    def cur_frame(self):
        """Obtain current frame.

        Returns:
            (int): current frame
        """
        raise NotImplementedError

    def error(self, error):
        """Raise an error.

        By default this will just show an error dialog containing the
        specified message, but it can be overriden in the dcc.

        Args:
            error (str): error message
        """
        from pini import qt
        qt.notify(error, title='Error', icon=icons.find('Hot Face'))
        raise RuntimeError(error)

    def find_pipe_ref(
            self, namespace=None, selected=False, extn=None, filter_=None,
            task=None, catch=False):
        """Find a reference in the current scene.

        Args:
            namespace (str): reference namespace to match
            selected (bool): return only selected refs
            extn (str): filter by extension
            filter_ (str): filter by namespace
            task (str): filter by task
            catch (bool): no error if no matching ref found

        Returns:
            (CPipeRef): matching ref
        """
        _refs = self.find_pipe_refs(
            extn=extn, namespace=namespace, selected=selected, filter_=filter_,
            task=task)
        _zero_error = _multi_error = _error = None
        if selected:
            _zero_error = 'No references selected'
            _multi_error = 'Multiple references selected'
        else:
            _error = f'Failed to match reference {namespace}'
        return single(
            _refs, catch=catch, error=_error, multi_error=_multi_error,
            zero_error=_zero_error)

    def find_pipe_refs(
            self, filter_=None, selected=False, extn=None,
            task=None, namespace=None, head=None):
        """Find reference in the current dcc.

        Args:
            filter_ (str): filter by namespace
            selected (bool): return only selected refs
            extn (str): filter by filter extension
            task (str): filter by task
            namespace (str): match namespace
            head (str): filter by namespace head/prefix

        Returns:
            (CPipeRef list): list of references
        """
        from pini import pipe
        _refs = []
        for _ref in self._read_pipe_refs(selected=selected):
            if filter_ and not passes_filter(_ref.namespace, filter_):
                continue
            if extn and _ref.extn != extn:
                continue
            if namespace and _ref.namespace != namespace:
                continue
            if head and not _ref.namespace.startswith(head):
                continue
            if task and task not in (
                    _ref.output.task, pipe.map_task(_ref.output.task)):
                continue
            _refs.append(_ref)
        return sorted(_refs)

    def _build_export_handlers(self):
        """Initiate export handlers list."""
        from .. import export
        from pini import pipe
        _LOGGER.debug('INIT EXPORT HANDLERS')
        _handlers = []
        if pipe.SHOTGRID_AVAILABLE:
            _submit = export.CBasicSubmitter()
            _handlers.append(_submit)
        return _handlers

    def _check_export_handlers(self):
        """Check export handlers have been set up."""
        if self._export_handlers is None:
            self._export_handlers = self._build_export_handlers()

    def find_export_handler(
            self, match=None, type_=None, filter_=None, profile=None,
            catch=False):
        """Find an installed export handler.

        Args:
            match (str): token to identify export handler
                (eg. name/action/type)
            type_ (str): filter by export type (eg. Publish/Render)
            filter_ (str): filter by exporter name
            profile (str): apply profile filter (eg. shot/asset)
            catch (bool): no error if no matching handler found

        Returns:
            (CExportHandler): matching export handler
        """
        _handlers = self.find_export_handlers(
            type_=type_, filter_=filter_, profile=profile)
        if len(_handlers) == 1:
            return single(_handlers)

        # Try type match
        _action_match = single(
            [_handler for _handler in _handlers if _handler.TYPE == match],
            catch=True)
        if _action_match:
            return _action_match

        # Try type match
        _type_match = single(
            [_handler for _handler in _handlers
             if type(_handler).__name__ == match],
            catch=True)
        if _type_match:
            return _type_match

        # Try exact name match
        _name_match = single(
            [_handler for _handler in _handlers if _handler.NAME == match],
            catch=True)
        if _name_match:
            return _name_match

        # Try type filter match
        _filter_match = single(
            [_handler for _handler in _handlers
             if passes_filter(type(_handler).__name__, match)],
            catch=True)
        if _filter_match:
            return _filter_match

        if catch:
            return None
        raise ValueError(_handlers)

    def find_export_handlers(self, type_=None, filter_=None, profile=None):
        """Find render handlers for this dcc.

        Args:
            type_ (str): filter by exporter type (eg. Publish/Render)
            filter_ (str): filter by exporter name
            profile (str): apply profile filter (eg. shot/asset)

        Returns:
            (CExportHandler list): installed export handlers
        """
        _LOGGER.debug('FIND EXPORT HANDLERS %s', self._export_handlers)
        self._check_export_handlers()
        if not (is_pascal(type_) or type_ is None):
            raise ValueError(type_)

        # Build list
        _handlers = []
        for _handler in self._export_handlers:
            if type_ and _handler.TYPE != type_:
                _LOGGER.debug(
                    ' - TYPE REJECTED %s %s %s', _handler,
                    _handler.TYPE, type_)
                continue
            if profile and not passes_filter(profile, _handler.profile_filter):
                _LOGGER.debug(
                    ' - PROFILE REJECTED %s %s %s', _handler,
                    _handler.profile_filter, profile)
                continue
            if not passes_filter(_handler.NAME, filter_):
                continue
            _handlers.append(_handler)

        return _handlers

    def _force_load(self, file_):
        """Force load the given scene.

        Args:
            file_ (str): scene to load
        """
        raise NotImplementedError

    def _force_new_scene(self):
        """Force new scene in current dcc."""
        raise NotImplementedError

    def _force_save(self, file_=None):
        """Force save the current scene without overwrite confirmation.

        Args:
            file_ (str): path to save scene to
        """
        raise NotImplementedError

    def get_audio(self, start=None):
        """Read scene audio.

        Args:
            start (float): override start frame

        Returns:
            (tuple): audio / offset from start frame (in secs)
        """
        raise NotImplementedError

    def get_fps(self):
        """Get current frame rate for this dcc.

        Returns:
            (float): frame rate
        """
        return None

    def get_main_window_ptr(self):
        """None if no dcc."""

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
        raise NotImplementedError

    def get_res(self):
        """Get current image resolution."""
        raise NotImplementedError

    def get_scene_data(self, key):
        """Retrieve data stored with this scene.

        Args:
            key (str): data to obtain
        """
        raise NotImplementedError

    def handle_unsaved_changes(self, save=True, parent=None):
        """Warn on unsaved changes.

        Args:
            save (bool): offer to save current scene (if available)
            parent (QDialog): parent dialog
        """
        from pini import qt

        if not self.unsaved_changes():
            return

        # Handle no file set (either lose changes or cancel)
        _file = self.cur_file()  # pylint: disable=assignment-from-none
        if not save or not _file:
            qt.ok_cancel(
                'Lose unsaved changes in current scene?', parent=parent,
                title='Unsaved changes')
            return

        # Offer to save unsaved changes
        _msg = f'Lose unsaved changes in the current scene?\n\n{_file}'
        _icon = icons.find('Tiger Face')
        _result = qt.raise_dialog(
            msg=_msg, buttons=('Save', "Don't Save", 'Cancel'),
            title='Save changes', icon=_icon, parent=parent)
        if _result == 'Save':
            self._force_save()

    def load(self, file_, parent=None, force=False, lazy=False):
        """Load scene.

        Args:
            file_ (str): file to load
            parent (QDialog): parent dialog for warnings
            force (bool): load scene without unsaved changes warnings
            lazy (bool): don't load if file is already open
        """
        _file = File(file_)
        if _file.extn.lower() not in self.VALID_EXTNS:
            raise RuntimeError('Invalid file ' + _file.path)
        if lazy and _file.path == self.cur_file():
            _LOGGER.info('Lazy load - scene currently open')
            return
        if not _file.exists():
            raise OSError('File not found ' + _file.path)
        if not force:
            _save = _file.path != self.cur_file()
            _LOGGER.debug('HANDLE UNSAVED CHANGES save=%d', _save)
            self.handle_unsaved_changes(parent=parent, save=_save)
        self._force_load(_file.path)

    def new_scene(self, force=False, parent=None):
        """Create new scene.

        Args:
            force (bool): new scene without warning dialogs
            parent (QDialog): parent dialog for confirmations
        """
        if not force:
            self.handle_unsaved_changes(parent=parent)
        self._force_new_scene()

    def _read_pipe_refs(self, selected=True):
        """Read pipeline references from the current scene.

        Args:
            selected (bool): filter by selected

        Returns:
            (CPipeRef list): scene references
        """
        del selected  # For linter
        return []

    def _read_version(self):
        """Read application version tuple.

        If no patch is available, patch is returned as None.

        Returns:
            (tuple): major/minor/patch
        """
        return sys.version_info.major, sys.version_info.minor, 0

    def refresh(self):
        """Refresh the ui."""

    def remove_export_handler(self, name):
        """Remove an export handler.

        Args:
            name (str): name of export handler to remove
        """
        _handler = self.find_export_handler(name)
        self._export_handlers.remove(_handler)

    def render(self, seq):
        """Render the current scene.

        Args:
            seq (Seq): image sequence to render to
        """
        raise NotImplementedError

    def save(self, file_=None, force=False, parent=None):
        """Save scene.

        Args:
            file_ (str): save path
            force (bool): overwrite existing without warning dialog
            parent (QDialog): parent dialog for confirmations
        """
        if file_:
            _file = File(file_)
            _file.test_dir()
            if not force and _file.exists() and _file != self.cur_file():
                from pini import qt
                qt.ok_cancel(
                    f'Overwrite existing file?\n\n{_file.path}',
                    parent=parent)
            self._force_save(file_=_file)
        else:
            self._force_save()

    def select_node(self, node):
        """Select the given node.

        Args:
            node (any): node to select
        """
        raise NotImplementedError

    def set_env(self, work):
        """Set environment to the given work file in this dcc.

        Args:
            work (CPWork): work file to apply
        """

    def set_fps(self, fps):
        """Set frame rate.

        Args:
            fps (float): frame rate to apply
        """
        raise NotImplementedError

    def set_range(self, start, end):
        """Set current frame range.

        Args:
            start (float): start frame
            end (float): end frame
        """
        raise NotImplementedError

    def set_res(self, width, height):  # pylint: disable=unused-argument
        """Set current image resolution.

        Args:
            width (int): image width
            height (int): image height
        """
        _LOGGER.warning('SET RES NOT IMPLEMENTED %s', self.NAME)

    def set_scene_data(self, key, val):
        """Store data within this scene.

        Args:
            key (str): name of data to store
            val (any): value of data to store
        """
        raise NotImplementedError

    def t_dur(self, class_=float):
        """Obtain timeline duration in frames.

        This is the end minus the start plus one - eg. 1001 to 1002
        counts as 2 frames.

        Args:
            class_ (class): override result type

        Returns:
            (float): timeline duration
        """
        return self.t_end(class_=class_) - self.t_start(class_=class_) + 1

    def t_end(self, class_=float):
        """Get end frame.

        Args:
            class_ (class): override result type

        Returns:
            (float): end time
        """
        raise NotImplementedError

    def t_frame(self, class_=float):
        """Obtain current frame.

        Args:
            class_ (class): override type of data to return (eg. int)

        Returns:
            (float): current frame
        """
        raise NotImplementedError

    def t_frames(self, mode='Timeline'):
        """Get list of timeline frames.

        Args:
            mode (str): where to read range from

        Returns:
            (int list): all frames in timeline
        """
        assert mode == 'Timeline'
        return list(range(self.t_start(int), self.t_end(int) + 1))

    def t_range(self, class_=float, expand=0):
        """Get start/end frames.

        Args:
            class_ (class): override result type
            expand (int): expand the range (ie. subtract from
                start and add to end)

        Returns:
            (float, float): start/end time
        """
        return (self.t_start(class_=class_) - expand,
                self.t_end(class_=class_) + expand)

    def t_start(self, class_=float):
        """Get start frame.

        Args:
            class_ (class): override result type

        Returns:
            (float): start time
        """
        raise NotImplementedError

    def take_snapshot(self, file_):
        """Take snapshot of the current scene.

        Args:
            file_ (str): path to save image to
        """
        raise NotImplementedError

    def to_node_name(self, node):
        """Obtain the name of the given node.

        In nuke, converting to string returns the full nk node data, so
        this is required to safely print nodes.

        Args:
            node (any): dcc native node to print

        Returns:
            (str): node name
        """
        return str(node)

    def to_version(self, type_=tuple):
        """Get version of this dcc.

        Default is to return as tuple for easy comparison.

        Args:
            type_ (type): format of result to return (float/str/tuple)

        Returns:
            (any): version in specified type format
        """
        _major, _minor, _patch = self._read_version()
        if type_ is tuple:
            if _patch is None:
                return _major, _minor
            return _major, _minor, _patch
        if type_ is float:
            return _major + 0.1 * _minor
        if type_ is str:
            if _patch is None:
                return f'{_major:d}.{_minor:d}'
            return f'{_major:d}.{_minor:d}.{_patch:d}'
        raise NotImplementedError(type_)

    def unsaved_changes(self):
        """Test whether the current scene has unsaved changes.

        Returns:
            (bool): unsaved changes
        """
        raise NotImplementedError
