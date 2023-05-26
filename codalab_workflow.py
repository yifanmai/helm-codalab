import os
import logging
from tqdm import tqdm
from typing import Any, Callable, Iterable, Dict

from codalab.lib.bundle_cli import BundleCLI
from codalab.lib.codalab_manager import CodaLabManager
from codalab.common import NotFoundError as CodaLabNotFoundError
from helm.benchmark.presentation.run_entry import RunEntry, RunEntries, read_run_entries
from helm.benchmark.run import run_entries_to_run_specs
from helm.benchmark.scenarios.scenario import create_scenario


# helm-run --suite v1 --max-eval-instances 10 --run-specs "mmlu:subject=philosophy,model=huggingface/gpt2"

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())
logging.basicConfig(format='%(asctime)s %(message)s %(pathname)s %(lineno)d')


WORKSHEET_NAME = "agaut-helm-dev-v10"

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
    
    def _make_private(self):
        """Ensure public can not read worksheets or bundles on worksheet.
        """
        self._cli.do_command(["wperm", WORKSHEET_NAME, "public", "none"])
    
    def _make_public(self):
        """Ensure public has read permsissions on worksheet.
        """
        self._cli.do_command(["wperm", WORKSHEET_NAME, "public", "read"])
    
    def _make_bundle_private(self, bundle_name):
        """Ensure public has no read permissions on bundle.
        """
        self._cli.do_command(["perm", bundle_name, "public", "none"])

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

    def _soft_delete_bundle(self, name: str, reason: str) -> None:
        if name not in self._bundle_states:
            raise Exception(f"Could not find bundle {name}")
        self._cli.do_command(["edit", "-n", f"_{reason}_{name}", f"{name}"])
        self._refresh_bundle_states()
    
    def wait_on_bundle(self, name: str):
        self._cli.do_command(['wait', name])

    def upsert_bundle(self, name: str, args: Iterable[str], private: bool = False) -> None:
        """Insert or update bundle.
        Args:
            name: Name of bundle.
            args: The command to be run by the bundle CLI.
            private: If True, set worksheet to private, upload bundle, make bundle private,
                then set worksheet back to public.
        """
        if private: self._make_private()

        if name in self._bundle_states:
            if self._bundle_states[name] in HEALTHY_STATES:
                return
            self._soft_delete_bundle(name, reason="failed")

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

        if private:
            self._make_bundle_private(name)
            self._make_public()

def format_bundle_name(description: str) -> str:
    return f"{description.replace('/', '_').replace(':', '_').replace('=', '_').replace(',', '_')}"

def parse_run_entry_files(dir_path: str = "run_specs", selection_criteria: Callable[[RunEntry], bool] = lambda x: x.priority <= 2) -> Dict[str, str]:
    """Read run entries from file and only select those which fit selection_criteria.

    Parameters:
        dir_path: Path to the folder containing all run specs.
        selection_criteria: Return true if input run_entry should be run.

    Returns:
        A mapping from descriptions of run entries to be run in bundles to the scenarios they use.
    """
    files = [os.path.join(dir_path, f) for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))]
    logger.debug(files)

    run_entries: List[RunEntry] = read_run_entries(files).entries
    scenario_to_description: Dict[str, str] = dict()
    for run_entry in run_entries:
        if not selection_criteria(run_entry): continue
        run_spec = run_entries_to_run_specs([run_entry])[0]
        scenario_name = create_scenario(run_spec.scenario_spec).name
        args_str = ",".join([f"{k}={v}" for k, v in sorted(run_spec.scenario_spec.args.items())])
        scenario_name_with_args = f"{scenario_name}:{args_str}" if args_str else f"{scenario.name}"
        scenario_to_description[scenario_name_with_args] = run_entry.description
    return scenario_to_description
    

def main(dir_path: str = "run_specs") -> None:
    """Execute all run entries listed in directory dir_path.
    """
    logger.info("Parsing run_specs...")
    scenario_to_description = parse_run_entry_files(dir_path)

    # Create worksheet client.
    logger.info("Getting worksheet client...")
    worksheet_client = WorksheetClient(WORKSHEET_NAME)  # temporary
    worksheet_client.upsert_bundle("credentials", ["upload", "credentials"], private=True)
    worksheet_client.upsert_bundle("scripts", ["upload", "scripts"])
    worksheet_client.upsert_bundle("run_specs", ["upload", "run_specs"])
    worksheet_client.upsert_bundle(
        "venv",
        [
            "run",
            ":scripts",
            "bash scripts/install.sh && bash scripts/output_directory.sh venv",
        ],
    )

    # Cache scenarios
    logger.info("Caching scenarios...")
    scenarios_done = set()
    for scenario, description in tqdm(scenario_to_description.items()):
        scenario_bundle_name = format_bundle_name(scenario)
        if scenario_bundle_name in scenarios_done: continue
        scenarios_done.add(scenario_bundle_name)
        worksheet_client.upsert_bundle(
            scenario_bundle_name,
            [
                "run",
                ":scripts",
                ":run_specs",
                ":credentials",
                ":venv",
                f"bash scripts/cache.sh {description}",
            ],
        )

    # Evaluate models on HELM.
    # Dependency is the cached scenarios.
    logger.info("Running model evals on helm...")
    run_bundle_names = []
    for scenario, description in tqdm(scenario_to_description.items()):
        run_bundle_name = format_bundle_name(description)
        worksheet_client.upsert_bundle(
            run_bundle_name,
            [
                "run",
                ":scripts",
                ":run_specs",
                ":credentials",
                f":{format_bundle_name(scenario)}",
                ":venv",
                f"bash scripts/run.sh {description} && bash scripts/output_directory.sh benchmark_output",
            ],
        )
        run_bundle_names.append(run_bundle_name)
    
    # Summarize
    logger.info("Summarizing...")
    worksheet_client.upsert_bundle(
        "summarize",
        ["run", ":scripts", ":venv"]
        + [f":{name}" for name in run_bundle_names]
        + [
            f"bash scripts/summarize.sh && bash scripts/output_directory.sh benchmark_output"
        ],
    )

    # Soft Link
    logger.info("Soft linking...")
    worksheet_client.upsert_bundle(
        "soft_link_dev_v0",
        ["run", ":scripts", ":venv"]
        + [f":{name}" for name in run_bundle_names]
        + [
            # f"rm run_*/stderr run_*/stdout && rm -rf run_*/runs/v1/eval_cache && mkdir -p benchmark_output/runs/v1 && ln -s run_*/runs/v1/* benchmark_output/runs/v1"
            f"mkdir -p benchmark_output/runs/v1 && ln -s run_*/runs/v1/* benchmark_output/runs/v1"
        ],
    )

if __name__ == "__main__":
    main()
