# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a lightweight Python CLI tool for generating incident-induced datasets and question/answer prompts to evaluate analytics agents. The tool integrates with Rockfish (data platform) and Manta (incident generation service) APIs to:

1. Take a source dataset and generate variants with synthetic incidents (spikes, sustained changes, outages, ramps)
2. Generate question/answer prompts for each incident dataset to evaluate analytics agents

## Core Architecture

**Single-file CLI application**: [incident-generator.py](incident-generator.py) (~175 lines)
- Handles all API interactions with Rockfish and Manta services
- Loads incident configurations from YAML
- Outputs generated prompts to stdout and optionally appends to a file
- Uses custom YAML dumper to format multiline strings (SQL queries, etc.) as block scalars (|) for readability

**Incident configuration**: [incidents.yaml](incidents.yaml)
- YAML file defining incidents to generate
- Each entry has a `type` (one of four incident endpoints) and `configuration` object
- Configuration parameters vary by incident type but commonly include:
  - `impacted_measurement`: which metric to affect (e.g., "views", "likes", "comments")
  - `impacted_metadata_predicate`: list of column_name/value pairs to filter which rows are affected
  - `timestamp_column`: name of the timestamp column in the dataset
  - Magnitude and timing parameters specific to each incident type

**API Integration Pattern**:
- All API calls require three custom headers: `X-API-Key`, `X-Project-ID`, `X-Organization-ID`
- Two-step process per incident:
  1. POST to `{MANTA_API_URL}/{incident-type}` with dataset_id and incident_config → returns new incident dataset_id
  2. POST to `{MANTA_API_URL}/prompts` with incident dataset_id → returns generated Q&A prompts

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

**Run incident generator** (prints to stdout):
```bash
python incident-generator.py <dataset-id> incidents.yaml
```

**Run and save prompts to file**:
```bash
python incident-generator.py <dataset-id> incidents.yaml --out prompts.yaml
```

**Example with actual dataset**:
```bash
python incident-generator.py 5itvKrpZ68vi0L0VKjfGDM incidents.yaml -o prompts.yaml
```

## Supported Incident Types

Four incident types correspond to Manta API endpoints:
1. `instantaneous-spike-data` - sudden spike in a measurement
2. `sustained-magnitude-change-data` - sustained change over a time period
3. `data-outage-data` - missing/zeroed data over a time period
4. `value-ramp-data` - gradual ramp up/down of values

Each type requires specific configuration fields. See [incidents.yaml](incidents.yaml) for examples of all four types.

## Key Implementation Details

**Custom YAML Formatting**: The `_BlockStrDumper` class extends `yaml.SafeDumper` to represent multiline strings with block scalar style (|) instead of escaped newlines. This makes SQL queries and long text in prompts readable in output files.

**Error Handling**: API calls use try/except with `requests.exceptions.RequestException` and print response text on failure. Missing environment variables or config files cause immediate exit with descriptive messages.

**Output Format**: When `--out` is specified, prompts are appended to the file with a header comment `# Incident dataset: {incident_dataset_id}` followed by the YAML-formatted prompts.

## Data Files

- `youtube_video_analytics.csv` - Example source dataset (1.9 MB, ~20K rows)
- Datasets must be pre-uploaded to Rockfish before running the incident generator

## Additional Documentation

- [README.md](README.md) - Quick start guide and prerequisites
- [incident-generator.md](incident-generator.md) - Detailed parameter documentation and troubleshooting

## Testing & CI Integration

This demo can be straightforwardly integrated into a CI workflow using pytest to validate generated prompts and incident datasets.
