"""Custom exception classes for the API."""
from fastapi import HTTPException, status


class AgentError(HTTPException):
    """Error from the trading agent."""
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)


class ValidationError(HTTPException):
    """Input validation error."""
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


class ConfigurationError(HTTPException):
    """Configuration error."""
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class SessionError(HTTPException):
    """Session/time related error."""
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class AgentReliabilityException(HTTPException):
    """Protocol or Reliability failure in Agent Core."""
    def __init__(self, detail: str, error_code: str = "AGENT_reliability_ERROR", status_code: int = status.HTTP_422_UNPROCESSABLE_ENTITY):
        self.error_code = error_code
        super().__init__(status_code=status_code, detail=detail)
