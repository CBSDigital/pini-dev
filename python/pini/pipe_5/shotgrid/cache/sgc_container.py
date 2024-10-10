"""Tools for managing shotgrid cache container classes.

These are simple classes for storing shotgrid results.
"""

import os

from pini.utils import basic_repr, strftime, Path

from . import sgc_elem


class SGCContainer(sgc_elem.SGCElem):
    """Base class for all container classes."""

    FIELDS = None
    ENTITY_TYPE = None

    def __init__(self, data, proj=None):
        """Constructor.

        Args:
            data (dict): shotgrid data
            proj (SGCProj): parent proj (if any)
        """
        self.data = data

        self.id_ = data['id']
        self.updated_at = data['updated_at']
        # self.type_ = data['type']
        assert self.ENTITY_TYPE
        assert self.FIELDS
        assert isinstance(self.FIELDS, tuple)

        self.proj = proj

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

    def __init__(self, data, proj=None, path=None):
        """Constructor.

        Args:
            data (dict): shotgrid data
            proj (SGCProj): parent proj
        """
        super().__init__(data, proj=proj)
        Path.__init__(self, path or data['path'])
        # self.template = data['template']
        # self.template_type = data['template_type']
        self.status = data['sg_status_list']

    def __lt__(self, other):
        return self.path < other.path

    def __repr__(self):
        return basic_repr(self, self.path)


# class SGCAsset(SGCPath):
#     """Represents an asset."""

#     ENTITY_TYPE = 'Asset'

#     def __init__(self, data, job):
#         """Constructor.

#         Args:
#             data (dict): shotgrid data
#             job (SGCProj): parent job
#         """
#         super().__init__(data, job)
#         self.name = data['code']
#         self.asset_type = data['sg_asset_type']

#     def to_filter(self):
#         return 'entity', 'is', self.to_entry()


# class SGCShot(SGCPath):
#     """Represents a shot."""

#     ENTITY_TYPE = 'Shot'
#     FIELDS = [
#         'sg_head_in', 'code', 'sg_sequence', 'sg_status_list',
#         'updated_at', 'sg_has_3d']

#     def __init__(self, data, job):
#         """Constructor.

#         Args:
#             data (dict): shotgrid data
#             job (SGCProj): parent job
#         """
#         super().__init__(data, job)
#         self.name = data['code']
#         self.has_3d = data['sg_has_3d']


class SGCTask(SGCContainer):
    """Represents a task."""

    ENTITY_TYPE = 'Task'
    FIELDS = (
        'step', 'sg_short_name', 'entity', 'sg_status_list', 'updated_at')

    def __init__(self, data, entity):
        """Constructor.

        Args:
            data (dict): shotgrid data
            proj (SGCProj): parent proj
        """
        self.entity = entity
        super().__init__(data, proj=entity.proj)
        self.name = data['sg_short_name']
        self.step_id = data['step']['id']
        self.step = data['step']['name']

    def __repr__(self):
        _step = self.proj.cache.find_step(self.step_id)
        return basic_repr(
            self, f'{self.entity.uid}.{_step.short_name}/{self.name}')


class SGCPubFile(SGCPath):
    """Represents a published file."""

    ENTITY_TYPE = 'PublishedFile'
    FIELDS = (
        'path_cache', 'path', 'sg_status_list', 'updated_at', 'updated_by')

    def __init__(self, data, proj, latest=None):
        """Constructor.

        Args:
            data (dict): shotgrid data
            proj (SGCProj): parent proj
            latest (bool): whether this latest version of this publish stream
        """
        super().__init__(data, proj)
        self.has_work_dir = data['has_work_dir']
        self.latest = latest


class SGCVersion(SGCPath):
    """Represents a version entity."""

    ENTITY_TYPE = 'Version'
