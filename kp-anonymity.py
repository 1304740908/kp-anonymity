import os
import numpy as np
import pandas as pd
import sys
from loguru import logger
import random
from node import Node
from dataset_anonymized import DatasetAnonymized

max_level = 4 # TODO you can change


def clean_data(dataset_path_to_clean):
    """
        Print on file the dataset cleaned, in this case remove all columns normalized
    :param dataset_path_to_clean:
    :return:
    """
    time_series = pd.read_csv(dataset_path)
    time_series = time_series.loc[0:len(time_series), "Product_Code":"W51"]
    time_series.to_csv(dataset_path_to_clean.replace(".csv", "_Final.csv"), index=False)



def find_tuple_with_maximum_ncp(fixed_tuple, time_series, key_fixed_tuple, maximum_value, minimum_value):
    """
    By scanning all tuples once, we can find tuple t1 that maximizes NCP(fixed_tuple, t1)
    :param fixed_tuple:
    :param time_series:
    :param key_fixed_tuple:
    :return:
    """
    max_value = 0
    tuple_with_max_ncp = None
    for key, value in time_series.items():
        if key != key_fixed_tuple:
            ncp = compute_normalized_certainty_penalty_on_ai([fixed_tuple, time_series[key]], maximum_value, minimum_value)
            if ncp >= max_value:
                tuple_with_max_ncp = key
    return tuple_with_max_ncp


def k_anonymity_top_down_approach(time_series=None, k_value=None, columns_list=None, maximum_value=None,
                                  minimum_value=None, time_series_k_anonymized=None):
    """
    k-anonymity based on work of Xu et al. 2006,
    Utility-Based Anonymization for Privacy Preservation with Less Information Loss
    :param time_series:
    :param k_value:
    :return:
    """
    if len(time_series) < 2*k_value:
        logger.info("End Recursion")
        time_series_k_anonymized.append(time_series)
        return
    else:
        # TODO compute max and minumum_value for each recursive methods
        # partition time_series into two exclusive subsets time_series_1 and time_series_2
        # such that time_series_1 and time_series_2 are more local than time_series,
        # and either time_series_1 or time_series_2 have at least k tuples
        logger.info("Start Partition with size {}".format(len(time_series)))
        keys = list(time_series.keys())
        rounds = 3

        # pick random tuple
        random_tuple = keys[random.randint(0, len(keys) - 1)]
        logger.info("Get random tuple (u1) {}".format(random_tuple))
        group_u = dict()
        group_v = dict()
        group_u[random_tuple] = time_series[random_tuple]
        del time_series[random_tuple]
        last_row = random_tuple
        for round in range(0, rounds*2 - 1):
            if len(time_series) > 0:
                if round % 2 == 0:
                    v = find_tuple_with_maximum_ncp(group_u[last_row], time_series, last_row, maximum_value, minimum_value)
                    logger.info("{} round: Find tuple (v) that has max ncp {}".format(round +1,v))

                    group_v[v] = time_series[v]
                    last_row = v
                    del time_series[v]
                else:
                    u = find_tuple_with_maximum_ncp(group_v[last_row], time_series, last_row, maximum_value, minimum_value)
                    logger.info("{} round: Find tuple (u) that has max ncp {}".format(round+1, u))
                    group_u[u] = time_series[u]
                    last_row = u
                    del time_series[u]

        # Now Assigned to group with lower uncertain penality
        index_keys_time_series = [x for x in range(0, len(list(time_series.keys())))]
        random.shuffle(index_keys_time_series)
        # add random row to group with lower NCP
        keys = [list(time_series.keys())[x] for x in index_keys_time_series]
        for key in keys:
            row_temp = time_series[key]
            group_u_values = list(group_u.values())
            group_v_values = list(group_v.values())
            group_u_values.append(row_temp)
            group_v_values.append(row_temp)

            ncp_u = compute_normalized_certainty_penalty_on_ai(group_u_values, maximum_value, minimum_value)
            ncp_v = compute_normalized_certainty_penalty_on_ai(group_v_values, maximum_value, minimum_value)

            if ncp_v < ncp_u:
                group_v[key] = row_temp
            else:
                group_u[key] = row_temp
            del time_series[key]

        logger.info("Group u: {}, Group v: {}".format(len(group_u), len(group_v)))
        if len(group_u) > k_value:
            # recursive partition group_u
            k_anonymity_top_down_approach(time_series=group_u, k_value=k_value, columns_list=columns_list,
                                          maximum_value=maximum_value, minimum_value=minimum_value,
                                          time_series_k_anonymized=time_series_k_anonymized)
        else:
            time_series_k_anonymized.append(group_u)

        if len(group_v) > k_value:
            # recursive partition group_v

            k_anonymity_top_down_approach(time_series=group_v, k_value=k_value, columns_list=columns_list,
                                          maximum_value=maximum_value, minimum_value=minimum_value,
                                          time_series_k_anonymized=time_series_k_anonymized)
        else:
            time_series_k_anonymized.append(group_v)


# TODO check if |Ai| should be calculate on original table or not
def compute_normalized_certainty_penalty_on_ai(table=None, maximum_value=None, minimum_value=None):
    """
    Compute NCP(T)
    :param table:
    :return:
    """
    z_1 = list()
    y_1 = list()
    a = list()
    for index_attribute in range(0, len(table[0])):
        temp_z1 = 0
        temp_y1 = float('inf')
        for row in table:
            if row[index_attribute] > temp_z1:
                temp_z1 = row[index_attribute]
            if row[index_attribute] < temp_y1:
                temp_y1 = row[index_attribute]
        z_1.append(temp_z1)
        y_1.append(temp_y1)
        a.append(abs(maximum_value[index_attribute] - minimum_value[index_attribute]))
    ncp_t = 0
    for index in range(0, len(z_1)):
        try:
            ncp_t += (z_1[index] - y_1[index]) / a[index]
        except ZeroDivisionError:
            ncp_t += 0
    ncp_T = len(table)*ncp_t
    return ncp_T


def get_list_min_and_max_from_table(table):
    """
        From a table get a list of maximum and minimum value of each attribut
    :param table:
    :return: list_of_minimum_value, list_of_maximum_value
    """

    attributes_maximum_value = table[0]
    attributes_minimum_value = table[0]

    for row in range(1, len(table)):
        for index_attribute in range(0, len(table[row])):
            if table[row][index_attribute] > attributes_maximum_value[index_attribute]:
                attributes_maximum_value[index_attribute] = table[row][index_attribute]
            if table[row][index_attribute] < attributes_minimum_value[index_attribute]:
                attributes_minimum_value[index_attribute] = table[row][index_attribute]

    return attributes_minimum_value, attributes_maximum_value

def main(k_value=None, p_value=None, paa_value=None, dataset_path=None):
    """

    :param k_value:
    :param p_value:
    :param dataset_path:
    :return:
    """
    if os.path.isfile(dataset_path):
        # read time_series_from_file
        time_series = pd.read_csv(dataset_path)

        # get columns name
        columns = list(time_series.columns)
        columns.pop(0)  # remove product code
        # save all maximum value for each attribute
        attributes_maximum_value = list()
        attributes_minimum_value = list()
        for column in columns:
            attributes_maximum_value.append(time_series[column].max())
            attributes_minimum_value.append(time_series[column].min())
        time_series_dict = dict()

        # save dict file instead pandas
        for index, row in time_series.iterrows():
            time_series_dict[row["Product_Code"]] = list(row["W0":"W51"])

        # start k_anonymity_top_down
        time_series_k_anonymized = list()
        time_series_dict_copy = time_series_dict.copy()
        logger.info("Start k-anonymity top down approach")
        k_anonymity_top_down_approach(time_series=time_series_dict_copy, k_value=k_value, columns_list=columns,
                                      maximum_value=attributes_maximum_value, minimum_value=attributes_minimum_value,
                                      time_series_k_anonymized=time_series_k_anonymized)
        logger.info("End k-anonymity top down approach")


        logger.info("Start node splitting for each groups")
        # TODO
        logger.info("End node splitting for each groups")

        logger.info("Save dataset anonymized")
        # TODO
        
if __name__ == "__main__":

    if len(sys.argv) == 5:

        k_value = int(sys.argv[1])
        p_value = int(sys.argv[2])
        paa_value = int(sys.argv[3])
        dataset_path = sys.argv[4]
        if k_value > p_value:
            main(k_value=k_value, p_value=p_value, paa_value=paa_value, dataset_path=dataset_path)
        else:
            print("[*] Usage: python kp-anonymity.py k_value p_value paa_value dataset.csv")
            print("[*] k_value should be greater than p_value")
    else:
        print("[*] Usage: python kp-anonymity.py k_value p_value paa_value dataset.csv")