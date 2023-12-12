"""General utilities for autowrite 2.0."""

from pini.utils import SixIntEnum

COL_FMT = '<p style="color:{col};">{text}</p>'

DEFAULT_COL = 'DarkGray'
NON_DEFAULT_COL = 'LightSalmon'
FILE_COL = 'Green'
ERROR_COL = 'Red'
INTERNAL_COL = 'Yellow'

RENDER_COL = 'CornflowerBlue'
PLATE_COL = 'MediumSpringGreen'


class UpdateLevel(SixIntEnum):
    """Enum for managing levels of autowrite update."""

    JOB = 0
    PROFILE = 1
    ENTITY_TYPE = 2
    ENTITY = 3
    TASK = 4
    TAG = 5
    VERSION = 6
    OUTPUT_NAME = 7
