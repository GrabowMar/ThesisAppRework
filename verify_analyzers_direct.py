#!/usr/bin/env python3
"""
Direct analyzer connectivity verification.
Sends real health check requests to all 4 analyzer services.
"""

import sys
import asyncio
sys.path.insert(0, 'src')

from app.services.analyzer_pool import AnalyzerPool
import uuid


async def test_analyzer_connectivity():
    """Test direct connectivity to all analyzer services."""
    print('=' * 80)
    print('DIRECT ANALYZER CONNECTIVITY VERIFICATION')
    print('=' * 80)
    print()

    # Initialize analyzer pool
    pool = AnalyzerPool()
    await pool.initialize()

    print(f'Pool initialized with {len(pool.endpoints)} services')
    for service_name, endpoints in pool.endpoints.items():
        print(f'  {service_name}: {len(endpoints)} endpoint(s)')
    print()

    # Test each analyzer service
    services_to_test = [
        'static-analyzer',
        'dynamic-analyzer',
        'performance-tester',
        'ai-analyzer'
    ]

    results = {}

    print('TESTING ANALYZER SERVICES:')
    print('=' * 80)

    for service_name in services_to_test:
        print(f'\nTesting {service_name}...')

        try:
            # Create a health check message
            message = {
                'request_id': str(uuid.uuid4()),
                'type': 'health_check'
            }

            # Send request with 10 second timeout
            print(f'  Sending health check request...')
            response = await asyncio.wait_for(
                pool.send_analysis_request(
                    service_name=service_name,
                    message=message
                ),
                timeout=10.0
            )

            if response:
                status = response.get('status', 'unknown')
                print(f'  ✓ Response received')
                print(f'    Status: {status}')

                if 'available_tools' in response:
                    tools = response.get('available_tools', [])
                    print(f'    Available tools: {len(tools)}')

                results[service_name] = {
                    'status': 'SUCCESS',
                    'response': response.get('status'),
                    'error': None
                }
            else:
                print(f'  ✗ Empty response')
                results[service_name] = {
                    'status': 'FAILED',
                    'response': None,
                    'error': 'Empty response'
                }

        except asyncio.TimeoutError:
            print(f'  ✗ Request timed out (10s)')
            results[service_name] = {
                'status': 'TIMEOUT',
                'response': None,
                'error': 'Request timeout'
            }
        except RuntimeError as e:
            error_msg = str(e)
            if 'No reachable endpoints' in error_msg:
                print(f'  ✗ CONNECTIVITY ERROR: {error_msg}')
                results[service_name] = {
                    'status': 'NO_ENDPOINTS',
                    'response': None,
                    'error': error_msg
                }
            else:
                print(f'  ✗ Runtime error: {error_msg}')
                results[service_name] = {
                    'status': 'ERROR',
                    'response': None,
                    'error': error_msg
                }
        except Exception as e:
            print(f'  ✗ Exception: {type(e).__name__}: {str(e)[:100]}')
            results[service_name] = {
                'status': 'EXCEPTION',
                'response': None,
                'error': str(e)[:100]
            }

    # Summary
    print()
    print('=' * 80)
    print('VERIFICATION SUMMARY')
    print('=' * 80)
    print()

    success_count = sum(1 for r in results.values() if r['status'] == 'SUCCESS')
    no_endpoint_count = sum(1 for r in results.values() if r['status'] == 'NO_ENDPOINTS')
    total_count = len(results)

    for service, result in results.items():
        icon = '✓' if result['status'] == 'SUCCESS' else '✗'
        status = result['status']
        print(f'{icon} {service}: {status}')
        if result['error']:
            print(f'  Error: {result["error"][:80]}')

    print()
    print(f'Success Rate: {success_count}/{total_count} ({(success_count/total_count)*100:.0f}%)')
    print()

    if no_endpoint_count > 0:
        print(f'❌ CONNECTIVITY FIX VERIFICATION FAILED')
        print(f'   {no_endpoint_count} services still have "No reachable endpoints" errors')
        return False
    elif success_count == total_count:
        print(f'✅ CONNECTIVITY FIX VERIFICATION SUCCESSFUL!')
        print(f'   All {total_count} analyzer services are reachable and responding')
        return True
    else:
        print(f'⚠️  PARTIAL SUCCESS')
        print(f'   {success_count}/{total_count} services reachable')
        print(f'   Some services have connectivity issues but not "No endpoints" errors')
        return False


if __name__ == '__main__':
    try:
        success = asyncio.run(test_analyzer_connectivity())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f'\nFATAL ERROR: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
