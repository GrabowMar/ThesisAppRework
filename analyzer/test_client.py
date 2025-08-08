"""
Test Client for Analyzer Infrastructure
======================================

Simple test client to verify the WebSocket-based analyzer infrastructure works correctly.
"""
import asyncio
import logging
from pathlib import Path

import sys
sys.path.append(str(Path(__file__).parent))

from shared.client import AnalyzerClient
from shared.protocol import (
    SecurityAnalysisRequest, AnalysisType, MessageType
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_progress_handler(message):
    """Handle progress updates from analysis."""
    if message.type == MessageType.PROGRESS_UPDATE:
        data = message.data
        logger.info(f"Progress: {data['stage']} - {data['progress']:.1%} - {data['message']}")


async def test_security_analysis():
    """Test security analysis functionality."""
    logger.info("Testing security analysis...")
    
    try:
        # Create test request
        request = SecurityAnalysisRequest(
            model="test_model",
            app_number=1,
            analysis_type=AnalysisType.SECURITY_PYTHON,
            source_path="test/app1",  # This should map to /app/sources/test/app1 in container
            tools=['bandit', 'safety'],
            scan_depth='standard',
            timeout=300
        )
        
        # Connect and analyze
        async with AnalyzerClient("ws://localhost:8765") as client:
            # Register progress handler
            client.register_handler(MessageType.PROGRESS_UPDATE, test_progress_handler)
            
            # Request analysis
            logger.info("Requesting security analysis...")
            result = await client.request_analysis(request, timeout=300.0)
            
            if result.type == MessageType.ANALYSIS_RESULT:
                data = result.data
                logger.info("Analysis completed successfully!")
                logger.info(f"Status: {data['status']}")
                logger.info(f"Issues found: {data['total_issues']}")
                logger.info(f"Duration: {data['duration']:.2f} seconds")
                
                # Show issue breakdown
                if data['total_issues'] > 0:
                    logger.info(f"  Critical: {data['critical_count']}")
                    logger.info(f"  High: {data['high_count']}")
                    logger.info(f"  Medium: {data['medium_count']}")
                    logger.info(f"  Low: {data['low_count']}")
            else:
                logger.error(f"Analysis failed: {result.data}")
                
    except Exception as e:
        logger.error(f"Test failed: {e}")


async def test_gateway_status():
    """Test gateway status functionality."""
    logger.info("Testing gateway status...")
    
    try:
        async with AnalyzerClient("ws://localhost:8765") as client:
            status = await client.get_status()
            
            if status.type == MessageType.STATUS_UPDATE:
                data = status.data
                logger.info("Gateway status:")
                logger.info(f"  Status: {data.get('gateway_status', 'unknown')}")
                logger.info(f"  Connected clients: {data.get('connected_clients', 0)}")
                logger.info(f"  Connected services: {data.get('connected_services', 0)}")
                logger.info(f"  Services by type: {data.get('services_by_type', {})}")
            else:
                logger.error(f"Status request failed: {status.data}")
                
    except Exception as e:
        logger.error(f"Status test failed: {e}")


async def main():
    """Run all tests."""
    logger.info("Starting analyzer infrastructure tests...")
    
    try:
        # Test gateway status first
        await test_gateway_status()
        
        # Wait a bit for services to register
        await asyncio.sleep(2)
        
        # Test security analysis
        await test_security_analysis()
        
        logger.info("All tests completed!")
        
    except Exception as e:
        logger.error(f"Test suite failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
