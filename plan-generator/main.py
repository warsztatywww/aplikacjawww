#!/usr/bin/python3
# flake8: noqa
from datetime import date

import argparse
import logging

from model import *
from optimization import OptimizationParams, find_plan
from presentation import pretty_print_plan, print_old_format
from evaluator import PlanEvaluator
    
wwww_19_blocks = [
    # set 1
    Block(block_id=1, name="RANO", start=date(2023, 7, 26), end=date(2023, 7, 28)),
    Block(block_id=2, name="POPOŁUDNIE", start=date(2023, 7, 26), end=date(2023, 7, 28)),

    # set 2
    Block(block_id=3, name="RANO", start=date(2023, 7, 30), end=date(2023, 8, 1)),
    Block(block_id=4, name="POPOŁUDNIE", start=date(2023, 7, 30), end=date(2023, 8, 1)),

    # set 3
    Block(block_id=5, name="RANO", start=date(2023, 8, 2), end=date(2023, 8, 4)),
    Block(block_id=6, name="POPOŁUDNIE", start=date(2023, 8, 2), end=date(2023, 8, 4)),
]

wwww_22_blocks = [
    # set 1
    Block(block_id=1, name="RANO", start=date(2026, 8, 5), end=date(2026, 4, 7)),
    Block(block_id=2, name="POPOŁUDNIE", start=date(2026, 8, 5), end=date(2026, 8, 7)),

    # set 2
    Block(block_id=3, name="RANO", start=date(2026, 8, 9), end=date(2026, 8, 11)),
    Block(block_id=4, name="POPOŁUDNIE", start=date(2026, 8, 9), end=date(2026, 8, 11)),

    # set 3
    Block(block_id=5, name="RANO", start=date(2026, 8, 13), end=date(2026, 8, 15)),
    Block(block_id=6, name="POPOŁUDNIE", start=date(2026, 8, 13), end=date(2026, 8, 15)),
]

blocks = wwww_22_blocks

optimization_params = OptimizationParams(
    initial_temperature=1000.0,
    final_temperature=0.1,
    cooling_rate=0.95,
    annealing_runs=100
)

def evaluate_existing_plan(camp_info, plan_path):
    with open(plan_path, "r") as f:
        plan = json.load(f)
    plan = { i+1: wids for i, wids in enumerate(plan) }
    plan_score = PlanEvaluator(camp_info).evaluate(plan)
    pretty_print_plan(plan, camp_info, plan_score)
    

def parse_arguments():
    """Parse command line arguments.

    Returns:
        Parsed arguments object
    """
    parser = argparse.ArgumentParser(description="Workshop Plan Generator")

    parser.add_argument("data_file", help="JSON file with workshop and user data")
    parser.add_argument("--plan", "-p", help="JSON string or file path of an existing plan to evaluate")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()

    camp_info = load_camp_info(args.data_file, blocks)
    
    logging.basicConfig(level=logging.INFO)

    if args.plan:
        evaluate_existing_plan(camp_info, args.plan)
    else:
        plan, score = find_plan(camp_info, optimization_params)
        pretty_print_plan(plan, camp_info, score)
        print_old_format(plan)