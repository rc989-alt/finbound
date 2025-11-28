"""
OpenAI Client Factory for FinBound.

Supports both OpenAI and Azure OpenAI through environment configuration.

Environment Variables:
    For OpenAI:
        OPENAI_API_KEY: Your OpenAI API key

    For Azure OpenAI:
        AZURE_OPENAI_API_KEY: Your Azure OpenAI API key
        AZURE_OPENAI_ENDPOINT: Your Azure endpoint (e.g., https://your-resource.openai.azure.com)
        AZURE_OPENAI_API_VERSION: API version (default: 2024-02-15-preview)
        AZURE_OPENAI_DEPLOYMENT_GPT4O: Deployment name for gpt-4o equivalent
        AZURE_OPENAI_DEPLOYMENT_GPT4O_MINI: Deployment name for gpt-4o-mini equivalent

Usage:
    >>> from finbound.utils.openai_client import get_client, get_model_name
    >>> client = get_client()
    >>> model = get_model_name("gpt-4o")  # Returns deployment name for Azure
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openai import OpenAI, AzureOpenAI

logger = logging.getLogger(__name__)

# Model mapping for Azure deployments
# Maps OpenAI model names to Azure deployment names
AZURE_MODEL_MAPPING: dict[str, str] = {}


def is_azure_configured() -> bool:
    """Check if Azure OpenAI is configured via environment variables."""
    return bool(
        os.getenv("AZURE_OPENAI_API_KEY")
        and os.getenv("AZURE_OPENAI_ENDPOINT")
    )


def is_openai_configured() -> bool:
    """Check if OpenAI is configured via environment variables."""
    api_key = os.getenv("OPENAI_API_KEY", "")
    return bool(api_key and api_key.startswith("sk-"))


@lru_cache(maxsize=1)
def get_client() -> "OpenAI | AzureOpenAI":
    """
    Get the appropriate OpenAI client based on environment configuration.

    Prefers Azure OpenAI if configured, falls back to OpenAI.

    Returns:
        OpenAI or AzureOpenAI client instance

    Raises:
        ValueError: If neither OpenAI nor Azure OpenAI is configured
    """
    if is_azure_configured():
        from openai import AzureOpenAI

        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

        logger.info("Using Azure OpenAI client: %s", endpoint)

        # Load model mappings from environment
        _load_azure_model_mapping()

        return AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
        )

    elif is_openai_configured():
        from openai import OpenAI

        logger.info("Using OpenAI client")
        return OpenAI()

    else:
        raise ValueError(
            "No OpenAI configuration found. Please set either:\n"
            "  - OPENAI_API_KEY for OpenAI, or\n"
            "  - AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT for Azure OpenAI"
        )


def _load_azure_model_mapping() -> None:
    """Load Azure deployment name mappings from environment."""
    global AZURE_MODEL_MAPPING

    # Get deployment names from environment
    main_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_GPT4O", "gpt-4o")
    mini_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_GPT4O_MINI", "gpt-4o-mini")

    # Map standard OpenAI model names to Azure deployment names
    mappings = {
        "gpt-4o": main_deployment,
        "gpt-4o-mini": mini_deployment,
        "gpt-4": os.getenv("AZURE_OPENAI_DEPLOYMENT_GPT4", "gpt-4"),
        "gpt-4-turbo": os.getenv("AZURE_OPENAI_DEPLOYMENT_GPT4_TURBO", "gpt-4-turbo"),
        "gpt-35-turbo": os.getenv("AZURE_OPENAI_DEPLOYMENT_GPT35_TURBO", "gpt-35-turbo"),
        # GPT-5 mappings
        "gpt-5": main_deployment,
        "gpt-5-mini": mini_deployment,
    }

    AZURE_MODEL_MAPPING.update(mappings)
    logger.debug("Azure model mappings: %s", AZURE_MODEL_MAPPING)


def is_gpt5_model() -> bool:
    """Check if we're using a GPT-5 model (which has different API requirements)."""
    main_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_GPT4O", "")
    return "gpt-5" in main_deployment.lower()


def get_model_name(model: str) -> str:
    """
    Get the appropriate model/deployment name.

    For OpenAI: Returns the model name as-is
    For Azure: Returns the deployment name from mapping

    Args:
        model: OpenAI model name (e.g., "gpt-4o", "gpt-4o-mini")

    Returns:
        Model name for OpenAI or deployment name for Azure
    """
    if is_azure_configured():
        # Ensure mapping is loaded
        if not AZURE_MODEL_MAPPING:
            _load_azure_model_mapping()

        deployment = AZURE_MODEL_MAPPING.get(model, model)
        logger.debug("Azure model mapping: %s -> %s", model, deployment)
        return deployment

    return model


def get_provider() -> str:
    """
    Get the current provider name.

    Returns:
        "azure" or "openai"
    """
    return "azure" if is_azure_configured() else "openai"


# Convenience function for checking configuration status
def check_configuration() -> dict[str, bool]:
    """
    Check configuration status for both providers.

    Returns:
        Dict with 'openai' and 'azure' keys indicating configuration status
    """
    return {
        "openai": is_openai_configured(),
        "azure": is_azure_configured(),
    }
