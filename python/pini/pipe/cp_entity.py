"""Tools for managing entities, the base class for shots and assets."""

# pylint: disable=no-member

import copy
import logging
import re

import six

from pini import dcc
from pini.utils import (
    Dir, single, cache_result, File, EMPTY, passes_filter, to_str)

from . import cp_template, cp_settings
from .cp_utils import task_sort, map_path

_LOGGER = logging.getLogger(__name__)


class CPEntity(cp_settings.CPSettingsLevel):
    """Represents an entity (ie. an asset or shots) dir on disk."""

    job = None
    name = None

    profile = None
    asset_type = None
    asset = None
    sequence = None
    shot = None

    def __init__(self, path):
        """Constructor.

        Args:
            path (str): entity path
        """
        super(CPEntity, self).__init__(path)

        # Reject leading underscore in name (archived entities)
        if self.name.startswith('_'):
            raise ValueError('Name has leading underscore '+self.name)

    def create(self, force=False, parent=None, shotgrid_=True):
        """Create this entity.

        Args:
            force (bool): create entity without confirmation
            parent (QDialog): parent for confirmation dialogs
            shotgrid_ (bool): register in shotgrid (if available)
        """
        from pini import pipe

        if not force:
            del parent
            raise NotImplementedError

        self._create_tasks()

        # Setup shotgrid
        _enable = shotgrid_ and not self.settings.get('disable_shotgrid', False)
        if _enable and pipe.SHOTGRID_AVAILABLE:
            from pini.pipe import shotgrid
            shotgrid.create_entity(self, force=force)

    def find_template(self, *args, **kwargs):
        """Find a template within this entity.

        Returns:
            (CPTemplate): matching template
        """
        return self.job.find_template(*args, profile=self.profile, **kwargs)

    def find_templates(self, *args, **kwargs):
        """Find templates within this entity.

        Returns:
            (CPTemplate list): matching templates
        """
        return self.job.find_templates(*args, profile=self.profile, **kwargs)

    def to_default_tasks(self, dcc_):
        """Read default tasks from config for the given dcc in this entity.

        Args:
            dcc_ (str): dcc to read tasks for

        Returns:
            (str list): tasks
        """
        _defaults = self.job.cfg['tasks']
        _dcc_key = '{}_{}s'.format(dcc_, self.profile)
        _generic_key = '{}s'.format(self.profile)
        if _dcc_key in _defaults:
            _tasks = _defaults[_dcc_key]
        else:
            _tasks = _defaults.get(_generic_key, [])
        return sorted(_tasks, key=task_sort)

    def _create_tasks(self):
        """Create task folders (work dirs)."""

        # Create tasks
        _LOGGER.debug('CREATE TASKS %s', self)
        for _dcc in dcc.DCCS:
            _tasks = self.to_default_tasks(dcc_=_dcc)
            _LOGGER.debug(' - TASKS %s %s', _dcc, _tasks)
            for _task in _tasks:
                _LOGGER.debug(' - CREATE WORKDIR %s %s', _task, _dcc)
                _work_dir = self.to_work_dir(task=_task, dcc_=_dcc)
                _work_dir.mkdir()

    def find_work_dir(self, task=None, dcc_=None, catch=False):
        """Find a work dir in this entity.

        Args:
            task (str): match by task
            dcc_ (str): match by dcc
            catch (bool): no error if no work dir found

        Returns:
            (CPWorkDir): matching work dir

        Raises:
            (ValueError): if exactly one work dir was not found
        """
        return single(self.find_work_dirs(task=task, dcc_=dcc_), catch=catch)

    def find_work_dirs(self, task=None, step=None, dcc_=None):
        """Find work dirs within this entity.

        Args:
            task (str): filter by task
            step (str): filter by step
            dcc_ (str): match by dcc

        Returns:
            (CPWorkDir list): matching work dirs
        """
        _LOGGER.debug('FIND WORK DIRS task=%s dcc_=%s', task, dcc_)
        _all_work_dirs = self._read_work_dirs()
        _LOGGER.debug(
            ' - READ %d WORK DIRS %s', len(_all_work_dirs), _all_work_dirs)

        # Apply filters
        _work_dirs = []
        for _work_dir in _all_work_dirs:
            if task and _work_dir.task != task:
                continue
            if step and _work_dir.step != step:
                continue
            _work_dirs.append(_work_dir)

        # Apply dcc filter
        if dcc_:
            _dcc_has_specific_tmpls = bool([
                _tmpl for _tmpl in self.find_templates('work_dir', dcc_=dcc_)
                if _tmpl.dcc == dcc_])
            if _dcc_has_specific_tmpls:
                _match = (dcc_, )
            else:
                _match = (dcc_, None)
            _LOGGER.debug(' - DCC HAS SPECIFIC TMPLS %d dcc=%s match=%s',
                          _dcc_has_specific_tmpls, dcc_, _match)
            _work_dirs = [_work_dir for _work_dir in _work_dirs
                          if _work_dir.dcc in _match]

        return _work_dirs

    def _find_work_dir_templates(self):
        """Find work_dir templates for this entity.

        Any dccs which contain a dcc tag and which don't have a specific
        template for that dcc are expanded for all unhandled dccs.

        For example if there's a nuke_work_dir template and a generic work_dir
        template which has a dcc tag, the generic work_dir template is
        duplicated for every dcc except nuke.

        Returns:
            (CPTemplate list): templates
        """

        # Find templates
        _tmpls = self.job.find_templates(
            type_='work_dir', profile=self.profile)
        if (  # shot/asset template replaces generic template
                len(_tmpls) > 1 and
                not _tmpls[-1].profile and
                _tmpls[-2].profile and
                not _tmpls[-2].dcc):
            _tmpls.pop(-1)

        # Apply cur entity path data
        _tmpls = sorted({_tmpl.apply_data(entity_path=self.path)
                         for _tmpl in _tmpls})

        # Expand for dccs if necessary
        _handled_dccs = {_tmpl.dcc for _tmpl in _tmpls if _tmpl.dcc}
        _unhandled_dccs = set(dcc.DCCS).difference(_handled_dccs)
        _tmpls = sorted({
            _tmpl.apply_data(dcc=_tmpl.dcc)
            if 'dcc' in _tmpl.keys() and _tmpl.dcc
            else _tmpl
            for _tmpl in _tmpls})
        _tmpls = sum([
            [_tmpl.apply_data(dcc=_dcc) for _dcc in _unhandled_dccs]
            if 'dcc' in _tmpl.keys() and not _tmpl.dcc
            else [_tmpl]
            for _tmpl in _tmpls], [])
        _LOGGER.debug(' - FOUND %d TMPLS', len(_tmpls))

        assert len({_tmpl.pattern for _tmpl in _tmpls}) == len(_tmpls)

        return _tmpls

    def _read_work_dirs(self, class_=None):
        """Read work dirs within this entity.

        Args:
            class_ (class): override work dir class

        Returns:
            (CPWorkDir list): work dirs
        """
        from pini import pipe
        _LOGGER.debug('READ WORK DIRS')

        _class = class_ or pipe.CPWorkDir
        if pipe.MASTER == 'disk':
            _work_dirs = self._read_work_dirs_disk(class_=_class)
        elif pipe.MASTER == 'shotgrid':
            _work_dirs = self._read_work_dirs_sg(class_=_class)
        else:
            raise ValueError(pipe.MASTER)

        return sorted(_work_dirs)

    def _read_work_dirs_disk(self, class_):
        """Read work dirs from disk.

        Args:
            class_ (class): work dir class

        Returns:
            (CPWorkDir list): work dirs
        """
        from pini import pipe
        _LOGGER.debug('READ WORK DIRS DISK')

        _work_dirs = []
        _tmpls = self._find_work_dir_templates()
        _LOGGER.debug(' - TMPLS %d %s', len(_tmpls), _tmpls)
        _globs = pipe.glob_templates(_tmpls, job=self.job)
        for _tmpl, _dir in _globs:
            _work_dir = class_(_dir, template=_tmpl, entity=self)
            _work_dirs.append(_work_dir)

        return _work_dirs

    def _read_work_dirs_sg(self, class_):
        """Read work dirs using shotgrid.

        Args:
            class_ (class): work dir class

        Returns:
            (CPWorkDir list): work dirs
        """
        from . import shotgrid

        _LOGGER.debug('READ WORK DIRS SG %s', self)

        _tmpl = self.find_template('work_dir')
        _tmpl = _tmpl.apply_data(entity_path=self.path)
        _LOGGER.debug(' - TMPL %s', _tmpl)

        _work_dirs = []
        for _work_dir in shotgrid.find_tasks(self):
            _work_dir = class_(_work_dir.path, template=_tmpl, entity=self)
            _LOGGER.debug('     - WORK DIR %s ', _work_dir)
            _work_dirs.append(_work_dir)

        return _work_dirs

    def to_work_dir(
            self, task, dcc_=None, step=None, user=None, catch=False,
            class_=None):
        """Build a work dir object matching this entity's tokens.

        Args:
            task (str): work dir task
            dcc_ (str): work dir dcc
            step (str): work dir step
            user (str): work dir user
            catch (bool): no error if arg do not create valid work dir object
            class_ (class): override work dir class

        Returns:
            (CPWorkDir): work dir object
        """
        from pini import pipe

        _class = class_ or pipe.CPWorkDir
        _step = step or task
        _user = user or pipe.cur_user()

        # Apply defaults
        _dcc = dcc_
        if _dcc is None:
            _dcc = dcc.NAME
        if not _dcc:
            raise ValueError('No dcc defined')

        # Find template
        _tmpls = self.job.find_templates(
            type_='work_dir', profile=self.profile, dcc_=_dcc)
        _tmpl = _tmpls[0].apply_data(entity_path=self.path)

        # Build work dir
        _data = {'task': task, 'dcc': _dcc, 'step': _step, 'user': _user}
        _LOGGER.debug('TO WORK DIR %s', self)
        _LOGGER.debug(' - DATA %s', _data)
        _LOGGER.debug(' - TMPL %s', _tmpl)
        _path = _tmpl.format(_data)
        _LOGGER.debug(' - PATH %s', _path)
        try:
            return _class(_path, entity=self, template=_tmpl)
        except ValueError as _exc:
            if catch:
                return None
            raise _exc

    def find_work(self, tag=EMPTY, ver_n=None, task=None, catch=False):
        """Find a work file in this entity.

        Args:
            tag (str|None): filter by tag
            ver_n (int): filter by version number
            task (str): filter by task
            catch (bool): no error if work not found

        Returns:
            (CPWork): matching work file
        """
        _works = self.find_works(tag=tag, ver_n=ver_n, task=task)
        return single(_works, catch=catch)

    def find_works(self, task=None, tag=EMPTY, ver_n=None, dcc_=None):
        """Find work files in this entity.

        Args:
            task (str): filter by task
            tag (str|None): filter by tag
            ver_n (int): filter by version number
            dcc_ (str): filter by dcc

        Returns:
            (CPWork list): matching work files
        """
        _LOGGER.debug('FIND WORKS')
        _works = []
        _work_dirs = self.find_work_dirs(task=task, dcc_=dcc_)
        _LOGGER.debug(' - WORK DIRS %d %s', len(_work_dirs), _work_dirs)
        for _work_dir in _work_dirs:
            _task_works = _work_dir.find_works(tag=tag, ver_n=ver_n)
            _LOGGER.debug(
                ' - ADD TASK WORKS %s %s', _work_dir.task, _task_works)
            _works += _task_works
        return _works

    def find_output(self, catch=False, **kwargs):
        """Find an output within this entity.

        Args:
            catch (bool): no error if no output found

        Returns:
            (CPOutput): matching output
        """
        return single(self.find_outputs(**kwargs), catch=catch)

    def find_outputs(
            self, type_=None, output_name=None, output_type=None, task=None,
            ver_n=EMPTY, tag=EMPTY, extn=None, filter_=None, class_=None):
        """Find outputs in this entity.

        This will only search outputs stored at entity level.

        Args:
            type_ (str): filter by output type (eg. render/cache)
            output_name (str): filter by output name
            output_type (str):  filter by output type
            task (str): filter by task
            ver_n (int|None): filter by version number
            tag (str|None): filter by tag
            extn (str): filter by extension
            filter_ (str): filter by path
            class_ (class): filter by class

        Returns:
            (CPOutput list): matching outputs
        """
        _LOGGER.debug('FIND OUTPUTS')
        _all_outs = self._read_outputs()
        _LOGGER.debug(' - FOUND %d OUTPUTS', len(_all_outs))

        # Apply latest filter
        _ver_n = ver_n
        if _ver_n == 'latest':
            _LOGGER.debug(' - APPLYING LATEST FILTER %s', _all_outs)
            _latests = {}
            for _out in _all_outs:
                _key = (_out.type_, _out.tag, _out.output_name, _out.task,
                        _out.output_type)
                _LOGGER.debug(' - ADDING %s', _out)
                _latests[_key] = _out
            _LOGGER.debug(' - LATESTS %s', _latests)
            _all_outs = sorted(_latests.values())
            _ver_n = EMPTY

        # Apply other filters
        _outs = []
        for _out in _all_outs:
            _LOGGER.debug(' - TESTING %s', _out)
            if extn and _out.extn != extn:
                continue
            if output_type and _out.output_type != output_type:
                continue
            if output_name and _out.output_name != output_name:
                continue
            if task and _out.task != task:
                continue
            if (
                    tag is not EMPTY and
                    self._template_type_uses_token(
                        type_=_out.type_, token='tag') and
                    _out.tag != tag):
                continue
            if _ver_n is not EMPTY and _out.ver_n != _ver_n:
                continue
            if type_ is not None and _out.type_ != type_:
                _LOGGER.debug('   - TYPE FILTERED %s (%s)', _out.type_, type_)
                continue
            if filter_ and not passes_filter(_out.path, filter_):
                continue
            if class_ and not isinstance(_out, class_):
                continue
            _outs.append(_out)
        return sorted(_outs)

    @cache_result
    def _template_type_uses_token(self, type_, token):
        """Test whether the given template type uses the given token.

        For example in some pipelines, the cache template doesn't use the
        tag token. This means that when searching for caches, the tag token
        should be ignored. However, if the cache template uses the tag token
        the searching for caches should take account of tag.

        Args:
            type_ (str): template type (eg. cache)
            token (str): token to check (eg. tag)

        Returns:
            (bool): whether any templates of the given type uses the
                given token
        """
        for _tmpl in self.find_templates(type_=type_):
            if token in _tmpl.keys():
                return True
        return False

    def _find_root_output_templates(self):
        """Find output templates for the root of this entity.

        This does not include work_dir or seq_dir templates.

        Returns:
            (CPTemplate list): output templates
        """
        from pini import pipe
        _LOGGER.debug('FIND ROOT OUTPUT TMPLS %s', self)

        # Find templates
        _types = ['seq_dir'] + (pipe.OUTPUT_TEMPLATE_TYPES +
                                pipe.OUTPUT_VIDEO_TEMPLATE_TYPES)
        _LOGGER.debug(' - TMPL TYPES %s', _types)
        _all_tmpls = sorted(sum([
            self.find_templates(_type) for _type in _types], []))

        # Remove work_dir + seq_dir templates
        _seq_dir_tmpls = [
            _tmpl for _tmpl in _all_tmpls if _tmpl.name == 'seq_dir']
        _LOGGER.debug(' - SEQ DIR TMPLS %d %s', len(_seq_dir_tmpls),
                      _seq_dir_tmpls)
        _tmpls = []
        for _tmpl in _all_tmpls:
            _LOGGER.debug(' - CHECKING TEMPLATE %s', _tmpl)
            if '{work_dir}' in _tmpl.pattern:
                _LOGGER.debug('   - WORK DIR')
                continue
            if _tmpl_in_seq_dir(_tmpl, seq_dir_tmpls=_seq_dir_tmpls):
                _LOGGER.debug('   - SEQ DIR')
                continue
            _LOGGER.debug('   - ACCEPTED')
            _tmpls.append(_tmpl)

        # Apply data
        _data = {'entity': self.name,
                 'entity_path': self.path}
        _tmpls = [_tmpl.apply_data(**_data) for _tmpl in _tmpls]

        return _tmpls

    def _read_output_globs(self):
        """Read globs data for outputs in this entity.

        Returns:
            (tuple): template/path data
        """
        _tmpls = self._find_root_output_templates()
        _globs = cp_template.glob_templates(_tmpls, job=self.job)
        _LOGGER.debug(
            ' FOUND %d GLOBS (%d TEMPLATES)', len(_globs), len(_tmpls))
        return _globs

    def find_output_seq_dir(self, match):
        """Find output sequence directory matching the given criteria.

        Args:
            match (str): token to match with

        Returns:
            (CPOutputSeqDir): matching output sequence directory
        """
        return single([
            _seq_dir for _seq_dir in self.find_output_seq_dirs()
            if _seq_dir.path == match])

    def find_output_seq_dirs(
            self, ver_n=None, tag=EMPTY, task=None, globs=None):
        """Find output sequence directories within this entity.

        Args:
            ver_n (int): filter by version number
            tag (str|None): filter by tag
            task (str): filter by task
            globs (tuple): override glob data

        Returns:
            (CPOutputSeqDir list): output sequence dirs
        """
        _seq_dirs = []
        for _seq_dir in self._build_output_seq_dirs(globs=globs):
            if ver_n and _seq_dir.ver_n != ver_n:
                continue
            if tag is not EMPTY and _seq_dir.tag != tag:
                continue
            if task and _seq_dir.task != task:
                continue
            _seq_dirs.append(_seq_dir)
        return _seq_dirs

    def _build_output_seq_dirs(self, globs=None, seq_dir_class=None):
        """Build outputs sequence directories from glob data.

        Args:
            globs (tuple): override globs data
            seq_dir_class (class): overide output seq dir class

        Returns:
            (CPOutputSeqDir list): output sequence dirs
        """
        from pini import pipe

        _seq_dir_class = seq_dir_class or pipe.CPOutputSeqDir
        _globs = globs or self._read_output_globs()

        # Build globs into output objects
        _seq_dirs = []
        for _tmpl, _path in _globs:
            _LOGGER.log(9, ' - TESTING %s', _path)
            _LOGGER.log(9, '   - TMPL %s', _tmpl)
            if not (isinstance(_path, Dir) and _tmpl.name == 'seq_dir'):
                _LOGGER.log(9, '   - IGNORING')
                continue
            try:
                _seq_dir = _seq_dir_class(_path, entity=self, template=_tmpl)
            except ValueError:
                continue
            _seq_dirs.append(_seq_dir)

        return sorted(_seq_dirs)

    def _build_output_files(
            self, globs=None, file_class=None, video_class=None):
        """Build output objects from glob data.

        Args:
            globs (tuple): override globs data
            file_class (class): override output file class
            video_class (class): override output video class

        Returns:
            (CPOutput list): all outputs in entity
        """
        _LOGGER.debug('BUILD OUTPUT FILES %s', self)
        from pini import pipe

        _file_class = file_class or pipe.CPOutput
        _video_class = video_class or pipe.CPOutputVideo
        _globs = globs or self._read_output_globs()
        _outs = []

        # Build globs into output files
        for _tmpl, _path in _globs:

            if not (isinstance(_path, File) and _tmpl.name != 'seq_dir'):
                continue

            # Determine output file class
            if _tmpl.type_ in pipe.OUTPUT_TEMPLATE_TYPES:
                _class = _file_class
            elif _tmpl.type_ in pipe.OUTPUT_VIDEO_TEMPLATE_TYPES:
                _class = _video_class
            else:
                raise ValueError(_tmpl)

            # Build output
            try:
                _out = _class(_path.path, template=_tmpl, entity=self)
            except ValueError:
                continue
            _LOGGER.debug(' - ADDING OUTPUT %s', _out)
            assert _out.cmp_key
            _outs.append(_out)

        return sorted(_outs)

    def _read_outputs(self):
        """Read outputs in this entity.

        Returns:
            (CPOutput list): outputs
        """
        from pini import pipe
        _LOGGER.debug('READ OUTPUTS')

        if pipe.MASTER == 'disk':
            _outs = self._read_outputs_disk()
        elif pipe.MASTER == 'shotgrid':
            _outs = self.job.find_outputs(entity=self)
        else:
            raise ValueError(pipe.MASTER)

        return _outs

    def _read_outputs_disk(self):
        """Build output objects.

        This uses glob data to construct output file and sequence dir objects.
        The sequence dirs are then used to find output sequences. This is
        constructed like this to facilitate caching (see pini.pipe.cache).

        Returns:
            (CPOutput list): entity outputs
        """

        # Read globs
        _globs = self._read_output_globs()
        _LOGGER.debug(' - FOUND %d GLOBS', len(_globs))

        # Add output file objects
        _files = self._build_output_files(globs=_globs)

        # Add sequence dir outputs
        _seq_dirs = self._build_output_seq_dirs(globs=_globs)
        _seqs = []
        for _seq_dir in _seq_dirs:
            _seqs += _seq_dir.find_outputs()

        _outs = sorted(_files+_seqs)
        _LOGGER.debug(
            'BUILT OUTPUTS %s outs=%d globs=%d files=%d seq_dirs=%d seqs=%d',
            self, len(_outs), len(_globs), len(_files), len(_seq_dirs),
            len(_seqs))

        return _outs

    def find_publish(self, catch=True, **kwargs):
        """Find a publish in this entity.

        Args:
            catch (bool): no error if fail to match single publish

        Returns:
            (CPOutput): matching publish
        """
        return single(self.find_publishes(**kwargs), catch=catch)

    def find_publishes(  # pylint: disable=too-many-branches
            self, task=None, output_type=EMPTY, output_name=None, ver_n=EMPTY,
            tag=EMPTY, extn=EMPTY, extns=None, versionless=None, filter_=None):
        """Find publishes in this entity.

        Args:
            task (str): filter by task
            output_type (str): filter by output type
            output_name (str): filter by output name
            ver_n (int): filter by version number
            tag (str): filter by tag
            extn (str): filter by publish extension
            extns (str list): filter by publish extensions
            versionless (bool): filter by versionless state
            filter_ (str): apply path filter

        Returns:
            (CPOutput list): matching publishes
        """
        from pini import pipe

        # Determine extns filter
        _extns = []
        if extn is not EMPTY:
            _extns.append(extn)
        if extns:
            _extns += extns

        # Filter list of extns
        _pubs = []
        for _pub in self._read_publishes():

            if task and (
                    _pub.task != task and
                    pipe.map_task(_pub.task) != task):
                continue
            if output_name and _pub.output_name != output_name:
                continue
            if output_type is not EMPTY and _pub.output_type != output_type:
                continue
            if tag is not EMPTY and _pub.tag != tag:
                continue
            if _extns and _pub.extn not in _extns:
                continue
            if versionless is not None and bool(_pub.ver_n) == versionless:
                continue
            if filter_ and not passes_filter(_pub.path, filter_):
                continue

            # Apply version filter
            if ver_n == 'latest':
                if not _pub.is_latest():
                    continue
            elif ver_n is not EMPTY:
                assert ver_n is None or isinstance(ver_n, int)
                if _pub.ver_n != ver_n:
                    continue

            _pubs.append(_pub)

        return _pubs

    def _read_publishes(self):
        """Read all publishes in this entity.

        Returns:
            (CPOutput list): all publishes
        """
        from pini import pipe

        if pipe.MASTER == 'disk':
            _pubs = self._read_publishes_disk()
        elif pipe.MASTER == 'shotgrid':
            _pubs = self.job.find_publishes(entity=self)
        else:
            raise ValueError(pipe.MASTER)

        _LOGGER.debug('READ PUBLISHES %s n_pubs=%d', self.name, len(_pubs))

        return _pubs

    def _read_publishes_disk(self):
        """Read publishes in this entity from disk.

        Returns:
            (CPOutput list): publishes
        """
        _pubs = []
        _work_dirs = self.find_work_dirs()
        for _work_dir in _work_dirs:
            for _out in _work_dir.find_outputs(type_='publish'):
                _pubs.append(_out)

        return _pubs

    def to_output(
            self, template, task=None, tag=None, output_type=None,
            output_name=None, ver_n=1, extn=None):
        """Build an output object for this entity.

        Args:
            template (CPTemplate): output template to use
            task (str): output task
            tag (str): output tag
            output_type (str): apply output name
            output_name (str): output name
            ver_n (int): output version
            extn (str): output extension

        Returns:
            (CPOutput): matching output
        """
        _LOGGER.info('TO OUTPUT')
        from pini import pipe

        # Get template
        _tag = tag or self.job.cfg['tokens']['tag']['default']
        if isinstance(template, pipe.CPTemplate):
            _tmpl = template
        elif isinstance(template, six.string_types):
            _want_key = {
                'output_type': bool(output_type)}
            _LOGGER.info(' - WANT KEY %s', _want_key)
            _has_key = {
                'tag': bool(_tag),
                'ver': bool(ver_n)}
            _LOGGER.info(' - HAS KEY %s', _has_key)
            _tmpl = self.find_template(
                template, has_key=_has_key, want_key=_want_key)
        else:
            raise ValueError(template)

        # Apply defaults
        _tag = tag
        if tag is None:
            _tag = self.job.cfg['tokens']['tag']['default']
        _extn = extn
        if extn is None:
            _extn = {'render': 'exr',
                     'mov': 'mp4',
                     'publish': dcc.DEFAULT_EXTN,
                     'cache': 'abc'}.get(_tmpl.type_)

        # Build data dict
        _data = copy.copy(self.data)
        _data['entity'] = self.name
        _data['entity_path'] = self.path
        _data['task'] = task
        _data['tag'] = _tag
        _data['ver'] = '{:03d}'.format(ver_n)
        _data['output_name'] = output_name
        _data['output_type'] = output_type
        _data['extn'] = _extn
        if 'work_dir' in _tmpl.keys():
            _work_dir = self.to_work_dir(task=task)
            _data['work_dir'] = _work_dir.path

        # Construct output
        _path = _tmpl.format(_data)
        return pipe.to_output(_path, template=_tmpl)

    def to_work(
            self, task, tag=None, ver_n=1, dcc_=None, user=None, extn=None,
            class_=None, catch=False):
        """Build a work file object for this entity.

        Args:
            task (str): work file task
            tag (str|None): work file tag
            ver_n (int): work file version number
            dcc_ (str): force dcc token
            user (str): override user (if applicable)
            extn (str): override extension
            class_ (CPWork): override work class
            catch (bool): no error if args are invalid (just
                return None)

        Returns:
            (CPWork): work file
        """
        _work_dir = self.to_work_dir(task=task, dcc_=dcc_)
        return _work_dir.to_work(
            tag=tag, ver_n=ver_n, extn=extn, catch=catch, class_=class_,
            user=user)


def _tmpl_in_seq_dir(tmpl, seq_dir_tmpls):
    """Test whether the given template falls inside a sequence directory.

    Args:
        tmpl (CPTemplate): template to check
        seq_dir_tmpls (CPTemplate list): sequence directory
            templates for this entity

    Returns:
        (bool): whether the given template is inside a sequence directory
    """
    if '{work_dir}' in tmpl.pattern:
        return False
    if tmpl.name == 'seq_dir':
        return False
    for _sd_tmpl in seq_dir_tmpls:
        if tmpl.pattern.startswith(_sd_tmpl.pattern+'/'):
            return True
    return False


def cur_entity(job=None):
    """Get the current entity (if any).

    Args:
        job (CPJob): force parent job (to facilitate caching)

    Returns:
        (CPEntity): current entity
    """
    try:
        return to_entity(dcc.cur_file(), job=job)
    except ValueError:
        return None


def find_entity(name):
    """Find entity matching the given name.

    Args:
        name (str): entity name (eg. hvtest_satan_220613/test010)

    Returns:
        (CPEntity): matching entity
    """
    from pini import pipe
    _job, _label = re.split('[./]', name)
    _job = pipe.find_job(_job)
    return _job.find_entity(_label)


def to_entity(path, job=None, catch=False):
    """Map the given path to an entity.

    Args:
        path (str): path to map
        job (CPJob): force parent job (to facilitate caching)
        catch (bool): no error if no entity found

    Returns:
        (CPAsset|CPShot): asset/shot object
    """
    from pini import pipe
    _LOGGER.debug('TO ENTITY %s', path)

    if isinstance(path, (pipe.CPAsset, pipe.CPShot)):
        return path

    # Treat as job/shot label
    if isinstance(path, six.string_types) and path.count('/') == 1:
        _job_s, _ety_s = path.split('/')
        _job = job or pipe.find_job(_job_s)
        return _job.find_entity(_ety_s)

    _path = to_str(path)
    _path = map_path(_path)
    _LOGGER.debug(' - MAPPED %s', _path)

    # Try as asset
    try:
        return pipe.CPAsset(_path, job=job)
    except ValueError:
        pass

    # Try as shot
    try:
        return pipe.CPShot(_path, job=job)
    except ValueError:
        pass

    if catch:
        return None
    raise ValueError(path)
