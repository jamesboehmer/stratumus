from __future__ import print_function

import errno
import itertools
import json
import logging
import os
import re
import sys

from argparse import ArgumentParser
from collections import OrderedDict
from glob import glob

import hiyapyco
from hiyapyco import odyldo, METHOD_SIMPLE, METHOD_MERGE
from jinja2 import Environment, DebugUndefined, StrictUndefined

hiyapyco.jinja2env = Environment(undefined=StrictUndefined)

hiconsole = logging.StreamHandler()
hiconsole.setLevel(logging.ERROR)
hilogger = logging.getLogger('hiyapyco')
hilogger.addHandler(hiconsole)

console = logging.StreamHandler()
logger = logging.getLogger('stratumus')
logger.addHandler(console)
logger.setLevel(logging.INFO)

INCLUSIVE_VALUE = '@'
YAML_SUFFIX_PATTERN = re.compile(r'.yaml$')


# Shamelessly copied from http://stackoverflow.com/questions/600268/mkdir-p-functionality-in-python
def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


# Shamelessly copied from https://stackoverflow.com/questions/8784813/lstrip-rstrip-for-lists
def _rstrip_list(l):
    reverse_stripped = itertools.dropwhile(lambda val: val == INCLUSIVE_VALUE, reversed(l))
    return reversed(list(reverse_stripped))


class Stratum(object):
    def __init__(self, root_dir, hierarchies, filters={}, attempt_deep_merge=False):
        self.root_dir = os.path.abspath(root_dir.rstrip('/'))
        self.config_dir = os.path.sep.join([self.root_dir, 'config'])
        self.default_dir = os.path.sep.join([self.root_dir, 'default'])
        self.attempt_deep_merge = attempt_deep_merge
        self.hierarchies = hierarchies or [[]]
        self.filters = filters
        self.config = {}
        self.walk_configs()

    def walk_configs(self):
        for hierarchy in self.hierarchies:
            glob_pattern_to_join = [self.config_dir]
            hierarchy_strings_to_alias = {}
            for i, h in enumerate(hierarchy):
                if isinstance(h, str):
                    hierarchy_string = h
                    alias = h
                elif isinstance(h, OrderedDict) and len(h) == 1:
                    hierarchy_string = list(h.keys())[0]
                    alias = h[hierarchy_string]
                else:
                    raise Exception(
                        'Hierarchy elements must be either strings or OrderedDicts of length 1. Received {}'.
                        format(h))
                hierarchy_strings_to_alias[hierarchy_string] = alias
                default_filter = '**'
                extension = ''
                if i == len(hierarchy_string) - 1:
                    default_filter = '*'
                    extension = '.yaml'
                glob_pattern_to_join.append(self.filters.get(hierarchy_string, default_filter) + extension)
            glob_pattern = os.path.sep.join(glob_pattern_to_join)
            logger.debug("Glob pattern: {}".format(glob_pattern))
            leaves = [path for path in glob(glob_pattern) if INCLUSIVE_VALUE not in path]
            for leaf in leaves:
                logger.debug("Config file: {}".format(leaf))
                _leaf = os.path.splitext(leaf)[0][len(self.config_dir):].lstrip('/')
                path_components = _leaf.split(os.path.sep)
                hierarchy_dict = OrderedDict(zip(list(hierarchy_strings_to_alias.keys()), path_components))
                logger.debug("Hierarchy: {}".format(json.dumps(hierarchy_dict)))
                yaml_hierarchy_defaults = odyldo.safe_dump(hierarchy_dict, default_flow_style=False)
                # FIRST APPEND HIERARCHICAL VALUES
                yaml_files_to_be_loaded = [
                    yaml_hierarchy_defaults
                ]

                # NOW APPEND DEFAULT FILES
                for k, v in hierarchy_dict.items():
                    default_fp = os.path.sep.join([self.default_dir, k, v + '.yaml'])
                    if os.path.isfile(default_fp):
                        yaml_files_to_be_loaded.append(default_fp)

                # NOW APPEND CONFIG FILES
                hierarchy_values = hierarchy_dict.values()
                possible_paths = itertools.product(*[[INCLUSIVE_VALUE, val] for val in hierarchy_values])

                def _gen_config_paths():
                    for possible_path_components in possible_paths:
                        # cut config/dev/foo/api/@/@.yaml to config/dev/foo/api.yaml
                        stripped = tuple(_rstrip_list(possible_path_components))
                        if stripped:
                            config_filename = stripped[-1] + '.yaml'
                            config_filepath = os.path.sep.join(
                                (self.config_dir,) + stripped[:-1] + (config_filename,)
                            )
                            if os.path.isfile(config_filepath):
                                yield config_filepath

                sorted_config_files = sorted(
                    _gen_config_paths(),
                    key=lambda value: (len(value.split(os.path.sep)), value)
                )

                yaml_files_to_be_loaded.extend(sorted_config_files)

                logger.debug("YAML files to be loaded: {}".format(yaml_files_to_be_loaded[1:]))
                config = {}
                if self.attempt_deep_merge:
                    try:
                        config = hiyapyco.load(yaml_files_to_be_loaded, failonmissingfiles=True, interpolate=True,
                                               method=METHOD_MERGE)
                    except:
                        logger.debug('Unable to load with method=merge, will attempt method=simple')
                if not config:
                    config = hiyapyco.load(yaml_files_to_be_loaded, failonmissingfiles=True, interpolate=True,
                                           method=METHOD_SIMPLE)
                for (hierarchy_string, hierarchy_alias) in hierarchy_strings_to_alias.items():
                    if hierarchy_alias != hierarchy_string:
                        if hierarchy_alias:
                            config[hierarchy_alias] = config[hierarchy_string]
                        config.pop(hierarchy_string)
                output_name = leaf[len(self.config_dir):].lstrip('/')
                self.config[output_name] = config

    def dump_configs(self, out_dir=None, with_json=False):
        if not self.config:
            logger.error("No configurations found")
            return
        if not out_dir:
            for filename, config in self.config.items():
                logger.info("{}:\n---\n{}".format(filename, odyldo.safe_dump(config, default_flow_style=False)))
                if with_json:
                    logger.info("{}\n".format(json.dumps(config)))
        else:
            for filename, config in self.config.items():
                output_name = os.path.sep.join([out_dir, filename])
                output_dir = os.path.dirname(output_name)
                mkdir_p(output_dir)
                with open(output_name, 'w') as f:
                    logger.info(output_name)
                    f.write('---\n')
                    f.write(hiyapyco.dump(config, default_flow_style=False))
                json_output_name = YAML_SUFFIX_PATTERN.sub('.json', output_name)
                if with_json:
                    with open(json_output_name, 'w') as f:
                        logger.info(json_output_name)
                        json.dump(config, f)


def main():
    parser = ArgumentParser(description="Stratumus Layered Config Parser")
    parser.add_argument("-c", "--config", type=str, default=None, required=False,
                        help="Stratumus hierarchy config (default: $root/stratumus.yaml")
    parser.add_argument("-r", "--root", type=str, default=None, required=False,
                        help="Directory with config data (default: .)")
    parser.add_argument("-i", "--hierarchy", nargs='+', action='append', type=str, required=False)
    parser.add_argument("-o", "--out", type=str, default=None, help="Output directory", required=False)
    parser.add_argument("-j", "--with-json", action='store_true', help="Dumps json in addition to yaml", required=False)
    parser.add_argument("-d", "--debug", action='store_true', help="Enable Debugging", required=False)
    parser.add_argument("-m", "--deep-merge", action='store_true', help="Attempt to use hiyapyco METHOD_MERGE. This"
                                                                        "will perform a deep merge, recursively merging"
                                                                        "dictionaries nested in lists.", required=False)

    args, unknown = parser.parse_known_args()

    if args.debug:
        hiyapyco.jinja2env = Environment(undefined=DebugUndefined)
        logger.setLevel(logging.DEBUG)
        hilogger.setLevel(logging.DEBUG)

    if args.config and args.root is None:
        args.root = os.path.dirname(args.config)

    if args.root is None:
        args.root = os.path.abspath('.')

    if args.config is None:
        args.config = os.path.sep.join([args.root, 'stratumus.yaml'])

    stratum_config = hiyapyco.load(args.config, failonmissingfiles=False) or {}

    stratum_config['root'] = args.root

    # Always use the user-specified hierarchy over the config file
    stratum_config['hierarchy'] = args.hierarchy or stratum_config.get('hierarchy') or [[]]

    stratum_config['out'] = args.out

    stratum_config['with_json'] = args.with_json

    stratum_config['attempt_deep_merge'] = args.deep_merge

    stratum_config['debug'] = args.debug

    filters = dict(zip([u[2:] for u in unknown[:-1:2] if u.startswith('--')], unknown[1::2]))

    stratum_config['filters'] = filters or stratum_config.get('filters') or {}

    logger.debug(json.dumps(stratum_config))

    try:
        stratum = Stratum(root_dir=stratum_config.get('root'), hierarchies=stratum_config.get('hierarchy'),
                          filters=filters, attempt_deep_merge=stratum_config.get('attempt_deep_merge'))
        stratum.dump_configs(stratum_config.get('out'), stratum_config['with_json'])
    except Exception as e:
        logger.exception(e)
        sys.exit(1)


if __name__ == '__main__':
    main()
