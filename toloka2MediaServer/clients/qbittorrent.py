"""qBittorrent client implementation with clean, maintainable code."""

import hashlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Set

import bencodepy
import qbittorrentapi

from toloka2MediaServer.clients.bittorrent_client import BittorrentClient


class TorrentState(Enum):
    """Known qBittorrent torrent states."""

    # Active/downloading states
    DOWNLOADING = "downloading"
    UPLOADING = "uploading"
    STALLED_DL = "stalledDL"
    STALLED_UP = "stalledUP"
    FORCED_DL = "forcedDL"
    FORCED_UP = "forcedUP"
    META_DL = "metaDL"
    ALLOCATING = "allocating"

    # Queued states
    QUEUED_DL = "queuedDL"
    QUEUED_UP = "queuedUP"

    # Paused/stopped states
    PAUSED_DL = "pausedDL"
    PAUSED_UP = "pausedUP"
    STOPPED_DL = "stoppedDL"
    STOPPED_UP = "stoppedUP"

    # Checking states
    CHECKING_UP = "checkingUP"
    CHECKING_DL = "checkingDL"
    CHECKING_RESUME = "checkingResumeData"

    # Error states
    ERROR = "error"
    MISSING_FILES = "missingFiles"
    UNKNOWN = "unknown"

    @classmethod
    def active_states(cls) -> Set[str]:
        """States indicating torrent is active/running."""
        return {
            cls.DOWNLOADING.value,
            cls.UPLOADING.value,
            cls.STALLED_DL.value,
            cls.STALLED_UP.value,
            cls.FORCED_DL.value,
            cls.FORCED_UP.value,
            cls.META_DL.value,
            cls.ALLOCATING.value,
            cls.QUEUED_DL.value,
            cls.QUEUED_UP.value,
            cls.CHECKING_DL.value,
            cls.CHECKING_UP.value,
        }

    @classmethod
    def checking_states(cls) -> Set[str]:
        """States indicating torrent is being checked."""
        return {
            cls.CHECKING_UP.value,
            cls.CHECKING_DL.value,
            cls.CHECKING_RESUME.value,
        }

    @classmethod
    def error_states(cls) -> Set[str]:
        """States indicating an error."""
        return {
            cls.ERROR.value,
            cls.MISSING_FILES.value,
            cls.UNKNOWN.value,
        }

    @classmethod
    def stopped_states(cls) -> Set[str]:
        """States indicating torrent is stopped."""
        return {
            cls.STOPPED_DL.value,
            cls.STOPPED_UP.value,
            cls.PAUSED_DL.value,
            cls.PAUSED_UP.value,
        }


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 10
    initial_delay: float = 1.0
    max_delay: float = 10.0
    backoff_factor: float = 1.5
    verification_delay: float = 3.0


@dataclass
class TimeoutConfig:
    """Configuration for timeout behavior (synchronous operations)."""

    operation_timeout: float = 360.0  # Overall timeout for complex operations
    recheck_start_timeout: float = 100.0  # Max wait for recheck to start
    recheck_complete_timeout: float = 30.0  # Max wait for recheck to complete (sync)
    poll_interval: float = 2.0  # Default polling interval


@dataclass
class BackgroundTaskConfig:
    """Configuration for background task handling."""

    max_workers: int = 4  # Max concurrent background recheck tasks
    recheck_timeout: float = 1800.0  # 30 minutes for background recheck
    progress_stall_timeout: float = 300.0  # 5 min without progress = warning
    poll_interval: float = 10.0  # Check every 10 seconds in background
    quick_start_timeout: float = 30.0  # Max wait to confirm recheck started


@dataclass
class ClientConfig:
    """Configuration extracted from application config."""

    host: str
    port: int
    username: str
    password: str
    category: str = ""
    tag: str = ""
    retry: RetryConfig = field(default_factory=RetryConfig)
    timeout: TimeoutConfig = field(default_factory=TimeoutConfig)
    background: BackgroundTaskConfig = field(default_factory=BackgroundTaskConfig)


class QbittorrentClient(BittorrentClient):
    """Clean qBittorrent client implementation with async support."""

    def __init__(self, config):
        """Initialize and log in to the qBittorrent client.

        Args:
            config: Application configuration object with client settings and logger.
        """
        super().__init__()
        self.logger = config.logger
        self.retry_config = RetryConfig()
        self.timeout_config = TimeoutConfig()
        self.background_config = BackgroundTaskConfig()

        # Background task management
        self._executor = ThreadPoolExecutor(
            max_workers=self.background_config.max_workers,
            thread_name_prefix="qbit_recheck_",
        )
        self._active_tasks: Dict[str, threading.Event] = {}
        self._tasks_lock = threading.Lock()

        self._connect(config)

    def _connect(self, config):
        """Establish connection to qBittorrent."""
        client_config = config.app_config[config.application_config.client]

        try:
            self.api_client = qbittorrentapi.Client(
                host=client_config["host"],
                port=client_config["port"],
                username=client_config["username"],
                password=client_config["password"],
            )

            self.category = client_config["category"]
            self.tags = client_config["tag"]

            self.api_client.auth_log_in()
            self._log("Connected to qBittorrent client successfully.")

        except qbittorrentapi.LoginFailed:
            self._log(
                "Failed to log in to qBittorrent: Incorrect login details.", "critical"
            )
            raise
        except qbittorrentapi.APIConnectionError:
            self._log(
                "Failed to connect to qBittorrent: Check connection details.",
                "critical",
            )
            raise
        except Exception as e:
            self._log(f"An unexpected error occurred: {str(e)}", "critical")
            raise

    # ==================== LOGGING ====================

    def _log(self, message: str, level: str = "info"):
        """Safe logging helper."""
        if self.logger:
            getattr(self.logger, level)(message)

    # ==================== CORE HELPERS ====================

    def _get_torrent(self, torrent_hash: str):
        """
        Get a single torrent by hash.

        Args:
            torrent_hash: The hash of the torrent to find.

        Returns:
            Torrent object if found, None otherwise.
        """
        torrents = self.api_client.torrents_info(torrent_hashes=torrent_hash)
        for torrent in torrents:
            if torrent.hash == torrent_hash:
                return torrent
        return None

    def _calculate_torrent_hash(self, torrent_file: bytes) -> str:
        """
        Calculate info hash from torrent file bytes.

        Args:
            torrent_file: Raw bytes of the .torrent file.

        Returns:
            SHA1 hash string of the torrent info dict.
        """
        decoded = bencodepy.decode(torrent_file)
        info = decoded[b"info"]
        info_encoded = bencodepy.encode(info)
        return hashlib.sha1(info_encoded).hexdigest()

    def _wait_for_state(
        self,
        torrent_hash: str,
        target_states: Set[str],
        timeout: float = None,
        poll_interval: float = None,
    ) -> Optional[str]:
        """
        Wait for torrent to reach one of the target states.

        Args:
            torrent_hash: Hash of the torrent to monitor.
            target_states: Set of state strings to wait for.
            timeout: Maximum time to wait in seconds.
            poll_interval: Time between state checks.

        Returns:
            The state reached, or None on timeout/not found.
        """
        timeout = timeout or self.timeout_config.operation_timeout
        poll_interval = poll_interval or self.timeout_config.poll_interval
        start = time.time()

        while time.time() - start < timeout:
            torrent = self._get_torrent(torrent_hash)
            if not torrent:
                return None

            if torrent.state in target_states:
                return torrent.state

            time.sleep(poll_interval)

        return None

    def _wait_until_not_state(
        self,
        torrent_hash: str,
        exclude_states: Set[str],
        timeout: float = None,
        poll_interval: float = None,
    ) -> Optional[str]:
        """
        Wait until torrent is NOT in any of the specified states.

        Args:
            torrent_hash: Hash of the torrent to monitor.
            exclude_states: Set of states to wait to exit from.
            timeout: Maximum time to wait in seconds.
            poll_interval: Time between state checks.

        Returns:
            The new state reached, or None on timeout/not found.
        """
        timeout = timeout or self.timeout_config.recheck_complete_timeout
        poll_interval = poll_interval or self.timeout_config.poll_interval
        start = time.time()

        while time.time() - start < timeout:
            torrent = self._get_torrent(torrent_hash)
            if not torrent:
                return None

            if torrent.state not in exclude_states:
                return torrent.state

            time.sleep(poll_interval)

        return None

    def _retry_operation(
        self,
        operation_func,
        verification_func,
        operation_name: str,
    ) -> bool:
        """
        Execute operation with retries and verification.

        Args:
            operation_func: Function that performs the operation.
            verification_func: Function that returns True if operation succeeded.
            operation_name: Name for logging purposes.

        Returns:
            True if operation succeeded and verified, False otherwise.

        Raises:
            Exception: If operation fails after all retries.
        """
        cfg = self.retry_config
        delay = cfg.initial_delay

        for attempt in range(cfg.max_attempts):
            try:
                operation_func()
                time.sleep(cfg.verification_delay)

                if verification_func():
                    return True

                if attempt < cfg.max_attempts - 1:
                    self._log(
                        f"{operation_name}: verification failed, attempt {attempt + 1}/{cfg.max_attempts}",
                        "warning",
                    )
                    time.sleep(delay)
                    delay = min(delay * cfg.backoff_factor, cfg.max_delay)
                    continue

                return False

            except Exception as e:
                if attempt < cfg.max_attempts - 1:
                    self._log(
                        f"{operation_name}: attempt {attempt + 1} failed: {e}",
                        "warning",
                    )
                    time.sleep(delay)
                    delay = min(delay * cfg.backoff_factor, cfg.max_delay)
                    continue
                raise Exception(
                    f"Failed to {operation_name} after {cfg.max_attempts} attempts: {str(e)}"
                )

        return False

    # ==================== PUBLIC API ====================

    def add_torrent(
        self,
        torrents,
        category: str,
        tags: List[str],
        is_paused: bool,
        download_dir: str,
    ) -> Optional[str]:
        """
        Add a torrent with verification.

        Args:
            torrents: Torrent file content (bytes).
            category: Category to assign.
            tags: Tags to assign.
            is_paused: Whether to add in paused state.
            download_dir: Download directory path.

        Returns:
            Torrent hash if successful, None if torrent already exists.
        """
        try:
            # Calculate hash from torrent file before adding
            torrent_hash = self._calculate_torrent_hash(torrents)

            # Check if torrent already exists
            if self._get_torrent(torrent_hash):
                self._log(f"Torrent {torrent_hash[:8]}... already exists")
                return None

            # Add the torrent
            self.api_client.torrents_add(
                torrent_files=torrents,
                category=category,
                tags=tags,
                is_paused=is_paused,
                download_path=download_dir,
            )

            # Wait and verify torrent was added
            time.sleep(1)

            if self._get_torrent(torrent_hash):
                return torrent_hash

            # Fallback: torrent might already exist (race condition)
            return None

        except qbittorrentapi.exceptions.Conflict409Error:
            # Explicit handling of duplicate torrent
            return None
        except Exception as e:
            raise Exception(f"Failed to add torrent: {str(e)}")

    def get_torrent_info(
        self,
        status_filter=None,
        category=None,
        tags=None,
        sort=None,
        reverse=False,
        torrent_hash=None,
    ):
        """
        Retrieve list of torrents with optional filtering.

        Args:
            status_filter: Filter torrents by status.
            category: Filter by category.
            tags: Filter by tags.
            sort: Sort by property.
            reverse: Reverse sort order.
            torrent_hash: Filter by specific torrent hash.

        Returns:
            TorrentInfoList: List of matching torrents.
        """
        return self.api_client.torrents_info(
            status_filter=status_filter,
            category=category,
            tag=tags,
            sort=sort,
            reverse=reverse,
            torrent_hashes=torrent_hash,
        )

    def get_files(self, torrent_hash: str):
        """Get files for a specific torrent."""
        return self.api_client.torrents_files(torrent_hash)

    def rename_file(self, torrent_hash: str, old_path: str, new_path: str) -> bool:
        """
        Rename a file in a torrent with retries and verification.

        Args:
            torrent_hash: Hash of the torrent.
            old_path: Current file path.
            new_path: New file path.

        Returns:
            True if rename was successful.
        """

        def operation():
            self.api_client.torrents_rename_file(
                torrent_hash=torrent_hash,
                old_path=old_path,
                new_path=new_path,
            )

        def verify():
            files = self.get_files(torrent_hash)
            # Verify both: new path exists AND old path is gone
            new_exists = any(f.name == new_path for f in files)
            old_exists = any(f.name == old_path for f in files)
            return new_exists and not old_exists

        return self._retry_operation(operation, verify, f"rename file '{old_path}'")

    def rename_folder(self, torrent_hash: str, old_path: str, new_path: str) -> bool:
        """
        Rename a folder in a torrent with retries and verification.

        Args:
            torrent_hash: Hash of the torrent.
            old_path: Current folder path.
            new_path: New folder path.

        Returns:
            True if rename was successful.
        """

        def operation():
            self.api_client.torrents_rename_folder(
                torrent_hash=torrent_hash,
                old_path=old_path,
                new_path=new_path,
            )

        def verify():
            files = self.get_files(torrent_hash)

            # Verify both: new path exists AND old path is gone
            def top_folder(path: str) -> str:
                sep = "/" if "/" in path else "\\"
                return path.split(sep)[0] if path else ""

            old_exists = any(top_folder(f.name) == old_path for f in files)
            new_exists = any(top_folder(f.name) == new_path for f in files)
            return new_exists and not old_exists

        return self._retry_operation(operation, verify, f"rename folder '{old_path}'")

    def rename_torrent(self, torrent_hash: str, new_torrent_name: str) -> bool:
        """
        Rename a torrent with retries and verification.

        Args:
            torrent_hash: Hash of the torrent.
            new_torrent_name: New name for the torrent.

        Returns:
            True if rename was successful.
        """

        def operation():
            self.api_client.torrents_rename(
                torrent_hash=torrent_hash,
                new_torrent_name=new_torrent_name,
            )

        def verify():
            torrent = self._get_torrent(torrent_hash)
            return torrent is not None and torrent.name == new_torrent_name

        return self._retry_operation(
            operation, verify, f"rename torrent to '{new_torrent_name}'"
        )

    def resume_torrent(self, torrent_hashes: str) -> bool:
        """
        Resume torrent with verification.

        Args:
            torrent_hashes: Hash of the torrent.

        Returns:
            True if resume was successful.
        """

        def operation():
            self.api_client.torrents_resume(torrent_hashes=torrent_hashes)

        def verify():
            torrent = self._get_torrent(torrent_hashes)
            if not torrent:
                return False
            return torrent.state in TorrentState.active_states()

        return self._retry_operation(operation, verify, "resume torrent")

    def delete_torrent(self, delete_files: bool, torrent_hashes: str) -> bool:
        """
        Delete torrent with verification.

        Args:
            delete_files: Whether to delete files along with torrent.
            torrent_hashes: Hash of the torrent to delete.

        Returns:
            True if torrent no longer exists (success).
        """
        try:
            # Check if torrent already doesn't exist
            if not self._get_torrent(torrent_hashes):
                return True

            # Delete the torrent
            self.api_client.torrents_delete(
                delete_files=delete_files,
                torrent_hashes=torrent_hashes,
            )

            # Wait and verify deletion
            time.sleep(1)

            return self._get_torrent(torrent_hashes) is None

        except Exception as e:
            raise Exception(f"Failed to delete torrent: {str(e)}")

    def recheck_torrent(self, torrent_hashes: str):
        """Start recheck on a torrent (no waiting)."""
        return self.api_client.torrents_recheck(torrent_hashes=torrent_hashes)

    # ==================== SYNCHRONOUS RECHECK (Original) ====================

    def recheck_and_resume(self, torrent_hash: str) -> tuple:
        """
        Recheck torrent integrity and resume (synchronous, short timeout).

        For web UI usage, consider using recheck_and_resume_async() instead,
        which returns quickly and handles completion in background.

        Args:
            torrent_hash: Hash of the torrent.

        Returns:
            Tuple of (success: bool, message: str or None).
        """
        overall_start = time.time()
        timeout = self.timeout_config.operation_timeout

        def check_timeout():
            if time.time() - overall_start > timeout:
                raise TimeoutError(f"Operation timed out after {timeout} seconds")

        try:
            # Step 1: Verify torrent exists
            torrent = self._get_torrent(torrent_hash)
            if not torrent:
                return (False, "Torrent not found")

            # Step 2: Start recheck
            try:
                self.api_client.torrents_recheck(torrent_hashes=torrent_hash)
            except Exception as e:
                self._log(f"Recheck command failed: {e}", "warning")

            # Step 3: Wait for recheck to start
            recheck_started = self._wait_for_recheck_start_sync(
                torrent_hash, check_timeout
            )

            # Step 4: Wait for recheck to complete (if it started)
            if recheck_started:
                self._wait_until_not_state(
                    torrent_hash,
                    TorrentState.checking_states(),
                    timeout=self.timeout_config.recheck_complete_timeout,
                )

            check_timeout()

            # Step 5: Resume the torrent
            try:
                self.api_client.torrents_resume(torrent_hashes=torrent_hash)
            except Exception as e:
                self._log(f"Resume command failed: {e}", "warning")

            time.sleep(3)
            check_timeout()

            # Step 6: Verify torrent is active
            return self._verify_torrent_active_sync(torrent_hash, check_timeout)

        except TimeoutError as e:
            raise Exception(f"Operation timed out: {str(e)}")
        except Exception as e:
            return self._fallback_verification(torrent_hash, e)

    def _wait_for_recheck_start_sync(self, torrent_hash: str, check_timeout) -> bool:
        """Wait for recheck to start (synchronous version)."""
        poll_interval = 10
        max_attempts = 10

        for attempt in range(max_attempts):
            check_timeout()

            torrent = self._get_torrent(torrent_hash)
            if not torrent:
                return False

            state = torrent.state

            if state in TorrentState.checking_states():
                return True

            if state in TorrentState.stopped_states():
                try:
                    self.api_client.torrents_recheck(torrent_hashes=torrent_hash)
                except Exception:
                    pass

            time.sleep(poll_interval)

        return False

    def _verify_torrent_active_sync(self, torrent_hash: str, check_timeout) -> tuple:
        """Verify torrent is active (synchronous version)."""
        torrent = self._get_torrent(torrent_hash)
        if not torrent:
            return (False, "Torrent not found after resume")

        state = torrent.state

        if state in TorrentState.active_states():
            return (True, f"Torrent active in state: {state}")

        if state in TorrentState.stopped_states():
            result = self._handle_stopped_state(torrent_hash)
            if result[0]:
                return result

        for attempt in range(3):
            time.sleep(2 * (attempt + 1))

            torrent = self._get_torrent(torrent_hash)
            if not torrent:
                continue

            state = torrent.state
            if state in TorrentState.active_states():
                return (True, f"Torrent active in state: {state}")

            if attempt < 2:
                try:
                    self.api_client.torrents_resume(torrent_hashes=torrent_hash)
                except Exception:
                    pass

        torrent = self._get_torrent(torrent_hash)
        if torrent and torrent.state not in TorrentState.error_states():
            return (True, f"Torrent exists in state: {torrent.state}")

        final_state = torrent.state if torrent else "not found"
        return (False, f"Torrent in invalid state: {final_state}")

    def _handle_stopped_state(self, torrent_hash: str) -> tuple:
        """Handle torrent stuck in stopped state."""
        try:
            self.api_client.torrents_resume(torrent_hashes=torrent_hash)
            time.sleep(2)

            torrent = self._get_torrent(torrent_hash)
            if torrent and torrent.state in TorrentState.active_states():
                return (True, f"Torrent started after stopped state: {torrent.state}")
        except Exception:
            pass

        return (False, None)

    def _fallback_verification(
        self, torrent_hash: str, original_error: Exception
    ) -> tuple:
        """Final fallback verification after an error."""
        try:
            torrent = self._get_torrent(torrent_hash)
            if torrent and torrent.state not in TorrentState.error_states():
                return (True, f"Torrent exists despite error: {torrent.state}")
        except Exception:
            pass

        raise Exception(f"Failed to recheck and resume torrent: {str(original_error)}")

    # ==================== ASYNC RECHECK (Background Worker) ====================

    def recheck_and_resume_async(
        self,
        torrent_hash: str,
        on_complete: Optional[Callable[[bool, str], None]] = None,
    ) -> tuple:
        """
        Start recheck and return immediately once recheck begins.
        Completion is handled in a background thread.

        This is the recommended method for web UI usage where you don't
        want to block the request for potentially 30+ minutes.

        Args:
            torrent_hash: Hash of the torrent.
            on_complete: Optional callback(success, message) when background completes.

        Returns:
            (True, "message") if recheck started successfully and is being monitored.
            (False, "message") if failed to start recheck.
        """
        # Step 1: Verify torrent exists
        torrent = self._get_torrent(torrent_hash)
        if not torrent:
            return (False, "Torrent not found")

        # Step 2: Check if already being processed
        with self._tasks_lock:
            if torrent_hash in self._active_tasks:
                return (True, "Recheck already in progress (monitored)")

        # Step 3: Start recheck
        try:
            self.api_client.torrents_recheck(torrent_hashes=torrent_hash)
        except Exception as e:
            return (False, f"Failed to start recheck: {e}")

        # Step 4: Wait briefly for recheck to actually start
        recheck_started = self._quick_wait_for_recheck_start(torrent_hash)

        if not recheck_started:
            # Check current state - maybe already complete or error
            torrent = self._get_torrent(torrent_hash)
            if torrent and torrent.state in TorrentState.active_states():
                return (True, f"Torrent already active: {torrent.state}")
            elif torrent and torrent.state in TorrentState.error_states():
                return (False, f"Torrent in error state: {torrent.state}")

        # Step 5: Spawn background thread for completion
        cancel_event = threading.Event()
        with self._tasks_lock:
            self._active_tasks[torrent_hash] = cancel_event

        self._executor.submit(
            self._background_recheck_completion,
            torrent_hash,
            cancel_event,
            on_complete,
        )

        state = "checking" if recheck_started else "pending"
        return (True, f"Recheck {state}, monitoring in background")

    def _quick_wait_for_recheck_start(self, torrent_hash: str) -> bool:
        """
        Quick check if recheck started within a short timeout.
        Used by async method to confirm recheck is running before returning.
        """
        timeout = self.background_config.quick_start_timeout
        start = time.time()

        while time.time() - start < timeout:
            torrent = self._get_torrent(torrent_hash)
            if not torrent:
                return False

            if torrent.state in TorrentState.checking_states():
                return True

            # If already past checking (very fast recheck), also OK
            if torrent.state in TorrentState.active_states():
                return True

            time.sleep(2)

        return False

    def _background_recheck_completion(
        self,
        torrent_hash: str,
        cancel_event: threading.Event,
        on_complete: Optional[Callable[[bool, str], None]],
    ):
        """
        Background thread that waits for recheck completion and resumes.
        Runs until recheck is complete (could be 30+ minutes).
        """
        short_hash = torrent_hash[:8]

        try:
            self._log(f"[BG:{short_hash}] Starting recheck monitor...")

            # Wait for recheck to complete with progress monitoring
            completed, final_state = self._wait_for_recheck_complete_with_progress(
                torrent_hash,
                cancel_event,
            )

            if cancel_event.is_set():
                self._log(f"[BG:{short_hash}] Cancelled")
                self._notify_complete(on_complete, False, "Cancelled")
                return

            if not completed:
                self._log(f"[BG:{short_hash}] Recheck failed: {final_state}", "error")
                self._notify_complete(
                    on_complete, False, f"Recheck failed: {final_state}"
                )
                return

            self._log(f"[BG:{short_hash}] Recheck complete, resuming...")

            # Resume the torrent
            success, message = self._background_resume_and_verify(torrent_hash)

            if success:
                self._log(f"[BG:{short_hash}] Success: {message}")
            else:
                self._log(f"[BG:{short_hash}] Failed: {message}", "error")

            self._notify_complete(on_complete, success, message)

        except Exception as e:
            self._log(f"[BG:{short_hash}] Error: {e}", "error")
            self._notify_complete(on_complete, False, f"Background error: {e}")
        finally:
            # Cleanup
            with self._tasks_lock:
                self._active_tasks.pop(torrent_hash, None)

    def _wait_for_recheck_complete_with_progress(
        self,
        torrent_hash: str,
        cancel_event: threading.Event,
    ) -> tuple:
        """
        Wait for recheck to complete, monitoring progress for stalls.

        Returns:
            (completed: bool, state_or_reason: str)
        """
        cfg = self.background_config
        short_hash = torrent_hash[:8]
        start = time.time()
        last_progress = 0.0
        last_progress_time = start
        last_logged_progress = -1  # Track last logged percentage

        while time.time() - start < cfg.recheck_timeout:
            if cancel_event.is_set():
                return (False, "cancelled")

            torrent = self._get_torrent(torrent_hash)
            if not torrent:
                return (False, "torrent_not_found")

            state = torrent.state
            progress = getattr(torrent, "progress", 0.0)
            progress_pct = int(progress * 100)

            # Recheck complete - not in checking state anymore
            if state not in TorrentState.checking_states():
                if state in TorrentState.error_states():
                    return (False, f"error_state:{state}")
                self._log(f"[BG:{short_hash}] Recheck finished at 100%")
                return (True, state)

            # Log progress every 10%
            if progress_pct >= last_logged_progress + 10:
                self._log(f"[BG:{short_hash}] Recheck progress: {progress_pct}%")
                last_logged_progress = progress_pct

            # Monitor progress for stalls
            if progress > last_progress + 0.001:  # More than 0.1% progress
                last_progress = progress
                last_progress_time = time.time()
            elif time.time() - last_progress_time > cfg.progress_stall_timeout:
                # No progress for too long - log warning but continue
                # qBit might be busy with other rechecks
                self._log(
                    f"[BG:{short_hash}] Recheck stalled at {progress_pct}% for {cfg.progress_stall_timeout}s",
                    "warning",
                )
                # Reset stall timer to avoid spam
                last_progress_time = time.time()

            time.sleep(cfg.poll_interval)

        # Timeout
        torrent = self._get_torrent(torrent_hash)
        if torrent and torrent.state in TorrentState.checking_states():
            progress_pct = int(getattr(torrent, "progress", 0.0) * 100)
            return (False, f"timeout_at_{progress_pct}%")

        # Finished during final check
        return (True, torrent.state if torrent else "completed")

    def _background_resume_and_verify(self, torrent_hash: str) -> tuple:
        """Resume torrent and verify it's active (background version)."""
        max_attempts = 5
        short_hash = torrent_hash[:8]

        for attempt in range(max_attempts):
            try:
                self.api_client.torrents_resume(torrent_hashes=torrent_hash)
            except Exception as e:
                self._log(
                    f"[BG:{short_hash}] Resume attempt {attempt + 1} failed: {e}",
                    "warning",
                )

            time.sleep(3)

            torrent = self._get_torrent(torrent_hash)
            if not torrent:
                return (False, "Torrent not found after resume")

            if torrent.state in TorrentState.active_states():
                return (True, f"Active in state: {torrent.state}")

            if torrent.state in TorrentState.error_states():
                return (False, f"Error state: {torrent.state}")

            time.sleep(2 * (attempt + 1))  # Backoff

        # Final check - accept non-error states
        torrent = self._get_torrent(torrent_hash)
        if torrent and torrent.state not in TorrentState.error_states():
            return (True, f"Exists in state: {torrent.state}")

        return (False, f"Failed to resume after {max_attempts} attempts")

    def _notify_complete(
        self,
        callback: Optional[Callable[[bool, str], None]],
        success: bool,
        message: str,
    ):
        """Safely invoke completion callback."""
        if callback:
            try:
                callback(success, message)
            except Exception as e:
                self._log(f"[BG] Callback error: {e}", "error")

    # ==================== BACKGROUND TASK MANAGEMENT ====================

    def cancel_background_recheck(self, torrent_hash: str) -> bool:
        """
        Cancel a running background recheck task.

        Args:
            torrent_hash: Hash of the torrent to cancel.

        Returns:
            True if task was found and cancelled, False if not found.
        """
        with self._tasks_lock:
            if torrent_hash in self._active_tasks:
                self._active_tasks[torrent_hash].set()
                return True
        return False

    def get_active_background_rechecks(self) -> List[str]:
        """
        Get list of torrent hashes with active background rechecks.

        Returns:
            List of torrent hashes being monitored.
        """
        with self._tasks_lock:
            return list(self._active_tasks.keys())

    def is_background_recheck_active(self, torrent_hash: str) -> bool:
        """
        Check if a background recheck is active for a torrent.

        Args:
            torrent_hash: Hash of the torrent to check.

        Returns:
            True if background recheck is active.
        """
        with self._tasks_lock:
            return torrent_hash in self._active_tasks

    def get_recheck_status(self, torrent_hash: str) -> tuple:
        """
        Get current recheck status for a torrent.

        Args:
            torrent_hash: Hash of the torrent.

        Returns:
            Tuple of (status: str, progress: float).
            Status is one of: 'not_found', 'checking', 'active', 'error', 'stopped', or state name.
        """
        torrent = self._get_torrent(torrent_hash)
        if not torrent:
            return ("not_found", 0.0)

        state = torrent.state
        progress = getattr(torrent, "progress", 0.0)

        if state in TorrentState.checking_states():
            return ("checking", progress)
        elif state in TorrentState.active_states():
            return ("active", progress)
        elif state in TorrentState.error_states():
            return ("error", progress)
        elif state in TorrentState.stopped_states():
            return ("stopped", progress)
        else:
            return (state, progress)

    # ==================== CLEANUP ====================

    def end_session(self):
        """Logout from the qBittorrent client."""
        return self.api_client.auth_log_out()

    def shutdown(self, wait: bool = True):
        """
        Shutdown the client and background executor.

        Args:
            wait: If True, wait for background tasks to complete.
        """
        # Cancel all active tasks
        with self._tasks_lock:
            for event in self._active_tasks.values():
                event.set()

        # Shutdown executor
        self._executor.shutdown(wait=wait)

        # Logout
        try:
            self.api_client.auth_log_out()
        except Exception:
            pass
