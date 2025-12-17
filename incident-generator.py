#!/usr/bin/env python3

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import pyarrow.csv as pa_csv
import requests
import yaml
from dotenv import find_dotenv, load_dotenv
import rockfish as rf
from rockfish.dataset import LocalDataset
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Metadata key for incident config (matches Manta API)
INCIDENT_CONFIG_METADATA_KEY = b"incident_config"


# Custom YAML dumper that emits block style (|) for multiline strings.
# This makes embedded SQL or long text fields readable instead of escaped "\n" sequences.
class _BlockStrDumper(yaml.SafeDumper):
    pass


def _str_presenter(dumper, data):
    if isinstance(data, str) and "\n" in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)


_BlockStrDumper.add_representer(str, _str_presenter)


def load_environment() -> Dict[str, str]:
    """Load environment variables from .env file."""
    env_file = find_dotenv()
    if not env_file:
        sys.exit("Error: .env file not found. Please create one based on .env.example")
    
    load_dotenv(env_file)
    
    required_vars = [
        "ROCKFISH_API_URL",
        "MANTA_API_URL",
        "ROCKFISH_API_KEY",
        "ROCKFISH_PROJECT_ID",
        "ROCKFISH_ORGANIZATION_ID"
    ]
    
    env_vars = {}
    for var in required_vars:
        value = os.environ.get(var)
        if not value:
            sys.exit(f"Error: {var} not found in environment variables")
        env_vars[var] = value
    
    return env_vars


def get_headers(api_key: str, project_id: str, org_id: str) -> Dict[str, str]:
    """Create API headers."""
    return {
        "X-API-Key": f"Bearer {api_key}",
        "X-Project-ID": project_id,
        "X-Organization-ID": org_id,
        "Content-Type": "application/json",
    }


async def create_dataset_from_csv(csv_path: str, env: Dict[str, str]) -> str:
    """Create a Rockfish dataset from a CSV file.

    Args:
        csv_path: Path to the CSV file
        env: Dictionary of environment variables

    Returns:
        Dataset ID of the created dataset
    """
    if not os.path.exists(csv_path):
        sys.exit(f"Error: CSV file not found at {csv_path}")

    # Create a remote connection using environment variables
    conn = rf.Connection.remote(
        env["ROCKFISH_API_KEY"],
        api_url=env["ROCKFISH_API_URL"],
        project=env["ROCKFISH_PROJECT_ID"],
        organization=env["ROCKFISH_ORGANIZATION_ID"]
    )

    try:
        # Generate a dataset name from the CSV filename
        dataset_name = Path(csv_path).stem

        # Load the CSV as a LocalDataset
        local_dataset = rf.Dataset.from_csv(dataset_name, csv_path)
        print(f"Loaded CSV file: {csv_path}")
        print(f"Dataset name: {dataset_name}")
        print(f"Number of rows: {len(local_dataset.table)}")

        # Upload to Rockfish
        print("Uploading dataset to Rockfish...")
        remote_dataset = await conn.create_dataset(local_dataset)
        dataset_id = remote_dataset.id

        print(f"Created Rockfish dataset with ID: {dataset_id}")
        return dataset_id
    finally:
        await conn.close()


async def download_dataset_as_csv(dataset_id: str, output_path: str, env: Dict[str, str]) -> Tuple[LocalDataset, Optional[Dict]]:
    """Download a Rockfish dataset and save it as a CSV file.

    Args:
        dataset_id: Dataset ID to download
        output_path: Path where the CSV file should be saved
        env: Dictionary of environment variables

    Returns:
        Tuple of (LocalDataset, incident_config dict or None)
    """
    # Create a remote connection using environment variables
    conn = rf.Connection.remote(
        env["ROCKFISH_API_KEY"],
        api_url=env["ROCKFISH_API_URL"],
        project=env["ROCKFISH_PROJECT_ID"],
        organization=env["ROCKFISH_ORGANIZATION_ID"]
    )

    try:
        # Get the remote dataset
        remote_dataset = await rf.Dataset.from_id(conn, dataset_id)

        # Convert to local dataset
        print(f"Downloading dataset {dataset_id}...")
        local_dataset = await remote_dataset.to_local(conn)

        # Extract incident config if present
        incident_config = None
        try:
            # Extract pattern_type from remote dataset labels
            pattern_type = remote_dataset.metadata.get("labels", {}).get("pattern_type")

            if pattern_type:
                # Map pattern_type to incident type name
                pattern_type_map = {
                    "InstantaneousSpike": "instantaneous-spike-data",
                    "SustainedMagnitudeChange": "sustained-magnitude-change-data",
                    "DataOutage": "data-outage-data",
                    "ValueRamp": "value-ramp-data"
                }
                incident_type = pattern_type_map.get(pattern_type)

                if incident_type:
                    # Extract incident config from schema metadata
                    schema_metadata = local_dataset.table.schema.metadata
                    if schema_metadata and INCIDENT_CONFIG_METADATA_KEY in schema_metadata:
                        config_json = schema_metadata[INCIDENT_CONFIG_METADATA_KEY].decode()
                        config_data = json.loads(config_json)

                        incident_config = {
                            "type": incident_type,
                            "configuration": config_data
                        }
        except Exception as e:
            print(f"Warning: Could not extract incident config: {e}")

        # Save as CSV
        pa_csv.write_csv(local_dataset.table, output_path)
        print(f"Saved dataset to: {output_path}")

        return local_dataset, incident_config
    finally:
        await conn.close()


def create_incident_comparison_plot(
    original_dataset: LocalDataset,
    incident_dataset: LocalDataset,
    incident_config: Dict,
    output_path: str
) -> None:
    """Create before/after comparison plots for incident datasets.

    Args:
        original_dataset: The original source dataset
        incident_dataset: The dataset with incidents injected
        incident_config: Configuration of the incident
        output_path: Path where the plot should be saved
    """
    # Convert to pandas for easier plotting
    original_df = original_dataset.to_pandas()
    incident_df = incident_dataset.to_pandas()

    # Identify timestamp column and impacted measurement
    incident_type = incident_config.get("type", "unknown")
    config = incident_config.get("configuration", {})
    timestamp_col = config.get("timestamp_column", "timestamp")
    impacted_measurement = config.get("impacted_measurement")
    metadata_predicate = config.get("impacted_metadata_predicate", [])

    # Apply metadata predicate filter if present
    if metadata_predicate:
        for predicate in metadata_predicate:
            column_name = predicate.get("column_name")
            value = predicate.get("value")
            if column_name and column_name in original_df.columns:
                original_df = original_df[original_df[column_name] == value]
                incident_df = incident_df[incident_df[column_name] == value]

        if len(original_df) == 0:
            print(f"Warning: No data matching metadata predicate for plotting")
            return

    # If no timestamp or measurement specified, try to infer
    if not timestamp_col or timestamp_col not in original_df.columns:
        # Try common timestamp column names
        for col in ["timestamp", "date", "time", "datetime", "ts"]:
            if col in original_df.columns:
                timestamp_col = col
                break

    if not impacted_measurement:
        # Try to find numeric columns that aren't metadata
        numeric_cols = original_df.select_dtypes(include=['number']).columns.tolist()
        if numeric_cols:
            impacted_measurement = numeric_cols[0]

    if not timestamp_col or not impacted_measurement:
        print(f"Warning: Could not determine timestamp or measurement columns for plotting")
        return

    if timestamp_col not in original_df.columns or impacted_measurement not in incident_df.columns:
        print(f"Warning: Required columns not found in datasets for plotting")
        return

    # Convert timestamp to datetime if needed
    try:
        original_df[timestamp_col] = pd.to_datetime(original_df[timestamp_col])
        incident_df[timestamp_col] = pd.to_datetime(incident_df[timestamp_col])
    except Exception as e:
        print(f"Warning: Could not convert timestamp column to datetime: {e}")
        return

    # Sort by timestamp
    original_df = original_df.sort_values(timestamp_col)
    incident_df = incident_df.sort_values(timestamp_col)

    # Create the plot
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    # Create title suffix if filtered
    filter_suffix = ""
    if metadata_predicate:
        filter_parts = [f"{p.get('column_name')}={p.get('value')}" for p in metadata_predicate]
        filter_suffix = f" (Filtered: {', '.join(filter_parts)})"

    # Plot original data
    ax1.plot(original_df[timestamp_col], original_df[impacted_measurement],
             label='Original', color='blue', linewidth=1.5)
    ax1.set_ylabel(impacted_measurement, fontsize=10)
    ax1.set_title(f'Original Dataset{filter_suffix}', fontsize=12, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    # Plot incident data
    ax2.plot(incident_df[timestamp_col], incident_df[impacted_measurement],
             label='With Incident', color='red', linewidth=1.5)
    ax2.set_ylabel(impacted_measurement, fontsize=10)
    ax2.set_xlabel('Time', fontsize=10)
    ax2.set_title(f'Incident Dataset ({incident_type}){filter_suffix}', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.legend()

    # Format x-axis
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"Saved comparison plot to: {output_path}")


def create_incident_data(manta_url: str, headers: Dict[str, str], dataset_id: str, 
                        incident_type: str, incident_config: Dict) -> Optional[Dict]:
    """Create incident data using Manta API."""
    url = f"{manta_url}/{incident_type}"
    payload = {"dataset_id": dataset_id, "incident_config": incident_config}

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error creating incident data: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"Response: {e.response.text}")
        return None


def create_prompts(manta_url: str, headers: Dict[str, str], dataset_id: str) -> Optional[Dict]:
    """Create prompts for a dataset using Manta API."""
    url = f"{manta_url}/prompts"
    payload = {"dataset_id": dataset_id}
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error creating prompts: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"Response: {e.response.text}")
        return None


def load_incidents_config(config_file: str) -> List[Dict]:
    """Load incidents configuration from YAML file."""
    try:
        with open(config_file, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        sys.exit(f"Error loading incidents configuration file: {e}")


def generate_prompts(manta_url: str, headers: Dict[str, str], dataset_id: str,
                    incidents: List[Dict]) -> List[Tuple[str, Dict]]:
    """Generate incident datasets and prompts for each incident configuration.

    Args:
        manta_url: Base URL for Manta API
        headers: API headers for authentication
        dataset_id: Source dataset ID
        incidents: List of incident configurations

    Returns:
        List of tuples containing (incident_dataset_id, incident_config)
    """
    incident_results = []

    # Process each incident
    for incident in incidents:
        incident_type = incident["type"]
        config = incident["configuration"]

        print(f"\nProcessing incident type: {incident_type}")

        # Create incident dataset
        response = create_incident_data(
            manta_url,
            headers,
            dataset_id,
            incident_type,
            config
        )

        if response:
            incident_dataset_id = response['dataset_id']
            # Store both the dataset ID and the full incident configuration
            incident_results.append((incident_dataset_id, incident))
            print(f"Created incident dataset: {incident_dataset_id}")

            # Generate prompts for the incident dataset
            prompt_response = create_prompts(
                manta_url,
                headers,
                incident_dataset_id
            )

            if prompt_response:
                print("Generated prompts (YAML)")

    return incident_results


def retrieve_incident_dataset_ids(manta_url: str, headers: Dict[str, str], dataset_id: str) -> Optional[List[str]]:
    """Retrieve list of incident dataset IDs for a given dataset using Manta API.

    Args:
        manta_url: Base URL for Manta API
        headers: API headers for authentication
        dataset_id: Source dataset ID to get incident datasets for

    Returns:
        List of incident dataset IDs or None if request fails
    """
    url = f"{manta_url}/incident-dataset-ids"
    payload = {"dataset_id": dataset_id}

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("dataset_ids", [])
    except requests.exceptions.RequestException as e:
        print(f"Error retrieving incident dataset IDs: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"Response: {e.response.text}")
        return None


def retrieve_prompts(manta_url: str, headers: Dict[str, str], dataset_id: str) -> Optional[Dict]:
    """Retrieve prompts for a dataset using Manta GET API.

    Args:
        manta_url: Base URL for Manta API
        headers: API headers for authentication
        dataset_id: Dataset ID to retrieve prompts for

    Returns:
        Dictionary containing prompts data or None if request fails
    """
    url = f"{manta_url}/prompts"
    params = {"dataset_id": dataset_id}

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error retrieving prompts: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"Response: {e.response.text}")
        return None


def format_output(dataset_id: str, incident_config: Dict, prompts: Dict) -> str:
    """Format incident dataset output with configuration and prompts in YAML.

    Args:
        dataset_id: The incident dataset ID
        incident_config: The incident configuration dictionary (can be empty in retrieve mode)
        prompts: The prompts dictionary

    Returns:
        Formatted string with dataset ID, incident config as comments (if present), and prompts
    """
    output = f"# Incident dataset: {dataset_id}\n"

    if incident_config:
        output += "# Incident configuration:\n"
        incident_yaml = yaml.dump(incident_config, Dumper=_BlockStrDumper, sort_keys=False, default_flow_style=False)
        for line in incident_yaml.split('\n'):
            if line:
                output += f"# {line}\n"
        output += "\n"

    prompts_yaml = yaml.dump(prompts, Dumper=_BlockStrDumper, sort_keys=False, default_flow_style=False)
    output += prompts_yaml
    return output


async def main():
    parser = argparse.ArgumentParser(
        description="Generate incident datasets and prompts, or retrieve existing incident datasets",
        epilog="Use --csv with --incident-config to generate new incidents, or use --dataset-id to retrieve existing incidents."
    )
    parser.add_argument("--csv", help="Path to CSV file (will create a new dataset in Rockfish). Required for generate mode.")
    parser.add_argument("--dataset-id", help="Existing dataset ID to retrieve incidents from. Required for retrieve mode.")
    parser.add_argument("--incident-config", help="Path to incidents configuration YAML file. Required for generate mode (use with --csv).")
    parser.add_argument("--out", "-o", help="Path to output file to write prompts (YAML). If provided, prompts will be appended.")
    parser.add_argument("--download-incidents", help="Directory path to save incident datasets as CSV files (optional)")
    args = parser.parse_args()

    # Validate argument combinations
    if args.incident_config and not args.csv:
        sys.exit("Error: --incident-config requires --csv (generate mode)")

    if args.csv and not args.incident_config:
        sys.exit("Error: --csv requires --incident-config (generate mode)")

    if not args.csv and not args.dataset_id:
        sys.exit("Error: Must provide either:\n  - Both --csv AND --incident-config (generate mode)\n  - Or --dataset-id (retrieve mode)")

    if args.csv and args.dataset_id:
        sys.exit("Error: Cannot use both --csv and --dataset-id together")

    # Load environment variables
    env = load_environment()

    # Determine which mode we're in
    original_dataset = None
    if args.csv and args.incident_config:
        # Generate mode: Upload CSV and create incidents
        print(f"Creating dataset from CSV file: {args.csv}")
        dataset_id = await create_dataset_from_csv(args.csv, env)

        # Keep a reference to the original dataset for plotting
        if args.download_incidents:
            original_dataset = rf.Dataset.from_csv(Path(args.csv).stem, args.csv)
    else:
        # Retrieve mode: Use existing dataset ID
        dataset_id = args.dataset_id
        print(f"Using existing dataset ID: {dataset_id}")

        # Download the original source dataset for plotting if requested
        if args.download_incidents:
            print(f"Downloading original source dataset for comparison plots...")
            try:
                original_dataset, _ = await download_dataset_as_csv(
                    dataset_id,
                    "/tmp/original_dataset.csv",  # Temporary file
                    env
                )
                print(f"Downloaded original dataset with {len(original_dataset.table)} rows")
            except Exception as e:
                print(f"Warning: Could not download original dataset: {e}")
                print("Plots will not be generated without original dataset")

    # Set up API headers
    headers = get_headers(
        env["ROCKFISH_API_KEY"],
        env["ROCKFISH_PROJECT_ID"],
        env["ROCKFISH_ORGANIZATION_ID"]
    )

    # Determine mode: generate new incidents or retrieve existing
    if args.incident_config:
        # Mode 1: Generate new incident datasets from config file
        incidents = load_incidents_config(args.incident_config)

        print(f"Generating incident datasets and prompts based on dataset {dataset_id} and {args.incident_config}")
        incident_results = generate_prompts(
            env["MANTA_API_URL"],
            headers,
            dataset_id,
            incidents
        )
    else:
        # Mode 2: Retrieve existing incident datasets
        print(f"Retrieving existing incident datasets for source dataset {dataset_id}")
        incident_dataset_ids = retrieve_incident_dataset_ids(
            env["MANTA_API_URL"],
            headers,
            dataset_id
        )

        if incident_dataset_ids is None:
            sys.exit("Failed to retrieve incident dataset IDs")

        if not incident_dataset_ids:
            print("No incident datasets found for this source dataset")
            return

        print(f"Found {len(incident_dataset_ids)} incident dataset(s)")
        # Create incident_results as list of lists (mutable)
        incident_results = [[incident_dataset_id, {}] for incident_dataset_id in incident_dataset_ids]

    # Download incident datasets
    if incident_results and args.download_incidents:
            print("\n" + "="*80)
            print("Downloading incident datasets")
            print("="*80)

            # Create the output directory if it doesn't exist
            output_dir = Path(args.download_incidents)
            output_dir.mkdir(parents=True, exist_ok=True)

            for i, (incident_dataset_id, incident_config) in enumerate(incident_results):
                print(f"\nDownloading incident dataset: {incident_dataset_id}")
                try:
                    temp_output_path = output_dir / f"temp_{incident_dataset_id}.csv"

                    incident_dataset, extracted_config = await download_dataset_as_csv(
                        incident_dataset_id,
                        str(temp_output_path),
                        env
                    )

                    if not incident_config and extracted_config:
                        incident_config = extracted_config
                        incident_results[i][1] = extracted_config  # Update the list
                        print(f"Extracted incident config from dataset metadata")

                    incident_type = incident_config.get("type", "unknown") if incident_config else "retrieved"
                    output_filename = f"incident_{incident_dataset_id}_{incident_type}.csv"
                    output_path = output_dir / output_filename

                    os.rename(str(temp_output_path), str(output_path))

                    # Create comparison plot if we have the original dataset
                    if original_dataset and incident_config:
                        plot_filename = f"incident_{incident_dataset_id}_{incident_type}_comparison.png"
                        plot_path = output_dir / plot_filename
                        print(f"Creating comparison plot...")
                        try:
                            create_incident_comparison_plot(
                                original_dataset,
                                incident_dataset,
                                incident_config,
                                str(plot_path)
                            )
                        except Exception as plot_error:
                            print(f"Warning: Could not create plot: {plot_error}")
                except Exception as e:
                    print(f"Error downloading dataset {incident_dataset_id}: {e}")

    # Retrieve prompts for each incident dataset
    if incident_results:
        print("\n" + "="*80)
        print("Retrieving prompts")
        print("="*80)

        for dataset_id, incident_config in incident_results:
            print(f"\nRetrieving prompts for dataset: {dataset_id}")
            retrieved_prompts = retrieve_prompts(
                env["MANTA_API_URL"],
                headers,
                dataset_id
            )

            if retrieved_prompts:
                # Format the output with incident config and prompts
                formatted_output = format_output(dataset_id, incident_config, retrieved_prompts)

                # Print to console
                print("Successfully retrieved prompts (YAML)")

                # If an output path was provided, write to file
                if args.out:
                    try:
                        with open(args.out, "a", encoding="utf-8") as fh:
                            fh.write(formatted_output)
                            fh.write("\n")
                        print(f"Wrote prompts to {args.out}")
                    except Exception as e:
                        print(f"Error writing prompts to {args.out}: {e}")
                else:
                    print(formatted_output)

if __name__ == "__main__":
    asyncio.run(main())