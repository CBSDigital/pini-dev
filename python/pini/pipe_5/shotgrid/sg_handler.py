"""Tools for managing the shotgrid handler.

This managing iteraction with the shotgrid via the shotgun_api3 api.
"""

import logging
import os
import pprint
import time

import shotgun_api3

from pini import pipe
from pini.utils import (
    plural, basic_repr, error_on_file_system_disabled, Video)

from . import sg_utils

_SG_KEY = os.environ.get('PINI_SG_KEY')
_SG_SCRIPT_NAME = os.environ.get('PINI_SG_SCRIPT', 'PiniAccess')
_SG_URL = os.environ.get('PINI_SG_URL')

_LOGGER = logging.getLogger(__name__)


class _CSGHandler(shotgun_api3.Shotgun):
    """Manages interactions with shotgrid.

    This wrappers allows better error messages to be provided and
    for requests to be sanity checked.
    """

    n_requests = 0  # Counter for number of requests
    request_t = 0.0  # Time spent on requests

    # Error if number of requests gets higher (for debugging)
    requests_limit = int(os.environ.get('PINI_SG_REQUESTS_LIMIT', 0))

    @sg_utils.sg_cache_result
    def _read_entity_types(self):
        """Read list of entity types.

        Returns:
            (str list): entity types
        """
        return sorted(self.schema_entity_read().keys())

    def create(self, entity_type, data, safe=True):  # pylint: disable=arguments-renamed
        """Create an entity.

        Args:
            entity_type (str): entity type to create (eg. Shot)
            data (dict): creation data for this entity
            safe (bool): sanity check args

        Returns:
            (dict): creation metadata
        """
        if safe:
            assert entity_type in self._read_entity_types()
        try:
            _result = super().create(entity_type, data)
        except shotgun_api3.Fault as _exc:
            _LOGGER.warning('SHOTGRID CREATE FAILED')
            pprint.pprint(data)
            raise _exc
        return _result

    def find(
            self, entity_type, filters=(), fields=(), order=None,
            filter_operator=None, limit=0, retired_only=False,
            page=0, include_archived_projects=True,
            additional_filter_presets=None, safe=True):
        """Search shotgrid.

        Args:
            entity_type (str): type of entity to find
            filters (list): filter the results
            fields (tuple): fields to return
            order (dict list): apply sorting (see sg docs)
            filter_operator (str): see sg docs
            limit (int): limit number of results (see sg docs)
            retired_only (bool): return only entries which have been retired
            page (int): page of results to result (applies to limit)
            include_archived_projects (bool): include archived projects
            additional_filter_presets (list): see sg docs
            safe (bool): check fields are valid before making request

        Returns:
            (dict list): matching entries
        """
        error_on_file_system_disabled()
        self.n_requests += 1
        _LOGGER.debug('SG FIND [%d] %s %s %s', self.n_requests,
                      entity_type, filters, fields)
        if self.requests_limit and self.n_requests > self.requests_limit:
            raise RuntimeError('Went over requests limit')

        # Sanity check
        if safe:
            if fields:
                _type_fields = self.find_fields(entity_type)
                assert isinstance(fields, (list, tuple))
                assert isinstance(_type_fields, (list, tuple))
                _bad_fields = sorted(set(fields) - set(_type_fields))
                if _bad_fields:
                    _LOGGER.info('FIELDS %s', self.find_fields(entity_type))
                    _bad_fields_s = '/'.join(_bad_fields)
                    raise RuntimeError(
                        f'Bad field{plural(_bad_fields)} {_bad_fields_s}')

        _start = time.time()
        _result = super().find(
            entity_type, filters, fields, order=order,
            filter_operator=filter_operator, limit=limit,
            retired_only=retired_only, page=page,
            include_archived_projects=include_archived_projects,
            additional_filter_presets=additional_filter_presets)
        self.request_t += time.time() - _start
        return _result

    @sg_utils.sg_cache_result
    def find_fields(self, entity_type):
        """Read fields stored for the given entity type.

        Args:
            entity_type (str): entity type to read fields for

        Returns:
            (str list): fields for the given entity
        """
        return sorted(self.schema_field_read(entity_type).keys())

    def find_one(self, entity_type, filters, fields):  # pylint: disable=arguments-differ
        """Find one matching shotgrid entry.

        Args:
            entity_type (str): type of entity to find
            filters (list): filter the results
            fields (tuple): fields to return

        Returns:
            (dict): matching result
        """
        error_on_file_system_disabled()
        _LOGGER.debug('SG FIND ONE %s %s %s', entity_type, filters, fields)
        self.n_requests += 1
        _start = time.time()
        _result = super().find_one(
            entity_type, filters, fields)
        self.request_t += time.time() - _start
        return _result

    def __repr__(self):
        return basic_repr(self, None)


def create(entity_type, data):
    """Wrapper for Shotgrid.create command.

    Args:
        entity_type (str): type of entity to create
        data (dict): creation data
    """
    return to_handler().create(entity_type, data)


def _to_filters(filters, job=None, entity=None, id_=None, path=None):
    """Build filters list.

    Args:
        filters (list): specified filters
        job (CPJob): add job filter
        entity (CPEntity): add entity filter
        id_ (int): match by id
        path (str): match by path (relative path in path_cache field is used)

    Returns:
        (tuple list): filters list
    """
    from pini.pipe import shotgrid

    _filters = list(filters) if filters else []
    if job:
        _proj_s = shotgrid.SGC.find_proj(job)
        _filters.append(_proj_s.to_filter())
    if entity:
        _ety_s = shotgrid.SGC.find_entity(entity)
        _filters.append(_ety_s.to_filter())
    if id_ is not None:
        _filters.append(('id', 'is', id_))
    if path:
        _rel_path = pipe.ROOT.rel_path(path)
        _filters.append(('path_cache', 'is', _rel_path))
    return _filters


def find(
        entity_type, filters=(), fields=(), fmt='list',
        job=None, entity=None, id_=None,
        limit=0, order=None):
    """Wrapper for Shotgrid.find command.

    Args:
        entity_type (str): type of entity to find
        filters (list): filter the results
        fields (tuple): fields to return
        fmt (str): format for results
            list - default results list
            dict - sort results into dict with id as key
        job (CPJob): apply job filter
        entity (CPEntity): add entity filter
        id_ (int): apply id filter
        limit (int): limit number of results (see sg docs)
        order (dict list): apply sorting (see sg docs)

    Returns:
        (dict list): results
    """
    _filters = _to_filters(filters, job=job, entity=entity, id_=id_)
    _results = to_handler().find(
        entity_type, filters=_filters, fields=fields, limit=limit,
        order=order)

    # Format results
    if fmt == 'list':
        pass
    elif fmt == 'dict':
        _dict = {}
        for _item in _results:
            _key = _item.pop('id')
            _item.pop('type')
            _dict[_key] = _item
        _results = _dict
    else:
        raise ValueError

    return _results


def find_all_data(entity_type, id_):
    """Find all shotgrid data for the given data element.

    Args:
        entity_type (str): entity type (eg. Project, Shot)
        id_ (int): entity id

    Returns:
        (dict): all stored data
    """
    _fields = find_fields(entity_type)
    _filters = [('id', 'is', id_)]
    return find_one(entity_type=entity_type, fields=_fields, filters=_filters)


def find_fields(entity_type):
    """Read available fields for the given entity type.

    Args:
        entity_type (str): type of entity to read

    Returns:
        (str list): fields
    """
    return to_handler().find_fields(entity_type)


def find_one(
        entity_type, filters=(), fields=(), job=None, entity=None, id_=None,
        path=None):
    """Wrapper for Shotgrid.find_one command.

    Args:
        entity_type (str): type of entity to find
        filters (list): filter the results
        fields (tuple): fields to return
        job (CPJob): apply job filter
        entity (CPEntity): add entity filter
        id_ (int): filter by entity id
        path (str): match by path (relative path in path_cache field is used)

    Returns:
        (dict): matching entry
    """
    _filters = _to_filters(
        filters, id_=id_, entity=entity, path=path, job=job)
    return to_handler().find_one(
        entity_type, filters=_filters, fields=fields)


@sg_utils.sg_cache_result
def to_handler(force=False, use_basic=False):
    """Obtain a shotgrid handler object.

    Args:
        force (bool): rebuild handler
        use_basic (bool): use basic handler rather than pini subclass

    Returns:
        (CSGHandler): pini shotgrid handler
    """
    if not pipe.SHOTGRID_AVAILABLE:
        _LOGGER.info('SG_KEY %s %s', _SG_KEY, os.environ.get('PINI_SG_KEY'))
        _LOGGER.info('SG_SCRIPT_NAME %s', _SG_SCRIPT_NAME)
        _LOGGER.info('SG_URL %s', _SG_URL)
        raise RuntimeError('Missing shotgrid environment')

    _class = _CSGHandler if not use_basic else shotgun_api3.Shotgun
    return _CSGHandler(_SG_URL, _SG_SCRIPT_NAME, _SG_KEY)


def update(entity_type, entity_id, data):
    """Update the given entry.

    Args:
        entity_type (str): entity type (eg. Shot/Asset)
        entity_id (int): entity id
        data (dict): data to apply
    """
    to_handler().update(
        entity_type=entity_type, entity_id=entity_id, data=data)


def upload(entity_type, entity_id, path, field_name='sg_uploaded_movie'):
    """Upload a file to the specified entity.

    Args:
        entity_type (str): entity type (eg. Shot/Asset)
        entity_id (int): entity id
        path (Path): path to apply
        field_name (str): field to apply data to
    """
    if field_name == 'sg_uploaded_movie':
        _video = Video(path)
        _path = _video.path
    else:
        raise NotImplementedError
    to_handler().upload(
        entity_type=entity_type, entity_id=entity_id, path=_path,
        field_name=field_name)


def upload_filmstrip_thumbnail(entity_type, entity_id, path):
    """Upload filmstrip thumbnail for the given entry.

    Filmstrip thumb should be an image containing any number of 240
    pixel wide images, side to side.

    Args:
        entity_type (str): entity type (eg. Shot/Asset)
        entity_id (int): entity id
        path (str): path to filmstrip
    """
    to_handler().upload_filmstrip_thumbnail(
        entity_type=entity_type, entity_id=entity_id, path=path)


def upload_thumbnail(entity_type, entity_id, path):
    """Upload  thumbnail for the given entry.

    Args:
        entity_type (str): entity type (eg. Shot/Asset)
        entity_id (int): entity id
        path (str): path to thumbnail
    """
    to_handler().upload_thumbnail(
        entity_type=entity_type, entity_id=entity_id, path=path)
