import yaml
import logging
import logging.config
import logging.handlers
from pathlib import Path


_INITIALIZED = False


def setup_logging():
    global _INITIALIZED
    if _INITIALIZED:
        return

    config_file = Path(__file__).parent / "config.yaml"
    if not config_file.exists():
        raise FileNotFoundError(f"Logging config not found: {config_file}")

    with open(config_file) as f:
        config = yaml.safe_load(f)

    logging.config.dictConfig(config)

    # Properly find QueueHandler and start listener
    root_logger = logging.getLogger()

    # if root_logger.handlers: