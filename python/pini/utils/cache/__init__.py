"""Tools for managing caching."""

from .uc_memory import (
    cache_result, get_result_cacher, cache_on_obj, flush_caches,
    obtain_results_cache)
from .uc_disk import (
    get_file_cacher, cache_method_to_file, get_method_to_file_cacher)
from .uc_tools import cache_property, build_cache_fmt, CacheOutdatedError
