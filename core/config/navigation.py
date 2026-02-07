"""
Navigation configuration module
Contains menu structures, page mappings, and navigation logic
"""
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class MenuItem:
    """Represents a menu item with its properties"""
    label: str
    icon: str


@dataclass
class MenuCategory:
    """Represents a menu category with its items"""
    name: str
    icon: str
    items: List[MenuItem]


# Menu styling configuration
MENU_STYLES: Dict[str, Dict[str, str]] = {
    "container": {"padding": "5!important", "background-color": "#fafafa"},
    "icon": {"color": "#0c323c", "font-size": "25px"},
    "nav-link": {
        "font-size": "16px",
        "text-align": "left",
        "margin": "0px",
        "--hover-color": "#eee"
    },
    "nav-link-selected": {"background-color": "#0c323c"},
}


def get_main_categories() -> List[MenuItem]:
    """
    Get the main navigation categories
    
    Returns:
        List of main menu items
    """
    return [
        MenuItem("Accueil", "house-door"),
        MenuItem("Monitoring & Visualisation", "bar-chart"),
        MenuItem("Traitement & Optimisation", "tools"),
        MenuItem("IA & Analytics", "cpu"),
    ]


def get_category_pages(category: str) -> MenuCategory:
    """
    Get pages for a specific category
    
    Args:
        category: Category name
        
    Returns:
        MenuCategory with all items for the category
    """
    categories: Dict[str, MenuCategory] = {
        "Accueil": MenuCategory(
            name="Accueil",
            icon="house-door",
            items=[
                MenuItem("Accueil", "house"),
                MenuItem("Parc immobilier", "buildings"),
            ]
        ),
        "Monitoring & Visualisation": MenuCategory(
            name="Monitoring & Visualisation",
            icon="bar-chart",
            items=[
                MenuItem("Monitoring", "activity"),
                MenuItem("Profils", "person"),
                MenuItem("Puissance Max", "battery-full"),
                MenuItem("Comparaison Puissance", "calendar-check"),
                MenuItem("Meteo", "cloud"),
                MenuItem("Carbone", "tree"),
            ]
        ),
        "Traitement & Optimisation": MenuCategory(
            name="Traitement & Optimisation",
            icon="tools",
            items=[
                MenuItem("Comparaison Periode", "arrow-left-right"),
                MenuItem("Comparatif Batiments", "buildings"),
                MenuItem("Autoconsommation", "lightning-charge"),
                MenuItem("Changepoints", "pin-angle"),
            ]
        ),
        "IA & Analytics": MenuCategory(
            name="IA & Analytics",
            icon="cpu",
            items=[
                MenuItem("Anomalies", "search"),
                MenuItem("Prediction", "graph-up-arrow"),
                MenuItem("NILM", "diagram-3"),
            ]
        ),
    }
    
    return categories.get(category, MenuCategory(category, "", []))


def get_page_module_path(page_name: str) -> str:
    """
    Get the module path for a given page name
    
    Args:
        page_name: Name of the page
        
    Returns:
        Module path as string
    """
    page_mappings: Dict[str, str] = {
        # Accueil
        "Accueil": "app_pages.board",
        "Parc immobilier": "app_pages.Dashboard_Multi",
        
        # Monitoring & Visualisation
        "Monitoring": "app_pages.Monitoring_Visualisation.Monitoring",
        "Profils": "app_pages.Monitoring_Visualisation.Profils",
        "Puissance Max": "app_pages.Monitoring_Visualisation.Puissance",
        "Comparaison Puissance": "app_pages.Monitoring_Visualisation.Comparaison_Puissance_Journaliere",
        "Meteo": "app_pages.Monitoring_Visualisation.Meteo",
        "Carbone": "app_pages.Monitoring_Visualisation.Carbone",
        
        # Traitement & Optimisation
        "Comparaison Periode": "app_pages.Traitement_Optimisation.Comparaison",
        "Comparatif Batiments": "app_pages.Traitement_Optimisation.batiments",
        "Autoconsommation": "app_pages.Traitement_Optimisation.autoconsommation",
        "Changepoints": "app_pages.Traitement_Optimisation.Prophet_Changepoints",
        
        # IA & Analytics
        "Anomalies": "app_pages.IA_Analytics.Anomalies",
        "Prediction": "app_pages.IA_Analytics.Prediccion",
        "NILM": "app_pages.IA_Analytics.NILM"
    }
    
    return page_mappings.get(page_name, "")


def extract_menu_labels(menu_category: MenuCategory) -> List[str]:
    """
    Extract labels from menu items
    
    Args:
        menu_category: Menu category containing items
        
    Returns:
        List of item labels
    """
    return [item.label for item in menu_category.items]


def extract_menu_icons(menu_category: MenuCategory) -> List[str]:
    """
    Extract icons from menu items
    
    Args:
        menu_category: Menu category containing items
        
    Returns:
        List of item icons
    """
    return [item.icon for item in menu_category.items]