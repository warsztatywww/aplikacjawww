#!/usr/bin/python3
# flake8: noqa
from datetime import date

import argparse

from model import *
from optimization import OptimizationParams, find_plan
from presentation import pretty_print_plan, print_old_format
from evaluator import PlanEvaluator
    
blocks = {
    1: Block(block_id=1, name="RANO", start=date(2023, 7, 25), end=date(2023, 7, 28)),
    2: Block(block_id=2, name="POPOŁUDNIE", start=date(2023, 7, 25), end=date(2023, 7, 28)),
    3: Block(block_id=3, name="RANO", start=date(2023, 7, 30), end=date(2023, 8, 1)),
    4: Block(block_id=4, name="POPOŁUDNIE", start=date(2023, 7, 30), end=date(2023, 8, 1)),
    5: Block(block_id=5, name="RANO", start=date(2023, 8, 2), end=date(2023, 8, 4)),
    6: Block(block_id=6, name="POPOŁUDNIE", start=date(2023, 8, 2), end=date(2023, 8, 4)),
}

optimization_params = OptimizationParams(
    initial_temperature=1000.0,
    final_temperature=0.1,
    cooling_rate=0.95,
    annealing_runs=100
)

def evaluate_existing_plan(camp_info, blocks, plan_path):
    with open(plan_path, "r") as f:
        plan = json.load(f)
    plan = { i+1: wids for i, wids in enumerate(plan) }
    plan_score = PlanEvaluator(camp_info, blocks).evaluate(plan)
    pretty_print_plan(plan, camp_info, blocks, plan_score)
    

def parse_arguments():
    """Parse command line arguments.

    Returns:
        Parsed arguments object
    """
    parser = argparse.ArgumentParser(description="Workshop Plan Generator")

    # Required arguments
    #parser.add_argument("data_file", help="JSON file with workshop and user data")

    # Optional arguments
    parser.add_argument("--plan", "-p", help="JSON string or file path of an existing plan to evaluate")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()

    camp_info = load_camp_info("www19-data-for-plan.json")
    blocks = Blocks.from_blocks_and_camp_info(blocks, camp_info)

    if args.plan:
        evaluate_existing_plan(camp_info, blocks, args.plan)
    else:
        plan, score = find_plan(camp_info, blocks, optimization_params)
        pretty_print_plan(plan, camp_info, blocks, score)
        print_old_format(plan)