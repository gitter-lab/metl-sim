#!/bin/bash

awk -F", " '{if ($2 == "False") print $1}' "../data/remodel_checks.csv"  > straggers_list.txt
