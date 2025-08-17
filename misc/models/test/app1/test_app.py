#!/usr/bin/env python3
"""
Test application with intentional security issues for testing.
"""
import os
import subprocess

# Security issue: hardcoded password
PASSWORD = "admin123"

# Security issue: SQL injection vulnerability
def get_user(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    return query

# Security issue: command injection
def run_command(cmd):
    os.system(cmd)

# Security issue: eval usage
def calculate(expression):
    return eval(expression)

# Security issue: weak random
import random
def generate_token():
    return str(random.randint(1000, 9999))

if __name__ == "__main__":
    print("Test application with security issues")
