"""Tools for managing work files."""

# pylint: disable=too-many-instance-attributes

import copy
import logging
import os
import platform
import sys
import time

import lucidity
import six

from pini import dcc, icons
from pini.utils import (
    File, strftime, HOME, cache_property, to_time_f, get_user,
    passes_filter, single, EMPTY, abs_path, Video, Seq, Image)

from .cp_work_dir import CPWorkDir
from .cp_utils import EXTN_TO_DCC, validate_tokens, map_path, cur_user

_LOGGER = logging.getLogger(__name__)
_SET_WORK_CALLBACKS = {}
_RECENT_WORK_YAML = HOME.to_file(
    '.pini/{}_recent_work.yml'.format(dcc.NAME))
_BKP_TSTAMP_FMT = '%y%m%d_%H%M%S'


class CPWork(File):  # pylint: disable=too-many-public-methods
    """Represents a work file on disk."""

    entity_type = None
    asset_type = None
    asset = None
    sequence = None
    shot = None

    tag = None
    task = None
    user = None
    ver = None

    def __init__(self, file_, work_dir=None, template=None):
        """Constructor.

        Args:
            file_ (str): path to work file
            work_dir (CPWorkDIr): force parent work dir
            template (CPTemplate): force template
        """
        _file = abs_path(file_)
        _LOGGER.debug('INIT %s %s', type(self).__name__, file_)
        super(CPWork, self).__init__(_file)

        if self.extn not in EXTN_TO_DCC:
            raise ValueError(self.extn)

        # Set up entity/job
        self.work_dir = work_dir or CPWorkDir(_file)
        self.entity = self.work_dir.entity
        self.job = self.entity.job

        # Pass attrs
        self.profile = self.entity.profile
        self.entity_type = self.entity.entity_type
        self.asset_type = self.entity.asset_type
        self.asset = self.entity.asset
        self.sequence = self.entity.sequence
        self.shot = self.entity.shot
        self.task = self.work_dir.task
        self.step = self.work_dir.step

        # Find templates
        if template:
            _tmpls = [template]
        else:
            _tmpls = [
                _tmpl.apply_data(
                    work_dir=self.work_dir.path, entity=self.entity.name,
                    task=self.work_dir.task, extn=self.extn,
                    step=self.work_dir.step, shot=self.entity.name)
                for _tmpl in self.job.find_templates(
                    type_='work', profile=self.entity.profile,
                    dcc_=EXTN_TO_DCC[self.extn])]
        _LOGGER.log(9, ' - TMPLS %s', _tmpls)

        # Extract data - use single template if possible for better error
        if len(_tmpls) == 1:
            self.template = single(_tmpls)
            try:
                self.data = self.template.parse(self.path)
            except lucidity.ParseError as _exc:
                _LOGGER.debug(' - TMPL %s', self.template)
                _LOGGER.debug(' - EXC %s', _exc)
                raise ValueError('Lucidity rejected '+self.path)
        else:
            try:
                self.data, self.template = lucidity.parse(self.path, _tmpls)
            except lucidity.ParseError as _exc:
                _LOGGER.debug(' - EXC %s', _exc)
                raise ValueError('Lucidity rejected '+self.path)
        self.data['task'] = self.work_dir.task
        _LOGGER.log(9, ' - WORK DATA %s', self.data)
        _LOGGER.log(9, ' - WORK TMPL %s', self.template)
        for _key, _val in self.data.items():
            if _key in ('entity', 'work_dir'):
                continue
            setattr(self, _key, _val)

        validate_tokens(self.data, job=self.job)

        self.dcc = (
            self.data.get('dcc') or
            self.work_dir.dcc or
            self.template.dcc)
        self.ver_n = int(self.ver)
        self.sequence = self.entity.sequence

        self.metadata_yml = self.to_dir().to_file(
            '.pini/metadata/{}.yml'.format(self.base))
        self.thumb = self.to_dir().to_file(
            '.pini/thumb/{}.jpg'.format(self.base))
        self.image = self.to_dir().to_file(
            '.pini/image/{}.jpg'.format(self.base))

    @property
    def cmp_key(self):
        """Obtain sort key for this work file.

        This allows work files to be sorted by version, even if there is
        a username token embedded in the path.

        Returns:
            (tuple): sort key
        """
        return self.work_dir.path, self.filename

    @property
    def metadata(self):
        """Object work metadata.

        Returns:
            (dict): metadata
        """
        return self._read_metadata()

    @property
    def notes(self):
        """Obtain work notes.

        Returns:
            (str): notes
        """
        return self.metadata.get('notes')

    def _owner_from_user(self):
        """Obtain owner based on user tag.

        Returns:
            (str|None): owner (if any)
        """
        if self.user:

            # Avoid nasty shotgrid name if possible
            from pini import pipe
            if self.user == pipe.cur_user():
                return get_user()

            return self.user

        return None

    def owner(self):
        """Obtain owner of this work file.

        In cases where the user is embedded in the path, this
        user token should be used, although to avoid ugly shotgrid
        names mapped from emails (eg. my-name-company-com), if the
        token is the current user then the login name can be used
        instead (eg. mname).

        Otherwise, this is simply the owner of the file on disk.

        Returns:
            (str): file owner
        """
        return self._owner_from_user() or super(CPWork, self).owner()

    def find_template(self, type_, has_key=None, want_key=None, dcc_=None,
                      catch=False):
        """Find template with keys matching this work file.

        Args:
            type_ (str): template type
            has_key (dict): dict of keys and whether that key should
                be present in the template
            want_key (list): list of keys which are preferred
                but not necessary
            dcc_ (str): filter by dcc
            catch (bool): no error if exactly one template isn't found

        Returns:
            (CPTemplate): matching template
        """
        _LOGGER.debug('FIND TEMPLATE %s', type_)
        _has_key = {'ver': True}
        if has_key:
            _has_key.update(has_key)
        _want_key = {'tag': bool(self.tag),
                     'user': bool(self.user)}
        if want_key:
            _want_key.update(want_key)
        _dcc = dcc_ or EXTN_TO_DCC[self.extn]
        return self.entity.find_template(
            type_=type_, has_key=_has_key, dcc_=_dcc, want_key=_want_key,
            catch=catch)

    def _read_metadata(self):
        """Read work metadata from disk.

        Returns:
            (dict): metadata
        """
        if self.metadata_yml.exists():
            _data = self.metadata_yml.read_yml()
        elif not self.exists():
            _data = {}
        else:
            _owner = self.user or super(CPWork, self).owner()
            _mtime = int(File(self).mtime())
            _data = {
                'size': self.size(),
                'owner': _owner,
                'mtime': _mtime,
            }
            self.metadata_yml.write_yml(_data)
        return _data

    def find_latest(self, catch=False):
        """Find latest version of this work file.

        Args:
            catch (bool): no error if no versions found

        Returns:
            (CPWork): latest version
        """
        _vers = self.find_vers()
        if _vers:
            return _vers[-1]
        if catch:
            return None
        raise ValueError('No versions found '+self.path)

    def find_next(self, user=None, class_=None):
        """Find next version, ie. one after the latest one.

        This version should not exist on disk.

        Args:
            user (str): override user
            class_ (class): override work file class

        Returns:
            (CPWork): next version
        """
        _LOGGER.debug('FIND NEXT %s', self)

        _latest = self.find_latest(catch=True)
        _LOGGER.debug(' - LATEST %s', _latest)

        # Determine next version
        if not _latest:
            _ver_n = 1
        else:
            _ver_n = _latest.ver_n+1
        _user = user or cur_user()
        _next = self.to_work(ver_n=_ver_n, class_=class_, user=_user)
        assert _next.work_dir is self.work_dir
        return _next

    def find_vers(self):
        """Find all versions of this work file.

        Returns:
            (CPWorkFile list): work file list
        """
        return self.work_dir.find_works(tag=self.tag)

    def has_bkp(self):
        """Test if this file has a corresponding backup file.

        This assumed that the mtime in the work metadata matches
        the mtime of the backup file.

        Returns:
            (bool): whether bkp file exists
        """
        _data = self.metadata
        _mtime = _data.get('mtime', int(File(self).mtime()))
        _bkp = self._to_bkp_file(mtime=_mtime)
        return _bkp.exists()

    def _to_bkp_file(self, mtime=None, extn=None):
        """Build a backup file object.

        Args:
            mtime (int): backup mtime
            extn (str): override backup extension

        Returns:
            (File): backup file
        """
        _mtime = mtime or time.time()
        _extn = extn or self.extn
        return self.to_dir().to_file('.pini/bkp/{}/{}.{}'.format(
            self.base, strftime(_BKP_TSTAMP_FMT, _mtime), _extn))

    def find_bkps(self):
        """Find backup files belonging to this work.

        Returns:
            (File list): backup files
        """
        _bkp_dir = self._to_bkp_file().to_dir()
        return _bkp_dir.find(
            depth=1, type_='f', extn=self.extn, class_=_CPWorkBkp,
            catch_missing=True)

    def flush_bkps(self, reason_filter=None):  # pylint: disable=arguments-differ
        """Remove backup files.

        Args:
            reason_filter (str): filter list by reason
        """
        for _bkp in self.find_bkps():
            if reason_filter and not passes_filter(_bkp.reason, reason_filter):
                continue
            _LOGGER.info(' - DELETE BKP %s %s', _bkp.reason, _bkp)
            _bkp.yml.delete(force=True)
            _bkp.delete(force=True)

    def find_output(self, type_=None, catch=False, **kwargs):
        """Find a matching output belonging to this work file.

        Args:
            type_ (str): filter by type (eg. publish/cache)
            catch (bool): no error if didn't match exactly one output

        Returns:
            (CPOutput): matching output
        """
        _outs = self.find_outputs(type_=type_, **kwargs)
        return single(_outs, catch=catch, items_label='outputs')

    def find_outputs(
            self, base=None, type_=None, output_name=None, extn=None):
        """Find outputs generated from this work file.

        Args:
            base (str): filter by filename base
            type_ (str): filter by type (eg. publish/cache)
            output_name (str): filter by output name (eg. bty_ao/horse02)
            extn (str): filter by file extension (eg. abc/jpg)

        Returns:
            (CPOutput list): matching outputs
        """
        _outs = []
        for _out in self._read_outputs():
            if base and _out.base != base:
                continue
            if type_ and _out.type_ != type_:
                continue
            if output_name and _out.output_name != output_name:
                continue
            if extn and _out.extn != extn:
                continue
            _outs.append(_out)
        return _outs

    def is_latest(self):
        """Test whether this is the latest version.

        Returns:
            (bool): whether latest
        """
        return self == self.find_latest()

    def _read_outputs(self):
        """Read disk to find outputs outputs generated from this work file.

        Returns:
            (CPOutput list): outputs
        """
        from pini import pipe
        _LOGGER.debug('READ OUTPUTS %s', self)

        _outs = []
        _start = time.time()

        # Find outputs
        if pipe.MASTER == 'disk':

            # Add entity level outputs
            _ety_outs = self.entity.find_outputs(
                task=self.task, ver_n=self.ver_n, tag=self.tag)
            _LOGGER.debug(
                ' - FOUND %d ENTITY OUTS IN %.01fs %s', len(_ety_outs),
                time.time() - _start, self.entity)
            _outs += _ety_outs

            # Add work dir level outputs
            _start = time.time()
            _wd_outs = self.work_dir.find_outputs(
                ver_n=self.ver_n, tag=self.tag)
            _LOGGER.debug(
                ' - FOUND %d WORKDIR OUTS IN %.01fs %s', len(_wd_outs),
                time.time() - _start, self.work_dir)
            _outs += _wd_outs

            assert not set(_wd_outs) & set(_ety_outs)
            _outs.sort()

        elif pipe.MASTER == 'shotgrid':
            _LOGGER.debug(' - SEARCHING JOB OUTS %s', self.job)
            _outs = self.job.find_outputs(
                entity=self.entity, task=self.task, ver_n=self.ver_n,
                tag=self.tag)
            _LOGGER.debug(' - FOUND %d OUTS', len(_outs))

        else:
            raise ValueError(pipe.MASTER)

        # Update image thumbnail
        self._check_image(_outs)
        return _outs

    def _check_image(self, outputs):
        """Check this work file's thumbnail image against the given outputs.

        If the image doesn't exist and there are convertable outputs (ie. videos
        or image sequences), it will be generated from the outputs.

        Args:
            outputs (CPOutput list): outputs from this work file
        """
        _LOGGER.debug(' - CHECK IMAGE')
        if self.image.exists():
            _LOGGER.debug(' - IMAGE EXISTS')
            return

        # Check videos
        _vids = [_out for _out in outputs if isinstance(_out, Video)]
        if _vids:
            _vid = _vids[0]
            _LOGGER.info(' - EXTRACT FRAME %s', _vid)
            _img = _vid.to_frame(self.image)
            _LOGGER.info(' - IMG %s', _img)
            assert self.image.exists()
            return

        # Check seqs
        _seqs = sorted(
            [_out for _out in outputs if isinstance(_out, Seq)],
            key=_out_seq_img_sort)
        if _seqs:
            _seq = _seqs[0]
            _LOGGER.info(' - EXTRACT FRAME %s', _seq)
            _frame = _seq.to_frame_file()
            if _frame.extn == 'jpg':
                _LOGGER.info(' - FRAME %s', _frame)
                _frame.copy_to(self.image)
                assert self.image.exists()
            else:
                Image(_frame).convert(self.image, catch=True)
            return

    def save(self, notes=None, reason=None, mtime=None, parent=None,
             force=None):
        """Save this work version.

        Args:
            notes (str): notes for save
            reason (str): save reason (for backup label)
            mtime (int): force save mtime
            parent (QDialog): parent dialog for confirmation dialogs
            force (bool): overwrite existing + create entity
                without confirmation
        """
        from pini import pipe
        _LOGGER.debug('SAVE WORK %s', self)

        if not self.work_dir.exists():
            self.work_dir.create(force=force)

        # Determine globals
        _mtime = mtime or int(time.time())
        _LOGGER.debug(' - MTIME %s %s %s', _mtime, strftime('%H:%M:%S', _mtime),
                      mtime)
        _reason = reason
        _notes = notes or self.notes
        if _notes:
            _notes = str(_notes)
        _force = force
        if (  # Save over existing without confirmation if owner matches
                _force is None and
                dcc.cur_file() == self.path and
                self.metadata.get('owner') == get_user()):
            _force = True

        # Backup any existing file if needed
        if not self.exists():
            _LOGGER.debug(' - NEW SAVE')
            _reason = _reason or 'new save'
        else:
            if not self.has_bkp():
                _LOGGER.debug(' - SAVING EXISTING WORK W/O BKP')
                _metadata = self.metadata
                _owner = _metadata.get('owner', self.owner())
                _owner = _owner or self.user
                _LOGGER.debug(' - OWNER %s', _owner)
                _e_mtime = int(File(self).mtime())
                self._save_bkp(
                    source=self, reason='backup existing', notes=_notes,
                    owner=_owner, mtime=_e_mtime)
            else:
                _LOGGER.debug(' - EXISTING FILE HAS BKP')
            _reason = reason or 'save over'

        # Save file + bkp + metadata
        _LOGGER.debug(' - SAVE SCENE %s', self.path)
        dcc.save(file_=self.path, force=_force, parent=parent)
        self._save_metadata(notes=_notes, mtime=_mtime)
        self._save_bkp(
            source=self, reason=_reason, mtime=_mtime, notes=_notes,
            owner=get_user())

        # Update shotgrid tasks (add user + set to in progress)
        if (
                pipe.SHOTGRID_AVAILABLE and
                not self.entity.settings['shotgrid']['disable']):
            from pini.pipe import shotgrid
            try:
                shotgrid.update_work_task(self)
            except Exception as _exc:  # pylint: disable=broad-except
                _LOGGER.error('FAILED TO UPDATE SHOTGRID %s', _exc)

        self.set_env()

    def _save_bkp(
            self, reason, source=None, mtime=None, owner=None, notes=None):
        """Save a backup file.

        Args:
            reason (str): backup reason
            source (File): source file
            mtime (int): backup mtime
            owner (str): force owner
            notes (str): notes for bkp metadata
        """
        _LOGGER.debug('SAVE BKP mtime=%s', mtime)

        # Check vars
        assert reason.islower()
        _mtime = mtime or self.metadata.get('mtime') or int(self.mtime())
        _LOGGER.debug(' - MTIME %s', _mtime)
        assert isinstance(_mtime, int)
        _data = {'owner': owner or self.metadata.get('owner'),
                 'notes': notes or self.metadata.get('notes'),
                 'reason': reason}
        _src = source or self

        # Determine bkp path
        _bkp = self._to_bkp_file(mtime=_mtime)
        _LOGGER.debug(' - BKP %s', _bkp.path)

        # Save bkp
        File(_src).copy_to(_bkp, force=True)
        _LOGGER.debug(' - SAVED BKP %s', _bkp.path)
        _bkp_yml = self._to_bkp_file(extn='yml', mtime=_mtime)
        _bkp_yml.write_yml(_data, force=True)
        _LOGGER.debug(' - SAVED BKP YML %s', _bkp_yml)

        return _bkp

    def _save_metadata(self, notes, mtime):
        """Save work metadata to yml.

        Args:
            notes (str): work notes
            mtime (int): work mtime
        """
        assert isinstance(mtime, int)

        _data = {}
        _data['fps'] = dcc.get_fps()
        _data['dcc'] = '{}-{}'.format(dcc.NAME, dcc.to_version(str))
        _data['machine'] = platform.node()
        _data['mtime'] = mtime
        _data['notes'] = notes
        _data['user'] = get_user()
        _data['owner'] = self.owner()
        _data['platform'] = sys.platform
        _data['range'] = dcc.t_range()
        _data['size'] = int(os.path.getsize(self.path))

        self.set_metadata(_data)

    def add_metadata(self, **kwargs):
        """Add to existing metadata."""
        _data = copy.copy(self.metadata)
        _data.update(kwargs)
        self.set_metadata(_data)

    def set_metadata(self, data):
        """Set metadata for this work file.

        Args:
            data (dict): metadata to apply
        """
        self.metadata_yml.write_yml(data, force=True)
        _LOGGER.debug('SAVED METADATA %s', self.metadata_yml.path)

    def set_notes(self, notes):
        """Set work file notes.

        Existing metadata is maintained.

        Args:
            notes (str): notes to apply
        """
        _data = self.metadata
        _data['notes'] = notes
        self.metadata_yml.write_yml(_data, force=True)

    def set_env(self):
        """Set environment to match this work file."""
        add_recent_work(self)

        os.environ['PINI_JOB'] = self.job.name
        os.environ['PINI_JOB_PATH'] = self.job.path
        os.environ['PINI_ENTITY'] = self.entity.name
        os.environ['PINI_ENTITY_PATH'] = self.entity.path

        os.environ['PINI_TASK'] = self.task
        os.environ['PINI_TAG'] = self.tag or ''
        os.environ['PINI_VER'] = self.ver

        if dcc.NAME == 'hou':
            import hou
            hou.putenv('JOB', self.job.path)  # pylint: disable=c-extension-no-member

        for _, _callback in sorted(_SET_WORK_CALLBACKS.items()):
            _callback(self)

    def load(self, parent=None, force=False, lazy=False, load_func=None):
        """Load this work file in the current dcc.

        Args:
            parent (QDialog): parent dialog for popups
            force (bool): load scene without unsaved changes warning
            lazy (bool): don't load the file if it's already open
            load_func (func): override load function
        """

        # Obtain file to load - if this work file does not exist then
        # load the job empty file (if any)
        _file = File(self.path)
        _save = False
        if not _file.exists():
            _file = self.job.to_empty_file()
            _save = True

        # Load the file or create the scene
        if load_func:
            load_func()
        elif _file:
            dcc.load(_file, parent=parent, force=force, lazy=lazy)
        else:
            dcc.new_scene(force=force, parent=parent)
        if _save:
            self.save()

        self.set_env()

    def to_output(
            self, template, has_key=None, dcc_=None, ver_n=None, **kwargs):
        """Build an output from this work file's template data.

        Args:
            template (CPTemplate): output template to use
            has_key (dict): dict of keys and whether that key should
                be present in the template
            dcc_ (str): filter by dcc
            ver_n (int): apply version number

        Returns:
            (CPOutput): output
        """
        from pini import pipe
        _LOGGER.debug('TO OUTPUT')
        _dcc = dcc_ or dcc.NAME

        # Build data
        _data = {
            'entity_path': self.entity.path,
            'entity': self.entity.name,
            'user': self.user,
            'dcc': _dcc}
        _data.update(self.data)
        if 'data' in kwargs:
            raise TypeError
        if ver_n is not None:
            _ver_pad = self.job.cfg['tokens']['ver']['len']
            _data['ver'] = str(ver_n).zfill(_ver_pad)
        _data.update(kwargs)
        _LOGGER.debug(' - DATA %s', _data)

        # Get template
        if isinstance(template, pipe.CPTemplate):
            _tmpl = template
        elif isinstance(template, six.string_types):
            _want_key = {}
            for _key in ['output_name', 'output_type', 'tag']:
                if _key in _data:
                    _want_key[_key] = bool(_data[_key])
            _LOGGER.debug(' - WANT KEY %s', _want_key)
            _tmpl = self.find_template(
                template, dcc_=_dcc, has_key=has_key, want_key=_want_key)
        else:
            raise ValueError(template)
        _LOGGER.debug(' - TEMPLATE %s', _tmpl)

        # Get output class
        if _tmpl.type_ in pipe.OUTPUT_TEMPLATE_TYPES:
            _class = pipe.CPOutput
        elif _tmpl.type_ in pipe.OUTPUT_VIDEO_TEMPLATE_TYPES:
            _class = pipe.CPOutputVideo
        elif _tmpl.type_ in pipe.OUTPUT_SEQ_TEMPLATE_TYPES:
            _class = pipe.CPOutputSeq
        else:
            raise ValueError(_tmpl.name)
        _LOGGER.debug(' - CLASS %s', _class)

        _path = _tmpl.format(_data)
        _LOGGER.debug(' - PATH %s', _path)
        _work_dir = self.work_dir if self.work_dir.contains(_path) else None
        if _work_dir:
            _tmpl = _tmpl.apply_data(work_dir=_work_dir.path)

        return _class(_path, templates=[_tmpl], entity=self.entity,
                      work_dir=_work_dir)

    def to_work(
            self, task=None, tag=EMPTY, user=EMPTY, ver_n=None, class_=None):
        """Build a work file using this work file's template data.

        Args:
            task (str): override task
            tag (str): override tag
            user (str): over user
            ver_n (int): override version number
            class_ (class): override work file class

        Returns:
            (CPWork): mapped work file
        """
        _LOGGER.debug('TO WORK %s', self.path)
        _class = class_ or CPWork

        # Determine work dir, maintaining current if possible
        _work_dir = self.work_dir.to_work_dir(user=user)
        _LOGGER.debug(' - WORK DIR %s', _work_dir)
        if _work_dir == self.work_dir:
            _LOGGER.debug(' - USING THIS WORK DIR')
            _work_dir = self.work_dir

        # Build data dict
        _data = copy.copy(self.data)
        if user:
            _data['user'] = user
        _data['work_dir'] = _work_dir.path
        if task is not None:
            _data['task'] = task
            _work_dir = self.entity.to_work_dir(task=task)
            _data['work_dir'] = _work_dir.path
        if tag is not EMPTY:
            _data['tag'] = tag
        if ver_n is not None:
            _ver_pad = self.job.cfg['tokens']['ver']['len']
            _data['ver'] = str(ver_n).zfill(_ver_pad)
        _LOGGER.debug(' - DATA %s', _data)

        # Obtain fresh template (in case tokens have been filled in)
        _tmpl = self.job.find_template(
            'work', profile=self.entity.profile, dcc_=self.dcc,
            has_key={'tag': 'tag' in _data})
        _LOGGER.debug(' - TMPL %s', _tmpl)

        return _class(_tmpl.format(_data), work_dir=_work_dir)

    def __lt__(self, other):
        return self.cmp_key < other.cmp_key


class _CPWorkBkp(File):
    """Represents a work backup file."""

    def mtime(self):
        """Obtain backup time by parsing filename.

        Returns:
            (float): mtime
        """
        return to_time_f(time.strptime(self.base, _BKP_TSTAMP_FMT))

    @cache_property
    def metadata(self):
        """Obtain backup metadata.

        Returns:
            (dict): metadata
        """
        return self.yml.read_yml()

    @property
    def reason(self):
        """Obtain backup reason (eg. save over, cache).

        Returns:
            (str): reason
        """
        return self.metadata['reason']

    @property
    def yml(self):
        """Obtain this backup file's yml file.

        Returns:
            (File): yml file
        """
        return self.to_file(extn='yml')


def add_recent_work(work):
    """Add work file to list of recent work.

    Args:
        work (CPWork): work file to add
    """
    _v000 = work.to_work(ver_n=0)
    _recent = recent_work()
    _recent.insert(0, _v000)

    _paths = []
    for _work in _recent:
        _path = str(_work.path)
        if _path in _paths:
            continue
        _paths.append(_path)
    _paths = _paths[:20]

    _RECENT_WORK_YAML.write_yml(_paths, force=True)


def cur_work(work_dir=None):
    """Get a work file object for the current scene.

    Args:
        work_dir (CPWorkDIr): force parent work dir (to faciliate caching)

    Returns:
        (CPWork|None): current work (if any)
    """
    _file = dcc.cur_file()
    if not _file:
        return None
    _file = abs_path(_file)
    try:
        return CPWork(_file, work_dir=work_dir)
    except (ValueError, TypeError):
        return None


def install_set_work_callback(callback):
    """Install callback to be applied on set work.

    Args:
        callback (fn): callback to execute on set work
    """
    _SET_WORK_CALLBACKS[callback.__name__] = callback


def load_recent():
    """Load most recent work file."""
    from pini import qt
    _latest = recent_work()[0].find_latest()
    qt.ok_cancel(
        'Load latest work file?\n\n'+_latest.path,
        title='Load Recent', icon=icons.find('Monkey Face'))
    _latest.load()


def recent_work():
    """Read list of recent work file.

    The newest is at the front of the list.

    Returns:
        (CPWork list): recent work files
    """
    _LOGGER.debug('RECENT WORK %s', _RECENT_WORK_YAML.path)
    _paths = _RECENT_WORK_YAML.read_yml(catch=True) or []
    _works = []
    for _path in _paths:
        try:
            _work = CPWork(_path)
        except ValueError:
            _LOGGER.debug(' - REJECTED %s', _path)
            continue
        _works.append(_work)
    return _works


def _out_seq_img_sort(seq):
    """Sort for output sequences to priorities certain layers.

    Args:
        seq (CPOutputSeq): output to sort

    Returns:
        (tuple): sort key
    """
    return seq.output_name in ['masterLayer', 'defaultRenderLayer'], seq.path


def to_work(file_, catch=True):
    """Build a work file from the given path.

    Args:
        file_ (str): path to work file
        catch (bool): no error if file doesn't create valid work file

    Returns:
        (CPWork): work file
    """
    _LOGGER.debug('TO WORK %s', file_)

    if isinstance(file_, CPWork):
        return file_
    if file_ is None:
        if catch:
            return None
        raise ValueError

    _file = map_path(file_)
    _LOGGER.debug(' - FILE %s', _file)
    try:
        return CPWork(_file)
    except ValueError as _exc:
        _LOGGER.debug(' - FAILED TO MAP %s', _exc)
        if catch:
            return None
        raise _exc
