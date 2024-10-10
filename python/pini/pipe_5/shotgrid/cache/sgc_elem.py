import logging

from pini.utils import single, to_time_t

from ...cache import pipe_cache_result

_LOGGER = logging.getLogger(__name__)


class SGCElem(object):

    FIELDS = None
    ENTITY_TYPE = None

    _sg = None

    @property
    def sg(self):
        """Obtain shotgrid handler.

        Returns:
            (CSGHandler): shotgrid request handler
        """
        if not self._sg:
            from pini.pipe import shotgrid
            self._sg = shotgrid.to_handler()
        return self._sg

    def to_filter(self):
        raise NotImplementedError

    def _build_filters(self):
        _filters = []
        # if self.FIELDS and 'sg_status_list' in self.FIELDS:
        #     _filters.append(('sg_status_list', 'is_not', 'omt'))
        _filter = self.to_filter()
        if _filter:
            _filters.append(_filter)
        return _filters
        
    @pipe_cache_result
    def _read_data(self, type_, force=False):

        _filters = self._build_filters()
        # _LOGGER.debug('READ DATA %s %s %s', type_, fields, _filters)
        
        return self.sg.find(
            type_.ENTITY_TYPE, fields=type_.FIELDS, filters=_filters)

    def _read_data_last_t(self, type_):

        _LOGGER.debug('READ DATA LAST T %s', type_.ENTITY_TYPE)

        _last_e = single(
            self.sg.find(
                type_.ENTITY_TYPE,
                filters=self._build_filters(),
                fields=['updated_at'],
                limit=1,
                order=[{'field_name': 'updated_at', 'direction': 'desc'}]),
            catch=True)
        if not _last_e:
            return None
        return to_time_t(_last_e['updated_at'])
