#!/usr/bin/env python3
"""
Quick test script for verifying all agents through supervisor.

This is a simplified version for quick validation during development.
"""

import asyncio
import httpx
import json


async def quick_test():
    """Quick test of all agents through supervisor."""
    
    print("🚀 Quick Multi-Agent Test")
    print("=" * 30)
    
    supervisor_url = "http://localhost:8000"
    
    # Quick test cases - one per agent type
    test_cases = [
        {
            "name": "Order Management",
            "query": "What is the status of order ORD-2024-001?",
            "customer_id": "cust001",
            "expected_agent": "order_management"
        },
        {
            "name": "Product Recommendation", 
            "query": "Can you recommend some good headphones?",
            "customer_id": "cust001",
            "expected_agent": "product_recommendation"
        },
        {
            "name": "Troubleshooting",
            "query": "My wireless headphones won't connect",
            "customer_id": "cust001", 
            "expected_agent": "troubleshooting"
        },
        {
            "name": "Personalization",
            "query": "What information do you have about my profile?",
            "customer_id": "cust001",
            "expected_agent": "personalization"
        },
        {
            "name": "Multi-Agent",
            "query": "Check my order status and recommend similar products",
            "customer_id": "cust001",
            "expected_agents": ["order_management", "product_recommendation"]
        }
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        # Check supervisor health
        try:
            response = await client.get(f"{supervisor_url}/health")
            if response.status_code == 200:
                print("✅ Supervisor is running")
            else:
                print("❌ Supervisor not available")
                return
        except Exception as e:
            print(f"❌ Cannot reach supervisor: {e}")
            return
        
        success_count = 0
        total_tests = len(test_cases)
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n{i}. {test_case['name']}:")
            print(f"   Query: {test_case['query']}")
            
            request_data = {
                "customer_message": test_case['query'],
                "session_id": f"quick-test-{i}",
                "customer_id": test_case.get('customer_id')
            }
            
            try:
                response = await client.post(
                    f"{supervisor_url}/process",
                    json=request_data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    agents_called = [str(agent).lower().replace('agenttype.', '') for agent in result.get('agents_called', [])]
                    confidence = result.get('confidence_score', 0)
                    response_text = result.get('response', '')
                    
                    print(f"   ✅ Response: {response_text[:100]}...")
                    print(f"   🎯 Agents: {agents_called}")
                    print(f"   📊 Confidence: {confidence:.2f}")
                    
                    # Check if expected agent was called
                    if 'expected_agents' in test_case:
                        # Multi-agent case
                        expected = test_case['expected_agents']
                        if any(exp in agents_called for exp in expected):
                            print("   ✅ Expected agents called")
                            success_count += 1
                        else:
                            print(f"   ❌ Expected {expected}, got {agents_called}")
                    else:
                        # Single agent case
                        expected = test_case['expected_agent']
                        if expected in agents_called:
                            print("   ✅ Correct agent called")
                            success_count += 1
                        else:
                            print(f"   ❌ Expected {expected}, got {agents_called}")
                else:
                    print(f"   ❌ HTTP Error: {response.status_code}")
                    
            except Exception as e:
                print(f"   ❌ Request failed: {e}")
        
        print(f"\n📊 Results: {success_count}/{total_tests} tests passed")
        
        if success_count == total_tests:
            print("🎉 All agents working correctly through supervisor!")
        else:
            print("⚠️  Some tests failed - check agent configurations")


if __name__ == "__main__":
    asyncio.run(quick_test())