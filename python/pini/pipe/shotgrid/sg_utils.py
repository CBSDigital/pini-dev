"""General utilities for shotgrid integration."""

import logging

from pini import icons, pipe
from pini.utils import single

_LOGGER = logging.getLogger(__name__)
ICON = icons.find("Spiral Notepad")


def output_to_work(output):
    """Obtain work file for the given output.

    Args:
        output (CPOutput): output to find work file for

    Returns:
        (CPWork): work file
    """
    _LOGGER.debug('OUTPUT TO WORK %s', output.path)

    # Try metadata
    if 'src' in output.metadata:
        _path = pipe.map_path(output.metadata['src'])
        _work = pipe.CPWork(_path)
        return pipe.CACHE.obt_work(_work)
    _LOGGER.debug(' - NO SRC IN METADATA')

    # Try mapping
    _mapped_work = output.to_work()
    _LOGGER.debug(' - MAPPED WORK %s', _mapped_work)
    if _mapped_work and _mapped_work.exists():
        return _mapped_work
    _LOGGER.debug(' - MAPPED DOES NOT EXIST')

    # Try search
    _search_work = single(
        output.entity.find_works(
            task=output.task, ver_n=output.ver_n, tag=output.tag),
        catch=True)
    if _search_work:
        return _search_work

    return None
