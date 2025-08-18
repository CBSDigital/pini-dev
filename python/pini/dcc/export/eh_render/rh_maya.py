"""Tools for managing maya render handlers."""

# pylint: disable=abstract-method

import logging
import types

from maya import cmds

from pini import pipe, farm, qt, icons
from pini.qt import QtWidgets
from pini.tools import helper, error
from pini.utils import strftime, Seq, cache_result, wrap_fn, TMP

from maya_pini import open_maya as pom
from maya_pini.utils import (
    render, to_audio, to_render_extn, find_cams)

from . import rh_base

_LOGGER = logging.getLogger(__name__)
_NO_WORK_ICON = icons.find('Red Circle')


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

    def build_ui(self):
        """Build basic render interface into the given layout."""
        super().build_ui(add_range='Frames', add_snapshot=False)

    def _add_custom_ui_elems(self):
        """Add custom ui elements."""
        self.ui.add_separator()

        # Read cams from scene
        _cams = find_cams(orthographic=False)
        _cam = pom.find_render_cam(catch=True)
        if not _cam:
            _r_cams = find_cams(renderable=True, orthographic=False)
            if _r_cams:
                _cam = _r_cams[0]
        if not _cam:
            _cam = _cams[0]
        _LOGGER.debug(' - CAM %s %s', _cam, _cam)
        self.ui.add_combo_box(
            name='Camera', items=_cams, val=_cam, label_w=60,
            save_policy=qt.SavePolicy.NO_SAVE)
        _LOGGER.debug(' - CAM UI %s', self.ui.Camera)
        self.ui.add_separator()


class CMayaLocalRender(CMayaRenderHandler):
    """Maya basic render handler.

    Facilities rendering to pipeline through the Render View window.
    """

    NAME = 'Maya Local Render'
    ICON = icons.find('Teapot')

    LABEL = (
        'Renders the current scene locally to disk using the maya interface.')

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


class CMayaFarmRender(CMayaRenderHandler):
    """Render handler which submits using the pini.farm API."""

    NAME = 'Maya Farm Render'
    ICON = farm.ICON

    LABEL = f'Renders the current scene to {farm.NAME}.'

    def __init__(self, priority=60, label_w=80):
        """Constructor.

        Args:
            priority (int): sort priority (higher priority handlers
                are sorted to top of option lists)
            label_w (int): label width in ui
        """
        super().__init__(priority=priority, label_w=label_w)

    def _add_custom_ui_elems(self):
        """Add custom ui elements."""
        self.ui.add_separator()
        self.ui.add_spin_box(name='Priority', val=50)
        self.ui.add_spin_box(name='ChunkSize', val=1, min_=1)
        self.ui.add_spin_box(name='MachineLimit', val=15)

        self.ui.add_check_box(name='StrictErrorChecking', val=True)

        self._build_limit_groups_elems()
        self.ui.add_separator()

        self._build_layers_elems()

        self.ui.add_check_box(
            name='HideImgPlanes', val=False,
            label='Hide image planes',
            tooltip='Hide image planes before submission')

    def _build_limit_groups_elems(self):
        """Build limit groups elements."""
        _btn = qt.CIconButton(
            parent=self.ui.parent, icon=icons.SELECT,
            name='LimitGrpsSelect')
        self.ui.LimitGrpsSelect = _btn

        self.ui.add_line_edit(
            name='LimitGrps', add_elems=[_btn], label='Limit groups')
        self.ui.LimitGrps.setEnabled(False)

    def _build_layers_elems(self):
        """Build render layer selection elements."""
        _work = pipe.cur_work()

        # Build layers section
        _label = qt.CLabel('Layers')
        _label.setFixedHeight(20)
        self.ui.layout.addWidget(_label)
        self.ui.Layers = qt.CListWidget()
        self.ui.Layers.setObjectName('Layers')
        self.ui.Layers.setSelectionMode(QtWidgets.QListView.ExtendedSelection)

        # Build layer items
        _items = []
        _select = []
        _fmt = to_render_extn() or 'jpg'
        for _lyr in pom.find_render_layers():
            if not _lyr.pass_name:
                continue
            if _work:
                _out = _work.to_output(
                    'render', output_name=_lyr.pass_name, extn=_fmt)
                _icon = helper.output_to_icon(_out)
            else:
                _icon = helper.obt_pixmap(_NO_WORK_ICON)
            _item = qt.CListWidgetItem(
                _lyr.pass_name, data=_lyr, icon=_icon)
            if _lyr.is_renderable():
                _select.append(_lyr)
            _items.append(_item)
        _LOGGER.debug(' - SELECT LAYERS %s', _select)
        self.ui.Layers.set_items(_items, select=_select)
        self.ui.Layers.setIconSize(qt.to_size(30))
        self.ui.Layers.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.MinimumExpanding)

        self.ui.layout.addWidget(self.ui.Layers)
        self.ui.layout.setStretch(self.ui.layout.count() - 1, 1)

        _signal = qt.widget_to_signal(self.ui.Layers)
        _signal.connect(self._callback__Layers)

    def _callback__LimitGrpsSelect(self):
        _LOGGER.info('CALLBACK LIMIT GROUPS SELECT')
        _cur_grps = self.ui.LimitGrps.text().split(',')
        _msg = (
            'Select limit groups for deadline.\n\n'
            'Hold down ctrl to select more than one group.')
        _grps = qt.multi_select(
            items=farm.find_limit_groups(),
            select=_cur_grps, multi=True, msg=_msg, title='Select groups')
        self.ui.LimitGrps.setText(','.join(_grps))

    def _callback__Layers(self):
        _sel_lyrs = self.ui.Layers.selected_datas()
        _LOGGER.debug('CALLBACK LAYERS %s', _sel_lyrs)
        for _lyr in pom.find_render_layers():
            _ren = _lyr in _sel_lyrs
            _LOGGER.debug(' - %s %d', _lyr, _ren)
            _lyr.set_renderable(_ren)

    def set_settings(self, *args, **kwargs):
        """Setup settings dict."""
        super().set_settings(
            *args, update_metadata=False, update_cache=False,
            bkp=True, **kwargs)

    def export(  # pylint: disable=unused-argument
            self, notes=None, version_up=True, camera=None, frames=None,
            render_=True, limit_grps=None, hide_img_planes=False, priority=50,
            machine_limit=15, chunk_size=1, strict_error_checking=True,
            force=False):
        """Execute render.

        Args:
            notes (str): export notes
            version_up (bool): version up after export
            camera (str): render camera
            frames (int list): list of frames to render
            render_ (bool): execute render (disable for debugging)
            limit_grps (str list): limit groups
            hide_img_planes (bool): hide image planes on submit
            priority (int): job priority (eg. 50)
            machine_limit (int): job machine limit (eg. 20 machines)
            chunk_size (int): job chunk size (frames to execute in one task)
            strict_error_checking (bool): apply deadline strict error checking
            force (bool): replace existing without confirmation
        """
        _lyrs = pom.find_render_layers(renderable=True)
        if not _lyrs:
            raise error.HandledError('No renderable layers')
        _cam = camera or pom.find_render_cam()
        _limit_grps = limit_grps
        if isinstance(_limit_grps, types.MethodType):
            _limit_grps = _limit_grps()

        pom.set_render_cam(_cam)

        # Apply hide image planes
        _reverts = []
        if hide_img_planes:
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

        _prepare_scene_for_render()

        self.submit_msg, _outs = farm.submit_maya_render(
            submit_=render_, force=True, result='msg/outs',
            metadata=self.metadata, frames=frames, camera=_cam,
            chunk_size=chunk_size, comment=notes, priority=priority,
            machine_limit=machine_limit, limit_groups=_limit_grps,
            strict_error_checking=strict_error_checking)

        for _revert in _reverts:
            _revert()

        return _outs

    def post_export(self):
        """Execute post export code."""
        _force = self.settings['force']
        super().post_export()
        if not _force:
            qt.notify(self.submit_msg, icon=farm.ICON, title='Render submitted')

    def exec_from_ui(self, **kwargs):
        """Execute this export using settings from ui."""
        _ui_kwargs = self.ui.to_kwargs()
        _ui_kwargs['limit_grps'] = self._read_limit_grps_from_ui
        super().exec_from_ui(ui_kwargs=_ui_kwargs, **kwargs)

    def _read_limit_grps_from_ui(self):
        """Read limit grps from interface.

        This is a provided as a function so that it can be executed at
        submission time, in case sanity check updates the limit groups.
        If a static value was provided, the ui updates wouldn't make it
        through to the exec or export kwargs.

        Returns:
            (str list): limit groups
        """
        _val = self.ui.LimitGrps.get_val()
        return _val.split(',') if _val else []

    @cache_result
    def to_icon(self):
        """Obtain icon for this render handler.

        Returns:
            (str): path to icon
        """
        return farm.ICON


def _prepare_scene_for_render():
    """Setup scene to prepare for render."""
    _ren = cmds.getAttr('defaultRenderGlobals.currentRenderer')
    if _ren == 'vray':
        cmds.setAttr('vraySettings.fileNamePadding', 4)
