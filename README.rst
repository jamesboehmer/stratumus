Stratumus Layered Yaml Python Configuration
===========================================

This tool was created to ease the management of your configuration data by enabling a layered approach with variable
interpolation and custom hierarchies.

Installation
------------

``pip install stratumus``

Usage
-----

Working With Hierarchies
~~~~~~~~~~~~~~~~~~~~~~~~

Your hierarchy defines a directory structure whose names can be interpolated (with jinja2) inside your configuration.
Given this directory structure:

::

    data
    ├── config
    │   └── dev
    │       └── foo
    │           └── api
    │               └── us-east-1
    │                   └── external.yaml
    └── default
        ├── app
        │   ├── api.yaml
        │   ├── db.yaml
        │   └── feed.yaml
        ├── env
        │   ├── dev.yaml
        │   ├── prod.yaml
        │   └── staging.yaml
        └── namespace
            ├── bar.yaml
            ├── baz.yaml
            └── foo.yaml

You might run:

``stratumus --root data --hierarchy env namespace app region group --out /tmp/data``

Stratumus will first look for yaml files under ``data/config`` which match your hierarchy pattern.  In the above
example, it will find ``data/config/dev/foo/api/us-east-1/external.yaml``, and your hierarchy variables will be
defined as:

::

    env: dev
    namespace: foo
    app: api
    region: us-east-1
    group: external

Now that stratumus has your hierarchy variables defined, it will first look under ``data/default`` for default
configurations to load, in hierarchy order. Stratumus will then look at the yaml files in the leaves of ``data/config``
to override any values found in defaults.  In this example, stratumus will look for the following files in order, and
ignore missing ones:

::

    data/default/env/dev.yaml
    data/default/namespace/foo.yaml
    data/default/app/api.yaml
    data/default/region/us-east-1.yaml # not found
    data/default/group/external.yaml # not found
    data/config/dev/foo/api/us-east-1/external.yaml

Your hierarchy variables are available for interpolation inside your yaml files as well, so you can use ``{{ env }}``
and ``{{ region }}`` in both your config and your defaults.

There is one output for each file found in the config hierarchy.  In this example, that output is
``/tmp/data/dev/foo/api/us-east-1/external.yaml``.

Sharing global variables
~~~~~~~~~~~~~~~~~~~~~~~~

Variables defined in the found files will be preserved unless they are overriden later in the hierarchy.  For example,
if ``data/default/env/dev.yaml`` defined the variable ``NEWRELIC_LICENSE_KEY: "abc123"``, and that variable appeared
nowhere else in the hierarchy, then the final output of layering and interpolation would include
``NEWRELIC_LICENSE_KEY: "abc123"`` .
This is useful when you need to share a value across every application configuration you have.


Overriding variables
~~~~~~~~~~~~~~~~~~~~

Variables defined in the found files will be overriden if they are found later in the hierarchy.  For example, if
``data/default/env/dev.yaml`` defined the variable ``NEWRELIC_LICENSE_KEY: "abc123"``, and that variable appeared later
in ``data/default/app/api.yaml`` as ``NEWRELIC_LICENSE_KEY: "def456"``, then the final output of layering and
interpolation would include ``NEWRELIC_LICENSE_KEY: "def456"``.  This is useful when you need to share a value across
most application configurations, but have specific needs to override.

Variable interpolation
~~~~~~~~~~~~~~~~~~~~~~

Variables defined from your hierarchy are available for interpolation anywhere in the hierarchy.  But you can also
refer to variables defined in the files themselves.  For example, if ``NEWRELIC_LICENSE_KEY`` were defined in
``data/default/env/dev.yaml``, you can refer to ``{{ NEWRELIC_LICENSE_KEY }}`` in any other file, so long as it is
loaded later in the hierarchy.  If you attempt to interpolate a variable which does not exist, stratumus will fail.

Since stratumus uses jinja2 for variable interpolation, all of Jinja2's `filters <http://jinja.pocoo.org/docs/latest/templates/>`_ are available.  
For example, you can use ``ENV: "{{ env | upper }}"``, and your final output will include ``ENV: DEV``.


Filtering
~~~~~~~~~

You may have hundreds of configurations.  But in the case where you only want to render a subset of them, you may pass
extra positional arguments as filters to stratumus.  For example, this command would run stratumus only for configs
under ``data/config/prod/**/us-east-1/*.yaml``:

``stratumus --root data --hierarchy env namespace app region group --out /tmp/data --env prod --region us-east-1``

