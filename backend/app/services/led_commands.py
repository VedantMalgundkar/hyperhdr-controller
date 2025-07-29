import requests

base_url = "http://localhost:8090"

def set_hyperhdr_brightness(brightness: int):
    """
    Adjust the brightness of HyperHDR.

    Args:
        ip (str): IP address of the HyperHDR instance (e.g., "192.168.1.100").
        brightness (int): Brightness level (0-255).
    
    Returns:
        dict: JSON response from HyperHDR.
    """
    url = f"{base_url}/json-rpc"
    payload = {
        "command": "adjustment",
        "adjustment": {
            "brightness": max(0, min(brightness, 100))
        }
    }

    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json()

def get_current_brightness():
    """
    Get the current brightness level (0–100) from HyperHDR.

    Returns:
        int | None: Brightness level if found, else None.
    """
    url = f"{base_url}/json-rpc"
    payload = {
        "command": "serverinfo"
    }

    response = requests.post(url, json=payload)
    response.raise_for_status()
    data = response.json()

    adjustments = data.get("info", {}).get("adjustment", [])
    if adjustments:
        return {"brightness" : adjustments[0].get("brightness")}

    return None


def get_hyperhdr_effects():
    """
    Fetch the list of available effects from HyperHDR.

    Returns:
        list: List of effect names.
    """
    url = f"{base_url}/json-rpc"
    payload = {
        "command": "serverinfo"
    }

    response = requests.post(url, json=payload)
    response.raise_for_status()
    data = response.json()

    effects = data.get("info", {}).get("effects", [])
    return effects

def clear_hyperhdr_effect(priority: int = 100):
    """
    Clear any currently running effect at the given priority.
    """
    url = f"{base_url}/json-rpc"
    payload = {
        "command": "clear",
        "priority": priority
    }

    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json()


def apply_hyperhdr_effect(effect_name: str, duration_ms: int = 0):
    """
    Apply an effect to HyperHDR after clearing any running effect at the same priority.

    Args:
        effect_name (str): Name of the effect to apply (e.g., "Rainbow swirl fast").
        duration_ms (int): Duration in milliseconds to run the effect. 0 means infinite.

    Returns:
        dict: JSON response from HyperHDR.
    """
    priority = 100
    clear_hyperhdr_effect(priority)

    url = f"{base_url}/json-rpc"
    payload = {
        "command": "effect",
        "effect": {
            "name": effect_name
        },
        "priority": priority,
        "duration": duration_ms
    }

    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json()
