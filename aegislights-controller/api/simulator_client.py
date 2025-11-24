"""Low-level HTTP client for simulator communication."""

import logging
import time
import requests
from typing import Optional, Dict, Any

from config.simulator import SimulatorConfig

logger = logging.getLogger(__name__)


class SimulatorClient:
    """Low-level HTTP client for CityFlow simulator API."""
    
    def __init__(self, config: SimulatorConfig):
        """
        Initialize simulator client.
        
        Args:
            config: Simulator configuration
        """
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def get(self, endpoint: str, params: Optional[Dict] = None, 
            **path_params) -> Optional[Dict]:
        """
        Make GET request to simulator.
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            **path_params: Path parameters for endpoint formatting
            
        Returns:
            Response data or None if failed
        """
        url = self.config.get_full_url(endpoint, **path_params)
        
        for attempt in range(self.config.retry_attempts):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.config.timeout_seconds
                )
                response.raise_for_status()
                return response.json()
            
            except requests.exceptions.RequestException as e:
                logger.warning(
                    f"GET {url} failed (attempt {attempt + 1}/{self.config.retry_attempts}): {e}"
                )
                if attempt < self.config.retry_attempts - 1:
                    time.sleep(self.config.retry_delay_seconds)
                else:
                    logger.error(f"GET {url} failed after {self.config.retry_attempts} attempts")
                    return None
    
    def post(self, endpoint: str, data: Dict[str, Any], 
            **path_params) -> Optional[Dict]:
        """
        Make POST request to simulator.
        
        Args:
            endpoint: API endpoint
            data: Request body data
            **path_params: Path parameters for endpoint formatting
            
        Returns:
            Response data or None if failed
        """
        url = self.config.get_full_url(endpoint, **path_params)
        
        for attempt in range(self.config.retry_attempts):
            try:
                response = self.session.post(
                    url,
                    json=data,
                    timeout=self.config.timeout_seconds
                )
                response.raise_for_status()
                return response.json()
            
            except requests.exceptions.RequestException as e:
                logger.warning(
                    f"POST {url} failed (attempt {attempt + 1}/{self.config.retry_attempts}): {e}"
                )
                if attempt < self.config.retry_attempts - 1:
                    time.sleep(self.config.retry_delay_seconds)
                else:
                    logger.error(f"POST {url} failed after {self.config.retry_attempts} attempts")
                    return None
    
    def check_connection(self) -> bool:
        """
        Check if CityFlow simulator is reachable.
        
        Returns:
            True if connected, False otherwise
        """
        try:
            response = self.session.get(
                f"{self.config.base_url}/health",
                timeout=5.0
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'ok' and data.get('service') == 'cityflow':
                    logger.info("Successfully connected to CityFlow simulator")
                    return True
            return False
        except requests.exceptions.RequestException as e:
            logger.warning(f"CityFlow connection check failed: {e}")
            return False
    
    def close(self) -> None:
        """Close the HTTP session."""
        self.session.close()
        logger.debug("Simulator client session closed")
