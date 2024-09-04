"""Tools for mangaging work dir objects in a disk-based pipeline."""

import logging

from . import cp_work_dir_base

_LOGGER = logging.getLogger(__name__)


class CPWorkDirDisk(cp_work_dir_base.CPWorkDir):
    """Represents a work directory in a disk-based pipeline."""

    def create(self, force=False):
        """Create this work dir.

        Args:
            force (bool): create any parent entity without confirmation
        """
        if not self.entity.exists():
            self.entity.create(force=force)
        self.mkdir()

    def _read_outputs(self, class_=None):
        """Read outputs from disk.

        Args:
            class_ (class): override output class

        Returns:
            (CPOutput list): outputs
        """
        from pini import pipe

        _class = class_ or pipe.CPOutputFile
        _LOGGER.debug('READ OUTPUTS DISK %s', _class)
        _tmpls = self._find_output_templates()
        _LOGGER.debug(' - FOUND %d TMPLS', len(_tmpls))

        _globs = pipe.glob_templates(_tmpls, job=self.job)
        _outs = []
        for _tmpl, _path in _globs:
            _out = _class(
                _path, template=_tmpl, work_dir=self, entity=self.entity)
            _outs.append(_out)

        return sorted(_outs)
