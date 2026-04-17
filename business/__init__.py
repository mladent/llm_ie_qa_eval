"""Business-layer adapters and contracts for evaluation artifacts."""

from business.artifacts_loader import load_business_contract_input
from business.types import BusinessContractInput

__all__ = ["BusinessContractInput", "load_business_contract_input"]
