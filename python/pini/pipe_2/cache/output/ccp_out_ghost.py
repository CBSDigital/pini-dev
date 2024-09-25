"""Tools for managing the output ghost object.

This is a container class which is only used for caching.
"""

# pylint: disable=too-many-instance-attributes

from pini.utils import basic_repr, File


class CCPOutputGhost(File):
    """Represents an output on disk in a cache.

    This is only use for caching, and should be converted to a live pipeline
    object before it is used for anything.
    """

    def __init__(
            self, path: str, latest: bool, template: str, type_: str,
            job: str, asset: str, asset_type: str, shot: str, sequence: str,
            step: str, task: str, pini_task: str, tag: str, ver_n,
            output_name: str, output_type: str, content_type: str,
            mtime: float):
        """Constructor.

        Args:
            path (str): path to output
            latest (bool): whether this is latest version
            template (str): path to output template source
            type_ (str): output type
            job (str): output job name
            asset (str): output asset name
            asset_type (str): output asset type name
            shot (str): output shot name
            sequence (str): output sequence name
            step (str): output step name
            task (str): output task name
            pini_task (str): output pini task name
            tag (str): output tag
            ver_n (int|None): output version number
            output_name (str): output name
            output_type (str): output type
            content_type (str): output content type
            mtime (float): output mtime
        """
        super().__init__(path)
        self.mtime = mtime

        self.template = template
        self.type_ = type_

        self.job = job
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

    def __lt__(self, other):
        return self.path < other.path

    def __nonzero__(self):
        return False

    def __repr__(self):
        return basic_repr(self, self.path)
