import os
from setuptools import setup, find_packages

from versionone_to_jira_reflector import __version__ as version_string


requirements_path = os.path.join(
    os.path.dirname(__file__),
    'requirements.txt',
)
try:
    from pip.req import parse_requirements
    requirements = [
        str(req.req) for req in parse_requirements(requirements_path)
    ]
except ImportError:
    requirements = []
    with open(requirements_path, 'r') as in_:
        requirements = [
            req for req in in_.readlines()
            if not req.startswith('-')
            and not req.startswith('#')
        ]


setup(
    name='versionone-to-jira-reflector',
    version=version_string,
    url='https://github.com/coddingtonbear/versionone-to-jira-reflector',
    description=(
        'Copy/update JIRA issues to match your VersionOne stories.'
    ),
    author='Adam Coddington',
    author_email='me@adamcoddington.net',
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
    ],
    install_requires=requirements,
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'v1tojira = versionone_to_jira_reflector.cmdline:main'
        ],
    },
)
