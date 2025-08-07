"""Tools for managing cacheable entities on a sg-based pipeline."""

import logging

from pini.utils import single, CacheOutdatedError

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
        self._read_outputs(force=force)

    def _update_publishes_cache(self):
        """Rebuild published file cache."""
        self.sg_entity.find_pub_files(force=True)
        super()._update_publishes_cache()

    def obt_work_dir(self, match, catch=False):
        """Find a work dir object within this entity.

        Args:
            match (CPWorkDir): work dir to find
            catch (bool): no error if fail to find work dir

        Returns:
            (CCPWorkDir): matching work dir
        """
        _work_dirs = self.find_work_dirs()
        _matches = [
            _work_dir for _work_dir in _work_dirs
            if match in (_work_dir, _work_dir.path, _work_dir.task)]
        if len(_matches) == 1:
            return single(_matches)
        if catch:
            return None
        raise ValueError(match)

    @pipe_cache_on_obj
    def _read_outputs(self, force=False):  # pylint: disable=arguments-renamed
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
            self.sg_entity.find_pub_files(force=force)

        # Read outputs
        _out_cs = []
        try:
            _out_us = super()._read_outputs()
        except CacheOutdatedError:
            _LOGGER.error('FORCE REBUILD OUTPUTS CACHE %s', self)
            _out_us = super()._read_outputs(force=max((force, True)))  # pylint: disable=unexpected-keyword-arg

        # Rebuild outputs into cacheable objects
        for _out_u in _out_us:

            _LOGGER.debug('   - OUT %s', _out_u)

            # Build shared kwargs
            _work_dir = single([
                _work_dir for _work_dir in self.work_dirs
                if _work_dir.contains(_out_u.path)], catch=True)
            _kwargs = {
                'template': _out_u.template,
                'entity': self,
                'work_dir': _work_dir,
                'latest': _out_u.is_latest()}

            # Build cacheable
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
            _out_c.sg_pub_file = _out_u.sg_pub_file
            _out_c.status = _out_u.status
            _out_cs.append(_out_c)

        _LOGGER.debug(' - FOUND %d OUTS', len(_out_cs))

        return sorted(_out_cs)

    @pipe_cache_on_obj
    def _read_linked_outputs(self, force=False):
        """Read linked outputs for this entity.

        Args:
            force (bool): force reread from disk

        Returns:
            (CCPOutput list): outputs
        """
        _outs = []
        for _asset in self._find_linked_assets():
            _asset_pubs = _asset.find_publishes()
            _outs += _asset_pubs
            _LOGGER.info('   - ADDED %d PUBS %s', len(_asset_pubs), _asset)
        return _outs

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

        # Read publishes
        _pubs = []
        for _out in self.find_outputs():
            _LOGGER.debug(' - OUT %s', _out)
            _LOGGER.debug('   - CONTENT TYPE %s', _out.content_type)
            if _out.is_media():
                continue
            assert not _out.is_media()
            _pub = _out.to_ghost()
            _LOGGER.debug('   - PUB %s', _pub)
            _LOGGER.debug('   - CONTENT TYPE %s', _pub.content_type)
            assert not _pub.is_media()
            _pubs.append(_pub)
        _LOGGER.info('   - ADDED %d PUBS %s', len(_pubs), self)

        return sorted(_pubs)

    def _find_linked_assets(self):
        """Find assets linked to this entity.

        (only applicable to shots)

        Returns:
            (CPAsset list): linked assets
        """
        from pini import pipe
        from pini.pipe import shotgrid

        if self.profile == 'asset':
            yield from []
            return
        assert self.profile == 'shot'
        assert 'assets' in self.sg_entity.data
        if not self.sg_entity.data['assets']:
            yield from []
            return

        # Map ids to asset objects
        _ids = [_item['id'] for _item in self.sg_entity.data['assets']]
        _LOGGER.debug(' - IDS %s', _ids)
        for _asset_d in shotgrid.find(
                'Asset', ids=_ids, fields=['project', 'code', 'sg_asset_type']):
            _LOGGER.debug(' - ADDING ASSET %s', _asset_d)
            _proj = shotgrid.SGC.find_proj(_asset_d['project']['id'])
            _LOGGER.debug('   - PROJ %s', _proj)
            _job = pipe.CACHE.find_job(_proj.name)
            _LOGGER.debug('   - JOB %s', _job)
            _asset = _job.find_asset(
                asset=_asset_d['code'],
                asset_type=_asset_d['sg_asset_type'])
            _LOGGER.debug('   - ASSET %s', _asset)
            yield _asset

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
        _out = self.find_output(path=output.path, catch=catch)
        _LOGGER.debug(' - FOUND OUTPUT %s', _out)

        # Check output
        if _out:
            assert isinstance(_out, pipe.CPOutputBase)
            assert isinstance(_out, cache.CCPOutputBase)

        return _out
