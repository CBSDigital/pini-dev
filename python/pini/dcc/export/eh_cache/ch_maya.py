"""Tools for managing cache export handlers in maya."""

from pini import pipe

from maya_pini import m_pipe

from .. import eh_base


class CMayaCache(eh_base.CExportHandler):
    """Manages abc caching in maya."""

    NAME = 'Maya Cache'
    TYPE = 'Cache'
    LABEL = 'Exports abcs from maya'
    ACTION = 'CacheAbc'

    def cache(self, cacheables, version_up=None, farm=False, force=False):
        """Execute cache operation.

        Args:
            cacheables (Cacheable list): items to cache
            version_up (bool): version up after export
            farm (bool): cache using farm
            force (bool): replace existing without confirmation
        """
        self.pre_export()

        _work = pipe.CACHE.obt_cur_work()
        _outs = m_pipe.cache(
            cacheables, version_up=False, update_cache=False,
            farm=farm, force=force)
        self.post_export(work=_work, outs=_outs, version_up=version_up)

    def build_ui(self):
        """Build cache interface."""
