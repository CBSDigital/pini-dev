"""Tools for managing cache export handlers in maya."""

import logging
import pprint

from maya import cmds

from pini import qt, farm, icons
from pini.utils import wrap_fn

from maya_pini import m_pipe

from .. import eh_base

_LOGGER = logging.getLogger(__name__)


class CMayaCache(eh_base.CExportHandler):
    """Manages abc caching in maya."""

    TYPE = 'Cache'

    def _add_custom_ui_elems(self):
        """Add custom elements for this cache handler."""

    def build_ui(self):
        """Build cache interface."""
        _LOGGER.debug('BUILD UI')
        self._build_ui_header(add_range=True)

        self.ui.add_list_widget(name='Cacheables')
        self.ui.add_spin_box('Substeps', 1, min_=1, max_=20)
        if farm.IS_AVAILABLE:
            self.ui.add_check_box('UseFarm', False)
        self._add_custom_ui_elems()
        self._build_ui_footer()

    def set_settings(self, **kwargs):
        """Setup settings dict."""
        super().set_settings(**kwargs)

        # Handled in m_pipe to allow embed asset path
        if not self.settings['update_metadata']:
            raise NotImplementedError

        self.settings['update_metadata'] = False

    def _redraw__Cacheables(self):
        _LOGGER.debug('REDRAW Cacheables')
        _items = []
        for _cbl in m_pipe.find_cacheables():
            _icon = qt.CPixmap(30, 30)
            _icon.fill('Transparent')
            _icon.draw_overlay(
                _cbl.to_icon(), _icon.center(), size=20, anchor='C')
            _item = qt.CListWidgetItem(_cbl.label, icon=_icon, data=_cbl)
            _items.append(_item)
        self.ui.Cacheables.set_items(_items, select=_items, emit=False)
        self.ui.Cacheables.load_setting()

    def _callback__Cacheables(self):
        self.ui.Execute.setEnabled(bool(self.ui.Cacheables.selected_datas()))

    def _context__Cacheables(self, menu):
        _cbl = self.ui.Cacheables.selected_data()
        _out = None
        if _cbl.output:
            _out = _cbl.output
        if _out:
            menu.add_action(
                'Print metadata', wrap_fn(pprint.pprint, _out.metadata))
        menu.add_action(
            'Select', wrap_fn(cmds.select, _cbl.node))


class CMayaAbcCache(CMayaCache):
    """Manages abc caching in maya."""

    NAME = 'Maya Abc Cache'
    LABEL = 'Exports abcs from maya'
    ACTION = 'AbcCache'
    ICON = icons.find('Input Latin Letters')

    def export(  # pylint: disable=unused-argument
            self, cacheables, notes=None, version_up=None, snapshot=True,
            save=True, bkp=True, use_farm=False, range_=None, substeps=1,
            format_='Ogawa', uv_write=True, world_space=True,
            renderable_only=True, force=False):
        """Execute cache operation.

        Args:
            cacheables (Cacheable list): items to cache
            notes (str): export notes
            version_up (bool): version up after export
            snapshot (bool): take thumbnail snapshot on export
            save (bool): save work file on export
            bkp (bool): save bkp file
            use_farm (bool): cache using farm
            range_ (tuple): override cache range
            substeps (int): substeps per frame
            format_ (str): abc format (eg. Ogawa/HDF5)
            uv_write (bool): write uvs to abc
            world_space (bool): write in world space
            renderable_only (bool): write renderable geometry only
            force (bool): replace existing without confirmation
        """
        self.outputs = m_pipe.cache(
            cacheables, version_up=False, update_cache=False,
            use_farm=use_farm, update_metadata=True,
            range_=range_, format_=format_, uv_write=uv_write,
            world_space=world_space, renderable_only=renderable_only,
            step=1 / substeps, force=force, extn='abc', save=False,
            checks_data=self.metadata['sanity_check'])

    def _add_custom_ui_elems(self):
        """Add custom elements for this cache handler."""
        self.ui.add_separator()
        self.ui.add_combo_box('Format', ['Ogawa', 'HDF5'])
        self.ui.add_check_box('UvWrite', label='Write UVs')
        self.ui.add_check_box('WorldSpace')
        self.ui.add_check_box('RenderableOnly')


class CMayaFbxCache(CMayaCache):
    """Manages fbx caching in maya."""

    NAME = 'Maya Fbx Cache'
    LABEL = 'Exports fbxs from maya'
    ACTION = 'FbxCache'
    ICON = icons.find('Worm')
    COL = 'LightPink'

    def export(  # pylint: disable=unused-argument
            self, cacheables, notes=None, version_up=None, snapshot=True,
            save=True, bkp=True, progress=False, use_farm=False, range_=None,
            substeps=1, format_='FBX201600', force=False):
        """Execute cache operation.

        Args:
            cacheables (Cacheable list): items to cache
            notes (str): cache notes
            version_up (bool): version up after export
            snapshot (bool): take thumbnail snapshot on export
            save (bool): save work file on export
            bkp (bool): save bkp file
            progress (bool): show cache progress
            use_farm (bool): cache using farm
            range_ (tuple): override cache range
            substeps (int): substeps per frame
            format_ (str): abc format (eg. Ogawa/HDF5)
            force (bool): replace existing without confirmation
        """
        self.outputs = m_pipe.cache(
            cacheables, version_up=False, update_cache=False, extn='fbx',
            use_farm=use_farm, checks_data=self.metadata['sanity_check'],
            range_=range_, format_=format_, step=1 / substeps, save=False,
            force=force, update_metadata=True)

    def _add_custom_ui_elems(self):
        """Add custom elements for this cache handler."""
        self.ui.add_combo_box('Format', ['FBX201600'])
        self.ui.add_separator()
