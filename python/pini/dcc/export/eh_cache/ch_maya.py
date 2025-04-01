"""Tools for managing cache export handlers in maya."""

from maya_pini import m_pipe

from .. import eh_base


class CMayaAbcCache(eh_base.CExportHandler):
    """Manages abc caching in maya."""

    NAME = 'Maya Abc Cache'
    TYPE = 'Cache'
    LABEL = 'Exports abcs from maya'
    ACTION = 'AbcCache'

    def cache(
            self, cacheables, notes=None, version_up=None, farm=False,
            force=False):
        """Execute cache operation.

        Args:
            cacheables (Cacheable list): items to cache
            notes (str): cache notes
            version_up (bool): version up after export
            farm (bool): cache using farm
            force (bool): replace existing without confirmation
        """
        self.init_export(notes=notes, force=force)
        _outs = m_pipe.cache(
            cacheables, version_up=False, update_cache=False,
            use_farm=farm, checks_data=self.metadata['sanity_check'],
            force=force)
        self.post_export(outs=_outs, version_up=version_up)

    def build_ui(self):
        """Build cache interface."""
