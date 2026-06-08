from model import *
from typing import Tuple, Dict

@dataclass
class PlanScore:
    penalty: int
    collisions: int
    empty_blocks: int
    user_empty_blocks: Dict[UserId, int]
    workshop_collisions: Dict[WorkshopId, int]

    def total_penalty(self) -> int:
        return self.penalty

class PlanEvaluator:
    # evaluates the plan against the constraints
    def __init__(self, camp_info: CampInfo, blocks: Blocks):
        self.camp_info = camp_info
        self.blocks = blocks

    def evaluate(self, plan: Plan) -> PlanScore:
        collision_penalty, collisions = self.evaluate_collisions(plan)
        collisions_count = sum(collisions.values()) / 2 # each collision is counted twice (for both workshops)

        empty_blocks_penalty, empty_blocks = self.evaluate_empty_blocks(plan)
        empty_blocks_count = sum(empty_blocks.values())
        
        penalty = collision_penalty + empty_blocks_penalty
        return PlanScore(
            penalty=penalty, 
            collisions=collisions_count, 
            empty_blocks=empty_blocks_count,
            user_empty_blocks=empty_blocks,
            workshop_collisions=collisions
        )

    def evaluate_collisions(self, plan: Plan) -> Tuple[int, Dict[WorkshopId, int]]:
        # We prefer to have more workshop with fewer collisions than fewer workshops with more collisions.
        # Therefore the penalty is sum of squares of the collisions per workshop.
        collisions = self.count_collisions(plan)
        penalty = sum(c ** 2 for c in collisions.values())
        return penalty, collisions

    def evaluate_empty_blocks(self, plan: Plan) -> int:
        # We want to avoid empty blocks for participants - i.e. everyone should have at least one workshop in each block they attend
        participant_workshops = self.participant_workshops(plan)
        empty_blocks = { uid : 0 for uid in self.camp_info.users }

        for participant_id in self.camp_info.users:
            for block_id in self.blocks.blocks.keys():
                if len(participant_workshops[participant_id, block_id]) == 0:
                    empty_blocks[participant_id] += 1
            always_empty_blocks = max(0, len(self.blocks.blocks) - len(self.camp_info.user_workshops(participant_id)))
            empty_blocks[participant_id] -= always_empty_blocks

        penalty = sum(empty_blocks.values()) ** 2
        return penalty, empty_blocks        

    def count_collisions(self, plan: Plan) -> Dict[WorkshopId, int]:
        # A collision occurs when a participant has two workshops in the same block
        # Count collisions for each workshop
        # Also we don't count collisions for lecturers, only for participants
        participants_workshops = self.participant_workshops(plan)
        collisions = {wid: 0 for wid in self.camp_info.workshops.keys()}
        for workshops in participants_workshops.values():
            for wid in workshops:
                collisions[wid] += len(workshops) - 1 # each additional workshop in the same block is a collision

        return collisions 

    def participant_workshops(self, plan: Plan):
        participant_workshops = {
            (uid, block_id): []
            for uid in self.camp_info.users
            for block_id in self.blocks.blocks.keys()
        }
        for block_id, workshop_ids in plan.items():
            for wid in workshop_ids:
                for participant_id in self.camp_info.workshop_participants(wid):
                    participant_workshops[participant_id, block_id].append(wid)
        return participant_workshops
