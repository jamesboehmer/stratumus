from __future__ import print_function

import errno
import json
import logging
import os
import sys
from argparse import ArgumentParser
from collections import OrderedDict
from glob import glob

import hiyapyco
from hiyapyco import odyldo
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


# Shamelessly copied from http://stackoverflow.com/questions/600268/mkdir-p-functionality-in-python
def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


class Stratum(object):
    def __init__(self, root_dir, hierarchies, filters={}):
        self.root_dir = os.path.abspath(root_dir.rstrip('/'))
        self.config_dir = os.path.sep.join([self.root_dir, 'config'])
        self.default_dir = os.path.sep.join([self.root_dir, 'default'])
        self.hierarchies = hierarchies or [[]]
        self.filters = filters
        self.config = {}
        self.walk_configs()

    def walk_configs(self):
        for hierarchy in self.hierarchies:
            glob_pattern = os.path.sep.join(
                [self.config_dir] + [self.filters.get(h, '**') for h in hierarchy[:-1]] + [
                    self.filters.get(hierarchy[-1], '*')]) + '.yaml'
            logger.debug("Glob pattern: {}".format(glob_pattern))
            leaves = glob(glob_pattern)
            for leaf in leaves:
                logger.debug("Config file: {}".format(leaf))
                _leaf = os.path.splitext(leaf)[0][len(self.config_dir):].lstrip('/')
                path_components = _leaf.split(os.path.sep)
                hierarchy_values = OrderedDict(zip(hierarchy, path_components))
                logger.debug("Hierarchy: {}".format(json.dumps(hierarchy_values)))
                yaml_hierarchy_defaults = odyldo.safe_dump(hierarchy_values, default_flow_style=False)
                yaml_files_to_be_loaded = [
                    yaml_hierarchy_defaults
                ]
                for k, v in hierarchy_values.items():
                    yaml_files_to_be_loaded.append(os.path.sep.join([self.default_dir, k, v + '.yaml']))

                leaf_parent_hierarchy = list(hierarchy_values.values())[:-1]
                leaf_parents = {k: v for k, v in enumerate(leaf_parent_hierarchy)}
                for k, v in leaf_parents.items():
                    try:
                        leaf_parent = os.path.sep.join(
                            [self.config_dir] + leaf_parent_hierarchy[0:k + 1] + [leaf_parents[k + 1] + '.yaml'])
                        yaml_files_to_be_loaded.append(leaf_parent)
                    except KeyError:
                        pass

                yaml_files_to_be_loaded.append(leaf)
                logger.debug("YAML files to be loaded: {}".format(yaml_files_to_be_loaded[1:]))
                config = hiyapyco.load(yaml_files_to_be_loaded, failonmissingfiles=False, interpolate=True)
                output_name = leaf[len(self.config_dir):].lstrip('/')
                self.config[output_name] = config

    def dump_configs(self, out_dir=None):
        if not self.config:
            logger.error("No configurations found")
            return
        if not out_dir:
            for filename, config in self.config.items():
                logger.info("{}:\n---\n{}".format(filename, odyldo.safe_dump(config, default_flow_style=False)))
        else:
            for filename, config in self.config.items():
                output_name = os.path.sep.join([out_dir, filename])
                output_dir = os.path.dirname(output_name)
                mkdir_p(output_dir)
                with open(output_name, 'w') as f:
                    logger.info(output_name)
                    f.write('---\n')
                    f.write(hiyapyco.dump(config, default_flow_style=False))


def main():
    parser = ArgumentParser(description="Stratumus Layered Config Parser")
    parser.add_argument("-c", "--config", type=str, default=None, required=False,
                        help="Stratumus hierarchy config (default: $root/stratumus.yaml")
    parser.add_argument("-r", "--root", type=str, default=None, required=False,
                        help="Directory with config data (default: .)")
    parser.add_argument("-i", "--hierarchy", nargs='+', action='append', type=str, required=False)
    parser.add_argument("-o", "--out", type=str, default=None, help="Output Directory", required=False)
    parser.add_argument("-d", "--debug", action='store_true', help="Enable Debugging", required=False)

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

    stratum_config['debug'] = args.debug

    filters = dict(zip([u[2:] for u in unknown[:-1:2] if u.startswith('--')], unknown[1::2]))

    stratum_config['filters'] = filters or stratum_config.get('filters') or {}

    logger.debug(json.dumps(stratum_config))

    try:
        stratum = Stratum(root_dir=stratum_config.get('root'), hierarchies=stratum_config.get('hierarchy'),
                          filters=filters)
        stratum.dump_configs(stratum_config.get('out'))
    except Exception as e:
        logger.error(e)
        sys.exit(1)


if __name__ == '__main__':
    main()
