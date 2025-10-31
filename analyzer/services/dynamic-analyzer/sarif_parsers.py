"""
SARIF 2.1.0 Compliant Parsers for Dynamic Analysis Tools
========================================================

Converts dynamic analysis tool outputs to SARIF format.
Focus: ZAP security scanner (nmap/curl excluded - not finding-oriented)
"""

from typing import Dict, Any, Optional, List
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Risk level mapping to SARIF levels
RISK_TO_LEVEL = {
    'high': 'error',
    'medium': 'warning',
    'low': 'warning',
    'informational': 'note',
    'info': 'note'
}


class SARIFBuilder:
    """Helper class for building SARIF 2.1.0 documents."""
    
    @staticmethod
    def create_run(tool_name: str, tool_version: str = "unknown") -> Dict[str, Any]:
        """Create a SARIF run structure."""
        return {
            "tool": {
                "driver": {
                    "name": tool_name,
                    "version": tool_version,
                    "informationUri": f"https://www.zaproxy.org/",
                }
            },
            "results": [],
            "invocations": [{
                "executionSuccessful": True,
                "endTimeUtc": datetime.now(timezone.utc).isoformat()
            }]
        }
    
    @staticmethod
    def create_result(
        rule_id: str,
        message: str,
        level: str,
        uri: Optional[str] = None,
        method: Optional[str] = None,
        risk: Optional[str] = None,
        confidence: Optional[str] = None,
        cwe: Optional[int] = None,
        wasc: Optional[int] = None,
        solution: Optional[str] = None,
        reference: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a SARIF result for web vulnerability."""
        result = {
            "ruleId": rule_id,
            "level": level,
            "message": {
                "text": message
            }
        }
        
        # Add location if URI available
        if uri:
            result["locations"] = [{
                "logicalLocations": [{
                    "kind": "namespace",
                    "fullyQualifiedName": uri
                }]
            }]
        
        # Add properties for security metadata
        properties = {}
        if risk:
            properties["risk"] = risk
        if confidence:
            properties["confidence"] = confidence
        if cwe:
            properties["cwe"] = [f"CWE-{cwe}"]
        if wasc:
            properties["wasc"] = wasc
        if method:
            properties["httpMethod"] = method
        if solution:
            properties["solution"] = solution
        if reference:
            properties["reference"] = reference
        
        if properties:
            result["properties"] = properties
        
        return result


class ZAPSARIFParser:
    """Parse OWASP ZAP output to SARIF format."""
    
    @staticmethod
    def parse(raw_output: Dict[str, Any], config: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Convert ZAP JSON/dict output to SARIF 2.1.0 format.
        
        ZAP output structure (custom format from dynamic-analyzer):
        {
            "alerts": [{
                "alert": "SQL Injection",
                "risk": "High",
                "confidence": "Medium",
                "cweid": "89",
                "wascid": "19",
                "description": "SQL injection may be possible",
                "solution": "Use prepared statements",
                "reference": "https://...",
                "instances": [{
                    "uri": "http://example.com/api",
                    "method": "POST",
                    "param": "id",
                    "attack": "' OR '1'='1",
                    "evidence": "SQL error"
                }]
            }],
            "summary": {
                "high": 2,
                "medium": 5,
                "low": 3,
                "informational": 1
            }
        }
        
        Alternative ZAP native JSON structure:
        {
            "site": [{
                "alerts": [{
                    "pluginid": "40018",
                    "alert": "SQL Injection",
                    "name": "SQL Injection",
                    "riskcode": "3",  # 0=info, 1=low, 2=medium, 3=high
                    "confidence": "2",  # 1=low, 2=medium, 3=high
                    "riskdesc": "High (Medium)",
                    "desc": "<p>SQL injection may be possible.</p>",
                    "instances": [...],
                    "count": "1",
                    "solution": "<p>Use prepared statements...</p>",
                    "reference": "<p>https://...</p>",
                    "cweid": "89",
                    "wascid": "19",
                    "sourceid": "3"
                }]
            }]
        }
        """
        if not isinstance(raw_output, dict):
            logger.error("Invalid ZAP output format")
            return SARIFBuilder.create_run("zap")
        
        run = SARIFBuilder.create_run("zap", raw_output.get('version', 'unknown'))
        
        # Handle custom format with top-level alerts
        if 'alerts' in raw_output and isinstance(raw_output['alerts'], list):
            alerts = raw_output['alerts']
        # Handle native ZAP format with site structure
        elif 'site' in raw_output and isinstance(raw_output['site'], list):
            alerts = []
            for site in raw_output['site']:
                if isinstance(site, dict) and 'alerts' in site:
                    alerts.extend(site['alerts'])
        else:
            logger.warning("No alerts found in ZAP output")
            return run
        
        for alert in alerts:
            if not isinstance(alert, dict):
                continue
            
            # Extract risk level
            risk = alert.get('risk', alert.get('riskdesc', 'medium')).lower()
            if isinstance(risk, str):
                # Handle "High (Medium)" format
                risk = risk.split('(')[0].strip().lower()
            
            # Map numeric risk codes to text
            risk_code = alert.get('riskcode')
            if risk_code is not None:
                risk_map = {0: 'informational', 1: 'low', 2: 'medium', 3: 'high'}
                risk = risk_map.get(int(risk_code), 'medium')
            
            level = RISK_TO_LEVEL.get(risk, 'warning')
            
            # Extract confidence
            confidence_raw = alert.get('confidence', 'medium')
            if isinstance(confidence_raw, str):
                # If it's already a string like 'low', 'medium', 'high', use it directly
                confidence = confidence_raw.split('(')[0].strip().lower()
            elif isinstance(confidence_raw, (int, float)):
                # If it's a numeric code, map it
                conf_map = {1: 'low', 2: 'medium', 3: 'high'}
                confidence = conf_map.get(int(confidence_raw), 'medium')
            else:
                confidence = 'medium'
            
            # Extract CWE and WASC
            cwe_id = None
            cweid_str = alert.get('cweid')
            if cweid_str:
                try:
                    cwe_id = int(str(cweid_str).strip())
                except (ValueError, AttributeError):
                    pass
            
            wasc_id = None
            wascid_str = alert.get('wascid')
            if wascid_str:
                try:
                    wasc_id = int(str(wascid_str).strip())
                except (ValueError, AttributeError):
                    pass
            
            # Extract description (strip HTML tags if present)
            description = alert.get('description', alert.get('desc', 'No description'))
            if isinstance(description, str):
                # Simple HTML tag removal
                import re
                description = re.sub(r'<[^>]+>', '', description).strip()
            
            # Extract solution and reference
            solution = alert.get('solution', '')
            if isinstance(solution, str):
                solution = re.sub(r'<[^>]+>', '', solution).strip()
            
            reference = alert.get('reference', '')
            if isinstance(reference, str):
                reference = re.sub(r'<[^>]+>', '', reference).strip()
            
            # Process instances
            instances = alert.get('instances', [])
            if not instances:
                # Create single result without specific instance
                result = SARIFBuilder.create_result(
                    rule_id=alert.get('pluginid', alert.get('alert', 'UNKNOWN')),
                    message=f"{alert.get('alert', alert.get('name', 'Security Issue'))}: {description}",
                    level=level,
                    risk=risk,
                    confidence=confidence,
                    cwe=cwe_id,
                    wasc=wasc_id,
                    solution=solution if solution else None,
                    reference=reference if reference else None
                )
                run["results"].append(result)
            else:
                # Create result per instance
                for instance in instances:
                    if not isinstance(instance, dict):
                        continue
                    
                    uri = instance.get('uri', '')
                    method = instance.get('method', '')
                    param = instance.get('param', '')
                    attack = instance.get('attack', '')
                    evidence = instance.get('evidence', '')
                    
                    # Build detailed message
                    message_parts = [alert.get('alert', alert.get('name', 'Security Issue'))]
                    if param:
                        message_parts.append(f"Parameter: {param}")
                    if attack:
                        message_parts.append(f"Attack: {attack}")
                    if evidence:
                        message_parts.append(f"Evidence: {evidence}")
                    message_parts.append(description)
                    
                    result = SARIFBuilder.create_result(
                        rule_id=alert.get('pluginid', alert.get('alert', 'UNKNOWN')),
                        message=". ".join(message_parts),
                        level=level,
                        uri=uri if uri else None,
                        method=method if method else None,
                        risk=risk,
                        confidence=confidence,
                        cwe=cwe_id,
                        wasc=wasc_id,
                        solution=solution if solution else None,
                        reference=reference if reference else None
                    )
                    run["results"].append(result)
        
        return run


# Parser registry
SARIF_PARSERS = {
    'zap': ZAPSARIFParser
}


def get_available_sarif_parsers() -> List[str]:
    """Get list of tools with SARIF parser support."""
    return list(SARIF_PARSERS.keys())


def parse_tool_output_to_sarif(
    tool_name: str,
    raw_output: Any,
    config: Optional[Dict] = None
) -> Optional[Dict[str, Any]]:
    """
    Parse tool output to SARIF format using the appropriate parser.
    
    Args:
        tool_name: Name of the tool (e.g., 'zap')
        raw_output: Raw tool output
        config: Optional configuration dict
        
    Returns:
        SARIF run dict or None if parser not found
    """
    parser_class = SARIF_PARSERS.get(tool_name.lower())
    
    if not parser_class:
        logger.warning(f"No SARIF parser found for tool: {tool_name}")
        return None
    
    try:
        return parser_class.parse(raw_output, config)
    except Exception as e:
        logger.error(f"Error parsing {tool_name} output to SARIF: {e}", exc_info=True)
        return None


def build_sarif_document(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build a complete SARIF 2.1.0 document from multiple runs.
    
    Args:
        runs: List of SARIF run objects
        
    Returns:
        Complete SARIF document
    """
    return {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": runs
    }
