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
    def __init__(self, root_dir='.', hierarchies=[[]]):
        self.root_dir = os.path.abspath(root_dir.rstrip('/'))
        self.config_dir = os.path.sep.join([self.root_dir, 'config'])
        self.default_dir = os.path.sep.join([self.root_dir, 'default'])
        self.hierarchies = hierarchies or [[]]
        self.config = {}
        self.walk_configs()

    def walk_configs(self):
        for hierarchy in self.hierarchies:
            glob_pattern = os.path.sep.join([self.config_dir] + ['**' for _ in hierarchy[:-1]] + ['*.yaml'])
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
                with open(output_name, 'wb') as f:
                    logger.info(output_name)
                    f.write('---\n')
                    f.write(hiyapyco.dump(config, default_flow_style=False))


def main():
    parser = ArgumentParser(description="Stratumus Layered Config Parser")
    parser.add_argument("--config", type=str, default='stratumus.yaml', required=False)
    parser.add_argument("--root", type=str, default='.', required=False)
    parser.add_argument("--hierarchy", nargs='+', action='append', type=str, required=False)
    parser.add_argument("--out", type=str, default=None, help="Output Directory", required=False)
    parser.add_argument("--debug", action='store_true', help="Enable Debugging", required=False)
    args = parser.parse_args()

    if args.debug:
        hiyapyco.jinja2env = Environment(undefined=DebugUndefined)
        logger.setLevel(logging.DEBUG)
        hilogger.setLevel(logging.DEBUG)

    stratum_config = hiyapyco.load(args.config, failonmissingfiles=False) or {}

    if not stratum_config.get('root'):
        stratum_config['root'] = args.root

    if not stratum_config.get('hierarchy'):
        stratum_config['hierarchy'] = args.hierarchy

    if not stratum_config.get('out'):
        stratum_config['out'] = args.out

    if stratum_config.get('debug') is None:
        stratum_config['debug'] = args.debug

    logger.debug(json.dumps(stratum_config))

    try:
        stratum = Stratum(root_dir=stratum_config.get('root'), hierarchies=stratum_config.get('hierarchy'))
        stratum.dump_configs(stratum_config.get('out'))
    except Exception as e:
        logger.error(e)
        sys.exit(1)


if __name__ == '__main__':
    main()
