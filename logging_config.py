import logging
import os

def setup_logging():
    log_file = "ontology_constructor.log"
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    logging.info("Логирование настроено, лог пишется в %s", os.path.abspath(log_file))