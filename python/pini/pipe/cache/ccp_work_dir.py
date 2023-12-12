"""Tools for managing cacheable work objects."""

import functools
import logging

from pini.utils import single

from .ccp_utils import pipe_cache_on_obj, pipe_cache_to_file
from ..cp_work_dir import CPWorkDir
from ..cp_work import CPWork

_LOGGER = logging.getLogger(__name__)


class CCPWorkDir(CPWorkDir):
    """Represents a task work file directory on disk."""

    _badly_named_files = None

    @property
    def cache_fmt(self):
        """Obtain cache format string for storing work dir data.

        Returns:
            (str): cache format
        """
        return self.to_file('.pini/cache/{func}.yml').path

    @property
    def works(self):
        """Obtain list of works in this work dir.

        Returns:
            (CCPWork tuple): tuple of works
        """
        return tuple(self.find_works())

    @property
    def badly_named_files(self):
        """Get number of badly named files in this work dir.

        Returns:
            (int): badly named files count
        """
        if self._badly_named_files is not None:
            return self._badly_named_files
        _, _badly_named_files = self._read_works_data()
        return _badly_named_files

    def set_badly_named_files(self, value):
        """Set number of badly named files.

        This allows the result to be forced - if we are creating
        a lot of new workdirs on the fly (eg. if someone is typing
        a task name), we don't want to keep checking disk.

        Args:
            value (int): value to apply
        """
        self._badly_named_files = value

    def create(self, force=False):
        """Create this work dir.

        Args:
            force (bool): create any parent entity without
                confirmation
        """
        _new_entity = not self.entity.exists()
        super(CCPWorkDir, self).create(force=force)
        if _new_entity:
            self.entity = self.job.find_entity(self.entity)
        if self not in self.entity.work_dirs:
            self.entity.find_work_dirs(force=True)
            assert self in self.entity.work_dirs

    def obt_work(self, match, catch=False):
        """Obtain a work file within this work dir's cache.

        Args:
            match (CPWork): work file to match
            catch (bool): no error of not matching work found

        Returns:
            (CCPWork): matching work file
        """
        if isinstance(match, CPWork):
            return single(
                [_work for _work in self.works if _work == match],
                catch=catch)
        raise NotImplementedError(match)

    def find_works(self, force=False, **kwargs):
        """Find works in this work dir.

        Args:
            force (bool): force reread from disk

        Returns:
            (CCPWork list): matching works
        """
        _works, _ = self._read_works_data(force=force)

        # Update has_works cache file
        if _works and not self.has_works():
            self.has_works(force=True, value=True)

        return super(CCPWorkDir, self).find_works(**kwargs)

    @pipe_cache_on_obj
    def _read_works_data(self, class_=None, force=False):
        """Read works from disk + cache result.

        Args:
            class_ (class): override work class
            force (bool): force rebuild cache from disk

        Returns:
            (CCPWork list): all works
        """
        from pini.pipe import cache
        _LOGGER.debug('READ WORKS force=%d %s', force, self)
        _works, _badly_named_files = super(CCPWorkDir, self)._read_works_data(
            class_=class_ or cache.CCPWork)
        _LOGGER.debug(' - WORKS %s', _works)
        return _works, _badly_named_files

    @pipe_cache_to_file
    def has_works(self, force=False, value=None):
        """Test if this work dir has work files.

        (Used by pini loader + cached to disk for speed)

        Args:
            force (bool): force reread from disk
            value (bool): force value rather than reading from disk

        Returns:
            (bool): whether work files exist
        """
        if value is not None:
            _val = value
        else:
            _works, _ = self._read_works_data(force=force)
            _val = bool(_works)
        return _val

    @property
    def outputs(self):
        """Obtain list of outputs within this work dir.

        Returns:
            (CPOutput list): outputs
        """
        return tuple(self.find_outputs())

    def find_outputs(self, force=False, **kwargs):
        """Find outputs within this work dir.

        Args:
            force (bool): force reread from disk

        Returns:
            (CCPOutput list): outputs
        """
        _LOGGER.debug('FIND OUTPUTS force=%d %s', force, self)
        if force:
            self._read_outputs(force=True)
            _LOGGER.debug(' - UPDATED CACHE %s', self)
        return super(CCPWorkDir, self).find_outputs(**kwargs)

    @functools.wraps(CPWorkDir.to_work)
    def to_work(self, **kwargs):
        """Build a work object using this work dir's data.

        Returns:
            (CCPWork): work object
        """
        from pini.pipe import cache
        _LOGGER.debug('TO WORK %s %s', kwargs, self)

        # Obtain work object to match with
        _work = super(CCPWorkDir, self).to_work(**kwargs)
        _LOGGER.debug(' - WORK %s', _work)
        _LOGGER.debug(' - WORK DIR %s', _work.work_dir)
        if not _work:
            return None
        _work_c = self.obt_work(_work, catch=True)
        _LOGGER.debug(' - WORK C %s', _work_c)
        if _work_c:
            return _work_c

        # Create dummy non-existing work
        _work_dir_c = self.entity.obt_work_dir(_work.work_dir)
        _work_c = cache.CCPWork(_work, work_dir=_work_dir_c)
        _work_c.set_exists(False)
        return _work_c

    @pipe_cache_on_obj
    def _read_outputs(self, class_=None, force=False):
        """Read outputs within this work dir from disk.

        Args:
            class_ (class): override work dir class
            force (bool): force reread from disk

        Returns:
            (CPOutput list): outputs
        """
        from pini.pipe import cache
        _LOGGER.debug('READ OUTPUTS force=%d %s', force, self)
        return super(CCPWorkDir, self)._read_outputs(
            class_=class_ or cache.CCPOutput)
