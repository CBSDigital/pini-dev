"""Tools for managing cinema4d interaction via the pini.dcc module."""

# pylint: disable=abstract-method

import logging

import c4d

from pini.utils import File, abs_path
from .d_base import BaseDCC

_LOGGER = logging.getLogger(__name__)


class C4dDCC(BaseDCC):
    """Manages interactions with c4d."""

    DEFAULT_EXTN = 'c4d'
    HELPER_AVAILABLE = True
    NAME = 'c4d'
    VALID_EXTNS = ('c4d', )

    def doc(self):
        """Obtain reference to active document.

        Returns:
            (BaseDocument): document
        """
        return c4d.documents.GetActiveDocument()

    def cur_file(self):
        """Get path to current file.

        Returns:
            (str): current file
        """
        _path = File(self.doc().GetDocumentPath()).to_dir().path
        _name = self.doc().GetDocumentName()
        if _name.startswith('Untitled'):
            return None
        return abs_path('/'.join([_path, _name]))

    def _force_new_scene(self):
        """Force new scene without confirmation."""
        _LOGGER.info('FORCE NEW SCENE')
        self.doc().Flush()
        self.doc().SetDocumentPath('')
        self.doc().SetDocumentName('Untitled')
        assert not self.cur_file()

    def _force_save(self, file_=None):
        """Force save the current scene without overwrite confirmation.

        Args:
            file_ (str): path to save scene to
        """
        _LOGGER.info('FORCE SAVE')
        assert file_
        _file = File(file_)
        # _doc = c4d.documents.GetActiveDocument()
        self.doc().SetDocumentPath(_file.path)
        self.doc().SetDocumentName(_file.filename)
        _LOGGER.info(' - FILE %s', _file.path)
        c4d.documents.SaveDocument(
            self.doc(), _file.path, c4d.SAVEDOCUMENTFLAGS_0,
            c4d.FORMAT_C4DEXPORT)

    def _force_load(self, file_):
        """Force load scene without confirmation.

        Args:
            file_ (str): file to load
        """
        _file = File(file_)
        _LOGGER.info('FORCE LOAD %s', _file.path)
        c4d.documents.LoadFile(_file.path)
        c4d.documents.LoadDocument(_file.path, c4d.SCENEFILTER_NONE)
        self.doc().SetDocumentPath(_file.dir + '/' + _file.base)

    def get_fps(self):
        """Get current fps.

        Returns:
            (float): frame rate
        """
        return self.doc().GetFps()

    def _read_version(self):
        """Read current c4d version.

        Returns:
            (tuple): c4d version
        """
        _ver = str(c4d.GetC4DVersion())
        return int(_ver[:2]), int(_ver[2:]), None

    def refresh(self):
        """Redraw ui."""
        c4d.EventAdd()
        c4d.DrawViews(
            c4d.DRAWFLAGS_ONLY_ACTIVE_VIEW |
            c4d.DRAWFLAGS_NO_THREAD |
            c4d.DRAWFLAGS_STATICBREAK)

    def t_end(self, class_=int):
        """Read timeline end frame.

        Args:
            class_ (class): override type of data to return

        Returns:
            (int): end frame
        """
        _max = self.doc().GetMaxTime()
        return class_(_max.GetFrame(self.get_fps()))

    def t_start(self, class_=int):
        """Read timeline start frame.

        Args:
            class_ (class): override type of data to return

        Returns:
            (int): start frame
        """
        _min = self.doc().GetMinTime()
        return class_(_min.GetFrame(self.get_fps()))

    def set_range(self, start, end):
        """Set timeline range.

        Args:
            start (int): start frame
            end (int): end frame
        """
        _fps = self.get_fps()
        _start_t = c4d.BaseTime(start / _fps)
        _end_t = c4d.BaseTime(end / _fps)
        if end > self.doc().GetMaxTime().GetFrame(_fps):
            self.doc().SetMaxTime(_end_t)
            self.doc().SetMinTime(_start_t)
        else:
            self.doc().SetMinTime(_start_t)
            self.doc().SetMaxTime(_end_t)

    def unsaved_changes(self):
        """Test whether there area unsaved changes.

        NOTE: this does not seem reliable.

        Returns:
            (bool): unsaved changes
        """
        return self.doc().GetChanged()
