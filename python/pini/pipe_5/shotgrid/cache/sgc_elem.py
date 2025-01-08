"""Tools for managing shotgrid elements, any queryable item in shotgrid."""

# pylint: disable=unsupported-membership-test

import logging
import os
import webbrowser

from pini.utils import strftime, basic_repr

from . import sgc_elem_reader

_LOGGER = logging.getLogger(__name__)


class SGCElem(sgc_elem_reader.SGCElemReader):
    """Base class for all shotgrid elements."""

    FIELDS = None
    ENTITY_TYPE = None

    FIELDS = None
    ENTITY_TYPE = None
    STATUS_KEY = 'sg_status_list'

    def __init__(self, data):
        """Constructor.

        Args:
            data (dict): shotgrid data
        """
        assert self.ENTITY_TYPE
        assert self.FIELDS
        assert isinstance(self.FIELDS, tuple)
        assert data['type'] == self.ENTITY_TYPE
        assert 'updated_at' in self.FIELDS

        self.data = data

        self.id_ = data['id']
        self.updated_at = data['updated_at']
        self.status = data.get(self.STATUS_KEY)

    @property
    def cmp_key(self):
        """Get comparison key.

        Returns:
            (tuple): cmp key
        """
        return self.id_, self.ENTITY_TYPE

    @property
    def entity(self):
        """Obtain parent entity for this element.

        Returns:
            (SGCEntity): entity
        """
        if 'entity' not in self.data:
            raise RuntimeError(self, self.data)
        return self.proj.find_entity(
            id_=self.data['entity']['id'],
            type_=self.data['entity']['type'])

    @property
    def proj(self):
        """Obtain parent project for this element.

        Returns:
            (SGCProj): project
        """
        if 'project' not in self.data:
            raise RuntimeError(self.data)
        return self.root.find_proj(self.data['project']['id'])

    @property
    def omitted(self):
        """Check whether this element has been omitted.

        Returns:
            (bool): whether omitted
        """
        return self.status == 'omt'

    @property
    def root(self):
        """Obtain cache root.

        Returns:
            (SGCRoot): cache root
        """
        from . import sgc_root
        return sgc_root.SGC

    @property
    def url(self):
        """Obtain url for this entry.

        Returns:
            (str): shotgrid url
        """
        return self.to_url()

    @classmethod
    def build_cls_filters(cls):
        """Build class filters for this element.

        This is used when elements of this type are queried.

        Returns:
            (tuple list): filters
        """
        _filters = []
        if cls.FIELDS and 'sg_status_list' in cls.FIELDS:
            _filters.append(('sg_status_list', 'is_not', 'omt'))
        return _filters

    def browser(self):
        """Open this element in a web browser."""
        webbrowser.open(self.url)

    def omit(self):
        """Omit this entry by setting status to 'omt'."""
        self.set_status('omt')

    def set_status(self, status):
        """Update status of this entry.

        NOTE: to force the update_at field to update, it seems like you need
        to also update a field other than sg_status_list, so the description
        is updated with a date-stamped status.

        Args:
            status (str): status to apply
        """
        from pini.pipe import shotgrid
        _data = {'sg_status_list': status}
        if status == 'omt':
            _desc = strftime('Omitted %d/%m/%y %H:%M:%S')
            _data['description'] = _desc
        elif status in ('wtg', 'apr', 'lapr'):
            pass
        else:
            raise NotImplementedError(status)
        shotgrid.update(self.ENTITY_TYPE, self.id_, _data)

    def to_entry(self):
        """Build shotgrid uid dict for this data entry.

        Returns:
            (dict): shotgrid entry
        """
        return {'type': self.ENTITY_TYPE, 'id': self.id_}

    def to_filter(self):
        """Build shotgrid search filter from this entry.

        Returns:
            (tuple): filter
        """
        return self.ENTITY_TYPE.lower(), 'is', self.to_entry()

    def to_url(self):
        """Obtain url for this entry.

        Returns:
            (str): entry url
        """
        _url = os.environ.get('PINI_SG_URL')
        return f'{_url}/detail/{self.ENTITY_TYPE}/{self.id_}'

    def __eq__(self, other):
        if hasattr(other, 'cmp_key'):
            return self.cmp_key == other.cmp_key
        if hasattr(self, 'path') and hasattr(other, 'path'):
            return self.path == other.path  # pylint: disable=no-member
        return False

    def __hash__(self):
        return hash(self.cmp_key)

    def __lt__(self, other):
        return self.cmp_key < other.cmp_key

    def __repr__(self):
        return basic_repr(self, str(self.id_))
