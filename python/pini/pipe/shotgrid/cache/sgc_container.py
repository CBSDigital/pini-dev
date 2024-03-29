"""Tools for managing shotgrid cache container classes.

These are simple classes for storing shotgrid results.
"""

from pini.utils import basic_repr


class SGCContainer(object):
    """Base class for all container classes."""
    def __init__(self, data):
        """Constructor.

        Args:
            data (dict): shotgrid data
        """
        self.data = data
        self.id_ = data['id']
        self.updated_at = data['updated_at']
        self.type_ = data['type']

    def to_entry(self):
        """Build shotgrid uid dict for this data entry.

        Returns:
            (dict): shotgrid entry
        """
        return {'type': self.type_, 'id': self.id_}


class SGCStep(SGCContainer):
    """Represents a pipeline step."""

    def __init__(self, data):
        """Constructor.

        Args:
            data (dict): shotgrid data
        """
        super(SGCStep, self).__init__(data)
        self.short_name = data['short_name']
        _dept = data.get('department') or {}
        self.department = _dept.get('name')

    def __repr__(self):
        return basic_repr(self, self.short_name)


class SGCUser(SGCContainer):
    """Represents a human user on shotgrid."""

    def __init__(self, data):
        """Constructor.

        Args:
            data (dict): shotgrid data
        """
        super(SGCUser, self).__init__(data)
        self.login = data['login']
        self.name = data['name']
        self.email = data['email']
        self.status = data['sg_status_list']

    def __repr__(self):
        return basic_repr(self, self.login)


class _SGCPath(SGCContainer):
    """Base class for all pipe template shotgrid elements."""

    def __init__(self, data):
        """Constructor.

        Args:
            data (dict): shotgrid data
        """
        super(_SGCPath, self).__init__(data)
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

    def __init__(self, data):
        """Constructor.

        Args:
            data (dict): shotgrid data
        """
        super(SGCAsset, self).__init__(data)
        self.name = data['code']
        self.asset_type = data['sg_asset_type']


class SGCShot(_SGCPath):
    """Represents a shot."""

    def __init__(self, data):
        """Constructor.

        Args:
            data (dict): shotgrid data
        """
        super(SGCShot, self).__init__(data)
        self.name = data['code']
        self.has_3d = data['sg_has_3d']


class SGCTask(_SGCPath):
    """Represents a task."""

    def __init__(self, data):
        """Constructor.

        Args:
            data (dict): shotgrid data
        """
        super(SGCTask, self).__init__(data)
        self.name = data['sg_short_name']
        self.step_id = data['step']['id']


class SGCPubFile(_SGCPath):
    """Represents a published file."""

    def __init__(self, data):
        """Constructor.

        Args:
            data (dict): shotgrid data
        """
        super(SGCPubFile, self).__init__(data)
        self.has_work_dir = data['has_work_dir']
