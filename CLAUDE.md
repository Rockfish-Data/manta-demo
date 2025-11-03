# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a lightweight Python CLI tool for generating incident-induced datasets and question/answer prompts to evaluate analytics agents. The tool integrates with Rockfish (data platform) and Manta (incident generation service) APIs to:

1. Take a source dataset and generate variants with synthetic incidents (spikes, sustained changes, outages, ramps)
2. Generate question/answer prompts for each incident dataset to evaluate analytics agents

## Core Architecture

**Single-file CLI application**: [incident-generator.py](incident-generator.py) (~320 lines)
- Operates in two modes: generate new incidents OR retrieve existing incident datasets
- Handles all API interactions with Rockfish and Manta services
- Loads incident configurations from YAML (Mode 1 only)
- Outputs generated prompts to stdout and optionally appends to a file
- Uses custom YAML dumper (`_BlockStrDumper`) to format multiline strings (SQL queries, etc.) as block scalars (|) for readability

**Incident configuration**: [incidents.yaml](incidents.yaml)
- YAML file defining incidents to generate (required only for Mode 1)
- Top-level is a list, each entry has a `type` (one of four incident endpoints) and `configuration` object
- Configuration parameters vary by incident type but commonly include:
  - `impacted_measurement`: which metric to affect (e.g., "views", "likes", "comments")
  - `impacted_metadata_predicate`: list of objects with `column_name` and `value` fields to filter which rows are affected
  - `timestamp_column`: name of the timestamp column in the dataset
  - Magnitude and timing parameters specific to each incident type (see incidents.yaml for examples)

**Dual-Mode Operation**:

*Mode 1 - Generate New Incidents*:
- Invoked when config file is provided: `python incident-generator.py <dataset-id> incidents.yaml`
- Two-step process per incident:
  1. POST to `{MANTA_API_URL}/{incident-type}` with dataset_id and incident_config → returns new incident dataset_id
  2. POST to `{MANTA_API_URL}/prompts` with incident dataset_id → generates Q&A prompts
  3. GET from `{MANTA_API_URL}/prompts?dataset_id={incident_dataset_id}` → retrieves generated prompts

*Mode 2 - Retrieve Existing Incidents*:
- Invoked when NO config file provided: `python incident-generator.py <dataset-id>`
- Two-step process:
  1. POST to `{MANTA_API_URL}/incident-dataset-ids` with dataset_id → returns list of incident dataset IDs
  2. GET from `{MANTA_API_URL}/prompts?dataset_id={incident_dataset_id}` for each → retrieves prompts

**API Authentication**:
- All API calls require three custom headers: `X-API-Key` (with "Bearer " prefix), `X-Project-ID`, `X-Organization-ID`

## Environment Setup

Required environment variables (in `.env`):
```
ROCKFISH_API_URL=https://sunset-beach.rockfish.ai
MANTA_API_URL=https://manta.sunset-beach.rockfish.ai
ROCKFISH_API_KEY=<your_key>
ROCKFISH_PROJECT_ID=<your_project>
ROCKFISH_ORGANIZATION_ID=<your_org>
```

Setup virtualenv and dependencies:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Common Commands

**Generate new incidents** (prints to stdout):
```bash
python incident-generator.py <dataset-id> incidents.yaml
```

**Generate and save prompts to file**:
```bash
python incident-generator.py <dataset-id> incidents.yaml --out prompts.yaml
```

**Retrieve existing incident datasets** (no config file needed):
```bash
python incident-generator.py <dataset-id>
```

**Retrieve and save to file**:
```bash
python incident-generator.py <dataset-id> --out prompts.yaml
```

**Example with actual dataset** (youtube_video_analytics.csv from Rockfish tutorials):
```bash
# Generate new incidents
python incident-generator.py 5itvKrpZ68vi0L0VKjfGDM incidents.yaml -o prompts.yaml

# Retrieve existing incidents
python incident-generator.py 5itvKrpZ68vi0L0VKjfGDM -o prompts.yaml
```

**Run tests** (if available):
```bash
pytest
```

## Supported Incident Types

Four incident types correspond to Manta API endpoints:
1. `instantaneous-spike-data` - sudden spike in a measurement
2. `sustained-magnitude-change-data` - sustained change over a time period
3. `data-outage-data` - missing/zeroed data over a time period
4. `value-ramp-data` - gradual ramp up/down of values

Each type requires specific configuration fields. See [incidents.yaml](incidents.yaml) for examples of all four types.

## Key Implementation Details

**Custom YAML Formatting**: The `_BlockStrDumper` class (incident-generator.py:16-26) extends `yaml.SafeDumper` to represent multiline strings with block scalar style (|) instead of escaped newlines. This makes SQL queries and long text in prompts readable in output files.

**Error Handling**: API calls use try/except with `requests.exceptions.RequestException` and print response text on failure. Missing environment variables or config files cause immediate exit with descriptive messages.

**Output Format**: When `--out` is specified, prompts are appended to the file with:
- Header comment: `# Incident dataset: {incident_dataset_id}`
- Incident configuration as comments (Mode 1 only)
- YAML-formatted prompts

**Key Functions**:
- `generate_prompts()` - Mode 1: Creates new incident datasets and generates prompts
- `retrieve_incident_dataset_ids()` - Mode 2: Fetches existing incident dataset IDs
- `retrieve_prompts()` - Both modes: GET request to fetch prompts for a dataset
- `format_output()` - Formats output with dataset ID, config, and prompts

## Data Files

- Example dataset: [youtube_video_analytics.csv](https://docs.rockfish.ai/tutorials/youtube_video_analytics.csv) from Rockfish tutorials
- Datasets must be pre-uploaded to Rockfish before running the incident generator
- `prompts.yaml` - Output file containing generated prompts (when using `--out` flag)

## Additional Documentation

- [README.md](README.md) - Quick start guide and prerequisites
- [incident-generator.md](incident-generator.md) - Detailed parameter documentation and troubleshooting

## Testing & CI Integration

This demo can be straightforwardly integrated into a CI workflow using pytest to validate generated prompts and incident datasets.
