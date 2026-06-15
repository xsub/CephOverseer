import httpx
import asyncio
from typing import Dict, Any, List

class CephMgrClient:
    """
    Client for the Ceph MGR REST API.
    Used for retrieving cluster topology (Hosts, OSDs, Pools) and administrative actions.
    """
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip('/')
        self.api_url = f"{self.base_url}/api"
        self.username = username
        self.password = password
        
        self.client = httpx.AsyncClient(verify=False, timeout=10.0) # Often self-signed
        self.token = None

    async def _authenticate(self) -> bool:
        """
        Authenticates with the Ceph MGR API and retrieves a JWT token.
        """
        if not self.username or not self.password:
            return False
            
        try:
            response = await self.client.post(
                f"{self.api_url}/auth",
                json={"username": self.username, "password": self.password},
                headers={"Accept": "application/vnd.ceph.api.v1.0+json", "Content-Type": "application/json"}
            )
            response.raise_for_status()
            data = response.json()
            self.token = data.get("token")
            return bool(self.token)
        except Exception as e:
            print(f"Ceph MGR Auth Error for {self.base_url}: {e}")
            self.token = None
            return False

    async def _request(self, method: str, endpoint: str, json_data: dict = None) -> Any:
        """
        Helper method to make authenticated requests. Automatically handles token retrieval.
        """
        if not self.token:
            success = await self._authenticate()
            if not success:
                return {}

        headers = {
            "Accept": "application/vnd.ceph.api.v1.0+json",
            "Authorization": f"Bearer {self.token}"
        }
        if json_data:
            headers["Content-Type"] = "application/json"
        
        url = f"{self.api_url}/{endpoint.lstrip('/')}"
        
        try:
            response = await self.client.request(method, url, headers=headers, json=json_data)
            
            # If token expired, retry once
            if response.status_code == 401:
                self.token = None
                success = await self._authenticate()
                if success:
                    headers["Authorization"] = f"Bearer {self.token}"
                    response = await self.client.request(method, url, headers=headers, json=json_data)
            
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Ceph MGR API Error on {endpoint}: {e}")
            return {}

    async def close(self):
        await self.client.aclose()

    # --- Specific API Endpoints ---
        
    async def get_osds(self) -> List[Dict[str, Any]]:
        """
        Get list of all OSDs and their states.
        """
        # Usually returns a list or dict depending on API version. 
        # For ceph-mgr dashboard API, it's often a list.
        res = await self._request("GET", "/osd")
        if isinstance(res, list):
            return res
        return res.get("osds", []) if isinstance(res, dict) else []
        
    async def get_hosts(self) -> List[Dict[str, Any]]:
        """
        Get list of all hosts in the cluster.
        """
        res = await self._request("GET", "/host")
        if isinstance(res, list):
            return res
        return res.get("hosts", []) if isinstance(res, dict) else []

    async def get_pools(self) -> List[Dict[str, Any]]:
        """
        Get list of storage pools.
        """
        res = await self._request("GET", "/pool")
        if isinstance(res, list):
            return res
        return res.get("pools", []) if isinstance(res, dict) else []

    async def set_osd_status(self, osd_id: int, action: str) -> bool:
        """
        Set OSD status (e.g., action="out", "in", "down").
        """
        res = await self._request("POST", f"/osd/{osd_id}/mark", json_data={"action": action})
        return bool(res)
