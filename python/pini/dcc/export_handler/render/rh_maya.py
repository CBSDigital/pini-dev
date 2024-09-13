"""Tools for managing maya render handlers."""

import logging

from maya import cmds

from pini import pipe, farm, qt, icons
from pini.qt import QtWidgets
from pini.tools import helper, error, sanity_check
from pini.utils import TMP_PATH, strftime, Seq, cache_result, wrap_fn

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
        _cam = pom.find_render_cam(catch=True)
        if not _cam:
            _r_cams = find_cams(renderable=True, orthographic=False)
            if _r_cams:
                _cam = _r_cams[0]
        if not _cam:
            _cam = _cams[0]
        _LOGGER.debug(' - CAM %s %s', _cam, _cam)
        self.ui.Camera = self.add_combobox_elem(
            name='Camera', items=_cams, val=_cam, label_w=60,
            disable_save_settings=True)
        _LOGGER.debug(' - CAM UI %s', self.ui.Camera)
        self.add_separator_elem()

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

    NAME = 'Maya Local Arnold'

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

        self.layout.addStretch()

    def _callback__Mov(self):
        self.ui.Cleanup.setVisible(self.ui.Mov.isChecked())

    def render(self, frames=None):
        """Execute render.

        Args:
            frames (int list): list of frames to render
        """
        _data = self.build_metadata()
        _cam = self.ui.Camera.currentText()
        _mov = self.ui.Mov.isChecked()
        _cleanup = self.ui.Cleanup.isChecked()

        # Determine output paths
        _work = pipe.CACHE.cur_work
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
        if _mov:
            _compile_video_with_scene_audio(seq=_out_seq, video=_out)
            if _cleanup:
                _out_seq.delete(force=True)
        if self.ui.View.isChecked():
            _out.view()

        # Save metadata
        if _mov:
            _data.update(_out.read_metadata())
        else:
            _data['size'] = _out.size()
            _data['range'] = _out.to_range(force=True)
        _out.set_metadata(_data, force=True)

        # Update pipeline
        if pipe.MASTER == 'shotgrid':
            from pini.pipe import shotgrid
            shotgrid.create_pub_file(_out)
        _work.update_outputs()


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

    def __init__(self, priority=60, label_w=80):
        """Constructor.

        Args:
            priority (int): sort priority (higher priority handlers
                are sorted to top of option lists)
            label_w (int): label width in ui
        """
        super(CMayaFarmRender, self).__init__(
            priority=priority, label_w=label_w)

    def build_ui(self, parent=None, layout=None):
        """Build basic render interface into the given layout.

        Args:
            parent (QWidget): parent widget
            layout (QLayout): layout to add widgets to
        """
        _LOGGER.debug('BUILD UI')
        super(CMayaFarmRender, self).build_ui(parent=parent, layout=layout)

        self.ui.Comment = self.add_lineedit_elem(
            name='Comment', disable_save_settings=True)
        self.ui.Priority = self.add_spinbox_elem(
            name='Priority', val=50)
        self.ui.ChunkSize = self.add_spinbox_elem(
            name='ChunkSize', val=1, min_=1)
        self.ui.MachineLimit = self.add_spinbox_elem(
            name='MachineLimit', val=15)
        self._build_limit_groups_elems()
        self.add_separator_elem()

        self._build_layers_elems()

        self.ui.HideImgPlanes = self.add_checkbox_elem(
            name='HideImgPlanes', val=False,
            label='Hide image planes',
            tooltip='Hide image planes before submission')
        self.ui.VersionUp = self.add_checkbox_elem(
            name='VersionUp', val=False,
            label='Version up on render',
            tooltip='Version up scene file after render submitted')
        self.add_separator_elem()

    def _build_limit_groups_elems(self):
        """Build limit groups elements."""
        _btn = QtWidgets.QPushButton(self.parent)
        _btn.setFixedWidth(20)
        _btn.setFixedHeight(20)
        _btn.setIconSize(qt.to_size(20))
        _btn.setIcon(qt.to_icon(icons.SELECT))
        _btn.setFlat(True)
        _btn.clicked.connect(self._callback__LimitGroupsSelect)
        self.ui.LimitGroupsSelect = _btn

        self.ui.LimitGroups = self.add_lineedit_elem(
            name='LimitGroups', add_elems=[_btn])
        self.ui.LimitGroups.setEnabled(False)

    def _build_layers_elems(self):
        """Build render layer selection elements."""
        _work = pipe.cur_work()

        # Build layers section
        _label = qt.CLabel('Layers')
        _label.setFixedHeight(20)
        self.layout.addWidget(_label)
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
        self.ui.Layers.set_items(_items, select=_select)
        self.ui.Layers.setIconSize(qt.to_size(30))
        self.ui.Layers.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.MinimumExpanding)

        self.layout.addWidget(self.ui.Layers)
        self.layout.setStretch(self.layout.count()-1, 1)

        _signal = qt.widget_to_signal(self.ui.Layers)
        _signal.connect(self._callback__Layers)

    def _callback__LimitGroupsSelect(self):
        _LOGGER.info('CALLBACK LIMIT GROUPS SELECT')
        _cur_grps = self.ui.LimitGroups.text().split(',')
        _grps = qt.multi_select(
            items=farm.find_limit_groups(),
            select=_cur_grps, multi=True,
            msg='Select limit groups:', title='Select groups')
        self.ui.LimitGroups.setText(','.join(_grps))

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
        _work = pipe.cur_work()
        if not _work:
            raise error.HandledError('No current work')
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

        _prepare_scene_for_render()
        _checks_data = sanity_check.launch_export_ui(action='render')

        farm.submit_maya_render(
            checks_data=_checks_data,
            frames=frames, camera=_cam,
            chunk_size=self.ui.ChunkSize.value(),
            comment=self.ui.Comment.text(),
            priority=self.ui.Priority.value(),
            machine_limit=self.ui.MachineLimit.value(),
            limit_groups=self.ui.LimitGroups.text().split(','),
            version_up=self.ui.VersionUp.isChecked())

        for _revert in _reverts:
            _revert()

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
