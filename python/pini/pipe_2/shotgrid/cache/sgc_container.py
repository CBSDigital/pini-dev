"""Tools for managing shotgrid cache container classes.

These are simple classes for storing shotgrid results.
"""

import os

from pini.utils import basic_repr, strftime


class SGCContainer(object):
    """Base class for all container classes."""

    ENTITY_TYPE = None

    def __init__(self, data, job=None):
        """Constructor.

        Args:
            data (dict): shotgrid data
            job (SGJob): parent job (if any)
        """
        self.data = data

        self.id_ = data['id']
        self.updated_at = data['updated_at']
        self.type_ = data['type']

        self.job = job

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

    def to_filter(self):
        """Build shotgrid search filter from this entry.

        Returns:
            (tuple): filter
        """
        return self.type_.lower(), 'is', self.to_entry()

    def to_entry(self):
        """Build shotgrid uid dict for this data entry.

        Returns:
            (dict): shotgrid entry
        """
        return {'type': self.type_, 'id': self.id_}

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

    ENTITY_TYPE = 'PipelineStep'

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


class _SGCPath(SGCContainer):
    """Base class for all pipe template shotgrid elements."""

    def __init__(self, data, job=None):
        """Constructor.

        Args:
            data (dict): shotgrid data
            job (SGJob): parent job
        """
        super().__init__(data, job=job)
        self.path = data['path']
        self.template = data['template']
        self.template_type = data['template_type']
        self.status = data['sg_status_list']

    def __lt__(self, other):
        return self.path < other.path

    def __repr__(self):
        return basic_repr(self, self.path)


class SGCAsset(_SGCPath):
    """Represents an asset."""

    ENTITY_TYPE = 'Asset'

    def __init__(self, data, job):
        """Constructor.

        Args:
            data (dict): shotgrid data
            job (SGJob): parent job
        """
        super().__init__(data, job)
        self.name = data['code']
        self.asset_type = data['sg_asset_type']


class SGCShot(_SGCPath):
    """Represents a shot."""

    ENTITY_TYPE = 'Shot'
    FIELDS = [
        'sg_head_in', 'code', 'sg_sequence', 'sg_status_list',
        'updated_at', 'sg_has_3d']

    def __init__(self, data, job):
        """Constructor.

        Args:
            data (dict): shotgrid data
            job (SGJob): parent job
        """
        super().__init__(data, job)
        self.name = data['code']
        self.has_3d = data['sg_has_3d']


class SGCTask(_SGCPath):
    """Represents a task."""

    ENTITY_TYPE = 'Task'
    FIELDS = [
        'step', 'sg_short_name', 'entity', 'sg_status_list', 'updated_at']

    def __init__(self, data, job):
        """Constructor.

        Args:
            data (dict): shotgrid data
            job (SGJob): parent job
        """
        super().__init__(data, job)
        self.name = data['sg_short_name']
        self.step_id = data['step']['id']


class SGCPubFile(_SGCPath):
    """Represents a published file."""

    ENTITY_TYPE = 'PublishedFile'
    FIELDS = (
        'path_cache', 'path', 'sg_status_list', 'updated_at', 'updated_by')

    def __init__(self, data, job, latest=None):
        """Constructor.

        Args:
            data (dict): shotgrid data
            job (SGJob): parent job
            latest (bool): whether this latest version of this publish stream
        """
        super().__init__(data, job)
        self.has_work_dir = data['has_work_dir']
        self.latest = latest


class SGCVersion(_SGCPath):
    """Represents a version entity."""

    ENTITY_TYPE = 'Version'
