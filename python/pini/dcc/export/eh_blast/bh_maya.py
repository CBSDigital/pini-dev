"""Tools for managing the maya blast handler."""

import logging

from pini import pipe

from maya_pini import m_pipe, open_maya as pom

from . import bh_base

_LOGGER = logging.getLogger(__name__)


class CMayaPlayblast(bh_base.CBlastHandler):
    """Blast handler for maya."""

    NAME = 'Playblast'
    LABEL = 'Playblasts the current scene.'

    def __init__(self, label_w=80):
        """Constructor.

        Args:
            label_w (int): label width in ui
        """
        super().__init__(label_w=label_w)

    def _add_custom_ui_elems(self):
        """Add custom ui elements."""
        super()._add_custom_ui_elems()

        # Read cams
        _cams = [str(_cam) for _cam in pom.find_cams()]
        if pom.find_render_cam():
            _cur_cam = pom.find_render_cam()
        elif pom.active_cam():
            _cur_cam = pom.active_cam()
        if _cur_cam:
            _cur_cam = str(_cur_cam)
        _LOGGER.debug('BUILD UI %s %s', _cur_cam, _cams)

        self.ui.add_separator()
        self.ui.add_combo_box(
            name='Camera', items=_cams, val=_cur_cam)
        self.ui.add_combo_box(
            name='Settings', items=['As is', 'Nice'])
        self.ui.add_combo_box(
            name='Res', items=['Full', 'Half', 'Quarter'], label='Resolution')
        self.ui.add_combo_box(
            name='OutputName', items=['blast', '<camera>'])

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
        super()._callback__Format()
        _en = False
        if self.template:
            _en = 'output_name' in self.template.keys()
        self.ui.OutputName.setEnabled(_en)

    def _set_camera(self):
        """Apply camera."""
        _cam = self.settings['camera']
        if _cam:
            _cam = pom.CCamera(_cam)
        if not _cam:
            _cam = pom.find_render_cam()
        assert isinstance(_cam, pom.CCamera)
        self.camera = _cam

    def export(  # pylint: disable=unused-argument
            self, notes=None, version_up=False, snapshot=True, save=True,
            bkp=True, camera=None, view=True, range_=None, format_='mp4',
            burnins=True, settings='As is', output_name='blast', res=None,
            force_replace=False, sanity_check_=False, force=False):
        """Blast current scene.

        Args:
            notes (str): export notes
            version_up (bool): version up after export
            snapshot (bool): take thumbnail snapshot on export
            save (bool): save work file on export
            bkp (bool): save bkp file
            camera (str): blast camera
            view (bool): view blast
            range_ (tuple): override range
            format_ (str): blast format (eg. mp4/jpg)
            burnins (bool): apply burnins (mov only)
            settings (str): apply settings (eg. "Nice", "As is")
            output_name (str): apply outputs name
                <camera> - uses camera name
            res (str): blast res (eg. "Full", "Half")
            force_replace (bool): replace existing without confirmation
            sanity_check_ (bool): apply sanity check
            force (bool): force blast with no confirmation dialogs
        """
        _out = m_pipe.blast(
            format_=format_, view=view, range_=range_, burnins=burnins,
            res=res, camera=camera, save=False, settings=settings,
            output_name=output_name, force=force or force_replace,
            update_metadata=False, update_cache=False)
        self.outputs = [_out]
