"""Tools for managing the maya blast handler."""

import logging

from pini import pipe, qt
from pini.tools import error

from maya_pini import m_pipe, open_maya as pom

from . import bh_base

_LOGGER = logging.getLogger(__name__)


class CMayaPlayblast(bh_base.CBlastHandler):
    """Blast handler for maya."""

    NAME = 'Playblast Tool'
    LABEL = 'Playblasts the current scene'
    LABEL_WIDTH = 80

    def build_ui(self, parent=None, layout=None):
        """Build ui elements for this handler.

        Args:
            parent (QWidget): parent widget
            layout (QLayout): parent layout
        """
        super(CMayaPlayblast, self).build_ui(parent=parent, layout=layout)

        # Read cams
        _cams = [str(_cam) for _cam in pom.find_cams()]
        if pom.find_render_cam():
            _cur_cam = pom.find_render_cam()
        elif pom.active_cam():
            _cur_cam = pom.active_cam()
        if _cur_cam:
            _cur_cam = str(_cur_cam)
        _LOGGER.debug('BUILD UI %s %s', _cur_cam, _cams)

        self.ui.Camera = self.add_combobox_elem(
            name='Camera', items=_cams, val=_cur_cam,
            disable_save_settings=True)
        self.ui.Settings = self.add_combobox_elem(
            name='Settings', items=['As is', 'Nice'])
        self.ui.Resolution = self.add_combobox_elem(
            name='Resolution', items=['Full', 'Half', 'Quarter'])
        self.ui.OutputName = self.add_combobox_elem(
            name='OutputName', items=['blast', '<camera>'])

    @property
    def output(self):
        """Obtain blast output path.

        Returns:
            (CPOutput): blast output
        """
        _fmt = self.ui.Format.currentText()
        _work = pipe.cur_work()
        return _work.to_output(
            self.template, output_name=self.output_name, extn=_fmt)

    @property
    def output_name(self):
        """Obtain current output name.

        Returns:
            (str): output name
        """
        _output_name = self.ui.OutputName.currentText()
        _cam = self.ui.Camera.currentText()
        if _output_name == '<camera>':
            _output_name = _cam.replace(':', '_')
        return _output_name

    @property
    def template(self):
        """Obtain current blast template.

        Returns:
            (CPTemplate): template
        """
        _work = pipe.cur_work()
        if not _work:
            return None
        _fmt = self.ui.Format.currentText()
        _tmpl_name = 'blast_mov' if _fmt in ('mp4', 'mov') else 'blast'
        return _work.find_template(_tmpl_name, catch=True)

    def _callback__Format(self):
        super(CMayaPlayblast, self)._callback__Format()
        _en = False
        if self.template:
            _en = 'output_name' in self.template.keys()
        self.ui.OutputName.setEnabled(_en)

    def _validate_output_name(self):
        """Check output name is valid."""
        if not self.ui.OutputName.isEnabled():
            return
        try:
            self.output
        except ValueError:
            raise error.HandledError(
                'You have chosen "{}" as the output name which is not '
                'valid within the pipeline.\n\nPlease select another '
                'output name.'.format(self.output_name))

    def blast(self):
        """Excute blast."""

        _work = pipe.cur_work()
        if not _work:
            qt.notify(
                "Please save your scene using PiniHelper before blasting.\n\n"
                "This allows the tools to tell what job/task you're working "
                "in, to know where to save the blast to.",
                title='Warning', parent=self.parent)
            return
        if not _work.find_template('blast', catch=True):
            qt.notify(
                'No blast template found in this job:\n\n{}\n\n'
                'Unable to blast.'.format(_work.job.path),
                title='Warning', parent=self.parent)
            return

        _force = self.ui.Force.isChecked()
        _output_name = self.ui.OutputName.currentText()
        _cam = self.ui.Camera.currentText()
        self._validate_output_name()

        m_pipe.blast(
            format_=self.ui.Format.currentText(),
            view=self.ui.View.isChecked(),
            range_=self._read_range(),
            burnins=self.ui.Burnins.isChecked(),
            res=self.ui.Resolution.currentText(),
            camera=_cam,
            save=not self.ui.DisableSave.isChecked(),
            settings=self.ui.Settings.currentText(),
            output_name=_output_name,
            force=_force)
