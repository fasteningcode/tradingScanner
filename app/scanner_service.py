"""
Scanner Service

This service handles stock scanner execution and profile management.
Scanning logic will be implemented later based on user requirements.
"""

import threading
from typing import Optional, Dict, List
from datetime import datetime
from flask import current_app
from app import db
from app.models import ScannerProfile, ScannerTask, Instrument

# Dictionary to track running scanner tasks
_running_tasks = {}


def start_scan(user_id: int, profile_id: int, app=None) -> Optional[int]:
    """
    Start scanner task in background

    Args:
        user_id: User ID
        profile_id: Scanner profile ID
        app: Flask app instance

    Returns:
        Task ID if started successfully, None otherwise
    """
    try:
        current_app.logger.info(f'Starting scanner for user {user_id}, profile {profile_id}')

        # Verify profile exists and belongs to user
        profile = ScannerProfile.query.filter_by(
            id=profile_id,
            user_id=user_id
        ).first()

        if not profile:
            current_app.logger.error(f'Profile {profile_id} not found for user {user_id}')
            return None

        # Create task record
        task = ScannerTask(
            user_id=user_id,
            profile_id=profile_id,
            status='pending'
        )
        db.session.add(task)
        db.session.commit()

        task_id = task.id
        current_app.logger.info(f'Created scanner task {task_id}')

        # Get app context if not provided
        if app is None:
            app = current_app._get_current_object()

        # Start scanner in background thread
        thread = threading.Thread(
            target=_run_scanner,
            args=(task_id, app),
            daemon=True
        )
        thread.start()
        _running_tasks[task_id] = thread

        current_app.logger.info(f'Scanner task {task_id} thread started')
        return task_id

    except Exception as e:
        current_app.logger.error(f'Error starting scanner: {str(e)}', exc_info=True)
        return None


def get_scan_status(user_id: int) -> Optional[Dict]:
    """
    Get status of the most recent scanner task for a user

    Args:
        user_id: User ID

    Returns:
        Task status dictionary or None if no task found
    """
    try:
        task = ScannerTask.query.filter_by(user_id=user_id).order_by(
            ScannerTask.created_at.desc()
        ).first()

        if task:
            return task.to_dict()
        return None

    except Exception as e:
        current_app.logger.error(f'Error getting scan status: {str(e)}', exc_info=True)
        return None


def cancel_scan(task_id: int) -> bool:
    """
    Cancel a running scanner task

    Args:
        task_id: Task ID

    Returns:
        True if cancelled successfully, False otherwise
    """
    try:
        task = ScannerTask.query.get(task_id)
        if task and task.status == 'running':
            task.status = 'cancelled'
            task.completed_at = datetime.utcnow()
            db.session.commit()
            current_app.logger.info(f'Scanner task {task_id} cancelled')
            return True
        return False

    except Exception as e:
        current_app.logger.error(f'Error cancelling scanner: {str(e)}', exc_info=True)
        return False


def _run_scanner(task_id: int, app):
    """
    Run scanner in background thread

    Args:
        task_id: Task ID
        app: Flask app instance
    """
    with app.app_context():
        try:
            current_app.logger.info(f'Scanner task {task_id}: Starting background execution')
            scanner = Scanner(task_id)
            scanner.run()
            current_app.logger.info(f'Scanner task {task_id}: Completed successfully')
        except Exception as e:
            current_app.logger.error(
                f'Scanner task {task_id} failed: {str(e)}',
                exc_info=True
            )
            try:
                task = ScannerTask.query.get(task_id)
                if task:
                    task.status = 'failed'
                    task.error_message = str(e)
                    task.completed_at = datetime.utcnow()
                    db.session.commit()
                    current_app.logger.info(f'Scanner task {task_id}: Marked as failed in database')
            except Exception as db_error:
                current_app.logger.error(
                    f'Scanner task {task_id}: Failed to update task status: {str(db_error)}',
                    exc_info=True
                )
        finally:
            # Remove from running tasks
            if task_id in _running_tasks:
                del _running_tasks[task_id]
                current_app.logger.info(f'Scanner task {task_id}: Removed from running tasks')


class Scanner:
    """Handles scanner execution"""

    def __init__(self, task_id: int):
        self.task_id = task_id
        self.task = ScannerTask.query.get(task_id)
        if not self.task:
            raise ValueError(f'Scanner task {task_id} not found')

    def run(self):
        """
        Execute the scanner

        NOTE: This is a placeholder implementation.
        Actual scanning logic will be implemented later based on user requirements.
        """
        current_app.logger.info(f'Scanner task {self.task_id}: Starting run()')

        # Update task status to running
        self.task.status = 'running'
        self.task.started_at = datetime.utcnow()
        db.session.commit()
        current_app.logger.info(f'Scanner task {self.task_id}: Status set to running')

        # Get stocks to scan
        # For now, just scan all NIFTY 500 stocks as a placeholder
        stocks = Instrument.query.filter_by(
            exchange='NSE',
            instrument_type='EQ',
            is_nifty500=True
        ).all()

        self.task.total_stocks = len(stocks)
        db.session.commit()

        current_app.logger.info(
            f'Scanner task {self.task_id}: Found {len(stocks)} stocks to scan'
        )

        if len(stocks) == 0:
            current_app.logger.warning(f'Scanner task {self.task_id}: No stocks found to scan')
            self.task.status = 'completed'
            self.task.completed_at = datetime.utcnow()
            db.session.commit()
            return

        # Placeholder: Just loop through stocks without actual filtering
        # Actual scanning logic will be added later
        for idx, stock in enumerate(stocks):
            # Check if task was cancelled
            db.session.refresh(self.task)
            if self.task.status == 'cancelled':
                current_app.logger.info(f'Scanner task {self.task_id} was cancelled')
                return

            try:
                self.task.current_stock_symbol = stock.tradingsymbol
                db.session.commit()

                # TODO: Add actual scanning/filtering logic here
                # For now, just simulate scanning by counting all stocks as scanned
                self.task.scanned_stocks += 1

                # Update progress
                self.task.progress_percentage = ((idx + 1) / len(stocks)) * 100
                db.session.commit()

            except Exception as e:
                self.task.failed_stocks += 1
                error_msg = f'Error scanning {stock.tradingsymbol}: {str(e)}'
                current_app.logger.error(
                    f'Scanner task {self.task_id}: {error_msg}',
                    exc_info=True
                )
                db.session.commit()

        # Mark task as completed
        self.task.status = 'completed'
        self.task.completed_at = datetime.utcnow()
        self.task.current_stock_symbol = None
        db.session.commit()

        current_app.logger.info(
            f'Scanner task {self.task_id}: Completed - '
            f'Scanned: {self.task.scanned_stocks}, '
            f'Matched: {self.task.matched_stocks}, '
            f'Failed: {self.task.failed_stocks}'
        )


# Profile Management Functions

def get_user_profiles(user_id: int) -> List[ScannerProfile]:
    """Get all scanner profiles for a user"""
    try:
        return ScannerProfile.query.filter_by(user_id=user_id).order_by(
            ScannerProfile.is_default.desc(),
            ScannerProfile.created_at.desc()
        ).all()
    except Exception as e:
        current_app.logger.error(f'Error getting user profiles: {str(e)}', exc_info=True)
        return []


def get_default_profile(user_id: int) -> Optional[ScannerProfile]:
    """Get user's default scanner profile"""
    try:
        return ScannerProfile.query.filter_by(
            user_id=user_id,
            is_default=True
        ).first()
    except Exception as e:
        current_app.logger.error(f'Error getting default profile: {str(e)}', exc_info=True)
        return None


def set_default_profile(user_id: int, profile_id: int) -> bool:
    """Set a profile as the default for a user"""
    try:
        # Unset all defaults for this user
        ScannerProfile.query.filter_by(
            user_id=user_id,
            is_default=True
        ).update({'is_default': False})

        # Set new default
        profile = ScannerProfile.query.filter_by(
            id=profile_id,
            user_id=user_id
        ).first()

        if profile:
            profile.is_default = True
            db.session.commit()
            return True

        return False

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error setting default profile: {str(e)}', exc_info=True)
        return False


def delete_profile(user_id: int, profile_id: int) -> bool:
    """Delete a scanner profile"""
    try:
        profile = ScannerProfile.query.filter_by(
            id=profile_id,
            user_id=user_id
        ).first()

        if profile:
            db.session.delete(profile)
            db.session.commit()
            return True

        return False

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error deleting profile: {str(e)}', exc_info=True)
        return False
