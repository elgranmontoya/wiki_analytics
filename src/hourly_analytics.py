import pandas as pd
import requests
import datetime
import os
import os.path
import logging
from config import *

# Configure logging
logger = logging.getLogger()
logger.setLevel(log_level)
formatter = logging.Formatter('%(asctime)s :: %(levelname)s :: %(message)s')
# Add logging to standard stream
stream_handler = logging.StreamHandler()
logger.addHandler(stream_handler)
# Add logging to file
file_handler = logging.FileHandler("hourly_analytics.log")
logger.addHandler(file_handler)

# Configure the logging for requests
logging.getLogger("requests").setLevel(logging.CRITICAL)


def create_dir(dir_path):
    if not (os.path.exists(dir_path)):
        # Only create
        os.makedirs(dir_path)
    elif not(os.path.isdir(dir_path)):
        raise Exception("{} already exists, but is not as directory, aborting...".format(dir_path))


def get_resource_name(target_datetime):
    """Returns the name of the resource associated with the given datetime"""
    return target_datetime.strftime("pagecounts-%Y%m%d-%H0000.gz")


def download_file(url, file_path):
    """Downloads the file present at the given url and saves it in file_path"""
    if not os.path.isfile(file_path):
        # Download only if necessary
        logger.info("Downloading the file for the url {}".format(url))
        with open(file_path, "wb") as fd:
            resource_data = requests.get(url, stream=True)
            for chunk in resource_data.iter_content(2048):
                fd.write(chunk)
    else:
        logger.info("File {} already present, no need to redownload".format(file_path))


def get_resource(target_date):
    """Downloads the resource corresponding to the given date from the wikimedia archive"""
    # Get the path of the resource file
    resource_path = resource_dir + "/" + get_resource_name(target_date)
    resource_url = "http://dumps.wikimedia.org/other/pagecounts-all-sites/" + target_date.strftime("%Y/%Y-%m/pagecounts-%Y%m%d-%H0000.gz")
    download_file(resource_url, resource_path)


def get_table_from_resource(file_path):
    """Imports a resource file as an in-memory Dataframe"""
    logger.info("Importing the resource into memory")
    try:
        return pd.read_table(file_path, sep=' ', names=["domain", "title", "count", "response_time"], usecols=["domain", "title", "count"])
    except:
        logger.error("Error during the importation of the resource file {}. Try to remove it and redownload it.".format(file_path))


def blacklist(table):
    """Returns the table filtered with the blacklist"""
    # First, download the blacklist file
    download_file(blacklist_origin, blacklist_path)

    # Import the blacklist as a dataframe
    blacklist = pd.read_table(blacklist_path, sep=' ', names=["domain", "title"])

    # Create and apply the mask
    blacklist_mask = table[["domain", "title"]].isin(blacklist.to_dict(outtype='list')).all(axis=1)
    # Remove the blacklist table
    del(blacklist)

    return table[~blacklist_mask]


def split_by_domain(dataframe):
    """Split a dataframe into domains"""
    return dataframe.groupby(["domain"])


def hourly_ranking(dates=None):
    """Computes and saves the pageview rankings"""
    if dates is None:
        # If the date is not given, take the last available data
        dates = [datetime.datetime.now() - datetime.timedelta(hours=2)]

    for date in dates:
        # Compute ranking for each given date
        # Substract local timezone
        floor_date = datetime.datetime(date.year, date.month, date.day, date.hour, 0) - datetime.timedelta(hours=local_timezone)

        # Define path of the output files
        output_path = output_dir + "/ranking-" + floor_date.strftime("%Y%m%d-%H0000") + ".csv"

        # Check wether the ranking as already benn computed
        if os.path.isfile(output_path):
            # If already present, do noting
            logger.error("Ranking for this date already present in {}, exiting.".format(output_path))
        else:
            logger.info("Computing the ranking")

            # Get and save the resource file on disk
            get_resource(floor_date)

            # Get the table as an in-memory object
            table = get_table_from_resource(resource_dir + "/" + get_resource_name(floor_date))

            # Blacklist elements
            table = blacklist(table)

            # Split elements by domain
            table_groups = split_by_domain(table)

            # Remove unnecessary object
            del(table)

            # Filter and write results
            with open(output_path, 'a') as output_fd:
                # Whether to add the header before each group
                header = False
                if not fancy_formatting:
                    output_fd.write("Original_index Domain Title Count\n")
                for name, group in table_groups:
                    # Sort
                    group.sort(("count"), ascending=False, inplace=True)
                    if fancy_formatting:
                        output_fd.write("Domain : " + name + "\n---\n")
                        header = True
                    # Select first 25
                    group[:25].to_csv(output_fd, sep=" ", header=header)
                    if fancy_formatting:
                        output_fd.write("----------\n\n")


def hourly_analytics(dates=None):
    """The main function"""
    # Create the directories if necessary
    create_dir(resource_dir)
    create_dir(output_dir)
    hourly_ranking(dates)


if __name__ == "__main__":
    hourly_analytics()
