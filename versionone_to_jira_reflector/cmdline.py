import argparse
import logging
import os

from configobj import ConfigObj

from .main import (
    ensure_default_settings,
    get_versionone_connection,
    get_jira_connection,
    get_jira_issue_for_v1_issue,
    get_versionone_story_by_name,
    update_jira_ticket_with_versionone_data,
    reset_saved_passwords
)


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
        '--label',
        dest='labels',
        type=str,
        nargs='+',
        default=argparse.SUPPRESS,
        help=(
            'Optional label(s) to be added to the created/updated JIRA tickets.'
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
        '--reset-saved-passwords',
        default=False,
        action='store_true',
        help=(
            'Reset saved passwords.'
        )
    )
    parser.add_argument(
        '--loglevel',
        type=str,
        default='INFO'
    )
    parser.add_argument(
        '--no-open',
        default=False,
        action='store_true',
        help=(
            'Do not open created/updated JIRA tickets in your default browser.'
        )
    )
    args = parser.parse_args()

    # Set up a simple console logger
    logging.basicConfig(level=args.loglevel)
    logging.addLevelName(
        logging.WARNING,
        "\033[1;31m%s\033[1;0m" % logging.getLevelName(logging.WARNING)
    )
    logging.addLevelName(
        logging.ERROR,
        "\033[1;41m%s\033[1;0m" % logging.getLevelName(logging.ERROR)
    )

    # Get configuration object
    logger.info(
        "Loading configuration from %s", args.configfile
    )
    config = ensure_default_settings(
        ConfigObj(args.configfile)
    )

    if args.reset_saved_passwords:
        reset_saved_passwords(config)

    v1_connection = get_versionone_connection(config)
    jira_connection = get_jira_connection(config)

    for story_number in args.versionone_ids:
        logger.info("Processing story #%s", story_number)
        story = get_versionone_story_by_name(
            v1_connection, config, story_number
        )
        ticket = get_jira_issue_for_v1_issue(
            jira_connection, config, story
        )

        update_jira_ticket_with_versionone_data(
            jira_connection,
            v1_connection,
            ticket,
            story,
            config,
            args.labels if 'labels' in args else None,
            open_url=not args.no_open
        )

    # If any configuration values were changed, let's save them
    config.write()
