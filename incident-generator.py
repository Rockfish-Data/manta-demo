#!/usr/bin/env python3

import argparse
import json
import os
import sys
from typing import Dict, List, Optional

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


def main():
    parser = argparse.ArgumentParser(description="Generate incident datasets and prompts")
    parser.add_argument("dataset_id", help="ID of the source dataset")
    parser.add_argument("config_file", help="Path to incidents configuration YAML file")
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
    
    # Load incidents configuration
    incidents = load_incidents_config(args.config_file)
    
    # Process each incident
    for incident in incidents:
        incident_type = incident["type"]
        config = incident["configuration"]
        
        print(f"\nProcessing incident type: {incident_type}")
        
        # Create incident dataset
        response = create_incident_data(
            env["MANTA_API_URL"],
            headers,
            args.dataset_id,
            incident_type,
            config
        )
        
        if response:
            incident_dataset_id = response['dataset_id']
            print(f"Created incident dataset: {incident_dataset_id}")
            
            # Generate prompts for the incident dataset
            prompt_response = create_prompts(
                env["MANTA_API_URL"],
                headers,
                incident_dataset_id
            )
            
            if prompt_response:
                # Print prompts in YAML for cleaner multiline output (SQL, etc.).
                # Use our custom dumper so multiline strings are emitted with the
                # YAML block scalar (|) instead of inline escaped newlines.
                print("Generated prompts (YAML):")
                yaml_text = yaml.dump(prompt_response, Dumper=_BlockStrDumper, sort_keys=False, default_flow_style=False)
                print(yaml_text)

                # If an output path was provided, append the YAML to that file with a header.
                if args.out:
                    try:
                        with open(args.out, "a", encoding="utf-8") as fh:
                            fh.write(f"# Incident dataset: {incident_dataset_id}\n")
                            fh.write(yaml_text)
                            fh.write("\n")
                        print(f"Wrote prompts to {args.out}")
                    except Exception as e:
                        print(f"Error writing prompts to {args.out}: {e}")


if __name__ == "__main__":
    main()