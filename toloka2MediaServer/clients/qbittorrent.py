import qbittorrentapi
import time

from toloka2MediaServer.clients.bittorrent_client import BittorrentClient


class QbittorrentClient(BittorrentClient):
    def __init__(self, config):
        """Initialize and log in to the qBittorrent client."""
        try:
            super().__init__()
            self.api_client = qbittorrentapi.Client(
                host=config.app_config[config.application_config.client]["host"],
                port=config.app_config[config.application_config.client]["port"],
                username=config.app_config[config.application_config.client][
                    "username"
                ],
                password=config.app_config[config.application_config.client][
                    "password"
                ],
            )

            self.category = config.app_config[config.application_config.client][
                "category"
            ]
            self.tags = config.app_config[config.application_config.client]["tag"]

            self.api_client.auth_log_in()
            config.logger.info("Connected to qBittorrent client successfully.")
        except qbittorrentapi.LoginFailed as e:
            config.logger.critical(
                "Failed to log in to qBittorrent: Incorrect login details."
            )
            raise
        except qbittorrentapi.APIConnectionError as e:
            config.logger.critical(
                "Failed to connect to qBittorrent: Check connection details."
            )
            raise
        except Exception as e:
            config.logger.critical(f"An unexpected error occurred: {str(e)}")
            raise

    def add_torrent(self, torrents, category, tags, is_paused, download_dir):
        """Add a torrent with verification.
        
        Args:
            torrents: Torrent file content
            category (str): Category to assign
            tags (list): Tags to assign
            is_paused (bool): Whether to add in paused state
            download_dir (str): Download directory path
            
        Returns:
            str: Torrent hash if successful, None if torrent already exists
        """
        try:
            # Try to add the torrent
            self.api_client.torrents.add(
                torrent_files=torrents, 
                category=category, 
                tags=tags, 
                is_paused=is_paused, 
                download_path=download_dir
            )
            
            # Wait a bit before checking
            time.sleep(1)
            
            # Get the most recently added torrent
            torrents = self.get_torrent_info(
                status_filter=None,  # Changed from "paused" to None to catch all states
                category=category,
                tags=tags,
                sort='added_on',
                reverse=True
            )
            
            if torrents:
                return torrents[0].hash
                
            # If we get here, likely the torrent already exists
            return None
                
        except qbittorrentapi.exceptions.Conflict409Error:
            # Explicit handling of duplicate torrent
            return None
        except Exception as e:
            raise Exception(f"Failed to add torrent: {str(e)}")

    def get_torrent_info(
        self, status_filter, category, tags, sort, reverse, torrent_hash=None
    ):
        return self.api_client.torrents_info(
            status_filter=status_filter,
            category=category,
            tag=tags,
            sort=sort,
            reverse=reverse,
        )

    def get_files(self, torrent_hash):
        return self.api_client.torrents_files(torrent_hash)

    def _retry_operation(self, operation_func, verification_func, operation_name, max_retries=3, retry_delay=2, initial_wait=1):
        """Helper method to handle retry logic for torrent operations.
        
        Args:
            operation_func: Function that performs the operation
            verification_func: Function that verifies if operation was successful
            operation_name (str): Name of operation for error messages
            max_retries (int): Maximum number of retry attempts
            retry_delay (int): Delay between retries in seconds
            initial_wait (int): Initial wait time after operation before first verification
            
        Returns:
            bool: True if operation was successful, False otherwise
            
        Raises:
            Exception: If operation fails after all retries
        """
        for attempt in range(max_retries):
            try:
                operation_func()
                # Always wait a bit after the operation before checking
                time.sleep(initial_wait)
                
                if verification_func():
                    return True
                    
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                    
                return False
                
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                raise Exception(f"Failed to {operation_name} after {max_retries} attempts: {str(e)}")
                
        return False

    def rename_file(self, torrent_hash, old_path, new_path):
        """Rename a file in a torrent with retries and verification.
        
        Args:
            torrent_hash (str): Hash of the torrent
            old_path (str): Current file path
            new_path (str): New file path
            
        Returns:
            bool: True if rename was successful
        """
        def operation():
            self.api_client.torrents_rename_file(
                torrent_hash=torrent_hash,
                old_path=old_path,
                new_path=new_path
            )
            
        def verify():
            files = self.get_files(torrent_hash)
            # Check both that new path exists and old path doesn't
            new_path_exists = any(file.name == new_path for file in files)
            old_path_exists = any(file.name == old_path for file in files)
            return new_path_exists and not old_path_exists
            
        return self._retry_operation(
            operation,
            verify,
            "rename file",
            max_retries=3,
            retry_delay=2,
            initial_wait=1
        )

    def rename_folder(self, torrent_hash, old_path, new_path):
        """Rename a folder in a torrent with retries and verification.
        
        Args:
            torrent_hash (str): Hash of the torrent
            old_path (str): Current folder path
            new_path (str): New folder path
            
        Returns:
            bool: True if rename was successful
        """
        def operation():
            self.api_client.torrents_rename_folder(
                torrent_hash=torrent_hash,
                old_path=old_path,
                new_path=new_path
            )
            
        def verify():
            files = self.get_files(torrent_hash)
            # Check that no files contain the old path and at least one contains the new path
            old_path_exists = any(old_path in file.name for file in files)
            new_path_exists = any(new_path in file.name for file in files)
            return new_path_exists and not old_path_exists
            
        return self._retry_operation(
            operation,
            verify,
            "rename folder",
            max_retries=3,
            retry_delay=2,
            initial_wait=1
        )

    def rename_torrent(self, torrent_hash, new_torrent_name):
        """Rename a torrent with retries and verification.
        
        Args:
            torrent_hash (str): Hash of the torrent
            new_torrent_name (str): New name for the torrent
            
        Returns:
            bool: True if rename was successful
        """
        def operation():
            self.api_client.torrents_rename(
                torrent_hash=torrent_hash,
                new_torrent_name=new_torrent_name
            )
            
        def verify():
            torrent_info = self.get_torrent_info(
                status_filter=None,
                category=None,
                tags=None,
                sort=None,
                reverse=False,
                torrent_hash=torrent_hash
            )
            # Verify both that torrent exists and has the new name
            return torrent_info and len(torrent_info) > 0 and torrent_info[0].name == new_torrent_name
            
        return self._retry_operation(
            operation,
            verify,
            "rename torrent",
            max_retries=3,
            retry_delay=2,
            initial_wait=1
        )

    def resume_torrent(self, torrent_hashes):
        """Resume torrent with verification.
        
        Args:
            torrent_hashes (str): Hash of the torrent
            
        Returns:
            bool: True if resume was successful
        """
        def operation():
            self.api_client.torrents_resume(torrent_hashes=torrent_hashes)
            
        def verify():
            torrent_info = self.get_torrent_info(
                status_filter=None,
                category=None,
                tags=None,
                sort=None,
                reverse=False,
                torrent_hash=torrent_hashes
            )
            if not torrent_info:
                return False
                
            state = torrent_info[0].state
            # States indicating torrent is active or queued
            valid_states = [
                'downloading', 'uploading',
                'stalledDL', 'stalledUP',
                'forcedDL', 'forcedUP',
                'metaDL', 'allocating',
                'checkingDL', 'checkingUP',
                'queuedDL', 'queuedUP'  # Include queued states as valid
            ]
            return state in valid_states
            
        return self._retry_operation(
            operation,
            verify,
            "resume torrent",
            max_retries=3,
            retry_delay=5,
            initial_wait=1
        )

    def delete_torrent(self, delete_files, torrent_hashes):
        """Delete torrent with verification.
        
        Args:
            delete_files (bool): Whether to delete files along with torrent
            torrent_hashes (str): Hash of the torrent to delete
            
        Returns:
            bool: True if torrent no longer exists (success), False otherwise
        """
        try:
            # First check if torrent exists before trying to delete
            initial_check = self.get_torrent_info(
                status_filter=None,
                category=None,
                tags=None,
                sort=None,
                reverse=False,
                torrent_hash=torrent_hashes
            )
            
            # Check if the specific torrent hash exists in the results
            target_exists = any(t.hash == torrent_hashes for t in initial_check)
            
            # If torrent doesn't exist, consider it already deleted - return success
            if not target_exists:
                return True
                
            # Torrent exists, try to delete it
            self.api_client.torrents_delete(
                delete_files=delete_files,
                torrent_hashes=torrent_hashes
            )
            
            # Wait a bit before checking
            time.sleep(1)
            
            # Verify torrent no longer exists
            torrent_info = self.get_torrent_info(
                status_filter=None,
                category=None,
                tags=None,
                sort=None,
                reverse=False,
                torrent_hash=torrent_hashes
            )
            
            # Check if the specific torrent hash still exists
            return not any(t.hash == torrent_hashes for t in torrent_info)
                
        except Exception as e:
            raise Exception(f"Failed to delete torrent: {str(e)}")

    def recheck_torrent(self, torrent_hashes):
        return self.api_client.torrents_recheck(torrent_hashes=torrent_hashes)

    def end_session(self):
        return self.api_client.auth_log_out()

    def recheck_and_resume(self, torrent_hash):
        """Recheck and resume torrent with verification.
        
        Args:
            torrent_hash (str): Hash of the torrent
            
        Returns:
            bool: True if operation was successful
        """
        try:
            # First verify torrent exists
            initial_check = self.get_torrent_info(
                status_filter=None,
                category=None,
                tags=None,
                sort=None,
                reverse=False,
                torrent_hash=torrent_hash
            )
            
            if not any(t.hash == torrent_hash for t in initial_check):
                return False
                
            # Start recheck
            self.api_client.torrents_recheck(torrent_hashes=torrent_hash)
            
            # Wait for recheck to start (with retry)
            check_interval = 1
            max_retries = 10
            for _ in range(max_retries):
                torrent_info = self.get_torrent_info(
                    status_filter=None,
                    category=None,
                    tags=None,
                    sort=None,
                    reverse=False,
                    torrent_hash=torrent_hash
                )
                
                matching_torrents = [t for t in torrent_info if t.hash == torrent_hash]
                if not matching_torrents:
                    return False
                    
                state = matching_torrents[0].state
                if state in ['checkingResumeData', 'checking', 'checkingDL', 'checkingUP']:
                    break
                    
                time.sleep(check_interval)
            else:
                return False  # Recheck didn't start
                
            # Now wait indefinitely for check to complete
            while True:
                torrent_info = self.get_torrent_info(
                    status_filter=None,
                    category=None,
                    tags=None,
                    sort=None,
                    reverse=False,
                    torrent_hash=torrent_hash
                )
                
                matching_torrents = [t for t in torrent_info if t.hash == torrent_hash]
                if not matching_torrents:
                    return False
                    
                state = matching_torrents[0].state
                # If no longer checking, break
                if state not in ['checkingResumeData', 'checking', 'checkingDL', 'checkingUP']:
                    break
                    
                time.sleep(2)
            
            # Resume the torrent
            self.api_client.torrents_resume(torrent_hashes=torrent_hash)
            
            # Wait a bit before final check
            time.sleep(1)
            
            # Verify torrent is active
            torrent_info = self.get_torrent_info(
                status_filter=None,
                category=None,
                tags=None,
                sort=None,
                reverse=False,
                torrent_hash=torrent_hash
            )
            
            matching_torrents = [t for t in torrent_info if t.hash == torrent_hash]
            if not matching_torrents:
                return False
                
            state = matching_torrents[0].state
            # States indicating torrent is active or queued
            valid_states = [
                'downloading', 'uploading',
                'stalledDL', 'stalledUP',
                'forcedDL', 'forcedUP',
                'metaDL', 'allocating',
                'queuedDL', 'queuedUP'
            ]
            return state in valid_states
                
        except Exception as e:
            raise Exception(f"Failed to recheck and resume torrent: {str(e)}")
