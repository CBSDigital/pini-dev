"""Tools for managing the shotgrid handler.

This managing iteraction with the shotgrid via the shotgun_api3 api.
"""

import logging
import os

import shotgun_api3

from pini import pipe
from pini.utils import cache_result, cache_property, plural, basic_repr

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
    requests_limit = 0  # Error if number of requests gets higher

    @cache_property
    def entity_types(self):
        """Obtain list of entity types.

        An entity is a type of entry which can be queried, eg. Project,
        Sequence, Version.

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
            assert entity_type in self.entity_types  # pylint: disable=unsupported-membership-test
        return super(_CSGHandler, self).create(entity_type, data)

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
            order (dict list): sorts dict (see sg docs)
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
        _LOGGER.debug('SG FIND %s %s %s', entity_type, filters, fields)
        self.n_requests += 1
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
                    raise RuntimeError(
                        'Bad field{} {}'.format(
                            plural(_bad_fields), '/'.join(_bad_fields)))

        return super(_CSGHandler, self).find(
            entity_type, filters, fields, order=order,
            filter_operator=filter_operator, limit=limit,
            retired_only=retired_only, page=page,
            include_archived_projects=include_archived_projects,
            additional_filter_presets=additional_filter_presets)

    @cache_result
    def find_fields(self, entity_type):
        """Read fields stored for the given entity type.

        Args:
            entity_type (str): entity type to read fields for

        Returns:
            (str list): fields for the given entity
        """
        return sorted(self.schema_field_read(entity_type).keys())

    def find_one(self, entity_type, filters, fields):
        """Find one matching shotgrid entry.

        Args:
            entity_type (str): type of entity to find
            filters (list): filter the results
            fields (tuple): fields to return

        Returns:
            (dict): matching result
        """
        _LOGGER.debug('SG FIND ONE %s %s %s', entity_type, filters, fields)
        self.n_requests += 1
        return super(_CSGHandler, self).find_one(entity_type, filters, fields)

    def __repr__(self):
        return basic_repr(self, None)


def create(entity_type, data):
    """Wrapper for Shotgrid.create command.

    Args:
        entity_type (str): type of entity to create
        data (dict): creation data
    """
    return to_handler().create(entity_type, data)


def find(entity_type, filters=(), fields=(), fmt='list', job=None):
    """Wrapper for Shotgrid.find command.

    Args:
        entity_type (str): type of entity to find
        filters (list): filter the results
        fields (tuple): fields to return
        fmt (str): format for results
            list - default results list
            dict - sort results into dict with id as key
        job (CPJob): apply job filter

    Returns:
        (dict list): results
    """
    from pini.pipe import shotgrid

    _filters = list(filters) if filters else []
    if job:
        _filters.append(shotgrid.to_job_filter(job))
    _results = to_handler().find(
        entity_type, filters=_filters, fields=fields)

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


def find_one(entity_type, filters=(), fields=(), id_=None):
    """Wrapper for Shotgrid.find_one command.

    Args:
        entity_type (str): type of entity to find
        filters (list): filter the results
        fields (tuple): fields to return
        id_ (int): filter by entity id

    Returns:
        (dict): matching entry
    """
    _filters = list(filters)
    if id_:
        _filters.append(('id', 'is', id_))
    return to_handler().find_one(
        entity_type, filters=_filters, fields=fields)


@cache_result
def to_handler():
    """Obtain a shotgrid handler object.

    Returns:
        (CSGHandler): pini shotgrid handler
    """
    if not pipe.SHOTGRID_AVAILABLE:
        _LOGGER.info('SG_KEY %s %s', _SG_KEY, os.environ.get('PINI_SG_KEY'))
        _LOGGER.info('SG_SCRIPT_NAME %s', _SG_SCRIPT_NAME)
        _LOGGER.info('SG_URL %s', _SG_URL)
        raise RuntimeError('Missing shotgrid environment')

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
