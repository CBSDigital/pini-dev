"""Tools for managing the element reader virtual base class."""

import operator
import logging

from pini.utils import single, to_time_f

from ..sg_utils import sg_cache_result

_LOGGER = logging.getLogger(__name__)


class SGCElemReader(object):
    """Base class for any shotgrid element."""

    @property
    def sg(self):
        """Obtain shotgrid handler.

        Returns:
            (CSGHandler): shotgrid request handler
        """
        from pini.pipe import shotgrid
        return shotgrid.to_handler()

    def _build_filters(self, type_):
        """Build filters to limit results to children of this element.

        Args:
            type_ (class): type of entity being requested

        Returns:
            (tuple list): filters
        """
        _filters = type_.build_cls_filters()
        _filter = self.to_filter()
        if _filter:
            _filters.append(_filter)

        return _filters

    @sg_cache_result
    def _read_elems(self, type_, sort_attr=None, force=None):
        """Read elements within this one.

        eg. read shots in a project

        Args:
            type_ (class): type of element to read
            sort_attr (str): apply sort attribute
            force (bool): force reread cached data

        Returns:
            (SGCElem list): elements
        """
        _LOGGER.debug('READ ELEMS %s', type_)
        _filters = self._build_filters(type_)
        _LOGGER.debug(' - FILTERS %s', _filters)
        _data = self.sg.find(
            type_.ENTITY_TYPE, fields=type_.FIELDS,
            filters=_filters)

        _elems = []
        for _item in _data:
            _LOGGER.debug('   - ADDING ITEM %s', _item)
            assert isinstance(_item, dict)
            try:
                _elem = type_(_item)
            except ValueError as _exc:
                _LOGGER.debug(' - REJECTED %s %s', type_, _item)
                _LOGGER.debug(' - ERROR %s', _exc)
                continue
            _elems.append(_elem)

        if sort_attr:
            _elems.sort(key=operator.attrgetter(sort_attr))
        _LOGGER.debug(' - FOUND %d ELEMS', len(_elems))
        return _elems

    def _read_elems_updated_t(self, type_):
        """Read the time the last element of this type was updated.

        If the update time of data cached to disk is the same, the data
        does not need to be rebuilt. This is to save time validating the
        read data (actually reading the data from shotgrid is not slow).

        Args:
            type_ (class): type of element to read

        Returns:
            (float): last update time
        """
        _LOGGER.debug('READ ELEMS UPDATED T %s', type_.ENTITY_TYPE)

        _last_e = single(
            self.sg.find(
                type_.ENTITY_TYPE,
                filters=self._build_filters(type_),
                fields=['updated_at'],
                limit=1,
                order=[{'field_name': 'updated_at', 'direction': 'desc'}]),
            catch=True)
        if not _last_e:
            return None
        return to_time_f(_last_e['updated_at'])

    def to_filter(self):
        """Build shotgrid search filter from this element.

        Returns:
            (tuple): filter
        """
        raise NotImplementedError
