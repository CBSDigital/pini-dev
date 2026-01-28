"""Tools for managing the base CExportHandler class.

An export handler is a plugin to facilitate exporting (eg rendering,
publishing) to pipeline by a dcc.
"""

# pylint: disable=too-many-instance-attributes

import logging
import inspect

from pini import qt, icons, pipe, dcc
from pini.qt import QtWidgets
from pini.pipe import cache
from pini.tools import error, usage
from pini.utils import cache_result, str_to_seed, last, is_pascal

from . import eh_utils, eh_ui

_LOGGER = logging.getLogger(__name__)


class CExportHandler:
    """Base class for any export handler."""

    NAME = None
    TYPE = None
    ACTION = None
    ICON = None

    LABEL = 'Export handler.'
    COL = 'Red'

    description = None
    profile_filter = None

    add_substeps = False
    add_notes = True
    add_range = False

    work = None
    metadata = None
    outputs = ()

    def __init__(self, priority=50, label_w=70):
        """Constructor.

        Args:
            priority (int): sort priority (higher priority handlers
                are sorted to top of option lists)
            label_w (int): label width in ui
        """
        self.ui = None
        self.priority = priority
        self.label_w = label_w

        assert self.NAME
        assert self.ACTION
        assert is_pascal(self.ACTION)
        assert self.ICON

        _name = self.NAME or type(self).__name__
        _name = _name.lower().replace(' ', '_')
        self._settings_file = f'{qt.SETTINGS_DIR}/{_name}.ini'

    @property
    def title(self):
        """Obtain title for this handler.

        This is used for the execute button in the ui and the title of the
        progress bar.

        Returns:
            (str): title (eg. Abc Publish, Playblast)
        """
        _title = self.NAME
        _dcc_prefix = f'{dcc.NAME.capitalize()} '
        if _title.startswith(_dcc_prefix):
            _title = _title[len(_dcc_prefix):]
        return _title

    @property
    def _ui_parent(self):
        """Obtain ui parent (if avaiable).

        Returns:
            (QDialog): parent dialog
        """
        return self.ui.parent if self.ui else None

    def _build_ui_header(self):
        """Build ui header elements."""
        self.ui.add_separator()

        self.ui.Label = QtWidgets.QLabel(self.LABEL, self.ui.parent)
        self.ui.Label.setWordWrap(True)
        self.ui.Label.setObjectName('Label')
        self.ui.layout.addWidget(self.ui.Label)

        if self.add_range:
            self.ui.add_separator()
            self.ui.assemble_range_elems(mode=self.add_range)

    def _add_custom_ui_elems(self):
        """Add custom ui elements.

        Allows extra ui elements to be added in subclass.
        """

    def _build_ui_footer(
            self, stretch=True, add_snapshot=True, add_version_up=True,
            version_up=True, exec_label=None):
        """Build ui footer elements.

        Args:
            stretch (bool): apply stretch (disable if the current ui
                contains a stretch element, ie. the interface should
                fill the whole layout)
            add_snapshot (bool): add snapshot checkbox
            add_version_up (bool): add version up option
            version_up (bool): default version up setting
            exec_label (str): override label for exec button
        """
        self.ui.assemble_footer_elems(
            add_version_up=add_version_up, version_up=version_up,
            add_snapshot=add_snapshot)

        self.ui.add_separator()
        self.ui.add_exec_btn(exec_label or self.title)
        if stretch:
            self.ui.layout.addStretch()

    def build_ui(
            self, add_snapshot=True, add_version_up=True, version_up=True,
            exec_label=None):
        """Build any specific ui elements for this handler.

        Args:
            add_snapshot (bool): add snapshot checkbox
            add_version_up (bool): add version up option
            version_up (bool): default version up setting
            exec_label (str): override label for exec button
        """
        _LOGGER.debug('BUILD UI')
        self._build_ui_header()
        self._add_custom_ui_elems()
        self._build_ui_footer(
            stretch=True, version_up=version_up, add_snapshot=add_snapshot,
            add_version_up=add_version_up, exec_label=exec_label)

    def build_metadata(self):
        """Obtain metadata to apply to a generated export.

        Returns:
            (dict): metadata
        """
        _LOGGER.debug('BUILD METADATA %s', self)
        _checks_data = self.settings['checks_data']
        _force = self.settings['force']
        _run_checks = self.settings['run_checks']
        _LOGGER.debug('BUILD METADATA force=%d')
        _LOGGER.debug(' - RUN CHECKS %d %s', _run_checks, _checks_data)

        _notes = self._obt_notes()
        _LOGGER.debug(' - NOTES %s', _notes)
        _data = eh_utils.build_metadata(
            action=self.ACTION, work=self.work, handler=type(self).__name__,
            run_checks=_run_checks, force=_force, task=self.work.pini_task,
            notes=_notes, require_notes=False, checks_data=_checks_data)

        return _data

    @cache_result
    def to_icon(self):
        """Obtain icon for this export handler.

        Returns:
            (str): path to icon
        """
        if self.ICON:
            return self.ICON
        _rand = str_to_seed(self.NAME)
        return _rand.choice(icons.find_grp('AnimalFaces'))

    def ui_is_active(self):
        """Test whether this export handler's ui is currently active.

        Returns:
            (bool): ui active status
        """
        if not self.ui:
            return False
        try:
            _widgets = self.ui.find_widgets()
        except RuntimeError:
            return False
        if not _widgets:
            return False
        _widget = _widgets[0]
        try:
            _widget.objectName()
        except RuntimeError:
            return False
        return True

    @error.get_catcher(qt_safe=True)
    def update_ui(self, parent, layout):
        """Builds the ui into the given layout, flushing any existing widgets.

        This method should not be overloaded - use the build_ui method.

        Args:
            parent (QWidget): parent widget
            layout (QLayout): layout to add elements to
        """
        _LOGGER.debug('UPDATE UI %s', self)

        # Setup ui
        self.ui = self.ui or eh_ui.CExportHandlerUI(
            settings_file=self._settings_file, handler=self,
            label_w=self.label_w)
        self.ui.parent = parent
        self.ui.layout = layout

        # Populate ui
        qt.flush_layout(self.ui.layout)
        self.build_ui()
        self.ui.load_settings()
        qt.connect_callbacks(
            self, settings_container=self.ui, catch_missing=True,
            error_catcher=error.get_catcher(qt_safe=True, supress_error=True))

    def to_frames(self):
        """Obtain list of export frames.

        Returns:
            (int list): frames
        """
        return self.ui.to_frames()

    def to_range(self):
        """Read range based on current ui settings.

        Returns:
            (tuple): start/end frames
        """
        _mode = self.ui.Range.currentText()
        if _mode == 'From timeline':
            return dcc.t_range(int)
        if _mode == 'Manual':
            return (
                self.ui.RangeManualStart.value(),
                self.ui.RangeManualEnd.value())
        if _mode == 'Current frame':
            return [dcc.t_frame(int), dcc.t_frame(int)]
        raise ValueError(_mode)

    def exec(self, *args, **kwargs):
        """Execute this export.

        Args:
            notes (str): cache notes
            version_up (bool): version up after export
            snapshot (bool): take thumbnail snapshot on export
            force (bool): replace existing outputs without confirmation
        """
        _LOGGER.debug('EXEC %s args=%s kwargs=%s', self, args, kwargs)
        self.set_settings(*args, **kwargs)
        self.init_export()

        self.outputs = self.export(*args, **kwargs)
        assert isinstance(self.outputs, list)

        self.post_export()

        return self.outputs

    def set_settings(self, *args, **kwargs):
        """Setup settings dict.

        Settings are initiated from the base class export methods kwargs (eg.
        version_up, notes), then updated with this class's export method's
        kwargs (so that the defaults are defined in this method's signature),
        and then updated with any kwargs passed by this export.
        """
        self.settings = {}

        # Apply kwarg defaults from export funcs
        for _func in [CExportHandler.export, self.export]:
            _sig = inspect.signature(_func)
            _parms = _sig.parameters.values()
            _settings = {
                _parm.name: _parm.default for _parm in _parms
                if _parm.default != inspect.Parameter.empty  # ignore args
            }
            _LOGGER.debug(' - ADD %s SETTINGS %s', _func, _settings)
            self.settings.update(_settings)
        self.settings.update(kwargs)

        # Apply args
        _sig = inspect.signature(self.export)
        _parms = list(_sig.parameters.values())
        for _idx, _arg in enumerate(args):
            _LOGGER.debug(' - ADD ARG %s', _arg)
            _arg_name = _parms[_idx].name
            _LOGGER.debug('   - SIG %s', )
            self.settings[_arg_name] = _arg

        _LOGGER.debug(' - SET SETTINGS %s', self.settings)

    def exec_from_ui(self, ui_kwargs=None, **kwargs):
        """Execute this export using settings from ui.

        Args:
            ui_kwargs (dict): override interface kwargs
        """
        _LOGGER.debug('EXEC FROM UI %s', kwargs)
        _func = self.exec
        _LOGGER.debug(' - EXEC FUNC %s', _func)
        _name = type(self).__name__.strip('_')
        _func = usage.get_tracker(name=_name)(_func)
        _func = error.get_catcher(qt_safe=True)(_func)

        _kwargs = ui_kwargs or self.ui.to_kwargs()
        _kwargs.update(kwargs)
        _LOGGER.debug(' - EXEC KWARGS %s', _kwargs)

        _result = _func(**_kwargs)
        _LOGGER.debug(' - EXEC RESULT %s', _result)
        return _result

    def init_export(self):
        """Initiate export.

        This is executed before export. It will:
         - check for current work
         - sets up work + metadata
         - applies save option
        """
        _bkp = self.settings['bkp']
        _force = self.settings['force']
        _notes = self.settings['notes']
        _progress = self.settings['progress']
        _save = self.settings['save']

        self._set_work()

        _notes = self._obt_notes()
        self.metadata = self.build_metadata()
        self._check_for_overwrite()

        # Show progress after any ops which might raise a dialog as this
        # can make the window behaviour get weird
        self.progress = qt.progress_dialog(
            self.title, stack_key=self.NAME, show=_progress, col=self.COL,
            lock_vis=True, modal=True)

        # Apply save options
        if _save:
            _LOGGER.info(' - SAVE bkp=%d force=%d', _bkp, _force)
            if _bkp:
                _bkp_file = self.work.save(
                    reason=self.TYPE.lower(), parent=self._ui_parent,
                    notes=_notes, result='bkp', update_outputs=False,
                    force=True)
                self.metadata['bkp'] = _bkp_file.path
            else:
                dcc.save()
        self.progress.set_pc(10)

    def _set_work(self):
        """Set work."""
        _check_work = self.settings['check_work']
        _work = self.settings['work']

        if _work:
            self.work = pipe.CACHE.obt_work(_work)
        else:
            self.work = pipe.CACHE.obt_cur_work()

        if not _check_work or self.work:
            return

        # Check for shot missing from
        _work_u = pipe.cur_work()
        if _work_u and pipe.SHOTGRID_AVAILABLE:
            raise error.HandledError(
                f"Current work file is invalid.\n\n{_work_u}\n\n"
                f"This could be because the {_work_u.profile} is missing "
                "or omitted in shotgrid.",
                title='Error', parent=self._ui_parent)

        raise error.HandledError(
            "No current work file - please save your scene using "
            "PiniHelper before exporting.\n\n"
            "This allows the tools to tell what job/task you are working "
            "in, to know where to save the files to.",
            title='Error', parent=self._ui_parent)

    def _check_for_overwrite(self):
        """Check for existing files that will be overwritten."""

    def export(
            self, notes=None, version_up=True, snapshot=True, save=True,
            bkp=True, progress=False, work=None, check_work=True,
            update_metadata=True, update_cache=True,
            run_checks=True, checks_data=None, force=False):
        """Execute this export.

        This is the main export method, to be implemented in each exporter.
        The signature of this method defines the export settings.

        Args:
            notes (str): export notes
            version_up (bool): version up after export
            snapshot (bool): take thumbnail snapshot on export
            save (bool): save work file on export
            bkp (bool): save bkp file
            progress (bool): show progress bar
            work (CPWork): override work file (for testing)
            check_work (bool): check for current work
            update_metadata (bool): update output metadata
            update_cache (bool): update pipe cache
            run_checks (bool): apply sanity check
            checks_data (dict): apply sanity checks data
            force (bool): replace existing outputs without confirmation
        """
        raise NotImplementedError

    def post_export(self):
        """Execute post export code.

        Executed after export. It will:
         - update metadata of generated outputs
         - update pipeline cache
         - apply version up flag
        """
        _LOGGER.info('POST EXPORT %s', self.work)

        _update_metadata = self.settings['update_metadata']
        _update_cache = self.settings['update_cache']
        _snapshot = self.settings['snapshot']
        _version_up = self.settings['version_up']

        _LOGGER.info(' - OUTS %d %s', len(self.outputs), self.outputs)
        _LOGGER.info(
            ' - METADATA update=%d %s', _update_metadata, self.metadata)

        self.progress.set_pc(90)
        if _update_metadata:
            self._update_metadata()
        self.progress.set_pc(92)
        if _snapshot:
            dcc.take_snapshot(self.work.image)
        self.progress.set_pc(94)
        if _update_metadata:
            if pipe.SHOTGRID_AVAILABLE:
                self._register_in_shotgrid()
        if _update_cache:
            self._update_pipe_cache()
        self.progress.set_pc(96)
        if _version_up:
            pipe.version_up()

        self.progress.set_pc(100)

    def _update_metadata(self):
        """Update metadata on generated outputs."""
        _LOGGER.info(
            ' - UPDATE METADATA %d %s', len(self.outputs), self.outputs)
        assert self.metadata
        for _out in self.outputs:
            _out.set_metadata(self.metadata, mode='add', force=True)

    def _obt_notes(self):
        """Obtain export notes.

        If none are provided and none are found on the work file, a dialog
        is raised requesting notes. These notes are then applied back to the
        work file.

        Returns:
            (str): notes
        """
        _LOGGER.debug('OBT NOTES %s', self)
        _notes = self.settings['notes']
        _force = self.settings['force']
        if not self.add_notes:
            _LOGGER.debug(' - ADD NOTES DISABLED')
            _force = True
        _LOGGER.debug(' - FORCE %d', _force)

        # Obtain notes
        if not _notes and self.work:  # Obtain from work
            _notes = self.work.notes
        if not _force and not _notes:  # Request from user
            _notes = qt.input_dialog(
                'Please enter notes for this export:', title='Notes')
            if self.ui and self.ui.notes_elem:
                _LOGGER.debug(
                    ' - APPLY NOTES %s %s', _notes, self.ui.notes_elem)
                self.ui.notes_elem.setText(_notes)

        # Apply notes to work
        if _notes and self.work and not self.work.notes:
            assert isinstance(self.work, cache.CCPWork)
            self.work.set_notes(_notes)

        return _notes

    def _register_in_shotgrid(self, upstream_files=None):
        """Register outputs in shotgrid.

        Args:
            upstream_files (list): list of upstream files
        """
        _update_cache = self.settings['update_cache']

        _LOGGER.info('REGISTER IN SHOTGRID %s', self)
        _LOGGER.info(' - OUTPUTS %d %s', len(self.outputs), self.outputs)
        from pini.pipe import shotgrid
        _work_thumb = self.work.image if self.work.image.exists() else None
        for _last, _out in last(self.outputs):

            _LOGGER.info(' - REGISTER %s update_cache=%d', _out, _last)

            _thumb = _work_thumb
            if _out.basic_type in ('texture', 'render', 'video'):
                _thumb = None

            shotgrid.create_pub_file_from_output(
                _out, thumb=_thumb, force=True, update_cache=_last,
                upstream_files=upstream_files)

    def _update_pipe_cache(self):
        """Update pipeline cache."""
        _LOGGER.info('UPDATE PIPE CACHE')

        _LOGGER.info(' - UPDATE WORK OUTPUTS')
        pipe.CACHE.reset()
        self.work = pipe.CACHE.obt(self.work)
        self.work.update_outputs()

        # Check output paths + update to cacheable
        _out_paths = [_out.path for _out in self.work.outputs]
        for _idx, _out in enumerate(self.outputs):

            # Check this output is in work outputs
            if _out.path not in _out_paths:
                raise RuntimeError(
                    f'Missing output {_out.path} - {_out_paths})')

            # Update output to cacheable version
            _out_c = pipe.CACHE.obt_output(_out, catch=True)
            if _out_c:
                self.outputs[_idx] = _out_c
            else:
                _LOGGER.warning('   - FAILED TO FIND OUT CACHE %s', _out)

        _LOGGER.info(' - UPDATED CACHE')

    def __lt__(self, other):
        return -self.priority < -other.priority

    def __repr__(self):
        _name = type(self).__name__.strip('_')
        return f'<{_name}>'
