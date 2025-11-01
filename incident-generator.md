# incident-generator - Detailed Documentation

This document provides detailed usage instructions, configuration examples, and troubleshooting for the incident generator CLI tool.

For quick start instructions, see [README.md](README.md).

## Overview

The `incident-generator.py` script is a compact CLI wrapper (~175 lines) that:
- Takes a source dataset ID and incident configurations
- Calls Manta API endpoints to generate incident variants
- Requests question/answer prompts for each generated incident dataset
- Outputs prompts to stdout and optionally appends to a YAML file

This tool complements the more verbose `data_generator.py` prototype which includes plotting and data exploration features.

## Command-Line Usage

```bash
python incident-generator.py <dataset-id> <incidents-config.yaml> [--out OUTPUT.yaml]
```

### Parameters

- **`<dataset-id>`** (required): ID of the source dataset already uploaded to Rockfish/Manta
- **`<incidents-config.yaml>`** (required): YAML file listing incidents to generate
- **`--out` / `-o`** (optional): File path to append generated prompts in YAML format

### Behavior

- Prompts are **always** printed to stdout
- When `--out` is specified, prompts are **also** appended to the file with headers
- Each incident generates a new dataset ID and a set of Q&A prompts

### Example Output Format

When using `--out`, the file receives blocks like:

```yaml
# Incident dataset: abc123xyz
prompts:
  - question: "What was the peak value during the spike?"
    answer: "The peak value reached 1250 at 2024-01-15 14:30:00"
  # ... more prompts
```

## Incident Configuration File

The [incidents.yaml](incidents.yaml) file in this repository demonstrates all four supported incident types. Each entry requires:

- **`type`**: One of four Manta API endpoints (see below)
- **`configuration`**: Object with incident-specific parameters

### Supported Incident Types

#### 1. instantaneous-spike-data

Generates a sudden spike in measurements at a specific timestamp.

**Configuration parameters:**
- `absolute_magnitude` (float): The spike value
- `timestamp` (ISO 8601 string): When the spike occurs
- `predicate` (SQL WHERE clause): Which rows to affect

#### 2. sustained-magnitude-change-data

Creates a sustained change in values over a time period.

**Configuration parameters:**
- `delta_magnitude` (float): Amount to change values by
- `start_timestamp` (ISO 8601 string): When change begins
- `end_timestamp` (ISO 8601 string): When change ends
- `predicate` (SQL WHERE clause): Which rows to affect

#### 3. data-outage-data

Simulates missing or zeroed data over a time period.

**Configuration parameters:**
- `start_timestamp` (ISO 8601 string): When outage begins
- `end_timestamp` (ISO 8601 string): When outage ends
- `predicate` (SQL WHERE clause): Which rows to affect

#### 4. value-ramp-data

Creates a gradual ramp up or down of values.

**Configuration parameters:**
- `start_magnitude` (float): Starting value
- `end_magnitude` (float): Ending value
- `start_timestamp` (ISO 8601 string): When ramp begins
- `end_timestamp` (ISO 8601 string): When ramp ends
- `predicate` (SQL WHERE clause): Which rows to affect

### Example incidents.yaml Structure

```yaml
incidents:
  - type: instantaneous-spike-data
    configuration:
      absolute_magnitude: 1000000
      timestamp: "2024-01-15T14:30:00Z"
      predicate: "channel_id = 'UC123'"

  - type: sustained-magnitude-change-data
    configuration:
      delta_magnitude: 5000
      start_timestamp: "2024-01-20T00:00:00Z"
      end_timestamp: "2024-01-22T00:00:00Z"
      predicate: "channel_id = 'UC456'"
```

## API Integration Details

The script uses a two-step process for each incident:

1. **Create Incident Dataset**
   - POST to `{MANTA_API_URL}/{incident-type}`
   - Body: `{"dataset_id": "...", "incident_config": {...}}`
   - Returns: New incident dataset ID

2. **Generate Prompts**
   - POST to `{MANTA_API_URL}/prompts`
   - Body: `{"dataset_id": "<incident_dataset_id>"}`
   - Returns: Array of question/answer prompt objects

All API calls require three custom headers:
- `X-API-Key`: Your Rockfish API key
- `X-Project-ID`: Your Rockfish project ID
- `X-Organization-ID`: Your Rockfish organization ID

## Output Formatting

The script uses a custom YAML dumper (`_BlockStrDumper`) that formats multiline strings with block scalar style (`|`) instead of escaped newlines. This makes SQL queries and long text in prompts more readable in output files.

## Troubleshooting

### Authentication Errors (401/403)

Check your `.env` file contains the correct:
- `ROCKFISH_API_KEY` - Must be a valid API key (starts with `sk_`)
- `ROCKFISH_PROJECT_ID` - Your project ID
- `ROCKFISH_ORGANIZATION_ID` - Your organization ID

Verify the Manta and Rockfish endpoints are reachable from your environment.

### Missing Dependencies

Re-run inside the activated virtualenv:
```bash
pip install -r requirements.txt
```

### Dataset Not Found (404)

Ensure the dataset ID you're using is:
- Already uploaded to your Rockfish account
- Accessible from your project/organization
- Spelled correctly (dataset IDs are case-sensitive)

### Invalid Incident Configuration

Check that your `incidents.yaml`:
- Has correct `type` values (must match one of the four endpoints exactly)
- Includes all required `configuration` fields for each incident type
- Uses valid ISO 8601 timestamp format: `YYYY-MM-DDTHH:MM:SSZ`
- Has valid SQL predicates (test them in your dataset first)

### Getting Help

When requesting support, include:
- The complete error message
- Your dataset ID
- The incident configuration that failed
- Request/response details if available

## Related Files

- [README.md](README.md) - Quick start guide
- [incidents.yaml](incidents.yaml) - Example configurations
- [CLAUDE.md](CLAUDE.md) - Architecture and implementation details
- `data_generator.py` - Verbose prototype with plotting capabilities
