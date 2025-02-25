"""Tools for managing shotgrid cache container classes.

These are simple classes for storing shotgrid results.
"""

# pylint: disable=abstract-method,unsupported-membership-test

import logging

from pini.utils import basic_repr, Path, abs_path

from . import sgc_elem

_LOGGER = logging.getLogger(__name__)


class SGCPubType(sgc_elem.SGCElem):
    """Represents a published file type."""

    ENTITY_TYPE = 'PublishedFileType'
    FIELDS = ('code', 'updated_at')

    def __init__(self, data):
        """Constructor.

        Args:
            data (dict): shotgrid data
        """
        super().__init__(data)
        self.code = data['code']

    def __repr__(self):
        return basic_repr(self, self.code)


class SGCStep(sgc_elem.SGCElem):
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


class SGCUser(sgc_elem.SGCElem):
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


class SGCPath(sgc_elem.SGCElem, Path):
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


class SGCTask(sgc_elem.SGCElem):
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
        self.task = self.name

        # Set step
        self.step = self.step_id = None
        _step_data = data.get('step', {}) or {}
        if _step_data:
            self.step_id = _step_data['id']
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
        'entity', 'project', 'task')

    def __init__(self, data):
        """Constructor.

        Args:
            data (dict): shotgrid data
        """
        _LOGGER.debug('INIT SGCPubFile')
        from pini import pipe

        _LOGGER.debug(' - DATA %s', data)
        if data['path_cache']:
            _path = pipe.ROOT.to_file(data['path_cache']).path
        elif data['path']:
            _path_data = data['path']
            if 'local_path' in _path_data:
                _path = abs_path(_path_data['local_path'])
            else:
                _path = None
        else:
            _path = None
        _LOGGER.debug(' - PATH %s', _path)

        super().__init__(data, path=_path)
        assert data
        assert self.data
        _task_data = self.data.get('task', {}) or {}
        self.task_long = _task_data.get('name')

        # These are set after init
        self.validated = None
        self.template = None
        self.stream = None
        self.task = None


class SGCVersion(sgc_elem.SGCElem):
    """Represents a version entity."""

    ENTITY_TYPE = 'Version'
    FIELDS = (
        'published_files', 'entity', 'project', 'sg_task', 'sg_path_to_movie',
        'updated_at', 'updated_by', 'sg_status_list')
