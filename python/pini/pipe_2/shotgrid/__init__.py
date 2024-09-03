"""Tools for managing shotgrid integration."""

import shotgun_api3

from .sg_utils import ICON, output_to_work

from .sg_handler import (
    to_handler, find, find_fields, find_one, update, create, find_all_data,
    upload_filmstrip_thumbnail, upload_thumbnail, upload)

from .sg_job import (
    to_job_data, to_job_filter, create_job, to_job_id, find_jobs, find_job)
from .sg_sequence import (
    to_sequence_filter, to_sequence_data, create_sequence, to_sequence_id,
    find_sequences)
from .sg_entity import (
    SHOT_TEMPLATE, ASSET_TEMPLATE, create_entity, to_entity_filter,
    to_entity_id, to_entity_range, to_entity_data, set_entity_range,
    find_shots, find_assets, to_entities_filter)
from .sg_user import to_user_data, to_user_filter
from .sg_step import to_step_data, MissingPipelineStep, find_steps
from .sg_task import (
    to_task_data, to_task_id, task_to_step_name, find_tasks, TASK_FIELDS)
from .sg_version import create_version, to_version_id, to_version_data
from .sg_pub_file import (
    create_pub_file, to_pub_file_id, to_pub_file_data, find_pub_files)

from .sg_tools import update_work_task
from .sg_submit import submit, set_submitter, CPSubmitter, SUBMITTER

from . import cache
from .cache import SGCPubFile

SGC = cache.SGDataCache()
