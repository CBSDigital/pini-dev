"""Tools for managing cacheable entity elements."""

import functools
import logging

from pini.utils import single

from ..ccp_utils import pipe_cache_on_obj, pipe_cache_to_file
from ...elem import CPEntity

_LOGGER = logging.getLogger(__name__)


class CCPEntityBase(CPEntity):
    """Cacheable version of the base entity object."""

    @property
    def cache_fmt(self):
        """Build cache path format.

        Returns:
            (str): cache format
        """
        from pini import pipe
        _ver = pipe.VERSION
        return f'{self.path}/.pini/cache/pipe_{_ver:d}/{{func}}.pkl'

    @property
    def outputs(self):
        """Obtain list of outputs in this entity.

        Returns:
            (CPOutput tuple): all entity-level outputs
        """
        return tuple(self.find_outputs())

    @property
    def work_dirs(self):
        """Access the list of tasks in this entity.

        Returns:
            (str list): tasks
        """
        return tuple(self.find_work_dirs())

    def obt_output(self, match, catch=False, force=False):
        """Obtain output output withing this entity.

        Args:
            match (any): token to match with output
            catch (bool): no error if no output found
            force (bool): reread outputs from disk

        Returns:
            (CPOutput): matching output
        """
        from pini import pipe

        if force:
            self.find_outputs(force=True)

        _match = match
        if isinstance(_match, pipe.CPOutputBase):
            _out = self.find_output(
                output_name=_match.output_name, task=_match.task,
                output_type=_match.output_type, ver_n=_match.ver_n,
                tag=_match.tag, extn=_match.extn, catch=catch)
            return _out

        raise NotImplementedError

    def find_outputs(  # pylint: disable=arguments-differ
            self, type_=None, content_type=None, force=False, **kwargs):
        """Find outputs in this entity (stored at entity level).

        Args:
            type_ (str): filter by type (eg. cache/render) - it is declared here
                to promote it to the first arg
            content_type (str): filter by content type (this attr is unique to
                cache outputs)
            force (bool): force reread from disk

        Returns:
            (CCPOutput list): entity level outputs
        """
        _LOGGER.debug('FIND OUTPUTS force=%d %s', force, self)
        if force:
            self._update_outputs_cache(force=force)

        # Apply outputs filter
        _outs = []
        for _out in super().find_outputs(type_=type_, **kwargs):
            if content_type and _out.content_type != content_type:
                continue
            _outs.append(_out)

        return _outs

    def find_publish(self, match=None, catch=False, **kwargs):
        """Find publish within this entity.

        Args:
            match (str): match by name/path
            catch (bool): no error if no match found

        Returns:
            (CPOutputGhost|None): matching publish
        """
        _pubs = self.find_publishes(**kwargs)
        if len(_pubs) == 1:
            return single(_pubs)
        if catch:
            return None
        _LOGGER.info(' - MATCHED %d PUBS %s', len(_pubs), _pubs[:5])
        raise ValueError(match or kwargs)

    def find_publishes(self, task=None, force=False, **kwargs):
        """Find publishes within this entity.

        Publishes are cached to disk a entity level, so a force flag
        is added here.

        Args:
            task (str): apply task filter
            force (bool): force reread from disk

        Returns:
            (CPOutputGhost list): publishes
        """
        from pini import pipe
        _LOGGER.debug('FIND PUBLISHES %s', self)
        _pubs = []
        for _pub in self._read_publishes(force=force):
            if not pipe.passes_filters(_pub, task=task, **kwargs):
                continue
            _pubs.append(_pub)
        return _pubs

    def _read_publishes(self, force=False):
        """Read all publishes in this entity.

        Args:
            force (bool): rebuild disk cache

        Returns:
            (CPOutput list): all publishes
        """
        raise NotImplementedError

    def _update_outputs_cache(self, force=True):
        """Rebuild outputs cache on this entity.

        Args:
            force (bool|int): force level
        """
        raise NotImplementedError

    def obt_work_dir(self, match, catch=False):
        """Find a work dir object within this entity.

        Args:
            match (CPWorkDir): work dir to find
            catch (bool): no error if fail to find work dir

        Returns:
            (CCPWorkDir): matching work dir
        """
        raise NotImplementedError

    def find_work_dirs(self, task=None, force=False, **kwargs):
        """Find work dirs.

        Args:
            task (str): apply task filter
            force (bool): force reread from disk

        Returns:
            (CCPWorkDir list): work dirs
        """
        if force:
            self._read_work_dirs(force=True)
        return super().find_work_dirs(task=task, **kwargs)

    # def _read_work_dirs(self, class_=None, force=False):
    #     """Read all work dirs for this entity.

    #     Args:
    #         class_ (class): override work dir class
    #         force (bool): rebuild cache

    #     Returns:
    #         (CCPWorkDir): work dirs
    #     """
    #     return super()._read_work_dirs(class_=class_)

    @pipe_cache_on_obj
    def _read_work_dirs(self, class_=None, force=False):
        """Read all work dirs for this entity.

        Args:
            class_ (class): override work dir class
            force (bool): rebuild cache

        Returns:
            (CCPWorkDir): work dirs
        """
        from ... import cache
        _LOGGER.debug('READ WORK DIRS %s', self)
        if class_:
            raise NotImplementedError
        _work_dirs = super()._read_work_dirs(class_=cache.CCPWorkDir)
        _LOGGER.debug(' - FOUND %d WORK DIRS %s', len(_work_dirs), _work_dirs)
        return _work_dirs

    def to_work_dir(self, *args, **kwargs):
        """Obtain a work dir object within this entity.

        If an existing work dir is not found, a new one is created.

        Args:
            task (str): work dir task
            dcc_ (str): work dir dcc
            catch (bool): no error if token fail to create valid
                work dir object (just return None)
            class_ (class): override work dir class

        Returns:
            (CCPWorkDir): work dir
        """
        from ... import cache
        _class = kwargs.pop('class_', None) or cache.CCPWorkDir
        _work_dir = super().to_work_dir(
            *args, class_=_class, **kwargs)
        _existing = single([
            _o_work_dir for _o_work_dir in self.work_dirs
            if _work_dir == _o_work_dir], catch=True)
        if _existing:
            return _existing
        return _work_dir

    @functools.wraps(CPEntity.to_work)
    def to_work(self, **kwargs):
        """Obtain a work object within this entity.

        If a matching one does not exist, a new object is created.

        Returns:
            (CCPWork): work
        """
        from ... import cache
        _kwargs = kwargs
        _kwargs['class_'] = _kwargs.get('class_', cache.CCPWork)
        return super().to_work(**_kwargs)

    def flush(self, force=False):
        """Flush contents of this entity.

        Args:
            force (bool): remove elements without confirmation
        """
        from pini import pipe

        _LOGGER.info('FLUSH %s', self)

        # Remove contents
        assert self.name == 'tmp'
        super().flush(force=force)

        # Update caches
        self.find_outputs(force=True)
        if self.profile == pipe.ASSET_PROFILE:
            self.job.find_publishes(force=True)

        # Check caches
        _this = pipe.CACHE.obt(self)
        assert not _this.find_outputs()
        assert not _this.outputs
        assert not pipe.CACHE.obt(self.job).find_publishes(entity=_this)

        _LOGGER.info(' - FLUSH COMPLETE %s', self)