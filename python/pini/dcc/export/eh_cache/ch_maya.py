"""Tools for managing cache export handlers in maya."""

import logging


from pini import icons

from . import ch_base

_LOGGER = logging.getLogger(__name__)


class CMayaCache(ch_base.CCacheHandler):
    """Manages abc caching in maya."""

    TYPE = 'Cache'

    block_update_metadata = False
    add_substeps = True
    add_use_farm = False


class CMayaAbcCache(CMayaCache):
    """Manages abc caching in maya."""

    NAME = 'Maya Abc Cache'
    LABEL = 'Exports abcs from maya'
    ACTION = 'AbcCache'
    ICON = icons.find('Input Latin Letters')

    block_update_metadata = True
    add_use_farm = True

    def find_cacheables(self):
        """Find cacheables in the current scene.

        Returns:
            (CCacheable list): cacheables
        """
        from maya_pini import m_pipe
        return m_pipe.find_cacheables(extn='abc')

    def export(  # pylint: disable=unused-argument
            self, cacheables=None, notes=None, version_up=None, snapshot=True,
            save=True, bkp=True, use_farm=False, range_=None, substeps=1,
            format_='Ogawa', uv_write=True, world_space=True,
            update_cache=True, renderable_only=True, checks_data=None,
            force=False):
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
            update_cache (bool): update pipe cache
            renderable_only (bool): write renderable geometry only
            checks_data (dict): apply sanity checks data
            force (bool): replace existing without confirmation
        """
        from maya_pini import m_pipe
        return m_pipe.cache(
            cacheables, version_up=False, update_cache=False,
            use_farm=use_farm, update_metadata=True,
            range_=range_, format_=format_, uv_write=uv_write,
            world_space=world_space, renderable_only=renderable_only,
            step=1 / substeps, force=True, extn='abc', save=False,
            checks_data=checks_data or self.metadata['sanity_check'])

    def _add_custom_ui_elems(self):
        """Add custom elements for this cache handler."""
        self.ui.add_separator()
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

    block_update_metadata = True
    add_use_farm = True

    def export(  # pylint: disable=unused-argument
            self, cacheables, notes=None, version_up=None, snapshot=True,
            save=True, bkp=True, progress=False, use_farm=False, range_=None,
            substeps=1, format_='FBX201600',
            update_cache=True, checks_data=None, force=False):
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
            update_cache (bool): update pipe cache
            checks_data (dict): apply sanity checks data
            force (bool): replace existing without confirmation
        """
        from maya_pini import m_pipe
        return m_pipe.cache(
            cacheables, version_up=False, extn='fbx',
            use_farm=use_farm, update_metadata=True,
            checks_data=checks_data or self.metadata['sanity_check'],
            range_=range_, format_=format_, step=1 / substeps, save=False,
            update_cache=False, force=force)

    def find_cacheables(self):
        """Find cacheables in the current scene.

        Returns:
            (CCacheable list): cacheables
        """
        from maya_pini import m_pipe
        return m_pipe.find_cacheables(extn='fbx')

    def _add_custom_ui_elems(self):
        """Add custom elements for this cache handler."""
        self.ui.add_separator()
        self.ui.add_combo_box(
            'Format', ['FBX201300', 'FBX201600'], val='FBX201600')


class CMayaCrvsCache(CMayaCache):
    """Manages fbx caching in maya."""

    NAME = 'Maya Curves Cache'
    LABEL = 'Exports anim curves from maya'
    ACTION = 'CurvesCache'
    ICON = icons.find('Performing Arts')
    COL = 'Red'

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
        from maya_pini import m_pipe
        return m_pipe.export_anim_curves(
            cacheables, range_=range_, force=force)

    def _update_metadata(self, content_type='CurvesMb'):
        """Update metadata.

        Args:
            content_type (str): apply content type
        """
        super()._update_metadata(content_type=content_type)
