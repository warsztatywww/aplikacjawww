from model import *
import random
import copy

class PlanMutator:
    def __init__(self, camp_info: CampInfo):
        self.camp_info = camp_info

    def mutate(self, plan: Plan) -> Plan:
        if random.random() < 0.5:
            return self.swap_random_workshops(plan)
        else:
            return self.move_random_workshop(plan)

    def swap_random_workshops(self, plan: Plan) -> Plan:
        new_plan = copy.deepcopy(plan)
        w1, w2 = random.sample(self.camp_info.workshop_ids, 2)
        b1 = get_workshop_block(plan, w1)
        b2 = get_workshop_block(plan, w2)
        if b1 != b2:
            new_plan[b1] = [w2 if wid == w1 else wid for wid in new_plan[b1]]
            new_plan[b2] = [w1 if wid == w2 else wid for wid in new_plan[b2]]
        return new_plan

    def move_random_workshop(self, plan: Plan) -> Plan:
        new_plan = copy.deepcopy(plan)
        w1 = random.choice(list(self.camp_info.workshop_ids))
        b1 = get_workshop_block(plan, w1)
        b2 = random.choice(list(plan.keys()))
        if b2 != b1:
            new_plan[b1] = [wid for wid in new_plan[b1] if wid != w1]
            new_plan[b2].append(w1)
        return new_plan