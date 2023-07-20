Changelog
=========

- new MAJOR version for incompatible API changes,
- new MINOR version for added functionality in a backwards compatible manner
- new PATCH version for backwards compatible bug fixes

tasks:
    - test if caching of handles make sense, especially on network
    - documentation update
    - pathlib-like Interface
    - jupyter notebook update

v2.0.8
---------
2023-07-20:
    - require minimum python 3.8
    - remove python 3.7 tests
    - introduce PEP517 packaging standard
    - introduce pyproject.toml build-system
    - remove mypy.ini
    - remove pytest.ini
    - remove setup.cfg
    - remove setup.py
    - remove .bettercodehub.yml
    - remove .travis.yml
    - update black config
    - clean ./tests/test_cli.py
    - add codeql badge
    - move 3rd_party_stubs outside the src directory to ``./.3rd_party_stubs``
    - add pypy 3.10 tests
    - add python 3.12-dev tests

v2.0.7
--------
2020-10-10: fix minor bugs

v2.0.6
--------
2020-10-09: service release
    - update travis build matrix for linux 3.9-dev
    - update travis build matrix (paths) for windows 3.9 / 3.10

v2.0.5
--------
2020-08-08: service release
    - fix documentation
    - fix travis
    - deprecate pycodestyle
    - implement flake8

v2.0.4
---------
2020-08-01: fix pypi deploy

v2.0.3
--------
2020-07-31: fix travis build

v2.0.2
--------
2020-07-29: feature release
    - use the new pizzacutter template
    - use cli_exit_tools

v2.0.1
--------
2020-07-16: feature release
    - fix cli test
    - enable traceback option on cli errors
    - corrected error in DeleteKey, missing_ok

v2.0.0
--------
2020-07-14 : feature release
    - fix setup.py for deploy on pypi
    - fix travis for pypi deploy testing

v2.0.0a0
--------
2020-07-13 : intermediate release
    - start to implement additional pathlib-like interface
    - implement fake-winreg to be able to develop and test under linux

v1.0.4
--------
2020-07-08 : patch release
    - new click CLI
    - use PizzaCutter Template
    - added jupyter notebook
    - reorganized modules and import
    - updated documentation

v1.0.3
--------
2019-09-02: strict mypy type checking, housekeeping

v1.0.2
--------
2019-04-10: initial PyPi release

v1.0.1
--------
2019-03-29: prevent import error when importing under linux

v1.0.0
--------
2019-03-28: Initial public release
