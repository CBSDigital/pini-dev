"""Tools for managing cacheable entities on a sg-based pipeline."""

import logging

from ..ccp_utils import pipe_cache_on_obj, pipe_cache_to_file
from . import ccp_ety_base

_LOGGER = logging.getLogger(__name__)


class CCPEntitySG(ccp_ety_base.CCPEntityBase):
    """Represents a cacheable entity on a sg-based pipeline."""

    def _update_outputs_cache(self, force=True):
        """Rebuild outputs cache on this entity.

        Args:
            force (bool): provided for symmetry
        """
        _LOGGER.info('UPDATE OUTPUTS CACHE')
        # self.sg_entity.find_pub_files(force=True)
        self._read_outputs(force=True)
        # asdasd
        # self.job.find_outputs(force=True)

    def _update_publishes_cache(self):
        """Rebuild published file cache."""
        self._read_publishes(force=True)
        # asdasdasd
        # self.job.find_publishes(force=True)

    def obt_work_dir(self, match, catch=False):
        """Find a work dir object within this entity.

        Args:
            match (CPWorkDir): work dir to find
            catch (bool): no error if fail to find work dir

        Returns:
            (CCPWorkDir): matching work dir
        """
        # from pini import pipe
        # if isinstance(match, pipe.CPWorkDir):
        #     return self.job.obt_work_dir(match)
        raise NotImplementedError

    # def _read_work_dirs(self, class_=None, force=False):
    #     """Read all work dirs for this entity.

    #     Args:
    #         class_ (class): override work dir class
    #         force (bool): rebuild cache

    #     Returns:
    #         (CCPWorkDir): work dirs
    #     """
    #     if class_:
    #         raise NotImplementedError(class_=
    #     return super()._read_publishes(class
    #     _LOGGER.debug('READ WORK DIRS %s %s', nice_id(self), self)
    #     _work_dirs = sorted(
    #         self.job.find_work_dirs(entity=self, force=force))
    #     _LOGGER.debug(' - FOUND %d WORK DIRS %s', len(_work_dirs), _work_dirs)
    #     return _work_dirs

    @pipe_cache_on_obj
    def _read_outputs(self, force=False):
        """Read outputs in this entity.

        Args:
            force (bool): force reread from shotgrid

        Returns:
            (CCPOutput list): outputs
        """
        _LOGGER.info('READ OUTPUTS %s', self)
        from pini import pipe
        from pini.pipe import cache

        if force:
            _LOGGER.debug(' - UPDATING SGC')
            self.sg_entity.find_pub_files(force=True)

        _out_cs = []
        _out_us = super()._read_outputs()
        for _out_u in _out_us:
            _LOGGER.debug('   - OUT %s', _out_u)
            _kwargs = {
                'template': _out_u.template,
                'entity': self,
                'latest': _out_u.sg_pub_file.latest}
            if isinstance(_out_u, pipe.CPOutputVideo):
                _out_c = cache.CCPOutputVideo(_out_u, **_kwargs)
            elif isinstance(_out_u, pipe.CPOutputFile):
                _out_c = cache.CCPOutputFile(_out_u, **_kwargs)
            elif isinstance(_out_u, pipe.CPOutputSeq):
                _LOGGER.debug('     - URL %s', _out_u.sg_pub_file.to_url())
                _out_c = cache.CCPOutputSeq(_out_u, **_kwargs)
                _LOGGER.debug('     - CACHE FMT %s', _out_c.cache_fmt)
            else:
                raise ValueError(_out_u)
            _LOGGER.debug('     - OUT C %s', _out_c)
            _out_cs.append(_out_c)
        _LOGGER.debug(' - FOUND %d OUTS', len(_out_cs))
        return _out_cs

    @pipe_cache_to_file
    def _read_publishes(self, force=False):
        """Read all publishes in this entity.

        Args:
            force (bool): rebuild disk cache

        Returns:
            (CPOutput list): all publishes
        """
        _LOGGER.debug('READ PUBLISHES %s', self)
        _LOGGER.debug(' - CACHE FMT %s', self.cache_fmt)
        _pubs = []
        _c_types = set()
        for _out in self.find_outputs():
            _LOGGER.debug(' - OUT %s', _out)
            _LOGGER.debug('   - CONTENT TYPE %s', _out.content_type)
            if _out.content_type in ('Video', 'Render', 'Video', 'Exr'):
                continue
            _c_types.add(_out.content_type)
            _pub = _out.to_ghost()
            _LOGGER.debug('   - PUB %s', _pub)
            _pubs.append(_pub)
        _c_types = sorted(_c_types)
        _LOGGER.debug(' - FOUND %d CONTENT TYPES %s', len(_c_types), _c_types)
        _LOGGER.info(' - FOUND %d PUBS %s', len(_pubs), self)
        return _pubs

    def _obt_output_cacheable(self, output, catch, force):
        """Obtain cacheable version of the given output.

        Args:
            output (CPOutput): output to convert
            catch (bool): no error if no output found
            force (bool): reread outputs from disk

        Returns:
            (CCPOutput): cacheable output
        """
        from pini import pipe
        from ... import cache

        _LOGGER.debug(' - OBTAINED OUTPUT %s', output)
        assert output.entity == self
        _LOGGER.debug(' - SEARCHING ENTITY OUTPUTS')
        _out = self.find_output(output, catch=catch)
        _LOGGER.debug(' - FOUND OUTPUT %s', _out)

        # Check output
        if _out:
            assert isinstance(_out, pipe.CPOutputBase)
            assert isinstance(_out, cache.CCPOutputBase)

        return _out
