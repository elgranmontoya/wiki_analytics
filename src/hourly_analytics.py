import pandas as pd
import requests
import datetime
import os.path

# Timezone
# Please indicate a valid int
timezone_delta = 2
# Path of the resources folder
resource_folder = "../resources"

# URL of the balcklist file
blacklist_origin = "https://s3.amazonaws.com/dd-interview-data/data_engineer/wikipedia/blacklist_domains_and_pages"

# Path of the blacklist file
blacklist_path = resource_folder + "/" + "blacklist_domains_and_pages"
blacklist = pd.read_table(blacklist_path, sep=' ', names=["domain", "title"])


def get_resource_name(target_datetime):
    """Returns the name of the resource associated with the given datetime"""
    return target_datetime.strftime("pagecounts-%Y%m%d-%H0000.gz")


def get_resource(target_date):
    """Downloads the resource corresponding to the given date from the wikimedia archive"""
    # Get the path of the resource file
    resource_path = resource_folder + "/" + get_resource_name(target_date)

    if not os.path.isfile(resource_path):
        # Download only if necessary
        print("Downloading the resource file for the date : " + str(target_date))

        print(" Getting : http://dumps.wikimedia.org/other/pagecounts-all-sites/" + target_date.strftime("%Y/%Y-%m/pagecounts-%Y%m%d-%H0000.gz"))
        with open(resource_path, "wb") as resource_fd:
            resource_data = requests.get("http://dumps.wikimedia.org/other/pagecounts-all-sites/" + target_date.strftime("%Y/%Y-%m/pagecounts-%Y%m%d-%H0000.gz"), stream=True)
            for chunk in resource_data.iter_content(2048):
                resource_fd.write(chunk)
    else:
        print("Resource file already present")


def get_table_from_resource(file_path):
    """Imports a resource file as an in-memory Dataframe"""
    print("Importing the resource into memory")
    return pd.read_table(file_path, sep=' ', names=["domain", "title", "count", "response_time"], usecols=["domain", "title", "count"])


def split_by_domain(dataframe):
    """Split a dataframe into domains"""
    return dataframe.groupby(["domain"])


def hourly_ranking(dates=None):
    """Computes and saves the pageview rankings"""
    if dates is None:
        # If the date is not given, take the last available data
        dates = [datetime.datetime.now() - datetime.timedelta(hours=2 + timezone_delta)]

    for date in dates:
        # Compute ranking for each given date
        floor_date = datetime.datetime(date.year, date.month, date.day, date.hour, 0)

        # Define path of the output file
        output_path = "../output/ranking" + floor_date.strftime("pagecounts-%Y%m%d-%H0000") + ".csv"

        # Check wether the ranking as already benn computed
        if os.path.isfile(output_path):
            # If already present, do noting
            print("Ranking for this date already present in {}, exiting.".format(floor_date))
        else:
            print("Computing the ranking")

            # Get and save the resource file on disk
            get_resource(floor_date)

            # Get the table as an in-memory object
            table = get_table_from_resource(resource_folder + "/" + get_resource_name(floor_date))

            # Blacklist elements
            blacklist_mask = table[["domain", "title"]].isin(blacklist.to_dict(outtype='list')).all(axis=1)
            table = table[~blacklist_mask]

            # Split elements by domain
            table_groups = split_by_domain(table)

            # Remove unnecessary object
            del(table)

            # Filter and write results
            with open(output_path, 'a') as output_fd:
                for name, group in table_groups:
                    # Sort
                    group.sort(("count"), ascending=False, inplace=True)
                    output_fd.write(name + "\n---\n")
                    # Select first 25
                    group[:25].to_csv(output_fd)
                    output_fd.write("----------\n\n")


if __name__ == "__main__":
    hourly_ranking()
