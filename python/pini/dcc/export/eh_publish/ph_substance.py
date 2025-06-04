"""Tools for managing texture publishing from substance."""

from pini import icons, pipe

from . import ph_basic


class CSubstanceTexturePublish(ph_basic.CBasicPublish):
    """Manages a substance texture publish."""

    NAME = 'Substance Texture Publish'
    ICON = icons.find('Framed Picture')
    COL = 'Salmon'
    TYPE = 'Publish'

    LABEL = '\n'.join([
        'Saves textures to disk',
    ])

    def export(self, notes=None):
        """Execute texture publish.

        Args:
            notes (str): publish notes
        """
        _job = pipe.CACHE.cur_job
        _tmpl = _job.find_template('texture_seq', catch=True)
        if not _tmpl:
            raise RuntimeError(
                f'No "texture_seq" template found in job "{_job.name}" - '
                'unable to export textures')

        del notes
        raise NotImplementedError
