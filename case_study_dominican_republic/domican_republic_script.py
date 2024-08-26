import pandas as pd
import json
from collections import defaultdict
from datetime import datetime
import jsonschema
from case_study_dominican_republic.tools import *
import uuid

pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)


# Read the Excel file into Pandas Dataframes, specifying the sheet names
df_processes = pd.read_excel('Dominican_Republic_Techsprint_Data (1).xlsx', sheet_name='Processes')
df_contracts = pd.read_excel('Dominican_Republic_Techsprint_Data (1).xlsx', sheet_name='Contracts')

# Display the first 5 rows of each DataFrame
print("First 5 rows of Processes DataFrame:")
print(df_processes.head().to_markdown(index=False, numalign="left", stralign="left"))

print("\nFirst 5 rows of Contracts DataFrame:")
print(df_contracts.head().to_markdown(index=False, numalign="left", stralign="left"))

# Print the column names and their data types for each DataFrame
print("\nColumn names and types for Processes DataFrame:")
print(df_processes.info())

print("\nColumn names and types for Contracts DataFrame:")
print(df_contracts.info())

# Preprocess `MontoEstimado` in df_processes
df_processes['MontoEstimado'] = df_processes['MontoEstimado'].astype(str).str.replace('e', 'E', regex=False)
df_processes['MontoEstimado'] = pd.to_numeric(df_processes['MontoEstimado'], errors='coerce')
df_processes['MontoEstimado'] = df_processes['MontoEstimado'].fillna(0)

# Replace 'e' with 'E' in `ValorContrato` column
df_contracts['ValorContrato'] = df_contracts['ValorContrato'].astype(str).str.replace('e', 'E', regex=False)

# Convert the `ValorContrato` column to numeric, setting failed conversions to NaN
df_contracts['ValorContrato'] = pd.to_numeric(df_contracts['ValorContrato'], errors='coerce')

# Fill NaN values in `ValorContrato` with 0
df_contracts['ValorContrato'] = df_contracts['ValorContrato'].fillna(0)

# Strip trailing whitespace from `CodigoProceso` in df_contracts
df_contracts['CodigoProceso'] = df_contracts['CodigoProceso'].astype(str).str.strip()

def generate_ocds_releases(df_processes, df_contracts):
    """
    Generates a list of OCDS releases, one for each unique 'CodigoProceso' in df_processes.

    Args:
        df_processes: DataFrame containing processes data.
        df_contracts: DataFrame containing contracts data.

    Returns:
        A list of dictionaries, each representing an OCDS release.
    """

    releases = []
    for codigo_proceso in df_processes['CodigoProceso'].unique():
        # Filter data for the current CodigoProceso
        df_process = df_processes[df_processes['CodigoProceso'] == codigo_proceso].iloc[0]
        df_contract = df_contracts[df_contracts['CodigoProceso'] == codigo_proceso]

        # Map 'EstadoProceso' to OCDS tender status
        status_mapping = {
            'Proceso adjudicado y celebrado': 'complete',
            'Proceso ad': 'active',
            'Cancelado': 'cancelled',
            'Proceso con etapa cerrada': 'active',
            'Sobres abiertos o aperturados': 'active',
            'No Definido': None,
            'Proceso desierto': 'unsuccessful'
        }
        ocds_status = status_mapping.get(df_process['EstadoProceso'], 'active') 

        # Map 'Modalidad' to OCDS procurementMethod
        procurement_method_mapping = {
            'Licitación Pública Nacional': 'open',
            'Compras por Debajo del Umbral': 'limited',  # Assuming these are limited tendering processes
            'Comparación de Precios': 'selective', 
            'Licitación Pública Internacional': 'open', 
            'Contratación Directa': 'direct',
            'Sorteo de Obras': 'open',  # Assuming this is a type of open lottery for works
            'Selección de Consultores': 'selective', 
            'Contratación Menor': 'limited' 
        }
        ocds_procurement_method = procurement_method_mapping.get(df_process['Modalidad'], None)

        release = {
            "ocid": f"ocds-r5n6j87-{codigo_proceso}",  # Use CodigoProceso in the OCID
            "id": str(uuid.uuid4()), 
            "date": pd.Timestamp.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
            "tag": ["tender"],
            "initiationType": "tender",
            "planning": {
                "budget": {
                    "amount": {
                        "amount": df_process['MontoEstimado'],
                        "currency": "DOP"
                    }
                }
            },
            "tender": {
                "id": codigo_proceso,
                "title": df_process['NombreProyecto'],
                "description": df_process['DescripcionProceso'],
                "status": ocds_status,
                "statusDetails": df_process['EstadoProceso'],
                "procurementMethod": ocds_procurement_method,
                "procurementMethodDetails": df_process['Modalidad'],
                # "tenderPeriod": {
                #     "startDate": "2023-01-01T00:00:00Z",  # Replace with actual start date if available
                #     "endDate": "2023-01-31T00:00:00Z"  # Replace with actual end date if available
                # }
            }
        }

        if not df_contract.empty:
            contracts = []
            for _, row in df_contract.iterrows():
                contracts.append({
                    "id": row['CodigoContrato'],
                    "title": row['DescripcionContrato'],
                    "status": row['EstadoContrato'],
                    "value": {
                        "amount": row['ValorContrato'],
                        "currency": row['MonedaContrato']
                    },
                    "awardID": "award-" + row['CodigoContrato'],
                    "suppliers": [
                        {
                            "id": row['CodigoProveedor'],
                            "name": row['Proveedor']
                        }
                    ]
                })

            release['tender']['contracts'] = contracts

        releases.append(release)

    return releases

def generate_ocds_package(release):
    """
    Generates an OCDS release package containing the provided releases.

    Args:
        releases: A list of dictionaries, each representing an OCDS release.

    Returns:
        A dictionary representing the OCDS release package.
    """

    package = {
        "uri": f"do.dgcprd.{release["ocid"]}",
        "version": "1.1",
        #"extensions": [],
        "publishedDate": datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
        "releases": [release],
        "publisher": {
            "name": "Dominican Republic"
        },
        # "license": "https://opendatacommons.org/licenses/by/1-0/",
        # "publicationPolicy": "",
    }

    return package

def validate_json_schema(
        dct: dict,
        schema: dict
    ):
        #deserialized = deserialize_dates(dct)
        jsonschema.validate(
            instance=dct,
            schema=schema
        )

# Example usage
ocds_releases = generate_ocds_releases(df_processes, df_contracts)

for release in ocds_releases:
    ocds_package = generate_ocds_package(release)

    with open("release_package_schema.json", "r") as f:
        schema = json.load(f)
        validate_json_schema(ocds_package, schema)

    # Print the generated OCDS package
    print(json.dumps(ocds_package, indent=4))