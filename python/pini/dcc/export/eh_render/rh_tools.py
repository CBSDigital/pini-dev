"""Tools for managing public render functions."""

import logging

from pini import dcc
from pini.tools import release

_LOGGER = logging.getLogger(__name__)
_DCC = (dcc.NAME or '').capitalize()


@release.transfer_kwarg_docs(
    mod='pini.dcc.export', func=f'C{_DCC}FarmRender.export')
def farm_render(**kwargs):
    """Farm render current scene."""
    _LOGGER.info('FARM RENDER')
    _exporter = dcc.find_export_handler('FarmRender')
    _LOGGER.info(' - EXPORTER %s', _exporter)
    return _exporter.exec(**kwargs)


@release.transfer_kwarg_docs(
    mod='pini.dcc.export', func=f'C{_DCC}LocalRender.export')
def local_render(**kwargs):
    """Local render current scene."""
    _LOGGER.info('LOCAL RENDER')
    _exporter = dcc.find_export_handler('LocalRender')
    _LOGGER.info(' - EXPORTER %s', _exporter)
    return _exporter.exec(**kwargs)
