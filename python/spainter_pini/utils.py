"""General utilites for substance."""

import substance_painter  # pylint: disable=unused-import

from pini.utils import Dir, abs_path


def project_uses_udims():
    """Test whether the current project uses udims.

    Returns:
        (bool): udims mode enabled
    """
    from substance_pini import s_pipe
    _pub_dir = Dir(abs_path('~/tmp'))
    _data = s_pipe.to_export_data()
    import pprint
    pprint.pprint(_data)
    _set_data = list(_data.values())[0]
    _file = _set_data[0]['filename']
    return _file.count('.') >= 2
