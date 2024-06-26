"""Tools for managing jobs."""

# pylint: disable=too-many-public-methods,disable=too-many-lines

import copy
import logging
import operator
import os
import time

import six

from pini import dcc, icons
from pini.utils import (
    Dir, abs_path, single, cache_property, norm_path, merge_dicts, to_str,
    apply_filter, DATA_PATH, File, cache_on_obj, EMPTY, cache_result,
    passes_filter, HOME_PATH, is_abs)

from . import cp_settings, cp_template
from .cp_utils import map_path

_LOGGER = logging.getLogger(__name__)

JOBS_ROOT = Dir(os.environ.get(
    'PINI_JOBS_ROOT',
    HOME_PATH+'/Documents/Projects'))

_JOB_MATCHES = {}
_DEFAULT_CFG_NAME = "Quirinus"
_DEFAULT_CFG = {
    'defaults': {},
    'name': None,
    'tasks': {},
    'templates': {},
    'tokens': {
        'asset_type': {'filter': None},
        'sequence': {'filter': None, 'whitelist': []},
        'dcc': {'allowed': dcc.DCCS},
        'tag': {'default': None, 'nounderscore': True},
        'ver': {'len': 3},
    }}


class CPJob(cp_settings.CPSettingsLevel):
    """Represents a job on disk.

    This is the top-level folder for any film/commercial.
    """

    def __init__(self, path, jobs_root=None):
        """Constructor.

        Args:
            path (str): path within the job
            jobs_root (str): override jobs root
        """
        _path = abs_path(to_str(path))
        _root = Dir(jobs_root or JOBS_ROOT)
        _rel_path = _root.rel_path(_path)
        _path = _root.to_subdir(_rel_path.split('/')[0])
        super(CPJob, self).__init__(_path)
        self.name = self.filename

    @property
    def cfg_file(self):
        """Obtain config file for this job.

        Returns:
            (File): config
        """
        _path = os.environ.get('PINI_PIPE_CFG_PATH', '.pini/config.yml')
        _file = self.to_file(_path) if not is_abs(_path) else File(_path)
        _file = File(map_path(_file.path))
        return _file

    @cache_on_obj
    def get_cfg(self, force=False):
        """Obtain job config.

        Args:
            force (bool): force reread config from disk

        Returns:
            (dict): job config
        """
        _yml_cfg = self.cfg_file.read_yml(catch=True)
        _cfg = merge_dicts(_DEFAULT_CFG, _yml_cfg)
        if 'name' in _cfg and _cfg['name']:
            assert _cfg['name'] == _yml_cfg['name']
        return _cfg

    def create(self, cfg_name=_DEFAULT_CFG_NAME):
        """Create this job on disk.

        Args:
            cfg_name (str): name of config to use

        Returns:
            (CPJob): updated job
        """
        from pini import qt
        qt.ok_cancel(
            'Create new job using <i>{}</i> structure?<br><br>{}'.format(
                cfg_name, self.path),
            icon=icons.find('Rosette'), title='Create Job')
        self.mkdir()
        self.setup_cfg(cfg_name)
        return self

    def setup_cfg(self, name=_DEFAULT_CFG_NAME):
        """Setup config file for this job.

        Args:
            name (str): name of config to apply
        """
        _dir = Dir(DATA_PATH).to_subdir('job_templates')
        _tmpl_cfg = single(_dir.find(
            depth=1, extn='yml', base=name, class_=True))
        _LOGGER.info('SETUP CFG %s', _tmpl_cfg)
        _tmpl_cfg.copy_to(self.cfg_file)

    @property
    def cfg(self):
        """Obtain config data.

        This is used to configure the pipeline and should be pretty
        static - changing it in an active job should normally be avoided.
        It is used to define paths and naming conventions.

        Returns:
            (dict): job config
        """
        return self.get_cfg()

    @property
    def templates(self):
        """Obtain templates data, read from config.

        Returns:
            ({name: Template list} dict): template name/object data
        """
        return self._build_templates()

    @cache_result
    def _build_templates(self, force=False, catch=True):
        """Build templates data from config into Template objects.

        To handling optional tokens (not supported by lucidity), optional
        tokens are expanded to a list of all the possible options. For
        this reason, each template name had a list of template options to
        apply. In most cases this will just contain a single item.

        Args:
            force (bool): force rebuild templates from config
            catch (bool): catch any errors and return an empty dict

        Returns:
            ({name: Template list} dict): template name/object data
        """
        return cp_template.build_job_templates(job=self, catch=catch)

    def find_template(
            self, type_, profile=None, dcc_=None, alt=EMPTY,
            has_key=None, want_key=None, catch=False):
        """Find a single template within this job's templates.

        Args:
            type_ (str): template type (eg. shot_entity_path/work)
            profile (str): template profile (ie. asset/shot)
            dcc_ (str): template dcc (eg. nuke/maya)
            alt (int): filter by alt version of template
            has_key (dict): dict of keys and whether that key should
                be present in the template
            want_key (list): list of keys which are preferred
                but not necessary
            catch (bool): no error if no matching template found

        Returns:
            (CPTemplate): matching template
        """
        _LOGGER.debug('FIND TEMPLATE')

        # Find matching templates
        _tmpls = self.find_templates(
            type_=type_, profile=profile, dcc_=dcc_, has_key=has_key,
            want_key=want_key, alt=alt)
        if len(_tmpls) == 1:
            return single(_tmpls)
        _LOGGER.debug(' - FOUND %s TEMPLATES', len(_tmpls))

        # Apply alt filtering
        _alts = sorted({_tmpl.alt for _tmpl in _tmpls})
        if len(_alts) > 1:
            _tmpls = [_tmpl for _tmpl in _tmpls if _tmpl.alt == _alts[0]]
            _LOGGER.debug(' - DISCARDING ALTS %d %s', len(_tmpls), _alts)

        try:
            return single(_tmpls, catch=catch)
        except ValueError:
            _LOGGER.debug(
                'FAILED TO FIND TEMPLATE tmpls=%d has_key=%s want_key=%s '
                'tmpls=%s', len(_tmpls), has_key, want_key, _tmpls)
            raise ValueError(
                'Failed to find template "{}" in {}'.format(
                    type_, self.name))

    @cache_result
    def find_template_by_pattern(self, pattern):
        """Find template by its pattern.

        Args:
            pattern (str): pattern to match

        Returns:
            (CPTemplate): matching template
        """
        _tmpl = single(self.find_templates(pattern=pattern), catch=True)
        if not _tmpl:
            raise ValueError('Failed to match pattern {}'.format(pattern))
        return _tmpl

    def find_templates(
            self, type_=None, profile=None, dcc_=None, alt=EMPTY, has_key=None,
            want_key=None, pattern=None):
        """Find templates in this job.

        The list is sorted in order of precendence, ie. a nuke_shot_work
        template will take precendence over a shot_work template, which
        will take precendence over a generic work template.

        Args:
            type_ (str): template type (eg. work_dir/work/entity_path)
            profile (str): filter by profile (ie. asset/shot)
            dcc_ (str): filter by dcc
            alt (int): filter by alt version of template
            has_key (dict): dict of keys and whether that key should
                be present in the template
            want_key (dict): dict of keys which are preferred
                but not necessary
            pattern (str): match template by pattern

        Returns:
            (CPTemplate list): matching templates
        """
        _LOGGER.log(9, 'FIND TEMPLATES %s type_=%s', self.name, type_)

        # Apply simple filters
        if profile:
            assert profile in ['shot', 'asset']
        _tmpls = []
        for _tmpl in sum(self.templates.values(), []):
            if type_ and _tmpl.type_ != type_:
                continue
            if profile and _tmpl.profile not in (None, profile):
                continue
            if pattern and _tmpl.pattern != pattern:
                continue
            if alt is not EMPTY and _tmpl.alt != alt:
                continue
            _tmpls.append(_tmpl)

        # Apply complex filters
        if dcc_:
            _tmpls = self._find_templates_dcc(_tmpls, dcc_=dcc_)
        if has_key:
            _tmpls = self._find_templates_has_key(_tmpls, has_key=has_key)
        if want_key:
            _tmpls = self._find_templates_want_key(_tmpls, want_key=want_key)

        _tmpls = sorted(_tmpls, key=operator.attrgetter('name'))
        return _tmpls

    def _find_templates_dcc(self, templates, dcc_):
        """Find templates matching the given dcc.

        If no templates match the given dcc then the filter is not applied.

        Args:
            templates (CPTemplate list): list of templates to filter
            dcc_ (str): dcc filter to apply

        Returns:
            (CPTemplate list): matching templates
        """
        _dcc_tmpls = [_tmpl for _tmpl in templates if _tmpl.dcc == dcc_]
        if _dcc_tmpls:
            _tmpls = _dcc_tmpls
        else:
            _tmpls = [_tmpl for _tmpl in templates if not _tmpl.dcc]
        return _tmpls

    def _find_templates_has_key(self, templates, has_key):
        """Find templates with specific keys.

        Args:
            templates (CPTemplate list): list of templates to filter
            has_key (dict): dict of keys and whether that key should
                be present in the template

        Returns:
            (CPTemplate list): matching templates
        """
        _tmpls = templates
        _LOGGER.debug(' - APPLY HAS KEY %s', has_key)
        assert isinstance(has_key, dict)
        for _key, _toggle in has_key.items():
            _tmpls = [_tmpl for _tmpl in _tmpls
                      if (_key in _tmpl.keys()) == _toggle]
        _LOGGER.debug(' - APPLIED HAS KEY %d %s', len(_tmpls), _tmpls)
        return _tmpls

    def _find_templates_want_key(self, templates, want_key):
        """Find templates with specific keys if they're available.

        If a want key is available, templates with that key are returned.
        However, if the key in unavailable then no filter is applied.

        Args:
            templates (CPTemplate list): list of templates to filter
            want_key (dict): dict of keys which are preferred
                but not necessary

        Returns:
            (CPTemplate list): matching templates
        """
        _tmpls = templates
        _LOGGER.debug(' - APPLY WANT KEY %s %s', want_key, _tmpls)
        assert isinstance(want_key, dict)
        for _key, _toggle in want_key.items():
            _matching_tmpls = [_tmpl for _tmpl in _tmpls
                               if (_key in _tmpl.keys()) == _toggle]
            if _matching_tmpls:
                _tmpls = _matching_tmpls
                _LOGGER.debug('   - ALLOWED %s FILTER', _key)
        _LOGGER.debug(' - APPLIED WANT KEY %d %s', len(_tmpls), _tmpls)
        return _tmpls

    @cache_property
    def uses_asset_type_dirs(self):
        """Test whether this job uses asset type dirs.


        This means that each asset type has its own directory, eg. /char/

        Returns:
            (bool): whether asset type dirs used
        """
        _tmpl = self.find_template('entity_path', profile='asset')
        _type_dir = single([_token for _token in _tmpl.pattern.split('/')
                            if '{asset_type}' in _token])
        return _type_dir == '{asset_type}'

    @cache_property
    def uses_sequence_dirs(self):
        """Check whether this job uses sequence dirs.

        If each sequence is in a separate directory, this returns true.
        Otherwise, if all shots are in the same directory, returns false.

        Returns:
            (bool): whether sequence dirs used
        """
        _tmpl = self.find_template('entity_path', profile='shot', catch=True)
        if not _tmpl:
            return True
        return '/{sequence}/' in _tmpl.pattern

    def create_asset_type(self, asset_type, force=False, parent=None):
        """Create an asset type within this job.

        Args:
            asset_type (str): name of asset type to create
            force (bool): create asset type without confirmation dialogs
            parent (QDialog): parent for confirmation dialogs
        """
        _LOGGER.info('CREATE ASSET TYPE %s', asset_type)

        # Obtain asset type dir
        _tmpl = self.find_template('entity_path', profile='asset')
        _tmpl = _tmpl.crop_to_token('asset_type')
        _tmpl = _tmpl.apply_data(job_path=self.path)
        _LOGGER.info(' - TMPL %s', _tmpl)
        _type_dir = Dir(_tmpl.format(asset_type=asset_type))
        _LOGGER.info(' - ASSET TYPE DIR %s', _type_dir)
        assert _type_dir.filename == asset_type
        assert not _type_dir.exists()

        # Confirm
        if not force:
            from pini import qt
            qt.ok_cancel(
                'Create new asset type {} in {}?\n\n{}'.format(
                    asset_type, self.name, _type_dir.path),
                icon=icons.find('Plus'), title='Create Asset Type',
                parent=parent)

        _type_dir.mkdir()

    def find_asset_types(self):
        """Find asset types inside this job.

        Returns:
            (str list): asset types
        """
        from pini import pipe
        _LOGGER.debug('FIND ASSET TYPES %s', self.name)

        # Find assets
        if pipe.MASTER == 'disk':
            _tmpl = self.find_template(
                'entity_path', profile='asset', catch=True)
            _LOGGER.debug(' - TMPL (A) %s', _tmpl)
            if not _tmpl:
                return []
            _tmpl = _tmpl.apply_data(job_path=self.path)
            _types = _tmpl.glob_token('asset_type')
        elif pipe.MASTER == 'shotgrid':
            _types = sorted({
                _asset.asset_type for _asset in self._read_assets_sg()})
        else:
            raise ValueError(pipe.MASTER)
        _LOGGER.debug(' - TYPES %s', _types)

        # Apply filter
        _filter = self.cfg['tokens']['asset_type']['filter']
        if _filter:
            _LOGGER.debug(' - FILTER %s', _filter)
            _types = apply_filter(_types, _filter)
            _LOGGER.debug(' - TYPES %s', _types)

        return _types

    def find_asset(self, match, asset_type=None, catch=False):
        """Find an asset in this job.

        Args:
            match (str): match by name or label (eg. char.robot)
            asset_type (str): filter by asset type
            catch (bool): no error if asset not found

        Returns:
            (CPAsset): matching asset
        """
        _LOGGER.debug('FIND ASSET %s', match)
        _assets = self.find_assets(asset_type=asset_type)
        _LOGGER.debug(' - FOUND %d ASSETS', len(_assets))

        # Match by name
        _name_assets = [_asset for _asset in _assets if _asset.name == match]
        _LOGGER.debug(' - NAME ASSETS %s', len(_name_assets))
        if len(_name_assets) == 1:
            return single(_name_assets)

        # Match by label
        for _asset in _assets:
            _label = '{}.{}'.format(_asset.asset_type, _asset.name)
            _LOGGER.debug(' - TESTING %s', _label)
            if _label == match:
                return _asset

        if catch:
            return None
        raise ValueError(match)

    def find_assets(self, asset_type=None, filter_=None):
        """Find assets in this job.

        Args:
            asset_type (str): filter by type
            filter_ (str): apply path filter

        Returns:
            (CPAsset list): matching assets
        """
        from pini import pipe

        _LOGGER.debug('FIND ASSETS')

        if pipe.MASTER == 'disk':

            _assets = []

            if not self.uses_asset_type_dirs:  # Assets in shared dir

                # Crop template to get assets dir
                _LOGGER.debug(' - FINDING ASSET TEMPLATE')
                _tmpl = self.find_template('entity_path', profile='asset')
                _tmpl = _tmpl.apply_data(job_path=self.path)
                _tmpl = _tmpl.crop_to_token('asset', include_token_dir=False)

                # Search for assets
                _LOGGER.debug(' - SEARCHING FOR ASSETS')
                for _path in Dir(_tmpl.pattern).find(
                        depth=1, type_='d', catch_missing=True):
                    try:
                        _asset = pipe.CPAsset(_path, job=self)
                    except ValueError:
                        continue
                    if asset_type and _asset.type_ != asset_type:
                        continue
                    _assets.append(_asset)

            else:

                # Search type dirs individually
                _types = [asset_type] if asset_type else self.find_asset_types()
                _LOGGER.debug(' - TYPES %s', _types)
                for _type in _types:
                    _assets += self.read_type_assets(asset_type=_type)

        elif pipe.MASTER == 'shotgrid':
            _assets = []
            for _asset in self._read_assets_sg():
                if asset_type and _asset.type_ != asset_type:
                    continue
                if filter_ and not passes_filter(_asset.path, filter_):
                    continue
                _assets.append(_asset)

        else:
            raise ValueError

        _LOGGER.debug(' - FOUND %d ASSETS', len(_assets))

        return _assets

    def _read_assets_disk_natd(self, class_=None):
        """Read assets from disk (no asset type dirs).

        NOTE: only applicable to jobs with don't use asset type dirs.

        Args:
            class_ (class): override asset class

        Returns:
            (CPAsset list): assets
        """
        _LOGGER.debug('READ ASSETS')
        from pini import pipe
        _start = time.time()
        assert not self.uses_asset_type_dirs
        _class = class_ or pipe.CPAsset

        # Get template
        _tmpl = self.find_template('entity_path', profile='asset')
        _tmpl = _tmpl.apply_data(job_path=self.path)
        _LOGGER.debug(' - TMPL %s', _tmpl)

        _assets = []
        for _path in _tmpl.glob_paths(job=self):
            _asset = _class(_path, job=self)
            _assets.append(_asset)
        _dur = time.time() - _start
        _LOGGER.info('FOUND %d %s ASSETS IN %.00fs', len(_assets),
                     self.name, _dur)

        return _assets

    def _read_assets_sg(self, class_=None):
        """Read assets from shotgrid.

        Args:
            class_ (class): override asset class

        Returns:
            (CPAsset list): assets
        """
        from pini import pipe
        from pini.pipe import shotgrid
        _sg_assets = shotgrid.SGC.find_assets(job=self)
        _class = class_ or pipe.CPAsset
        _assets = [_class(_sg_asset.path, job=self) for _sg_asset in _sg_assets]
        return _assets

    def find_sequence(self, match=None):
        """Find a sequence in this job.

        Args:
            match (str): match by name

        Returns:
            (CPSequence): matching sequence
        """
        _seqs = self.find_sequences()

        if not match:
            return single(_seqs)

        # Try exact name match
        _name_seqs = [_seq for _seq in _seqs if _seq.name == match]
        if len(_name_seqs) == 1:
            return single(_name_seqs)

        # Try filter match
        _filter_seqs = apply_filter(
            _seqs, match, key=operator.attrgetter('name'))
        if len(_filter_seqs) == 1:
            return single(_filter_seqs)

        raise ValueError(match)

    def find_sequences(self, class_=None, filter_=None, head=None):
        """Find sequences in this job.

        Args:
            class_ (class): override sequence class
            filter_ (str): filter by sequence name
            head (str): filter by sequence name prefix

        Returns:
            (str|CPSequence list): sequences
        """
        from pini import pipe

        _LOGGER.debug('FIND SEQUENCES')

        # Find sequences as strs from shots
        if not self.uses_sequence_dirs:
            _shots = self.find_shots()
            _seqs = sorted({_shot.sequence for _shot in _shots})
            _filter_key = None

        # Find sequences as CPSequence dir objects
        else:

            _LOGGER.debug(' - SEQUENCES AS DIRS')

            _class = class_ or pipe.CPSequence
            _filter = self.cfg['tokens']['sequence']['filter']
            _LOGGER.debug(' - FILTER %s', _filter)

            # Set up template
            _tmpl = self.find_template('entity_path', profile='shot')
            _tmpl = _tmpl.crop_to_token('sequence')
            _tmpl = _tmpl.apply_data(job_path=self.path)
            _LOGGER.debug(' - TMPL %s', _tmpl)
            assert len(_tmpl.keys()) == 1
            assert single(_tmpl.keys()) == 'sequence'

            # Find paths
            if pipe.MASTER == 'disk':
                _paths = _tmpl.glob_paths(job=self)
            elif pipe.MASTER == 'shotgrid':
                _paths = sorted({
                    pipe.CPSequence(_shot, job=self)
                    for _shot in self.read_shots_sg()})
                _LOGGER.debug(' - SEQ PATHS %s', _paths)
            else:
                raise ValueError(pipe.MASTER)

            # Build sequence objects
            _seqs = []
            for _path in _paths:
                try:
                    _seq = _class(_path, job=self)
                except ValueError:
                    _LOGGER.debug('   - INVALID SEQ %s', _path)
                    continue
                _seqs.append(_seq)
            _filter_key = operator.attrgetter('filename')

        if filter_:
            _seqs = apply_filter(_seqs, filter_, key=_filter_key)
        if head:
            _seqs = [_seq for _seq in _seqs
                     if _filter_key(_seq).startswith(head)]

        return _seqs

    def find_shot(self, match, sequence=None, catch=False):
        """Find shot within this job.

        Args:
            match (str): match by shot name
            sequence (str): filter by sequence
            catch (bool): no error if shot not found

        Returns:
            (CPShot): matching shot
        """
        _match = norm_path(match)
        _LOGGER.debug('FIND SHOT %s %s', match, _match)
        _shots = self.find_shots(sequence=sequence)
        _LOGGER.debug(' - FOUND %d SHOTS', len(_shots))

        # Test name match
        _name_shot = single([
            _shot for _shot in _shots if _shot.name == _match], catch=True)
        if _name_shot:
            return _name_shot

        # Test path match
        _path_shot = single([
            _shot for _shot in _shots
            if _match.startswith(_shot.path)], catch=True)
        if _path_shot:
            return _path_shot

        # Test sequence match
        _seq_match = single([
            _shot for _shot in _shots if _shot.sequence == _match], catch=True)
        if _seq_match:
            return _seq_match

        if catch:
            return None
        raise ValueError('Failed to find shot '+match)

    def find_shots(self, sequence=None, class_=None, filter_=None):
        """Find shots in this job.

        Args:
            sequence (str): filter by sequence
            class_ (class): override shot class
            filter_ (str): filter by shot name

        Returns:
            (CPShot list): matching shots
        """
        _LOGGER.debug('FIND SHOTS %s class=%s filter=%s', self, class_, filter_)
        from pini import pipe

        # No sequence dirs - find shots at job level
        if not self.uses_sequence_dirs:
            _shots = self._read_shots_disk(class_=class_)
            if sequence:
                _shots = [_shot for _shot in _shots
                          if _shot.sequence == sequence]
            if filter_:
                _shots = apply_filter(
                    _shots, filter_, key=operator.attrgetter('name'))

        # Find shots in sequence dirs
        else:

            # Get sequence dirs to search
            if isinstance(sequence, pipe.CPSequence):
                _seqs = [sequence]
            elif isinstance(sequence, six.string_types):
                _seq = self.find_sequence(sequence)
                _seqs = [_seq] if _seq else []
            elif sequence is None:
                _seqs = self.find_sequences()
            else:
                raise ValueError(sequence)
            _LOGGER.debug(' - SEQS %s', _seqs)

            # Read shots from seqs
            _shots = []
            for _seq in _seqs:
                _seq_shots = _seq.find_shots(class_=class_, filter_=filter_)
                _LOGGER.debug(
                    ' - ADDING SEQ SHOTS %s %s %s', id(_seq), _seq.name,
                    [_shot.name for _shot in _seq_shots])
                _shots += _seq_shots

        return _shots

    def _read_shots_disk(self, class_=None):
        """Read shots from disk.

        (Only applicable to jobs which don't use sequence dirs)

        Args:
            class_ (class): override shot class

        Returns:
            (CPShot list): shots
        """
        from pini import pipe
        _LOGGER.debug('READ SHOTS %s', self)
        assert not self.uses_sequence_dirs

        _class = class_ or pipe.CPShot
        _LOGGER.debug(' - CLASS %s', _class)

        # Set up template
        _tmpl = self.find_template('entity_path', profile='shot')
        _tmpl = _tmpl.apply_data(job_path=self.path)
        _LOGGER.debug(' - TMPL %s', _tmpl)

        # Find shots
        _shots = []
        for _path in _tmpl.glob_paths(job=self):
            _shot = _class(_path)
            _shots.append(_shot)
        _LOGGER.debug(' - FOUND %d SHOTS %s', len(_shots), _shots)

        return _shots

    def read_shots_sg(self, class_=None):
        """Read shots from shotgrid.

        Args:
            class_ (class): override shot class

        Returns:
            (CPShot list): shots
        """
        from pini import pipe
        from pini.pipe import shotgrid
        _LOGGER.debug('READ SHOTS SG')
        _class = class_ or pipe.CPShot
        _has_3d = True if self.settings['shotgrid']['only_3d'] else None
        _sg_shots = shotgrid.SGC.find_shots(job=self, has_3d=_has_3d)
        _sg_shots = [
            _sg_shot for _sg_shot in _sg_shots
            if _sg_shot.status not in ('omt', )]
        _shots = [_class(_sg_shot.path, job=self) for _sg_shot in _sg_shots]
        _LOGGER.debug(' - MAPPED %d SHOTS', len(_shots))
        assert len(_sg_shots) == len(_shots)
        return _shots

    def read_type_assets(self, asset_type, class_=None):
        """Read assets of the given type from this job.

        Args:
            asset_type (str): type to read (eg. char/veh)
            class_ (class): override asset class

        Returns:
            (CPAsset list): assets of given type
        """
        from pini import pipe
        _LOGGER.debug('READ TYPE ASSETS %s', asset_type)

        _class = class_ or pipe.CPAsset
        if not self.uses_asset_type_dirs:
            _LOGGER.debug(' - NO ASSET TYPE DIRS')
            return [_asset for _asset in self._read_assets_disk_natd()
                    if _asset.type_ == asset_type]

        # Setup up template
        _tmpl = self.find_template('entity_path', profile='asset')
        _tmpl = _tmpl.apply_data(job_path=self.path, asset_type=asset_type)

        # Get asset paths
        if pipe.MASTER == 'disk':
            _paths = pipe.glob_template(template=_tmpl, job=self)
        elif pipe.MASTER == 'shotgrid':
            _paths = [_asset for _asset in self._read_assets_sg()
                      if _asset.asset_type == asset_type]
        else:
            raise ValueError(pipe.MASTER)

        # Cast to asset objects
        _assets = []
        for _path in _paths:
            try:
                _asset = _class(_path, job=self)
            except ValueError:
                continue
            _assets.append(_asset)

        return _assets

    def find_entity(self, match):
        """Find entity in this job.

        Args:
            match (str): match by label (eg. mercury/rnd010)

        Returns:
            (CPEntity): matching entity
        """
        from pini import pipe

        if isinstance(match, six.string_types):
            if '.' in match:
                return self.find_asset(match)
            return self.find_shot(match)

        if isinstance(match, (pipe.CPAsset, pipe.CPShot)):
            return single(
                _ety for _ety in self.find_entities() if _ety == match)

        raise NotImplementedError(match)

    def find_entities(self, entity_type=None, filter_=None):
        """Find entities in this job.

        Args:
            entity_type (str): filter by entity type (ie. asset type
                or sequence name)
            filter_ (str): apply path filter

        Returns:
            (CPEntity list): entities (shots + assets)
        """
        _etys = self.find_assets() + self.find_shots()
        if entity_type:
            _etys = [_ety for _ety in _etys
                     if _ety.entity_type == entity_type]
        if filter_:
            _etys = apply_filter(
                _etys, filter_, key=operator.attrgetter('path'))
        return _etys

    def find_publish(
            self, asset=None, extn=EMPTY, tag=EMPTY, task=None,
            ver_n='latest', versionless=None):
        """Find publish within this job.

        Args:
            asset (str): filter by asset name (eg. deadHorse)
            extn (str): filter by extension
            tag (str): filter by tag
            task (str): filter by task (eg. rig)
            ver_n (str): filter by version number (default is latest)
            versionless (bool): filter by versionless status

        Returns:
            (CPOutput): publish
        """
        _pubs = self.find_publishes(
            asset=asset, task=task, ver_n=ver_n, tag=tag, extn=extn,
            versionless=versionless)
        return single(_pubs, items_label='publishes', verbose=1)

    def find_publishes(
            self, task=None, entity=None, asset=None, asset_type=None,
            output_name=None, tag=EMPTY, ver_n=EMPTY, versionless=None,
            extn=EMPTY, extns=None):
        """Find asset publishes within this job.

        Args:
            task (str): filter by task
            entity (CPEntity): filter by entity
            asset (str): filter by asset name (eg. deadHorse)
            asset_type (str): filter by asset type name (eg. char)
            output_name (str): filter by output name
            tag (str): filter by tag
            ver_n (int): filter by version number
            versionless (bool): filter by versionless status
            extn (str): filter by publish extension
            extns (str list): filter by publish extensions

        Returns:
            (CPOutput list): publishes
        """
        _LOGGER.debug('FIND PUBLISHES')

        from pini import pipe
        from pini.pipe import cp_entity

        assert asset is None or isinstance(asset, six.string_types)
        assert entity is None or isinstance(entity, cp_entity.CPEntity)

        # Search publishes
        if pipe.MASTER == 'disk':
            _start = time.time()
            _pubs = []
            for _asset in self.find_assets(asset_type=asset_type):
                if asset and _asset.name != asset:
                    continue
                if entity and _asset != entity:
                    continue
                _pubs += _asset.find_publishes(
                    ver_n=ver_n, task=task, output_name=output_name, extn=extn,
                    extns=extns, tag=tag, versionless=versionless)
            _LOGGER.debug('FOUND %s %d PUBLISHES IN %.01fs', self, len(_pubs),
                          time.time() - _start)
        elif pipe.MASTER == 'shotgrid':
            assert not asset
            assert not asset_type
            assert not output_name
            assert not versionless
            assert extn is EMPTY
            _pubs = []
            for _type in ['publish', 'publish_seq']:
                _pubs += self.find_outputs(
                    type_=_type, entity=entity, task=task, tag=tag, ver_n=ver_n,
                    extns=extns, profile='asset')
            _pubs.sort()
        else:
            raise ValueError(pipe.MASTER)

        return _pubs

    def find_outputs(
            self, type_=None, filter_=None, profile=None, entity=None,
            step=None, task=None, tag=EMPTY, ver_n=None, extns=None,
            progress=False):
        """Find outputs in this job.

        (Only applicable to shotgrid jobs)

        Args:
            type_ (str): filter by output type
            filter_ (str): apply path filter
            profile (str): filter by entity profile (asset/shot)
            entity (CPEntity): filter by entity
            step (str): apply step filter
            task (str): filter by task
            tag (str): filter by tag
            ver_n (int): filter by version number
            extns (str list): filter by output extensions
            progress (bool): show progress

        Returns:
            (CPOutput list): outputs
        """
        from pini import pipe
        _LOGGER.debug('FIND OUTPUTS %s', self)

        if not (entity is None or isinstance(entity, pipe.ENTITY_TYPES)):
            raise TypeError(entity)

        _all_outs = self._read_outputs_sg(progress=progress)
        _all_outs, _ver_n = self._apply_latest_output_version_filter(
            ver_n=ver_n, outputs=_all_outs)

        _outs = []
        for _out in _all_outs:
            _LOGGER.debug(' - TESTING %s', _out)
            if filter_ and not passes_filter(_out.path, filter_):
                continue
            if type_ and _out.type_ != type_:
                continue
            if step and _out.step != step:
                continue
            if task and task not in (_out.task, _out.pini_task):
                continue
            if tag is not EMPTY and _out.tag != tag:
                continue
            if _ver_n and _out.ver_n != _ver_n:
                continue
            if profile and _out.entity.profile != profile:
                continue
            if entity and _out.entity != entity:
                _LOGGER.debug('   - REJECT ENTITY %s %s', _out.entity, entity)
                continue
            if extns and _out.extn not in extns:
                continue
            _outs.append(_out)

        _LOGGER.debug(' - FOUND %d OUTPUTS', len(_outs))
        return _outs

    def _apply_latest_output_version_filter(self, outputs, ver_n):
        """Apply "latest" version filter.

        If the ver_n filter is "latest" then remove all non-latest
        versions from the list.

        Args:
            outputs (CPOutput list): outputs
            ver_n (int|str|None): version filter

        Returns:
            (tuple): outputs list, updated version filter
        """
        _outs = outputs
        _ver_n = ver_n
        if _ver_n == 'latest':
            _ver_n = None
            _n_outs = len(_outs)
            _outs = sorted({
                _to_out_stream_uid(_out): _out
                for _out in _outs}.values())
            _LOGGER.debug(
                ' - APPLY LATEST %d -> %d OUTS', _n_outs, len(_outs))
        else:
            assert _ver_n in (None, EMPTY) or isinstance(_ver_n, int)

        return _outs, _ver_n

    def _read_outputs_sg(self, progress=False):
        """Read outputs in this job from shotgrid.

        Args:
            progress (bool): show progress

        Returns:
            (CPOutput list): outputs
        """
        raise NotImplementedError("Use cache")

    def to_prefix(self):
        """Obtain prefix for this job.

        Returns:
            (str): job prefix
        """
        from .. import pipe
        if pipe.MASTER != 'shotgrid':
            raise NotImplementedError
        from pini.pipe import shotgrid
        return shotgrid.to_job_data(self)['sg_short_name']

    def to_asset(self, asset_type, asset, class_=None, catch=True):
        """Build an asset object for an asset within this job.

        Args:
            asset_type (str): asset type (eg. char/veh)
            asset (str): asset name (eg. deadHorse)
            class_ (class): override asset class
            catch (bool): no error if fail to build valid asset

        Returns:
            (CPAsset): asset object
        """
        from pini import pipe

        # Obtain template
        _tmpl = self.find_template('entity_path', profile='asset', catch=True)
        if not _tmpl:
            if catch:
                return None
            raise ValueError('No matching template')

        # Build asset
        _path = _tmpl.format(dict(  # pylint: disable=use-dict-literal
            job_path=self.path, asset_type=asset_type, asset=asset))
        _class = class_ or pipe.CPAsset
        try:
            return _class(_path, job=self)
        except ValueError as _exc:
            if not catch:
                raise _exc
            return None

    def to_sequence(self, sequence, class_=None, catch=False):
        """Build a sequence object for this job.

        Args:
            sequence (CPSequence): sequence name
            class_ (class): override sequence class
            catch (bool): no error if no valid sequence created

        Returns:
            (CPSequence): sequence
        """
        from pini import pipe
        if not self.uses_sequence_dirs:
            return sequence

        _LOGGER.debug('TO SEQUENCE')
        _class = class_ or pipe.CPSequence

        # Obtain template
        _tmpl = self.find_template('entity_path', profile='shot', catch=True)
        if not _tmpl:
            if catch:
                return None
            raise ValueError
        _tmpl = _tmpl.crop_to_token('sequence')
        _LOGGER.debug(' - TMPL %s', _tmpl)

        # Build path
        _path = _tmpl.format(job_path=self.path, sequence=sequence)
        _LOGGER.debug(' - PATH %s', _path)

        # Build sequence object
        try:
            _result = _class(_path, job=self)
        except ValueError:
            _result = None
        _LOGGER.debug(' - RESULT %s', _result)

        return _result

    def to_shot(self, shot, sequence=None, class_=None):
        """Build a shot object based on the given args.

        Args:
            shot (str): shot name
            sequence (str): sequence
            class_ (class): override shot type

        Returns:
            (CPShot): shot object
        """
        _LOGGER.debug('TO SHOT %s %s', self, shot)
        from pini import pipe

        _tmpl = self.find_template('entity_path', profile='shot')

        # Set up sequence
        _seq = sequence
        if isinstance(sequence, pipe.CPSequence):
            _seq = _seq.name
        if not _seq and 'sequence' in _tmpl.keys():
            raise ValueError('Missing sequence key')

        # Apply data to template
        _path = _tmpl.format(
            job_path=self.path, sequence=_seq, shot=shot)
        _class = class_ or pipe.CPShot
        try:
            return _class(_path, job=self)
        except ValueError as _exc:
            _LOGGER.debug(' - EXC %s', _exc)
            return None

    def to_empty_file(self, dcc_=None):
        """Obtain an empty file for this job.

        This is a template file which is loaded on new scene creation.

        Args:
            dcc_ (str): empty file dcc

        Returns:
            (File): empty file path
        """
        _dcc = dcc_ or dcc.NAME
        if _dcc == dcc.NAME:
            _extn = dcc.DEFAULT_EXTN
        else:
            _extn = {'nuke': 'nk', 'maya': 'ma'}[_dcc]

        _tmpl = self.find_template('empty_file', catch=True, dcc_=_dcc)
        if not _tmpl:
            _LOGGER.info('NO EMPTY FILE TEMPLATE FOUND IN CFG')
            return None

        _file = File(_tmpl.format(dict(  # pylint: disable=use-dict-literal
            job_path=self.path, dcc=_dcc, extn=_extn)))
        if not _file.exists():
            _LOGGER.info('EMPTY FILE IS MISSING %s', _file.path)
            return None
        _LOGGER.info('FOUND EMPTY FILE %s', _file.path)
        return _file

    def __lt__(self, other):
        return self.name.lower() < other.name.lower()


def cur_job(class_=None, jobs_root=None):
    """Build a job object for the current job.

    Args:
        class_ (class): override job class
        jobs_root (str): override jobs root

    Returns:
        (CPJob): current job
    """
    _class = class_ or CPJob
    try:
        return _class(dcc.cur_file(), jobs_root=jobs_root)
    except ValueError:
        return None


def obtain_job(match):
    """Factory to obtain job object.

    Once the first instance of a job is created, this object is
    always returned.

    Args:
        match (str): name of job to obtain object for

    Returns:
        (CPJob): job object
    """
    _LOGGER.debug('OBT JOB %s', match)
    _job = _JOB_MATCHES.get(match)
    if not _job:
        _job = find_job(match)
        _JOB_MATCHES[match] = _job
    return _job


def find_job(match=None, filter_=None, catch=False, class_=None):
    """Find a job.

    Args:
        match (str): name to match
        filter_ (str): apply filter to jobs list
        catch (bool): no error of exactly one job isn't found
        class_ (class): override job class

    Returns:
        (CPJob): matching job (if any)
    """
    _LOGGER.debug('FIND JOB %s', match)
    _jobs = find_jobs(class_=class_, filter_=filter_)

    # Try single job
    _job = single(_jobs, catch=True)
    if _job:
        return _job

    # Try name match
    _match_job = single(
        [_job for _job in _jobs if _job.name == match], catch=True)
    if _match_job:
        return _match_job

    # Try filter match
    _filter_jobs = apply_filter(_jobs, match, key=operator.attrgetter('name'))
    _LOGGER.debug(' - FILTER JOBS %d %s', len(_filter_jobs), _filter_jobs)
    if len(_filter_jobs) == 1:
        return single(_filter_jobs)

    if catch:
        return None
    raise ValueError(match)


def find_jobs(filter_=None, class_=None, cfg_name=None, jobs_root=None):
    """Find jobs in the current pipeline.

    Args:
        filter_ (str): apply filter to jobs list
        class_ (class): override job class
        cfg_name (str): filter by config name
        jobs_root (str): override jobs root

    Returns:
        (CPJob list): matching jobs
    """
    from pini import pipe

    _class = class_ or CPJob
    _root = Dir(jobs_root or JOBS_ROOT)
    _LOGGER.debug('FIND JOBS %s %s exists=%d', _class, _root.path,
                  _root.exists())

    # Find dirs
    if pipe.MASTER == 'disk':
        _dirs = _root.find(depth=1, type_='d', catch_missing=True)
    elif pipe.MASTER == 'shotgrid':
        from pini.pipe import shotgrid
        _dirs = [_job.path for _job in shotgrid.SGC.jobs]
    else:
        raise ValueError(pipe.MASTER)

    # Convert to job objects
    _jobs = []
    for _dir in _dirs:
        _LOGGER.debug(' - TESTING DIR %s', _dir)
        _job = _class(_dir, jobs_root=_root)
        if _job.name not in _JOB_MATCHES:
            _JOB_MATCHES[_job.name] = _job
        if not passes_filter(_job.name, filter_):
            continue
        if cfg_name and (
                not _job.cfg_file.exists(catch=True) or
                _job.cfg['name'] != cfg_name):
            continue
        _jobs.append(_job)

    return _jobs


def set_jobs_root(path):
    """Update jobs root path.

    Args:
        path (str): path to set as jobs root
    """
    from pini import pipe
    global JOBS_ROOT
    _path = abs_path(path)
    _LOGGER.info('SET JOBS ROOT %s', _path)
    os.environ['PINI_JOBS_ROOT'] = _path
    JOBS_ROOT = Dir(_path)
    pipe.JOBS_ROOT = JOBS_ROOT
    pipe.CACHE.reset()


def to_job(name, catch=False):
    """Build a job object with the given name.

    Args:
        name (str): job name
        catch (bool): no error if no matching job found

    Returns:
        (CPJob): job
    """
    _LOGGER.debug('TO JOB %s', name)

    # Determine path
    _name = to_str(name)
    if '/' not in _name:
        _path = JOBS_ROOT.to_subdir(_name)
    else:
        _path = _name
    _LOGGER.debug(' - PATH %s', _path)

    # Build job
    try:
        _job = CPJob(_path)
    except ValueError as _exc:
        if not catch:
            raise _exc
        _job = None
    _LOGGER.debug(' - JOB %s', _job)

    return _job


def _to_out_stream_uid(output):
    """Build a hashable uid for the given output's version stream.

    ie. build an uid that identifies all versions of an output stream.

    This could be achieved by using CPOutput.to_work(ver_n=0) but that is
    slow. Instead, the data dict with the version key removed is converted
    to a tuple.

    Args:
        output (CPOutput): output to read

    Returns:
        (tuple): uid
    """
    _data = copy.copy(output.data)
    _data.pop('ver')
    return tuple(_data.items())
