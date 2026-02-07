"""
UI Layout module
Handles page configuration and sidebar rendering
"""
import streamlit as st
from typing import Tuple, Optional
from streamlit_option_menu import option_menu

from core.config.navigation import (
    MENU_STYLES,
    get_main_categories,
    get_category_pages,
    extract_menu_labels,
    extract_menu_icons,
)


def setup_page_config() -> None:
    """Configure Streamlit page settings"""
    st.set_page_config(
        page_title="V-Kallpa APP",
        page_icon="🚀",
        layout="wide"
    )


def render_logo(logo_path: str = "./V-Kallpa.png", width: int = 300) -> None:
    """
    Render logo in sidebar
    
    Args:
        logo_path: Path to logo image
        width: Width of the logo in pixels
    """
    st.image(logo_path, width=width)


def render_main_menu() -> str:
    """
    Render main navigation menu
    
    Returns:
        Selected category name
    """
    categories = get_main_categories()
    labels = [cat.label for cat in categories]
    icons = [cat.icon for cat in categories]
    
    selected_category = option_menu(
        "Navigation",
        labels,
        icons=icons,
        menu_icon="menu-button-wide",
        default_index=0,
        styles=MENU_STYLES
    )
    
    return selected_category


def render_category_menu(category: str) -> Optional[str]:
    """
    Render submenu for a specific category
    
    Args:
        category: Category name
        
    Returns:
        Selected page name or None
    """
    menu_category = get_category_pages(category)
    
    if not menu_category.items:
        return None
    
    labels = extract_menu_labels(menu_category)
    icons = extract_menu_icons(menu_category)
    
    selected_page = option_menu(
        menu_category.name,
        labels,
        icons=icons,
        menu_icon=menu_category.icon,
        default_index=0,
        styles=MENU_STYLES
    )
    
    return selected_page


def render_sidebar() -> Tuple[str, Optional[str]]:
    """
    Render complete sidebar with logo and menus
    
    Returns:
        Tuple of (selected_category, selected_page)
    """
    with st.sidebar:
        render_logo()
        selected_category = render_main_menu()
        selected_page = render_category_menu(selected_category)
    
    return selected_category, selected_page