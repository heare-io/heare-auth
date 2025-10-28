"""
Statistics/metrics client for heare-auth.
"""
import os
from typing import Optional
from heare.stats.client import HttpClient, BaseStatsClient


_stats_client: Optional[BaseStatsClient] = None


def get_stats_client() -> Optional[BaseStatsClient]:
    """
    Get the configured stats client, or None if not configured.
    
    Returns None if stats are disabled or not properly configured.
    """
    global _stats_client
    
    if _stats_client is None:
        _stats_client = _initialize_stats_client()
    
    return _stats_client


def _initialize_stats_client() -> Optional[BaseStatsClient]:
    """Initialize the stats client from environment variables."""
    protocol = os.environ.get('PROTOCOL', '').lower()
    dest_host = os.environ.get('DEST_HOST', '')
    dest_port = os.environ.get('DEST_PORT', '')
    secret = os.environ.get('SECRET', '')
    
    # Only initialize if we have the required configuration
    if not (protocol and dest_host and dest_port):
        return None
    
    try:
        port = int(dest_port)
    except ValueError:
        return None
    
    # Currently only HTTP is supported
    if protocol != 'http':
        return None
    
    return HttpClient(
        host=dest_host,
        port=port,
        secret=secret,
        prefix='heare-auth'
    )
