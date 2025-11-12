"""
Master Synchronization Service

This module orchestrates all data synchronization and analysis tasks in a single workflow:
1. Historical Data Sync (or Download if first time)
2. Market Cap Fetch
3. Generate Historical Indices
4. Stage Analysis (Sectors/Subsectors)
5. Stock Stage Analysis
6. Relative Strength Calculation
7. Volume Dry-Up Analysis
"""

import time
import threading
import json
from datetime import datetime, timedelta, date
from typing import Optional, Tuple, Dict
from flask import current_app
from app import db
from app.models import (
    User, MasterSyncTask, DownloadTask, SyncTask, MarketCapFetchTask,
    StageAnalysisTask, StockStageAnalysisTask, RSCalculationTask,
    VolumeDryUpTask, HistoricalData, HistoricalDataSettings
)
from app.download_service import create_download_task
from app.sync_service import start_sync_task
from app.marketcap_service import create_marketcap_fetch_task
from app.historical_index_service import HistoricalIndexService
from app.stage_analysis_service import start_stage_analysis
from app.stock_stage_analysis_service import start_stock_stage_analysis
from app.rs_calculation_service import start_rs_calculation
from app.volume_dryup_service import start_volume_dryup_analysis


# Global dictionary to store active master sync tasks
active_master_syncs = {}

# Step weights for progress calculation (total = 100%)
STEP_WEIGHTS = {
    1: 30,  # Historical Data Sync
    2: 20,  # Generate Indices
    3: 20,  # Stage Analysis
    4: 15,  # Stock Stage Analysis
    5: 10,  # RS Calculation
    6: 5    # Volume Dry-Up
}

# Step names
STEP_NAMES = {
    1: "Sync Historical Data",
    2: "Generate Historical Indices",
    3: "Analyze Sector/SubSector Stages",
    4: "Analyze Individual Stock Stages",
    5: "Calculate Relative Strength",
    6: "Run Volume Dry-Up Analysis"
}


def start_master_sync(user_id: int, app) -> Tuple[bool, str, Optional[int]]:
    """
    Start a new master synchronization task

    Args:
        user_id: ID of the user
        app: Flask app instance

    Returns:
        Tuple of (success, message, task_id)
    """
    try:
        # Check if there's already an active master sync task
        existing_task = MasterSyncTask.query.filter_by(
            user_id=user_id,
            status='running'
        ).first()

        if existing_task:
            return False, 'A master sync task is already running', None

        # Pre-flight checks
        user = User.query.get(user_id)
        if not user:
            return False, 'User not found', None

        # Check Kite connection
        if not user.kite_connected or not user.kite_access_token:
            return False, 'Please connect to Kite Connect first in Settings > Kite Connect', None

        # Check historical data settings
        settings = HistoricalDataSettings.query.filter_by(user_id=user_id).first()
        if not settings:
            return False, 'Please configure historical data settings first in Settings > Historical Data', None

        # Create new master sync task
        task = MasterSyncTask(
            user_id=user_id,
            status='pending',
            current_step=0,
            progress_percentage=0.0
        )
        db.session.add(task)
        db.session.commit()

        # Initialize step_details JSON
        step_details = {}
        for step_num in range(1, 7):  # Changed from 8 to 7 (6 steps now)
            step_details[str(step_num)] = {
                'status': 'pending',
                'progress': 0,
                'message': ''
            }
        task.step_details = json.dumps(step_details)
        db.session.commit()

        # Start master sync in background thread
        orchestrator = MasterSyncOrchestrator(task.id, app)
        orchestrator.start_sync()

        current_app.logger.info(f'Started master sync task {task.id} for user {user_id}')

        return True, 'Master sync started successfully', task.id

    except Exception as e:
        current_app.logger.error(f'Error starting master sync: {str(e)}')
        return False, str(e), None


def get_master_sync_status(user_id: int) -> Optional[dict]:
    """
    Get the status of the current master sync task for a user

    Args:
        user_id: ID of the user

    Returns:
        Dictionary with master sync status or None
    """
    try:
        task = MasterSyncTask.query.filter_by(user_id=user_id).order_by(
            MasterSyncTask.created_at.desc()
        ).first()

        if not task:
            return None

        # Get task dict
        task_dict = task.to_dict()

        # Aggregate subtask statuses
        subtask_statuses = {}

        if task.download_task:
            subtask_statuses['download'] = task.download_task.to_dict()
        if task.sync_task:
            subtask_statuses['sync'] = task.sync_task.to_dict()
        if task.marketcap_task:
            subtask_statuses['marketcap'] = task.marketcap_task.to_dict()
        if task.stage_analysis_task:
            subtask_statuses['stage_analysis'] = task.stage_analysis_task.to_dict()
        if task.stock_stage_task:
            subtask_statuses['stock_stage'] = task.stock_stage_task.to_dict()
        if task.rs_calculation_task:
            subtask_statuses['rs_calculation'] = task.rs_calculation_task.to_dict()
        if task.volume_dryup_task:
            subtask_statuses['volume_dryup'] = task.volume_dryup_task.to_dict()

        task_dict['subtask_statuses'] = subtask_statuses

        return task_dict

    except Exception as e:
        current_app.logger.error(f'Error getting master sync status: {str(e)}')
        return None


def cancel_master_sync(task_id: int) -> Tuple[bool, str]:
    """
    Cancel a running master sync task

    Args:
        task_id: ID of the task to cancel

    Returns:
        Tuple of (success, message)
    """
    try:
        task = MasterSyncTask.query.get(task_id)
        if not task:
            return False, 'Task not found'

        if task.status not in ['pending', 'running']:
            return False, f'Cannot cancel task with status: {task.status}'

        # Mark as cancelled
        task.status = 'cancelled'
        task.completed_at = datetime.utcnow()
        db.session.commit()

        # Stop any running subtasks
        # (Individual services should check parent task status)

        current_app.logger.info(f'Cancelled master sync task {task_id}')

        return True, 'Master sync task cancelled'

    except Exception as e:
        current_app.logger.error(f'Error cancelling master sync: {str(e)}')
        return False, str(e)


class MasterSyncOrchestrator:
    """Orchestrates the execution of all sync and analysis tasks"""

    def __init__(self, task_id: int, app):
        self.task_id = task_id
        self.app = app
        self.should_stop = False

    def start_sync(self):
        """Start the master sync in a background thread"""
        thread = threading.Thread(
            target=self._execute_sync_pipeline,
            args=(self.task_id, self.app),
            daemon=True
        )
        thread.start()

        # Store in active syncs
        active_master_syncs[self.task_id] = {
            'thread': thread,
            'orchestrator': self
        }

    def _execute_sync_pipeline(self, task_id: int, app):
        """
        Execute all sync steps in sequence

        Args:
            task_id: ID of the master sync task
            app: Flask app instance
        """
        with app.app_context():
            try:
                task = MasterSyncTask.query.get(task_id)
                if not task:
                    return

                # Mark as running
                task.status = 'running'
                task.started_at = datetime.utcnow()
                db.session.commit()

                current_app.logger.info(f'Master sync task {task_id}: Starting pipeline')

                # Execute each step (removed Market Cap Fetch - step 2)
                steps = [
                    self._step_1_sync_historical_data,
                    self._step_2_generate_indices,          # Was step 3
                    self._step_3_stage_analysis,            # Was step 4
                    self._step_4_stock_stage_analysis,      # Was step 5
                    self._step_5_rs_calculation,            # Was step 6
                    self._step_6_volume_dryup               # Was step 7
                ]

                for step_num, step_func in enumerate(steps, 1):
                    if self.should_stop or task.status == 'cancelled':
                        current_app.logger.info(f'Master sync task {task_id}: Stopped at step {step_num}')
                        break

                    # Update current step
                    task.current_step = step_num
                    task.current_step_name = STEP_NAMES[step_num]
                    db.session.commit()

                    # Execute step
                    success, message = step_func(task)

                    if not success:
                        # Step failed
                        self._mark_step_failed(task, step_num, message)
                        task.status = 'failed'
                        task.error_message = f'Step {step_num} ({STEP_NAMES[step_num]}) failed: {message}'
                        task.completed_at = datetime.utcnow()
                        db.session.commit()
                        current_app.logger.error(f'Master sync task {task_id}: Failed at step {step_num}')
                        return

                    # Step succeeded
                    self._mark_step_completed(task, step_num, message)

                # All steps completed
                task.status = 'completed'
                task.progress_percentage = 100.0
                task.completed_at = datetime.utcnow()
                db.session.commit()

                current_app.logger.info(f'Master sync task {task_id}: Completed successfully')

            except Exception as e:
                task.status = 'failed'
                task.error_message = str(e)
                task.completed_at = datetime.utcnow()
                db.session.commit()
                current_app.logger.error(f'Master sync task {task_id}: Exception - {str(e)}')

            finally:
                # Remove from active syncs
                if task_id in active_master_syncs:
                    del active_master_syncs[task_id]

    def _update_progress(self, task: MasterSyncTask, step_num: int, step_progress: float):
        """
        Update overall progress based on step progress

        Args:
            task: MasterSyncTask instance
            step_num: Current step number (1-7)
            step_progress: Progress of current step (0-100)
        """
        # Calculate progress of completed steps
        completed_progress = sum(STEP_WEIGHTS[i] for i in range(1, step_num))

        # Add progress of current step
        current_step_contribution = (step_progress / 100.0) * STEP_WEIGHTS[step_num]

        total_progress = completed_progress + current_step_contribution

        task.progress_percentage = min(total_progress, 100.0)
        db.session.commit()

    def _mark_step_completed(self, task: MasterSyncTask, step_num: int, message: str = ''):
        """Mark a step as completed"""
        step_details = json.loads(task.step_details) if task.step_details else {}
        step_details[str(step_num)] = {
            'status': 'completed',
            'progress': 100,
            'message': message
        }
        task.step_details = json.dumps(step_details)
        self._update_progress(task, step_num, 100)

    def _mark_step_failed(self, task: MasterSyncTask, step_num: int, error_message: str):
        """Mark a step as failed"""
        step_details = json.loads(task.step_details) if task.step_details else {}
        step_details[str(step_num)] = {
            'status': 'failed',
            'progress': 0,
            'message': error_message
        }
        task.step_details = json.dumps(step_details)

        error_details = json.loads(task.error_details) if task.error_details else {}
        error_details[f'step_{step_num}'] = error_message
        task.error_details = json.dumps(error_details)
        db.session.commit()

    def _wait_for_subtask(self, subtask, step_num: int, task: MasterSyncTask, poll_interval: int = 3) -> Tuple[bool, str]:
        """
        Wait for a subtask to complete and update progress

        Args:
            subtask: The subtask object (DownloadTask, SyncTask, etc.)
            step_num: Current step number
            task: MasterSyncTask instance
            poll_interval: Seconds between status checks

        Returns:
            Tuple of (success, message)
        """
        while True:
            if self.should_stop or task.status == 'cancelled':
                return False, 'Cancelled by user'

            # Refresh subtask from database
            db.session.refresh(subtask)

            if subtask.status == 'completed':
                return True, 'Completed successfully'

            elif subtask.status == 'failed':
                error_msg = getattr(subtask, 'error_message', 'Unknown error')
                return False, error_msg

            elif subtask.status == 'cancelled':
                return False, 'Subtask was cancelled'

            elif subtask.status in ['running', 'pending']:
                # Update progress
                progress = getattr(subtask, 'progress_percentage', 0)
                self._update_progress(task, step_num, progress)

                # Wait before next check
                time.sleep(poll_interval)

            else:
                return False, f'Unknown subtask status: {subtask.status}'

    # ==================== STEP IMPLEMENTATIONS ====================

    def _step_1_sync_historical_data(self, task: MasterSyncTask) -> Tuple[bool, str]:
        """Step 1: Sync or download historical data"""
        try:
            current_app.logger.info(f'Master sync {task.id}: Step 1 - Historical data sync')

            # Check if historical data exists
            existing_data_count = HistoricalData.query.count()

            if existing_data_count > 0:
                # Sync latest data
                success, message, subtask_id = start_sync_task(task.user_id, self.app)

                if not success:
                    return False, f'Failed to start sync: {message}'

                # Link subtask
                task.sync_task_id = subtask_id
                db.session.commit()

                # Wait for completion
                subtask = SyncTask.query.get(subtask_id)
                return self._wait_for_subtask(subtask, 1, task)

            else:
                # First time - full download
                subtask = create_download_task(task.user_id)

                if not subtask:
                    return False, 'Failed to create download task - settings not configured'

                # Link subtask
                task.download_task_id = subtask.id
                db.session.commit()

                # Wait for completion
                return self._wait_for_subtask(subtask, 1, task)

        except Exception as e:
            return False, str(e)

    def _step_2_generate_indices(self, task: MasterSyncTask) -> Tuple[bool, str]:
        """Step 2: Generate historical indices"""
        try:
            current_app.logger.info(f'Master sync {task.id}: Step 2 - Generate indices')

            # Determine date range (from last index date to today)
            # For now, generate last 60 days
            end_date = date.today()
            start_date = end_date - timedelta(days=60)

            # Create index service instance
            index_service = HistoricalIndexService()

            # Generate indices (this is synchronous)
            result = index_service.generate_all_indices(start_date, end_date)

            if result.get('success'):
                stats = result.get('statistics', {})
                message = f"Generated indices for {stats.get('total_dates', 0)} dates"
                self._update_progress(task, 3, 100)
                return True, message
            else:
                error = result.get('error', 'Unknown error')
                return False, f'Index generation failed: {error}'

        except Exception as e:
            return False, str(e)

    def _step_3_stage_analysis(self, task: MasterSyncTask) -> Tuple[bool, str]:
        """Step 4: Stage analysis for sectors/subsectors"""
        try:
            current_app.logger.info(f'Master sync {task.id}: Step 3 - Stage analysis')

            success, message, subtask_id = start_stage_analysis(task.user_id, self.app)

            if not success:
                return False, f'Failed to start stage analysis: {message}'

            # Link subtask
            task.stage_analysis_task_id = subtask_id
            db.session.commit()

            # Wait for completion
            subtask = StageAnalysisTask.query.get(subtask_id)
            return self._wait_for_subtask(subtask, 3, task)

        except Exception as e:
            return False, str(e)

    def _step_4_stock_stage_analysis(self, task: MasterSyncTask) -> Tuple[bool, str]:
        """Step 5: Stock stage analysis for all NIFTY 500 stocks"""
        try:
            current_app.logger.info(f'Master sync {task.id}: Step 4 - Stock stage analysis')

            # Run for NIFTY 500 stocks
            subtask_id = start_stock_stage_analysis(
                user_id=task.user_id,
                filter_type='nifty500',
                sector_id=None,
                subsector_id=None,
                app=self.app
            )

            if not subtask_id:
                return False, 'Failed to start stock stage analysis'

            # Link subtask
            task.stock_stage_task_id = subtask_id
            db.session.commit()

            # Wait for completion
            subtask = StockStageAnalysisTask.query.get(subtask_id)
            return self._wait_for_subtask(subtask, 4, task)

        except Exception as e:
            return False, str(e)

    def _step_5_rs_calculation(self, task: MasterSyncTask) -> Tuple[bool, str]:
        """Step 6: Calculate relative strength"""
        try:
            current_app.logger.info(f'Master sync {task.id}: Step 5 - RS calculation')

            # Use default base date (July 1, 2024)
            base_date = date(2024, 7, 1)

            subtask_id = start_rs_calculation(
                user_id=task.user_id,
                base_date=base_date,
                app=self.app
            )

            if not subtask_id:
                return False, 'Failed to start RS calculation'

            # Link subtask
            task.rs_calculation_task_id = subtask_id
            db.session.commit()

            # Wait for completion
            subtask = RSCalculationTask.query.get(subtask_id)
            return self._wait_for_subtask(subtask, 5, task)

        except Exception as e:
            return False, str(e)

    def _step_6_volume_dryup(self, task: MasterSyncTask) -> Tuple[bool, str]:
        """Step 7: Volume dry-up analysis"""
        try:
            current_app.logger.info(f'Master sync {task.id}: Step 6 - Volume dry-up analysis')

            # Use default parameters
            min_volume_pct = 50.0  # Volume < 50% of 20-day average
            max_consolidation_pct = 6.0  # 5-day range < 6%

            subtask_id = start_volume_dryup_analysis(
                user_id=task.user_id,
                min_volume_pct=min_volume_pct,
                max_consolidation_pct=max_consolidation_pct,
                app=self.app
            )

            if not subtask_id:
                return False, 'Failed to start volume dry-up analysis'

            # Link subtask
            task.volume_dryup_task_id = subtask_id
            db.session.commit()

            # Wait for completion
            subtask = VolumeDryUpTask.query.get(subtask_id)
            return self._wait_for_subtask(subtask, 6, task)

        except Exception as e:
            return False, str(e)
