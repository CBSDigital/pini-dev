"""Tools for managing the base CExportHandler class.

An export handler is a plugin to facilitate exporting (eg rendering,
publishing) to pipeline by a dcc.
"""

# pylint: disable=too-many-instance-attributes

import logging

from pini import qt, icons, pipe, dcc
from pini.pipe import cache
from pini.tools import error
from pini.utils import cache_result, str_to_seed, last, single

from . import eh_utils, eh_ui

_LOGGER = logging.getLogger(__name__)


class CExportHandler:
    """Base class for any export handler."""

    NAME = None
    TYPE = None
    ACTION = None
    ICON = None

    description = None

    work = None
    metadata = None

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
        assert self.ACTION
        _name = self.NAME or type(self).__name__
        _name = _name.lower().replace(' ', '_')
        self._settings_file = f'{qt.SETTINGS_DIR}/{_name}.ini'

    @property
    def _ui_parent(self):
        """Obtain ui parent (if avaiable).

        Returns:
            (QDialog): parent dialog
        """
        return self.ui.parent if self.ui else None

    def build_ui(self):
        """Build any specific ui elements for this handler.

        This should be implemeneted in the child class.
        """
        _LOGGER.debug('BUILD UI')
        self.ui.layout.addStretch()

    def build_metadata(
            self, work=None, sanity_check_=True, task=None, notes=None,
            force=False):
        """Obtain metadata to apply to a generated export.

        Args:
            work (CPWork): override workfile to read metadata from
            sanity_check_ (bool): run sanity checks before publish
            task (str): task to pass to sanity check
            notes (str): export notes
            force (bool): force completion without any confirmations

        Returns:
            (dict): metadata
        """

        # Handle notes - NOTE: ideally all handlers should be obtaining
        # notes in init_export method so code here should be deprecated
        _notes = notes or self._obt_notes(force=force)

        _LOGGER.debug('NOTES %s', _notes)
        _data = eh_utils.build_metadata(
            action=self.ACTION, work=work or self.work, handler=self.NAME,
            sanity_check_=sanity_check_, force=force, task=task, notes=_notes,
            require_notes=True)

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
        qt.connect_callbacks(self, settings_container=self.ui)

    def init_export(self, notes=None, force=False):
        """Initiate export.

        Args:
            notes (str): apply export notes
            force (bool): force overwrite/update without confirmation
        """

        # Check current work
        self.work = pipe.CACHE.obt_cur_work()
        if not self.work:
            raise error.HandledError(
                "Please save your scene using PiniHelper before exporting."
                "\n\n"
                "This allows the tools to tell what job/task you are working "
                "in, to know where to save the files to.",
                title='Warning', parent=self._ui_parent)

        # Build metadata
        _notes = self._obt_notes(notes=notes, force=force)
        self.metadata = self.build_metadata(notes=_notes, force=force)
        _bkp = self.work.save(
            reason=self.TYPE.lower(), parent=self._ui_parent, notes=_notes)
        self.metadata['bkp'] = _bkp.path

    def to_range(self):
        """Read range based on current ui settings.

        Returns:
            (tuple): start/end frames
        """
        _mode = self.ui.Range.currentText()
        if _mode == 'From timeline':
            return dcc.t_range(int)
        if _mode == 'Manual':
            return self.ui.RangeManStart.value(), self.ui.RangeManEnd.value()
        if _mode == 'Current frame':
            return [dcc.t_frame(int), dcc.t_frame(int)]
        raise ValueError(_mode)

    def exec(self, notes=None, version_up=True, snapshot=True, force=False):
        """Execute this export.

        Args:
            notes (str): cache notes
            version_up (bool): version up after export
            snapshot (bool): take thumbnail snapshot on export
            force (bool): replace existing outputs without confirmation
        """
        raise NotImplementedError

    def exec_from_ui(self):
        """Execuate this export using settings from ui."""
        _kwargs = self.ui.to_kwargs()
        self.exec(**_kwargs)

    def post_export(
            self, work=None, outs=(), version_up=None, update_cache=True,
            notes=None, snapshot=True):
        """Execute post export code.

        This manages updating the shot publish cache and cache and can
        also be extended in subclasses.

        Args:
            work (CPWork): source work file
            outs (CPOutput list): outputs that were generated
            version_up (bool): whether to version up on publish
            update_cache (bool): update work file cache
            notes (str): export notes
            snapshot (bool): save snapshot to work thumbnail
        """
        _work = work or self.work
        _LOGGER.info('POST EXPORT %s', _work.path)
        _LOGGER.info(' - OUTS %d %s', len(outs), outs)

        if (
                (snapshot is not None and snapshot) or
                (self.ui and self.ui.snapshot_elem)):
            self._apply_snapshot(work=_work)

        if update_cache:
            if pipe.SHOTGRID_AVAILABLE:
                self._register_in_shotgrid(work=_work, outs=outs)
            self._update_pipe_cache(work=_work, outs=outs)

        # Apply notes to work
        _work_c = pipe.CACHE.obt(_work)  # May have been rebuilt on update cache
        _notes = notes or single(
            {_out.metadata['notes'] for _out in outs}, catch=True)
        if _notes and not _work_c.notes:
            _work_c.set_notes(_notes)

        self._apply_version_up(version_up=version_up)

    def _obt_notes(self, notes=None, work=None, force=False):
        """Obtain export notes.

        Args:
            notes (str): force notes
            work (CPWork): force work file
            force (bool): suppress request notes dialog

        Returns:
            (str): notes
        """
        _notes = notes
        _work = work or self.work

        # Handle notes
        if not _notes and (
                self.ui and self.ui.is_active() and self.ui.notes_elem):
            _notes = self.ui.notes_elem.text()
        if not _notes and _work:
            _notes = _work.notes
        if not force and not _notes:
            _notes = qt.input_dialog(
                'Please enter notes for this export:', title='Notes')
            if self.ui.notes_elem:
                _LOGGER.debug(
                    ' - APPLY NOTES %s %s', _notes, self.ui.notes_elem)
                self.ui.notes_elem.setText(_notes)

        # Apply notes to work
        if _notes and _work and not _work.notes:
            assert isinstance(_work, cache.CCPWork)
            _work.set_notes(_notes)

        return _notes

    def _register_in_shotgrid(self, work, outs, upstream_files=None):
        """Register outputs in shotgrid.

        Args:
            work (CPWork): source work file
            outs (CPOutput list): outputs that were generated
            upstream_files (list): list of upstream files
        """
        from pini.pipe import shotgrid
        _thumb = work.image if work.image.exists() else None
        for _last, _out in last(outs):
            _LOGGER.info(' - REGISTER %s update_cache=%d', _out, _last)
            shotgrid.create_pub_file_from_output(
                _out, thumb=_thumb, force=True, update_cache=_last,
                upstream_files=upstream_files)

    def _update_pipe_cache(self, work, outs):
        """Update pipeline cache.

        Args:
            work (CPWork): work file being published
            outs (CPOutput list): outputs being exported
        """
        _work_c = pipe.CACHE.obt(work)  # Has been rebuilt
        _work_c.update_outputs()
        _out_paths = [_out.path for _out in _work_c.outputs]
        for _out in outs:
            if _out.path not in _out_paths:
                raise RuntimeError(
                    f'Missing output {_out.path} - {_out_paths})')
        _LOGGER.info(' - UPDATED CACHE')

    def _apply_snapshot(self, work):
        """Apply take snapshot setting.

        Args:
            work (CPWork): work file
        """
        if (
                not self.ui or
                not self.ui.snapshot_elem or
                not self.ui.snapshot_elem.isChecked()):
            return

        _LOGGER.info(' - BLAST FRAME %s', work.image)
        dcc.take_snapshot(work.image)

    def _apply_version_up(self, version_up=None):
        """Apply version up setting.

        Args:
            version_up (bool): force version up setting
        """
        if version_up is not None:
            _version_up = version_up
        elif self.ui:
            _version_up = self.ui.VersionUp.isChecked()
        else:
            _version_up = False
        if _version_up:
            pipe.version_up()

    def __lt__(self, other):
        return -self.priority < -other.priority

    def __repr__(self):
        _name = type(self).__name__.strip('_')
        return f'<{_name}>'
