import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Generator

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


def _report_summaries_generator(url: str, token: str) -> Generator[tuple[int, str, dict[str, Any]], None, None]:
    page_num = 1
    while True:
        response = requests.post(
                f"{url}/xray/api/v1/reports",
                params={
                    "direction"  : "asc",
                    "page_num"   : page_num,
                    "num_of_rows": 10,
                    "order_by"   : "name"
                },
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept"       : "application/json",
                })
        _raise_for_status(response)
        result = response.json()
        reports = result.get("reports", [])
        if not reports:
            break
        for definition in reports:
            yield definition["id"], definition["name"], definition
        page_num += 1


def export_definitions(
        url: str,
        token: str,
        output_dir: Path,
        **_):
    output_dir.mkdir(parents=True, exist_ok=True)
    for report_id, report_name, definition in _report_summaries_generator(url, token):
        summary_output_path = output_dir.joinpath(f"{report_id}-summary.json")
        logger.info("Exporting summary of report '%s' (ID: %d) to %s", report_name, report_id, summary_output_path)
        with summary_output_path.open("w", encoding="UTF-8") as f:
            json.dump(definition, f, indent=2)
        details_output_path = output_dir.joinpath(f"{report_id}-details.json")
        logger.info("Exporting definition of report '%s' (ID: %d) to %s", report_name, report_id, details_output_path)
        response = requests.get(
                f"{url}/xray/api/v1/reports/{report_id}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept"       : "application/json",
                })
        _raise_for_status(response)
        with details_output_path.open("w", encoding="utf-8") as f:
            json.dump(response.json(), f, indent=2)


def import_definitions(
        url: str,
        token: str,
        input_dir: Path,
        **_):
    if not input_dir.is_dir():
        raise Exception(f"Path is not a directory or doesn't exist: {input_dir}")

    for definition_file in input_dir.rglob("*.json"):
        logger.info("Importing definition: %s", definition_file)
        with definition_file.open("r", encoding="UTF-8") as f:
            definition = json.load(f)
        report_type = definition["report_type"]
        if report_type == "license":
            uri_type = "licenses"
        elif report_type == "vulnerability":
            uri_type = "vulnerabilities"
        elif report_type == "operational_risk":
            uri_type = "operationalRisks"
        else:
            raise Exception(f"Unrecognized report type: {report_type}")
        response = requests.post(
                f"{url}/xray/api/v1/reports/{uri_type}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept"       : "application/json",
                },
                json=definition
        )
        _raise_for_status(response)


def export_contents(
        url: str,
        token: str,
        output_dir: Path,
        report_format: str,
        **_):
    output_dir.mkdir(parents=True, exist_ok=True)
    for report_id, report_name, definition in _report_summaries_generator(url, token):
        output_path = output_dir.joinpath(f"{report_id}-{report_name}.zip")
        logger.info(
                "Exporting results of report '%s' (ID: %d) to %s (format: %s)", report_name, report_id,
                output_path, report_format)
        with requests.get(
                f"{url}/xray/api/v1/reports/export/{report_id}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept"       : "application/zip"
                },
                params={
                    "file_name": f"{report_id}-{report_name}",
                    "format"   : report_format
                },
                stream=True) as r:
            _raise_for_status(r)
            with output_path.open(mode="wb") as f:
                for chunk in r.iter_content(chunk_size=None):
                    f.write(chunk)


def main():
    parser = argparse.ArgumentParser()

    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--url", required=True, metavar="url", help="Artifactory's root URL")
    common_parser.add_argument("--token", required=True, metavar="token", help="Identity / Access token")

    output_dir_parser = argparse.ArgumentParser(add_help=False)
    output_dir_parser.add_argument("--output-dir", required=True, metavar="path", type=Path, help="Output directory")

    subparsers = parser.add_subparsers(dest="command", required=True)

    export_definitions_subparser = subparsers.add_parser(
            "export-definitions", parents=[common_parser, output_dir_parser])
    export_definitions_subparser.set_defaults(func=export_definitions)

    import_definitions_subparser = subparsers.add_parser("import-definitions", parents=[common_parser])
    import_definitions_subparser.add_argument(
            "--input-dir", required=True, metavar="path", type=Path, help="Input directory")
    import_definitions_subparser.set_defaults(func=import_definitions)

    export_contents_subparser = subparsers.add_parser("export-contents", parents=[common_parser, output_dir_parser])
    export_contents_subparser.add_argument(
            "--format", dest="report_format", metavar="format", required=True, choices=["pdf", "json", "csv"])
    export_contents_subparser.set_defaults(func=export_contents)

    args = parser.parse_args()
    args.func(**vars(args))


if __name__ == "__main__":
    main()
