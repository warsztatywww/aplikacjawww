from model import *

class Validator:
    '''
    Validator checks plan against hard constraints that cannot be violated:
    - there are no empty blocks
    - lecturers have at most one workshop in each block
    - lecturers are present during their workshop
    '''
    def __init__(self, camp_info: CampInfo, blocks: Blocks):
        self.camp_info = camp_info
        self.blocks = blocks

    def is_plan_valid(self, plan: Plan) -> bool:
        return all(self.is_block_valid(block_id, workshop_ids) for block_id, workshop_ids in plan.items())

    def is_block_valid(self, block_id: BlockId, workshop_ids: List[WorkshopId]) -> bool:
        return (
            len(workshop_ids) > 0 
            and self.lecturers_present_during_workshops(block_id, workshop_ids)
            and self.lecturers_have_no_collisions(workshop_ids)
        )

    def lecturers_have_no_collisions(self, workshop_ids: List[WorkshopId]):
        lecturers_with_workshops = set()
        for workshop_id in workshop_ids:
            workshop = self.camp_info.workshops[workshop_id]
            for lecturer_id in workshop.lecturers:
                if lecturer_id in lecturers_with_workshops:
                    return False
                else:
                    lecturers_with_workshops.add(lecturer_id)
        return True

    def lecturers_present_during_workshops(self, block_id, workshop_ids): 
        return all(
            self.lecturers_present_during_block(block_id, workshop_id)
            for workshop_id in workshop_ids
        )

    def lecturers_present_during_block(self, block_id: BlockId, workshop_id: WorkshopId) -> bool:
        workshop = self.camp_info.workshops[workshop_id]
        return all(self.user_present_during_block(block_id, lecturer_id) for lecturer_id in workshop.lecturers)
    
    def user_present_during_block(self, block_id: BlockId, user_id: UserId) -> bool:
        block = self.blocks.blocks[block_id]
        attendance = self.camp_info.attendance[user_id]
        return block.feasible_for_attendance(attendance)
