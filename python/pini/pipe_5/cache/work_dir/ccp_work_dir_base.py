"""Tools for managing cacheable work objects."""

import functools
import logging

from pini.utils import single

from ..ccp_utils import pipe_cache_on_obj, pipe_cache_to_file
from ...elem import CPWorkDir, CPWork

_LOGGER = logging.getLogger(__name__)


class CCPWorkDirBase(CPWorkDir):
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
        super().create(force=force)
        if _new_entity:
            self.entity = self.job.find_entity(self.entity)
        if self not in self.entity.work_dirs:
            self.entity.find_work_dirs(force=True)

    def obt_output(self, match, catch=False, force=False):
        """Obtain output object from within this work dir.

        Args:
            match (str): match by name/path
            catch (bool): no error if no matching output found
            force (bool): force rebuild cache

        Returns:
            (CCPOutput): output
        """
        _LOGGER.debug('OBT OUTPUT %s', match)
        from pini import pipe
        assert isinstance(match, pipe.CPOutputBase)
        _outs = [
            _out for _out in self.find_outputs(force=force) if _out == match]
        _LOGGER.debug(' - FOUND %d OUTPUTS %s', len(_outs), _outs)
        return single(_outs, catch=catch)

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

        return super().find_works(**kwargs)

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
        _result = super()._read_works_data(
            class_=class_ or cache.CCPWork)
        _works, _badly_named_files = _result
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

    def find_outputs(self, content_type=None, force=False, **kwargs):
        """Find outputs within this work dir.

        Args:
            content_type (str): filter by content type
            force (bool): force reread from disk

        Returns:
            (CCPOutput list): outputs
        """
        _LOGGER.debug('FIND OUTPUTS force=%d %s', force, self)

        # Apply CCPWorkDirBase specific filters
        _outs = []
        for _out in super().find_outputs(**kwargs):
            if content_type and _out.content_type != content_type:
                continue
            _outs.append(_out)

        return _outs

    @functools.wraps(CPWorkDir.to_work)
    def to_work(self, **kwargs):
        """Build a work object using this work dir's data.

        Returns:
            (CCPWork): work object
        """
        from pini.pipe import cache
        _LOGGER.debug('TO WORK %s %s', kwargs, self)

        # Obtain work object to match with
        _work = super().to_work(**kwargs)
        _LOGGER.debug(' - WORK %s', _work)
        if not _work:
            return None
        _LOGGER.debug(' - WORK DIR %s', _work.work_dir)
        _work_c = self.obt_work(_work, catch=True)
        _LOGGER.debug(' - WORK C %s', _work_c)
        if _work_c:
            return _work_c

        # Create dummy non-existing work
        _work_dir_c = self.entity.to_work_dir(
            task=_work.task, user=_work.user, step=_work.step)
        assert _work_dir_c.task == _work.task
        assert _work_dir_c.step == _work.step
        _LOGGER.debug(' - WORK DIR C %s', _work_dir_c)
        _work_c = cache.CCPWork(_work.path, work_dir=_work_dir_c)
        _work_c.set_exists(False)
        _LOGGER.debug(' - WORK C %s', _work_dir_c)
        return _work_c
