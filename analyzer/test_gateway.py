import asyncio

# __test__ = False  # Prevent pytest from collecting tests from this legacy module

# Legacy analyzer gateway tests removed from automated test runs; file retained for manual inspection.
# pytest.skip("Legacy analyzer gateway tests removed from scope", allow_module_level=True)

# The rest of this file remains for manual invocation patterns only. Imports below would fail during pytest.
# import websockets
# from shared.protocol import (
#     AnalysisRequest,
#     AnalysisType,
#     ServiceType,
#     create_analysis_request_message,
# )


async def main():
    # No-op; kept for historical reference only
    return

    # Kept for reference only; manual runs would need to restore imports above
    # req = AnalysisRequest(
    #     model=model,
    #     app_number=app_number,
    #     analysis_type=AnalysisType.CODE_QUALITY_PYTHON,
    #     source_path=''
    # )
    # msg = create_analysis_request_message(req, client_id='cli-test', service=ServiceType.CODE_QUALITY)

    # print(f"Connecting to {uri}...")
    # async with websockets.connect(uri) as ws:
    #     await ws.send(msg.to_json())
    #     print("Request sent, awaiting response...")
    #     resp = await ws.recv()
    #     try:
    #         data = json.loads(resp)
    #     except json.JSONDecodeError:
    #         print("Non-JSON response:", resp)
    #         return
    #     print("Received:")
    #     # Print a concise summary
    #     print(json.dumps(
    #         {
    #             'type': data.get('type'),
    #             'correlation_id': data.get('correlation_id'),
    #             'service_status': data.get('data', {}).get('status'),
    #             'inner_type': data.get('data', {}).get('type'),
    #         },
    #         indent=2
    #     ))


if __name__ == '__main__':
    asyncio.run(main())
