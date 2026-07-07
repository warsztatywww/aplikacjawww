from abc import ABC, abstractmethod

from model import *
from typing import Tuple, Dict

@dataclass
class PlanScore:
    penalty: int
    empty_blocks: int
    user_empty_blocks: Dict[UserId, int]
    workshop_collisions: Dict[WorkshopId, int]

    def total_penalty(self) -> int:
        return self.penalty

    def collisions(self):
        return sum(self.workshop_collisions.values()) // 2 # Each collision is counted twice

def participant_block_workshops(camp_info: CampInfo, plan: Plan):
    participant_workshops = {
        (uid, block_id): []
        for uid in camp_info.users
        for block_id in camp_info.blocks.keys()
    }
    for block_id, workshop_ids in plan.items():
        for wid in workshop_ids:
            for participant_id in camp_info.workshop_participants(wid):
                participant_workshops[participant_id, block_id].append(wid)
    return participant_workshops

class Metric(ABC):
    @abstractmethod
    def evaluate(plan: Plan) -> (int, dict):
        '''
        Evaluate plan and return penalty and relevant scores
        '''
        pass

class CollisionMetric(Metric):
    '''
    Cost of collisions (participants having two of their selections in the same block).

    '''
    def __init__(self, camp_info: CampInfo):
        self.camp_info = camp_info

    def evaluate(self, plan: Plan) -> (int, dict):
        collision_penalty, collisions = self.evaluate_collisions(plan)
        return collision_penalty, collisions
        

    def evaluate_collisions(self, plan: Plan) -> Tuple[int, Dict[WorkshopId, int]]:
        # We prefer to have more workshops with fewer collisions than fewer workshops with more collisions.
        # Therefore the penalty is sum of squares of the collisions per workshop.
        collisions = self.count_collisions(plan)
        penalty = sum(c ** 2 for c in collisions.values())
        return penalty, collisions

    def count_collisions(self, plan: Plan) -> Dict[WorkshopId, int]:
        # A collision occurs when a participant has two workshops in the same block
        participants_workshops = participant_block_workshops(self.camp_info, plan)
        collisions = {wid: 0 for wid in self.camp_info.workshops.keys()}
        for workshops in participants_workshops.values():
            for wid in workshops:
                collisions[wid] += len(workshops) - 1 # each additional workshop in the same block is a collision

        return collisions 


class ParticipantEmptyBlockMetric(Metric):
    '''
    Penalty of empty blocks - people having nothing to do during some block i.e. they have no enlisted workshop and no lectured workshop.
    '''
    def __init__(self, camp_info: CampInfo):
        self.camp_info = camp_info

    def evaluate(self, plan: Plan):
        participant_workshops = participant_block_workshops(self.camp_info, plan)
        empty_blocks = { uid : 0 for uid in self.camp_info.users }

        for user_id in self.camp_info.users:
            always_empty_blocks = len(self.camp_info.blocks) - self.attendable_block_count(user_id)
            empty_blocks[user_id] = self.empty_blocks(user_id, plan, participant_workshops) - always_empty_blocks

        penalty = sum(empty_blocks.values()) ** 2
        return penalty, empty_blocks    
    
    def empty_blocks(self, user_id: UserId, plan: Plan, participant_workshops):
        empty_blocks = 0
        for block_id in self.camp_info.blocks.keys():
            if len(participant_workshops[user_id, block_id]) == 0:
                empty_blocks += 1
        return empty_blocks

    def attendable_block_count(self, user_id: UserId) -> int:
        lectured_workshop_count = len(self.camp_info.user_lectured_workshops(user_id))
        enlisted_workshop_count = len(self.camp_info.user_enlisted_workshops(user_id))

        return min(len(self.camp_info.blocks), lectured_workshop_count + enlisted_workshop_count)


class PlanEvaluator:
    def __init__(self, camp_info: CampInfo):
        self.camp_info = camp_info
        self.collision_metric = CollisionMetric(camp_info)
        self.empty_block_metric = ParticipantEmptyBlockMetric(camp_info)

    def evaluate(self, plan: Plan) -> PlanScore:
        collision_penalty, collisions = self.collision_metric.evaluate(plan)
        empty_blocks_penalty, empty_blocks = self.empty_block_metric.evaluate(plan)
        empty_blocks_count = sum(empty_blocks.values())
        
        penalty = collision_penalty + empty_blocks_penalty
        return PlanScore(
            penalty=penalty, 
            empty_blocks=empty_blocks_count,
            user_empty_blocks=empty_blocks,
            workshop_collisions=collisions
        )

