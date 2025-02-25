"""Tools for managing output sequence directories.

These are used to managed caching for disk-based output sequences.
"""

import logging

from pini.utils import File, Seq, Dir

_LOGGER = logging.getLogger(__name__)


class CPOutputSeqDir(Dir):
    """Represents a directory containing output file sequences.

    This is used to facilitate caching.
    """

    def __init__(self, path, entity, template):
        """Constructor.

        Args:
            path (str): path to directory
            entity (CPEntity): parent entity
            template (CPTemplate): seq_dir template
        """
        super().__init__(path)

        self.template = template
        self.entity = entity

        self.data = self.template.parse(self.path)

        self.task = self.data.get('task')
        self.tag = self.data.get('tag')
        self.ver_n = int(self.data['ver'])

    def find_outputs(self):
        """Find outputs within this directory.

        Returns:
            (CPOutputSeq list): outputs
        """
        return self._read_outputs()

    def _read_outputs(self, output_seq_class=None, output_video_class=None):
        """Read outputs within this directory from disk.

        Args:
            output_seq_class (class): override output seq class
            output_video_class (class): override output video class

        Returns:
            (CPOutputSeq list): outputs
        """
        from pini import pipe
        _LOGGER.debug('[CPOutputSeqDir] READ OUTPUTS %s', self)

        _outs = []
        _output_seq_class = output_seq_class or pipe.CPOutputSeq
        _output_video_class = output_video_class or pipe.CPOutputVideo
        _LOGGER.debug(' - OUTPUT SEQ CLASS %s', _output_seq_class)
        for _path in self.find_seqs():

            _LOGGER.debug(' - TESTING PATH %s', _path)

            # Try as output seq
            if isinstance(_path, Seq):
                try:
                    _out = _output_seq_class(
                        _path.path, frames=_path.frames, dir_=self,
                        entity=self.entity)
                except ValueError:
                    continue

            elif isinstance(_path, File):
                try:
                    _out = _output_video_class(
                        _path.path, entity=self.entity)
                except ValueError:
                    continue

            else:
                raise ValueError(_path)

            _outs.append(_out)

        return _outs
