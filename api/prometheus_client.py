import httpx
import asyncio
from typing import Dict, Any, Tuple

class PrometheusClient:
    """
    Client for the Prometheus HTTP API.
    Used to run PromQL queries against the Ceph metrics endpoint.
    """
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.query_url = f"{self.base_url}/api/v1/query"
        # Async HTTP client
        self.client = httpx.AsyncClient(timeout=5.0)

    async def _query_single_value(self, promql: str, default: float = 0.0) -> float:
        """
        Executes a PromQL query that is expected to return a single numeric value.
        """
        try:
            response = await self.client.get(self.query_url, params={"query": promql})
            response.raise_for_status()
            data = response.json()
            
            # Prometheus JSON format:
            # {'status': 'success', 'data': {'resultType': 'vector', 'result': [{'metric': {}, 'value': [1686866160.718, "42"]}]}}
            results = data.get("data", {}).get("result", [])
            if results:
                # The value is the second item in the 'value' array, and it's a string
                return float(results[0].get("value", [0, "0"])[1])
            return default
        except httpx.RequestError as e:
            print(f"Prometheus connection error {e.request.url!r}: {e}")
            return default
        except Exception as e:
            print(f"Prometheus query parsing error: {e}")
            return default

    async def close(self):
        await self.client.aclose()

    # --- Specific Metric Queries ---
    
    async def get_total_iops(self) -> float:
        """
        Returns total cluster IOPS (Reads + Writes) over 1m window.
        """
        q = 'sum(rate(ceph_osd_op_r[1m])) + sum(rate(ceph_osd_op_w[1m]))'
        return await self._query_single_value(q)
        
    async def get_bandwidth_bytes_sec(self) -> Tuple[float, float]:
        """
        Returns (Read Bytes/sec, Write Bytes/sec) over 1m window.
        """
        q_read = 'sum(rate(ceph_osd_op_r_out_bytes[1m]))'
        q_write = 'sum(rate(ceph_osd_op_w_in_bytes[1m]))'
        
        # Run both queries concurrently
        read_bw, write_bw = await asyncio.gather(
            self._query_single_value(q_read),
            self._query_single_value(q_write)
        )
        return read_bw, write_bw

    async def get_active_pgs(self) -> int:
        """
        Returns total active Placement Groups.
        """
        return int(await self._query_single_value('sum(ceph_pg_active)'))

    async def get_health_status(self) -> str:
        """
        Returns health status string. 
        ceph_health_status metric: 0=OK, 1=WARN, 2=ERR.
        """
        val = await self._query_single_value('ceph_health_status', default=-1)
        if val == 0:
            return "HEALTH_OK"
        elif val == 1:
            return "HEALTH_WARN"
        elif val == 2:
            return "HEALTH_ERR"
        return "HEALTH_UNKNOWN"
