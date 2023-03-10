import hashlib

from codalab.lib.bundle_cli import BundleCLI
from codalab.lib.codalab_manager import CodaLabManager
from codalab.common import NotFoundError as CodaLabNotFoundError

from typing import Any, Iterable, Dict

WORKSHEET_NAME = "yifanmai-helm-dev-v4"

MODELS = ["openai/davinci", "openai/text-davinci-002"]
SCENARIOS = ["bold", "boolq", "mmlu"]

HEALTHY_STATES = [
    "created",
    "staged",
    "starting",
    "preparing",
    "running",
    "finalizing",
    "ready",
]
FAILED_STATE = "failed"


class WorksheetClient:
    _cli: BundleCLI
    _client: Any
    _worksheet_uuid: str
    _bundle_states: Dict[str, str]

    def __init__(self, worksheet_name: str):
        self._cli = BundleCLI(CodaLabManager())
        try:
            self._client, self._worksheet_uuid = self._cli.parse_client_worksheet_uuid(
                worksheet_name
            )
        except CodaLabNotFoundError:
            self._client, self._worksheet_uuid = self._cli.parse_client_worksheet_uuid(
                ""
            )
            new_worksheet = self._client.create(
                "worksheets", data={"name": worksheet_name}
            )
            self._worksheet_uuid = new_worksheet["uuid"]
        self._cli.do_command(["work", WORKSHEET_NAME])
        self._refresh_bundle_states()

    def _refresh_bundle_states(self) -> None:
        self._bundle_states = {}
        worksheet_info = self._client.fetch(
            "worksheets",
            self._worksheet_uuid,
            params={
                "include": [
                    "items",
                    "items.bundle",
                ]
            },
        )
        bundles = [
            item["bundle"]
            for item in worksheet_info["items"]
            if item["type"] == "bundle"
        ]
        for bundle in bundles:
            bundle_name = bundle["metadata"]["name"]
            if bundle_name in self._bundle_states:
                raise Exception(f"Found more than one bundles with name {bundle_name}")
            bundle_state = bundle["state"]
            self._bundle_states[bundle_name] = bundle_state

    def soft_delete_bundle(self, name: str, reason: str) -> None:
        if name not in self._bundle_states:
            raise Exception(f"Could not find bundle {name}")
        self._cli.do_command(["cl", "edit", "-n", f"_{reason}_name", f":{name}"])

    def upsert_bundle(self, name: str, args: Iterable[str]) -> None:
        if name in self._bundle_states:
            if self._bundle_states[name] in HEALTHY_STATES:
                return
            self._refresh_bundle_states(name, reason="failed")

        if "-n" in args:
            raise Exception(
                f"Cannot specify -n flag; flag is controlled by upsert_bundle"
            )
        args = args[:1] + ["-n", name] + args[1:]
        old_bundle_names = set(self._bundle_states.keys())
        self._cli.do_command(args)
        self._refresh_bundle_states()
        new_bundle_names = set(self._bundle_states.keys())
        if len(new_bundle_names) - len(old_bundle_names) != 1:
            raise Exception(
                f"Command {args} did not result in exactly one bundle being created"
            )
        new_bundle_name = next(iter(new_bundle_names - old_bundle_names))
        if new_bundle_name != name:
            raise Exception(
                f"Expected command {args} to create a new bundle named {name}, instead it created {new_bundle_name}"
            )


def format_run_bundle_name(scenario: str, model: str):
    return f"run_{scenario}_{model.replace('/', '_')}"


def main():
    worksheet_client = WorksheetClient(WORKSHEET_NAME)
    worksheet_client.upsert_bundle("scripts", ["upload", "scripts"])
    worksheet_client.upsert_bundle("run_specs", ["upload", "run_specs"])
    worksheet_client.upsert_bundle("credentials", ["upload", "credentials"])
    worksheet_client.upsert_bundle(
        "venv",
        [
            "run",
            ":scripts",
            "bash scripts/install.sh && bash scripts/output_directory.sh venv",
        ],
    )
    run_bundle_names = []
    for scenario in SCENARIOS:
        for model in MODELS:
            run_bundle_name = format_run_bundle_name(scenario, model)
            worksheet_client.upsert_bundle(
                run_bundle_name,
                [
                    "run",
                    ":scripts",
                    ":run_specs",
                    ":credentials",
                    ":venv",
                    f"bash scripts/run.sh {scenario} {model} && bash scripts/output_directory.sh benchmark_output",
                ],
            )
            run_bundle_names.append(run_bundle_name)
    worksheet_client.upsert_bundle(
        "summarize",
        ["run", ":scripts", ":venv"]
        + [f":{name}" for name in run_bundle_names]
        + [
            f"bash scripts/summarize.sh && bash scripts/output_directory.sh benchmark_output"
        ],
    )


if __name__ == "__main__":
    main()
