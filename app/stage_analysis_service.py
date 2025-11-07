"""
Stage Analysis Service

This module implements Weinstein's 4-Stage Market Methodology for sectors and subsectors.
Calculates current stage based on historical index data and moving averages.
"""

import threading
from datetime import datetime, timedelta, date
from typing import Optional, Tuple, Dict
from flask import current_app
from app import db
from app.models import (
    Sector, SubSector, IndexHistory, StageAnalysisTask,
    StageAnalysisHistory
)


# Global dictionary to store active analysis threads
active_analyses = {}


def start_stage_analysis(user_id: int, app) -> Tuple[bool, str, Optional[int]]:
    """
    Start a new stage analysis task for all sectors and subsectors

    Args:
        user_id: ID of the user requesting analysis
        app: Flask app instance

    Returns:
        Tuple of (success, message, task_id)
    """
    try:
        # Check if there's already an active analysis task
        existing_task = StageAnalysisTask.query.filter_by(
            user_id=user_id,
            status='running'
        ).first()

        if existing_task:
            return False, 'A stage analysis task is already running', None

        # Count total symbols to analyze
        sectors = Sector.query.filter_by(is_active=True).filter(
            Sector.index_symbol.isnot(None)
        ).all()
        subsectors = SubSector.query.filter_by(is_active=True).filter(
            SubSector.index_symbol.isnot(None)
        ).all()

        total_symbols = len(sectors) + len(subsectors)

        if total_symbols == 0:
            return False, 'No sectors or subsectors with index symbols found', None

        # Create new analysis task
        task = StageAnalysisTask(
            user_id=user_id,
            total_symbols=total_symbols,
            status='pending'
        )
        db.session.add(task)
        db.session.commit()

        # Start analysis in background thread
        analyzer = StageAnalyzer(task.id, app)
        analyzer.start_analysis()

        current_app.logger.info(f'Started stage analysis task {task.id} for user {user_id}')

        return True, 'Stage analysis started successfully', task.id

    except Exception as e:
        current_app.logger.error(f'Error starting stage analysis: {str(e)}')
        return False, str(e), None


def get_stage_analysis_status(user_id: int) -> Optional[dict]:
    """
    Get the status of the current stage analysis task for a user

    Args:
        user_id: ID of the user

    Returns:
        Dictionary with analysis status or None
    """
    try:
        task = StageAnalysisTask.query.filter_by(user_id=user_id).order_by(
            StageAnalysisTask.created_at.desc()
        ).first()

        if not task:
            return None

        return task.to_dict()

    except Exception as e:
        current_app.logger.error(f'Error getting stage analysis status: {str(e)}')
        return None


def cancel_stage_analysis(task_id: int) -> Tuple[bool, str]:
    """
    Cancel a running stage analysis task

    Args:
        task_id: ID of the analysis task

    Returns:
        Tuple of (success, message)
    """
    try:
        task = StageAnalysisTask.query.get(task_id)
        if not task:
            return False, 'Task not found'

        if task.status != 'running':
            return False, f'Task is not running (status: {task.status})'

        # Stop the analysis
        if task_id in active_analyses:
            analyzer = active_analyses[task_id]
            analyzer.cancel_analysis()

        task.status = 'cancelled'
        task.completed_at = datetime.utcnow()
        db.session.commit()

        return True, 'Stage analysis cancelled successfully'

    except Exception as e:
        current_app.logger.error(f'Error cancelling stage analysis: {str(e)}')
        return False, str(e)


def get_stage_description(stage: int) -> Dict[str, str]:
    """
    Get human-readable description of a stage

    Args:
        stage: Stage number (1-4)

    Returns:
        Dictionary with stage name, description, and color
    """
    stages = {
        1: {
            'name': 'Accumulation',
            'description': 'Basing pattern, preparing for uptrend',
            'color': 'primary',
            'badge_class': 'bg-primary'
        },
        2: {
            'name': 'Markup',
            'description': 'Strong uptrend, advancing',
            'color': 'success',
            'badge_class': 'bg-success'
        },
        3: {
            'name': 'Distribution',
            'description': 'Topping pattern, preparing for downtrend',
            'color': 'warning',
            'badge_class': 'bg-warning text-dark'
        },
        4: {
            'name': 'Decline',
            'description': 'Downtrend, declining',
            'color': 'danger',
            'badge_class': 'bg-danger'
        }
    }
    return stages.get(stage, {
        'name': 'Unknown',
        'description': 'Stage not determined',
        'color': 'secondary',
        'badge_class': 'bg-secondary'
    })


class StageAnalyzer:
    """Service class to handle stage analysis calculations"""

    def __init__(self, task_id: int, app):
        """
        Initialize analyzer with a task ID

        Args:
            task_id: ID of the StageAnalysisTask to process
            app: Flask app instance
        """
        self.task_id = task_id
        self.task = None
        self.should_stop = False
        self.app = app

    def start_analysis(self):
        """Start the analysis process in a background thread"""
        thread = threading.Thread(
            target=self._analysis_worker,
            daemon=True,
            name=f"StageAnalyzer-{self.task_id}"
        )
        active_analyses[self.task_id] = self
        thread.start()

        self.app.logger.info(f"Started stage analysis task {self.task_id} in background thread")

    def cancel_analysis(self):
        """Cancel the running analysis"""
        self.should_stop = True
        self.app.logger.info(f"Cancelled stage analysis task {self.task_id}")

    def _analysis_worker(self):
        """Main worker function that runs in background thread"""
        with self.app.app_context():
            try:
                current_app.logger.info(f"Stage analysis task {self.task_id}: Worker thread started")

                # Load task
                self.task = StageAnalysisTask.query.get(self.task_id)
                if not self.task:
                    current_app.logger.error(f"Stage analysis task {self.task_id} not found")
                    return

                # Update task status to running
                self.task.status = 'running'
                self.task.started_at = datetime.utcnow()
                db.session.commit()

                # Get all sectors and subsectors with index symbols
                sectors = Sector.query.filter_by(is_active=True).filter(
                    Sector.index_symbol.isnot(None)
                ).all()

                subsectors = SubSector.query.filter_by(is_active=True).filter(
                    SubSector.index_symbol.isnot(None)
                ).all()

                current_app.logger.info(
                    f"Stage analysis task {self.task_id}: Analyzing {len(sectors)} sectors "
                    f"and {len(subsectors)} subsectors"
                )

                # Analyze each sector
                for sector in sectors:
                    if self.should_stop:
                        current_app.logger.info(f"Stage analysis task {self.task_id}: Stopped by user")
                        break

                    try:
                        self.task.current_symbol = sector.index_symbol
                        db.session.commit()

                        stage_result = self._calculate_stage(sector.index_symbol)

                        if stage_result:
                            sector.current_stage = stage_result['stage']
                            sector.stage_confidence = stage_result['confidence']
                            sector.stage_updated_at = datetime.utcnow()
                            db.session.add(sector)  # Explicitly add to session to track changes

                            # Save to history
                            self._save_stage_history(sector.index_symbol, stage_result)

                            current_app.logger.info(
                                f"Stage analysis task {self.task_id}: {sector.index_symbol} = Stage {stage_result['stage']}"
                            )

                        self.task.analyzed_symbols += 1
                        self.task.progress_percentage = (self.task.analyzed_symbols / self.task.total_symbols) * 100
                        db.session.commit()

                    except Exception as e:
                        self.task.failed_symbols += 1
                        error_msg = f"Error analyzing sector {sector.index_symbol}: {str(e)}"
                        current_app.logger.error(f"Stage analysis task {self.task_id}: {error_msg}")
                        db.session.commit()

                # Analyze each subsector
                for subsector in subsectors:
                    if self.should_stop:
                        current_app.logger.info(f"Stage analysis task {self.task_id}: Stopped by user")
                        break

                    try:
                        self.task.current_symbol = subsector.index_symbol
                        db.session.commit()

                        stage_result = self._calculate_stage(subsector.index_symbol)

                        if stage_result:
                            subsector.current_stage = stage_result['stage']
                            subsector.stage_confidence = stage_result['confidence']
                            subsector.stage_updated_at = datetime.utcnow()
                            db.session.add(subsector)  # Explicitly add to session to track changes

                            # Save to history
                            self._save_stage_history(subsector.index_symbol, stage_result)

                            current_app.logger.info(
                                f"Stage analysis task {self.task_id}: {subsector.index_symbol} = Stage {stage_result['stage']}"
                            )

                        self.task.analyzed_symbols += 1
                        self.task.progress_percentage = (self.task.analyzed_symbols / self.task.total_symbols) * 100
                        db.session.commit()

                    except Exception as e:
                        self.task.failed_symbols += 1
                        error_msg = f"Error analyzing subsector {subsector.index_symbol}: {str(e)}"
                        current_app.logger.error(f"Stage analysis task {self.task_id}: {error_msg}")
                        db.session.commit()

                # Mark task as completed
                self.task.status = 'completed'
                self.task.completed_at = datetime.utcnow()
                self.task.progress_percentage = 100.0
                db.session.commit()

                current_app.logger.info(
                    f"Stage analysis task {self.task_id}: Completed - "
                    f"{self.task.analyzed_symbols} analyzed, {self.task.failed_symbols} failed"
                )

            except Exception as e:
                current_app.logger.error(f"Stage analysis task {self.task_id}: Unexpected error: {str(e)}")
                self.task.status = 'failed'
                self.task.error_message = str(e)
                self.task.completed_at = datetime.utcnow()
                db.session.commit()

            finally:
                # Remove from active analyses
                if self.task_id in active_analyses:
                    del active_analyses[self.task_id]

    def _calculate_stage(self, index_symbol: str, analysis_date: Optional[date] = None) -> Optional[Dict]:
        """
        Calculate Weinstein stage for an index symbol using 30-day and 150-day moving averages

        Args:
            index_symbol: The index symbol to analyze
            analysis_date: Date to analyze (defaults to latest available)

        Returns:
            Dictionary with stage, confidence, moving averages, etc., or None if insufficient data
        """
        try:
            # Get historical data (need at least 150 days for 150-day MA)
            end_date = analysis_date or date.today()
            start_date = end_date - timedelta(days=200)  # Get extra days to ensure 150 data points

            history = IndexHistory.query.filter_by(index_symbol=index_symbol).filter(
                IndexHistory.date >= start_date,
                IndexHistory.date <= end_date
            ).order_by(IndexHistory.date).all()

            if len(history) < 150:
                current_app.logger.warning(
                    f"Insufficient data for {index_symbol}: {len(history)} days (need 150)"
                )
                return None

            # Extract index values
            prices = [h.index_value for h in history]
            dates = [h.date for h in history]

            # Calculate moving averages
            ma_30 = sum(prices[-30:]) / 30
            ma_150 = sum(prices[-150:]) / 150
            current_price = prices[-1]

            # Calculate slope of moving averages (trend direction)
            # Positive slope = rising, negative = falling
            ma_30_prev = sum(prices[-35:-5]) / 30  # MA 30 from 5 days ago
            ma_150_prev = sum(prices[-155:-5]) / 150  # MA 150 from 5 days ago

            ma_30_slope = (ma_30 - ma_30_prev) / ma_30_prev * 100
            ma_150_slope = (ma_150 - ma_150_prev) / ma_150_prev * 100

            # Determine stage based on Weinstein methodology
            stage, confidence = self._determine_weinstein_stage(
                current_price, ma_30, ma_150, ma_30_slope, ma_150_slope
            )

            return {
                'stage': stage,
                'confidence': confidence,
                'current_price': current_price,
                'ma_30': ma_30,
                'ma_150': ma_150,
                'ma_30_slope': ma_30_slope,
                'ma_150_slope': ma_150_slope,
                'date': dates[-1]
            }

        except Exception as e:
            current_app.logger.error(f"Error calculating stage for {index_symbol}: {str(e)}")
            return None

    def _determine_weinstein_stage(
        self,
        price: float,
        ma_30: float,
        ma_150: float,
        ma_30_slope: float,
        ma_150_slope: float
    ) -> Tuple[int, float]:
        """
        Determine Weinstein stage based on price, moving averages, and slopes

        Stage 1 (Accumulation): Price below both MAs, 30 MA flattening/turning up
        Stage 2 (Markup): Price above both MAs, 30 MA above 150 MA, both rising
        Stage 3 (Distribution): Price above both MAs, 30 MA flattening/turning down
        Stage 4 (Decline): Price below both MAs, 30 MA below 150 MA, both declining

        Args:
            price: Current price
            ma_30: 30-day moving average
            ma_150: 150-day moving average
            ma_30_slope: Slope of 30-day MA (% change)
            ma_150_slope: Slope of 150-day MA (% change)

        Returns:
            Tuple of (stage, confidence_score)
        """
        confidence = 0.0

        # Calculate relative position
        price_vs_ma30 = ((price - ma_30) / ma_30) * 100
        price_vs_ma150 = ((price - ma_150) / ma_150) * 100
        ma_30_vs_ma_150 = ((ma_30 - ma_150) / ma_150) * 100

        # Stage 2: Markup (Strong Uptrend)
        if (price > ma_30 and price > ma_150 and
            ma_30 > ma_150 and
            ma_30_slope > 0 and ma_150_slope > 0):
            stage = 2
            # Confidence based on strength of signals
            if ma_30_slope > 1 and ma_150_slope > 0.5:
                confidence = 90.0
            elif ma_30_slope > 0.5 and ma_150_slope > 0.2:
                confidence = 75.0
            else:
                confidence = 60.0

        # Stage 4: Decline (Strong Downtrend)
        elif (price < ma_30 and price < ma_150 and
              ma_30 < ma_150 and
              ma_30_slope < 0 and ma_150_slope < 0):
            stage = 4
            # Confidence based on strength of signals
            if ma_30_slope < -1 and ma_150_slope < -0.5:
                confidence = 90.0
            elif ma_30_slope < -0.5 and ma_150_slope < -0.2:
                confidence = 75.0
            else:
                confidence = 60.0

        # Stage 1: Accumulation (Basing)
        elif (price < ma_30 and price < ma_150):
            stage = 1
            # Look for signs of bottoming
            if ma_30_slope > -0.5 and ma_30_slope <= 0.5:  # Flattening
                confidence = 70.0
            elif ma_30_slope > 0:  # Starting to turn up
                confidence = 80.0
            else:
                confidence = 60.0

        # Stage 3: Distribution (Topping)
        elif (price > ma_30 and price > ma_150):
            stage = 3
            # Look for signs of topping
            if ma_30_slope < 0.5 and ma_30_slope >= -0.5:  # Flattening
                confidence = 70.0
            elif ma_30_slope < 0:  # Starting to turn down
                confidence = 80.0
            else:
                confidence = 60.0

        # Edge case: Mixed signals
        else:
            # Default to stage based on MA relationship
            if ma_30 > ma_150:
                stage = 2 if ma_30_slope > 0 else 3
            else:
                stage = 4 if ma_30_slope < 0 else 1
            confidence = 50.0  # Low confidence for mixed signals

        return stage, round(confidence, 2)

    def _save_stage_history(self, index_symbol: str, stage_result: Dict):
        """
        Save stage analysis result to history

        Args:
            index_symbol: The index symbol
            stage_result: Dictionary with stage analysis results
        """
        try:
            # Check if record already exists for this date
            existing = StageAnalysisHistory.query.filter_by(
                index_symbol=index_symbol,
                date=stage_result['date']
            ).first()

            if existing:
                # Update existing record
                existing.stage = stage_result['stage']
                existing.stage_confidence = stage_result['confidence']
                existing.moving_avg_30 = stage_result['ma_30']
                existing.moving_avg_150 = stage_result['ma_150']
                existing.current_price = stage_result['current_price']
            else:
                # Create new record
                history_record = StageAnalysisHistory(
                    index_symbol=index_symbol,
                    date=stage_result['date'],
                    stage=stage_result['stage'],
                    stage_confidence=stage_result['confidence'],
                    moving_avg_30=stage_result['ma_30'],
                    moving_avg_150=stage_result['ma_150'],
                    current_price=stage_result['current_price']
                )
                db.session.add(history_record)

            db.session.commit()

        except Exception as e:
            current_app.logger.error(
                f"Error saving stage history for {index_symbol}: {str(e)}"
            )
            db.session.rollback()
