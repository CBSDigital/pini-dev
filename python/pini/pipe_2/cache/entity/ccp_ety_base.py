"""Tools for managing cacheable entity elements."""

import functools
import logging

from pini.utils import single

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

    @functools.wraps(CPEntity.find_publishes)
    def find_publishes(  # pylint: disable=arguments-differ
            self, content_type=None, force=False, **kwargs):
        """Find publishes within this entity.

        Publishes are cached to disk a entity level, so a force flag
        is added here.

        Args:
            content_type (str): apply content type filter (eg. ShadersMa)
            force (bool): force reread from disk

        Returns:
            (CCPOutput list): publishes
        """

        # Apply recache
        if force:
            self._update_publishes_cache()

        # Apply filters to publishes
        _pubs = []
        for _pub in super().find_publishes(**kwargs):
            if content_type and _pub.content_type != content_type:
                continue
            _pubs.append(_pub)

        return _pubs

    def _update_publishes_cache(self):
        """Rebuild published file cache."""
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

    def find_work_dirs(self, force=False, **kwargs):
        """Find work dirs.

        Args:
            force (bool): force reread from disk

        Returns:
            (CCPWorkDir list): work dirs
        """
        if force:
            self._read_work_dirs(force=True)
        return super().find_work_dirs(**kwargs)

    def _read_work_dirs(self, class_=None, force=False):
        """Read all work dirs for this entity.

        Args:
            class_ (class): override work dir class
            force (bool): rebuild cache

        Returns:
            (CCPWorkDir): work dirs
        """
        return super()._read_work_dirs(class_=class_)

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
        super().flush(force=force)
        self.find_outputs(force=True)
