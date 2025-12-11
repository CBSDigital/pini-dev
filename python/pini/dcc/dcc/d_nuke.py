"""Tools for managing nuke/pini interface."""

# pylint: disable=abstract-method,too-many-public-methods

import logging
import os

import nuke

from pini.utils import (
    abs_path, File, Seq, check_heart, passes_filter, to_str)
from nuke_pini.utils import clear_selection

from .d_base import BaseDCC

if not nuke.__file__:
    raise ImportError('Bad nuke module')

_LOGGER = logging.getLogger(__name__)


def _obtain_menu(name):
    """Obtain menu of the given name, creating it if needed.

    Args:
        name (str): menu name (eg. File)

    Returns:
        (Menu): nuke menu object
    """
    _menu_bar = nuke.menu("Nuke")
    _menu = _menu_bar.findItem(name)
    if not _menu or not isinstance(_menu, nuke.Menu):
        _menu = _menu_bar.addMenu(name)
    return _menu


class NukeDCC(BaseDCC):
    """Manages interactions with nuke."""

    NAME = 'nuke'

    if nuke.env.get('nc'):
        DEFAULT_EXTN = 'nknc'
    else:
        DEFAULT_EXTN = 'nk'
    VALID_EXTNS = (DEFAULT_EXTN, )

    def add_menu_divider(self, parent, name=None):  # pylint: disable=unused-argument
        """Add menu divider to maya ui.

        Args:
            parent (str): parent menu
            name (str): uid for divider
        """
        assert parent
        _menu = _obtain_menu(parent)
        _div = _menu.addSeparator()
        _LOGGER.debug('ADDED MENU DIVIDER %s (menu=%s)', _div, parent)
        return _div

    def add_menu_item(self, parent, command, image, label, name=None):  # pylint: disable=unused-argument
        """Add menu item to maya ui.

        Args:
            parent (str): parent menu
            command (func): command to call on item click
            image (str): path to item icon
            label (str): label for item
            name (str): uid for item
        """
        assert parent
        _menu = _obtain_menu(parent)
        _menu.removeItem(label)
        _item = _menu.addCommand(
            name=label, command=command, icon=to_str(image))
        _LOGGER.debug('ADDED MENU ITEM %s (menu=%s)', _item, parent)
        return _item

    def batch_mode(self):
        """Test if nuke is in batch mode.

        Returns:
            (bool): whether in batch mode
        """
        return not nuke.GUI

    def can_reference_output(self, output):
        """Test whether maya can reference the given output.

        Args:
            output (CPOutput): output to reference

        Returns:
            (bool): whether output can be referenced
        """
        from pini import pipe
        return (
            isinstance(output, (pipe.CPOutputSeq, pipe.CPOutputVideo)) or
            output.extn in ['abc', 'mp4', 'mov'])

    def create_ref(self, path, namespace, force=False):
        """Create reference instance of the given path.

        Args:
            path (File): file to reference
            namespace (str): namespace reference
            force (bool): replace existing without confirmation

        Returns:
            (FileRef): reference
        """
        _LOGGER.info('CREATE REF %s', path)
        from pini import pipe

        _knobs = f'file "{path.path}" name {namespace}'
        if isinstance(path, Seq):
            _seq = path
            _start, _end = _seq.to_range(force=True)
            _LOGGER.info(' - SEQ %d-%d', _start, _end)
            _knobs += f' first {_start:d} last {_end:d}'
            _type = 'Read'
        elif path.extn in ['mov', 'mp4']:
            _knobs += ' colorspace color_picking'
            _type = 'Read'
        elif isinstance(path, pipe.CPOutputFile) and path.extn == 'abc':
            _out = path
            _out_type = _out.metadata.get('type')
            _fps = _out.metadata.get('fps')
            if _out_type == 'CPCacheableCam':
                _type = 'Camera2'
                _knobs += ' read_from_file true'
                if _fps:
                    _knobs += f' frame_rate {_fps:f}'
            else:
                _type = 'ReadGeo2'
        else:
            raise ValueError(path)

        _LOGGER.info(' - CREATE NODE %s knobs=%s', _type, _knobs)
        clear_selection()
        _node = nuke.createNode(_type, _knobs)

        # Select all items in abc
        if _type == 'ReadGeo2':
            _scene_view = _node['scene_view']
            _scene_view.setAllItems(_scene_view.getAllItems(), True)

        _LOGGER.info(' - NAME %s', path)
        return self.find_pipe_ref(_node.name())

    def cur_file(self):
        """Get path to current script.

        Returns:
            (str): current scene path
        """
        _file = nuke.Root()["name"].getValue()
        if not _file:
            return None
        return abs_path(_file)

    def cur_frame(self):
        """Obtain current frame.

        Returns:
            (int): current frame
        """
        from pini.tools import release
        release.apply_depreaction('14/08/25', 'Use t_frame')
        return nuke.frame()

    def _force_load(self, file_, clear=True):
        """Force load the given scene.

        Args:
            file_ (str): scene to load
            clear (bool): clear scene before load to prevent
                new nuke from spawning
        """
        from pini.tools import error

        _file = to_str(file_)
        if clear:
            self._force_new_scene()

        # Load scene
        try:
            nuke.scriptOpen(_file)
        except RuntimeError as _exc:
            _msg = str(_exc)

            # Catch version mismatch
            if (
                    _msg.startswith(_file) and
                    'is for nuke' in _msg and
                    '; this is nuke' in _msg):
                _file_ver = _msg.split('is for nuke')[1].split()[0].strip(';')
                _this_ver = _msg.split()[-1].replace('nuke', '')
                _msg = (
                    f'Nuke errored on load because the file was saved in '
                    f'nuke-{_file_ver} and this is nuke-{_this_ver}:'
                    f'\n\n{_file}')
                raise error.HandledError(_msg, title='Version Mismatch')
            raise _exc

    def _force_new_scene(self):
        """Force new scene."""
        nuke.scriptClear()

    def _force_save(self, file_=None):
        """Force save the current scene without overwrite confirmation.

        Args:
            file_ (str): path to save scene to
        """
        _file = file_ or self.cur_file()
        if not _file:
            raise RuntimeError('Unabled to determine save file')
        _file = File(_file)
        _LOGGER.info('FORCE SAVE %s', _file.path)
        nuke.scriptSaveAs(_file.path, overwrite=True)

        # Update current shortcut in nuke file browser
        os.chdir(_file.to_dir().path)

    def get_fps(self):
        """Obtain current frame rate from root node.

        Returns:
            (float): frame rate
        """
        return nuke.Root()['fps'].value()

    def get_main_window_ptr(self):
        """Get main window pointer to main maya window.

        Returns:
            (QDialog): main window pointer
        """
        from pini import qt
        _app = qt.get_application()
        for _widget in _app.topLevelWidgets():
            _name = _widget.metaObject().className()
            if _name == 'Foundry::UI::DockMainWindow':
                return _widget
        _LOGGER.info('MAIN WINDOW NOT FOUND')
        return None

    def get_next_namespace(self, base, ignore=(), mode='asset'):  # pylint: disable=unused-argument
        """Get next available namespace.

        Args:
            base (str): namespace base
            ignore (str list): list of namespaces to ignore
            mode (str): how to allocate next namespace
        """
        _name = base
        _count = 1
        while nuke.toNode(_name):
            check_heart()
            _name = f'{base}_{_count:d}'
            if _name in ignore:
                continue
            _count += 1
        return _name

    def get_res(self):
        """Read current resolution setting.

        Returns:
            (tuple): width/height
        """
        _fmt = nuke.Root()['format'].value()
        return _fmt.width(), _fmt.height()

    def get_scene_data(self, key):
        """Retrieve data stored with this scene.

        Args:
            key (str): data to obtain
        """
        _key = 'PINI_DATA_' + key
        _knob = nuke.Root().knob(_key)
        if not _knob:
            return None
        _LOGGER.debug('KNOB %s', _knob)
        return _knob.value()

    def _read_pipe_refs(self, selected=False, filter_=None):
        """Find reference in the current dcc.

        If a node is found that is referencing a valid output but that output
        isn't in the cache for that entity, the cache is rebuilt. This can
        arise from a render being submitted but never being registered in
        the pipeline, and the initial disk cache showing the directory as
        empty.

        However, sometimes the output may be missing from the cache because
        it has been deleted - if this is the case then it's flagged as a bad
        output, and any future instances of it in the current session are
        ignored.

        Args:
            selected (bool): return only selected refs
            filter_ (str): filter node list (for debugging)

        Returns:
            (CPipeRef list): list of references
        """
        from pini import pipe
        from pini.dcc.pipe_ref import pr_nuke

        _LOGGER.debug('READ PIPE REFS')
        _refs = []
        _rebuilt = []
        for _type, _class in [
                ('Read', pr_nuke.CNukeReadRef),
                ('Camera2', pr_nuke.CNukeCamAbcRef),
                ('Camera3', pr_nuke.CNukeCamAbcRef),
                ('ReadGeo2', pr_nuke.CNukeAbcRef),
        ]:
            _nodes = nuke.allNodes(_type)
            _LOGGER.debug(
                ' - CHECKING TYPE %s %d %s', _type, len(_nodes), _nodes)
            for _node in _nodes:

                if not passes_filter(_node.name(), filter_):
                    continue
                _LOGGER.debug(' - CHECKING NODE %s', _node.name())

                # Get file path
                _file = _node['file'].getValue()
                _file = _file.replace('.####.', '.%04d.')
                _file = pipe.map_path(_file)
                _LOGGER.debug('   - FILE "%s"', _file)

                # Check if valid pipeline output
                try:
                    _out = pipe.to_output(_file)
                except ValueError as _exc:
                    _LOGGER.debug('   - REJECTED %s', _exc)
                    continue
                _LOGGER.debug('   - OUT %s', _out)

                # Build pipe ref object
                _ref = _class(path=_file, node=_node)
                _LOGGER.debug('   - ACCEPTED %s', _ref)
                if selected and not _node.isSelected():
                    continue
                _refs.append(_ref)

        return _refs

    def select_node(self, node):
        """Select the given node.

        Args:
            node (Node): node to select
        """
        _LOGGER.info('SELECT NODE %s', node.name())
        clear_selection()
        node.setSelected(True)
        node.showControlPanel()

    def set_fps(self, fps):
        """Set frame rate.

        Args:
            fps (float): frame rate to apply
        """
        nuke.Root()['fps'].setValue(fps)

    def set_range(self, start, end):
        """Set current frame range.

        Args:
            start (float): start frame
            end (float): end frame
        """
        nuke.Root()['first_frame'].setValue(start)
        nuke.Root()['last_frame'].setValue(end)

    def set_res(self, width, height):
        """Set current resolution.

        Args:
            width (int): width in pixels
            height (int): height in pixels
        """
        _res = width, height
        for _fmt in nuke.formats():
            _fmt_res = _fmt.width(), _fmt.height()
            if _fmt_res == _res:
                break
        else:
            raise ValueError(
                f'Failed to find format {width:d}x{height:d}')
        _LOGGER.info('APPLY FORMAT %s', _fmt)
        nuke.Root()['format'].setValue(_fmt)
        assert self.get_res() == _res

    def set_scene_data(self, key, val):
        """Store data within this scene.

        Args:
            key (str): name of data to store
            val (any): value of data to store
        """
        _key = 'PINI_DATA_' + key
        _root = nuke.Root()

        _tab = _root.knob('Pini')
        if not _tab:
            _tab = _root.addKnob(nuke.Tab_Knob("Pini"))

        # Determine knob class
        _apply_val = False
        _args = _key, key, val
        if isinstance(val, bool):
            _class = nuke.Boolean_Knob
        elif isinstance(val, str):
            _class = nuke.String_Knob
        elif isinstance(val, int):
            _class = nuke.Int_Knob
            _apply_val = True
            _args = _key, key
        elif isinstance(val, float):
            _class = nuke.Double_Knob
            _apply_val = True
            _args = _key, key
        else:
            raise ValueError(val)

        _knob = _root.knob(_key)
        if _knob:
            _LOGGER.debug('EXISTING KNOB %s', _knob)
            assert isinstance(_knob, _class)
            _knob.setValue(val)
        else:
            _knob = _class(*_args)
            _root.addKnob(_knob)
            if _apply_val:
                _knob.setValue(val)

    def t_end(self, class_=float):
        """Obtain timeline end frame.

        Args:
            class_ (class): force class of result

        Returns:
            (float): end frame
        """
        return class_(nuke.Root()["last_frame"].getValue())

    def t_start(self, class_=float):
        """Obtain timeline start frame.

        Args:
            class_ (class): force class of result

        Returns:
            (float): start frame
        """
        return class_(nuke.Root()["first_frame"].getValue())

    def to_node_name(self, node):
        """Obtain name of the given node.

        Args:
            node (Node): node to read

        Returns:
            (str): node name
        """
        return node.name()

    def _read_version(self):
        """Read nuke version.

        Returns:
            (tuple): major/minor versions
        """
        return nuke.NUKE_VERSION_MAJOR, nuke.NUKE_VERSION_MINOR, None

    def unsaved_changes(self):
        """Test whether there are currently unsaved changes.

        Returns:
            (bool): unsaved changes
        """
        return nuke.modified()
