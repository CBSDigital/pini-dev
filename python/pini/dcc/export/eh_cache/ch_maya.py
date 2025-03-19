"""Tools for managing cache export handlers in maya."""

from .. import eh_base


class CMayaCache(eh_base.CExportHandler):
    """Manages abc caching in maya."""

    NAME = 'Maya Cache'
    LABEL = 'Exports abcs from maya'
    ACTION = 'CacheAbc'

    # def
