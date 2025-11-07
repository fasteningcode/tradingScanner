"""
Storage and File Management Service

Handles project organization, file cleanup, and storage analysis operations.
All operations are designed to be safe and idempotent.
"""

import os
import shutil
import glob
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class StorageService:
    """Service for managing project files and storage"""

    def __init__(self, project_root: str = None):
        """Initialize storage service

        Args:
            project_root: Path to project root directory (defaults to app parent dir)
        """
        if project_root is None:
            # Get project root (parent of app directory)
            app_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(app_dir)

        self.project_root = project_root
        self.tests_dir = os.path.join(project_root, 'tests')
        self.scripts_dir = os.path.join(project_root, 'scripts')
        self.docs_dir = os.path.join(project_root, 'docs')
        self.archive_dir = os.path.join(self.docs_dir, 'archive')
        self.instance_dir = os.path.join(project_root, 'instance')
        self.logs_dir = os.path.join(project_root, 'logs')

    def analyze_storage(self) -> Dict:
        """Analyze storage usage across the project

        Returns:
            Dictionary with storage statistics
        """
        try:
            stats = {
                'database': self._get_directory_size(self.instance_dir),
                'logs': self._get_directory_size(self.logs_dir),
                'backups': self._count_backup_files(),
                'temp_files': self._count_temp_files(),
                'total_size': 0,
                'organized': self._check_if_organized(),
                'last_organized': self._get_last_organized_timestamp()
            }

            stats['total_size'] = (
                stats['database']['size'] +
                stats['logs']['size'] +
                stats['backups']['size']
            )

            return stats
        except Exception as e:
            logger.error(f"Error analyzing storage: {e}")
            return {}

    def check_organization_status(self) -> Dict:
        """Check if project is already organized

        Returns:
            Dictionary with organization status and file counts
        """
        status = {
            'is_organized': True,
            'tests_in_root': [],
            'scripts_in_root': [],
            'docs_in_root': [],
            'needs_organization': False
        }

        # Check for test files in root
        test_patterns = ['test_*.py']
        for pattern in test_patterns:
            files = glob.glob(os.path.join(self.project_root, pattern))
            status['tests_in_root'].extend([os.path.basename(f) for f in files])

        # Check for script files in root
        script_files = [
            'clear_all_stocks.py', 'fix_nifty500_classification.py',
            'import_nifty500_stocks.py', 'manage_nifty500.py',
            'migrate_add_nifty500.py', 'migrate_institutional_sectors.py',
            'migrate_sectors.py', 'sync_instruments_cli.py',
            'update_instrument_tokens.py', 'view_logs.sh'
        ]
        for script in script_files:
            path = os.path.join(self.project_root, script)
            if os.path.exists(path):
                status['scripts_in_root'].append(script)

        # Check for debug/status docs in root
        doc_patterns = [
            'DEBUG_*.md', 'DETAILED_*.md', 'FINAL_*.md', 'FORCE_*.md',
            'HISTORICAL_*.md', 'INSTRUMENT_*.md', 'JAVASCRIPT_*.md',
            'MONITORING_*.md', 'PROJECT_STATUS.md', 'RESOLUTION_*.md',
            'SECTOR_MANAGEMENT_*.md', 'QUICK_TEST_GUIDE.md', 'QUICK_START.md'
        ]
        for pattern in doc_patterns:
            files = glob.glob(os.path.join(self.project_root, pattern))
            status['docs_in_root'].extend([os.path.basename(f) for f in files])

        # Determine if organization is needed
        status['needs_organization'] = (
            len(status['tests_in_root']) > 0 or
            len(status['scripts_in_root']) > 0 or
            len(status['docs_in_root']) > 0
        )

        status['is_organized'] = not status['needs_organization']

        return status

    def organize_project(self, dry_run: bool = False) -> Dict:
        """Organize project files into proper directories

        Args:
            dry_run: If True, return what would be done without making changes

        Returns:
            Dictionary with operation results
        """
        results = {
            'success': False,
            'dry_run': dry_run,
            'moved_files': [],
            'created_dirs': [],
            'errors': [],
            'message': ''
        }

        try:
            # Check if already organized
            status = self.check_organization_status()
            if status['is_organized']:
                results['message'] = 'Project is already organized'
                results['success'] = True
                return results

            # Create directories if they don't exist
            dirs_to_create = [
                self.tests_dir,
                self.scripts_dir,
                self.archive_dir
            ]

            for directory in dirs_to_create:
                if not os.path.exists(directory):
                    if not dry_run:
                        os.makedirs(directory, exist_ok=True)
                        logger.info(f"Created directory: {directory}")
                    results['created_dirs'].append(directory)

            # Move test files
            for test_file in status['tests_in_root']:
                src = os.path.join(self.project_root, test_file)
                dst = os.path.join(self.tests_dir, test_file)
                if not dry_run:
                    shutil.move(src, dst)
                    self._update_python_imports(dst)
                    logger.info(f"Moved test file: {test_file}")
                results['moved_files'].append({
                    'file': test_file,
                    'from': 'root',
                    'to': 'tests/'
                })

            # Move script files
            for script_file in status['scripts_in_root']:
                src = os.path.join(self.project_root, script_file)
                dst = os.path.join(self.scripts_dir, script_file)
                if not dry_run:
                    shutil.move(src, dst)
                    self._update_python_imports(dst)
                    logger.info(f"Moved script file: {script_file}")
                results['moved_files'].append({
                    'file': script_file,
                    'from': 'root',
                    'to': 'scripts/'
                })

            # Move documentation files
            for doc_file in status['docs_in_root']:
                # Determine destination
                if doc_file in ['QUICK_START.md', 'QUICK_TEST_GUIDE.md']:
                    dst = os.path.join(self.docs_dir, doc_file)
                    dest_folder = 'docs/'
                else:
                    dst = os.path.join(self.archive_dir, doc_file)
                    dest_folder = 'docs/archive/'

                src = os.path.join(self.project_root, doc_file)
                if not dry_run:
                    shutil.move(src, dst)
                    logger.info(f"Moved doc file: {doc_file}")
                results['moved_files'].append({
                    'file': doc_file,
                    'from': 'root',
                    'to': dest_folder
                })

            # Save organization timestamp
            if not dry_run:
                self._save_organization_timestamp()

            results['success'] = True
            results['message'] = f"Successfully {'would move' if dry_run else 'moved'} {len(results['moved_files'])} files"

        except Exception as e:
            logger.error(f"Error organizing project: {e}")
            results['errors'].append(str(e))
            results['message'] = f"Error: {str(e)}"

        return results

    def clean_temp_files(self, dry_run: bool = False) -> Dict:
        """Clean temporary files

        Args:
            dry_run: If True, return what would be deleted without deleting

        Returns:
            Dictionary with cleanup results
        """
        results = {
            'success': False,
            'dry_run': dry_run,
            'deleted_files': [],
            'space_freed': 0,
            'errors': []
        }

        try:
            # Patterns for temporary files
            temp_patterns = [
                os.path.join(self.instance_dir, 'temp_*.db'),
                os.path.join(self.instance_dir, '*.tmp'),
                os.path.join(self.project_root, '*.pyc'),
                os.path.join(self.project_root, '.DS_Store'),
            ]

            for pattern in temp_patterns:
                for file_path in glob.glob(pattern):
                    try:
                        file_size = os.path.getsize(file_path)
                        if not dry_run:
                            os.remove(file_path)
                            logger.info(f"Deleted temp file: {file_path}")
                        results['deleted_files'].append(os.path.basename(file_path))
                        results['space_freed'] += file_size
                    except Exception as e:
                        results['errors'].append(f"{file_path}: {str(e)}")

            results['success'] = True

        except Exception as e:
            logger.error(f"Error cleaning temp files: {e}")
            results['errors'].append(str(e))

        return results

    def clean_old_logs(self, days_to_keep: int = 7, dry_run: bool = False) -> Dict:
        """Clean or archive old log files

        Args:
            days_to_keep: Number of days of logs to keep
            dry_run: If True, return what would be done without making changes

        Returns:
            Dictionary with cleanup results
        """
        results = {
            'success': False,
            'dry_run': dry_run,
            'archived_files': [],
            'deleted_lines': 0,
            'space_freed': 0,
            'errors': []
        }

        try:
            if not os.path.exists(self.logs_dir):
                results['success'] = True
                return results

            cutoff_date = datetime.now() - timedelta(days=days_to_keep)

            for log_file in os.listdir(self.logs_dir):
                if not log_file.endswith('.log'):
                    continue

                file_path = os.path.join(self.logs_dir, log_file)

                # For log files, we'll truncate old entries rather than delete
                if not dry_run:
                    original_size = os.path.getsize(file_path)
                    lines_removed = self._truncate_old_log_entries(file_path, cutoff_date)
                    new_size = os.path.getsize(file_path)

                    if lines_removed > 0:
                        results['archived_files'].append(log_file)
                        results['deleted_lines'] += lines_removed
                        results['space_freed'] += (original_size - new_size)
                        logger.info(f"Truncated {lines_removed} old entries from {log_file}")

            results['success'] = True

        except Exception as e:
            logger.error(f"Error cleaning logs: {e}")
            results['errors'].append(str(e))

        return results

    def clean_old_backups(self, keep_count: int = 5, dry_run: bool = False) -> Dict:
        """Clean old backup files, keeping only the most recent ones

        Args:
            keep_count: Number of most recent backups to keep
            dry_run: If True, return what would be deleted without deleting

        Returns:
            Dictionary with cleanup results
        """
        results = {
            'success': False,
            'dry_run': dry_run,
            'deleted_files': [],
            'space_freed': 0,
            'kept_files': [],
            'errors': []
        }

        try:
            backup_pattern = os.path.join(self.instance_dir, 'app.db.backup_*')
            backup_files = glob.glob(backup_pattern)

            # Sort by modification time (newest first)
            backup_files.sort(key=os.path.getmtime, reverse=True)

            # Keep the most recent backups
            files_to_keep = backup_files[:keep_count]
            files_to_delete = backup_files[keep_count:]

            results['kept_files'] = [os.path.basename(f) for f in files_to_keep]

            for file_path in files_to_delete:
                try:
                    file_size = os.path.getsize(file_path)
                    if not dry_run:
                        os.remove(file_path)
                        logger.info(f"Deleted old backup: {file_path}")
                    results['deleted_files'].append(os.path.basename(file_path))
                    results['space_freed'] += file_size
                except Exception as e:
                    results['errors'].append(f"{file_path}: {str(e)}")

            results['success'] = True

        except Exception as e:
            logger.error(f"Error cleaning backups: {e}")
            results['errors'].append(str(e))

        return results

    def vacuum_database(self) -> Dict:
        """Vacuum the SQLite database to reclaim space

        Returns:
            Dictionary with vacuum results
        """
        results = {
            'success': False,
            'size_before': 0,
            'size_after': 0,
            'space_freed': 0,
            'errors': []
        }

        try:
            db_path = os.path.join(self.instance_dir, 'app.db')

            if not os.path.exists(db_path):
                results['errors'].append('Database file not found')
                return results

            results['size_before'] = os.path.getsize(db_path)

            # Import here to avoid circular imports
            import sqlite3

            conn = sqlite3.connect(db_path)
            conn.execute('VACUUM')
            conn.close()

            results['size_after'] = os.path.getsize(db_path)
            results['space_freed'] = results['size_before'] - results['size_after']
            results['success'] = True

            logger.info(f"Database vacuumed. Space freed: {results['space_freed']} bytes")

        except Exception as e:
            logger.error(f"Error vacuuming database: {e}")
            results['errors'].append(str(e))

        return results

    # Helper methods

    def _get_directory_size(self, directory: str) -> Dict:
        """Get total size of a directory

        Args:
            directory: Path to directory

        Returns:
            Dictionary with size info
        """
        total_size = 0
        file_count = 0

        if not os.path.exists(directory):
            return {'size': 0, 'files': 0, 'readable': '0 B'}

        for dirpath, dirnames, filenames in os.walk(directory):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                    file_count += 1
                except (OSError, FileNotFoundError):
                    pass

        return {
            'size': total_size,
            'files': file_count,
            'readable': self._format_bytes(total_size)
        }

    def _count_backup_files(self) -> Dict:
        """Count and size backup files

        Returns:
            Dictionary with backup file info
        """
        backup_pattern = os.path.join(self.instance_dir, 'app.db.backup_*')
        backup_files = glob.glob(backup_pattern)

        total_size = sum(os.path.getsize(f) for f in backup_files)

        return {
            'count': len(backup_files),
            'size': total_size,
            'readable': self._format_bytes(total_size)
        }

    def _count_temp_files(self) -> Dict:
        """Count temporary files

        Returns:
            Dictionary with temp file info
        """
        temp_patterns = [
            os.path.join(self.instance_dir, 'temp_*.db'),
            os.path.join(self.instance_dir, '*.tmp'),
        ]

        temp_files = []
        for pattern in temp_patterns:
            temp_files.extend(glob.glob(pattern))

        total_size = sum(os.path.getsize(f) for f in temp_files if os.path.exists(f))

        return {
            'count': len(temp_files),
            'size': total_size,
            'readable': self._format_bytes(total_size)
        }

    def _check_if_organized(self) -> bool:
        """Check if project is organized

        Returns:
            True if organized, False otherwise
        """
        status = self.check_organization_status()
        return status['is_organized']

    def _get_last_organized_timestamp(self) -> Optional[str]:
        """Get timestamp of last organization

        Returns:
            ISO format timestamp or None
        """
        timestamp_file = os.path.join(self.project_root, '.organized_timestamp')

        if os.path.exists(timestamp_file):
            try:
                with open(timestamp_file, 'r') as f:
                    return f.read().strip()
            except Exception:
                return None

        return None

    def _save_organization_timestamp(self):
        """Save organization timestamp"""
        timestamp_file = os.path.join(self.project_root, '.organized_timestamp')

        try:
            with open(timestamp_file, 'w') as f:
                f.write(datetime.now().isoformat())
        except Exception as e:
            logger.error(f"Error saving organization timestamp: {e}")

    def _update_python_imports(self, file_path: str):
        """Update Python file imports to work from new location

        Args:
            file_path: Path to Python file to update
        """
        if not file_path.endswith('.py'):
            return

        try:
            with open(file_path, 'r') as f:
                content = f.read()

            # Check if it already has the path fix
            if 'project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))' in content:
                return

            # Add path fix after imports
            lines = content.split('\n')
            import_end_idx = 0

            for i, line in enumerate(lines):
                if line.startswith('import ') or line.startswith('from '):
                    import_end_idx = i + 1
                elif line.strip() and not line.startswith('#') and not line.startswith('"""') and not line.startswith("'''"):
                    if 'import' not in line and 'from' not in line:
                        break

            # Insert path fix code
            path_fix = [
                '',
                '# Add the project root directory to the path',
                'project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))',
                'sys.path.insert(0, project_root)',
                ''
            ]

            # Ensure sys and os are imported
            has_sys = any('import sys' in line for line in lines[:import_end_idx])
            has_os = any('import os' in line for line in lines[:import_end_idx])

            if not has_sys:
                lines.insert(0, 'import sys')
                import_end_idx += 1
            if not has_os:
                lines.insert(0, 'import os')
                import_end_idx += 1

            # Insert path fix
            for i, fix_line in enumerate(path_fix):
                lines.insert(import_end_idx + i, fix_line)

            # Write back
            with open(file_path, 'w') as f:
                f.write('\n'.join(lines))

            logger.info(f"Updated imports in {file_path}")

        except Exception as e:
            logger.error(f"Error updating imports in {file_path}: {e}")

    def _truncate_old_log_entries(self, log_file: str, cutoff_date: datetime) -> int:
        """Remove old entries from log file

        Args:
            log_file: Path to log file
            cutoff_date: Date before which to remove entries

        Returns:
            Number of lines removed
        """
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()

            kept_lines = []
            removed_count = 0

            for line in lines:
                # Try to parse timestamp from log line
                # Assuming format: [YYYY-MM-DD HH:MM:SS,mmm] ...
                try:
                    if line.startswith('['):
                        timestamp_str = line[1:24]  # Extract timestamp
                        log_date = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')

                        if log_date >= cutoff_date:
                            kept_lines.append(line)
                        else:
                            removed_count += 1
                    else:
                        # Keep lines without timestamps (continuations, etc.)
                        kept_lines.append(line)
                except (ValueError, IndexError):
                    # If we can't parse the date, keep the line
                    kept_lines.append(line)

            if removed_count > 0:
                with open(log_file, 'w') as f:
                    f.writelines(kept_lines)

            return removed_count

        except Exception as e:
            logger.error(f"Error truncating log file {log_file}: {e}")
            return 0

    @staticmethod
    def _format_bytes(bytes_value: int) -> str:
        """Format bytes into human-readable string

        Args:
            bytes_value: Number of bytes

        Returns:
            Formatted string (e.g., "1.5 MB")
        """
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f} TB"
