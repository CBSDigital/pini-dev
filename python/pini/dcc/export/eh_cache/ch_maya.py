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

    def exec(
            self, cacheables, notes=None, version_up=None, use_farm=False,
            range_=None, force=False):
        """Execute cache operation.

        Args:
            cacheables (Cacheable list): items to cache
            notes (str): cache notes
            version_up (bool): version up after export
            use_farm (bool): cache using farm
            range_ (tuple): override cache range
            force (bool): replace existing without confirmation
        """
        raise NotImplementedError

    def _add_custom_ui_elems(self):
        """Add custom elements for this cache handler."""

    def build_ui(self):
        """Build cache interface."""
        _LOGGER.debug('BUILD UI')

        self.ui.add_range_elems()

        self.ui.add_list_widget(name='Cacheables')
        self.ui.add_spin_box('Substeps', 1, min_=1, max_=20)
        if farm.IS_AVAILABLE:
            self.ui.add_check_box('UseFarm', False)
        self.ui.add_separator()
        self._add_custom_ui_elems()
        self.ui.add_footer_elems()
        self.ui.add_separator()
        self.ui.add_exec_button('Cache')
        super().build_ui()

    def _redraw__Cacheables(self):
        _LOGGER.debug('REDRAW Cacheables')
        _cbls = m_pipe.find_cacheables()
        _items = [
            qt.CListWidgetItem(_cbl.label, icon=_cbl.to_icon(), data=_cbl)
            for _cbl in _cbls
        ]
        self.ui.Cacheables.set_items(_items, emit=False)
        self.ui.Cacheables.load_setting()

    def _callback__Cacheables(self):
        self.ui.Cache.setEnabled(bool(self.ui.Cacheables.selected_datas()))

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
    ICON = icons.find('Input Latin Lowercase')

    def exec(
            self, cacheables, notes=None, version_up=None, snapshot=True,
            use_farm=False, range_=None, substeps=1, format_='Ogawa',
            uv_write=True, world_space=True, renderable_only=True,
            force=False):
        """Execute cache operation.

        Args:
            cacheables (Cacheable list): items to cache
            notes (str): cache notes
            version_up (bool): version up after export
            snapshot (bool): take thumbnail snapshot on export
            use_farm (bool): cache using farm
            range_ (tuple): override cache range
            substeps (int): substeps per frame
            format_ (str): abc format (eg. Ogawa/HDF5)
            uv_write (bool): write uvs to abc
            world_space (bool): write in world space
            renderable_only (bool): write renderable geometry only
            force (bool): replace existing without confirmation
        """
        self.init_export(notes=notes, force=force)
        _outs = m_pipe.cache(
            cacheables, version_up=False, update_cache=False,
            use_farm=use_farm, checks_data=self.metadata['sanity_check'],
            range_=range_, format_=format_, uv_write=uv_write,
            world_space=world_space, renderable_only=renderable_only,
            step=1 / substeps, force=force, extn='abc')
        self.post_export(
            outs=_outs, version_up=version_up, snapshot=snapshot)

    def _add_custom_ui_elems(self):
        """Add custom elements for this cache handler."""
        self.ui.add_combo_box('Format', ['Ogawa', 'HDF5'])
        self.ui.add_check_box('UvWrite', label='Write UVs')
        self.ui.add_check_box('WorldSpace')
        self.ui.add_check_box('RenderableOnly')
        self.ui.add_separator()


class CMayaFbxCache(CMayaCache):
    """Manages fbx caching in maya."""

    NAME = 'Maya Fbx Cache'
    LABEL = 'Exports fbxs from maya'
    ACTION = 'FbxCache'
    ICON = icons.find('Worm')

    def exec(
            self, cacheables, notes=None, version_up=None, snapshot=True,
            use_farm=False, range_=None, substeps=1, format_='FBX201600',
            force=False):
        """Execute cache operation.

        Args:
            cacheables (Cacheable list): items to cache
            notes (str): cache notes
            version_up (bool): version up after export
            snapshot (bool): take thumbnail snapshot on export
            use_farm (bool): cache using farm
            range_ (tuple): override cache range
            substeps (int): substeps per frame
            format_ (str): abc format (eg. Ogawa/HDF5)
            force (bool): replace existing without confirmation
        """
        self.init_export(notes=notes, force=force)
        _outs = m_pipe.cache(
            cacheables, version_up=False, update_cache=False,
            use_farm=use_farm, checks_data=self.metadata['sanity_check'],
            range_=range_, format_=format_,
            step=1 / substeps, force=force, extn='fbx')
        self.post_export(
            outs=_outs, version_up=version_up, snapshot=snapshot)

    def _add_custom_ui_elems(self):
        """Add custom elements for this cache handler."""
        self.ui.add_combo_box('Format', ['FBX201600'])

        self.ui.add_separator()
