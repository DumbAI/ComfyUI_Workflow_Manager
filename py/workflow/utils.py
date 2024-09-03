import logging
import os
import subprocess

# Setup logging to stdout
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def run_command(command, cwd=None):
    try:
        if cwd:
            result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=True)
        else:
            result = subprocess.run(command, capture_output=True, text=True, check=True)
        logger.info(f"Command {command} succeeded with output: {result.stdout}")
        return result.stdout.strip()
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise

def force_create_symlink(source, link_name):
    """ Create a symlink, remove existing file or symlink if exists"""
    if os.path.isfile(source):
        if os.path.exists(link_name) or os.path.islink(link_name):
            os.remove(link_name)
        os.symlink(source, link_name)