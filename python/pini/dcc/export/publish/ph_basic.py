"""Tools for managing basic publishes."""

# pylint: disable=abstract-method

import logging

from pini import pipe
from pini.pipe import cache
from pini.qt import QtWidgets
from pini.utils import find_callback

from .. import eh_base

_LOGGER = logging.getLogger(__name__)


class CBasicPublish(eh_base.CExportHandler):
    """Manages a basic publish."""

    NAME = 'Basic Publish'
    TYPE = 'Publish'
    LABEL = 'Makes a copy of this scene in the publish directory'
    ACTION = 'BasicPublish'

    def build_metadata(
            self, work=None, sanity_check_=True, task=None, force=False):
        """Obtain metadata for this publish.

        Args:
            work (CPWork): override workfile to read metadata from
            sanity_check_ (bool): run sanity checks before publish
            task (str): task to pass to sanity check
            force (bool): force completion without any confirmations

        Returns:
            (dict): metadata
        """
        _data = super().build_metadata(
            work=work, sanity_check_=sanity_check_, task=task, force=force)
        _data['publish_type'] = type(self).__name__
        return _data

    def build_ui(self, add_footer=True):
        """Build basic render interface into the given layout.

        Args:
            add_footer (bool): add footer elements
        """
        self.ui.Label = QtWidgets.QLabel(self.LABEL, self.parent)
        self.ui.Label.setWordWrap(True)
        self.ui.Label.setObjectName('Label')
        self.layout.addWidget(self.ui.Label)

        if add_footer:
            self.add_footer_elems()

    def publish(self, work=None, force=False):
        """Publish this file.

        Args:
            work (CPWork): override publish work file
            force (bool): overwrite existing without confirmation

        Returns:
            (CPOutput): new versioned output
        """
        _work = work or pipe.cur_work()
        _LOGGER.info('PUBLISH %s', _work)

        # Get versioned publish
        _pub = _work.to_output('publish', has_key={'output_type': False})
        _LOGGER.info(' - OUT VER %s', _pub)

        # Save + copy to publish dirs
        _metadata = self.build_metadata(work=_work, force=force)
        _work.save(reason='published', force=force)
        _LOGGER.info('SAVED SCENE')
        _work.copy_to(_pub, force=force)
        _LOGGER.info(' - PUBLISHED VERSIONED FILE %s', _pub.path)

        # Write metadata
        _pub.set_metadata(_metadata)

        self.create_versionless(work=_work, metadata=_metadata, publish=_pub)

        self.post_export(work=_work, outs=[_pub])

        return _pub

    def create_versionless(self, work, publish, metadata):
        """Create versionless publish.

        Args:
            work (CPWork): source work file
            publish (CPOutput): versioned publish output
            metadata (dict): publish metadata
        """
        _tmpl = work.find_template(
            'publish', has_key={'ver': False}, catch=True)
        if not _tmpl:
            _LOGGER.info('NO VERSIONLESS TEMPLATE FOUND %s', work)
            return None

        _versionless = work.to_output(_tmpl, output_name=None)
        publish.copy_to(_versionless, force=True)
        _versionless.set_metadata(metadata)
        _LOGGER.info('CREATED VERSIONLESS PUBLISH %s', _versionless.path)

        return _versionless

    def _update_pipe_cache(self, work, outs):
        """Update pipeline cache.

        Args:
            work (CPWork): work file being published
            outs (CPOutput list): outputs being published
        """
        _job_c = work.job
        _ety_c = work.entity

        _LOGGER.info(' - UPDATING CACHE')
        if not isinstance(work.entity, cache.CCPEntity):
            _ety_c = pipe.CACHE.obt_entity(_ety_c)
        _LOGGER.info(' - UPDATING ENTITY PUBLISH CACHE %s', _ety_c)
        _ety_c.find_publishes(force=True)
        _job_c.find_publishes(force=True)

        super()._update_pipe_cache(work=work, outs=outs)

    def post_export(self, outs, **kwargs):
        """Run post export scripts.

        For publish this allows any publish callback to be installed.

        Args:
            outs (CPOutput list): outputs which were generated
        """
        _LOGGER.info('POST EXPORT %s', self)
        super().post_export(outs=outs, **kwargs)

        _callback = find_callback('Publish')
        _LOGGER.info(' - PUBLISH CALLBACK %s', _callback)
        for _out in outs:
            _callback(_out)
