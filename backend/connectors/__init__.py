"""
Connector registry — add new connectors here to make them available.
"""

from connectors.microsoft_defender import MicrosoftDefenderConnector
from connectors.okta import OktaConnector
from connectors.spreadsheet import SpreadsheetConnector

CONNECTOR_REGISTRY = {
    "microsoft_defender": MicrosoftDefenderConnector,
    "okta": OktaConnector,
    "spreadsheet": SpreadsheetConnector,
}

def get_connector(name: str):
    cls = CONNECTOR_REGISTRY.get(name)
    if not cls:
        raise ValueError(f"Unknown connector: {name}. Available: {list(CONNECTOR_REGISTRY.keys())}")
    return cls()

def get_all_connectors():
    return {name: cls() for name, cls in CONNECTOR_REGISTRY.items()}
