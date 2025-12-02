"""Tools for managing the local maya render handler."""

import logging

from maya import cmds

from pini import pipe, qt, icons
from pini.utils import strftime, Seq, TMP

from maya_pini import open_maya as pom
from maya_pini.utils import render, to_audio

from . import rhm_base

_LOGGER = logging.getLogger(__name__)


class CMayaLocalRender(rhm_base.CMayaRenderHandler):
    """Maya basic render handler.

    Facilitates rendering to pipeline through the Render View window.
    """

    NAME = 'Maya Local Render'
    ICON = icons.find('Teapot')

    LABEL = (
        'Renders the current scene locally to disk using the maya interface.')

    add_passes = False

    def _add_custom_ui_elems(self):
        """Build basic render interface into the given layout."""
        super()._add_custom_ui_elems()

        self.ui.add_check_box(
            name='View', val=True, label='View render')
        self.ui.add_check_box(
            name='Mov', val=False, label='Convert to mov')
        self.ui.add_check_box(
            name='Cleanup', val=True,
            label='Delete images after mov conversion')

        self._callback__Mov()

    def _callback__Mov(self):
        self.ui.Cleanup.setVisible(self.ui.Mov.isChecked())

    def export(  # pylint: disable=unused-argument
            self, notes=None, version_up=True, bkp=True, camera=None,
            frames=None, mov=None, view=None, render_=True, cleanup=True,
            format_=None, force=False):
        """Execute render.

        Args:
            notes (str): export notes
            version_up (bool): version up after export
            bkp (bool): save bkp file
            camera (str): render camera
            frames (int list): list of frames to render
            mov (bool): convert to mov
            view (bool): view render on completion
            render_ (bool): execute render (disable for debugging)
            cleanup (bool): cleanup tmp files (video only)
            format_ (str): render format (eg. jpg, exr)
            force (bool): replace existing without confirmation
        """
        _cam = camera or pom.find_render_cam()

        # Determine output paths
        _output_name = _get_current_lyr()
        if mov:
            if not self.work.find_template('mov', catch=True):
                qt.notify(
                    f'No mov template found in this job:'
                    f'\n\n{self.work.job.path}\n\nUnable to render.',
                    title='Warning', parent=self.ui.parent)
                return []
            _out = self.work.to_output(
                'mov', output_name=_output_name, extn='mp4')
            _t_stamp = strftime("%y%m%d_%H%M%S")
            _tmp_path = TMP.to_seq(
                f'pini/render/PiniHelper_{_t_stamp}/render.%04d.jpg')
            _LOGGER.info('TMP PATH %s', _tmp_path)
            _out_seq = Seq(_tmp_path)
        else:
            if not self.work.find_template('render', catch=True):
                qt.notify(
                    f'No render template found in this job:'
                    f'\n\n{self.work.job.path}\n\nUnable to render.',
                    title='Warning', parent=self.ui.parent)
                return []
            _fmt = format_ or cmds.getAttr(
                'defaultArnoldDriver.ai_translator', asString=True)
            _extn = {'jpeg': 'jpg'}.get(_fmt, _fmt)
            _out = self.work.to_output(
                'render', output_name=_output_name, extn=_extn)
            _out_seq = _out
        _out.delete(wording='replace', force=force)

        # Execute render
        if not render_:
            return []
        render(seq=_out_seq, frames=frames, camera=_cam)
        if mov:
            _compile_video_with_scene_audio(seq=_out_seq, video=_out)
            if cleanup:
                _out_seq.delete(force=True)
        _outs = [_out]
        if view:
            _out.view()

        _LOGGER.info(' - RENDER COMPLETE')
        return _outs

    def _update_metadata(self):
        """Update outputs metadata."""
        super()._update_metadata()
        for _out in self.outputs:
            if isinstance(_out, pipe.CPOutputVideo):
                _data = _out.metadata
                _data.update(_out.read_metadata())
                _out.set_metadata(_data, force=True)
            else:
                _out.add_metadata(size=_out.size())
                _out.add_metadata(range=_out.to_range(force=True))


def _compile_video_with_scene_audio(seq, video):
    """Compile a mov using current scene audio.

    Args:
        seq (Seq): input image sequence
        video (Video): video to compile
    """
    from pini import dcc

    _LOGGER.info('COMPILE MOV')

    _start, _end = seq.to_range(force=True)
    _fps = dcc.get_fps()

    _audio, _audio_offs = to_audio()
    seq.to_video(video, fps=_fps, audio=_audio, audio_offset=_audio_offs)


def _get_current_lyr():
    """Get current render layer.

    Returns:
        (str): layer name
    """
    _name = cmds.editRenderLayerGlobals(query=True, currentRenderLayer=True)
    if _name == 'defaultRenderLayer':
        return 'masterLayer'
    if _name.startswith('rs_'):
        return _name[3:]
    raise ValueError(_name)
