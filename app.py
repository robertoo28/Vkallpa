"""
V-Kallpa APP - Main Entry Point
Streamlit application for energy monitoring and analytics
"""
import streamlit as st
from core.ui.layout import setup_page_config, render_sidebar
from core.ui.page_loader import load_and_run_page


def main() -> None:
    """Main application entry point"""
    setup_page_config()
    
    selected_category, selected_page = render_sidebar()
    
    if selected_page:
        load_and_run_page(selected_page)


if __name__ == "__main__":
    main()