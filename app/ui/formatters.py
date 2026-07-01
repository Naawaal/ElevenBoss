# UI Text Formatting Helpers

def format_money(amount: int) -> str:
    """Format currency values like $10,000,000."""
    return f"${amount:,}"

def format_percentage(value: int) -> str:
    """Format numeric values as percentages (e.g., 75%)."""
    return f"{value}%"

def format_progress_bar(value: int, max_value: int = 100, bar_length: int = 10) -> str:
    """Creates a visual progress bar representation, e.g., [██████░░░░] 60%"""
    clamped = max(0, min(value, max_value))
    filled_len = int(round(bar_length * clamped / float(max_value)))
    bar = "█" * filled_len + "░" * (bar_length - filled_len)
    return f"[{bar}] {clamped}%"
