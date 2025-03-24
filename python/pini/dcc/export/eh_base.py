"""Tools for managing the base CExportHandler class.

An export handler is a plugin to facilitate exporting (eg rendering,
publishing) to pipeline by a dcc.
"""

# pylint: disable=too-many-instance-attributes

import logging

from pini import qt, icons, pipe, dcc
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

    def build_ui(self):
        """Build any specific ui elements for this handler.

        This should be implemeneted in the child class.
        """
        _LOGGER.debug('BUILD UI')

    def build_metadata(
            self, work=None, sanity_check_=True, task=None, force=False):
        """Obtain metadata to apply to a generated export.

        Args:
            work (CPWork): override workfile to read metadata from
            sanity_check_ (bool): run sanity checks before publish
            task (str): task to pass to sanity check
            force (bool): force completion without any confirmations

        Returns:
            (dict): metadata
        """

        # Handle notes
        if self.ui and self.ui.is_active() and self.ui.notes_elem:
            _notes = self.ui.notes_elem.text()
        else:
            _notes = None
        if not force and not _notes:
            _notes = qt.input_dialog(
                'Please enter notes for this export:', title='Notes')
            if self.ui.notes_elem:
                _LOGGER.debug(
                    ' - APPLY NOTES %s %s', _notes, self.ui.notes_elem)
                self.ui.notes_elem.setText(_notes)

        _LOGGER.debug('NOTES %s', _notes)
        _data = eh_utils.build_metadata(
            action=self.ACTION, work=work, sanity_check_=sanity_check_,
            force=force, handler=self.NAME, task=task, notes=_notes,
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
        qt.connect_callbacks(self, settings=self.ui.settings)

    def init_export(self):
        """Run pre export code."""
        self.work = pipe.CACHE.obt_cur_work()
        if not self.work:
            raise error.HandledError(
                "Please save your scene using PiniHelper before blasting.\n\n"
                "This allows the tools to tell what job/task you're working "
                "in, to know where to save the blast to.",
                title='Warning', parent=self.parent)
        self.metadata = eh_utils.build_metadata(
            sanity_check_=True, src=self.work)
        _bkp = self.work.save(reason=self.ACTION)
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
        raise ValueError(_mode)

    def post_export(
            self, work, outs=(), version_up=None, update_cache=True,
            notes=None):
        """Execute post export code.

        This manages updating the shot publish cache and cache and can
        also be extended in subclasses.

        Args:
            work (CPWork): source work file
            outs (CPOutput list): outputs that were generated
            version_up (bool): whether to version up on publish
            update_cache (bool): update work file cache
            notes (str): export notes
        """
        _LOGGER.info('POST EXPORT %s', work.path)
        _LOGGER.info(' - OUTS %d %s', len(outs), outs)

        if self.ui and self.ui.snapshot_elem:
            self._apply_snapshot(work=work)

        if update_cache:
            if pipe.SHOTGRID_AVAILABLE:
                self._register_in_shotgrid(work=work, outs=outs)
            self._update_pipe_cache(work=work, outs=outs)

        # Apply notes to work
        _work_c = pipe.CACHE.obt(work)  # May have been rebuilt on update cache
        _notes = notes or single(
            {_out.metadata['notes'] for _out in outs}, catch=True)
        if _notes and not _work_c.notes:
            _work_c.set_notes(_notes)

        self._apply_version_up(version_up=version_up)

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
