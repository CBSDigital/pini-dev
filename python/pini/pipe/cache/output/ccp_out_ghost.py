"""Tools for managing the output ghost object.

This is a container class which is only used for caching.
"""

# pylint: disable=too-many-instance-attributes

from pini.utils import basic_repr, File

from . import ccp_out_base


class CCPOutputGhost(File):
    """Represents an output on disk in a cache.

    This is only use for caching, and should be converted to a live pipeline
    object before it is used for anything.
    """

    def __init__(
            self, path: str, stream: str, template: str,
            src: str, src_ref: str,
            type_: str, basic_type: str,
            job: str, profile: str,
            asset: str, asset_type: str,
            shot: str, sequence: str,
            step: str, task: str, pini_task: str, tag: str,
            ver_n, ver: str, latest: bool,
            output_name: str, output_type: str, content_type: str,
            updated_at: float, updated_by: str, range_: tuple,
            submittable: bool, handler: str, status: str):
        """Constructor.

        Args:
            path (str): path to output
            stream (str): path to output version stream
                (ie. version zero of stream)
            template (str): path to output template source
            src (str): path to source work file
            src_ref (str): path to source reference (eg. rig path)
            type_ (str): output type
            basic_type (str): output basic type
            job (str): output job name
            profile (str): output profile
            asset (str): output asset name
            asset_type (str): output asset type name
            shot (str): output shot name
            sequence (str): output sequence name
            step (str): output step name
            task (str): output task name
            pini_task (str): output pini task name
            tag (str): output tag
            ver_n (int|None): output version number
            ver (str|None): output version string
            latest (bool): whether this is latest version
            output_name (str): output name
            output_type (str): output type
            content_type (str): output content type
            updated_at (float): output mtime
            updated_by (str): output owner
            range_ (tuple|None): output range
            submittable (bool): whether this output is submittable
            handler (str): export handler
            status (str): output status (eg. cmpt/lapr)
        """
        assert isinstance(updated_by, str) or updated_by is None
        super().__init__(path)

        # Path list attrs
        self.template = template
        self.stream = stream
        self.src = src
        self.src_ref = src_ref

        self.type_ = type_
        self.basic_type = basic_type

        self.job = job
        self.profile = profile
        self.asset = asset
        self.asset_type = asset_type
        self.shot = shot
        self.sequence = sequence

        self.step = step
        self.task = task
        self.pini_task = pini_task
        self.tag = tag

        self.output_name = output_name
        self.output_type = output_type
        self.content_type = content_type

        self.latest = latest
        self.ver_n = ver_n
        self.ver = ver

        self.updated_at = updated_at
        self.updated_by = updated_by
        self.range_ = range_
        self.submittable = submittable
        self.handler = handler
        self.status = status

    def is_latest(self):
        """Test whether this is the latest version.

        Returns:
            (bool): whether latest
        """
        return self.latest

    def is_media(self):
        """Test whether this output is media.

        Returns:
            (bool): whether media (eg. render/blast)
        """
        return self.content_type in ccp_out_base.OUTPUT_MEDIA_CONTENT_TYPES

    def __eq__(self, other):
        if hasattr(other, 'path'):
            return self.path == other.path
        return False

    def __hash__(self):
        return hash(self.path)

    def __lt__(self, other):
        return self.path < other.path

    def __nonzero__(self):
        return False

    def __repr__(self):
        return basic_repr(self, self.path)
