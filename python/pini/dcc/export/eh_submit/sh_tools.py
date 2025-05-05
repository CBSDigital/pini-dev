"""Tools for managing public submit functions."""

import logging

from pini import dcc
from pini.tools import release

_LOGGER = logging.getLogger(__name__)


@release.transfer_kwarg_docs(
    mod='pini.dcc.export', func='CBasicSubmitter.export')
def submit(render, **kwargs):
    """Farm submit current scene.

    Args:
        render (CPOutputBase): render to submit
    """
    _LOGGER.info('SUBMIT')
    _exporter = dcc.find_export_handler('BasicSubmitter')
    _LOGGER.info(' - EXPORTER %s', _exporter)
    _exporter.exec(render, **kwargs)
