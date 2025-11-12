"""
API routes for external integrations (cron jobs, webhooks, etc.)
These routes do not require authentication but have IP restrictions
"""

from flask import Blueprint, jsonify, request
from app.models import User
from flask import current_app as app

# Create blueprint without URL prefix for root-level API routes
api_bp = Blueprint('api', __name__)


@api_bp.route('/api/master-sync/cron', methods=['GET'])
def master_sync_cron():
    """
    Cron endpoint for scheduled master synchronization execution

    Security:
    - No authentication required
    - IP restricted to localhost only (127.0.0.1, localhost, ::1)

    Usage:
    - Add to crontab for daily 4 PM IST execution:
      30 10 * * * curl -s http://localhost:5002/api/master-sync/cron

    Returns:
    - 200: {"success": true, "message": "...", "task_id": N}
    - 400: {"success": false, "error": "..."}
    - 403: {"success": false, "error": "Unauthorized IP address"}
    """
    from app.master_sync_service import start_master_sync as start_sync_service
    from app.models import MasterSyncTask

    # Security check: Only allow from localhost
    allowed_ips = ['127.0.0.1', 'localhost', '::1']
    if request.remote_addr not in allowed_ips:
        return jsonify({
            'success': False,
            'error': 'Unauthorized IP address'
        }), 403

    # Check if there's already a running task
    active_task = MasterSyncTask.query.filter_by(status='running').first()
    if active_task:
        return jsonify({
            'success': False,
            'message': 'A master sync task is already running',
            'task_id': active_task.id
        })

    # Get system user (first user in database)
    system_user = User.query.first()
    if not system_user:
        return jsonify({
            'success': False,
            'error': 'No users found in database'
        }), 400

    # Start master sync
    success, message, task_id = start_sync_service(system_user.id, app._get_current_object())

    if success:
        return jsonify({
            'success': True,
            'message': message,
            'task_id': task_id
        })
    else:
        return jsonify({
            'success': False,
            'error': message
        }), 400
