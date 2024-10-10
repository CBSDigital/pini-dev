"""General utilities for managing the shotgrid cache."""

import datetime
import logging

from pini.utils import cache_result, strftime, to_time_f, nice_age

_LOGGER = logging.getLogger(__name__)


def to_cache_file(range_, entity_type, job, fields, ver_n=None):
    """Build cache file path for the given range.

    Args:
        range_ (SGCRange): time range
        entity_type (str): entity being requested
        job (SGCJob): job being queried
        fields (str tuple): fields being requested
        ver_n (int): append version token - this can be used to regenerate
            caches if the data format is changed in the code

    Returns:
        (File): cache file
    """
    from pini import pipe

    _fields_key = to_fields_key(tuple(fields))
    _ver_key = '' if ver_n is None else '_V{:d}'.format(ver_n)

    if not range_.end_t:
        _d_token = strftime('T%y%m%d_%H%M%S', range_.start_t)
        return job.to_cache_dir().to_file(
            'snapshot_{}_{}_F{}_P{:d}{}.pkl'.format(
                entity_type, _d_token, _fields_key, pipe.VERSION, _ver_key))

    if range_.end_t >= datetime.datetime.today():
        return None

    _dur = to_time_f(range_.end_t) - to_time_f(range_.start_t)
    _LOGGER.debug(' - DUR %s', nice_age(_dur))
    if 52*7*24*60*60 <= _dur <= 53*7*24*60*60:
        _d_token = strftime('Y%y', range_.start_t)
    elif 4*7*24*60*60 <= _dur <= 5*7*24*60*60:
        _d_token = strftime('M%y%m', range_.start_t)
    elif 7*24*60*60 - 1*60*60 <= _dur <= 7*24*60*60 + 1*60*60:
        _d_token = strftime('W%y%m%d', range_.start_t)
    elif 23*60*60 <= _dur <= 25*60*60:
        _d_token = strftime('D%y%m%d', range_.start_t)
    else:
        raise ValueError(nice_age(_dur))
    return job.to_cache_dir().to_file(
        'region_{}_{}_F{}_P{:d}{}.pkl'.format(
            entity_type, _d_token, _fields_key, pipe.VERSION, _ver_key))


@cache_result
def to_fields_key(fields):
    """Build a cache file fields key for the given fields.

    This is a unique key based on the requested fields.

    Args:
        fields (str tuple): requested fields

    Returns:
        (str): fields key
    """
    _map = {
        'code': 'C',
        'created_at': 'Cr',
        'department': 'D',
        'email': 'Em',
        'entity': 'En',
        'entity_type': 'Et',
        'login': 'L',
        'list_order': 'Lo',
        'name': 'Na',
        'path': 'P',
        'path_cache': 'Pc',
        'sg_asset_type': 'At',
        'sg_frame_rate': 'Fr',
        'sg_has_3d': '3d',
        'sg_head_in': 'Hi',
        'sg_path_to_movie': 'Mp',
        'sg_sequence': 'Se',
        'sg_short_name': 'Sn',
        'sg_status_list': 'Sl',
        'sg_status': 'S',
        'short_name': 'Sh',
        'step': 'St',
        'tank_name': 'Tn',
        'updated_at': 'Ua',
        'updated_by': 'Ub',
    }
    assert len(set(_map.keys())) == len(set(_map.values()))
    return 'F'+''.join(_map[_field] for _field in sorted(fields))
