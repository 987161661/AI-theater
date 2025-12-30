from core.state.manager import state_manager

def get_versioned_key(base_key: str) -> str:
    """
    Appends the current prompt_version to a key to force widget refresh.
    Example: 'sys_prompt' -> 'sys_prompt_v3'
    """
    return f"{base_key}_v{state_manager.prompt_version}"

def force_refresh():
    """Increments the global version to invalidate versioned widgets."""
    state_manager.increment_prompt_version()
