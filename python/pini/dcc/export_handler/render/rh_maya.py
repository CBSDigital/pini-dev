"""Tools for managing maya render handlers."""

import logging

from maya import cmds

from pini import pipe, farm, qt
from pini.qt import QtWidgets
from pini.tools import helper
from pini.utils import TMP_PATH, strftime, Seq, cache_result, wrap_fn

from maya_pini import open_maya as pom
from maya_pini.utils import render, find_render_cam, find_cams, to_audio

from . import rh_base

_LOGGER = logging.getLogger(__name__)


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


class CMayaRenderHandler(rh_base.CRenderHandler):
    """Base class for any maya render handler."""

    def build_ui(self, parent=None, layout=None):
        """Build basic render interface into the given layout.

        Args:
            parent (QWidget): parent widget
            layout (QLayout): layout to add widgets to
        """
        _LOGGER.debug('BUILD UI')
        super(CMayaRenderHandler, self).build_ui(parent=parent, layout=layout)

        # Read cams from scene
        _cams = find_cams(orthographic=False)
        _cam = find_render_cam(catch=True)
        if not _cam:
            _r_cams = find_cams(renderable=True, orthographic=False)
            if _r_cams:
                _cam = _r_cams[0]
        if not _cam:
            _cam = _cams[0]
        self.ui.Camera = self.add_combobox_elem(
            name='Camera', items=_cams, val=_cam)

    def render(self, frames=None):
        """Execute render - to be implemented in child class.

        Args:
            frames (int list): list of frames to render
        """
        raise NotImplementedError


class CMayaLocalRender(CMayaRenderHandler):
    """Maya basic render handler.

    Facilities rendering to pipeline through the Render View window.
    """

    NAME = 'Maya Local'

    description = (
        'Renders the current scene locally to disk using the maya interface')

    def build_ui(self, parent=None, layout=None):
        """Build basic render interface into the given layout.

        Args:
            parent (QWidget): parent widget
            layout (QLayout): layout to add widgets to
        """
        super(CMayaLocalRender, self).build_ui(parent=parent, layout=layout)

        self.ui.View = self.add_checkbox_elem(
            name='View', val=True,
            label='View render on completion')
        self.ui.Mov = self.add_checkbox_elem(
            name='Mov', val=False,
            label='Convert to mov')
        self.ui.Cleanup = self.add_checkbox_elem(
            name='Cleanup', val=True,
            label='Delete images after mov conversion')

    def _callback__Mov(self):
        self.ui.Cleanup.setVisible(self.ui.Mov.isChecked())

    def render(self, frames=None):
        """Execute render.

        Args:
            frames (int list): list of frames to render
        """
        _data = self.obtain_metadata()
        _cam = self.ui.Camera.currentText()
        _mov = self.ui.Mov.isChecked()
        _cleanup = self.ui.Cleanup.isChecked()

        # Determine output paths
        _work = pipe.cur_work()
        _output_name = _get_current_lyr()
        if _mov:
            if not _work.find_template('mov', catch=True):
                qt.notify(
                    'No mov template found in this job:\n\n{}\n\n'
                    'Unable to render.'.format(_work.job.path),
                    title='Warning', parent=self.parent)
                return
            _out = _work.to_output(
                'mov', output_name=_output_name, extn='mp4')
            _tmp_path = '{}/pini/render/PiniHelper_{}/render.%04d.jpg'.format(
                TMP_PATH, strftime('%y%m%d_%H%M%S'))
            _LOGGER.info('TMP PATH %s', _tmp_path)
            _out_seq = Seq(_tmp_path)
            _out.delete(wording='Replace')
        else:
            if not _work.find_template('render', catch=True):
                qt.notify(
                    'No render template found in this job:\n\n{}\n\n'
                    'Unable to render.'.format(_work.job.path),
                    title='Warning', parent=self.parent)
                return
            _fmt = cmds.getAttr(
                'defaultArnoldDriver.ai_translator', asString=True)
            _extn = {'jpeg': 'jpg'}.get(_fmt, _fmt)
            _out = _work.to_output(
                'render', output_name=_output_name, extn=_extn)
            _out_seq = _out

        # Execute render
        _work.save(reason='render')
        render(seq=_out_seq, frames=frames, camera=_cam)
        _out_seq.to_frame_file().copy_to(_work.image)
        if _mov:
            _compile_video_with_scene_audio(seq=_out_seq, video=_out)
            if _cleanup:
                _out_seq.delete(force=True)

        # Save metadata
        if _mov:
            _data.update(_out.read_metadata())
        else:
            _data['size'] = _out.size()
            _data['range'] = _out.to_range(force=True)
        _out.set_metadata(_data, force=True)

        if self.ui.View.isChecked():
            _out.view()

        # Update pini helper
        _helper = helper.DIALOG
        if _helper:
            _helper.jump_to(_work)
            assert _work == _helper.work
            _work = _helper.work
            _helper.ui.WWorkRefresh.click()


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


class CMayaFarmRender(CMayaRenderHandler):
    """Render handler which submits using the pini.farm API."""

    NAME = 'Maya Farm'
    ICON = farm.ICON

    description = 'Renders the current scene to {}.'.format(
        farm.NAME)

    def build_ui(self, parent=None, layout=None):
        """Build basic render interface into the given layout.

        Args:
            parent (QWidget): parent widget
            layout (QLayout): layout to add widgets to
        """
        _LOGGER.debug('BUILD UI')
        super(CMayaFarmRender, self).build_ui(parent=parent, layout=layout)

        self.add_separator_elem()

        self.ui.Comment = self.add_lineedit_elem(
            name='Comment', disable_save_settings=True)
        self.ui.Priority = self.add_spinbox_elem(
            name='Priority', val=50)
        self.add_separator_elem()

        # Build layers section
        _label = qt.CLabel('Layers')
        _label.setFixedHeight(20)
        self.layout.addWidget(_label)
        self.ui.Layers = qt.CListWidget()
        self.ui.Layers.setObjectName('Layers')
        self.ui.Layers.setSelectionMode(QtWidgets.QListView.ExtendedSelection)
        _work = pipe.cur_work()
        _items = []
        _select = []
        if cmds.objExists('defaultArnoldDriver'):
            _fmt = pom.CPlug('defaultArnoldDriver.aiTranslator').get_val()
            for _lyr in pom.find_render_layers():
                _out = _work.to_output(
                    'render', output_name=_lyr.pass_name, extn=_fmt)
                _icon = helper.output_to_icon(_out)
                _item = qt.CListWidgetItem(
                    _lyr.pass_name, data=_lyr, icon=_icon)
                if _lyr.is_renderable():
                    _select.append(_lyr)
                _items.append(_item)
        self.ui.Layers.set_items(_items, select=_select)
        self.ui.Layers.setIconSize(qt.to_size(30))
        self.ui.Layers.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding)
        self.layout.addWidget(self.ui.Layers)

        self.ui.HideImgPlanes = self.add_checkbox_elem(
            name='HideImgPlanes', val=False,
            label='Hide image planes',
            tooltip='Hide image planes before submission')
        self.add_separator_elem()

    def _callback__Layers(self):
        _sel_lyrs = self.ui.Layers.selected_datas()
        _LOGGER.debug('CALLBACK LAYERS %s', _sel_lyrs)
        for _lyr in pom.find_render_layers():
            _ren = _lyr in _sel_lyrs
            _LOGGER.debug(' - %s %d', _lyr, _ren)
            _lyr.set_renderable(_ren)

    def render(self, frames=None):
        """Launch deadline render ui.

        Args:
            frames (int list): list of frames to render
        """

        _cam = self.ui.Camera.currentText()
        pom.set_render_cam(_cam)

        # Apply hide image planes
        _reverts = []
        if self.ui.HideImgPlanes.isChecked():
            for _img_plane in pom.CMDS.ls(type='imagePlane'):
                _display_mode = _img_plane.plug['displayMode'].get_enum()
                _LOGGER.info(' - CHECKING IMAGE PLANE %s displayMode=%s',
                             _img_plane, _display_mode)
                if _display_mode == 'None':
                    continue
                _LOGGER.info('   - HIDING')
                _img_plane.plug['displayMode'].set_enum('None')
                _revert = wrap_fn(
                    _img_plane.plug['displayMode'].set_enum, _display_mode)
                _reverts.append(_revert)

        farm.submit_maya_render(
            frames=frames, camera=_cam,
            comment=self.ui.Comment.text(),
            priority=self.ui.Priority.value())

        for _revert in _reverts:
            _revert()

    @cache_result
    def to_icon(self):
        """Obtain icon for this render handler.

        Returns:
            (str): path to icon
        """
        return farm.ICON
