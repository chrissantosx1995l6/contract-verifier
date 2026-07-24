"""Fast HTTP contract verification utilities."""

from contract_verifier.checker import verify_service
from contract_verifier.models import ContractSpec, VerificationResult

__version__ = "0.3.1"
__all__ = ["verify_service", "ContractSpec", "VerificationResult", "__version__"]
