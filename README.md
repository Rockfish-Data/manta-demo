# agent-eval

Lightweight Python CLI tool for generating incident-induced datasets and question/answer prompts to evaluate analytics agents.

## What This Does

This tool operates in two modes:

**Mode 1: Generate New Incidents** - Given a CSV file and incident configuration:
1. Uploads the CSV to Rockfish to create a source dataset
2. Calls the Manta service to generate incident variants (spikes, sustained changes, outages, ramps)
3. Generates question/answer prompts for each incident dataset to evaluate analytics agents
4. Optionally downloads incident datasets as CSV files with before/after visualization plots

**Mode 2: Retrieve Existing Incidents** - Given an existing dataset ID:
1. Retrieves all previously generated incident datasets for that source
2. Fetches the question/answer prompts for each incident dataset
3. Optionally downloads incident datasets as CSV files with before/after visualization plots

## Supported Incident Types

- **instantaneous-spike-data** - Sudden spike in a measurement
- **sustained-magnitude-change-data** - Sustained change over a time period
- **data-outage-data** - Missing/zeroed data over a time period
- **value-ramp-data** - Gradual ramp up/down of values

## Prerequisites

- Rockfish account with Manta service access
- CSV file for generate mode, or existing dataset ID for retrieve mode

## Quick Start

1. Create a Python virtualenv and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -U 'rockfish[labs]' -f 'https://packages.rockfish.ai'
```

2. Create a `.env` file with your credentials:

```bash
ROCKFISH_API_URL=https://otter-shores.rockfish.ai
MANTA_API_URL=https://manta.otter-shores.rockfish.ai
ROCKFISH_API_KEY=sk_your_api_key_here
ROCKFISH_PROJECT_ID=your_project_id
ROCKFISH_ORGANIZATION_ID=your_org_id
```

3. Run the incident generator:

### Mode 1: Generate New Incidents

**Basic usage** (generates incidents, prints prompts to stdout):
```bash
python incident-generator.py --csv data.csv --incident-config incidents.yaml
```

**Save prompts to file**:
```bash
python incident-generator.py --csv data.csv --incident-config incidents.yaml --out prompts.yaml
```

**Download incident datasets and create visualization plots**:
```bash
python incident-generator.py --csv data.csv --incident-config incidents.yaml --out prompts.yaml --download-incidents ./outputs
```
This creates:
- `./outputs/incident_<id>_<type>.csv` - Incident dataset CSV files
- `./outputs/incident_<id>_<type>_comparison.png` - Before/after comparison plots

### Mode 2: Retrieve Existing Incidents

**Retrieve from existing dataset** (requires dataset ID):
```bash
python incident-generator.py --dataset-id <your-dataset-id> --out prompts.yaml
```

**Retrieve and download incident datasets**:
```bash
python incident-generator.py --dataset-id <your-dataset-id> --out prompts.yaml --download-incidents ./outputs
```

### Example with Tutorial Dataset

The current content of `incidents.yaml` works with the dataset from the Rockfish Data tutorials: [youtube_video_analytics.csv](https://docs.rockfish.ai/tutorials/youtube_video_analytics.csv)

```bash
# Download the sample CSV
curl -O https://docs.rockfish.ai/tutorials/youtube_video_analytics.csv

# Generate new incidents with visualizations
python incident-generator.py \
  --csv youtube_video_analytics.csv \
  --incident-config incidents.yaml \
  --out prompts.yaml \
  --download-incidents ./outputs

# Later, retrieve existing incidents for that dataset
python incident-generator.py \
  --dataset-id <your-dataset-id> \
  --out prompts.yaml
```

## Key Files

- [incident-generator.py](incident-generator.py) - Main CLI script (~540 lines)
  - CSV upload and dataset creation
  - Incident generation and prompt retrieval
  - Dataset download functionality
  - Automatic before/after visualization plots
- [incidents.yaml](incidents.yaml) - Example incident configurations (one of each type)

## Next Steps

- Edit [incidents.yaml](incidents.yaml) to customize incident configurations
