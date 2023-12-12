"""Tools for managing code repositories."""

import logging
import os
import re
import time

from pini.utils import (
    Dir, cache_property, TMP_PATH, lprint, search_files_for_text, restore_cwd,
    system)

from .r_version import PRVersion, DEV_VER

_LOGGER = logging.getLogger(__name__)


class PRRepo(Dir):
    """Represents a code repository on disk."""

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

    @cache_property
    def version(self):
        """Obtain current repo version.

        Returns:
            (PRVersion): version
        """
        return self.read_version()

    def find_versions(self):
        """Find versions of this repo.

        Returns:
            (PRVersion list): repo versions
        """
        _lines = self.changelog.read().split('\n')
        _vers = []
        for _line in _lines:
            if (
                    not _line.startswith('## ') or
                    _line.count('[') != 1 or
                    not _line.count(']')):
                continue

            _ver = PRVersion(re.split(r'[\[\]]', _line)[1])
            _vers.append(_ver)

        return sorted(_vers)

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
        _LOGGER.info(' - CHANGELOG NOTES\n%s', _cl_notes)
        if update_ver:
            if _cl_notes not in _cl_body:
                _cl_body = '{}\n\n\n{}'.format(_cl_notes, _cl_body)
                self.changelog.write(_cl_body, wording='Update', force=True)
                self.changelog.edit()
            else:
                _LOGGER.info('CHANGELOG ALREADY UPDATED %s', self.changelog)
        else:
            _LOGGER.info('NOT UPDATING CHANGELOG')

    def _print_release_cmds(
            self, notes, ver, pull_mode, target, tmp_yml, email):
        """Print shell commands to execute this release.

        Args:
            notes (PRNotes): release notes
            ver (PRVersion): release version
            pull_mode (str): how to update release target (pull/clone)
            target (Dir): release target
            tmp_yml (File): release yaml data
            email (bool): print send email command
        """
        print('')
        print('# Release dev code')
        print('cd '+self.path)
        print('git add -A')
        print('git commit -m "{}" -a'.format(
            notes.to_cmdline(repo=self, ver=ver)))
        print('git push')
        print('git tag '+ver.string)
        print('git push --tags')
        print('')

        if target:
            print('# Update release code')
            if pull_mode == 'pull':
                print('cd '+target.path)
                print('git pull')
            elif pull_mode == 'clone':
                print('cd '+target.to_dir().path)
                print('git clone {} .tmp'.format(self.to_url()))
                print('rm -fr '+target.filename)
                print('mv .tmp '+target.filename)
            else:
                raise ValueError(pull_mode)
            print('')

        if email:
            print('send_release_email {}'.format(tmp_yml.path))
            print('')

    def release(
            self, target, type_, notes, update_ver=True, pull_mode='pull',
            email=True):
        """Release this repo.

        Args:
            target (Dir): release target
            type_ (str): release type (major/minor/patch)
            notes (PRNotes): release notes
            update_ver (bool): whether to update version on release
            pull_mode (str): how to update release target (pull/clone)
            email (bool): print send email command
        """
        _LOGGER.info('RELEASE')

        _mtime = time.time()
        _cur = self.read_version()
        _LOGGER.info(' - CUR VER %s', _cur)

        # Check release target
        _trg = PRRepo(target) if target else None
        if _trg:
            assert _trg.exists()
            assert (_trg.name == self.name or
                    _trg.name.split('-')[0] == self.name.split('-')[0])
            _rel = _trg.read_version()
            _LOGGER.info(' - REL VER %s', _rel)
        else:
            _rel = None

        # Get release version
        if update_ver:
            if not _cur:
                _next = PRVersion('0.0.0')
            else:
                _next = _cur.to_next(type_)
            _LOGGER.info(' - NEXT VER %s', _next)
        else:
            if _rel:
                assert _cur != _rel
                assert _cur.string != _rel.string
            _next = _cur

        # Save release data to tmp yml
        _data = {'notes': notes, 'version': _next, 'mtime': _mtime,
                 'repo': self}
        _tmp_yml = Dir(TMP_PATH).to_file(self.name+'.yml')
        _tmp_yml.write_yml(_data, force=True)

        self._update_changelog(
            notes=notes, update_ver=update_ver, ver=_next, mtime=_mtime)
        self._print_release_cmds(
            notes=notes, ver=_next, pull_mode=pull_mode, target=target,
            tmp_yml=_tmp_yml, email=email)

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
        lprint('FOUND {:d} FILES'.format(len(_files)))
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


_PINI_DIR, _ = __file__.split('python', 1)
PINI = PRRepo(_PINI_DIR)


def cur_ver():
    """Obtain current pini version.

    Returns:
        (PRVersion): pini version
    """
    from pini import testing
    if testing.dev_mode():
        return DEV_VER
    return PINI.version
