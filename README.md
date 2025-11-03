# agent-eval

Lightweight Python CLI tool for generating incident-induced datasets and question/answer prompts to evaluate analytics agents.

## What This Does

This tool operates in two modes:

**Mode 1: Generate New Incidents** - Given a source dataset and incident configuration:
1. Calls the Manta service to generate incident variants (spikes, sustained changes, outages, ramps)
2. Generates question/answer prompts for each incident dataset to evaluate analytics agents

**Mode 2: Retrieve Existing Incidents** - Given a source dataset:
1. Retrieves all previously generated incident datasets for that source
2. Fetches the question/answer prompts for each incident dataset

## Supported Incident Types

- **instantaneous-spike-data** - Sudden spike in a measurement
- **sustained-magnitude-change-data** - Sustained change over a time period
- **data-outage-data** - Missing/zeroed data over a time period
- **value-ramp-data** - Gradual ramp up/down of values

## Prerequisites

- Rockfish account with Manta service access
- Source dataset already uploaded to Rockfish

## Quick Start

1. Create a Python virtualenv and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Create a `.env` file (or copy from `.env.example` if available) with your credentials:

```bash
ROCKFISH_API_URL=https://sunset-beach.rockfish.ai
MANTA_API_URL=https://manta.sunset-beach.rockfish.ai
ROCKFISH_API_KEY=sk_your_api_key_here
ROCKFISH_PROJECT_ID=your_project_id
ROCKFISH_ORGANIZATION_ID=your_org_id
```

3. Run the incident generator:

**Generate new incidents** (prints prompts to stdout):
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

**Example with actual dataset:**
The current content of `incidents.yaml` works with the dataset used in one of the Rockfish Data tutorials: [youtube_video_analytics.csv](https://docs.rockfish.ai/tutorials/youtube_video_analytics.csv)
```bash
# Generate new incidents
python incident-generator.py 5itvKrpZ68vi0L0VKjfGDM incidents.yaml -o prompts.yaml

# Retrieve existing incidents
python incident-generator.py 5itvKrpZ68vi0L0VKjfGDM -o prompts.yaml
```

## Key Files

- [incident-generator.py](incident-generator.py) - Main CLI script (~175 lines)
- [incidents.yaml](incidents.yaml) - Example incident configurations (one of each type)
- [incident-generator.md](incident-generator.md) - Detailed documentation, advanced usage, and troubleshooting

## Next Steps

- Edit [incidents.yaml](incidents.yaml) to customize incident configurations
- See [incident-generator.md](incident-generator.md) for detailed usage, parameter explanations, and troubleshooting
- Check [CLAUDE.md](CLAUDE.md) for architecture and implementation details
