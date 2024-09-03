"""Tools for managing lucidity templates."""

# pylint: disable=too-many-instance-attributes

import collections
import logging
import time

import lucidity

from pini import dcc
from pini.utils import six_cmp, File, norm_path, Dir, is_abs, single

from .cp_utils import (
    is_valid_token, are_valid_tokens, validate_tokens,
    expand_pattern_variations)

_LOGGER = logging.getLogger(__name__)


class CPTemplate(lucidity.Template):
    """Adds pini-specific functionality to the basic template class."""

    task = None

    def __init__(
            self, name, pattern, anchor=lucidity.Template.ANCHOR_END,
            separate_dir=False, path_type=None, job=None, alt=None,
            source=None):
        """Constructor.

        For a dcc template override the dcc needs to be at the front of the
        name. A profile override can then follow, but they must be in that
        order, eg:

            maya_shot_render
            maya_render
            shot_render

        Args:
            name (str): template name
            pattern (str): template pattern
            anchor (Enum): anchor type
            separate_dir (bool): check dir first and then filename - this
                allows more complex paths to be parsed successfully
                (eg. abc files with many tokens)
            path_type (str): specify path type (d for dir, f for file)
            job (CPJob): template job (used to validate tokens)
            alt (int): this is used to prioritise different versions of the
                same templates type - eg. if cache and cache_alt1 templates
                are declared, the basic pattern (alt will be zero) will be
                used for caching, but the alt1 pattern will still be valid
                and appear in output lists
            source (CPTemplate): original source of this template (if any)
        """
        self._separate_dir = separate_dir

        _pattern = pattern
        super().__init__(
            name, _pattern, anchor,
            default_placeholder_expression=r'[\w_. \-]+')

        self.profile = None
        self.path_type = path_type
        self.anchor = anchor
        self.job = job
        self.alt = alt
        self.source = source or self

        # Read dcc override
        _tokens = self.name.split('_')
        _dcc = set(dcc.DCCS)
        self._dcc = None
        if _tokens[0] in _dcc:
            self._dcc = _tokens.pop(0)
        assert not _dcc & set(_tokens)

        # Set profile
        _profiles = {'asset', 'shot'}
        if _tokens[0] in _profiles:
            self.profile = _tokens.pop(0)
        assert not _profiles & set(_tokens)
        assert self.profile in ['asset', 'shot', None]

        self.type_ = '_'.join(_tokens)
        self.embedded_data = {}

        # Apply sort key, dcc templates appear first, then profile specific
        # ones, then the longest pattern should dominate
        self.cmp_str = '{:d}_{:d}_{:05d}_{}'.format(
            not bool(self.dcc), not bool(self.profile),
            10000-len(self.pattern), self.type_)

    @property
    def dcc(self):
        """Obtain dcc for this work dir.

        This can be defined in the template or as a tag, or not at all.

        Returns:
            (str): dcc name
        """
        if self._dcc:
            return self._dcc
        return self.embedded_data.get('dcc')

    def apply_data(self, **kwargs):
        """Apply data to this template.

        This generates a new template with known data applied, which can be
        useful if some data is already known - eg. if we know entity and
        task then it can make it easier for lucidity to extract the remaining
        data from a path if we apply that data to the template.

        Returns:
            (CPTemplate): updated template
        """
        _pattern = self.pattern
        _updated = {}
        for _name, _val in kwargs.items():

            if not _val:
                continue
            if _name not in self.keys():
                continue

            # Update pattern
            _token_s = '{{{}}}'.format(_name)  # Basic pattern
            if _token_s not in _pattern:  # Pattern contains regex
                _start = _pattern.find(_token_s[:-1]+':')
                _end = _pattern.find('}', _start)+1
                _token_s = _pattern[_start: _end]
            _pattern = _pattern.replace(_token_s,  _val)

            _updated[_name] = _val

        _tmpl = self.duplicate(pattern=_pattern)
        _tmpl.embedded_data.update(_updated)
        return _tmpl

    def crop_to_token(self, token, include_token_dir=True, name=None):
        """Crop this template to the given token.

        eg. {A}/{B}/{C} cropped to B would return {A}/{B}

        Args:
            token (str): token to crop to
            include_token_dir (bool): include the token dir
            name (str): update template name

        Returns:
            (CPTemplate): cropped template
        """
        if token not in self.keys():
            raise RuntimeError(
                f'Token "{token}" not in template "{self.pattern}"')
        _LOGGER.log(9, 'CROP TO TOKEN %s', self)
        _type_dir = [_token for _token in self.pattern.split('/')
                     if '{{{}}}'.format(token) in _token][0]
        _LOGGER.log(9, ' - TYPE DIR %s', _type_dir)
        _root, _ = self.pattern.split(_type_dir, 1)
        if include_token_dir:
            _pattern = norm_path(_root)+'/'+_type_dir
        else:
            _pattern = norm_path(_root)
        return self.duplicate(pattern=_pattern, name=name)

    def duplicate(self, name=None, pattern=None, separate_dir=None):
        """Duplicate this template.

        Embedded data and anchor are maintained.

        Args:
            name (str): update name
            pattern (str): update pattern
            separate_dir (bool): update separate_dir setting

        Returns:
            (CPTemplate): duplicate
        """
        _separate_dir = (
            self._separate_dir if separate_dir is None else separate_dir)
        _tmpl = CPTemplate(
            name or self.name, pattern or self.pattern, anchor=self.anchor,
            separate_dir=_separate_dir, path_type=self.path_type,
            job=self.job, source=self.source)
        _tmpl.embedded_data.update(self.embedded_data)
        return _tmpl

    def format(self, *args, **kwargs):
        """Apply data to this template.

        By default this method accepts a dict, but it is overloaded here
        to allow data to be passed as kwargs.

        eg.

        >>> _tmpl = CPTemplate('test', '{a}/{b}')

        # This is default behaviour
        >>> _tmpl.format({'a": 'A', 'b': 'B'})
        'A/B'

        # This is added functionality
        >>> _tmpl.format(a='A', b='B')
        'A/B'

        Returns:
            (str): pattern string formatted with data provided
        """

        # Allow format with dict or kwargs
        if args:  # Default usage
            assert not kwargs
            assert len(args) == 1
            _data = single(args)
            assert isinstance(_data, dict)
        elif kwargs:  # Allow kwargs
            assert not args
            _data = kwargs
        else:
            _LOGGER.info('FORMAT FAIL args=%s kwargs%s', args, kwargs)
            raise ValueError('Format fail')

        _req_keys = set(self.keys())
        _data_keys = set(_data.keys())
        _missing_keys = _req_keys - _data_keys
        if _missing_keys:
            raise RuntimeError('Missing keys: {}'.format(
                ', '.join(sorted(_missing_keys))))

        return super().format(_data)

    def glob_token(self, token, job=None, type_='d'):
        """Search disks for valid values of the given token.

        The template is cropped to the given token, and then the remaining
        directory is searched for paths which given valid values of the
        token.

        Args:
            token (str): token to glob
            job (CPJob): job (to validate token values)
            type_ (str): type of path to search for (d/f)

        Returns:
            (str list): valid token values
        """
        _LOGGER.debug('GLOB TOKEN %s', token)
        _cropped_tmpl = self.crop_to_token(token)
        _dir, _pattern = _cropped_tmpl.pattern.rsplit('/', 1)

        # Check dir
        _dir = Dir(_dir)
        _LOGGER.debug(' - DIR %s', _dir)
        if not _dir.exists():
            _LOGGER.debug(' - DIR DOES NOT EXIST')
            return []
        _dir_tmpl = CPTemplate('dir', _pattern)
        _LOGGER.debug(' - DIR TMPL %s', _dir_tmpl)

        # Find possible vals
        _vals = set()
        for _filename in Dir(_dir).find(
                depth=1, type_=type_, full_path=False, catch_missing=True):
            _LOGGER.debug(' - CHECKING FILENAME %s', _filename)
            try:
                _val = _dir_tmpl.parse(_filename)[token]
            except lucidity.ParseError:
                continue
            if job and not is_valid_token(_val, token=token, job=job):
                continue
            _vals.add(_val)
        _vals = sorted(_vals)
        _LOGGER.debug(' - VALS %s', _vals)

        return _vals

    def glob_tokens(self, job, type_='d'):
        """Glob all tokens in this template.

        Find all valid instances of this template. Generally this
        requires the template to be hardened (ie. no tokens in the
        path) up until the final few directories.

        Args:
            job (CPJob): containing job (to validate tokens)
            type_ (str): type of path to glob (ie. f/d)

        Returns:
            (dict list): list of token instances
        """
        _LOGGER.debug('GLOB TOKENS %s', self)
        _dir, _tmpl = self.split_hardened()
        _LOGGER.debug(' - DIR %s', _dir)
        _depth = _tmpl.pattern.count('/') + 1
        _LOGGER.debug(' - TMPL %s depth=%d', _tmpl, _depth)
        if _depth > 3:
            raise NotImplementedError(self)
        _datas = []
        for _path in _dir.find(
                depth=_depth, type_=type_, full_path=False,
                catch_missing=True):
            if _path.count('/')+1 != _depth:
                continue
            _LOGGER.debug(' - CHECKING PATH %s', _path)

            # Apply template
            try:
                _data = _tmpl.parse(_path)
            except lucidity.ParseError:
                continue

            # Validate tokens
            _bad_tokens = [
                _token for _token, _val in _data.items()
                if not is_valid_token(value=_val, token=_token, job=job)]
            if _bad_tokens:
                continue

            _datas.append(_data)

        return _datas

    def glob_paths(self, job, type_='d'):
        """Glob paths matching this template.

        This will search a maxiumum of two directories deep for paths
        which match this template's pattern.

        Args:
            job (CPJob): current job (to validate tokens)
            type_ (str): path type (d/f)

        Returns:
            (str list): valid paths
        """
        _LOGGER.debug('GLOB PATHS')
        _LOGGER.debug(' - TMPL %s', self)
        _LOGGER.debug(' - JOB %s', job)

        _dir, _tmpl = self.split_hardened()

        _depth = _tmpl.pattern.count('/')+1
        assert _depth <= 2
        _paths = []
        for _rel_path in _dir.find(
                type_=type_, depth=_depth, full_path=False,
                catch_missing=True):

            # Apply template
            try:
                _data = _tmpl.parse(_rel_path)
            except lucidity.ParseError:
                continue

            # Validate tokens
            if not are_valid_tokens(data=_data, job=job):
                continue

            _path = '{}/{}'.format(_dir.path, _rel_path)
            _paths.append(_path)

        return _paths

    def is_abs(self):
        """Test whether this template's pattern is absolute.

        Returns:
            (bool): whether absolute
        """
        return is_abs(self.pattern)

    def is_resolved(self):
        """Test whether this template has been resolved.

        ie. all tokens have data applied

        Returns:
            (bool): whether any keys remain
        """
        return len(self.keys()) == 0

    def parse(self, path):
        """Wrapper for parse function.

        Maintains applied data so that this data is still returned in
        the parse result. Remaps data to check parse was successful.
        Also applies separate dir mode.

        Args:
            path (str): path to parse

        Returns:
            (dict): token/value data
        """
        _LOGGER.debug('PARSE %s', path)
        _path = path
        if self._separate_dir:
            _LOGGER.debug(' - SEPARATE DIR')
            return self._parse_dir_then_filename(_path)

        _LOGGER.debug(' - PATTERN %s', self.pattern)
        try:
            _data = super().parse(_path)
        except lucidity.ParseError as _exc:
            _LOGGER.log(9, ' - PARSE FAILED')
            raise _exc
        _LOGGER.debug(' - PARSED %s', _data)

        if self.job:
            try:
                validate_tokens(_data, job=self.job)
            except ValueError as _exc:
                raise lucidity.ParseError(_exc)

        _data.update(self.embedded_data)
        _LOGGER.debug(' - UPDATED DATA %s', _data)

        # Test remap data into path
        _remap_path = self.format(_data)
        _LOGGER.log(9, ' - REMAP PATH %s', _remap_path)
        if not _path.endswith(_remap_path):
            _LOGGER.log(9, ' - REMAP FAILED')
            raise lucidity.ParseError('Tokens failed to map back to path')
        _LOGGER.log(9, ' - ACCEPTED')

        return _data

    def _parse_dir_then_filename(self, path):
        """Parse directory and then filename.

        This implements the separate_dir feature.

        Args:
            path (str): path to parse

        Returns:
            (dict): token/value data
        """
        _LOGGER.log(9, ' - PARSE SEPARATE DIR %s', path)

        # Extract data from dir
        _dir = File(path).dir
        _dir_tmpl = self.duplicate(
            'tmp', File(self.pattern).dir, separate_dir=False)
        _LOGGER.log(9, ' - DIR TMPL %s %s', _dir_tmpl, _dir_tmpl.anchor)
        _data = _dir_tmpl.parse(_dir)

        _file = File(path).filename
        _file_tmpl = self.duplicate(
            'tmp', File(self.pattern).filename, separate_dir=False)
        _file_tmpl = _file_tmpl.apply_data(**_data)
        _file_data = _file_tmpl.parse(_file)

        _data.update(_file_data)

        return _data

    def split_hardened(self, name='tmp'):
        """Split this template into a hardened dir and the remaining template.

        eg:

        Template('C:/test/{token}') -> Dir('C:/test'), Template('{token}')
        Template('C:/A/{B}/{C}_{D}') -> Dir('C:/A'), Template('{B}/{C}_{D}')

        Args:
            name (str): override template name

        Returns:
            (Dir, CPTemplate): hardened dir, remaining template
        """
        _hard = []
        _tokens = self.pattern.split('/')
        while _tokens:
            if '{' in _tokens[0]:
                break
            _hard.append(_tokens.pop(0))
        _dir = Dir('/'.join(_hard))
        _tmpl = self.duplicate(name=name, pattern='/'.join(_tokens))
        return _dir, _tmpl

    def to_dir(self, name=None):
        """Move this template up one level, ie. find its directory.

        Args:
            name (str): override new template name

        Returns:
            (CPTemplate): parent template
        """
        return self.duplicate(
            pattern=File(self.pattern).to_dir().path, name=name)

    def __cmp__(self, other):
        return six_cmp(self.cmp_str, other.cmp_str)

    def __hash__(self):
        return hash(self.cmp_str)

    def __lt__(self, other):
        return self.cmp_str < other.cmp_str


def build_job_templates(job, catch=True):
    """Build templates data from config into Template objects.

    To handling optional tokens (not supported by lucidity), optional
    tokens are expanded to a list of all the possible options. For
    this reason, each template name had a list of template options to
    apply. In most cases this will just contain a single item.

    Args:
        job (CPJob): job to build templates for
        catch (bool): catch any errors and return an empty dict

    Returns:
        ({name: Template list} dict): template name/object data
    """
    _LOGGER.debug('BUILD TEMPLATES %s', job.name)
    _start = time.time()

    # Read templates from yaml
    try:
        _tmpls_cfg = job.cfg['templates']
    except KeyError:
        if not job.cfg_file.exists():
            if not catch:
                raise OSError('Missing config '+job.cfg_file.path)
            _LOGGER.warning('MISSING CONFIG FILE %s', job.cfg_file.path)
            return {}
        _LOGGER.info('CFG %s', job.cfg)
        raise RuntimeError('Bad config '+job.cfg_file.path)

    # Build configs into dict
    _tmpls = collections.defaultdict(list)
    for _name, _pattern in _tmpls_cfg.items():
        _LOGGER.debug(' - EXPANDING FMT %s', _pattern)
        _fmts = expand_pattern_variations(_pattern)
        for _pattern in _fmts:

            _LOGGER.debug('   - ADD PATTERN %s', _pattern)

            # Determine whether dir is to be separated + anchor type
            _anchor = lucidity.Template.ANCHOR_END
            _separate_dir = False
            if (
                    'render' in _name or
                    'plate' in _name or
                    # 'cache' in _name or
                    'mov' in _name):
                _anchor = lucidity.Template.ANCHOR_START
                _separate_dir = True
            elif 'cache' in _name:
                _separate_dir = True

            # Add regex to placeholders
            for _token, _data in job.cfg['tokens'].items():
                _regex = None
                if _data.get('nounderscore'):
                    _regex = '[^_]+'
                if _regex:
                    _find = '{{{}}}'.format(_token)
                    _replace = '{{{}:{}}}'.format(_token, _regex)
                    _pattern = _pattern.replace(_find, _replace)
                    _LOGGER.debug('   - FIND %s %s', _find, _replace)

            # Build template
            _name, _alt = _extract_alt_from_name(_name)
            _path_type = _to_path_type(name=_name, pattern=_pattern)
            _tmpl = CPTemplate(
                _name, pattern=_pattern, anchor=_anchor, job=job,
                separate_dir=_separate_dir, path_type=_path_type, alt=_alt)
            _tmpls[_name].append(_tmpl)

    _build_seq_dir_tmpls(_tmpls, job=job)
    _build_sequence_tmpl(_tmpls, job=job)
    if 'arnold' in dcc.allowed_renderers():
        _build_ass_gz_tmpls(_tmpls, job=job)
    _LOGGER.debug(' - BUILT %s TEMPLATES IN %.02fs', job.name,
                  time.time() - _start)

    return dict(_tmpls)


def _extract_alt_from_name(name):
    """Extract alt index from template name.

    If there is no alt suffix, the alt is set to zero.

    eg. blah -> blah, 0
        blah_alt1 -> blah, 1

    Args:
        name (str): template name to extract alt from

    Returns:
        (tuple): cleaned name, alt index
    """
    if '_' not in name:
        return name, 0
    _base, _alt_token = name.rsplit('_', 1)
    if not _alt_token.startswith('alt'):
        return name, 0
    _alt_digit = _alt_token[3:]
    if not _alt_digit.isdigit():
        return name, 0
    _alt_n = int(_alt_digit)
    return _base, _alt_n


def _build_seq_dir_tmpls(tmpls, job):
    """Add seq dir templates.

    These are used for caching on disk pipelines.

    Args:
        tmpls (dict): templates dict
        job (CPJob): parent job
    """
    from pini import pipe
    _seq_dirs = set()
    for _type in pipe.OUTPUT_SEQ_TYPES:
        for _tmpl in tmpls[_type]:
            _seq_dir = File(_tmpl.pattern).to_dir().path
            if _seq_dir in _seq_dirs:
                continue
            _seq_dirs.add(_seq_dir)
            _tmpl = CPTemplate(
                name='seq_dir', pattern=_seq_dir, path_type='d', job=job)
            tmpls['seq_dir'].append(_tmpl)


def _build_sequence_tmpl(tmpls, job):
    """Add sequence path template based on shot path.

    Args:
        tmpls (dict): templates dict
        job (CPJob): parent job
    """
    _shot_tmpl = single(tmpls['shot_entity_path'], catch=True)
    if _shot_tmpl and '{sequence}' in _shot_tmpl.pattern:
        _root, _ = _shot_tmpl.pattern.split('{sequence}')
        _seq_pattern = _root + '{sequence}'
        tmpls['sequence_path'] = [CPTemplate(
            'sequence_path', _seq_pattern, job=job, path_type='d',
            anchor=lucidity.Template.ANCHOR_END)]


def _build_ass_gz_tmpls(tmpls, job):
    """Add ass.gz templates based on cache template.

    These need to be added as a special case because ass.gz causes issues
    in lucidity parsing.

    Args:
        tmpls (dict): templates dict
        job (CPJob): parent job
    """
    _cache_names = [_name for _name in tmpls.keys() if 'cache' in _name]
    for _cache_name in _cache_names:
        _ass_gz_name = _cache_name.replace('cache', 'ass_gz')
        _LOGGER.debug('BUILD ASS GZ %s -> %s', _cache_name, _ass_gz_name)
        for _cache_tmpl in tmpls[_cache_name]:
            _LOGGER.debug(' - CACHE TMPL %s', _cache_tmpl)
            _ass_gz_tmpl = CPTemplate(
                name=_ass_gz_name, job=job, path_type='f',
                pattern=_cache_tmpl.pattern.replace('{extn}', 'ass.gz'))
            _LOGGER.debug(' - CACHE TMPL %s', _ass_gz_tmpl)
            tmpls[_ass_gz_name].append(_ass_gz_tmpl)


def _to_path_type(name, pattern=None):
    """Match a template name to a path type.

    Args:
        name (str): template name
        pattern (str): template pattern

    Returns:
        (chr): path type
            f - file
            d - dir
            s - sequence (ie. file sequence)
    """
    for _suffix, _type in [
            ('ass_gz', 'f'),
            ('blast', 's'),
            ('cache', 'f'),
            ('cache_seq', 's'),
            ('empty_file', 'f'),
            ('entity_path', 'd'),
            ('mov', 'f'),
            ('plate', 's'),
            ('publish', 'f'),
            ('render', 's'),
            ('shot_path', 'd'),
            ('work', 'f'),
            ('work_dir', 'd'),
    ]:
        if name.endswith(_suffix):
            return _type
    if pattern and pattern.endswith('.{extn}'):
        return 'f'
    raise ValueError(name)


def _separate_finalised_templates(templates, dir_):
    """Separate templates into finalised and subdir ones.

    This separates templates into subdir ones (which will needs an
    additional solve - ie. having at least one subdir) and ones which
    can be finalised in this dir (ie. they can be solved here).

    Args:
        templates (CPTemplates): templates to read
        dir_ (Dir): dir to test

    Returns:
        (list, list): subdir templates, final templates
    """
    _LOGGER.log(9, ' - SEP FINALISED TMPLS %s %s', dir_, templates)
    _subdir_tmpls = collections.defaultdict(set)
    _fin_tmpls = []

    for _tmpl in templates:
        assert _tmpl.is_abs()

        # Catch templates which map to outside this dir
        if not dir_.contains(_tmpl.pattern):
            _LOGGER.debug(
                ' - IGNORING TEMPLATE OUTSIDE DIR %s %s',
                _tmpl, dir_.path)
            continue

        _rel_path = dir_.rel_path(_tmpl.pattern)
        if '/' in _rel_path:
            _subdir, _ = _rel_path.split('/', 1)
            _subdir_tmpl = _tmpl.duplicate(pattern=_subdir, name='subdir')
            _subdir_tmpls[_subdir_tmpl].add(_tmpl)
        else:
            _fin_tmpls.append(_tmpl)

    _subdir_tmpls = dict(_subdir_tmpls)

    return _subdir_tmpls, _fin_tmpls


def _glob_rel_templates(templates, dir_, job):  # pylint: disable=too-many-branches,too-many-statements
    """Glob the given templates in the given directory.

    This allows directories to be searched for templates efficently, only
    search each directory once and then checked that the templates are
    valid at each stage before recursing into subdirectories.

    The templates should be solved up to the given dir, ie. their
    path should fall within it.

    Args:
        templates (CPTemplates): templates to glob
        dir_ (Dir): dir to glob
        job (CPJob): job to read config from

    Returns:
        (tuple list): list of valid template/path pairs
    """
    _LOGGER.debug('GLOB REL TEMPLATES %s %s', dir_.path, templates)

    _subdir_tmpls, _fin_tmpls = _separate_finalised_templates(templates, dir_)
    _LOGGER.debug(
        ' - SUBDIR TEMPLATES %d %s', len(_subdir_tmpls), _subdir_tmpls)
    _LOGGER.debug(
        ' - FINAL TEMPLATES %d %s', len(_fin_tmpls), _fin_tmpls)

    # Apply templates to this dir
    _results = []
    _sub_results = {}
    _dir_results = {}
    _paths = dir_.find(
        depth=1, class_=True, full_path=False, catch_missing=True,
        filter_='-~')
    _LOGGER.debug(' - FOUND %d PATHS %s', len(_paths), _paths)
    for _path in _paths:

        _abs_path = dir_.to_subdir(_path.path)
        _LOGGER.log(9, ' - CHECK PATH %s', _abs_path)

        # Check unfinished template roots and recurse into subdir
        if isinstance(_path, Dir):

            # Find templates to solve within this dir
            _tmpls = set()
            for _dir_tmpl, _child_tmpls in _subdir_tmpls.items():

                _LOGGER.log(
                    9, '   - TESTING SUBDIR %s %s', _dir_tmpl, _child_tmpls)

                # Check template
                _LOGGER.log(9, '   - CHECKING TEMPLATE')
                try:
                    _data = _dir_tmpl.parse(_path.path)
                except lucidity.ParseError:
                    _LOGGER.log(9, '     - PARSE FAILED %s', _path.path)
                    continue
                _LOGGER.log(9, '     - DATA %s', _data)
                try:
                    validate_tokens(_data, job=job)
                except ValueError:
                    _LOGGER.log(9, '     - VALIDATE TOKENS FAILED')
                    continue

                # Apply data from this dir to child templates and
                # add them to list of templates to apply in subdir
                _tmpls |= {_tmpl.apply_data(**_data) for
                           _tmpl in _child_tmpls}
                _LOGGER.log(9, '     - ACCEPTED %s', _tmpls)

            # Get results from this dir from matching templates
            if _tmpls:
                _results += _glob_rel_templates(
                    dir_=_abs_path, templates=sorted(_tmpls), job=job)

        # Check for finished templates
        for _fin_tmpl in _fin_tmpls:

            # Apply path type filter
            if not _fin_tmpl.path_type:
                pass
            elif _fin_tmpl.path_type == 'd':
                if not isinstance(_path, Dir):
                    continue
            elif _fin_tmpl.path_type == 'f':
                if not isinstance(_path, File):
                    continue
            else:
                raise ValueError(_fin_tmpl.path_type)

            if _path.extn:
                _fin_tmpl.apply_data(extn=_path.extn)
            try:
                _data = _fin_tmpl.parse(_abs_path.path)
            except lucidity.ParseError:
                continue
            try:
                validate_tokens(_data, job=job)
            except ValueError:
                continue
            _path = _path.to_abs(root=dir_)
            _result = _fin_tmpl, _path

            # In case of clash, favour results with fewer keys
            if _path in _dir_results:
                _cur_tmpl = _dir_results[_path][0]
                _tmpls = [_fin_tmpl, _cur_tmpl]
                _tmpls.sort(key=_get_tmpl_n_keys)
                _fin_tmpl = _tmpls[-1]
            _dir_results[_path] = _fin_tmpl, _path

    _LOGGER.debug(' - FOUND %d RESULTS', len(_dir_results))
    _results += _dir_results.values()

    return _results


def _get_tmpl_n_keys(template):
    """Count the number of keys in the given template.

    Args:
        template (CPTemplate): template to read

    Returns:
        (int): number of keys
    """
    return len(template.keys())


def glob_template(template, job):
    """Glob the given template.

    This applies the template to the file system and returns paths
    which satisfy it.

    Args:
        template (CPTemplate): template to glob
        job (CPJob): parent job (used to validate tokens)

    Returns:
        (Path list): matching paths
    """
    _tmpl_globs = glob_templates(templates=[template], job=job)
    _globs = [_path for _, _path in _tmpl_globs]
    return sorted(_globs)


def glob_templates(templates, job):
    """Glob the given templates.

    This searches for valid values of the given templates making sure
    to only search each directory one.

    Args:
        templates (CPTemplate list): templates to search for
        job (CPJob): templates job (to validate tokens)

    Returns:
        (tuple list): list of valid template/path pairs
    """
    _LOGGER.debug('GLOB TEMPLATES')

    # Sort into hardened roots
    _roots = collections.defaultdict(list)
    for _tmpl in templates:
        _root, _ = _tmpl.split_hardened(name=_tmpl.name)
        assert _root.is_abs()
        _roots[_root].append(_tmpl)
    _roots = dict(_roots)
    _LOGGER.debug(' - ROOTS %s', _root)

    # Search roots
    _results = []
    for _root, _tmpls in _roots.items():
        _results += _glob_rel_templates(dir_=_root, templates=_tmpls, job=job)

    return _results
