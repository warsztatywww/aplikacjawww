import math
import random
from typing import Tuple
import logging

import tqdm


from model import *
from evaluator import PlanEvaluator, PlanScore
from validator import Validator
from mutator import PlanMutator


log = logging.getLogger(__name__)

@dataclass
class OptimizationParams:
    initial_temperature: float
    final_temperature: float
    cooling_rate: float
    annealing_runs: int

def random_plan(camp_info: CampInfo) -> Plan:
    '''
    Generate a random plan that does not have to be valid.
    '''
    workshop_ids = list(camp_info.workshops.keys())
    plan = {block_id: [] for block_id in camp_info.blocks.keys()}
    for workshop_id in workshop_ids:
        block_id = random.choice(camp_info.blocks_feasible_for_workshop(workshop_id))
        plan[block_id].append(workshop_id)
    return plan

VALID_PLAN_GENERATION_ATTEMPTS = 1000
VALID_PLAN_MUTATION_ATTEMPTS = 1000

def random_correct_plan(camp_info: CampInfo, validator: Validator) -> Plan:
    '''
    Generate a random plan and ensure it is valid.
    '''
    for _ in range(VALID_PLAN_GENERATION_ATTEMPTS):
        plan = random_plan(camp_info)
        if validator.is_plan_valid(plan):
            return plan

def should_accept(current_score: PlanScore, new_score: PlanScore, temperature: float) -> bool:
    if new_score.total_penalty() <= current_score.total_penalty():
        return True
    else:
        # accept with a probability based on the score difference and temperature
        penalty_diff = new_score.total_penalty() - current_score.total_penalty()
        acceptance_probability = min(1, math.exp(-penalty_diff / temperature))

        return random.random() < acceptance_probability

def mutate_plan(plan: Plan, mutator: PlanMutator, validator: Validator) -> Plan:
    for _ in range(VALID_PLAN_MUTATION_ATTEMPTS):
        new_plan = mutator.mutate(plan)
        if validator.is_plan_valid(new_plan):
            return new_plan

def run_annealing(evaluator: PlanEvaluator, mutator: PlanMutator, validator: Validator, initial_plan: Plan, optimization_params: OptimizationParams) -> Tuple[Plan, PlanScore]:
    current_plan = initial_plan
    current_score = evaluator.evaluate(current_plan)

    best_plan = current_plan 
    best_score = current_score

    temperature = optimization_params.initial_temperature
    cooling_rate = optimization_params.cooling_rate

    while temperature > optimization_params.final_temperature:
        new_plan = mutate_plan(current_plan, mutator, validator)
        new_score = evaluator.evaluate(new_plan)

        if should_accept(current_score, new_score, temperature):
            current_plan = new_plan
            current_score = new_score

        if new_score.total_penalty() < best_score.total_penalty():
            best_plan = new_plan
            best_score = new_score

        temperature *= cooling_rate
    
    return best_plan, best_score


def find_plan(camp_info: CampInfo, optimization_params: OptimizationParams) -> Tuple[Plan, PlanScore]:
    evaluator = PlanEvaluator(camp_info)
    mutator = PlanMutator(camp_info)
    validator = Validator(camp_info)

    best_plan, best_score = None, None
    
    log.info(f"Starting optimization with {optimization_params.annealing_runs} runs.")
    for _ in tqdm.tqdm(range(optimization_params.annealing_runs)):
        plan = random_correct_plan(camp_info, validator)
        plan, score = run_annealing(evaluator, mutator, validator, plan, optimization_params)
        log.debug(f"Score: {score.total_penalty()} ; best: {best_score.total_penalty() if best_score else None}")
        if best_plan is None or score.total_penalty() < best_score.total_penalty():
            best_plan = plan
            best_score = score

    return best_plan, best_score