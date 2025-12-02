"""Tools for managing the maya farm render submission handler."""

import logging
import types

from maya import cmds

from pini import farm, qt, icons
from pini.tools import error
from pini.utils import cache_result, wrap_fn

from maya_pini import open_maya as pom

from . import rhm_layer, rhm_base

_LOGGER = logging.getLogger(__name__)


class CMayaFarmRender(rhm_base.CMayaRenderHandler):
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

    def find_passes(self):
        """Find passes in the current scene.

        Returns:
            (CRenderLayer list): layers
        """
        return [
            rhm_layer.CRenderLayer(_lyr) for _lyr in pom.find_render_layers()]

    def _add_custom_ui_elems(self):
        """Add custom ui elements."""
        super()._add_custom_ui_elems()

        # self.ui.add_separator()
        self.ui.add_spin_box(name='Priority', val=50)
        self.ui.add_spin_box(name='ChunkSize', val=1, min_=1)
        self.ui.add_spin_box(name='MachineLimit', val=15)

        # self.ui.add_separator()
        self.ui.add_check_box(name='StrictErrorChecking', val=True)
        self.ui.add_check_box(
            name='HideImgPlanes', val=False,
            label='Hide image planes',
            tooltip='Hide image planes before submission')
        self._build_limit_groups_elems()

    def _build_limit_groups_elems(self):
        """Build limit groups elements."""
        _btn = qt.CIconButton(
            parent=self.ui.parent, icon=icons.SELECT, name='LimitGrpsSelect')
        self.ui.LimitGrpsSelect = _btn

        self.ui.add_line_edit(
            name='LimitGrps', add_elems=[_btn], label='Limit groups')
        self.ui.LimitGrps.setEnabled(False)

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

    def set_settings(self, *args, **kwargs):
        """Setup settings dict."""
        super().set_settings(
            *args, update_metadata=False, update_cache=False,
            bkp=True, **kwargs)

    def export(  # pylint: disable=unused-argument
            self, passes, notes=None, version_up=True, camera=None, frames=None,
            render_=True, limit_grps=None, hide_img_planes=False, priority=50,
            machine_limit=15, chunk_size=1, strict_error_checking=True,
            force=False):
        """Execute render.

        Args:
            passes (CRenderLayer list): layers to render
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
        _lyrs = [_pass.node for _pass in passes]

        pom.set_render_cam(_cam)

        _reverts = _prepare_scene_for_render(hide_img_planes=hide_img_planes)

        self.submit_msg, _outs = farm.submit_maya_render(
            submit_=render_, force=True, result='msg/outs', layers=_lyrs,
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


def _apply_hide_img_planes():
    """Hide image planes.

    Returns:
        (fn list): functions to revert scene
    """
    _LOGGER.debug('APPLY HIDE IMG PLANES')
    _reverts = []

    # Hide image planes
    for _img_plane in pom.CMDS.ls(type='imagePlane'):
        _display_mode = _img_plane.plug['displayMode'].get_enum()
        _LOGGER.info(' - CHECKING IMAGE PLANE %s displayMode=%s',
                     _img_plane, _display_mode)
        if _display_mode == 'None':
            continue
        _LOGGER.info('   - HIDING %s', _img_plane)
        _img_plane.plug['displayMode'].set_enum('None')
        _revert = wrap_fn(
            _img_plane.plug['displayMode'].set_enum, _display_mode)
        _reverts.append(_revert)

    # Hide rs dome light backdrops
    _ren = cmds.getAttr('defaultRenderGlobals.currentRenderer')
    if _ren == 'redshift':
        for _dome in pom.CMDS.ls(type='RedshiftDomeLight'):
            _plate = _dome.plug['backPlateEnabled']
            if not _plate.get_val():
                continue
            _LOGGER.debug(' - HIDING %s', _dome)
            _plate.set_val(False)
            _reverts.append(wrap_fn(_plate.set_val, True))

    return _reverts


def _prepare_scene_for_render(hide_img_planes=False):
    """Setup scene to prepare for render.

    Args:
        hide_img_planes (bool): hide image planes on render

    Returns:
        (fn list): functions to revert scene
    """
    _reverts = []

    # Apply vray padding to avoid badly named files
    _ren = cmds.getAttr('defaultRenderGlobals.currentRenderer')
    if _ren == 'vray':
        cmds.setAttr('vraySettings.fileNamePadding', 4)

    if hide_img_planes:
        _reverts += _apply_hide_img_planes()

    return _reverts
