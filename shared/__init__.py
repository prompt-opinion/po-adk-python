# shared — infrastructure library shared by all agents in this repo.
# Import from sub-modules directly: from shared.middleware import ApiKeyMiddleware

from shared.logging_utils import configure_logging
configure_logging("shared")
