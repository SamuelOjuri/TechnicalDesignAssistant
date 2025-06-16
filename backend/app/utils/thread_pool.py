from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Callable, Any
from flask import Flask, current_app
import functools
import logging
import time

logger = logging.getLogger(__name__)

def with_app_context(app: Flask, func: Callable) -> Callable:
    """
    Decorator to ensure function runs within app context.
    
    Args:
        app: Flask application instance
        func: Function to wrap with app context
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with app.app_context():
            return func(*args, **kwargs)
    return wrapper

def process_items_in_parallel(
    items: List[Tuple[str, Any]], 
    process_func: Callable, 
    max_workers: int = 7,  
    batch_size: int = None  # Optional batch size for large sets
) -> List[Tuple[str, Any]]:
    """
    Process items in parallel using a thread pool.
    
    Args:
        items: List of (type, item) tuples to process
        process_func: Function that processes a single item
        max_workers: Maximum number of worker threads
        batch_size: Optional size for processing in batches
        
    Returns:
        List of (filename, processed_text) tuples
    """
    all_results = []
    app = current_app._get_current_object()
    
    def run_with_context(*args, **kwargs):
        with app.app_context():
            start_time = time.time()
            result = process_func(*args, **kwargs)
            logger.info(f"Thread completed processing in {time.time() - start_time:.2f}s")
            return result
    
    # Process items in batches if batch_size is specified
    if batch_size:
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1} of {(len(items) + batch_size - 1)//batch_size}")
            batch_results = []
            
            with ThreadPoolExecutor(max_workers=min(max_workers, len(batch))) as executor:
                # Submit all jobs in this batch simultaneously
                future_to_item = {
                    executor.submit(run_with_context, item_type, item): (item_type, item)
                    for item_type, item in batch
                }
                
                # Wait for all futures to complete
                for future in as_completed(future_to_item):
                    item_type, item = future_to_item[future]
                    try:
                        filename, text = future.result()
                        batch_results.append((filename, text))
                        logger.info(f"Completed processing {filename}")
                    except Exception as e:
                        if isinstance(item, dict):
                            filename = item.get('filename', 'unknown')
                        elif isinstance(item, list) and len(item) > 0 and isinstance(item[0], dict):
                            filename = f"batch_of_{len(item)}_items"
                        else:
                            filename = item[0] if item else 'unknown'
                        logger.error(f"Error processing {filename}: {str(e)}")
                        batch_results.append((
                            filename,
                            f"Error processing file: {str(e)}"
                        ))
            
            all_results.extend(batch_results)
    else:
        # Process all items at once - optimized for ≤10 items
        logger.info(f"Processing all {len(items)} items concurrently")
        with ThreadPoolExecutor(max_workers=min(max_workers, len(items))) as executor:
            # Submit all jobs simultaneously
            future_to_item = {
                executor.submit(run_with_context, item_type, item): (item_type, item)
                for item_type, item in items
            }
            
            # Wait for all futures to complete
            for future in as_completed(future_to_item):
                item_type, item = future_to_item[future]
                try:
                    filename, text = future.result()
                    all_results.append((filename, text))
                    logger.info(f"Completed processing {filename}")
                except Exception as e:
                    if isinstance(item, dict):
                        filename = item.get('filename', 'unknown')
                    elif isinstance(item, list) and len(item) > 0 and isinstance(item[0], dict):
                        filename = f"batch_of_{len(item)}_items"
                    else:
                        filename = item[0] if item else 'unknown'
                    logger.error(f"Error processing {filename}: {str(e)}")
                    all_results.append((
                        filename,
                        f"Error processing file: {str(e)}"
                    ))
    
    return all_results
