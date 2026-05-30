"""KM domain exceptions."""


class KmError(Exception):
    """Base error for Knowledge Management operations."""


class ConfigError(KmError):
    """Invalid or missing workspace / LO configuration."""


class WorkspaceNotFoundError(KmError):
    """No .km/ directory found while searching for workspace root."""


class FeatureNotImplementedError(KmError):
    """Raised when a wired surface is not yet implemented."""

    def __init__(self, feature: str) -> None:
        self.feature = feature
        super().__init__(f"feature not yet implemented: {feature}")
