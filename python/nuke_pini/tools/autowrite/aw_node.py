"""Tools for managing the autowrite 2.0 node."""

import logging
import re

import nuke

from pini import pipe, qt
from pini.dcc import export
from pini.pipe import cache
from pini.utils import basic_repr, single, cache_result

from nuke_pini.utils import set_node_col

from .aw_utils import (
    COL_FMT, DEFAULT_COL, NON_DEFAULT_COL, UpdateLevel, RENDER_COL,
    PLATE_COL, FILE_COL, ERROR_COL)

_LOGGER = logging.getLogger(__name__)
_RES_MAP = {
    (640, 640): 'insta',
    (1920, 1080): 'HD',
    (3840, 2160): 'UHD',
    (1080, 1920): 'HDv',
    (1920, 1920): 'HDsq',
    (1000, 1000): '1Ksq',
    (2000, 2000): '2Ksq',
}


class CAutowrite:
    """Represents an autowrite 2.0 node."""

    def __init__(self, node):
        """Constructor.

        Args:
            node (Node): autowrite 2.0 node
        """
        _node = node
        if isinstance(_node, str):
            _node = nuke.toNode(_node)
        self.node = _node

        _knob = self['is_pini_autowrite_2']
        if not _knob:
            raise ValueError(
                f'Missing {_node.name()}.is_pini_autowrite_2')

    @property
    def entity(self):
        """Obtain current node entity.

        Returns:
            (CPEntity): entity
        """
        _job = pipe.cur_job()
        _ety_type = self['ety_type'].value()
        _ety = self['ety'].value()
        return _job.find_entity(_ety)

    @property
    def output(self):
        """Obtain current node output.

        Returns:
            (CPOutput|CPOutputSeq): output
        """
        return pipe.to_output(self['file'].value())

    def jump_to(self, path):
        """Jump this node to the given path.

        Args:
            path (str): path to jump to
        """
        _ety = pipe.to_entity(path)
        self['ety_type_mode'].setValue('Select')
        self['ety_type'].setValue(_ety.entity_type)

        _work_dir = pipe.to_work_dir(path)
        self['task_mode'].setValue('Select')
        self['task'].setValue(_work_dir.task)

    def _apply_render(self):
        """Executed post-render.

        Register render in the pipeline.
        """
        _LOGGER.info('APPLY RENDER %s', self.output)

        _work = pipe.CACHE.cur_work
        if not _work:
            _LOGGER.info(' - NO CURRENT WORK')
            return
        _LOGGER.info(' - UPDATING OUTPUTS %s', _work)

        assert self.output.exists()
        _metadata = export.build_metadata(handler='PiniAutowrite')
        self.output.set_metadata(_metadata)
        if pipe.MASTER == 'shotgrid':
            from pini.pipe import shotgrid
            shotgrid.create_pub_file_from_output(self.output)

        _work.update_outputs()

    def _update_ety_type(self, level):
        """Update entity type.

        Args:
            level (UpdateLevel): level of update

        Returns:
            (str): selected entity type
        """
        if not pipe.CACHE.cur_work:
            return None
        if pipe.CACHE.cur_work.profile == 'asset':
            _ety_types = pipe.CACHE.cur_job.asset_types
        elif pipe.CACHE.cur_work.profile == 'shot':
            _ety_types = [
                _seq.name for _seq in pipe.CACHE.cur_job.find_sequences()]
        else:
            raise ValueError(pipe.CACHE.cur_work)

        if level <= UpdateLevel.ENTITY_TYPE:
            _LOGGER.debug(' - UPDATE ENITITY TYPE')
            _mode = self['ety_type_mode'].value()
            _cur = self['ety_type'].value()
            if _mode == 'Select' and _cur in _ety_types:
                _val = _cur
            else:
                _val = pipe.CACHE.cur_work.entity_type
            self['ety_type'].setValues(_ety_types)
            self['ety_type'].setValue(_val)

        return self['ety_type'].value()

    def _update_ety(self, level, ety_type):
        """Update entity.

        Args:
            level (UpdateLevel): level of update
            ety_type (str): entity type

        Returns:
            (CPEntity): selected entity
        """
        _LOGGER.debug('UPDATE ETY cur=%s level=%s', self['ety'].value(), level)
        if not pipe.CACHE.cur_work:
            return None

        if ety_type == pipe.CACHE.cur_work.entity_type:
            self['ety_mode'].setEnabled(True)
        else:
            _LOGGER.debug(' - FORCE ETY TO SELECT %s %s', ety_type,
                          pipe.CACHE.cur_work.entity_type)
            self['ety_mode'].setEnabled(False)
            self['ety_mode'].setValue('Select')

        # Repopulate list
        if level <= UpdateLevel.ENTITY:
            _mode = self['ety_mode'].value()
            _cur = self['ety'].value()
            _LOGGER.debug(' - UPDATING VALUES mode=%s cur=%s', _mode, _cur)
            _etys = pipe.CACHE.cur_job.find_entities(entity_type=ety_type)
            _vals = [_ety.name for _ety in _etys]
            if _mode == 'Select' and _cur and _cur in _vals:
                _val = _cur
            else:
                _val = pipe.CACHE.cur_work.entity.name
            self['ety'].setValues(_vals)
            self['ety'].setValue(_val)

        # Map selection back to entity for result
        _ety = single([
            _ety for _ety in pipe.CACHE.cur_job.entities
            if _ety.name == self['ety'].value() and
            _ety.entity_type == self['ety_type'].value()])
        _LOGGER.debug(' - UPDATE ETY COMPLETE %s', _ety)

        return _ety

    def _update_pipeline_ui(self):
        """Update pipeline knob ui settings (not opts/values)."""

        # Update entity type label
        _work = pipe.CACHE.cur_work
        if not _work:
            _ety_type_label = 'sequence'
            _ety_label = 'shot'
        elif _work.profile == 'asset':
            _ety_type_label = 'category'
            _ety_label = 'asset'
        elif _work.profile == 'shot':
            _ety_type_label = 'sequence'
            _ety_label = 'shot'
        else:
            raise ValueError(_work)

        # Update lines Linked/Select status
        for _name in ['ety_type', 'ety', 'task', 'tag', 'ver']:

            _mode_knob = self[_name + '_mode']
            _list_knob = self[_name]
            _mode = _mode_knob.value()

            # Update mode label colour
            _col = {'Linked': DEFAULT_COL,
                    'Select': NON_DEFAULT_COL}[_mode]
            _cur_label = re.split('[<>]', _mode_knob.label())[-3]
            _label = {
                'ety_type': _ety_type_label,
                'ety': _ety_label}.get(_name, _cur_label)
            _LOGGER.debug(' - UPDATE MODE mode=%s label=%s', _mode, _label)
            _label = COL_FMT.format(col=_col, text=_label)
            _mode_knob.setLabel(_label)

            # Update list enabled
            _list_en = _mode == 'Select'
            _list_knob.setEnabled(_list_en)

    def _update_task(self, level, ety):
        """Update task.

        Args:
            level (UpdateLevel): level of update
            ety (CPEntity): selected entity

        Returns:
            (CPWorkDir): selected work dir
        """
        _LOGGER.debug('UPDATE TASK')

        # Get tasks list
        _tasks = set(['precomp'])
        _etys = sorted({_ety for _ety in (ety, pipe.CACHE.cur_entity) if _ety})
        for _ety in _etys:
            _work_dirs = _ety.find_work_dirs(dcc_='nuke')
            _ety_tasks = {_work_dir.task for _work_dir in _work_dirs}
            _tasks |= _ety_tasks
        _tasks = sorted(_tasks)

        # Update list
        if level <= UpdateLevel.TASK:
            _mode = self['task_mode'].value()
            _cur = self['task'].value()
            _LOGGER.debug(' - REPOPULATE TASKS mode=%s cur=%s', _mode, _cur)
            if _mode == 'Select' and _cur and _cur in _tasks:
                _task = _cur
            else:
                _task = (pipe.CACHE.cur_work.task if pipe.CACHE.cur_work
                         else None)
            self['task'].setValues(_tasks)
            self['task'].setValue(_task)

        # Build work dir
        _task = self['task'].value()
        if not ety or not _task:
            _work_dir = None
        else:
            _work_dir = ety.to_work_dir(dcc_='nuke', task=_task)
        _LOGGER.debug(' - WORK DIR %s', _work_dir)

        return _work_dir

    def _update_tag(self, level, work_dir):
        """Update tag.

        Args:
            level (UpdateLevel): level of update
            work_dir (CPWorkDir): selected work dir

        Returns:
            (str): selected tag
        """

        # Read tags
        _work_dirs = {work_dir, pipe.CACHE.cur_work_dir}
        _tags = {'<default>'}
        for _o_work_dir in _work_dirs:
            if not isinstance(_o_work_dir, cache.CCPWorkDir):
                continue
            _tags |= {_work.tag or '<default>'
                      for _work in _o_work_dir.find_works()}
        _tags = sorted(_tags)

        # Update list
        if level <= UpdateLevel.TAG:
            _mode = self['tag_mode'].value()
            _cur = self['tag'].value()
            if _mode == 'Select' and _cur in _tags:
                _val = _cur
            else:
                _val = pipe.CACHE.cur_work.tag if pipe.CACHE.cur_work else None
                _val = _val or '<default>'
            self['tag'].setValues(_tags)
            self['tag'].setValue(_val)

        _tag = self['tag'].value()
        if _tag == '<default>':
            _tag = None

        return _tag

    def _update_ver(self, level):
        """Update version.

        Args:
            level (UpdateLevel): level of update

        Returns:
            (int): selected version number
        """

        # Get list of vers
        if not pipe.CACHE.cur_work:
            _vers = []
        else:
            _vers = [_work.ver for _work in pipe.CACHE.cur_work.find_vers()]

        # Update list
        if level <= UpdateLevel.VERSION:
            _mode = self['ver_mode'].value()
            _cur = self['ver'].value()
            if _mode == 'Select' and _cur in _vers:
                _val = _cur
            else:
                _val = pipe.CACHE.cur_work.ver if pipe.CACHE.cur_work else None
            self['ver'].setValues(_vers)
            self['ver'].setValue(_val)
        _ver_n = int(self['ver'].value())

        return _ver_n

    def _update_pipeline(self, level=None):
        """Update pipeline knobs.

        Args:
            level (UpdateLevel): level of update

        Returns:
            (CPWork): current work file defined by pipeline knobs
        """
        _job = pipe.CACHE.cur_job
        _cur_work = pipe.CACHE.cur_work
        _LOGGER.debug('UPDATE PIPELINE level=%s %s', level, _cur_work)

        _ety_type = self._update_ety_type(level=level)
        _ety = self._update_ety(level=level, ety_type=_ety_type)
        self._update_pipeline_ui()
        _work_dir = self._update_task(level=level, ety=_ety)
        _tag = self._update_tag(level=level, work_dir=_work_dir)
        _ver_n = self._update_ver(level=level)

        # Update work knob (internal)
        _work = _work_dir.to_work(ver_n=_ver_n, tag=_tag) if _work_dir else None
        self['work'].setValue(_work.path if _work else '')
        _LOGGER.debug(' - WORK %s', _work)

        return _work

    def _update_desc(self):
        """Update description field and obtain description.

        Returns:
            (str): description
        """
        _desc_mode = self['desc_mode'].value()
        self['desc_text'].setEnabled(_desc_mode == 'Manual')
        if _desc_mode == 'From node':
            _desc = self.node.name()
            self['desc_text'].setValue(_desc)
            _col = DEFAULT_COL
        elif _desc_mode == 'Manual':
            _desc = self['desc_text'].value()
            _col = NON_DEFAULT_COL
        else:
            raise ValueError(_desc)
        _label = COL_FMT.format(col=_col, text='desc')
        self['desc_mode'].setLabel(_label)

        return _desc

    def _update_tmpl(self):
        """Apply template updates.

        Returns:
            (str): template settings (render/plate)
        """
        _tmpl = self['tmpl'].value()

        for _names, _tgl in [
                (['desc_mode', 'desc_text'], _tmpl == 'render'),
                (['grade', 'aw_layer', 'denoise', 'timewarp'],
                 _tmpl == 'plate'),
        ]:
            for _name in _names:
                _knob = self[_name]
                if not _knob:
                    continue
                _knob.setVisible(_tgl)
                _LOGGER.debug('SET VISIBLE %s %d', _name, _tgl)
        _col = {'render': RENDER_COL,
                'plate': PLATE_COL}[_tmpl]
        set_node_col(self.node, _col)

        return _tmpl

    def _update_res(self):
        """Apply res updates.

        Res is disabled by default in renders and set to auto in plates.

        Returns:
            (str|None): res setting
        """
        _tmpl = self['tmpl'].value()
        _res_mode = self['res_mode'].value()

        self['res_text'].setEnabled(_res_mode == 'Manual')
        _res = self.node.width(), self.node.height()
        _res_name = _RES_MAP.get(_res, f'{_res[0]:d}x{_res[1]:d}')
        if _res_mode == 'Auto':
            self['res_text'].setValue(_res_name)
            _col = DEFAULT_COL if _tmpl == 'plate' else NON_DEFAULT_COL
        elif _res_mode == 'Manual':
            _cur_res = self['res_text'].value()
            if _cur_res in ['unset', '']:
                self['res_text'].setValue(_res_name)
            _res_name = self['res_text'].value()
            _col = NON_DEFAULT_COL
        elif _res_mode == 'Disable':
            _res_name = None
            self['res_text'].setValue('')
            _col = NON_DEFAULT_COL if _tmpl == 'plate' else DEFAULT_COL
        else:
            raise ValueError(_res_mode)
        _LOGGER.debug(' - RES NAME %s', _res_name)

        _label = COL_FMT.format(col=_col, text='res')
        self['res_mode'].setLabel(_label)

        return _res_name

    def _update_output_name(self):
        """Update output name knob.

        Returns:
            (str): output name
        """
        _tmpl = self._update_tmpl()
        _res_name = self._update_res()

        # Update output name (internal)
        if _tmpl == 'render':
            _desc = self._update_desc()
            _output_tokens = [_desc]
        elif _tmpl == 'plate':
            _output_tokens = []
            for _knob in ['grade', 'aw_layer', 'denoise', 'timewarp']:
                _val = self[_knob].value()
                if _val == 'Disable':
                    continue
                _output_tokens.append(_val)
        else:
            raise ValueError(_tmpl)
        if _res_name:
            _output_tokens.append(_res_name)
        _output_name = '_'.join(_output_tokens)
        self['output_name'].setValue(_output_name)
        self['output_name'].setFlag(nuke.READ_ONLY)

        self._update_tag_elems_vis()

        return _output_name or 'default'

    def _update_tag_elems_vis(self):
        """Update tag elements visibility.

        If the job doesn't have tags in the plate template then the tag
        knobs are hidden in plate mode.
        """
        _tmpl = self['tmpl'].value()
        if _tmpl == 'plate' and not _job_plate_uses_tag(pipe.cur_job()):
            _vis = False
        else:
            _vis = True
        for _elem in ['tag', 'tag_mode']:
            self[_elem].setVisible(_vis)

    def _update_internals_vis(self):
        """Update internals elements visibility."""
        _vis = self['show_internals'].value()
        for _knob in ['work', 'output_name', 'is_pini_autowrite_2']:
            self[_knob].setVisible(_vis)

    def _update_file(self, work, output_name):
        """Update output file.

        Args:
            work (CPWork): current node work file
            output_name (str): current node output name
        """
        _extn = self['file_type'].value()

        # Detemine template name
        _base_tmpl = self['tmpl'].value()
        _mov = _extn == 'mov'
        _tmpl_name = {
            ('render', False): 'render',
            ('render', True): 'mov',
            ('plate', False): 'plate',
            ('plate', True): 'plate_mov'}[(_base_tmpl, _mov)]

        # Find matching template
        if not work:
            _err = 'cannot build file path - no current work'
            _file = ''
        else:
            try:
                _tmpl = work.find_template(_tmpl_name)
            except ValueError as _exc:
                _tmpl = None
                _err = str(_exc)
                _file = ''
            else:
                _err = ''
                _out = work.to_output(
                    _tmpl, output_name=output_name, extn=_extn)
                _file = _out.path
        _LOGGER.debug(' - FILE %s', _file)

        # Update knobs
        for _knob in ['file', 'aw_file']:
            self[_knob].setValue(_file)
            self[_knob].setFlag(nuke.READ_ONLY)
            _label = COL_FMT.format(
                col=ERROR_COL if _err else FILE_COL, text='file')
            self[_knob].setLabel(_label)
        _text = COL_FMT.format(col=ERROR_COL, text=_err)
        self['error'].setValue(_text)
        self['error'].setVisible(bool(_err))

    def update(self, level=UpdateLevel.JOB):
        """Apply update triggered by knob change.

        Args:
            level (UpdateLevel): level of update
        """
        _LOGGER.debug('UPDATE FILE node=%s level=%s', self.node.name(), level)
        _work = self._update_pipeline(level=level)
        _output_name = self._update_output_name()
        self._update_file(work=_work, output_name=_output_name)
        self._update_internals_vis()

    def knob_changed_callback(self, knob):
        """Callback triggered by knob change.

        Args:
            knob (Knob): knob which was changed
        """
        _LOGGER.debug(' - UPDATE KNOB %s type=%s', knob.name(), type(knob))
        _name = knob.name()
        if _name == 'tmpl':
            _res_mode = {'render': 'Disable',
                         'plate': 'Auto'}[knob.value()]
            self['res_mode'].setValue(_res_mode)
            self.update(level=UpdateLevel.OUTPUT_NAME)
        elif _name == 'ety_type_mode':
            self.update(level=UpdateLevel.ENTITY_TYPE)
        elif _name in ('ety_type', 'ety_mode'):
            self.update(level=UpdateLevel.ENTITY)
        elif _name in ('ety', 'task_mode'):
            self.update(level=UpdateLevel.TASK)
        elif _name in ('task', 'tag_mode'):
            self.update(level=UpdateLevel.TAG)
        elif _name == 'tag':
            self.update(level=UpdateLevel.VERSION)
        elif (
                _name in [
                    'channels',
                    'colorspace',
                    'compression',
                    'denoise',
                    'desc_mode',
                    'desc_text',
                    'grade',
                    'inputChange',
                    'aw_layer',
                    'name',
                    'res_text',
                    'show_internals',
                    'timewarp',
                    'ver'] or
                _name.endswith('_mode')):
            self.update(level=UpdateLevel.OUTPUT_NAME)
        elif _name == 'file_type':
            self.update()
        elif _name == 'Render':
            self._apply_render()
        else:
            _LOGGER.info(' - UNHANDLED KNOB %s', _name)
            return

        _LOGGER.debug(' - KNOB CHANGED CALLBACK COMPETE %s',
                      knob.fullyQualifiedName())

        # Set write flag on triggering knob to force revert to its tab
        # (nuke switches to pipeline tab when it updates elements there,
        # which annoying and unintuitive for artists)
        knob.setFlag(nuke.WRITE_ALL)

    def reset(self):
        """Reset this node."""
        from . import aw_callbacks

        _LOGGER.debug('RESET %s', self)
        aw_callbacks.flush_callbacks()

        pipe.CACHE.reset()
        self.node.resetKnobsToDefault()
        self['file_type'].setValue('exr')
        _LOGGER.debug(' - SET ETY MODE %s', self['ety_mode'].value())
        self.update(level=UpdateLevel.ENTITY_TYPE)

        aw_callbacks.install_callbacks()

    def __getitem__(self, name):
        return self.node.knobs().get(name)

    def __repr__(self):
        return basic_repr(self, self.node.name())


def get_selected():
    """Get currently selected autowrite 2.0 node.

    Returns:
        (CAutowrite): selected node
    """
    return CAutowrite(nuke.selectedNode())


def _find_tab_widget(node):
    """Find tab widget in nuke's ui for the given node.

    Args:
        node (Node): node to find tab widget for

    Returns:
        (QTabWidget): tab widget in the Properties pane
    """
    _widget = _find_node_widget(node)
    if not _widget:
        return None
    return _widget.children()[-1]


def _find_node_widget(node):
    """Find widget for this given node in the Properties pane.

    Args:
        node (Node): node to find widget for

    Returns:
        (QWidget): widget in the Properties pane
    """
    _name = node.name()
    for _widget in qt.get_application().allWidgets():
        _title = _widget.windowTitle()
        if not _title:
            continue
        if _title == _name:
            return _widget
    return None


@cache_result
def _job_plate_uses_tag(job):
    """Test whether the given job uses tags in the plate path.

    Args:
        job (CPJob): job to test

    Returns:
        (bool): whether tags used in plates
    """
    return bool(job.find_templates('plate', has_key={'tag': True}))
