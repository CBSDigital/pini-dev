"""Tools for managing shotgrid cache container classes.

These are simple classes for storing shotgrid results.
"""

# pylint: disable=abstract-method

import logging
import os

from pini.utils import basic_repr, strftime, Path, abs_path

from . import sgc_elem

_LOGGER = logging.getLogger(__name__)


class SGCContainer(sgc_elem.SGCElem):
    """Base class for all container classes."""

    FIELDS = None
    ENTITY_TYPE = None
    STATUS_KEY = 'sg_status_list'

    def __init__(self, data):
        """Constructor.

        Args:
            data (dict): shotgrid data
        """
        self.data = data

        self.id_ = data['id']
        self.updated_at = data['updated_at']
        self.status = data.get(self.STATUS_KEY)

        assert self.ENTITY_TYPE
        assert self.FIELDS
        assert isinstance(self.FIELDS, tuple)
        assert data['type'] == self.ENTITY_TYPE

    @property
    def omitted(self):
        """Check whether this element has been omitted.

        Returns:
            (bool): whether omitted
        """
        return self.status == 'omt'

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
        if status == 'omt':
            _desc = strftime('Omitted %d/%m/%y %H:%M:%S')
        else:
            raise NotImplementedError(status)
        _data = {'sg_status_list': status, 'description': _desc}
        shotgrid.update('PublishedFile', self.id_, _data)

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
        return '{}/detail/{}/{}'.format(
            os.environ.get('PINI_SG_URL'), self.ENTITY_TYPE, self.id_)


class SGCPubType(SGCContainer):
    """Represents a published file type."""

    ENTITY_TYPE = 'PublishedFileType'
    FIELDS = ('code', )

    def __init__(self, data):
        """Constructor.

        Args:
            data (dict): shotgrid data
        """
        super().__init__(data)
        self.code = data['code']

    def __repr__(self):
        return basic_repr(self, self.code)


class SGCStep(SGCContainer):
    """Represents a pipeline step."""

    FIELDS = (
        'entity_type', 'code', 'short_name', 'department', 'updated_at',
        'list_order')
    ENTITY_TYPE = 'Step'

    def __init__(self, data):
        """Constructor.

        Args:
            data (dict): shotgrid data
        """
        super().__init__(data)
        self.short_name = data['short_name']
        self.list_order = data['list_order']

        _dept = data.get('department') or {}
        self.department = _dept.get('name')

    def __repr__(self):
        return basic_repr(self, self.short_name)


class SGCUser(SGCContainer):
    """Represents a human user on shotgrid."""

    ENTITY_TYPE = 'HumanUser'
    FIELDS = ('name', 'email', 'login', 'sg_status_list', 'updated_at')

    def __init__(self, data):
        """Constructor.

        Args:
            data (dict): shotgrid data
        """
        super().__init__(data)
        self.login = data['login']
        self.name = data['name']
        self.email = data['email']
        self.status = data['sg_status_list']

    def __repr__(self):
        return basic_repr(self, self.login)


class SGCPath(SGCContainer, Path):
    """Base class for all pipe template shotgrid elements."""

    def __init__(self, data, path):
        """Constructor.

        Args:
            data (dict): shotgrid data
            path (str): element path
        """
        super().__init__(data)

        if path:
            Path.__init__(self, path)
        else:
            self.path = ''
        self.status = data['sg_status_list']

    def __lt__(self, other):
        return self.path < other.path

    def __repr__(self):
        return basic_repr(self, self.path)


class SGCTask(SGCContainer):
    """Represents a task."""

    ENTITY_TYPE = 'Task'
    FIELDS = (
        'step', 'sg_short_name', 'entity', 'sg_status_list',
        'updated_at', 'project')

    def __init__(self, data):
        """Constructor.

        Args:
            data (dict): shotgrid data
        """
        super().__init__(data)
        self.name = data['sg_short_name']
        self.step_id = data['step']['id']
        _step = self.root.find_step(self.step_id)
        self.step = _step.short_name

    def __repr__(self):
        return basic_repr(
            self, f'{self.entity.uid}.{self.step}/{self.name}')


class SGCPubFile(SGCPath):
    """Represents a published file."""

    ENTITY_TYPE = 'PublishedFile'
    FIELDS = (
        'path_cache', 'path', 'sg_status_list', 'updated_at', 'updated_by',
        'entity', 'project')

    def __init__(self, data):
        """Constructor.

        Args:
            data (dict): shotgrid data
        """
        from pini import pipe

        if data['path_cache']:
            _path = pipe.ROOT.to_file(data['path_cache']).path
        elif data['path']:
            _path = abs_path(data['path']['local_path'])
            _LOGGER.debug(' - PATH %s', _path)
            # asdasd
        else:
            _path = None

        super().__init__(data, path=_path)

        # These are set after init
        self.latest = None
        self.validated = None
        self.template = None
        self.stream = None


class SGCVersion(SGCPath):
    """Represents a version entity."""

    ENTITY_TYPE = 'Version'
