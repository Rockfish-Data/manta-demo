#!/usr/bin/env python3

import argparse
import json
import os
import sys
from typing import Dict, List, Optional, Tuple

import requests
import yaml
from dotenv import find_dotenv, load_dotenv


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
        incident_config: The incident configuration dictionary
        prompts: The prompts dictionary

    Returns:
        Formatted string with dataset ID, incident config as comments, and prompts
    """
    output = f"# Incident dataset: {dataset_id}\n"
    output += "# Incident configuration:\n"
    incident_yaml = yaml.dump(incident_config, Dumper=_BlockStrDumper, sort_keys=False, default_flow_style=False)
    for line in incident_yaml.split('\n'):
        if line:
            output += f"# {line}\n"
    output += "\n"
    prompts_yaml = yaml.dump(prompts, Dumper=_BlockStrDumper, sort_keys=False, default_flow_style=False)
    output += prompts_yaml
    return output


def main():
    parser = argparse.ArgumentParser(
        description="Generate incident datasets and prompts, or retrieve existing incident datasets",
        epilog="If config_file is not provided, the script will retrieve existing incident datasets."
    )
    parser.add_argument("dataset_id", help="ID of the source dataset")
    parser.add_argument("config_file", nargs="?", default=None,
                       help="Path to incidents configuration YAML file (optional). If not provided, retrieves existing incident datasets.")
    parser.add_argument("--out", "-o", dest="out", help="Path to output file to write prompts (YAML). If provided, prompts will be appended.")
    args = parser.parse_args()

    # Load environment variables
    env = load_environment()

    # Set up API headers
    headers = get_headers(
        env["ROCKFISH_API_KEY"],
        env["ROCKFISH_PROJECT_ID"],
        env["ROCKFISH_ORGANIZATION_ID"]
    )

    # Determine mode: generate new incidents or retrieve existing
    if args.config_file:
        # Mode 1: Generate new incident datasets from config file
        incidents = load_incidents_config(args.config_file)

        print(f"Generating incident datasets and prompts based on dataset {args.dataset_id} and {args.config_file}")
        incident_results = generate_prompts(
            env["MANTA_API_URL"],
            headers,
            args.dataset_id,
            incidents
        )
    else:
        # Mode 2: Retrieve existing incident datasets
        print(f"Retrieving existing incident datasets for source dataset {args.dataset_id}")
        incident_dataset_ids = retrieve_incident_dataset_ids(
            env["MANTA_API_URL"],
            headers,
            args.dataset_id
        )

        if incident_dataset_ids is None:
            sys.exit("Failed to retrieve incident dataset IDs")

        if not incident_dataset_ids:
            print("No incident datasets found for this source dataset")
            return

        print(f"Found {len(incident_dataset_ids)} incident dataset(s)")
        # Create incident_results list with dataset IDs and empty config
        incident_results = [(dataset_id, {}) for dataset_id in incident_dataset_ids]

    # Retrieve prompts for each incident dataset using GET API
    if incident_results:
        print("\n" + "="*80)
        print("Retrieving prompts via GET /prompts API")
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
    main()