"""
Parallel processing utilities for Workflowy projects.
Optimizes content scraping while maintaining sequential tweet posting.
"""

import asyncio
import time
from typing import List, Dict
from workflowy.config.logger import structured_logger, LogContext
from workflowy.core.scraper.main import WorkflowyTesterV2


async def process_projects_in_batches(projects: List[Dict], environment: str, 
                                    batch_size: int = 10, 
                                    delay_between_batches: float = 1.0) -> List[Dict]:
    """
    Process projects in controlled batches to optimize performance while minimizing API risk.
    
    Args:
        projects: List of project configurations
        environment: Environment string
        batch_size: Number of projects to process concurrently (default: 10)
        delay_between_batches: Delay in seconds between batches (default: 1.0)
    
    Returns:
        List of processing results
    """
    all_results = []
    total_batches = (len(projects) + batch_size - 1) // batch_size
    
    structured_logger.info_operation("process_projects_in_batches", 
                                   f"🔄 Processing {len(projects)} projects in {total_batches} batches of {batch_size}")
    
    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, len(projects))
        batch_projects = projects[start_idx:end_idx]
        
        structured_logger.info_operation("process_projects_in_batches", 
                                       f"📦 Processing batch {batch_num + 1}/{total_batches} ({len(batch_projects)} projects)")
        
        batch_start_time = time.time()
        
        # Process batch concurrently with proper context isolation
        import contextvars
        
        # Create tasks with explicit context copying for each project
        batch_tasks = []
        for project in batch_projects:
            # Copy the current context and create a task in that context
            ctx = contextvars.copy_context()
            task = asyncio.create_task(
                process_single_project_in_batch(project, environment),
                context=ctx
            )
            batch_tasks.append(task)
        
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
        
        # Handle any exceptions from gather
        processed_batch_results = []
        for i, result in enumerate(batch_results):
            if isinstance(result, Exception):
                project_id = batch_projects[i]['project_id']
                structured_logger.error_operation("process_projects_in_batches", 
                                                f"❌ Batch processing exception for project {project_id}: {result}")
                processed_batch_results.append({
                    'project_id': project_id,
                    'status': 'error',
                    'error': str(result)
                })
            else:
                processed_batch_results.append(result)
        
        all_results.extend(processed_batch_results)
        
        batch_duration = time.time() - batch_start_time
        successful_in_batch = len([r for r in processed_batch_results if r and r.get('status') == 'success'])
        
        structured_logger.info_operation("process_projects_in_batches", 
                                       f"✅ Batch {batch_num + 1} complete: {successful_in_batch}/{len(batch_projects)} successful in {batch_duration:.1f}s")
        
        # Respectful delay between batches (except for last batch)
        if batch_num < total_batches - 1:
            structured_logger.info_operation("process_projects_in_batches", 
                                           f"⏱️ Waiting {delay_between_batches}s before next batch...")
            await asyncio.sleep(delay_between_batches)
    
    successful_total = len([r for r in all_results if r and r.get('status') == 'success'])
    structured_logger.info_operation("process_projects_in_batches", 
                                   f"🏁 All batches complete: {successful_total}/{len(projects)} projects successful")
    
    return all_results


async def process_single_project_in_batch(project: Dict, environment: str) -> Dict:
    """
    Process a single project within a batch, with proper isolation and error handling.
    Sets context for each individual task to ensure proper logging throughout the call chain.
    
    Args:
        project: Project configuration dictionary
        environment: Environment string
    
    Returns:
        Processing result dictionary
    """
    project_id = project['project_id']
    project_name = project['name']
    
    # ✅ Set context for this specific task/coroutine - this will propagate through the call chain
    LogContext.set_project_context(project_id, project_name)
    
    try:
        # Each task gets its own tester instance to avoid session conflicts
        async with WorkflowyTesterV2(environment) as tester:
            structured_logger.info_operation(
                "process_single_project_in_batch", 
                f"🔄 Processing project: {project_name} ({project_id})",
                project_id=project_id, 
                project_name=project_name
            )
            
            result = await tester.process_single_project(project_id)
            
            structured_logger.info_operation(
                "process_single_project_in_batch",
                f"✅ Completed project: {project_name} ({project_id})",
                project_id=project_id,
                project_name=project_name,
                status=result.get('status', 'unknown') if result else 'none'
            )
            
            return result
            
    except Exception as e:
        structured_logger.error_operation(
            "process_single_project_in_batch", 
            f"❌ Error processing project {project_id}: {e}",
            project_id=project_id, 
            project_name=project_name,
            error=str(e)
        )
        return {
            'project_id': project_id,
            'status': 'error',
            'error': str(e)
        }
    finally:
        # ✅ Clean up context for this task
        LogContext.clear_project_context()
