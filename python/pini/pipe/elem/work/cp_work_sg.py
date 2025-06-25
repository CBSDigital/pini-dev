"""Tools for managing work files on a shotgrid-based pipeline."""

import logging

from pini.tools import release
from pini.utils import get_user

from . import cp_work_base

_LOGGER = logging.getLogger(__name__)


class CPWorkSG(cp_work_base.CPWorkBase):
    """Represents a work file in a shotgrid-based pipeline."""

    def owner(self):
        """Obtain owner of this work file.

        In cases where the user is embedded in the path, this
        user token should be used, although to avoid ugly shotgrid
        names mapped from emails (eg. my-name-company-com), if the
        token is the current user then the login name can be used
        instead (eg. mname).

        Otherwise, this is simply the owner of the file on disk.

        Returns:
            (str): file owner
        """
        return self._owner_from_user() or super().owner()

    def _owner_from_user(self):
        """Obtain owner based on user tag.

        Returns:
            (str|None): owner (if any)
        """
        if self.user:

            # Avoid nasty shotgrid name if possible
            from pini import pipe
            if self.user == pipe.cur_user():
                return get_user()

            return self.user

        return None

    def _read_outputs_from_pipe(self):
        """Read outputs from shotgrid.

        Returns:
            (CPOutput list): outputs
        """
        _LOGGER.debug(' - SEARCHING JOB OUTS %s', self.job)
        _outs = self.work_dir.find_outputs(
            ver_n=self.ver_n, tag=self.tag)
        _LOGGER.debug(' - FOUND %d OUTS', len(_outs))

        return _outs

    @release.transfer_kwarg_docs(cp_work_base.CPWorkBase.save)
    def save(self, **kwargs):
        """Save this work file in the current dcc.

        Returns:
            (CPWorkBkp): backup file
        """
        from pini.pipe import shotgrid
        from pini.tools import error

        _bkp = super().save(**kwargs)

        # Update task on shotgrid
        if not self.entity.settings['shotgrid']['disable']:
            try:
                shotgrid.update_work_task(self)
            except Exception as _exc:  # pylint: disable=broad-except
                _LOGGER.debug(error.PEError().to_text())
                _LOGGER.error('FAILED TO UPDATE SHOTGRID %s', _exc)

        return _bkp
