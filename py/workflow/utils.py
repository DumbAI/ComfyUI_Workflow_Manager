import logging
import os

# Setup logging to stdout
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def force_create_symlink(source, link_name):
    """ Create a symlink, remove existing file or symlink if exists"""
    if os.path.isfile(source):
        if os.path.exists(link_name) or os.path.islink(link_name):
            os.remove(link_name)
        os.symlink(source, link_name)