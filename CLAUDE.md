# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a lightweight Python CLI tool for generating incident-induced datasets and question/answer prompts to evaluate analytics agents. The tool integrates with Rockfish (data platform) and Manta (incident generation service) APIs.

**Two Operating Modes:**
1. **Generate Mode**: Takes a source dataset and generates variants with synthetic incidents (spikes, sustained changes, outages, ramps), then generates Q&A prompts
2. **Retrieve Mode**: Retrieves all previously generated incident datasets for a source dataset and their associated prompts

## Core Architecture

**Single-file CLI application**: [incident-generator.py](incident-generator.py) (~320 lines)
- Handles all API interactions with Rockfish and Manta services
- Two modes: generate new incidents (with config file) or retrieve existing (without config file)
- Outputs generated prompts to stdout and optionally appends to a file
- Uses custom YAML dumper (`_BlockStrDumper`) to format multiline strings as block scalars (|) for readability

**Incident configuration**: [incidents.yaml](incidents.yaml)
- YAML file defining incidents to generate (only required for generate mode)
- Each entry has a `type` (one of four incident endpoints) and `configuration` object
- Configuration parameters vary by incident type but commonly include:
  - `impacted_measurement`: which metric to affect (e.g., "views", "likes", "comments")
  - `impacted_metadata_predicate`: list of column_name/value pairs to filter which rows are affected
  - `timestamp_column`: name of the timestamp column in the dataset
  - Magnitude and timing parameters specific to each incident type

**API Integration Patterns**:
- All API calls require three custom headers: `X-API-Key`, `X-Project-ID`, `X-Organization-ID`
- Header format: `X-API-Key: Bearer {api_key}` (note the "Bearer " prefix)

**Generate Mode** (two-step process per incident):
1. POST to `{MANTA_API_URL}/{incident-type}` with dataset_id and incident_config → returns new incident dataset_id
2. POST to `{MANTA_API_URL}/prompts` with incident dataset_id → returns generated Q&A prompts
3. GET from `{MANTA_API_URL}/prompts?dataset_id={incident_dataset_id}` → retrieves prompts for display/saving

**Retrieve Mode** (two-step process):
1. POST to `{MANTA_API_URL}/incident-dataset-ids` with dataset_id → returns list of incident dataset IDs
2. GET from `{MANTA_API_URL}/prompts?dataset_id={incident_dataset_id}` for each → retrieves existing prompts

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

**Retrieve existing incident datasets** (no config file):
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

## Supported Incident Types

Four incident types correspond to Manta API endpoints:
1. `instantaneous-spike-data` - sudden spike in a measurement
2. `sustained-magnitude-change-data` - sustained change over a time period
3. `data-outage-data` - missing/zeroed data over a time period
4. `value-ramp-data` - gradual ramp up/down of values

Each type requires specific configuration fields. See [incidents.yaml](incidents.yaml) for examples of all four types.

## Key Implementation Details

**Custom YAML Formatting**: The `_BlockStrDumper` class (lines 16-26) extends `yaml.SafeDumper` to represent multiline strings with block scalar style (|) instead of escaped newlines. This makes SQL queries and long text in prompts readable in output files.

**Error Handling**: API calls use try/except with `requests.exceptions.RequestException` and print response text on failure. Missing environment variables or config files cause immediate exit with descriptive messages via `sys.exit()`.

**Output Format**: The `format_output()` function (lines 208-228) generates output with:
- Header: `# Incident dataset: {incident_dataset_id}`
- Commented incident configuration (only in generate mode)
- YAML-formatted prompts
- When `--out` is specified, this is appended to the file; otherwise printed to stdout

**Mode Detection**: The script detects which mode based on whether `config_file` argument is provided (line 253). If present, runs generate mode; if absent, runs retrieve mode.

## Testing

Dependencies include pytest (>=7.4.0) and pytest-html (>=4.0.0) in [requirements.txt](requirements.txt). The project can be integrated into CI workflows to validate generated prompts and incident datasets.

## Additional Documentation

- [README.md](README.md) - Quick start guide and prerequisites
- [incident-generator.md](incident-generator.md) - Detailed parameter documentation, API details, and troubleshooting
