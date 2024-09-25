"""Tools for managing cacheable output file objects."""

import logging
import operator

from pini.utils import single, File, EMPTY

from ... import elem
from . import ccp_out_base

_LOGGER = logging.getLogger(__name__)


class CCPOutputFile(elem.CPOutputFile, ccp_out_base.CCPOutputBase):
    """Represents an output on disk with built in caching."""

    get_metadata = ccp_out_base.CCPOutputBase.get_metadata
    set_metadata = ccp_out_base.CCPOutputBase.set_metadata
    _exists = True

    yaml_tag = '!CCPOutputFile'

    @classmethod
    def from_yaml(cls, loader, node):
        """Build output object from yaml.

        Args:
            cls (class): output class
            loader (Loader): yaml loader
            node (Node): yaml data

        Returns:
            (CPOutput): output
        """
        from pini import pipe

        _LOGGER.debug('FROM YAML cls=%s loader=%s node=%s', cls, loader, node)
        del loader  # for linter
        _path = pipe.map_path(node.value)
        _LOGGER.debug(' - PATH %s', _path)

        # Allocate work dir
        _work_dir_c = None
        _work_dir = pipe.to_work_dir(_path)
        if _work_dir:
            _work_dir_c = pipe.CACHE.obt_work_dir(_work_dir)
        _LOGGER.debug(' - WORK DIR %s', _work_dir_c)

        # Allocate entity
        _ety_c = None
        if _work_dir_c:
            _ety_c = _work_dir_c.entity
        else:
            _ety = pipe.to_entity(_path)
            _ety_c = pipe.CACHE.obt_entity(_ety)
        _LOGGER.debug(' - ENTITY %s', _ety_c)

        _out_c = cls(_path, work_dir=_work_dir_c, entity=_ety_c)
        _LOGGER.debug(' - OUT %s', _out_c)
        return _out_c

    def delete(self, force=False):  # pylint: disable=arguments-differ
        """Delete this output file and update parent caches.

        Args:
            force (bool): delete without confirmation
        """
        super().delete(force=force)
        _parent = self.work_dir or self.entity
        _parent.find_outputs(force=True)
        self._exists = False

    def exists(self, force=False):  # pylint: disable=arguments-differ
        """Test whether this output exists.

        Args:
            force (bool): force read exists from disk

        Returns:
            (bool): whether exists
        """
        if force:
            self._exists = File(self).exists()
        return self._exists

    def find_lookdev_shaders(self, tag=EMPTY):
        """Find matching lookdev for this output.

        This is used to find a lookdev publish to attach to an abc export.
        Any lookdev publish in the same asset should be allowed to attach to
        to this output.

        Lookdevs are matched in this order:
         - matching tag
         - default tag
         - any tag

        Args:
            tag (str): force tag to attach

        Returns:
            (CPOutputFile): matching lookdev
        """
        from pini import pipe
        _LOGGER.debug('FIND LOOKDEV %s', self)

        # Ignore ouputs without lookdev
        _pub_type = self.metadata.get('publish_type')
        _LOGGER.debug(' - PUB TYPE %s', _pub_type)
        if _pub_type in ('CMayaLookdevPublish', ):
            return None
        _out_type = self.metadata.get('type')
        if _out_type in ('CPCacheableCam', ):
            return None

        # Find asset
        _asset = _out = None
        if self.profile == 'asset':
            _out = self
            _asset = self.entity
        if not _asset:
            _asset_path = pipe.map_path(self.metadata.get('asset'))
            if _asset_path:
                _out = pipe.to_output(_asset_path)
                _out = pipe.CACHE.obt(_out)
                _asset = _out.entity
        if not _asset:
            _LOGGER.debug(' - NO ASSET FOUND')
            return None
        _LOGGER.debug(' - ASSET %s', _asset)

        # Find lookdevs
        _lookdevs = _out.entity.find_publishes(
            content_type='ShadersMa', tag=tag, ver_n='latest')
        _LOGGER.debug(' - LOOKDEVS %d %s', len(_lookdevs), _lookdevs)
        if not _lookdevs:
            return None

        # Match to tag
        _tags = sorted(
            {_lookdev.tag for _lookdev in _lookdevs}, key=pipe.tag_sort)
        _default_tag = self.job.cfg['tokens']['tag']['default']
        if _out.tag in _tags:
            _tag = _out.tag
        elif _default_tag in _tags:
            _tag = _default_tag
        else:
            _tag = _tags[0]
        _LOGGER.debug(' - APPLY TAG FILTER %s %s', _tag, _tags)
        _lookdevs = [_lookdev for _lookdev in _lookdevs if _lookdev.tag == _tag]
        _LOGGER.debug(' - LOOKDEVS %d %s', len(_lookdevs), _lookdevs)

        # Return most recent if multiple
        if len(_lookdevs) == 1:
            _ld_pub = single(_lookdevs)
        else:
            _LOGGER.debug(' - APPLYING DATE SORT')
            _lookdevs.sort(key=operator.methodcaller('mtime'))
            _ld_pub = _lookdevs[-1]
            _LOGGER.debug(' - RECENT %s', _ld_pub)
        _ld = pipe.CACHE.obt(_ld_pub)

        return _ld
