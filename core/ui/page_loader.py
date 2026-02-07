"""
Page loader module
Handles dynamic loading and execution of page modules
"""
import streamlit as st
import importlib
from typing import Optional

from core.config.navigation import get_page_module_path


def load_module(module_path: str) -> Optional[object]:
    """
    Dynamically load a module by its path
    
    Args:
        module_path: Dot-separated module path
        
    Returns:
        Loaded module or None if error occurs
    """
    try:
        module = importlib.import_module(module_path)
        return module
    except ModuleNotFoundError as e:
        st.error(f"Module non trouvé: {module_path}")
        st.error(f"Détails: {str(e)}")
        return None
    except Exception as e:
        st.error(f"Erreur lors du chargement du module: {module_path}")
        st.error(f"Détails: {str(e)}")
        return None


def execute_module_run(module: object, page_name: str) -> bool:
    """
    Execute the run function of a module
    
    Args:
        module: Loaded module object
        page_name: Name of the page (for error messages)
        
    Returns:
        True if execution successful, False otherwise
    """
    if not hasattr(module, "run"):
        st.error(f"La page {page_name} ne contient pas de fonction 'run()'")
        return False
    
    try:
        module.run()
        return True
    except Exception as e:
        st.error(f"Erreur lors de l'exécution de la page {page_name}")
        st.error(f"Détails: {str(e)}")
        return False


def load_and_run_page(page_name: str) -> None:
    """
    Load and execute a page module
    
    Args:
        page_name: Name of the page to load
    """
    module_path = get_page_module_path(page_name)
    
    if not module_path:
        st.error(f"Page non configurée: {page_name}")
        return
    
    module = load_module(module_path)
    
    if module:
        execute_module_run(module, page_name)