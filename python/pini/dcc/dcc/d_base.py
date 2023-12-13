"""Tools for managing the base dcc object."""

# pylint: disable=too-many-public-methods

import logging
import os
import sys

from pini import icons
from pini.utils import File, single, passes_filter

_LOGGER = logging.getLogger(__name__)


class BaseDCC(object):
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
        """Add a render handler to the current list.

        Each new render handler is added as the top level renderer -
        generally if you're adding a render handler for a site, that
        should be at the top of the list.

        Args:
            handler (CRenderHandler): render handler to add.
        """
        _LOGGER.debug('ADD RENDER HANDLER %s', handler)
        self._init_export_handlers()
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
            output (CPOutputBase): output to reference

        Returns:
            (bool): whether output can be referenced
        """
        return output.extn in self.REF_EXTNS

    def clear_terminal(self):
        """Clear current terminal or script editor (if applicable)."""

    def create_cache_ref(
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
            catch=False):
        """Find a reference in the current scene.

        Args:
            namespace (str): reference namespace to match
            selected (bool): return only selected refs
            extn (str): filter by extension
            filter_ (str): filter by namespace
            catch (bool): no error if no matching ref found

        Returns:
            (CPipeRef): matching ref
        """
        _refs = self.find_pipe_refs(
            extn=extn, namespace=namespace, selected=selected, filter_=filter_)
        _error = 'Failed to match reference'
        if selected:
            _error = 'Multiple references selected'
        return single(_refs, catch=catch, error=_error)

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
            if task and _ref.output.task != task:
                continue
            _refs.append(_ref)
        return sorted(_refs)

    def find_export_handler(self, action=None, filter_=None, catch=False):
        """Find an installed export handler.

        Args:
            action (str): filter by export type (eg. publish/render)
            filter_ (str): filter by exporter name
            catch (bool): no error if no matching handler found

        Returns:
            (CExportHandler): matching export handler
        """
        _handlers = self.find_export_handlers(action=action, filter_=filter_)
        return single(
            _handlers, catch=catch, verbose=1,
            items_label='{} {} handlers'.format(self.NAME, action))

    def find_export_handlers(self, action=None, filter_=None):
        """Find render handlers for this dcc.

        Args:
            action (str): filter by export type (eg. publish/render)
            filter_ (str): filter by exporter name

        Returns:
            (CExportHandler list): installed export handlers
        """
        _LOGGER.debug('FIND EXPORT HANDLERS %s', self._export_handlers)
        self._init_export_handlers()

        # Build list
        _handlers = []
        for _handler in self._export_handlers:
            if action and _handler.ACTION != action:
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
                title='Unsaved Changes')
            return

        # Offer to save unsaved changes
        _msg = 'Lose unsaved changes in the current scene?\n\n{}'.format(
            _file)
        _icon = icons.find('Thinking')
        _result = qt.raise_dialog(
            msg=_msg, buttons=('Save', "Don't Save", 'Cancel'),
            title='Save Changes', icon=_icon, parent=parent)
        if _result == 'Save':
            self._force_save()

    def _init_export_handlers(self):
        """Initiate export handlers list."""
        if self._export_handlers is None:
            from .. import export_handler
            _LOGGER.debug('INIT EXPORT HANDLERS')
            self._export_handlers = [
                export_handler.CBasicPublish(),
            ]

    def load(self, file_, parent=None, force=False, lazy=False):
        """Load scene.

        Args:
            file_ (str): file to load
            parent (QDialog): parent dialog for warnings
            force (bool): load scene without unsaved changes warnings
            lazy (bool): don't load if file is already open
        """
        _file = File(file_)
        if _file.extn not in self.VALID_EXTNS:
            raise RuntimeError('Invalid file '+_file.path)
        if lazy and _file.path == self.cur_file():
            _LOGGER.info('Lazy load - scene currently open')
            return
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
                qt.ok_cancel('Overwrite existing file?\n\n{}'.format(
                    _file.path), parent=parent)
            self._force_save(file_=_file)
        else:
            self._force_save()

    def select_node(self, node):
        """Select the given node.

        Args:
            node (any): node to select
        """
        raise NotImplementedError

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

    def set_res(self, width, height):
        """Set current image resolution.

        Args:
            width (int): image width
            height (int): image height
        """
        raise NotImplementedError

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
        return list(range(self.t_start(int), self.t_end(int)+1))

    def t_range(self, class_=float, expand=0):
        """Get start/end frames.

        Args:
            class_ (class): override result type
            expand (int): expand the range (ie. subtract from
                start and add to end)

        Returns:
            (float, float): start/end time
        """
        return (self.t_start(class_=class_)-expand,
                self.t_end(class_=class_)+expand)

    def t_start(self, class_=float):
        """Get start frame.

        Args:
            class_ (class): override result type

        Returns:
            (float): start time
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
            return _major+0.1*_minor
        if type_ is str:
            if _patch is None:
                return '{:d}.{:d}'.format(_major, _minor)
            return '{:d}.{:d}.{:d}'.format(_major, _minor, _patch)
        raise NotImplementedError(type_)

    def unsaved_changes(self):
        """Test whether the current scene has unsaved changes.

        Returns:
            (bool): unsaved changes
        """
        raise NotImplementedError
