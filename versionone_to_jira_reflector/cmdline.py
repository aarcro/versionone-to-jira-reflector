import argparse
import logging
import os

from configobj import ConfigObj

from .main import (
    get_versionone_connection,
    get_jira_connection,
    get_versionone_story_by_name,
)
from .reflector import Reflector


logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'versionone_ids',
        type=str,
        nargs='+',
        help=(
            'A list of VersionOne IDs for which to'
            'create/update JIRA tickets.'
        )
    )
    parser.add_argument(
        '--configfile',
        type=str,
        default=os.path.expanduser(
            '~/.versionone-to-jira-reflector',
        )
    )
    parser.add_argument(
        '--loglevel',
        type=str,
        default='INFO'
    )
    args = parser.parse_args()

    # Set up a simple console logger
    logging.basicConfig(level=args.loglevel)

    # Get configuration object
    logger.debug(
        "Loading configuration from %s", args.configfile
    )
    config = ConfigObj(args.configfile)

    v1_connection = get_versionone_connection(config)
    jira_connection = get_jira_connection(config)

    # If any configuration values were changed, let's save them
    config.write()
