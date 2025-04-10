"""Tools for managing code repositories."""

import logging
import os
import re
import time

from pini.utils import (
    Dir, cache_property, TMP_PATH, lprint, search_files_for_text, restore_cwd,
    system, to_time_f, abs_path, cache_result, dprint)

from . import test
from .r_version import PRVersion, DEV_VER

_LOGGER = logging.getLogger(__name__)


class PRRepo(Dir):
    """Represents a code repository on disk."""

    def __init__(self, dir_):
        """Constructor.

        Args:
            dir_ (str): path to repo
        """
        _dir = abs_path(dir_)
        _LOGGER.debug('INIT PRRepo %s', _dir)
        super().__init__(_dir)

    @property
    def name(self):
        """Get name of this reposity.

        Returns:
            (str): repo name
        """
        return self.filename

    @property
    def changelog(self):
        """Obtain this repo's CHANGELOG file.

        Returns:
            (File): CHANGELOG
        """
        return self.to_file('CHANGELOG')

    @property
    def git_repo(self):
        """Get dev repo.

        Returns:
            (git.Repo): dev repo
        """
        import git
        return git.Repo(self.path)

    @cache_property
    def version(self):
        """Obtain current repo version.

        Returns:
            (PRVersion): version
        """
        return self.read_version()

    @cache_result
    def find_py_files(self, filter_=None, class_=None, force=False):
        """Find python files in the dev codebase.

        Args:
            filter_ (str): apply filter to the list
            class_ (type): override py file class
            force (bool): force reread file list

        Returns:
            (str list): list of files to check
        """
        _files = []
        _LOGGER.info("SEARCHING %s", self.path)
        assert self.exists()
        _files += self.find(
            extn='py', type_='f', filter_=filter_, class_=class_,
            catch_missing=False)
        _files += Dir(self.path + '/bin').find(
            type_='f', filter_=filter_, class_=class_, extn=None,
            catch_missing=True)
        return _files

    def find_tests(self, mode='all', filter_=None):
        """Find tests in this repo.

        Args:
            mode (str): type of tests to find (all/unit/integration)
            filter_ (str): apply filter to test name

        Returns:
            (PRTest list): matching tests
        """
        from pini import dcc

        _files = self.find(
            extn='py', filter_='/tests/', class_=test.PRTestFile)

        # Apply dcc filter
        _files = [
            _file for _file in _files
            if _file.dcc_ in (None, dcc.NAME)]

        # Apply mode filter
        if str(mode).lower() in ('unit', 'integration'):
            _files = [
                _file for _file in _files if _file.test_type == mode.lower()]
        elif mode is None or str(mode).lower() == 'all':
            pass
        else:
            raise ValueError(mode)

        _tests = sum(
            [_file.find_tests(filter_=filter_) for _file in _files], [])

        return _tests

    def find_versions(self):
        """Find versions of this repo.

        Returns:
            (PRVersion list): repo versions
        """
        _LOGGER.debug('FIND VERS %s', self)
        _lines = self.changelog.read().split('\n')
        _vers = []
        for _line in _lines:
            if (
                    not _line.startswith('## ') or
                    _line.count('[') != 1 or
                    not _line.count(']')):
                continue
            _ver_s = re.split(r'[\[\]]', _line)[1]
            _LOGGER.debug(' - ADD VER %s', _ver_s)
            _LOGGER.debug('   - LINE %s', _line)
            _, _time_s = _line.split(' - ', 1)
            _time_t = time.strptime(_time_s, '%a %Y-%m-%d %H:%M')
            _time_f = to_time_f(_time_t)
            _LOGGER.debug('   - TIME %s %s', _time_s, _time_f)
            _ver = PRVersion(_ver_s, mtime=_time_f)
            _vers.append(_ver)

        return sorted(_vers)

    def pull(self, repo=None):
        """Pull this repo's dev code.

        Args:
            repo (GitRepo): override repo
        """
        dprint('PULLING', self)
        _repo = repo or self.git_repo
        print(' - PATH', _repo.working_dir)
        print(' - REPO', _repo)
        print(' -', _repo.git.pull())

    def push(self, message, repo=None, force=False):
        """Push this repo's dev code.

        Args:
            message (str): commit message
            repo (GitRepo): override repo
            force (bool): push even if nothing committed
        """
        dprint('PUSHING', self)
        _repo = repo or self.git_repo
        print(' - PATH', _repo.working_dir)
        print(' - REPO', _repo)

        _repo.git.add(all=True)

        _dirty = _repo.is_dirty()
        if not force and not _dirty:
            print(' - NO PUSH NEEDED')
            return

        _repo.git.commit(all=True, message=message)
        _result = _repo.git.push()
        print(' - PUSHED DATA', _result)

    def read_version(self):
        """Read current version from CHANGELOG.

        Returns:
            (PRVersion): version
        """
        _lines = self.changelog.read().split('\n')
        _lines = [_line for _line in _lines
                  if _line.startswith('## ') and
                  _line.count('[') == 1 and
                  _line.count(']')]
        if not _lines:
            return None
        return PRVersion(re.split(r'[\[\]]', _lines[0])[1])

    def _update_changelog(self, notes, update_ver, ver, mtime):
        """Update CHANGELOG with new version info.

        Args:
            notes (PRNotes): release notes
            update_ver (bool): whether to update version on release
            ver (PRVersion): release version
            mtime (float): release mtime
        """
        _cl_notes = notes.to_changelog(ver=ver, mtime=mtime)
        _cl_body = self.changelog.read().rstrip()
        _LOGGER.debug(' - CHANGELOG NOTES\n%s', _cl_notes)
        if update_ver:
            if _cl_notes not in _cl_body:
                _cl_body = f'{_cl_notes}\n\n\n{_cl_body}'
                self.changelog.write(_cl_body, wording='Update', force=True)
                self.changelog.edit()
            else:
                _LOGGER.debug('CHANGELOG ALREADY UPDATED %s', self.changelog)
        else:
            _LOGGER.debug('NOT UPDATING CHANGELOG')

    def _print_release_cmds(
            self, notes, ver, pull_mode, target, tmp_yml, email, dev_label):
        """Print shell commands to execute this release.

        Args:
            notes (PRNotes): release notes
            ver (PRVersion): release version
            pull_mode (str): how to update release target (pull/clone)
            target (Dir): release target
            tmp_yml (File): release yaml data
            email (bool): print send email command
            dev_label (str): how to label dev push in comment
        """
        print(f'# Release {dev_label} code')
        print('cd ' + self.path)
        print('git add -A')
        print(f'git commit -m "{notes.to_cmdline(repo=self, ver=ver)}" -a')
        print('git push')
        print('git tag ' + ver.string)
        print('git push --tags')

        if target:
            print('')
            print('# Update release code')
            if pull_mode == 'pull':
                print('cd ' + target.path)
                print('git pull')
            elif pull_mode == 'clone':
                print('cd ' + target.to_dir().path)
                print(f'git clone {self.to_url()} .tmp')
                print('rm -fr ' + target.filename)
                print('mv .tmp ' + target.filename)
            else:
                raise ValueError(pull_mode)
            print('')

        if email:
            print(f'send_release_email {tmp_yml.path}')
            print('')

    def release(
            self, target, type_, notes, update_ver=True, pull_mode='pull',
            email=True, dev_label='dev'):
        """Release this repo.

        Args:
            target (Dir): release target
            type_ (str): release type (major/minor/patch)
            notes (PRNotes): release notes
            update_ver (bool): whether to update version on release
            pull_mode (str): how to update release target (pull/clone)
            email (bool): print send email command
            dev_label (str): how to label dev push in comment
        """
        _LOGGER.debug('RELEASE')

        _mtime = time.time()
        _cur = self.read_version()
        _LOGGER.debug(' - CUR VER %s', _cur)

        # Check release target
        _trg = PRRepo(target) if target else None
        if _trg:
            assert _trg.exists()
            assert (_trg.name == self.name or
                    _trg.name.split('-')[0] == self.name.split('-')[0])
            _rel = _trg.read_version()
            _LOGGER.debug(' - REL VER %s', _rel)
        else:
            _rel = None

        # Get release version
        if update_ver:
            if not _cur:
                _next = PRVersion('0.0.0')
            else:
                _next = _cur.to_next(type_)
            _LOGGER.debug(' - NEXT VER %s', _next)
        else:
            if _rel:
                assert _cur != _rel
                assert _cur.string != _rel.string
            _next = _cur

        # Save release data to tmp yml
        _data = {'notes': notes, 'version': _next, 'mtime': _mtime,
                 'repo': self}
        _tmp_yml = Dir(TMP_PATH).to_file(
            f'{self.name}_{_next.to_str()}.yml')
        _tmp_yml.write_yml(_data, force=True)

        self._update_changelog(
            notes=notes, update_ver=update_ver, ver=_next, mtime=_mtime)
        self._print_release_cmds(
            notes=notes, ver=_next, pull_mode=pull_mode, target=target,
            tmp_yml=_tmp_yml, email=email, dev_label=dev_label)

        return _tmp_yml

    def search_code(self, filter_=None, edit=False, text=None,
                    file_filter=None, extn='py', verbose=0):
        """Search code for text.

        Args:
            filter_ (str): line match filter
            edit (bool): edit text on first occurance then exit
            text (str): exact text match
            file_filter (str): file filter
            extn (str): extension filter (default is py)
            verbose (int): print process data
        """
        lprint('SEARCHING', self.path, verbose=verbose)
        _files = Dir(self.path).find(
            type_='f', extn=extn, filter_=file_filter)
        lprint(f'FOUND {len(_files):d} FILES')
        search_files_for_text(
            files=_files, filter_=filter_, edit=edit, text=text)

    @restore_cwd
    def to_url(self):
        """Obtain this repo's clone url.

        Returns:
            (str): clone url
        """
        os.chdir(self.path)
        return system('git config --get remote.origin.url').strip()


_FILE = os.environ.get('PINI_REPO_FILE', __file__)
_PINI_DIR, _ = _FILE.split('python', 1)
PINI = PRRepo(_PINI_DIR)


def add_repo(repo):
    """Add repo to pini repos.

    Args:
        repo (PRRepo): repo to add
    """
    from pini.tools import release
    _names = [_repo.name for _repo in release.REPOS]
    if repo.name in _names:
        release.REPOS[_names.index(repo.name)] = repo
    else:
        release.REPOS.append(repo)


def cur_ver():
    """Obtain current pini version.

    Returns:
        (PRVersion): pini version
    """
    from pini import testing
    if testing.dev_mode():
        return DEV_VER
    return PINI.version
