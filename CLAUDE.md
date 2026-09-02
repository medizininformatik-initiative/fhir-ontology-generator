# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository does

Generates the ontology used by the FDPG+ feasibility/dataportal stack: the metadata that lets researchers search for,
display, and select criteria for a **cohort** (cohort selection ontology) and for **health record items to extract**
(data selection ontology, "DSE"). Output is consumed by the `feasibility-backend`, `feasibility-gui`, and an
Elasticsearch instance in sibling repositories.

The ontology is built in stages, each historically a separate top-level module, orchestrated by
`./generate_full_ontology.sh`:

1. `cohort_selection_ontology` — generate UI trees, UI profiles, term-code-info, CQL/FHIR mappings per FHIR module
2. `data_selection_extraction` — generate the DSE profile tree + profile details
3. `ontology_merging` — merge per-module cohort ontologies and the DSE ontology into one
4. *(project-specific, e.g. `fdpg-ontology`)* — e.g. `combined_consent_generation.py` merges in consent-policy criteria
5. `elasticsearch` — convert the merged ontology into Elasticsearch input documents
6. `parceling` — package everything into `backend.zip`, `elastic.zip`, `mapping.zip` for distribution

`availability` (generates FHIR `Measure` resources describing coding/DSE-element availability) and `flattening`
(generates a lookup file) are separate side pipelines invoked independently (see `.github/actions/`).

Everything is scoped to a **project**: `projects/<project-name>/{input,output}/...`. `fdpg-ontology` is the only
project currently checked in; it also carries project-specific scripts (e.g. `combined_consent_generation.py`) and
`config.yml`.

## Repository is mid-migration — two coexisting layouts

This repo is being restructured from flat top-level Python modules into a `uv` workspace of standalone packages
under `packages/*` (see branch `472-refactor-projects-into-dedicated-repositories`, eventual goal per its name is
splitting these into their own repos). Expect both styles to coexist for a while:

- **Legacy (not yet migrated):** `cohort_selection_ontology/`, `data_selection_extraction/`, `elasticsearch/`,
  `flattening/`, `ontology_merging/`, `parceling/`, and (still present, in parallel with its migrated counterpart)
  `common/`. These import as top-level packages (`from common.util... import ...`, `from cohort_selection_ontology...`)
  and require `PYTHONPATH` set to the repo root. Their tests live under the hidden `.tests/` directory at repo root
  (mirrored by structure, e.g. `.tests/unit/<module>/...`, `.tests/integration/...`) — this is what CI actually runs.
- **Migrated:** `packages/common/` and `packages/availability/` are standalone `uv` workspace members (registered via
  `[tool.uv.workspace]` in the root `pyproject.toml`). Code lives under
  `packages/<name>/src/dataportal_generator/<name>/...` and imports as `from dataportal_generator.common... import ...`
  / `from dataportal_generator.availability... import ...`. Their tests live in `packages/<name>/tests/`. Each package
  ships a pytest plugin (`common-test`, `availability-test` entry points) exposing shared fixtures
  (`dataportal_generator.common_test.fixtures`, `dataportal_generator.availability_test.fixtures`) for reuse by other
  packages' test suites — the equivalent of the shared fixtures in `.tests/conftest.py` for the legacy suite.

When editing, check which layout the code you're touching actually lives in before assuming import paths — `common`
exists in both forms simultaneously, and CI/action YAML in `.github/` may still reference pre-migration paths (e.g.
the `availability` action references a top-level `availability/` dir that has already moved to
`packages/availability/`) that haven't been updated yet. The plain (non-dot) `tests/` directory at repo root is
currently just build/test scratch output, not a real suite.

## The `Project` abstraction

Nearly every script takes `--project <name>` and resolves it via a `Project` class (legacy:
`common/util/project/__init__.py`; migrated: `packages/common/src/dataportal_generator/common/model/project.py`) to
`projects/<name>/`. It exposes `.input` / `.output`, each of which exposes fixed subdirectories: `.cso`, `.dse`,
`.elastic`, `.availability`, `.flattening`, `.terminology`, `.translation` (plus `.output.generated_ontology` →
`merged_ontology/`). Project-level config (`projects/<name>/config.yml`, optional) is parsed into a `ProjectConfig`
pydantic model controlling things like which FHIR package manager to use.

## Commands

### Setup

```bash
pip install -r requirements.txt        # legacy top-level modules
uv sync                                 # packages/ workspace (common, availability)
```
Legacy scripts need `PYTHONPATH` set to the repo root (see `.env` / `generate_full_ontology.sh`, which sets it from
its own location). Generating snapshots requires **Firely Terminal** (`dotnet tool install -g firely.terminal`,
v3.1.0+) and access to a FHIR terminology server.

**Required env vars** for anything touching the terminology server: `ONTOLOGY_SERVER_ADDRESS`,
`SERVER_CERTIFICATE` (path to cert), `PRIVATE_KEY` (path to key). Optional: `POSTGRES_VERSION` /
`POSTGRES_BASE_IMAGE` for integration tests spinning up Postgres via `pytest-docker`.

### Generate the ontology

```bash
./generate_full_ontology.sh --project fdpg-ontology --all       # all 6 steps, wipes output dir first
./generate_full_ontology.sh --project fdpg-ontology --step 3    # single step (repeatable)
```
Individual stage scripts can also be run directly from their module dir, e.g.:
```bash
cd cohort_selection_ontology && python3 scripts/generate_ontology.py --project fdpg-ontology \
  --generate_ui_trees --generate_ui_profiles --generate_mapping
```
See `docs/DSE-README.md`, `docs/Merger-README.md`, `docs/Elastic-README.md`, `docs/Parcel-README.md` for each
stage's script options.

### Tests

```bash
# legacy suite (what CI runs)
pytest .tests/unit -v
pytest .tests/unit/common/test_fhirpath_functions.py -v          # single file
pytest .tests/unit/common/test_fhirpath_functions.py::test_name  # single test
pytest .tests/integration --project fdpg-ontology                # needs a generated ontology in projects/fdpg-ontology/output + docker

# packages/ workspace
cd packages/common && uv run pytest
cd packages/availability && uv run pytest
```
`CCTB_CLI_VERSION` and `MII_CDS_TEST_DATA_VERSION` are pinned via `pytest-env` in `pyproject.toml` (root and each
package's own `pyproject.toml`) — no need to set them manually. Integration tests spin up Docker containers
(`pytest-docker`) for things like Elasticsearch, the feasibility backend, and CQL query execution.

### Linting

`packages/*/pyproject.toml` declare `ruff` as a lint dev-dependency (`uv run ruff check`), but no lint step currently
runs in CI. `requirements.txt` includes `black`/`flake8` for the legacy code but there's no config or CI step
enforcing them either — treat both as available tools, not gated checks.

## Querying-metadata config (cohort_selection_ontology)

Ontology generation for a FHIR profile is driven by a "querying metadata" JSON config (e.g.
`resources/QueryingMetaData/<Module>/*.json`), matched to a downloaded/generated snapshot by filename via
`resources/profile_to_query_meta_data_resolver_mapping.json`. Key fields, each an element ID (FHIR path) resolved
against the snapshot:
- `term_code_defining_id` — identifies/generates the criterion itself (required)
- `value_defining_id` — the criterion's main filterable value, if any (CodeableConcept/Coding → value-set lookup;
  Quantity → unit taken from the differential)
- `attribute_defining_id_type_map` — additional filterable attributes; entries can be typed `reference`, in which
  case the id uses a `((...).value[x])...` bracket syntax pointing at where the reference target (e.g. an extension)
  is resolved and which value-set/slice it must belong to
- `time_restriction_defining_id` — element defining the time-restriction filter

New modules are added by: downloading profile snapshots from simplifier.net, writing a differential referencing the
snapshot's `baseDefinition`, adding required packages to `resources/required_packages.json`, generating snapshots
(`--generate_snapshot`), writing the querying-metadata config, then running `--generate_ui_trees
--generate_ui_profiles --generate_mapping`. Full walkthrough in the README's "step-by-step guide to a new ontology".
