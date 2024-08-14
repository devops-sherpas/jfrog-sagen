#####################################################################
# Performs a site differences analysis between two Artifactory sites.
#
# 1. Compares which repositories exist in one and not in the other.
# 2. Checks for differences between artifacts.

import argparse
import json
import logging
import sys
from typing import Any

import requests
from requests.exceptions import HTTPError


logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s", stream=sys.stderr, level=logging.INFO)

logger = logging.getLogger(__name__)


def _raise_for_status(response: requests.Response) -> None:
    try:
        response.raise_for_status()
    except HTTPError:
        try:
            response_text = response.text
        except:
            response_text = "<unknown>"
        logger.error("Erronous response encountered and will be re-raised; response text: %s", response_text)
        raise


def _auth_header(token: str) -> dict[str, str]:
    return dict(Authorization=f"Bearer {token}")


def diff(
        url_1: str,
        url_2: str,
        token_1: str,
        token_2: str,
        exclude_artifacts: bool,
        **_):
    def _repository_keys(url: str, token: str) -> dict[str, dict[str, Any]]:
        response = requests.get(
                f"{url}/artifactory/api/repositories",
                headers=_auth_header(token),
        )
        _raise_for_status(response)
        return {item["key"]: item for item in response.json()}

    def _list_items(url: str, token: str, repository: str) -> dict[str, dict[str, Any]]:
        response = requests.get(
                f"{url}/artifactory/api/storage/{repository}?list",
                params={
                    "deep"           : 1,
                    "listFolders"    : 0,
                    "mdTimestamps"   : 0,
                    "includeRootPath": 0
                },
                headers=_auth_header(token))
        _raise_for_status(response)
        return {item["uri"]: item for item in response.json()["files"]}

    repositories_1 = _repository_keys(url_1, token_1)
    repositories_2 = _repository_keys(url_2, token_2)

    repositories_1_keys = set(repositories_1.keys())
    repositories_2_keys = set(repositories_2.keys())
    missing_in_1 = repositories_2_keys - repositories_1_keys
    missing_in_2 = repositories_1_keys - repositories_2_keys
    exists_in_both = repositories_1_keys.intersection(repositories_2_keys)
    rclass_mismatch: list[str] = []

    for key in missing_in_1:
        logger.info("Repository exists in site 2 and missing in site 1: %s", key)
    for key in missing_in_2:
        logger.info("Repository exists in site 1 and missing in site 2: %s", key)
    for key in exists_in_both:
        rclass_1 = repositories_1[key]["type"]
        rclass_2 = repositories_2[key]["type"]
        if rclass_1 != rclass_2:
            logger.info("Repository %s is of type %s on site 1, but %s on site 2", key, rclass_1, rclass_2)
            rclass_mismatch.append(key)

    artifacts_report = None
    if not exclude_artifacts:
        artifacts_report = {}
        for key in exists_in_both:
            if repositories_1[key]["type"] in {"VIRTUAL", "REMOTE"}:
                continue
            logger.info("Comparing repository: %s", key)

            def _artifacts_report() -> dict:
                return artifacts_report.setdefault(key, {})

            items_in_1 = _list_items(url_1, token_1, key)
            items_in_2 = _list_items(url_2, token_2, key)
            items_in_1_uris = set(items_in_1.keys())
            items_in_2_uris = set(items_in_2.keys())
            missing_in_1_uris = items_in_2_uris - items_in_1_uris
            missing_in_2_uris = items_in_1_uris - items_in_2_uris
            if missing_in_1_uris:
                _artifacts_report()["missing_in_1"] = list(missing_in_1_uris)
            if missing_in_2_uris:
                _artifacts_report()["missing_in_2"] = list(missing_in_2_uris)
            items_existing_in_both = items_in_1_uris.intersection(items_in_2_uris)

            for uri in items_existing_in_both:
                item_in_1 = items_in_1[uri]
                item_in_2 = items_in_2[uri]
                if item_in_1["sha1"] != item_in_2["sha1"] or item_in_1["sha2"] != item_in_2["sha2"]:
                    _artifacts_report().setdefault("diffs", []).append(uri)

    report = {
        "repositories": {
            "missing_in_1"   : list(missing_in_1),
            "missing_in_2"   : list(missing_in_2),
            "rclass_mismatch": rclass_mismatch
        },
        "artifacts"   : artifacts_report
    }

    json.dump(report, sys.stdout, indent=2)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--url-1", required=True, metavar="url", help="Artifactory's root URL for site 1")
    parser.add_argument("--url-2", required=True, metavar="url", help="Artifactory's root URL for site 2")

    parser.add_argument("--token-1", required=True, metavar="token", help="Identity / Access token for site 1")
    parser.add_argument("--token-2", required=True, metavar="token", help="Identity / Access token for site 2")

    parser.add_argument("--exclude-artifacts", action="store_true", help="Exclude artifacts comparison", default=False)

    args = parser.parse_args()
    diff(**vars(args))


if __name__ == "__main__":
    main()
