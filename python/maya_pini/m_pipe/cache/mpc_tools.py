"""General cache tools."""

import logging

from pini.utils import single, passes_filter

from maya_pini import open_maya as pom

from . import mpc_ref, mpc_cam, mpc_cset

_LOGGER = logging.getLogger(__name__)


def find_cacheable(
        match=None, filter_=None, type_=None, output_name=None, extn='abc',
        catch=False):
    """Find a cacheable in the current scene.

    Args:
        match (str): match by name
        filter_ (str): label filter
        type_ (str): filter by cacheable type (ref/cam/cset)
        output_name (str): match by output name
        extn (str): extension for cacheable
        catch (bool): no error if no single cacheable matched

    Returns:
        (CPCacheable): matching cacheable
    """
    _cbls = find_cacheables(
        filter_=filter_, output_name=output_name, type_=type_, extn=extn)
    _LOGGER.debug(' - CBLS %s', _cbls)
    _cbl = single(_cbls, catch=True)
    if _cbl:
        return _cbl

    if isinstance(match, str):
        _match_s = match
    elif isinstance(match, pom.CReference):
        _match_s = match.namespace
    else:
        raise NotImplementedError(match)
    _LOGGER.debug(' - MATCH %s', _match_s)

    _matches = [
        _cbl for _cbl in _cbls
        if _match_s in (_cbl.output_name, _cbl.label, _cbl.node)]
    _LOGGER.debug(' - MATCHES %s', _matches)
    if len(_matches) == 1:
        return single(_matches)

    if catch:
        return None
    raise ValueError(_match_s)


def _read_cacheables(extn):
    """Read cacheables in the current scene.

    Args:
        extn (str): extension for cacheable

    Returns:
        (CCacheable list): cacheables
    """

    # Find all cacheables in scene
    _all = []
    for _ref in pom.find_refs():
        try:
            _cbl = mpc_ref.CPCacheableRef(_ref, extn=extn)
        except ValueError:
            continue
        _all.append(_cbl)
    _all += mpc_cam.find_cams(extn=extn)
    _all += mpc_cset.find_csets(extn=extn)
    _all.sort()
    _LOGGER.debug(' - FOUND %d CACHEABLES %s', len(_all), _all)

    return _all


def find_cacheables(
        extn='abc', filter_=None, task=None, type_=None, output_name=None):
    """Find cacheables in the current scene.

    Args:
        extn (str): type of cacheable
        filter_ (str): filter cacheables by label
        task (str): return only cacheables from the given task
        type_ (str): filter by cacheable type (ref/cam/cset)
        output_name (str): match by output name

    Returns:
        (CPCacheable list): cacheables
    """
    _LOGGER.debug('FIND CACHEABLES')

    if type_ not in (None, 'cset', 'cam', 'ref'):
        raise ValueError(type_)

    # Apply filters
    _cbls = []
    for _cbl in _read_cacheables(extn=extn):

        _LOGGER.debug(' - CHECK CACHEABLE %s', _cbl)

        if type_:
            raise NotImplementedError
        if not passes_filter(_cbl.label, filter_):
            continue
        if task and _cbl.task != task:
            continue
        if output_name and _cbl.output_name != output_name:
            continue

        # Check maps to asset correctly
        try:
            _out = _cbl.output
        except ValueError:
            _LOGGER.debug('   - FAILED TO BUILD OUTPUT')
            continue
        if not _out:
            _LOGGER.debug('   - MISSING OUTPUT')
            continue

        _cbls.append(_cbl)

    return _cbls
