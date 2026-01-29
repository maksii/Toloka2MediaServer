"""Functions for working with torrents"""

import time

from toloka2MediaServer.clients.bittorrent_client import BittorrentClient

from toloka2MediaServer.config_parser import update_config
from toloka2MediaServer.models.operation_result import OperationResult, ResponseCode
from toloka2MediaServer.models.title import Title, title_to_config
from toloka2MediaServer.utils.general import (
    get_numbers,
    replace_second_part_in_path,
    get_folder_name_from_path,
)


def process_torrent(config, title, torrent, new=False):
    """Common logic to process torrents, either updating or adding new ones"""
    title.publish_date = torrent.date

    tolokaTorrentFile = config.toloka.download_torrent(
        f"{config.toloka.toloka_url}/{torrent.torrent_url}"
    )

    category = config.client.category
    tag = config.client.tags

    add_torrent_response = config.client.add_torrent(
        torrents=tolokaTorrentFile,
        category=category,
        tags=[tag],
        is_paused=True,
        download_dir=title.download_dir,
    )
    
    if add_torrent_response is None:
        message = f"Torrent already exists: {torrent.name}"
        config.operation_result.operation_logs.append(message)
        config.logger.info(message)
        config.operation_result.response_code = ResponseCode.FAILURE
        return config.operation_result

    time.sleep(config.application_config.client_wait_time)
    
    if config.application_config.client == "qbittorrent":
        # Use the hash returned from add_torrent (calculated from torrent file)
        title.hash = add_torrent_response
        
        # Get torrent info using the known hash
        filtered_torrents = config.client.get_torrent_info(
            status_filter="paused",
            category=category,
            tags=tag,
            sort="added_on",
            reverse=True,
            torrent_hash=title.hash,
        )
        if not filtered_torrents:
            message = f"Failed to get torrent info after adding: {torrent.name}"
            config.operation_result.operation_logs.append(message)
            config.logger.error(message)
            config.operation_result.response_code = ResponseCode.FAILURE
            return config.operation_result
            
        added_torrent = filtered_torrents[0]
        get_filelist = config.client.get_files(title.hash)

    else:
        added_torrent = config.client.get_torrent_info(
            status_filter=["paused"],
            category=category,
            tags=[tag],
            sort="added_on",
            reverse=True,
            torrent_hash=add_torrent_response,
        )
        title.hash = added_torrent.hash_string
        get_filelist = added_torrent.get_files()

    config.logger.debug(added_torrent)

    first_fileName = get_filelist[0].name

    if new:
        title.guid = torrent.url
        # Extract numbers from the filename
        numbers = get_numbers(first_fileName)

        if title.episode_index == -1:
            # Display the numbers to the user, starting count from 1
            print(
                f"{first_fileName}\nEnter the order number of the episode index from the list below:"
            )
            for index, number in enumerate(numbers, start=1):
                print(f"{index}: {number}")

            # Get user input and adjust for 0-based index
            episode_order = int(input("Your choice (use order number): "))
            episode_index = episode_order - 1  # Convert to 0-based index
            source_episode_number = numbers[episode_index]
            print(f"You selected episode number: {numbers[episode_index]}")

            adjustment_input = input(
                "Enter the adjustment value (e.g., '+9' or '-3', default is 0): "
            ).strip()
            adjusted_episode_number = int(adjustment_input) if adjustment_input else 0

            if adjusted_episode_number != 0:
                # Calculate new episode number considering adjustment and preserve leading zeros if any
                adjusted_episode = str(
                    int(source_episode_number) + adjusted_episode_number
                ).zfill(len(source_episode_number))
            else:
                adjusted_episode = source_episode_number
            print(f"Adjusted episode number: {adjusted_episode}")

            title.episode_index = episode_index
            title.adjusted_episode_number = adjusted_episode_number

    # Store episode range for partial seasons
    episode_range = []
    
    for file in get_filelist:
        ext_name = file.name.split('.')[-1]

        source_episode = get_numbers(file.name)[title.episode_index]
        calculated_episode = str(
            int(source_episode) + title.adjusted_episode_number
        ).zfill(len(source_episode))
        episode_range.append(int(calculated_episode))

        if config.application_config.enable_dot_spacing_in_file_name:
            # Use dots as separators and no hyphen
            new_name = f"{title.torrent_name}.S{title.season_number}E{calculated_episode}.{title.meta}{title.release_group}.{ext_name}"
            # Just in case replace spaces if any in name, meta or release group
            new_name = new_name.replace("  ", ".").replace(" ", ".")
        else:
            # Use spaces as separators and a hyphen before release_group
            new_name = f"{title.torrent_name} S{title.season_number}E{calculated_episode} {title.meta}-{title.release_group}.{ext_name}"

        if config.application_config.client == "qbittorrent":
            new_path = replace_second_part_in_path(file.name, new_name)
        else:
            new_path = new_name
        
        # In partial season mode, skip files that already have the desired name
        # This allows recheck to work by keeping existing files unchanged
        if title.is_partial_season:
            # Extract just the filename from paths for comparison
            current_filename = file.name.split('/')[-1] if '/' in file.name else file.name
            desired_filename = new_path.split('/')[-1] if '/' in new_path else new_path
            
            if current_filename == desired_filename:
                config.logger.debug(f"Skipping rename for existing file: {current_filename}")
                continue
        
        config.client.rename_file(
            torrent_hash=title.hash, old_path=file.name, new_path=new_path
        )

    # Determine folder name based on whether it's a partial season
    if title.is_partial_season:
        min_ep = min(episode_range)
        max_ep = max(episode_range)
        
        # Handle single episode case - don't use range notation for single episode
        if min_ep == max_ep:
            folderName = f"{title.torrent_name} S{title.season_number}E{str(min_ep).zfill(2)} {title.meta}[{title.release_group}]"
        else:
            # Use range notation with properly determined min/max
            folderName = f"{title.torrent_name} S{title.season_number}E{str(min_ep).zfill(2)}-E{str(max_ep).zfill(2)} {title.meta}[{title.release_group}]"
    else:
        folderName = f"{title.torrent_name} S{title.season_number} {title.meta}[{title.release_group}]"

    if config.application_config.enable_dot_spacing_in_file_name:
        folderName = folderName.replace("  ", ".").replace(" ", ".")

    old_path = get_folder_name_from_path(first_fileName)
    config.client.rename_folder(
        torrent_hash=title.hash, old_path=old_path, new_path=folderName
    )
    config.client.rename_torrent(torrent_hash=title.hash, new_torrent_name=folderName)

    if config.application_config.client == "qbittorrent":
        if new:
            # New torrent - just resume, no recheck needed
            success = config.client.resume_torrent(torrent_hashes=title.hash)
            if not success:
                message = f"Failed to start torrent: {torrent.name}"
                config.operation_result.operation_logs.append(message)
                config.logger.error(message)
                config.operation_result.response_code = ResponseCode.FAILURE
                return config.operation_result
        else:
            # Update scenario - use async recheck (returns quickly, completes in background)
            # This allows web UI to respond without waiting 30+ minutes for recheck
            success, message = config.client.recheck_and_resume_async(
                torrent_hash=title.hash,
                on_complete=lambda ok, msg: config.logger.info(
                    f"Background recheck completed for {torrent.name}: {ok}, {msg}"
                )
            )
            if message:
                config.operation_result.operation_logs.append(message)
                if success:
                    config.logger.info(message)
                else:
                    config.logger.error(message)
            
            if not success:
                message = f"Failed to start recheck for torrent: {torrent.name}"
                config.operation_result.operation_logs.append(message)
                config.logger.error(message)
                config.operation_result.response_code = ResponseCode.FAILURE
                return config.operation_result
    else:
        if new:
            config.client.resume_torrent(torrent_hashes=title.hash)
        else:
            config.client.recheck_torrent(torrent_hashes=title.hash)
            config.client.resume_torrent(torrent_hashes=title.hash)

    titleConfig = title_to_config(title)
    update_config(titleConfig, title.code_name)

    config.operation_result.response_code = ResponseCode.SUCCESS
    return config.operation_result


def update(config, title):
    config.operation_result.titles_references.append(title)
    if title == None:
        config.operation_result.operation_logs.append("Title not found")
        config.operation_result.response_code = ResponseCode.FAILURE
        return config.operation_result
        
    guid = title.guid.strip('"') if title.guid else ""
    torrent = config.toloka.get_torrent(f"{config.toloka.toloka_url}/{guid}")
    config.operation_result.torrent_references.append(torrent)
    
    if title.publish_date not in torrent.date:
        message = f"Date is different! : {torrent.name}"
        config.operation_result.operation_logs.append(message)
        config.logger.info(message)
        
        if not config.args.force:
            # If it's a partial season, rename to base format first
            if title.is_partial_season:
                config.logger.info("Processing partial season update")
                if config.application_config.client == "qbittorrent":
                    base_folder = f"{title.torrent_name} S{title.season_number}"
                    config.client.rename_folder(
                        torrent_hash=title.hash,
                        old_path=get_folder_name_from_path(config.client.get_files(title.hash)[0].name),
                        new_path=base_folder
                    )
            
            # Delete old torrent but keep files
            delete_success = config.client.delete_torrent(delete_files=False, torrent_hashes=title.hash)
            if not delete_success:
                message = f"Failed to delete old torrent: {torrent.name}"
                config.operation_result.operation_logs.append(message)
                config.logger.error(message)
                config.operation_result.response_code = ResponseCode.FAILURE
                return config.operation_result
                
            # Wait a bit before adding new torrent
            time.sleep(config.application_config.client_wait_time)
            
            config.operation_result = process_torrent(config, title, torrent)
    else:
        message = f"Update not required! : {torrent.name}"
        config.operation_result.operation_logs.append(message)
        config.logger.info(message)
        config.operation_result.response_code = ResponseCode.SUCCESS

    return config.operation_result

def add(config, title, torrent):
    config.operation_result.titles_references.append(title)
    config.operation_result.torrent_references.append(torrent)
    config.operation_result = process_torrent(config, title, torrent, new=True)
    config.client.end_session()

    return config.operation_result
