"""
Test script for parallel processing functionality.
"""
import asyncio
import os
from pathlib import Path
import time
import sys

# Add the root directory to Python path BEFORE any workflowy imports
script_dir = Path(__file__).parent  # scripts directory
workflowy_dir = script_dir.parent   # workflowy directory
root_dir = workflowy_dir.parent     # BrainLiftTracker (root)
sys.path.insert(0, str(root_dir))

from workflowy.lambda_handler import process_and_post_v2
from workflowy.config.logger import structured_logger


async def test_parallel_processing():
    """Test the parallel processing with controlled parameters."""
    
    # Test configurations
    test_configs = [
        # {"batch_size": 3, "delay": 2.0, "parallel": True, "name": "Small Batch Test"},
        # {"batch_size": 8, "delay": 1.0, "parallel": True, "name": "Medium Batch Test"}
        {"batch_size": 1, "delay": 0.0, "parallel": False, "name": "Sequential (Control)"}
    ]
    
    print("🧪 PARALLEL PROCESSING TEST SUITE")
    print("=" * 60)
    
    for i, config in enumerate(test_configs, 1):
        print(f"\n🔬 Test {i}/{len(test_configs)}: {config['name']}")
        print(f"   📦 Batch Size: {config['batch_size']}")
        print(f"   ⏱️  Delay: {config['delay']}s")
        print(f"   🔄 Parallel: {config['parallel']}")
        print("-" * 40)
        
        # Set environment variables
        os.environ['WORKFLOWY_ENABLE_PARALLEL_PROCESSING'] = str(config['parallel']).lower()
        os.environ['WORKFLOWY_BATCH_SIZE'] = str(config['batch_size'])
        os.environ['WORKFLOWY_DELAY_BETWEEN_BATCHES'] = str(config['delay'])
        
        start_time = time.time()
        
        try:
            results = await process_and_post_v2('test')
            end_time = time.time()
            
            processing_successful = len([r for r in results['processing_results'] if r and r.get('status') == 'success'])
            processing_total = len(results['processing_results'])
            duration = end_time - start_time
            
            print(f"   ✅ Results: {processing_successful}/{processing_total} successful")
            print(f"   ⏱️  Duration: {duration:.1f}s")
            
            if processing_total > 0:
                avg_per_project = duration / processing_total
                print(f"   📊 Avg per project: {avg_per_project:.1f}s")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            structured_logger.error_operation("test_parallel_processing", f"Test failed: {e}")

    print(f"\n🏁 All tests completed!")


async def test_single_batch():
    """Quick test with a single small batch."""
    print("🚀 QUICK BATCH TEST")
    print("=" * 30)
    
    # Set test configuration
    os.environ['WORKFLOWY_ENABLE_PARALLEL_PROCESSING'] = 'true'
    os.environ['WORKFLOWY_BATCH_SIZE'] = '3'
    os.environ['WORKFLOWY_DELAY_BETWEEN_BATCHES'] = '1.0'
    
    start_time = time.time()
    
    try:
        results = await process_and_post_v2('test')
        end_time = time.time()
        
        processing_successful = len([r for r in results['processing_results'] if r and r.get('status') == 'success'])
        processing_total = len(results['processing_results'])
        duration = end_time - start_time
        
        print(f"✅ Quick test completed!")
        print(f"📊 Results: {processing_successful}/{processing_total} successful in {duration:.1f}s")
        
    except Exception as e:
        print(f"❌ Quick test failed: {e}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "quick":
        # Quick test mode
        asyncio.run(test_single_batch())
    else:
        # Full test suite
        asyncio.run(test_parallel_processing())
