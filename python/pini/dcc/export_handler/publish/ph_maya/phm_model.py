"""Tools for managing maya publish handlers."""

import logging

from maya import cmds

from pini import pipe, qt
from maya_pini import open_maya as pom, m_pipe

from . import phm_basic

_LOGGER = logging.getLogger(__name__)


class CMayaModelPublish(phm_basic.CMayaBasicPublish):
    """Manages maya model publish."""

    NAME = 'Maya Model Publish'
    LABEL = (
        'Copies this scene to the publish directory - make sure there '
        'is only one top node named MDL and that it has a cache set named '
        'cache_SET')

    def build_ui(self, parent=None, layout=None, add_footer=True):
        """Build basic render interface into the given layout.

        Args:
            parent (QWidget): parent widget
            layout (QLayout): layout to add widgets to
            add_footer (bool): add footer elements
        """
        super(CMayaModelPublish, self).build_ui(
            parent=parent, layout=layout, add_footer=False)

        self.ui.FreezeTfms = self.add_checkbox_elem(
            val=True, name='FreezeTfms',
            label="Freeze transforms")
        self.ui.DeleteHistory = self.add_checkbox_elem(
            val=True, name='DeleteHistory')
        self.add_separator_elem()
        if add_footer:
            self.add_footer_elems()

    def publish(
            self, work=None, force=False, revert=True, metadata=None,
            sanity_check_=True, export_abc=None, export_fbx=None,
            references=None, version_up=None):
        """Execute this publish.

        Args:
            work (CPWork): override work
            force (bool): force overwrite without confirmation
            revert (bool): revert to work file on completion
            metadata (dict): override metadata
            sanity_check_ (bool): apply sanity check
            export_abc (bool): whether to export rest cache abc
            export_fbx (bool): whether to export rest cache fbx
            references (str): how to handle references (eg. Remove)
            version_up (bool): whether to version up on publish

        Returns:
            (CPOutput): publish file
        """
        _LOGGER.info('PUBLISH')

        _work = work or pipe.cur_work()
        if not _work.job.find_templates('publish'):
            qt.notify(
                'No publish template found in this job:\n\n{}\n\n'
                'Unable to publish.'.format(_work.job.path),
                title='Warning', parent=self.parent)
            return None

        _data = metadata or self.build_metadata(
            work=work, force=force, sanity_check_=sanity_check_, task='model')

        _del_history = self.ui.DeleteHistory.isChecked() if self.ui else True
        _freeze_tfms = self.ui.FreezeTfms.isChecked() if self.ui else True

        self._clean_geos(
            delete_history=_del_history, freeze_tfms=_freeze_tfms)

        # Execute publish
        _outs = super(CMayaModelPublish, self).publish(
            work=work, force=force, revert=False, metadata=_data,
            export_abc=export_abc, export_fbx=export_fbx,
            references=references, version_up=False)

        if revert:
            _work.load(force=True)
            self._apply_version_up(version_up=version_up)

        return _outs

    def _clean_geos(
            self, delete_history=True, freeze_tfms=True,
            setup_pref=False):
        """Clean geometry.

        Args:
            delete_history (bool): delete history
            freeze_tfms (bool): freeze transforms
            setup_pref (bool): setup Pref attribute (never got this working)
        """
        _LOGGER.info('CLEAN GEO')
        if not cmds.objExists('cache_SET'):
            _LOGGER.info(' - NO cache_SET FOUND')
            return

        _tfms = m_pipe.read_cache_set(mode='transforms')
        _LOGGER.info(' - TFMS %s', _tfms)
        for _tfm in _tfms:
            if delete_history:
                _tfm.delete_history()
            if freeze_tfms:
                _tfm.freeze_tfms()

        if setup_pref:
            _geos = pom.set_to_geos('cache_SET')
            _LOGGER.info(' - GEOS %s', _geos)
            for _geo in qt.progress_bar(
                    _geos, 'Applying Pref to {:d} geo{}'):
                for _vtx in _geo.to_vtxs():
                    _pos = pom.CPoint(cmds.xform(
                        _vtx, query=True, worldSpace=True, translation=True))
                    cmds.polyColorPerVertex(_vtx, colorRGB=_pos.to_tuple())
