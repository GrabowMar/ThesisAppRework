"""
Install all CLI analysis tools for the security analysis system.
This script installs all required tools for comprehensive code analysis.
"""

import subprocess
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_command(command, description):
    """Run a command and return success status."""
    try:
        logger.info(f"Installing {description}...")
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=False)
        
        if result.returncode == 0:
            logger.info(f"✅ {description} installed successfully")
            return True
        else:
            logger.warning(f"⚠️ {description} installation had issues: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"❌ Failed to install {description}: {e}")
        return False

def install_python_tools():
    """Install Python-based analysis tools."""
    python_tools = [
        (f"{sys.executable} -m pip install bandit", "Bandit (Python security)"),
        (f"{sys.executable} -m pip install safety", "Safety (dependency vulnerabilities)"),
        (f"{sys.executable} -m pip install pylint", "Pylint (code quality)"),
        (f"{sys.executable} -m pip install vulture", "Vulture (dead code detection)"),
        (f"{sys.executable} -m pip install flake8", "Flake8 (style guide)"),
        (f"{sys.executable} -m pip install radon", "Radon (complexity analysis)"),
    ]
    
    results = []
    for command, description in python_tools:
        results.append(run_command(command, description))
    
    return results

def install_node_tools():
    """Install Node.js-based analysis tools."""
    # Check if npm is available
    try:
        subprocess.run(["npm", "--version"], capture_output=True, check=True)
        logger.info("✅ npm is available")
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.error("❌ npm not found. Please install Node.js first.")
        return [False] * 6
    
    node_tools = [
        ("npm install -g eslint", "ESLint (JavaScript linting)"),
        ("npm install -g prettier", "Prettier (code formatting)"),
        ("npm install -g jshint", "JSHint (JavaScript quality)"),
        ("npm install -g retire", "Retire.js (vulnerability scanning)"),
        ("npm install -g snyk", "Snyk (security scanning)"),
    ]
    
    results = []
    for command, description in node_tools:
        results.append(run_command(command, description))
    
    return results

def check_tool_availability():
    """Check which tools are available after installation."""
    logger.info("\n🔍 Checking tool availability...")
    
    tools_to_check = [
        # Python tools
        ([sys.executable, "-m", "bandit", "--version"], "Bandit"),
        ([sys.executable, "-m", "safety", "--version"], "Safety"),
        ([sys.executable, "-m", "pylint", "--version"], "Pylint"),
        ([sys.executable, "-m", "vulture", "--version"], "Vulture"),
        ([sys.executable, "-m", "flake8", "--version"], "Flake8"),
        ([sys.executable, "-m", "radon", "--version"], "Radon"),
        
        # Node.js tools
        (["eslint", "--version"], "ESLint"),
        (["prettier", "--version"], "Prettier"),
        (["jshint", "--version"], "JSHint"),
        (["retire", "--version"], "Retire.js"),
        (["snyk", "--version"], "Snyk"),
    ]
    
    available_tools = []
    for command, name in tools_to_check:
        try:
            result = subprocess.run(command, capture_output=True, check=True)
            logger.info(f"✅ {name} - Available")
            available_tools.append(name)
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning(f"❌ {name} - Not Available")
    
    logger.info(f"\n📊 Summary: {len(available_tools)}/{len(tools_to_check)} tools available")
    return available_tools

def main():
    """Main installation process."""
    logger.info("🚀 Starting CLI tools installation...")
    
    # Install Python tools
    logger.info("\n📦 Installing Python tools...")
    python_results = install_python_tools()
    
    # Install Node.js tools
    logger.info("\n📦 Installing Node.js tools...")
    node_results = install_node_tools()
    
    # Check final availability
    available_tools = check_tool_availability()
    
    # Summary
    total_python = len(python_results)
    successful_python = sum(python_results)
    total_node = len(node_results)
    successful_node = sum(node_results)
    
    logger.info(f"\n📈 Installation Summary:")
    logger.info(f"   Python tools: {successful_python}/{total_python} successful")
    logger.info(f"   Node.js tools: {successful_node}/{total_node} successful")
    logger.info(f"   Total available: {len(available_tools)} tools")
    
    if len(available_tools) >= 10:
        logger.info("🎉 Great! Most tools are available for comprehensive analysis.")
    elif len(available_tools) >= 6:
        logger.info("👍 Good! Basic analysis tools are available.")
    else:
        logger.warning("⚠️ Limited tools available. Consider installing Node.js for frontend analysis.")

if __name__ == "__main__":
    main()
