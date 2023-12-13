"""Tools for managing basic publishes."""

import logging

from pini import pipe, qt
from pini.pipe import cache
from pini.qt import QtWidgets

from .. import eh_base

_LOGGER = logging.getLogger(__name__)


class CBasicPublish(eh_base.CExportHandler):
    """Manages a basic publish."""

    NAME = 'Basic Publish'
    LABEL = 'Makes a copy of this scene in the publish directory'
    ACTION = 'publish'

    def obtain_metadata(self, work=None, sanity_check_=True, force=False):
        """Obtain metadata for this publish.

        Args:
            work (CPWork): override workfile to read metadata from
            sanity_check_ (bool): run sanity checks before publish
            force (bool): force completion without any confirmations

        Returns:
            (dict): metadata
        """
        _data = super(CBasicPublish, self).obtain_metadata(
            work=work, sanity_check_=sanity_check_, force=force)
        _data['publish_type'] = type(self).__name__
        return _data

    def build_ui(self, parent=None, layout=None, add_footer=True):
        """Build basic render interface into the given layout.

        Args:
            parent (QWidget): parent widget
            layout (QLayout): layout to add widgets to
            add_footer (bool): add footer elements
        """
        self.ui.Label = QtWidgets.QLabel(self.LABEL, parent)
        self.ui.Label.setWordWrap(True)
        self.ui.Label.setObjectName('Label')
        layout.addWidget(self.ui.Label)

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
        _metadata = self.obtain_metadata(work=_work, force=force)
        _work.save(reason='published', force=force)
        _LOGGER.info('SAVED SCENE')
        _work.copy_to(_pub, force=force)
        _LOGGER.info(' - PUBLISHED VERSIONED FILE %s', _pub.path)

        # Write metadata
        _pub.set_metadata(_metadata)

        self.create_versionless(work=_work, metadata=_metadata, publish=_pub)

        self.post_publish(work=_work, outs=[_pub])

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

    def post_publish(self, work, outs, version_up=None):
        """Execute post publish code.

        This manages updating the shot publish cache and cache and can
        also be extended in subclasses.

        Args:
            work (CPWork): source work file
            outs (CPOutput list): outputs that were generated
            version_up (bool): whether to version up on publish
        """
        _LOGGER.info('POST PUBLISH %s', work.path)
        _LOGGER.info(' - OUTS %d %s', len(outs), outs)

        # Update entity cache
        _ety_c = work.entity
        if not isinstance(work.entity, cache.CCPEntity):
            _ety_c = pipe.CACHE.obt_entity(_ety_c)
        _LOGGER.info(' - UPDATING ENTITY PUBLISH CACHE %s', _ety_c)
        _ety_c.find_publishes(force=True)

        # Register in shotgrid
        if pipe.SHOTGRID_AVAILABLE:
            from pini.pipe import shotgrid
            for _out in outs:
                if _out.asset_type == 'test':
                    continue
                try:
                    shotgrid.create_pub_file(_out)
                except shotgrid.MissingPipelineStep:
                    qt.notify(
                        'Failed to find pipeline step for output:\n\n{}'.format(
                            _out.path),
                        title='Shotgrid Register Failed', icon=shotgrid.ICON)

        # Update work outputs cache
        _work = pipe.CACHE.obt_work(work)  # Has been rebuilt
        _work.find_outputs(force=True)

        _version_up = (
            version_up if version_up is not None
            else self.ui.VersionUp.isChecked())
        if _version_up:
            pipe.version_up()
